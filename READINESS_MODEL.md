# Readiness Model

## States

`ready`

The feature has enough valid local data for trustworthy analysis.

`partial`

Some useful data exists, but not enough for complete conclusions.

`blocked`

Required data is missing or invalid.

`excluded`

The feature does not apply to this ticker or asset type.

## Feature Readiness Matrix

| Readiness Type | Required Inputs | Minimum Data Requirements | Validation Rules | Affected Outputs | Dashboard Ready Behavior | Partial Behavior | Blocked Behavior | Excluded Behavior |
|---|---|---|---|---|---|---|---|---|
| `universe_ready` | `data/universe_master.csv`, `data/universe_active.csv`, compatibility `data/universe.csv` | ticker, source, asset type or conservative unknown | ticker required, source required, boolean listing fields parseable, duplicate tickers deduped | universe reports, readiness reports | show counts by universe layer | show missing metadata | show import/rejection instructions | not applicable |
| `price_ready` | `data/prices.csv` | configurable default 5 rows, positive close | ticker exists in universe, date parseable, close positive, numeric OHLCV when present | price coverage, ticker readiness | show latest dates and row count | show rows but insufficient thresholds | show missing price reason | not applicable |
| `momentum_ready` | prices | configurable default 20 rows | same as price plus enough history for momentum metrics | `momentum_leaders.csv`, decisions | rank only ready tickers | show partial history notes | list blocked tickers separately | not applicable |
| `market_direction_ready` | prices, theme/sector metadata | configurable default 20 rows per included ticker/theme | price validation plus theme/sector presence | `market_direction.csv` | show included themes/tickers | show incomplete themes | list excluded ticker count | ETFs may be included as market proxies |
| `liquidity_ready` | prices with volume | configurable default 60 rows preferred, at least enough for local estimate | numeric volume and close | `liquidity_risk.csv` | show liquidity calculations | show short-history warning | list unavailable tickers | not applicable |
| `correlation_ready` | prices | enough overlapping return rows, default 60 preferred | parseable prices by date | `correlation_risk.csv` | show correlation context | show insufficient overlap | list unavailable tickers | not applicable |
| `fundamentals_ready` | `data/fundamentals.csv` | at least one trusted row with source | ticker exists, numeric fields numeric, source required | fundamentals coverage, DCF readiness | show field coverage | show available subset | list missing fields | ETFs/funds may be excluded from company fundamentals use |
| `dcf_ready` | prices, fundamentals, company-like asset type | price, free cash flow, shares, revenue, FCF margin or derivable margin | company-like only, numeric required fields | DCF readiness, `undervalued_candidates.csv` | show valuation only for ready companies | show partial fields | show missing fields, `valuation_status=not_ready` | ETFs/index proxies/funds excluded |
| `peer_ready` | peers, universe, peer metrics | configurable peer count, default 2 | peer tickers exist, source required, no self-peer only | peer readiness, peer-relative valuation | show peer-relative context | show insufficient peer count | list missing peer reason | not applicable unless asset type unsupported |
| `earnings_ready` | `data/earnings.csv` | trusted local earnings row with source and useful date or metrics | dates parseable, numerics numeric, source required | earnings readiness, stock report | show earnings summary | show sparse row note | show unavailable state | not applicable |
| `analyst_estimates_ready` | `data/analyst_estimates.csv` | trusted local estimate row with source and useful metrics | numerics numeric, source required | analyst readiness, stock report | show estimate summary | show sparse row note | show unavailable state | not applicable |
| `portfolio_ready` | holdings, prices, purpose metadata | holding row plus enough relevant data for review component | holding ticker parseable, position fields numeric when present | `portfolio_review.csv` | show review state | show missing components | mark holding blocked | not applicable |
| `final_decision_ready` | central readiness report plus analysis outputs | enough data for the chosen decision bucket | blocked features reduce confidence | `research_decisions.csv`, `final_watchlist.csv` | show decision bucket and confidence | show reduced confidence | classify as Blocked by Data | classify as Excluded |

## General Dashboard Rules

- Show readiness before conclusions.
- Show `ready`, `partial`, `blocked`, and `excluded` labels plainly.
- Never rank blocked tickers as weak candidates.
- Never show empty earnings or estimate charts as analysis.
- ETFs and index proxies can support market/risk workflows but are excluded from operating-company DCF.
