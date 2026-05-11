# Stock Research Screener

This project is a local Python stock research screener for watchlist generation, portfolio review, risk discipline, and optional value / re-rating review.

It is research-only software:

- no auto-trading
- no broker integration
- no order routing
- no direct buy/sell advice
- no fabricated prices or fundamentals

## Active implementation

The supported implementation lives in `src/`.

- Use `python -m src.report_generator` to generate outputs.
- Use `streamlit run src/dashboard.py` to run the dashboard.
- The root `run.py` and `dashboard.py` files are compatibility wrappers that forward to the active `src` implementation.

The `stock_analysis/` directory is a documented legacy scaffold kept for reference only. It is not the active pipeline.

## Project layout

- `config.yaml`: thresholds, benchmark settings, and allowed state labels
- `data/universe.csv`: screening universe, default purposes, theme metadata, and sector ETFs
- `data/holdings.csv`: portfolio holdings, declared purposes, sizing, and thesis metadata
- `data/theme_map.csv`: theme-to-ETF mapping used by Market Direction
- `data/prices.csv`: local OHLCV source used by the default CSV provider
- `data/fundamentals.csv`: optional fundamentals for the value / re-rating engine
- `src/providers/local_data_catalog.py`: detects which local CSV datasets actually exist and what columns/tickers they cover
- `src/providers/csv_provider.py`: active local CSV data provider
- `outputs/`: generated research outputs
- `tests/`: regression and output-contract coverage for the active pipeline

## Setup

1. Create and activate a Python 3.10+ virtual environment.
2. Install dependencies:

```bash
pip install -e .[dev]
```

If you want the optional research-grade yfinance-backed stock report workflow, install:

```bash
pip install -e .[dev,research]
```

## Run the pipeline

Generate all active outputs:

```bash
python -m src.report_generator
```

The active pipeline now owns all generated CSVs:

- `outputs/purpose_classification.csv`
- `outputs/market_direction.csv`
- `outputs/momentum_leaders.csv`
- `outputs/portfolio_review.csv`
- `outputs/undervalued_candidates.csv`
- `outputs/final_watchlist.csv`

## Agent workflow layer

This repo also includes a Codex/agent workflow layer under:

- `.agents/skills/stock-analysis-core/`

It adapts selected market-analysis concepts from `himself65/finance-skills` for this project:

- `yfinance-data`
- `company-valuation`
- `earnings-preview`
- `earnings-recap`
- `estimate-analysis`

These are integrated as reusable research workflows only. They are not broker automations, trade execution systems, or production market-data guarantees.

## Optional stock report workflow

The project now includes a typed stock-report assembly layer for research workflows.

- provider interface: `src/providers/market_data.py`
- mock provider for tests: `src/providers/mock_market_data.py`
- optional yfinance adapter: `src/providers/yfinance_provider.py`
- report assembly: `src/stock_report.py`
- valuation engine: `src/valuation.py`

Important:

- yfinance-backed data should be treated as unofficial / research-grade
- the core screener still runs on the local CSV-first pipeline
- all new market/fundamental calls stay behind provider interfaces
- valuation is informational only and not financial advice
- local earnings and analyst-estimate coverage is intentionally limited unless a richer data source is added

### Local CSV-first architecture

The stock-report beta uses local files first.

- required for local stock reports: `data/prices.csv`
- optional for richer local stock reports: `data/fundamentals.csv`
- optional if you add them later: `data/earnings.csv`, `data/earnings_calendar.csv`, `data/earnings_history.csv`
- optional if you add them later: `data/analyst_estimates.csv` or `data/estimates.csv`
- optional if you add them later: `data/peers.csv`
- existing screener outputs under `outputs/*.csv` can also be surfaced as local context when they exist for a ticker

The local CSV path is now schema-driven and validated before the Stock Report Beta uses it. Missing files or sparse columns do not crash the workflow. The report continues with explicit missing-data warnings, schema validation notes, and source/freshness metadata.

### Phase 2B local schema definitions

The local schema validator lives in `src/providers/local_schemas.py`. It defines a small expected contract for optional enrichment files without requiring them to exist.

| Dataset | Required fields | Common optional valuation/report fields |
| --- | --- | --- |
| `data/fundamentals.csv` | `ticker` | `theme`, `sector`, `revenue`, `revenue_growth`, `eps`, `free_cash_flow`, `fcf_margin`, `profit_margin`, `operating_margin`, `ebitda`, `cash`, `debt`, `shares_outstanding`, `market_cap`, `pe_ratio`, `source`, `as_of_date` |
| `data/earnings.csv` / `data/earnings_history.csv` | `ticker` | `next_earnings_date`, `last_earnings_date`, `fiscal_period`, `eps_estimate`, `eps_actual`, `revenue_estimate`, `revenue_actual`, `surprise_pct`, `source`, `as_of_date` |
| `data/analyst_estimates.csv` / `data/estimates.csv` | `ticker` | `current_quarter_eps`, `next_quarter_eps`, `current_year_eps`, `next_year_eps`, `target_mean_price`, `target_high_price`, `target_low_price`, `recommendation`, `revision_trend`, `source`, `as_of_date` |
| `data/peers.csv` | `ticker`, `peer_ticker` | `peer_group`, `sector`, `industry`, `source`, `as_of_date` |

