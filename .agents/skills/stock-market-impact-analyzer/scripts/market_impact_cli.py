#!/usr/bin/env python3
"""
market_impact_cli.py — CLI for FII/DII Institutional Flows & Sector Impact Analysis
"""

import os
import sys
import json
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../../pulse_media"))
if not os.path.exists(PROJECT_ROOT):
    PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../pulse_media"))
sys.path.insert(0, PROJECT_ROOT)

from fii_dii import fetch_fii_dii_data, analyze_sector_impact, generate_market_impact_post

def show_fii_dii():
    data = fetch_fii_dii_data()
    print("=" * 70)
    print(f"🏛️  INSTITUTIONAL TRADING FLOWS (FII / DII) — {data['date']}")
    print("=" * 70)
    print(f"  Source: {data['source']}")
    print(f"  • FII / FPI Net : {data['fii']['formatted_net']:<16} ({data['fii']['bias']})")
    print(f"    └─ Gross Buy  : ₹{data['fii']['buy']:,.2f} Cr | Gross Sell: ₹{data['fii']['sell']:,.2f} Cr")
    print(f"  • DII (Domestic): {data['dii']['formatted_net']:<16} ({data['dii']['bias']})")
    print(f"    └─ Gross Buy  : ₹{data['dii']['buy']:,.2f} Cr | Gross Sell: ₹{data['dii']['sell']:,.2f} Cr")
    print("-" * 70)
    print(f"  📊 TOTAL NET FLOW : {data['formatted_total_net']} | Sentiment: {data['sentiment']}")
    print("=" * 70)

def show_sector_impact():
    res = analyze_sector_impact()
    fii = res["fii_dii"]
    print("=" * 70)
    print(f"🔍 AI SECTOR & MARKET IMPACT ANALYSIS")
    print("=" * 70)
    print(f"  Market Mood : {res.get('market_mood', 'Neutral')}")
    print(f"  Key Catalyst: {res.get('key_catalyst', '')}")
    print(f"  FII Flow    : {fii['fii']['formatted_net']} ({fii['fii']['bias']}) | DII Flow: {fii['dii']['formatted_net']}")
    print("-" * 70)
    print("  AFFECTED MARKET SECTORS:")
    for s in res.get("sectors", []):
        icon = "🟢" if s["impact"] == "BULLISH" else ("🔴" if s["impact"] == "BEARISH" else "🟡")
        stocks = ", ".join(s.get("affected_stocks", []))
        print(f"\n  {icon} {s['sector_name'].upper()} [{s['impact']} — {s.get('impact_score', 0)} pts]")
        print(f"     Catalyst    : {s['catalyst']}")
        print(f"     Key Tickers : {stocks}")
        print(f"     Action Take : {s.get('key_takeaway', '')}")
    print("-" * 70)
    print(f"  💡 Outlook : {res.get('institutional_outlook', '')}")
    print(f"  🎯 Strategy: {res.get('tactical_strategy', '')}")
    print("=" * 70)

def run_generate():
    print("✦ Generating full Market Impact & FII-DII Instagram Post (Caption + 5-Slide Carousel)...")
    res = generate_market_impact_post()
    if res.get("success"):
        print(f"✅ Success! Generated {res.get('slide_count', 5)} Carousel Slides.")
        print(f"🖼️ Cover Slide: {res.get('image_file')}")
        print("\n📝 Caption Preview:")
        print("-" * 60)
        print(res["caption"][:350] + "...\n")
    else:
        print(f"❌ Failed: {res.get('error')}")

def main():
    parser = argparse.ArgumentParser(description="Stock Market Impact & FII-DII Analyzer")
    parser.add_argument("--fii-dii", action="store_true", help="Display latest FII and DII cash market flows")
    parser.add_argument("--analyze", action="store_true", help="Analyze market news sector impact")
    parser.add_argument("--generate-post", action="store_true", help="Generate 5-slide carousel and caption")
    args = parser.parse_args()

    if args.generate_post:
        run_generate()
    elif args.analyze:
        show_sector_impact()
    else:
        show_fii_dii()

if __name__ == "__main__":
    main()
