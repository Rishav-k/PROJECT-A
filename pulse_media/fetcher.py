"""
fetcher.py — Pulse Media News Fetcher v2
=========================================
A clean, data-driven, robust news fetching module.

Replaces workers/ with a single, maintainable file.

Key improvements:
  ✅ Source registry as data — add new sources by adding one dict entry
  ✅ ThreadPoolExecutor — cleaner parallel fetching
  ✅ DB-aware deduplication — skips stories already in DB within last 48h
  ✅ In-memory dedup — 55% Jaccard overlap (same story, different wording)
  ✅ Retry with exponential backoff — handles flaky feeds
  ✅ 3-signal scoring: keyword density + recency + source trust
  ✅ All 4 pages fully covered with real, working source URLs
  ✅ Graceful degradation — one dead source never kills the whole run
  ✅ Rich progress output + results summary table

Usage:
    from fetcher import fetch_page, fetch_all_pages

    articles = fetch_page("finpulse", top_n=10)
    all_articles = fetch_all_pages()

CLI:
    python3 fetcher.py finpulse
    python3 fetcher.py all
    python3 fetcher.py finpulse --dry-run   # print results, don't save
"""

from __future__ import annotations

import os
import re
import sys
import time
import hashlib
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional

import requests

sys.path.insert(0, os.path.dirname(__file__))

# ══════════════════════════════════════════════════════════════════════════════
# SOURCE REGISTRY
# ══════════════════════════════════════════════════════════════════════════════
# To add a new source: add one dict to SOURCES.
# Required keys: name, display, page, type, url
# Optional: trust, category, max_items, score_boost

