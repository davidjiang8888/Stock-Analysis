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
- `data/custom_universe.csv`: optional manual tickers for larger universe builds
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

### Command location and path safety

The safest workflow is to run commands from the repository root:

```bash
cd "/Users/yjian070/Documents/New project"
```

Most project CLIs now print the resolved project root, data directory, and outputs directory before doing file work. By default, they resolve paths from this repository root rather than from whatever shell directory you happen to be in. If you intentionally want to run against a fixture or alternate local dataset, pass explicit paths:

```bash
python3 -m src.stock_report --project-root "/Users/yjian070/Documents/New project" --validate-local-data
python3 -m src.stock_report --data-dir data --output-dir outputs --ticker NVDA --provider local
python3 -m src.report_generator --data-dir data --output-dir outputs
python3 -m src.monthly_picks --generate --data-dir data --output-dir outputs
```

For tests, prefer the bounded command below so pytest never scans your home directory by accident:

```bash
python3 -m pytest tests -q
```

## Convenience commands

The repo includes a `Makefile` and shell launchers so you do not need to remember every path-sensitive command.

Common commands:

```bash
make help
make status
make test
make verify
make validate-all
make pipeline
make monthly
make track-record
make validate-data
make research-health
make action-queue
make coverage
make onboarding
make templates
make price-refresh
make price-status
make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual
make price-validate
make price-preview
make price-apply
make daily
make dashboard
make dashboard-smoke
```

SEC and universe helpers:

```bash
SEC_USER_AGENT="Your Name your.email@example.com" make sec-stage
SEC_USER_AGENT="Your Name your.email@example.com" make sec-stage TICKERS=NVDA,MSFT
make sec-validate
make sec-preview
make sec-apply
make universe-preview
make universe-apply
```

If you are unsure what to run next, start with `make help`; it prints the core workflow, onboarding, price fallback, SEC staging, and universe commands. Use `make status` for a read-only local project snapshot. Use `make verify` for deterministic local verification that avoids remote price refresh. Use `make validate-all` for the extended local validation launcher, including monthly picks, track record, data-source checks, and a dashboard smoke check. Use `make dashboard-smoke` for only the quick headless Streamlit health check.

Path-proof shell launchers:

