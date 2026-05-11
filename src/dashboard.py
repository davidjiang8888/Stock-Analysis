from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.stock_report import build_provider, build_stock_report, export_stock_report_json


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"
DATA_DIR = BASE_DIR / "data"
WARNING_STATES = {"Broken", "Extended / No Chase", "Risk Reduce"}
PAGE_TO_FILE = {
    "Market Direction": "market_direction.csv",
    "Momentum Leaders": "momentum_leaders.csv",
    "Portfolio Review": "portfolio_review.csv",
    "Value / Re-rating Candidates": "undervalued_candidates.csv",
    "Final Watchlist": "final_watchlist.csv",
}
PIPELINE_MANAGED_FILES = {
    "market_direction.csv",
    "purpose_classification.csv",
    "momentum_leaders.csv",
    "portfolio_review.csv",
    "undervalued_candidates.csv",
    "final_watchlist.csv",
}
STATE_COLORS = {
    "Buyable Area": "#d1fae5",
    "Watch": "#dbeafe",
    "Setup Forming": "#fef3c7",
    "Pullback Add Candidate": "#e0f2fe",
    "Extended / No Chase": "#fde68a",
    "Risk Reduce": "#fecaca",
    "Broken": "#fca5a5",
    "Review Thesis": "#fcd34d",
    "Keep": "#d1fae5",
    "Add Candidate": "#bae6fd",
    "Hold but Do Not Add": "#e5e7eb",
    "Avoid": "#e5e7eb",
    "Ignore": "#f3f4f6",
}


def load_output(path: Path) -> tuple[pd.DataFrame | None, str | None]:
    if not path.exists():
        return None, f"`{path.name}` has not been generated yet. Run `python -m src.report_generator` first."
    try:
        frame = pd.read_csv(path)
    except Exception as exc:  # pragma: no cover - defensive UI path
        return None, f"Could not read `{path.name}`: {exc}"
    if frame.empty:
        return frame, f"`{path.name}` is present but currently empty."
    return frame, None


def is_state_column(name: str) -> bool:
    lowered = name.lower()
    return lowered.endswith("state") or lowered.endswith("status") or lowered == "classification"


def style_state_columns(frame: pd.DataFrame):
    state_columns = [column for column in frame.columns if is_state_column(column)]

    def color_value(value: object) -> str:
        if pd.isna(value):
            return ""
        return f"background-color: {STATE_COLORS.get(str(value), '')}"

    if not state_columns:
        return frame
    return frame.style.map(color_value, subset=state_columns)


def find_warning_rows(frame: pd.DataFrame) -> pd.DataFrame:
    state_columns = [column for column in frame.columns if is_state_column(column)]
    if not state_columns:
        return pd.DataFrame(columns=frame.columns)

    mask = pd.Series(False, index=frame.index)
    for column in state_columns:
        mask = mask | frame[column].astype(str).isin(WARNING_STATES)
    return frame.loc[mask].copy()


def render_reasons(frame: pd.DataFrame) -> None:
    reason_columns = [column for column in frame.columns if column.lower() == "reason" or "reason" in column.lower()]
    if not reason_columns:
        st.info("No reason columns were found in this output.")
        return

    with st.expander("Reasons", expanded=True):
        for column in reason_columns:
            st.markdown(f"**{column}**")
            reasons = frame[[col for col in frame.columns if col in {"Ticker", "Theme", "FinalState", "SetupStatus", "ReviewState", column}]].copy()
            st.dataframe(reasons, width="stretch", hide_index=True)


def render_supporting_columns(frame: pd.DataFrame) -> None:
    supporting_columns = [
        column
        for column in frame.columns
        if any(keyword in column.lower() for keyword in ("missing", "conflict", "risk"))
    ]
    if not supporting_columns:
        return

    with st.expander("Missing Data And Risk Details", expanded=False):
        columns = [
            column
            for column in frame.columns
            if column in {"Ticker", "Theme", "FinalState", "SetupStatus", "ReviewState", "ThemeStatus"}
            or column in supporting_columns
        ]
        st.dataframe(frame[columns], width="stretch", hide_index=True)