Validation behavior:

- missing required columns are reported as `invalid`
- optional missing files are reported as `missing_file`
- unknown extra columns are surfaced as warnings, not hard failures
- numeric/date parse failures are surfaced as warnings, not crashes
- ticker keys are normalized to uppercase
- `source` / `as_of_date` are preserved when present, otherwise freshness falls back to file-level metadata

The bundled `data/fundamentals.csv` remains intentionally sparse today. As of this repo state, its columns are:

- `ticker`
- `theme`
- `sector`
- `pe_ratio`
- `revenue_growth`
- `profit_margin`
- `debt_to_equity`

That means the bundled local path can usually provide partial relative-valuation context, but not a full DCF.

### Phase 2A valuation methodology

The stock report now includes a real valuation engine that stays conservative about missing data.

- DCF is calculated only when the local/provider inputs are sufficient
- direct FCF projection is used when free cash flow exists
- revenue-plus-FCF-margin projection is used when revenue and FCF margin exist
- EPS is never used as a hidden substitute for free cash flow
- WACC must remain above terminal growth
- per-share fair value is shown only when equity value and shares outstanding are both available
- when the inputs are incomplete, the valuation result returns `insufficient_data` or partial coverage instead of fabricated outputs

DCF defaults are explicit in code:

- bear: lower growth, lower FCF margin, higher WACC, lower terminal growth
- base: moderate growth, moderate WACC, moderate terminal growth
- bull: higher growth, higher FCF margin, lower WACC, higher terminal growth while still below WACC

Sensitivity:

- the dashboard and JSON output include a WACC vs terminal-growth sensitivity table
- the grid is only produced when the base DCF can actually derive fair value per share

Relative valuation:

- standalone P/E is calculated when price and EPS exist
- standalone P/S is calculated when price, revenue, and shares exist
- standalone P/FCF is calculated when price, FCF, and shares exist
- EV/EBITDA is calculated only when EBITDA, cash, debt, and market-cap context are available
- peer multiples are not fabricated; if `data/peers.csv` or peer fundamentals are unavailable, the result is labeled accordingly
- local peer medians can be used when `data/peers.csv` and the matching peer fundamentals are available
- peer-aware comparisons stay transparent through fields such as `PeerRelativeStatus` and `RelativeOpportunityScore`

Missing-data behavior for valuation:

- if local fundamentals only contain sparse fields, DCF returns `insufficient_data`
- if standalone multiples can be calculated but peer medians cannot, relative valuation returns `peer_data_unavailable`
- if local earnings or analyst-estimate files are missing, those sections stay explicit about local unavailability
- the stock report never fabricates prices, fundamentals, earnings, analyst estimates, or peer values

### Stock Report Beta in the dashboard

The Streamlit dashboard now includes a `Stock Report (Beta)` section.

- default mode uses the local CSV-backed provider
- optional yfinance mode is only used if you explicitly enable it
- yfinance results are labeled unofficial / research-grade
- the Beta section can export the structured report as JSON
- the Beta section can show local dataset coverage for the selected ticker
- the Beta section can show local dataset validation status and schema warnings
- the Beta section surfaces missing-data warnings instead of guessing unavailable values
- the Beta section shows valuation status, bull/base/bear scenarios, relative multiples, and sensitivity when available

This section is additive and does not replace the existing CSV-first screener pages.

### JSON / CLI export

You can generate a structured JSON stock report from the command line:

```bash
python -m src.stock_report --ticker NVDA --provider local
```

To discover locally available tickers first:

```bash
python -m src.stock_report --list-local-tickers
```

To validate your local CSV datasets and see schema/freshness warnings:

```bash
python -m src.stock_report --validate-local-data
```

For JSON-friendly validation output:

```bash
python -m src.stock_report --validate-local-data --json
```

For a demo/smoke workflow:

```bash
python -m src.stock_report --ticker AAPL --provider mock
```

To write JSON to a file:

```bash
python -m src.stock_report --ticker NVDA --provider local --output outputs/nvda_stock_report.json
```

For the local provider, use a ticker that actually exists in the bundled `data/prices.csv`. The sample project data currently supports names such as `NVDA`, `TSLA`, `SPY`, and `QQQ`.

The exported JSON includes:

- ticker
- generated timestamp
- provider name
- price snapshot and performance windows
- financial / earnings / analyst-estimate sections when local data exists
- valuation status, DCF result, bull/base/bear scenarios, sensitivity, and relative valuation context
- key risks
- missing-data warnings
- source / freshness metadata
- local dataset coverage
- local schema validation metadata

## Optional daily price-data update

The project remains CSV-first and works without network access. If you want to refresh `data/prices.csv` from a free daily source before running the screener, you can use:

