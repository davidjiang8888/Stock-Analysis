---
name: stock-analysis-core
description: >
  Reusable stock-analysis workflow for this project. Activate when building or
  updating stock research features, market-analysis workflows, valuation
  summaries, earnings previews, earnings recaps, analyst estimate analysis, or
  yfinance-backed research adapters. Do not use for trade execution, broker
  automation, social sentiment scraping, TradingView desktop integration, or
  paid API provider integration.
---

# Stock Analysis Core Skill

This skill adapts selected workflow concepts from `himself65/finance-skills` for this repository.

Use it as an analysis workflow layer only.

- Never implement order placement, broker connections, or auto-trading.
- Keep all market and fundamental access behind the project's provider interfaces.
- Treat Yahoo/yfinance data as unofficial and research-grade when shown to users.
- Prefer structured data objects first, then render reports/UI from those objects.

## Step 1: Gather Research Inputs

For a stock-analysis feature, collect:

- quote / price snapshot
- price history for 1M / 3M / 1Y performance
- financials when available
- earnings context when available
- analyst estimates when available
- valuation assumptions and scenario ranges
- source and freshness metadata for every external data field

If any input is missing, continue with explicit missing-data notes instead of guessing.

## Step 2: Apply the Workflow Concepts

### `yfinance-data`

Use only through this repo's provider abstraction.

- pull quote, history, financials, earnings, analyst estimates, and optional options chain data
- label source as unofficial / research-grade
- capture retrieval time and freshness notes

### `company-valuation`

Produce valuation scaffolding, not false precision.

- define bull / base / bear assumptions
- define DCF inputs and relative-valuation inputs
- include sensitivity placeholders for WACC and terminal growth
- show assumptions explicitly

### `earnings-preview`

Before earnings:

- summarize consensus EPS / revenue if available
- show upcoming earnings date if available
- include prior beat/miss or estimate-trend context when available
- highlight what data is missing

### `earnings-recap`

After earnings:

- compare actual vs estimated EPS / revenue when available
- summarize surprise magnitude
- note price reaction only if price history supports it
- avoid narrative overreach when source coverage is weak

### `estimate-analysis`

When analyst data is available:

- summarize current-quarter, next-quarter, current-year, and next-year estimate trends
- call out missing coverage clearly
- avoid treating analyst consensus as a recommendation

## Step 3: Build the Output Object

Prefer a typed stock-report object with:

1. price snapshot
2. performance windows
3. financial summary
4. valuation snapshot
5. earnings summary
6. analyst estimate summary
7. key risks
8. source and freshness notes

The UI, CLI, or CSV renderer should consume this object rather than re-query data directly.

## Step 4: Guardrails

- No trade execution
- No broker integration
- No "buy now" / "sell now" style advice
- No paid or API-key-dependent provider in this first pass
- No direct TradingView/Funda/social-reader integration in this first pass
- No hidden data fetches bypassing provider interfaces

## Reference Files

- `references/data-providers.md` — source rules and provider boundaries
- `references/valuation-workflow.md` — valuation scaffolding and scenario design
- `references/earnings-workflow.md` — preview / recap / estimate-analysis steps
- `references/risk-guardrails.md` — research-only constraints and review checklist
