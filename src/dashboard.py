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
from src.project_status import build_project_status_payload
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
DASHBOARD_TAB_TITLES = [
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
DATA_SOURCE_FILES = {
    "data_source_status.csv": "Data Source Status",
    "data_gap_report.csv": "Data Gap Report",
}
DATA_ONBOARDING_FILES = {
    "ticker_data_coverage.csv": "Ticker Data Coverage",
    "data_onboarding_actions.csv": "Data Onboarding Actions",
    "data_coverage_wizard.csv": "Data Coverage Wizard",
    "price_import_worklist.csv": "Price Import Worklist",
    "fundamentals_peer_worklist.csv": "Fundamentals Peer Worklist",
    "optional_context_worklist.csv": "Optional Context Worklist",
    "ticker_unlock_ladder.csv": "Ticker Unlock Ladder",
    "unlock_priority_summary.csv": "Unlock Priority Summary",
}
ACTION_QUEUE_FILE = "research_action_queue.csv"
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
OUTPUT_TAB_GUIDANCE = {
    "Market Direction": "Theme and ETF rotation context from available local price data.",
    "Momentum Leaders": "Setup quality and leadership context, with missing price history called out explicitly.",
    "Portfolio Review": "Holding-level thesis review and concentration/risk context.",
    "Value / Re-rating": "Local quality and valuation context where fundamentals exist.",
    "Final Watchlist": "Combined research-state view assembled from transparent pipeline outputs.",
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
COLUMN_LABELS = {
    "Ticker": "Ticker",
    "Theme": "Theme",
    "Sector": "Sector",
    "SectorETF": "Sector ETF",
    "FinalState": "Final State",
    "SetupStatus": "Setup Status",
    "ReviewState": "Review State",
    "ThemeStatus": "Theme Status",
    "FinalValueCategory": "Value Category",
    "PeerRelativeStatus": "Peer Relative",
    "RelativeOpportunityScore": "Relative Score",
    "WatchlistScore": "Watchlist Score",
    "WatchlistRank": "Watchlist Rank",
    "RankReasonSummary": "Rank Reason",
    "ReasonSummary": "Reason",
    "DataGaps": "Data Gaps",
    "MissingDataFields": "Missing Data",
    "Return1M": "1M Return",
    "Return3M": "3M Return",
    "Return6M": "6M Return",
    "Return12M": "1Y Return",
    "RSPercentile": "RS Percentile",
    "QualityScore": "Quality Score",
    "ValuationScore": "Valuation Score",
    "ValueTrapRiskScore": "Value Trap Risk",
    "ConcentrationRisk": "Concentration Risk",
    "AvgDollarVolume20D": "Avg $ Volume 20D",
    "AvgVolume20D": "Avg Volume 20D",
    "VolumeTrend5DVs20D": "Volume Trend 5D vs 20D",
    "VolatilityProxy20D": "Volatility Proxy 20D",
    "MostCorrelatedTicker": "Most Correlated Ticker",
    "OverlapDays": "Overlap Days",
    "NextBestAction": "Next Best Action",
    "DataQualityScore": "Data Quality Score",
    "MomentumReady": "Momentum Ready",
    "DCFReady": "DCF Ready",
    "PeerReady": "Peer Ready",
    "PriceHistoryDays": "Price History Days",
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


def load_action_queue(
    outputs_dir: Path = OUTPUTS_DIR,
) -> tuple[pd.DataFrame | None, str | None]:
    path = outputs_dir / ACTION_QUEUE_FILE
    if not path.exists():
        return None, "`research_action_queue.csv` has not been generated yet. Run `python3 -m src.action_queue --write-output` or `make action-queue`."
    return load_output(path)


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


def summarize_price_worklist(worklist: pd.DataFrame | None) -> dict[str, int]:
    if worklist is None or worklist.empty:
        return {
            "momentum_ready": 0,
            "track_record_ready": 0,
            "preferred_history_ready": 0,
            "priority_1": 0,
        }

    def count_true(column: str) -> int:
        if column not in worklist.columns:
            return 0
        return int(worklist[column].astype(str).str.lower().isin({"true", "1", "yes"}).sum())

    priority_1 = 0
    if "priority" in worklist.columns:
        priority_1 = int(pd.to_numeric(worklist["priority"], errors="coerce").fillna(0).eq(1).sum())

    return {
        "momentum_ready": count_true("momentum_ready"),
        "track_record_ready": count_true("track_record_ready"),
        "preferred_history_ready": count_true("preferred_history_ready"),
        "priority_1": priority_1,
    }


def summarize_fundamentals_peer_worklist(worklist: pd.DataFrame | None) -> dict[str, int]:
    if worklist is None or worklist.empty:
        return {
            "dcf_ready": 0,
            "peer_ready": 0,
            "fundamentals_priority_1": 0,
            "peer_priority_2": 0,
        }

    def count_true(column: str) -> int:
        if column not in worklist.columns:
            return 0
        return int(worklist[column].astype(str).str.lower().isin({"true", "1", "yes"}).sum())

    priorities = pd.to_numeric(worklist.get("priority", pd.Series(dtype=float)), errors="coerce").fillna(0)
    dcf_ready_mask = worklist.get("dcf_ready", pd.Series(dtype=object)).astype(str).str.lower().isin({"true", "1", "yes"})
    peer_ready_mask = worklist.get("peer_ready", pd.Series(dtype=object)).astype(str).str.lower().isin({"true", "1", "yes"})

    return {
        "dcf_ready": count_true("dcf_ready"),
        "peer_ready": count_true("peer_ready"),
        "fundamentals_priority_1": int((priorities.eq(1) & ~dcf_ready_mask).sum()),
        "peer_priority_2": int((priorities.eq(2) & ~peer_ready_mask).sum()),
    }


def summarize_optional_context_worklist(worklist: pd.DataFrame | None) -> dict[str, int]:
    if worklist is None or worklist.empty:
        return {
            "earnings_ready": 0,
            "estimates_ready": 0,
            "missing_both": 0,
            "missing_one": 0,
        }

    priorities = pd.to_numeric(worklist.get("priority", pd.Series(dtype=float)), errors="coerce").fillna(0)

    def count_true(column: str) -> int:
        if column not in worklist.columns:
            return 0
        return int(worklist[column].astype(str).str.lower().isin({"true", "1", "yes"}).sum())

    return {
        "earnings_ready": count_true("has_earnings"),
        "estimates_ready": count_true("has_analyst_estimates"),
        "missing_both": int(priorities.eq(5).sum()),
        "missing_one": int(priorities.eq(6).sum()),
    }


def summarize_ticker_unlock_ladder(worklist: pd.DataFrame | None) -> dict[str, int]:
    if worklist is None or worklist.empty:
        return {
            "price_stage": 0,
            "fundamentals_stage": 0,
            "peer_stage": 0,
            "optional_stage": 0,
            "ready_stage": 0,
        }

    stage_series = worklist.get("current_unlock_stage", pd.Series(dtype=object)).astype(str)
    return {
        "price_stage": int(stage_series.eq("prices").sum()),
        "fundamentals_stage": int(stage_series.eq("fundamentals").sum()),
        "peer_stage": int(stage_series.eq("peers").sum()),
        "optional_stage": int(stage_series.eq("optional_context").sum()),
        "ready_stage": int(stage_series.eq("ready").sum()),
    }


def summarize_unlock_priority_summary(worklist: pd.DataFrame | None) -> dict[str, int]:
    if worklist is None or worklist.empty:
        return {
            "holdings_groups": 0,
            "theme_groups": 0,
            "sector_groups": 0,
            "price_led_groups": 0,
            "fundamentals_led_groups": 0,
        }

    group_type = worklist.get("group_type", pd.Series(dtype=object)).astype(str)
    top_stage = worklist.get("top_priority_stage", pd.Series(dtype=object)).astype(str)
    return {
        "holdings_groups": int(group_type.eq("holdings").sum()),
        "theme_groups": int(group_type.eq("theme").sum()),
        "sector_groups": int(group_type.eq("sector_etf").sum()),
        "price_led_groups": int(top_stage.eq("prices").sum()),
        "fundamentals_led_groups": int(top_stage.eq("fundamentals").sum()),
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
          margin: 1.35rem 0 0.42rem 0;
          font-size: 1.28rem;
          font-weight: 900;
          letter-spacing: -0.035em;
          color: var(--research-ink);
        }
        .section-caption {
          margin-top: 0;
          margin-bottom: 0.92rem;
          color: #526071;
          font-size: 0.93rem;
          line-height: 1.45;
          max-width: 70rem;
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
          padding: 0.26rem 0.56rem;
          border-radius: 999px;
          background: linear-gradient(180deg, #eef9f5, #dff3ea);
          border: 1px solid rgba(15, 118, 110, 0.18);
          color: #0b3b36;
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
          font-size: 0.76rem;
          font-weight: 800;
          letter-spacing: -0.01em;
        }
        .notice-card {
          margin: 0.75rem 0 1rem 0;
          padding: 1rem 1.05rem;
          border-radius: 18px;
          border: 1px solid #bfdbfe;
          border-left: 6px solid #2563eb;
          background: linear-gradient(180deg, #eff6ff, #ffffff);
          box-shadow: 0 10px 26px rgba(37, 99, 235, 0.08);
        }
        .notice-card.warning {
          border-color: #fed7aa;
          border-left-color: #d97706;
          background: linear-gradient(180deg, #fff7ed, #ffffff);
        }
        .notice-card.success {
          border-color: #bbf7d0;
          border-left-color: #16a34a;
          background: linear-gradient(180deg, #f0fdf4, #ffffff);
        }
        .notice-title {
          color: #111827;
          font-size: 0.98rem;
          font-weight: 900;
        }
        .notice-body {
          color: #475569;
          margin-top: 0.32rem;
          font-size: 0.9rem;
          line-height: 1.45;
        }
        .signal-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 0.85rem;
          margin: 0.8rem 0 1rem 0;
        }
        .signal-card {
          background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,246,0.96));
          border: 1px solid var(--research-border);
          border-radius: 20px;
          padding: 1rem 1.05rem;
          box-shadow: 0 14px 34px rgba(17, 24, 39, 0.07);
        }
        .signal-kicker {
          color: #0f766e;
          font-size: 0.71rem;
          letter-spacing: 0.11em;
          text-transform: uppercase;
          font-weight: 900;
        }
        .signal-title {
          color: #111827;
          font-size: 1rem;
          font-weight: 900;
          margin-top: 0.32rem;
        }
        .signal-body {
          color: #475467;
          font-size: 0.89rem;
          line-height: 1.45;
          margin-top: 0.45rem;
        }
        .signal-footer {
          margin-top: 0.7rem;
          display: flex;
          flex-wrap: wrap;
          gap: 0.45rem;
          align-items: center;
        }
        .pick-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
          gap: 0.95rem;
          margin: 0.8rem 0 1.1rem 0;
        }
        .pick-card {
          position: relative;
          overflow: hidden;
          background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(250,248,239,0.96));
          border: 1px solid var(--research-border);
          border-radius: 24px;
          padding: 1rem 1.05rem;
          box-shadow: 0 16px 38px rgba(17, 24, 39, 0.08);
        }
        .pick-card::before {
          content: "";
          position: absolute;
          inset: 0 auto 0 0;
          width: 7px;
          background: linear-gradient(180deg, #0f766e, #99f6e4);
        }
        .pick-head {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 0.75rem;
        }
        .pick-rank {
          color: #0f766e;
          font-size: 0.75rem;
          font-weight: 950;
          letter-spacing: 0.12em;
          text-transform: uppercase;
        }
        .pick-ticker {
          color: #111827;
          font-size: 1.65rem;
          font-weight: 950;
          letter-spacing: -0.055em;
          line-height: 1;
          margin-top: 0.18rem;
        }
        .pick-meta {
          color: #475569;
          font-size: 0.86rem;
          margin-top: 0.28rem;
          line-height: 1.35;
        }
        .pick-score {
          min-width: 74px;
          text-align: center;
          border-radius: 18px;
          padding: 0.55rem 0.6rem;
          background: #0b3b36;
          color: #ecfdf5;
          box-shadow: inset 0 0 0 1px rgba(255,255,255,0.16);
        }
        .pick-score-label {
          color: #99f6e4;
          font-size: 0.68rem;
          font-weight: 900;
          letter-spacing: 0.1em;
          text-transform: uppercase;
        }
        .pick-score-value {
          color: #ffffff;
          font-size: 1.22rem;
          font-weight: 950;
          letter-spacing: -0.04em;
        }
        .pick-badges {
          display: flex;
          flex-wrap: wrap;
          gap: 0.45rem;
          margin-top: 0.8rem;
        }
        .pick-reason {
          color: #1f2937;
          font-size: 0.92rem;
          line-height: 1.48;
          margin-top: 0.82rem;
        }
        .pick-missing {
          color: #475569;
          font-size: 0.84rem;
          line-height: 1.38;
          border-top: 1px solid #e5e7eb;
          margin-top: 0.85rem;
          padding-top: 0.72rem;
        }
        .report-brief {
          display: grid;
          grid-template-columns: minmax(260px, 1.15fr) minmax(260px, 1.85fr);
          gap: 1rem;
          margin: 0.85rem 0 1.05rem 0;
        }
        .report-brief-main {
          border-radius: 24px;
          padding: 1rem 1.05rem;
          background: linear-gradient(145deg, #172033, #0f766e);
          border: 1px solid rgba(255,255,255,0.22);
          box-shadow: 0 16px 38px rgba(17, 24, 39, 0.14);
        }
        .report-brief-kicker {
          color: #99f6e4;
          font-size: 0.72rem;
          font-weight: 950;
          letter-spacing: 0.13em;
          text-transform: uppercase;
        }
        .report-brief-title {
          color: #ffffff;
          font-size: 1.45rem;
          font-weight: 950;
          letter-spacing: -0.05em;
          line-height: 1.05;
          margin-top: 0.4rem;
        }
        .report-brief-copy {
          color: rgba(255,255,255,0.82);
          font-size: 0.9rem;
          line-height: 1.42;
          margin-top: 0.55rem;
        }
        .report-brief-grid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 0.7rem;
        }
        .report-brief-card {
          border-radius: 18px;
          padding: 0.85rem 0.9rem;
          background: rgba(255, 254, 250, 0.95);
          border: 1px solid var(--research-border);
          box-shadow: 0 10px 26px rgba(17,24,39,0.06);
        }
        .report-brief-label {
          color: #475569;
          font-size: 0.7rem;
          font-weight: 950;
          letter-spacing: 0.09em;
          text-transform: uppercase;
        }
        .report-brief-value {
          color: #111827;
          font-size: 1.05rem;
          font-weight: 950;
          line-height: 1.14;
          margin-top: 0.28rem;
        }
        .report-brief-note {
          color: #475569;
          font-size: 0.79rem;
          line-height: 1.35;
          margin-top: 0.28rem;
        }
        @media (max-width: 1050px) {
          .report-brief {
            grid-template-columns: 1fr;
          }
          .report-brief-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
        }
        @media (max-width: 650px) {
          .report-brief-grid {
            grid-template-columns: 1fr;
          }
        }
        .tiny-badge {
          display: inline-block;
          padding: 0.22rem 0.54rem;
          border-radius: 999px;
          font-size: 0.73rem;
          font-weight: 900;
          border: 1px solid rgba(15, 59, 54, 0.12);
          background: linear-gradient(180deg, #f8fafc, #eef4f7);
          color: #334155;
          box-shadow: inset 0 0 0 1px rgba(255,255,255,0.28);
        }
        .subtle-panel {
          border: 1px solid var(--research-border);
          background: rgba(255, 254, 250, 0.78);
          border-radius: 18px;
          padding: 0.95rem 1rem;
          margin: 0.85rem 0 1rem 0;
        }
        .subtle-panel strong {
          color: #111827;
        }
        .context-note {
          display: block;
          margin: 0.55rem 0 0.95rem 0;
          padding: 0.72rem 0.85rem;
          border-radius: 14px;
          border: 1px solid #dce5dc;
          background: rgba(255, 254, 250, 0.82);
          color: #526071;
          font-size: 0.86rem;
          line-height: 1.44;
        }
        .context-note strong {
          color: #102a43;
          font-weight: 900;
        }
        .context-note.warning {
          background: linear-gradient(180deg, #fff8ee, rgba(255,255,255,0.92));
          border-color: #f4c78a;
        }
        .context-note.success {
          background: linear-gradient(180deg, #f2fbf7, rgba(255,255,255,0.92));
          border-color: #b9e5cf;
        }
        .cockpit-panel {
          display: grid;
          grid-template-columns: minmax(260px, 1.1fr) minmax(260px, 1.6fr);
          gap: 1rem;
          align-items: stretch;
          margin: 0.8rem 0 1.05rem 0;
        }
        .cockpit-summary {
          border-radius: 24px;
          padding: 1.15rem 1.2rem;
          background: linear-gradient(145deg, #102f2c, #0f766e);
          box-shadow: 0 18px 38px rgba(15, 59, 54, 0.18);
          border: 1px solid rgba(255, 255, 255, 0.22);
        }
        .cockpit-kicker {
          color: #99f6e4;
          font-size: 0.73rem;
          font-weight: 900;
          text-transform: uppercase;
          letter-spacing: 0.13em;
        }
        .cockpit-title {
          color: #ffffff;
          font-size: 1.45rem;
          line-height: 1.08;
          font-weight: 950;
          letter-spacing: -0.045em;
          margin-top: 0.45rem;
        }
        .cockpit-copy {
          color: rgba(255, 255, 255, 0.82);
          font-size: 0.9rem;
          line-height: 1.42;
          margin-top: 0.55rem;
        }
        .cockpit-lanes {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 0.75rem;
        }
        .cockpit-lane {
          border-radius: 20px;
          padding: 0.95rem 1rem;
          background: rgba(255, 254, 250, 0.94);
          border: 1px solid var(--research-border);
          box-shadow: 0 12px 30px rgba(17, 24, 39, 0.07);
        }
        .cockpit-lane.warning {
          border-top: 5px solid #d97706;
        }
        .cockpit-lane.danger {
          border-top: 5px solid #dc2626;
        }
        .cockpit-lane.neutral {
          border-top: 5px solid #0f766e;
        }
        .cockpit-lane-label {
          color: #475569;
          font-size: 0.72rem;
          font-weight: 900;
          letter-spacing: 0.09em;
          text-transform: uppercase;
        }
        .cockpit-lane-value {
          color: #111827;
          font-size: 1.55rem;
          font-weight: 950;
          letter-spacing: -0.045em;
          margin-top: 0.2rem;
        }
        .cockpit-lane-note {
          color: #475569;
          font-size: 0.84rem;
          line-height: 1.38;
          margin-top: 0.28rem;
        }
        @media (max-width: 900px) {
          .cockpit-panel {
            grid-template-columns: 1fr;
          }
          .cockpit-lanes {
            grid-template-columns: 1fr;
          }
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


def notice_card_html(title: str, body: str, command: str = "", tone: str = "info") -> str:
    tone_class = "warning" if tone == "warning" else "success" if tone == "success" else ""
    command_html = f"<div class='command-chip'>{html.escape(command)}</div>" if command else ""
    return (
        f"<div class='notice-card {tone_class}'>"
        f"<div class='notice-title'>{html.escape(title)}</div>"
        f"<div class='notice-body'>{html.escape(body)}</div>"
        f"{command_html}"
        "</div>"
    )


def render_notice_card(title: str, body: str, command: str = "", tone: str = "info") -> None:
    st.markdown(notice_card_html(title, body, command, tone), unsafe_allow_html=True)


def context_note_html(title: str, body: str, tone: str = "neutral") -> str:
    tone_class = "warning" if tone == "warning" else "success" if tone == "success" else ""
    return (
        f"<div class='context-note {tone_class}'>"
        f"<strong>{html.escape(title)}</strong> {html.escape(body)}"
        "</div>"
    )


def render_context_note(title: str, body: str, tone: str = "neutral") -> None:
    st.markdown(context_note_html(title, body, tone), unsafe_allow_html=True)


def chart_panel_title(title: str) -> str:
    cleaned = " ".join(str(title).strip().rstrip(".:;").split())
    return cleaned if cleaned else "Chart"


def render_chart_panel(title: str, description: str, chart_frame: pd.DataFrame, chart_kind: str = "bar", height: int = 280) -> None:
    st.markdown(f"#### {chart_panel_title(title)}")
    render_context_note(chart_panel_title(title) + ".", description)
    if chart_kind == "line":
        st.line_chart(chart_frame, height=height)
    else:
        st.bar_chart(chart_frame, height=height)


def tiny_badge_html(label: str) -> str:
    return f"<span class='tiny-badge'>{html.escape(label)}</span>"


def signal_card_html(kicker: str, title: str, body: str, badges: list[str] | None = None, command: str = "") -> str:
    footer_parts = "".join(tiny_badge_html(badge) for badge in (badges or []))
    if command:
        footer_parts += f"<span class='command-chip'>{html.escape(command)}</span>"
    return (
        "<div class='signal-card'>"
        f"<div class='signal-kicker'>{html.escape(kicker)}</div>"
        f"<div class='signal-title'>{html.escape(title)}</div>"
        f"<div class='signal-body'>{html.escape(body)}</div>"
        f"<div class='signal-footer'>{footer_parts}</div>"
        "</div>"
    )


def render_signal_cards(cards: list[dict[str, object]]) -> None:
    st.markdown(
        "<div class='signal-grid'>"
        + "".join(
            signal_card_html(
                str(card.get("kicker", "")),
                str(card.get("title", "")),
                str(card.get("body", "")),
                [str(item) for item in card.get("badges", [])],
                str(card.get("command", "")),
            )
            for card in cards
        )
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


def report_display_value(value: object, value_type: str = "number") -> str:
    if value_type == "percent":
        return format_percent(value)
    if value_type == "date":
        return format_date_short(value)
    if value_type == "integer":
        number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        if pd.isna(number):
            return "Not available"
        return f"{int(number):,}"
    if value_type == "currency":
        number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        if pd.isna(number):
            return "Not available"
        return f"${float(number):,.2f}"
    return format_value(value)


def stock_report_key_value_frame(
    data: dict[str, object],
    fields: list[tuple[str, str, str]],
) -> pd.DataFrame:
    rows = []
    for key, label, value_type in fields:
        rows.append({"Metric": label, "Value": report_display_value(data.get(key), value_type)})
    return pd.DataFrame(rows)


def stock_report_readiness_badges(readiness: dict[str, object]) -> list[str]:
    definitions = [
        ("dcf_ready", "DCF ready", "DCF needs data"),
        ("peer_ready", "Peer ready", "Peers needed"),
        ("earnings_available", "Earnings available", "Earnings missing"),
        ("analyst_estimates_available", "Estimates available", "Estimates missing"),
    ]
    return [ready_label if readiness.get(key) else missing_label for key, ready_label, missing_label in definitions]


def stock_report_summary_cards(report_payload: dict[str, object]) -> list[dict[str, object]]:
    price = report_payload.get("price_snapshot", {}) or {}
    performance = report_payload.get("performance", {}) or {}
    valuation = report_payload.get("valuation_snapshot", {}) or {}
    readiness = report_payload.get("valuation_readiness", {}) or {}
    warnings = report_payload.get("missing_data_warnings", []) or []
    return [
        {
            "kicker": "PRICE",
            "title": report_display_value(price.get("price"), "currency"),
            "body": f"Volume {report_display_value(price.get('volume'), 'integer')} from {format_missing(price.get('market_time'), 'local data')}.",
            "badges": [format_missing(report_payload.get("provider_name"), "local provider")],
        },
        {
            "kicker": "PERFORMANCE",
            "title": f"1M {report_display_value(performance.get('one_month'), 'percent')}",
            "body": f"3M {report_display_value(performance.get('three_month'), 'percent')} · 1Y {report_display_value(performance.get('one_year'), 'percent')}.",
            "badges": ["Local price history"],
        },
        {
            "kicker": "VALUATION",
            "title": format_missing(valuation.get("status"), "Not available"),
            "body": f"Coverage: {format_missing(valuation.get('coverage'), 'Not available')}. Assumptions remain visible and informational only.",
            "badges": stock_report_readiness_badges(readiness)[:2],
        },
        {
            "kicker": "DATA",
            "title": f"{len(warnings)} warning{'s' if len(warnings) != 1 else ''}",
            "body": "Missing inputs stay visible; the report does not fabricate unavailable fields.",
            "badges": stock_report_readiness_badges(readiness)[2:],
        },
    ]


def stock_report_local_context_cards(
    coverage: pd.DataFrame,
    peer_summary: dict[str, object],
) -> list[dict[str, object]]:
    available_datasets = 0 if coverage.empty else int(coverage.get("ticker_present", pd.Series(dtype=object)).astype(bool).sum())
    validation_warnings = 0
    if not coverage.empty and "validation_status" in coverage.columns:
        validation_warnings = int(coverage["validation_status"].astype(str).eq("valid_with_warnings").sum())
    peer_count = int(peer_summary.get("peer_count") or 0)
    return [
        {
            "kicker": "LOCAL DATASETS",
            "title": f"{available_datasets} available",
            "body": f"{validation_warnings} dataset warning{'s' if validation_warnings != 1 else ''} remain for this ticker's local coverage view.",
            "badges": ["csv-first"],
        },
        {
            "kicker": "PEER MAPPING",
            "title": "Present" if peer_summary.get("peer_dataset_present") else "Missing",
            "body": f"{peer_count} peer ticker{'s' if peer_count != 1 else ''} configured for local peer-relative context.",
            "badges": ["manual research"],
        },
        {
            "kicker": "PEER FUNDAMENTALS",
            "title": format_missing(peer_summary.get("peer_fundamentals_available"), "0"),
            "body": "Peer-relative valuation only uses locally available peer fundamentals and market context.",
            "badges": ["no fabrication"],
        },
        {
            "kicker": "PEER MARKET",
            "title": format_missing(peer_summary.get("peer_market_context_available"), "0"),
            "body": "Price and peer readiness remain explicit instead of being inferred from missing local files.",
            "badges": ["research only"],
        },
    ]


def stock_report_price_chart_frame(history: pd.DataFrame | None) -> pd.DataFrame:
    if history is None or history.empty or "date" not in history.columns or "close" not in history.columns:
        return pd.DataFrame(columns=["Close"])

    frame = history.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.loc[frame["date"].notna() & frame["close"].notna(), ["date", "close"]].copy()
    if frame.empty:
        return pd.DataFrame(columns=["Close"])

    frame = frame.sort_values("date").drop_duplicates(subset="date", keep="last")
    return frame.rename(columns={"close": "Close"}).set_index("date")


def monthly_pick_score_chart_frame(picks_frame: pd.DataFrame | None, max_rows: int = 8) -> pd.DataFrame:
    if picks_frame is None or picks_frame.empty or "Ticker" not in picks_frame.columns:
        return pd.DataFrame()

    score_columns = [
        column
        for column in ["CompositeScore", "MomentumScore", "QualityScore", "ValuationContextScore", "LiquidityScore"]
        if column in picks_frame.columns
    ]
    if not score_columns:
        return pd.DataFrame()

    frame = picks_frame.copy()
    for column in score_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    rank_columns = ["Rank"] if "Rank" in frame.columns else []
    frame = frame.loc[frame[score_columns].notna().any(axis=1), ["Ticker", *score_columns, *rank_columns]].copy()
    if frame.empty:
        return pd.DataFrame()

    frame["Ticker"] = frame["Ticker"].astype(str).str.upper().str.strip()
    if "Rank" in frame.columns:
        frame["Rank"] = pd.to_numeric(frame["Rank"], errors="coerce")
        frame = frame.sort_values(["Rank", "CompositeScore"], ascending=[True, False], na_position="last")
    else:
        frame = frame.sort_values("CompositeScore", ascending=False, na_position="last")

    frame = frame.drop_duplicates(subset=["Ticker"], keep="first").head(max_rows)
    chart_frame = frame.set_index("Ticker")[score_columns]
    return chart_frame.rename(columns={"ValuationContextScore": "ValuationScore"})


def _technical_distance_label(value: object, label: str) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return f"{label} unavailable"
    relation = "Above" if float(number) >= 0 else "Below"
    return f"{relation} {label}"


def stock_report_technical_context_cards(report_payload: dict[str, object]) -> list[dict[str, object]]:
    screener_context = report_payload.get("screener_context", {}) or {}
    momentum = screener_context.get("momentum_leaders", {}) or {}
    watchlist = screener_context.get("final_watchlist", {}) or {}
    setup_status = format_missing(momentum.get("SetupStatus") or watchlist.get("SetupStatus"), "Not available")
    final_state = format_missing(watchlist.get("FinalState"), "Not available")
    rs_percentile = momentum.get("RSPercentile")
    relative_spy = momentum.get("RelativeReturnVsSPY")
    relative_qqq = momentum.get("RelativeReturnVsQQQ")
    volume_ratio = momentum.get("VolumeRatio")
    volatility_proxy = momentum.get("ATRorVolatilityPct")
    ma_stack = [
        _technical_distance_label(momentum.get("DistanceFrom10EMA"), "10 EMA"),
        _technical_distance_label(momentum.get("DistanceFrom21EMA"), "21 EMA"),
        _technical_distance_label(momentum.get("DistanceFrom50SMA"), "50 SMA"),
    ]
    return [
        {
            "kicker": "SETUP",
            "title": setup_status,
            "body": f"Current watchlist state: {final_state}. Momentum setup remains research context, not a trade instruction.",
            "badges": [final_state],
        },
        {
            "kicker": "RELATIVE STRENGTH",
            "title": report_display_value(rs_percentile, "number"),
            "body": f"vs SPY {report_display_value(relative_spy, 'percent')} · vs QQQ {report_display_value(relative_qqq, 'percent')}.",
            "badges": ["RS percentile"],
        },
        {
            "kicker": "TREND STACK",
            "title": ma_stack[0],
            "body": " · ".join(ma_stack[1:]),
            "badges": ["moving averages"],
        },
        {
            "kicker": "FLOW / VOLATILITY",
            "title": f"Volume {report_display_value(volume_ratio, 'number')}x",
            "body": f"ATR / volatility proxy {report_display_value(volatility_proxy, 'percent')}. Missing values stay visible instead of guessed.",
            "badges": ["local screener"],
        },
    ]


def stock_report_technical_context_frame(report_payload: dict[str, object]) -> pd.DataFrame:
    screener_context = report_payload.get("screener_context", {}) or {}
    momentum = screener_context.get("momentum_leaders", {}) or {}
    watchlist = screener_context.get("final_watchlist", {}) or {}
    rows = [
        {"Metric": "Setup Status", "Value": format_missing(momentum.get("SetupStatus") or watchlist.get("SetupStatus"))},
        {"Metric": "Final State", "Value": format_missing(watchlist.get("FinalState"))},
        {"Metric": "RS Percentile", "Value": report_display_value(momentum.get("RSPercentile"), "number")},
        {"Metric": "Relative Return vs SPY", "Value": report_display_value(momentum.get("RelativeReturnVsSPY"), "percent")},
        {"Metric": "Relative Return vs QQQ", "Value": report_display_value(momentum.get("RelativeReturnVsQQQ"), "percent")},
        {"Metric": "10 EMA Distance", "Value": report_display_value(momentum.get("DistanceFrom10EMA"), "percent")},
        {"Metric": "21 EMA Distance", "Value": report_display_value(momentum.get("DistanceFrom21EMA"), "percent")},
        {"Metric": "50 SMA Distance", "Value": report_display_value(momentum.get("DistanceFrom50SMA"), "percent")},
        {"Metric": "Average Volume 20D", "Value": report_display_value(momentum.get("AvgVolume20D"), "integer")},
        {"Metric": "Volume Ratio", "Value": report_display_value(momentum.get("VolumeRatio"), "number")},
        {"Metric": "ATR / Volatility Proxy", "Value": report_display_value(momentum.get("ATRorVolatilityPct"), "percent")},
    ]
    return pd.DataFrame(rows)


def stock_report_missing_data_text(warnings: list[object]) -> str:
    if not warnings:
        return "No explicit missing-data warnings were assembled from the current inputs."
    return "; ".join(summarize_missing_fields(warning, max_items=4) for warning in warnings)


def stock_report_source_frame(source_rows: list[dict[str, object]]) -> pd.DataFrame:
    if not source_rows:
        return pd.DataFrame(columns=["Provider", "Freshness", "Retrieved", "Official", "Notes"])
    rows = []
    for row in source_rows:
        rows.append(
            {
                "Provider": format_missing(row.get("provider")),
                "Freshness": format_missing(row.get("freshness")),
                "Retrieved": format_date_short(row.get("retrieved_at"), fallback="Not available"),
                "Official": "Yes" if row.get("official") else "No",
                "Notes": joined_notes(row.get("notes")),
            }
        )
    return pd.DataFrame(rows)


def stock_report_detail_frame(data: dict[str, object]) -> pd.DataFrame:
    rows = []
    for key, value in data.items():
        if isinstance(value, bool):
            display = "Yes" if value else "No"
        elif isinstance(value, list):
            display = joined_notes(value)
        elif isinstance(value, dict):
            display = ", ".join(f"{item_key}: {format_missing(item_value)}" for item_key, item_value in value.items()) or "Not available"
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            display = format_value(value)
        else:
            display = format_date_short(value) if "date" in str(key).lower() or "time" in str(key).lower() else format_missing(value)
        rows.append({"Field": display_column_label(str(key)), "Value": display})
    return pd.DataFrame(rows)


def stock_report_notes_frame(
    valuation: dict[str, object],
    relative: dict[str, object],
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Section": "DCF warnings", "Details": joined_notes(valuation.get("warnings", []))},
            {"Section": "DCF notes", "Details": joined_notes(valuation.get("notes", []))},
            {"Section": "Peer warnings", "Details": joined_notes(relative.get("peer_missing_data_warnings", []))},
            {"Section": "Peer missing fields", "Details": joined_notes(relative.get("missing_fields", []))},
        ]
    )


def data_health_overview_cards(
    validation_rows: pd.DataFrame,
    price_status_frame: pd.DataFrame | None,
    action_queue_frame: pd.DataFrame | None,
    coverage_frame: pd.DataFrame | None,
) -> list[dict[str, object]]:
    if validation_rows.empty:
        dataset_title = "No validation rows"
        dataset_body = "Run local validation to inspect configured CSV datasets."
        dataset_badges = ["make validate-data"]
    else:
        status_series = validation_rows.get("validation_status", pd.Series(dtype=object)).astype(str)
        valid_count = int(status_series.isin({"valid", "valid_with_warnings"}).sum())
        missing_count = int(status_series.eq("missing_file").sum())
        dataset_title = f"{valid_count} usable datasets"
        dataset_body = f"{missing_count} optional local file{'s' if missing_count != 1 else ''} missing. Partial reports remain safe."
        dataset_badges = ["CSV-first", f"{len(validation_rows)} checked"]

    price_counts = summarize_price_update_status(price_status_frame)
    price_problem_count = sum(
        price_counts.get(status, 0)
        for status in ["parse_error", "source_unavailable", "network_error", "no_rows", "failed"]
    )
    if price_status_frame is None:
        price_title = "Price status not generated"
        price_body = "Run price refresh or use manual staged OHLCV import when the remote source is unavailable."
        price_badges = ["make price-refresh"]
    elif price_problem_count:
        price_title = f"{price_problem_count} price issue{'s' if price_problem_count != 1 else ''}"
        price_body = "Use raw downloaded CSVs only as user-provided inputs, then normalize, validate, preview, and apply."
        price_badges = ["make price-normalize", "manual fallback"]
    else:
        price_title = f"{price_counts.get('fetched', 0)} fetched"
        price_body = "Latest price refresh did not report blocking source errors."
        price_badges = ["price status"]

    queue_summary = action_queue_summary(action_queue_frame)
    action_title = f"{queue_summary['critical']} critical actions"
    action_body = f"{queue_summary['high']} high-priority and {queue_summary['medium']} medium-priority remediation rows are queued."
    action_badges = ["make action-queue", "read-only dashboard"]

    coverage_summary = summarize_ticker_coverage(coverage_frame)
    coverage_title = f"{coverage_summary['usable_price_tickers']} price-ready tickers"
    coverage_body = (
        f"{coverage_summary['dcf_ready_tickers']} DCF-ready, "
        f"{coverage_summary['peer_ready_tickers']} peer-ready, "
        f"{coverage_summary['optional_only_missing_tickers']} missing only optional files."
    )
    coverage_badges = ["make onboarding"]

    return [
        {"kicker": "DATASETS", "title": dataset_title, "body": dataset_body, "badges": dataset_badges},
        {"kicker": "PRICES", "title": price_title, "body": price_body, "badges": price_badges},
        {"kicker": "NEXT ACTIONS", "title": action_title, "body": action_body, "badges": action_badges},
        {"kicker": "COVERAGE", "title": coverage_title, "body": coverage_body, "badges": coverage_badges},
    ]


def data_health_tab_summary_cards(
    tab_name: str,
    validation_rows: pd.DataFrame,
    coverage_frame: pd.DataFrame | None,
    status_frame: pd.DataFrame | None,
    price_status_frame: pd.DataFrame | None,
    staged_imports: dict[str, object],
) -> list[dict[str, object]]:
    coverage_summary = summarize_ticker_coverage(coverage_frame)
    if tab_name == "Coverage":
        return [
            {
                "kicker": "PRICE READY",
                "title": str(coverage_summary["usable_price_tickers"]),
                "body": "Tickers with enough local price history for momentum and monthly research surfaces.",
                "badges": ["local prices"],
            },
            {
                "kicker": "DCF READY",
                "title": str(coverage_summary["dcf_ready_tickers"]),
                "body": "Tickers with sufficient local valuation fields for DCF calculations.",
                "badges": ["fundamentals"],
            },
            {
                "kicker": "PEER READY",
                "title": str(coverage_summary["peer_ready_tickers"]),
                "body": "Tickers with manual peer mapping plus enough peer context for relative valuation.",
                "badges": ["peers.csv"],
            },
            {
                "kicker": "OPTIONAL ONLY",
                "title": str(coverage_summary["optional_only_missing_tickers"]),
                "body": "Tickers missing only optional earnings or analyst-estimate files rather than core research inputs.",
                "badges": ["safe partials"],
            },
        ]
    if tab_name == "Sources":
        available = 0
        partial = 0
        if status_frame is not None and not status_frame.empty and "availability_status" in status_frame.columns:
            series = status_frame["availability_status"].astype(str)
            available = int(series.eq("available").sum())
            partial = int(series.eq("partial").sum())
        return [
            {
                "kicker": "AVAILABLE",
                "title": str(available),
                "body": "Local or source-backed datasets that currently look usable in the status registry.",
                "badges": ["registry"],
            },
            {
                "kicker": "PARTIAL",
                "title": str(partial),
                "body": "Datasets where the project can proceed, but freshness or completeness is still limited.",
                "badges": ["transparent gaps"],
            },
        ]
    if tab_name == "Price Refresh":
        counts = summarize_price_update_status(price_status_frame)
        problem_total = sum(counts.get(status, 0) for status in ["parse_error", "source_unavailable", "network_error", "no_rows", "failed"])
        return [
            {
                "kicker": "FETCHED",
                "title": str(counts.get("fetched", 0)),
                "body": "Rows fetched in the last machine-readable price refresh run.",
                "badges": ["remote attempt"],
            },
            {
                "kicker": "SKIPPED",
                "title": str(counts.get("skipped_fresh", 0)),
                "body": "Tickers skipped because local rows already looked fresh enough.",
                "badges": ["fresh local data"],
            },
            {
                "kicker": "ISSUES",
                "title": str(problem_total),
                "body": "Parse, source, or network failures now surface here instead of hiding in logs.",
                "badges": ["manual fallback"],
            },
        ]
    if tab_name == "Staged Imports":
        file_count = len(staged_imports.get("files", [])) if isinstance(staged_imports, dict) else 0
        return [
            {
                "kicker": "STAGED FILES",
                "title": str(file_count),
                "body": "Local staged imports waiting for review before any canonical CSV apply step.",
                "badges": ["preview first"],
            }
        ]
    valid_count = int(validation_rows.get("validation_status", pd.Series(dtype=object)).astype(str).isin({"valid", "valid_with_warnings"}).sum()) if not validation_rows.empty else 0
    missing_count = int(validation_rows.get("validation_status", pd.Series(dtype=object)).astype(str).eq("missing_file").sum()) if not validation_rows.empty else 0
    return [
        {
            "kicker": "VALIDATED",
            "title": str(valid_count),
            "body": "Datasets that loaded cleanly or with visible warnings in the local validator.",
            "badges": ["schema checks"],
        },
        {
            "kicker": "OPTIONAL MISSING",
            "title": str(missing_count),
            "body": "Optional files can stay missing without breaking the research pipeline.",
            "badges": ["partial safe"],
        },
    ]


def data_health_fix_first_cards(actions_frame: pd.DataFrame | None, limit: int = 4) -> list[tuple[str, str, str, str]]:
    if actions_frame is None or actions_frame.empty:
        return [
            (
                "Generate onboarding actions",
                "Run the local onboarding workflow to identify price, fundamentals, peer, earnings, and estimate gaps.",
                "make onboarding",
                "warning",
            )
        ]
    ordered = actions_frame.sort_values(["priority", "ticker", "dataset"], na_position="last").head(limit)
    cards: list[tuple[str, str, str, str]] = []
    for _, row in ordered.iterrows():
        priority = int(row.get("priority") or 999)
        dataset = format_missing(row.get("dataset"), "data")
        ticker = format_missing(row.get("ticker"), fallback="")
        title = f"P{priority} {dataset}" + (f" - {ticker}" if ticker else "")
        reason = compact_reason(row.get("reason"), max_sentences=1, max_chars=150)
        action = format_missing(row.get("recommended_action"), fallback="Review local data coverage.")
        command = format_missing(row.get("example_command"), fallback="make onboarding")
        body = f"{reason} {action}".strip()
        tone = "danger" if priority <= 1 else "warning" if priority <= 2 else "neutral"
        cards.append((title, body, command, tone))
    return cards


def data_coverage_wizard_cards(wizard_frame: pd.DataFrame | None) -> list[dict[str, object]]:
    goals = [
        ("Unlock Monthly Picks", "MONTHLY"),
        ("Unlock Track Record", "TRACK RECORD"),
        ("Unlock DCF", "VALUATION"),
        ("Unlock Peer Relative", "PEERS"),
    ]
    if wizard_frame is None or wizard_frame.empty:
        return [
            {
                "kicker": "DATA WIZARD",
                "title": "Not generated",
                "body": "Run the local data wizard to see which verified CSV inputs unlock the most value next.",
                "badges": ["make data-wizard"],
            }
        ]
    cards: list[dict[str, object]] = []
    for goal, kicker in goals:
        subset = wizard_frame.loc[wizard_frame.get("unlock_goal", pd.Series(dtype=object)).astype(str).eq(goal)]
        if subset.empty:
            cards.append(
                {
                    "kicker": kicker,
                    "title": "Ready or not blocking",
                    "body": "No priority wizard rows currently block this research surface.",
                    "badges": ["local CSV"],
                }
            )
            continue
        ordered = subset.sort_values(["priority", "ticker", "blocking_dataset"], na_position="last")
        first = ordered.iloc[0]
        ticker = format_missing(first.get("ticker"), "portfolio")
        command = format_missing(first.get("example_command"), "make onboarding")
        cards.append(
            {
                "kicker": kicker,
                "title": f"{len(subset)} blocker{'s' if len(subset) != 1 else ''}",
                "body": f"Start with {ticker}: {compact_reason(first.get('why_it_matters'), max_sentences=1, max_chars=150)}",
                "badges": [format_missing(first.get("blocking_dataset"), "data"), command],
            }
        )
    return cards


def universe_workflow_cards(universe_summary: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    current = universe_summary.get("current_universe", {})
    staged = universe_summary.get("staged_universe", {})
    current_rows = int(current.get("row_count") or 0)
    duplicate_count = int(current.get("duplicate_ticker_count") or 0)
    missing_context = int(current.get("missing_theme_count") or 0) + int(current.get("unclassified_theme_count") or 0)
    missing_sector_etf = int(current.get("missing_sector_etf_count") or 0)
    staged_exists = bool(staged.get("path")) and int(staged.get("row_count") or 0) > 0
    staged_rows = int(staged.get("row_count") or 0)
    quality_tone = "warning" if duplicate_count or missing_context or missing_sector_etf else "neutral"
    return [
        (
            "Current universe",
            f"{current_rows} tickers are active. {duplicate_count} duplicate rows, {missing_context} missing/unclassified themes, and {missing_sector_etf} missing sector ETF values.",
            "data/universe.csv",
            quality_tone,
        ),
        (
            "Staged universe",
            f"{staged_rows} staged ticker rows are waiting for review." if staged_exists else "No staged universe import is waiting. Build an import before applying changes.",
            "make universe-preview",
            "warning" if staged_exists else "neutral",
        ),
        (
            "Safe expansion path",
            "Preview source-driven candidates first, write a staged CSV, then apply from the CLI only after review.",
            "make universe-preview",
            "neutral",
        ),
        (
            "Manual fallback",
            "If SMH or remote sources degrade, add verified rows through data/custom_universe.csv or data/imports/universe.csv.",
            "make templates",
            "neutral",
        ),
    ]


def staged_universe_status_frame(staged: dict[str, Any]) -> pd.DataFrame:
    validation = staged.get("validation", {}) if isinstance(staged, dict) else {}
    warnings = validation.get("warnings", []) if isinstance(validation, dict) else []
    if isinstance(warnings, list):
        warning_text = "; ".join(str(item) for item in warnings if str(item).strip()) or "No validation warnings"
    else:
        warning_text = format_missing(warnings, "No validation warnings")
    return pd.DataFrame(
        [
            {"Field": "Staged file", "Value": format_missing(staged.get("path"), "Not staged")},
            {"Field": "Rows", "Value": format_value(staged.get("row_count"), fallback="0")},
            {"Field": "Validation", "Value": format_missing(validation.get("status"), "Not available")},
            {"Field": "Warnings", "Value": warning_text},
        ]
    )


def non_empty_count(frame: pd.DataFrame, columns: list[str]) -> int:
    if frame.empty:
        return 0
    mask = pd.Series(False, index=frame.index)
    for column in columns:
        if column not in frame.columns:
            continue
        values = frame[column].fillna("").astype(str).str.strip().str.lower()
        mask = mask | (~values.isin({"", "nan", "none", "null", "not available"}))
    return int(mask.sum())


def dominant_value(frame: pd.DataFrame, columns: list[str], fallback: str = "Not available") -> tuple[str, int]:
    for column in columns:
        if column not in frame.columns:
            continue
        values = frame[column].dropna().astype(str).str.strip()
        values = values.loc[~values.str.lower().isin({"", "nan", "none", "null", "not available"})]
        if values.empty:
            continue
        counts = values.value_counts()
        return str(counts.index[0]), int(counts.iloc[0])
    return fallback, 0


def output_tab_summary_cards(title: str, frame: pd.DataFrame) -> list[dict[str, object]]:
    status, status_count = dominant_value(
        frame,
        ["FinalState", "SetupStatus", "ReviewState", "ThemeStatus", "FinalValueCategory", "Classification"],
    )
    theme, theme_count = dominant_value(frame, ["Theme", "Sector", "SectorETF"])
    missing_count = non_empty_count(frame, [column for column in frame.columns if "missing" in column.lower()])
    reason_count = non_empty_count(frame, [column for column in frame.columns if "reason" in column.lower()])
    row_count = len(frame)
    return [
        {
            "kicker": title.upper(),
            "title": f"{row_count} row{'s' if row_count != 1 else ''}",
            "body": OUTPUT_TAB_GUIDANCE.get(title, "Local CSV output with transparent reasons and visible gaps."),
            "badges": ["CSV output"],
        },
        {
            "kicker": "STATE",
            "title": status,
            "body": f"Most common visible state across {status_count} row{'s' if status_count != 1 else ''}.",
            "badges": ["status context"],
        },
        {
            "kicker": "DATA GAPS",
            "title": f"{missing_count} row{'s' if missing_count != 1 else ''}",
            "body": "Rows with explicit missing-data fields stay visible instead of being silently scored.",
            "badges": ["missing data"],
        },
        {
            "kicker": "THEME",
            "title": theme,
            "body": f"Most common theme/sector context across {theme_count} row{'s' if theme_count != 1 else ''}. {reason_count} rows include reason text.",
            "badges": ["explainable"],
        },
    ]


def market_direction_chart_frame(frame: pd.DataFrame | None, max_rows: int = 6) -> pd.DataFrame:
    if frame is None or frame.empty or "Theme" not in frame.columns:
        return pd.DataFrame()

    chart = frame.copy()
    numeric_columns = [column for column in ["Return1M", "RelativeReturnVsSPY", "RelativeReturnVsQQQ"] if column in chart.columns]
    if not numeric_columns:
        return pd.DataFrame()

    for column in numeric_columns:
        chart[column] = pd.to_numeric(chart[column], errors="coerce")

    chart = chart.loc[chart[numeric_columns].notna().any(axis=1), ["Theme", *numeric_columns]].copy()
    if chart.empty:
        return pd.DataFrame()

    sort_column = "RelativeReturnVsSPY" if "RelativeReturnVsSPY" in chart.columns else numeric_columns[0]
    chart["Theme"] = chart["Theme"].astype(str).str.strip()
    chart = chart.sort_values(sort_column, ascending=False, na_position="last").head(max_rows)
    return chart.set_index("Theme")


def momentum_setup_distribution_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty or "SetupStatus" not in frame.columns:
        return pd.DataFrame(columns=["Count"])

    setup_counts = (
        frame["SetupStatus"]
        .fillna("Not available")
        .astype(str)
        .str.strip()
        .replace({"": "Not available", "nan": "Not available", "None": "Not available"})
        .value_counts()
        .rename_axis("SetupStatus")
        .reset_index(name="Count")
    )
    return setup_counts.set_index("SetupStatus")


def momentum_relative_strength_chart_frame(frame: pd.DataFrame | None, max_rows: int = 8) -> pd.DataFrame:
    if frame is None or frame.empty or "Ticker" not in frame.columns:
        return pd.DataFrame()

    chart = frame.copy()
    numeric_columns = [column for column in ["RSPercentile", "RelativeReturnVsSPY", "RelativeReturnVsQQQ"] if column in chart.columns]
    if not numeric_columns:
        return pd.DataFrame()

    for column in numeric_columns:
        chart[column] = pd.to_numeric(chart[column], errors="coerce")

    chart = chart.loc[chart[numeric_columns].notna().any(axis=1), ["Ticker", *numeric_columns]].copy()
    if chart.empty:
        return pd.DataFrame()

    chart["Ticker"] = chart["Ticker"].astype(str).str.upper().str.strip()
    sort_column = "RSPercentile" if "RSPercentile" in chart.columns else numeric_columns[0]
    chart = chart.sort_values(sort_column, ascending=False, na_position="last").drop_duplicates(subset=["Ticker"]).head(max_rows)
    return chart.set_index("Ticker")


def categorical_count_frame(frame: pd.DataFrame | None, column: str, label: str) -> pd.DataFrame:
    if frame is None or frame.empty or column not in frame.columns:
        return pd.DataFrame(columns=["Count"])

    values = (
        frame[column]
        .fillna("Not available")
        .astype(str)
        .str.strip()
        .replace({"": "Not available", "nan": "Not available", "None": "Not available"})
        .value_counts()
        .rename_axis(label)
        .reset_index(name="Count")
    )
    return values.set_index(label)


def portfolio_review_risk_chart_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()

    pieces: list[pd.DataFrame] = []
    review_counts = categorical_count_frame(frame, "ReviewState", "ReviewState")
    if not review_counts.empty:
        pieces.append(review_counts.rename(columns={"Count": "ReviewStateCount"}))

    concentration_counts = categorical_count_frame(frame, "ConcentrationRisk", "ConcentrationRisk")
    if not concentration_counts.empty:
        concentration_chart = concentration_counts.rename(columns={"Count": "ConcentrationRiskCount"})
        concentration_chart.index = concentration_chart.index.map(
            lambda value: "Concentration risk" if str(value).lower() == "true" else "No concentration risk" if str(value).lower() == "false" else str(value)
        )
        pieces.append(concentration_chart)

    if not pieces:
        return pd.DataFrame()
    return pd.concat(pieces, axis=1).fillna(0)


def final_watchlist_score_chart_frame(frame: pd.DataFrame | None, max_rows: int = 8) -> pd.DataFrame:
    if frame is None or frame.empty or "Ticker" not in frame.columns:
        return pd.DataFrame()

    chart = frame.copy()
    numeric_columns = [column for column in ["WatchlistScore", "RelativeOpportunityScore"] if column in chart.columns]
    if not numeric_columns:
        return pd.DataFrame()

    for column in numeric_columns:
        chart[column] = pd.to_numeric(chart[column], errors="coerce")
    if "WatchlistRank" in chart.columns:
        chart["WatchlistRank"] = pd.to_numeric(chart["WatchlistRank"], errors="coerce")

    rank_columns = ["WatchlistRank"] if "WatchlistRank" in chart.columns else []
    chart = chart.loc[chart[numeric_columns].notna().any(axis=1), ["Ticker", *numeric_columns, *rank_columns]].copy()
    if chart.empty:
        return pd.DataFrame()

    chart["Ticker"] = chart["Ticker"].astype(str).str.upper().str.strip()
    sort_columns = ["WatchlistRank", "WatchlistScore"] if "WatchlistRank" in chart.columns else ["WatchlistScore"]
    ascending = [True, False] if "WatchlistRank" in chart.columns else [False]
    chart = chart.sort_values(sort_columns, ascending=ascending, na_position="last").drop_duplicates(subset=["Ticker"]).head(max_rows)
    return chart.set_index("Ticker")[numeric_columns]


def output_tab_chart_sections(title: str, frame: pd.DataFrame) -> list[tuple[str, str, pd.DataFrame, str]]:
    if title == "Market Direction":
        chart_frame = market_direction_chart_frame(frame)
        if chart_frame.empty:
            return []
        return [
            (
                "Theme performance snapshot",
                "Shows the strongest locally supported themes by relative return. Themes without enough numeric context stay out of the chart instead of being guessed.",
                chart_frame,
                "bar",
            )
        ]
    if title == "Momentum Leaders":
        sections: list[tuple[str, str, pd.DataFrame, str]] = []
        distribution_frame = momentum_setup_distribution_frame(frame)
        if not distribution_frame.empty:
            sections.append(
                (
                    "Setup distribution",
                    "Counts the current local setup states so you can see whether the universe is mostly watch-only, avoid, or developing new setups.",
                    distribution_frame,
                    "bar",
                )
            )
        rs_frame = momentum_relative_strength_chart_frame(frame)
        if not rs_frame.empty:
            sections.append(
                (
                    "Relative strength snapshot",
                    "Ranks the best locally supported momentum names by RS percentile and benchmark-relative performance.",
                    rs_frame,
                    "bar",
                )
            )
        return sections
    if title == "Portfolio Review":
        risk_frame = portfolio_review_risk_chart_frame(frame)
        if risk_frame.empty:
            return []
        return [
            (
                "Portfolio risk snapshot",
                "Summarizes current holding review states and explicit concentration-risk flags from the local portfolio review output.",
                risk_frame,
                "bar",
            )
        ]
    if title == "Final Watchlist":
        sections: list[tuple[str, str, pd.DataFrame, str]] = []
        final_state_counts = categorical_count_frame(frame, "FinalState", "FinalState")
        if not final_state_counts.empty:
            sections.append(
                (
                    "Final state distribution",
                    "Shows how the current watchlist splits across local end states such as setup-forming, review-thesis, or ignored names.",
                    final_state_counts,
                    "bar",
                )
            )
        score_frame = final_watchlist_score_chart_frame(frame)
        if not score_frame.empty:
            sections.append(
                (
                    "Watchlist score snapshot",
                    "Ranks the strongest locally scored watchlist names without inventing missing peer-relative or valuation data.",
                    score_frame,
                    "bar",
                )
            )
        return sections
    return []


def universe_preset_cards() -> list[dict[str, object]]:
    preset_descriptions = {
        "core": "Current local universe plus holdings. Safest and quickest workflow.",
        "sp500_smh": "S&P 500 community list, SMH holdings if available, plus holdings.",
        "broad": "Adds Nasdaq-listed common stocks. Larger and slower; preview first.",
    }
    cards = []
    for name, sources in SOURCE_PRESETS.items():
        cards.append(
            {
                "kicker": "PRESET",
                "title": name,
                "body": preset_descriptions.get(name, "Source-driven universe preset. Preview before applying."),
                "badges": [", ".join(sources)],
                "command": f"python3 -m src.universe_builder --preview --preset {name} --max-tickers 50",
            }
        )
    return cards


def status_legend_rows() -> list[dict[str, str]]:
    return [
        {
            "Label": "Research Ready",
            "Meaning": "Local price context and required research inputs are usable for the current workflow.",
        },
        {
            "Label": "Partial Coverage",
            "Meaning": "Some useful data exists, but at least one research path is incomplete.",
        },
        {
            "Label": "Needs Price Data",
            "Meaning": "Add or refresh verified OHLCV rows before relying on momentum or track-record context.",
        },
        {
            "Label": "Needs Enrichment",
            "Meaning": "Add verified local fundamentals, peer mappings, earnings, or estimate files as needed.",
        },
        {
            "Label": "Insufficient Data",
            "Meaning": "The app intentionally avoided calculating a result from incomplete inputs.",
        },
    ]


def missing_data_guide_rows() -> list[dict[str, str]]:
    return [
        {
            "Dashboard Label": "Not enough price history",
            "What to do": "Run `make price-refresh`, or normalize verified downloaded OHLCV files before validate/preview/apply.",
        },
        {
            "Dashboard Label": "Needs SEC enrichment",
            "What to do": "Use SEC staging for fundamentals, then validate and preview before applying.",
        },
        {
            "Dashboard Label": "Needs peers.csv",
            "What to do": "Add manually researched peer mappings through `data/imports/peers.csv`.",
        },
        {
            "Dashboard Label": "Needs earnings.csv",
            "What to do": "Add trusted local earnings rows only if you have a reliable source.",
        },
        {
            "Dashboard Label": "Needs analyst_estimates.csv",
            "What to do": "Optional file. Leave missing unless you have a trusted local source.",
        },
    ]


def workflow_command_rows() -> list[dict[str, str]]:
    return [
        {"Step": "Command menu", "Command": "make help"},
        {"Step": "Read-only status", "Command": "make status"},
        {"Step": "Deterministic verification", "Command": "make verify"},
        {"Step": "Extended validation", "Command": "make validate-all"},
        {"Step": "Dashboard smoke check", "Command": "make dashboard-smoke"},
        {"Step": "Daily refresh", "Command": "make daily"},
        {"Step": "Data coverage", "Command": "make onboarding"},
        {"Step": "Manual price normalization", "Command": "make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual"},
        {"Step": "Price import safety", "Command": "make price-validate && make price-preview && make price-apply"},
        {"Step": "SEC fundamentals staging", "Command": "make sec-stage TICKERS=NVDA,MSFT"},
        {"Step": "Universe preview", "Command": "make universe-preview"},
    ]


def dashboard_navigation_cards() -> list[tuple[str, str, str, str]]:
    return [
        (
            "Start in Overview",
            "Check workflow health, critical actions, and the next local data unlocks before reading the deeper tabs.",
            f"{DASHBOARD_TAB_TITLES[0]} tab",
            "neutral",
        ),
        (
            "Use Monthly Picks",
            "Review the current research candidates and whether conservative filters left fewer than the target count.",
            f"{DASHBOARD_TAB_TITLES[1]} tab",
            "neutral",
        ),
        (
            "Open Stock Report Beta",
            "Generate a structured single-ticker report with valuation, peer, earnings, and freshness context.",
            f"{DASHBOARD_TAB_TITLES[7]} tab",
            "neutral",
        ),
        (
            "Fix gaps in Data Health",
            "Use local validation, price refresh status, and onboarding actions before trusting thin or partial data.",
            f"{DASHBOARD_TAB_TITLES[8]} tab",
            "warning",
        ),
    ]


def empty_state_command_rows() -> list[dict[str, str]]:
    return [
        {"Scenario": "No local prices or short history", "Next step": "make price-refresh or make price-normalize INPUT=... TICKER=... SOURCE=..."},
        {"Scenario": "No local fundamentals for valuation", "Next step": "make sec-stage TICKERS=NVDA,MSFT then make sec-preview"},
        {"Scenario": "No peer-relative context", "Next step": "make templates, fill peers.csv locally, then validate/preview/apply"},
        {"Scenario": "No earnings or analyst estimates", "Next step": "Leave them missing safely unless you have a trusted local source"},
        {"Scenario": "No staged imports to review", "Next step": "Use templates or SEC/manual price staging first, then come back to preview/apply"},
    ]


def action_queue_summary(queue: pd.DataFrame | None) -> dict[str, int]:
    if queue is None or queue.empty:
        return {"critical": 0, "high": 0, "medium": 0}
    urgency = queue.get("urgency", pd.Series(dtype=object)).astype(str).str.lower()
    return {
        "critical": int(urgency.eq("critical").sum()),
        "high": int(urgency.eq("high").sum()),
        "medium": int(urgency.eq("medium").sum()),
    }


def workflow_health_score(
    queue_summary: dict[str, int],
    health_summary: dict[str, int],
) -> tuple[int, str]:
    score = 100
    score -= queue_summary.get("critical", 0) * 4
    score -= queue_summary.get("high", 0) * 2
    score -= health_summary.get("needs_price_data", 0) * 3
    score -= health_summary.get("thin_liquidity", 0)
    score -= health_summary.get("high_correlation", 0) * 2
    score = max(0, min(100, int(score)))
    if score >= 80:
        return score, "Ready"
    if score >= 55:
        return score, "Partial"
    return score, "Needs Data"


def project_status_metric_cards(payload: dict[str, Any] | None) -> list[tuple[str, object, str]]:
    if not payload:
        return []
    summary = payload.get("summary", {})
    total_sources = int(summary.get("data_sources_total") or 0)
    available_sources = int(summary.get("data_sources_available") or 0)
    total_tickers = int(summary.get("tickers_total") or 0)
    price_ready = int(summary.get("tickers_with_prices") or 0)
    dcf_ready = int(summary.get("tickers_dcf_ready") or 0)
    peer_ready = int(summary.get("tickers_peer_ready") or 0)
    return [
        ("Data Sources", f"{available_sources}/{total_sources}", "Available local/source coverage"),
        ("Data Gaps", int(summary.get("data_gaps") or 0), "Rows in the current gap report"),
        ("Price Ready", f"{price_ready}/{total_tickers}", "Tickers with usable local prices"),
        ("DCF Ready", f"{dcf_ready}/{total_tickers}", "Tickers with enough local valuation fields"),
        ("Peer Ready", f"{peer_ready}/{total_tickers}", "Tickers with local peer context"),
        (
            "Critical Actions",
            int(summary.get("critical_actions") or 0),
            f"{int(summary.get('onboarding_actions') or 0)} onboarding actions total",
        ),
    ]


def project_status_action_cards(payload: dict[str, Any] | None, limit: int = 3) -> list[tuple[str, str, str, str]]:
    if not payload:
        return [
            (
                "Project status unavailable",
                "Run the read-only status command to rebuild local source and onboarding summaries.",
                "make status",
                "warning",
            )
        ]
    actions: list[tuple[str, str, str, str]] = []
    for row in payload.get("top_onboarding_actions", [])[:limit]:
        priority = int(row.get("priority") or 999)
        dataset = format_missing(row.get("dataset"))
        ticker = format_missing(row.get("ticker"), fallback="")
        reason = format_missing(row.get("reason"), fallback="Local data coverage needs attention.")
        command = format_missing(row.get("example_command"), fallback="make onboarding")
        title = f"P{priority} {dataset}" + (f" - {ticker}" if ticker else "")
        tone = "danger" if priority <= 1 else "warning" if priority <= 2 else "neutral"
        actions.append((title, reason, command, tone))
    if not actions:
        actions.append(
            (
                "No urgent onboarding actions",
                "The read-only project status did not find priority local data tasks.",
                "make verify",
                "neutral",
            )
        )
    return actions


def project_status_command_rows(payload: dict[str, Any] | None) -> list[dict[str, str]]:
    commands = [] if not payload else payload.get("recommended_next_commands", [])
    return [{"Step": f"Next {index}", "Command": str(command)} for index, command in enumerate(commands, start=1)]


def project_status_cockpit_html(payload: dict[str, Any] | None, health_score: int, health_label: str) -> str:
    if not payload:
        return notice_card_html(
            "Project status unavailable",
            "Run `make status` to rebuild the local project status snapshot.",
            "make status",
            tone="warning",
        )
    summary = payload.get("summary", {})
    total_tickers = int(summary.get("tickers_total") or 0)
    price_ready = int(summary.get("tickers_with_prices") or 0)
    dcf_ready = int(summary.get("tickers_dcf_ready") or 0)
    peer_ready = int(summary.get("tickers_peer_ready") or 0)
    critical_actions = int(summary.get("critical_actions") or 0)
    data_gaps = int(summary.get("data_gaps") or 0)
    tone = "danger" if critical_actions else "warning" if data_gaps else "neutral"
    summary_copy = (
        f"{critical_actions} critical actions and {data_gaps} data gaps are currently visible. "
        "The workflow stays usable because missing inputs are labeled instead of guessed."
    )
    lanes = [
        ("Price Coverage", f"{price_ready}/{total_tickers}", "Momentum and track-record readiness", "danger" if price_ready < total_tickers else "neutral"),
        ("Valuation Coverage", f"{dcf_ready}/{total_tickers}", "DCF-ready local fundamentals", "warning" if dcf_ready < total_tickers else "neutral"),
        ("Peer Context", f"{peer_ready}/{total_tickers}", "Manual peer mappings plus peer data", "warning" if peer_ready < total_tickers else "neutral"),
    ]
    lane_html = "".join(
        (
            f"<div class='cockpit-lane {html.escape(lane_tone)}'>"
            f"<div class='cockpit-lane-label'>{html.escape(label)}</div>"
            f"<div class='cockpit-lane-value'>{html.escape(value)}</div>"
            f"<div class='cockpit-lane-note'>{html.escape(note)}</div>"
            "</div>"
        )
        for label, value, note, lane_tone in lanes
    )
    return (
        "<div class='cockpit-panel'>"
        f"<div class='cockpit-summary {html.escape(tone)}'>"
        "<div class='cockpit-kicker'>Research Cockpit</div>"
        f"<div class='cockpit-title'>{html.escape(health_label)} workflow, {health_score}/100</div>"
        f"<div class='cockpit-copy'>{html.escape(summary_copy)}</div>"
        "</div>"
        f"<div class='cockpit-lanes'>{lane_html}</div>"
        "</div>"
    )


def overview_landing_cards(
    project_status_payload: dict[str, Any] | None,
    queue_summary: dict[str, int],
    latest_price: str,
    watchlist_count: int,
    monthly_count: int,
) -> list[dict[str, object]]:
    summary = {} if not project_status_payload else project_status_payload.get("summary", {})
    total_tickers = int(summary.get("tickers_total") or 0)
    price_ready = int(summary.get("tickers_with_prices") or 0)
    dcf_ready = int(summary.get("tickers_dcf_ready") or 0)
    peer_ready = int(summary.get("tickers_peer_ready") or 0)
    gap_count = int(summary.get("data_gaps") or 0)
    return [
        {
            "kicker": "RESEARCH FLOW",
            "title": f"{watchlist_count} watchlist rows",
            "body": f"{monthly_count} current monthly candidates and latest local price date {latest_price}.",
            "badges": ["local outputs"],
        },
        {
            "kicker": "PRICE COVERAGE",
            "title": f"{price_ready}/{total_tickers}",
            "body": "Tickers with enough local price context for momentum and track-record workflows.",
            "badges": ["highest leverage"],
        },
        {
            "kicker": "VALUATION PATH",
            "title": f"{dcf_ready} DCF-ready",
            "body": f"{peer_ready} tickers also have peer-relative context. {gap_count} data gaps remain visible, not guessed.",
            "badges": ["research only"],
        },
        {
            "kicker": "FIX FIRST",
            "title": f"{queue_summary.get('critical', 0)} critical",
            "body": f"{queue_summary.get('high', 0)} high-priority remediation items remain in the local action queue.",
            "badges": ["make onboarding"],
        },
    ]


def holdings_unlock_cards(
    holdings: pd.DataFrame | None,
    ticker_unlock_ladder: pd.DataFrame | None,
    unlock_priority_summary: pd.DataFrame | None,
    limit: int = 3,
) -> list[dict[str, object]]:
    if holdings is None or holdings.empty or ticker_unlock_ladder is None or ticker_unlock_ladder.empty:
        return [
            {
                "kicker": "HOLDINGS FIRST",
                "title": "No holdings unlock board yet",
                "body": "Add holdings rows and generate onboarding outputs to surface blocked portfolio names before broader universe work.",
                "badges": ["read-only"],
            }
        ]

    holdings_lookup = {str(column).strip().lower(): str(column) for column in holdings.columns}
    ticker_col = holdings_lookup.get("ticker")
    purpose_col = holdings_lookup.get("primarypurpose")
    if not ticker_col:
        return []

    holding_tickers = holdings[ticker_col].dropna().astype(str).str.upper().str.strip().tolist()
    ladder = ticker_unlock_ladder.copy()
    if "ticker" not in ladder.columns:
        return []
    ladder["ticker"] = ladder["ticker"].astype(str).str.upper().str.strip()
    holding_rows = ladder.loc[ladder["ticker"].isin(holding_tickers)].copy()
    if holding_rows.empty:
        return []

    stage_rank = {"prices": 1, "fundamentals": 2, "peers": 3, "optional_context": 4, "ready": 5}
    holding_rows["stage_rank"] = holding_rows.get("current_unlock_stage", pd.Series(dtype=object)).map(stage_rank).fillna(99)
    cards: list[dict[str, object]] = []

    if unlock_priority_summary is not None and not unlock_priority_summary.empty and "group_type" in unlock_priority_summary.columns:
        holdings_summary = unlock_priority_summary.loc[unlock_priority_summary["group_type"].astype(str).eq("holdings")]
        if not holdings_summary.empty:
            row = holdings_summary.iloc[0]
            cards.append(
                {
                    "kicker": "HOLDINGS FIRST",
                    "title": format_missing(row.get("next_unlock_goal"), "Unlock holdings"),
                    "body": (
                        f"{format_missing(row.get('ticker_count'), '0')} holding names are currently led by "
                        f"{format_missing(row.get('top_priority_stage'), 'coverage')} gaps. "
                        f"Representative names: {format_missing(row.get('representative_tickers'), 'Not available')}."
                    ),
                    "badges": [format_missing(row.get("top_priority_stage"), "stage"), "portfolio"],
                }
            )

    holding_context = holdings.copy()
    holding_context[ticker_col] = holding_context[ticker_col].astype(str).str.upper().str.strip()
    purpose_map = (
        holding_context.set_index(ticker_col)[purpose_col].astype(str).to_dict()
        if purpose_col and purpose_col in holding_context.columns
        else {}
    )

    for _, row in holding_rows.sort_values(["stage_rank", "ticker"]).head(limit).iterrows():
        ticker = format_missing(row.get("ticker"), "Holding")
        stage = format_missing(row.get("current_unlock_stage"), "coverage")
        goal = format_missing(row.get("next_unlock_goal"), "Unlock data")
        purpose = format_missing(purpose_map.get(ticker), "Portfolio holding")
        cards.append(
            {
                "kicker": ticker,
                "title": goal,
                "body": (
                    f"{purpose}. Current stage: {stage}. "
                    f"Next action: {compact_reason(row.get('recommended_action'), max_sentences=1, max_chars=150)}"
                ),
                "badges": [stage, format_missing(row.get("price_stage_status"), "prices")],
                "command": format_missing(row.get("example_command"), ""),
            }
        )
    return cards


def theme_unlock_cards(
    unlock_priority_summary: pd.DataFrame | None,
    limit: int = 3,
) -> list[dict[str, object]]:
    if unlock_priority_summary is None or unlock_priority_summary.empty or "group_type" not in unlock_priority_summary.columns:
        return [
            {
                "kicker": "THEME FIRST",
                "title": "No theme unlock board yet",
                "body": "Generate onboarding outputs to surface which local themes or sector ETF clusters are blocked first.",
                "badges": ["read-only"],
            }
        ]

    summary = unlock_priority_summary.copy()
    summary["group_type"] = summary["group_type"].astype(str)
    theme_rows = summary.loc[summary["group_type"].isin(["theme", "sector_etf"])].copy()
    if theme_rows.empty:
        return [
            {
                "kicker": "THEME FIRST",
                "title": "No grouped theme unlocks yet",
                "body": "Theme and sector ETF rows will appear here once local universe context is available.",
                "badges": ["read-only"],
            }
        ]

    stage_rank = {"prices": 1, "fundamentals": 2, "peers": 3, "optional_context": 4, "ready": 5}
    theme_rows["stage_rank"] = theme_rows.get("top_priority_stage", pd.Series(dtype=object)).map(stage_rank).fillna(99)
    cards: list[dict[str, object]] = [
        {
            "kicker": "THEME FIRST",
            "title": format_missing(theme_rows.iloc[0].get("next_unlock_goal"), "Unlock themes"),
            "body": (
                f"{len(theme_rows)} grouped theme or sector ETF contexts are available. "
                f"Start where the highest-priority stage is still {format_missing(theme_rows.iloc[0].get('top_priority_stage'), 'coverage')}."
            ),
            "badges": ["theme lens", "research only"],
        }
    ]

    for _, row in theme_rows.sort_values(["stage_rank", "holdings_count", "ticker_count", "group_name"], ascending=[True, False, False, True]).head(limit).iterrows():
        cards.append(
            {
                "kicker": format_missing(row.get("group_name"), "Theme"),
                "title": format_missing(row.get("next_unlock_goal"), "Unlock data"),
                "body": (
                    f"{format_missing(row.get('group_type'), 'group')} group with "
                    f"{format_missing(row.get('ticker_count'), '0')} tickers and "
                    f"{format_missing(row.get('holdings_count'), '0')} holdings. "
                    f"Next action: {compact_reason(row.get('recommended_action'), max_sentences=1, max_chars=150)}"
                ),
                "badges": [
                    format_missing(row.get("top_priority_stage"), "stage"),
                    format_missing(row.get("group_type"), "group"),
                ],
            }
        )
    return cards


def overview_market_context_cards(
    market_direction: pd.DataFrame | None,
    limit: int = 3,
) -> list[dict[str, object]]:
    if market_direction is None or market_direction.empty or "Theme" not in market_direction.columns:
        return [
            {
                "kicker": "MARKET CONTEXT",
                "title": "No local market direction context yet",
                "body": "Run the pipeline to surface theme and sector ETF context from local price history.",
                "badges": ["read-only"],
            }
        ]

    chart = market_direction.copy()
    numeric_candidates = [column for column in ["RelativeReturnVsSPY", "RelativeReturnVsQQQ", "Return1M"] if column in chart.columns]
    for column in numeric_candidates:
        chart[column] = pd.to_numeric(chart[column], errors="coerce")
    chart["Theme"] = chart["Theme"].astype(str).str.strip()
    if "ThemeStatus" in chart.columns:
        chart["ThemeStatus"] = chart["ThemeStatus"].astype(str).str.strip()
    chart = chart.loc[chart[numeric_candidates].notna().any(axis=1)].copy()
    if chart.empty:
        return [
            {
                "kicker": "MARKET CONTEXT",
                "title": "Insufficient local theme performance",
                "body": "Themes stay out of this strip until local benchmark-relative data is available.",
                "badges": ["no guessing"],
            }
        ]

    sort_column = "RelativeReturnVsSPY" if "RelativeReturnVsSPY" in chart.columns else numeric_candidates[0]
    top_rows = chart.sort_values(sort_column, ascending=False, na_position="last").head(limit)
    cards: list[dict[str, object]] = [
        {
            "kicker": "MARKET CONTEXT",
            "title": format_missing(top_rows.iloc[0].get("ThemeStatus"), "Theme rotation"),
            "body": (
                f"Top locally supported theme is {format_missing(top_rows.iloc[0].get('Theme'), 'Not available')} "
                f"with {report_display_value(top_rows.iloc[0].get(sort_column), 'percent')} "
                f"vs benchmark context."
            ),
            "badges": ["local benchmark context", "research only"],
        }
    ]
    for _, row in top_rows.iterrows():
        cards.append(
            {
                "kicker": format_missing(row.get("Theme"), "Theme"),
                "title": format_missing(row.get("ThemeStatus"), "Theme status"),
                "body": (
                    f"1M {report_display_value(row.get('Return1M'), 'percent')}, "
                    f"vs SPY {report_display_value(row.get('RelativeReturnVsSPY'), 'percent')}, "
                    f"vs QQQ {report_display_value(row.get('RelativeReturnVsQQQ'), 'percent')}."
                ),
                "badges": [format_missing(row.get("ETF"), "ETF"), "theme lens"],
            }
        )
    return cards


def overview_benchmark_pressure_cards(
    market_direction: pd.DataFrame | None,
    price_status_frame: pd.DataFrame | None,
    project_status_payload: dict[str, Any] | None,
) -> list[dict[str, object]]:
    summary = {} if not project_status_payload else project_status_payload.get("summary", {})
    total_tickers = int(summary.get("tickers_total") or 0)
    price_ready = int(summary.get("tickers_with_prices") or 0)
    missing_prices = max(total_tickers - price_ready, 0)
    price_counts = summarize_price_update_status(price_status_frame)
    parse_or_source_errors = sum(
        price_counts.get(status, 0) for status in ("parse_error", "source_unavailable", "network_error", "failed", "no_rows")
    )

    strongest_theme = "Not available"
    relative_spy = "Not available"
    if market_direction is not None and not market_direction.empty and "Theme" in market_direction.columns:
        chart = market_direction.copy()
        if "RelativeReturnVsSPY" in chart.columns:
            chart["RelativeReturnVsSPY"] = pd.to_numeric(chart["RelativeReturnVsSPY"], errors="coerce")
            chart = chart.loc[chart["RelativeReturnVsSPY"].notna()].copy()
            if not chart.empty:
                top_row = chart.sort_values("RelativeReturnVsSPY", ascending=False, na_position="last").iloc[0]
                strongest_theme = format_missing(top_row.get("Theme"), "Not available")
                relative_spy = report_display_value(top_row.get("RelativeReturnVsSPY"), "percent")

    pressure_title = "Missing local prices" if missing_prices else "Local prices present"
    pressure_body = (
        f"{missing_prices}/{total_tickers} tickers still need verified local price history."
        if total_tickers
        else "Ticker coverage is not available yet."
    )
    if parse_or_source_errors:
        pressure_body += f" Latest refresh surfaced {parse_or_source_errors} source-side price issues, so manual staged imports may still be the safer path."

    benchmark_body = (
        f"Strongest current local theme is {strongest_theme} at {relative_spy} vs SPY."
        if strongest_theme != "Not available"
        else "Local benchmark-relative theme context is not available yet."
    )

    return [
        {
            "kicker": "BENCHMARK PRESSURE",
            "title": pressure_title,
            "body": pressure_body,
            "badges": ["price moat", "local only"],
        },
        {
            "kicker": "SPY CONTEXT",
            "title": strongest_theme,
            "body": benchmark_body,
            "badges": ["benchmark lens", "research only"],
        },
    ]


def overview_next_command_cards(
    project_status_payload: dict[str, Any] | None,
    action_queue: pd.DataFrame | None,
    limit: int = 3,
) -> list[dict[str, object]]:
    commands = project_status_command_rows(project_status_payload)
    cards: list[dict[str, object]] = []

    if commands:
        for row in commands[:limit]:
            command = format_missing(row.get("Command"), "")
            title = command if command else "Recommended command"
            body = (
                "Repo-native next step from the current read-only project status snapshot."
                if command
                else "No explicit command was available from project status."
            )
            badges = ["command", "research only"]
            lowered = command.lower()
            if "onboarding" in lowered:
                body = "Refresh local data coverage, onboarding outputs, and action guidance before broader research work."
                badges = ["data moat", "command"]
            elif "verify" in lowered:
                body = "Run deterministic local verification before trusting the current dashboard and CSV outputs."
                badges = ["verification", "command"]
            elif "dashboard" in lowered:
                body = "Open the Streamlit surface after local outputs and onboarding artifacts are refreshed."
                badges = ["ui", "command"]
            cards.append(
                {
                    "kicker": format_missing(row.get("Step"), "Next"),
                    "title": title,
                    "body": body,
                    "badges": badges,
                    "command": command,
                }
            )

    if len(cards) < limit:
        for signal in top_priority_signals(action_queue, limit=limit):
            command = format_missing(signal.get("command"), "")
            title = command or format_missing(signal.get("title"), "Priority action")
            cards.append(
                {
                    "kicker": format_missing(signal.get("kicker"), "Priority"),
                    "title": title,
                    "body": compact_reason(signal.get("body"), max_sentences=1, max_chars=160),
                    "badges": [str(item) for item in signal.get("badges", [])][:2],
                    "command": command,
                }
            )
            if len(cards) >= limit:
                break

    if not cards:
        cards.append(
            {
                "kicker": "NEXT COMMAND",
                "title": "make help",
                "body": "Start with the local command map if no project-status or action-queue guidance is available yet.",
                "badges": ["safe default"],
                "command": "make help",
            }
        )

    deduped: list[dict[str, object]] = []
    seen: set[str] = set()
    for card in cards:
        key = str(card.get("title", "")) + "|" + str(card.get("command", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(card)
    return deduped[:limit]


def monthly_pick_card_html(row: pd.Series | dict[str, object]) -> str:
    get_value = row.get if hasattr(row, "get") else dict(row).get
    ticker = format_missing(get_value("Ticker"))
    rank = format_value(get_value("Rank"), fallback="-")
    theme = format_missing(get_value("Theme"), "Unclassified")
    sector = format_missing(get_value("Sector"), "No sector")
    purpose = format_missing(get_value("PrimaryPurpose"), "Research candidate")
    reason = compact_reason(get_value("Reason"), max_sentences=2, max_chars=260)
    score = format_value(get_value("CompositeScore"), fallback="N/A")
    missing_fields = summarize_missing_fields(get_value("MissingDataFields"), max_items=4)
    missing_text = "No required gaps flagged" if missing_fields == "Not available" else missing_fields
    badges = [
        score_badge(get_value("MomentumScore")),
        status_badge(get_value("SetupStatus")),
        status_badge(get_value("FinalState")),
    ]
    return (
        "<div class='pick-card'>"
        "<div class='pick-head'>"
        "<div>"
        f"<div class='pick-rank'>Rank {html.escape(rank)}</div>"
        f"<div class='pick-ticker'>{html.escape(ticker)}</div>"
        f"<div class='pick-meta'>{html.escape(theme)} · {html.escape(sector)} · {html.escape(purpose)}</div>"
        "</div>"
        "<div class='pick-score'>"
        "<div class='pick-score-label'>Score</div>"
        f"<div class='pick-score-value'>{html.escape(score)}</div>"
        "</div>"
        "</div>"
        f"<div class='pick-badges'>{''.join(badges)}</div>"
        f"<div class='pick-reason'>{html.escape(reason)}</div>"
        f"<div class='pick-missing'><strong>Data gaps:</strong> {html.escape(missing_text)}</div>"
        "</div>"
    )


def monthly_picks_landing_cards(
    picks_frame: pd.DataFrame | None,
    track_frame: pd.DataFrame | None,
    equity_frame: pd.DataFrame | None,
    top_n: int,
    latest_price: str,
    universe_count: int,
) -> list[dict[str, object]]:
    candidate_count = 0 if picks_frame is None else len(picks_frame)
    month_value = "Not generated" if picks_frame is None or picks_frame.empty else format_missing(picks_frame.iloc[0].get("Month"), "Not available")
    track_ready = equity_frame is not None and not equity_frame.empty
    track_rows = 0 if track_frame is None else len(track_frame)
    pick_gap_count = 0
    if picks_frame is not None and not picks_frame.empty and "MissingDataFields" in picks_frame.columns:
        pick_gap_count = non_empty_count(picks_frame, ["MissingDataFields"])
    return [
        {
            "kicker": "MONTH",
            "title": month_value,
            "body": f"{candidate_count} of {top_n} conservative research candidate slots are filled from the current local run.",
            "badges": ["transparent ranking"],
        },
        {
            "kicker": "TRACK RECORD",
            "title": "Ready" if track_ready else "Needs history",
            "body": f"{track_rows} local monthly track-record row{'s' if track_rows != 1 else ''}. Forward returns appear only when enough history exists.",
            "badges": ["SPY benchmark"],
        },
        {
            "kicker": "LOCAL COVERAGE",
            "title": latest_price,
            "body": f"{universe_count} current universe tickers feed the monthly workflow through local price and screener outputs.",
            "badges": ["latest price date"],
        },
        {
            "kicker": "CONFIDENCE",
            "title": f"{pick_gap_count} rows with gaps",
            "body": "Missing fields remain attached to each candidate card so short history or missing fundamentals are obvious.",
            "badges": ["no forced fills"],
        },
    ]


def stock_report_brief_html(payload: dict[str, Any]) -> str:
    ticker = format_missing(payload.get("ticker"), "Selected ticker")
    valuation = payload.get("valuation_snapshot", {})
    readiness = payload.get("valuation_readiness", {})
    warnings = payload.get("missing_data_warnings", []) or []
    dcf_label = "DCF Ready" if readiness.get("dcf_ready") else "DCF Needs Data"
    peer_label = "Peers Ready" if readiness.get("peer_ready") else "Peers Need Data"
    earnings_label = "Earnings Present" if readiness.get("earnings_available") else "Earnings Missing"
    estimates_label = "Estimates Present" if readiness.get("analyst_estimates_available") else "Estimates Missing"
    missing_count = len(warnings)
    main_copy = (
        "Local structured report assembled from provider data and existing screener context. "
        "Unavailable inputs stay visible and are not inferred."
    )
    cards = [
        ("Valuation", format_missing(valuation.get("status"), "Not available"), format_missing(valuation.get("coverage"), "Coverage not available")),
        ("DCF", dcf_label, "Uses local fundamentals only"),
        ("Peer Relative", peer_label, "Requires data/peers.csv plus peer data"),
        ("Earnings", earnings_label, "Optional local earnings file"),
        ("Analyst Estimates", estimates_label, "Optional trusted local estimates file"),
        ("Missing Data", str(missing_count), "Warnings shown in Sources & Gaps"),
        ("Provider", format_missing(payload.get("provider_name"), "Not available"), "Review freshness notes"),
        ("Generated", format_date_short(payload.get("generated_at"), "Not available"), "Local report timestamp"),
    ]
    card_html = "".join(
        (
            "<div class='report-brief-card'>"
            f"<div class='report-brief-label'>{html.escape(label)}</div>"
            f"<div class='report-brief-value'>{html.escape(value)}</div>"
            f"<div class='report-brief-note'>{html.escape(note)}</div>"
            "</div>"
        )
        for label, value, note in cards
    )
    return (
        "<div class='report-brief'>"
        "<div class='report-brief-main'>"
        "<div class='report-brief-kicker'>Stock Report Beta</div>"
        f"<div class='report-brief-title'>{html.escape(ticker)} research snapshot</div>"
        f"<div class='report-brief-copy'>{html.escape(main_copy)}</div>"
        "</div>"
        f"<div class='report-brief-grid'>{card_html}</div>"
        "</div>"
    )


def top_priority_signals(action_queue: pd.DataFrame | None, limit: int = 3) -> list[dict[str, object]]:
    if action_queue is None or action_queue.empty:
        return []
    rows = []
    ordered = action_queue.sort_values(["priority", "ticker", "action_type"], na_position="last").head(limit)
    for _, row in ordered.iterrows():
        rows.append(
            {
                "kicker": str(row.get("urgency", "Action")).upper(),
                "title": format_missing(row.get("title"), "Research action"),
                "body": compact_reason(row.get("reason"), max_sentences=1, max_chars=180),
                "badges": [
                    f"P{format_missing(row.get('priority'), '-')}",
                    format_missing(row.get("action_type"), "action"),
                    format_missing(row.get("ticker"), "portfolio-wide"),
                ],
                "command": format_missing(row.get("example_command"), ""),
            }
        )
    return rows


def clean_display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    def clean_cell(value: object) -> str:
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, list):
            return ", ".join(str(item) for item in value if str(item).strip()) or "Not available"
        if isinstance(value, dict):
            return ", ".join(f"{key}: {val}" for key, val in value.items()) or "Not available"
        return format_missing(value)

    return frame.copy().map(clean_cell)


def display_column_label(column: str) -> str:
    if column in COLUMN_LABELS:
        return COLUMN_LABELS[column]
    label = []
    previous = ""
    for char in column.replace("_", " "):
        if previous and previous.islower() and char.isupper():
            label.append(" ")
        label.append(char)
        previous = char
    return "".join(label).strip().title()


def format_table_cell(column: str, value: object) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip()) or "Not available"
    if isinstance(value, dict):
        return ", ".join(f"{key}: {val}" for key, val in value.items()) or "Not available"

    lowered = column.lower()
    if "missing" in lowered or column == "DataGaps":
        return summarize_missing_fields(value)
    if "reason" in lowered:
        return compact_reason(value)

    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return format_missing(value)

    if any(token in lowered for token in ("return", "margin", "growth", "yield", "surprise_pct")):
        numeric = float(number)
        if abs(numeric) <= 2:
            numeric *= 100
        return f"{numeric:.1f}%"
    if any(token in lowered for token in ("score", "risk", "percentile", "correlation", "trend", "multiple")):
        return f"{float(number):.1f}".rstrip("0").rstrip(".")
    if any(token in lowered for token in ("volume", "marketcap", "revenue", "cash", "debt", "value")):
        return format_value(value)
    return format_missing(value)


def presentation_frame(frame: pd.DataFrame) -> pd.DataFrame:
    display_columns: dict[str, pd.Series] = {}
    label_counts: dict[str, int] = {}
    for index, column in enumerate(frame.columns):
        label = display_column_label(column)
        label_counts[label] = label_counts.get(label, 0) + 1
        if label_counts[label] > 1:
            label = f"{label} ({label_counts[label]})"
        series = frame.iloc[:, index].map(lambda value, column=column: format_table_cell(column, value))
        display_columns[label] = series
    display = pd.DataFrame(display_columns)
    return display


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
        "Month",
        "Rank",
        "Ticker",
        "CompanyName",
        "Theme",
        "Sector",
        "SectorETF",
        "ETF",
        "PrimaryPurpose",
        "FinalState",
        "SetupStatus",
        "ReviewState",
        "ThemeStatus",
        "FinalValueCategory",
        "PeerRelativeStatus",
        "RelativeOpportunityScore",
        "CompositeScore",
        "MomentumScore",
        "TechnicalContextScore",
        "QualityScore",
        "ValuationScore",
        "RiskPenalty",
        "LiquidityScore",
        "WatchlistScore",
        "WatchlistRank",
        "Return1M",
        "Return3M",
        "Return6M",
        "Return12M",
        "RSPercentile",
        "DataQualityScore",
        "MomentumReady",
        "DCFReady",
        "PeerReady",
        "PriceHistoryDays",
        "NextBestAction",
        "RankReasonSummary",
        "ReasonSummary",
        "DataGaps",
        "Reason",
        "RankReason",
        "MissingDataFields",
    ]
    ordered = [column for column in priority if column in frame.columns]
    remaining = [column for column in frame.columns if column not in ordered]
    return frame[ordered + remaining].copy()


def compact_table_columns(frame: pd.DataFrame) -> list[str]:
    priority = [
        "Month",
        "Rank",
        "Ticker",
        "CompanyName",
        "Theme",
        "Sector",
        "SectorETF",
        "ETF",
        "PrimaryPurpose",
        "FinalState",
        "SetupStatus",
        "ReviewState",
        "ThemeStatus",
        "FinalValueCategory",
        "PeerRelativeStatus",
        "RelativeOpportunityScore",
        "CompositeScore",
        "MomentumScore",
        "TechnicalContextScore",
        "RiskPenalty",
        "LiquidityScore",
        "WatchlistScore",
        "WatchlistRank",
        "RSPercentile",
        "PriceHistoryDays",
        "NextBestAction",
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
        selected.extend(
            column
            for column in frame.columns
            if column not in selected
            and column
            not in {
                "Reason",
                "RankReason",
                "MissingDataFields",
                "SourceFiles",
                "GeneratedAt",
                "Source",
                "Description",
                "MemberTickers",
            }
        )
    return selected[:14]


def table_focus_cards(frame: pd.DataFrame) -> list[dict[str, object]]:
    row_count = len(frame)
    row_label = "row" if row_count == 1 else "rows"
    lead_state, lead_state_count = dominant_value(
        frame,
        ["FinalState", "SetupStatus", "ReviewState", "ThemeStatus", "FinalValueCategory", "PeerRelativeStatus"],
    )
    lead_context, lead_context_count = dominant_value(frame, ["PrimaryPurpose", "Theme", "Sector", "SectorETF", "ETF"])
    missing_count = non_empty_count(frame, [column for column in frame.columns if "missing" in column.lower()])
    missing_label = "row" if missing_count == 1 else "rows"
    score_count = non_empty_count(
        frame,
        [
            column
            for column in frame.columns
            if any(token in column.lower() for token in ("score", "percentile", "return", "relativeopportunity"))
        ],
    )
    return [
        {
            "kicker": "VISIBLE ROWS",
            "title": f"{row_count} {row_label}",
            "body": "Current filtered view. Use search and status/theme filters to narrow the table before opening full details.",
            "badges": ["filter-aware"],
        },
        {
            "kicker": "LEAD STATE",
            "title": lead_state,
            "body": f"Most common visible state across {lead_state_count} row{'s' if lead_state_count != 1 else ''}.",
            "badges": ["status first"],
        },
        {
            "kicker": "LEAD CONTEXT",
            "title": lead_context,
            "body": f"Most common purpose/theme context across {lead_context_count} row{'s' if lead_context_count != 1 else ''}.",
            "badges": ["research lens"],
        },
        {
            "kicker": "DATA COVERAGE",
            "title": f"{missing_count} {missing_label} with gaps",
            "body": f"{score_count} row{'s' if score_count != 1 else ''} include score, return, or percentile context in the visible view.",
            "badges": ["missing data stays visible"],
        },
    ]


TABLE_IDENTITY_COLUMNS = {
    "Month",
    "Rank",
    "Ticker",
    "CompanyName",
    "Theme",
    "Sector",
    "SectorETF",
    "ETF",
    "PrimaryPurpose",
    "FinalState",
    "SetupStatus",
    "ReviewState",
    "ThemeStatus",
    "FinalValueCategory",
    "PeerRelativeStatus",
    "RelativeOpportunityScore",
    "WatchlistScore",
    "WatchlistRank",
    "CompositeScore",
    "MomentumScore",
    "TechnicalContextScore",
    "QualityScore",
    "ValuationScore",
    "RiskPenalty",
    "LiquidityScore",
    "RSPercentile",
    "Return1M",
    "Return3M",
    "Return6M",
    "Return12M",
}

TABLE_OPERATIONAL_COLUMNS = {
    "Source",
    "SourceFiles",
    "GeneratedAt",
    "Description",
    "MemberTickers",
    "TickersWithData",
    "HistoryDays",
}


def detail_columns(frame: pd.DataFrame, category: str) -> list[str]:
    columns = list(frame.columns)
    identity = [column for column in columns if column in TABLE_IDENTITY_COLUMNS]
    if category == "reasons":
        detail = [column for column in columns if "reason" in column.lower()]
    elif category == "support":
        detail = [
            column
            for column in columns
            if any(keyword in column.lower() for keyword in ("missing", "conflict", "risk"))
        ]
    elif category == "operations":
        detail = [
            column
            for column in columns
            if column in TABLE_OPERATIONAL_COLUMNS
            or any(keyword in column.lower() for keyword in ("source", "generated", "member", "description"))
        ]
    else:
        detail = []
    selected = [column for column in identity + detail if column in columns]
    return list(dict.fromkeys(selected))


def detail_sections(frame: pd.DataFrame, show_reason_details: bool) -> list[tuple[str, pd.DataFrame]]:
    sections: list[tuple[str, pd.DataFrame]] = []
    if show_reason_details:
        reason_cols = detail_columns(frame, "reasons")
        if any("reason" in column.lower() for column in reason_cols):
            sections.append(("Reasons", frame[reason_cols].copy()))

    support_cols = detail_columns(frame, "support")
    if any(
        any(keyword in column.lower() for keyword in ("missing", "conflict", "risk"))
        for column in support_cols
    ):
        sections.append(("Risk and data gaps", frame[support_cols].copy()))

    operations_cols = detail_columns(frame, "operations")
    if any(column not in TABLE_IDENTITY_COLUMNS for column in operations_cols):
        sections.append(("Source and operational context", frame[operations_cols].copy()))
    return sections


def pick_filter_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    for column in candidates:
        if column in frame.columns:
            values = frame[column].dropna().astype(str).str.strip()
            values = values.loc[~values.str.lower().isin({"", "nan", "none", "null", "not available"})]
            if not values.empty:
                return column
    return None


def filter_summary_text(
    key: str,
    search_value: str,
    status_column: str | None,
    selected_statuses: list[str],
    theme_column: str | None,
    selected_themes: list[str],
    sector_column: str | None,
    selected_sectors: list[str],
    filtered_count: int,
    total_count: int,
) -> str:
    labels: list[str] = []
    if search_value.strip():
        labels.append(f"search `{search_value.strip()}`")
    if status_column and selected_statuses:
        labels.append(f"{display_column_label(status_column)}: {', '.join(selected_statuses[:3])}")
        if len(selected_statuses) > 3:
            labels[-1] += f" +{len(selected_statuses) - 3} more"
    if theme_column and selected_themes:
        labels.append(f"{display_column_label(theme_column)}: {', '.join(selected_themes[:3])}")
        if len(selected_themes) > 3:
            labels[-1] += f" +{len(selected_themes) - 3} more"
    if sector_column and selected_sectors:
        labels.append(f"{display_column_label(sector_column)}: {', '.join(selected_sectors[:3])}")
        if len(selected_sectors) > 3:
            labels[-1] += f" +{len(selected_sectors) - 3} more"

    scope = f"{filtered_count} of {total_count} rows visible" if total_count else "No rows available"
    if not labels:
        return f"{display_column_label(key.replace('-', ' ')) if '-' in key else key.title()}: {scope}. Use search or filters to narrow the table."
    return f"{scope}. Active filters: " + " | ".join(labels) + "."


def filter_frame(frame: pd.DataFrame, key: str) -> pd.DataFrame:
    filtered = frame.copy()
    with st.container():
        total_count = len(filtered)
        search_col, status_col_ui, theme_col_ui, sector_col_ui = st.columns([2.4, 1.4, 1.4, 1.4])
        search_value = search_col.text_input("Search", key=f"{key}-search", placeholder="Ticker, theme, state, reason...")
        if search_value:
            mask = filtered.astype(str).apply(
                lambda row: row.str.contains(search_value, case=False, na=False).any(),
                axis=1,
            )
            filtered = filtered.loc[mask].copy()

        status_columns = [column for column in filtered.columns if is_state_column(column)]
        status_column = status_columns[0] if status_columns else None
        selected_statuses: list[str] = []
        if status_column:
            statuses = sorted(value for value in filtered[status_column].dropna().astype(str).unique().tolist() if value)
            selected_statuses = status_col_ui.multiselect(
                display_column_label(status_column),
                options=statuses,
                default=[],
                key=f"{key}-status",
                placeholder="All",
            )
            if selected_statuses:
                filtered = filtered.loc[filtered[status_column].astype(str).isin(selected_statuses)].copy()

        theme_column = pick_filter_column(filtered, ["Theme"])
        selected_themes: list[str] = []
        if theme_column:
            themes = sorted(value for value in filtered[theme_column].dropna().astype(str).unique().tolist() if value)
            selected_themes = theme_col_ui.multiselect(
                display_column_label(theme_column),
                options=themes,
                default=[],
                key=f"{key}-theme",
                placeholder="All",
            )
            if selected_themes:
                filtered = filtered.loc[filtered[theme_column].astype(str).isin(selected_themes)].copy()

        sector_column = pick_filter_column(filtered, ["Sector", "SectorETF", "ETF"])
        selected_sectors: list[str] = []
        if sector_column:
            sectors = sorted(value for value in filtered[sector_column].dropna().astype(str).unique().tolist() if value)
            selected_sectors = sector_col_ui.multiselect(
                display_column_label(sector_column),
                options=sectors,
                default=[],
                key=f"{key}-sector",
                placeholder="All",
            )
            if selected_sectors:
                filtered = filtered.loc[filtered[sector_column].astype(str).isin(selected_sectors)].copy()

        render_context_note(
            "Active filters.",
            filter_summary_text(
                key,
                search_value,
                status_column,
                selected_statuses,
                theme_column,
                selected_themes,
                sector_column,
                selected_sectors,
                len(filtered),
                total_count,
            ),
        )
    return filtered


def render_table(frame: pd.DataFrame, key: str, show_reason_details: bool) -> None:
    filtered = filter_frame(reorder_columns(frame), key)
    display_frame = reorder_columns(display_with_summaries(filtered))
    compact_columns = compact_table_columns(display_frame)
    render_signal_cards(table_focus_cards(filtered))
    render_context_note(
        "Default view.",
        "Showing the most useful columns first. Open the detail panels below for reasons, data gaps, and operational context.",
    )
    st.dataframe(style_frame(presentation_frame(display_frame[compact_columns])), width="stretch", hide_index=True)

    for title, section_frame in detail_sections(filtered, show_reason_details):
        with st.expander(f"{key} {title.lower()}", expanded=False):
            st.dataframe(style_frame(presentation_frame(section_frame)), width="stretch", hide_index=True)

    with st.expander(f"{key} full table", expanded=False):
        st.dataframe(style_frame(presentation_frame(filtered)), width="stretch", hide_index=True)


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


def render_overview(
    output_frames: dict[str, tuple[pd.DataFrame | None, str | None]],
    catalog: LocalDataCatalog,
    universe_summary: dict[str, Any],
    project_status_payload: dict[str, Any] | None,
) -> None:
    holdings = catalog.load_dataframe("holdings")
    market_direction_frame, _ = output_frames.get("market_direction.csv", (None, None))
    final_watchlist_frame, _ = output_frames.get("final_watchlist.csv", (None, None))
    price_status_frame, _ = load_price_update_status()
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
    action_queue_frame, _ = load_action_queue()
    queue_summary = action_queue_summary(action_queue_frame)
    health_score, health_label = workflow_health_score(queue_summary, health_summary)
    onboarding_tables = load_data_onboarding_tables()
    wizard_frame, _ = onboarding_tables["data_coverage_wizard.csv"]
    ticker_unlock_ladder_frame, _ = onboarding_tables["ticker_unlock_ladder.csv"]
    unlock_priority_summary_frame, _ = onboarding_tables["unlock_priority_summary.csv"]
    latest_price = _latest_local_price_date(catalog)
    watchlist_count = 0 if final_watchlist_frame is None else len(final_watchlist_frame)
    monthly_frame, _ = load_output(OUTPUTS_DIR / "monthly_research_picks.csv")
    monthly_count = 0 if monthly_frame is None else len(monthly_frame)

    render_section_header(
        "Overview",
        "A quick read on whether the local research workflow is ready, partial, or waiting on data.",
    )
    st.markdown(project_status_cockpit_html(project_status_payload, health_score, health_label), unsafe_allow_html=True)
    render_signal_cards(
        overview_landing_cards(
            project_status_payload,
            queue_summary,
            latest_price,
            watchlist_count,
            monthly_count,
        )
    )
    render_section_header("Holdings First", "Blocked portfolio names and the next local unlock stage before broader universe work.")
    render_signal_cards(holdings_unlock_cards(holdings, ticker_unlock_ladder_frame, unlock_priority_summary_frame))
    render_section_header("Theme First", "Which local themes or sector ETF clusters unlock the most research value next.")
    render_signal_cards(theme_unlock_cards(unlock_priority_summary_frame))
    render_section_header("Market Context", "The strongest locally supported theme and ETF context from current benchmark-relative output rows.")
    render_signal_cards(overview_market_context_cards(market_direction_frame))
    render_section_header("Benchmark Pressure", "Whether weak coverage is mostly a local price-history issue or a broader benchmark-relative context issue.")
    render_signal_cards(overview_benchmark_pressure_cards(market_direction_frame, price_status_frame, project_status_payload))
    render_section_header("Best Next Commands", "A few repo-native commands that best match the current local blockers and verification state.")
    render_signal_cards(overview_next_command_cards(project_status_payload, action_queue_frame))
    render_metric_cards(
        [
            ("Workflow Health", f"{health_score}/100", health_label),
            ("Universe", current_universe["row_count"], "Tickers in data/universe.csv"),
            ("Holdings", 0 if holdings is None or holdings.empty else len(holdings), "Rows in holdings.csv"),
            ("Final Watchlist", watchlist_count, "Current state-machine rows"),
            ("Latest Price", latest_price, "From local prices.csv"),
            ("DCF Ready", _dcf_ready_count(catalog), "Enough local fields for DCF path"),
            ("Peer Ready", _peer_ready_count(catalog), "Local peer mapping + peer context"),
            ("Research Ready", health_summary["research_ready"], "Data Quality Wizard rows"),
            ("Critical Actions", queue_summary["critical"], "Highest-priority remediation items"),
        ]
    )

    st.markdown(
        (
            "<div class='subtle-panel'>"
            f"<strong>Coverage snapshot.</strong> {output_file_count} generated outputs are present. "
            f"{missing_warning_count} names still carry explicit missing-data warnings, "
            f"{health_summary['thin_liquidity']} tickers look thin on local liquidity context, and "
            f"{health_summary['high_correlation']} tickers show high local co-movement."
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    status_cards = project_status_metric_cards(project_status_payload)
    if status_cards:
        render_section_header(
            "Project Status",
            "The same read-only snapshot shown by `make status`, surfaced here so the dashboard and terminal agree.",
        )
        render_metric_cards(status_cards)
        command_rows = project_status_command_rows(project_status_payload)
        if command_rows:
            with st.expander("Recommended next commands", expanded=False):
                st.dataframe(pd.DataFrame(command_rows), width="stretch", hide_index=True)

    render_section_header("Next Data Unlocks", "The next local data unlocks for richer research output.")
    render_signal_cards(data_coverage_wizard_cards(wizard_frame))

    priority_signals = top_priority_signals(action_queue_frame, limit=3)
    if priority_signals:
        render_section_header("Priority Now", "The fastest way to improve the local research workflow today.")
        render_signal_cards(priority_signals)
    else:
        actions: list[tuple[str, str, str, str]] = project_status_action_cards(project_status_payload)
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
    with st.expander("Generated output files", expanded=False):
        st.dataframe(pd.DataFrame(output_rows), width="stretch", hide_index=True)

    if final_watchlist_frame is not None and not final_watchlist_frame.empty:
        render_section_header("Final Watchlist Snapshot", "Top-level state and reason context without opening the full table.")
        snapshot_columns = [column for column in ["Ticker", "FinalState", "SetupStatus", "FinalValueCategory", "WatchlistRank", "RankReason", "Reason"] if column in final_watchlist_frame.columns]
        st.dataframe(clean_display_frame(final_watchlist_frame[snapshot_columns].head(8)), width="stretch", hide_index=True)
        with st.expander("Full final watchlist snapshot", expanded=False):
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
    universe_count = 0 if universe is None or universe.empty else len(universe)
    candidate_count = 0 if picks_frame is None else len(picks_frame)
    action_queue_frame, _ = load_action_queue()
    render_signal_cards(
        monthly_picks_landing_cards(
            picks_frame,
            track_frame,
            equity_frame,
            top_n,
            latest_price,
            universe_count,
        )
    )

    render_metric_cards(
        [
            ("Candidates", f"{candidate_count} of {top_n}", "Conservative filters may return fewer"),
            ("Current Month", "Not generated" if picks_frame is None or picks_frame.empty else picks_frame.iloc[0].get("Month", "Not available"), "Generated from local outputs"),
            ("Benchmark", "SPY", "For local track-record comparison"),
            ("Universe", universe_count, "Current local universe size"),
            ("Latest Price", latest_price, "From data/prices.csv"),
        ]
    )

    if picks_frame is None:
        render_notice_card(
            "Monthly picks are not generated yet",
            picks_message or "Generate the local candidate list after refreshing pipeline outputs. This stays research-only and may return fewer than five names.",
            "python3 -m src.monthly_picks --generate --top-n 5",
        )
    elif picks_frame.empty:
        render_notice_card(
            "No monthly candidates passed the current filters",
            "The output exists, but the conservative scoring rules did not find supported local candidates. Improve price/fundamental coverage before broadening interpretation.",
            "make onboarding",
            tone="warning",
        )
    else:
        st.info(monthly_pick_availability_message(candidate_count, top_n))
        if candidate_count < top_n:
            st.warning(
                "The candidate list is intentionally shorter than the configured top count because the current local data "
                "or conservative filters did not support filling the remaining slots."
            )
        priority_signals = top_priority_signals(action_queue_frame, limit=2)
        if priority_signals:
            render_signal_cards(priority_signals)
        render_section_header("Research Candidates", "Ranked research candidates, not buy/sell instructions.")
        ordered_picks = picks_frame.sort_values(["Rank", "CompositeScore"], ascending=[True, False])
        st.markdown(
            "<div class='pick-grid'>"
            + "".join(monthly_pick_card_html(row) for _, row in ordered_picks.iterrows())
            + "</div>",
            unsafe_allow_html=True,
        )
        score_chart_frame = monthly_pick_score_chart_frame(ordered_picks)
        if not score_chart_frame.empty:
            render_chart_panel(
                "Score context",
                "This chart compares transparent local score components for the current candidate set. Missing components stay blank instead of being inferred.",
                score_chart_frame,
                chart_kind="bar",
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
        render_chart_panel(
            "Equity curve",
            "Compares the locally calculated monthly picks equity curve against the benchmark only when enough local price history exists.",
            chart_frame,
            chart_kind="line",
        )
    else:
        render_notice_card(
            "Track record needs more local history",
            track_record_status_message(track_frame, equity_frame),
            "python3 -m src.track_record --monthly-picks",
        )
    if track_frame is not None and not track_frame.empty:
        st.dataframe(clean_display_frame(track_frame), width="stretch", hide_index=True)
    else:
        render_notice_card(
            "Track-record table is not available yet",
            "Run the track-record command after monthly picks exist. If local price history is short, the result will explain that instead of fabricating performance.",
            "python3 -m src.track_record --monthly-picks",
        )

    render_section_header("Archive", "Prior local monthly pick lists and returns when calculable.")
    if track_frame is not None and not track_frame.empty:
        archive_columns = [column for column in ["Month", "Picks", "AveragePickReturn", "BenchmarkReturn", "ExcessReturn", "Notes"] if column in track_frame.columns]
        st.dataframe(clean_display_frame(track_frame[archive_columns]), width="stretch", hide_index=True)
    else:
        render_notice_card(
            "No monthly archive yet",
            "The archive appears only after enough local monthly pick and price-history rows exist. Nothing is backfilled or invented.",
            "python3 -m src.track_record --monthly-picks",
        )

    with st.expander("Methodology", expanded=False):
        st.write("Monthly rankings use local screener outputs, local price history, optional local fundamentals, and transparent score components.")
        st.write("Missing inputs reduce confidence and remain visible in the output.")
        st.write("Track-record files are calculated only from local historical price data; insufficient history is shown explicitly.")


def render_output_tab(title: str, output_frames: dict[str, tuple[pd.DataFrame | None, str | None]], show_reason_details: bool) -> None:
    filename = TAB_TO_FILE[title]
    frame, message = output_frames[filename]
    render_section_header(title, OUTPUT_TAB_GUIDANCE.get(title, "Search, filter, and inspect the most important columns first."))
    if message and frame is None:
        render_notice_card(
            f"{title} output is not available yet",
            message,
            "python3 -m src.report_generator",
        )
        return
    if message and frame is not None:
        render_notice_card(f"{title} output note", message, "python3 -m src.report_generator")
    if frame is None:
        return
    render_signal_cards(output_tab_summary_cards(title, frame))
    for section_title, description, chart_frame, chart_kind in output_tab_chart_sections(title, frame):
        render_chart_panel(section_title, description, chart_frame, chart_kind=chart_kind)
    render_table(frame, title.lower().replace(" ", "-"), show_reason_details)


def render_stock_report_beta(provider, show_raw_json: bool) -> None:
    render_section_header(
        "Stock Report Beta",
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
        peer_summary = provider.get_peer_summary(ticker)
        render_context_note(
            "Local coverage.",
            "Dataset readiness for the selected ticker based on local CSV availability and schema validation.",
        )
        render_signal_cards(stock_report_local_context_cards(coverage, peer_summary))
        st.dataframe(style_frame(clean_display_frame(ticker_coverage_display_frame(coverage))), width="stretch", hide_index=True)
        with st.expander("Full local coverage details", expanded=False):
            st.dataframe(clean_display_frame(coverage), width="stretch", hide_index=True)
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
                history = chosen_provider.get_price_history(ticker, period="1y", interval="1d")
                st.session_state["stock_report_beta_payload"] = report.to_dict()
                st.session_state["stock_report_beta_download"] = export_stock_report_json(report)
                st.session_state["stock_report_beta_ticker"] = ticker
                st.session_state["stock_report_beta_provider"] = provider_name
                st.session_state["stock_report_beta_history"] = history
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
    render_section_header(
        f"{format_missing(report_payload.get('ticker'), 'Selected ticker')} Report",
        "A structured view of local research inputs. This is context only, not a trading instruction.",
    )
    render_signal_cards(stock_report_summary_cards(report_payload))
    st.markdown(
        "<div style='display:flex;gap:0.5rem;flex-wrap:wrap;margin:0.5rem 0 1rem 0;'>"
        + "".join(status_badge(label) for label in stock_report_readiness_badges(readiness))
        + "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(stock_report_brief_html(report_payload), unsafe_allow_html=True)

    price = report_payload["price_snapshot"]
    performance = report_payload["performance"]
    financials = report_payload["financial_summary"]
    valuation = report_payload["valuation_snapshot"]
    relative = valuation["relative_valuation"]

    snapshot_tab, valuation_tab, earnings_tab, sources_tab = st.tabs(
        ["Snapshot", "Valuation", "Earnings / Estimates", "Sources & Gaps"]
    )

    with snapshot_tab:
        render_context_note("Snapshot view.", "Price, performance, and local financial context appear here first so you can confirm basic coverage before reading valuation detail.")
        price_columns = st.columns(3)
        price_columns[0].metric("Last Price", report_display_value(price.get("price"), "currency"))
        price_columns[1].metric("Previous Close", report_display_value(price.get("previous_close"), "currency"))
        price_columns[2].metric("Volume", report_display_value(price.get("volume"), "integer"))
        history_chart = stock_report_price_chart_frame(st.session_state.get("stock_report_beta_history"))
        if not history_chart.empty:
            render_chart_panel(
                "Price history chart",
                "Shows the selected provider's daily close history for up to one year. Short local history stays visible instead of being padded or backfilled.",
                history_chart,
                chart_kind="line",
            )
            if len(history_chart) < 60:
                render_context_note(
                    "Short history.",
                    f"Only {len(history_chart)} daily rows are available for this chart. Longer local history improves trend and track-record context.",
                    tone="warning",
                )
        else:
            render_notice_card(
                "Price chart not available yet",
                "The report generated, but there is not enough provider-backed daily close history to render a chart. Add verified local prices or retry with an explicitly enabled research-grade provider.",
                "make price-refresh",
                tone="warning",
            )

        performance_columns = st.columns(3)
        performance_columns[0].metric("1M Return", report_display_value(performance.get("one_month"), "percent"))
        performance_columns[1].metric("3M Return", report_display_value(performance.get("three_month"), "percent"))
        performance_columns[2].metric("1Y Return", report_display_value(performance.get("one_year"), "percent"))

        st.markdown("#### Technical Context")
        render_context_note(
            "Technical context.",
            "These fields come from the current local momentum and watchlist outputs. They summarize setup quality and trend context without implying a buy or sell action.",
        )
        render_signal_cards(stock_report_technical_context_cards(report_payload))
        st.dataframe(
            clean_display_frame(stock_report_technical_context_frame(report_payload)),
            width="stretch",
            hide_index=True,
        )

        st.markdown("#### Financial Context")
        financial_fields = [
            ("revenue", "Revenue", "number"),
            ("revenue_growth", "Revenue Growth", "percent"),
            ("eps", "EPS", "number"),
            ("operating_margin", "Operating Margin", "percent"),
            ("profit_margin", "Profit Margin", "percent"),
            ("free_cash_flow", "Free Cash Flow", "number"),
            ("fcf_margin", "FCF Margin", "percent"),
            ("cash", "Cash", "number"),
            ("debt", "Debt", "number"),
            ("shares_outstanding", "Shares Outstanding", "integer"),
        ]
        st.dataframe(
            clean_display_frame(stock_report_key_value_frame(financials, financial_fields)),
            width="stretch",
            hide_index=True,
        )

        with st.expander("Price snapshot detail", expanded=False):
            st.dataframe(stock_report_detail_frame(price), width="stretch", hide_index=True)

    with valuation_tab:
        base_dcf = valuation["dcf_result"]
        render_context_note("Valuation view.", "DCF, peer-relative context, and sensitivity stay informational only. Missing assumptions remain visible instead of being guessed.")
        valuation_columns = st.columns(4)
        valuation_columns[0].metric("Valuation Status", format_missing(valuation.get("status")))
        valuation_columns[1].metric("Coverage", format_missing(valuation.get("coverage")))
        valuation_columns[2].metric("DCF Status", format_missing(base_dcf.get("status")))
        valuation_columns[3].metric(
            "Base Fair Value / Share",
            report_display_value(base_dcf.get("fair_value_per_share"), "currency"),
        )
        if base_dcf.get("fair_value_per_share") is None:
            st.info("Per-share DCF output is unavailable with the current local inputs. Missing fields remain visible below.")

        scenario_rows = []
        for scenario in valuation.get("scenarios", []):
            result = scenario["dcf_result"]
            assumptions = scenario["assumptions"]
            scenario_rows.append(
                {
                    "Scenario": scenario["name"],
                    "Status": result["status"],
                    "Revenue Growth": report_display_value(assumptions.get("revenue_growth"), "percent"),
                    "FCF Margin": report_display_value(assumptions.get("fcf_margin"), "percent"),
                    "WACC": report_display_value(assumptions.get("wacc"), "percent"),
                    "Terminal Growth": report_display_value(assumptions.get("terminal_growth"), "percent"),
                    "Fair Value / Share": report_display_value(result.get("fair_value_per_share"), "currency"),
                }
            )
        if scenario_rows:
            st.markdown("#### Bull / Base / Bear Scenarios")
            st.dataframe(pd.DataFrame(scenario_rows), width="stretch", hide_index=True)

        st.markdown("#### Peer-Relative Valuation")
        peer_columns = st.columns(4)
        peer_columns[0].metric("Peer Status", format_missing(relative.get("status")))
        peer_columns[1].metric("Peer Group", format_missing(relative.get("peer_group"), "Not configured"))
        peer_columns[2].metric("Peer Count", report_display_value(relative.get("peer_count"), "integer"))
        peer_columns[3].metric(
            "Relative Score",
            report_display_value(relative.get("relative_opportunity_score"), "number"),
        )
        st.markdown(status_badge(relative.get("peer_relative_status", "insufficient_peer_data")), unsafe_allow_html=True)

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
                    "Subject": report_display_value(subject, "number"),
                    "Peer Median": report_display_value(peer_median, "number"),
                    "Discount / Premium": report_display_value(discount, "percent"),
                }
            )
        if comparison_rows:
            st.dataframe(pd.DataFrame(comparison_rows), width="stretch", hide_index=True)
        else:
            st.info("Peer-relative multiples are unavailable until local peers and peer fundamentals/prices are present.")

        sensitivity = valuation["sensitivity_table"]
        if sensitivity["status"] == "calculated" and sensitivity["fair_value_grid"]:
            with st.expander("DCF sensitivity table", expanded=False):
                sensitivity_frame = pd.DataFrame(
                    sensitivity["fair_value_grid"],
                    index=[f"WACC {value:.1%}" for value in sensitivity["wacc_values"]],
                    columns=[f"TG {value:.1%}" for value in sensitivity["terminal_growth_values"]],
                )
                st.dataframe(sensitivity_frame, width="stretch")

        with st.expander("Valuation warnings and methodology notes", expanded=False):
            st.dataframe(stock_report_notes_frame(valuation, relative), width="stretch", hide_index=True)

    with earnings_tab:
        earnings = report_payload["earnings_summary"]
        estimates = report_payload["analyst_estimate_summary"]
        render_context_note("Optional context.", "Earnings and analyst estimates only appear when trusted local files exist. Missing files are safe and stay explicit.")
        earnings_col, estimates_col = st.columns(2)
        with earnings_col:
            st.markdown("#### Earnings")
            earnings_fields = [
                ("next_earnings_date", "Next Earnings Date", "date"),
                ("last_earnings_date", "Last Earnings Date", "date"),
                ("fiscal_period", "Fiscal Period", "number"),
                ("eps_estimate", "EPS Estimate", "number"),
                ("eps_actual", "EPS Actual", "number"),
                ("revenue_estimate", "Revenue Estimate", "number"),
                ("revenue_actual", "Revenue Actual", "number"),
                ("surprise_pct", "Surprise", "percent"),
            ]
            st.dataframe(clean_display_frame(stock_report_key_value_frame(earnings, earnings_fields)), width="stretch", hide_index=True)
            with st.expander("Earnings detail", expanded=False):
                st.dataframe(stock_report_detail_frame(earnings), width="stretch", hide_index=True)
        with estimates_col:
            st.markdown("#### Analyst Estimates")
            estimate_fields = [
                ("current_quarter_eps", "Current Quarter EPS", "number"),
                ("next_quarter_eps", "Next Quarter EPS", "number"),
                ("current_year_eps", "Current Year EPS", "number"),
                ("next_year_eps", "Next Year EPS", "number"),
                ("target_mean_price", "Target Mean Price", "currency"),
                ("target_high_price", "Target High Price", "currency"),
                ("target_low_price", "Target Low Price", "currency"),
                ("revision_trend", "Revision Trend", "number"),
            ]
            st.dataframe(clean_display_frame(stock_report_key_value_frame(estimates, estimate_fields)), width="stretch", hide_index=True)
            with st.expander("Analyst estimate detail", expanded=False):
                st.dataframe(stock_report_detail_frame(estimates), width="stretch", hide_index=True)

    with sources_tab:
        render_context_note("Source and gaps.", "Use this tab to verify freshness, missing inputs, and how much of the report is based on local coverage versus unavailable optional files.")
        st.markdown("#### Missing Data")
        warning_text = stock_report_missing_data_text(report_payload.get("missing_data_warnings", []))
        if report_payload.get("missing_data_warnings"):
            st.warning(warning_text)
        else:
            st.success(warning_text)

        st.markdown("#### Source / Freshness")
        st.dataframe(
            clean_display_frame(stock_report_source_frame(report_payload.get("data_freshness", []))),
            width="stretch",
            hide_index=True,
        )

        if report_payload.get("screener_context"):
            with st.expander("Existing screener context", expanded=False):
                st.dataframe(stock_report_detail_frame(report_payload["screener_context"]), width="stretch", hide_index=True)

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
    action_queue_frame, action_queue_message = load_action_queue()
    health_tables = load_research_health_tables()
    data_quality_frame, data_quality_message = health_tables["data_quality_wizard.csv"]
    liquidity_frame, liquidity_message = health_tables["liquidity_risk.csv"]
    correlation_frame, correlation_message = health_tables["correlation_risk.csv"]
    source_tables = load_data_source_status_tables()
    status_frame, status_message = source_tables["data_source_status.csv"]
    gap_frame, gap_message = source_tables["data_gap_report.csv"]
    price_status_frame, price_status_message = load_price_update_status()
    onboarding_tables = load_data_onboarding_tables()
    coverage_frame, coverage_message = onboarding_tables["ticker_data_coverage.csv"]
    actions_frame, actions_message = onboarding_tables["data_onboarding_actions.csv"]
    wizard_frame, wizard_message = onboarding_tables["data_coverage_wizard.csv"]
    price_worklist_frame, price_worklist_message = onboarding_tables["price_import_worklist.csv"]
    fundamentals_peer_worklist_frame, fundamentals_peer_worklist_message = onboarding_tables["fundamentals_peer_worklist.csv"]
    optional_context_worklist_frame, optional_context_worklist_message = onboarding_tables["optional_context_worklist.csv"]
    ticker_unlock_ladder_frame, ticker_unlock_ladder_message = onboarding_tables["ticker_unlock_ladder.csv"]
    unlock_priority_summary_frame, unlock_priority_summary_message = onboarding_tables["unlock_priority_summary.csv"]
    staged_imports = validate_imports(base_dir=BASE_DIR)
    universe_summary = summarize_universe_manager(BASE_DIR)
    staged_universe = universe_summary["staged_universe"]

    render_signal_cards(data_health_overview_cards(validation_rows, price_status_frame, action_queue_frame, coverage_frame))
    render_section_header("Next Data Unlocks", "What to unlock next for Monthly Picks, track record, DCF, and peer-relative research.")
    render_signal_cards(data_coverage_wizard_cards(wizard_frame))
    if wizard_frame is None:
        render_notice_card(
            "Coverage wizard has not been generated",
            wizard_message or "Generate the local data coverage wizard to see the next best coverage unlocks.",
            "python3 -m src.data_onboarding --write-output",
        )
    render_section_header("Priority Fixes", "Highest-priority local data actions. Apply/merge steps remain CLI-only and reviewable.")
    render_action_cards(data_health_fix_first_cards(actions_frame))

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
        with st.expander("Local dataset validation details", expanded=False):
            st.dataframe(clean_display_frame(validation_rows[display_columns]), width="stretch", hide_index=True)
    else:
        render_notice_card(
            "Local validation is not available yet",
            "Generate local validation rows to confirm which CSV datasets are present, partial, or missing before relying on broader outputs.",
            "python3 -m src.stock_report --validate-local-data",
            tone="warning",
        )

    health_tabs = st.tabs(["Actions", "Coverage", "Sources", "Price Refresh", "Staged Imports"])

    with health_tabs[0]:
        render_signal_cards(
            data_health_tab_summary_cards(
                "Actions",
                validation_rows,
                coverage_frame,
                status_frame,
                price_status_frame,
                staged_imports,
            )
        )
        if action_queue_frame is None:
            render_notice_card(
                "Action queue is not available yet",
                action_queue_message or "Generate the research action queue to surface priority price, fundamentals, peer, and onboarding tasks.",
                "python3 -m src.action_queue --write-output",
                tone="warning",
            )
        else:
            queue_summary = action_queue_summary(action_queue_frame)
            metric_cols = st.columns(3)
            metric_cols[0].metric("Critical", queue_summary["critical"])
            metric_cols[1].metric("High", queue_summary["high"])
            metric_cols[2].metric("Medium", queue_summary["medium"])
            render_signal_cards(top_priority_signals(action_queue_frame, limit=3))
            queue_columns = [
                column
                for column in [
                    "priority",
                    "urgency",
                    "action_type",
                    "ticker",
                    "title",
                    "recommended_action",
                    "example_command",
                    "reason",
                ]
                if column in action_queue_frame.columns
            ]
            st.dataframe(clean_display_frame(action_queue_frame[queue_columns].head(15)), width="stretch", hide_index=True)

    with health_tabs[1]:
        render_signal_cards(
            data_health_tab_summary_cards(
                "Coverage",
                validation_rows,
                coverage_frame,
                status_frame,
                price_status_frame,
                staged_imports,
            )
        )
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

            if coverage_frame is not None and not coverage_frame.empty:
                summary = summarize_ticker_coverage(coverage_frame)
                metric_cols = st.columns(4)
                metric_cols[0].metric("Usable Price Data", summary["usable_price_tickers"])
                metric_cols[1].metric("DCF Ready", summary["dcf_ready_tickers"])
                metric_cols[2].metric("Peer Ready", summary["peer_ready_tickers"])
                metric_cols[3].metric("Only Optional Gaps", summary["optional_only_missing_tickers"])
            if price_worklist_frame is not None and not price_worklist_frame.empty:
                worklist_summary = summarize_price_worklist(price_worklist_frame)
                metric_cols = st.columns(4)
                metric_cols[0].metric("Momentum Ready", worklist_summary["momentum_ready"])
                metric_cols[1].metric("Track Record Ready", worklist_summary["track_record_ready"])
                metric_cols[2].metric("1Y History Ready", worklist_summary["preferred_history_ready"])
                metric_cols[3].metric("Urgent Price Gaps", worklist_summary["priority_1"])
            if fundamentals_peer_worklist_frame is not None and not fundamentals_peer_worklist_frame.empty:
                fp_summary = summarize_fundamentals_peer_worklist(fundamentals_peer_worklist_frame)
                metric_cols = st.columns(4)
                metric_cols[0].metric("DCF Ready", fp_summary["dcf_ready"])
                metric_cols[1].metric("Peer Ready", fp_summary["peer_ready"])
                metric_cols[2].metric("Need Fundamentals", fp_summary["fundamentals_priority_1"])
                metric_cols[3].metric("Need Peer Context", fp_summary["peer_priority_2"])
            if optional_context_worklist_frame is not None and not optional_context_worklist_frame.empty:
                oc_summary = summarize_optional_context_worklist(optional_context_worklist_frame)
                metric_cols = st.columns(4)
                metric_cols[0].metric("Earnings Ready", oc_summary["earnings_ready"])
                metric_cols[1].metric("Estimates Ready", oc_summary["estimates_ready"])
                metric_cols[2].metric("Missing Both Optional", oc_summary["missing_both"])
                metric_cols[3].metric("Missing One Optional", oc_summary["missing_one"])
            if ticker_unlock_ladder_frame is not None and not ticker_unlock_ladder_frame.empty:
                ladder_summary = summarize_ticker_unlock_ladder(ticker_unlock_ladder_frame)
                metric_cols = st.columns(5)
                metric_cols[0].metric("Need Prices", ladder_summary["price_stage"])
                metric_cols[1].metric("Need Fundamentals", ladder_summary["fundamentals_stage"])
                metric_cols[2].metric("Need Peers", ladder_summary["peer_stage"])
                metric_cols[3].metric("Need Optional Context", ladder_summary["optional_stage"])
                metric_cols[4].metric("Coverage Ready", ladder_summary["ready_stage"])
            if unlock_priority_summary_frame is not None and not unlock_priority_summary_frame.empty:
                summary = summarize_unlock_priority_summary(unlock_priority_summary_frame)
                metric_cols = st.columns(5)
                metric_cols[0].metric("Holdings Groups", summary["holdings_groups"])
                metric_cols[1].metric("Theme Groups", summary["theme_groups"])
                metric_cols[2].metric("Sector ETF Groups", summary["sector_groups"])
                metric_cols[3].metric("Price-Led Groups", summary["price_led_groups"])
                metric_cols[4].metric("Fundamentals-Led Groups", summary["fundamentals_led_groups"])

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

            if actions_frame is not None and not actions_frame.empty:
                with st.expander("Top Onboarding Actions", expanded=False):
                    top_actions = actions_frame.sort_values(["priority", "ticker", "dataset"], na_position="last").head(10)
                    action_columns = [
                        column
                        for column in ["priority", "ticker", "dataset", "status", "reason", "recommended_action", "target_file"]
                        if column in top_actions.columns
                    ]
                    st.dataframe(clean_display_frame(top_actions[action_columns]), width="stretch", hide_index=True)
            elif actions_message:
                st.info(actions_message)

            if wizard_frame is not None and not wizard_frame.empty:
                with st.expander("Data Coverage Wizard Rows", expanded=False):
                    wizard_columns = [
                        column
                        for column in [
                            "priority",
                            "ticker",
                            "unlock_goal",
                            "blocking_dataset",
                            "current_status",
                            "recommended_action",
                            "safe_next_step",
                        ]
                        if column in wizard_frame.columns
                    ]
                    st.dataframe(clean_display_frame(wizard_frame[wizard_columns].head(20)), width="stretch", hide_index=True)
            if price_worklist_frame is not None and not price_worklist_frame.empty:
                with st.expander("Price Import Worklist", expanded=False):
                    worklist_columns = [
                        column
                        for column in [
                            "priority",
                            "ticker",
                            "price_history_days",
                            "first_local_date",
                            "latest_local_date",
                            "momentum_ready",
                            "track_record_ready",
                            "preferred_history_ready",
                            "missing_for_momentum",
                            "missing_for_track_record",
                            "missing_for_preferred_history",
                            "example_command",
                        ]
                        if column in price_worklist_frame.columns
                    ]
                    st.dataframe(clean_display_frame(price_worklist_frame[worklist_columns].head(20)), width="stretch", hide_index=True)
            if fundamentals_peer_worklist_frame is not None and not fundamentals_peer_worklist_frame.empty:
                with st.expander("Fundamentals / Peer Worklist", expanded=False):
                    fp_columns = [
                        column
                        for column in [
                            "priority",
                            "ticker",
                            "has_fundamentals",
                            "dcf_ready",
                            "has_peer_mapping",
                            "peer_ready",
                            "missing_required_for_dcf",
                            "missing_required_for_peer_relative",
                            "example_command",
                        ]
                        if column in fundamentals_peer_worklist_frame.columns
                    ]
                    st.dataframe(clean_display_frame(fundamentals_peer_worklist_frame[fp_columns].head(20)), width="stretch", hide_index=True)
            if optional_context_worklist_frame is not None and not optional_context_worklist_frame.empty:
                with st.expander("Optional Context Worklist", expanded=False):
                    oc_columns = [
                        column
                        for column in [
                            "priority",
                            "ticker",
                            "has_earnings",
                            "has_analyst_estimates",
                            "missing_optional_context",
                            "recommended_action",
                            "example_command",
                        ]
                        if column in optional_context_worklist_frame.columns
                    ]
                    st.dataframe(clean_display_frame(optional_context_worklist_frame[oc_columns].head(20)), width="stretch", hide_index=True)
            if ticker_unlock_ladder_frame is not None and not ticker_unlock_ladder_frame.empty:
                with st.expander("Ticker Unlock Ladder", expanded=False):
                    ladder_columns = [
                        column
                        for column in [
                            "ticker",
                            "current_unlock_stage",
                            "next_unlock_goal",
                            "price_stage_status",
                            "dcf_stage_status",
                            "peer_stage_status",
                            "optional_context_status",
                            "example_command",
                        ]
                        if column in ticker_unlock_ladder_frame.columns
                    ]
                    st.dataframe(clean_display_frame(ticker_unlock_ladder_frame[ladder_columns].head(20)), width="stretch", hide_index=True)
            if unlock_priority_summary_frame is not None and not unlock_priority_summary_frame.empty:
                with st.expander("Unlock Priority Summary", expanded=False):
                    summary_columns = [
                        column
                        for column in [
                            "group_type",
                            "group_name",
                            "ticker_count",
                            "holdings_count",
                            "top_priority_stage",
                            "next_unlock_goal",
                            "representative_tickers",
                            "recommended_action",
                        ]
                        if column in unlock_priority_summary_frame.columns
                    ]
                    st.dataframe(clean_display_frame(unlock_priority_summary_frame[summary_columns].head(20)), width="stretch", hide_index=True)

    with health_tabs[2]:
        render_signal_cards(
            data_health_tab_summary_cards(
                "Sources",
                validation_rows,
                coverage_frame,
                status_frame,
                price_status_frame,
                staged_imports,
            )
        )
        if status_frame is None and gap_frame is None:
            render_notice_card(
                "Data source status is not generated yet",
                "Build the local source registry so this tab can show what is available, partial, manual-only, or missing.",
                "python3 -m src.data_sources --write-output",
                tone="warning",
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
                render_notice_card(
                    "No data source status rows are available",
                    status_message or "Generate the local source registry to inspect dataset availability and fallback actions.",
                    "python3 -m src.data_sources --write-output",
                    tone="warning",
                )
            if gap_frame is not None and not gap_frame.empty:
                with st.expander("Data Gap Report", expanded=False):
                    display_gaps = gap_frame.copy()
                    if "status" in display_gaps.columns:
                        display_gaps["status"] = display_gaps["status"].map(friendly_data_source_status)
                    st.dataframe(clean_display_frame(display_gaps), width="stretch", hide_index=True)
            else:
                render_notice_card(
                    "No data gaps were reported",
                    gap_message or "Either the local gap report has not been generated yet or there are currently no explicit source-gap rows to show.",
                    "python3 -m src.data_sources --write-output",
                )

    with health_tabs[3]:
        render_signal_cards(
            data_health_tab_summary_cards(
                "Price Refresh",
                validation_rows,
                coverage_frame,
                status_frame,
                price_status_frame,
                staged_imports,
            )
        )
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
            render_context_note(
                "Manual fallback.",
                "CLI-only: fill data/imports/prices.csv with verified OHLCV rows, then run make price-validate, make price-preview, and make price-apply.",
                tone="warning",
            )
        if price_worklist_frame is not None and not price_worklist_frame.empty:
            render_context_note(
                "Price history worklist.",
                "This local worklist shows which tickers still need more verified history for momentum, track record, or preferred long-history research context.",
            )
            worklist_columns = [
                column
                for column in [
                    "priority",
                    "ticker",
                    "price_history_days",
                    "first_local_date",
                    "latest_local_date",
                    "missing_for_momentum",
                    "missing_for_track_record",
                    "missing_for_preferred_history",
                    "example_command",
                ]
                if column in price_worklist_frame.columns
            ]
            st.dataframe(clean_display_frame(price_worklist_frame[worklist_columns].head(15)), width="stretch", hide_index=True)
        else:
            render_notice_card(
                "Price history worklist is not available yet",
                price_worklist_message
                or "Generate the onboarding outputs to see exact local price-history gaps and the safe manual-import path.",
                "python3 -m src.data_onboarding --write-output",
                tone="warning",
            )
        if fundamentals_peer_worklist_frame is not None and not fundamentals_peer_worklist_frame.empty:
            render_context_note(
                "Fundamentals and peer worklist.",
                "This local worklist shows which tickers are blocked on SEC-stageable fundamentals versus manual peer mappings and peer context.",
            )
            fp_columns = [
                column
                for column in [
                    "priority",
                    "ticker",
                    "has_fundamentals",
                    "dcf_ready",
                    "has_peer_mapping",
                    "peer_ready",
                    "missing_required_for_dcf",
                    "missing_required_for_peer_relative",
                    "example_command",
                ]
                if column in fundamentals_peer_worklist_frame.columns
            ]
            st.dataframe(clean_display_frame(fundamentals_peer_worklist_frame[fp_columns].head(15)), width="stretch", hide_index=True)
        else:
            render_notice_card(
                "Fundamentals and peer worklist is not available yet",
                fundamentals_peer_worklist_message
                or "Generate the onboarding outputs to see which tickers still need SEC fundamentals or manual peer mappings.",
                "python3 -m src.data_onboarding --write-output",
                tone="warning",
            )
        if optional_context_worklist_frame is not None and not optional_context_worklist_frame.empty:
            render_context_note(
                "Optional context worklist.",
                "This queue keeps optional earnings and analyst-estimate enrichment explicit and lower priority than prices, fundamentals, and peers.",
            )
            oc_columns = [
                column
                for column in [
                    "priority",
                    "ticker",
                    "has_earnings",
                    "has_analyst_estimates",
                    "missing_optional_context",
                    "recommended_action",
                    "example_command",
                ]
                if column in optional_context_worklist_frame.columns
            ]
            st.dataframe(clean_display_frame(optional_context_worklist_frame[oc_columns].head(15)), width="stretch", hide_index=True)
        else:
            render_notice_card(
                "Optional context worklist is not available yet",
                optional_context_worklist_message
                or "Generate the onboarding outputs to see which tickers still have optional earnings or analyst-estimate gaps.",
                "python3 -m src.data_onboarding --write-output",
                tone="warning",
            )
        if ticker_unlock_ladder_frame is not None and not ticker_unlock_ladder_frame.empty:
            render_context_note(
                "Ticker unlock ladder.",
                "This single table combines prices, DCF, peer-relative, and optional context into one next-step ladder per ticker.",
            )
            ladder_columns = [
                column
                for column in [
                    "ticker",
                    "current_unlock_stage",
                    "next_unlock_goal",
                    "recommended_action",
                    "target_file",
                    "example_command",
                ]
                if column in ticker_unlock_ladder_frame.columns
            ]
            st.dataframe(clean_display_frame(ticker_unlock_ladder_frame[ladder_columns].head(15)), width="stretch", hide_index=True)
        else:
            render_notice_card(
                "Ticker unlock ladder is not available yet",
                ticker_unlock_ladder_message
                or "Generate the onboarding outputs to see the next per-ticker local data unlock stage.",
                "python3 -m src.data_onboarding --write-output",
                tone="warning",
            )
        if unlock_priority_summary_frame is not None and not unlock_priority_summary_frame.empty:
            render_context_note(
                "Unlock priority summary.",
                "This grouped summary rolls the ticker ladders up by holdings, theme, and sector ETF so you can unlock the most research value first.",
            )
            summary_columns = [
                column
                for column in [
                    "group_type",
                    "group_name",
                    "ticker_count",
                    "holdings_count",
                    "top_priority_stage",
                    "next_unlock_goal",
                    "representative_tickers",
                ]
                if column in unlock_priority_summary_frame.columns
            ]
            st.dataframe(clean_display_frame(unlock_priority_summary_frame[summary_columns].head(15)), width="stretch", hide_index=True)
        else:
            render_notice_card(
                "Unlock priority summary is not available yet",
                unlock_priority_summary_message
                or "Generate the onboarding outputs to see grouped unlock priorities by holdings, theme, and sector ETF.",
                "python3 -m src.data_onboarding --write-output",
                tone="warning",
            )

    with health_tabs[4]:
        render_signal_cards(
            data_health_tab_summary_cards(
                "Staged Imports",
                validation_rows,
                coverage_frame,
                status_frame,
                price_status_frame,
                staged_imports,
            )
        )
        if staged_imports["status"] == "no_staged_files":
            render_notice_card(
                "No staged imports to review",
                staged_imports["warnings"][0],
                "make templates",
            )
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
                render_context_note("Preview only.", "Apply remains CLI-only for safer staged import review.")
                st.dataframe(pd.DataFrame(preview["preview"]), width="stretch", hide_index=True)

        st.markdown("#### Staged Universe Import")
        st.dataframe(staged_universe_status_frame(staged_universe), width="stretch", hide_index=True)
        with st.expander("Raw staged universe diagnostics", expanded=False):
            st.json(staged_universe, expanded=False)

        st.markdown("#### Runtime Artifact Hygiene")
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

    render_section_header("Universe Workflow", "Preview-first expansion status. The dashboard stays read-only for safer universe changes.")
    render_action_cards(universe_workflow_cards(universe_summary))

    render_signal_cards(
        [
            {
                "kicker": "CURRENT",
                "title": f"{current['row_count']} tickers",
                "body": f"{current['duplicate_ticker_count']} duplicate rows and {current['missing_theme_count'] + current['unclassified_theme_count']} missing or unclassified themes.",
                "badges": ["data/universe.csv"],
            },
            {
                "kicker": "STAGING",
                "title": "Staged file present" if staged.get("exists") else "No staged universe",
                "body": "Preview staged universe changes before applying. Dashboard stays read-only for safety.",
                "badges": ["data/imports/universe.csv"],
                "command": "python3 -m src.universe_builder --apply-import",
            },
            {
                "kicker": "WORKFLOW",
                "title": "Preview first",
                "body": "Use source presets to build a candidate universe, then apply only after reviewing the staged CSV.",
                "badges": ["CSV-first", "backup on apply"],
                "command": "make universe-preview",
            },
        ]
    )

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
    render_signal_cards(universe_preset_cards())
    preset_rows = [{"Preset": name, "Sources": ", ".join(sources)} for name, sources in SOURCE_PRESETS.items()]
    with st.expander("Preset source table", expanded=False):
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
        render_notice_card(
            "Current universe is empty",
            "Add or stage a local universe before running broader screening, monthly picks, or larger price refresh workflows.",
            "make universe-preview",
            tone="warning",
        )

    st.markdown("### Staged Universe Import Status")
    st.dataframe(staged_universe_status_frame(staged), width="stretch", hide_index=True)
    with st.expander("Raw staged universe diagnostics", expanded=False):
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
project_status_payload = build_project_status_payload(BASE_DIR, data_dir=DATA_DIR, output_dir=OUTPUTS_DIR, top_n=5)
render_app_header(catalog, output_frames)

with st.sidebar:
    st.header("Research Controls")
    show_reason_details = st.checkbox("Show reason expanders", value=True)
    show_raw_json = st.checkbox("Show raw report JSON expanders", value=False)
    st.divider()
    render_context_note(
        "Start here.",
        "Overview shows workflow health, Monthly Picks shows current candidates, Stock Report Beta handles single-name deep dives, and Data Health explains what local data is still missing.",
        tone="success",
    )
    render_action_cards(dashboard_navigation_cards())
    render_context_note("Safe local commands.", "These commands are read-only or preview-first by default.")
    st.code("make help\nmake verify\nmake onboarding\nmake daily\nmake dashboard", language="bash")
    render_context_note("Safety note.", "CLI-only applies remain the safest path for staged imports and universe changes.", tone="warning")
    with st.expander("How to read this dashboard", expanded=False):
        st.dataframe(pd.DataFrame(status_legend_rows()), width="stretch", hide_index=True)
    with st.expander("Missing-data recovery guide", expanded=False):
        st.dataframe(pd.DataFrame(missing_data_guide_rows()), width="stretch", hide_index=True)
    with st.expander("Workflow command guide", expanded=False):
        st.dataframe(pd.DataFrame(workflow_command_rows()), width="stretch", hide_index=True)
    with st.expander("Common empty states", expanded=False):
        st.dataframe(pd.DataFrame(empty_state_command_rows()), width="stretch", hide_index=True)
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

tabs = st.tabs(DASHBOARD_TAB_TITLES)

with tabs[0]:
    render_overview(output_frames, catalog, universe_summary, project_status_payload)
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