```bash
scripts/daily.sh
scripts/dashboard.sh
scripts/smoke_dashboard.sh
scripts/validate_all.sh
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

### External skill notes

This project also reviews selected ideas from:

- `himself65/finance-skills`
- `himself65/trade-skills`

Usage boundaries:

- finance-skills concepts are used only as research workflow inspiration
- trade-skills concepts are used only as options risk education
- no trade recommendations are generated
- no order execution or broker integration is implemented
- any future options-payoff tooling must stay educational only and require user-supplied legs or clearly labeled examples

Additional open-source product references are documented in:

- `.agents/skills/stock-analysis-core/references/open-source-product-map.md`

QuantGT is used only as product inspiration for a simple monthly research-candidate experience, benchmark comparison, archive, and methodology layout. This project does not copy QuantGT branding, text, pricing, proprietary strategy, or performance claims.

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

### Data source availability

Optional files being missing is not automatically a bug. The app is designed to continue with partial coverage and clear warnings instead of inventing unavailable data.

Run a local-only source check:

```bash
python3 -m src.data_sources --check
python3 -m src.data_sources --check --json
python3 -m src.data_sources --write-output
```

`--write-output` creates:

- `outputs/data_source_status.csv`
- `outputs/data_gap_report.csv`

Important source boundaries:

- SEC Companyfacts can stage candidate fundamentals only; it does not provide market prices, analyst estimates, earnings calendars, or peer mappings.
- Peer mappings are manual/local research. Add them through `data/imports/peers.csv` or `data/peers.csv`; the app never guesses peers.
- Earnings and analyst-estimate files are optional local CSVs and are not bundled with fabricated values.
- SMH holdings can be unavailable because the VanEck page may require redirect, cookie, or location handling. Use `data/custom_universe.csv` or staged universe imports as the manual fallback.
- yfinance remains optional, unofficial, and research-grade only. It is never required for the CSV-first pipeline.
- Short local price history limits track-record, 3M/6M/1Y returns, and long-horizon momentum calculations.

### Data onboarding workflow

Use the onboarding workflow when the dashboard shows sparse coverage or when you want a prioritized checklist for improving the local CSV dataset. It inspects local files only by default and does not fetch, guess, or fabricate unavailable data.

```bash
python3 -m src.data_onboarding --coverage
python3 -m src.data_onboarding --coverage --tickers NVDA,MSFT,AMD,AVGO
python3 -m src.data_onboarding --write-output
python3 -m src.data_onboarding --write-templates
```

Convenience targets:

```bash
make coverage
make onboarding
make templates
```

`--write-output` creates:

- `outputs/ticker_data_coverage.csv`
- `outputs/data_onboarding_actions.csv`

`--write-templates` creates header-only local templates under `data/templates/` for:

- `peers.csv`
- `fundamentals.csv`
- `earnings.csv`
- `analyst_estimates.csv`
- `custom_universe.csv`

Recommended order:

1. Run `make onboarding`.
2. Inspect the dashboard `Data Health` tab.
3. Refresh prices for priority tickers, for example `python3 -m src.data_update --tickers NVDA,MSFT`.
4. Stage SEC fundamentals for tickers that need DCF inputs.
5. Manually add peer mappings for important themes in `data/imports/peers.csv`.
6. Optionally add earnings or analyst-estimate CSVs only from trusted sources.
7. Rerun `make pipeline` and `make dashboard`.

Missing optional files are expected in many local workflows. Earnings, analyst estimates, peers, and SMH fallback data should remain blank until you provide verified local data.

### Phase 2B local schema definitions

The local schema validator lives in `src/providers/local_schemas.py`. It defines a small expected contract for optional enrichment files without requiring them to exist.

| Dataset | Required fields | Common optional valuation/report fields |
| --- | --- | --- |
| `data/fundamentals.csv` | `ticker` | `theme`, `sector`, `revenue`, `revenue_growth`, `eps`, `free_cash_flow`, `fcf_margin`, `profit_margin`, `operating_margin`, `ebitda`, `cash`, `debt`, `shares_outstanding`, `market_cap`, `pe_ratio`, `source`, `as_of_date` |
| `data/earnings.csv` / `data/earnings_history.csv` | `ticker` | `next_earnings_date`, `last_earnings_date`, `fiscal_period`, `eps_estimate`, `eps_actual`, `revenue_estimate`, `revenue_actual`, `surprise_pct`, `source`, `as_of_date` |
| `data/analyst_estimates.csv` / `data/estimates.csv` | `ticker` | `current_quarter_eps`, `next_quarter_eps`, `current_year_eps`, `next_year_eps`, `current_quarter_revenue`, `next_quarter_revenue`, `current_year_revenue`, `next_year_revenue`, `target_mean_price`, `target_high_price`, `target_low_price`, `recommendation`, `revision_trend`, `source`, `as_of_date` |
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
- unusually high observed revenue growth is normalized through a deterministic fade path instead of being compounded flat for the full forecast
- high observed growth and extreme FCF margins can be capped conservatively, with the original observed values preserved in the assumption output
- WACC must remain above terminal growth
- per-share fair value is shown only when equity value and shares outstanding are both available
- when the inputs are incomplete, the valuation result returns `insufficient_data` or partial coverage instead of fabricated outputs

DCF defaults are explicit in code:

- bear: lower growth, lower FCF margin, higher WACC, lower terminal growth
- base: moderate growth, moderate WACC, moderate terminal growth
- bull: higher growth, higher FCF margin, lower WACC, higher terminal growth while still below WACC
- all three scenarios use the same conservative growth-normalization framework rather than blindly extrapolating a single high-growth year

Assumption transparency:

- DCF output includes the observed revenue growth, normalized growth target, applied year-by-year growth path, and whether the growth path was capped
- fair value outputs are assumption-driven and informational only
- users should review the staged/local assumptions before relying on the valuation output

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
- peer-aware comparisons stay transparent through fields such as `peer_relative_status`, `relative_discount_premium_by_metric`, and `relative_opportunity_score`
- `peer_relative_status` meanings:
  - `peer_discount`: the subject screens cheaper than local peer medians across the available comparison metrics
  - `peer_premium`: the subject screens richer than local peer medians across the available comparison metrics
  - `mixed`: some metrics screen cheaper while others screen richer
  - `insufficient_peer_data`: there is not enough peer-relative data to form a comparison
- peer-relative output is research context only, not a buy/sell/hold recommendation

Missing-data behavior for valuation:

- if local fundamentals only contain sparse fields, DCF returns `insufficient_data`
- if standalone multiples can be calculated but peer medians cannot, relative valuation returns `peer_data_unavailable`
- if local earnings or analyst-estimate files are missing, those sections stay explicit about local unavailability
- the stock report never fabricates prices, fundamentals, earnings, analyst estimates, or peer values

### Local peer mappings

You can add local peer mappings with `data/peers.csv`.

Required columns:

- `ticker`
- `peer_ticker`

Optional columns:

- `peer_group`
- `sector`
- `industry`
- `source`
- `as_of_date`

Example:

```csv
ticker,peer_ticker,peer_group,source,as_of_date
NVDA,AMD,ai_semis,manual_research,2026-05-11
NVDA,AVGO,ai_semis,manual_research,2026-05-11
```

Behavior:

- ticker keys are normalized to uppercase
- self-peers are ignored with warnings
- duplicate `ticker + peer_ticker` rows are deduplicated conservatively
- peer medians only use local peer fundamentals and local prices when the required fields actually exist
- missing peer metrics are excluded instead of fabricated

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

To scaffold header-only local enrichment templates without fabricating any production data:

```bash
python -m src.stock_report --write-local-data-templates
```

For JSON-friendly template creation output:

```bash
python -m src.stock_report --write-local-data-templates --json
```

To scaffold header-only staging files directly under `data/imports/`:

```bash
python -m src.stock_report --write-import-staging
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
- valuation readiness diagnostics showing whether DCF, peer-relative work, earnings, and analyst estimates are actually available

