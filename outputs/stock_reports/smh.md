# SMH Research Readiness Report

Research-only local report. This is not a trade instruction and cannot execute transactions.

## One-Minute Status
SMH state: partial. Decision: Monitor - ETF Market Proxy. Primary blocker: peers. DCF: excluded. Peer workflow: missing_peer_mapping. Optional earnings or analyst-estimate context is unavailable until trusted local CSV rows exist. Next: Add source-backed peer mappings and peer metrics for SMH.

## Decision
- Bucket: Monitor
- Subtype: Monitor - ETF Market Proxy
- Primary blocker: peers
- Main reason: etf is usable for market/risk monitoring and excluded from company DCF.
- Next action: Add source-backed peer mappings and peer metrics for SMH.

## Readiness
- Overall state: partial
- Price ready: True
- Momentum ready: True
- Liquidity ready: True
- Correlation ready: True
- Fundamentals ready: False
- DCF ready: False
- Peer ready: False
- Earnings ready: False
- Analyst estimates ready: False
- Blocked features: fundamentals, peer, earnings, analyst_estimates
- Excluded features: dcf, portfolio

## Price Coverage
- Price rows: 616
- First date: 2023-12-07
- Last date: 2026-05-22
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
- Next peer action: Add at least 2 source-backed peer mappings for SMH in data/imports/peers.csv.

## Missing Data
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
- fundamentals has no local row for this ticker.

## Sources And Freshness
- local:prices.csv: research-grade / local, retrieved 2026-05-27T21:34:28.109158039+00:00; Local CSV-backed research data.
- local:fundamentals.csv: research-grade / local, retrieved 2026-05-29T02:03:20+00:00; No local fundamentals row was found for this ticker.
- local:earnings.csv: research-grade / local, retrieved 2026-05-29T02:03:20+00:00; Earnings fields are unavailable from the bundled local sample files.
- local:analyst_estimates.csv: research-grade / local, retrieved 2026-05-29T02:03:20+00:00; Analyst estimate fields are unavailable from the bundled local sample files.

## Source/Freshness Audit
- Prices: True; local source `data/prices.csv`; coverage 2023-12-07 to 2026-05-22; rows=616; staged path `data/staged/prices/` or `data/imports/prices.csv`; rejected rows `data/rejected/price_import_rejected.csv`.
- Fundamentals / DCF: excluded; local source `data/fundamentals.csv`; reason DCF excluded for etf; use ETF/rotation analysis instead of operating-company DCF.; SEC_USER_AGENT present; staged path `data/staged/fundamentals/` or `data/imports/fundamentals.csv`; rejected rows `data/rejected/fundamentals_import_rejected.csv`.
- Peers: missing_peer_mapping; local source `data/peers.csv`; staged path `data/imports/peers.csv`; next peer action Add at least 2 source-backed peer mappings for SMH in data/imports/peers.csv.
- Earnings: False; trusted local CSV only; staged path `data/staged/earnings/`; command `make import-earnings`; rejected rows `data/rejected/earnings_import_rejected.csv`.
- Analyst estimates: False; trusted local CSV only; staged path `data/staged/analyst_estimates/`; command `make import-analyst-estimates`; rejected rows `data/rejected/analyst_estimates_import_rejected.csv`.
- Credentials: SEC_USER_AGENT present; STOOQ_API_KEY missing; missing remote credentials should not break local CSV reports or staged import workflows.
- Report command: `make stock-report TICKER=SMH`. Research-only output; no transaction execution.
