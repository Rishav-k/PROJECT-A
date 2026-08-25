"""
dashboard/server.py — Pulse Media Command Center Server
Run:  python3 dashboard/server.py
Open: http://localhost:8888
"""

import sys, os, json, re, threading, mimetypes, time, base64
import queue as _queue
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import env_loader  # noqa: F401 — loads .env on import

# Dashboard credentials (set DASHBOARD_USER / DASHBOARD_PASS in .env, or defaults)
_DASH_USER = os.environ.get("DASHBOARD_USER", "pulse")
_DASH_PASS = os.environ.get("DASHBOARD_PASS", "pulse2024")
_DASH_TOKEN = base64.b64encode(f"{_DASH_USER}:{_DASH_PASS}".encode()).decode()

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
from database.schema import get_connection, migrate_db

# Run migrations on every server start (safe — skips existing columns)
try:
    migrate_db()
except Exception as _me:
    print(f"⚠️  Migration warning: {_me}")

# ─────────────────────────────────────────────
# MANUAL-ONLY PROCESSING MODE
# Auto-generation is disabled to conserve credits.
# Articles are fetched and displayed; AI captions and carousels
# are generated strictly on-demand when the user clicks generate.
# ─────────────────────────────────────────────

def get_bg_status():
    """Return idle status since auto-processor is disabled."""
    return {
        "queue_size":   0,
        "active":       {},
        "active_count": 0,
        "done_count":   0,
        "errors":       {},
        "is_busy":      False,
    }

PORT     = int(os.environ.get("PORT", 8888))
IMAGES_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "output", "images"))
LOG_PATH   = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "logs", "scheduler.log"))


# ─────────────────────────────────────────────
# DATA HELPERS
# ─────────────────────────────────────────────

def get_stats():
    conn = get_connection()
    total_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    total_posted   = conn.execute("SELECT COUNT(*) FROM posts WHERE status='posted'").fetchone()[0]
    total_pending  = conn.execute("SELECT COUNT(*) FROM posts WHERE status='pending' AND image_path IS NOT NULL").fetchone()[0]
    total_errors   = conn.execute("SELECT COUNT(*) FROM errors").fetchone()[0]
    total_sources  = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    sources_ok     = conn.execute("SELECT COUNT(*) FROM sources WHERE last_status='ok'").fetchone()[0]
    per_page = conn.execute("""
        SELECT a.page,
               COUNT(a.id)                                        as total,
               SUM(a.is_posted)                                   as posted,
               COUNT(CASE WHEN p.status='pending' AND p.image_path IS NOT NULL THEN 1 END) as ready_queue
        FROM articles a
        LEFT JOIN posts p ON p.article_id = a.id
        GROUP BY a.page
    """).fetchall()
    conn.close()
    return {
        "total_articles": total_articles,
        "total_posted":   total_posted,
        "total_pending":  total_pending,
        "total_errors":   total_errors,
        "total_sources":  total_sources,
        "sources_ok":     sources_ok,
        "per_page":       [dict(r) for r in per_page],
    }

