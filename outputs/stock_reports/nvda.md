# NVDA Research Readiness Report

Research-only local report. This is not a trade instruction and cannot execute transactions.

## Decision
- Bucket: Research Now
- Subtype: Research Candidate - Core Data Ready
- Primary blocker: earnings
- Main reason: Core data is ready for a supported research pass.
- Next action: Optional context missing for NVDA; leave unavailable unless trusted local CSVs exist.

## Readiness
- Overall state: partial
- Price ready: True
- Momentum ready: True
- Liquidity ready: True
- Correlation ready: True
- Fundamentals ready: True
- DCF ready: True
- Peer ready: True
- Earnings ready: False
- Analyst estimates ready: False
- Blocked features: earnings, analyst_estimates
- Excluded features: Not available

## Price Coverage
- Price rows: 621
- First date: 2023-12-07
- Last date: 2026-05-22
- Missing price reason: Not available

## Valuation And DCF
- DCF status: calculated
- DCF missing fields: Not available
- Reason not ready: Not available

## Peer Workflow
- Peer blocker type: Not available
- Mapping status: mapped
- Peer count: 2
- Trend comparison ready: True
- Valuation comparison ready: True
- DCF peer comparison ready: True
- Sample peers: AMD, AVGO
- Next peer action: Peer trend and valuation comparison are ready for NVDA.

## Missing Data
- No local analyst-estimate dataset is configured in the CSV-first pipeline.
- No local earnings dataset is configured in the CSV-first pipeline.
- Normalized growth target was reduced to keep it conservatively below WACC.
- Observed FCF margin 47.8% exceeded the conservative margin cap of 45.0% and was normalized before projection.
- Observed revenue growth 61.5% exceeded the conservative start-growth cap of 40.0% and was normalized before projection.
- Observed revenue growth 65.5% exceeded the conservative start-growth cap of 40.0% and was normalized before projection.
- Observed revenue growth 69.5% exceeded the conservative start-growth cap of 40.0% and was normalized before projection.
- Valuation missing field: ebitda
- analyst_estimates has no local row for this ticker.
- earnings has no local row for this ticker.

## Sources And Freshness
- local:prices.csv: research-grade / local, retrieved 2026-05-27T21:34:28.109158039+00:00; Local CSV-backed research data.
- local:fundamentals.csv: research-grade / local, retrieved 2026-05-27T21:34:35.086026430+00:00; Local fundamentals data.; Dataset row source: sec_companyfacts
- local:earnings.csv: research-grade / local, retrieved 2026-05-28T14:25:05+00:00; Earnings fields are unavailable from the bundled local sample files.
- local:analyst_estimates.csv: research-grade / local, retrieved 2026-05-28T14:25:05+00:00; Analyst estimate fields are unavailable from the bundled local sample files.