def get_dashboard_tickers() -> list[str]:
    tickers: set[str] = set()
    for filename in ("universe.csv", "holdings.csv"):
        path = DATA_DIR / filename
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        normalized_columns = [column.strip().lower() for column in frame.columns]
        frame.columns = normalized_columns
        if "ticker" in frame.columns:
            tickers.update(frame["ticker"].dropna().astype(str).str.upper().str.strip())
    return sorted(ticker for ticker in tickers if ticker)


def render_stock_report_beta() -> None:
    st.divider()
    with st.expander("Stock Report (Beta)", expanded=False):
        st.caption(
            "Structured research report workflow. Uses the local CSV-backed provider by default. "
            "Optional yfinance mode is unofficial / research-grade and must be explicitly enabled."
        )

        try:
            local_provider = build_provider("local", base_dir=BASE_DIR)
            preset_tickers = local_provider.list_local_tickers() if hasattr(local_provider, "list_local_tickers") else get_dashboard_tickers()
        except FileNotFoundError:
            local_provider = None
            preset_tickers = get_dashboard_tickers()
        ticker_options = ["Custom"] + preset_tickers if preset_tickers else ["Custom"]
        selected = st.selectbox("Ticker", ticker_options, index=1 if len(ticker_options) > 1 else 0)
        custom_ticker = st.text_input("Custom ticker", value="" if selected != "Custom" else "AAPL")
        ticker = (custom_ticker if selected == "Custom" else selected).strip().upper()

        use_yfinance = st.checkbox(
            "Use yfinance (unofficial / research-grade)",
            value=False,
            help="Leave this off to stay on the local CSV-first data path.",
        )
        provider_name = "yfinance" if use_yfinance else "local"

        if local_provider is not None and ticker and hasattr(local_provider, "get_ticker_dataset_coverage"):
            with st.expander("Local dataset coverage for selected ticker", expanded=False):
                coverage = pd.DataFrame(local_provider.get_ticker_dataset_coverage(ticker))
                st.dataframe(coverage, width="stretch", hide_index=True)

        if st.button("Generate Stock Report", key="stock-report-beta"):
            if not ticker:
                st.warning("Enter a ticker to generate a stock report.")
                return
            try:
                provider = build_provider(provider_name, base_dir=BASE_DIR)
                report = build_stock_report(ticker, provider)
            except RuntimeError as exc:
                st.error(str(exc))
                return
            except (LookupError, FileNotFoundError, ValueError) as exc:
                st.warning(str(exc))
                return

            report_payload = report.to_dict()
            if use_yfinance:
                st.info("Using yfinance as an unofficial / research-grade source. This is not a production market-data feed.")

            st.subheader(f"{ticker} Stock Report")
            st.markdown("**1. Price Snapshot**")
            st.json(report_payload["price_snapshot"], expanded=False)

            st.markdown("**2. 1M / 3M / 1Y Performance**")
            st.json(report_payload["performance"], expanded=False)

            st.markdown("**3. Financial Summary**")
            st.json(report_payload["financial_summary"], expanded=False)

            valuation = report_payload["valuation_snapshot"]
            st.markdown("**4. Valuation**")
            st.write(f"Status: `{valuation['status']}`")
            st.write(f"Coverage: `{valuation.get('coverage', 'n/a')}`")

            base_dcf = valuation["dcf_result"]
            if base_dcf.get("fair_value_per_share") is not None:
                st.write(f"Base-case fair value per share: `{base_dcf['fair_value_per_share']:.2f}`")
            else:
                st.write("Base-case fair value per share is unavailable with the current data.")

            scenario_rows = []
            for scenario in valuation.get("scenarios", []):
                result = scenario["dcf_result"]
                scenario_rows.append(
                    {
                        "Scenario": scenario["name"],
                        "Status": result["status"],
                        "WACC": scenario["assumptions"]["wacc"],
                        "TerminalGrowth": scenario["assumptions"]["terminal_growth"],
                        "RevenueGrowth": scenario["assumptions"]["revenue_growth"],
                        "FCFMargin": scenario["assumptions"]["fcf_margin"],
                        "FairValuePerShare": result["fair_value_per_share"],
                        "EnterpriseValue": result["enterprise_value"],
                        "EquityValue": result["equity_value"],
                    }
                )
            if scenario_rows:
                st.caption("Bull / base / bear scenarios")
                st.dataframe(pd.DataFrame(scenario_rows), width="stretch", hide_index=True)

            relative = valuation["relative_valuation"]
            st.caption("Relative valuation")
            st.json(
                {
                    "status": relative["status"],
                    "available_multiples": relative["available_multiples"],
                    "missing_fields": relative["missing_fields"],
                    "warnings": relative["warnings"],
                    "notes": relative["notes"],
                },
                expanded=False,
            )

            sensitivity = valuation["sensitivity_table"]
            if sensitivity["status"] == "calculated" and sensitivity["fair_value_grid"]:
                sensitivity_frame = pd.DataFrame(
                    sensitivity["fair_value_grid"],
                    index=[f"WACC {value:.1%}" for value in sensitivity["wacc_values"]],
                    columns=[f"TG {value:.1%}" for value in sensitivity["terminal_growth_values"]],
                )
                st.caption("DCF sensitivity table")
                st.dataframe(sensitivity_frame, width="stretch")
            else:
                st.caption("DCF sensitivity table unavailable")
                st.write(", ".join(sensitivity["missing_fields"]) if sensitivity["missing_fields"] else "Not enough inputs for sensitivity analysis.")

            if valuation.get("warnings") or valuation.get("notes"):
                with st.expander("Valuation warnings and methodology notes", expanded=False):
                    if valuation.get("warnings"):
                        st.markdown("**Warnings**")
                        for warning in valuation["warnings"]:
                            st.write(f"- {warning}")
                    if valuation.get("notes"):
                        st.markdown("**Notes**")
                        for note in valuation["notes"]:
                            st.write(f"- {note}")

            st.markdown("**5. Earnings Summary**")
            st.json(report_payload["earnings_summary"], expanded=False)

            st.markdown("**6. Analyst Estimate Summary**")
            st.json(report_payload["analyst_estimate_summary"], expanded=False)

            st.markdown("**7. Key Risks**")
            if report_payload["key_risks"]:
                for risk in report_payload["key_risks"]:
                    st.write(f"- {risk}")
            else:
                st.write("No explicit risks were assembled from the currently available inputs.")

            st.markdown("**8. Missing-Data Warnings**")
            if report_payload["missing_data_warnings"]:
                for warning in report_payload["missing_data_warnings"]:
                    st.write(f"- {warning}")
            else:
                st.write("No explicit missing-data warnings were assembled from the current inputs.")

            st.markdown("**9. Source / Freshness Notes**")
            st.dataframe(pd.DataFrame(report_payload["data_freshness"]), width="stretch", hide_index=True)

            if report_payload.get("screener_context"):
                with st.expander("Existing screener context", expanded=False):
                    st.json(report_payload["screener_context"], expanded=False)

            payload = export_stock_report_json(report)
            st.download_button(
                "Download Stock Report JSON",
                data=payload,
                file_name=f"{ticker.lower()}_stock_report.json",
                mime="application/json",
            )


