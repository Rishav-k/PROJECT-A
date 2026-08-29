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

### 3. Generate Complete 4-Slide Instagram Carousel & Caption
```bash
python3 .agents/skills/stock-market-impact-analyzer/scripts/market_impact_cli.py --generate-post
```

**4-Slide Premium Visual Architecture**:
- **Slide 1**: Nifty 50, BSE Sensex, Bank Nifty & India VIX Scorecard.
  - *Background*: Deep Crimson-to-Maroon gradient (`#B91C1C` → `#450A0A`) with BSE Phiroze Towers & Wall Street exchange architectural silhouettes and candlestick grid watermarks.
  - *Dynamic Mascots*: Emerald Charging Bull (`🐂 BULL POWER`) on market rallies vs. Roaring Bear (`🐻 BEAR ALERT`) on corrections.
  - *Metrics*: Nifty & Sensex in bold impact typography with solid contrast status pills.
- **Slide 2**: Nifty Cash Inflows (FII / FPI, DII Domestic, Institutional Total & Retail Flows).
  - *Background*: Obsidian Navy-to-Sapphire gradient (`#0F172A` → `#020617`) with technical orderbook grid.
  - *Banner*: Tangerine ribbon badge with official NSE trade date.
  - *Dynamic Motif*: Green Institutional Bull badge on net buying days.
- **Slide 3**: Market Sentiments & Sector Radar Matrix.
  - *Background*: Deep Ocean Teal gradient (`#0369A1` → `#042F2E`) with exchange skyline texture.
  - *Gauges*: Overall market mood, India VIX cooling/spike interpretation.
  - *Sector Cards*: Bullish (Emerald Green) & Bearish (Rose Red) badges, tickers, and macroeconomic catalysts.
- **Slide 4**: Major Market News & Catalysts.
  - *Background*: Warm Amber-to-Sienna gradient (`#C2410C` → `#7C2D12`) with Wall Street pillar silhouettes.
  - *Content*: Top 3 breaking market developments with clean source badges and full caption link callouts.

---

## 🎨 Color Palette & Design Tokens
- **Crimson & Maroon** (`#B91C1C` / `#450A0A`): Index headers, Bearish alerts, risk warnings.
- **Emerald Green** (`#10B981` / `#059669`): Bullish breakouts, net inflows, institutional buying.
- **Electric Amber & Tangerine** (`#F59E0B` / `#EF8D32`): FII-DII ribbons, retail cards, highlight banners.
- **Ocean Blue & Teal** (`#0369A1` / `#3FA9BE`): Sentiment radar, sector matrix, swipe indicators.
- **Vintage Cream & Crisp White** (`#FEF3DC` / `#FFFFFF`): Borderless readable card surfaces with high contrast.

---

## 🌐 Dashboard UI Integration
Access the dedicated view directly in the dashboard:
- **URL**: [http://localhost:8888](http://localhost:8888) → **🔥 Top 5 Picks** → **📊 Market Impact & FII-DII** tab.
- **REST Endpoints**:
  - `GET /api/fii-dii`: Live FII & DII flows.
  - `GET /api/market-impact`: AI sector impact analysis matrix.
  - `POST /api/market-impact/generate-post`: 1-Click visual carousel + caption generator.