def get_pipeline_data():
    conn = get_connection()
    stages = {
        "fetched":   conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0],
        "scored":    conn.execute("SELECT COUNT(*) FROM articles WHERE score > 0").fetchone()[0],
        "captioned": conn.execute("SELECT COUNT(*) FROM posts WHERE caption IS NOT NULL AND caption != ''").fetchone()[0],
        "imaged":    conn.execute("SELECT COUNT(*) FROM posts WHERE image_path IS NOT NULL AND image_path != ''").fetchone()[0],
        "posted":    conn.execute("SELECT COUNT(*) FROM posts WHERE status='posted'").fetchone()[0],
    }
    recent = conn.execute("""
        SELECT a.id, a.title, a.source_name, a.page, a.score,
               a.fetched_at, a.is_posted, a.url,
               p.id as post_id, p.caption, p.image_path,
               p.status as post_status, p.instagram_post_id, p.created_at as post_created
        FROM articles a
        LEFT JOIN posts p ON p.article_id = a.id
        ORDER BY
            CASE WHEN p.id IS NOT NULL THEN 0 ELSE 1 END,
            CASE p.status WHEN 'posted' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END,
            a.score DESC
        LIMIT 200
    """).fetchall()
    conn.close()
    rows = []
    for r in recent:
        d = dict(r)
        # normalise image_path to just filename
        if d.get("image_path"):
            d["image_file"] = os.path.basename(d["image_path"])
            # prefer _clean.jpg → .jpg → .png for display
            stem = d["image_file"].replace("_clean.jpg","").replace(".jpg","").replace(".png","")
            for ext in ("_clean.jpg", ".jpg", ".png"):
                candidate = stem + ext
                if os.path.exists(os.path.join(IMAGES_DIR, candidate)):
                    d["image_file"] = candidate
                    break
        else:
            d["image_file"] = None
        rows.append(d)
    return {"stages": stages, "items": rows}

def get_posts_by_page(page=None, status=None, limit=30):
    conn = get_connection()
    q = """
        SELECT p.id, p.page, p.status, p.caption, p.image_path,
               p.instagram_post_id, p.created_at, p.posted_at,
               a.title, a.source_name, a.url, a.score, a.fetched_at
        FROM posts p JOIN articles a ON p.article_id = a.id
        WHERE 1=1
    """
    params = []
    if page and page != "all":
        q += " AND p.page = ?"; params.append(page)
    if status:
        q += " AND p.status = ?"; params.append(status)
    q += " ORDER BY p.created_at DESC LIMIT ?"; params.append(limit)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("image_path"):
            stem = os.path.basename(d["image_path"]).replace("_clean.jpg","").replace(".jpg","").replace(".png","")
            for ext in ("_clean.jpg", ".jpg", ".png"):
                c = stem + ext
                if os.path.exists(os.path.join(IMAGES_DIR, c)):
                    d["image_file"] = c; break
            else:
                d["image_file"] = os.path.basename(d["image_path"])
        else:
            d["image_file"] = None
        result.append(d)
    return result

def get_sources():
    conn = get_connection()
    # Join with articles to get real unique article counts (not the inflated running counter)
    rows = conn.execute("""
        SELECT s.*,
               COUNT(a.id) as real_article_count
        FROM sources s
        LEFT JOIN articles a ON a.source_name = s.display_name
        GROUP BY s.id
        ORDER BY s.page, s.last_status DESC
    """).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["total_articles"] = d["real_article_count"]  # override inflated counter
        result.append(d)
    return result

