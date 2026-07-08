from __future__ import annotations
"""
workers/api_workers.py — API-based workers
These use API keys (stored in .env). They're optional — the pipeline
works without them, they just add extra data.
"""

import os
from workers.base import BaseWorker


class NewsDataWorker(BaseWorker):
    """
    NewsData.io API worker.
    Free tier: 200 credits/day. Each call = 10 credits. Max 20 calls/day.
    Called sparingly — 4x/day per page to stay well under limit.
    """
    source_type = "api"

    def __init__(self, page: str):
        self.page         = page
        self.name         = f"newsdata_{page[:4]}"
        self.display_name = f"NewsData.io ({page})"
        self._api_key     = os.getenv("NEWSDATA_API_KEY", "")

    CATEGORY_MAP = {
        "finpulse":  "business",
        "techpulse": "technology",
        "corppulse": "business",
        "worldpulse": "world",
    }

    def fetch(self):
        if not self._api_key:
            print(f"  [{self.display_name}] Skipped — no API key in .env")
            return []

        category = self.CATEGORY_MAP.get(self.page, "top")
        r = self._get("https://newsdata.io/api/1/news", params={
            "apikey":   self._api_key,
            "language": "en",
            "category": category,
        }, timeout=15)
        r.raise_for_status()
        data = r.json()

        articles = []
        for item in data.get("results", []):
            title = (item.get("title") or "").strip()
            if not title:
                continue
            a = {
                "title":        title,
                "summary":      (item.get("description") or "")[:500],
                "url":          item.get("link", ""),
                "source_name":  (item.get("source_id") or "NewsData").title(),
                "page":         self.page,
                "category":     category,
                "published_at": item.get("pubDate", ""),
                "score":        0.0,
            }
            self.score(a)
            articles.append(a)

        return articles


class YFinanceWorker(BaseWorker):
    """
    yfinance Python library worker.
    Gets the latest news for major tickers — completely free, no API key.
    Also fetches real-time price data to enrich posts.
    """
    name         = "yfinance_lib"
    display_name = "yfinance (Yahoo)"
    page         = "finpulse"
    source_type  = "library"

    # Tickers to monitor for news
    TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA",
               "SPY", "QQQ", "BTC-USD", "GLD"]

    def fetch(self):
        try:
            import yfinance as yf
        except ImportError:
            print(f"  [{self.display_name}] Skipped — yfinance not installed")
            print(f"    Install with: pip3 install yfinance")
            return []
        except TypeError:
            print(f"  [{self.display_name}] Skipped — yfinance requires Python 3.10+")
            return []

        articles = []
        seen_urls = set()

        for ticker_sym in self.TICKERS:
            try:
                ticker = yf.Ticker(ticker_sym)
                news_items = ticker.news or []
                for item in news_items[:3]:  # 3 per ticker max
                    url = item.get("link", "")
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title = (item.get("title") or "").strip()
                    if not title:
                        continue

                    # Convert Unix timestamp to ISO
                    pub_ts = item.get("providerPublishTime", 0)
                    if pub_ts:
                        from datetime import datetime, timezone
                        pub_iso = datetime.fromtimestamp(pub_ts, tz=timezone.utc).isoformat()
                    else:
                        pub_iso = ""

                    a = {
                        "title":        title,
                        "summary":      (item.get("summary") or "")[:500],
                        "url":          url,
                        "source_name":  item.get("publisher", "Yahoo Finance"),
                        "page":         self.page,
                        "category":     "markets",
                        "published_at": pub_iso,
                        "score":        0.0,
                        "ticker":       ticker_sym,  # extra field for context
                    }
                    self.score(a)
                    articles.append(a)

            except Exception as e:
                print(f"  [{self.display_name}] ✗ {ticker_sym}: {e}")
                continue

        return articles

    @staticmethod
    def get_price_snapshot(tickers=None) -> dict:
        """
        Get current price + % change for a list of tickers.
        Used by ai.py to add real data to captions.
        Returns: {"AAPL": {"price": 213.5, "change_pct": +1.2}, ...}
        """
        try:
            import yfinance as yf
            result = {}
            tickers = tickers or ["SPY", "QQQ", "BTC-USD", "^VIX"]
            for sym in tickers:
                try:
                    t = yf.Ticker(sym)
                    info = t.fast_info
                    price = info.last_price
                    prev  = info.previous_close
                    if price and prev:
                        change_pct = round(((price - prev) / prev) * 100, 2)
                        result[sym] = {"price": round(price, 2), "change_pct": change_pct}
                except Exception:
                    pass
            return result
        except ImportError:
            return {}
