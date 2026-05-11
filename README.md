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
- valuation scaffolding: `src/valuation.py`

Important:

- yfinance-backed data should be treated as unofficial / research-grade
- the core screener still runs on the local CSV-first pipeline
- all new market/fundamental calls stay behind provider interfaces

### Stock Report Beta in the dashboard

The Streamlit dashboard now includes a `Stock Report (Beta)` section.

- default mode uses the local CSV-backed provider
- optional yfinance mode is only used if you explicitly enable it
- yfinance results are labeled unofficial / research-grade
- the Beta section can export the structured report as JSON

This section is additive and does not replace the existing CSV-first screener pages.

### JSON / CLI export

You can generate a structured JSON stock report from the command line:

```bash
python -m src.stock_report --ticker AAPL --provider local
```

For a demo/smoke workflow:

```bash
python -m src.stock_report --ticker AAPL --provider mock
```

To write JSON to a file:

```bash
python -m src.stock_report --ticker AAPL --provider local --output outputs/aapl_stock_report.json
```

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
- uses conservative categories such as `Insufficient Data` and `Possible Value Trap`
- always includes a `Reason`

### `outputs/final_watchlist.csv`

Final state-machine view combining purpose, momentum, and portfolio context into one watchlist state.

- uses configured state labels from `config.yaml`
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
