from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.providers.local_data_catalog import LocalDataCatalog
from src.providers.local_importer import preview_import_merge, validate_imports
from src.monthly_picks import MonthlyPickConfig
from src.paths import path_context
from src.stock_report import build_provider, build_stock_report, export_stock_report_json
from src.universe_builder import SOURCE_PRESETS, summarize_universe_manager


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"
DATA_DIR = BASE_DIR / "data"
PIPELINE_FILES = {
    "purpose_classification.csv": "Purpose Classification",
    "market_direction.csv": "Market Direction",
    "momentum_leaders.csv": "Momentum Leaders",
    "portfolio_review.csv": "Portfolio Review",
    "undervalued_candidates.csv": "Value / Re-rating",
    "final_watchlist.csv": "Final Watchlist",
}
MONTHLY_FILES = {
    "monthly_research_picks.csv": "Monthly Research Picks",
    "monthly_picks_track_record.csv": "Monthly Picks Track Record",
    "monthly_picks_equity_curve.csv": "Monthly Picks Equity Curve",
}
DATA_SOURCE_FILES = {
    "data_source_status.csv": "Data Source Status",
    "data_gap_report.csv": "Data Gap Report",
}
DATA_ONBOARDING_FILES = {
    "ticker_data_coverage.csv": "Ticker Data Coverage",
    "data_onboarding_actions.csv": "Data Onboarding Actions",
}
PRICE_STATUS_FILE = "price_update_status.csv"
TAB_TO_FILE = {
    "Market Direction": "market_direction.csv",
    "Momentum Leaders": "momentum_leaders.csv",
    "Portfolio Review": "portfolio_review.csv",
    "Value / Re-rating": "undervalued_candidates.csv",
    "Final Watchlist": "final_watchlist.csv",
}
STATE_COLORS = {
    "Buyable Area": ("#dcfce7", "#14532d"),
    "Watch": ("#dbeafe", "#1e3a8a"),
    "Setup Forming": ("#fef9c3", "#713f12"),
    "Pullback Add Candidate": ("#e0f2fe", "#075985"),
    "Extended / No Chase": ("#ffedd5", "#9a3412"),
    "Risk Reduce": ("#fee2e2", "#991b1b"),
    "Broken": ("#fecaca", "#7f1d1d"),
    "Review Thesis": ("#fef3c7", "#78350f"),
    "Keep": ("#dcfce7", "#14532d"),
    "Add Candidate": ("#dbeafe", "#1e3a8a"),
    "Hold but Do Not Add": ("#e2e8f0", "#334155"),
    "Avoid": ("#fee2e2", "#991b1b"),
    "Insufficient Data": ("#e2e8f0", "#334155"),
    "Strong Rotation": ("#dcfce7", "#14532d"),
    "Early Rotation": ("#dbeafe", "#1e3a8a"),
    "Overextended": ("#ffedd5", "#9a3412"),
    "Weak": ("#fee2e2", "#991b1b"),
    "Broken / Avoid": ("#fecaca", "#7f1d1d"),
    "Peer Data Unavailable": ("#e2e8f0", "#334155"),
    "Insufficient Peer Data": ("#e2e8f0", "#334155"),
    "valid": ("#dcfce7", "#14532d"),
    "valid_with_warnings": ("#fef9c3", "#713f12"),
    "missing_file": ("#e2e8f0", "#334155"),
    "Available": ("#dcfce7", "#14532d"),
    "Not available": ("#e2e8f0", "#334155"),
    "peer_discount": ("#dcfce7", "#14532d"),
    "peer_premium": ("#ffedd5", "#9a3412"),
    "mixed": ("#e2e8f0", "#334155"),
    "insufficient_peer_data": ("#e2e8f0", "#334155"),
}
BADGE_COLORS = {
    "positive": ("#064e3b", "#d1fae5"),
    "neutral": ("#1f2937", "#e5e7eb"),
    "caution": ("#78350f", "#fef3c7"),
    "negative": ("#7f1d1d", "#fee2e2"),
    "info": ("#1e3a8a", "#dbeafe"),
}
DATA_SOURCE_STATUS_LABELS = {
    "available": "Available",
    "partial": "Partial",
    "missing_file": "Missing local file",
    "source_unavailable": "Source unavailable",
    "manual_only": "Manual input needed",
    "optional_unofficial": "Optional unofficial",
    "not_supported": "Not supported",
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


def load_pipeline_outputs() -> dict[str, tuple[pd.DataFrame | None, str | None]]:
    return {filename: load_output(OUTPUTS_DIR / filename) for filename in PIPELINE_FILES}


def load_data_source_status_tables(
    outputs_dir: Path = OUTPUTS_DIR,
) -> dict[str, tuple[pd.DataFrame | None, str | None]]:
    return {filename: load_output(outputs_dir / filename) for filename in DATA_SOURCE_FILES}


def load_data_onboarding_tables(
    outputs_dir: Path = OUTPUTS_DIR,
) -> dict[str, tuple[pd.DataFrame | None, str | None]]:
    return {filename: load_output(outputs_dir / filename) for filename in DATA_ONBOARDING_FILES}


def load_price_update_status(
    outputs_dir: Path = OUTPUTS_DIR,
) -> tuple[pd.DataFrame | None, str | None]:
    path = outputs_dir / PRICE_STATUS_FILE
    if not path.exists():
        return None, (
            "`price_update_status.csv` has not been generated yet. Run "
            "`python3 -m src.data_update --universe-file data/universe.csv` or `make price-refresh`."
        )
    return load_output(path)


def friendly_data_source_status(value: object) -> str:
    return DATA_SOURCE_STATUS_LABELS.get(format_missing(value, "-"), format_missing(value, "-"))


def summarize_price_update_status(status_frame: pd.DataFrame | None) -> dict[str, int]:
    if status_frame is None or status_frame.empty or "status" not in status_frame.columns:
        return {}
    counts = status_frame["status"].astype(str).str.lower().value_counts()
    return {status: int(count) for status, count in counts.items()}


def summarize_ticker_coverage(coverage: pd.DataFrame | None) -> dict[str, int]:
    if coverage is None or coverage.empty:
        return {
            "usable_price_tickers": 0,
            "dcf_ready_tickers": 0,
            "peer_ready_tickers": 0,
            "optional_only_missing_tickers": 0,
        }

    def count_true(column: str) -> int:
        if column not in coverage.columns:
            return 0
        return int(coverage[column].astype(str).str.lower().isin({"true", "1", "yes"}).sum())

    optional_only = 0
    for _, row in coverage.iterrows():
        required_gaps = [
            format_missing(row.get("missing_required_for_momentum"), ""),
            format_missing(row.get("missing_required_for_dcf"), ""),
            format_missing(row.get("missing_required_for_peer_relative"), ""),
        ]
        has_required_gap = any(value.strip() for value in required_gaps)
        missing_optional = not bool(str(row.get("has_earnings", "")).lower() in {"true", "1", "yes"}) or not bool(
            str(row.get("has_analyst_estimates", "")).lower() in {"true", "1", "yes"}
        )
        if missing_optional and not has_required_gap:
            optional_only += 1

    return {
        "usable_price_tickers": count_true("usable_for_momentum"),
        "dcf_ready_tickers": count_true("dcf_ready"),
        "peer_ready_tickers": count_true("peer_ready"),
        "optional_only_missing_tickers": optional_only,
    }


def is_state_column(name: str) -> bool:
    lowered = name.lower()
    return (
        lowered.endswith("state")
        or lowered.endswith("status")
        or lowered == "classification"
        or lowered in {"setupstatus", "reviewstate", "finalstate", "themestatus", "peer_relative_status"}
    )


def style_frame(frame: pd.DataFrame):
    state_columns = [column for column in frame.columns if is_state_column(column)]
    highlight_columns = [
        column
        for column in frame.columns
        if column in {"FinalState", "SetupStatus", "ReviewState", "ThemeStatus", "PeerRelativeStatus"}
        or "reason" in column.lower()
        or "missing" in column.lower()
    ]

    def color_state(value: object) -> str:
        if pd.isna(value):
            return ""
        style = STATE_COLORS.get(str(value))
        if style is None:
            return ""
        background, foreground = style
        return f"background-color: {background}; color: {foreground}; font-weight: 700"

    def emphasize_text(value: object) -> str:
        if pd.isna(value) or str(value).strip() in {"", "nan"}:
            return ""
        return "font-weight: 600; color: #111827"

    styler = frame.style
    styler = styler.set_properties(**{"background-color": "#ffffff", "color": "#111827"})
    if state_columns:
        styler = styler.map(color_state, subset=state_columns)
    if highlight_columns:
        styler = styler.map(emphasize_text, subset=highlight_columns)
    return styler


def apply_dashboard_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
          --research-bg: #f6f1e8;
          --research-panel: #fffdf8;
          --research-text: #172033;
          --research-muted: #5b6474;
          --research-border: #d8ccbc;
          --research-accent: #0f6b63;
          --research-accent-soft: #d9f3ec;
        }
        .stApp {
          background: radial-gradient(circle at top left, #fff9ed 0, #f6f1e8 34%, #edf3f1 100%);
          color: var(--research-text);
        }
        [data-testid="stSidebar"] {
          background: #efe7da;
          border-right: 1px solid var(--research-border);
        }
        [data-testid="stSidebar"] * {
          color: var(--research-text) !important;
        }
        h1, h2, h3, h4, h5, h6, p, label, span, div {
          color: var(--research-text);
        }
        [data-testid="stMarkdownContainer"] p {
          color: var(--research-muted);
        }
        [data-testid="stMetric"] {
          background: rgba(255, 253, 248, 0.86);
          border: 1px solid var(--research-border);
          border-radius: 14px;
          padding: 0.8rem 0.9rem;
          box-shadow: 0 1px 2px rgba(23,32,51,0.06);
        }
        [data-testid="stMetricLabel"] p {
          color: #485365 !important;
          font-weight: 750;
        }
        [data-testid="stMetricValue"] {
          color: #172033 !important;
        }
        .stTabs [data-baseweb="tab-list"] {
          gap: 0.35rem;
          border-bottom: 1px solid var(--research-border);
        }
        .stTabs [data-baseweb="tab"] {
          background: transparent;
          border-radius: 999px 999px 0 0;
          color: #334155;
          font-weight: 750;
        }
        .stTabs [aria-selected="true"] {
          background: #172033 !important;
          color: #ffffff !important;
        }
        .stTabs [data-baseweb="tab"] p {
          color: inherit !important;
        }
        .stTabs [aria-selected="true"] p {
          color: #ffffff !important;
        }
        div[data-testid="stAlert"] {
          border-radius: 12px;
          border: 1px solid #93c5fd;
          background-color: #eff6ff;
        }
        div[data-testid="stAlert"] * {
          color: #1e3a8a !important;
        }
        div[data-testid="stDataFrame"] {
          border: 1px solid var(--research-border);
          border-radius: 12px;
          overflow: hidden;
          background: #ffffff;
        }
        input, textarea, [data-baseweb="select"] > div {
          background: #ffffff !important;
          color: #172033 !important;
          border-color: var(--research-border) !important;
        }
        code {
          color: #0f6b63 !important;
          background: #eaf7f3 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_missing(value: object, fallback: str = "Not available") -> str:
    if value is None:
        return fallback
    try:
        if pd.isna(value):
            return fallback
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "<na>"}:
        return fallback
    return text


def format_value(value: object, fallback: str = "Not available") -> str:
    text = format_missing(value, fallback=fallback)
    if text == fallback:
        return text
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return text
    if abs(float(number)) >= 1_000_000:
        return f"{float(number) / 1_000_000:.1f}M"
    if abs(float(number)) >= 1_000:
        return f"{float(number):,.0f}"
    return f"{float(number):.2f}".rstrip("0").rstrip(".")


def format_date_short(value: object, fallback: str = "Not available") -> str:
    text = format_missing(value, fallback=fallback)
    if text == fallback:
        return fallback
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return text
    return parsed.strftime("%Y-%m-%d")


def format_percent(value: object, fallback: str = "Not enough history") -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return fallback
    return f"{float(number) * 100:.1f}%"


def _badge(text: object, tone: str = "neutral") -> str:
    foreground, background = BADGE_COLORS.get(tone, BADGE_COLORS["neutral"])
    label = format_missing(text)
    return (
        f"<span style='display:inline-block;padding:0.18rem 0.48rem;border-radius:0.45rem;"
        f"font-size:0.78rem;font-weight:700;color:{foreground};background:{background};"
        f"border:1px solid {foreground}22;'>{label}</span>"
    )


def status_badge(status: object) -> str:
    text = format_missing(status)
    lowered = text.lower()
    if any(keyword in lowered for keyword in ("broken", "avoid", "risk reduce")):
        return _badge(text, "negative")
    if any(keyword in lowered for keyword in ("extended", "review", "insufficient")):
        return _badge(text, "caution")
    if any(keyword in lowered for keyword in ("watch", "setup", "candidate", "rotation", "keep")):
        return _badge(text, "positive")
    return _badge(text, "neutral")


def score_badge(score: object) -> str:
    number = pd.to_numeric(pd.Series([score]), errors="coerce").iloc[0]
    if pd.isna(number):
        return _badge("Not available", "neutral")
    tone = "positive" if float(number) >= 75 else "info" if float(number) >= 55 else "caution" if float(number) >= 35 else "negative"
    return _badge(f"{float(number):.1f}", tone)


def _translated_missing_item(item: str) -> str:
    lowered = item.lower()
    if "fundamentals unavailable" in lowered:
        return "Needs SEC enrichment"
    if "peer" in lowered:
        return "Needs peers.csv"
    if "earnings" in lowered:
        return "Needs earnings.csv"
    if "analyst" in lowered:
        return "Needs analyst_estimates.csv"
    if "return" in lowered or "price history" in lowered:
        return "Not enough price history"
    return item.strip()


def summarize_missing_fields(value: object, max_items: int = 5) -> str:
    text = format_missing(value, fallback="No explicit missing-data warnings")
    if text == "No explicit missing-data warnings":
        return text
    items = [_translated_missing_item(item.strip()) for item in text.split(",") if item.strip()]
    if not items:
        return "No explicit missing-data warnings"
    unique_items = list(dict.fromkeys(items))
    if len(unique_items) <= max_items:
        return ", ".join(unique_items)
    shown = ", ".join(unique_items[:max_items])
    return f"{shown}, +{len(unique_items) - max_items} more"


def missing_data_notice(value: object) -> str:
    text = summarize_missing_fields(value)
    if text == "No explicit missing-data warnings":
        return _badge(text, "positive")
    return _badge(text, "caution")


def compact_reason(value: object, max_sentences: int = 2, max_chars: int = 260) -> str:
    text = format_missing(value)
    if text == "Not available":
        return text
    sentences = [part.strip() for part in text.replace("\n", " ").split(". ") if part.strip()]
    compact = ". ".join(sentences[:max_sentences])
    if compact and not compact.endswith("."):
        compact += "."
    if len(compact) > max_chars:
        compact = compact[: max_chars - 1].rstrip() + "..."
    return compact


def monthly_pick_availability_message(candidate_count: int, top_n: int) -> str:
    if candidate_count >= top_n:
        return f"{top_n} of {top_n} research candidates available."
    if candidate_count == 0:
        return f"0 of {top_n} research candidates available. Current filters found no qualifying local candidates."
    return (
        f"{candidate_count} of {top_n} research candidates available. Conservative filters left the rest unfilled; "
        "weak or ignored names are not forced into the list."
    )


def track_record_status_message(track_frame: pd.DataFrame | None, equity_frame: pd.DataFrame | None) -> str:
    if equity_frame is not None and not equity_frame.empty:
        return "Local equity curve available."
    if track_frame is not None and not track_frame.empty and "Notes" in track_frame.columns:
        notes = "; ".join(
            str(note)
            for note in track_frame["Notes"].dropna().astype(str).unique().tolist()
            if note and note.lower() != "nan"
        )
        if notes:
            return f"Insufficient local history for an equity curve: {notes}"
    return (
        "Insufficient local history for an equity curve. Add more dated local prices for picks and the benchmark "
        "so the app can calculate month-end selections and next-month forward returns."
    )


def joined_notes(value: object) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value if str(item).strip()) or "-"
    return format_missing(value, "-")


