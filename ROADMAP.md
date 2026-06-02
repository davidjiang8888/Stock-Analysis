# Roadmap

This roadmap reflects the current direction of the local Python/Streamlit stock research command center. The product principle remains:

1. Data readiness first.
2. Analysis second.
3. Recommendation last.

The next phase is not to add more indicators or AI-generated summaries. The next phase is to make the product page operational for a broad market universe while continuing to unlock decision-useful research through trusted fundamentals, peer metrics, earnings, and analyst estimates.

## 1. Completed Milestones

The following milestones are completed or mostly completed across the active-universe workflow and the broad-universe command-center foundation:

- [x] Readiness-first architecture.
- [x] CSV-first workflow.
- [x] Central readiness reporting.
- [x] Data-source status reporting.
- [x] Staged/manual import paths.
- [x] Price readiness for the current active universe.
- [x] Master-vs-active universe separation.
- [x] DCF gating.
- [x] ETF and index-proxy exclusion from operating-company DCF.
- [x] Final watchlist blocking when valuation is not ready.
- [x] Monthly picks staying empty when data is insufficient.
- [x] Dashboard smoke passing.
- [x] Test suite passing.
- [x] Broad-universe command center visibility for the current 3,538-ticker master universe.
- [x] Product-page readiness filters, row limits, and single-stock drilldown.
- [x] Peer Mapping Studio V1 with peer blocker filters and safe command cards.
- [x] Feature readiness summary and readiness-gated decision subtype reporting.

## 2. Current Product State

The product is usable today for price, momentum, and market-direction monitoring across the current active universe and a growing analysis-ready subset of the broad master universe.

The product is partially decision-useful for DCF-ready company research, but peer-relative analysis, earnings context, and analyst-estimate context remain blocked for most tickers because trusted source data is missing or incomplete. This is expected and correct: the system should not promote unsupported conclusions when the underlying data is not ready.

Current verified readiness baseline:

- Master universe rows: 3,538.
- Active research rows: 12.
- Price ready: 240/3,538.
- Momentum ready: 237/3,538.
- Liquidity ready: 232/3,538.
- Correlation ready: 232/3,538.
- Fundamentals ready: 23/3,538.
- DCF ready: 23/3,538.
- Peer ready: 3/3,538.
- Earnings ready: 0/3,538.
- Analyst estimates ready: 0/3,538.
- Overall readiness: 3,298 blocked, 240 partial.
- Decision buckets: 3,513 Blocked by Data, 23 Research Now, 2 Monitor.

The product correctly avoids fake conclusions. The next improvement is product-page workflow clarity plus trusted data ingestion, not more indicators.

## 3. Product-Page Roadmap

Goal: make the Streamlit page feel like a research command center instead of a collection of CSV tables.

- Keep the top-level page focused on readiness, blockers, next actions, and single-stock drilldowns.
- Group next actions by feature:
  - Price Coverage Batch
  - Fundamentals / DCF Unlock
  - Peer Mapping Unlock
  - Earnings Import Setup
  - Analyst Estimates Import Setup
  - Single-Stock Review
- Keep dashboard commands copyable only; do not execute actions from the product page.
- Keep broad-universe tables row-limited by default.
- Add source/freshness notes wherever an action depends on local CSVs, staged imports, Yahoo price refresh, SEC staging, or manual trusted inputs.
- Make active-universe vs master-universe language visible wherever counts differ.

## 4. Data-Unlock Roadmap

### A. Trusted Fundamentals Ingestion

Goal: unlock fundamentals readiness without fabricating company data.

- Configure `SEC_USER_AGENT`.
- Run SEC staging for active company tickers.
- Or support trusted manual fundamentals import through existing validate/preview/apply workflows.
- Validate required fields:
  - `revenue`
  - `free_cash_flow`
  - `fcf_margin`
  - `shares_outstanding`
- Generate or update `fundamentals_coverage_report.csv`.
- Improve `fundamentals_ready` from the current broad baseline of 23/3,538.

Acceptance notes:

- SEC staging should remain staged and reviewable.
- Manual imports must be source-backed.
- Invalid rows must be rejected into CSV reports instead of silently dropped.

### B. DCF Readiness Unlock

Goal: allow valuation conclusions only when DCF data is genuinely ready.

- Keep ETFs and index proxies excluded from operating-company DCF.
- Do not generate undervalued or overvalued conclusions for `not_ready` tickers.
- Improve `dcf_readiness_report.csv`.
- Only allow valuation conclusions for DCF-ready companies.
- Keep missing fields explicit per ticker.

Acceptance notes:

- `undervalued_candidates.csv` must keep `valuation_status=not_ready` for incomplete rows.
- DCF-ready companies must have trusted price and fundamentals inputs.
- DCF logic should remain transparent and conservative.

### C. Peer Readiness Unlock

Goal: support peer analysis without pretending peer valuation is available when only partial peer data exists.

- Add source-backed peer mappings.
- Add peer metrics.
- Separate readiness into:
  - `peer_price_ready`
  - `peer_momentum_ready`
  - `peer_fundamentals_ready`
  - `peer_valuation_ready`
