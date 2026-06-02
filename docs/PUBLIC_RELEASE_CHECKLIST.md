# Public Release Checklist

Use this checklist before sharing the repository on GitHub or LinkedIn.

## README And Visitor Experience

- Keep the top of `README.md` focused on what the project does, why it matters, and how to run it.
- Put the best demo commands near the top: `make pipeline`, `make project-status`, `make stock-report TICKER=NVDA`, and `make dashboard`.
- Include current readiness numbers only when they are clearly labeled as local snapshots.
- Keep generated examples that help visitors understand the product, such as `outputs/stock_reports/qqq.md` and `outputs/stock_reports/nvda.md`.
- Avoid committing huge timestamp-only generated CSV churn.

## Open-Source And Attribution Hygiene

Do not claim that the project uses no open-source software. A Python project normally depends on open-source packages such as pandas, pytest, Streamlit, or yfinance.

Safe public wording:

- "Original local research workflow and application code."
- "Built with the Python data ecosystem."
- "CSV-first implementation with optional provider interfaces."
- "Research-only; no broker integration or order execution."

Avoid public wording like:

- "No open source was used."
- "All code is 100% original" if the repo includes third-party dependencies, copied snippets, or adapted code.
- "Inspired by X" unless you intentionally want that connection visible.

If internal reference notes are not part of the public product, consider moving them out of the public branch before sharing. In this repo, that means reviewing whether `.agents/`, `AGENTS.md`, and internal skill/reference docs should be public-facing or kept as private development workflow material.

## License And Legal Basics

- Add a `LICENSE` file before sharing if you want others to know whether they can reuse the code.
- If the repo includes copied third-party code, keep required attribution and license notices.
- If the repo only uses normal package dependencies, dependency licenses are usually handled through package metadata, but do not hide or misrepresent them.
- Public data sources should be described accurately as data sources, not as proprietary data you created.

## Data And Privacy

- Check `data/holdings.csv` for personal portfolio details before publishing.
- Remove real account identifiers, emails, API keys, or private notes.
- Keep `.env`, caches, raw downloads, and rejected import files out of GitHub unless they are intentionally sanitized examples.
- Prefer small sample CSVs and Markdown reports over large generated datasets.

## Product Guardrails To Preserve

- No broker integration.
- No order routing.
- No auto-trading.
- No direct buy/sell instructions.
- No options recommendations.
- No fabricated prices, fundamentals, peer mappings, earnings, analyst estimates, valuation inputs, or recommendations.

## Suggested Final Verification

```bash
make pipeline
make readiness
make project-status
make stock-report TICKER=NVDA
make stock-report TICKER=QQQ
make test
make dashboard-smoke
git diff --check
```

If `make dashboard-smoke` fails only because the local sandbox cannot bind a port, mention that in the final release notes and verify the dashboard manually on your machine.
