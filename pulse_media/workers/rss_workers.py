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
    URL = "https://finance.yahoo.com/news/rssindex"

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


class CoinDeskWorker(BaseWorker):
    name         = "coindesk"
    display_name = "CoinDesk"
    page         = "finpulse"
    source_type  = "rss"
    URL = "https://www.coindesk.com/arc/outboundfeeds/rss/"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "crypto"
            self.score(a)
        return articles


class SECEdgarWorker(BaseWorker):
    name         = "sec_edgar"
    display_name = "SEC EDGAR"
    page         = "finpulse"
    source_type  = "rss"
    URL = ("https://www.sec.gov/cgi-bin/browse-edgar"
           "?action=getcurrent&type=8-K&dateb=&owner=include&count=40&output=atom")

    def fetch(self):
        r = self._get(self.URL, headers={"User-Agent": "PulseMediaBot/1.0 (contact@pulsemedia.com)"})
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "filing"
            a["source_name"] = "SEC EDGAR"
            a["score"] = max(a.get("score", 0), 70.0)
            self.score(a)
        return articles


class FederalReserveWorker(BaseWorker):
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
            a["score"] = max(a.get("score", 0), 80.0)
            self.score(a)
        return articles


class SeekingAlphaWorker(BaseWorker):
    name         = "seeking_alpha"
    display_name = "Seeking Alpha"
    page         = "finpulse"
    source_type  = "rss"
    URL = "https://seekingalpha.com/market_currents.xml"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "analysis"
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


class WiredWorker(BaseWorker):
    name         = "wired"
    display_name = "Wired"
    page         = "techpulse"
    source_type  = "rss"
    URL = "https://www.wired.com/feed/rss"

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


class VentureBeatWorker(BaseWorker):
    name         = "venturebeat"
    display_name = "VentureBeat"
    page         = "techpulse"
    source_type  = "rss"
    URL = "https://venturebeat.com/feed/"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "tech"
            self.score(a)
        return articles


class TechmemeWorker(BaseWorker):
    name         = "techmeme"
    display_name = "Techmeme"
    page         = "techpulse"
    source_type  = "rss"
    URL = "https://www.techmeme.com/feed.xml"

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


class PoliticoWorker(BaseWorker):
    name         = "politico"
    display_name = "Politico"
    page         = "worldpulse"
    source_type  = "rss"
    URL = "https://rss.politico.com/politics-news.xml"

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


class NYTWorldWorker(BaseWorker):
    name         = "nyt_world"
    display_name = "NYT World"
    page         = "worldpulse"
    source_type  = "rss"
    URL = "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "world"
            self.score(a)
        return articles


class GuardianWorldWorker(BaseWorker):
    name         = "guardian_world"
    display_name = "The Guardian"
    page         = "worldpulse"
    source_type  = "rss"
    URL = "https://www.theguardian.com/world/rss"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "world"
            self.score(a)
        return articles


class France24Worker(BaseWorker):
    name         = "france24"
    display_name = "France 24"
    page         = "worldpulse"
    source_type  = "rss"
    URL = "https://www.france24.com/en/rss"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "world"
            self.score(a)
        return articles


# ── CORPPULSE WORKERS ───────────────────────────────────────────

class FortuneWorker(BaseWorker):
    name         = "fortune"
    display_name = "Fortune"
    page         = "corppulse"
    source_type  = "rss"
    URL = "https://fortune.com/feed/"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "corporate"
            self.score(a)
        return articles


class ForbesWorker(BaseWorker):
    name         = "forbes_corp"
    display_name = "Forbes"
    page         = "corppulse"
    source_type  = "rss"
    URL = "https://www.forbes.com/business/feed/"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "corporate"
            self.score(a)
        return articles


class CNBCBizWorker(BaseWorker):
    name         = "cnbc_biz"
    display_name = "CNBC Business"
    page         = "corppulse"
    source_type  = "rss"
    URL = "https://www.cnbc.com/id/10001147/device/rss/rss.html"

    def fetch(self):
        r = self._get(self.URL)
        articles = self._parse_rss(r.text)
        for a in articles:
            a["category"] = "corporate"
            self.score(a)
        return articles


class BusinessInsiderWorker(BaseWorker):
    name         = "business_insider"
    display_name = "Business Insider"
    page         = "corppulse"
    source_type  = "rss"
    URL = "https://feeds.businessinsider.com/custom/all"

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
    CoinDeskWorker,
    SECEdgarWorker,
    FederalReserveWorker,
    SeekingAlphaWorker,
    # TechPulse
    TechCrunchWorker,
    TheVergeWorker,
    ArsTechnicaWorker,
    WiredWorker,
    HackerNewsWorker,
    VentureBeatWorker,
    TechmemeWorker,
    # WorldPulse
    BBCWorldWorker,
    PoliticoWorker,
    AlJazeeraWorker,
    NYTWorldWorker,
    GuardianWorldWorker,
    France24Worker,
    # CorpPulse
    FortuneWorker,
    ForbesWorker,
    CNBCBizWorker,
    BusinessInsiderWorker,
]

# Filter by page
def get_workers_for_page(page: str) -> list:
    return [W() for W in ALL_WORKERS if W.page == page]

def get_all_workers() -> list:
    return [W() for W in ALL_WORKERS]
