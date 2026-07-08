"""
workers/rss_workers.py — All RSS-based workers
Each class = one source employee. All inherit BaseWorker.
"""

from workers.base import BaseWorker


# ── FINPULSE WORKERS ────────────────────────────────────────────

class YahooFinanceWorker(BaseWorker):
    name         = "yahoo_finance"
    display_name = "Yahoo Finance"
    page         = "finpulse"
    source_type  = "rss"
    URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC,^DJI,^IXIC&region=US&lang=en-US"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "markets"
            self.score(a)
        return articles


class CNBCMarketsWorker(BaseWorker):
    name         = "cnbc_markets"
    display_name = "CNBC Markets"
    page         = "finpulse"
    source_type  = "rss"
    URL = "https://www.cnbc.com/id/100003114/device/rss/rss.html"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "markets"
            self.score(a)
        return articles


class CNBCEconomyWorker(BaseWorker):
    name         = "cnbc_economy"
    display_name = "CNBC Economy"
    page         = "finpulse"
    source_type  = "rss"
    URL = "https://www.cnbc.com/id/10000664/device/rss/rss.html"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "macro"
            self.score(a)
        return articles


class MarketWatchWorker(BaseWorker):
    name         = "marketwatch"
    display_name = "MarketWatch"
    page         = "finpulse"
    source_type  = "rss"
    URL = "https://feeds.marketwatch.com/marketwatch/topstories/"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "markets"
            self.score(a)
        return articles


class ReutersBusinessWorker(BaseWorker):
    name         = "reuters_biz"
    display_name = "Reuters Business"
    page         = "finpulse"
    source_type  = "rss"
    URL = "https://www.reuters.com/arc/outboundfeeds/rss/?outputType=xml"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "business"
            self.score(a)
        return articles


class SECEdgarWorker(BaseWorker):
    """
    SEC EDGAR — official company filings (8-K forms).
    8-K = major company event: earnings, CEO change, merger, bankruptcy.
    This is PRIMARY SOURCE data — highest trust.
    """
    name         = "sec_edgar"
    display_name = "SEC EDGAR"
    page         = "finpulse"
    source_type  = "rss"
    URL = ("https://www.sec.gov/cgi-bin/browse-edgar"
           "?action=getcurrent&type=8-K&dateb=&owner=include&count=40&output=atom")

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "filing"
            a["source_name"] = "SEC EDGAR"
            # SEC filings are primary source — always high score
            a["score"] = max(a.get("score", 0), 70.0)
            self.score(a)
        return articles


class FederalReserveWorker(BaseWorker):
    """Federal Reserve press releases — rate decisions, policy statements."""
    name         = "federal_reserve"
    display_name = "Federal Reserve"
    page         = "finpulse"
    source_type  = "rss"
    URL = "https://www.federalreserve.gov/feeds/press_all.xml"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "macro"
            a["score"] = max(a.get("score", 0), 80.0)  # Fed news = always important
            self.score(a)
        return articles


class BLSWorker(BaseWorker):
    """Bureau of Labor Statistics — CPI (inflation), jobs reports."""
    name         = "bls_gov"
    display_name = "BLS (Inflation Data)"
    page         = "finpulse"
    source_type  = "rss"
    URL = "https://www.bls.gov/feed/bls_latest.rss"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "macro"
            self.score(a)
        return articles


# ── TECHPULSE WORKERS ───────────────────────────────────────────

class TechCrunchWorker(BaseWorker):
    name         = "techcrunch"
    display_name = "TechCrunch"
    page         = "techpulse"
    source_type  = "rss"
    URL = "https://techcrunch.com/feed/"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "tech"
            self.score(a)
        return articles


class TheVergeWorker(BaseWorker):
    name         = "the_verge"
    display_name = "The Verge"
    page         = "techpulse"
    source_type  = "rss"
    URL = "https://www.theverge.com/rss/index.xml"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "tech"
            self.score(a)
        return articles


class ArsTechnicaWorker(BaseWorker):
    name         = "ars_technica"
    display_name = "Ars Technica"
    page         = "techpulse"
    source_type  = "rss"
    URL = "https://feeds.arstechnica.com/arstechnica/index"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "tech"
            self.score(a)
        return articles


class HackerNewsWorker(BaseWorker):
    name         = "hacker_news"
    display_name = "Hacker News"
    page         = "techpulse"
    source_type  = "rss"
    URL = "https://news.ycombinator.com/rss"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "tech"
            self.score(a)
        return articles


# ── WORLDPULSE WORKERS ──────────────────────────────────────────

class BBCWorldWorker(BaseWorker):
    name         = "bbc_world"
    display_name = "BBC World"
    page         = "worldpulse"
    source_type  = "rss"
    URL = "https://feeds.bbci.co.uk/news/world/rss.xml"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "world"
            self.score(a)
        return articles


class ReutersWorldWorker(BaseWorker):
    name         = "reuters_world"
    display_name = "Reuters World"
    page         = "worldpulse"
    source_type  = "rss"
    URL = "https://www.reuters.com/arc/outboundfeeds/rss/?outputType=xml"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "world"
            self.score(a)
        return articles


class AlJazeeraWorker(BaseWorker):
    name         = "aljazeera"
    display_name = "Al Jazeera"
    page         = "worldpulse"
    source_type  = "rss"
    URL = "https://www.aljazeera.com/xml/rss/all.xml"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "world"
            self.score(a)
        return articles


# ── CORPPULSE WORKERS ───────────────────────────────────────────

class ForbesWorker(BaseWorker):
    name         = "forbes"
    display_name = "Forbes"
    page         = "corppulse"
    source_type  = "rss"
    URL = "https://www.forbes.com/real-time/feed2/"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "corporate"
            self.score(a)
        return articles


# ── WORKER REGISTRY — orchestrator imports this ─────────────────

ALL_WORKERS = [
    # FinPulse
    YahooFinanceWorker,
    CNBCMarketsWorker,
    CNBCEconomyWorker,
    MarketWatchWorker,
    ReutersBusinessWorker,
    SECEdgarWorker,
    FederalReserveWorker,
    BLSWorker,
    # TechPulse
    TechCrunchWorker,
    TheVergeWorker,
    ArsTechnicaWorker,
    HackerNewsWorker,
    # WorldPulse
    BBCWorldWorker,
    ReutersWorldWorker,
    AlJazeeraWorker,
    # CorpPulse
    ForbesWorker,
]

# Filter by page
def get_workers_for_page(page: str) -> list:
    return [W() for W in ALL_WORKERS if W.page == page]

def get_all_workers() -> list:
    return [W() for W in ALL_WORKERS]
