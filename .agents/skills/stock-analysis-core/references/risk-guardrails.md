# Risk Guardrails

Use this workflow layer for research only.

## Never do

- trade execution
- broker automation
- order placement
- position synchronization with a brokerage
- hidden recommendation scoring that implies a trading action

## Always do

- show missing-data limitations
- keep assumptions visible
- mark unofficial data sources clearly
- keep provider boundaries explicit
- run available tests before finishing a change

## Review checklist

Before completing stock-analysis workflow work:

1. Is every external market/fundamental call routed through a provider interface?
2. Is source/freshness metadata preserved?
3. Are valuation assumptions explicit?
4. Are earnings/estimate gaps shown rather than guessed?
5. Is there any accidental trade-execution or order-routing logic?
6. Were the available tests run?
