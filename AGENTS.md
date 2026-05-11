# AGENTS.md

You are building a local Python stock research screener.

This project is for investment research, watchlist generation, portfolio review, and risk discipline.
It must not implement auto-trading, order execution, broker integration, or direct buy/sell instructions.

## Core philosophy

The system should not ask "Is this stock good?"
It should ask:
1. What is the purpose of this stock?
2. Does the current data still match that purpose?
3. What is the setup status?
4. What is the invalidation condition?
5. What is the portfolio risk?

Each ticker should be classified by purpose before being scored.

## Stock purpose categories

Use these primary purpose categories:

1. Momentum Leader
2. Pullback Add Candidate
3. Core Compounder
4. Re-rating / Undervalued
5. Speculative Optionality
6. ETF / Defensive / Hedge
7. Broken / Avoid

A ticker may have multiple tags, but it must have one primary purpose.

## Required engines

Build the project with these engines:

1. Purpose Router
- Assigns primary purpose and secondary tags.
- Uses config rules and available market/fundamental data.
- For user holdings, respect the user-provided primary purpose in holdings.csv, but flag if the current data conflicts with that purpose.

2. Market Direction Engine
- Identifies strongest themes, sectors, and ETFs.
- Calculates relative strength vs SPY and QQQ.
- Classifies themes as Strong Rotation, Early Rotation, Overextended, Weak, or Broken.

3. Momentum Engine
- Finds leaders.
- Calculates relative strength, moving averages, volume confirmation, extension risk, and pivot proximity.
- Classifies each ticker as Buyable Area, Watch, Setup Forming, Extended / No Chase, Pullback Add Candidate, Broken, or Avoid.

4. Portfolio Review Engine
- Reads holdings.csv.
- Evaluates each holding against its purpose.
- Checks trend, relative strength, concentration risk, opportunity cost, and invalidation level.
- Outputs Keep, Add Candidate, Hold but Do Not Add, Risk Reduce, Broken, or Review Thesis.

5. Value / Re-rating Engine
- Looks for quality stocks that may be undervalued.
- Separates Re-rating Candidate from Cheap but Weak and Possible Value Trap.
- Never fabricates unavailable fundamentals.

6. Risk Engine
- Enforces max position size.
- Flags high-volatility names.
- Flags broken trends.
- Flags excessive theme concentration.
- Provides invalidation levels and risk notes.

## Technical rules

Use adjusted prices where possible.
Handle missing data gracefully.
Never fabricate missing data.
Keep scoring formulas transparent.
Every output row must include reasons, not just scores.
Do not hide rules inside black-box model calls.

## Output files

Generate these outputs:

outputs/purpose_classification.csv
outputs/market_direction.csv
outputs/momentum_leaders.csv
outputs/portfolio_review.csv
outputs/undervalued_candidates.csv
outputs/final_watchlist.csv

## Dashboard

Build a simple Streamlit dashboard with pages:

1. Market Direction
2. Momentum Leaders
3. Portfolio Review
4. Value / Re-rating Candidates
5. Final Watchlist

## Testing and validation

Add unit tests for:
- moving average calculations
- relative strength calculations
- purpose classification rules
- broken trend rules
- extended / no chase rules
- portfolio concentration rules

## Done means

The project is done when:
- It can run locally with one command.
- It generates all output CSV files.
- The dashboard opens successfully.
- Missing data does not crash the program.
- README explains setup, inputs, outputs, and limitations.
- The system does not output direct buy/sell commands.
