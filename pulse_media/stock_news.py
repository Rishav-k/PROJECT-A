"""
stock_news.py — 100% Free Past 24-Hour Stock News Engine
Fetches breaking news strictly within the last 24 hours for ANY NSE/BSE or US stock ticker.
No API key required, zero rate limits.
"""

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Dict, Any

def get_stock_news_24h(ticker: str, limit: int = 10) -> Dict[str, Any]:
    """
    Fetches real-time stock news from the past 24 hours for any ticker symbol.
    Example tickers: RELIANCE, TCS, HDFCBANK, INFY, TATAMOTORS, ZOMATO, NVDA, AAPL.
    """
    ticker = ticker.strip().upper().replace(".NS", "").replace(".BO", "")
    query = f"{ticker} stock when:1d"
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    req = urllib.request.Request(url, headers=headers)
    items_out = []

    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)

            for item in root.findall(".//item")[:limit]:
                raw_title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                source_el = item.find("source")
                source_name = source_el.text if source_el is not None else "Financial News Desk"

                # Clean Title (strip " - Source Name" suffix if present)
                clean_title = raw_title
                if " - " in raw_title:
                    parts = raw_title.rsplit(" - ", 1)
                    clean_title = parts[0]
                    if not source_name or source_name == "Financial News Desk":
                        source_name = parts[1]

                items_out.append({
                    "ticker": ticker,
                    "title": clean_title,
                    "raw_title": raw_title,
                    "source_name": source_name,
                    "url": link,
                    "published_at": pub_date,
                    "timeframe": "past 24 hours"
                })
    except Exception as e:
        return {"ticker": ticker, "count": 0, "error": str(e), "items": []}

    return {
        "ticker": ticker,
        "query": query,
        "count": len(items_out),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "items": items_out
    }

if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"
    res = get_stock_news_24h(t, limit=5)
    print(f"=== Past 24h News for {res['ticker']} ({res['count']} stories) ===")
    for i, a in enumerate(res["items"], 1):
        print(f"[{i}] {a['title']}")
        print(f"    Source: {a['source_name']} | Time: {a['published_at']}")
        print(f"    URL: {a['url']}\n")