Example peer-aware workflow:

```bash
python -m src.stock_report --write-local-data-templates
# fill data/imports/peers.csv or data/peers.csv with real peer mappings
python -m src.stock_report --validate-imports
python -m src.stock_report --preview-import-merge
python -m src.stock_report --apply-import-merge
python -m src.stock_report --ticker NVDA --provider local --output outputs/nvda_stock_report.json
```

## Optional daily price-data update

The project remains CSV-first and works without network access. If you want to refresh `data/prices.csv` from a free daily source before running the screener, you can use:

```bash
python -m src.data_update
```

This updater:

- uses a free daily source with no paid API keys
- merges fetched rows into the local `data/prices.csv`
- processes larger ticker sets in chunks
- skips already-fresh tickers unless you pass `--refresh`
- preserves partial progress instead of failing all-or-nothing when one ticker has issues
- keeps the existing local CSV fallback if the remote source is unavailable
- does not change the report pipeline requirement that local CSV data must exist for deterministic runs

Useful flags:

```bash
python -m src.data_update --universe-file data/universe.csv --max-tickers 100
python -m src.data_update --tickers NVDA,MSFT,AVGO
python -m src.data_update --chunk-size 25 --refresh
```

### Price data fallback workflow

Remote price refresh can fail because the default source is free, unofficial, and outside this repo's control. That is expected; the app keeps using local CSV fallback data instead of fabricating prices.

When remote refresh fails, use the staged manual import path:

```bash
make price-refresh
make price-status
# Fill data/imports/prices.csv with verified exported/local OHLCV rows.
make price-validate
make price-preview
make price-apply
make onboarding
make daily
make dashboard
```

Manual staged prices live at `data/imports/prices.csv`.

Required columns:

- `date`
- `ticker`
- `open`
- `high`
- `low`
- `close`
- `volume`

Optional columns:

- `adjusted_close`
- `source`
- `as_of_date`
- `notes`

Validation checks required columns, parseable dates, uppercase tickers, numeric OHLCV fields, duplicate `date + ticker` rows, `high >= low`, and non-missing positive closes. Preview shows new rows, updated rows, skipped rows, duplicates, and affected tickers before anything is written. Apply creates a backup under `data/backups/<timestamp>/` and never deletes existing canonical price rows in this phase.

Price update diagnostics are written to:

- `outputs/price_update_status.csv`

The dashboard `Data Health` tab surfaces this status file and gives the manual fallback commands. Price imports are still research-only local data management; no broker, order routing, or trade-execution integration is added.

### Normalize manually downloaded price CSVs

If you download historical OHLCV CSVs from a trusted source, place the raw files under:

