# QQQ Research Readiness Report

Research-only local report. This is not a trade instruction and cannot execute transactions.

## Decision
- Bucket: Monitor
- Subtype: Monitor - ETF Market Proxy
- Primary blocker: fundamentals
- Main reason: etf is usable for market/risk monitoring and excluded from company DCF.
- Next action: Add source-backed peer mappings and peer metrics for QQQ.

## Readiness
- Overall state: partial
- Price ready: True
- Momentum ready: True
- Liquidity ready: False
- Correlation ready: False
- Fundamentals ready: False
- DCF ready: False
- Peer ready: False
- Earnings ready: False
- Analyst estimates ready: False
- Blocked features: fundamentals, peer, earnings, analyst_estimates
- Excluded features: dcf, portfolio

## Price Coverage
- Price rows: 25
- First date: 2026-02-10
- Last date: 2026-03-14
- Missing price reason: Not available

## Valuation And DCF
- DCF status: insufficient_data
- DCF missing fields: Not available
- Reason not ready: DCF excluded for etf; use ETF/rotation analysis instead of operating-company DCF.

## Peer Workflow
- Peer blocker type: missing_peer_mapping
- Mapping status: missing_mapping
- Peer count: 0
- Trend comparison ready: False
- Valuation comparison ready: False
- DCF peer comparison ready: False
- Sample peers: Not available
- Next peer action: Add at least 2 source-backed peer mappings for QQQ in data/imports/peers.csv.

## Missing Data
- 1Y performance is unavailable from the current local price history.
- 3M performance is unavailable from the current local price history.
- EPS is unavailable from the current local fundamentals dataset.
- Free cash flow is unavailable from the current local fundamentals dataset.
- No local analyst-estimate dataset is configured in the CSV-first pipeline.
- No local earnings dataset is configured in the CSV-first pipeline.
- Normalized growth target was reduced to keep it conservatively below WACC.
- Revenue is unavailable from the current local fundamentals dataset.
- Valuation missing field: cash
- Valuation missing field: debt
- Valuation missing field: ebitda
- Valuation missing field: eps
- Valuation missing field: fcf_margin
- Valuation missing field: free_cash_flow
- Valuation missing field: market_cap_or_price_and_shares
- Valuation missing field: revenue
- analyst_estimates has no local row for this ticker.
- earnings has no local row for this ticker.

## Sources And Freshness
- local:prices.csv: research-grade / local, retrieved 2026-05-27T21:34:28.109158039+00:00; Local CSV-backed research data.
- local:fundamentals.csv: research-grade / local, retrieved 2026-05-27T21:34:35.086026430+00:00; Local fundamentals data.
- local:earnings.csv: research-grade / local, retrieved 2026-05-28T03:34:36+00:00; Earnings fields are unavailable from the bundled local sample files.
- local:analyst_estimates.csv: research-grade / local, retrieved 2026-05-28T03:34:36+00:00; Analyst estimate fields are unavailable from the bundled local sample files.

