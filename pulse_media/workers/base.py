from __future__ import annotations
"""
workers/base.py — BaseWorker
Every source worker inherits from this class and implements fetch().

The contract:
  - Each worker knows one source (Yahoo Finance, CNBC, SEC EDGAR, etc.)
  - fetch() returns a list of Article dicts in the STANDARD FORMAT
  - Errors are caught inside the worker — never crash the pipeline
  - Workers update their own DB status after each fetch
"""

import re
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
import requests

# ─────────────────────────────────────────────
# STANDARD ARTICLE FORMAT
# Every worker must return articles in this shape.
# ─────────────────────────────────────────────
"""
Article = {
    "title":        str,   # Headline — required
    "summary":      str,   # First 500 chars of body — empty string if none
    "url":          str,   # Full article URL
    "source_name":  str,   # Display name e.g. "Reuters"
    "source_id":    int,   # DB ID from sources table (set by orchestrator)
    "page":         str,   # "finpulse" | "techpulse" | "corppulse" | "worldpulse"
    "category":     str,   # "earnings" | "macro" | "crypto" | "" etc.
    "published_at": str,   # ISO 8601 string e.g. "2026-07-05T14:30:00+00:00"
    "score":        float, # Relevance score 0–100 (set by orchestrator scorer)
}
"""

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PulseMediaBot/1.0)"}

KEYWORDS = {
    "finpulse":  ["fed","rate","interest","inflation","gdp","recession","rally",
                  "crash","surge","plunge","earnings","profit","loss","stocks",
                  "bitcoin","crypto","market","nasdaq","dow","s&p","billion",
                  "trillion","ipo","merger","acquisition","layoff","bankrupt"],
    "techpulse": ["ai","artificial intelligence","chatgpt","openai","google",
                  "apple","microsoft","meta","amazon","startup","funding",
                  "launch","breakthrough","robot","chip","semiconductor",
                  "cybersecurity","hack","breach","cloud","quantum"],
    "corppulse": ["ceo","cfo","resign","fired","hired","acquisition","merger",
                  "deal","billion","revenue","profit","loss","layoff","strike",
                  "lawsuit","fraud","investigation","scandal","dividend"],
    "worldpulse": ["war","conflict","peace","treaty","election","president",
                   "government","sanctions","trade","diplomacy","crisis",
                   "protest","disaster","earthquake","flood","climate","nato"],
}

TRUSTED = ["reuters","bloomberg","cnbc","bbc","ft.com","wsj","nytimes",
           "apnews","marketwatch","techcrunch","sec.gov","federalreserve.gov"]


