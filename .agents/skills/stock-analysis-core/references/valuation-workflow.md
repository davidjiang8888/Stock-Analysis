# Valuation Workflow

This project uses valuation scaffolding, not fully automated investment conclusions.

## Required components

### DCF assumptions

- base-year free cash flow
- forecast horizon
- WACC
- terminal growth
- shares outstanding
- net cash / debt adjustment

### Relative valuation assumptions

- peer set
- target metric or multiple
- low / base / high peer multiple range

### Scenario framing

Every valuation workflow should support:

- bull case
- base case
- bear case

Each case should expose its assumptions instead of hiding them in a single score.

## Sensitivity expectations

When possible, include a sensitivity table placeholder that varies:

- WACC
- terminal growth

If the project lacks enough data to calculate implied values, keep the table structure and mark it as a TODO rather than inventing numbers.

## Output expectations

Valuation output should clearly separate:

- observed market data
- derived valuation assumptions
- scenario-based interpretation

Do not convert valuation scaffolding into direct buy/sell advice.
