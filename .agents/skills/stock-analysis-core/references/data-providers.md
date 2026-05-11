# Data Providers

This project keeps market and fundamental data behind provider interfaces.

## Current policy

- The existing screener pipeline remains CSV-first for deterministic local runs.
- Optional network-backed research providers must sit behind typed provider interfaces.
- yfinance may be used for research workflows, but only as an unofficial source.
- Do not bypass the provider layer by calling `yfinance`, `requests`, or browser scrapers directly from report assembly code.

## Source labeling rules

When data is shown to users, include:

- provider name
- retrieval timestamp or freshness note
- whether the source is official or unofficial
- any missing-data caveats

For Yahoo/yfinance-backed data, use wording such as:

- `Unofficial / research-grade market data`
- `Not affiliated with Yahoo`

## First-pass scope

Allowed in this pass:

- quote snapshots
- daily price history
- high-level financial summaries
- earnings metadata
- analyst estimate summaries
- optional options-chain interface stubs

Not allowed in this pass:

- TradingView desktop readers
- Funda integrations
- social readers
- paid API-key providers
- direct broker or order-routing integrations