class BaseWorker(ABC):
    """
    Abstract base class for all news source workers.

    Subclasses must set:
        name         — unique snake_case ID  e.g. "yahoo_finance"
        display_name — human label           e.g. "Yahoo Finance"
        page         — which page            e.g. "finpulse"
        source_type  — "rss" | "api" | "library"

    Subclasses must implement:
        fetch() -> list[dict]   — return list of Article dicts
    """

    name:         str = ""
    display_name: str = ""
    page:         str = ""
    source_type:  str = "rss"

    def run(self) -> list[dict]:
        """
        Public entry point called by the orchestrator.
        Wraps fetch() with error handling and DB status updates.
        """
        from database.models import update_source_status, log_error
        try:
            print(f"  [{self.display_name}] Fetching...")
            articles = self.fetch()
            update_source_status(self.name, "ok", len(articles))
            print(f"  [{self.display_name}] ✓ {len(articles)} articles")
            return articles
        except requests.exceptions.Timeout:
            msg = "Request timed out"
            log_error(self.name, "timeout", msg)
            update_source_status(self.name, "timeout")
            print(f"  [{self.display_name}] ✗ Timeout")
            return []
        except requests.exceptions.RequestException as e:
            log_error(self.name, "http_error", str(e))
            update_source_status(self.name, "error")
            print(f"  [{self.display_name}] ✗ HTTP error: {e}")
            return []
        except TypeError as e:
            if "GenericAlias" in str(e):
                print(f"  [{self.display_name}] Skipped — requires Python 3.10+ (you have 3.9)")
                update_source_status(self.name, "error")
            else:
                log_error(self.name, "parse_error", str(e))
                update_source_status(self.name, "error")
                print(f"  [{self.display_name}] ✗ Error: {e}")
            return []
        except Exception as e:
            log_error(self.name, "parse_error", str(e))
            update_source_status(self.name, "error")
            print(f"  [{self.display_name}] ✗ Error: {e}")
            return []

    @abstractmethod
    def fetch(self) -> list[dict]:
        """Fetch articles and return them in standard Article format."""
        pass

    # ── Shared utilities all workers can use ──

    def _get(self, url: str, timeout: int = 10, **kwargs) -> requests.Response:
        """HTTP GET with standard headers and timeout."""
        return requests.get(url, timeout=timeout, headers=HEADERS, **kwargs)

    def _parse_rss(self, xml_text: str, max_items: int = 20) -> list[dict]:
        """
        Parse RSS 2.0 or Atom XML into a list of raw article dicts.
        Returns: [{title, summary, url, published_at}, ...]
        """
        articles = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        is_atom = "Atom" in root.tag or root.tag.startswith("{http://www.w3.org/2005/Atom}")

        items = root.findall("atom:entry", ns) if is_atom else root.findall(".//item")

        for item in items[:max_items]:
            if is_atom:
                title   = self._tag(item, "atom:title", ns)
                summary = self._tag(item, "atom:summary", ns) or self._tag(item, "atom:content", ns)
                link_el = item.find("atom:link", ns)
                url     = link_el.get("href", "") if link_el is not None else ""
                pub     = self._tag(item, "atom:published", ns) or self._tag(item, "atom:updated", ns)
            else:
                title   = self._tag(item, "title")
                summary = self._tag(item, "description")
                url     = self._tag(item, "link")
                pub     = self._tag(item, "pubDate")

            title = (title or "").strip()
            if not title:
                continue

            articles.append({
                "title":        title,
                "summary":      self._clean(summary or "")[:500],
                "url":          (url or "").strip(),
                "published_at": self._parse_date(pub or ""),
                "source_name":  self.display_name,
                "page":         self.page,
                "category":     "",
                "score":        0.0,
            })

        return articles

    def _tag(self, el, tag: str, ns: dict = None) -> str:
        found = el.find(tag, ns) if ns else el.find(tag)
        return (found.text or "").strip() if found is not None and found.text else ""

    def _clean(self, text: str) -> str:
        """Strip HTML tags and extra whitespace."""
        text = re.sub(r"<[^>]+>", "", text)
        return re.sub(r"\s+", " ", text).strip()

    def _parse_date(self, s: str) -> str:
        """Parse RSS/Atom date to ISO 8601 string."""
        if not s:
            return ""
        for parser in (parsedate_to_datetime,
                       lambda x: datetime.fromisoformat(x.replace("Z", "+00:00"))):
            try:
                return parser(s).isoformat()
            except Exception:
                pass
        return ""

    def score(self, article: dict) -> float:
        """Score an article 0–100 for relevance to this page's niche."""
        s = 0.0
        text  = (article["title"] + " " + article["summary"]).lower()
        kws   = KEYWORDS.get(self.page, [])

        # Keyword match — up to 50 pts
        s += min(sum(8 for kw in kws if kw in text), 50)

        # Recency — up to 30 pts
        pub = article.get("published_at", "")
        if pub:
            try:
                dt = datetime.fromisoformat(pub)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
                s += 30 if age_h < 2 else 20 if age_h < 6 else 10 if age_h < 12 else 5 if age_h < 24 else 0
            except Exception:
                pass

        # Source trust — up to 20 pts
        src = article.get("source_name", "").lower()
        if any(t in src for t in TRUSTED):
            s += 20

        article["score"] = round(s, 1)
        return s
