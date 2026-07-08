"""
scheduler.py — Pulse Media Automated Scheduler
Runs the full pipeline (fetch → caption → image → post) 4x per day per page.

POSTING SCHEDULE (based on optimal Instagram engagement times):
  06:00 — Morning news cycle (pre-market open)
  09:30 — Market open / top stories
  13:00 — Lunch scroll peak
  17:00 — Post-work evening peak

Each run:
  1. Fetches fresh news from all sources
  2. Deduplicates + scores articles
  3. Generates AI caption (Groq/Gemini/template)
  4. Generates branded image (Pillow)
  5. Posts to Instagram
  6. Logs results to DB

HOW TO RUN:
  # Run once now (good for testing):
  python3 scheduler.py --once

  # Run once for a specific page:
  python3 scheduler.py --once --page finpulse

  # Run in background (keeps running, posts at scheduled times):
  python3 scheduler.py

  # Dry run (full pipeline but don't post to Instagram):
  python3 scheduler.py --once --dry-run

HOW TO RUN 24/7 (free):
  Deploy to Render.com free tier — see DEPLOY.md (coming soon)
  Or run locally: nohup python3 scheduler.py >> logs/scheduler.log 2>&1 &
"""

from __future__ import annotations

import os
import sys
import time
import signal
import traceback
from datetime import datetime, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))

# ─────────────────────────────────────────────
# SCHEDULE CONFIG
# ─────────────────────────────────────────────

ALL_PAGES = ["finpulse", "techpulse", "corppulse", "worldpulse"]

# Post times in 24h format (hour, minute) — UTC
# Stagger by 5 min between pages to avoid rate spikes
POST_SCHEDULE = [
    (6,  0),   # 6:00 AM  UTC
    (9,  30),  # 9:30 AM  UTC (US pre-market)
    (13, 0),   # 1:00 PM  UTC
    (17, 0),   # 5:00 PM  UTC
]

PAGE_STAGGER_MINUTES = 5  # minutes between each page post in the same cycle


# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