```bash
python -m src.data_update
```

This updater:

- uses a free daily source with no paid API keys
- merges fetched rows into the local `data/prices.csv`
- keeps the existing local CSV fallback if the remote source is unavailable
- does not change the report pipeline requirement that local CSV data must exist for deterministic runs

## Run the dashboard

```bash
streamlit run src/dashboard.py
```

The dashboard includes:

- Market Direction
- Momentum Leaders
- Portfolio Review
- Value / Re-rating Candidates
- Final Watchlist

It reads from `outputs/*.csv`, shows friendly messages when files are missing, and surfaces explanation columns such as `Reason`, `MissingDataFields`, and `ConflictReasons` when available.

The dashboard and CLI are research-only surfaces. They do not execute trades, route orders, or connect to brokers.

## Enriching local CSV data

If you want richer deterministic valuation coverage without relying on yfinance:

1. Keep `data/prices.csv` populated for the tickers you care about.
2. Expand `data/fundamentals.csv` with real local fields such as:
   - `revenue`
   - `eps`
   - `free_cash_flow`
   - `fcf_margin`
   - `ebitda`
   - `cash`
   - `debt`
   - `shares_outstanding`
   - `market_cap`
   - `source`
   - `as_of_date`
3. Optionally add:
   - `data/earnings.csv`
   - `data/analyst_estimates.csv`
   - `data/peers.csv`
4. Re-run:

```bash
python -m src.stock_report --validate-local-data
python -m src.stock_report --ticker NVDA --provider local --output outputs/nvda_stock_report.json
```

This workflow remains CSV-first. yfinance is optional, unofficial / research-grade, and should only be used when you explicitly opt in.

## Run tests

```bash
pytest
```

## What each output means

### `outputs/purpose_classification.csv`

Primary purpose routing for each screened ticker or holding.

- assigns `FinalPrimaryPurpose`
- keeps `ConflictFlag` and `ConflictReasons` when the declared thesis conflicts with current data
- always includes a `Reason`

### `outputs/market_direction.csv`

Theme and ETF rotation view produced by the active `src` pipeline.

- reads `theme_map.csv` and `universe.csv`
- uses theme ETF data when available
- falls back to constituent medians when ETF data is unavailable
- computes 1M / 3M / 6M returns and relative performance vs SPY / QQQ when possible
- classifies themes as `Strong Rotation`, `Early Rotation`, `Overextended`, `Weak`, `Broken`, or `Insufficient Data`
- always includes `Reason` and `MissingDataFields`

### `outputs/momentum_leaders.csv`

Momentum setup classification for screened tickers.

- includes states such as `Watch`, `Setup Forming`, `Buyable Area`, `Extended / No Chase`, `Pullback Add Candidate`, `Broken`, and `Avoid`
- uses transparent moving-average, return, relative-strength, and volume rules
- always includes a `Reason`

### `outputs/portfolio_review.csv`

Holding review output for names in `holdings.csv`.

- includes action labels such as `Keep`, `Add Candidate`, `Hold but Do Not Add`, `Risk Reduce`, `Broken`, and `Review Thesis`
- evaluates concentration, setup quality, and thesis integrity
- always includes a `Reason`

### `outputs/undervalued_candidates.csv`

Optional value / re-rating screen.

- never fabricates missing fundamentals
- includes `MissingDataFields` when financial coverage is incomplete
- can include peer-aware relative valuation context when `data/peers.csv` and matching peer fundamentals are available
- surfaces fields such as `PeerCount`, `PeerRelativeStatus`, and `RelativeOpportunityScore`
- uses conservative categories such as `Insufficient Data` and `Possible Value Trap`
- always includes a `Reason`

### `outputs/final_watchlist.csv`

Final state-machine view combining purpose, momentum, and portfolio context into one watchlist state.

- uses configured state labels from `config.yaml`
- now adds transparent ranking fields such as `WatchlistScore`, `WatchlistRank`, and `RankReason`
- ranking is driven by final state plus value context, not by hidden model output
- always includes a `Reason`

## Missing-data behavior

The pipeline is designed to continue safely when data is sparse.

- Missing OHLCV produces warnings and conservative classifications instead of crashes.
- Missing theme ETF data can fall back to constituent-level theme medians when available.
- Missing fundamentals never get guessed; the value engine marks rows as incomplete instead.
- Long-horizon calculations stay blank until there is enough history.
- Output rows include `Reason`, and where applicable `MissingDataFields` or `ConflictReasons`, so missing inputs remain visible.

## Notes on local sample data

- The sample dataset intentionally has sparse OHLCV coverage for several universe tickers.
- Warnings about missing daily price history are expected with the bundled sample data.
- Benchmarks like `SPY` and `QQQ` may be used internally for comparisons without appearing in the screened outputs unless explicitly present in the universe or holdings.

## Constraints

- Research-only workflow
- No auto-trading
- No broker integration
- No direct buy/sell commands
- No fabricated market or fundamental data
- Explainable rules only
