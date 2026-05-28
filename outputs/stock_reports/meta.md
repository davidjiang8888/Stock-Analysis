# META Research Readiness Report

Research-only local report. This is not a trade instruction and cannot execute transactions.

## Decision
- Bucket: Blocked by Data
- Subtype: Blocked by Data - Missing Fundamentals
- Primary blocker: fundamentals
- Main reason: Company research is blocked by missing dcf data.
- Next action: Import trusted fundamentals for META. If SEC_USER_AGENT is configured, use SEC staging; otherwise use the manual fundamentals import workflow.

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
- Blocked features: dcf, peer, earnings, analyst_estimates
- Excluded features: Not available

## Price Coverage
- Price rows: 616
- First date: 2023-12-07
- Last date: 2026-05-22
- Missing price reason: Not available

## Valuation And DCF
- DCF status: calculated
- DCF missing fields: shares_outstanding
- Reason not ready: missing shares_outstanding

## Peer Workflow
- Peer blocker type: missing_peer_mapping
- Mapping status: missing_mapping
- Peer count: 0
- Trend comparison ready: False
- Valuation comparison ready: False
- DCF peer comparison ready: False
- Sample peers: Not available
- Next peer action: Add at least 2 source-backed peer mappings for META in data/imports/peers.csv.

## Missing Data
- Fair value per share could not be derived because shares outstanding is unavailable.
- No local analyst-estimate dataset is configured in the CSV-first pipeline.
- No local earnings dataset is configured in the CSV-first pipeline.
- Normalized growth target was reduced to keep it conservatively below WACC.
- Observed FCF margin 110.4% exceeded the conservative margin cap of 45.0% and was normalized before projection.
- Observed FCF margin 113.4% exceeded the conservative margin cap of 45.0% and was normalized before projection.
- Observed FCF margin 116.4% exceeded the conservative margin cap of 45.0% and was normalized before projection.
- Observed revenue growth 43.1% exceeded the conservative start-growth cap of 40.0% and was normalized before projection.
- Observed revenue growth 47.1% exceeded the conservative start-growth cap of 40.0% and was normalized before projection.
- Observed revenue growth 51.1% exceeded the conservative start-growth cap of 40.0% and was normalized before projection.
- Peer data is unavailable or insufficient, so only standalone multiples are shown.
- Valuation missing field: ebitda
- Valuation missing field: market_cap_or_price_and_shares
- Valuation missing field: shares_outstanding
- analyst_estimates has no local row for this ticker.
- earnings has no local row for this ticker.

## Sources And Freshness
- local:prices.csv: research-grade / local, retrieved 2026-05-27T21:34:28.109158039+00:00; Local CSV-backed research data.
- local:fundamentals.csv: research-grade / local, retrieved 2026-05-27T21:34:35.086026430+00:00; Local fundamentals data.; Dataset row source: sec_companyfacts
- local:earnings.csv: research-grade / local, retrieved 2026-05-28T14:25:05+00:00; Earnings fields are unavailable from the bundled local sample files.
- local:analyst_estimates.csv: research-grade / local, retrieved 2026-05-28T14:25:05+00:00; Analyst estimate fields are unavailable from the bundled local sample files.