def get_source_articles_data(source_name: str, limit: int = 80):
    """
    Return articles for a source name with full pipeline status.
    Adds a pipeline_stage field and a show_likes flag for posted articles.
    """
    try:
        from database.models import get_source_articles
        articles = get_source_articles(source_name, limit)
    except Exception as e:
        return {"error": str(e), "items": []}

    now = datetime.now(timezone.utc)
    for a in articles:
        # Determine pipeline stage — check both the posts.status field AND the
        # articles.is_posted flag so they stay consistent even if one lags.
        is_posted = (a.get("post_status") == "posted") or (a.get("is_posted") == 1)
        if is_posted:
            a["pipeline_stage"] = "posted"
            pa = a.get("post_published_at") or a.get("posted_at") or ""
            try:
                dt = datetime.fromisoformat(pa.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age_days = (now - dt).total_seconds() / 86400
            except Exception:
                age_days = 0
            a["show_likes"]  = age_days >= 1
        elif a.get("image_path"):
            a["pipeline_stage"] = "image_ready"
            a["show_likes"] = False
        elif a.get("caption"):
            a["pipeline_stage"] = "captioned"
            a["show_likes"] = False
        elif a.get("post_id"):
            a["pipeline_stage"] = "creating"
            a["show_likes"] = False
        else:
            a["pipeline_stage"] = "fetched"
            a["show_likes"] = False

        # Build image_file for primary image
        if a.get("image_path"):
            stem = os.path.basename(a["image_path"]).replace("_clean.jpg","").replace(".jpg","").replace(".png","")
            for ext in ("_clean.jpg", ".jpg", ".png"):
                candidate = stem + ext
                if os.path.exists(os.path.join(IMAGES_DIR, candidate)):
                    a["image_file"] = candidate
                    break
            else:
                a["image_file"] = os.path.basename(a["image_path"])
        else:
            a["image_file"] = None

        # Build slide_files list (filenames only) from slide_paths JSON
        raw_sp = a.get("slide_paths", "[]") or "[]"
        try:
            sp_paths = json.loads(raw_sp) if isinstance(raw_sp, str) else []
        except Exception:
            sp_paths = []
        slide_files = []
        for sp in sp_paths:
            fname = os.path.basename(sp)
            # prefer _clean.jpg variant
            stem2 = fname.replace("_clean.jpg","").replace(".jpg","")
            for ext in ("_clean.jpg", ".jpg"):
                c = stem2 + ext
                if os.path.exists(os.path.join(IMAGES_DIR, c)):
                    slide_files.append(c)
                    break
            else:
                if os.path.exists(sp):
                    slide_files.append(fname)
    return {"items": articles, "source": source_name}


def get_top_news_data(page: str = "all", limit: int = 5):
    """Return top ranked news articles across segments or for a specific page."""
    try:
        from database.models import get_top_news_across_segments
        articles = get_top_news_across_segments(page, limit)
    except Exception as e:
        return {"error": str(e), "items": []}

    now = datetime.now(timezone.utc)
    for a in articles:
        is_posted = (a.get("post_status") == "posted") or (a.get("is_posted") == 1)
        if is_posted:
            a["pipeline_stage"] = "posted"
            pa = a.get("post_published_at") or a.get("posted_at") or ""
            try:
                dt = datetime.fromisoformat(pa.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age_days = (now - dt).total_seconds() / 86400
            except Exception:
                age_days = 0
            a["show_likes"]  = age_days >= 1
        elif a.get("image_path"):
            a["pipeline_stage"] = "image_ready"
            a["show_likes"] = False
        elif a.get("caption"):
            a["pipeline_stage"] = "captioned"
            a["show_likes"] = False
        elif a.get("post_id"):
            a["pipeline_stage"] = "creating"
            a["show_likes"] = False
        else:
            a["pipeline_stage"] = "fetched"
            a["show_likes"] = False

        # Image file
        if a.get("image_path"):
            stem = os.path.basename(a["image_path"]).replace("_clean.jpg","").replace(".jpg","").replace(".png","")
            for ext in ("_clean.jpg", ".jpg", ".png"):
                candidate = stem + ext
                if os.path.exists(os.path.join(IMAGES_DIR, candidate)):
                    a["image_file"] = candidate
                    break
            else:
                a["image_file"] = os.path.basename(a["image_path"])
        else:
            a["image_file"] = None

        raw_sp = a.get("slide_paths", "[]") or "[]"
        try:
            sp_paths = json.loads(raw_sp) if isinstance(raw_sp, str) else []
        except Exception:
            sp_paths = []
        slide_files = []
        for sp in sp_paths:
            fname = os.path.basename(sp)
            stem2 = fname.replace("_clean.jpg","").replace(".jpg","")
            for ext in ("_clean.jpg", ".jpg"):
                c = stem2 + ext
                if os.path.exists(os.path.join(IMAGES_DIR, c)):
                    slide_files.append(c)
                    break
            else:
                if os.path.exists(sp):
                    slide_files.append(fname)
        a["slide_files"] = slide_files

    return {"items": articles, "page": page, "count": len(articles)}


def get_workers():
    """Return all sources with live DB article/posted counts (for workers view)."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            s.id, s.name, s.display_name, s.source_type, s.page, s.feed_url,
            s.last_fetched_at, s.last_status, s.total_fetches,
            s.total_errors, s.created_at,
            COUNT(DISTINCT a.id)                                          AS real_count,
            SUM(CASE WHEN a.is_posted = 1 THEN 1 ELSE 0 END)             AS posted_count,
            SUM(CASE WHEN a.image_url  != '' AND a.image_url IS NOT NULL
                          AND a.image_url != 'null' THEN 1 ELSE 0 END)   AS with_image_count,
            MAX(a.fetched_at)                                             AS latest_article_at
        FROM sources s
        LEFT JOIN articles a ON a.source_name = s.display_name
        GROUP BY s.id
        ORDER BY s.page, s.display_name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_article_content_data(article_id: int):
    """Fetch and return full article content on demand (lazy load)."""
    conn = get_connection()
    row = conn.execute(
        "SELECT url, article_body, image_url, image_urls FROM articles WHERE id = ?",
        (article_id,)
    ).fetchone()
    conn.close()
    if not row:
        return {"error": "Article not found"}
    d = dict(row)

    # If we already have a body stored, return it
    if d.get("article_body"):
        try:
            d["image_urls"] = json.loads(d["image_urls"] or "[]")
        except Exception:
            d["image_urls"] = []
        return d

    # Otherwise fetch on demand
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from fetcher import _extract_article_content
        content = _extract_article_content(d["url"])
        body      = content.get("body", "")
        og_image  = content.get("og_image", "")
        extra_imgs = content.get("images", [])

        # Cache body + images back to DB
        if body or og_image or extra_imgs:
            existing_urls = []
            try:
                existing_urls = json.loads(d.get("image_urls") or "[]")
            except Exception:
                pass
            merged_urls = list(dict.fromkeys(
                ([og_image] if og_image else []) + existing_urls + extra_imgs
            ))
            upconn = get_connection()
            upconn.execute(
                "UPDATE articles SET article_body=?, image_url=COALESCE(NULLIF(image_url,''),?), image_urls=? WHERE id=?",
                (body[:6000], og_image, json.dumps(merged_urls), article_id)
            )
            upconn.commit()
            upconn.close()

        d["article_body"] = body
        d["og_image"]     = og_image
        try:
            existing = json.loads(d.get("image_urls") or "[]")
        except Exception:
            existing = []
        # Merge og_image + extra_imgs with existing
        merged = list(dict.fromkeys(
            ([og_image] if og_image else []) + existing + extra_imgs
        ))
        d["image_urls"] = merged
        if not d["image_url"] and merged:
            d["image_url"] = merged[0]
    except Exception as e:
        d["error"] = str(e)
        d["article_body"] = ""
        d["image_urls"] = []

    return d


# ─────────────────────────────────────────────
# ARTICLE ACTION HELPERS (called from do_POST)
# ─────────────────────────────────────────────

def _get_article_with_post(article_id: int) -> dict:
    """Return article + its latest post record merged into one dict."""
    conn = get_connection()
    row = conn.execute("""
        SELECT a.*,
               p.id           AS post_id,
               p.caption      AS caption,
               p.hashtags     AS hashtags,
               p.image_path   AS image_path,
               p.slide_paths  AS slide_paths,
               p.image_url    AS post_image_url,
               p.status       AS post_status,
               p.instagram_post_id,
               p.posted_at    AS post_published_at
        FROM articles a
        LEFT JOIN posts p ON p.article_id = a.id
        WHERE a.id = ?
        ORDER BY p.created_at DESC
        LIMIT 1
    """, (article_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}


def article_action_generate_caption(article_id: int) -> dict:
    article = _get_article_with_post(article_id)
    if not article:
        return {"error": "Article not found"}
    page = article.get("page", "finpulse")
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from ai import generate_caption
        result = generate_caption(article, page)
        caption  = result.get("caption", "")
        hashtags = result.get("hashtags", "")
        upconn = get_connection()
        post_id = article.get("post_id")
        if post_id:
            upconn.execute(
                "UPDATE posts SET caption=?, hashtags=? WHERE id=?",
                (caption, hashtags, post_id)
            )
        else:
            cur = upconn.execute(
                "INSERT INTO posts (article_id, page, caption, hashtags, status) VALUES (?,?,?,?,'pending')",
                (article_id, page, caption, hashtags)
            )
            post_id = cur.lastrowid
        upconn.commit(); upconn.close()
        return {"success": True, "post_id": post_id, "caption": caption,
                "hashtags": hashtags, "backend": result.get("backend", "")}
    except Exception as e:
        return {"error": str(e), "success": False}


def article_action_generate_image(article_id: int) -> dict:
    article = _get_article_with_post(article_id)
    if not article:
        return {"error": "Article not found"}
    page = article.get("page", "finpulse")
    if not article.get("caption"):
        return {"error": "Generate caption first"}
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from carousel import generate_carousel, _parse_caption
        # Parse caption for structured analysis data
        caption = article.get("caption", "")
        cd = _parse_caption(caption, article.get("title", ""))
        slide_paths = generate_carousel(article, page=page, caption=caption, caption_data=cd)
        # Use first slide as primary image_path
        image_path  = str(slide_paths[0])
        image_file  = os.path.basename(image_path)
        slide_paths_json = json.dumps([str(p) for p in slide_paths])
        # Update / create post record
        post_id = article.get("post_id")
        upconn  = get_connection()
        if post_id:
            upconn.execute(
                "UPDATE posts SET image_path=?, slide_paths=? WHERE id=?",
                (image_path, slide_paths_json, post_id)
            )
        else:
            cur = upconn.execute(
                "INSERT INTO posts (article_id, page, caption, image_path, slide_paths, status) "
                "VALUES (?,?,?,?,?,'pending')",
                (article_id, page, caption, image_path, slide_paths_json)
            )
            post_id = cur.lastrowid
        upconn.commit(); upconn.close()
        return {"success": True, "post_id": post_id, "image_file": image_file,
                "image_path": image_path, "slide_count": len(slide_paths)}
    except Exception as e:
        return {"error": str(e), "success": False}


def article_action_post(article_id: int, repost: bool = False) -> dict:
    article = _get_article_with_post(article_id)
    if not article:
        return {"error": "Article not found"}
    if article.get("post_status") == "posted" and not repost:
        return {"already_posted": True, "error": "Already posted — confirm to repost"}
    if not article.get("caption"):
        return {"error": "No caption — generate caption first"}
    if not article.get("image_path"):
        return {"error": "No image — generate post image first"}
    page    = article.get("page", "finpulse")
    caption = article["caption"]
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        # Detect carousel vs single image
        slide_paths_raw = article.get("slide_paths") or "[]"
        try:
            slide_paths = json.loads(slide_paths_raw) if isinstance(slide_paths_raw, str) else []
        except Exception:
            slide_paths = []
        # Filter to existing files
        slide_paths = [p for p in slide_paths if os.path.exists(p)]
        if len(slide_paths) >= 2:
            # Post as carousel
            from instagram import post_carousel_to_instagram
            result = post_carousel_to_instagram(article, caption, slide_paths, page, dry_run=False)
        else:
            # Single image fallback
            from instagram import post_to_instagram
            result = post_to_instagram(article, caption, article["image_path"], page, dry_run=False)
        if result.get("success"):
            ig_id   = result.get("post_id") or ""
            upconn  = get_connection()
            post_id = article.get("post_id")
            if post_id:
                upconn.execute(
                    "UPDATE posts SET status='posted', instagram_post_id=?, posted_at=datetime('now') WHERE id=?",
                    (ig_id, post_id)
                )
            upconn.execute(
                "UPDATE articles SET is_posted=1, posted_at=datetime('now') WHERE id=?",
                (article_id,)
            )
            upconn.commit(); upconn.close()
            return {"success": True, "instagram_post_id": ig_id,
                    "is_carousel": len(slide_paths) >= 2}
        else:
            return {"error": result.get("error", "Instagram post failed"), "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


def article_action_generate_full(article_id: int) -> dict:
    """Generate both caption and 5-slide carousel on demand for an article."""
    cap_res = article_action_generate_caption(article_id)
    if not cap_res.get("success"):
        return {"error": cap_res.get("error", "Caption generation failed"), "success": False}
    img_res = article_action_generate_image(article_id)
    return {
        "success": img_res.get("success", False),
        "caption": cap_res.get("caption"),
        "backend": cap_res.get("backend"),
        "post_id": img_res.get("post_id"),
        "image_file": img_res.get("image_file"),
        "slide_count": img_res.get("slide_count", 0),
        "error": img_res.get("error"),
    }


def article_action_mark_posted(article_id: int) -> dict:
    try:
        upconn = get_connection()
        upconn.execute(
            "UPDATE articles SET is_posted=1, posted_at=datetime('now') WHERE id=?",
            (article_id,)
        )
        upconn.execute(
            "UPDATE posts SET status='posted', posted_at=datetime('now') WHERE article_id=? AND status='pending'",
            (article_id,)
        )
        upconn.commit(); upconn.close()
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


def get_ready_posts():
    """
    All articles with caption + carousel generated but not yet posted.
    Sorted by page then score.
    """
    conn = get_connection()
    posts_cols = {r[1] for r in conn.execute("PRAGMA table_info(posts)").fetchall()}
    slide_col  = ("COALESCE(p.slide_paths,'[]') AS slide_paths"
                  if "slide_paths" in posts_cols else "'[]' AS slide_paths")
    rows = conn.execute(f"""
        SELECT a.id, a.title, a.source_name, a.page, a.score,
               a.published_at, a.fetched_at,
               p.id AS post_id, p.caption, p.image_path,
               p.status AS post_status, {slide_col}
        FROM articles a
        JOIN  posts p ON p.article_id = a.id
        WHERE a.is_posted = 0
          AND p.image_path IS NOT NULL AND p.image_path != ''
          AND (p.status IS NULL OR p.status != 'posted')
        ORDER BY a.page, a.score DESC
        LIMIT 60
    """).fetchall()
    conn.close()

    PAGE_ORDER = {"finpulse": 0, "techpulse": 1, "corppulse": 2, "worldpulse": 3}
    result = []
    for r in rows:
        d = dict(r)
        # Build slide_files list
        try:
            sp_paths = json.loads(d.get("slide_paths") or "[]")
        except Exception:
            sp_paths = []
        slide_files = []
        for sp in sp_paths:
            fname = os.path.basename(sp)
            stem  = fname.replace("_clean.jpg","").replace(".jpg","")
            for ext in ("_clean.jpg", ".jpg"):
                c = stem + ext
                if os.path.exists(os.path.join(IMAGES_DIR, c)):
                    slide_files.append(c); break
            else:
                if os.path.exists(sp):
                    slide_files.append(fname)
        d["slide_files"] = slide_files
        d["image_file"]  = (slide_files[0] if slide_files
                            else (os.path.basename(d["image_path"]) if d.get("image_path") else None))
        d["page_order"]  = PAGE_ORDER.get(d.get("page",""), 99)
        result.append(d)

    result.sort(key=lambda x: (x["page_order"], -float(x.get("score") or 0)))
    return {"items": result, "count": len(result)}


def get_errors(limit=40):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM errors ORDER BY occurred_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_log_tail(n=100):
    try:
        if not os.path.exists(LOG_PATH):
            return ["No log file yet — run the scheduler first."]
        with open(LOG_PATH) as f:
            lines = f.readlines()
        return [l.rstrip() for l in lines[-n:]]
    except Exception as e:
        return [f"Error: {e}"]

def get_activity():
    conn = get_connection()
    articles_by_day = conn.execute("""
        SELECT date(fetched_at) as day, COUNT(*) as count
        FROM articles WHERE fetched_at >= date('now','-7 days')
        GROUP BY day ORDER BY day
    """).fetchall()
    posts_by_day = conn.execute("""
        SELECT date(posted_at) as day, COUNT(*) as count
        FROM posts WHERE status='posted' AND posted_at >= date('now','-7 days')
        GROUP BY day ORDER BY day
    """).fetchall()
    conn.close()
    return {
        "articles": [dict(r) for r in articles_by_day],
        "posts":    [dict(r) for r in posts_by_day],
    }

def get_next_schedule():
    from datetime import datetime, timedelta
    SCHEDULE = [(6,0),(9,30),(13,0),(17,0)]
    now = datetime.utcnow()
    slots = []
    for offset in range(2):
        day = now.date() + timedelta(days=offset)
        for h, m in SCHEDULE:
            t = datetime(day.year, day.month, day.day, h, m)
            if t > now:
                slots.append(t.isoformat() + "Z")
    return slots[:4]


# ─────────────────────────────────────────────
# HTTP HANDLER
# ─────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def log_message(self, *a): pass

    def _check_auth(self) -> bool:
        """Return True if request is authenticated, otherwise send 401 and return False."""
        auth = self.headers.get("Authorization", "")
        if auth == f"Basic {_DASH_TOKEN}":
            return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Pulse Media Dashboard"')
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Unauthorized")
        return False

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if not self._check_auth(): return
        parsed = urlparse(self.path)
        path   = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length)) if length > 0 else {}
        except Exception:
            body = {}

        if path == "/api/market-impact/generate-post":
            try:
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
                from fii_dii import generate_market_impact_post
                self._json(generate_market_impact_post())
            except Exception as e:
                self._json({"error": str(e), "success": False})
            return

        m = re.match(r"^/api/article/(\d+)/(generate-caption|generate-image|generate-full|post|mark-posted)$", path)
        if not m:
            self.send_error(404); return
        article_id = int(m.group(1))
        action     = m.group(2)

        if action == "generate-caption":
            self._json(article_action_generate_caption(article_id))
        elif action == "generate-image":
            self._json(article_action_generate_image(article_id))
        elif action == "generate-full":
            self._json(article_action_generate_full(article_id))
        elif action == "post":
            repost = bool(body.get("repost", False))
            self._json(article_action_post(article_id, repost=repost))
        elif action == "mark-posted":
            self._json(article_action_mark_posted(article_id))
        else:
            self.send_error(404)

    def do_GET(self):
        if not self._check_auth(): return
        parsed = urlparse(self.path)
        qs     = parse_qs(parsed.query)
        path   = parsed.path
        def qp(k, d=None): return qs.get(k,[d])[0]

        if path == "/":
            self._file("index.html", "text/html")
        elif path == "/api/stats":
            self._json(get_stats())
        elif path == "/api/pipeline":
            self._json(get_pipeline_data())
        elif path == "/api/posts":
            self._json(get_posts_by_page(qp("page"), qp("status"), int(qp("limit",30))))
        elif path == "/api/sources":
            self._json(get_sources())
        elif path == "/api/errors":
            self._json(get_errors(int(qp("limit",40))))
        elif path == "/api/log":
            self._json(get_log_tail(int(qp("n",100))))
        elif path == "/api/activity":
            self._json(get_activity())
        elif path == "/api/schedule":
            self._json({"next": get_next_schedule()})
        elif path == "/api/top-news":
            page = qp("page", "all")
            limit = int(qp("limit", 5))
            self._json(get_top_news_data(page=page, limit=limit))
        elif path == "/api/fii-dii":
            try:
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
                from fii_dii import fetch_fii_dii_data
                self._json(fetch_fii_dii_data())
            except Exception as e:
                self._json({"error": str(e)})
        elif path == "/api/market-impact":
            try:
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
                from fii_dii import analyze_sector_impact
                self._json(analyze_sector_impact())
            except Exception as e:
                self._json({"error": str(e)})
        elif path.startswith("/api/trigger/"):
            page = path.split("/")[-1]
            self._trigger(page, qp("dry","0")=="1")
        elif path.startswith("/api/fetch-source/"):
            display_name = unquote(path[len("/api/fetch-source/"):])
            self._fetch_one_source(display_name)
        elif path.startswith("/api/fetch/"):
            page = path.split("/")[-1]
            self._fetch_only(page)
        elif path == "/api/workers":
            self._json(get_workers())
        elif path == "/api/ready-posts":
            self._json(get_ready_posts())
        elif path == "/api/bg-status":
            self._json(get_bg_status())
        elif path.startswith("/api/source/") and path.endswith("/articles"):
            # /api/source/<encoded_name>/articles
            source_name = unquote(path[len("/api/source/"):-len("/articles")])
            limit = int(qp("limit", 80))
            self._json(get_source_articles_data(source_name, limit))
        elif path.startswith("/api/article/") and path.endswith("/content"):
            try:
                art_id = int(path[len("/api/article/"):-len("/content")])
                self._json(fetch_article_content_data(art_id))
            except Exception as e:
                self._json({"error": str(e)})
        elif path.startswith("/img/"):
            self._image(path[5:])
        else:
            self.send_error(404)

    def _fetch_one_source(self, display_name: str):
        """Synchronously fetch a single source (manual mode — no auto-post generation)."""
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
            from fetcher import fetch_one_source
            result = fetch_one_source(display_name)
            self._json(result)
        except Exception as e:
            self._json({"error": str(e), "saved": 0, "total": 0})

    def _fetch_only(self, page):
        """Run fetcher.py to retrieve and store news (manual mode — no auto-post generation)."""
        def _run():
            try:
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
                from fetcher import fetch_page, fetch_all_pages
                if page == "all":
                    fetch_all_pages(top_n=10, dry_run=False)
                else:
                    fetch_page(page, top_n=10, dry_run=False)
            except Exception as e:
                print(f"[fetch:{page}] {e}")
        threading.Thread(target=_run, daemon=True).start()
        self._json({"status": "started", "page": page})

    def _trigger(self, page, dry):
        def _run():
            try:
                from pipeline.orchestrator import run_pipeline
                from instagram import run_post_cycle
                run_pipeline(page, top_n=3)
                run_post_cycle(page, dry_run=dry)
            except Exception as e:
                print(f"[trigger:{page}] {e}")
        threading.Thread(target=_run, daemon=True).start()
        self._json({"status":"triggered","page":page,"dry":dry})

    def _image(self, filename):
        p = os.path.join(IMAGES_DIR, os.path.basename(filename))
        if not os.path.exists(p):
            self.send_error(404); return
        ct = "image/jpeg" if p.endswith((".jpg",".jpeg")) else "image/png"
        with open(p,"rb") as f: body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Cache-Control","public,max-age=3600")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data):
        body = json.dumps(data, default=str).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Cache-Control","no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, name, ct):
        p = os.path.join(os.path.dirname(__file__), name)
        with open(p,"rb") as f: body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    import webbrowser
    print(f"\n{'='*48}")
    print(f"  🚀 Pulse Media Command Center")
    print(f"  → http://localhost:{PORT}")
    print(f"  🔐 Login: {_DASH_USER} / {_DASH_PASS}")
    print(f"     (set DASHBOARD_USER/DASHBOARD_PASS in .env to change)")
    print(f"{'='*48}\n")
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        webbrowser.open(f"http://localhost:{PORT}")
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹  Stopped.")
