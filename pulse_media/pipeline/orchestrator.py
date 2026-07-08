#!/usr/bin/env python3
from __future__ import annotations
import warnings
warnings.filterwarnings("ignore", category=Warning, module="urllib3")
"""
pipeline/orchestrator.py — Pipeline Orchestrator
The brain. Runs all workers, deduplicates, scores, saves to DB.

Flow:
  run_pipeline(page)
    └─ launch all workers for that page (threaded)
        └─ collect all articles
            └─ deduplicate (exact + fuzzy)
                └─ score each article
                    └─ save new articles to DB
                        └─ return top N for AI processing
"""

import re
import sys
import os
import threading
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.models import (
    save_article, article_exists, get_top_articles,
    get_dashboard_stats, get_all_sources
)
from workers.rss_workers import get_workers_for_page, get_all_workers
from workers.api_workers import NewsDataWorker, YFinanceWorker


# ─────────────────────────────────────────────
# DEDUPLICATION
# ─────────────────────────────────────────────

def _word_set(title: str) -> set:
    """Extract meaningful words (4+ chars) from a title."""
    return set(re.findall(r"\b\w{4,}\b", title.lower()))


def deduplicate(articles: list[dict]) -> list[dict]:
    """
    Remove duplicates. Two articles are the same if:
    1. Exact title hash match (caught by DB UNIQUE constraint anyway), OR
    2. Titles share >55% word overlap (same story, different wording)
    """
    seen_word_sets = []
    unique = []

    for article in articles:
        words = _word_set(article["title"])
        if not words:
            continue

        is_dup = False
        for seen in seen_word_sets:
            if not seen:
                continue
            overlap = len(words & seen) / len(words | seen)
            if overlap > 0.55:
                is_dup = True
                break

        if not is_dup:
            seen_word_sets.append(words)
            unique.append(article)

    return unique


# ─────────────────────────────────────────────
# WORKER RUNNER (threaded)
# ─────────────────────────────────────────────

def _run_worker(worker, results: list, lock: threading.Lock):
    """Run a single worker and append its articles to shared results list."""
    articles = worker.run()
    with lock:
        results.extend(articles)


def fetch_all(page: str) -> list[dict]:
    """
    Run all workers for a page in parallel threads.
    Tries fetcher.py (v2) first; falls back to legacy workers if unavailable.
    Returns all fetched articles (before dedup/save).
    """
    # ── Try new fetcher.py (v2) ──────────────────────────────────────────────
    try:
        from fetcher import fetch_source, list_sources, score_article
        page_sources = list_sources(page)
        if page_sources:
            results = []
            lock = threading.Lock()
            futures = []

            def _run_fetcher_source(s, results, lock):
                _, articles, _ = fetch_source(s)
                with lock:
                    results.extend(articles)

            threads = []
            for s in page_sources:
                t = threading.Thread(target=_run_fetcher_source, args=(s, results, lock))
                t.start()
                threads.append(t)
            for t in threads:
                t.join(timeout=35)
            return results
    except ImportError:
        pass

    # ── Fallback: legacy workers ──────────────────────────────────────────────
    workers = get_workers_for_page(page)
    workers.append(NewsDataWorker(page))
    if page == "finpulse":
        workers.append(YFinanceWorker())

    results = []
    lock    = threading.Lock()
    threads = []
    for worker in workers:
        t = threading.Thread(target=_run_worker, args=(worker, results, lock))
        t.start()
        threads.append(t)
    for t in threads:
        t.join(timeout=30)
    return results


# ─────────────────────────────────────────────
# MAIN PIPELINE FUNCTION
# ─────────────────────────────────────────────

def run_pipeline(page: str, top_n: int = 5) -> list[dict]:
    """
    Full pipeline for one page.

    Steps:
      1. Fetch from all workers (parallel)
      2. Deduplicate
      3. Filter already-in-DB articles
      4. Score each article
      5. Save new articles to DB
      6. Return top N by score (for AI processing)

    Args:
        page:  "finpulse" | "techpulse" | "corppulse" | "worldpulse"
        top_n: how many top articles to return

    Returns:
        List of top article dicts, ready for ai.py
    """
    print(f"\n{'='*60}")
    print(f"🚀 PIPELINE: {page.upper()} — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    # Step 1: Fetch
    all_articles = fetch_all(page)
    print(f"\n📥 Total fetched:    {len(all_articles)}")

    # Step 2: Deduplicate
    unique = deduplicate(all_articles)
    print(f"🔀 After dedup:      {len(unique)}")

    # Step 3 + 4 + 5: Filter known, score, save new
    saved = 0
    skipped = 0
    for article in unique:
        article["page"] = page
        row_id = save_article(article)
        if row_id:
            saved += 1
        else:
            skipped += 1

    print(f"💾 Saved to DB:      {saved} new articles")
    print(f"⏭️  Already known:   {skipped} duplicates")

    # Step 6: Get top N from DB (includes previously saved unposted ones)
    top = get_top_articles(page, limit=top_n)
    print(f"\n🏆 Top {len(top)} articles for AI:")
    for i, a in enumerate(top, 1):
        print(f"   {i}. [{a['score']:.0f}pts] {a['title'][:65]}")

    return top


def run_all_pages():
    """Run the full pipeline for all 4 pages. Called by the scheduler."""
    pages = ["finpulse", "techpulse", "corppulse", "worldpulse"]
    results = {}
    for page in pages:
        try:
            top = run_pipeline(page)
            results[page] = top
        except Exception as e:
            print(f"❌ Pipeline failed for {page}: {e}")
            results[page] = []
    return results


# ─────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # Usage: python pipeline/orchestrator.py [page]
    # Examples:
    #   python pipeline/orchestrator.py finpulse
    #   python pipeline/orchestrator.py all

    target = sys.argv[1] if len(sys.argv) > 1 else "finpulse"

    if target == "all":
        run_all_pages()
    else:
        run_pipeline(target)

    # Print DB stats after run
    print(f"\n{'='*60}")
    print("📊 DATABASE STATS")
    print("="*60)
    stats = get_dashboard_stats()
    print(f"  Total articles: {stats['total_articles']}")
    print(f"  Total posted:   {stats['total_posted']}")
    print(f"  Sources active: {stats['sources_ok']}/{stats['total_sources']}")
    for p in stats["per_page"]:
        print(f"  {p['page']:12} — {p['total']} articles, {p['posted']} posted")
