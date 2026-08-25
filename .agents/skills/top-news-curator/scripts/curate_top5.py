#!/usr/bin/env python3
"""
curate_top5.py — CLI helper for Top 5 News Curation & On-Demand Post Generation
"""

import os
import sys
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../../pulse_media"))
if not os.path.exists(PROJECT_ROOT):
    PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../pulse_media"))
sys.path.insert(0, PROJECT_ROOT)

from database.models import get_top_news_across_segments
from database.schema import init_db

PAGE_NAMES = {
    "finpulse": "FinPulse (Finance & Markets)",
    "techpulse": "TechPulse (Technology & AI)",
    "corppulse": "CorpPulse (Corporate & Business)",
    "worldpulse": "WorldPulse (Global Affairs)"
}

def display_top_news(page: str = "all", limit: int = 5):
    articles = get_top_news_across_segments(page=page, limit=limit)
    if not articles:
        print("No articles found. Try fetching news first.")
        return

    print("=" * 80)
    print(f"🔥 TOP {limit} NEWS PICKS — {page.upper()}")
    print("=" * 80)

    current_page = None
    rank = 1
    for a in articles:
        pg = a.get("page", "finpulse")
        if pg != current_page and page == "all":
            current_page = pg
            rank = 1
            print(f"\n📁 [{PAGE_NAMES.get(pg, pg.upper())}]")
            print("-" * 80)

        status = "✅ Posted" if a.get("is_posted") else ("🎨 Carousel Ready" if a.get("image_path") else ("📝 Captioned" if a.get("caption") else "🆕 Fetched"))
        score = a.get("score", 0)
        title = a.get("title", "Untitled")
        source = a.get("source_name", "Unknown")
        pub = a.get("published_at", "N/A")
        aid = a.get("id")

        print(f"  #{rank:02d} [ID:{aid:<4}] ({score:2.0f} pts) {title}")
        print(f"       Source: {source} | Published: {pub} | Status: {status}")
        if a.get("summary"):
            clean_sum = (a["summary"][:120] + "...") if len(a["summary"]) > 120 else a["summary"]
            print(f"       Summary: {clean_sum}")
        print()
        rank += 1

def generate_post_for_article(article_id: int):
    from dashboard.server import article_action_generate_full
    print(f"✦ Generating full post (AI Caption + 5-Slide Carousel) for Article ID #{article_id}...")
    res = article_action_generate_full(article_id)
    if res.get("success"):
        print(f"✅ Success! Caption generated via {res.get('backend')}.")
        print(f"🖼️ {res.get('slide_count', 5)} Carousel slides created: {res.get('image_file')}")
        if res.get("caption"):
            print("\n📝 Caption Preview:")
            print("-" * 60)
            print(res["caption"][:300] + "...\n")
    else:
        print(f"❌ Failed: {res.get('error')}")

def main():
    parser = argparse.ArgumentParser(description="Top 5 News Curator & Generator")
    parser.add_argument("--page", default="all", choices=["all", "finpulse", "techpulse", "corppulse", "worldpulse"], help="Segment page")
    parser.add_argument("--top", type=int, default=5, help="Number of articles per segment")
    parser.add_argument("--generate", type=int, help="Article ID to generate caption and carousel for")
    args = parser.parse_args()

    if args.generate:
        generate_post_for_article(args.generate)
    else:
        display_top_news(page=args.page, limit=args.top)

if __name__ == "__main__":
    main()
