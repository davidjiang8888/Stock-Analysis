# Legacy Scaffold

`stock_analysis/` is a legacy prototype kept only for reference during the transition to the active `src/` implementation.

- Use `python -m src.report_generator` for fresh outputs.
- Use `streamlit run src/dashboard.py` for the active dashboard.
- Tests are written against the `src/` pipeline, not this legacy scaffold.

Nothing in the current supported workflow should import or execute `stock_analysis.pipeline`.
