"""
database/models.py — Database Query Helpers
All reads/writes to the database go through these functions.
No raw SQL outside this file.
"""

import hashlib
import json
import re
from datetime import datetime
from typing import Optional
from database.schema import get_connection


# ─────────────────────────────────────────────
# ARTICLE HELPERS
# ─────────────────────────────────────────────

def article_hash(title: str) -> str:
    """Normalized MD5 hash of a title — used as the dedup key."""
    normalized = re.sub(r"[^a-z0-9]", "", title.lower())
    return hashlib.md5(normalized.encode()).hexdigest()


def article_exists(title: str) -> bool:
    """Return True if an article with this title is already in the DB."""
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM articles WHERE article_hash = ?",
        (article_hash(title),)
    ).fetchone()
    conn.close()
    return row is not None


def save_article(article: dict) -> Optional[int]:
    """
    Insert an article. Returns the new row ID, or None if it's a duplicate.
    article dict must have: title, summary, url, source_name, page
    Optional: published_at, score, category, source_id
    """
    h = article_hash(article["title"])
    conn = get_connection()
    try:
        # Serialize image_urls list to JSON string for storage
        image_urls_raw = article.get("image_urls", [])
        if isinstance(image_urls_raw, list):
            image_urls_json = json.dumps(image_urls_raw)
        else:
            image_urls_json = image_urls_raw or "[]"

        cur = conn.execute("""
            INSERT INTO articles
                (article_hash, title, summary, url, source_name, source_id,
                 page, category, published_at, score,
                 image_url, image_urls, article_body)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            h,
            article["title"],
            article.get("summary", ""),
            article.get("url", ""),
            article.get("source_name", ""),
            article.get("source_id"),
            article.get("page", ""),
            article.get("category", ""),
            article.get("published_at", ""),
            article.get("score", 0.0),
            article.get("image_url", ""),
            image_urls_json,
            article.get("article_body", ""),
        ))
        conn.commit()
        return cur.lastrowid
    except Exception:
        return None  # duplicate (UNIQUE constraint on article_hash)
    finally:
        conn.close()


def get_top_articles(page: str, limit: int = 5) -> list[dict]:
    """Return top unposted articles for a page, sorted by score."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM articles
        WHERE page = ? AND is_posted = 0 AND is_duplicate = 0
        ORDER BY score DESC, fetched_at DESC
        LIMIT ?
    """, (page, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_articles(page: str = None, limit: int = 20) -> list[dict]:
    """Return recently fetched articles (for dashboard)."""
    conn = get_connection()
    if page:
        rows = conn.execute("""
            SELECT * FROM articles WHERE page = ?
            ORDER BY fetched_at DESC LIMIT ?
        """, (page, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM articles
            ORDER BY fetched_at DESC LIMIT ?
        """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_article_posted(article_id: int, posted_at: str = None):
    """Mark an article as posted."""
    conn = get_connection()
    conn.execute("""
        UPDATE articles SET is_posted = 1, posted_at = ?
        WHERE id = ?
    """, (posted_at or datetime.utcnow().isoformat(), article_id))
    conn.commit()
    conn.close()


def get_source_articles(source_display_name: str, limit: int = 80) -> list[dict]:
    """
    Return articles for a specific source with full pipeline data.
    Joins with posts table to get caption, image, status, and engagement.
    Gracefully handles missing image_url/image_urls columns (pre-migration DBs).
    """
    conn = get_connection()

    # Check which columns exist in BOTH tables (graceful pre-migration support)
    art_cols   = {row[1] for row in conn.execute("PRAGMA table_info(articles)").fetchall()}
    posts_cols = {row[1] for row in conn.execute("PRAGMA table_info(posts)").fetchall()}

    img_url_col    = "a.image_url"   if "image_url"    in art_cols   else "'' AS image_url"
    img_urls_col   = "a.image_urls"  if "image_urls"   in art_cols   else "NULL AS image_urls"
    art_body_col   = "a.article_body" if "article_body" in art_cols  else "'' AS article_body"
    slide_paths_col = ("COALESCE(p.slide_paths, '[]') AS slide_paths"
                       if "slide_paths" in posts_cols else "'[]' AS slide_paths")

    rows = conn.execute(f"""
        SELECT
            a.id, a.title, a.summary, a.url, a.source_name, a.page,
            a.category, a.score, a.published_at, a.fetched_at,
            a.is_posted, a.posted_at,
            {img_url_col}, {img_urls_col}, {art_body_col},
            p.id          AS post_id,
            p.status      AS post_status,
            p.caption,
            p.image_path,
            p.instagram_post_id,
            p.likes,
            p.comments,
            p.created_at  AS post_created,
            p.posted_at   AS post_published_at,
            {slide_paths_col}
        FROM articles a
        LEFT JOIN posts p ON p.article_id = a.id
        WHERE a.source_name = ?
        ORDER BY
            CASE WHEN p.status='posted' THEN 0
                 WHEN p.id IS NOT NULL   THEN 1
                 ELSE 2 END,
            a.score DESC,
            a.fetched_at DESC
        LIMIT ?
    """, (source_display_name, limit)).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        # Deserialize image_urls JSON string → list
        if isinstance(d.get("image_urls"), str):
            try:
                d["image_urls"] = json.loads(d["image_urls"])
            except Exception:
                d["image_urls"] = []
        elif not d.get("image_urls"):
            d["image_urls"] = []
        result.append(d)
    return result


def get_article_counts() -> dict:
    """Return article counts per page (for dashboard)."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT page, COUNT(*) as total,
               SUM(is_posted) as posted,
               SUM(CASE WHEN is_posted = 0 THEN 1 ELSE 0 END) as pending
        FROM articles GROUP BY page
    """).fetchall()
    conn.close()
    return {r["page"]: dict(r) for r in rows}


