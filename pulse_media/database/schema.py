"""
database/schema.py — Pulse Media Group Database
SQLite schema setup. Run once to initialize the database.

Tables:
  articles  — every article fetched from every source
  posts     — articles that were turned into Instagram posts
  sources   — each worker/source and its health stats
  errors    — error log for failed fetches

To initialize:  python database/schema.py
To reset:       python database/schema.py --reset
"""

import sqlite3
import os
import sys

DB_PATH = os.environ.get(
    "PULSE_DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "data", "pulse.db")
)


def get_connection() -> sqlite3.Connection:
    """Return a database connection with row factory enabled."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # rows behave like dicts
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(reset: bool = False):
    """Create all tables. If reset=True, drops and recreates everything."""
    conn = get_connection()
    cur = conn.cursor()

    if reset:
        print("⚠️  Dropping all tables...")
        cur.execute("DROP TABLE IF EXISTS errors")
        cur.execute("DROP TABLE IF EXISTS posts")
        cur.execute("DROP TABLE IF EXISTS articles")
        cur.execute("DROP TABLE IF EXISTS sources")

    # ─────────────────────────────────────────────
    # TABLE: sources
    # One row per worker (e.g. "yahoo_finance", "cnbc")
    # Tracks health and fetch statistics
    # ─────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL UNIQUE,   -- e.g. "yahoo_finance"
            display_name    TEXT NOT NULL,           -- e.g. "Yahoo Finance"
            source_type     TEXT NOT NULL,           -- "rss" | "api" | "library"
            page            TEXT NOT NULL,           -- "finpulse" | "techpulse" | "corppulse" | "worldpulse" | "all"
            feed_url        TEXT,                    -- RSS URL or API endpoint
            last_fetched_at TEXT,                    -- ISO timestamp of last successful fetch
            last_status     TEXT DEFAULT 'never',   -- "ok" | "error" | "timeout" | "never"
            total_fetches   INTEGER DEFAULT 0,
            total_articles  INTEGER DEFAULT 0,
            total_errors    INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)

    # ─────────────────────────────────────────────
    # TABLE: articles
    # Every article fetched, before any dedup or scoring
    # ─────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            article_hash    TEXT NOT NULL UNIQUE,    -- MD5 of normalized title (dedup key)
            title           TEXT NOT NULL,
            summary         TEXT DEFAULT '',
            url             TEXT NOT NULL,
            source_name     TEXT NOT NULL,           -- display name e.g. "Reuters"
            source_id       INTEGER REFERENCES sources(id),
            page            TEXT NOT NULL,           -- which page this belongs to
            category        TEXT DEFAULT '',         -- "earnings" | "macro" | "crypto" | etc.
            published_at    TEXT,                    -- ISO timestamp from source
            fetched_at      TEXT DEFAULT (datetime('now')),
            score           REAL DEFAULT 0.0,        -- relevance score 0–100
            is_duplicate    INTEGER DEFAULT 0,       -- 1 if flagged as near-duplicate
            is_posted       INTEGER DEFAULT 0,       -- 1 once turned into an Instagram post
            posted_at       TEXT                     -- when it was posted
        )
    """)

    # ─────────────────────────────────────────────
    # TABLE: posts
    # Articles that were turned into actual Instagram posts
    # ─────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id          INTEGER NOT NULL REFERENCES articles(id),
            page                TEXT NOT NULL,           -- "finpulse" etc.
            caption             TEXT NOT NULL,           -- AI-generated caption
            hashtags            TEXT DEFAULT '',         -- space-separated hashtags
            image_path          TEXT,                    -- local path to generated image
            image_url           TEXT,                    -- public URL (Imgur/Cloudinary)
            instagram_post_id   TEXT,                    -- ID returned by Instagram API
            status              TEXT DEFAULT 'pending',  -- "pending" | "posted" | "failed"
            likes               INTEGER DEFAULT 0,
            comments            INTEGER DEFAULT 0,
            reach               INTEGER DEFAULT 0,
            created_at          TEXT DEFAULT (datetime('now')),
            posted_at           TEXT
        )
    """)

    # ─────────────────────────────────────────────
    # TABLE: errors
    # Every fetch error, for monitoring and debugging
    # ─────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS errors (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            error_type  TEXT NOT NULL,   -- "timeout" | "parse_error" | "http_error" | "api_error"
            error_msg   TEXT NOT NULL,
            feed_url    TEXT,
            occurred_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # ─────────────────────────────────────────────
    # INDEXES — speed up common queries
    # ─────────────────────────────────────────────
    cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_page     ON articles(page)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_score    ON articles(score DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_posted   ON articles(is_posted)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_hash     ON articles(article_hash)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_articles_fetched  ON articles(fetched_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_page        ON posts(page)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_status      ON posts(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_errors_source     ON errors(source_name)")

    # ─────────────────────────────────────────────
    # SEED: Insert all source workers
    # ─────────────────────────────────────────────
    sources_seed = [
        # name, display_name, type, page, feed_url
        ("yahoo_finance",          "Yahoo Finance",          "rss",     "finpulse",  "https://finance.yahoo.com/news/rssindex"),
        ("cnbc_markets",           "CNBC Markets",           "rss",     "finpulse",  "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
        ("cnbc_economy",           "CNBC Economy",           "rss",     "finpulse",  "https://www.cnbc.com/id/10000664/device/rss/rss.html"),
        ("marketwatch",            "MarketWatch",            "rss",     "finpulse",  "https://feeds.marketwatch.com/marketwatch/topstories/"),
        ("coindesk",               "CoinDesk",               "rss",     "finpulse",  "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("seeking_alpha",          "Seeking Alpha",          "rss",     "finpulse",  "https://seekingalpha.com/market_currents.xml"),
        ("investing_com",          "Investing.com",          "rss",     "finpulse",  "https://www.investing.com/rss/news.rss"),
        ("sec_edgar",              "SEC EDGAR",              "rss",     "finpulse",  "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=40&output=atom"),
        ("federal_reserve",        "Federal Reserve",        "rss",     "finpulse",  "https://www.federalreserve.gov/feeds/press_all.xml"),
        ("google_news_finance",    "Google News Finance",    "rss",     "finpulse",  "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"),
        ("google_news_stocks",     "Google News Stocks",     "rss",     "finpulse",  "https://news.google.com/rss/search?q=stock+market+OR+nasdaq+OR+SP500+when:48h&hl=en-US&gl=US&ceid=US:en"),
        ("yfinance_lib",           "yfinance Library",       "library", "finpulse",  None),
        ("newsdata_fin",           "NewsData.io",            "api",     "finpulse",  "https://newsdata.io/api/1/news"),

        ("techcrunch",             "TechCrunch",             "rss",     "techpulse", "https://techcrunch.com/feed/"),
        ("the_verge",              "The Verge",              "rss",     "techpulse", "https://www.theverge.com/rss/index.xml"),
        ("ars_technica",           "Ars Technica",           "rss",     "techpulse", "https://feeds.arstechnica.com/arstechnica/index"),
        ("wired",                  "Wired",                  "rss",     "techpulse", "https://www.wired.com/feed/rss"),
        ("hacker_news",            "Hacker News",            "rss",     "techpulse", "https://news.ycombinator.com/rss"),
        ("mit_tech_review",        "MIT Tech Review",        "rss",     "techpulse", "https://www.technologyreview.com/feed/"),
        ("venturebeat",            "VentureBeat",            "rss",     "techpulse", "https://venturebeat.com/feed/"),
        ("techmeme",               "Techmeme",               "rss",     "techpulse", "https://www.techmeme.com/feed.xml"),
        ("google_news_tech",       "Google News Tech",       "rss",     "techpulse", "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en"),
        ("google_news_ai",         "Google News AI",         "rss",     "techpulse", "https://news.google.com/rss/search?q=artificial+intelligence+OR+OpenAI+OR+LLM+OR+startup+when:48h&hl=en-US&gl=US&ceid=US:en"),
        ("newsdata_tech",          "NewsData.io Tech",       "api",     "techpulse", "https://newsdata.io/api/1/news"),

        ("fortune",                "Fortune",                "rss",     "corppulse", "https://fortune.com/feed/"),
        ("forbes_corp",            "Forbes",                 "rss",     "corppulse", "https://www.forbes.com/business/feed/"),
        ("ft_corp",                "Financial Times",        "rss",     "corppulse", "https://www.ft.com/?format=rss"),
        ("cnbc_biz",               "CNBC Business",          "rss",     "corppulse", "https://www.cnbc.com/id/10001147/device/rss/rss.html"),
        ("business_insider",       "Business Insider",       "rss",     "corppulse", "https://feeds.businessinsider.com/custom/all"),
        ("sec_edgar_corp",         "SEC 8-K Filings",        "rss",     "corppulse", "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=40&output=atom"),
        ("google_news_corp",       "Google News Business",   "rss",     "corppulse", "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"),
        ("google_news_earnings",   "Google News Earnings",   "rss",     "corppulse", "https://news.google.com/rss/search?q=earnings+OR+merger+OR+acquisition+OR+layoffs+OR+IPO+when:48h&hl=en-US&gl=US&ceid=US:en"),

        ("bbc_world",              "BBC World",              "rss",     "worldpulse","https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("politico",               "Politico",               "rss",     "worldpulse","https://rss.politico.com/politics-news.xml"),
        ("aljazeera",              "Al Jazeera",             "rss",     "worldpulse","https://www.aljazeera.com/xml/rss/all.xml"),
        ("nyt_world",              "NYT World",              "rss",     "worldpulse","https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
        ("guardian_world",         "The Guardian",           "rss",     "worldpulse","https://www.theguardian.com/world/rss"),
        ("france24",               "France 24",              "rss",     "worldpulse","https://www.france24.com/en/rss"),
        ("google_news_world",      "Google News World",      "rss",     "worldpulse","https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en"),
        ("google_news_geopolitics","Google News Geopolitics","rss",     "worldpulse","https://news.google.com/rss/search?q=geopolitics+OR+diplomacy+OR+summit+OR+election+OR+sanctions+when:48h&hl=en-US&gl=US&ceid=US:en"),
    ]

    cur.executemany("""
        INSERT OR IGNORE INTO sources (name, display_name, source_type, page, feed_url)
        VALUES (?, ?, ?, ?, ?)
    """, sources_seed)

    conn.commit()
    conn.close()

    migrate_db()  # safely add new columns if not present

    count = len(sources_seed)
    print(f"✅ Database initialized: {DB_PATH}")
    print(f"   Tables: articles, posts, sources, errors")
    print(f"   Sources seeded: {count} workers")


def migrate_db():
    """
    Add new columns to existing tables (safe to run multiple times).
    Adds: articles.image_url, articles.image_urls, articles.article_body
    """
    conn = get_connection()
    cur = conn.cursor()
    migrations = [
        "ALTER TABLE articles ADD COLUMN image_url    TEXT DEFAULT ''",
        "ALTER TABLE articles ADD COLUMN image_urls   TEXT DEFAULT '[]'",
        "ALTER TABLE articles ADD COLUMN article_body TEXT DEFAULT ''",
        "ALTER TABLE posts    ADD COLUMN slide_paths  TEXT DEFAULT '[]'",
    ]
    added = []
    for sql in migrations:
        try:
            cur.execute(sql)
            col = sql.split("COLUMN")[1].strip().split()[0]
            added.append(col)
        except sqlite3.OperationalError:
            pass  # column already exists
    if added:
        conn.commit()
        print(f"   Migration: added columns {', '.join(added)}")
    conn.close()


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    init_db(reset=reset)