def ticker_coverage_display_frame(coverage: pd.DataFrame) -> pd.DataFrame:
    if coverage.empty:
        return coverage
    display = coverage.copy()
    display["Status"] = display["validation_status"].map(format_missing)
    display["TickerData"] = display["ticker_present"].map(lambda value: "Available" if bool(value) else "Not available")
    display["Rows"] = display["row_count_for_ticker"].map(lambda value: format_value(value, fallback="0"))
    display["Latest"] = display["latest_data_timestamp"].map(lambda value: format_date_short(value, fallback="Not available"))
    display["Notes"] = display["notes"].map(joined_notes)
    return display[["dataset_name", "Status", "TickerData", "Rows", "Latest", "Notes"]].rename(
        columns={"dataset_name": "Dataset"}
    )


def readable_card(title: str, body: str, footer: str = "") -> None:
    footer_html = f"<div style='margin-top:0.65rem;color:#334155;font-size:0.86rem;'>{footer}</div>" if footer else ""
    st.markdown(
        f"""
        <div style="border:1px solid #94a3b8;border-left:5px solid #2563eb;border-radius:10px;padding:0.95rem 1rem;background:#ffffff;margin-bottom:0.85rem;box-shadow:0 1px 2px rgba(15,23,42,0.08);">
          <div style="font-size:0.78rem;text-transform:uppercase;letter-spacing:0.02em;color:#334155;font-weight:800;">{html.escape(title)}</div>
          <div style="margin-top:0.35rem;color:#0f172a;font-size:1rem;line-height:1.45;">{body}</div>
          {footer_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def clean_display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    def clean_cell(value: object) -> str:
        if isinstance(value, list):
            return ", ".join(str(item) for item in value if str(item).strip()) or "Not available"
        if isinstance(value, dict):
            return ", ".join(f"{key}: {val}" for key, val in value.items()) or "Not available"
        return format_missing(value)

    return frame.copy().map(clean_cell)


def display_with_summaries(frame: pd.DataFrame) -> pd.DataFrame:
    display = clean_display_frame(frame)
    if "Reason" in frame.columns:
        display["ReasonSummary"] = frame["Reason"].map(compact_reason)
    if "RankReason" in frame.columns:
        display["RankReasonSummary"] = frame["RankReason"].map(compact_reason)
    if "MissingDataFields" in frame.columns:
        display["DataGaps"] = frame["MissingDataFields"].map(summarize_missing_fields)
    return display


def reorder_columns(frame: pd.DataFrame) -> pd.DataFrame:
    priority = [
        "Ticker",
        "Theme",
        "SectorETF",
        "FinalState",
        "SetupStatus",
        "ReviewState",
        "ThemeStatus",
        "FinalValueCategory",
        "PeerRelativeStatus",
        "RelativeOpportunityScore",
        "WatchlistScore",
        "Reason",
        "MissingDataFields",
    ]
    ordered = [column for column in priority if column in frame.columns]
    remaining = [column for column in frame.columns if column not in ordered]
    return frame[ordered + remaining].copy()


def compact_table_columns(frame: pd.DataFrame) -> list[str]:
    priority = [
        "Ticker",
        "Theme",
        "SectorETF",
        "FinalState",
        "SetupStatus",
        "ReviewState",
        "ThemeStatus",
        "FinalValueCategory",
        "PeerRelativeStatus",
        "WatchlistScore",
        "WatchlistRank",
        "RankReasonSummary",
        "ReasonSummary",
        "DataGaps",
        "Return1M",
        "Return3M",
        "Return6M",
        "RSPercentile",
        "QualityScore",
        "ValuationScore",
        "ValueTrapRiskScore",
        "ConcentrationRisk",
    ]
    selected = [column for column in priority if column in frame.columns]
    if len(selected) < 6:
        selected.extend(column for column in frame.columns if column not in selected and column not in {"Reason", "RankReason", "MissingDataFields"})
    return selected[:14]


def filter_frame(frame: pd.DataFrame, key: str) -> pd.DataFrame:
    filtered = frame.copy()
    with st.container():
        search_value = st.text_input(f"Search {key}", key=f"{key}-search")
        if search_value:
            mask = filtered.astype(str).apply(
                lambda row: row.str.contains(search_value, case=False, na=False).any(),
                axis=1,
            )
            filtered = filtered.loc[mask].copy()

        status_columns = [column for column in filtered.columns if is_state_column(column)]
        status_column = status_columns[0] if status_columns else None
        if status_column:
            statuses = sorted(value for value in filtered[status_column].dropna().astype(str).unique().tolist() if value)
            selected_statuses = st.multiselect(
                f"Filter {key} by {status_column}",
                options=statuses,
                default=[],
                key=f"{key}-status",
            )
            if selected_statuses:
                filtered = filtered.loc[filtered[status_column].astype(str).isin(selected_statuses)].copy()

        if "Theme" in filtered.columns:
            themes = sorted(value for value in filtered["Theme"].dropna().astype(str).unique().tolist() if value)
            selected_themes = st.multiselect(f"Filter {key} by Theme", options=themes, default=[], key=f"{key}-theme")
            if selected_themes:
                filtered = filtered.loc[filtered["Theme"].astype(str).isin(selected_themes)].copy()

        if "SectorETF" in filtered.columns:
            sectors = sorted(value for value in filtered["SectorETF"].dropna().astype(str).unique().tolist() if value)
            selected_sectors = st.multiselect(
                f"Filter {key} by Sector ETF",
                options=sectors,
                default=[],
                key=f"{key}-sector",
            )
            if selected_sectors:
                filtered = filtered.loc[filtered["SectorETF"].astype(str).isin(selected_sectors)].copy()
    return filtered


def render_table(frame: pd.DataFrame, key: str, show_reason_details: bool) -> None:
    filtered = filter_frame(reorder_columns(frame), key)
    display_frame = display_with_summaries(filtered)
    compact_columns = compact_table_columns(display_frame)
    st.caption("Showing the most useful columns first. Open the detail expanders below for full reasons, missing fields, and raw columns.")
    st.dataframe(style_frame(display_frame[compact_columns]), width="stretch", hide_index=True)

    with st.expander(f"{key} full table", expanded=False):
        st.dataframe(style_frame(clean_display_frame(filtered)), width="stretch", hide_index=True)

    if show_reason_details:
        reason_columns = [column for column in filtered.columns if "reason" in column.lower()]
        if reason_columns:
            with st.expander(f"{key} reasons", expanded=False):
                detail_columns = [column for column in filtered.columns if column in {"Ticker", "Theme", "FinalState", "SetupStatus", "ReviewState"} or column in reason_columns]
                st.dataframe(clean_display_frame(filtered[detail_columns]), width="stretch", hide_index=True)

    support_columns = [
        column
        for column in filtered.columns
        if any(keyword in column.lower() for keyword in ("missing", "conflict", "risk"))
    ]
    if support_columns:
        with st.expander(f"{key} supporting details", expanded=False):
            detail_columns = [column for column in filtered.columns if column in {"Ticker", "Theme", "FinalState", "SetupStatus", "ReviewState", "ThemeStatus"} or column in support_columns]
            st.dataframe(clean_display_frame(filtered[detail_columns]), width="stretch", hide_index=True)


def get_local_provider():
    try:
        return build_provider("local", base_dir=BASE_DIR)
    except Exception:  # pragma: no cover - defensive dashboard path
        return None


def _count_missing_warning_rows(output_frames: dict[str, tuple[pd.DataFrame | None, str | None]]) -> int:
    identifiers: set[str] = set()
    for filename, (frame, _message) in output_frames.items():
        if frame is None or frame.empty:
            continue
        missing_columns = [column for column in frame.columns if "missing" in column.lower()]
        if not missing_columns:
            continue
        identifier_column = "Ticker" if "Ticker" in frame.columns else "Theme" if "Theme" in frame.columns else None
        if identifier_column is None:
            continue
        mask = pd.Series(False, index=frame.index)
        for column in missing_columns:
            values = frame[column].fillna("").astype(str).str.strip()
            mask = mask | values.ne("") & values.ne("nan")
        identifiers.update(frame.loc[mask, identifier_column].astype(str).tolist())
    return len({value for value in identifiers if value})


def _latest_local_price_date(catalog: LocalDataCatalog) -> str:
    metadata = catalog.dataset_metadata("prices")
    return format_date_short(metadata.latest_data_timestamp, fallback="Unavailable")


def _monthly_top_n() -> int:
    try:
        return MonthlyPickConfig.from_yaml(BASE_DIR / "config.yaml").top_n
    except Exception:  # pragma: no cover - dashboard fallback
        return 5


def _fundamentals_coverage_count(catalog: LocalDataCatalog) -> int:
    frame = catalog.load_dataframe("fundamentals")
    if frame is None or frame.empty or "ticker" not in frame.columns:
        return 0
    return int(frame["ticker"].dropna().nunique())


def _dcf_ready_count(catalog: LocalDataCatalog) -> int:
    frame = catalog.load_dataframe("fundamentals")
    if frame is None or frame.empty:
        return 0
    empty_series = pd.Series(index=frame.index, dtype=float)
    fcf_ready = frame.get("free_cash_flow", empty_series).notna() | frame.get("fcf", empty_series).notna()
    revenue_margin_ready = frame.get("revenue", empty_series).notna() & frame.get("fcf_margin", empty_series).notna()
    if "ticker" not in frame.columns:
        return 0
    return int(frame.loc[fcf_ready | revenue_margin_ready, "ticker"].dropna().nunique())


def _peer_ready_count(catalog: LocalDataCatalog) -> int:
    peers = catalog.load_dataframe("peers")
    fundamentals = catalog.load_dataframe("fundamentals")
    if peers is None or peers.empty or fundamentals is None or fundamentals.empty:
        return 0
    peer_column = "peer_ticker" if "peer_ticker" in peers.columns else None
    if "ticker" not in peers.columns or peer_column is None or "ticker" not in fundamentals.columns:
        return 0
    fundamentals_set = set(fundamentals["ticker"].dropna().astype(str))
    ready_subjects = set()
    for _, row in peers.iterrows():
        subject = str(row.get("ticker", "")).upper().strip()
        peer = str(row.get(peer_column, "")).upper().strip()
        if subject and peer and peer in fundamentals_set and subject != peer:
            ready_subjects.add(subject)
    return len(ready_subjects)


def render_overview(output_frames: dict[str, tuple[pd.DataFrame | None, str | None]], catalog: LocalDataCatalog, universe_summary: dict[str, Any]) -> None:
    holdings = catalog.load_dataframe("holdings")
    final_watchlist_frame, _ = output_frames.get("final_watchlist.csv", (None, None))
    monthly_file_count = sum(1 for filename in MONTHLY_FILES if (OUTPUTS_DIR / filename).exists())
    output_file_count = sum(1 for frame, _message in output_frames.values() if frame is not None) + monthly_file_count
    missing_warning_count = _count_missing_warning_rows(output_frames)
    current_universe = universe_summary["current_universe"]

    metrics_top = st.columns(5)
    metrics_top[0].metric("Universe Tickers", current_universe["row_count"])
    metrics_top[1].metric("Holdings", 0 if holdings is None or holdings.empty else len(holdings))
    metrics_top[2].metric("Output Files Present", output_file_count)
    metrics_top[3].metric("Final Watchlist Candidates", 0 if final_watchlist_frame is None else len(final_watchlist_frame))
    metrics_top[4].metric("Missing-Data Warning Names", missing_warning_count)

    metrics_bottom = st.columns(4)
    metrics_bottom[0].metric("Latest Local Price Date", _latest_local_price_date(catalog))
    metrics_bottom[1].metric("Fundamentals Coverage", _fundamentals_coverage_count(catalog))
    metrics_bottom[2].metric("DCF-Ready Count", _dcf_ready_count(catalog))
    metrics_bottom[3].metric("Peer-Ready Count", _peer_ready_count(catalog))

    st.markdown("### Output Snapshot")
    output_rows = []
    for filename, label in PIPELINE_FILES.items():
        frame, message = output_frames[filename]
        output_rows.append(
            {
                "Output": label,
                "File": filename,
                "Present": frame is not None,
                "Rows": 0 if frame is None else len(frame),
                "Message": message or "",
            }
        )
    for filename, label in MONTHLY_FILES.items():
        frame, message = load_output(OUTPUTS_DIR / filename)
        output_rows.append(
            {
                "Output": label,
                "File": filename,
                "Present": frame is not None,
                "Rows": 0 if frame is None else len(frame),
                "Message": message or "",
            }
        )
    st.dataframe(pd.DataFrame(output_rows), width="stretch", hide_index=True)

    if final_watchlist_frame is not None and not final_watchlist_frame.empty:
        st.markdown("### Final Watchlist Snapshot")
        snapshot_columns = [column for column in ["Ticker", "FinalState", "SetupStatus", "FinalValueCategory", "WatchlistRank", "RankReason", "Reason"] if column in final_watchlist_frame.columns]
        st.dataframe(clean_display_frame(final_watchlist_frame[snapshot_columns]), width="stretch", hide_index=True)


def render_monthly_picks(catalog: LocalDataCatalog) -> None:
    st.subheader("Monthly Picks")
    top_n = _monthly_top_n()
    st.caption(f"Up to {top_n} local research candidates. These are candidate rankings, not trade instructions.")
    picks_frame, picks_message = load_output(OUTPUTS_DIR / "monthly_research_picks.csv")
    track_frame, _track_message = load_output(OUTPUTS_DIR / "monthly_picks_track_record.csv")
    equity_frame, _equity_message = load_output(OUTPUTS_DIR / "monthly_picks_equity_curve.csv")
    latest_price = _latest_local_price_date(catalog)
    universe = catalog.load_dataframe("universe")
    candidate_count = 0 if picks_frame is None else len(picks_frame)

    hero_cols = st.columns(5)
    hero_cols[0].metric("Research Candidates", f"{candidate_count} of {top_n}")
    hero_cols[1].metric("Current Month", "Not generated" if picks_frame is None or picks_frame.empty else picks_frame.iloc[0].get("Month", "Not available"))
    hero_cols[2].metric("Benchmark", "SPY")
    hero_cols[3].metric("Universe Size", 0 if universe is None or universe.empty else len(universe))
    hero_cols[4].metric("Latest Price Date", latest_price)

    if picks_frame is None:
        st.info(picks_message or "Run `python3 -m src.monthly_picks --generate --top-n 5` to create monthly research candidates.")
    elif picks_frame.empty:
        st.info("Monthly picks output exists, but no candidates were generated from the current local outputs.")
    else:
        st.info(monthly_pick_availability_message(candidate_count, top_n))
        st.markdown("### Research Candidates")
        for _, row in picks_frame.sort_values(["Rank", "CompositeScore"], ascending=[True, False]).iterrows():
            ticker = html.escape(format_missing(row.get("Ticker")))
            rank = html.escape(format_value(row.get("Rank")))
            theme = html.escape(format_missing(row.get("Theme"), "Unclassified"))
            sector = html.escape(format_missing(row.get("Sector"), "No sector"))
            reason = html.escape(compact_reason(row.get("Reason")))
            body = (
                f"<div style='display:flex;gap:0.5rem;flex-wrap:wrap;margin-bottom:0.55rem;'>"
                f"{score_badge(row.get('CompositeScore'))}"
                f"{status_badge(row.get('SetupStatus'))}"
                f"{status_badge(row.get('FinalState'))}"
                f"</div>"
                f"<strong>{ticker}</strong> "
                f"<span style='color:#334155;'>Rank {rank} · {theme} · {sector}</span>"
                f"<p style='margin:0.55rem 0 0 0;'>{reason}</p>"
                f"<p style='margin:0.35rem 0 0 0;color:#475569;font-size:0.88rem;'>Full transparent reason is available in the table below.</p>"
            )
            readable_card(
                title="Research Candidate",
                body=body,
                footer=f"Data coverage: {missing_data_notice(row.get('MissingDataFields'))}",
            )

        with st.expander("Monthly candidates table", expanded=False):
            display_columns = [
                column
                for column in [
                    "Rank",
                    "Ticker",
                    "Theme",
                    "Sector",
                    "CompositeScore",
                    "MomentumScore",
                    "QualityScore",
                    "ValuationContextScore",
                    "RiskPenalty",
                    "LiquidityScore",
                    "MAStackStatus",
                    "RSI14",
                    "Reason",
                    "MissingDataFields",
                ]
                if column in picks_frame.columns
            ]
            st.dataframe(clean_display_frame(picks_frame[display_columns]), width="stretch", hide_index=True)

    st.markdown("### Track Record")
    if equity_frame is not None and not equity_frame.empty and {"Month", "PicksEquity", "BenchmarkEquity"}.issubset(equity_frame.columns):
        chart_frame = equity_frame.set_index("Month")[["PicksEquity", "BenchmarkEquity"]]
        st.line_chart(chart_frame)
    else:
        st.info(track_record_status_message(track_frame, equity_frame))
    if track_frame is not None and not track_frame.empty:
        st.dataframe(clean_display_frame(track_frame), width="stretch", hide_index=True)
    else:
        st.info("Run `python3 -m src.track_record --monthly-picks` to create the local track-record files.")

    st.markdown("### Archive")
    if track_frame is not None and not track_frame.empty:
        archive_columns = [column for column in ["Month", "Picks", "AveragePickReturn", "BenchmarkReturn", "ExcessReturn", "Notes"] if column in track_frame.columns]
        st.dataframe(clean_display_frame(track_frame[archive_columns]), width="stretch", hide_index=True)
    else:
        st.info("No local monthly archive is available yet.")

    with st.expander("Methodology", expanded=False):
        st.write("Monthly rankings use local screener outputs, local price history, optional local fundamentals, and transparent score components.")
        st.write("Missing inputs reduce confidence and remain visible in the output.")
        st.write("Track-record files are calculated only from local historical price data; insufficient history is shown explicitly.")


def render_output_tab(title: str, output_frames: dict[str, tuple[pd.DataFrame | None, str | None]], show_reason_details: bool) -> None:
    filename = TAB_TO_FILE[title]
    frame, message = output_frames[filename]
    st.subheader(title)
    if message and frame is None:
        st.info(message)
        return
    if message and frame is not None:
        st.info(message)
    if frame is None:
        return
    render_table(frame, title.lower().replace(" ", "-"), show_reason_details)


def render_stock_report_beta(provider, show_raw_json: bool) -> None:
    st.subheader("Stock Report (Beta)")
    st.caption(
        "Structured research report workflow. Local CSV-backed data is the default. "
        "Optional yfinance mode stays off by default and is labeled unofficial / research-grade."
    )
    local_tickers = provider.list_local_tickers() if provider is not None and hasattr(provider, "list_local_tickers") else []
    selection_cols = st.columns([2, 2, 1])
    selected = selection_cols[0].selectbox("Local ticker", ["Custom"] + local_tickers if local_tickers else ["Custom"], index=1 if local_tickers else 0)
    manual_ticker = selection_cols[1].text_input("Manual ticker", value="" if selected != "Custom" else "AAPL")
    use_yfinance = selection_cols[2].checkbox("Use yfinance", value=False, help="Unofficial / research-grade. Leave off for the CSV-first path.")
    ticker = (manual_ticker if selected == "Custom" else selected).strip().upper()
    provider_name = "yfinance" if use_yfinance else "local"

    if provider is not None and ticker:
        coverage = pd.DataFrame(provider.get_ticker_dataset_coverage(ticker))
        st.caption("Local dataset coverage for the selected ticker")
        st.dataframe(style_frame(clean_display_frame(ticker_coverage_display_frame(coverage))), width="stretch", hide_index=True)
        with st.expander("Full local coverage details", expanded=False):
            st.dataframe(clean_display_frame(coverage), width="stretch", hide_index=True)
        peer_summary = provider.get_peer_summary(ticker)
        readiness_cols = st.columns(4)
        readiness_cols[0].metric("Peer Dataset", "Present" if peer_summary["peer_dataset_present"] else "Missing")
        readiness_cols[1].metric("Peer Count", peer_summary["peer_count"])
        readiness_cols[2].metric("Peer Fundamentals", peer_summary["peer_fundamentals_available"])
        readiness_cols[3].metric("Peer Market Context", peer_summary["peer_market_context_available"])

    if st.button("Generate Stock Report", key="stock-report-beta-button"):
        if not ticker:
            st.warning("Enter a ticker to generate a stock report.")
        else:
            try:
                chosen_provider = build_provider(provider_name, base_dir=BASE_DIR)
                report = build_stock_report(ticker, chosen_provider)
                st.session_state["stock_report_beta_payload"] = report.to_dict()
                st.session_state["stock_report_beta_download"] = export_stock_report_json(report)
                st.session_state["stock_report_beta_ticker"] = ticker
                st.session_state["stock_report_beta_provider"] = provider_name
            except RuntimeError as exc:
                st.error(str(exc))
            except (LookupError, FileNotFoundError, ValueError) as exc:
                st.warning(str(exc))

    report_payload = st.session_state.get("stock_report_beta_payload")
    if not report_payload:
        return

    if st.session_state.get("stock_report_beta_provider") == "yfinance":
        st.info("Using yfinance as an unofficial / research-grade source. Review source/freshness notes carefully.")

    readiness = report_payload.get("valuation_readiness", {})
    readiness_cols = st.columns(4)
    readiness_cols[0].metric("DCF Ready", "Yes" if readiness.get("dcf_ready") else "No")
    readiness_cols[1].metric("Peer Ready", "Yes" if readiness.get("peer_ready") else "No")
    readiness_cols[2].metric("Earnings Available", "Yes" if readiness.get("earnings_available") else "No")
    readiness_cols[3].metric("Analyst Estimates", "Yes" if readiness.get("analyst_estimates_available") else "No")

    price = report_payload["price_snapshot"]
    performance = report_payload["performance"]
    financials = report_payload["financial_summary"]
    valuation = report_payload["valuation_snapshot"]
    relative = valuation["relative_valuation"]

    section_a, section_b = st.columns(2)
    with section_a:
        st.markdown("#### Price")
        price_metrics = st.columns(3)
        price_metrics[0].metric("Price", "n/a" if price["price"] is None else f"{price['price']:.2f}")
        price_metrics[1].metric("Previous Close", "n/a" if price["previous_close"] is None else f"{price['previous_close']:.2f}")
        price_metrics[2].metric("Volume", "n/a" if price["volume"] is None else f"{int(price['volume']):,}")
        with st.expander("Price detail", expanded=False):
            st.json(price, expanded=False)

        st.markdown("#### Financials")
        financial_columns = [
            "revenue",
            "revenue_growth",
            "eps",
            "operating_margin",
            "profit_margin",
            "free_cash_flow",
            "fcf_margin",
            "cash",
            "debt",
            "shares_outstanding",
        ]
        financial_frame = pd.DataFrame(
            [
                {"Field": column, "Value": format_value(financials.get(column))}
                for column in financial_columns
            ]
        )
        st.dataframe(clean_display_frame(financial_frame), width="stretch", hide_index=True)

        st.markdown("#### Earnings / Analyst Estimates")
        earnings_col, estimates_col = st.columns(2)
        with earnings_col:
            st.caption("Earnings")
            st.json(report_payload["earnings_summary"], expanded=False)
        with estimates_col:
            st.caption("Analyst estimates")
            st.json(report_payload["analyst_estimate_summary"], expanded=False)

    with section_b:
        st.markdown("#### Performance")
        perf_metrics = st.columns(3)
        perf_metrics[0].metric("1M", "n/a" if performance["one_month"] is None else f"{performance['one_month'] * 100:.1f}%")
        perf_metrics[1].metric("3M", "n/a" if performance["three_month"] is None else f"{performance['three_month'] * 100:.1f}%")
        perf_metrics[2].metric("1Y", "n/a" if performance["one_year"] is None else f"{performance['one_year'] * 100:.1f}%")

        st.markdown("#### Valuation")
        st.write(f"Status: `{valuation['status']}`")
        st.write(f"Coverage: `{valuation.get('coverage', 'n/a')}`")
        base_dcf = valuation["dcf_result"]
        if base_dcf.get("fair_value_per_share") is not None:
            st.metric("Base Fair Value / Share", f"{base_dcf['fair_value_per_share']:.2f}")
        else:
            st.info("Per-share DCF output is unavailable with the current inputs.")

        scenario_rows = []
        for scenario in valuation.get("scenarios", []):
            result = scenario["dcf_result"]
            scenario_rows.append(
                {
                    "Scenario": scenario["name"],
                    "Status": result["status"],
                    "RevenueGrowth": scenario["assumptions"]["revenue_growth"],
                    "FCFMargin": scenario["assumptions"]["fcf_margin"],
                    "WACC": scenario["assumptions"]["wacc"],
                    "TerminalGrowth": scenario["assumptions"]["terminal_growth"],
                    "FairValuePerShare": result["fair_value_per_share"],
                }
            )
        if scenario_rows:
            st.dataframe(pd.DataFrame(scenario_rows), width="stretch", hide_index=True)

        st.markdown("#### Peer-Relative Valuation")
        st.write(f"Status: `{relative['status']}`")
        st.write(f"Peer-relative status: `{relative.get('peer_relative_status', 'insufficient_peer_data')}`")
        if relative.get("relative_opportunity_score") is not None:
            st.metric("Relative Opportunity Score", f"{relative['relative_opportunity_score']:.1f}")
        comparison_rows = []
        metric_labels = {"pe": "P/E", "ps": "P/S", "p_fcf": "P/FCF", "ev_ebitda": "EV/EBITDA"}
        for metric_key, label in metric_labels.items():
            subject = relative.get("subject_multiples", {}).get(metric_key)
            peer_median = relative.get("peer_median_multiples", {}).get(metric_key)
            discount = relative.get("relative_discount_premium_by_metric", {}).get(metric_key)
            if subject is None and peer_median is None and discount is None:
                continue
            comparison_rows.append(
                {
                    "Metric": label,
                    "Subject": subject,
                    "PeerMedian": peer_median,
                    "DiscountPremiumPct": None if discount is None else discount * 100.0,
                }
            )
        if comparison_rows:
            st.dataframe(pd.DataFrame(comparison_rows), width="stretch", hide_index=True)

    st.markdown("#### Missing Data")
    if report_payload["missing_data_warnings"]:
        for warning in report_payload["missing_data_warnings"]:
            st.write(f"- {warning}")
    else:
        st.write("No explicit missing-data warnings were assembled from the current inputs.")

    st.markdown("#### Source / Freshness")
    st.dataframe(pd.DataFrame(report_payload["data_freshness"]), width="stretch", hide_index=True)

    sensitivity = valuation["sensitivity_table"]
    if sensitivity["status"] == "calculated" and sensitivity["fair_value_grid"]:
        with st.expander("DCF sensitivity table", expanded=False):
            sensitivity_frame = pd.DataFrame(
                sensitivity["fair_value_grid"],
                index=[f"WACC {value:.1%}" for value in sensitivity["wacc_values"]],
                columns=[f"TG {value:.1%}" for value in sensitivity["terminal_growth_values"]],
            )
            st.dataframe(sensitivity_frame, width="stretch")

    with st.expander("Valuation warnings / methodology notes", expanded=False):
        st.json(
            {
                "warnings": valuation.get("warnings", []),
                "notes": valuation.get("notes", []),
                "peer_missing_data_warnings": relative.get("peer_missing_data_warnings", []),
                "relative_missing_fields": relative.get("missing_fields", []),
            },
            expanded=False,
        )

    if report_payload.get("screener_context"):
        with st.expander("Existing screener context", expanded=False):
            st.json(report_payload["screener_context"], expanded=False)

    if show_raw_json:
        with st.expander("Raw stock report JSON", expanded=False):
            st.json(report_payload, expanded=False)

    st.download_button(
        "Download Stock Report JSON",
        data=st.session_state.get("stock_report_beta_download", "{}"),
        file_name=f"{st.session_state.get('stock_report_beta_ticker', 'stock').lower()}_stock_report.json",
        mime="application/json",
    )


def render_data_health(provider) -> None:
    st.subheader("Data Health")
    if provider is None:
        st.warning("Local provider could not be initialized.")
        return
    validation_rows = pd.DataFrame(provider.get_local_data_validation())
    if not validation_rows.empty:
        missing_optional = validation_rows.loc[
            validation_rows.get("validation_status", pd.Series(dtype=str)).astype(str).eq("missing_file"),
            "name",
        ].astype(str).tolist()
        if missing_optional:
            st.info(
                "Optional local datasets not configured: "
                + ", ".join(missing_optional)
                + ". This is expected until you add those CSVs; reports will show partial coverage instead of fabricating data."
            )
        validation_rows = validation_rows.copy()
        if "validation_warnings" in validation_rows.columns:
            validation_rows["validation_warnings"] = validation_rows["validation_warnings"].map(
                lambda value: "; ".join(value) if isinstance(value, list) else format_missing(value, "-")
            )
        display_columns = [
            column
            for column in [
                "name",
                "validation_status",
                "row_count",
                "latest_data_timestamp",
                "ticker_column",
                "date_column",
                "validation_warnings",
                "file_path",
            ]
            if column in validation_rows.columns
        ]
        st.dataframe(clean_display_frame(validation_rows[display_columns]), width="stretch", hide_index=True)
    else:
        st.info("No local data validation rows are available.")

    st.markdown("### Data Source Availability")
    source_tables = load_data_source_status_tables()
    status_frame, status_message = source_tables["data_source_status.csv"]
    gap_frame, gap_message = source_tables["data_gap_report.csv"]
    if status_frame is None and gap_frame is None:
        st.info(
            "Data source status outputs have not been generated yet. Run "
            "`python3 -m src.data_sources --write-output`."
        )
    else:
        if status_frame is not None and not status_frame.empty:
            display_status = status_frame.copy()
            if "availability_status" in display_status.columns:
                display_status["availability_status"] = display_status["availability_status"].map(friendly_data_source_status)
            columns = [
                column
                for column in [
                    "dataset",
                    "availability_status",
                    "row_count",
                    "source_name",
                    "required_for",
                    "fallback_action",
                    "notes",
                ]
                if column in display_status.columns
            ]
            st.dataframe(clean_display_frame(display_status[columns]), width="stretch", hide_index=True)
        else:
            st.info(status_message or "No data source status rows are available.")
        if gap_frame is not None and not gap_frame.empty:
            with st.expander("Data Gap Report", expanded=False):
                display_gaps = gap_frame.copy()
                if "status" in display_gaps.columns:
                    display_gaps["status"] = display_gaps["status"].map(friendly_data_source_status)
                st.dataframe(clean_display_frame(display_gaps), width="stretch", hide_index=True)
        else:
            st.info(gap_message or "No data gaps were reported.")

    st.markdown("### Price Update Status")
    price_status_frame, price_status_message = load_price_update_status()
    if price_status_frame is None:
        st.info(
            (price_status_message or "Price update status is unavailable.")
            + " If the remote source fails, add verified rows to `data/imports/prices.csv`, then run "
            "`make price-validate`, `make price-preview`, and `make price-apply`."
        )
    else:
        status_counts = summarize_price_update_status(price_status_frame)
        if status_counts:
            statuses = ["fetched", "skipped_fresh", "parse_error", "source_unavailable", "network_error", "no_rows", "failed"]
            metric_cols = st.columns(4)
            metric_cols[0].metric("Fetched", status_counts.get("fetched", 0))
            metric_cols[1].metric("Skipped Fresh", status_counts.get("skipped_fresh", 0))
            metric_cols[2].metric("Parse / Source Errors", sum(status_counts.get(status, 0) for status in statuses[2:]))
            metric_cols[3].metric("Fallback Used", int(price_status_frame.get("fallback_used", pd.Series(dtype=object)).astype(str).str.lower().isin({"true", "1", "yes"}).sum()))
        display_columns = [
            column
            for column in [
                "ticker",
                "status",
                "rows_fetched",
                "rows_merged",
                "error_category",
                "error_message",
                "fallback_used",
                "recommended_action",
            ]
            if column in price_status_frame.columns
        ]
        st.dataframe(clean_display_frame(price_status_frame[display_columns]), width="stretch", hide_index=True)
        st.caption(
            "Manual fallback is CLI-only: fill `data/imports/prices.csv` with verified OHLCV rows, then run "
            "`make price-validate`, `make price-preview`, and `make price-apply`."
        )

    st.markdown("### Ticker Coverage / Onboarding")
    onboarding_tables = load_data_onboarding_tables()
    coverage_frame, coverage_message = onboarding_tables["ticker_data_coverage.csv"]
    actions_frame, actions_message = onboarding_tables["data_onboarding_actions.csv"]
    if coverage_frame is None and actions_frame is None:
        st.info(
            "Ticker coverage outputs have not been generated yet. Run "
            "`python3 -m src.data_onboarding --write-output`."
        )
    else:
        summary = summarize_ticker_coverage(coverage_frame)
        metric_cols = st.columns(4)
        metric_cols[0].metric("Usable Price Data", summary["usable_price_tickers"])
        metric_cols[1].metric("DCF Ready", summary["dcf_ready_tickers"])
        metric_cols[2].metric("Peer Ready", summary["peer_ready_tickers"])
        metric_cols[3].metric("Only Optional Gaps", summary["optional_only_missing_tickers"])

        if coverage_frame is not None and not coverage_frame.empty:
            coverage_columns = [
                column
                for column in [
                    "ticker",
                    "has_prices",
                    "price_history_days",
                    "dcf_ready",
                    "peer_ready",
                    "has_earnings",
                    "has_analyst_estimates",
                    "next_best_action",
                ]
                if column in coverage_frame.columns
            ]
            st.dataframe(clean_display_frame(coverage_frame[coverage_columns]), width="stretch", hide_index=True)
        else:
            st.info(coverage_message or "No ticker coverage rows are available.")

        if actions_frame is not None and not actions_frame.empty:
            st.markdown("#### Top 10 Onboarding Actions")
            top_actions = actions_frame.sort_values(["priority", "ticker", "dataset"], na_position="last").head(10)
            action_columns = [
                column
                for column in ["priority", "ticker", "dataset", "status", "reason", "recommended_action", "target_file"]
                if column in top_actions.columns
            ]
            st.dataframe(clean_display_frame(top_actions[action_columns]), width="stretch", hide_index=True)
        else:
            st.info(actions_message or "No onboarding action rows are available.")

    staged_imports = validate_imports(base_dir=BASE_DIR)
    st.markdown("### Staged Import Status")
    if staged_imports["status"] == "no_staged_files":
        st.info(staged_imports["warnings"][0])
    else:
        staged_rows = []
        for item in staged_imports["files"]:
            staged_rows.append(
                {
                    "File": item["file_name"],
                    "Dataset": item["dataset_name"],
                    "Status": item["validation"]["status"],
                    "Rows": item["validation"]["row_count"],
                    "Warnings": "; ".join(item["validation"]["warnings"]) or "-",
                }
            )
        st.dataframe(pd.DataFrame(staged_rows), width="stretch", hide_index=True)
        preview = preview_import_merge(base_dir=BASE_DIR)
        if preview.get("preview"):
            st.caption("Preview only. Apply remains CLI-only.")
            st.dataframe(pd.DataFrame(preview["preview"]), width="stretch", hide_index=True)

    universe_summary = summarize_universe_manager(BASE_DIR)
    staged_universe = universe_summary["staged_universe"]
    st.markdown("### Staged Universe Import")
    st.json(staged_universe, expanded=False)

    st.markdown("### Runtime Artifact Hygiene")
    st.write("- `data/cache/` is ignored for local cache payloads.")
    st.write("- `data/backups/` is ignored for safe import/apply backups.")
    st.write("- `data/imports/*.csv` is ignored so staged imports stay local until reviewed.")
    st.write("- `outputs/*stock_report.json` is ignored so exported reports do not dirty the repo.")


def render_universe_manager(universe_summary: dict[str, Any]) -> None:
    st.subheader("Universe Manager")
    current = universe_summary["current_universe"]
    staged = universe_summary["staged_universe"]

    metric_cols = st.columns(4)
    metric_cols[0].metric("Current Universe Size", current["row_count"])
    metric_cols[1].metric("Duplicate Tickers", current["duplicate_ticker_count"])
    metric_cols[2].metric("Missing Theme", current["missing_theme_count"] + current["unclassified_theme_count"])
    metric_cols[3].metric("Missing Sector ETF", current["missing_sector_etf_count"])

    st.markdown("### Source Membership Counts")
    membership_rows = [
        {"MembershipFlag": key, "Count": value}
        for key, value in current["membership_counts"].items()
    ]
    if membership_rows:
        st.dataframe(pd.DataFrame(membership_rows), width="stretch", hide_index=True)
    else:
        st.info("No source membership flags are currently present in the canonical universe file.")

    st.markdown("### Available Presets")
    preset_rows = [{"Preset": name, "Sources": ", ".join(sources)} for name, sources in SOURCE_PRESETS.items()]
    st.dataframe(pd.DataFrame(preset_rows), width="stretch", hide_index=True)

    current_frame = pd.DataFrame(current["rows"])
    if not current_frame.empty:
        search = st.text_input("Search current universe", key="universe-manager-search")
        if search:
            current_frame = current_frame.loc[
                current_frame.astype(str).apply(lambda row: row.str.contains(search, case=False, na=False).any(), axis=1)
            ].copy()
        st.dataframe(current_frame, width="stretch", hide_index=True)
    else:
        st.info("The current universe file is empty.")

    st.markdown("### Staged Universe Import Status")
    st.json(staged, expanded=False)

    st.markdown("### CLI Workflow")
    st.code(
        "\n".join(
            [
                "python3 -m src.universe_builder --validate-sources",
                "python3 -m src.universe_builder --preview --preset sp500_smh --max-tickers 50",
                "python3 -m src.universe_builder --write-import --preset sp500_smh --max-tickers 50",
                "python3 -m src.universe_builder --apply-import",
            ]
        ),
        language="bash",
    )


st.set_page_config(page_title="Stock Research Screener", layout="wide")
apply_dashboard_theme()
st.title("Stock Research Screener")
st.caption(
    "Research-only dashboard. No direct buy/sell advice, no broker integration, and no auto-trading. "
    "The local CSV-first workflow remains the default path."
)

with st.sidebar:
    st.header("Controls")
    show_reason_details = st.checkbox("Show reason expanders", value=True)
    show_raw_json = st.checkbox("Show raw report JSON expanders", value=False)
    st.caption("CLI-only applies remain the safest path for staged imports and universe changes.")
    with st.expander("Resolved local paths", expanded=False):
        context = path_context(BASE_DIR, DATA_DIR, OUTPUTS_DIR)
        st.code(
            "\n".join(
                [
                    f"Project root: {context['project_root']}",
                    f"Data dir: {context['data_dir']}",
                    f"Outputs dir: {context['outputs_dir']}",
                ]
            ),
            language="text",
        )

catalog = LocalDataCatalog(BASE_DIR)
provider = get_local_provider()
output_frames = load_pipeline_outputs()
universe_summary = summarize_universe_manager(BASE_DIR)

tabs = st.tabs(
    [
        "Overview",
        "Monthly Picks",
        "Market Direction",
        "Momentum Leaders",
        "Portfolio Review",
        "Value / Re-rating",
        "Final Watchlist",
        "Stock Report Beta",
        "Data Health",
        "Universe Manager",
    ]
)

with tabs[0]:
    render_overview(output_frames, catalog, universe_summary)
with tabs[1]:
    render_monthly_picks(catalog)
with tabs[2]:
    render_output_tab("Market Direction", output_frames, show_reason_details)
with tabs[3]:
    render_output_tab("Momentum Leaders", output_frames, show_reason_details)
with tabs[4]:
    render_output_tab("Portfolio Review", output_frames, show_reason_details)
with tabs[5]:
    render_output_tab("Value / Re-rating", output_frames, show_reason_details)
with tabs[6]:
    render_output_tab("Final Watchlist", output_frames, show_reason_details)
with tabs[7]:
    render_stock_report_beta(provider, show_raw_json)
with tabs[8]:
    render_data_health(provider)
with tabs[9]:
    render_universe_manager(universe_summary)