- `data/raw/prices/`

Raw downloaded files are ignored by git so they do not get committed accidentally. They are treated as user-provided local data and are never applied directly to canonical `data/prices.csv`.

Yahoo-style historical exports are supported when they contain:

- `Date`
- `Open`
- `High`
- `Low`
- `Close`
- `Adj Close` or `Adj Close*`
- `Volume`

Example:

```bash
make price-worklist
make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual
make price-validate
make price-preview
make price-apply
```

`make price-worklist` shows the current ticker-by-ticker local history gap list, including which names are not yet ready for momentum, track record, or longer-horizon research context.

For DCF and peer-relative blockers, use:

```bash
make fundamentals-peer-worklist
```

This prints which tickers still need:

- SEC-stageable fundamentals for DCF readiness
- manual peer mappings in `data/imports/peers.csv`
- peer fundamentals or peer price / market-cap context for peer-relative valuation

For optional earnings and analyst-estimate context, use:

```bash
make optional-context-worklist
```

This keeps non-blocking enrichment explicit without treating it like a core pipeline failure. The output shows which tickers still have optional local context gaps and points back to `data/imports/earnings.csv` or `data/imports/analyst_estimates.csv` only when you have trusted local data.

Generic OHLCV CSVs are also supported when they include `date`, `ticker`, `open`, `high`, `low`, `close`, and `volume` columns:

```bash
python3 -m src.price_import_normalizer \
  --input data/raw/prices/prices.csv \
  --source generic_manual \
  --output data/imports/prices.csv
```

For unusual exports, map columns explicitly:

```bash
python3 -m src.price_import_normalizer \
  --input data/raw/prices/custom.csv \
  --date-col when \
  --ticker-col symbol \
  --open-col o \
  --high-col h \
  --low-col l \
  --close-col c \
  --volume-col v \
  --adjusted-close-col adj \
  --source mapped_manual
```

The normalizer writes/upserts only to `data/imports/prices.csv` using `date + ticker`. It reports rows read, written, skipped, invalid, and deduplicated, then prints the next validation/preview/apply commands. Do not use unverified or fabricated prices.

## Run the dashboard

```bash
streamlit run src/dashboard.py
```

If your shell is not already at the repository root, either `cd` there first or use the absolute dashboard path:

```bash
streamlit run "/Users/yjian070/Documents/New project/src/dashboard.py"
```

The dashboard now uses a wide tabbed layout with a sidebar for display controls.

Tabs:

- Overview
- Monthly Picks
- Market Direction
- Momentum Leaders
- Portfolio Review
- Value / Re-rating
- Final Watchlist
- Stock Report Beta
- Data Health
- Universe Manager

What each tab is for:

- `Overview`: quick metrics for universe size, holdings count, output coverage, missing-data warnings, local fundamentals coverage, DCF-ready count, peer-ready count, and research-health readiness
- `Monthly Picks`: top-five local research candidates, transparent scoring components, local track record, and archive views when enough local history exists
- `Market Direction`, `Momentum Leaders`, `Portfolio Review`, `Value / Re-rating`, `Final Watchlist`: filterable research tables with search, status filters, and highlighted explanation/risk fields
- `Stock Report Beta`: user-triggered structured stock reports with local CSV data first and optional yfinance clearly labeled as unofficial / research-grade
- `Data Health`: local dataset validation, research-health readiness, liquidity context, correlation concentration context, a ranked action queue, row counts, freshness timestamps, staged import status, and schema warnings
- `Universe Manager`: current universe size, source membership counts, staged universe import visibility, and CLI guidance for safe preview/write/apply flows

It reads from local files and `outputs/*.csv`, shows friendly messages when files are missing, and surfaces explanation columns such as `Reason`, `MissingDataFields`, and `ConflictReasons` when available.

The dashboard and CLI are research-only surfaces. They do not execute trades, route orders, or connect to brokers.

## Recommended daily workflow

The easiest path is now:

```bash
make onboarding
make daily
make dashboard
```

`make onboarding` refreshes local source/gap reports, ticker-level coverage actions, and the unified action queue. `make daily` runs the local price updater, report generator, monthly picks, track record, local-data validation, and the action queue in order. `make dashboard` opens the Streamlit dashboard from the repo root.

If price history is the main blocker, run:

```bash
make price-worklist
```

This prints the exact local price-history shortfall for each ticker and points back to the safe staged-import path:

- `data/raw/prices/`
- `make price-normalize`
- `make price-validate`
- `make price-preview`
- `make price-apply`

If valuation coverage is the main blocker, run:

```bash
make fundamentals-peer-worklist
```

This complements `make price-worklist` by showing which tickers are blocked on:

- missing local fundamentals rows
- incomplete DCF inputs such as free cash flow or shares outstanding
- missing peer mappings
- incomplete peer-relative inputs

If you want a clean list of optional earnings and analyst-estimate gaps, run:

```bash
make optional-context-worklist
```

This keeps optional enrichment visible while preserving the rule that missing earnings or estimates should never be fabricated and should not block the core local workflow.

If you prefer the explicit commands, the equivalent workflow is:

```bash
python3 -m src.data_update --universe-file data/universe.csv
python3 -m src.report_generator
python3 -m src.research_health --write-output
python3 -m src.monthly_picks --generate --top-n 5
python3 -m src.track_record --monthly-picks
python3 -m src.stock_report --validate-local-data
python3 -m src.data_sources --write-output
python3 -m src.data_onboarding --write-output
streamlit run src/dashboard.py
```

This keeps the project on its local research path:

- refresh local prices if you want newer research inputs
- regenerate the core screener CSV outputs
- generate local-only research-health outputs for data readiness, liquidity context, and correlation concentration
- generate the monthly research-candidate layer and local track-record files
- validate local enrichment coverage before relying on valuation-heavy reports
- create Data Health coverage/action reports so missing data has clear next steps
- review everything through the dashboard without any broker or trade execution features

## Monthly Research Picks

The productized monthly layer produces a small, transparent research-candidate list:

```bash
python3 -m src.monthly_picks --generate --top-n 5
python3 -m src.monthly_picks --generate --top-n 5 --json
```

Output:

- `outputs/monthly_research_picks.csv`

The default target is five candidates per month. The output may contain fewer than five rows when conservative filters
exclude weak, ignored, or insufficiently supported names. The dashboard will show messages such as `4 of 5 research
candidates available` rather than forcing lower-quality names into the list. These rows are research candidates, not
direct trade advice.

### How scoring works

The score is intentionally transparent and uses local fields that already exist in the CSV-first workflow:

- momentum / setup context from `outputs/momentum_leaders.csv`
- final-state context from `outputs/final_watchlist.csv`
- quality and value context from `outputs/undervalued_candidates.csv`
- local liquidity and technical context from `data/prices.csv`
- missing-data penalties when fields are unavailable

Default weights live in `config.yaml` under `monthly_picks`:

- momentum: 40%
- final state: 25%
- quality: 15%
- valuation context: 10%
- liquidity: 10%
- risk penalty: subtractive 10% weight

The output includes:

- transparent score components
- reason text
- missing-data fields
- source files
- generation timestamp

### Track record

The local track-record module uses only local historical prices:

```bash
python3 -m src.track_record --monthly-picks
python3 -m src.track_record --monthly-picks --benchmark SPY --json
```

Outputs:

- `outputs/monthly_picks_track_record.csv`
- `outputs/monthly_picks_equity_curve.csv`

The track record compares equal-weight monthly candidates against the benchmark when local price history supports the
selection date and forward return window. It needs enough dated local prices for the candidates and benchmark to form
month-end selections and next-month forward returns. If the bundled sample history is too short, the output says
`Insufficient local history` instead of fabricating a performance record or showing an empty chart as if it were real
performance.

### Interpretation

- monthly picks are research candidates, not trade instructions
- benchmark comparison is local-history-only and may be unavailable on sparse sample data
- no unverified performance claim is shown
- missing data reduces confidence and remains visible
- expanding the universe first can improve coverage, but larger universes require price updates and validation

## Universe expansion

The project now includes a source-driven universe builder that stages candidate universes before you apply them.

Supported sources:

- current local sample universe from `data/universe.csv`
- current holdings from `data/holdings.csv`
- S&P 500 companies from the open-source/community `datasets/s-and-p-500-companies` constituent list
- Nasdaq-listed securities from the official Nasdaq Trader symbol directory
- SMH holdings from VanEck’s public holdings surface when accessible
- manual local tickers from `data/custom_universe.csv`