SOURCES = [

    # ── FINPULSE — Finance & Markets ──────────────────────────────────────────
    {
        "name":    "yahoo_finance",
        "display": "Yahoo Finance",
        "page":    "finpulse",
        "type":    "rss",
        "url":     "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC,^DJI,^IXIC&region=US&lang=en-US",
        "trust":   "high",
        "category":"markets",
        "max_items": 20,
    },
    {
        "name":    "cnbc_markets",
        "display": "CNBC Markets",
        "page":    "finpulse",
        "type":    "rss",
        "url":     "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "trust":   "high",
        "category":"markets",
        "max_items": 20,
    },
    {
        "name":    "cnbc_economy",
        "display": "CNBC Economy",
        "page":    "finpulse",
        "type":    "rss",
        "url":     "https://www.cnbc.com/id/10000664/device/rss/rss.html",
        "trust":   "high",
        "category":"macro",
        "max_items": 15,
    },
    {
        "name":    "marketwatch",
        "display": "MarketWatch",
        "page":    "finpulse",
        "type":    "rss",
        "url":     "https://feeds.marketwatch.com/marketwatch/topstories/",
        "trust":   "high",
        "category":"markets",
        "max_items": 20,
    },
    {
        "name":    "reuters_finance",
        "display": "Reuters Finance",
        "page":    "finpulse",
        "type":    "rss",
        "url":     "https://feeds.reuters.com/reuters/businessNews",
        "trust":   "high",
        "category":"business",
        "max_items": 20,
    },
    {
        "name":    "sec_edgar",
        "display": "SEC EDGAR",
        "page":    "finpulse",
        "type":    "rss",
        "url":     "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=40&output=atom",
        "trust":   "primary",   # primary source = highest trust
        "category":"filing",
        "max_items": 20,
        "score_boost": 20,      # all SEC filings get +20 pts
    },
    {
        "name":    "federal_reserve",
        "display": "Federal Reserve",
        "page":    "finpulse",
        "type":    "rss",
        "url":     "https://www.federalreserve.gov/feeds/press_all.xml",
        "trust":   "primary",
        "category":"macro",
        "max_items": 10,
        "score_boost": 30,      # Fed news = always critical
    },
    {
        "name":    "bls_gov",
        "display": "BLS (Inflation/Jobs)",
        "page":    "finpulse",
        "type":    "rss",
        "url":     "https://www.bls.gov/feed/bls_latest.rss",
        "trust":   "primary",
        "category":"macro",
        "max_items": 10,
        "score_boost": 15,
    },
    {
        "name":    "seeking_alpha",
        "display": "Seeking Alpha",
        "page":    "finpulse",
        "type":    "rss",
        "url":     "https://seekingalpha.com/market_currents.xml",
        "trust":   "medium",
        "category":"analysis",
        "max_items": 15,
    },
    {
        "name":    "investing_com",
        "display": "Investing.com",
        "page":    "finpulse",
        "type":    "rss",
        "url":     "https://www.investing.com/rss/news.rss",
        "trust":   "medium",
        "category":"markets",
        "max_items": 15,
    },
    # ── Google News — FinPulse ────────────────────────────────────────────────
    {
        "name":    "google_news_finance",
        "display": "Google News Finance",
        "page":    "finpulse",
        "type":    "rss",
        # Google News Business topic feed (Atom format, auto-curated by Google)
        "url":     "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
        "trust":   "high",
        "category":"markets",
        "max_items": 25,
    },
    {
        "name":    "google_news_stocks",
        "display": "Google News Stocks",
        "page":    "finpulse",
        "type":    "rss",
        # Targeted search: stock market, nasdaq, S&P, investing
        "url":     "https://news.google.com/rss/search?q=stock+market+nasdaq+SP500+investing+fed+rate&hl=en-US&gl=US&ceid=US:en",
        "trust":   "high",
        "category":"markets",
        "max_items": 25,
    },

    # ── TECHPULSE — Technology ────────────────────────────────────────────────
    {
        "name":    "techcrunch",
        "display": "TechCrunch",
        "page":    "techpulse",
        "type":    "rss",
        "url":     "https://techcrunch.com/feed/",
        "trust":   "high",
        "category":"tech",
        "max_items": 20,
    },
    {
        "name":    "the_verge",
        "display": "The Verge",
        "page":    "techpulse",
        "type":    "rss",
        "url":     "https://www.theverge.com/rss/index.xml",
        "trust":   "high",
        "category":"tech",
        "max_items": 20,
    },
    {
        "name":    "ars_technica",
        "display": "Ars Technica",
        "page":    "techpulse",
        "type":    "rss",
        "url":     "https://feeds.arstechnica.com/arstechnica/index",
        "trust":   "high",
        "category":"tech",
        "max_items": 20,
    },
    {
        "name":    "wired",
        "display": "Wired",
        "page":    "techpulse",
        "type":    "rss",
        "url":     "https://www.wired.com/feed/rss",
        "trust":   "high",
        "category":"tech",
        "max_items": 15,
    },
    {
        "name":    "hacker_news",
        "display": "Hacker News",
        "page":    "techpulse",
        "type":    "rss",
        "url":     "https://news.ycombinator.com/rss",
        "trust":   "medium",
        "category":"tech",
        "max_items": 20,
    },
    {
        "name":    "mit_tech_review",
        "display": "MIT Tech Review",
        "page":    "techpulse",
        "type":    "rss",
        "url":     "https://www.technologyreview.com/feed/",
        "trust":   "high",
        "category":"tech",
        "max_items": 10,
    },
    {
        "name":    "venturebeat",
        "display": "VentureBeat",
        "page":    "techpulse",
        "type":    "rss",
        "url":     "https://venturebeat.com/feed/",
        "trust":   "medium",
        "category":"tech",
        "max_items": 15,
    },
    # ── Google News — TechPulse ───────────────────────────────────────────────
    {
        "name":    "google_news_tech",
        "display": "Google News Tech",
        "page":    "techpulse",
        "type":    "rss",
        # Google News Technology topic feed (curated by Google)
        "url":     "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNREptZEhjU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
        "trust":   "high",
        "category":"tech",
        "max_items": 25,
    },
    {
        "name":    "google_news_ai",
        "display": "Google News AI",
        "page":    "techpulse",
        "type":    "rss",
        # Targeted search: AI, LLMs, OpenAI, startups
        "url":     "https://news.google.com/rss/search?q=artificial+intelligence+OpenAI+LLM+startup+funding+tech&hl=en-US&gl=US&ceid=US:en",
        "trust":   "high",
        "category":"tech",
        "max_items": 25,
    },

    # ── CORPPULSE — Corporate News ────────────────────────────────────────────
    {
        "name":    "reuters_corp",
        "display": "Reuters Business",
        "page":    "corppulse",
        "type":    "rss",
        "url":     "https://feeds.reuters.com/reuters/businessNews",
        "trust":   "high",
        "category":"corporate",
        "max_items": 20,
    },
    {
        "name":    "forbes_corp",
        "display": "Forbes",
        "page":    "corppulse",
        "type":    "rss",
        "url":     "https://www.forbes.com/real-time/feed2/",
        "trust":   "high",
        "category":"corporate",
        "max_items": 15,
    },
    {
        "name":    "ft_corp",
        "display": "Financial Times",
        "page":    "corppulse",
        "type":    "rss",
        "url":     "https://www.ft.com/?format=rss",
        "trust":   "high",
        "category":"corporate",
        "max_items": 15,
    },
    {
        "name":    "cnbc_biz",
        "display": "CNBC Business",
        "page":    "corppulse",
        "type":    "rss",
        "url":     "https://www.cnbc.com/id/10001147/device/rss/rss.html",
        "trust":   "high",
        "category":"corporate",
        "max_items": 15,
    },
    {
        "name":    "business_insider",
        "display": "Business Insider",
        "page":    "corppulse",
        "type":    "rss",
        "url":     "https://feeds.businessinsider.com/custom/all",
        "trust":   "medium",
        "category":"corporate",
        "max_items": 15,
    },
    {
        "name":    "sec_edgar_corp",
        "display": "SEC 8-K Filings",
        "page":    "corppulse",
        "type":    "rss",
        "url":     "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=40&output=atom",
        "trust":   "primary",
        "category":"filing",
        "max_items": 20,
        "score_boost": 20,
    },
    # ── Google News — CorpPulse ───────────────────────────────────────────────
    {
        "name":    "google_news_corp",
        "display": "Google News Business",
        "page":    "corppulse",
        "type":    "rss",
        # Google News Business topic feed (curated by Google)
        "url":     "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
        "trust":   "high",
        "category":"corporate",
        "max_items": 25,
    },
    {
        "name":    "google_news_earnings",
        "display": "Google News Earnings",
        "page":    "corppulse",
        "type":    "rss",
        # Targeted search: CEO moves, earnings, M&A
        "url":     "https://news.google.com/rss/search?q=CEO+earnings+merger+acquisition+corporate+layoffs+IPO&hl=en-US&gl=US&ceid=US:en",
        "trust":   "high",
        "category":"corporate",
        "max_items": 25,
    },

    # ── WORLDPULSE — Global News ──────────────────────────────────────────────
    {
        "name":    "bbc_world",
        "display": "BBC World",
        "page":    "worldpulse",
        "type":    "rss",
        "url":     "https://feeds.bbci.co.uk/news/world/rss.xml",
        "trust":   "high",
        "category":"world",
        "max_items": 20,
    },
    {
        "name":    "reuters_world",
        "display": "Reuters World",
        "page":    "worldpulse",
        "type":    "rss",
        "url":     "https://feeds.reuters.com/reuters/worldNews",
        "trust":   "high",
        "category":"world",
        "max_items": 20,
    },
    {
        "name":    "aljazeera",
        "display": "Al Jazeera",
        "page":    "worldpulse",
        "type":    "rss",
        "url":     "https://www.aljazeera.com/xml/rss/all.xml",
        "trust":   "high",
        "category":"world",
        "max_items": 20,
    },
    {
        "name":    "ap_news",
        "display": "AP News",
        "page":    "worldpulse",
        "type":    "rss",
        "url":     "https://rsshub.app/apnews/topics/world-news",
        "trust":   "high",
        "category":"world",
        "max_items": 20,
    },
    {
        "name":    "nyt_world",
        "display": "NYT World",
        "page":    "worldpulse",
        "type":    "rss",
        "url":     "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "trust":   "high",
        "category":"world",
        "max_items": 15,
    },
    {
        "name":    "guardian_world",
        "display": "The Guardian",
        "page":    "worldpulse",
        "type":    "rss",
        "url":     "https://www.theguardian.com/world/rss",
        "trust":   "high",
        "category":"world",
        "max_items": 15,
    },
    {
        "name":    "france24",
        "display": "France 24",
        "page":    "worldpulse",
        "type":    "rss",
        "url":     "https://www.france24.com/en/rss",
        "trust":   "medium",
        "category":"world",
        "max_items": 15,
    },
    # ── Google News — WorldPulse ──────────────────────────────────────────────
    {
        "name":    "google_news_world",
        "display": "Google News World",
        "page":    "worldpulse",
        "type":    "rss",
        # Google News World topic feed (curated by Google)
        "url":     "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
        "trust":   "high",
        "category":"world",
        "max_items": 25,
    },
    {
        "name":    "google_news_geopolitics",
        "display": "Google News Geopolitics",
        "page":    "worldpulse",
        "type":    "rss",
        # Targeted search: elections, conflict, diplomacy
        "url":     "https://news.google.com/rss/search?q=election+conflict+diplomacy+geopolitics+sanctions+war+ceasefire&hl=en-US&gl=US&ceid=US:en",
        "trust":   "high",
        "category":"world",
        "max_items": 25,
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# SCORING CONFIG
# ══════════════════════════════════════════════════════════════════════════════

KEYWORDS = {
    "finpulse":  [
        "fed","federal reserve","rate","interest rate","inflation","cpi","gdp",
        "recession","rally","crash","surge","plunge","earnings","profit","loss",
        "revenue","stocks","bitcoin","crypto","market","nasdaq","dow","s&p 500",
        "billion","trillion","ipo","merger","acquisition","layoff","bankrupt",
        "hedge fund","portfolio","dividend","bond","yield","treasury","debt",
        "unemployment","jobs","payroll","rate hike","rate cut","powell",
    ],
    "techpulse": [
        "ai","artificial intelligence","chatgpt","openai","gpt","llm","gemini",
        "claude","google","apple","microsoft","meta","amazon","nvidia","startup",
        "funding","series a","series b","launch","breakthrough","robot","chip",
        "semiconductor","cybersecurity","hack","breach","ransomware","cloud",
        "quantum","autonomous","self-driving","drone","space","satellite",
        "acquisition","ipo","valuation","billion",
    ],
    "corppulse": [
        "ceo","cfo","coo","resign","fired","hired","appointment","acquisition",
        "merger","deal","billion","revenue","profit","loss","layoff","strike",
        "lawsuit","fraud","investigation","scandal","dividend","spinoff",
        "bankruptcy","restructuring","ipo","activist investor","board","shares",
        "buyback","takeover","hostile","settlement","class action",
    ],
    "worldpulse": [
        "war","conflict","peace","ceasefire","treaty","election","president",
        "prime minister","government","sanctions","trade war","diplomacy",
        "crisis","protest","coup","revolution","disaster","earthquake","flood",
        "hurricane","climate","nato","un","g7","g20","nuclear","missile",
        "refugee","immigration","border","tariff","summit","bilateral",
    ],
}

TRUST_SCORES = {
    "primary": 25,   # government/regulatory sources (SEC, Fed, BLS)
    "high":    15,   # major established publications
    "medium":   8,   # known but less authoritative
    "low":      2,   # aggregators, community sources
}

RECENCY_SCORES = {
    # (max_hours, score)
    2:   30,
    6:   22,
    12:  14,
    24:   8,
    48:   3,
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

# Media RSS namespace (Yahoo Finance, Reuters, Verge, etc.)
_MEDIA_NS = {"media": "http://search.yahoo.com/mrss/"}


def _extract_images_from_item(item: ET.Element, is_atom: bool, ns: dict) -> list[str]:
    """
    Extract all image URLs from an RSS/Atom item.
    Checks: media:content, media:thumbnail, enclosure, img tags in description HTML.
    Returns a deduplicated list of absolute image URLs.
    """
    import html as _html_mod
    images = []

    # 1. media:content elements (Yahoo Finance, Reuters, The Verge…)
    for mc in item.findall("media:content", _MEDIA_NS):
        url    = (mc.get("url") or "").strip()
        medium = mc.get("medium", "")
        mime   = mc.get("type", "")
        if url and url.startswith("http") and (
            medium == "image" or mime.startswith("image") or
            any(url.lower().endswith(e) for e in (".jpg", ".jpeg", ".png", ".webp", ".gif"))
        ):
            images.append(url)

    # 2. media:thumbnail elements
    for mt in item.findall("media:thumbnail", _MEDIA_NS):
        url = (mt.get("url") or "").strip()
        if url and url.startswith("http"):
            images.append(url)

    # 3. enclosure (some feeds attach images this way)
    for enc in item.findall("enclosure"):
        url  = (enc.get("url") or "").strip()
        mime = enc.get("type", "")
        if url and url.startswith("http") and mime.startswith("image"):
            images.append(url)

    # 4. <img> tags embedded in description/content HTML (BBC, Google News, etc.)
    desc_paths = (
        ["{http://www.w3.org/2005/Atom}content", "{http://www.w3.org/2005/Atom}summary"]
        if is_atom else ["description"]
    )
    for path in desc_paths:
        el = item.find(path)
        if el is not None and el.text:
            text  = _html_mod.unescape(el.text)
            found = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', text, re.I)
            images.extend(u for u in found if u.startswith("http"))

    # Deduplicate preserving order
    seen, result = set(), []
    for u in images:
        u = u.strip()
        if u and u not in seen:
            seen.add(u)
            result.append(u)
    return result


def _is_content_image(url: str) -> bool:
    """Filter out non-content images — icons, logos, trackers, tiny UI elements."""
    if not url or not url.startswith("http"):
        return False
    u = url.lower()
    # Skip known noise
    skip = [
        "logo", "icon", "avatar", "sprite", "1x1", "pixel", "1px",
        "tracking", "beacon", "analytics", "doubleclick", "ads", "adsys",
        "badge", "spinner", "loading", "placeholder", "spacer", "blank",
        "favicon", "arrow", "bullet", "dot.png", "dot.gif",
        "/s.gif", "/b.gif", "transparent", "clear.gif",
    ]
    if any(k in u for k in skip):
        return False
    # SVG icons are usually UI elements, not editorial photos
    if u.endswith(".svg"):
        return False
    # Must look like an image (extension or CDN keyword)
    img_ext = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")
    cdn_kw  = ["cloudfront", "akamaized", "fastly", "cloudinary", "imgix",
               "wp-content/uploads", "/images/", "/media/", "/photos/",
               "/img/", "/assets/", "/picture/", "thumbor", "resize"]
    has_ext = any(ext in u for ext in img_ext)
    has_cdn = any(k in u for k in cdn_kw)
    return has_ext or has_cdn


def _extract_article_content(url: str) -> dict:
    """
    Fetch the article page and extract body text + ALL content images.

    Strategy (layered):
      1. newspaper3k — best body text + top_image
      2. BeautifulSoup — scrape every <img>, <picture>, srcset from article/main elements
      3. Regex fallback — og:image meta tag + img[src] from raw HTML

    Returns {"body": str, "og_image": str, "images": list[str]}   (images capped at 30)
    """
    result: dict = {"body": "", "og_image": "", "images": []}
    try:
        raw_html = ""

        # ── Step 1: newspaper3k ──────────────────────────────────────────────
        try:
            from newspaper import Article as _NpArt  # type: ignore
            art = _NpArt(url, fetch_images=True, request_timeout=12)
            art.download()
            art.parse()
            result["body"]     = (art.text or "")[:6000]
            result["og_image"] = art.top_image or ""
            np_imgs = [str(i) for i in (art.images or []) if str(i).startswith("http")]
            result["images"]   = [i for i in np_imgs if _is_content_image(i)]
            raw_html           = art.html or ""
        except (ImportError, ModuleNotFoundError):
            pass
        except Exception:
            pass

        # ── Step 2: full HTML scrape ─────────────────────────────────────────
        if not raw_html:
            try:
                resp = requests.get(url, headers=HEADERS, timeout=12)
                raw_html = resp.text
            except Exception:
                pass

        html_chunk = raw_html[:400_000]  # 400 KB cap

        try:
            from bs4 import BeautifulSoup  # type: ignore  (ships with newspaper3k)

            soup = BeautifulSoup(html_chunk, "html.parser")

            # og:image (most reliable single hero image)
            og_meta = (soup.find("meta", property="og:image") or
                       soup.find("meta", attrs={"name": "og:image"}) or
                       soup.find("meta", attrs={"property": "og:image:secure_url"}))
            if og_meta:
                og_url = (og_meta.get("content") or "").strip()
                if og_url and og_url.startswith("http"):
                    result["og_image"] = result["og_image"] or og_url
                    result["images"].insert(0, og_url)

            # Prefer article / main content area to avoid nav / sidebar clutter
            content_root = (soup.find("article") or
                            soup.find("main") or
                            soup.find(attrs={"class": re.compile(
                                r"(article|content|story|post|entry|body)[-_ ]?(body|text|wrap|inner)?",
                                re.I)}) or
                            soup.body or soup)

            def _harvest_imgs(el):
                """Yield all candidate image URLs from an element."""
                for img in el.find_all(["img", "source"]):
                    # Try srcset first — grab the URL part(s)
                    for attr in ("srcset", "data-srcset"):
                        srcset_val = img.get(attr, "")
                        if srcset_val:
                            for part in srcset_val.split(","):
                                candidate = part.strip().split()[0]
                                if candidate.startswith("http"):
                                    yield candidate
                    # Then src / data-src / data-lazy-src
                    for attr in ("src", "data-src", "data-lazy-src",
                                 "data-original", "data-url"):
                        val = (img.get(attr) or "").strip()
                        if val.startswith("http"):
                            yield val

            for img_url in _harvest_imgs(content_root):
                if _is_content_image(img_url):
                    result["images"].append(img_url)

        except (ImportError, ModuleNotFoundError):
            # ── Step 3: regex fallback ─────────────────────────────────────
            def _og_meta(prop: str) -> str:
                m = (re.search(
                        rf'<meta[^>]+property=["\']og:{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)["\']',
                        html_chunk, re.I) or
                     re.search(
                        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:{re.escape(prop)}["\']',
                        html_chunk, re.I))
                return m.group(1).strip() if m else ""

            og = _og_meta("image")
            if og:
                result["og_image"] = result["og_image"] or og
                result["images"].insert(0, og)

            # img[src]
            for src in re.findall(
                    r'<img[^>]+(?:src|data-src|data-lazy-src)=["\']([^"\']+)["\']',
                    html_chunk, re.I):
                if _is_content_image(src):
                    result["images"].append(src)

            # srcset
            for srcset_raw in re.findall(r'srcset=["\']([^"\']+)["\']', html_chunk, re.I):
                for part in srcset_raw.split(","):
                    candidate = part.strip().split()[0]
                    if _is_content_image(candidate):
                        result["images"].append(candidate)

    except Exception:
        pass

    # ── Deduplicate and cap ──────────────────────────────────────────────────
    seen, unique = set(), []
    for u in result["images"]:
        u = u.strip()
        if u and u not in seen and len(u) < 600:
            seen.add(u)
            unique.append(u)
    result["images"] = unique[:30]

    if not result["og_image"] and result["images"]:
        result["og_image"] = result["images"][0]

    return result


# ══════════════════════════════════════════════════════════════════════════════
# ARTICLE SCHEMA
# ══════════════════════════════════════════════════════════════════════════════
"""
Every article returned by this module has this structure:

{
    "title":        str,   REQUIRED  — Headline text
    "summary":      str,   — First 500 chars of body/description
    "url":          str,   — Full article URL
    "source_name":  str,   — Display name e.g. "Reuters Finance"
    "source_key":   str,   — Machine name e.g. "reuters_finance"
    "page":         str,   — "finpulse" | "techpulse" | "corppulse" | "worldpulse"
    "category":     str,   — "markets" | "macro" | "tech" | "corporate" | "world" | "filing"
    "published_at": str,   — ISO 8601 timestamp from source, or "" if unknown
    "fetched_at":   str,   — ISO 8601 when we fetched it
    "score":        float, — Relevance score 0–100
    "score_breakdown": {
        "keywords": float,
        "recency":  float,
        "trust":    float,
        "boost":    float,
    },
    "article_hash": str,   — MD5 of normalized title (dedup key)
}
"""


# ══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def _normalize_title(title: str) -> str:
    """Lowercase, strip punctuation and extra whitespace for hashing."""
    t = title.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _article_hash(title: str) -> str:
    return hashlib.md5(_normalize_title(title).encode()).hexdigest()


def _word_set(title: str) -> frozenset:
    """Meaningful 4+ char words for Jaccard dedup."""
    return frozenset(re.findall(r"\b\w{4,}\b", title.lower()))


def _clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(s: str) -> str:
    if not s:
        return ""
    for fn in (
        parsedate_to_datetime,
        lambda x: datetime.fromisoformat(x.replace("Z", "+00:00")),
    ):
        try:
            dt = fn(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass
    return ""


def _age_hours(published_at: str) -> Optional[float]:
    """Return hours since published_at, or None if unknown."""
    if not published_at:
        return None
    try:
        dt = datetime.fromisoformat(published_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return delta.total_seconds() / 3600
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# SCORING ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def score_article(article: dict, page: str, source_config: dict) -> dict:
    """
    Score an article 0–100 for relevance. Adds score + score_breakdown to article.

    Signals:
      1. Keyword density (0–50 pts)  — how many niche keywords appear
      2. Recency         (0–30 pts)  — how fresh the article is
      3. Source trust    (0–25 pts)  — is this a primary/high/medium source
      4. Boost           (0–30 pts)  — optional source-level score_boost
    """
    kws  = KEYWORDS.get(page, [])
    text = f"{article.get('title','')} {article.get('summary','')}".lower()

    # 1. Keyword density — count unique keyword matches, cap at 50
    matched = sum(1 for kw in kws if kw in text)
    kw_score = min(matched * 8, 50)

    # 2. Recency
    age_h = _age_hours(article.get("published_at", ""))
    rec_score = 0
    if age_h is not None:
        for max_h, pts in sorted(RECENCY_SCORES.items()):
            if age_h <= max_h:
                rec_score = pts
                break

    # 3. Source trust
    trust_key  = source_config.get("trust", "medium")
    trust_score = TRUST_SCORES.get(trust_key, 8)

    # 4. Source-level boost (e.g. SEC filings always important)
    boost = source_config.get("score_boost", 0)

    total = round(min(kw_score + rec_score + trust_score + boost, 100), 1)

    article["score"] = total
    article["score_breakdown"] = {
        "keywords": kw_score,
        "recency":  rec_score,
        "trust":    trust_score,
        "boost":    boost,
    }
    return article


# ══════════════════════════════════════════════════════════════════════════════
# RSS PARSER
# ══════════════════════════════════════════════════════════════════════════════

def _parse_rss(xml_text: str, source_config: dict, max_items: int) -> list[dict]:
    """
    Parse RSS 2.0 or Atom XML into article dicts.
    Handles both RSS <item> and Atom <entry> formats.
    """
    articles = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        return []

    ns  = {"atom": "http://www.w3.org/2005/Atom"}
    tag = root.tag.lower()
    is_atom = "atom" in tag or root.tag.startswith("{http://www.w3.org/2005/Atom}")

    def _t(el, path, ns_=None):
        """Safe tag text getter."""
        found = el.find(path, ns_) if ns_ else el.find(path)
        return (found.text or "").strip() if found is not None and found.text else ""

    items = (root.findall("atom:entry", ns) if is_atom
             else root.findall(".//item"))

    for item in items[:max_items]:
        if is_atom:
            title   = _t(item, "atom:title",   ns)
            summary = _t(item, "atom:summary", ns) or _t(item, "atom:content", ns)
            link_el = item.find("atom:link", ns)
            url     = link_el.get("href", "") if link_el is not None else ""
            pub     = _t(item, "atom:published", ns) or _t(item, "atom:updated", ns)
        else:
            title   = _t(item, "title")
            summary = _t(item, "description")
            url     = _t(item, "link")
            pub     = _t(item, "pubDate")

        title = title.strip()
        if not title or len(title) < 10:
            continue

        published_at = _parse_date(pub)

        # Skip articles older than 72h if we have a date
        age = _age_hours(published_at)
        if age is not None and age > 72:
            continue

        # Extract images from the RSS item itself (fast — no extra HTTP requests)
        images = _extract_images_from_item(item, is_atom, ns)

        articles.append({
            "title":        title,
            "summary":      _clean_html(summary or "")[:500],
            "url":          url.strip(),
            "source_name":  source_config["display"],
            "source_key":   source_config["name"],
            "page":         source_config["page"],
            "category":     source_config.get("category", ""),
            "published_at": published_at,
            "fetched_at":   datetime.now(timezone.utc).isoformat(),
            "score":        0.0,
            "score_breakdown": {},
            "article_hash": _article_hash(title),
            "image_url":    images[0] if images else "",
            "image_urls":   images,
        })

    return articles


# ══════════════════════════════════════════════════════════════════════════════
# HTTP FETCHER (with retry)
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_url(url: str, timeout: int = 12, retries: int = 2) -> Optional[str]:
    """
    Fetch a URL with retry + exponential backoff.
    Returns response text or None on failure.
    """
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.Timeout:
            if attempt < retries:
                time.sleep(2 ** attempt)
            else:
                return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in (429, 503) and attempt < retries:
                time.sleep(3 * (attempt + 1))
            else:
                return None
        except requests.exceptions.RequestException:
            return None
    return None


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE SOURCE FETCHER
# ══════════════════════════════════════════════════════════════════════════════

def fetch_source(source_config: dict) -> tuple[str, list[dict], str]:
    """
    Fetch one source. Returns (source_name, articles, status).
    Called in parallel by fetch_page().
    """
    name       = source_config["display"]
    url        = source_config.get("url")
    max_items  = source_config.get("max_items", 20)
    page       = source_config["page"]

    if not url:
        return name, [], "no_url"

    xml_text = _fetch_url(url)
    if not xml_text:
        return name, [], "fetch_failed"

    articles = _parse_rss(xml_text, source_config, max_items)
    if not articles:
        return name, [], "empty"

    # Score each article
    for a in articles:
        score_article(a, page, source_config)

    # ── Image enrichment ──────────────────────────────────────────────────────
    # For top-scored articles that have no image from RSS, scrape the page for
    # ALL content images. Take top 15 per source (fast enough, comprehensive).
    articles_needing_image = [
        a for a in articles if not a.get("image_url") and a.get("url")
    ]
    articles_needing_image.sort(key=lambda x: x.get("score", 0), reverse=True)
    for a in articles_needing_image[:15]:
        try:
            content = _extract_article_content(a["url"])
            if content.get("og_image"):
                a["image_url"]  = content["og_image"]
                all_imgs = [content["og_image"]] + content.get("images", [])
                a["image_urls"] = list(dict.fromkeys(all_imgs))
            elif content.get("images"):
                a["image_url"]  = content["images"][0]
                a["image_urls"] = content["images"]
            if content.get("body") and not a.get("article_body"):
                a["article_body"] = content["body"]
        except Exception:
            pass

    return name, articles, "ok"


# ══════════════════════════════════════════════════════════════════════════════
# DEDUPLICATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def deduplicate_in_memory(articles: list[dict], threshold: float = 0.55) -> list[dict]:
    """
    Remove near-duplicate articles using Jaccard similarity on title words.
    When two articles are duplicates, keep the one with the higher score.
    """
    unique = []
    seen_word_sets = []
    seen_hashes = set()

    # Sort by score descending first — so we keep the best version of a story
    articles = sorted(articles, key=lambda x: x.get("score", 0), reverse=True)

    for article in articles:
        ah = article.get("article_hash", "")
        if ah in seen_hashes:
            continue

        words = _word_set(article["title"])
        if not words:
            continue

        is_dup = False
        for seen_words in seen_word_sets:
            if not seen_words:
                continue
            union = seen_words | words
            inter = seen_words & words
            if union and (len(inter) / len(union)) > threshold:
                is_dup = True
                break

        if not is_dup:
            seen_word_sets.append(words)
            seen_hashes.add(ah)
            unique.append(article)

    return unique


def deduplicate_against_db(articles: list[dict], hours: int = 48) -> list[dict]:
    """
    Filter out articles whose title hash is already in the DB
    (fetched within the last `hours` hours).
    Falls back to returning all articles if DB is unavailable.
    """
    try:
        from database.schema import get_connection
        conn = get_connection()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        rows = conn.execute(
            "SELECT article_hash FROM articles WHERE fetched_at >= ?",
            (cutoff,)
        ).fetchall()
        conn.close()

        known_hashes = {r[0] for r in rows}
        new = [a for a in articles if a.get("article_hash") not in known_hashes]
        return new

    except Exception:
        # DB not available (e.g. sandbox) — return all articles
        return articles


# ══════════════════════════════════════════════════════════════════════════════
# SAVE TO DATABASE
# ══════════════════════════════════════════════════════════════════════════════

def save_articles(articles: list[dict]) -> tuple[int, int]:
    """
    Save articles to the database.
    Returns (saved_count, skipped_count).
    """
    saved   = 0
    skipped = 0

    try:
        from database.models import save_article
        for a in articles:
            result = save_article(a)
            if result:
                saved += 1
            else:
                skipped += 1
    except Exception as e:
        print(f"  ⚠️  DB save error: {e}")
        return 0, len(articles)

    return saved, skipped


# ══════════════════════════════════════════════════════════════════════════════
# UPDATE SOURCE STATUS
# ══════════════════════════════════════════════════════════════════════════════

def _update_source_status(source_key: str, status: str, count: int = 0):
    try:
        from database.models import update_source_status
        update_source_status(source_key, status, count)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINTS
# ══════════════════════════════════════════════════════════════════════════════

def fetch_page(page: str, top_n: int = 10, dry_run: bool = False,
               max_workers: int = 6) -> list[dict]:
    """
    Fetch, deduplicate, score, and save all news for one page.

    Args:
        page:        "finpulse" | "techpulse" | "corppulse" | "worldpulse"
        top_n:       how many top articles to return
        dry_run:     if True, don't write to DB
        max_workers: max parallel HTTP threads

    Returns:
        List of top N article dicts, sorted by score descending
    """
    start = time.time()
    print(f"\n{'='*62}")
    print(f"  📡  FETCH: {page.upper()}  —  {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*62}")

    page_sources = [s for s in SOURCES if s["page"] == page]
    if not page_sources:
        print(f"  ❌ No sources configured for '{page}'")
        return []

    print(f"  Sources: {len(page_sources)}")

    # ── Parallel fetch ────────────────────────────────────────────────────────
    all_articles = []
    results_log  = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fetch_source, s): s for s in page_sources}

        for future in as_completed(futures):
            src = futures[future]
            try:
                name, articles, status = future.result(timeout=35)
                count = len(articles)
                all_articles.extend(articles)

                icon = "✓" if status == "ok" else "✗"
                results_log.append((icon, name, count, status))
                _update_source_status(src["name"], status if status != "ok" else "ok", count)

            except Exception as e:
                results_log.append(("✗", src["display"], 0, str(e)[:40]))
                _update_source_status(src["name"], "error")

    # Print source results table
    print()
    for icon, name, count, status in results_log:
        pad = 24 - len(name)
        bar = ("  +" + "─" * min(count // 2, 20)) if count > 0 else ""
        print(f"  {icon} {name}{' '*pad}  {count:3d} articles{bar}")

    print(f"\n  📥 Total raw:   {len(all_articles)}")

    # ── Deduplication ─────────────────────────────────────────────────────────
    unique = deduplicate_in_memory(all_articles)
    print(f"  🔀 After in-memory dedup: {len(unique)}")

    if not dry_run:
        new_articles = deduplicate_against_db(unique, hours=48)
        print(f"  🆕 New (not in DB):       {len(new_articles)}")
    else:
        new_articles = unique

    # ── Sort by score ─────────────────────────────────────────────────────────
    new_articles.sort(key=lambda x: x.get("score", 0), reverse=True)

    # ── Save to DB ────────────────────────────────────────────────────────────
    if not dry_run and new_articles:
        # Set page on all articles
        for a in new_articles:
            a["page"] = page
        saved, skipped = save_articles(new_articles)
        print(f"  💾 Saved: {saved} new  |  Skipped: {skipped} known")

    # ── Top N results ─────────────────────────────────────────────────────────
    top = new_articles[:top_n] if dry_run else _get_top_from_db(page, top_n)

    elapsed = time.time() - start
    print(f"\n  ⏱️  Completed in {elapsed:.1f}s")
    print(f"\n  🏆 Top {len(top)} articles:")
    for i, a in enumerate(top, 1):
        bd = a.get("score_breakdown", {})
        kw = bd.get("keywords", "?")
        rc = bd.get("recency", "?")
        ts = bd.get("trust", "?")
        bst = bd.get("boost", 0)
        score_str = f"{a['score']:.0f}pts (kw:{kw} rc:{rc} tr:{ts}{f' bo:{bst}' if bst else ''})"
        print(f"  {i:2}. [{score_str}] {a['title'][:58]}")
        print(f"       └─ {a.get('source_name','?')}  {a.get('published_at','')[:16]}")

    return top


def fetch_one_source(display_name: str) -> dict:
    """
    Fetch, deduplicate, and save articles for a single source by display name.
    Called from the dashboard Refetch button.
    Returns {"saved": int, "total": int, "status": str}
    """
    config = next((s for s in SOURCES if s["display"] == display_name), None)
    if not config:
        return {"error": f"Unknown source: {display_name}", "saved": 0, "total": 0}

    try:
        name, articles, status = fetch_source(config)
    except Exception as e:
        _update_source_status(config["name"], "error")
        return {"error": str(e), "saved": 0, "total": 0, "status": "error"}

    _update_source_status(config["name"], status, len(articles))

    if not articles:
        return {"saved": 0, "total": 0, "status": status}

    # Deduplicate against DB
    unique = deduplicate_in_memory(articles)
    new_articles = []
    try:
        from database.models import article_exists
        for a in unique:
            if not article_exists(a["title"]):
                new_articles.append(a)
    except Exception:
        new_articles = unique

    # Ensure page is set
    for a in new_articles:
        a["page"] = config["page"]

    saved, skipped = save_articles(new_articles)
    return {"saved": saved, "total": len(articles), "status": "ok"}


def fetch_all_pages(top_n: int = 5, dry_run: bool = False) -> dict[str, list]:
    """
    Fetch all 4 pages. Returns dict mapping page → top articles.
    """
    pages = ["finpulse", "techpulse", "corppulse", "worldpulse"]
    results = {}
    for page in pages:
        try:
            results[page] = fetch_page(page, top_n=top_n, dry_run=dry_run)
        except Exception as e:
            print(f"  ❌ Failed for {page}: {e}")
            results[page] = []
    return results


def _get_top_from_db(page: str, limit: int) -> list[dict]:
    """Get top N unposted articles from DB after saving."""
    try:
        from database.models import get_top_articles
        return get_top_articles(page, limit=limit)
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE INSPECTION HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def list_sources(page: str = None) -> list[dict]:
    """Return all sources, optionally filtered by page."""
    if page:
        return [s for s in SOURCES if s["page"] == page]
    return SOURCES


def source_count_by_page() -> dict:
    """Return count of sources per page."""
    counts = {}
    for s in SOURCES:
        counts[s["page"]] = counts.get(s["page"], 0) + 1
    return counts


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    target  = "finpulse"
    top_n   = 10
    dry_run = False

    for arg in sys.argv[1:]:
        if arg == "--dry-run":  dry_run = True
        elif arg == "--all":    target  = "all"
        elif arg in ("finpulse", "techpulse", "corppulse", "worldpulse", "all"):
            target = arg
        elif arg.startswith("--top="):
            try: top_n = int(arg.split("=")[1])
            except: pass

    print(f"\n⚡ PULSE MEDIA — News Fetcher v2")
    counts = source_count_by_page()
    for p, c in counts.items():
        print(f"   {p:12} {c} sources")

    if target == "all":
        fetch_all_pages(top_n=top_n, dry_run=dry_run)
    else:
        fetch_page(target, top_n=top_n, dry_run=dry_run)