st.set_page_config(page_title="Stock Purpose Screener", layout="wide")
st.title("Stock Purpose Screener")
st.caption("Research-oriented dashboard only. No direct buy/sell instructions, no broker integration, and no auto-trading.")

page = st.sidebar.radio("Pages", list(PAGE_TO_FILE.keys()))
selected_file = OUTPUTS_DIR / PAGE_TO_FILE[page]
frame, message = load_output(selected_file)

st.subheader(page)

if message and frame is None:
    st.info(message)
    st.stop()

if message and frame is not None:
    st.info(message)

if selected_file.name not in PIPELINE_MANAGED_FILES:
    st.info(
        f"`{selected_file.name}` is not refreshed by `python -m src.report_generator` in the current pipeline. "
        "This page is intentionally not rendered from legacy output so stale data is not mistaken for a fresh run."
    )
    st.stop()

if frame is None:
    st.stop()

warning_rows = find_warning_rows(frame)
if not warning_rows.empty:
    present_states: list[str] = []
    for state in ("Broken", "Extended / No Chase", "Risk Reduce"):
        if warning_rows.astype(str).eq(state).any().any():
            present_states.append(state)
    st.warning(
        "Warnings present in this page: "
        + ", ".join(present_states)
        + ". These are research risk flags, not trading instructions."
    )
    with st.expander("Show warning rows", expanded=False):
        st.dataframe(style_state_columns(warning_rows), width="stretch", hide_index=True)

st.dataframe(style_state_columns(frame), width="stretch", hide_index=True)
render_reasons(frame)
render_supporting_columns(frame)
render_stock_report_beta()
