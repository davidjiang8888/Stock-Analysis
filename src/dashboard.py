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
RESEARCH_HEALTH_FILES = {
    "data_quality_wizard.csv": "Data Quality Wizard",
    "liquidity_risk.csv": "Liquidity Risk",
    "correlation_risk.csv": "Correlation Risk",
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
    "Research Ready": ("#dcfce7", "#14532d"),
    "Partial Coverage": ("#fef9c3", "#713f12"),
    "Needs Price Data": ("#fee2e2", "#991b1b"),
    "Needs Enrichment": ("#ffedd5", "#9a3412"),
    "Liquid": ("#dcfce7", "#14532d"),
    "Moderate Liquidity": ("#dbeafe", "#1e3a8a"),
    "Thin / Needs Review": ("#ffedd5", "#9a3412"),
    "High Co-movement": ("#fee2e2", "#991b1b"),
    "Moderate Co-movement": ("#fef9c3", "#713f12"),
    "Low Co-movement": ("#dcfce7", "#14532d"),
    "Insufficient Overlap": ("#e2e8f0", "#334155"),
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


def load_research_health_tables(
    outputs_dir: Path = OUTPUTS_DIR,
) -> dict[str, tuple[pd.DataFrame | None, str | None]]:
    return {filename: load_output(outputs_dir / filename) for filename in RESEARCH_HEALTH_FILES}


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


def summarize_research_health_tables(
    data_quality: pd.DataFrame | None,
    liquidity: pd.DataFrame | None,
    correlation: pd.DataFrame | None,
) -> dict[str, int]:
    def count_status(frame: pd.DataFrame | None, column: str, status: str) -> int:
        if frame is None or frame.empty or column not in frame.columns:
            return 0
        return int(frame[column].astype(str).str.casefold().eq(status.casefold()).sum())

    return {
        "research_ready": count_status(data_quality, "ReadinessStatus", "Research Ready"),
        "partial_coverage": count_status(data_quality, "ReadinessStatus", "Partial Coverage"),
        "needs_price_data": count_status(data_quality, "ReadinessStatus", "Needs Price Data"),
        "liquid": count_status(liquidity, "LiquidityStatus", "Liquid"),
        "thin_liquidity": count_status(liquidity, "LiquidityStatus", "Thin / Needs Review"),
        "high_correlation": count_status(correlation, "CorrelationStatus", "High Co-movement"),
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
          --research-bg: #f4f6f1;
          --research-panel: #fffefa;
          --research-ink: #111827;
          --research-text: #1f2937;
          --research-muted: #667085;
          --research-border: #d7ddcf;
          --research-accent: #0f766e;
          --research-accent-strong: #0b3b36;
          --research-accent-soft: #d8f3ed;
          --research-warning: #a16207;
          --research-danger: #b42318;
        }
        .stApp {
          background:
            radial-gradient(circle at top left, rgba(15, 118, 110, 0.15) 0, rgba(244, 246, 241, 0) 32rem),
            linear-gradient(135deg, #fbfaf4 0%, #f3f7f4 42%, #eef5f2 100%);
          color: var(--research-text);
          font-family: "Avenir Next", "SF Pro Display", "Segoe UI", sans-serif;
        }
        [data-testid="stSidebar"] {
          background: #f0f4ee;
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
        .block-container {
          padding-top: 1.6rem;
          max-width: 1500px;
        }
        .app-hero {
          position: relative;
          overflow: hidden;
          border-radius: 28px;
          padding: 1.6rem 1.8rem;
          margin: 0.2rem 0 1.2rem 0;
          background:
            linear-gradient(135deg, rgba(15, 59, 54, 0.96), rgba(15, 118, 110, 0.90)),
            radial-gradient(circle at 78% 8%, rgba(236, 253, 245, 0.34), rgba(236, 253, 245, 0) 18rem);
          border: 1px solid rgba(255, 255, 255, 0.36);
          box-shadow: 0 22px 55px rgba(15, 59, 54, 0.18);
        }
        .hero-kicker {
          color: #b8f5e8;
          font-size: 0.78rem;
          font-weight: 850;
          letter-spacing: 0.14em;
          text-transform: uppercase;
        }
        .hero-title {
          color: #ffffff;
          font-size: clamp(2.0rem, 4vw, 4.1rem);
          line-height: 0.98;
          font-weight: 900;
          letter-spacing: -0.06em;
          margin: 0.38rem 0 0.55rem 0;
        }
        .hero-subtitle {
          color: rgba(255, 255, 255, 0.84);
          max-width: 56rem;
          font-size: 1.02rem;
          line-height: 1.55;
        }
        .hero-pills {
          display: flex;
          flex-wrap: wrap;
          gap: 0.55rem;
          margin-top: 1.05rem;
        }
        .hero-pill {
          color: #ecfdf5;
          background: rgba(255, 255, 255, 0.12);
          border: 1px solid rgba(255, 255, 255, 0.24);
          border-radius: 999px;
          padding: 0.34rem 0.68rem;
          font-size: 0.82rem;
          font-weight: 750;
        }
        .section-title {
          margin: 1.2rem 0 0.55rem 0;
          font-size: 1.28rem;
          font-weight: 900;
          letter-spacing: -0.035em;
          color: var(--research-ink);
        }
        .section-caption {
          margin-top: -0.35rem;
          margin-bottom: 0.8rem;
          color: var(--research-muted);
          font-size: 0.94rem;
        }
        .metric-card-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 0.8rem;
          margin: 0.75rem 0 1.05rem 0;
        }
        .metric-card {
          background: rgba(255, 254, 250, 0.92);
          border: 1px solid var(--research-border);
          border-radius: 18px;
          padding: 0.95rem 1rem;
          box-shadow: 0 10px 28px rgba(17, 24, 39, 0.06);
        }
        .metric-label {
          color: #5b6474;
          font-size: 0.72rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          font-weight: 850;
        }
        .metric-value {
          color: var(--research-ink);
          font-size: 1.65rem;
          font-weight: 900;
          letter-spacing: -0.045em;
          margin-top: 0.2rem;
        }
        .metric-note {
          color: var(--research-muted);
          font-size: 0.82rem;
          margin-top: 0.18rem;
        }
        .action-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
          gap: 0.85rem;
          margin: 0.8rem 0 1rem 0;
        }
        .action-card {
          background: #fffefa;
          border: 1px solid var(--research-border);
          border-left: 6px solid var(--research-accent);
          border-radius: 18px;
          padding: 0.95rem 1rem;
          box-shadow: 0 12px 32px rgba(17, 24, 39, 0.07);
        }
        .action-card.warning { border-left-color: #d97706; }
        .action-card.danger { border-left-color: #dc2626; }
        .action-title {
          color: var(--research-ink);
          font-size: 0.94rem;
          font-weight: 900;
          margin-bottom: 0.32rem;
        }
        .action-body {
          color: var(--research-muted);
          font-size: 0.88rem;
          line-height: 1.4;
        }
        .command-chip {
          display: inline-block;
          margin-top: 0.45rem;
          padding: 0.22rem 0.46rem;
          border-radius: 8px;
          background: #e7f5ef;
          color: #0b3b36;
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 0.76rem;
          font-weight: 800;
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
          flex-wrap: wrap;
          row-gap: 0.25rem;
        }
        .stTabs [data-baseweb="tab"] {
          background: rgba(255, 254, 250, 0.72);
          border: 1px solid var(--research-border);
          border-bottom: 0;
          border-radius: 999px;
          color: #334155;
          font-weight: 800;
          padding: 0.42rem 0.78rem;
        }
        .stTabs [aria-selected="true"] {
          background: #0b3b36 !important;
          color: #ffffff !important;
          border-color: #0b3b36 !important;
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
          background-color: #eef7ff;
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


def render_section_header(title: str, caption: str = "") -> None:
    caption_html = f"<div class='section-caption'>{html.escape(caption)}</div>" if caption else ""
    st.markdown(
        f"<div class='section-title'>{html.escape(title)}</div>{caption_html}",
        unsafe_allow_html=True,
    )


def metric_card_html(label: str, value: object, note: str = "") -> str:
    note_html = f"<div class='metric-note'>{html.escape(note)}</div>" if note else ""
    return (
        "<div class='metric-card'>"
        f"<div class='metric-label'>{html.escape(label)}</div>"
        f"<div class='metric-value'>{html.escape(str(value))}</div>"
        f"{note_html}"
        "</div>"
    )


def render_metric_cards(cards: list[tuple[str, object, str]]) -> None:
    st.markdown(
        "<div class='metric-card-grid'>"
        + "".join(metric_card_html(label, value, note) for label, value, note in cards)
        + "</div>",
        unsafe_allow_html=True,
    )


def action_card_html(title: str, body: str, command: str = "", tone: str = "neutral") -> str:
    tone_class = "warning" if tone == "warning" else "danger" if tone == "danger" else ""
    command_html = f"<div class='command-chip'>{html.escape(command)}</div>" if command else ""
    return (
        f"<div class='action-card {tone_class}'>"
        f"<div class='action-title'>{html.escape(title)}</div>"
        f"<div class='action-body'>{html.escape(body)}</div>"
        f"{command_html}"
        "</div>"
    )


def render_action_cards(cards: list[tuple[str, str, str, str]]) -> None:
    st.markdown(
        "<div class='action-grid'>"
        + "".join(action_card_html(title, body, command, tone) for title, body, command, tone in cards)
        + "</div>",
        unsafe_allow_html=True,
    )


def render_app_header(catalog: LocalDataCatalog, output_frames: dict[str, tuple[pd.DataFrame | None, str | None]]) -> None:
    universe = catalog.load_dataframe("universe")
    tickers = 0 if universe is None or universe.empty else len(universe)
    final_frame, _ = output_frames.get("final_watchlist.csv", (None, None))
    monthly_frame, _ = load_output(OUTPUTS_DIR / "monthly_research_picks.csv")
    final_count = 0 if final_frame is None else len(final_frame)
    monthly_count = 0 if monthly_frame is None else len(monthly_frame)
    latest_price = _latest_local_price_date(catalog)
    st.markdown(
        f"""
        <div class="app-hero">
          <div class="hero-kicker">CSV-first research cockpit</div>
          <div class="hero-title">Stock Research Screener</div>
          <div class="hero-subtitle">
            A local, explainable workflow for market direction, momentum leadership, portfolio review,
            valuation context, monthly research candidates, and data readiness. No trade execution.
          </div>
          <div class="hero-pills">
            <span class="hero-pill">{tickers} universe tickers</span>
            <span class="hero-pill">{final_count} watchlist rows</span>
            <span class="hero-pill">{monthly_count} monthly candidates</span>
            <span class="hero-pill">Latest price: {html.escape(latest_price)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
    footer_html = f"<div style='margin-top:0.72rem;color:#475467;font-size:0.86rem;'>{footer}</div>" if footer else ""
    st.markdown(
        f"""
        <div style="border:1px solid #d7ddcf;border-radius:20px;padding:1.05rem 1.1rem;background:rgba(255,254,250,0.94);margin-bottom:0.85rem;box-shadow:0 14px 34px rgba(17,24,39,0.07);">
          <div style="font-size:0.74rem;text-transform:uppercase;letter-spacing:0.12em;color:#0f766e;font-weight:900;">{html.escape(title)}</div>
          <div style="margin-top:0.45rem;color:#111827;font-size:1rem;line-height:1.46;">{body}</div>
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
    health_tables = load_research_health_tables()
    health_file_count = sum(1 for frame, _message in health_tables.values() if frame is not None)
    output_file_count = sum(1 for frame, _message in output_frames.values() if frame is not None) + monthly_file_count + health_file_count
    missing_warning_count = _count_missing_warning_rows(output_frames)
    current_universe = universe_summary["current_universe"]
    data_quality_frame, _ = health_tables["data_quality_wizard.csv"]
    liquidity_frame, _ = health_tables["liquidity_risk.csv"]
    correlation_frame, _ = health_tables["correlation_risk.csv"]
    health_summary = summarize_research_health_tables(data_quality_frame, liquidity_frame, correlation_frame)

    render_section_header(
        "Command Center",
        "A quick read on whether the local research workflow is ready, partial, or waiting on data.",
    )
    render_metric_cards(
        [
            ("Universe", current_universe["row_count"], "Tickers in data/universe.csv"),
            ("Holdings", 0 if holdings is None or holdings.empty else len(holdings), "Rows in holdings.csv"),
            ("Outputs", output_file_count, "Generated research files present"),
            ("Final Watchlist", 0 if final_watchlist_frame is None else len(final_watchlist_frame), "Current state-machine rows"),
            ("Missing Data", missing_warning_count, "Names with explicit warnings"),
            ("Latest Price", _latest_local_price_date(catalog), "From local prices.csv"),
            ("Fundamentals", _fundamentals_coverage_count(catalog), "Tickers with local fundamentals"),
            ("DCF Ready", _dcf_ready_count(catalog), "Enough local fields for DCF path"),
            ("Peer Ready", _peer_ready_count(catalog), "Local peer mapping + peer context"),
            ("Research Ready", health_summary["research_ready"], "Data Quality Wizard rows"),
            ("Thin Liquidity", health_summary["thin_liquidity"], "Local liquidity context rows"),
            ("High Correlation", health_summary["high_correlation"], "Local co-movement context rows"),
        ]
    )

    actions: list[tuple[str, str, str, str]] = []
    if missing_warning_count:
        actions.append(
            (
                "Data gaps are visible",
                f"{missing_warning_count} ticker/theme names have missing-data warnings. Use onboarding before trusting broader rankings.",
                "make onboarding",
                "warning",
            )
        )
    if _dcf_ready_count(catalog) == 0:
        actions.append(
            (
                "Valuation coverage is sparse",
                "DCF-ready count is zero. Stage SEC fundamentals or add verified local fundamentals before leaning on valuation context.",
                "make sec-stage TICKERS=NVDA,MSFT",
                "warning",
            )
        )
    if _peer_ready_count(catalog) == 0:
        actions.append(
            (
                "Peer context needs local research",
                "No peer-ready tickers detected. Add verified peer mappings manually if peer-relative valuation matters.",
                "make templates",
                "neutral",
            )
        )
    if not actions:
        actions.append(
            (
                "Workflow looks ready",
                "Core outputs are present and the dashboard can proceed with the current local dataset.",
                "make daily",
                "neutral",
            )
        )
    render_action_cards(actions)

    render_section_header("Output Snapshot", "Generated files and row counts from the active CSV-first pipeline.")
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
    for filename, label in RESEARCH_HEALTH_FILES.items():
        frame, message = health_tables[filename]
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
        render_section_header("Final Watchlist Snapshot", "Top-level state and reason context without opening the full table.")
        snapshot_columns = [column for column in ["Ticker", "FinalState", "SetupStatus", "FinalValueCategory", "WatchlistRank", "RankReason", "Reason"] if column in final_watchlist_frame.columns]
        st.dataframe(clean_display_frame(final_watchlist_frame[snapshot_columns]), width="stretch", hide_index=True)


def render_monthly_picks(catalog: LocalDataCatalog) -> None:
    render_section_header(
        "Monthly Picks",
        "A compact, product-style view of the current local research candidates and whether the track record has enough data.",
    )
    top_n = _monthly_top_n()
    picks_frame, picks_message = load_output(OUTPUTS_DIR / "monthly_research_picks.csv")
    track_frame, _track_message = load_output(OUTPUTS_DIR / "monthly_picks_track_record.csv")
    equity_frame, _equity_message = load_output(OUTPUTS_DIR / "monthly_picks_equity_curve.csv")
    latest_price = _latest_local_price_date(catalog)
    universe = catalog.load_dataframe("universe")
    candidate_count = 0 if picks_frame is None else len(picks_frame)

    render_metric_cards(
        [
            ("Candidates", f"{candidate_count} of {top_n}", "Conservative filters may return fewer"),
            ("Current Month", "Not generated" if picks_frame is None or picks_frame.empty else picks_frame.iloc[0].get("Month", "Not available"), "Generated from local outputs"),
            ("Benchmark", "SPY", "For local track-record comparison"),
            ("Universe", 0 if universe is None or universe.empty else len(universe), "Current local universe size"),
            ("Latest Price", latest_price, "From data/prices.csv"),
        ]
    )

    if picks_frame is None:
        st.info(picks_message or "Run `python3 -m src.monthly_picks --generate --top-n 5` to create monthly research candidates.")
    elif picks_frame.empty:
        st.info("Monthly picks output exists, but no candidates were generated from the current local outputs.")
    else:
        st.info(monthly_pick_availability_message(candidate_count, top_n))
        render_section_header("Research Candidates", "Ranked research candidates, not buy/sell instructions.")
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

    render_section_header("Track Record", "Shown only when local historical prices support benchmark comparison.")
    if equity_frame is not None and not equity_frame.empty and {"Month", "PicksEquity", "BenchmarkEquity"}.issubset(equity_frame.columns):
        chart_frame = equity_frame.set_index("Month")[["PicksEquity", "BenchmarkEquity"]]
        st.line_chart(chart_frame)
    else:
        st.info(track_record_status_message(track_frame, equity_frame))
    if track_frame is not None and not track_frame.empty:
        st.dataframe(clean_display_frame(track_frame), width="stretch", hide_index=True)
    else:
        st.info("Run `python3 -m src.track_record --monthly-picks` to create the local track-record files.")

    render_section_header("Archive", "Prior local monthly pick lists and returns when calculable.")
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
    render_section_header(title, "Search, filter, and inspect the most important columns first.")
    if message and frame is None:
        st.info(message)
        return
    if message and frame is not None:
        st.info(message)
    if frame is None:
        return
    render_table(frame, title.lower().replace(" ", "-"), show_reason_details)


def render_stock_report_beta(provider, show_raw_json: bool) -> None:
    render_section_header(
        "Stock Report (Beta)",
        "Structured research report workflow. Local CSV-backed data is the default. "
        "Optional yfinance mode stays off by default and is labeled unofficial / research-grade.",
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
    render_section_header(
        "Data Health",
        "Validation, source availability, price refresh diagnostics, and onboarding actions in one place.",
    )
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

    st.markdown("### Research Health")
    health_tables = load_research_health_tables()
    data_quality_frame, data_quality_message = health_tables["data_quality_wizard.csv"]
    liquidity_frame, liquidity_message = health_tables["liquidity_risk.csv"]
    correlation_frame, correlation_message = health_tables["correlation_risk.csv"]
    if data_quality_frame is None and liquidity_frame is None and correlation_frame is None:
        st.info(
            "Research health outputs have not been generated yet. Run "
            "`python3 -m src.research_health --write-output` or `python3 -m src.report_generator`."
        )
    else:
        health_summary = summarize_research_health_tables(data_quality_frame, liquidity_frame, correlation_frame)
        metric_cols = st.columns(4)
        metric_cols[0].metric("Research Ready", health_summary["research_ready"])
        metric_cols[1].metric("Partial Coverage", health_summary["partial_coverage"])
        metric_cols[2].metric("Needs Price Data", health_summary["needs_price_data"])
        metric_cols[3].metric("High Co-movement", health_summary["high_correlation"])

        if data_quality_frame is not None and not data_quality_frame.empty:
            data_quality_columns = [
                column
                for column in [
                    "Ticker",
                    "ReadinessStatus",
                    "DataQualityScore",
                    "MomentumReady",
                    "DCFReady",
                    "PeerReady",
                    "PriceHistoryDays",
                    "MissingDataFields",
                    "NextBestAction",
                    "Reason",
                ]
                if column in data_quality_frame.columns
            ]
            st.dataframe(style_frame(clean_display_frame(data_quality_frame[data_quality_columns])), width="stretch", hide_index=True)
        else:
            st.info(data_quality_message or "No data-quality rows are available.")

        with st.expander("Liquidity Context", expanded=False):
            if liquidity_frame is not None and not liquidity_frame.empty:
                liquidity_columns = [
                    column
                    for column in [
                        "Ticker",
                        "LiquidityStatus",
                        "AvgDollarVolume20D",
                        "AvgVolume20D",
                        "VolumeTrend5DVs20D",
                        "VolatilityProxy20D",
                        "MissingDataFields",
                        "Reason",
                    ]
                    if column in liquidity_frame.columns
                ]
                st.dataframe(style_frame(clean_display_frame(liquidity_frame[liquidity_columns])), width="stretch", hide_index=True)
            else:
                st.info(liquidity_message or "No liquidity rows are available.")

        with st.expander("Correlation Concentration Context", expanded=False):
            if correlation_frame is not None and not correlation_frame.empty:
                correlation_columns = [
                    column
                    for column in [
                        "Ticker",
                        "CorrelationStatus",
                        "MostCorrelatedTicker",
                        "Correlation",
                        "OverlapDays",
                        "MissingDataFields",
                        "Reason",
                    ]
                    if column in correlation_frame.columns
                ]
                st.dataframe(style_frame(clean_display_frame(correlation_frame[correlation_columns])), width="stretch", hide_index=True)
            else:
                st.info(correlation_message or "No correlation rows are available.")

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
        problematic_statuses = {"parse_error", "source_unavailable", "network_error", "failed"}
        if "status" in price_status_frame.columns and price_status_frame["status"].astype(str).str.lower().isin(problematic_statuses).any():
            st.warning(
                "Remote price refresh had source issues. Use `data/raw/prices/` for downloaded CSVs, then run "
                "`make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual`, "
                "`make price-validate`, `make price-preview`, and `make price-apply`."
            )
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
    render_section_header(
        "Universe Manager",
        "Review current universe coverage and use CLI-only apply commands for safer changes.",
    )
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
catalog = LocalDataCatalog(BASE_DIR)
provider = get_local_provider()
output_frames = load_pipeline_outputs()
universe_summary = summarize_universe_manager(BASE_DIR)
render_app_header(catalog, output_frames)

with st.sidebar:
    st.header("Research Controls")
    show_reason_details = st.checkbox("Show reason expanders", value=True)
    show_raw_json = st.checkbox("Show raw report JSON expanders", value=False)
    st.divider()
    st.caption("Safe local commands")
    st.code("make onboarding\nmake daily\nmake dashboard", language="bash")
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