Recommended presets:

- `core`: local universe + holdings
- `sp500_smh`: S&P 500 + SMH + holdings
- `broad`: S&P 500 + Nasdaq-listed common stocks + SMH + holdings

Useful commands:

```bash
python3 -m src.universe_builder --validate-sources
python3 -m src.universe_builder --preview --sources sp500,smh,holdings
python3 -m src.universe_builder --preview --sources sp500,nasdaq,smh,holdings --max-tickers 100
python3 -m src.universe_builder --write-import --sources sp500,smh,holdings
python3 -m src.universe_builder --apply-import
```

Safer smoke run for a larger build:

```bash
python3 -m src.universe_builder --preview --preset sp500_smh --max-tickers 50
python3 -m src.universe_builder --write-import --preset sp500_smh --max-tickers 50
```

Warnings:

- all-Nasdaq mode can be large and slow
- the Nasdaq directory contains many securities unless filtered
- the S&P 500 source is not the official paid S&P feed
- SMH holdings can change and should not be treated as recommendations
- the VanEck SMH web surface may redirect through cookie or location flows in automated runtimes; if that source is
  unavailable, use `data/custom_universe.csv` or stage `data/imports/universe.csv` manually with tickers you verified
  yourself

### `data/custom_universe.csv`

If you want to seed manual names into broader builds, create `data/custom_universe.csv` with columns such as:

- `ticker`
- `company_name`
- `theme`
- `sector`
- `sector_etf`
- `source`
- `notes`

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
python -m src.stock_report --write-local-data-templates
python -m src.stock_report --ticker NVDA --provider local --output outputs/nvda_stock_report.json
```

This workflow remains CSV-first. yfinance is optional, unofficial / research-grade, and should only be used when you explicitly opt in.

## Staged local import / merge workflow

You can now place real locally sourced enrichment files under:

- `data/imports/`

Supported staged files:

- `fundamentals.csv`
- `earnings.csv`
- `earnings_history.csv`
- `analyst_estimates.csv`
- `estimates.csv`
- `peers.csv`
- `universe.csv`

The importer never fabricates values. You must provide real local data and, where possible, include `source` and `as_of_date`.

### Import workflow commands

Validate staged files without mutating canonical data:

```bash
python -m src.stock_report --validate-imports
```

Preview what would change:

```bash
python -m src.stock_report --preview-import-merge
```

Apply the merge safely:

```bash
python -m src.stock_report --apply-import-merge
```

JSON output is also available:

```bash
python -m src.stock_report --validate-imports --json
python -m src.stock_report --preview-import-merge --json
python -m src.stock_report --apply-import-merge --json
```

### Merge behavior

- `fundamentals`, `earnings`, and `analyst estimates` merge by `ticker`
- `peers` merges by `ticker + peer_ticker`
- staged validation runs before merge
- invalid required columns refuse the apply step
- existing canonical rows are updated by key
- new keyed rows are appended
- rows with missing merge keys or duplicate staged keys are skipped and reported
- canonical files are backed up under `data/backups/<timestamp>/` before changed files are written
- staged unknown extra columns are ignored and reported
- existing canonical extra columns are preserved during merge
- this workflow does not delete canonical rows in this phase

### Example workflow

```bash
python -m src.stock_report --write-local-data-templates
cp data/templates/fundamentals.csv data/imports/fundamentals.csv
# fill in real local data manually
python -m src.stock_report --validate-imports
python -m src.stock_report --preview-import-merge
python -m src.stock_report --apply-import-merge
python -m src.stock_report --validate-local-data
python -m src.stock_report --ticker NVDA --provider local --output outputs/nvda_stock_report.json
```

To add peer mappings through the same workflow, use `data/imports/peers.csv` with:

- required: `ticker`, `peer_ticker`
- optional: `peer_group`, `sector`, `industry`, `source`, `as_of_date`

Peer mappings are not fabricated by the project. They must come from your own local research workflow.

## Universe Manager and Data Health

The `Data Health` tab helps you inspect:

- local dataset validation status
- row counts and latest timestamps
- missing optional files
- schema warnings
- staged import status
- data coverage wizard rows showing what unlocks Monthly Picks, track record, DCF, and peer-relative research next

The `Universe Manager` tab helps you inspect:

- current universe size
- source membership counts
- duplicate ticker count
- missing theme / sector ETF coverage
- staged `data/imports/universe.csv` visibility
- CLI commands for safe preview/write/apply workflows

Universe changes remain CLI-first on purpose. The dashboard is read-only for apply actions.

## Dashboard troubleshooting for partial data

The dashboard is designed to look usable even when local data is sparse:

- `Not available` means the source column or file is missing locally.
- `Needs SEC enrichment` means valuation-heavy fields are not present in `data/fundamentals.csv`.
- `Needs peers.csv`, `Needs earnings.csv`, or `Needs analyst_estimates.csv` means optional enrichment files are not configured.
- `Not enough price history` means the local `data/prices.csv` window is too short for that return, technical context, or track-record calculation.
- Monthly Picks may show fewer than the configured `top_n` when conservative filters reject weak or ignored names.
- Track-record panels stay informational until local historical prices support month-end selection and next-month return calculations.

## Research Health outputs

The pipeline also writes local-only research health files:

- `outputs/data_quality_wizard.csv`: ticker-level readiness for momentum, monthly picks, DCF, peer-relative valuation, earnings, and analyst-estimate coverage
- `outputs/liquidity_risk.csv`: local volume and dollar-volume context using only local price rows
- `outputs/correlation_risk.csv`: local co-movement context based on overlapping local return history

Generate them through the normal pipeline or directly:

```bash
python3 -m src.report_generator
python3 -m src.research_health --write-output
make research-health
```

These files are diagnostic. They do not change ticker classifications, do not execute trades, and do not turn missing data into synthetic values. Liquidity and correlation rows are research context only; they are not buy/sell/hold instructions.

## Research action queue

The project can also generate:

- `outputs/research_action_queue.csv`

This queue combines:

- price refresh failures from `outputs/price_update_status.csv`
- source gaps from `outputs/data_gap_report.csv`
- ticker-level onboarding priorities from `outputs/data_onboarding_actions.csv`
- readiness signals from `outputs/data_quality_wizard.csv`

Generate it with:

```bash
python3 -m src.action_queue --write-output
make action-queue
```

The queue stays read-only and research-only. It does not apply imports or write market data for you; it only ranks what to fix next and shows the relevant local file or command.

## Data coverage wizard

The data coverage wizard is the next layer above onboarding. It translates local coverage gaps into explicit unlock paths:

- `Unlock Monthly Picks`: usually blocked by missing or short local price history.
- `Unlock Track Record`: blocked by insufficient dated local price history for picks and benchmark comparison.
- `Unlock DCF`: blocked by missing fundamentals such as free cash flow or revenue plus FCF margin, and shares outstanding.
- `Unlock Peer Relative`: blocked by missing peer mappings or missing peer fundamentals/prices.
- `Add Earnings Context` and `Add Analyst Estimate Context`: optional local enrichments that do not block the core workflow.

Generate it with:

```bash
python3 -m src.data_onboarding --wizard
python3 -m src.data_onboarding --wizard --json
python3 -m src.data_onboarding --write-output
make data-wizard
make onboarding
```

`python3 -m src.data_onboarding --write-output` writes:

- `outputs/ticker_data_coverage.csv`
- `outputs/data_onboarding_actions.csv`
- `outputs/data_coverage_wizard.csv`

The wizard is read-only. It does not fetch, stage, merge, or fabricate data. Use the existing safe workflows for actual data changes:

- prices: `data/raw/prices/` -> `make price-normalize` -> `make price-validate` -> `make price-preview` -> `make price-apply`
- fundamentals: SEC staging -> validate -> preview -> apply
- peers/earnings/estimates: fill trusted local CSVs under `data/imports/`, then validate and preview before applying

## SEC Companyfacts staging workflow

The project now includes a read-only SEC Companyfacts adapter that can stage candidate fundamentals into:

- `data/imports/fundamentals.csv`

It never writes directly to `data/fundamentals.csv`. You must still review staged data and run the explicit import workflow.

### User-Agent requirement

SEC requests require an identifying User-Agent. You can provide it either as:

- CLI flag: `--sec-user-agent "Your Name your.email@example.com"`
- environment variable: `SEC_USER_AGENT`

Example:

```bash
export SEC_USER_AGENT="Your Name your.email@example.com"
```

### Cache and fair-access behavior

- the SEC ticker map and Companyfacts responses are cached under `data/cache/sec/`
- cached JSON is reused unless you pass `--sec-refresh`
- the adapter uses a small delay between live requests to stay within fair-access expectations
- tests mock SEC responses and do not require network access

### What the SEC adapter can stage

When the facts are available, the adapter may stage:

- `revenue`
- `revenue_growth`
- `eps`
- `free_cash_flow`
- `fcf_margin`
- `profit_margin`
- `operating_margin`
- `ebitda` only when directly available from SEC facts
- `cash`
- `debt`
- `shares_outstanding`
- `source`
- `as_of_date`
- SEC metadata fields such as `sec_cik`, `sec_form`, `sec_filed_date`, `sec_accession`, `sec_fact_warnings`, and `sec_entity_name`

Fields may remain blank when the official SEC facts are missing or not reliably derivable.

Important limits:

- SEC staging does not create analyst estimates
- SEC staging does not create peer mappings
- SEC staging does not fetch market prices
- SEC staging does not apply imports automatically
- user review is still required before merging staged data

### SEC staging commands

Stage explicit tickers:

```bash
python -m src.stock_report --sec-stage-fundamentals --tickers NVDA,MSFT --sec-user-agent "Your Name your.email@example.com"
```

Stage from the local ticker universe:

```bash
python -m src.stock_report --sec-stage-fundamentals --from-local-tickers --sec-user-agent "Your Name your.email@example.com"
python -m src.stock_report --sec-stage-fundamentals --from-universe --sec-user-agent "Your Name your.email@example.com"
python -m src.stock_report --sec-stage-fundamentals --from-holdings --sec-user-agent "Your Name your.email@example.com"
```

Optional flags:

- `--sec-refresh` to refresh SEC cache entries
- `--overwrite` to replace the staged `data/imports/fundamentals.csv` file instead of upserting by ticker
- `--json` for JSON-formatted CLI output

### SEC staging example

```bash
export SEC_USER_AGENT="Your Name your.email@example.com"
python -m src.stock_report --sec-stage-fundamentals --tickers NVDA,MSFT
python -m src.stock_report --validate-imports
python -m src.stock_report --preview-import-merge
python -m src.stock_report --apply-import-merge
python -m src.stock_report --validate-local-data
python -m src.stock_report --ticker NVDA --provider local --output outputs/nvda_stock_report.json
```

This remains a research-only workflow. It does not execute trades, place orders, or provide direct buy/sell advice.

## Fundamentals enrichment workflow

If you want to enrich canonical local fundamentals safely, use the staged SEC + import flow:

```bash
export SEC_USER_AGENT="Your Name your.email@example.com"
python3 -m src.stock_report --sec-stage-fundamentals --from-local-tickers
python3 -m src.stock_report --validate-imports
python3 -m src.stock_report --preview-import-merge
python3 -m src.stock_report --apply-import-merge
python3 -m src.stock_report --validate-local-data
```

This flow is explicit by design:

- SEC enrichment stays read-only until you apply the local import merge
- analyst estimates, peer mappings, and market prices are still separate local inputs
- valuation remains informational and assumption-driven even after fundamentals are enriched

If you also want to expand the screening universe afterward:

```bash
python3 -m src.universe_builder --preview --preset sp500_smh --max-tickers 50
python3 -m src.universe_builder --write-import --preset sp500_smh --max-tickers 50
python3 -m src.universe_builder --apply-import
python3 -m src.data_update --universe-file data/universe.csv --max-tickers 100
```

## Run tests

```bash
python3 -m pytest tests -q
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

## Local data onboarding tips

- `python3 -m src.data_onboarding --write-output` creates ticker-level coverage and action reports for the Data Health dashboard
- `python3 -m src.data_onboarding --write-templates` creates header-only onboarding templates under `data/templates/`
- `--write-local-data-templates` creates header-only CSV templates under `data/templates/`
- `--write-import-staging` creates header-only staging files under `data/imports/`
- these templates are safe starting points for adding real local data later
- they do not fabricate fundamentals, earnings, analyst estimates, or peer mappings
- the Stock Report Beta now includes valuation-readiness diagnostics so you can see exactly which inputs are still missing for:
  - DCF
  - peer-relative valuation
  - earnings summary
  - analyst estimate summary

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