def _log(msg: str, level: str = "INFO"):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    try:
        with open(os.path.join(LOG_DIR, "scheduler.log"), "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ─────────────────────────────────────────────
# CORE: RUN ONE PAGE CYCLE
# ─────────────────────────────────────────────

def run_page(page: str, dry_run: bool = False) -> bool:
    """
    Run the full pipeline for one page:
    fetch → ai caption → image → post to Instagram
    Returns True on success.
    """
    _log(f"Starting cycle for {page.upper()}")
    try:
        # Step 1: Fetch fresh articles
        _log(f"[{page}] Fetching news...")
        from pipeline.orchestrator import run_pipeline
        articles = run_pipeline(page, top_n=3)
        if not articles:
            _log(f"[{page}] No new articles — skipping post", "WARN")
            return False

        # Step 2–5: Caption → Image → Post (handled by instagram.run_post_cycle)
        from instagram import run_post_cycle
        result = run_post_cycle(page, dry_run=dry_run)

        if result.get("success"):
            _log(f"[{page}] ✅ Cycle complete! Post ID: {result.get('post_id', 'dry-run')}")
            return True
        else:
            _log(f"[{page}] ❌ Post failed: {result.get('error')}", "ERROR")
            return False

    except Exception as e:
        _log(f"[{page}] ❌ Unhandled error: {e}", "ERROR")
        _log(traceback.format_exc(), "DEBUG")
        return False


def run_all_pages(dry_run: bool = False):
    """Run post cycle for all 4 pages, staggered."""
    _log("=" * 50)
    _log(f"FULL CYCLE START — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
    _log("=" * 50)

    results = {}
    for i, page in enumerate(ALL_PAGES):
        if i > 0:
            _log(f"Waiting {PAGE_STAGGER_MINUTES}m before next page...")
            time.sleep(PAGE_STAGGER_MINUTES * 60)
        results[page] = run_page(page, dry_run=dry_run)

    # Summary
    ok   = [p for p, r in results.items() if r]
    fail = [p for p, r in results.items() if not r]
    _log(f"CYCLE DONE — ✅ {ok} | ❌ {fail}")


# ─────────────────────────────────────────────
# SCHEDULER LOOP
# ─────────────────────────────────────────────

_running = True

def _handle_signal(sig, frame):
    global _running
    _log("Shutdown signal received — stopping after current cycle")
    _running = False

signal.signal(signal.SIGINT,  _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def _next_run_time() -> Optional[datetime]:
    """
    Calculate the next scheduled post time from now (UTC).
    Returns a datetime object, or None if none today.
    """
    now = datetime.utcnow()
    today = now.date()

    candidates = []
    for h, m in POST_SCHEDULE:
        t = datetime(today.year, today.month, today.day, h, m)
        if t > now:
            candidates.append(t)

    # Check tomorrow's first slot too
    tomorrow = today + timedelta(days=1)
    h, m = POST_SCHEDULE[0]
    candidates.append(datetime(tomorrow.year, tomorrow.month, tomorrow.day, h, m))

    return min(candidates) if candidates else None


def run_scheduler(dry_run: bool = False):
    """
    Main scheduler loop. Runs until interrupted.
    Wakes up every minute to check if it's time to post.
    """
    _log("🚀 Pulse Media Scheduler started")
    _log(f"   Schedule: {', '.join(f'{h:02d}:{m:02d}' for h, m in POST_SCHEDULE)} UTC")
    _log(f"   Pages: {', '.join(ALL_PAGES)}")
    _log(f"   Dry run: {dry_run}")
    _log("   Press Ctrl+C to stop\n")

    last_run_hour: set = set()  # track which (date, hour, minute) slots we've fired

    while _running:
        now = datetime.utcnow()
        slot = (now.date(), now.hour, now.minute)

        # Check if current minute matches a scheduled slot
        for h, m in POST_SCHEDULE:
            if now.hour == h and now.minute == m and slot not in last_run_hour:
                last_run_hour.add(slot)
                # Keep set small
                if len(last_run_hour) > 20:
                    last_run_hour.pop()
                run_all_pages(dry_run=dry_run)
                break

        # Show next run time every 30 minutes
        if now.minute % 30 == 0 and now.second < 60:
            next_run = _next_run_time()
            if next_run:
                delta = next_run - now
                hours, rem = divmod(int(delta.total_seconds()), 3600)
                mins = rem // 60
                _log(f"⏰ Next post in {hours}h {mins}m ({next_run.strftime('%H:%M')} UTC)")

        time.sleep(60)  # check every minute

    _log("Scheduler stopped.")


# ─────────────────────────────────────────────
# STATS REPORTER
# ─────────────────────────────────────────────

def print_stats():
    """Print current DB stats — useful to call after --once."""
    try:
        from database.models import get_dashboard_stats
        stats = get_dashboard_stats()
        print(f"\n{'='*50}")
        print("📊 PULSE MEDIA — PIPELINE STATS")
        print("="*50)
        print(f"  Total articles : {stats['total_articles']}")
        print(f"  Total posted   : {stats['total_posted']}")
        print(f"  Active sources : {stats['sources_ok']}/{stats['total_sources']}")
        print()
        for p in stats["per_page"]:
            bar = "█" * min(int(p["total"] / 10), 20)
            print(f"  {p['page']:12} {bar:<20} {p['total']:3} articles  {p['posted']:2} posted")
    except Exception as e:
        print(f"  (Stats unavailable: {e})")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    once    = False
    dry_run = False
    page    = None
    stats   = False

    for arg in sys.argv[1:]:
        if arg == "--once":     once    = True
        elif arg == "--dry-run": dry_run = True
        elif arg == "--stats":  stats   = True
        elif arg.startswith("--page="): page = arg.split("=")[1]
        elif arg in ALL_PAGES:  page    = arg

    if stats:
        print_stats()
        return

    if once:
        if page and page != "all":
            # First fetch news, then run post cycle
            _log(f"Single run for {page.upper()}")
            from pipeline.orchestrator import run_pipeline
            run_pipeline(page, top_n=3)
            from instagram import run_post_cycle
            result = run_post_cycle(page, dry_run=dry_run)
            if result.get("success"):
                _log(f"✅ Done! Post ID: {result.get('post_id','dry-run')}")
            else:
                _log(f"❌ Failed: {result.get('error')}", "ERROR")
        else:
            run_all_pages(dry_run=dry_run)
        print_stats()
    else:
        # Continuous scheduler
        run_scheduler(dry_run=dry_run)


if __name__ == "__main__":
    main()
