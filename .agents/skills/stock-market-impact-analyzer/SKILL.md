---
name: stock-market-impact-analyzer
description: >-
  Analyzes stock market news to evaluate which industry sectors and stocks are affected (Bullish/Bearish/Neutral),
  fetches live FII/DII institutional cash and derivatives flows, and generates high-impact Instagram carousel posts on demand.
---

# Stock Market Sector Impact & FII-DII Analyzer Skill

This skill allows the agent to analyze market developments across key market sectors (Banking & Financials, IT & AI, Energy, Auto, Metals, FMCG, Pharma), fetch real-time institutional FII/DII flow metrics, and create publication-ready Instagram posts combining macro positioning with sector-specific stock analysis.

---

## 🏛️ Institutional Data Sources (FII / DII)
- **FII / FPI**: Foreign Institutional Investor cash market net buy/sell flows.
- **DII**: Domestic Institutional Investor mutual funds and insurance net flows.
- **Institutional Sentiment Index**: Bullish / Bearish net bias calculated from total institutional net balance.

---

## 🔍 Sector Impact Breakdown Matrix
When stock market news breaks, the analyzer maps:
1. **Affected Sectors**: Identifies specific industry segments impacted by policy, earnings, or macro news.
2. **Impact Direction**:
   - 🟢 `BULLISH`: Positive revenue/margin catalyst or rate tailwind.
   - 🔴 `BEARISH`: Margin contraction, regulatory headwinds, or geopolitical friction.
   - 🟡 `NEUTRAL / VOLATILE`: Mixed cross-currents.
3. **Key Stock Tickers**: Specific leading companies directly influenced (e.g. HDFC Bank, TCS, Reliance, Infosys, Nvidia).
4. **Institutional Strategy & Takeaways**: Actionable trading bias and portfolio positioning notes.

---

## 🛠️ CLI & Automated Workflows

### 1. Fetch Latest FII / DII Cash Flows
```bash
python3 .agents/skills/stock-market-impact-analyzer/scripts/market_impact_cli.py --fii-dii
```

### 2. Run Sector Impact Analysis on Top News
```bash
python3 .agents/skills/stock-market-impact-analyzer/scripts/market_impact_cli.py --analyze
```

### 3. Generate Complete 5-Slide Instagram Carousel & Caption
```bash
python3 .agents/skills/stock-market-impact-analyzer/scripts/market_impact_cli.py --generate-post
```

---

## 🌐 Dashboard UI Integration
Access the dedicated view directly in the dashboard:
- **URL**: [http://localhost:8888](http://localhost:8888) → **🔥 Top 5 Picks** → **📊 Market Impact & FII-DII** tab.
- **REST Endpoints**:
  - `GET /api/fii-dii`: Live FII & DII flows.
  - `GET /api/market-impact`: AI sector impact analysis matrix.
  - `POST /api/market-impact/generate-post`: 1-Click visual carousel + caption generator.
