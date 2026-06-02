# Product Spec

## Product Purpose

This project is a local, CSV-first stock research command center. It helps a user understand which tickers are available, which tickers are actively being researched, which analyses are trustworthy today, and what data should be imported next.

The product is not a trading bot. It does not place orders, connect to brokers, recommend options trades, or fabricate missing market, fundamentals, earnings, or analyst-estimate data.

## Target User

The target user is an individual investor or research operator who wants a deterministic local workflow for:

- maintaining a broad market universe;
- narrowing that universe into an active research list;
- reviewing portfolio holdings;
- tracking readiness by analysis feature;
- generating watchlists only when the needed data exists;
- seeing exact data blockers and next import actions.

## Non-Goals

- Broker integration.
- Auto-trading.
- Buy/sell/option-trade recommendations.
- Bloomberg-style full-provider coverage.
- Fabricated prices, fundamentals, earnings, analyst estimates, peers, or tickers.
- Hiding missing data behind weak rankings.
- Running expensive full-market analysis on every dashboard refresh.

## Core Product Principle

The product order is:

1. Data readiness first.
2. Analysis second.
3. Recommendation last.

Operationally:

- No data, no conclusion.
- Insufficient data, show exactly what is missing.
- Sufficient data, run the relevant analysis.
- Completed analysis, generate research decisions.
- Blocked analysis must not be rendered as a weak recommendation.

## Market-Wide Expansion Goal

The product should grow from a small watchlist workflow into a market-wide research system. Market-wide support means the product can store and report on a large master universe, while scoped analysis remains efficient and explicit.

Large-universe rules:

- Do not require all master tickers to have data.
- Do not analyze all master tickers by default.
- Support active-universe, selected-sector, selected-ticker, missing-only, and ready-only scopes.
- Keep human-readable CSV outputs.
- Keep active-watchlist workflows fast even when the master universe is large.

## Universe Layers

`master market universe`

All known tickers the product can reference. It is broad metadata, not a promise of analysis coverage.

`active research universe`

The smaller set the user currently wants to research. This preserves compatibility with the old `data/universe.csv` workflow.

`portfolio universe`

Tickers currently present in `data/holdings.csv`.

`watchlist`

Ticker-level research outputs from analysis and decision layers.

`analysis-ready subset`

The per-feature subset of tickers with enough data for a specific module, such as momentum, DCF, liquidity, or earnings.

## Core User Decisions

- What should I research now?
- What should I monitor?
- What is blocked by missing data?
- What should I exclude because the analysis does not apply?
- What data should I import next?
- Which analyses are trustworthy today?

## MVP Definition

The MVP is successful when:

- the app can run locally from CSV files;
- master and active universe concepts exist;
- readiness is reported per ticker and per feature;
- blocked and excluded states are visible;
- final research decisions are readiness-aware;
- staged manual imports are available;
- invalid import rows are rejected into CSV files;
- dashboard smoke passes with missing credentials and empty staged folders.

## Future Enhancements Not Implemented Yet

- Paid data-provider integrations.
- Broker connections.
- Automated order routing.
- Full SEC financial-statement modeling beyond staged fundamentals.
- Full market-scale background job scheduling.
- Parquet or SQLite caches for very large CSVs.
- Automated peer inference beyond clearly labeled sector/industry fallback.
- Options payoff workflows beyond educational user-supplied examples.
