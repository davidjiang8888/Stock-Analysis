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