# ─────────────────────────────────────────────
# SOURCE HELPERS
# ─────────────────────────────────────────────

def get_source_id(name: str) -> Optional[int]:
    """Look up a source ID by its unique name."""
    conn = get_connection()
    row = conn.execute("SELECT id FROM sources WHERE name = ?", (name,)).fetchone()
    conn.close()
    return row["id"] if row else None


def update_source_status(name: str, status: str, articles_added: int = 0):
    """Update last_fetched_at, status, and cumulative counts for a source."""
    conn = get_connection()
    conn.execute("""
        UPDATE sources SET
            last_fetched_at = datetime('now'),
            last_status     = ?,
            total_fetches   = total_fetches + 1,
            total_articles  = total_articles + ?,
            total_errors    = total_errors + ?
        WHERE name = ?
    """, (status, articles_added if status == "ok" else 0,
          1 if status == "error" else 0, name))
    conn.commit()
    conn.close()


def get_all_sources() -> list[dict]:
    """Return all sources with their stats (for dashboard)."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM sources ORDER BY page, source_type").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# POST HELPERS
# ─────────────────────────────────────────────

def save_post(post: dict) -> int:
    """Insert a new post record. Returns new post ID."""
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO posts (article_id, page, caption, hashtags, image_path, image_url, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
    """, (
        post["article_id"],
        post["page"],
        post["caption"],
        post.get("hashtags", ""),
        post.get("image_path"),
        post.get("image_url"),
    ))
    conn.commit()
    post_id = cur.lastrowid
    conn.close()
    return post_id


def update_post_published(post_id: int, instagram_post_id: str):
    """Mark a post as successfully published to Instagram."""
    conn = get_connection()
    conn.execute("""
        UPDATE posts SET
            status = 'posted',
            instagram_post_id = ?,
            posted_at = datetime('now')
        WHERE id = ?
    """, (instagram_post_id, post_id))
    conn.commit()
    conn.close()


def get_recent_posts(limit: int = 10) -> list[dict]:
    """Return recent posts across all pages (for dashboard)."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT p.*, a.title as article_title
        FROM posts p JOIN articles a ON p.article_id = a.id
        ORDER BY p.created_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# ERROR HELPERS
# ─────────────────────────────────────────────

def log_error(source_name: str, error_type: str, error_msg: str, feed_url: str = None):
    """Log a fetch error to the errors table."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO errors (source_name, error_type, error_msg, feed_url)
        VALUES (?, ?, ?, ?)
    """, (source_name, error_type, str(error_msg)[:1000], feed_url))
    conn.commit()
    conn.close()


def get_recent_errors(limit: int = 20) -> list[dict]:
    """Return recent errors (for dashboard)."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM errors ORDER BY occurred_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# DASHBOARD STATS (single call for all numbers)
# ─────────────────────────────────────────────

def get_dashboard_stats() -> dict:
    """Return all stats needed to render the dashboard."""
    conn = get_connection()

    total_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    total_posted   = conn.execute("SELECT COUNT(*) FROM posts WHERE status='posted'").fetchone()[0]
    total_errors   = conn.execute("SELECT COUNT(*) FROM errors").fetchone()[0]
    total_sources  = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    sources_ok     = conn.execute("SELECT COUNT(*) FROM sources WHERE last_status='ok'").fetchone()[0]

    per_page = conn.execute("""
        SELECT page, COUNT(*) as total, SUM(is_posted) as posted
        FROM articles GROUP BY page
    """).fetchall()

    conn.close()
    return {
        "total_articles": total_articles,
        "total_posted":   total_posted,
        "total_errors":   total_errors,
        "total_sources":  total_sources,
        "sources_ok":     sources_ok,
        "per_page":       [dict(r) for r in per_page],
    }
