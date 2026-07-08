"""
post_carousel_now.py — Post a fresh carousel RIGHT NOW to @finpulse.daily

Run from your Terminal:
    cd /Users/risha/PROJECT-A/pulse_media
    python3 post_carousel_now.py

Optionally pass a page:
    python3 post_carousel_now.py techpulse
    python3 post_carousel_now.py finpulse --dry-run
"""

import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(__file__))

import env_loader  # noqa: F401 — loads .env on import

page    = "finpulse"
dry_run = False
for arg in sys.argv[1:]:
    if arg == "--dry-run":
        dry_run = True
    elif arg in ("finpulse", "techpulse", "corppulse", "worldpulse"):
        page = arg

print(f"\n{'='*60}")
print(f"  🎠  Pulse Carousel Poster")
print(f"  Page:    {page}")
print(f"  Mode:    {'DRY RUN' if dry_run else 'LIVE POST'}")
print(f"{'='*60}\n")

# ── 1. Get top unposted article ───────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "pulse.db")
# Use immutable mode so SQLite doesn't try to create WAL files (sandbox-safe)
conn = sqlite3.connect(f"file:{DB_PATH}?immutable=1", uri=True)
conn.row_factory = sqlite3.Row

row = conn.execute("""
    SELECT a.id, a.title, a.source_name, a.score, a.page, a.url, a.fetched_at
    FROM articles a
    LEFT JOIN posts p ON p.article_id = a.id
    WHERE a.page = ? AND a.is_posted = 0
      AND (p.id IS NULL OR p.status != 'posted')
    ORDER BY a.score DESC
    LIMIT 1
""", (page,)).fetchone()

if not row:
    # Fallback: top article by score even if posted before (for demo)
    row = conn.execute("""
        SELECT id, title, source_name, score, page, url, fetched_at
        FROM articles WHERE page = ?
        ORDER BY score DESC LIMIT 1
    """, (page,)).fetchone()
    if not row:
        print("❌ No articles found. Run the pipeline first:")
        print("   python3 pipeline/orchestrator.py")
        sys.exit(1)
    print(f"⚠️  All articles posted — reposting top article for demo.")

article = dict(row)
print(f"📰 Article: {article['title'][:72]}")
print(f"   Source:  {article['source_name']}  |  Score: {article['score']}")

# ── 2. Generate caption (template mode, works without API) ────────────────────
print("\n🤖 Generating caption...")

PAGE_CAPTIONS = {
    "finpulse": {
        "intro": "📈 Breaking market news you need to know:\n\n",
        "points": [
            "✅ Markets are reacting to fresh economic signals",
            "✅ Investors are watching this story closely",
            "✅ Key price levels and catalysts are in play",
        ],
        "outro": "\nFollow @finpulse.daily for daily market intelligence.\n\n#finpulse #stocks #investing #markets #finance #wallstreet",
    },
    "techpulse": {
        "intro": "🚀 Big tech news breaking right now:\n\n",
        "points": [
            "✅ This story is moving the tech sector",
            "✅ Key players and products are front and center",
            "✅ Investors and builders are paying attention",
        ],
        "outro": "\nFollow @techpulse.feed for daily tech intelligence.\n\n#techpulse #tech #AI #startup #innovation",
    },
    "corppulse": {
        "intro": "🏢 Corporate news that matters:\n\n",
        "points": [
            "✅ Major corporate decision with broad implications",
            "✅ Shareholders and analysts are watching closely",
            "✅ Strategy shifts could reshape the competitive landscape",
        ],
        "outro": "\nFollow @corppulse for daily corporate intelligence.\n\n#corppulse #business #corporate #earnings #CEO",
    },
    "worldpulse": {
        "intro": "🌍 Global news making waves:\n\n",
        "points": [
            "✅ International developments with market implications",
            "✅ Geopolitical context shapes the story",
            "✅ Global investors are closely monitoring this",
        ],
        "outro": "\nFollow @worldpulse.news for global intelligence.\n\n#worldpulse #geopolitics #global #news #world",
    },
}

tpl = PAGE_CAPTIONS.get(page, PAGE_CAPTIONS["finpulse"])
caption = (
    tpl["intro"]
    + article["title"] + "\n\n"
    + "\n".join(tpl["points"]) + "\n"
    + tpl["outro"]
)
print(f"  ✅ Caption ready ({len(caption)} chars)")

# ── 3. Generate carousel slides ───────────────────────────────────────────────
print("\n🎨 Generating 5-slide carousel...")
from carousel import generate_carousel
slide_paths = generate_carousel(article, page=page, caption=caption)
print(f"  ✅ {len(slide_paths)} slides ready")

if dry_run:
    print(f"\n✅ DRY RUN complete — slides saved to output/images/")
    print("   Remove --dry-run to post live.")
    for p in slide_paths:
        print(f"   {p.name}")
    conn.close()
    sys.exit(0)

# ── 4. Post to Instagram ──────────────────────────────────────────────────────
print("\n📲 Posting to Instagram...")
from instagram import post_carousel

try:
    post_id = post_carousel(page, slide_paths, caption)
    print(f"\n🎉 Carousel posted! Post ID: {post_id}")

    # Update DB — open writable connection for updates
    try:
        conn.close()
        wconn = sqlite3.connect(DB_PATH)
        existing = wconn.execute(
            "SELECT id FROM posts WHERE article_id=? AND page=?",
            (article["id"], page)
        ).fetchone()

        if existing:
            wconn.execute("""
                UPDATE posts
                SET instagram_post_id=?, status='posted', posted_at=datetime('now')
                WHERE article_id=? AND page=?
            """, (post_id, article["id"], page))
        else:
            wconn.execute("""
                INSERT INTO posts (article_id, page, caption, image_path, status,
                                   instagram_post_id, posted_at, created_at)
                VALUES (?, ?, ?, ?, 'posted', ?, datetime('now'), datetime('now'))
            """, (article["id"], page, caption, str(slide_paths[0]), post_id))

        wconn.execute("UPDATE articles SET is_posted=1 WHERE id=?", (article["id"],))
        wconn.commit()
        wconn.close()
        conn = None
        print("  💾 DB updated")
    except Exception as dbe:
        print(f"  ⚠️  DB update skipped: {dbe}")
        conn = None

except Exception as e:
    print(f"\n❌ Post failed: {e}")
    print("\nTroubleshooting:")
    print("  • Run setup_login.py if session is expired")
    print("  • Check .env has correct credentials")
    conn.close()
    sys.exit(1)

if conn:
    conn.close()
print(f"\n✅ Done! View it at: https://instagram.com/{page.replace('finpulse','finpulse.daily').replace('techpulse','techpulse.feed')}/")
