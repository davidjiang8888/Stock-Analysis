# APLD Research Readiness Report

Research-only local report. This is not a trade instruction and cannot execute transactions.

This is a readiness-only report because the full stock-report provider could not assemble price-backed analysis.
Provider blocker: No local price rows were found for APLD.

## One-Minute Status
APLD state: blocked. Decision: Blocked by Data - Missing Price. Primary blocker: price. DCF: blocked. Peer workflow: missing_peer_mapping. Optional earnings or analyst-estimate context is unavailable until trusted local CSV rows exist. Next: Import staged price rows or refresh price provider for APLD.

## Decision
- Bucket: Blocked by Data
- Subtype: Blocked by Data - Missing Price
- Primary blocker: price
- Main reason: Missing usable price data.
- Next action: Import staged price rows or refresh price provider for APLD.

## Readiness
- Overall state: blocked
- Asset type: company
- Price ready: False
- Momentum ready: False
- Fundamentals ready: False
- DCF ready: False
- Peer ready: False
- Earnings ready: False
- Analyst estimates ready: False
- Blocked features: price, momentum, market_direction, liquidity, correlation, fundamentals, dcf, peer, earnings, analyst_estimates
- Excluded features: portfolio

## Price Coverage
- Price rows: 0
- Missing price reason: needs at least 5 valid price rows with positive close

## DCF
- Missing fields: free_cash_flow, shares_outstanding, revenue, fcf_margin, price
- Reason not ready: missing free_cash_flow, shares_outstanding, revenue, fcf_margin, price

## Peer Workflow
- Peer blocker type: missing_peer_mapping
- Mapping status: missing_mapping
- Peer count: 0
- Trend comparison ready: False
- Valuation comparison ready: False
- Next peer action: Add at least 2 source-backed peer mappings for APLD in data/imports/peers.csv.

## Missing Data
- needs at least 5 valid price rows with positive close; dcf: free_cash_flow, shares_outstanding, revenue, fcf_margin, price; peers: needs at least 2 source-backed peer mappings; earnings: trusted local CSV input; analyst_estimates: trusted local CSV input

## Source/Freshness Audit
- Prices: False; local source `data/prices.csv`; coverage unknown to unknown; rows=0; staged path `data/staged/prices/` or `data/imports/prices.csv`; rejected rows `data/rejected/price_import_rejected.csv`.
- Fundamentals / DCF: blocked; local source `data/fundamentals.csv`; reason missing free_cash_flow, shares_outstanding, revenue, fcf_margin, price; SEC_USER_AGENT present; staged path `data/staged/fundamentals/` or `data/imports/fundamentals.csv`; rejected rows `data/rejected/fundamentals_import_rejected.csv`.
- Peers: missing_peer_mapping; local source `data/peers.csv`; staged path `data/imports/peers.csv`; next peer action Add at least 2 source-backed peer mappings for APLD in data/imports/peers.csv.
- Earnings: False; trusted local CSV only; staged path `data/staged/earnings/`; command `make import-earnings`; rejected rows `data/rejected/earnings_import_rejected.csv`.
- Analyst estimates: False; trusted local CSV only; staged path `data/staged/analyst_estimates/`; command `make import-analyst-estimates`; rejected rows `data/rejected/analyst_estimates_import_rejected.csv`.
- Credentials: SEC_USER_AGENT present; STOOQ_API_KEY missing; missing remote credentials should not break local CSV reports or staged import workflows.
- Report command: `make stock-report TICKER=APLD`. Research-only output; no transaction execution.