- Do not require valuation readiness for peer trend comparison.
- Do not show peer valuation if peer valuation inputs are missing.

Acceptance notes:

- Peer relationships must be source-backed or transparently labeled as sector/industry fallback.
- Peer trend comparison may use price/momentum readiness.
- Peer valuation requires valuation inputs and should remain blocked when metrics are missing.

### D. Decision-Bucket Refinement

Goal: make decisions more informative than generic monitoring rows.

Baseline issue: the system previously produced generic `Monitor` decisions when price data was ready but core company research data was blocked. Recent work has started separating company data blockers from ETF monitoring, but the roadmap should continue refining this into durable reason codes and sub-buckets.

Add reason codes or sub-buckets:

- `Monitor - Price/Momentum Ready`
- `Monitor - ETF Market Proxy`
- `Blocked by Data - Missing Fundamentals`
- `Blocked by Data - Missing Peer Metrics`
- `Excluded - DCF Not Applicable`

Rules:

- `Research Now` cannot be assigned when critical data is missing.
- Company tickers with missing fundamentals or DCF inputs should not be treated as generic monitor candidates.
- ETFs can remain monitor candidates for market/risk use while staying excluded from company DCF.

## 5. P1 Roadmap

### A. Portfolio/Risk Completeness

Goal: make risk readiness clearer and reduce avoidable warnings.

- Fix the `ARKF` OHLCV missing warning or classify it as optional missing context.
- Improve liquidity/correlation readiness from the current broad baseline of 232/3,538 where appropriate.
- Make ATR proxy usage explicit for `NVDA` and `TSLA`.
- Keep proxy-based risk notes clearly labeled as approximations.

### B. Single Stock Research Mode

Goal: produce a data-honest single-ticker research report that uses the same readiness engine as the dashboard.

- Add ticker search in the dashboard.
- Support the CLI command:

```bash
make stock-report TICKER=META
```

The report should generate:

- Readiness.
- Company snapshot.
- Industry context.
- Trend analysis.
- Valuation status.
- Research decision.
- Source audit.
- Markdown report.

Rules:

- Must be data-honest.
- Must show blocked, partial, ready, and excluded states.
- Must not fabricate missing fundamentals, earnings, or analyst estimates.
- Must not produce unsupported buy/sell instructions.

### C. Market-Wide Universe Layer

Goal: support broader universe management without forcing expensive full-market analysis on dashboard load.

- Add or continue planning `universe_master.csv`.
- Keep `universe_active.csv` as the focused research subset.
- Allow single-stock lookup outside the active universe.
- Do not force full-market analysis on dashboard load.
- Support lazy/scoped analysis.
- Support active-universe, ticker-list, sector/theme, ready-only, and missing-data scopes.

## 6. P2 Roadmap

Goal: add trusted optional context workflows after fundamentals/DCF/peer readiness is no longer the main blocker.

- Trusted earnings import.
- Trusted analyst estimates import.
- Dashboard unavailable states when no trusted rows exist.
- Rejected-row reporting.
- Readiness reports for earnings and analyst estimates.

Rules:

- Earnings and analyst estimates are manual/trusted-local only until a provider interface is deliberately added.
- Empty trusted rows should render as unavailable, not as weak conclusions.
- Analyst consensus must not be treated as a recommendation.

## 7. Deprioritized Items

The following are intentionally deprioritized:

- More technical indicators.
- AI-generated recommendations.
- Monthly picks.
- Full-market ranking.
- Complex DCF model tuning.
- Additional dashboard charts.

Reason: the blocker is not the lack of indicators. The blocker is missing trusted data for fundamentals, peers, earnings, and analyst estimates.

## 8. Acceptance Criteria For The Next Roadmap Milestone

The next roadmap milestone is complete when:

- The product page clearly separates the 3,538-ticker master universe, 12-ticker active universe, and analysis-ready subset.
- The product page includes a grouped next-action console with safe capped or ticker-targeted commands.
- Next-action rows include source/freshness context and make clear that dashboard commands are copyable only.
- `SEC_USER_AGENT` is configured or manual fundamentals import is working.
- `fundamentals_ready` improves beyond 23/3,538 with trusted data only.
- `dcf_ready` improves beyond 23/3,538 with trusted data only.
- Peer readiness improves beyond 3/3,538 or peer blockers become more specific and actionable.
- Decision buckets remain more informative than generic monitor rows.
- `ARKF` and risk warnings are resolved or clearly classified.
- Single-stock research mode can generate a data-honest report.
- `make pipeline` passes.
- `make onboarding` passes.
- `make research-health` passes.
- `make readiness` passes.
- `make test` passes.
- `make dashboard-smoke` passes.

## Guardrails

- Do not fabricate market data.
- Do not fabricate fundamentals.
- Do not fabricate peer metrics.
- Do not fabricate earnings.
- Do not fabricate analyst estimates.
- Do not add broker integration.
- Do not add auto-trading.
- Do not make unsupported buy/sell recommendations.
