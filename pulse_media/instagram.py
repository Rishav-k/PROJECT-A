"""
instagram.py — Pulse Media Instagram Posting Module
Posts AI-generated news cards using instagrapi (no Facebook Developer App needed).

SETUP:
  pip3 install instagrapi

  Add to .env:
    INSTAGRAM_FINPULSE_USERNAME=finpulse.daily
    INSTAGRAM_FINPULSE_PASSWORD=yourpassword

Usage:
  python3 instagram.py                        # post top article for finpulse
  python3 instagram.py --page techpulse       # specific page
  python3 instagram.py --dry-run              # preview only, don't post
  python3 instagram.py --page all --dry-run   # preview all 4 pages
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

# ─────────────────────────────────────────────
# ENV LOADER
# ─────────────────────────────────────────────

import env_loader  # noqa: F401 — loads .env on import

# ─────────────────────────────────────────────
# SESSION CACHE DIR (saves login session so we
# don't re-login every single post)
# ─────────────────────────────────────────────

SESSION_DIR = os.path.join(os.path.dirname(__file__), "data", "sessions")
os.makedirs(SESSION_DIR, exist_ok=True)


# ─────────────────────────────────────────────
# CREDENTIALS
# ─────────────────────────────────────────────

def get_credentials(page: str) -> dict:
    key = page.upper()
    username = os.environ.get(f"INSTAGRAM_{key}_USERNAME", "")
    password = os.environ.get(f"INSTAGRAM_{key}_PASSWORD", "")
    return {"username": username, "password": password}


def credentials_configured(page: str) -> bool:
    creds = get_credentials(page)
    return bool(
        creds["username"] and creds["username"] != "REPLACE_ME" and
        creds["password"] and creds["password"] != "REPLACE_ME"
    )


# ─────────────────────────────────────────────
# INSTAGRAM CLIENT (instagrapi)
# ─────────────────────────────────────────────

def get_client(page: str, verification_code: Optional[str] = None):
    """
    Get a logged-in instagrapi Client for the given page.
    Saves session to disk so we only login once.
    """
    try:
        from instagrapi import Client
        from instagrapi.exceptions import LoginRequired, TwoFactorRequired
    except ImportError:
        print("❌ instagrapi not installed.")
        print("   Run: pip3 install instagrapi")
        sys.exit(1)

    creds        = get_credentials(page)
    username     = creds["username"]
    password     = creds["password"]
    session_file = os.path.join(SESSION_DIR, f"{page}_session.json")

    cl = Client()
    cl.delay_range = [2, 5]  # random delay between actions (looks human)

    # Try to reuse saved session first
    if os.path.exists(session_file):
        try:
            cl.load_settings(session_file)
            cl.login(username, password)
            cl.get_timeline_feed()  # test if session is still valid
            print(f"  🔑 Session loaded for {username}")
            return cl
        except Exception:
            print(f"  🔄 Session expired — logging in fresh...")
            try:
                os.remove(session_file)
            except Exception:
                pass

    # Auto-generate TOTP code if 2FA secret seed is in .env
    two_fa_seed = os.environ.get(f"INSTAGRAM_{page.upper()}_2FA_SEED", "").strip() or os.environ.get("INSTAGRAM_2FA_SEED", "").strip()
    if not verification_code and two_fa_seed:
        try:
            import pyotp
            verification_code = pyotp.TOTP(two_fa_seed).now()
            print(f"  🔐 Generated TOTP 2FA code automatically from seed: {verification_code}")
        except Exception as e:
            print(f"  ⚠️ Error generating TOTP: {e}")

    # Fresh login
    print(f"  🔑 Logging in as {username}...")
    try:
        if verification_code:
            cl.login(username, password, verification_code=verification_code)
        else:
            cl.login(username, password)
        cl.dump_settings(session_file)
        print(f"  ✅ Logged in and session saved to {session_file}")
        return cl
    except Exception as e:
        err_msg = str(e)
        if "TwoFactorRequired" in str(type(e)) or "two-factor" in err_msg.lower() or "verification_code" in err_msg.lower():
            raise RuntimeError(
                f"TWO_FACTOR_REQUIRED: Instagram account @{username} has 2FA enabled. "
                f"Run `python3 instagram.py --login {page} <CODE>` or enter the 6-digit code from SMS / Authenticator app."
            ) from e
        raise


# ─────────────────────────────────────────────
# IMAGE CONVERSION: PNG → JPEG
# (Instagram only accepts JPEG)
# ─────────────────────────────────────────────

def png_to_jpeg(png_path: str) -> str:
    """Convert PNG to JPEG. Returns path to JPEG file.
    Uses non-progressive, no-optimize settings — required by instagrapi.
    """
    from PIL import Image
    jpeg_path = png_path.replace(".png", ".jpg")
    img = Image.open(png_path).convert("RGB")
    # Must be: progressive=False, optimize=False — instagrapi fails otherwise
    img.save(jpeg_path, "JPEG", quality=90, optimize=False, progressive=False)
    size_kb = os.path.getsize(jpeg_path) // 1024
    print(f"  🔄 Converted to JPEG ({size_kb}KB)")
    return jpeg_path


# ─────────────────────────────────────────────
# POST PHOTO
# ─────────────────────────────────────────────

def post_photo(page: str, image_path: str, caption: str) -> str:
    """
    Post a photo to Instagram. Returns the media ID.
    image_path should be a local JPEG file.
    Tries album_upload first (different API endpoint, more reliable for new accounts),
    falls back to photo_upload.
    """
    from pathlib import Path
    from PIL import Image

    # Re-save as clean non-progressive JPEG
    clean_path = image_path.replace(".jpg", "_clean.jpg")
    img = Image.open(image_path).convert("RGB")
    img.save(clean_path, "JPEG", quality=90,
             optimize=False, progressive=False, subsampling=0)
    print(f"  🖼  Clean JPEG ready: {Path(clean_path).name}")

    cl = get_client(page)

    # Try album_upload first — uses a different configure endpoint,
    # avoids "no media payload" on new accounts
    try:
        print("  📤 Trying album_upload (single-image carousel)...")
        media = cl.album_upload([Path(clean_path)], caption)
        post_id = str(media.id)
        print(f"  🎉 Posted via album_upload! Media ID: {post_id}")
        return post_id
    except Exception as e1:
        print(f"  ⚠️  album_upload failed: {e1}")

    # Fallback: standard photo_upload
    try:
        print("  📤 Trying photo_upload fallback...")
        media = cl.photo_upload(Path(clean_path), caption)
        post_id = str(media.id)
        print(f"  🎉 Posted via photo_upload! Media ID: {post_id}")
        return post_id
    except Exception as e2:
        raise RuntimeError(
            f"Both upload methods failed.\n"
            f"  album_upload: {e1}\n"
            f"  photo_upload: {e2}\n\n"
            f"If errors mention 'media payload' or 'feedback_required', "
            f"Instagram is blocking this new account via API. "
            f"Fix: open the app manually, make a few likes/follows, then retry."
        ) from e2


# ─────────────────────────────────────────────
# POST CAROUSEL (multi-image album)
# ─────────────────────────────────────────────

def post_carousel(page: str, slide_paths: list, caption: str) -> str:
    """
    Post a multi-image carousel to Instagram.

    Args:
        page:        page name (finpulse, techpulse, etc.)
        slide_paths: list of Path or str pointing to 1080x1080 JPEGs
        caption:     full caption text

    Returns:
        Instagram media ID string
    """
    from pathlib import Path as _Path
    from PIL import Image as _Image

    if not slide_paths:
        raise ValueError("slide_paths is empty")

    # Ensure every slide is a clean non-progressive JPEG
    clean_paths = []
    for i, sp in enumerate(slide_paths):
        sp = str(sp)
        clean = sp.replace(".jpg", "_clean.jpg").replace(".jpeg", "_clean.jpg")
        if not clean.endswith("_clean.jpg"):
            clean = sp + "_clean.jpg"
        img = _Image.open(sp).convert("RGB")
        img.save(clean, "JPEG", quality=92, optimize=False, progressive=False, subsampling=0)
        clean_paths.append(_Path(clean))
        print(f"  🖼  Slide {i+1}/{len(slide_paths)}: {_Path(clean).name}")

    cl = get_client(page)

    print(f"  📤 Uploading {len(clean_paths)}-slide carousel...")
    media = cl.album_upload(clean_paths, caption)
    post_id = str(media.id)
    print(f"  🎉 Carousel posted! Media ID: {post_id}")
    return post_id


def post_carousel_to_instagram(article: dict, caption: str, slide_paths: list,
                                page: str, dry_run: bool = False) -> dict:
    """
    Full carousel post flow. Returns dict with success, post_id, error.
    """
    result = {"success": False, "post_id": None, "error": None}

    if dry_run:
        print(f"\n  🔍 DRY RUN — carousel not posted")
        print(f"  📰 Article: {article.get('title','')[:65]}")
        print(f"  🖼  Slides:  {len(slide_paths)}")
        print(f"  📄 Caption: {len(caption)} chars")
        result["success"] = True
        return result

    if not credentials_configured(page):
        result["error"] = f"No credentials for {page} in .env"
        print(f"  ❌ {result['error']}")
        return result

    try:
        post_id = post_carousel(page, slide_paths, caption)
        result["post_id"] = post_id
        result["success"] = True
    except Exception as e:
        result["error"] = str(e)
        print(f"  ❌ Carousel post failed: {e}")

    return result


# ─────────────────────────────────────────────
# POST STORY
# ─────────────────────────────────────────────

def post_story(page: str, image_path: str) -> str:
    """Post an image as a Story."""
    cl    = get_client(page)
    media = cl.photo_upload_to_story(image_path)
    print(f"  📖 Story posted! ID: {media.id}")
    return str(media.id)


# ─────────────────────────────────────────────
# FULL POST FLOW
# ─────────────────────────────────────────────

def post_to_instagram(article: dict, caption: str, image_path: str,
                      page: str, dry_run: bool = False) -> dict:
    """
    Full flow: convert image → post to Instagram.
    Returns dict with success, post_id, error.
    """
    result = {"success": False, "post_id": None, "error": None}

    if dry_run:
        print(f"\n  🔍 DRY RUN — no actual post")
        print(f"  📰 Would post: {article['title'][:65]}")
        print(f"  📄 Caption: {len(caption)} chars")
        print(f"  🖼  Image: {os.path.basename(image_path)}")
        result["success"] = True
        return result

    if not credentials_configured(page):
        result["error"] = f"No credentials for {page} in .env"
        print(f"  ❌ {result['error']}")
        return result

    try:
        # Convert PNG → JPEG
        jpeg_path = png_to_jpeg(image_path)

        # Post to Instagram
        post_id = post_photo(page, jpeg_path, caption)
        result["post_id"]  = post_id
        result["success"]  = True

    except Exception as e:
        result["error"] = str(e)
        print(f"  ❌ Post failed: {e}")

    return result


# ─────────────────────────────────────────────
# DB UPDATE
# ─────────────────────────────────────────────

def update_db(article_id: int, page: str, post_id: str, status: str = "posted"):
    try:
        from database.schema import get_connection
        conn = get_connection()
        conn.execute("""
            UPDATE posts
               SET instagram_post_id = ?,
                   status            = ?,
                   posted_at         = datetime('now')
             WHERE article_id = ? AND page = ?
        """, (post_id, status, article_id, page))
        conn.commit()
        conn.close()
        print(f"  💾 DB updated — status: {status}")
    except Exception as e:
        print(f"  ⚠️  DB update skipped: {e}")


# ─────────────────────────────────────────────
# END-TO-END RUNNER (used by scheduler)
# ─────────────────────────────────────────────

def run_post_cycle(page: str, dry_run: bool = False) -> dict:
    """
    Full cycle: get article → caption → image → post
    """
    print(f"\n{'='*60}")
    print(f"🚀 POST CYCLE: {page.upper()} — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    from database.models import get_top_articles
    articles = get_top_articles(page, limit=1)
    if not articles:
        print(f"  ❌ No unposted articles for {page}")
        return {"success": False, "error": "no_articles"}

    article = articles[0]
    print(f"\n📰 {article['title'][:65]}")
    print(f"   Source: {article['source_name']}  |  Score: {article['score']}pts\n")

    # Caption
    print("🤖 Generating caption...")
    from ai import generate_caption, save_to_db as save_caption
    caption_result = generate_caption(article, page)
    if not caption_result:
        return {"success": False, "error": "caption_failed"}
    caption = caption_result["caption"]
    print(f"  ✅ {len(caption)} chars (backend: {caption_result.get('backend','?')})")
    save_caption(article, caption_result, page)

    # Image
    print("\n🎨 Generating image...")
    from image import generate_image, save_image_path
    image_path = generate_image(article, page)
    save_image_path(article.get("id", 0), image_path, page)

    # Post
    print("\n📲 Posting to Instagram...")
    result = post_to_instagram(article, caption, image_path, page, dry_run=dry_run)

    if result["success"] and not dry_run:
        update_db(article["id"], page, result.get("post_id", ""))
        print(f"\n✅ {page.upper()} posted!")
        print(f"   Post ID: {result['post_id']}")
    elif dry_run:
        print(f"\n👁  Dry run complete")

    return result


# ─────────────────────────────────────────────
# CAROUSEL CYCLE RUNNER (used by scheduler / CLI)
# ─────────────────────────────────────────────

def run_carousel_cycle(page: str, dry_run: bool = False) -> dict:
    """
    Full carousel cycle: fetch top article → generate caption → generate
    5-slide carousel → post to Instagram as album.
    """
    print(f"\n{'='*60}")
    print(f"🎠 CAROUSEL CYCLE: {page.upper()} — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    from database.models import get_top_articles
    articles = get_top_articles(page, limit=1)
    if not articles:
        print(f"  ❌ No unposted articles for {page}")
        return {"success": False, "error": "no_articles"}

    article = articles[0]
    print(f"\n📰 {article['title'][:65]}")
    print(f"   Source: {article['source_name']}  |  Score: {article['score']}pts\n")

    # Caption
    print("🤖 Generating caption...")
    from ai import generate_caption, save_to_db as save_caption
    caption_result = generate_caption(article, page)
    if not caption_result:
        return {"success": False, "error": "caption_failed"}
    caption = caption_result["caption"]
    print(f"  ✅ {len(caption)} chars (backend: {caption_result.get('backend','?')})")
    save_caption(article, caption_result, page)

    # Carousel images
    print("\n🎨 Generating carousel slides...")
    from carousel import generate_carousel
    slide_paths = generate_carousel(article, page=page, caption=caption)

    # Save first slide as the "image_path" for DB tracking
    from image import save_image_path
    save_image_path(article.get("id", 0), str(slide_paths[0]), page)

    # Post
    print("\n📲 Posting carousel to Instagram...")
    result = post_carousel_to_instagram(article, caption, slide_paths, page, dry_run=dry_run)

    if result["success"] and not dry_run:
        update_db(article["id"], page, result.get("post_id", ""))
        print(f"\n✅ {page.upper()} carousel posted!")
        print(f"   Post ID: {result['post_id']}")
    elif dry_run:
        print(f"\n👁  Dry run complete — {len(slide_paths)} slides ready")

    return result


def main():
    if "--login" in sys.argv:
        idx = sys.argv.index("--login")
        page = sys.argv[idx + 1] if len(sys.argv) > idx + 1 and not sys.argv[idx + 1].startswith("-") else "finpulse"
        code = sys.argv[idx + 2] if len(sys.argv) > idx + 2 and not sys.argv[idx + 2].startswith("-") else None
        if not code:
            code = input(f"Enter 2FA verification code (from SMS or Authenticator app) for {page} [press Enter if none]: ").strip() or None
        print(f"🔑 Logging in to Instagram for {page}...")
        try:
            cl = get_client(page, verification_code=code)
            creds = get_credentials(page)
            info = cl.user_info_by_username(creds["username"])
            print(f"🎉 Login successful! Connected as @{creds['username']} (Followers: {info.follower_count})")
            print(f"   Session saved to data/sessions/{page}_session.json")
        except Exception as e:
            print(f"❌ Login failed: {e}")
        return

    page     = "finpulse"
    dry_run  = False
    carousel = False

    for arg in sys.argv[1:]:
        if arg == "--dry-run":              dry_run  = True
        elif arg == "--carousel":           carousel = True
        elif arg.startswith("--page="):     page     = arg.split("=")[1]
        elif arg in ("finpulse","techpulse","corppulse","worldpulse","all"): page = arg

    ALL_PAGES = ["finpulse","techpulse","corppulse","worldpulse"]
    runner = run_carousel_cycle if carousel else run_post_cycle

    if page == "all":
        for p in ALL_PAGES:
            runner(p, dry_run=dry_run)
    else:
        runner(page, dry_run=dry_run)


if __name__ == "__main__":
    main()
