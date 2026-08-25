---
name: top-news-curator
description: >-
  Curates, ranks, and reviews the Top 5 highest-scoring news stories from all segments
  (FinPulse, TechPulse, CorpPulse, WorldPulse) and triggers on-demand AI caption and
  5-slide carousel post generation for Instagram without burning background credits.
---

# Top News Curator & Post Generator Skill

This skill allows the agent to inspect real-time ranked news across all 4 Pulse Media segments, identify the top 5 highest-impact stories, evaluate their engagement potential, and generate Instagram posts (AI caption + 5-slide visual carousel) strictly on-demand.

---

## 🧭 Pulse Media Segments

| Segment | Handle | Focus Area | Top Sources |
| :--- | :--- | :--- | :--- |
| **FinPulse** | `@finpulse.daily` | Markets, Fed, Stocks, Crypto, Macro | Yahoo Finance, CNBC, MarketWatch, SEC EDGAR, CoinDesk |
| **TechPulse** | `@techpulse.daily` | AI, Startups, Big Tech, Cyber | TechCrunch, The Verge, Ars Technica, Wired, Techmeme |
| **CorpPulse** | `@corppulse.daily` | M&A, Strategy, Earnings, Layoffs | Fortune, Forbes, FT, CNBC Business, Business Insider |
| **WorldPulse** | `@worldpulse.daily` | Geopolitics, Global Policy, Summits | BBC World, Politico, Al Jazeera, NYT World, France 24 |

---

## 🛠️ Workflows & CLI Commands

### 1. View Top 5 News Across All Segments
Run the curation helper to display the top 5 stories per segment with scores and post statuses:
```bash
python3 .agents/skills/top-news-curator/scripts/curate_top5.py --page all --top 5
```

### 2. View Top 5 News for a Specific Segment
```bash
python3 .agents/skills/top-news-curator/scripts/curate_top5.py --page techpulse --top 5
```

### 3. Generate Post Assets (Caption + Carousel) on Demand
Generate complete Instagram assets for a specific article ID:
```bash
# Generate both caption + 5-slide carousel
python3 .agents/skills/top-news-curator/scripts/curate_top5.py --generate <article_id>
```

### 4. Interactive Dashboard Endpoint
The dashboard provides a dedicated **Top 5 Picks** tab and API:
- **UI Tab**: Click **🔥 Top 5 Picks** in the sidebar.
- **REST Endpoint**: `GET /api/top-news?page=all&limit=5` or `?page=finpulse&limit=5`
- **1-Click Generation**: `POST /api/article/<id>/generate-full`

---

## 📊 Scoring Criteria
News articles are evaluated on a 100-point scale:
- **Keyword & Topic Impact** (0-50 pts): Breaking market moves, AI breakthroughs, Fed policy, major M&A.
- **Recency** (0-30 pts): Published within last 4 to 24 hours.
- **Source Authority** (0-20 pts): Tier-1 primary wires, SEC EDGAR filings, Central Banks.
- **Regulatory / Filing Boost** (+20 pts): 8-K filings, Federal Reserve decisions.
