from __future__ import annotations

import html
import os
import re
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.action_queue import write_action_queue_output
from src.data_onboarding import write_onboarding_outputs
from src.data_update import enrich_price_update_status_frame
from src.data_sources import write_data_source_outputs
from src.monthly_picks import build_monthly_research_picks
from src.monthly_picks import MonthlyPickConfig
from src.providers.local_data_catalog import LocalDataCatalog
from src.providers.local_importer import preview_import_merge, validate_imports
from src.report_generator import run as run_report_generator
from src.research_health import run as run_research_health
from src.paths import path_context
from src.project_status import build_project_status_payload
from src.stock_report import build_provider, build_stock_report, export_stock_report_json
from src.track_record import calculate_monthly_track_record
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
    "research_decisions.csv": "Research Decisions",
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
    "sec_stage_queue.csv": "SEC Stage Queue",
    "peer_mapping_queue.csv": "Peer Mapping Queue",
    "ticker_unlock_ladder.csv": "Ticker Unlock Ladder",
    "unlock_priority_summary.csv": "Unlock Priority Summary",
    "command_bundles.csv": "Command Bundles",
    "command_bundle_details.csv": "Command Bundle Details",
    "command_bundle_runbook.csv": "Command Bundle Runbook",
}
ACTION_QUEUE_FILE = "research_action_queue.csv"
RESEARCH_HEALTH_FILES = {
    "data_quality_wizard.csv": "Data Quality Wizard",
    "liquidity_risk.csv": "Liquidity Risk",
    "correlation_risk.csv": "Correlation Risk",
}
PRICE_STATUS_FILE = "price_update_status.csv"
DCF_READINESS_FILE = "dcf_readiness.csv"
EARNINGS_READINESS_FILE = "earnings_readiness.csv"
ANALYST_ESTIMATES_READINESS_FILE = "analyst_estimates_readiness.csv"
TICKER_READINESS_REPORT_FILE = "reports/ticker_readiness_report.csv"
FEATURE_READINESS_SUMMARY_FILE = "reports/feature_readiness_summary.csv"
PEER_READINESS_REPORT_FILE = "reports/peer_readiness_report.csv"
PEER_UNLOCK_WORKLIST_FILE = "peer_unlock_worklist.csv"
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
    "LiquidityScore": "Liquidity Score",
    "LiquidityInputsUsed": "Liquidity Inputs",
    "LiquidityBlindSpots": "Liquidity Blind Spots",
    "AvgDollarVolume20D": "Avg $ Volume 20D",
    "AvgVolume20D": "Avg Volume 20D",
    "VolumeTrend5DVs20D": "Volume Trend 5D vs 20D",
    "VolatilityProxy20D": "Volatility Proxy 20D",
    "CorrelationMethod": "Correlation Method",
    "ReturnType": "Return Type",
    "MostCorrelatedTicker": "Most Correlated Ticker",
    "OverlapDays": "Overlap Days",
    "MacroNarrativeCaution": "Macro Narrative Caution",
    "NextBestAction": "Next Best Action",
    "ExampleCommand": "Example Command",
    "credential_required": "Credential Required",
    "credential_present": "Credential Present",
    "manual_fallback_command": "Manual Fallback Command",
    "command_safety_note": "Command Safety Note",
    "DataQualityScore": "Data Quality Score",
    "MomentumReady": "Momentum Ready",
    "DCFReady": "DCF Ready",
    "PeerReady": "Peer Ready",
    "PriceHistoryDays": "Price History Days",
    "GoalSummary": "Goal Summary",
    "TargetGoal": "Target Goal",
    "RowsNeeded": "Rows Needed",
    "TargetHistoryRows": "Target History Rows",
    "SuggestedStartDate": "Suggested Start Date",
    "FallbackManualCommand": "Fallback Manual Command",
    "ExactNextCommand": "Exact Next Command",
    "FocusCommand": "Focus Command",
}


def load_output(path: Path) -> tuple[pd.DataFrame | None, str | None]:
    if not path.exists():
        return None, f"`{path.name}` has not been generated yet. Run `make verify` to regenerate local CSV outputs and validation artifacts first."
    try:
        frame = pd.read_csv(path)
    except Exception as exc:  # pragma: no cover - defensive UI path
        return None, f"Could not read `{path.name}`: {exc}"
    if frame.empty:
        return frame, f"`{path.name}` is present but currently empty."
    return frame, None


def load_pipeline_outputs(
    outputs_dir: Path = OUTPUTS_DIR,
) -> dict[str, tuple[pd.DataFrame | None, str | None]]:
    tables = {filename: load_output(outputs_dir / filename) for filename in PIPELINE_FILES}
    if any(frame is None for frame, _ in tables.values()):
        run_report_generator(BASE_DIR, output_dir=outputs_dir)
        tables = {filename: load_output(outputs_dir / filename) for filename in PIPELINE_FILES}
    return tables


def load_monthly_outputs(
    outputs_dir: Path = OUTPUTS_DIR,
) -> dict[str, tuple[pd.DataFrame | None, str | None]]:
    tables = {filename: load_output(outputs_dir / filename) for filename in MONTHLY_FILES}
    picks_frame, _ = tables["monthly_research_picks.csv"]
    track_frame, _ = tables["monthly_picks_track_record.csv"]
    equity_frame, _ = tables["monthly_picks_equity_curve.csv"]

    if picks_frame is None:
        build_monthly_research_picks(BASE_DIR, output_dir=outputs_dir, top_n=_monthly_top_n())
        tables["monthly_research_picks.csv"] = load_output(outputs_dir / "monthly_research_picks.csv")
        picks_frame, _ = tables["monthly_research_picks.csv"]

    if track_frame is None or equity_frame is None:
        calculate_monthly_track_record(BASE_DIR, output_dir=outputs_dir, top_n=_monthly_top_n(), write_output=True)
        tables["monthly_picks_track_record.csv"] = load_output(outputs_dir / "monthly_picks_track_record.csv")
        tables["monthly_picks_equity_curve.csv"] = load_output(outputs_dir / "monthly_picks_equity_curve.csv")
    return tables


def _data_gap_action_needs_refresh(row: pd.Series) -> bool:
    dataset = str(row.get("dataset", "")).strip()
    ticker = str(row.get("ticker", "")).strip().upper()
    recommended_action = str(row.get("recommended_action", "")).strip()
    focus_command = normalize_operator_command(str(row.get("focus_command", "")).strip())
    normalized_action = recommended_action.lower()
    if focus_command == "make imports-validate":
        return "make imports-validate" not in normalized_action or "make imports-preview" not in normalized_action
    if dataset == "prices" and ticker:
        expected_focus = f"make focus-price ticker={ticker.lower()}"
        return expected_focus not in normalized_action or "make price-refresh tickers=" not in normalized_action
    if dataset == "fundamentals" and ticker:
        expected_focus = f"make focus-fundamentals ticker={ticker.lower()}"
        return expected_focus not in normalized_action or "make sec-stage tickers=" not in normalized_action
    if dataset == "peers" and ticker:
        expected_focus = f"make focus-peers ticker={ticker.lower()}"
        return expected_focus not in normalized_action or "make templates" not in normalized_action
    return False


def _data_source_action_needs_refresh(row: pd.Series) -> bool:
    dataset = str(row.get("dataset", "")).strip()
    fallback_action = str(row.get("fallback_action", "")).strip()
    focus_command = normalize_operator_command(str(row.get("focus_command", "")).strip())
    normalized_action = fallback_action.lower()
    if focus_command == "make imports-validate":
        return "make imports-validate" not in normalized_action or "make imports-preview" not in normalized_action
    if dataset == "prices":
        return (
            "make status" not in normalized_action
            or "normalize verified local ohlcv files" not in normalized_action
            or "make price-validate" not in normalized_action
            or "make price-preview" not in normalized_action
            or "make price-apply" not in normalized_action
        )
    if dataset == "fundamentals":
        return (
            "make status" not in normalized_action
            or "make imports-validate" not in normalized_action
            or "make imports-preview" not in normalized_action
            or "make imports-apply" not in normalized_action
        )
    if dataset == "peers":
        return "make status" not in normalized_action or "make templates" not in normalized_action
    return False


def _staged_import_cell_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value or "").strip()


def _is_dataset_level_staged_import_row(row: pd.Series, dataset: str) -> bool:
    ticker = _staged_import_cell_text(row.get("ticker", ""))
    target_file = _staged_import_cell_text(row.get("target_file", ""))
    source_file = _staged_import_cell_text(row.get("source_file", ""))
    staged_file = f"data/imports/{dataset}.csv"
    return not ticker and (target_file == staged_file or source_file == staged_file)


def _staged_import_guidance(dataset: str) -> tuple[str, str]:
    if dataset == "peers":
        return (
            "Advance staged peer import",
            "Run make imports-validate, then make imports-preview, then make imports-apply, then make status to confirm the live local peer mappings.",
        )
    return (
        "Advance staged fundamentals import",
        "Run make imports-validate, then make imports-preview, then make imports-apply, then make status to confirm the live local fundamentals and DCF inputs.",
    )


def _normalize_dataset_level_staged_import_rows(frame: pd.DataFrame | None, action_column: str) -> pd.DataFrame | None:
    if frame is None or frame.empty:
        return frame
    normalized = frame.copy()
    for idx, row in normalized.iterrows():
        dataset = _staged_import_cell_text(row.get("dataset", row.get("action_type", "")))
        if dataset not in {"fundamentals", "peers"}:
            continue
        if not _is_dataset_level_staged_import_row(row, dataset):
            continue
        title, action = _staged_import_guidance(dataset)
        if action_column in normalized.columns:
            normalized.at[idx, action_column] = action
        if "focus_command" in normalized.columns:
            normalized.at[idx, "focus_command"] = "make imports-validate"
        if "example_command" in normalized.columns:
            normalized.at[idx, "example_command"] = "make imports-preview"
        if "title" in normalized.columns:
            normalized.at[idx, "title"] = title
        if "reason" in normalized.columns:
            staged_file = f"data/imports/{dataset}.csv"
            if dataset == "peers":
                normalized.at[idx, "reason"] = (
                    f"Staged import rows are present in {staged_file}; validate, preview, apply, "
                    "then refresh status before relying on peer-relative context."
                )
            else:
                normalized.at[idx, "reason"] = (
                    f"Staged import rows are present in {staged_file}; validate, preview, apply, "
                    "then refresh status before relying on DCF coverage."
                )
    return normalized


def load_data_source_status_tables(
    outputs_dir: Path = OUTPUTS_DIR,
) -> dict[str, tuple[pd.DataFrame | None, str | None]]:
    tables = {filename: load_output(outputs_dir / filename) for filename in DATA_SOURCE_FILES}
    source_frame, _ = tables["data_source_status.csv"]
    gap_frame, _ = tables["data_gap_report.csv"]
    source_frame = _normalize_dataset_level_staged_import_rows(source_frame, "fallback_action")
    gap_frame = _normalize_dataset_level_staged_import_rows(gap_frame, "recommended_action")
    source_frame = ensure_command_safety_columns(source_frame)
    gap_frame = ensure_command_safety_columns(gap_frame)
    tables["data_source_status.csv"] = (source_frame, tables["data_source_status.csv"][1])
    tables["data_gap_report.csv"] = (gap_frame, tables["data_gap_report.csv"][1])
    required_columns = {"focus_command", "example_command", "target_file"}
    needs_refresh = source_frame is None or gap_frame is None
    if gap_frame is not None and not gap_frame.empty and not required_columns.issubset(set(gap_frame.columns)):
        needs_refresh = True
    if source_frame is not None and not source_frame.empty and not required_columns.issubset(set(source_frame.columns)):
        needs_refresh = True
    if not needs_refresh and gap_frame is not None and not gap_frame.empty:
        for _, row in gap_frame.iterrows():
            dataset = str(row.get("dataset", "")).strip()
            ticker = str(row.get("ticker", "")).strip().upper()
            focus_command = normalize_operator_command(str(row.get("focus_command", "")).strip())
            example_command = normalize_operator_command(str(row.get("example_command", "")).strip())
            expected_example = ""
            if focus_command == "make imports-validate":
                expected_example = "make imports-preview"
            elif dataset == "prices" and ticker:
                expected_example = f"make price-normalize INPUT=data/raw/prices/{ticker}.csv TICKER={ticker} SOURCE=yahoo_manual"
            elif dataset == "fundamentals" and ticker:
                expected_example = f"make sec-stage TICKERS={ticker}"
            elif dataset == "peers" and ticker:
                expected_example = "make templates"
            elif dataset == "fundamentals" and focus_command == "make status":
                expected_example = "make runbook-fundamentals-broader"
            elif dataset == "peers" and focus_command == "make status":
                expected_example = "make runbook-peers-broader"
            elif dataset in {"earnings", "analyst_estimates", "smh_holdings"}:
                expected_example = "make templates"
            elif dataset in {"sp500_constituents", "nasdaq_symbols", "universe"} and focus_command == "make universe-preview":
                expected_example = "make universe-preview"
            elif dataset == "local_outputs" and focus_command == "make status":
                expected_example = "make status"
            if expected_example and example_command != expected_example:
                needs_refresh = True
                break
            if _data_gap_action_needs_refresh(row):
                needs_refresh = True
                break
    if not needs_refresh and source_frame is not None and not source_frame.empty:
        for _, row in source_frame.iterrows():
            dataset = str(row.get("dataset", "")).strip()
            focus_command = normalize_operator_command(str(row.get("focus_command", "")).strip())
            example_command = normalize_operator_command(str(row.get("example_command", "")).strip())
            expected_example = ""
            if focus_command == "make imports-validate":
                expected_example = "make imports-preview"
            elif dataset == "fundamentals" and focus_command == "make status":
                expected_example = "make runbook-fundamentals-broader"
            elif dataset == "peers" and focus_command == "make status":
                expected_example = "make runbook-peers-broader"
            elif dataset in {"earnings", "analyst_estimates", "smh_holdings"}:
                expected_example = "make templates"
            elif dataset in {"sp500_constituents", "nasdaq_symbols", "universe"} and focus_command == "make universe-preview":
                expected_example = "make universe-preview"
            elif dataset == "local_outputs" and focus_command == "make status":
                expected_example = "make status"
            if expected_example and example_command != expected_example:
                needs_refresh = True
                break
            if _data_source_action_needs_refresh(row):
                needs_refresh = True
                break
    if needs_refresh:
        payload = write_data_source_outputs(BASE_DIR, output_dir=outputs_dir)
        tables["data_source_status.csv"] = (pd.DataFrame(payload["data_sources"]), None)
        tables["data_gap_report.csv"] = (pd.DataFrame(payload["data_gaps"]), None)
    return tables


def load_data_onboarding_tables(
    outputs_dir: Path = OUTPUTS_DIR,
) -> dict[str, tuple[pd.DataFrame | None, str | None]]:
    tables = {filename: load_output(outputs_dir / filename) for filename in DATA_ONBOARDING_FILES}
    needs_refresh = any(frame is None for frame, _ in tables.values())
    coverage_frame, _ = tables.get("ticker_data_coverage.csv", (None, None))
    if coverage_frame is not None and not coverage_frame.empty:
        required_columns = {"target_file", "focus_command", "example_command"}
        if not required_columns.issubset(set(coverage_frame.columns)):
            needs_refresh = True
    actions_frame, _ = tables.get("data_onboarding_actions.csv", (None, None))
    if actions_frame is not None and not actions_frame.empty:
        required_columns = {
            "credential_required",
            "credential_present",
            "manual_fallback_command",
            "command_safety_note",
        }
        if not required_columns.issubset(set(actions_frame.columns)):
            needs_refresh = True
    optional_context_frame, _ = tables.get("optional_context_worklist.csv", (None, None))
    if optional_context_frame is not None and not optional_context_frame.empty:
        if "focus_command" not in optional_context_frame.columns:
            needs_refresh = True
    coverage_wizard_frame, _ = tables.get("data_coverage_wizard.csv", (None, None))
    if coverage_wizard_frame is not None and not coverage_wizard_frame.empty:
        required_columns = {
            "target_file",
            "focus_command",
            "example_command",
            "credential_required",
            "credential_present",
            "manual_fallback_command",
            "command_safety_note",
        }
        if not required_columns.issubset(set(coverage_wizard_frame.columns)):
            needs_refresh = True
        elif {"blocking_dataset", "recommended_action", "focus_command"}.issubset(set(coverage_wizard_frame.columns)):
            core_rows = coverage_wizard_frame.loc[
                coverage_wizard_frame["blocking_dataset"].astype(str).str.strip().isin(["prices", "fundamentals", "peers"])
            ]
            for _, row in core_rows.iterrows():
                dataset = str(row.get("blocking_dataset", "")).strip()
                ticker = str(row.get("ticker", "")).strip().upper()
                recommended_action = str(row.get("recommended_action", "")).strip()
                focus_command = normalize_operator_command(str(row.get("focus_command", "")).strip())
                example_command = normalize_operator_command(str(row.get("example_command", "")).strip())
                expected = ""
                expected_example = ""
                if focus_command == "make imports-validate":
                    expected = "make imports-validate"
                    expected_example = "make imports-preview"
                elif dataset == "prices" and ticker:
                    expected = f"make focus-price TICKER={ticker}"
                    expected_example = f"make price-normalize INPUT=data/raw/prices/{ticker}.csv TICKER={ticker} SOURCE=yahoo_manual"
                elif dataset == "fundamentals" and ticker:
                    expected = f"make focus-fundamentals TICKER={ticker}"
                    expected_example = f"make sec-stage TICKERS={ticker}"
                elif dataset == "peers" and ticker:
                    expected = f"make focus-peers TICKER={ticker}"
                    expected_example = "make templates"
                if expected and (
                    focus_command != expected
                    or expected not in recommended_action
                    or (expected_example and example_command != expected_example)
                    or (dataset == "prices" and "make price-refresh TICKERS=" not in recommended_action)
                ):
                    needs_refresh = True
                    break
    command_bundles_frame, _ = tables.get("command_bundles.csv", (None, None))
    if command_bundles_frame is not None and not command_bundles_frame.empty:
        primary_commands = command_bundles_frame.get("primary_command")
        if primary_commands is not None:
            normalized_primary = primary_commands.astype(str).map(normalize_operator_command)
            if normalized_primary.ne(primary_commands.astype(str).str.strip()).any():
                needs_refresh = True
    command_bundle_details_frame, _ = tables.get("command_bundle_details.csv", (None, None))
    if command_bundle_details_frame is not None and not command_bundle_details_frame.empty:
        exact_next_commands = command_bundle_details_frame.get("exact_next_command")
        primary_commands = command_bundle_details_frame.get("primary_command")
        if exact_next_commands is not None:
            normalized_exact = exact_next_commands.astype(str).map(normalize_operator_command)
            if normalized_exact.ne(exact_next_commands.astype(str).str.strip()).any():
                needs_refresh = True
        if not needs_refresh and primary_commands is not None:
            normalized_primary = primary_commands.astype(str).map(normalize_operator_command)
            if normalized_primary.ne(primary_commands.astype(str).str.strip()).any():
                needs_refresh = True
    command_bundle_runbook_frame, _ = tables.get("command_bundle_runbook.csv", (None, None))
    if command_bundle_runbook_frame is not None and not command_bundle_runbook_frame.empty:
        commands = command_bundle_runbook_frame.get("command")
        if commands is not None:
            normalized_commands = commands.astype(str).map(normalize_operator_command)
            if normalized_commands.ne(commands.astype(str).str.strip()).any():
                needs_refresh = True
    if needs_refresh:
        write_onboarding_outputs(BASE_DIR, output_dir=outputs_dir)
        for filename in DATA_ONBOARDING_FILES:
            tables[filename] = load_output(outputs_dir / filename)
    return tables


def load_research_health_tables(
    outputs_dir: Path = OUTPUTS_DIR,
) -> dict[str, tuple[pd.DataFrame | None, str | None]]:
    tables = {filename: load_output(outputs_dir / filename) for filename in RESEARCH_HEALTH_FILES}
    wizard_frame, _ = tables.get("data_quality_wizard.csv", (None, None))
    needs_refresh = any(frame is None for frame, _ in tables.values())
    if wizard_frame is not None and not wizard_frame.empty:
        required_columns = {"FocusCommand", "ExampleCommand"}
        if not required_columns.issubset(set(wizard_frame.columns)):
            needs_refresh = True
        elif {"ReadinessStatus", "NextBestAction"}.issubset(set(wizard_frame.columns)):
            stale_price_rows = wizard_frame.loc[
                wizard_frame["ReadinessStatus"].astype(str).str.strip().eq("Needs Price Data")
            ]
            if not stale_price_rows.empty:
                normalized_actions = stale_price_rows["NextBestAction"].astype(str).str.strip().str.lower()
                if not (
                    normalized_actions.str.contains("make focus-price").all()
                    and normalized_actions.str.contains("make price-refresh tickers=").all()
                ):
                    needs_refresh = True
                elif "ExampleCommand" in stale_price_rows.columns:
                    for _, row in stale_price_rows.iterrows():
                        ticker = str(row.get("Ticker", "")).strip().upper()
                        expected_example = (
                            f"make price-normalize INPUT=data/raw/prices/{ticker}.csv TICKER={ticker} SOURCE=yahoo_manual"
                            if ticker
                            else ""
                        )
                        example_command = normalize_operator_command(str(row.get("ExampleCommand", "")).strip())
                        if expected_example and example_command != expected_example:
                            needs_refresh = True
                            break
            if not needs_refresh:
                enrichment_rows = wizard_frame.loc[
                    wizard_frame["ReadinessStatus"].astype(str).str.strip().isin({"Needs Enrichment", "Partial Coverage"})
                ]
                if not enrichment_rows.empty:
                    normalized_actions = enrichment_rows["NextBestAction"].astype(str).str.strip().str.lower()
                    if not normalized_actions.str.contains(r"make focus-(?:fundamentals|peers)|make imports-validate", regex=True).all():
                        needs_refresh = True
                    elif {"Ticker", "FocusCommand", "ExampleCommand"}.issubset(set(enrichment_rows.columns)):
                        for _, row in enrichment_rows.iterrows():
                            ticker = str(row.get("Ticker", "")).strip().upper()
                            focus_command = normalize_operator_command(str(row.get("FocusCommand", "")).strip())
                            example_command = normalize_operator_command(str(row.get("ExampleCommand", "")).strip())
                            expected_example = ""
                            if focus_command == "make imports-validate":
                                expected_example = "make imports-preview"
                            elif focus_command.startswith("make focus-fundamentals") and ticker:
                                expected_example = f"make sec-stage TICKERS={ticker}"
                            elif focus_command.startswith("make focus-peers"):
                                expected_example = "make templates"
                            if expected_example and example_command != expected_example:
                                needs_refresh = True
                                break
    if needs_refresh:
        run_research_health(BASE_DIR, output_dir=outputs_dir)
        tables["data_quality_wizard.csv"] = load_output(outputs_dir / "data_quality_wizard.csv")
        for key in ("liquidity_risk", "correlation_risk"):
            filename = f"{key}.csv"
            tables[filename] = load_output(outputs_dir / filename)
    return tables


def load_dcf_readiness(data_dir: Path = DATA_DIR) -> tuple[pd.DataFrame | None, str | None]:
    return load_output(data_dir / DCF_READINESS_FILE)


def load_optional_context_readiness(data_dir: Path = DATA_DIR) -> dict[str, tuple[pd.DataFrame | None, str | None]]:
    return {
        "earnings_readiness": load_output(data_dir / EARNINGS_READINESS_FILE),
        "analyst_estimates_readiness": load_output(data_dir / ANALYST_ESTIMATES_READINESS_FILE),
    }


def load_ticker_readiness_report(data_dir: Path = DATA_DIR) -> tuple[pd.DataFrame | None, str | None]:
    return load_output(data_dir / TICKER_READINESS_REPORT_FILE)


def load_feature_readiness_summary(data_dir: Path = DATA_DIR) -> tuple[pd.DataFrame | None, str | None]:
    return load_output(data_dir / FEATURE_READINESS_SUMMARY_FILE)


def load_peer_readiness_report(data_dir: Path = DATA_DIR) -> tuple[pd.DataFrame | None, str | None]:
    return load_output(data_dir / PEER_READINESS_REPORT_FILE)


def load_peer_unlock_worklist(outputs_dir: Path = OUTPUTS_DIR) -> tuple[pd.DataFrame | None, str | None]:
    return load_output(outputs_dir / PEER_UNLOCK_WORKLIST_FILE)


def load_action_queue(
    outputs_dir: Path = OUTPUTS_DIR,
) -> tuple[pd.DataFrame | None, str | None]:
    path = outputs_dir / ACTION_QUEUE_FILE
    if not path.exists():
        write_action_queue_output(BASE_DIR, output_dir=outputs_dir)
        return load_output(path)
    frame, message = load_output(path)
    if frame is None:
        return frame, message
    frame = _normalize_dataset_level_staged_import_rows(frame, "recommended_action")
    frame = ensure_command_safety_columns(frame)
    needs_refresh = False
    required_columns = {"focus_command", "example_command", "target_file"}
    if not required_columns.issubset(set(frame.columns)):
        needs_refresh = True
    elif {"action_type", "recommended_action"}.issubset(frame.columns):
        price_rows = frame.loc[frame["action_type"].astype(str).str.strip().eq("prices")]
        if not price_rows.empty:
            normalized_actions = price_rows["recommended_action"].astype(str).str.strip().str.lower()
            if not (
                normalized_actions.str.contains("make focus-price").all()
                and normalized_actions.str.contains("make price-refresh tickers=").all()
            ):
                needs_refresh = True
        if not needs_refresh and {"ticker", "status", "focus_command"}.issubset(frame.columns):
            core_rows = frame.loc[
                frame["action_type"].astype(str).str.strip().isin(["fundamentals", "peers"])
            ]
            for _, row in core_rows.iterrows():
                action_type = str(row.get("action_type", "")).strip()
                ticker = _staged_import_cell_text(row.get("ticker", "")).upper()
                status = str(row.get("status", "")).strip()
                recommended_action = str(row.get("recommended_action", "")).strip()
                focus_command = str(row.get("focus_command", "")).strip()
                if action_type == "fundamentals" and ticker:
                    expected = f"make focus-fundamentals TICKER={ticker}"
                    if expected not in recommended_action or focus_command != expected:
                        needs_refresh = True
                        break
                if action_type == "peers" and ticker and status == "manual_input_needed":
                    expected = f"make focus-peers TICKER={ticker}"
                    if expected not in recommended_action or focus_command != expected:
                        needs_refresh = True
                        break
    if not needs_refresh and {"focus_command", "title", "reason"}.issubset(frame.columns):
        staged_import_rows = frame.loc[
            frame["focus_command"].astype(str).str.strip().str.lower().eq("make imports-validate")
        ]
        if not staged_import_rows.empty:
            normalized_titles = staged_import_rows["title"].astype(str).str.strip().str.lower()
            normalized_reasons = staged_import_rows["reason"].astype(str).str.strip().str.lower()
            if (
                normalized_titles.str.contains(r"resolve fundamentals gap").any()
                or normalized_titles.str.contains(r"resolve peers gap").any()
                or normalized_reasons.str.contains("freshness is file-based only").any()
            ):
                needs_refresh = True
    if needs_refresh:
        write_action_queue_output(BASE_DIR, output_dir=outputs_dir)
        refreshed_frame, refreshed_message = load_output(path)
        return ensure_command_safety_columns(refreshed_frame), refreshed_message
    return frame, message


def load_price_update_status(
    outputs_dir: Path = OUTPUTS_DIR,
) -> tuple[pd.DataFrame | None, str | None]:
    path = outputs_dir / PRICE_STATUS_FILE
    if not path.exists():
        return None, (
            "`price_update_status.csv` has not been generated yet. Run "
            "`make runbook-prices-broader` or `make focus-price TICKER=...` first. "
            "For downloaded files, use `make price-normalize`, then run `make price-validate`, "
            "`make price-preview`, and `make price-apply`."
        )
    frame, message = load_output(path)
    if frame is None:
        return frame, message
    enriched = enrich_price_update_status_frame(frame)
    if not enriched.equals(frame):
        enriched.to_csv(path, index=False)
    return enriched, message


def friendly_data_source_status(value: object) -> str:
    return DATA_SOURCE_STATUS_LABELS.get(format_missing(value, "-"), format_missing(value, "-"))


def data_source_status_table_columns(frame: pd.DataFrame | None) -> list[str]:
    if frame is None:
        return []
    columns = [
        "dataset",
        "availability_status",
        "required_for",
        "fallback_action",
        "target_file",
        "focus_command",
        "example_command",
        "local_file",
        "row_count",
        "validation_warnings",
        "source_name",
        "source_type",
        "expected_local_file",
        "notes",
    ]
    return operator_workflow_table_columns(frame, columns)


def price_update_status_table_columns(frame: pd.DataFrame | None) -> list[str]:
    if frame is None:
        return []
    columns = [
        "ticker",
        "status",
        "rows_fetched",
        "rows_merged",
        "error_category",
        "error_message",
        "fallback_used",
        "recommended_action",
        "focus_command",
        "example_command",
        "target_file",
    ]
    return [column for column in columns if column in frame.columns]


def action_queue_table_columns(frame: pd.DataFrame | None) -> list[str]:
    if frame is None:
        return []
    columns = [
        "priority",
        "urgency",
        "action_type",
        "ticker",
        "title",
        "recommended_action",
        "focus_command",
        "example_command",
        "credential_required",
        "credential_present",
        "manual_fallback_command",
        "command_safety_note",
        "reason",
    ]
    return [column for column in columns if column in frame.columns]


COMMAND_SAFETY_COLUMNS = [
    "credential_required",
    "credential_present",
    "manual_fallback_command",
    "command_safety_note",
]


def operator_workflow_table_columns(frame: pd.DataFrame | None, base_columns: list[str]) -> list[str]:
    if frame is None:
        return []
    columns: list[str] = []
    for column in base_columns:
        if column in frame.columns and column not in columns:
            columns.append(column)
        if column == "example_command":
            for safety_column in COMMAND_SAFETY_COLUMNS:
                if safety_column in frame.columns and safety_column not in columns:
                    columns.append(safety_column)
    return columns


def command_safety_fields(example_command: object) -> dict[str, object]:
    command = normalize_operator_command(example_command).lower()
    if not command.startswith("make sec-stage"):
        return {
            "credential_required": "",
            "credential_present": "",
            "manual_fallback_command": "",
            "command_safety_note": "",
        }
    credential_present = bool(os.environ.get("SEC_USER_AGENT", "").strip())
    return {
        "credential_required": "SEC_USER_AGENT",
        "credential_present": credential_present,
        "manual_fallback_command": "make templates",
        "command_safety_note": (
            "SEC staging requires SEC_USER_AGENT. If it is missing, use make templates, fill "
            "data/imports/fundamentals.csv with trusted manual rows, then run make imports-validate, "
            "make imports-preview, and make imports-apply."
        ),
    }


def ensure_command_safety_columns(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    if frame is None or frame.empty or "example_command" not in frame.columns:
        return frame
    enriched = frame.copy()
    safety_columns = ["credential_required", "credential_present", "manual_fallback_command", "command_safety_note"]
    missing_columns = [column for column in safety_columns if column not in enriched.columns]
    if not missing_columns:
        return enriched
    for column in missing_columns:
        default_value: object = False if column == "credential_present" else ""
        enriched[column] = pd.Series([default_value] * len(enriched), index=enriched.index, dtype=object)
    for idx, row in enriched.iterrows():
        safety = command_safety_fields(row.get("example_command"))
        for column in missing_columns:
            enriched.at[idx, column] = safety[column]
    return enriched


def summarize_price_update_status(status_frame: pd.DataFrame | None) -> dict[str, int]:
    if status_frame is None or status_frame.empty or "status" not in status_frame.columns:
        return {}
    counts = status_frame["status"].astype(str).str.lower().value_counts()
    return {status: int(count) for status, count in counts.items()}


def _target_rows_hint(value: object) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return ""
    return str(int(numeric))


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


def summarize_sec_stage_queue(worklist: pd.DataFrame | None) -> dict[str, int]:
    if worklist is None or worklist.empty:
        return {
            "priority_1": 0,
            "priority_2": 0,
            "holdings": 0,
            "missing_fundamentals": 0,
        }

    priorities = pd.to_numeric(worklist.get("priority", pd.Series(dtype=float)), errors="coerce").fillna(0)
    holdings_mask = worklist.get("is_holding", pd.Series(dtype=object)).astype(str).str.lower().isin({"true", "1", "yes"})
    missing_fundamentals_mask = ~worklist.get("has_fundamentals", pd.Series(dtype=object)).astype(str).str.lower().isin({"true", "1", "yes"})
    return {
        "priority_1": int(priorities.eq(1).sum()),
        "priority_2": int(priorities.eq(2).sum()),
        "holdings": int(holdings_mask.sum()),
        "missing_fundamentals": int(missing_fundamentals_mask.sum()),
    }


def summarize_peer_mapping_queue(worklist: pd.DataFrame | None) -> dict[str, int]:
    if worklist is None or worklist.empty:
        return {
            "priority_1": 0,
            "priority_2": 0,
            "holdings": 0,
            "missing_peer_mapping": 0,
            "mapped_peer_follow_through": 0,
            "staged_peer_import": 0,
        }

    priorities = pd.to_numeric(worklist.get("priority", pd.Series(dtype=float)), errors="coerce").fillna(0)
    holdings_mask = worklist.get("is_holding", pd.Series(dtype=object)).astype(str).str.lower().isin({"true", "1", "yes"})
    has_peer_mapping_mask = worklist.get("has_peer_mapping", pd.Series(dtype=object)).astype(str).str.lower().isin({"true", "1", "yes"})
    missing_peer_mapping_mask = ~has_peer_mapping_mask
    peer_ready_mask = worklist.get("peer_ready", pd.Series(dtype=object)).astype(str).str.lower().isin({"true", "1", "yes"})
    mapped_peer_follow_through_mask = has_peer_mapping_mask & ~peer_ready_mask
    staged_peer_import_mask = (
        worklist.get("focus_command", pd.Series(dtype=object)).astype(str).str.strip().str.lower().eq("make imports-validate")
        & worklist.get("target_file", pd.Series(dtype=object)).astype(str).str.strip().eq("data/imports/peers.csv")
    )
    return {
        "priority_1": int(priorities.eq(1).sum()),
        "priority_2": int(priorities.eq(2).sum()),
        "holdings": int(holdings_mask.sum()),
        "missing_peer_mapping": int(missing_peer_mapping_mask.sum()),
        "mapped_peer_follow_through": int(mapped_peer_follow_through_mask.sum()),
        "staged_peer_import": int(staged_peer_import_mask.sum()),
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
          color: var(--research-text) !important;
          font-family: "Avenir Next", "SF Pro Display", "Segoe UI", sans-serif;
        }
        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
          background: var(--research-bg) !important;
          color: var(--research-text) !important;
        }
        [data-testid="stSidebar"] {
          background: #f8faf5 !important;
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
          color: var(--research-text) !important;
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
        .section-shell {
          margin: 1.35rem 0 0.95rem 0;
          padding: 0.85rem 1rem 0.9rem 1rem;
          border-radius: 18px;
          border: 1px solid rgba(148, 163, 184, 0.22);
          background:
            linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(249, 251, 247, 0.9));
          box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
          position: relative;
        }
        .section-shell::before {
          content: "";
          position: absolute;
          inset: 0 auto 0 0;
          width: 5px;
          border-radius: 18px 0 0 18px;
          background: linear-gradient(180deg, #0f766e, #14b8a6);
        }
        .section-kicker {
          color: #0f766e;
          font-size: 0.7rem;
          font-weight: 900;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          margin-left: 0.05rem;
        }
        .section-title {
          margin: 0.24rem 0 0.25rem 0;
          font-size: 1.28rem;
          font-weight: 900;
          letter-spacing: -0.035em;
          color: var(--research-ink);
        }
        .section-caption {
          margin-top: 0;
          margin-bottom: 0;
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
        div[data-testid="stDataFrame"],
        [data-testid="stTable"],
        .stDataFrame {
          border: 1px solid var(--research-border);
          border-radius: 12px;
          overflow: hidden;
          background: #fffefa !important;
          color: #111827 !important;
        }
        div[data-testid="stDataFrame"] *,
        [data-testid="stTable"] *,
        .stDataFrame * {
          color: #111827 !important;
        }
        [role="gridcell"],
        [role="columnheader"],
        [data-testid="stDataFrame"] [role="gridcell"],
        [data-testid="stDataFrame"] [role="columnheader"] {
          background-color: #fffefa !important;
          color: #111827 !important;
        }
        [data-testid="stExpander"] {
          background: rgba(255, 254, 250, 0.96) !important;
          border: 1px solid var(--research-border) !important;
          border-radius: 14px !important;
        }
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] p,
        [data-testid="stExpander"] span {
          color: #111827 !important;
        }
        input, textarea, [data-baseweb="select"] > div {
          background: #fffefa !important;
          color: #111827 !important;
          border-color: var(--research-border) !important;
        }
        [data-baseweb="popover"],
        [data-baseweb="menu"],
        [role="listbox"] {
          background: #fffefa !important;
          color: #111827 !important;
        }
        [data-baseweb="menu"] *,
        [role="option"] {
          color: #111827 !important;
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


def ticker_focus_command(lane: str, ticker: object, fallback: str = "") -> str:
    ticker_text = format_missing(ticker, fallback="").upper()
    if not ticker_text:
        return fallback
    lane_key = format_missing(lane, fallback="").strip().lower()
    command_map = {
        "prices": f"make focus-price TICKER={ticker_text}",
        "fundamentals": f"make focus-fundamentals TICKER={ticker_text}",
        "peers": f"make focus-peers TICKER={ticker_text}",
    }
    return command_map.get(lane_key, fallback)


def preferred_row_command(row: pd.Series | dict[str, object], fallback: str = "") -> str:
    def _raw_value(key: str) -> object:
        return row.get(key) if hasattr(row, "get") else ""

    focus_command = ""
    if hasattr(row, "get"):
        focus_command = normalize_operator_command(format_missing(_raw_value("focus_command"), fallback=""))
    example_command = normalize_operator_command(format_missing(_raw_value("example_command"), fallback=""))
    return focus_command or example_command or normalize_operator_command(fallback)


def normalize_operator_command(command: object) -> str:
    command_text = format_missing(command, "")
    if command_text == "make status":
        return "make status-check TOP_N=5"
    if command_text == "make onboarding":
        return "make status-check TOP_N=5"
    if command_text == "make dashboard":
        return "make dashboard-smoke"
    sec_stage_match = re.fullmatch(
        r"SEC_USER_AGENT=(?:'[^']*'|\"[^\"]*\"|\S+)\s+make sec-stage TICKERS=(.+)",
        command_text,
    )
    if sec_stage_match:
        tickers = ",".join(
            part.strip().upper()
            for part in sec_stage_match.group(1).split(",")
            if part.strip()
        )
        if tickers:
            return f"make sec-stage TICKERS={tickers}"
    price_match = re.fullmatch(r"python3 -m src\.data_update --tickers (.+)", command_text)
    if price_match:
        tickers = ",".join(
            part.strip().upper()
            for part in price_match.group(1).split(",")
            if part.strip()
        )
        if tickers:
            return f"make price-refresh TICKERS={tickers}"
    if re.fullmatch(r"python3 -m src\.universe_builder --preview --preset .+", command_text):
        return "make universe-preview"
    if re.fullmatch(r"python3 -m src\.universe_builder --preview --sources .+", command_text):
        return "make universe-preview"
    if re.fullmatch(r"python3 -m src\.universe_builder --write-import .+", command_text):
        return "make universe-apply"
    if command_text == "python3 -m src.universe_builder --apply-import":
        return "make universe-apply"
    return command_text


def preferred_bundle_command(row: pd.Series | dict[str, object], fallback: str = "") -> str:
    if hasattr(row, "get"):
        shortcut = normalize_operator_command(format_missing(row.get("bundle_shortcut_command"), fallback=""))
        if shortcut:
            return shortcut
        primary = normalize_operator_command(format_missing(row.get("primary_command"), fallback=""))
        if primary:
            return primary
        runbook = normalize_operator_command(format_missing(row.get("runbook_shortcut_command"), fallback=""))
        if runbook:
            return runbook
        detail = normalize_operator_command(format_missing(row.get("detail_shortcut_command"), fallback=""))
        if detail:
            return detail
        lane_fallback = unlock_stage_command(format_missing(row.get("lane"), ""), "")
        if lane_fallback:
            return lane_fallback
    return normalize_operator_command(fallback)


def unlock_ladder_table_columns(frame: pd.DataFrame | None, *, include_statuses: bool = True) -> list[str]:
    if frame is None:
        return []
    columns = [
        "ticker",
        "current_unlock_stage",
        "next_unlock_goal",
        "recommended_action",
        "focus_command",
        "example_command",
        "target_file",
    ]
    if include_statuses:
        columns[3:3] = [
            "price_stage_status",
            "dcf_stage_status",
            "peer_stage_status",
            "optional_context_status",
        ]
    return operator_workflow_table_columns(frame, columns)


def unlock_priority_summary_table_columns(frame: pd.DataFrame | None) -> list[str]:
    if frame is None:
        return []
    columns = [
        "group_type",
        "group_name",
        "ticker_count",
        "holdings_count",
        "top_priority_stage",
        "next_unlock_goal",
        "representative_tickers",
        "recommended_action",
        "focus_command",
        "example_command",
    ]
    return operator_workflow_table_columns(frame, columns)


def price_refresh_fallback_message(include_remote_failure_prefix: bool = False) -> str:
    body = (
        "Use `make runbook-prices-broader` or `make focus-price TICKER=...` first. "
        "For downloaded OHLCV files, run `make price-normalize INPUT=data/raw/prices/NVDA.csv "
        "TICKER=NVDA SOURCE=yahoo_manual`, then `make price-validate`, `make price-preview`, and `make price-apply`."
    )
    if include_remote_failure_prefix:
        return f"Remote price refresh had source issues. {body}"
    return body


def price_refresh_cli_note_message() -> str:
    return "CLI-only: " + price_refresh_fallback_message()


def data_gap_report_notice(message: str | None) -> tuple[str, str]:
    body = message or "Either the local gap report has not been generated yet or there are currently no explicit source-gap rows to show."
    return body, "make data-sources"


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


def normalize_operator_copy(text: object) -> str:
    normalized = format_missing(text)
    if normalized == "Not available":
        return normalized
    return re.sub(r"\bmake status\b(?!-check)", "make status-check TOP_N=5", normalized)


def review_path_fallback(dataset: object) -> str:
    lowered = format_missing(dataset, fallback="").strip().lower()
    if lowered in {"fundamentals", "dcf", "sec"}:
        return "Review fundamentals path."
    if lowered in {"peers", "peer", "peer_relative"}:
        return "Review peer path."
    if lowered in {"prices", "price", "price_history"}:
        return "Review price path."
    if lowered in {"optional_context", "context"}:
        return "Review optional context path."
    return "Review local data coverage."


def command_family_fallback(command: object, default: str) -> str:
    lowered = format_missing(command, fallback="").strip().lower()
    if "imports-" in lowered or "runbook-" in lowered:
        return "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
    if "bundle-" in lowered:
        return "Use the highest-leverage local bundle first so price, fundamentals, or peer follow-through stays coordinated."
    return default


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


def section_header_html(title: str, caption: str = "") -> str:
    caption_html = f"<div class='section-caption'>{html.escape(caption)}</div>" if caption else ""
    return (
        "<div class='section-shell'>"
        "<div class='section-kicker'>Research View</div>"
        f"<div class='section-title'>{html.escape(title)}</div>"
        f"{caption_html}"
        "</div>"
    )


def render_section_header(title: str, caption: str = "") -> None:
    st.markdown(section_header_html(title, caption), unsafe_allow_html=True)


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
    monthly_tables = load_monthly_outputs()
    monthly_frame, _ = monthly_tables["monthly_research_picks.csv"]
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
    text = normalize_operator_copy(value)
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


def optional_context_available(data: dict[str, object], fields: list[str]) -> bool:
    for field in fields:
        value = data.get(field)
        if value is None:
            continue
        try:
            if pd.isna(value):
                continue
        except (TypeError, ValueError):
            pass
        if str(value).strip() != "":
            return True
    return False


def optional_context_empty_state_message(dataset_label: str) -> str:
    return (
        "Not available: missing trusted local CSV input. "
        f"Add verified {dataset_label} rows through the staged manual CSV workflow, then run "
        "make imports-validate, make imports-preview, make imports-apply, and make onboarding TOP_N=10."
    )


def optional_context_unlock_cards() -> list[dict[str, object]]:
    return [
        {
            "kicker": "EARNINGS INPUT",
            "title": "Trusted CSV required",
            "body": (
                "Schema: ticker, fiscal_period, report_date, eps_actual, eps_estimate, "
                "revenue_actual, revenue_estimate, source, updated_at. "
                "Stage raw trusted files under data/staged/earnings/ or canonical rows in data/imports/earnings.csv. "
                "Rejected rows: data/rejected/earnings_import_rejected.csv."
            ),
            "badges": ["data/staged/earnings/", "missing trusted local CSV input"],
            "command": "make import-earnings",
        },
        {
            "kicker": "ESTIMATES INPUT",
            "title": "Trusted CSV required",
            "body": (
                "Schema: ticker, period, eps_estimate, revenue_estimate, price_target_mean, "
                "price_target_high, price_target_low, rating_consensus, source, updated_at. "
                "Stage raw trusted files under data/staged/analyst_estimates/ or canonical rows in data/imports/analyst_estimates.csv. "
                "Rejected rows: data/rejected/analyst_estimates_import_rejected.csv."
            ),
            "badges": ["data/staged/analyst_estimates/", "missing trusted local CSV input"],
            "command": "make import-analyst-estimates",
        },
        {
            "kicker": "VALIDATION",
            "title": "Validate and preview",
            "body": (
                "Use make templates first, then run make import-earnings or make import-analyst-estimates for staged files, "
                "then make imports-validate, make imports-preview, and make imports-apply. Invalid rows stay visible in rejected CSV reports."
            ),
            "badges": ["csv-first", "no fabrication"],
            "command": "make templates",
        },
        {
            "kicker": "SCHEMA-ONLY EXAMPLES",
            "title": "Templates are not data",
            "body": (
                "Generated templates and example schemas are blank operator aids, not synthetic earnings or estimate coverage. "
                "Keep optional context unavailable until trusted rows are staged, validated, previewed, and applied."
            ),
            "badges": ["schema only", "trusted rows required"],
            "command": "make imports-preview",
        },
    ]


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
    peer_row: pd.Series | None = None
    if not coverage.empty and "dataset" in coverage.columns:
        peer_matches = coverage.loc[
            coverage["dataset"].astype(str).str.strip().str.lower().eq("peers")
        ]
        if not peer_matches.empty:
            peer_row = peer_matches.iloc[0]
    available_datasets = 0 if coverage.empty else int(coverage.get("ticker_present", pd.Series(dtype=object)).astype(bool).sum())
    validation_warnings = 0
    if not coverage.empty and "validation_status" in coverage.columns:
        validation_warnings = int(coverage["validation_status"].astype(str).eq("valid_with_warnings").sum())
    peer_count = int(peer_summary.get("peer_count") or 0)
    peer_target_file = format_missing(peer_row.get("target_file"), "") if peer_row is not None else ""
    peer_fallback_command = (
        "make imports-validate"
        if peer_target_file == "data/imports/peers.csv"
        else ticker_focus_command("peers", peer_row.get("ticker") if peer_row is not None else "", "make onboarding")
    )
    peer_focus_command = (
        preferred_row_command(
            peer_row,
            peer_fallback_command,
        )
        if peer_row is not None
        else "make onboarding"
    )
    staged_peer_import = peer_target_file == "data/imports/peers.csv"
    return [
        {
            "kicker": "LOCAL DATASETS",
            "title": f"{available_datasets} available",
            "body": f"{validation_warnings} dataset warning{'s' if validation_warnings != 1 else ''} remain for this ticker's local coverage view.",
            "badges": ["csv-first"],
        },
        {
            "kicker": "PEER MAPPING",
            "title": "Staged" if staged_peer_import else "Present" if peer_summary.get("peer_dataset_present") else "Missing",
            "body": (
                f"{peer_count} peer ticker{'s' if peer_count != 1 else ''} staged locally and waiting on make imports-validate, make imports-preview, and make imports-apply before live peer-relative context."
                if staged_peer_import
                else f"{peer_count} peer ticker{'s' if peer_count != 1 else ''} configured for local peer-relative context."
            ),
            "badges": ["manual research", "staged import" if staged_peer_import else "csv-first"],
            "command": peer_focus_command,
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


def stock_report_next_step_cards(
    report_payload: dict[str, object],
    coverage: pd.DataFrame | None,
    peer_summary: dict[str, object] | None,
) -> list[dict[str, object]]:
    ticker = format_missing(report_payload.get("ticker"), "Selected ticker")
    readiness = report_payload.get("valuation_readiness", {}) or {}
    warnings = report_payload.get("missing_data_warnings", []) or []
    peer_summary = peer_summary or {}
    cards: list[dict[str, object]] = []

    has_prices = False
    has_fundamentals = False
    fundamentals_row: pd.Series | None = None
    peer_row: pd.Series | None = None
    if coverage is not None and not coverage.empty:
        coverage_frame = coverage.copy()
        if "dataset" in coverage_frame.columns and "ticker_present" in coverage_frame.columns:
            coverage_frame["dataset"] = coverage_frame["dataset"].astype(str).str.strip().str.lower()
            coverage_frame["ticker_present_bool"] = coverage_frame["ticker_present"].astype(str).str.lower().isin({"true", "1", "yes"})
            has_prices = bool(
                coverage_frame.loc[coverage_frame["dataset"].eq("prices"), "ticker_present_bool"].any()
            )
            has_fundamentals = bool(
                coverage_frame.loc[coverage_frame["dataset"].eq("fundamentals"), "ticker_present_bool"].any()
            )
            fundamentals_matches = coverage_frame.loc[coverage_frame["dataset"].eq("fundamentals")]
            if not fundamentals_matches.empty:
                fundamentals_row = fundamentals_matches.iloc[0]
            peer_matches = coverage_frame.loc[coverage_frame["dataset"].eq("peers")]
            if not peer_matches.empty:
                peer_row = peer_matches.iloc[0]

    fundamentals_target_file = format_missing(fundamentals_row.get("target_file"), "") if fundamentals_row is not None else ""
    fundamentals_fallback = (
        "make imports-validate"
        if fundamentals_target_file == "data/imports/fundamentals.csv"
        else ticker_focus_command("fundamentals", ticker, fallback=f"make sec-stage TICKERS={ticker}")
    )
    fundamentals_command = preferred_row_command(
        fundamentals_row,
        fundamentals_fallback,
    ) if fundamentals_row is not None else ticker_focus_command(
        "fundamentals",
        ticker,
        fallback=f"make sec-stage TICKERS={ticker}",
    )
    staged_fundamentals_import = (
        fundamentals_target_file == "data/imports/fundamentals.csv"
    )
    peer_target_file = format_missing(peer_row.get("target_file"), "") if peer_row is not None else ""
    peer_fallback = (
        "make imports-validate"
        if peer_target_file == "data/imports/peers.csv"
        else ticker_focus_command("peers", ticker, fallback="make templates")
    )
    peer_command = preferred_row_command(peer_row, peer_fallback) if peer_row is not None else ticker_focus_command("peers", ticker, fallback="make templates")
    staged_peer_import = (
        peer_target_file == "data/imports/peers.csv"
    )

    if not has_prices:
        cards.append(
            {
                "kicker": "NEXT STEP",
                "title": "Fix price coverage",
                "body": (
                    f"{ticker} still needs stronger verified local price history before broader trust. "
                    "Use the manual staged price workflow if the free refresh path stays unreliable."
                ),
                "badges": ["prices", "data moat"],
                "command": ticker_focus_command("prices", ticker, fallback=f"make price-refresh TICKERS={ticker}"),
            }
        )
    elif not readiness.get("dcf_ready") and not has_fundamentals:
        cards.append(
            {
                "kicker": "NEXT STEP",
                "title": "Advance staged fundamentals import" if staged_fundamentals_import else "Stage fundamentals",
                "body": (
                    f"{ticker} already has staged fundamentals in {fundamentals_target_file}. "
                    "Validate, preview, and apply them before trusting DCF coverage."
                    if staged_fundamentals_import
                    else (
                        f"{ticker} has enough price context for more research, but DCF coverage is still missing local fundamentals. "
                        "Stage SEC fundamentals before leaning on valuation."
                    )
                ),
                "badges": ["fundamentals", "staged import" if staged_fundamentals_import else "sec queue"],
                "command": fundamentals_command,
            }
        )
    elif not readiness.get("peer_ready") or not peer_summary.get("peer_dataset_present"):
        cards.append(
            {
                "kicker": "NEXT STEP",
                "title": "Advance staged peer import" if staged_peer_import else "Add peer mappings",
                "body": (
                    f"{ticker} already has staged peer mappings in {peer_target_file}. "
                    "Validate, preview, and apply them before trusting peer-relative context."
                    if staged_peer_import
                    else (
                        f"{ticker} can be reviewed now, but peer-relative context is still partial. "
                        "Add manually researched peers if this name matters for deeper relative work."
                    )
                ),
                "badges": ["peers", "staged import" if staged_peer_import else "manual research"],
                "command": peer_command,
            }
        )
    else:
        cards.append(
            {
                "kicker": "NEXT STEP",
                "title": "Review full report",
                "body": (
                    f"{ticker} already has the minimum local context for a deeper single-name pass. "
                    "Move through valuation, technical context, and source/freshness together."
                ),
                "badges": ["ready", "single name"],
                "command": "make verify",
            }
        )

    cards.append(
        {
            "kicker": "DATA GAPS",
            "title": f"{len(warnings)} visible",
            "body": (
                "Warnings stay explicit and should guide the next research step instead of being hidden behind a score."
            ),
            "badges": stock_report_readiness_badges(readiness)[:2],
        }
    )
    return cards


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
        dataset_command = "make validate-data"
    else:
        status_series = validation_rows.get("validation_status", pd.Series(dtype=object)).astype(str)
        valid_count = int(status_series.isin({"valid", "valid_with_warnings"}).sum())
        missing_count = int(status_series.eq("missing_file").sum())
        dataset_title = f"{valid_count} usable datasets"
        dataset_body = f"{missing_count} optional local file{'s' if missing_count != 1 else ''} missing. Partial reports remain safe."
        dataset_badges = ["CSV-first", f"{len(validation_rows)} checked"]
        dataset_command = "make validate-data"

    price_counts = summarize_price_update_status(price_status_frame)
    price_problem_count = sum(
        price_counts.get(status, 0)
        for status in ["parse_error", "source_unavailable", "network_error", "no_rows", "failed"]
    )
    if price_status_frame is None:
        price_title = "Price status not generated"
        price_body = (
            "Use make runbook-prices-broader or make focus-price TICKER=... first. "
            "For downloaded files, run make price-normalize, make price-validate, "
            "make price-preview, and make price-apply."
        )
        price_badges = ["make runbook-prices-broader", "manual fallback"]
        price_command = "make runbook-prices-broader"
    elif price_problem_count:
        price_title = f"{price_problem_count} price issue{'s' if price_problem_count != 1 else ''}"
        price_body = (
            "Use raw downloaded CSVs only as user-provided inputs, then run make price-normalize, "
            "make price-validate, make price-preview, and make price-apply."
        )
        price_badges = ["make price-status TOP_N=10", "manual fallback"]
        price_command = "make price-status TOP_N=10"
    else:
        price_title = f"{price_counts.get('fetched', 0)} fetched"
        price_body = "Latest price refresh did not report blocking source errors."
        price_badges = ["make price-status TOP_N=10"]
        price_command = "make price-status TOP_N=10"

    queue_summary = action_queue_summary(action_queue_frame)
    action_title = f"{queue_summary['critical']} critical actions"
    action_body = f"{queue_summary['high']} high-priority and {queue_summary['medium']} medium-priority remediation rows are queued."
    action_badges = ["make action-queue-check TOP_N=10", "read-only dashboard"]
    action_command = "make action-queue-check TOP_N=10"
    signal_ready = (
        action_queue_frame is not None
        and not action_queue_frame.empty
        and {"priority", "action_type"}.issubset(set(action_queue_frame.columns))
    )
    top_signal = top_priority_signals(action_queue_frame, limit=1) if signal_ready else []
    if top_signal:
        signal = top_signal[0]
        signal_body = compact_reason(signal.get("body"), max_sentences=2, max_chars=220)
        signal_command = format_missing(signal.get("command"), "")
        if signal_body and signal_body != "Not available":
            action_body = (
                f"{queue_summary['high']} high-priority and {queue_summary['medium']} medium-priority remediation rows are queued. "
                f"Top next step: {signal_body}"
            )
        if signal_command and signal_command != "Not available":
            action_command = signal_command

    coverage_summary = summarize_ticker_coverage(coverage_frame)
    coverage_title = f"{coverage_summary['usable_price_tickers']} price-ready tickers"
    coverage_body = (
        f"{coverage_summary['dcf_ready_tickers']} DCF-ready, "
        f"{coverage_summary['peer_ready_tickers']} peer-ready, "
        f"{coverage_summary['optional_only_missing_tickers']} missing only optional files."
    )
    coverage_badges = ["make data-wizard TOP_N=10"]
    coverage_command = "make data-wizard TOP_N=10"

    return [
        {"kicker": "DATASETS", "title": dataset_title, "body": dataset_body, "badges": dataset_badges, "command": dataset_command},
        {"kicker": "PRICES", "title": price_title, "body": price_body, "badges": price_badges, "command": price_command},
        {"kicker": "NEXT ACTIONS", "title": action_title, "body": action_body, "badges": action_badges, "command": action_command},
        {"kicker": "COVERAGE", "title": coverage_title, "body": coverage_body, "badges": coverage_badges, "command": coverage_command},
    ]


def data_health_action_path_cards(
    actions_frame: pd.DataFrame | None,
    action_queue_frame: pd.DataFrame | None,
) -> list[dict[str, object]]:
    def _action_path_body(row: pd.Series) -> str:
        command = preferred_row_command(
            row,
            ticker_focus_command(row.get("dataset"), row.get("ticker"), "make data-wizard TOP_N=10"),
        )
        reason = normalize_operator_copy(row.get("reason"))
        recommended_action = normalize_operator_copy(row.get("recommended_action"))
        target_file = format_missing(row.get("target_file"), "")
        body_source = command_family_fallback(command, review_path_fallback(row.get("dataset")))
        if reason and reason != "Not available":
            body_source = f"{reason} {recommended_action}".strip() if recommended_action and recommended_action != reason else reason
        elif recommended_action and recommended_action != "Not available":
            body_source = recommended_action
        staged_follow_through = ""
        if target_file == "data/imports/fundamentals.csv":
            staged_follow_through = "Run make imports-validate, then make imports-preview, then make imports-apply for the staged fundamentals import."
        elif target_file == "data/imports/peers.csv":
            staged_follow_through = "Run make imports-validate, then make imports-preview, then make imports-apply for the staged peer import."
        elif target_file == "data/imports/prices.csv":
            staged_follow_through = "Run make price-validate, then make price-preview, then make price-apply for the staged price import."
        if staged_follow_through:
            normalized_body = body_source.lower()
            if target_file == "data/imports/prices.csv":
                if (
                    "make price-validate" not in normalized_body
                    or "make price-preview" not in normalized_body
                    or "make price-apply" not in normalized_body
                ):
                    body_source = (
                        f"{reason} {staged_follow_through}".strip()
                        if reason and reason != "Not available"
                        else staged_follow_through
                    )
            else:
                if (
                    "make imports-validate" not in normalized_body
                    or "make imports-preview" not in normalized_body
                    or "make imports-apply" not in normalized_body
                ):
                    body_source = (
                        f"{reason} {staged_follow_through}".strip()
                        if reason and reason != "Not available"
                        else staged_follow_through
                    )
        return compact_reason(body_source, max_sentences=2, max_chars=220)

    def _fallback_card() -> list[dict[str, object]]:
        return [
            {
                "kicker": "ACTION PATHS",
                "title": "No action paths yet",
                "body": "Run make onboarding to refresh the onboarding outputs and action queue, then use the best local command path for prices, fundamentals, peers, and optional context.",
                "badges": ["read-only"],
                "command": "make onboarding",
            }
        ]

    if (actions_frame is None or actions_frame.empty) and (action_queue_frame is None or action_queue_frame.empty):
        return _fallback_card()

    cards: list[dict[str, object]] = []

    if actions_frame is not None and not actions_frame.empty and "dataset" in actions_frame.columns:
        ordered = actions_frame.copy()
        ordered["priority"] = pd.to_numeric(ordered.get("priority"), errors="coerce").fillna(999)
        ordered["dataset"] = ordered["dataset"].astype(str).str.strip().str.lower()
        lane_map = {
            "prices": ("PRICES", "Price path"),
            "fundamentals": ("FUNDAMENTALS", "Fundamentals path"),
            "peers": ("PEERS", "Peer path"),
        }
        for dataset, (kicker, title) in lane_map.items():
            lane_rows = ordered.loc[ordered["dataset"].eq(dataset)].sort_values(["priority", "ticker"], na_position="last")
            if lane_rows.empty:
                continue
            row = lane_rows.iloc[0]
            cards.append(
                {
                    "kicker": kicker,
                    "title": title,
                    "body": (
                        f"{format_missing(row.get('ticker'), 'Ticker')}: "
                        f"{_action_path_body(row)}"
                    ),
                    "badges": [f"P{format_missing(row.get('priority'), '-')}", dataset],
                    "command": preferred_row_command(
                        row,
                        ticker_focus_command(dataset, row.get("ticker"), "make data-wizard TOP_N=10"),
                    ),
                }
            )

    if action_queue_frame is not None and not action_queue_frame.empty:
        top_signal = top_priority_signals(action_queue_frame, limit=1)
        if top_signal:
            signal = top_signal[0]
            command = format_missing(signal.get("command"), "make action-queue-check TOP_N=10")
            cards.insert(
                0,
                {
                    "kicker": "BEST NEXT",
                    "title": command,
                    "body": compact_reason(signal.get("body"), max_sentences=2, max_chars=220),
                    "badges": [str(item) for item in signal.get("badges", [])][:2] or ["priority"],
                    "command": command,
                },
            )

    if not cards:
        return _fallback_card()
    return cards[:4]


def data_health_command_bundle_cards(bundle_frame: pd.DataFrame | None, limit: int = 3) -> list[dict[str, object]]:
    if bundle_frame is None or bundle_frame.empty:
        return [
            {
                "kicker": "COMMAND BUNDLES",
                "title": "No command bundles yet",
                "body": "Run make onboarding to refresh the onboarding outputs and surface holdings-first local command bundles for prices, SEC staging, and peer mapping.",
                "badges": ["read-only"],
                "command": "make onboarding",
            }
        ]

    ordered = bundle_frame.copy()
    if "ticker_count" in ordered.columns:
        ordered["ticker_count"] = pd.to_numeric(ordered["ticker_count"], errors="coerce").fillna(0)

    cards: list[dict[str, object]] = []
    for _, row in ordered.head(limit).iterrows():
        command = preferred_bundle_command(row, "")
        goal_summary = compact_reason(row.get("goal_summary"), max_sentences=1, max_chars=110)
        lane_summary = command_family_fallback(command, review_path_fallback(row.get("lane")))
        if "runbook-" in command.lower():
            lane_summary = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
        target_file = format_missing(row.get("target_file"), "")
        staged_summary = ""
        if target_file in {"data/imports/fundamentals.csv", "data/imports/peers.csv", "data/imports/prices.csv"}:
            staged_summary = compact_reason(row.get("safe_next_step"), max_sentences=1, max_chars=150)
            if target_file == "data/imports/fundamentals.csv":
                default_staged_summary = "Run make imports-validate, make imports-preview, and make imports-apply for the staged fundamentals import."
            elif target_file == "data/imports/peers.csv":
                default_staged_summary = "Run make imports-validate, make imports-preview, and make imports-apply for the staged peer import."
            else:
                default_staged_summary = "Run make price-validate, make price-preview, and make price-apply for the staged price import."
            if staged_summary == "Not available":
                staged_summary = default_staged_summary
            elif target_file == "data/imports/prices.csv" and (
                "make price-validate" not in staged_summary
                or "make price-preview" not in staged_summary
                or "make price-apply" not in staged_summary
            ):
                staged_summary = default_staged_summary
        body_summary = (
            goal_summary
            if goal_summary != "Not available"
            else compact_reason(row.get("why_it_matters") or staged_summary or lane_summary, max_sentences=1, max_chars=150)
        )
        target_history_rows = _target_rows_hint(row.get("target_history_rows"))
        suggested_start_date = format_missing(row.get("suggested_start_date"), "")
        hints: list[str] = []
        if target_history_rows not in {"", "-"}:
            hints.append(f"{target_history_rows} target rows")
        if suggested_start_date not in {"", "-"}:
            hints.append(f"start by {suggested_start_date}")
        cards.append(
            {
                "kicker": format_missing(row.get("lane"), "bundle").upper(),
                "title": format_missing(row.get("bundle_name"), "Local bundle"),
                "body": (
                    f"{format_missing(row.get('tickers'), 'No tickers')}: "
                    f"{body_summary}"
                    f"{' (' + '; '.join(hints) + ')' if hints else ''}"
                ),
                "badges": [
                    format_missing(row.get("scope"), "scope").replace("_", " "),
                    f"{format_value(row.get('ticker_count'), fallback='0')} tickers",
                ],
                "command": command,
            }
        )
    return cards


def data_health_command_bundle_runbook_cards(runbook_frame: pd.DataFrame | None, limit: int = 3) -> list[dict[str, object]]:
    if runbook_frame is None or runbook_frame.empty:
        return [
            {
                "kicker": "RUNBOOK",
                "title": "No bundle runbook yet",
                "body": "Run make onboarding to refresh the onboarding outputs and surface ordered bundle command steps for prices, SEC staging, and peer mapping.",
                "badges": ["read-only"],
                "command": "make onboarding",
            }
        ]

    ordered = runbook_frame.copy()
    if "step_order" in ordered.columns:
        ordered["step_order"] = pd.to_numeric(ordered["step_order"], errors="coerce")
        ordered = ordered.sort_values(["lane", "step_order", "bundle_name"], kind="stable")

    cards: list[dict[str, object]] = []
    for lane in ("prices", "fundamentals", "peers"):
        lane_rows = ordered.loc[ordered.get("lane", pd.Series(dtype=str)).astype(str).eq(lane)]
        if lane_rows.empty:
            continue
        bundle_name = format_missing(lane_rows.iloc[0].get("bundle_name"), "Local bundle")
        goal_summary = compact_reason(lane_rows.iloc[0].get("goal_summary"), max_sentences=1, max_chars=110)
        target_file = format_missing(lane_rows.iloc[0].get("target_file"), "")
        staged_summary = ""
        default_staged_summary = ""
        if target_file in {"data/imports/fundamentals.csv", "data/imports/peers.csv", "data/imports/prices.csv"}:
            staged_summary = compact_reason(lane_rows.iloc[0].get("safe_next_step"), max_sentences=1, max_chars=150)
            if target_file == "data/imports/fundamentals.csv":
                default_staged_summary = "Run make imports-validate, make imports-preview, and make imports-apply for the staged fundamentals import."
            elif target_file == "data/imports/peers.csv":
                default_staged_summary = "Run make imports-validate, make imports-preview, and make imports-apply for the staged peer import."
            else:
                default_staged_summary = "Run make price-validate, make price-preview, and make price-apply for the staged price import."
            if staged_summary == "Not available":
                staged_summary = default_staged_summary
            elif target_file == "data/imports/prices.csv" and (
                "make price-validate" not in staged_summary
                or "make price-preview" not in staged_summary
                or "make price-apply" not in staged_summary
            ):
                staged_summary = default_staged_summary
        target_history_rows = _target_rows_hint(lane_rows.iloc[0].get("target_history_rows"))
        suggested_start_date = format_missing(lane_rows.iloc[0].get("suggested_start_date"), "")
        hint_text = ""
        if target_history_rows not in {"", "-"} or suggested_start_date not in {"", "-"}:
            parts = []
            if target_history_rows not in {"", "-"}:
                parts.append(f"{target_history_rows} target rows")
            if suggested_start_date not in {"", "-"}:
                parts.append(f"start by {suggested_start_date}")
            hint_text = f" ({'; '.join(parts)})"
        steps = []
        first_command = ""
        fallback_first_command = ""
        if target_file == "data/imports/fundamentals.csv":
            fallback_first_command = "make imports-validate"
        elif target_file == "data/imports/peers.csv":
            fallback_first_command = "make imports-validate"
        elif target_file == "data/imports/prices.csv":
            fallback_first_command = "make price-validate"
        max_steps = 7 if lane == "prices" else 5
        for _, row in lane_rows.head(max_steps).iterrows():
            step_label = format_missing(row.get("step_label"), "Step")
            command = format_missing(row.get("command"), "")
            normalized_command = normalize_operator_command(command)
            step_command = normalized_command or command
            if not step_command and fallback_first_command and not first_command:
                step_command = fallback_first_command
            if step_command:
                first_command = first_command or step_command
                steps.append(f"{step_label}: {step_command}")
        surfaced_command = first_command or fallback_first_command
        lane_summary = command_family_fallback(surfaced_command, review_path_fallback(lane))
        if "runbook-" in surfaced_command.lower():
            lane_summary = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
        body_summary = (
            goal_summary
            if goal_summary not in {"", "Not available"}
            else compact_reason(lane_rows.iloc[0].get("why_it_matters") or staged_summary or lane_summary, max_sentences=1, max_chars=150)
        )
        cards.append(
            {
                "kicker": f"{lane.upper()} RUNBOOK",
                "title": bundle_name,
                "body": (
                    f"{body_summary}{hint_text}. " if body_summary not in {"", "Not available"} else ""
                ) + (" | ".join(steps) if steps else "No runbook steps available."),
                "badges": [
                    format_missing(lane_rows.iloc[0].get("scope"), "scope").replace("_", " "),
                    format_missing(lane_rows.iloc[0].get("tickers"), "No tickers"),
                ],
                "command": first_command or fallback_first_command,
            }
        )
        if len(cards) >= limit:
            break
    return cards or [
        {
            "kicker": "RUNBOOK",
            "title": "No bundle runbook yet",
            "body": "Run make onboarding to refresh the onboarding outputs and surface ordered bundle command steps for prices, SEC staging, and peer mapping.",
            "badges": ["read-only"],
            "command": "make onboarding",
        }
    ]


def data_health_price_target_cards(price_worklist_frame: pd.DataFrame | None, limit: int = 3) -> list[dict[str, object]]:
    if price_worklist_frame is None or price_worklist_frame.empty:
        return [
            {
                "kicker": "PRICE TARGETS",
                "title": "No price targets yet",
                "body": "Run make onboarding to refresh the onboarding outputs and surface exact history targets for Monthly Picks, track record, and fuller 1Y local coverage.",
                "badges": ["read-only"],
                "command": "make onboarding",
            }
        ]

    ordered = price_worklist_frame.copy()
    sort_columns: list[str] = []
    if "priority" in ordered.columns:
        ordered["priority"] = pd.to_numeric(ordered["priority"], errors="coerce")
        sort_columns.append("priority")
    if "rows_needed_for_next_goal" in ordered.columns:
        ordered["rows_needed_for_next_goal"] = pd.to_numeric(ordered["rows_needed_for_next_goal"], errors="coerce")
        sort_columns.append("rows_needed_for_next_goal")
    if "ticker" in ordered.columns:
        sort_columns.append("ticker")
    if sort_columns:
        ordered = ordered.sort_values(sort_columns, kind="stable")

    cards: list[dict[str, object]] = []
    for _, row in ordered.head(limit).iterrows():
        target_file = format_missing(row.get("target_file"), "")
        manual_command = normalize_operator_command(format_missing(row.get("example_command"), ""))
        staged_summary = compact_reason(row.get("safe_next_step"), max_sentences=1, max_chars=140)
        follow_through = ""
        if target_file == "data/imports/prices.csv":
            default_staged_summary = "Run make price-validate, make price-preview, and make price-apply for the staged price import."
            if staged_summary in {"", "Not available"} or (
                "make price-validate" not in staged_summary
                or "make price-preview" not in staged_summary
                or "make price-apply" not in staged_summary
            ):
                staged_summary = default_staged_summary
            follow_through = (
                f" Local fallback: {manual_command}. {staged_summary}"
                if manual_command and staged_summary not in {"", "Not available"}
                else f" Local fallback: {manual_command}."
                if manual_command
                else f" {staged_summary}"
                if staged_summary not in {"", "Not available"}
                else ""
            )
        cards.append(
            {
                "kicker": format_missing(row.get("next_price_goal"), "Price target").upper(),
                "title": format_missing(row.get("ticker"), "Ticker"),
                "body": (
                    f"{format_value(row.get('rows_needed_for_next_goal'), fallback='0')} rows still needed to reach "
                    f"{format_value(row.get('next_target_history_rows'), fallback='0')} rows. "
                    f"Suggested start: {format_missing(row.get('suggested_start_date'), 'Not available')}.{follow_through}"
                ),
                "badges": [
                    f"{format_value(row.get('price_history_days'), fallback='0')} local rows",
                    f"P{format_value(row.get('priority'), fallback='-')}",
                ],
                "command": preferred_row_command(
                    row,
                    ticker_focus_command("prices", row.get("ticker"), "make runbook-prices-broader"),
                ),
            }
        )
    return cards


def data_health_deep_research_target_cards(
    sec_stage_queue_frame: pd.DataFrame | None,
    peer_mapping_queue_frame: pd.DataFrame | None,
    limit_per_lane: int = 2,
) -> list[dict[str, object]]:
    cards: list[dict[str, object]] = []

    if sec_stage_queue_frame is not None and not sec_stage_queue_frame.empty:
        sec_rows = sec_stage_queue_frame.copy()
        if "priority" in sec_rows.columns:
            sec_rows["priority"] = pd.to_numeric(sec_rows["priority"], errors="coerce")
            sec_rows = sec_rows.sort_values(["priority", "price_history_days", "ticker"], ascending=[True, False, True], kind="stable")
        for _, row in sec_rows.head(limit_per_lane).iterrows():
            target_file = format_missing(row.get("target_file"), "")
            staged_fundamentals_import = target_file == "data/imports/fundamentals.csv"
            command = (
                preferred_row_command(
                    row,
                    (
                        "make imports-validate"
                        if staged_fundamentals_import
                        else ticker_focus_command("fundamentals", row.get("ticker"), fallback=format_missing(row.get("example_command"), ""))
                    ),
                )
                if staged_fundamentals_import or format_missing(row.get("focus_command"), "")
                else ticker_focus_command("fundamentals", row.get("ticker"), fallback=format_missing(row.get("example_command"), ""))
            )
            fallback_action = (
                f"Staged fundamentals import is waiting in {target_file}. "
                "Run make imports-validate, then make imports-preview, then make imports-apply."
                if staged_fundamentals_import
                else command_family_fallback(command, "Review fundamentals path.")
            )
            if not staged_fundamentals_import and "runbook-" in command.lower():
                fallback_action = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
            cards.append(
                {
                    "kicker": "DCF TARGET",
                    "title": format_missing(row.get("ticker"), "Ticker"),
                    "body": (
                        f"{compact_reason(row.get('recommended_action') or fallback_action, max_sentences=1, max_chars=150)} "
                        f"Missing: {format_missing(row.get('missing_required_for_dcf'), 'Not specified')}."
                    ),
                    "badges": [
                        "holding" if bool(row.get("is_holding", False)) else format_missing(row.get("theme"), "theme"),
                        f"{format_value(row.get('price_history_days'), fallback='0')} price rows",
                    ],
                    "command": command,
                }
            )

    if peer_mapping_queue_frame is not None and not peer_mapping_queue_frame.empty:
        peer_rows = peer_mapping_queue_frame.copy()
        if "priority" in peer_rows.columns:
            peer_rows["priority"] = pd.to_numeric(peer_rows["priority"], errors="coerce")
            peer_rows = peer_rows.sort_values(["priority", "ticker"], kind="stable")
        for _, row in peer_rows.head(limit_per_lane).iterrows():
            target_file = format_missing(row.get("target_file"), "")
            staged_peer_import = target_file == "data/imports/peers.csv"
            command = (
                preferred_row_command(row, "make imports-validate")
                if staged_peer_import
                else (
                    preferred_row_command(
                        row,
                        ticker_focus_command("peers", row.get("ticker"), fallback=format_missing(row.get("example_command"), "")),
                    )
                    if format_missing(row.get("focus_command"), "")
                    else ticker_focus_command("peers", row.get("ticker"), fallback=format_missing(row.get("example_command"), ""))
                )
            )
            fallback_action = (
                f"Staged peer import is waiting in {target_file}. "
                "Run make imports-validate, then make imports-preview, then make imports-apply."
                if staged_peer_import
                else command_family_fallback(command, "Review peer path.")
            )
            if not staged_peer_import and "runbook-" in command.lower():
                fallback_action = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
            cards.append(
                {
                    "kicker": "PEER TARGET",
                    "title": format_missing(row.get("ticker"), "Ticker"),
                    "body": (
                        f"{compact_reason(row.get('recommended_action') or fallback_action, max_sentences=1, max_chars=150)} "
                        f"Missing: {format_missing(row.get('missing_required_for_peer_relative'), 'Not specified')}."
                    ),
                    "badges": [
                        "holding" if bool(row.get("is_holding", False)) else format_missing(row.get("theme"), "theme"),
                        "dcf ready" if str(row.get("dcf_ready", "")).lower() in {"true", "1"} else "dcf blocked",
                    ],
                    "command": command,
                }
            )

    if cards:
        return cards
    return [
        {
            "kicker": "DEEP TARGETS",
            "title": "No DCF or peer targets yet",
            "body": "Run make onboarding to refresh the onboarding outputs and surface explicit fundamentals and peer-relative target queues.",
            "badges": ["read-only"],
            "command": "make onboarding",
        }
    ]


def overview_deep_research_target_cards(
    sec_stage_queue_frame: pd.DataFrame | None,
    peer_mapping_queue_frame: pd.DataFrame | None,
    limit_per_lane: int = 2,
) -> list[dict[str, object]]:
    cards: list[dict[str, object]] = []

    if sec_stage_queue_frame is not None and not sec_stage_queue_frame.empty:
        sec_rows = sec_stage_queue_frame.copy()
        if "priority" in sec_rows.columns:
            sec_rows["priority"] = pd.to_numeric(sec_rows["priority"], errors="coerce")
            sec_rows = sec_rows.sort_values(["priority", "price_history_days", "ticker"], ascending=[True, False, True], kind="stable")
        for _, row in sec_rows.head(limit_per_lane).iterrows():
            target_file = format_missing(row.get("target_file"), "")
            staged_fundamentals_import = target_file == "data/imports/fundamentals.csv"
            command = (
                preferred_row_command(
                    row,
                    (
                        "make imports-validate"
                        if staged_fundamentals_import
                        else ticker_focus_command("fundamentals", row.get("ticker"), fallback=format_missing(row.get("example_command"), ""))
                    ),
                )
                if staged_fundamentals_import or format_missing(row.get("focus_command"), "")
                else ticker_focus_command("fundamentals", row.get("ticker"), fallback=format_missing(row.get("example_command"), ""))
            )
            fallback_action = (
                f"Staged fundamentals import is waiting in {target_file}. "
                "Run make imports-validate, then make imports-preview, then make imports-apply."
                if staged_fundamentals_import
                else command_family_fallback(command, "Review fundamentals path.")
            )
            if not staged_fundamentals_import and "runbook-" in command.lower():
                fallback_action = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
            cards.append(
                {
                    "kicker": "UNLOCK DCF",
                    "title": format_missing(row.get("ticker"), "Ticker"),
                    "body": (
                        f"{format_missing(row.get('missing_required_for_dcf'), 'Not specified')}. "
                        f"{compact_reason(row.get('recommended_action') or fallback_action, max_sentences=1, max_chars=140)}"
                    ),
                    "badges": [
                        "holding" if bool(row.get("is_holding", False)) else format_missing(row.get("theme"), "theme"),
                        f"P{format_value(row.get('priority'), fallback='-')}",
                    ],
                    "command": command,
                }
            )

    if peer_mapping_queue_frame is not None and not peer_mapping_queue_frame.empty:
        peer_rows = peer_mapping_queue_frame.copy()
        if "priority" in peer_rows.columns:
            peer_rows["priority"] = pd.to_numeric(peer_rows["priority"], errors="coerce")
            peer_rows = peer_rows.sort_values(["priority", "ticker"], kind="stable")
        for _, row in peer_rows.head(limit_per_lane).iterrows():
            target_file = format_missing(row.get("target_file"), "")
            staged_peer_import = target_file == "data/imports/peers.csv"
            command = (
                preferred_row_command(row, "make imports-validate")
                if staged_peer_import
                else (
                    preferred_row_command(
                        row,
                        ticker_focus_command("peers", row.get("ticker"), fallback=format_missing(row.get("example_command"), "")),
                    )
                    if format_missing(row.get("focus_command"), "")
                    else ticker_focus_command("peers", row.get("ticker"), fallback=format_missing(row.get("example_command"), ""))
                )
            )
            fallback_action = (
                f"Staged peer import is waiting in {target_file}. "
                "Run make imports-validate, then make imports-preview, then make imports-apply."
                if staged_peer_import
                else command_family_fallback(command, "Review peer path.")
            )
            if not staged_peer_import and "runbook-" in command.lower():
                fallback_action = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
            cards.append(
                {
                    "kicker": "UNLOCK PEERS",
                    "title": format_missing(row.get("ticker"), "Ticker"),
                    "body": (
                        f"{format_missing(row.get('missing_required_for_peer_relative'), 'Not specified')}. "
                        f"{compact_reason(row.get('recommended_action') or fallback_action, max_sentences=1, max_chars=140)}"
                    ),
                    "badges": [
                        "holding" if bool(row.get("is_holding", False)) else format_missing(row.get("theme"), "theme"),
                        "dcf ready" if str(row.get("dcf_ready", "")).lower() in {"true", "1"} else "dcf blocked",
                    ],
                    "command": command,
                }
            )

    if cards:
        return cards
    return [
        {
            "kicker": "DEEP TARGETS",
            "title": "No DCF or peer targets yet",
            "body": "Run make onboarding to refresh the onboarding outputs and surface the next exact fundamentals and peer-relative targets.",
            "badges": ["read-only", "data moat"],
            "command": "make onboarding",
        }
    ]


def overview_price_target_cards(price_worklist_frame: pd.DataFrame | None, limit: int = 3) -> list[dict[str, object]]:
    if price_worklist_frame is None or price_worklist_frame.empty:
        return [
            {
                "kicker": "PRICE TARGET",
                "title": "No price targets yet",
                "body": "Run make onboarding to refresh the onboarding outputs and surface the next exact history targets for Monthly Picks, track record, and fuller local coverage.",
                "badges": ["read-only", "data moat"],
                "command": "make onboarding",
            }
        ]

    ordered = price_worklist_frame.copy()
    sort_columns: list[str] = []
    if "priority" in ordered.columns:
        ordered["priority"] = pd.to_numeric(ordered["priority"], errors="coerce")
        sort_columns.append("priority")
    if "rows_needed_for_next_goal" in ordered.columns:
        ordered["rows_needed_for_next_goal"] = pd.to_numeric(ordered["rows_needed_for_next_goal"], errors="coerce")
        sort_columns.append("rows_needed_for_next_goal")
    if "ticker" in ordered.columns:
        sort_columns.append("ticker")
    if sort_columns:
        ordered = ordered.sort_values(sort_columns, kind="stable")

    cards: list[dict[str, object]] = []
    for _, row in ordered.head(limit).iterrows():
        target_file = format_missing(row.get("target_file"), "")
        manual_command = normalize_operator_command(format_missing(row.get("example_command"), ""))
        staged_summary = compact_reason(row.get("safe_next_step"), max_sentences=1, max_chars=140)
        follow_through = ""
        if target_file == "data/imports/prices.csv":
            default_staged_summary = "Run make price-validate, make price-preview, and make price-apply for the staged price import."
            if staged_summary in {"", "Not available"} or (
                "make price-validate" not in staged_summary
                or "make price-preview" not in staged_summary
                or "make price-apply" not in staged_summary
            ):
                staged_summary = default_staged_summary
            follow_through = (
                f" Local fallback: {manual_command}. {staged_summary}"
                if manual_command and staged_summary not in {"", "Not available"}
                else f" Local fallback: {manual_command}."
                if manual_command
                else f" {staged_summary}"
                if staged_summary not in {"", "Not available"}
                else ""
            )
        cards.append(
            {
                "kicker": format_missing(row.get("next_price_goal"), "Price target").upper(),
                "title": format_missing(row.get("ticker"), "Ticker"),
                "body": (
                    f"{format_value(row.get('rows_needed_for_next_goal'), fallback='0')} rows still needed. "
                    f"Target: {format_value(row.get('next_target_history_rows'), fallback='0')} rows. "
                    f"Start from: {format_missing(row.get('suggested_start_date'), 'Not available')}.{follow_through}"
                ),
                "badges": [
                    f"{format_value(row.get('price_history_days'), fallback='0')} local rows",
                    f"P{format_value(row.get('priority'), fallback='-')}",
                ],
                "command": preferred_row_command(
                    row,
                    ticker_focus_command("prices", row.get("ticker"), "make runbook-prices-broader"),
                ),
            }
        )
    return cards


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
                "command": "make runbook-prices-broader",
            },
            {
                "kicker": "DCF READY",
                "title": str(coverage_summary["dcf_ready_tickers"]),
                "body": "Tickers with sufficient local valuation fields for DCF calculations.",
                "badges": ["fundamentals"],
                "command": "make runbook-fundamentals-broader",
            },
            {
                "kicker": "PEER READY",
                "title": str(coverage_summary["peer_ready_tickers"]),
                "body": "Tickers with manual peer mapping plus enough peer context for relative valuation.",
                "badges": ["peers.csv"],
                "command": "make runbook-peers-broader",
            },
            {
                "kicker": "OPTIONAL ONLY",
                "title": str(coverage_summary["optional_only_missing_tickers"]),
                "body": "Tickers missing only optional earnings or analyst-estimate files rather than core research inputs.",
                "badges": ["safe partials"],
                "command": "make onboarding",
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
                "command": "make data-sources",
            },
            {
                "kicker": "PARTIAL",
                "title": str(partial),
                "body": "Datasets where the project can proceed, but freshness or completeness is still limited.",
                "badges": ["transparent gaps"],
                "command": "make data-sources",
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
                "command": "make price-status TOP_N=10",
            },
            {
                "kicker": "SKIPPED",
                "title": str(counts.get("skipped_fresh", 0)),
                "body": "Tickers skipped because local rows already looked fresh enough.",
                "badges": ["fresh local data"],
                "command": "make price-status TOP_N=10",
            },
            {
                "kicker": "ISSUES",
                "title": str(problem_total),
                "body": (
                    "Parse, source, or network failures now surface here instead of hiding in logs. "
                    "For downloaded files, run make price-normalize, make price-validate, "
                    "make price-preview, and make price-apply."
                ),
                "badges": ["make price-status TOP_N=10", "manual fallback"],
                "command": "make price-status TOP_N=10",
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
                "command": "make imports-preview",
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
            "command": "make validate-data",
        },
        {
            "kicker": "OPTIONAL MISSING",
            "title": str(missing_count),
            "body": "Optional files can stay missing without breaking the research pipeline.",
            "badges": ["partial safe"],
            "command": "make validate-data",
        },
    ]


def data_health_fix_first_cards(actions_frame: pd.DataFrame | None, limit: int = 4) -> list[tuple[str, str, str, str]]:
    if actions_frame is None or actions_frame.empty:
        return [
            (
                "No fix-first actions yet",
                "Start with make onboarding so the local action set refreshes before you follow the printed focus or runbook path for prices, fundamentals, peers, earnings, and estimate gaps.",
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
        command = preferred_row_command(
            row,
            ticker_focus_command(row.get("dataset"), row.get("ticker"), "make data-wizard TOP_N=10"),
        )
        target_file = format_missing(row.get("target_file"), "")
        staged_follow_through = ""
        if target_file == "data/imports/fundamentals.csv":
            command = "make imports-validate"
            staged_follow_through = "Run make imports-validate, then make imports-preview, then make imports-apply for the staged fundamentals import."
        elif target_file == "data/imports/peers.csv":
            command = "make imports-validate"
            staged_follow_through = "Run make imports-validate, then make imports-preview, then make imports-apply for the staged peer import."
        elif target_file == "data/imports/prices.csv":
            command = "make price-validate"
            staged_follow_through = "Run make price-validate, then make price-preview, then make price-apply for the staged price import."
        action = compact_reason(
            row.get("recommended_action") or command_family_fallback(command, "Review local data coverage."),
            max_sentences=1,
            max_chars=150,
        )
        lowered_command = command.lower()
        if "runbook-" in lowered_command:
            action = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
        elif lowered_command == "make imports-validate":
            normalized_action = action.lower()
            if "make imports-preview" not in normalized_action or "make imports-apply" not in normalized_action:
                action = "Run make imports-validate, then make imports-preview, then make imports-apply so staged local data is reviewed before apply."
        elif lowered_command == "make price-validate":
            normalized_action = action.lower()
            if "make price-preview" not in normalized_action or "make price-apply" not in normalized_action:
                action = "Run make price-validate, then make price-preview, then make price-apply so staged price rows are reviewed before apply."
        if staged_follow_through:
            normalized_action = action.lower()
            if target_file == "data/imports/prices.csv":
                if (
                    "make price-validate" not in normalized_action
                    or "make price-preview" not in normalized_action
                    or "make price-apply" not in normalized_action
                ):
                    action = staged_follow_through
            else:
                if (
                    "make imports-validate" not in normalized_action
                    or "make imports-preview" not in normalized_action
                    or "make imports-apply" not in normalized_action
                ):
                    action = staged_follow_through
        body = action if not reason or reason == "Not available" else f"{reason} {action}".strip()
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
                "command": "make data-wizard TOP_N=10",
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
        command = format_missing(first.get("focus_command"), "")
        if not command or command == "Not available":
            command = preferred_row_command(
                first,
                ticker_focus_command(
                    first.get("blocking_dataset"),
                    first.get("ticker"),
                    "make data-wizard TOP_N=10",
                ),
            )
        current_status = format_missing(first.get("current_status"), "")
        why_it_matters = compact_reason(first.get("why_it_matters"), max_sentences=1, max_chars=140)
        recommended_action = compact_reason(first.get("recommended_action"), max_sentences=1, max_chars=150)
        target_file = format_missing(first.get("target_file"), "")
        staged_follow_through = ""
        if target_file == "data/imports/fundamentals.csv":
            command = "make imports-validate"
            staged_follow_through = "Run make imports-validate, then make imports-preview, then make imports-apply for the staged fundamentals import."
        elif target_file == "data/imports/peers.csv":
            command = "make imports-validate"
            staged_follow_through = "Run make imports-validate, then make imports-preview, then make imports-apply for the staged peer import."
        elif target_file == "data/imports/prices.csv":
            command = "make price-validate"
            staged_follow_through = "Run make price-validate, then make price-preview, then make price-apply for the staged price import."
        if staged_follow_through:
            normalized_action = recommended_action.lower()
            if target_file == "data/imports/prices.csv":
                if (
                    "make price-validate" not in normalized_action
                    or "make price-preview" not in normalized_action
                    or "make price-apply" not in normalized_action
                ):
                    recommended_action = staged_follow_through
            else:
                if (
                    "make imports-validate" not in normalized_action
                    or "make imports-preview" not in normalized_action
                    or "make imports-apply" not in normalized_action
                ):
                    recommended_action = staged_follow_through
        lowered_command = command.lower()
        if "runbook-" in lowered_command:
            recommended_action = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
        elif lowered_command == "make imports-validate":
            normalized_action = recommended_action.lower()
            if "make imports-preview" not in normalized_action or "make imports-apply" not in normalized_action:
                recommended_action = "Run make imports-validate, then make imports-preview, then make imports-apply so staged local data is reviewed before apply."
        elif lowered_command == "make price-validate":
            normalized_action = recommended_action.lower()
            if "make price-preview" not in normalized_action or "make price-apply" not in normalized_action:
                recommended_action = "Run make price-validate, then make price-preview, then make price-apply so staged price rows are reviewed before apply."
        body_parts = [f"Start with {ticker}."]
        if current_status and current_status != "Not available":
            body_parts.append(f"Current blocker: {current_status}.")
        if why_it_matters and why_it_matters != "Not available":
            body_parts.append(why_it_matters)
        if recommended_action and recommended_action != "Not available":
            body_parts.append(recommended_action)
        if len(body_parts) == 1:
            body_parts.append(command_family_fallback(command, review_path_fallback(first.get("blocking_dataset"))))
        cards.append(
            {
                "kicker": kicker,
                "title": f"{len(subset)} blocker{'s' if len(subset) != 1 else ''}",
                "body": " ".join(body_parts),
                "badges": [format_missing(first.get("blocking_dataset"), "data"), command],
                "command": command,
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
            (
                f"{staged_rows} staged ticker rows are waiting for review before make universe-apply."
                if staged_exists
                else "No staged universe import is waiting. Build one with make universe-preview before make universe-apply."
            ),
            "make universe-preview",
            "warning" if staged_exists else "neutral",
        ),
        (
            "Safe expansion path",
            "Run make universe-preview first, inspect the staged CSV, then run make universe-apply from the CLI only after review.",
            "make universe-preview",
            "neutral",
        ),
        (
            "Manual fallback",
            "If SMH or remote sources degrade, run make templates, then fill data/custom_universe.csv with verified tickers only before any staged universe apply step.",
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


def bool_series(frame: pd.DataFrame | None, column: str) -> pd.Series:
    if frame is None or frame.empty or column not in frame.columns:
        return pd.Series(dtype=bool)
    values = frame[column]
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False).astype(bool)
    return values.fillna("").astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def ticker_set_from_bool(frame: pd.DataFrame | None, column: str) -> set[str]:
    if frame is None or frame.empty or "ticker" not in frame.columns:
        return set()
    mask = bool_series(frame, column)
    if mask.empty:
        return set()
    return set(frame.loc[mask, "ticker"].dropna().astype(str).str.upper().str.strip())


READINESS_PROGRESS_FEATURES = [
    ("price_ready", "Price"),
    ("momentum_ready", "Momentum"),
    ("market_direction_ready", "Market direction"),
    ("liquidity_ready", "Liquidity"),
    ("correlation_ready", "Correlation"),
    ("fundamentals_ready", "Fundamentals"),
    ("dcf_ready", "DCF"),
    ("peer_ready", "Peers"),
    ("earnings_ready", "Earnings"),
    ("analyst_estimates_ready", "Analyst estimates"),
]
PRIOR_READINESS_FILENAMES = [
    "ticker_readiness_report.previous.csv",
    "previous_ticker_readiness_report.csv",
    "ticker_readiness_report_prior.csv",
    "ticker_readiness_baseline.csv",
]


def _frame_bool_series(frame: pd.DataFrame, column: str) -> pd.Series:
    values = bool_series(frame, column)
    if values.empty:
        return pd.Series(False, index=frame.index)
    return values.reindex(frame.index, fill_value=False)


def _latest_frame_timestamp(frame: pd.DataFrame | None) -> str:
    if frame is None or frame.empty:
        return ""
    for column in ("updated_at", "generated_at", "last_success_at", "last_attempted_at"):
        if column not in frame.columns:
            continue
        values = frame[column].dropna().astype(str).str.strip()
        values = values.loc[~values.str.lower().isin({"", "nan", "none", "null", "not available"})]
        if not values.empty:
            return str(values.max())
    return ""


def load_prior_ticker_readiness_report(data_dir: Path = DATA_DIR) -> tuple[pd.DataFrame | None, str]:
    reports_dir = data_dir / "reports"
    for filename in PRIOR_READINESS_FILENAMES:
        path = reports_dir / filename
        if path.exists():
            frame, message = load_output(path)
            return frame, str(path) if frame is not None else (message or str(path))
    return None, "No prior ticker readiness snapshot found in data/reports."


def build_readiness_change_frame(
    current_frame: pd.DataFrame | None,
    previous_frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    columns = [
        "feature",
        "current_ready",
        "previous_ready",
        "delta_ready",
        "current_blocked",
        "newly_ready_tickers",
    ]
    if current_frame is None or current_frame.empty:
        return pd.DataFrame(columns=columns)

    current = current_frame.copy()
    previous = previous_frame.copy() if previous_frame is not None else pd.DataFrame()
    if "ticker" in current.columns:
        current["ticker"] = current["ticker"].astype(str).str.upper().str.strip()
    if not previous.empty and "ticker" in previous.columns:
        previous["ticker"] = previous["ticker"].astype(str).str.upper().str.strip()

    rows: list[dict[str, object]] = []
    for column, label in READINESS_PROGRESS_FEATURES:
        current_ready = _frame_bool_series(current, column)
        current_ready_count = int(current_ready.sum())
        previous_ready_count: int | None = None
        delta_ready: int | None = None
        newly_ready = ""
        if not previous.empty and column in previous.columns:
            previous_ready = _frame_bool_series(previous, column)
            previous_ready_count = int(previous_ready.sum())
            delta_ready = current_ready_count - previous_ready_count
            if "ticker" in current.columns and "ticker" in previous.columns:
                previous_ready_tickers = set(previous.loc[previous_ready, "ticker"].dropna().astype(str).str.upper().str.strip())
                current_ready_tickers = current.loc[current_ready, "ticker"].dropna().astype(str).str.upper().str.strip()
                newly_ready = ", ".join([ticker for ticker in current_ready_tickers if ticker not in previous_ready_tickers][:8])

        blocked_count = 0
        blocker_name = column.removesuffix("_ready")
        if "blocked_features" in current.columns:
            blocked_count = int(
                current["blocked_features"]
                .fillna("")
                .astype(str)
                .str.contains(rf"(?:^|,\s*){re.escape(blocker_name)}(?:$|,)", case=False, regex=True)
                .sum()
            )
        rows.append(
            {
                "feature": label,
                "current_ready": current_ready_count,
                "previous_ready": previous_ready_count,
                "delta_ready": delta_ready,
                "current_blocked": blocked_count,
                "newly_ready_tickers": newly_ready,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def readiness_recent_progress_cards(
    current_frame: pd.DataFrame | None,
    previous_frame: pd.DataFrame | None = None,
    feature_summary_frame: pd.DataFrame | None = None,
    previous_snapshot_label: str = "",
) -> list[dict[str, object]]:
    if current_frame is None or current_frame.empty:
        return [
            {
                "kicker": "WHAT CHANGED",
                "title": "Readiness report missing",
                "body": "Run make readiness before comparing current and prior product status.",
                "badges": ["blocked"],
                "command": "make readiness",
            }
        ]

    current = current_frame.copy()
    total = int(len(current))
    active = int(_frame_bool_series(current, "in_active_universe").sum()) if "in_active_universe" in current.columns else 0
    state_counts = (
        current.get("overall_readiness_state", pd.Series(dtype=object))
        .fillna("unknown")
        .astype(str)
        .str.lower()
        .value_counts()
    )
    change_frame = build_readiness_change_frame(current, previous_frame)
    latest = _latest_frame_timestamp(current)
    prior_latest = _latest_frame_timestamp(previous_frame)
    prior_label = format_missing(previous_snapshot_label, "data/reports/ticker_readiness_report.previous.csv")
    price_ready = int(change_frame.loc[change_frame["feature"].eq("Price"), "current_ready"].max() or 0)
    dcf_ready = int(change_frame.loc[change_frame["feature"].eq("DCF"), "current_ready"].max() or 0)
    peer_ready = int(change_frame.loc[change_frame["feature"].eq("Peers"), "current_ready"].max() or 0)
    cards = [
        {
            "kicker": "READINESS NOW",
            "title": f"{price_ready}/{total} price-ready",
            "body": (
                f"Active universe: {active}. DCF-ready: {dcf_ready}. Peer-ready: {peer_ready}. "
                f"Blocked: {int(state_counts.get('blocked', 0))}. Partial: {int(state_counts.get('partial', 0))}. "
                f"Latest generated: {format_missing(latest)}."
            ),
            "badges": ["current counts", "readiness first"],
            "command": "make readiness",
        }
    ]

    has_previous = previous_frame is not None and not previous_frame.empty
    if has_previous:
        changed = change_frame.dropna(subset=["delta_ready"]).copy()
        changed["abs_delta"] = pd.to_numeric(changed["delta_ready"], errors="coerce").abs()
        changed = changed.sort_values(["abs_delta", "feature"], ascending=[False, True], kind="stable")
        top_changed = changed.loc[changed["abs_delta"].gt(0)].head(4)
        changed_text = ", ".join(
            f"{row.feature} {'+' if int(row.delta_ready) >= 0 else ''}{int(row.delta_ready)}"
            for row in top_changed.itertuples(index=False)
        )
        newly_ready = next(
            (
                str(value)
                for value in changed["newly_ready_tickers"].dropna().astype(str)
                if value.strip()
            ),
            "",
        )
        cards.append(
            {
                "kicker": "WHAT CHANGED",
                "title": changed_text or "No ready-count change",
                "body": (
                    f"Compared with prior snapshot {prior_label}; prior generated: {format_missing(prior_latest)}. "
                    f"Newly ready tickers: {newly_ready or 'none detected'}. "
                    "This is a count comparison only; review source/freshness before interpreting analysis."
                ),
                "badges": ["previous vs current", "no fabricated deltas"],
                "command": "make readiness",
            }
        )
    else:
        cards.append(
            {
                "kicker": "WHAT CHANGED",
                "title": "Current-only baseline",
                "body": (
                    "No prior readiness snapshot was found, so the dashboard shows current counts without pretending a delta exists. "
                    "Run make readiness-snapshot before the next targeted refresh or import, then run make readiness to compare real before/after counts from data/reports/ticker_readiness_report.previous.csv."
                ),
                "badges": ["no prior snapshot", "data-honest"],
                "command": "make readiness-snapshot",
            }
        )

    cards.append(
        {
            "kicker": "SNAPSHOT WORKFLOW",
            "title": "Snapshot -> targeted update -> compare",
            "body": (
                "Use make readiness-snapshot, then one targeted refresh/import workflow, then make readiness. "
                "The dashboard compares only saved local CSV snapshots and never invents progress."
            ),
            "badges": ["operator workflow", "copy only"],
            "command": "make readiness-snapshot",
        }
    )

    blocked_rows: list[str] = []
    if feature_summary_frame is not None and not feature_summary_frame.empty:
        summary = feature_summary_frame.copy()
        if "blocked_count" in summary.columns:
            summary["blocked_count"] = pd.to_numeric(summary["blocked_count"], errors="coerce").fillna(0).astype(int)
            summary = summary.sort_values(["blocked_count", "feature"], ascending=[False, True], kind="stable")
            for row in summary.head(4).itertuples(index=False):
                feature = format_missing(getattr(row, "feature", ""), "feature")
                blocked = int(getattr(row, "blocked_count", 0) or 0)
                blocked_rows.append(f"{feature}: {blocked}")
    if not blocked_rows and not change_frame.empty:
        blocked = change_frame.sort_values(["current_blocked", "feature"], ascending=[False, True], kind="stable").head(4)
        blocked_rows = [f"{row.feature}: {int(row.current_blocked)}" for row in blocked.itertuples(index=False)]
    cards.append(
        {
            "kicker": "STILL BLOCKED",
            "title": ", ".join(blocked_rows[:2]) or "No blockers reported",
            "body": (
                (", ".join(blocked_rows) if blocked_rows else "No current blocker summary is available.")
                + " Use capped, feature-specific worklists instead of rendering or refreshing all master rows."
            ),
            "badges": ["top blocked features", "row-limited"],
            "command": "make onboarding TOP_N=10",
        }
    )
    cards.append(
        {
            "kicker": "SOURCE / FRESHNESS",
            "title": "Copyable commands only",
            "body": (
                "Dashboard cards display local commands and paths only; they do not execute imports, refreshes, or external actions. "
                "Earnings and analyst estimates remain unavailable until trusted local CSV rows validate."
            ),
            "badges": ["copy only", "research-only"],
            "command": "make imports-validate",
        }
    )
    return cards


def dashboard_readiness_summary(
    coverage_frame: pd.DataFrame | None,
    dcf_readiness_frame: pd.DataFrame | None,
    earnings_readiness_frame: pd.DataFrame | None,
    analyst_readiness_frame: pd.DataFrame | None,
    ticker_readiness_frame: pd.DataFrame | None = None,
) -> dict[str, object]:
    universe_count = 0 if coverage_frame is None or coverage_frame.empty else len(coverage_frame)
    master_count = 0 if ticker_readiness_frame is None or ticker_readiness_frame.empty else int(bool_series(ticker_readiness_frame, "in_master_universe").sum())
    active_count = 0 if ticker_readiness_frame is None or ticker_readiness_frame.empty else int(bool_series(ticker_readiness_frame, "in_active_universe").sum())
    price_ready = len(ticker_set_from_bool(coverage_frame, "has_prices"))
    momentum_ready = len(ticker_set_from_bool(coverage_frame, "usable_for_momentum"))
    peer_ready = len(ticker_set_from_bool(coverage_frame, "peer_ready"))
    liquidity_ready = int(bool_series(ticker_readiness_frame, "liquidity_ready").sum()) if ticker_readiness_frame is not None else 0
    correlation_ready = int(bool_series(ticker_readiness_frame, "correlation_ready").sum()) if ticker_readiness_frame is not None else 0
    fundamentals_ready = int(bool_series(ticker_readiness_frame, "fundamentals_ready").sum()) if ticker_readiness_frame is not None else 0
    blocked_by_data = 0
    excluded_count = 0
    if ticker_readiness_frame is not None and not ticker_readiness_frame.empty and "overall_readiness_state" in ticker_readiness_frame.columns:
        state_series = ticker_readiness_frame["overall_readiness_state"].fillna("").astype(str).str.lower()
        blocked_by_data = int(state_series.eq("blocked").sum())
        excluded_count = int(state_series.eq("excluded").sum())
    if ticker_readiness_frame is not None and not ticker_readiness_frame.empty and "dcf_ready" in ticker_readiness_frame.columns:
        dcf_ready = int(bool_series(ticker_readiness_frame, "dcf_ready").sum())
    else:
        dcf_ready = int(bool_series(dcf_readiness_frame, "is_dcf_ready").sum()) if dcf_readiness_frame is not None else 0
    dcf_excluded = 0
    if ticker_readiness_frame is not None and not ticker_readiness_frame.empty and "excluded_features" in ticker_readiness_frame.columns:
        dcf_excluded = int(
            ticker_readiness_frame["excluded_features"]
            .fillna("")
            .astype(str)
            .str.contains(r"\bdcf\b", case=False, na=False)
            .sum()
        )
    elif dcf_readiness_frame is not None and not dcf_readiness_frame.empty and "asset_type" in dcf_readiness_frame.columns:
        dcf_excluded = int(dcf_readiness_frame["asset_type"].fillna("company").astype(str).str.lower().ne("company").sum())
    earnings_ready = int(bool_series(earnings_readiness_frame, "has_trusted_earnings").sum()) if earnings_readiness_frame is not None else 0
    analyst_ready = int(bool_series(analyst_readiness_frame, "has_trusted_analyst_estimates").sum()) if analyst_readiness_frame is not None else 0
    updated_at = ""
    if ticker_readiness_frame is not None and not ticker_readiness_frame.empty and "updated_at" in ticker_readiness_frame.columns:
        updated_values = ticker_readiness_frame["updated_at"].dropna().astype(str).str.strip()
        if not updated_values.empty:
            updated_at = str(updated_values.max())
    missing_credentials = [
        name
        for name in ("STOOQ_API_KEY", "SEC_USER_AGENT")
        if not os.environ.get(name, "").strip()
    ]
    return {
        "universe_count": universe_count,
        "master_count": master_count or universe_count,
        "active_count": active_count or universe_count,
        "price_ready": price_ready,
        "momentum_ready": momentum_ready,
        "liquidity_ready": liquidity_ready,
        "correlation_ready": correlation_ready,
        "fundamentals_ready": fundamentals_ready,
        "dcf_ready": dcf_ready,
        "dcf_excluded": dcf_excluded,
        "peer_ready": peer_ready,
        "earnings_ready": earnings_ready,
        "analyst_ready": analyst_ready,
        "blocked_by_data": blocked_by_data,
        "excluded_count": excluded_count or dcf_excluded,
        "missing_credentials": missing_credentials,
        "updated_at": updated_at,
        "manual_import_paths": [
            "data/staged/prices/ -> make import-prices",
            "data/staged/fundamentals/ -> make import-fundamentals",
            "data/staged/earnings/ -> make import-earnings",
            "data/staged/analyst_estimates/ -> make import-analyst-estimates",
        ],
    }


def readiness_panel_cards(summary: dict[str, object]) -> list[dict[str, object]]:
    universe_count = int(summary.get("universe_count") or 0)
    missing_credentials = list(summary.get("missing_credentials") or [])
    credential_title = "Credentials configured" if not missing_credentials else ", ".join(missing_credentials)
    credential_body = (
        "Remote/staged helpers have the needed environment variables."
        if not missing_credentials
        else "Missing credentials block remote refresh or SEC staging; manual CSV workflows remain available."
    )
    return [
        {
            "kicker": "UNIVERSE",
            "title": f"{universe_count} tickers",
            "body": f"Master universe: {summary.get('master_count', universe_count)}. Active research universe: {summary.get('active_count', universe_count)}.",
            "badges": ["ready labels: ready / partial / blocked / excluded"],
        },
        {
            "kicker": "PRICE / MOMENTUM",
            "title": f"{summary.get('price_ready', 0)} price-covered / {summary.get('momentum_ready', 0)} momentum-ready",
            "body": "Momentum, liquidity, and correlation should be interpreted only for locally price-ready tickers.",
            "badges": ["analysis available" if summary.get("momentum_ready", 0) else "blocked"],
            "command": "make price-coverage",
        },
        {
            "kicker": "RISK READINESS",
            "title": f"{summary.get('liquidity_ready', 0)} liquidity / {summary.get('correlation_ready', 0)} correlation",
            "body": f"{summary.get('blocked_by_data', 0)} ticker(s) are currently blocked by data and {summary.get('excluded_count', 0)} feature exclusions are visible.",
            "badges": ["analysis available", "blocked listed"],
            "command": "make readiness",
        },
        {
            "kicker": "VALUATION",
            "title": f"{summary.get('dcf_ready', 0)} DCF-ready / {summary.get('peer_ready', 0)} peer-ready",
            "body": f"{summary.get('dcf_excluded', 0)} ETF/index proxy row(s) are excluded from operating-company DCF.",
            "badges": ["excluded handled", "not fabricated"],
            "command": "make dcf-readiness",
        },
        {
            "kicker": "OPTIONAL CONTEXT",
            "title": f"{summary.get('earnings_ready', 0)} earnings / {summary.get('analyst_ready', 0)} estimates",
            "body": "Earnings and analyst estimate sections stay unavailable until trusted canonical local CSV rows exist.",
            "badges": ["manual only"],
            "command": "make optional-context-readiness",
        },
        {
            "kicker": "CREDENTIALS",
            "title": credential_title,
            "body": credential_body,
            "badges": ["STOOQ_API_KEY", "SEC_USER_AGENT"],
        },
        {
            "kicker": "MANUAL IMPORTS",
            "title": "CSV fallback paths available",
            "body": "; ".join(str(path) for path in summary.get("manual_import_paths", [])),
            "badges": ["staged", "review/apply"],
            "command": "make imports-validate",
        },
    ]


MARKET_READINESS_FILTERS = [
    "All",
    "Price-ready only",
    "Momentum-ready only",
    "DCF-ready only",
    "Blocked by price",
    "Blocked by fundamentals",
    "Blocked by peers",
    "Earnings unavailable",
    "Analyst estimates unavailable",
]
MARKET_ASSET_FILTERS = ["All assets", "Companies only", "ETFs / index proxies"]
DEFAULT_MARKET_ROW_LIMIT = 200


def market_wide_readiness_summary(
    ticker_readiness_frame: pd.DataFrame | None,
    coverage_frame: pd.DataFrame | None = None,
    decisions_frame: pd.DataFrame | None = None,
) -> dict[str, object]:
    summary = dashboard_readiness_summary(
        coverage_frame,
        None,
        None,
        None,
        ticker_readiness_frame,
    )
    decisions = {} if decisions_frame is None or decisions_frame.empty or "decision_bucket" not in decisions_frame.columns else {
        str(bucket): int(count)
        for bucket, count in decisions_frame["decision_bucket"].fillna("Not available").astype(str).value_counts().items()
    }
    summary["decision_buckets"] = decisions
    return summary


def feature_readiness_cards(feature_summary_frame: pd.DataFrame | None, *, limit: int = 6) -> list[dict[str, object]]:
    if feature_summary_frame is None or feature_summary_frame.empty:
        return [
            {
                "kicker": "FEATURE READINESS",
                "title": "Summary not generated",
                "body": "Run make readiness to build data/reports/feature_readiness_summary.csv before reviewing feature-level product status.",
                "badges": ["blocked"],
                "command": "make readiness",
            }
        ]
    frame = feature_summary_frame.copy()
    for column in ["ready_count", "partial_count", "blocked_count", "excluded_count", "total_count"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0).astype(int)
    if "blocked_count" in frame.columns:
        frame = frame.sort_values(["blocked_count", "ready_count"], ascending=[False, True]).copy()
    cards: list[dict[str, object]] = []
    for _, row in frame.head(limit).iterrows():
        feature = format_missing(row.get("feature"), "Feature")
        ready = int(row.get("ready_count") or 0)
        partial = int(row.get("partial_count") or 0)
        blocked = int(row.get("blocked_count") or 0)
        excluded = int(row.get("excluded_count") or 0)
        total = int(row.get("total_count") or 0)
        blocker = format_missing(row.get("top_blocker"), "No dominant blocker")
        section = format_missing(row.get("dashboard_section"), "Dashboard")
        cards.append(
            {
                "kicker": section.upper(),
                "title": f"{feature}: {ready}/{total} ready",
                "body": f"Partial: {partial}. Blocked: {blocked}. Excluded: {excluded}. Top blocker: {blocker}.",
                "badges": ["feature readiness", "product status"],
                "command": str(row.get("next_action") or "make readiness"),
            }
        )
    return cards


def peer_readiness_product_cards(
    peer_readiness_frame: pd.DataFrame | None,
    peer_mapping_queue_frame: pd.DataFrame | None = None,
) -> list[dict[str, object]]:
    if peer_readiness_frame is None or peer_readiness_frame.empty:
        return [
            {
                "kicker": "PEER READINESS",
                "title": "Report not generated",
                "body": "Run make readiness to build data/reports/peer_readiness_report.csv before reviewing peer workflow blockers.",
                "badges": ["blocked"],
                "command": "make readiness",
            }
        ]

    frame = peer_readiness_frame.copy()
    for column in [
        "peer_count",
        "ready_peer_count",
        "peer_price_ready_count",
        "peer_momentum_ready_count",
        "peer_fundamentals_ready_count",
        "peer_valuation_ready_count",
    ]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0).astype(int)
    peer_ready = bool_series(frame, "peer_ready")
    trend_ready = bool_series(frame, "peer_trend_comparison_ready")
    valuation_ready = bool_series(frame, "peer_valuation_comparison_ready")
    dcf_ready = bool_series(frame, "peer_dcf_comparison_ready")
    blocker_counts = {}
    if "peer_blocker_type" in frame.columns:
        blocker_counts = {
            str(key): int(value)
            for key, value in frame.loc[~peer_ready, "peer_blocker_type"].fillna("peer_blocked").astype(str).value_counts().items()
            if str(key).strip()
        }
    top_blocker = next(iter(blocker_counts), "peer_blocked")
    queue_rows = 0 if peer_mapping_queue_frame is None else int(len(peer_mapping_queue_frame))
    next_ticker = "Not available"
    next_reason = "Run make peer-mapping-queue TOP_N=25 to refresh prioritized peer work."
    if "peer_ready" in frame.columns:
        candidates = frame.loc[~peer_ready].copy()
        if "peer_blocker_type" in candidates.columns:
            candidates = candidates.sort_values(["peer_blocker_type", "ticker"], kind="stable")
        if not candidates.empty:
            next_ticker = format_missing(candidates.iloc[0].get("ticker"), "Ticker")
            next_reason = compact_reason(candidates.iloc[0].get("next_peer_action") or candidates.iloc[0].get("missing_peer_reason"), max_sentences=1, max_chars=140)
    return [
        {
            "kicker": "PEER READY",
            "title": f"{int(peer_ready.sum())}/{len(frame)} ready",
            "body": f"Trend-ready peers: {int(trend_ready.sum())}. Valuation comparison ready: {int(valuation_ready.sum())}. DCF peer comparison ready: {int(dcf_ready.sum())}.",
            "badges": ["peer workflow", "data-honest"],
            "command": "make readiness",
        },
        {
            "kicker": "TOP PEER BLOCKER",
            "title": top_blocker.replace("_", " "),
            "body": ", ".join(f"{key.replace('_', ' ')}: {value}" for key, value in list(blocker_counts.items())[:3]) or "No peer blockers reported.",
            "badges": ["specific blockers"],
            "command": "make peer-mapping-queue TOP_N=25",
        },
        {
            "kicker": "NEXT PEER TARGET",
            "title": next_ticker,
            "body": next_reason,
            "badges": ["manual research", "source-backed peers"],
            "command": f"make focus-peers TICKER={next_ticker}" if next_ticker != "Not available" else "make peer-mapping-queue TOP_N=25",
        },
        {
            "kicker": "PEER QUEUE",
            "title": f"{queue_rows} queued",
            "body": "Use capped peer worklists and staged CSV validation before relying on peer-relative context.",
            "badges": ["TOP_N safe", "preview first"],
            "command": "make peer-mapping-queue TOP_N=25",
        },
    ]


def peer_mapping_studio_summary_cards(
    peer_readiness_frame: pd.DataFrame | None,
    ticker_readiness_frame: pd.DataFrame | None = None,
) -> list[dict[str, object]]:
    if peer_readiness_frame is None or peer_readiness_frame.empty:
        return [
            {
                "kicker": "PEER STUDIO",
                "title": "No peer report",
                "body": "Run make readiness to generate peer readiness before using the mapping studio.",
                "badges": ["blocked"],
                "command": "make readiness",
            }
        ]

    frame = peer_readiness_frame.copy()
    if "ticker" in frame.columns:
        frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()
    if ticker_readiness_frame is not None and not ticker_readiness_frame.empty and "ticker" in ticker_readiness_frame.columns:
        readiness_columns = [
            column
            for column in ["ticker", "dcf_ready", "in_active_universe"]
            if column in ticker_readiness_frame.columns
        ]
        readiness = ticker_readiness_frame[readiness_columns].copy()
        readiness["ticker"] = readiness["ticker"].astype(str).str.upper().str.strip()
        frame = frame.merge(readiness, on="ticker", how="left", suffixes=("", "_ticker"))

    peer_ready = bool_series(frame, "peer_ready")
    dcf_ready = bool_series(frame, "dcf_ready")
    blocker = frame.get("peer_blocker_type", pd.Series("", index=frame.index)).fillna("").astype(str)
    missing_mapping = blocker.eq("missing_peer_mapping")
    peer_price_missing = blocker.eq("peer_price_missing")
    peer_fundamentals_missing = blocker.eq("peer_fundamentals_missing")
    valuation_blocked = blocker.eq("peer_valuation_blocked") | (~bool_series(frame, "peer_valuation_comparison_ready") & ~peer_ready)
    trend_ready = bool_series(frame, "peer_trend_comparison_ready")
    active = bool_series(frame, "in_active_universe")

    return [
        {
            "kicker": "DCF PEER BLOCKERS",
            "title": f"{int((dcf_ready & ~peer_ready).sum())} tickers",
            "body": "DCF-ready names that still need source-backed peer mappings or peer metric follow-through.",
            "badges": ["dcf-ready", "peer-blocked"],
            "command": "make peer-mapping-queue TOP_N=25",
        },
        {
            "kicker": "MISSING MAPPINGS",
            "title": f"{int(missing_mapping.sum())} tickers",
            "body": f"Active-universe affected: {int((missing_mapping & active).sum())}. Add transparent mappings through staged peers CSV and preview before apply.",
            "badges": ["manual peers", "source-backed"],
            "command": "make templates",
        },
        {
            "kicker": "PEER PRICE GAPS",
            "title": f"{int(peer_price_missing.sum())} tickers",
            "body": "Mapped peers exist, but at least one peer lacks enough price rows for trend comparison.",
            "badges": ["prices", "follow-through"],
            "command": "make price-worklist TOP_N=25",
        },
        {
            "kicker": "PEER FUNDAMENTALS",
            "title": f"{int(peer_fundamentals_missing.sum())} tickers",
            "body": "Mapped peers exist, but peer fundamentals are not ready for valuation comparison.",
            "badges": ["fundamentals", "valuation-blocked"],
            "command": "make sec-stage-queue TOP_N=25",
        },
        {
            "kicker": "TREND POSSIBLE",
            "title": f"{int(trend_ready.sum())} tickers",
            "body": "Peer trend comparison can be reviewed before peer valuation is fully unlocked.",
            "badges": ["trend ready", "not valuation"],
            "command": "make readiness",
        },
        {
            "kicker": "VALUATION BLOCKED",
            "title": f"{int(valuation_blocked.sum())} tickers",
            "body": "Do not show peer valuation conclusions until peer fundamentals and valuation metrics are present.",
            "badges": ["data-honest", "blocked"],
            "command": "make imports-validate",
        },
    ]


def peer_unlock_operator_cards(peer_unlock_worklist_frame: pd.DataFrame | None) -> list[dict[str, object]]:
    if peer_unlock_worklist_frame is None or peer_unlock_worklist_frame.empty:
        return [
            {
                "kicker": "PEER UNLOCK QUEUE",
                "title": "No unlock worklist",
                "body": "Run make readiness to generate outputs/peer_unlock_worklist.csv before editing trusted peer rows.",
                "badges": ["blocked"],
                "command": "make readiness",
            }
        ]

    frame = peer_unlock_worklist_frame.copy()
    if "ticker" in frame.columns:
        frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()
    if "priority" in frame.columns:
        frame["priority"] = pd.to_numeric(frame["priority"], errors="coerce").fillna(999).astype(int)
    else:
        frame["priority"] = 999
    if "workflow_group" not in frame.columns:
        frame["workflow_group"] = "peer_workflow"
    if "workflow_scope" not in frame.columns:
        frame["workflow_scope"] = "unknown_scope"
    workflow_counts = frame.get("workflow_group", pd.Series("peer_workflow", index=frame.index)).fillna("peer_workflow").astype(str).value_counts()
    scope_counts = frame.get("workflow_scope", pd.Series("unknown_scope", index=frame.index)).fillna("unknown_scope").astype(str).value_counts()
    priority_counts = frame["priority"].value_counts().sort_index()
    ordered = frame.sort_values(
        [
            "priority",
            "workflow_scope",
            "workflow_group",
            "ticker",
        ],
        ascending=[True, True, True, True],
        kind="stable",
    )
    top_row = ordered.iloc[0]
    top_ticker = format_missing(top_row.get("ticker"), "Ticker")
    top_summary = compact_reason(top_row.get("next_action_summary") or top_row.get("next_peer_action"), max_sentences=1, max_chars=180)
    input_file = format_missing(top_row.get("next_input_file"), "data/imports/peers.csv")
    validation = format_missing(top_row.get("validation_sequence"), "make templates -> make imports-validate -> make imports-preview -> make imports-apply")
    priority_text = ", ".join(f"P{int(key)}: {int(value)}" for key, value in priority_counts.head(4).items())
    workflow_text = ", ".join(f"{str(key).replace('_', ' ')}: {int(value)}" for key, value in workflow_counts.head(3).items())
    scope_text = ", ".join(f"{str(key).replace('_', ' ')}: {int(value)}" for key, value in scope_counts.head(3).items())
    return [
        {
            "kicker": "PEER UNLOCK QUEUE",
            "title": priority_text or f"{len(frame)} queued",
            "body": f"{len(frame)} peer unlock row(s). Scope mix: {scope_text or 'not available'}.",
            "badges": ["priority grouped", "row-limited"],
            "command": "make peer-mapping-queue TOP_N=25",
        },
        {
            "kicker": "NEXT PEER ROW",
            "title": top_ticker,
            "body": f"{top_summary} Input file: {input_file}. Validate with: {validation}.",
            "badges": ["source-backed", "preview before apply"],
            "command": str(top_row.get("focus_command") or f"make focus-peers TICKER={top_ticker}"),
        },
        {
            "kicker": "WORKFLOW GROUPS",
            "title": "What kind of peer data?",
            "body": workflow_text or "No workflow grouping is available yet.",
            "badges": ["mapping vs metrics", "no fallback peers"],
            "command": "make templates",
        },
    ]


def fundamentals_dcf_diagnostic_cards(
    ticker_readiness_frame: pd.DataFrame | None,
    dcf_readiness_frame: pd.DataFrame | None = None,
) -> list[dict[str, object]]:
    if ticker_readiness_frame is None or ticker_readiness_frame.empty:
        return [
            {
                "kicker": "FUNDAMENTALS / DCF",
                "title": "Readiness not generated",
                "body": "Run make readiness before reviewing fundamentals and DCF unlock diagnostics.",
                "badges": ["blocked"],
                "command": "make readiness",
            }
        ]

    frame = ticker_readiness_frame.copy()
    if "ticker" in frame.columns:
        frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()
    company = frame.get("asset_type", pd.Series("", index=frame.index)).fillna("").astype(str).str.lower().eq("company")
    price_ready = bool_series(frame, "price_ready")
    fundamentals_ready = bool_series(frame, "fundamentals_ready")
    dcf_ready = bool_series(frame, "dcf_ready")
    active = bool_series(frame, "in_active_universe")
    price_ready_missing_fundamentals = frame.loc[company & price_ready & ~fundamentals_ready].copy()
    dcf_ready_peer_blocked = frame.loc[company & dcf_ready & ~bool_series(frame, "peer_ready")].copy()
    active_missing = int((company & active & price_ready & ~fundamentals_ready).sum())

    next_ticker = "Not available"
    next_action = "Run make sec-stage-queue TOP_N=25 to refresh the fundamentals unlock queue."
    if not price_ready_missing_fundamentals.empty:
        ordered = price_ready_missing_fundamentals.assign(_active_rank=(~bool_series(price_ready_missing_fundamentals, "in_active_universe")).astype(int))
        ordered = ordered.sort_values(["_active_rank", "ticker"], kind="stable")
        next_row = ordered.iloc[0]
        next_ticker = format_missing(next_row.get("ticker"), "Ticker")
        next_action = compact_reason(next_row.get("next_action"), max_sentences=2, max_chars=220)

    missing_field_text = "No DCF readiness table available."
    excluded_count = 0
    if dcf_readiness_frame is not None and not dcf_readiness_frame.empty:
        dcf_frame = dcf_readiness_frame.copy()
        excluded_count = int(dcf_frame.get("asset_type", pd.Series("", index=dcf_frame.index)).fillna("").astype(str).str.lower().ne("company").sum())
        if "missing_dcf_fields" in dcf_frame.columns:
            missing_counts = (
                dcf_frame["missing_dcf_fields"]
                .fillna("")
                .astype(str)
                .str.split(",")
                .explode()
                .str.strip()
            )
            missing_counts = missing_counts.loc[missing_counts.ne("")]
            if not missing_counts.empty:
                missing_field_text = ", ".join(f"{field}: {count}" for field, count in missing_counts.value_counts().head(4).items())
            else:
                missing_field_text = "No missing DCF fields reported for generated rows."

    sec_configured = bool(os.environ.get("SEC_USER_AGENT", "").strip())
    return [
        {
            "kicker": "FUNDAMENTALS GAP",
            "title": f"{len(price_ready_missing_fundamentals)} price-ready companies",
            "body": f"{active_missing} active-universe price-ready company row(s) still need trusted fundamentals before DCF can be interpreted.",
            "badges": ["trusted rows only", "no valuation conclusion"],
            "command": "make sec-stage-queue TOP_N=25",
        },
        {
            "kicker": "NEXT FUNDAMENTALS TARGET",
            "title": next_ticker,
            "body": next_action,
            "badges": ["focus first", "preview before apply"],
            "command": f"make focus-fundamentals TICKER={next_ticker}" if next_ticker != "Not available" else "make sec-stage-queue TOP_N=25",
        },
        {
            "kicker": "DCF FIELD GAPS",
            "title": missing_field_text,
            "body": f"{excluded_count} ETF/index/fund row(s) remain excluded from operating-company DCF rather than failed valuation.",
            "badges": ["missing fields explicit", "excluded is not failed"],
            "command": "make dcf-readiness",
        },
        {
            "kicker": "DCF-READY PEER BLOCKERS",
            "title": f"{len(dcf_ready_peer_blocked)} DCF-ready companies",
            "body": "These rows can have standalone DCF context, but peer valuation remains blocked until trusted peer mappings and peer fundamentals exist.",
            "badges": ["peer valuation blocked", "manual peers"],
            "command": "make peer-mapping-queue TOP_N=25",
        },
        {
            "kicker": "INPUT PATH",
            "title": "SEC staging" if sec_configured else "Manual CSV fallback",
            "body": (
                "Use make sec-stage TICKERS=<ticker> for staged SEC fundamentals, or fill data/imports/fundamentals.csv with trusted rows. "
                "Always run make imports-validate, make imports-preview, and make imports-apply before claiming readiness improved."
            ),
            "badges": ["source/freshness audit", "copy only"],
            "command": "make imports-validate",
        },
    ]


PEER_STUDIO_FILTERS = [
    "DCF-ready but peer-blocked",
    "Missing peer mapping",
    "Peer price missing",
    "Peer fundamentals missing",
    "Peer valuation blocked",
    "Peer trend comparison ready",
    "All peer-blocked",
]


def build_peer_mapping_studio_frame(
    peer_readiness_frame: pd.DataFrame | None,
    ticker_readiness_frame: pd.DataFrame | None = None,
    peer_unlock_worklist_frame: pd.DataFrame | None = None,
    *,
    filter_mode: str = "DCF-ready but peer-blocked",
    ticker_search: str = "",
    active_universe_only: bool = False,
    dcf_ready_only: bool = False,
    row_limit: int | None = 50,
) -> pd.DataFrame:
    if peer_readiness_frame is None or peer_readiness_frame.empty:
        return pd.DataFrame()
    frame = peer_readiness_frame.copy()
    if "ticker" not in frame.columns:
        return pd.DataFrame()
    frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()

    if ticker_readiness_frame is not None and not ticker_readiness_frame.empty and "ticker" in ticker_readiness_frame.columns:
        readiness_columns = [
            column
            for column in [
                "ticker",
                "name",
                "asset_type",
                "theme",
                "in_active_universe",
                "price_ready",
                "dcf_ready",
                "fundamentals_ready",
                "overall_readiness_state",
                "decision_bucket",
                "next_action",
            ]
            if column in ticker_readiness_frame.columns
        ]
        readiness = ticker_readiness_frame[readiness_columns].copy()
        readiness["ticker"] = readiness["ticker"].astype(str).str.upper().str.strip()
        frame = frame.merge(readiness, on="ticker", how="left", suffixes=("", "_ticker"))

    if peer_unlock_worklist_frame is not None and not peer_unlock_worklist_frame.empty and "ticker" in peer_unlock_worklist_frame.columns:
        unlock_columns = [
            column
            for column in [
                "ticker",
                "priority",
                "unlock_stage",
                "workflow_group",
                "workflow_scope",
                "next_action_summary",
                "peer_trend_status",
                "peer_valuation_status",
                "next_input_file",
                "validation_sequence",
                "focus_command",
                "example_command",
                "copy_only_note",
            ]
            if column in peer_unlock_worklist_frame.columns
        ]
        unlock = peer_unlock_worklist_frame[unlock_columns].copy()
        unlock["ticker"] = unlock["ticker"].astype(str).str.upper().str.strip()
        frame = frame.merge(unlock, on="ticker", how="left", suffixes=("", "_unlock"))

    peer_ready = bool_series(frame, "peer_ready")
    dcf_ready = bool_series(frame, "dcf_ready")
    blocker = frame.get("peer_blocker_type", pd.Series("", index=frame.index)).fillna("").astype(str)

    if active_universe_only:
        frame = frame.loc[bool_series(frame, "in_active_universe")].copy()
        peer_ready = bool_series(frame, "peer_ready")
        dcf_ready = bool_series(frame, "dcf_ready")
        blocker = frame.get("peer_blocker_type", pd.Series("", index=frame.index)).fillna("").astype(str)
    if dcf_ready_only:
        frame = frame.loc[dcf_ready].copy()
        peer_ready = bool_series(frame, "peer_ready")
        dcf_ready = bool_series(frame, "dcf_ready")
        blocker = frame.get("peer_blocker_type", pd.Series("", index=frame.index)).fillna("").astype(str)

    if filter_mode == "DCF-ready but peer-blocked":
        frame = frame.loc[dcf_ready & ~peer_ready].copy()
    elif filter_mode == "Missing peer mapping":
        frame = frame.loc[blocker.eq("missing_peer_mapping")].copy()
    elif filter_mode == "Peer price missing":
        frame = frame.loc[blocker.eq("peer_price_missing")].copy()
    elif filter_mode == "Peer fundamentals missing":
        frame = frame.loc[blocker.eq("peer_fundamentals_missing")].copy()
    elif filter_mode == "Peer valuation blocked":
        frame = frame.loc[blocker.eq("peer_valuation_blocked")].copy()
    elif filter_mode == "Peer trend comparison ready":
        frame = frame.loc[bool_series(frame, "peer_trend_comparison_ready")].copy()
    elif filter_mode == "All peer-blocked":
        frame = frame.loc[~peer_ready].copy()

    if ticker_search.strip():
        search_columns = [
            column
            for column in [
                "ticker",
                "name",
                "theme",
                "peer_blocker_type",
                "missing_peer_reason",
                "next_peer_action",
                "sample_peers",
            ]
            if column in frame.columns
        ]
        if search_columns:
            mask = frame[search_columns].astype(str).apply(
                lambda row: row.str.contains(ticker_search, case=False, na=False).any(),
                axis=1,
            )
            frame = frame.loc[mask].copy()

    if "priority" in frame.columns:
        frame["priority"] = pd.to_numeric(frame["priority"], errors="coerce").fillna(999).astype(int)
    else:
        frame["priority"] = 999
    if "workflow_scope" in frame.columns:
        frame["workflow_scope_rank"] = frame["workflow_scope"].map({"active_universe": 0, "master_universe": 1}).fillna(2).astype(int)
    else:
        frame["workflow_scope_rank"] = 2
    if "workflow_group" not in frame.columns:
        frame["workflow_group"] = ""
    if "ticker" in frame.columns:
        frame = frame.sort_values(["priority", "workflow_scope_rank", "workflow_group", "ticker"], kind="stable").copy()
    frame = frame.drop(columns=["workflow_scope_rank"], errors="ignore")
    if row_limit is not None and row_limit > 0:
        frame = frame.head(row_limit).copy()
    return frame


def peer_mapping_studio_table_columns(frame: pd.DataFrame) -> list[str]:
    preferred = [
        "priority",
        "ticker",
        "name",
        "asset_type",
        "theme",
        "in_active_universe",
        "dcf_ready",
        "peer_ready",
        "peer_blocker_type",
        "unlock_stage",
        "workflow_group",
        "workflow_scope",
        "next_action_summary",
        "peer_trend_status",
        "peer_valuation_status",
        "mapping_status",
        "peer_count",
        "ready_peer_count",
        "peer_price_ready_count",
        "peer_momentum_ready_count",
        "peer_fundamentals_ready_count",
        "peer_valuation_ready_count",
        "sample_peers",
        "peer_missing_price_tickers",
        "peer_missing_fundamentals_tickers",
        "peer_missing_valuation_tickers",
        "missing_peer_reason",
        "next_peer_action",
        "next_input_file",
        "validation_sequence",
        "focus_command",
        "example_command",
        "copy_only_note",
    ]
    return [column for column in preferred if column in frame.columns]


def decision_workflow_summary_cards(decisions_frame: pd.DataFrame | None) -> list[dict[str, object]]:
    if decisions_frame is None or decisions_frame.empty:
        return [
            {
                "kicker": "DECISIONS",
                "title": "Not generated",
                "body": "Run make pipeline or make readiness to refresh research decision outputs.",
                "badges": ["blocked"],
                "command": "make pipeline",
            }
        ]

    frame = decisions_frame.copy()
    bucket_counts = frame.get("decision_bucket", pd.Series(dtype=object)).fillna("Unknown").astype(str).value_counts()
    subtype_counts = frame.get("decision_subtype", pd.Series(dtype=object)).fillna("Unknown").astype(str).value_counts()
    blocker_counts = frame.get("primary_blocker", pd.Series(dtype=object)).fillna("none").astype(str).replace({"": "none"}).value_counts()
    next_actions = frame.get("next_best_action", pd.Series(dtype=object)).fillna("").astype(str)
    top_action = next((value for value in next_actions if value.strip()), "Run make project-status for next steps.")
    research_now = int(bucket_counts.get("Research Now", 0))
    blocked = int(bucket_counts.get("Blocked by Data", 0))
    monitor = int(bucket_counts.get("Monitor", 0))
    excluded = int(bucket_counts.get("Excluded", 0))
    review_later = int(bucket_counts.get("Review Later", 0))
    top_blocker = str(blocker_counts.index[0]) if not blocker_counts.empty else "none"
    top_subtype = str(subtype_counts.index[0]) if not subtype_counts.empty else "Not available"
    return [
        {
            "kicker": "DECISION BUCKETS",
            "title": f"{research_now} research / {blocked} blocked",
            "body": f"Monitor: {monitor}. Excluded: {excluded}. Review later: {review_later}. Buckets are readiness-gated, not trade instructions.",
            "badges": ["readiness-gated", "research-only"],
            "command": "make project-status",
        },
        {
            "kicker": "TOP DECISION SUBTYPE",
            "title": top_subtype,
            "body": ", ".join(f"{key}: {int(value)}" for key, value in list(subtype_counts.items())[:3]),
            "badges": ["reason codes"],
            "command": "make readiness",
        },
        {
            "kicker": "TOP PRIMARY BLOCKER",
            "title": top_blocker,
            "body": ", ".join(f"{key}: {int(value)}" for key, value in list(blocker_counts.items())[:3]),
            "badges": ["blocked by data"],
            "command": "make onboarding TOP_N=10",
        },
        {
            "kicker": "NEXT DECISION ACTION",
            "title": "Top safe action",
            "body": compact_reason(top_action, max_sentences=1, max_chars=180),
            "badges": ["copy command only", "no execution"],
            "command": "make project-status",
        },
    ]


def _text_contains(frame: pd.DataFrame, column: str, token: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index)
    return frame[column].fillna("").astype(str).str.contains(token, case=False, na=False)


def _readiness_search_mask(frame: pd.DataFrame, search_value: str) -> pd.Series:
    if not search_value.strip():
        return pd.Series(True, index=frame.index)
    search_columns = [
        column
        for column in [
            "ticker",
            "name",
            "exchange",
            "asset_type",
            "sector",
            "industry",
            "theme",
            "overall_readiness_state",
            "missing_data",
            "next_action",
            "decision_bucket",
        ]
        if column in frame.columns
    ]
    if not search_columns:
        return pd.Series(True, index=frame.index)
    search_frame = frame[search_columns].astype(str)
    return search_frame.apply(lambda row: row.str.contains(search_value, case=False, na=False).any(), axis=1)


def filter_market_readiness_frame(
    frame: pd.DataFrame | None,
    *,
    scope: str = "Active research only",
    readiness_filter: str = "All",
    asset_filter: str = "All assets",
    ticker_search: str = "",
    sector: str = "All",
    theme: str = "All",
    row_limit: int | None = DEFAULT_MARKET_ROW_LIMIT,
) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    filtered = frame.copy()
    if scope == "Active research only" and "in_active_universe" in filtered.columns:
        filtered = filtered.loc[bool_series(filtered, "in_active_universe")].copy()
    elif scope == "All master universe" and "in_master_universe" in filtered.columns:
        filtered = filtered.loc[bool_series(filtered, "in_master_universe")].copy()

    if readiness_filter == "Price-ready only":
        filtered = filtered.loc[bool_series(filtered, "price_ready")].copy()
    elif readiness_filter == "Momentum-ready only":
        filtered = filtered.loc[bool_series(filtered, "momentum_ready")].copy()
    elif readiness_filter == "DCF-ready only":
        filtered = filtered.loc[bool_series(filtered, "dcf_ready")].copy()
    elif readiness_filter == "Blocked by price":
        ready = bool_series(filtered, "price_ready")
        filtered = filtered.loc[~ready | _text_contains(filtered, "blocked_features", "price") | _text_contains(filtered, "missing_data", "price")].copy()
    elif readiness_filter == "Blocked by fundamentals":
        ready = bool_series(filtered, "fundamentals_ready")
        filtered = filtered.loc[
            ~ready
            & (
                _text_contains(filtered, "blocked_features", "fundamental")
                | _text_contains(filtered, "missing_data", "fundamental")
                | _text_contains(filtered, "missing_data", "free_cash_flow")
                | _text_contains(filtered, "missing_data", "shares_outstanding")
            )
        ].copy()
    elif readiness_filter == "Blocked by peers":
        ready = bool_series(filtered, "peer_ready")
        filtered = filtered.loc[~ready & (_text_contains(filtered, "blocked_features", "peer") | _text_contains(filtered, "missing_data", "peer"))].copy()
    elif readiness_filter == "Earnings unavailable":
        filtered = filtered.loc[~bool_series(filtered, "earnings_ready")].copy()
    elif readiness_filter == "Analyst estimates unavailable":
        filtered = filtered.loc[~bool_series(filtered, "analyst_estimates_ready")].copy()

    asset_type = filtered.get("asset_type", pd.Series("", index=filtered.index)).fillna("").astype(str).str.lower()
    if asset_filter == "Companies only":
        filtered = filtered.loc[asset_type.eq("company")].copy()
    elif asset_filter == "ETFs / index proxies":
        filtered = filtered.loc[asset_type.isin({"etf", "index_proxy", "fund"})].copy()

    if sector != "All" and "sector" in filtered.columns:
        filtered = filtered.loc[filtered["sector"].fillna("").astype(str).eq(sector)].copy()
    if theme != "All" and "theme" in filtered.columns:
        filtered = filtered.loc[filtered["theme"].fillna("").astype(str).eq(theme)].copy()
    filtered = filtered.loc[_readiness_search_mask(filtered, ticker_search)].copy()
    if "ticker" in filtered.columns:
        filtered = filtered.sort_values("ticker").copy()
    if row_limit is not None and row_limit > 0:
        return filtered.head(row_limit).copy()
    return filtered


def market_readiness_table_columns(frame: pd.DataFrame) -> list[str]:
    preferred = [
        "ticker",
        "name",
        "asset_type",
        "sector",
        "industry",
        "theme",
        "in_active_universe",
        "overall_readiness_state",
        "price_ready",
        "momentum_ready",
        "liquidity_ready",
        "correlation_ready",
        "fundamentals_ready",
        "dcf_ready",
        "peer_ready",
        "earnings_ready",
        "analyst_estimates_ready",
        "blocked_features",
        "excluded_features",
        "missing_data",
        "next_action",
        "updated_at",
    ]
    return [column for column in preferred if column in frame.columns]


def _join_tickers(values: pd.Series, limit: int = 8) -> str:
    tickers = values.dropna().astype(str).str.upper().str.strip()
    tickers = tickers.loc[tickers.ne("")]
    return ",".join(tickers.head(limit).tolist())


NEXT_ACTION_CONSOLE_COLUMNS = [
    "priority",
    "action_category",
    "affected_feature",
    "scope",
    "ticker_count",
    "sample_tickers",
    "command",
    "why_it_matters",
    "source_freshness_note",
    "safety_note",
]


def safe_action_console_command(category: str, command: object = "") -> str:
    command_text = normalize_operator_command(command)
    lowered = command_text.lower()
    category_key = category.strip().lower()
    if category_key == "price coverage batch":
        if "top_n=" in lowered or "tickers=" in lowered:
            return command_text
        return "make price-refresh TOP_N=25 PROVIDER=yahoo"
    if category_key == "fundamentals / dcf unlock":
        if "top_n=" in lowered or "tickers=" in lowered or lowered == "make imports-validate":
            return command_text
        return "make sec-stage-queue TOP_N=25"
    if category_key == "peer mapping unlock":
        if "top_n=" in lowered or "ticker=" in lowered or lowered == "make imports-validate":
            return command_text
        return "make peer-mapping-queue TOP_N=25"
    if category_key == "earnings import setup":
        return command_text if lowered in {"make import-earnings", "make templates", "make imports-validate"} else "make import-earnings"
    if category_key == "analyst estimates import setup":
        return command_text if lowered in {"make import-analyst-estimates", "make templates", "make imports-validate"} else "make import-analyst-estimates"
    if category_key == "single-stock review":
        return command_text if "ticker=" in lowered else "make stock-report TICKER=META"
    return command_text or "make project-status"


def next_action_console_source_note(category: str) -> str:
    notes = {
        "Price Coverage Batch": "Uses local prices first, then capped Yahoo refresh or staged manual OHLCV CSVs with preview/apply safeguards.",
        "Fundamentals / DCF Unlock": "Uses SEC Companyfacts staging when configured, or trusted manual fundamentals CSV rows with validate/preview/apply.",
        "Peer Mapping Unlock": "Uses source-backed manual peer mappings or clearly labeled fallback context; no peer relationship is inferred as trusted.",
        "Earnings Import Setup": "Manual trusted local CSV only; feature stays unavailable until rows validate.",
        "Analyst Estimates Import Setup": "Manual trusted local CSV only; consensus context stays unavailable until rows validate.",
        "Single-Stock Review": "Reads current readiness, decisions, coverage, DCF, peer, and optional-context outputs for one ticker.",
    }
    return notes.get(category, "Uses generated local CSV reports; run make readiness and make project-status after data changes.")


def next_action_console_safety_note(command: object) -> str:
    command_text = format_missing(command, "")
    lowered = command_text.lower()
    if "top_n=" in lowered:
        return "Capped batch; copy into a terminal when ready. The dashboard does not execute it."
    if "ticker=" in lowered or "tickers=" in lowered:
        return "Ticker-targeted command; copy into a terminal when ready. The dashboard does not execute it."
    if "imports-validate" in lowered or "import-" in lowered or "templates" in lowered:
        return "Preview or import workflow; validate before apply. The dashboard does not execute it."
    return "Copyable local command only; the dashboard does not execute it."


def build_next_action_console_frame(
    ticker_readiness_frame: pd.DataFrame | None,
    action_queue_frame: pd.DataFrame | None = None,
    project_status_payload: dict[str, Any] | None = None,
    *,
    limit: int = 8,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    if ticker_readiness_frame is not None and not ticker_readiness_frame.empty and "ticker" in ticker_readiness_frame.columns:
        frame = ticker_readiness_frame.copy()
        company_mask = frame.get("asset_type", pd.Series("", index=frame.index)).fillna("").astype(str).str.lower().eq("company")
        active_mask = bool_series(frame, "in_active_universe")
        price_missing = frame.loc[~bool_series(frame, "price_ready")]
        fundamentals_missing = frame.loc[company_mask & bool_series(frame, "price_ready") & ~bool_series(frame, "fundamentals_ready")]
        dcf_peer_blocked = frame.loc[bool_series(frame, "dcf_ready") & ~bool_series(frame, "peer_ready")]
        optional_scope = frame.loc[active_mask] if active_mask.any() else frame
        earnings_missing = optional_scope.loc[~bool_series(optional_scope, "earnings_ready")]
        analyst_missing = optional_scope.loc[~bool_series(optional_scope, "analyst_estimates_ready")]

        feature_rows = [
            (
                1,
                "Price Coverage Batch",
                "price_ready",
                price_missing,
                "Refresh the next small missing-price batch so the broad-universe frontier advances without requiring all tickers at once.",
                "make price-refresh TOP_N=25 PROVIDER=yahoo",
            ),
            (
                2,
                "Fundamentals / DCF Unlock",
                "fundamentals_ready, dcf_ready",
                fundamentals_missing,
                "Price-ready company tickers are the highest-leverage DCF unlock targets because price context already exists.",
                "make sec-stage-queue TOP_N=25",
            ),
            (
                3,
                "Peer Mapping Unlock",
                "peer_ready",
                dcf_peer_blocked,
                "DCF-ready names without peer context need source-backed mappings before peer-relative conclusions are useful.",
                "make peer-mapping-queue TOP_N=25",
            ),
            (
                4,
                "Earnings Import Setup",
                "earnings_ready",
                earnings_missing,
                "Earnings context should stay locked until trusted local rows exist and validate cleanly.",
                "make import-earnings",
            ),
            (
                5,
                "Analyst Estimates Import Setup",
                "analyst_estimates_ready",
                analyst_missing,
                "Analyst-estimate context should stay locked until trusted local rows exist and validate cleanly.",
                "make import-analyst-estimates",
            ),
        ]
        for priority, category, feature, subset, why, command in feature_rows:
            if subset.empty:
                continue
            safe_command = safe_action_console_command(category, command)
            scope_label = "active universe" if category in {"Earnings Import Setup", "Analyst Estimates Import Setup"} else "broad universe"
            rows.append(
                {
                    "priority": priority,
                    "action_category": category,
                    "affected_feature": feature,
                    "scope": scope_label,
                    "ticker_count": len(subset),
                    "sample_tickers": _join_tickers(subset["ticker"], 6),
                    "command": safe_command,
                    "why_it_matters": why,
                    "source_freshness_note": next_action_console_source_note(category),
                    "safety_note": next_action_console_safety_note(safe_command),
                }
            )

        single_stock_candidates = frame.loc[bool_series(frame, "price_ready")].copy()
        if not single_stock_candidates.empty:
            if "dcf_ready" in single_stock_candidates.columns:
                single_stock_candidates = single_stock_candidates.sort_values(["dcf_ready", "ticker"], ascending=[False, True], kind="stable")
            first_ticker = format_missing(single_stock_candidates.iloc[0].get("ticker"), "META").upper()
            command = safe_action_console_command("Single-Stock Review", f"make stock-report TICKER={first_ticker}")
            rows.append(
                {
                    "priority": 6,
                    "action_category": "Single-Stock Review",
                    "affected_feature": "single_stock_research",
                    "scope": "analysis-ready subset",
                    "ticker_count": len(single_stock_candidates),
                    "sample_tickers": _join_tickers(single_stock_candidates["ticker"], 6),
                    "command": command,
                    "why_it_matters": "Use one ticker drilldown to verify that readiness, DCF, peer, optional context, and decision state all tell the same story.",
                    "source_freshness_note": next_action_console_source_note("Single-Stock Review"),
                    "safety_note": next_action_console_safety_note(command),
                }
            )

    for row in project_status_command_rows(project_status_payload)[:2]:
        command = normalize_operator_command(row.get("Command"))
        if not command:
            continue
        lowered = command.lower()
        if "price" in lowered:
            category = "Price Coverage Batch"
            feature = "price_ready"
        elif "sec-stage" in lowered or "fundamental" in lowered:
            category = "Fundamentals / DCF Unlock"
            feature = "fundamentals_ready, dcf_ready"
        elif "peer" in lowered:
            category = "Peer Mapping Unlock"
            feature = "peer_ready"
        elif "earnings" in lowered:
            category = "Earnings Import Setup"
            feature = "earnings_ready"
        elif "analyst" in lowered or "estimate" in lowered:
            category = "Analyst Estimates Import Setup"
            feature = "analyst_estimates_ready"
        else:
            category = "Single-Stock Review" if "stock-report" in lowered or "focus-" in lowered else "Project Refresh"
            feature = "operator_workflow"
        command = safe_action_console_command(category, command)
        rows.append(
            {
                "priority": 7,
                "action_category": category,
                "affected_feature": feature,
                "scope": "project status",
                "ticker_count": "",
                "sample_tickers": "",
                "command": command,
                "why_it_matters": compact_reason(row.get("Reason"), max_sentences=1, max_chars=180),
                "source_freshness_note": next_action_console_source_note(category),
                "safety_note": next_action_console_safety_note(command),
            }
        )

    if action_queue_frame is not None and not action_queue_frame.empty:
        for signal in top_priority_signals(action_queue_frame, limit=2):
            command = format_missing(signal.get("command"), "")
            lowered = command.lower()
            category = "Price Coverage Batch" if "price" in lowered else "Fundamentals / DCF Unlock" if "fundamental" in lowered or "sec-stage" in lowered else "Peer Mapping Unlock" if "peer" in lowered else "Single-Stock Review"
            command = safe_action_console_command(category, command)
            rows.append(
                {
                    "priority": 8,
                    "action_category": category,
                    "affected_feature": category.lower().replace(" / ", "_").replace(" ", "_"),
                    "scope": "action queue",
                    "ticker_count": "",
                    "sample_tickers": "",
                    "command": command,
                    "why_it_matters": compact_reason(signal.get("body"), max_sentences=1, max_chars=180),
                    "source_freshness_note": next_action_console_source_note(category),
                    "safety_note": next_action_console_safety_note(command),
                }
            )

    if not rows:
        return pd.DataFrame(columns=NEXT_ACTION_CONSOLE_COLUMNS)

    console = pd.DataFrame(rows)
    console = console.drop_duplicates(subset=["action_category", "command"], keep="first")
    console["priority"] = pd.to_numeric(console["priority"], errors="coerce").fillna(999).astype(int)
    console = console.sort_values(["priority", "action_category"], kind="stable")
    return console[NEXT_ACTION_CONSOLE_COLUMNS].head(limit).reset_index(drop=True)


def next_action_console_cards(console_frame: pd.DataFrame | None, limit: int = 4) -> list[dict[str, object]]:
    if console_frame is None or console_frame.empty:
        return [
            {
                "kicker": "NEXT ACTIONS",
                "title": "Refresh project status",
                "body": "Run the local status workflow to regenerate grouped action guidance before the next research pass.",
                "badges": ["copy only", "local"],
                "command": "make project-status",
            }
        ]
    cards: list[dict[str, object]] = []
    for _, row in console_frame.head(limit).iterrows():
        category = format_missing(row.get("action_category"), "Next action")
        scope = format_missing(row.get("scope"), "")
        sample = format_missing(row.get("sample_tickers"), "")
        body = compact_reason(row.get("why_it_matters"), max_sentences=1, max_chars=150)
        source_note = compact_reason(row.get("source_freshness_note"), max_sentences=1, max_chars=140)
        if scope and scope != "Not available":
            body = f"{scope}: {body}"
        if sample and sample != "Not available":
            body = f"{body} Sample: {sample}."
        if source_note and source_note != "Not available":
            body = f"{body} {source_note}"
        cards.append(
            {
                "kicker": category.upper(),
                "title": format_missing(row.get("command"), "make project-status"),
                "body": body,
                "badges": ["copy only", format_missing(row.get("affected_feature"), "workflow")],
                "command": format_missing(row.get("command"), "make project-status"),
            }
        )
    return cards


def market_next_action_cards(
    ticker_readiness_frame: pd.DataFrame | None,
    action_queue_frame: pd.DataFrame | None = None,
    *,
    limit: int = 8,
) -> list[dict[str, object]]:
    cards: list[dict[str, object]] = []
    if ticker_readiness_frame is not None and not ticker_readiness_frame.empty and "ticker" in ticker_readiness_frame.columns:
        frame = ticker_readiness_frame.copy()
        price_missing = frame.loc[~bool_series(frame, "price_ready")]
        price_tickers = _join_tickers(price_missing["ticker"], limit)
        if price_tickers:
            cards.append(
                {
                    "kicker": "PRICE DATA",
                    "title": f"{len(price_missing)} ticker(s) need prices",
                    "body": "Refresh or stage prices for a small batch first; do not require the whole market to be ready.",
                    "badges": ["blocked by data", "batch safe"],
                    "command": f"make price-refresh TICKERS={price_tickers}",
                }
            )

        company_mask = frame.get("asset_type", pd.Series("", index=frame.index)).fillna("").astype(str).str.lower().eq("company")
        fundamentals_missing = frame.loc[company_mask & bool_series(frame, "price_ready") & ~bool_series(frame, "fundamentals_ready")]
        fundamentals_tickers = _join_tickers(fundamentals_missing["ticker"], limit)
        if fundamentals_tickers:
            cards.append(
                {
                    "kicker": "FUNDAMENTALS",
                    "title": f"{len(fundamentals_missing)} price-ready company ticker(s) need fundamentals",
                    "body": "Use SEC staging when SEC_USER_AGENT is configured, otherwise stage trusted manual CSV rows.",
                    "badges": ["DCF unlock", "source-backed only"],
                    "command": f"make sec-stage TICKERS={fundamentals_tickers}",
                }
            )

        peer_missing = frame.loc[bool_series(frame, "in_active_universe") & ~bool_series(frame, "peer_ready")]
        peer_tickers = _join_tickers(peer_missing["ticker"], limit)
        if peer_tickers:
            cards.append(
                {
                    "kicker": "PEERS",
                    "title": f"{len(peer_missing)} active ticker(s) need peer context",
                    "body": "Add transparent peer mappings only from trusted local or source-backed context.",
                    "badges": ["manual review", "no fabricated peers"],
                    "command": "make templates",
                }
            )

        optional_missing = frame.loc[bool_series(frame, "in_active_universe") & (~bool_series(frame, "earnings_ready") | ~bool_series(frame, "analyst_estimates_ready"))]
        if not optional_missing.empty:
            cards.append(
                {
                    "kicker": "OPTIONAL CONTEXT",
                    "title": f"{len(optional_missing)} active ticker(s) lack earnings or estimates",
                    "body": "Keep optional sections unavailable until trusted local CSV rows exist.",
                    "badges": ["manual only", "safe empty state"],
                    "command": "make templates",
                }
            )

    if action_queue_frame is not None and not action_queue_frame.empty:
        cards.append(
            {
                "kicker": "ACTION QUEUE",
                "title": f"{len(action_queue_frame)} queued data action(s)",
                "body": "The dashboard shows a short actionable slice; use onboarding outputs for the complete queue.",
                "badges": ["row-limited", "review first"],
                "command": "make onboarding",
            }
        )
    cards.append(
        {
            "kicker": "REFRESH REPORTS",
            "title": "Regenerate readiness after imports",
            "body": "After any staged import or provider refresh, regenerate pipeline and readiness outputs before interpreting conclusions.",
            "badges": ["deterministic", "CSV-first"],
            "command": "make readiness",
        }
    )
    return cards[:5]


def market_blocker_summary_cards(ticker_readiness_frame: pd.DataFrame | None) -> list[dict[str, object]]:
    if ticker_readiness_frame is None or ticker_readiness_frame.empty:
        return [
            {
                "kicker": "BLOCKERS",
                "title": "Readiness report missing",
                "body": "Generate the central readiness report before reviewing broad-universe blocker queues.",
                "badges": ["blocked"],
                "command": "make readiness",
            }
        ]
    frame = ticker_readiness_frame.copy()
    company_mask = frame.get("asset_type", pd.Series("", index=frame.index)).fillna("").astype(str).str.lower().eq("company")
    active_mask = bool_series(frame, "in_active_universe")
    price_missing = frame.loc[~bool_series(frame, "price_ready")]
    fundamentals_missing = frame.loc[company_mask & bool_series(frame, "price_ready") & ~bool_series(frame, "fundamentals_ready")]
    peer_missing = frame.loc[active_mask & ~bool_series(frame, "peer_ready")]
    optional_missing = frame.loc[active_mask & (~bool_series(frame, "earnings_ready") | ~bool_series(frame, "analyst_estimates_ready"))]
    dcf_excluded = frame.loc[_text_contains(frame, "excluded_features", "dcf")]
    return [
        {
            "kicker": "PRICE BLOCKERS",
            "title": f"{len(price_missing)} ticker(s)",
            "body": "Most broad-universe names are known metadata only until trusted price rows are refreshed or staged.",
            "badges": ["batch first", "no full-market blast"],
            "command": "make price-worklist TOP_N=25",
        },
        {
            "kicker": "FUNDAMENTALS BLOCKERS",
            "title": f"{len(fundamentals_missing)} price-ready company ticker(s)",
            "body": "These are the best valuation unlock candidates because they already have local price coverage.",
            "badges": ["DCF inputs", "source-backed"],
            "command": "make sec-stage-queue TOP_N=25",
        },
        {
            "kicker": "PEER BLOCKERS",
            "title": f"{len(peer_missing)} active ticker(s)",
            "body": "Peer context requires transparent mappings and enough peer metrics; do not infer fake relationships.",
            "badges": ["manual review", "active universe"],
            "command": "make peer-mapping-queue TOP_N=25",
        },
        {
            "kicker": "OPTIONAL CONTEXT",
            "title": f"{len(optional_missing)} active ticker(s)",
            "body": "Earnings and analyst estimates remain unavailable until trusted local CSV rows exist.",
            "badges": ["safe empty state", "manual only"],
            "command": "make optional-context-worklist TOP_N=25",
        },
        {
            "kicker": "DCF EXCLUSIONS",
            "title": f"{len(dcf_excluded)} ticker(s)",
            "body": "ETFs, index proxies, and funds stay excluded from operating-company DCF and can still be used for market/risk context.",
            "badges": ["excluded", "not a data error"],
            "command": "make readiness",
        },
    ]


def single_stock_readiness_snapshot(
    ticker: str,
    ticker_readiness_frame: pd.DataFrame | None,
    coverage_frame: pd.DataFrame | None = None,
    decisions_frame: pd.DataFrame | None = None,
    dcf_readiness_frame: pd.DataFrame | None = None,
    peer_readiness_frame: pd.DataFrame | None = None,
    earnings_readiness_frame: pd.DataFrame | None = None,
    analyst_readiness_frame: pd.DataFrame | None = None,
) -> dict[str, object]:
    symbol = ticker.strip().upper()
    if not symbol:
        return {"ticker": "", "status": "missing", "main_reason": "Enter a ticker.", "next_action": "Search by ticker."}
    readiness_row: dict[str, object] = {}
    if ticker_readiness_frame is not None and not ticker_readiness_frame.empty and "ticker" in ticker_readiness_frame.columns:
        matches = ticker_readiness_frame.loc[ticker_readiness_frame["ticker"].astype(str).str.upper().str.strip().eq(symbol)]
        if not matches.empty:
            readiness_row = matches.iloc[0].to_dict()
    if not readiness_row:
        return {
            "ticker": symbol,
            "status": "missing",
            "main_reason": "Ticker is not in the current master or active universe outputs.",
            "next_action": "Stage or refresh universe metadata, then run make universe-report and make readiness.",
        }

    decision_row: dict[str, object] = {}
    if decisions_frame is not None and not decisions_frame.empty and "ticker" in decisions_frame.columns:
        matches = decisions_frame.loc[decisions_frame["ticker"].astype(str).str.upper().str.strip().eq(symbol)]
        if not matches.empty:
            decision_row = matches.iloc[0].to_dict()

    dcf_row: dict[str, object] = {}
    if dcf_readiness_frame is not None and not dcf_readiness_frame.empty and "ticker" in dcf_readiness_frame.columns:
        matches = dcf_readiness_frame.loc[dcf_readiness_frame["ticker"].astype(str).str.upper().str.strip().eq(symbol)]
        if not matches.empty:
            dcf_row = matches.iloc[0].to_dict()

    coverage_row: dict[str, object] = {}
    if coverage_frame is not None and not coverage_frame.empty and "ticker" in coverage_frame.columns:
        matches = coverage_frame.loc[coverage_frame["ticker"].astype(str).str.upper().str.strip().eq(symbol)]
        if not matches.empty:
            coverage_row = matches.iloc[0].to_dict()

    peer_row: dict[str, object] = {}
    if peer_readiness_frame is not None and not peer_readiness_frame.empty and "ticker" in peer_readiness_frame.columns:
        matches = peer_readiness_frame.loc[peer_readiness_frame["ticker"].astype(str).str.upper().str.strip().eq(symbol)]
        if not matches.empty:
            peer_row = matches.iloc[0].to_dict()

    asset_type = str(readiness_row.get("asset_type", "") or "").lower()
    excluded_features = str(readiness_row.get("excluded_features", "") or "")
    if "dcf" in excluded_features.lower() or asset_type in {"etf", "index_proxy", "fund"}:
        dcf_status = "excluded"
        dcf_reason = str(dcf_row.get("reason_not_ready") or "Excluded from operating-company DCF.")
    elif bool_series(pd.DataFrame([readiness_row]), "dcf_ready").any():
        dcf_status = "ready"
        dcf_reason = "DCF inputs are present."
    else:
        dcf_status = "blocked"
        dcf_reason = str(dcf_row.get("reason_not_ready") or readiness_row.get("missing_data") or "Missing required DCF inputs.")

    snapshot = {
        "ticker": symbol,
        "status": str(readiness_row.get("overall_readiness_state") or "partial"),
        "name": readiness_row.get("name", ""),
        "asset_type": readiness_row.get("asset_type", ""),
        "ready_features": readiness_row.get("ready_features", ""),
        "partial_features": readiness_row.get("partial_features", ""),
        "blocked_features": readiness_row.get("blocked_features", ""),
        "excluded_features": readiness_row.get("excluded_features", ""),
        "price_ready": bool(bool_series(pd.DataFrame([readiness_row]), "price_ready").any()),
        "momentum_ready": bool(bool_series(pd.DataFrame([readiness_row]), "momentum_ready").any()),
        "dcf_status": dcf_status,
        "dcf_reason": dcf_reason,
        "peer_ready": bool(bool_series(pd.DataFrame([readiness_row]), "peer_ready").any()),
        "peer_blocker_type": peer_row.get("peer_blocker_type", ""),
        "peer_mapping_status": peer_row.get("mapping_status", ""),
        "peer_count": peer_row.get("peer_count", ""),
        "ready_peer_count": peer_row.get("ready_peer_count", ""),
        "peer_trend_comparison_ready": peer_row.get("peer_trend_comparison_ready", ""),
        "peer_valuation_comparison_ready": peer_row.get("peer_valuation_comparison_ready", ""),
        "peer_dcf_comparison_ready": peer_row.get("peer_dcf_comparison_ready", ""),
        "sample_peers": peer_row.get("sample_peers", ""),
        "next_peer_action": peer_row.get("next_peer_action") or peer_row.get("missing_peer_reason", ""),
        "earnings_ready": bool(bool_series(pd.DataFrame([readiness_row]), "earnings_ready").any()),
        "analyst_estimates_ready": bool(bool_series(pd.DataFrame([readiness_row]), "analyst_estimates_ready").any()),
        "decision_bucket": decision_row.get("decision_bucket", "Not available"),
        "decision_subtype": decision_row.get("decision_subtype", "Not available"),
        "primary_blocker": decision_row.get("primary_blocker", "Not available"),
        "confidence": decision_row.get("confidence", "Not available"),
        "main_reason": decision_row.get("main_reason") or readiness_row.get("missing_data") or "Readiness state available.",
        "next_action": decision_row.get("next_best_action") or decision_row.get("next_action") or readiness_row.get("next_action") or "Run make readiness after the next data import.",
        "missing_data": readiness_row.get("missing_data", ""),
        "price_rows": coverage_row.get("price_history_days", coverage_row.get("price_rows", "")),
        "price_first_date": coverage_row.get("first_price_date", ""),
        "price_last_date": coverage_row.get("last_price_date", ""),
        "updated_at": readiness_row.get("updated_at", ""),
    }
    snapshot["one_minute_summary"] = single_stock_one_minute_summary(snapshot)
    return snapshot


def single_stock_one_minute_summary(snapshot: dict[str, object]) -> str:
    ticker = format_missing(snapshot.get("ticker"), "Ticker")
    status = format_missing(snapshot.get("status"), "unknown")
    decision = format_missing(snapshot.get("decision_subtype") or snapshot.get("decision_bucket"), "not classified")
    blocker = format_missing(snapshot.get("primary_blocker"), "")
    dcf_status = format_missing(snapshot.get("dcf_status"), "unknown")
    peer_blocker = format_missing(snapshot.get("peer_blocker_type"), "")
    next_action = format_missing(snapshot.get("next_action"), "")

    parts = [f"{ticker} is {status}; decision: {decision}."]
    if blocker and blocker.lower() not in {"none", "not available"}:
        parts.append(f"Primary blocker: {blocker}.")
    if dcf_status.lower() == "excluded":
        parts.append("DCF is excluded because this asset is not an operating-company DCF candidate.")
    elif dcf_status.lower() == "blocked":
        parts.append(f"DCF is blocked: {compact_reason(snapshot.get('dcf_reason'), max_sentences=1, max_chars=120)}")
    elif dcf_status.lower() == "ready":
        parts.append("DCF inputs are ready, but peer and optional context may still be partial.")
    if peer_blocker and peer_blocker.lower() not in {"not available", "nan", "none", ""}:
        parts.append(f"Peer workflow: {peer_blocker}.")
    if not snapshot.get("earnings_ready") or not snapshot.get("analyst_estimates_ready"):
        parts.append("Optional earnings or analyst-estimate context is unavailable until trusted local CSV rows exist.")
    if next_action and next_action != "Not available":
        parts.append(f"Next: {next_action}")
    return " ".join(part for part in parts if part and part != "Not available")


def single_stock_source_audit_frame(snapshot: dict[str, object]) -> pd.DataFrame:
    ticker = format_missing(snapshot.get("ticker"), "TICKER").upper()
    price_ready = bool(snapshot.get("price_ready"))
    earnings_ready = bool(snapshot.get("earnings_ready"))
    estimates_ready = bool(snapshot.get("analyst_estimates_ready"))
    dcf_status = format_missing(snapshot.get("dcf_status"), "blocked").lower()
    peer_ready = bool(snapshot.get("peer_ready"))
    peer_blocker = format_missing(snapshot.get("peer_blocker_type"), "Not available")
    sec_present = bool(os.environ.get("SEC_USER_AGENT", "").strip())
    stooq_present = bool(os.environ.get("STOOQ_API_KEY", "").strip() or os.environ.get("STOQ_API_KEY", "").strip())
    if dcf_status == "ready":
        dcf_command = f"make stock-report TICKER={ticker}"
    elif dcf_status == "excluded":
        dcf_command = "make readiness"
    elif sec_present:
        dcf_command = f"make sec-stage TICKERS={ticker}"
    else:
        dcf_command = "make imports-validate"
    peer_command = f"make stock-report TICKER={ticker}" if peer_ready else f"make focus-peers TICKER={ticker}"

    rows = [
        {
            "Area": "Prices",
            "Status": "ready" if price_ready else "blocked",
            "Freshness": f"{format_missing(snapshot.get('price_first_date'), 'unknown')} to {format_missing(snapshot.get('price_last_date'), 'unknown')}; rows/days={format_missing(snapshot.get('price_rows'))}",
            "Local source": "data/prices.csv",
            "Manual path": "data/imports/prices.csv or data/staged/prices/",
            "Rejected rows": "data/rejected/price_import_rejected.csv",
            "Next command": f"make stock-report TICKER={ticker}" if price_ready else f"make price-refresh TICKERS={ticker}",
        },
        {
            "Area": "Fundamentals / DCF",
            "Status": dcf_status,
            "Freshness": compact_reason(snapshot.get("dcf_reason"), max_sentences=1, max_chars=140),
            "Local source": "data/fundamentals.csv",
            "Manual path": "data/imports/fundamentals.csv or data/staged/fundamentals/",
            "Rejected rows": "data/rejected/fundamentals_import_rejected.csv",
            "Next command": dcf_command,
        },
        {
            "Area": "Peers",
            "Status": "ready" if peer_ready else peer_blocker,
            "Freshness": compact_reason(snapshot.get("next_peer_action"), max_sentences=1, max_chars=140),
            "Local source": "data/peers.csv",
            "Manual path": "data/imports/peers.csv",
            "Rejected rows": "data/rejected/peers_import_rejected.csv",
            "Next command": peer_command,
        },
        {
            "Area": "Earnings",
            "Status": "ready" if earnings_ready else "missing trusted local CSV input",
            "Freshness": "Trusted local rows only; no conclusion is shown while empty.",
            "Local source": "data/earnings.csv",
            "Manual path": "data/staged/earnings/",
            "Rejected rows": "data/rejected/earnings_import_rejected.csv",
            "Next command": "make import-earnings",
        },
        {
            "Area": "Analyst estimates",
            "Status": "ready" if estimates_ready else "missing trusted local CSV input",
            "Freshness": "Trusted local rows only; no consensus context is shown while empty.",
            "Local source": "data/analyst_estimates.csv",
            "Manual path": "data/staged/analyst_estimates/",
            "Rejected rows": "data/rejected/analyst_estimates_import_rejected.csv",
            "Next command": "make import-analyst-estimates",
        },
        {
            "Area": "Credentials",
            "Status": f"SEC_USER_AGENT={'present' if sec_present else 'missing'}; STOOQ_API_KEY={'present' if stooq_present else 'missing'}",
            "Freshness": "Missing credentials should block only the remote workflow, not local CSV reports.",
            "Local source": ".zshrc or shell environment",
            "Manual path": "staged CSV import folders remain available",
            "Rejected rows": "not applicable",
            "Next command": "make project-status",
        },
    ]
    return pd.DataFrame(rows)


def single_stock_source_audit_cards(snapshot: dict[str, object]) -> list[dict[str, object]]:
    audit = single_stock_source_audit_frame(snapshot)
    cards: list[dict[str, object]] = []
    for area in ["Prices", "Fundamentals / DCF", "Peers", "Earnings"]:
        row = audit.loc[audit["Area"].eq(area)]
        if row.empty:
            continue
        item = row.iloc[0]
        cards.append(
            {
                "kicker": str(item["Area"]).upper(),
                "title": format_missing(item["Status"]),
                "body": compact_reason(item["Freshness"], max_sentences=1, max_chars=150),
                "badges": ["source audit", "local CSV"],
                "command": format_missing(item["Next command"]),
            }
        )
    return cards


def single_stock_status_cards(snapshot: dict[str, object]) -> list[dict[str, object]]:
    if not snapshot or snapshot.get("status") == "missing":
        return [
            {
                "kicker": "TICKER STATUS",
                "title": format_missing(snapshot.get("ticker") if snapshot else "", "Missing ticker"),
                "body": format_missing(snapshot.get("main_reason") if snapshot else "", "Ticker is not available in current outputs."),
                "badges": ["missing"],
                "command": str(snapshot.get("next_action") if snapshot else "make universe-report"),
            }
        ]

    ready_features = format_missing(snapshot.get("ready_features"), "-")
    blocked_features = format_missing(snapshot.get("blocked_features"), "-")
    excluded_features = format_missing(snapshot.get("excluded_features"), "-")
    price_window = "Price coverage unavailable"
    first_date = format_missing(snapshot.get("price_first_date"), "")
    last_date = format_missing(snapshot.get("price_last_date"), "")
    if first_date or last_date:
        price_window = f"Price rows span {first_date or 'unknown'} to {last_date or 'unknown'}."
    elif format_missing(snapshot.get("price_rows"), ""):
        price_window = f"Price rows/days: {format_missing(snapshot.get('price_rows'))}."

    return [
        {
            "kicker": "ONE-MINUTE READ",
            "title": format_missing(snapshot.get("ticker"), "Selected ticker"),
            "body": format_missing(snapshot.get("one_minute_summary"), "Readiness state available."),
            "badges": ["readiness first", "single name"],
            "command": f"make stock-report TICKER={format_missing(snapshot.get('ticker'))}",
        },
        {
            "kicker": "TICKER STATUS",
            "title": f"{format_missing(snapshot.get('ticker'))}: {format_missing(snapshot.get('status'))}",
            "body": format_missing(snapshot.get("main_reason"), "Readiness state available."),
            "badges": [
                f"decision: {format_missing(snapshot.get('decision_subtype'))}",
                f"confidence: {format_missing(snapshot.get('confidence'))}",
            ],
            "command": str(snapshot.get("next_action") or "make readiness"),
        },
        {
            "kicker": "FEATURE BADGES",
            "title": f"Ready: {ready_features}",
            "body": f"Blocked: {blocked_features}. Excluded: {excluded_features}. Missing data: {format_missing(snapshot.get('missing_data'), '-')}",
            "badges": ["readiness first"],
            "command": "make readiness",
        },
        {
            "kicker": "PEER PATH",
            "title": format_missing(snapshot.get("peer_blocker_type"), "Peer ready"),
            "body": format_missing(snapshot.get("next_peer_action"), "Peer context is available or not required for this view."),
            "badges": [
                f"trend: {format_missing(snapshot.get('peer_trend_comparison_ready'))}",
                f"valuation: {format_missing(snapshot.get('peer_valuation_comparison_ready'))}",
            ],
            "command": f"make focus-peers TICKER={format_missing(snapshot.get('ticker'))}",
        },
        {
            "kicker": "SOURCE FRESHNESS",
            "title": price_window,
            "body": f"Last readiness update: {format_missing(snapshot.get('updated_at'), 'not available')}. Optional context requires trusted local CSV input.",
            "badges": ["local CSV", "freshness"],
            "command": "make project-status",
        },
    ]


def split_momentum_readiness(frame: pd.DataFrame, coverage_frame: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    if frame.empty or "Ticker" not in frame.columns:
        return frame.copy(), pd.DataFrame(columns=frame.columns)
    ready_tickers = ticker_set_from_bool(coverage_frame, "usable_for_momentum")
    if ready_tickers:
        ready_mask = frame["Ticker"].astype(str).str.upper().str.strip().isin(ready_tickers)
    else:
        numeric_columns = [column for column in ["Close", "RSPercentile", "Return1M", "AvgVolume20D"] if column in frame.columns]
        ready_mask = frame[numeric_columns].apply(pd.to_numeric, errors="coerce").notna().any(axis=1) if numeric_columns else pd.Series(False, index=frame.index)
    return frame.loc[ready_mask].copy(), frame.loc[~ready_mask].copy()


def split_dcf_readiness(dcf_readiness_frame: pd.DataFrame | None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if dcf_readiness_frame is None or dcf_readiness_frame.empty:
        empty = pd.DataFrame()
        return empty, empty, empty
    frame = dcf_readiness_frame.copy()
    asset_type = frame.get("asset_type", pd.Series("company", index=frame.index)).fillna("company").astype(str).str.lower()
    ready_mask = bool_series(frame, "is_dcf_ready")
    company_mask = asset_type.eq("company")
    return frame.loc[company_mask & ready_mask].copy(), frame.loc[company_mask & ~ready_mask].copy(), frame.loc[~company_mask].copy()


def split_risk_context_by_price_ready(frame: pd.DataFrame | None, unavailable_statuses: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    if frame is None or frame.empty:
        return pd.DataFrame(), pd.DataFrame()
    status_column = next((column for column in ["LiquidityStatus", "CorrelationStatus"] if column in frame.columns), "")
    if not status_column:
        return frame.copy(), pd.DataFrame(columns=frame.columns)
    status = frame[status_column].fillna("").astype(str).str.strip().str.lower()
    unavailable = status.isin({value.lower() for value in unavailable_statuses})
    return frame.loc[~unavailable].copy(), frame.loc[unavailable].copy()


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
        "core": "Current local universe plus holdings. Safest and quickest workflow; start with make universe-preview.",
        "sp500_smh": "S&P 500 community list, SMH holdings if available, plus holdings. Start with make universe-preview before make universe-apply.",
        "broad": "Adds Nasdaq-listed common stocks. Larger and slower; run make universe-preview before make universe-apply.",
    }
    cards = []
    for name, sources in SOURCE_PRESETS.items():
        cards.append(
            {
                "kicker": "PRESET",
                "title": name,
                "body": preset_descriptions.get(
                    name,
                    "Source-driven universe preset. Run make universe-preview before make universe-apply.",
                ),
                "badges": [", ".join(sources)],
                "command": "make universe-preview",
            }
        )
    return cards


def universe_action_path_cards(universe_summary: dict[str, Any]) -> list[dict[str, object]]:
    current = universe_summary.get("current_universe", {})
    staged = universe_summary.get("staged_universe", {})
    row_count = int(current.get("row_count") or 0)
    missing_theme_total = int(current.get("missing_theme_count") or 0) + int(current.get("unclassified_theme_count") or 0)
    duplicate_count = int(current.get("duplicate_ticker_count") or 0)
    staged_exists = bool(staged.get("exists"))
    staged_rows = int(staged.get("row_count") or 0)

    cards = [
        {
            "kicker": "BEST NEXT",
            "title": "Preview universe update" if not staged_exists else "Apply staged universe",
            "body": (
                "Start with make universe-preview so larger source-driven changes stay reviewable before make universe-apply."
                if not staged_exists
                else f"{staged_rows} staged ticker rows are already visible in the dashboard; run make universe-apply only after reviewing the staged CSV and diagnostics."
            ),
            "badges": ["preview first", "read-only"],
            "command": "make universe-preview" if not staged_exists else "make universe-apply",
        },
        {
            "kicker": "CURRENT FILE",
            "title": f"{row_count} current rows",
            "body": (
                f"{duplicate_count} duplicate ticker rows and {missing_theme_total} missing or unclassified themes are still visible in the canonical universe file."
            ),
            "badges": ["data/universe.csv", "coverage"],
            "command": "make templates" if missing_theme_total else "make universe-preview",
        },
        {
            "kicker": "STAGED FLOW",
            "title": "Apply stays CLI-only",
            "body": "Run make universe-preview first, inspect the staged CSV and diagnostics, then run make universe-apply only after review.",
            "badges": ["backup on apply", "csv-first"],
            "command": "make universe-apply",
        },
    ]
    return cards


def universe_manager_summary_cards(current: dict[str, Any], staged: dict[str, Any]) -> list[dict[str, object]]:
    return [
        {
            "kicker": "CURRENT",
            "title": f"{current['row_count']} tickers",
            "body": (
                f"{current['duplicate_ticker_count']} duplicate rows and "
                f"{current['missing_theme_count'] + current['unclassified_theme_count']} missing or unclassified themes."
            ),
            "badges": ["data/universe.csv"],
        },
        {
            "kicker": "STAGING",
            "title": "Staged file present" if staged.get("exists") else "No staged universe",
            "body": (
                "Run make universe-preview before make universe-apply. Dashboard stays read-only for safety."
                if staged.get("exists")
                else "No staged universe is waiting; run make universe-preview before make universe-apply."
            ),
            "badges": ["data/imports/universe.csv"],
            "command": "make universe-apply",
        },
        {
            "kicker": "WORKFLOW",
            "title": "Preview first",
            "body": "Use source presets to build a candidate universe with make universe-preview, then run make universe-apply only after reviewing the staged CSV.",
            "badges": ["CSV-first", "backup on apply"],
            "command": "make universe-preview",
        },
    ]


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
            "Meaning": "Add or refresh verified OHLCV files before relying on momentum or track-record context.",
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
            "What to do": "Use `make runbook-prices-broader` or `make focus-price TICKER=...` first. For downloaded files, use `make price-normalize`, then run `make price-validate`, `make price-preview`, and `make price-apply`.",
        },
        {
            "Dashboard Label": "Needs SEC enrichment",
            "What to do": "Use `make runbook-fundamentals-broader` or `make focus-fundamentals TICKER=...` first, then run `make imports-validate`, `make imports-preview`, `make imports-apply`, and `make status-check TOP_N=5`.",
        },
        {
            "Dashboard Label": "Needs peers.csv",
            "What to do": "Use `make runbook-peers-broader` or `make focus-peers TICKER=...` first, then add manually researched mappings through `data/imports/peers.csv`, run `make imports-validate`, `make imports-preview`, `make imports-apply`, and `make status-check TOP_N=5`. If mappings already exist, finish the staged peer fundamentals or peer price follow-through the queue points to.",
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
        {"Step": "Read-only status", "Command": "make status-check TOP_N=5"},
        {"Step": "Single-name price fix", "Command": "make focus-price TICKER=NVDA"},
        {"Step": "Single-name fundamentals fix", "Command": "make focus-fundamentals TICKER=NVDA"},
        {"Step": "Single-name peers fix", "Command": "make focus-peers TICKER=NVDA"},
        {"Step": "Broader price runbook", "Command": "make runbook-prices-broader"},
        {"Step": "Deterministic verification", "Command": "make verify"},
        {"Step": "Extended validation", "Command": "make validate-all"},
        {"Step": "Dashboard smoke check", "Command": "make dashboard-smoke"},
        {"Step": "Optional broader pipeline", "Command": "make daily"},
        {"Step": "Data coverage", "Command": "make data-wizard TOP_N=5"},
        {"Step": "Manual price normalization", "Command": "make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual"},
        {"Step": "Price import safety", "Command": "make price-validate && make price-preview && make price-apply"},
        {"Step": "SEC fundamentals staging", "Command": "make focus-fundamentals TICKER=NVDA"},
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
        {"Scenario": "No local prices or short history", "Next step": "Use make runbook-prices-broader or make focus-price TICKER=... first. For downloaded files, use make price-normalize INPUT=... TICKER=... SOURCE=..., then run make price-validate, make price-preview, and make price-apply."},
        {"Scenario": "No local fundamentals for valuation", "Next step": "Use make runbook-fundamentals-broader or make focus-fundamentals TICKER=... first, then run make imports-validate, make imports-preview, and make imports-apply."},
        {"Scenario": "No peer-relative context", "Next step": "Use make runbook-peers-broader or make focus-peers TICKER=... first. If mappings are missing, run make templates, then fill data/imports/peers.csv; if mappings already exist, follow the staged peer fundamentals or price blocker the queue prints."},
        {"Scenario": "No earnings or analyst estimates", "Next step": "Leave them missing safely unless you have a trusted local source"},
        {"Scenario": "No staged imports to review", "Next step": "Use templates or SEC/manual price staging first, then run make imports-validate, make imports-preview, and make imports-apply for staged local datasets, or use make price-validate, make price-preview, and make price-apply for staged price rows."},
    ]


def unlock_stage_command(stage: object, fallback: str = "") -> str:
    stage_text = format_missing(stage, "").strip().lower()
    command_map = {
        "prices": "make runbook-prices-broader",
        "fundamentals": "make runbook-fundamentals-broader",
        "peers": "make runbook-peers-broader",
        "optional_context": "make onboarding",
        "ready": "make status-check TOP_N=5",
    }
    return command_map.get(stage_text, fallback)


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
                "make status-check TOP_N=5",
                "warning",
            )
        ]
    actions: list[tuple[str, str, str, str]] = []
    for row in payload.get("top_onboarding_actions", [])[:limit]:
        priority = int(row.get("priority") or 999)
        dataset = format_missing(row.get("dataset"))
        ticker = format_missing(row.get("ticker"), fallback="")
        target_file = format_missing(row.get("target_file"), "")
        command = preferred_row_command(
            row,
            ticker_focus_command(row.get("dataset"), row.get("ticker"), "make status-check TOP_N=5"),
        )
        reason = normalize_operator_copy(row.get("reason"))
        recommended_action = normalize_operator_copy(row.get("recommended_action"))
        body = command_family_fallback(command, review_path_fallback(row.get("dataset")))
        lowered_command = command.lower()
        if "runbook-" in lowered_command:
            body = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
        if reason and reason != "Not available":
            body = f"{reason} {recommended_action}".strip() if recommended_action and recommended_action != reason else reason
        elif recommended_action and recommended_action != "Not available":
            body = recommended_action
        elif body == "Review local data coverage.":
            body = "Local data coverage needs attention."
        if lowered_command == "make imports-validate":
            normalized_body = body.lower()
            if "make imports-preview" not in normalized_body or "make imports-apply" not in normalized_body:
                body = (
                    f"{reason} Run make imports-validate, then make imports-preview, then make imports-apply so staged local data is reviewed before apply."
                    if reason and reason != "Not available"
                    else "Run make imports-validate, then make imports-preview, then make imports-apply so staged local data is reviewed before apply."
                )
        elif lowered_command == "make price-validate":
            normalized_body = body.lower()
            if "make price-preview" not in normalized_body or "make price-apply" not in normalized_body:
                body = (
                    f"{reason} Run make price-validate, then make price-preview, then make price-apply so staged price rows are reviewed before apply."
                    if reason and reason != "Not available"
                    else "Run make price-validate, then make price-preview, then make price-apply so staged price rows are reviewed before apply."
                )
        staged_follow_through = ""
        if target_file == "data/imports/fundamentals.csv":
            staged_follow_through = "Run make imports-validate, then make imports-preview, then make imports-apply for the staged fundamentals import."
        elif target_file == "data/imports/peers.csv":
            staged_follow_through = "Run make imports-validate, then make imports-preview, then make imports-apply for the staged peer import."
        elif target_file == "data/imports/prices.csv":
            staged_follow_through = "Run make price-validate, then make price-preview, then make price-apply for the staged price import."
        if staged_follow_through:
            normalized_body = body.lower()
            needs_staged_upgrade = False
            if target_file == "data/imports/prices.csv":
                needs_staged_upgrade = (
                    "make price-validate" not in normalized_body
                    or "make price-preview" not in normalized_body
                    or "make price-apply" not in normalized_body
                )
            else:
                needs_staged_upgrade = (
                    "make imports-validate" not in normalized_body
                    or "make imports-preview" not in normalized_body
                    or "make imports-apply" not in normalized_body
                )
            if needs_staged_upgrade:
                body = (
                    f"{reason} {staged_follow_through}".strip()
                    if reason and reason != "Not available"
                    else staged_follow_through
                )
        title = f"P{priority} {dataset}" + (f" - {ticker}" if ticker else "")
        tone = "danger" if priority <= 1 else "warning" if priority <= 2 else "neutral"
        actions.append((title, compact_reason(body, max_sentences=2, max_chars=220), command, tone))
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
    if not payload:
        return []

    command_rows = payload.get("recommended_next_command_rows", [])
    if command_rows:
        rows: list[dict[str, str]] = []
        for row in command_rows:
            command = normalize_operator_command(row.get("Command"))
            if not command:
                command = "make status-check TOP_N=5"
            rows.append(
                {
                    "Step": format_missing(row.get("Step"), "Next"),
                    "Command": command,
                    "Reason": format_missing(row.get("Reason"), ""),
                }
            )
        if rows:
            return rows

    commands = payload.get("recommended_next_commands", [])
    normalized: list[dict[str, str]] = []
    for index, command in enumerate(commands, start=1):
        command_text = normalize_operator_command(command)
        normalized.append({"Step": f"Next {index}", "Command": command_text})
    return normalized


def project_status_cockpit_html(payload: dict[str, Any] | None, health_score: int, health_label: str) -> str:
    if not payload:
        return notice_card_html(
            "Project status unavailable",
            "Run `make status-check TOP_N=5` to rebuild the local read-only project status snapshot.",
            "make status-check TOP_N=5",
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
            "command": "make monthly",
        },
        {
            "kicker": "PRICE COVERAGE",
            "title": f"{price_ready}/{total_tickers}",
            "body": "Tickers with enough local price context for momentum and track-record workflows.",
            "badges": ["highest leverage"],
            "command": "make runbook-prices-broader",
        },
        {
            "kicker": "VALUATION PATH",
            "title": f"{dcf_ready} DCF-ready",
            "body": f"{peer_ready} tickers also have peer-relative context. {gap_count} data gaps remain visible, not guessed.",
            "badges": ["research only"],
            "command": "make runbook-fundamentals-broader",
        },
        {
            "kicker": "FIX FIRST",
            "title": f"{queue_summary.get('critical', 0)} critical",
            "body": f"{queue_summary.get('high', 0)} high-priority remediation items remain in the local action queue.",
            "badges": ["make action-queue-check TOP_N=10"],
            "command": "make action-queue-check TOP_N=10",
        },
    ]


def overview_interpretation_guardrail_card(
    project_status_payload: dict[str, Any] | None,
    queue_summary: dict[str, int],
    health_summary: dict[str, int],
) -> dict[str, object]:
    summary = {} if not project_status_payload else project_status_payload.get("summary", {})
    total_tickers = int(summary.get("tickers_total") or 0)
    price_ready = int(summary.get("tickers_with_prices") or 0)
    dcf_ready = int(summary.get("tickers_dcf_ready") or 0)
    peer_ready = int(summary.get("tickers_peer_ready") or 0)
    data_gaps = int(summary.get("data_gaps") or 0)
    health_score, health_label = workflow_health_score(queue_summary, health_summary)

    if health_label == "Ready":
        body = (
            f"Local coverage is strong enough to read momentum, watchlist, and valuation context with fewer blockers. "
            f"{price_ready}/{total_tickers} tickers have prices, {dcf_ready} are DCF-ready, and {peer_ready} have peer-relative context."
        )
        badges = ["ready", "read with context"]
        command = "make dashboard-smoke"
    elif health_label == "Partial":
        body = (
            f"The workflow is usable, but some outputs should still be treated as partial. "
            f"{data_gaps} visible data gaps remain, so rankings and valuation context should stay tied to the missing-data notes."
        )
        badges = ["partial", "check gaps"]
        command = "make status-check TOP_N=5"
    else:
        body = (
            f"Coverage is still the main blocker. "
            f"Only {price_ready}/{total_tickers} tickers have usable prices, while DCF-ready and peer-ready coverage remain sparse. "
            "Use onboarding and Data Health before leaning on downstream rankings."
        )
        badges = ["needs data", "coverage first"]
        command = "make onboarding"

    return {
        "kicker": "INTERPRETATION GUARDRAIL",
        "title": f"{health_label} workflow · {health_score}/100",
        "body": body,
        "badges": badges,
        "command": command,
    }


def overview_coverage_hotspot_cards(action_queue: pd.DataFrame | None, limit: int = 4) -> list[dict[str, object]]:
    if action_queue is None or action_queue.empty or "action_type" not in action_queue.columns:
        return [
            {
                "kicker": "COVERAGE HOTSPOT",
                "title": "No hotspot queue yet",
                "body": "Run make action-queue to generate the local action queue and see whether prices, fundamentals, peers, or optional context are creating the most research friction.",
                "badges": ["research queue"],
                "command": "make action-queue",
            }
        ]

    queue = action_queue.copy()
    queue["action_type"] = queue["action_type"].astype(str).str.strip().str.lower()
    if "ticker" in queue.columns:
        queue["ticker"] = queue["ticker"].fillna("").astype(str).str.strip().str.upper()
    else:
        queue["ticker"] = ""
    queue["priority"] = pd.to_numeric(queue.get("priority"), errors="coerce").fillna(999)

    label_map = {
        "prices": ("PRICE PRESSURE", "Prices", "Verified local price history still drives the most downstream research value."),
        "fundamentals": ("DCF PRESSURE", "Fundamentals", "SEC-stageable or local fundamentals are still blocking richer valuation context."),
        "peers": ("PEER PRESSURE", "Peers", "Manual peer mappings are still required for peer-relative research and medians."),
        "earnings": ("OPTIONAL CONTEXT", "Earnings", "Optional earnings context is still missing for some single-name reports."),
        "analyst_estimates": ("OPTIONAL CONTEXT", "Analyst Estimates", "Optional analyst context is still missing for some single-name reports."),
    }
    command_map = {
        "prices": "make runbook-prices-broader",
        "fundamentals": "make runbook-fundamentals-broader",
        "peers": "make runbook-peers-broader",
        "earnings": "make onboarding",
        "analyst_estimates": "make onboarding",
    }

    cards: list[dict[str, object]] = []
    grouped = (
        queue.groupby("action_type", dropna=False)
        .agg(
            row_count=("action_type", "size"),
            ticker_count=("ticker", lambda series: int(series.replace("", pd.NA).dropna().nunique())),
            best_priority=("priority", "min"),
        )
        .reset_index()
        .sort_values(["best_priority", "row_count", "action_type"], ascending=[True, False, True])
    )

    for _, row in grouped.head(limit).iterrows():
        action_type = str(row.get("action_type", "")).strip().lower()
        kicker, title, base_body = label_map.get(
            action_type,
            ("COVERAGE HOTSPOT", display_column_label(action_type or "coverage"), "This dataset type still has visible local workflow pressure."),
        )
        sample_rows = queue.loc[queue["action_type"] == action_type].sort_values(["priority", "ticker"], na_position="last").head(3)
        tickers = [
            str(ticker).strip().upper()
            for ticker in sample_rows["ticker"].tolist()
            if pd.notna(ticker) and str(ticker).strip() and str(ticker).strip().upper() != "NAN"
        ]
        ticker_count = int(row.get("ticker_count", 0) or 0)
        row_count = int(row.get("row_count", 0) or 0)
        body = f"{base_body} {row_count} action rows and {ticker_count} affected tickers are currently visible."
        if tickers:
            body += f" Examples: {', '.join(tickers[:3])}."
        cards.append(
            {
                "kicker": kicker,
                "title": title,
                "body": body,
                "badges": [f"P{int(row.get('best_priority', 999))}", f"{ticker_count} tickers"],
                "command": command_map.get(action_type, "make action-queue-check TOP_N=10"),
            }
        )

    return cards or [
        {
            "kicker": "COVERAGE HOTSPOT",
            "title": "No hotspot queue yet",
            "body": "Run make action-queue to generate the local action queue and see whether prices, fundamentals, peers, or optional context are creating the most research friction.",
            "badges": ["research queue"],
            "command": "make action-queue",
        }
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
                "body": "Add holdings rows, then run make onboarding to refresh onboarding outputs and surface blocked portfolio names before broader universe work.",
                "badges": ["read-only"],
                "command": "make onboarding",
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
                    "command": (
                        normalize_operator_command(format_missing(row.get("example_command"), ""))
                        or preferred_row_command(
                            row,
                            unlock_stage_command(row.get("top_priority_stage"), "make onboarding"),
                        )
                    ),
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
        target_file = format_missing(row.get("target_file"), "")
        staged_fundamentals_import = target_file == "data/imports/fundamentals.csv"
        staged_peer_import = target_file == "data/imports/peers.csv"
        staged_price_import = target_file == "data/imports/prices.csv"
        command = (
            preferred_row_command(row, "make imports-validate")
            if staged_fundamentals_import or staged_peer_import
            else (
                preferred_row_command(row, "make price-validate")
                if staged_price_import
                else preferred_row_command(
                    row,
                    ticker_focus_command(
                        stage,
                        row.get("ticker"),
                        unlock_stage_command(stage, "make onboarding"),
                    ),
                )
            )
        )
        if staged_fundamentals_import:
            fallback_action = (
                f"Staged fundamentals import is waiting in {target_file}; run make imports-validate, then make imports-preview, then make imports-apply before trusting DCF coverage."
            )
        elif staged_peer_import:
            fallback_action = (
                f"Staged peer import is waiting in {target_file}; run make imports-validate, then make imports-preview, then make imports-apply before trusting peer-relative context."
            )
        elif staged_price_import:
            fallback_action = (
                f"Staged price import is waiting in {target_file}; run make price-validate, then make price-preview, then make price-apply before trusting local price coverage."
            )
        else:
            fallback_action = command_family_fallback(command, f"Review {stage} path.")
            if "runbook-" in command.lower():
                fallback_action = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
        next_action_summary = compact_reason(row.get("recommended_action") or fallback_action, max_sentences=1, max_chars=150)
        if staged_price_import and (
            "make price-validate" not in next_action_summary
            or "make price-preview" not in next_action_summary
            or "make price-apply" not in next_action_summary
        ):
            next_action_summary = compact_reason(fallback_action, max_sentences=1, max_chars=150)
        cards.append(
            {
                "kicker": ticker,
                "title": goal,
                "body": (
                    f"{purpose}. Current stage: {stage}. "
                    f"Next action: {next_action_summary}"
                ),
                "badges": [stage, format_missing(row.get("price_stage_status"), "prices")],
                "command": command,
            }
        )
    return cards


def holdings_deep_research_cards(
    holdings: pd.DataFrame | None,
    sec_stage_queue: pd.DataFrame | None,
    peer_mapping_queue: pd.DataFrame | None,
    limit: int = 4,
) -> list[dict[str, object]]:
    if holdings is None or holdings.empty:
        return [
            {
                "kicker": "HOLDINGS DCF / PEERS",
                "title": "No holdings deep-research board yet",
                "body": "Add holdings rows, then run make onboarding to refresh onboarding outputs and see which portfolio names next benefit from SEC staging or manual peer research.",
                "badges": ["read-only"],
                "command": "make onboarding",
            }
        ]

    holdings_lookup = {str(column).strip().lower(): str(column) for column in holdings.columns}
    ticker_col = holdings_lookup.get("ticker")
    purpose_col = holdings_lookup.get("primarypurpose")
    if not ticker_col:
        return []

    holding_context = holdings.copy()
    holding_context[ticker_col] = holding_context[ticker_col].astype(str).str.upper().str.strip()
    holding_tickers = holding_context[ticker_col].dropna().astype(str).tolist()
    purpose_map = (
        holding_context.set_index(ticker_col)[purpose_col].astype(str).to_dict()
        if purpose_col and purpose_col in holding_context.columns
        else {}
    )

    cards: list[dict[str, object]] = []

    if sec_stage_queue is not None and not sec_stage_queue.empty and "ticker" in sec_stage_queue.columns:
        sec_rows = sec_stage_queue.copy()
        sec_rows["ticker"] = sec_rows["ticker"].astype(str).str.upper().str.strip()
        sec_rows = sec_rows.loc[sec_rows["ticker"].isin(holding_tickers)].copy()
        if not sec_rows.empty:
            sec_rows["priority"] = pd.to_numeric(sec_rows.get("priority"), errors="coerce").fillna(999)
            for _, row in sec_rows.sort_values(["priority", "price_history_days", "ticker"], ascending=[True, False, True]).head(limit).iterrows():
                ticker = format_missing(row.get("ticker"), "Holding")
                target_file = format_missing(row.get("target_file"), "")
                staged_import = target_file == "data/imports/fundamentals.csv"
                command = preferred_row_command(
                    row,
                    (
                        "make imports-validate"
                        if staged_import
                        else ticker_focus_command("fundamentals", row.get("ticker"), "make onboarding")
                    ),
                )
                fallback_action = (
                    "Staged fundamentals import ready. "
                    "Run make imports-validate, then make imports-preview, then make imports-apply before trusting DCF coverage."
                    if staged_import
                    else command_family_fallback(command, "Review fundamentals path.")
                )
                if not staged_import and "runbook-" in command.lower():
                    fallback_action = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
                next_action_summary = compact_reason(row.get("recommended_action") or fallback_action, max_sentences=1, max_chars=150)
                if staged_import and (
                    "make imports-validate" not in next_action_summary
                    or "make imports-preview" not in next_action_summary
                    or "make imports-apply" not in next_action_summary
                ):
                    next_action_summary = fallback_action
                cards.append(
                    {
                        "kicker": ticker,
                        "title": "Advance staged fundamentals import" if staged_import else "Unlock DCF",
                        "body": (
                            f"{format_missing(purpose_map.get(ticker), 'Portfolio holding')}. "
                            f"SEC/fundamentals queue priority P{format_missing(row.get('priority'), '-')}. "
                            f"{next_action_summary}"
                        ),
                        "badges": ["fundamentals", format_missing(row.get("theme"), "theme")],
                        "command": command,
                    }
                )

    if peer_mapping_queue is not None and not peer_mapping_queue.empty and "ticker" in peer_mapping_queue.columns:
        peer_rows = peer_mapping_queue.copy()
        peer_rows["ticker"] = peer_rows["ticker"].astype(str).str.upper().str.strip()
        peer_rows = peer_rows.loc[peer_rows["ticker"].isin(holding_tickers)].copy()
        if not peer_rows.empty:
            peer_rows["priority"] = pd.to_numeric(peer_rows.get("priority"), errors="coerce").fillna(999)
            for _, row in peer_rows.sort_values(["priority", "ticker"], ascending=[True, True]).head(limit).iterrows():
                ticker = format_missing(row.get("ticker"), "Holding")
                target_file = format_missing(row.get("target_file"), "")
                staged_import = target_file == "data/imports/peers.csv"
                command = preferred_row_command(
                    row,
                    (
                        "make imports-validate"
                        if staged_import
                        else ticker_focus_command("peers", row.get("ticker"), "make onboarding")
                    ),
                )
                fallback_action = (
                    "Staged peer import ready. "
                    "Run make imports-validate, then make imports-preview, then make imports-apply before trusting peer-relative context."
                    if staged_import
                    else command_family_fallback(command, "Review peer path.")
                )
                if not staged_import and "runbook-" in command.lower():
                    fallback_action = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
                next_action_summary = compact_reason(row.get("recommended_action") or fallback_action, max_sentences=1, max_chars=150)
                if staged_import and (
                    "make imports-validate" not in next_action_summary
                    or "make imports-preview" not in next_action_summary
                    or "make imports-apply" not in next_action_summary
                ):
                    next_action_summary = fallback_action
                cards.append(
                    {
                        "kicker": ticker,
                        "title": "Advance staged peer import" if staged_import else "Unlock Peer Relative",
                        "body": (
                            f"{format_missing(purpose_map.get(ticker), 'Portfolio holding')}. "
                            f"Peer queue priority P{format_missing(row.get('priority'), '-')}. "
                            f"{next_action_summary}"
                        ),
                        "badges": ["peers", format_missing(row.get("theme"), "theme")],
                        "command": command,
                    }
                )

    deduped: list[dict[str, object]] = []
    seen: set[str] = set()
    for card in cards:
        key = f"{card.get('kicker')}|{card.get('title')}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(card)

    if deduped:
        return deduped[:limit]

    return [
        {
            "kicker": "HOLDINGS DCF / PEERS",
            "title": "No holdings DCF / peer queue yet",
            "body": "Run make onboarding to refresh the onboarding outputs and generate the SEC stage queue plus peer mapping queue for holdings-first deep-research blockers.",
            "badges": ["read-only"],
            "command": "make onboarding",
        }
    ]


def theme_unlock_cards(
    unlock_priority_summary: pd.DataFrame | None,
    limit: int = 3,
) -> list[dict[str, object]]:
    if unlock_priority_summary is None or unlock_priority_summary.empty or "group_type" not in unlock_priority_summary.columns:
        return [
            {
                "kicker": "THEME FIRST",
                "title": "No theme unlock board yet",
                "body": "Run make onboarding to refresh the onboarding outputs and surface which local themes or sector ETF clusters are blocked first.",
                "badges": ["read-only"],
                "command": "make onboarding",
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
                "body": "Run make universe-preview to stage broader local universe context, then refresh onboarding outputs so grouped theme and sector ETF unlock rows can appear here.",
                "badges": ["read-only"],
                "command": "make universe-preview",
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
            "command": (
                normalize_operator_command(format_missing(theme_rows.iloc[0].get("example_command"), ""))
                or preferred_row_command(
                    theme_rows.iloc[0],
                    unlock_stage_command(theme_rows.iloc[0].get("top_priority_stage"), "make universe-preview"),
                )
            ),
        }
    ]

    for _, row in theme_rows.sort_values(["stage_rank", "holdings_count", "ticker_count", "group_name"], ascending=[True, False, False, True]).head(limit).iterrows():
        target_file = format_missing(row.get("target_file"), "")
        staged_fundamentals_import = target_file == "data/imports/fundamentals.csv"
        staged_peer_import = target_file == "data/imports/peers.csv"
        staged_price_import = target_file == "data/imports/prices.csv"
        command = (
            preferred_row_command(row, "make imports-validate")
            if staged_fundamentals_import or staged_peer_import
            else (
                preferred_row_command(row, "make price-validate")
                if staged_price_import
                else (
                    normalize_operator_command(format_missing(row.get("example_command"), ""))
                    or preferred_row_command(
                        row,
                        unlock_stage_command(row.get("top_priority_stage"), "make universe-preview"),
                    )
                )
            )
        )
        if staged_fundamentals_import:
            fallback_action = (
                f"Staged fundamentals import is waiting in {target_file}; run make imports-validate, then make imports-preview, then make imports-apply before trusting grouped DCF coverage."
            )
        elif staged_peer_import:
            fallback_action = (
                f"Staged peer import is waiting in {target_file}; run make imports-validate, then make imports-preview, then make imports-apply before trusting grouped peer-relative context."
            )
        elif staged_price_import:
            fallback_action = (
                f"Staged price import is waiting in {target_file}; run make price-validate, then make price-preview, then make price-apply before trusting grouped local price coverage."
            )
        else:
            fallback_action = command_family_fallback(command, 'Review grouped unlock path.')
        next_action_summary = compact_reason(row.get("recommended_action") or fallback_action, max_sentences=1, max_chars=150)
        if staged_price_import and (
            "make price-validate" not in next_action_summary
            or "make price-preview" not in next_action_summary
            or "make price-apply" not in next_action_summary
        ):
            next_action_summary = compact_reason(fallback_action, max_sentences=1, max_chars=150)
        cards.append(
            {
                "kicker": format_missing(row.get("group_name"), "Theme"),
                "title": format_missing(row.get("next_unlock_goal"), "Unlock data"),
                "body": (
                    f"{format_missing(row.get('group_type'), 'group')} group with "
                    f"{format_missing(row.get('ticker_count'), '0')} tickers and "
                    f"{format_missing(row.get('holdings_count'), '0')} holdings. "
                    f"Next action: {next_action_summary}"
                ),
                "badges": [
                    format_missing(row.get("top_priority_stage"), "stage"),
                    format_missing(row.get("group_type"), "group"),
                ],
                "command": command,
            }
        )
    return cards


def theme_deep_research_cards(
    sec_stage_queue: pd.DataFrame | None,
    peer_mapping_queue: pd.DataFrame | None,
    limit: int = 4,
) -> list[dict[str, object]]:
    def _group_rows(frame: pd.DataFrame | None, goal: str, dataset_badge: str) -> list[dict[str, object]]:
        if frame is None or frame.empty or "theme" not in frame.columns:
            return []
        grouped = frame.copy()
        grouped["theme"] = grouped["theme"].astype(str).str.strip()
        grouped = grouped.loc[grouped["theme"].ne("") & grouped["theme"].ne("Unclassified")].copy()
        if grouped.empty:
            return []
        grouped["priority"] = pd.to_numeric(grouped.get("priority"), errors="coerce").fillna(999)
        grouped["ticker"] = grouped.get("ticker", pd.Series(dtype=object)).astype(str).str.upper().str.strip()
        grouped["is_holding"] = grouped.get("is_holding", pd.Series(dtype=object)).astype(str).str.lower().isin({"true", "1", "yes"})

        rows: list[dict[str, object]] = []
        for theme_name, theme_frame in grouped.groupby("theme", dropna=False):
            theme_frame = theme_frame.sort_values(["priority", "is_holding", "ticker"], ascending=[True, False, True])
            top_row = theme_frame.iloc[0]
            tickers = ", ".join(theme_frame["ticker"].head(4).tolist())
            target_file = format_missing(top_row.get("target_file"), "")
            staged_import = (
                (dataset_badge == "fundamentals" and target_file == "data/imports/fundamentals.csv")
                or (dataset_badge == "peers" and target_file == "data/imports/peers.csv")
            )
            command = preferred_row_command(
                top_row,
                (
                    "make imports-validate"
                    if staged_import
                    else ticker_focus_command(dataset_badge, top_row.get("ticker"), "make onboarding")
                ),
            )
            fallback_action = (
                f"Staged {dataset_badge.lower()} import in {target_file}; run make imports-validate, make imports-preview, then make imports-apply."
                if staged_import
                else command_family_fallback(
                    command,
                    "Review fundamentals path." if dataset_badge == "fundamentals" else "Review peer path.",
                )
            )
            if not staged_import and "runbook-" in command.lower():
                fallback_action = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
            next_action_summary = compact_reason(top_row.get("recommended_action") or fallback_action, max_sentences=1, max_chars=150)
            if staged_import and (
                "make imports-validate" not in next_action_summary
                or "make imports-preview" not in next_action_summary
                or "make imports-apply" not in next_action_summary
            ):
                next_action_summary = fallback_action
            rows.append(
                {
                    "kicker": str(theme_name),
                    "title": (
                        "Advance staged fundamentals import"
                        if staged_import and dataset_badge == "fundamentals"
                        else "Advance staged peer import"
                        if staged_import and dataset_badge == "peers"
                        else goal
                    ),
                    "body": (
                        f"{len(theme_frame)} ticker rows in this theme currently point to {dataset_badge.lower()} work. "
                        f"Representative names: {tickers}. "
                        f"Next action: {next_action_summary}"
                    ),
                    "badges": [dataset_badge, f"P{format_missing(top_row.get('priority'), '-')}"],
                    "command": command,
                    "sort_priority": float(top_row.get("priority", 999)),
                    "holdings_count": int(theme_frame["is_holding"].sum()),
                }
            )
        return rows

    cards = _group_rows(sec_stage_queue, "Unlock DCF", "fundamentals") + _group_rows(
        peer_mapping_queue, "Unlock Peer Relative", "peers"
    )
    if not cards:
        return [
            {
                "kicker": "THEME DCF / PEERS",
                "title": "No theme deep-research board yet",
                "body": "Run make onboarding to refresh the onboarding outputs and generate the SEC stage queue plus peer mapping queue for theme-level deep-research blockers.",
                "badges": ["read-only"],
                "command": "make onboarding",
            }
        ]

    cards = sorted(cards, key=lambda item: (item.get("sort_priority", 999), -item.get("holdings_count", 0), str(item.get("kicker", ""))))
    trimmed = []
    seen: set[str] = set()
    for card in cards:
        key = f"{card.get('kicker')}|{card.get('title')}"
        if key in seen:
            continue
        seen.add(key)
        trimmed.append({key: value for key, value in card.items() if key not in {"sort_priority", "holdings_count"}})
        if len(trimmed) >= limit:
            break
    return trimmed


def overview_research_pressure_cards(
    price_worklist: pd.DataFrame | None,
    sec_stage_queue: pd.DataFrame | None,
    peer_mapping_queue: pd.DataFrame | None,
    unlock_priority_summary: pd.DataFrame | None,
) -> list[dict[str, object]]:
    theme_price_led = 0
    if unlock_priority_summary is not None and not unlock_priority_summary.empty:
        summary = unlock_priority_summary.copy()
        theme_mask = summary.get("group_type", pd.Series(dtype=object)).astype(str).isin(["theme", "sector_etf"])
        theme_price_led = int(
            (
                theme_mask
                & summary.get("top_priority_stage", pd.Series(dtype=object)).astype(str).eq("prices")
            ).sum()
        )

    cards: list[dict[str, object]] = []

    price_summary = summarize_price_worklist(price_worklist)
    price_priority = price_summary.get("priority_1", 0)
    cards.append(
        {
            "kicker": "PRICE PRESSURE",
            "title": f"{price_priority} urgent price gaps",
            "body": (
                f"{price_summary.get('momentum_ready', 0)} tickers are momentum-ready, "
                f"{price_summary.get('track_record_ready', 0)} support track-record work, and "
                f"{theme_price_led} grouped themes are still price-led."
            ),
            "badges": ["prices", "highest leverage" if price_priority else "monitor"],
            "command": "make runbook-prices-broader",
        }
    )

    sec_summary = summarize_sec_stage_queue(sec_stage_queue)
    cards.append(
        {
            "kicker": "DCF PRESSURE",
            "title": f"{sec_summary.get('priority_1', 0)} holdings-first DCF unlocks",
            "body": (
                f"{sec_summary.get('priority_2', 0)} more price-supported names are queued next, and "
                f"{sec_summary.get('missing_fundamentals', 0)} tickers still lack a local fundamentals row."
            ),
            "badges": ["fundamentals", "sec queue"],
            "command": "make runbook-fundamentals-broader",
        }
    )

    peer_summary = summarize_peer_mapping_queue(peer_mapping_queue)
    peer_missing = peer_summary.get("missing_peer_mapping", 0)
    peer_follow_through = peer_summary.get("mapped_peer_follow_through", 0)
    staged_peer_imports = peer_summary.get("staged_peer_import", 0)
    cards.append(
        {
            "kicker": "PEER PRESSURE",
            "title": (
                f"{peer_missing} missing peer mappings"
                if not peer_follow_through
                else f"{peer_missing} missing peer mappings · {peer_follow_through} mapped follow-through"
            ),
            "body": (
                f"{peer_summary.get('priority_1', 0)} holdings-first peer unlocks and "
                f"{peer_summary.get('priority_2', 0)} theme-level follow-ons are visible in the local queue. "
                + (
                    f"{staged_peer_imports} staged peer import{'s' if staged_peer_imports != 1 else ''} already need make imports-validate, make imports-preview, and make imports-apply."
                    if staged_peer_imports
                    else (
                        f"{peer_follow_through} mapped peer set{'s' if peer_follow_through != 1 else ''} still need peer-relative follow-through beyond the initial mapping step."
                        if peer_follow_through
                        else "Manual peer research is still the main blocker here."
                    )
                )
            ),
            "badges": ["peers", "staged follow-through" if staged_peer_imports else "manual research" if peer_missing else "peer support data"],
            "command": "make runbook-peers-broader",
        }
    )

    return cards


def overview_deep_research_leverage_cards(
    holdings: pd.DataFrame | None,
    sec_stage_queue: pd.DataFrame | None,
    peer_mapping_queue: pd.DataFrame | None,
) -> list[dict[str, object]]:
    holding_tickers: set[str] = set()
    if holdings is not None and not holdings.empty:
        holdings_lookup = {str(column).strip().lower(): str(column) for column in holdings.columns}
        ticker_col = holdings_lookup.get("ticker")
        if ticker_col:
            holding_tickers = set(holdings[ticker_col].dropna().astype(str).str.upper().str.strip())

    def _peer_lane_title(row: pd.Series) -> str:
        if format_missing(row.get("target_file"), "") == "data/imports/peers.csv":
            return "Staged peer import path"
        command = preferred_row_command(row, "")
        has_peer_mapping = format_missing(row.get("has_peer_mapping"), "").lower() in {"true", "1", "yes"}
        if has_peer_mapping:
            return "Peer support follow-through path"
        return "Manual peer path"

    def _lane_card(frame: pd.DataFrame | None, lane_name: str, title: str, badge: str) -> dict[str, object] | None:
        if frame is None or frame.empty or "ticker" not in frame.columns:
            return None
        rows = frame.copy()
        rows["ticker"] = rows["ticker"].astype(str).str.upper().str.strip()
        rows["priority"] = pd.to_numeric(rows.get("priority"), errors="coerce").fillna(999)
        rows["is_holding"] = rows["ticker"].isin(holding_tickers)
        rows["theme"] = rows.get("theme", pd.Series(dtype=object)).astype(str).str.strip()
        rows = rows.loc[rows["ticker"].ne("")].copy()
        if rows.empty:
            return None

        sorted_rows = rows.sort_values(["priority", "is_holding", "ticker"], ascending=[True, False, True])
        top_row = sorted_rows.iloc[0]
        holdings_count = int(rows["is_holding"].sum())
        unique_tickers = int(rows["ticker"].nunique())
        themes = sorted({theme for theme in rows["theme"].tolist() if theme and theme != "Unclassified"})
        lead_theme = themes[0] if themes else "Unclassified"
        lead_names = ", ".join(sorted_rows["ticker"].head(3).tolist()) or "Not available"
        leverage_score = holdings_count * 3 + len(themes) * 2 + min(unique_tickers, 5)
        card_title = title
        card_badges = [badge, f"leverage {leverage_score}"]
        lane_fallback = "make onboarding"
        target_file = format_missing(top_row.get("target_file"), "")
        staged_fundamentals_import = lane_name == "DCF LEVERAGE" and target_file == "data/imports/fundamentals.csv"
        staged_peer_import = lane_name == "PEER LEVERAGE" and target_file == "data/imports/peers.csv"
        if lane_name == "DCF LEVERAGE":
            lane_fallback = "make imports-validate" if staged_fundamentals_import else ticker_focus_command("fundamentals", top_row.get("ticker"), "make onboarding")
        elif lane_name == "PEER LEVERAGE":
            lane_fallback = "make imports-validate" if staged_peer_import else ticker_focus_command("peers", top_row.get("ticker"), "make onboarding")
        command = preferred_row_command(top_row, lane_fallback)
        if staged_fundamentals_import:
            card_title = "Staged fundamentals import path"
            card_badges = ["staged import", f"leverage {leverage_score}"]
        elif lane_name == "PEER LEVERAGE":
            card_title = _peer_lane_title(top_row)
            if command == "make imports-validate":
                card_badges = ["staged import", f"leverage {leverage_score}"]
            elif format_missing(top_row.get("has_peer_mapping"), "").lower() in {"true", "1", "yes"}:
                card_badges = ["peer support data", f"leverage {leverage_score}"]
        if staged_fundamentals_import:
            fallback_action = (
                f"Staged fundamentals import in {target_file}; run make imports-validate, make imports-preview, then make imports-apply."
            )
        elif staged_peer_import:
            fallback_action = (
                f"Staged peer import in {target_file}; run make imports-validate, make imports-preview, then make imports-apply."
            )
        else:
            fallback_action = command_family_fallback(
                command,
                "Review fundamentals path." if lane_name == "DCF LEVERAGE" else "Review peer path.",
            )
            if "runbook-" in command.lower():
                fallback_action = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
        next_action_summary = compact_reason(top_row.get("recommended_action") or fallback_action, max_sentences=1, max_chars=140)
        if (staged_fundamentals_import or staged_peer_import) and (
            "make imports-validate" not in next_action_summary
            or "make imports-preview" not in next_action_summary
            or "make imports-apply" not in next_action_summary
        ):
            next_action_summary = compact_reason(fallback_action, max_sentences=1, max_chars=140)
        return {
            "kicker": lane_name,
            "title": card_title,
            "body": (
                f"{holdings_count} holdings, {len(themes)} themes, and {unique_tickers} queued tickers are currently gated here. "
                f"Lead theme: {lead_theme}. Start with: {lead_names}. "
                f"Next action: {next_action_summary}"
            ),
            "badges": card_badges,
            "command": command,
            "_score": leverage_score,
        }

    sec_card = _lane_card(sec_stage_queue, "DCF LEVERAGE", "SEC fundamentals path", "fundamentals")
    peer_card = _lane_card(peer_mapping_queue, "PEER LEVERAGE", "Manual peer path", "peers")

    if sec_card is None and peer_card is None:
        return [
            {
                "kicker": "DEEP RESEARCH LEVERAGE",
                "title": "No deep-research leverage view yet",
                "body": "Run make onboarding to refresh the onboarding outputs and generate the SEC stage queue plus peer mapping queue before ranking the highest-leverage deep-research lane.",
                "badges": ["read-only"],
                "command": "make onboarding",
            }
        ]

    candidate_cards = [card for card in [sec_card, peer_card] if card is not None]
    best_lane = max(candidate_cards, key=lambda item: item.get("_score", 0))
    output_cards = [
        {
            "kicker": "BEST DEEP WORK NEXT",
            "title": str(best_lane.get("title", "Deep research")),
            "body": (
                f"{best_lane.get('kicker', 'This lane')} currently unlocks the most local research value next "
                "when you weigh holdings impact, grouped theme breadth, and queued ticker count."
            ),
            "badges": [str(item) for item in best_lane.get("badges", [])][:2] or ["research only"],
            "command": str(best_lane.get("command", "make onboarding")),
        }
    ]
    output_cards.extend({key: value for key, value in card.items() if key != "_score"} for card in candidate_cards)
    return output_cards


def overview_deep_research_priority_bridge_cards(
    holdings: pd.DataFrame | None,
    sec_stage_queue: pd.DataFrame | None,
    peer_mapping_queue: pd.DataFrame | None,
    limit: int = 3,
) -> list[dict[str, object]]:
    holding_tickers: set[str] = set()
    if holdings is not None and not holdings.empty:
        holdings_lookup = {str(column).strip().lower(): str(column) for column in holdings.columns}
        ticker_col = holdings_lookup.get("ticker")
        if ticker_col:
            holding_tickers = set(holdings[ticker_col].dropna().astype(str).str.upper().str.strip())

    priority_rows: list[dict[str, object]] = []

    def _collect_rows(frame: pd.DataFrame | None, lane: str, next_surface: str) -> None:
        if frame is None or frame.empty or "ticker" not in frame.columns:
            return
        rows = frame.copy()
        rows["ticker"] = rows["ticker"].astype(str).str.upper().str.strip()
        rows["priority"] = pd.to_numeric(rows.get("priority"), errors="coerce").fillna(999)
        rows["theme"] = rows.get("theme", pd.Series(dtype=object)).astype(str).str.strip()
        rows["is_holding"] = rows["ticker"].isin(holding_tickers)
        rows = rows.loc[rows["ticker"].ne("")].copy()
        if rows.empty:
            return
        lane_fallback = ""
        if lane == "Unlock DCF":
            lane_fallback = "fundamentals"
        elif lane == "Unlock Peer Relative":
            lane_fallback = "peers"
        for _, row in rows.sort_values(["priority", "is_holding", "ticker"], ascending=[True, False, True]).iterrows():
            ticker = format_missing(row.get("ticker"), "Ticker")
            target_file = format_missing(row.get("target_file"), "")
            staged_fundamentals_import = lane == "Unlock DCF" and target_file == "data/imports/fundamentals.csv"
            staged_peer_import = lane == "Unlock Peer Relative" and target_file == "data/imports/peers.csv"
            if staged_fundamentals_import or staged_peer_import:
                fallback_command = "make imports-validate"
            else:
                fallback_command = ticker_focus_command(lane_fallback, ticker, fallback="") if lane_fallback else ""
            command = preferred_row_command(row, fallback_command or "Not available")
            if staged_fundamentals_import:
                fallback_action = (
                    "Run make imports-validate, then make imports-preview, then make imports-apply for the staged fundamentals import."
                )
            elif staged_peer_import:
                fallback_action = (
                    "Run make imports-validate, then make imports-preview, then make imports-apply for the staged peer import."
                )
            else:
                fallback_action = command_family_fallback(
                    command,
                    "Review fundamentals path." if lane == "Unlock DCF" else "Review peer path.",
                )
                if "runbook-" in command.lower():
                    fallback_action = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
            next_action_summary = compact_reason(
                row.get("recommended_action") or fallback_action,
                max_sentences=1,
                max_chars=140,
            )
            if (staged_fundamentals_import or staged_peer_import) and (
                "make imports-validate" not in next_action_summary
                or "make imports-preview" not in next_action_summary
                or "make imports-apply" not in next_action_summary
            ):
                next_action_summary = compact_reason(fallback_action, max_sentences=1, max_chars=140)
            priority_rows.append(
                {
                    "ticker": ticker,
                    "lane": (
                        "Advance staged fundamentals import"
                        if staged_fundamentals_import
                        else "Advance staged peer import"
                        if staged_peer_import
                        else lane
                    ),
                    "theme": format_missing(row.get("theme"), "Unclassified"),
                    "is_holding": bool(row.get("is_holding")),
                    "priority": float(row.get("priority", 999)),
                    "next_surface": next_surface,
                    "recommended_action": next_action_summary,
                    "command": command,
                }
            )

    _collect_rows(sec_stage_queue, "Unlock DCF", "Data Health")
    _collect_rows(peer_mapping_queue, "Unlock Peer Relative", "Data Health")

    if not priority_rows:
        return [
            {
                "kicker": "DEEP RESEARCH PRIORITIES",
                "title": "No deep-research shortlist yet",
                "body": "Run make onboarding to refresh the onboarding outputs and generate the SEC stage queue plus peer mapping queue for the next deep-research names.",
                "badges": ["read-only"],
                "command": "make onboarding",
            }
        ]

    priority_rows.sort(key=lambda item: (item["priority"], not item["is_holding"], item["ticker"]))
    cards: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in priority_rows:
        key = row["ticker"]
        if key in seen:
            continue
        seen.add(key)
        cards.append(
            {
                "kicker": row["ticker"],
                "title": row["lane"],
                "body": (
                    f"{'Current holding' if row['is_holding'] else 'Universe name'} in {row['theme']}. "
                    f"Next surface: {row['next_surface']}. "
                    f"{row['recommended_action']}"
                ),
                "badges": [
                    "holding" if row["is_holding"] else "theme",
                    row["theme"],
                ],
                "command": row["command"],
                "command_reason": row["recommended_action"],
            }
        )
        if len(cards) >= limit:
            break
    return cards


def overview_deep_research_handoff_cards(
    holdings: pd.DataFrame | None,
    sec_stage_queue: pd.DataFrame | None,
    peer_mapping_queue: pd.DataFrame | None,
    project_status_payload: dict[str, Any] | None,
    action_queue: pd.DataFrame | None,
) -> list[dict[str, object]]:
    top_priority = overview_deep_research_priority_bridge_cards(
        holdings,
        sec_stage_queue,
        peer_mapping_queue,
        limit=1,
    )[0]
    fallback_command = overview_next_command_cards(project_status_payload, action_queue, limit=1)[0]
    handoff_tabs = overview_handoff_cards()
    next_tab = next((card for card in handoff_tabs if card.get("title") == "Data Health"), handoff_tabs[0])

    ticker = format_missing(top_priority.get("kicker"), "Not available")
    empty_shortlist = ticker == "DEEP RESEARCH PRIORITIES"
    if ticker == "DEEP RESEARCH PRIORITIES":
        ticker = format_missing(top_priority.get("title"), "Not available")
    lane = format_missing(top_priority.get("title"), "Deep research")
    command_text = format_missing(top_priority.get("command"), "")
    if not command_text or command_text == "Not available":
        command_text = format_missing(fallback_command.get("title"), "make status")
    command_reason = compact_reason(top_priority.get("command_reason"), max_sentences=2, max_chars=220)
    if not command_reason or command_reason == "Not available":
        command_reason = compact_reason(top_priority.get("body"), max_sentences=3, max_chars=240)
    if command_text == format_missing(fallback_command.get("title"), "make status"):
        fallback_reason = compact_reason(fallback_command.get("body"), max_sentences=2, max_chars=220)
        if fallback_reason and fallback_reason != "Not available":
            command_reason = fallback_reason
    if not command_reason or command_reason == "Not available":
        command_reason = (
            f"Run {command_text} next so the local queue step for {ticker} is explicit and reviewable before deeper interpretation."
        )

    return [
        {
            "kicker": "DEEP RESEARCH NAME",
            "title": ticker,
            "body": (
                "Deep-research queues are not available yet. Refresh the onboarding outputs before ranking the next SEC or peer-research lane."
                if empty_shortlist
                else f"{ticker} is the clearest current name for {lane.lower()} based on the local SEC and peer queues."
            ),
            "badges": [str(item) for item in top_priority.get("badges", [])][:2] or ["research only"],
            "command": command_text,
        },
        {
            "kicker": "DEEP RESEARCH COMMAND",
            "title": command_text,
            "body": command_reason,
            "badges": ["command", "read-only"],
            "command": command_text,
        },
        {
            "kicker": "DEEP RESEARCH TAB",
            "title": str(next_tab.get("title", "Data Health")),
            "body": (
                f"Use {next_tab.get('title', 'Data Health')} to confirm the queue status for {ticker}, "
                f"then return to Stock Report Beta once the local {lane.lower()} step is complete."
                if not empty_shortlist
                else "Use Data Health after onboarding refresh to confirm the SEC stage and peer-mapping queues before deeper interpretation."
            ),
            "badges": [str(item) for item in next_tab.get("badges", [])][:2] or ["coverage", "read-only"],
        },
    ]


def overview_ready_blocked_cards(
    coverage: pd.DataFrame | None,
    ticker_unlock_ladder: pd.DataFrame | None,
    holdings: pd.DataFrame | None,
    limit: int = 3,
) -> list[dict[str, object]]:
    if coverage is None or coverage.empty or ticker_unlock_ladder is None or ticker_unlock_ladder.empty:
        return [
            {
                "kicker": "READY NOW VS BLOCKED",
                "title": "No readiness shortlist yet",
                "body": "Run make onboarding to refresh the onboarding outputs and separate names that are already usable from names still blocked by local data gaps.",
                "badges": ["read-only"],
                "command": "make onboarding",
            }
        ]

    coverage_frame = coverage.copy()
    ladder_frame = ticker_unlock_ladder.copy()
    coverage_frame["ticker"] = coverage_frame.get("ticker", pd.Series(dtype=object)).astype(str).str.upper().str.strip()
    ladder_frame["ticker"] = ladder_frame.get("ticker", pd.Series(dtype=object)).astype(str).str.upper().str.strip()
    merged = coverage_frame.merge(
        ladder_frame[["ticker", "current_unlock_stage", "next_unlock_goal"]],
        on="ticker",
        how="left",
    )

    holding_tickers: set[str] = set()
    if holdings is not None and not holdings.empty:
        lookup = {str(column).strip().lower(): str(column) for column in holdings.columns}
        ticker_col = lookup.get("ticker")
        if ticker_col:
            holding_tickers = set(holdings[ticker_col].dropna().astype(str).str.upper().str.strip())
    merged["is_holding"] = merged["ticker"].isin(holding_tickers)

    def _truthy(series_name: str) -> pd.Series:
        return merged.get(series_name, pd.Series(dtype=object)).astype(str).str.lower().isin({"true", "1", "yes"})

    merged["usable_for_momentum_bool"] = _truthy("usable_for_momentum")
    merged["dcf_ready_bool"] = _truthy("dcf_ready")
    merged["peer_ready_bool"] = _truthy("peer_ready")

    ready_rows = merged.loc[merged["usable_for_momentum_bool"]].copy()
    ready_rows["readiness_score"] = (
        ready_rows["dcf_ready_bool"].astype(int) * 2
        + ready_rows["peer_ready_bool"].astype(int) * 2
        + ready_rows["is_holding"].astype(int)
    )
    ready_rows = ready_rows.sort_values(
        ["readiness_score", "is_holding", "ticker"],
        ascending=[False, False, True],
    )
    blocked_rows = merged.loc[~merged["usable_for_momentum_bool"] | merged["current_unlock_stage"].astype(str).ne("ready")].copy()
    stage_rank = {"prices": 1, "fundamentals": 2, "peers": 3, "optional_context": 4, "ready": 5}
    blocked_rows["stage_rank"] = blocked_rows.get("current_unlock_stage", pd.Series(dtype=object)).map(stage_rank).fillna(99)
    blocked_rows = blocked_rows.sort_values(["stage_rank", "is_holding", "ticker"], ascending=[True, False, True])

    ready_names = ", ".join(ready_rows["ticker"].head(limit).tolist()) or "Not available"
    blocked_names = ", ".join(blocked_rows["ticker"].head(limit).tolist()) or "Not available"
    blocked_command = "make onboarding"
    if not blocked_rows.empty:
        blocked_command = unlock_stage_command(blocked_rows.iloc[0].get("current_unlock_stage"), "make onboarding")

    return [
        {
            "kicker": "READY NOW",
            "title": f"{len(ready_rows)} usable names",
            "body": (
                f"These names already support momentum-style local research. "
                f"Start with: {ready_names}."
            ),
            "badges": ["usable today", "local data"],
            "command": "make monthly",
        },
        {
            "kicker": "BLOCKED NOW",
            "title": f"{len(blocked_rows)} names still blocked",
            "body": (
                f"These names still need more local coverage before broader trust. "
                f"Start with: {blocked_names}."
            ),
            "badges": ["needs data", "prioritize"],
            "command": blocked_command,
        },
    ]


def overview_best_current_name_cards(
    coverage: pd.DataFrame | None,
    holdings: pd.DataFrame | None,
    limit: int = 3,
) -> list[dict[str, object]]:
    if coverage is None or coverage.empty:
        return [
            {
                "kicker": "READY NAME STATUS",
                "title": "No current ready names yet",
                "body": "Run make onboarding to refresh the onboarding outputs and surface which names are already usable with today’s local coverage.",
                "badges": ["read-only"],
                "command": "make onboarding",
            }
        ]

    coverage_frame = coverage.copy()
    coverage_frame["ticker"] = coverage_frame.get("ticker", pd.Series(dtype=object)).astype(str).str.upper().str.strip()
    holding_tickers: set[str] = set()
    if holdings is not None and not holdings.empty:
        lookup = {str(column).strip().lower(): str(column) for column in holdings.columns}
        ticker_col = lookup.get("ticker")
        if ticker_col:
            holding_tickers = set(holdings[ticker_col].dropna().astype(str).str.upper().str.strip())
    coverage_frame["is_holding"] = coverage_frame["ticker"].isin(holding_tickers)

    def _truthy(column: str) -> pd.Series:
        return coverage_frame.get(column, pd.Series(dtype=object)).astype(str).str.lower().isin({"true", "1", "yes"})

    coverage_frame["usable_for_momentum_bool"] = _truthy("usable_for_momentum")
    coverage_frame["dcf_ready_bool"] = _truthy("dcf_ready")
    coverage_frame["peer_ready_bool"] = _truthy("peer_ready")

    ready = coverage_frame.loc[coverage_frame["usable_for_momentum_bool"]].copy()
    if ready.empty:
        return [
            {
                "kicker": "READY NAME STATUS",
                "title": "No current ready names yet",
                "body": "Run make onboarding to refresh local coverage and unblock the next price-ready names before treating any name as ready.",
                "badges": ["needs prices"],
                "command": "make onboarding",
            }
        ]

    ready["score"] = (
        ready["dcf_ready_bool"].astype(int) * 2
        + ready["peer_ready_bool"].astype(int) * 2
        + ready["is_holding"].astype(int)
    )
    ready = ready.sort_values(["score", "is_holding", "ticker"], ascending=[False, False, True])

    cards: list[dict[str, object]] = []
    for _, row in ready.head(limit).iterrows():
        ticker = format_missing(row.get("ticker"), "Ticker")
        if bool(row.get("dcf_ready_bool")) or bool(row.get("peer_ready_bool")):
            next_surface = "Stock Report Beta"
            body = "This name already has enough local context for a deeper single-name review."
        else:
            next_surface = "Monthly Picks"
            body = "This name is usable for current momentum-style research even if valuation context is still partial."
        if bool(row.get("is_holding")):
            body += " It is also a current holding, so portfolio review context is immediately relevant."
        cards.append(
            {
                "kicker": ticker,
                "title": next_surface,
                "body": body,
                "badges": [
                    "holding" if bool(row.get("is_holding")) else "universe",
                    "dcf ready" if bool(row.get("dcf_ready_bool")) else "momentum ready",
                    "peer ready" if bool(row.get("peer_ready_bool")) else "partial context",
                ],
                "command": "make verify" if next_surface == "Stock Report Beta" else "make monthly",
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
                "body": "Run make pipeline to surface theme and sector ETF context from local price history.",
                "badges": ["read-only"],
                "command": "make pipeline",
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
                "command": "make pipeline",
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
            "command": "make pipeline",
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
                "command": "make pipeline",
            }
        )
    return cards


ONBOARDING_NOTICE_DEFAULTS: dict[str, str] = {
    "coverage_wizard": "Run make onboarding to refresh the local data coverage wizard and see the next best coverage unlocks.",
    "command_bundles": "Run make onboarding to refresh the onboarding outputs and generate holdings-first local command bundles.",
    "command_bundle_details": "Run make onboarding to refresh the onboarding outputs and generate ticker-level bundle detail rows.",
    "command_bundle_runbook": "Run make onboarding to refresh the onboarding outputs and generate ordered bundle runbook rows.",
    "price_worklist": "Run make onboarding to refresh the onboarding outputs and see exact local price-history gaps plus the safe manual-import path.",
    "fundamentals_peer_worklist": "Run make onboarding to refresh the onboarding outputs and see which tickers still need SEC fundamentals or manual peer mappings.",
    "optional_context_worklist": "Run make onboarding to refresh the onboarding outputs and see which tickers still have optional earnings or analyst-estimate gaps.",
    "ticker_unlock_ladder": "Run make onboarding to refresh the onboarding outputs and see the next per-ticker local data unlock stage.",
    "unlock_priority_summary": "Run make onboarding to refresh the onboarding outputs and see grouped unlock priorities by holdings, theme, and sector ETF.",
}


def onboarding_notice_copy(kind: str, message: str | None = None) -> tuple[str, str]:
    return (message or ONBOARDING_NOTICE_DEFAULTS[kind], "make onboarding")


ARTIFACT_NOTICE_DEFAULTS: dict[str, tuple[str, str]] = {
    "action_queue": (
        "Run make action-queue to refresh the research action queue and surface priority price, fundamentals, peer, and onboarding tasks.",
        "make action-queue",
    ),
    "research_health": (
        "Research health outputs are not available yet. Run make research-health to refresh those diagnostics, or make verify for the broader local validation pass.",
        "make research-health",
    ),
    "data_source_status": (
        "Run make data-sources to refresh the local source registry so this tab can show what is available, partial, manual-only, or missing.",
        "make data-sources",
    ),
    "data_source_rows": (
        "Run make data-sources to refresh the local source registry and inspect dataset availability plus fallback actions.",
        "make data-sources",
    ),
}


def artifact_notice_copy(kind: str, message: str | None = None) -> tuple[str, str]:
    default_body, command = ARTIFACT_NOTICE_DEFAULTS[kind]
    return (message or default_body, command)


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
            "command": (
                "make runbook-prices-broader"
                if (not total_tickers or missing_prices or parse_or_source_errors)
                else "make price-status TOP_N=10"
            ),
        },
        {
            "kicker": "SPY CONTEXT",
            "title": strongest_theme,
            "body": benchmark_body,
            "badges": ["benchmark lens", "research only"],
            "command": "make pipeline",
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
            reason = compact_reason(row.get("Reason"), max_sentences=1, max_chars=160)
            has_reason = bool(reason and reason != "Not available")
            lower_reason = reason.lower() if has_reason else ""
            body = (
                "Repo-native next step from the current read-only project status snapshot."
                if command
                else "No explicit command was available from project status."
            )
            badges = ["command", "research only"]
            lowered = command.lower()
            if "focus-" in lowered:
                body = reason if has_reason else "Use the current single-name shortcut first to unblock the highest-leverage local data gap."
                badges = ["single name", "command"]
            elif "imports-" in lowered:
                if has_reason and "make imports-preview" in lower_reason and "make imports-apply" in lower_reason:
                    body = reason
                else:
                    body = "Run make imports-validate, then make imports-preview, then make imports-apply so staged local data is reviewed before apply."
                badges = ["staged flow", "command"]
            elif lowered == "make price-validate":
                if has_reason and "make price-preview" in lower_reason and "make price-apply" in lower_reason:
                    body = reason
                else:
                    body = "Run make price-validate, then make price-preview, then make price-apply so staged price rows are reviewed before apply."
                badges = ["staged flow", "command"]
            elif "bundle-" in lowered:
                body = reason if has_reason else "Use the highest-leverage local bundle first so price, fundamentals, or peer follow-through stays coordinated."
                badges = ["bundle first", "command"]
            elif "runbook-" in lowered:
                body = reason if has_reason else "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
                badges = ["runbook", "command"]
            elif "onboarding" in lowered:
                body = "Refresh local data coverage, onboarding outputs, and action guidance before broader research work."
                badges = ["data moat", "command"]
            elif "verify" in lowered:
                body = "Run deterministic local verification before trusting the current dashboard and CSV outputs."
                badges = ["verification", "command"]
            elif "dashboard-smoke" in lowered:
                body = "Smoke-check the Streamlit surface after local outputs and operator artifacts are refreshed."
                badges = ["ui check", "command"]
            elif "dashboard" in lowered:
                body = "Open the Streamlit surface after the smoke check confirms the local dashboard still boots cleanly."
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
                    "body": compact_reason(signal.get("body"), max_sentences=2, max_chars=240),
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
                "title": "make onboarding",
                "body": "Run make onboarding to refresh local coverage, onboarding outputs, and operator guidance before broader research work.",
                "badges": ["data moat", "command"],
                "command": "make onboarding",
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


def overview_command_bundle_cards(bundle_frame: pd.DataFrame | None, limit: int = 2) -> list[dict[str, object]]:
    if bundle_frame is None or bundle_frame.empty:
        return [
            {
                "kicker": "DATA BUNDLE",
                "title": "No command bundles yet",
                "body": "Run make onboarding to refresh the onboarding outputs and surface holdings-first local bundles for prices, SEC staging, and peer mapping.",
                "badges": ["read-only", "data moat"],
                "command": "make onboarding",
            }
        ]

    ordered = bundle_frame.copy()
    if "ticker_count" in ordered.columns:
        ordered["ticker_count"] = pd.to_numeric(ordered["ticker_count"], errors="coerce").fillna(0)

    cards: list[dict[str, object]] = []
    for _, row in ordered.head(limit).iterrows():
        command = preferred_bundle_command(row, "")
        lane = format_missing(row.get("lane"), "bundle").replace("_", " ")
        scope = format_missing(row.get("scope"), "scope").replace("_", " ")
        goal_summary = compact_reason(row.get("goal_summary"), max_sentences=1, max_chars=110)
        lane_summary = command_family_fallback(command, review_path_fallback(row.get("lane")))
        if "runbook-" in command.lower():
            lane_summary = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
        target_file = format_missing(row.get("target_file"), "")
        staged_summary = ""
        if target_file in {"data/imports/fundamentals.csv", "data/imports/peers.csv", "data/imports/prices.csv"}:
            staged_summary = compact_reason(row.get("safe_next_step"), max_sentences=1, max_chars=150)
            if target_file == "data/imports/fundamentals.csv":
                default_staged_summary = "Run make imports-validate, make imports-preview, and make imports-apply for the staged fundamentals import."
            elif target_file == "data/imports/peers.csv":
                default_staged_summary = "Run make imports-validate, make imports-preview, and make imports-apply for the staged peer import."
            else:
                default_staged_summary = "Run make price-validate, make price-preview, and make price-apply for the staged price import."
            if staged_summary == "Not available":
                staged_summary = default_staged_summary
            elif target_file == "data/imports/prices.csv" and (
                "make price-validate" not in staged_summary
                or "make price-preview" not in staged_summary
                or "make price-apply" not in staged_summary
            ):
                staged_summary = default_staged_summary
        body_summary = (
            goal_summary
            if goal_summary != "Not available"
            else compact_reason(row.get("why_it_matters") or staged_summary or lane_summary, max_sentences=1, max_chars=150)
        )
        target_history_rows = _target_rows_hint(row.get("target_history_rows"))
        suggested_start_date = format_missing(row.get("suggested_start_date"), "")
        hints: list[str] = []
        if target_history_rows not in {"", "-"}:
            hints.append(f"{target_history_rows} target rows")
        if suggested_start_date not in {"", "-"}:
            hints.append(f"start by {suggested_start_date}")
        cards.append(
            {
                "kicker": f"{lane.upper()} BUNDLE",
                "title": format_missing(row.get("bundle_name"), "Local bundle"),
                "body": (
                    f"{format_missing(row.get('tickers'), 'No tickers')}: "
                    f"{body_summary}"
                    f"{' (' + '; '.join(hints) + ')' if hints else ''}"
                ),
                "badges": [scope, f"{format_value(row.get('ticker_count'), fallback='0')} tickers"],
                "command": command,
            }
        )
    return cards


def overview_bundle_handoff_cards(
    bundle_frame: pd.DataFrame | None,
    bundle_detail_frame: pd.DataFrame | None,
    bundle_runbook_frame: pd.DataFrame | None = None,
) -> list[dict[str, object]]:
    if bundle_frame is None or bundle_frame.empty:
        return [
            {
                "kicker": "BUNDLE HANDOFF",
                "title": "No bundle guidance yet",
                "body": "Run make onboarding first, then use Data Health to inspect the current local bundle workflow.",
                "badges": ["read-only", "data moat"],
                "command": "make onboarding",
            }
        ]

    top_bundle = bundle_frame.iloc[0]
    bundle_name = format_missing(top_bundle.get("bundle_name"), "Local bundle")
    primary_command = preferred_bundle_command(top_bundle, "")
    follow_up_command = normalize_operator_command(format_missing(top_bundle.get("follow_up_command"), ""))
    goal_summary = compact_reason(top_bundle.get("goal_summary"), max_sentences=1, max_chars=120)
    target_history_rows = _target_rows_hint(top_bundle.get("target_history_rows"))
    suggested_start_date = format_missing(top_bundle.get("suggested_start_date"), "")
    hint_text = ""
    if target_history_rows not in {"", "-"} or suggested_start_date not in {"", "-"}:
        parts = []
        if target_history_rows not in {"", "-"}:
            parts.append(f"{target_history_rows} target rows")
        if suggested_start_date not in {"", "-"}:
            parts.append(f"start by {suggested_start_date}")
        hint_text = f" ({'; '.join(parts)})"
    lane = format_missing(top_bundle.get("lane"), "bundle").replace("_", " ")
    ticker_text = format_missing(top_bundle.get("tickers"), "No tickers")
    target_file = format_missing(top_bundle.get("target_file"), "")
    staged_summary = ""
    if target_file in {"data/imports/fundamentals.csv", "data/imports/peers.csv", "data/imports/prices.csv"}:
        staged_summary = compact_reason(top_bundle.get("safe_next_step"), max_sentences=1, max_chars=150)
        if target_file == "data/imports/fundamentals.csv":
            default_staged_summary = "Run make imports-validate, make imports-preview, and make imports-apply for the staged fundamentals import."
        elif target_file == "data/imports/peers.csv":
            default_staged_summary = "Run make imports-validate, make imports-preview, and make imports-apply for the staged peer import."
        else:
            default_staged_summary = "Run make price-validate, make price-preview, and make price-apply for the staged price import."
        if staged_summary == "Not available":
            staged_summary = default_staged_summary
        elif target_file == "data/imports/prices.csv" and (
            "make price-validate" not in staged_summary
            or "make price-preview" not in staged_summary
            or "make price-apply" not in staged_summary
        ):
            staged_summary = default_staged_summary
    bundle_summary = (
        goal_summary
        if goal_summary not in {"", "Not available"}
        else compact_reason(
            top_bundle.get("why_it_matters")
            or staged_summary
            or command_family_fallback(primary_command, review_path_fallback(top_bundle.get("lane"))),
            max_sentences=1,
            max_chars=150,
        )
    )
    refresh_command = "make onboarding"
    refresh_step_label = "Refresh onboarding outputs"

    first_ticker = "Not available"
    if bundle_detail_frame is not None and not bundle_detail_frame.empty:
        details = bundle_detail_frame.copy()
        details["bundle_name"] = details.get("bundle_name", pd.Series(dtype=str)).astype(str)
        matches = details.loc[details["bundle_name"].eq(str(top_bundle.get("bundle_name", "")))]
        if not matches.empty and "ticker" in matches.columns:
            first_ticker = format_missing(matches.iloc[0].get("ticker"), "Not available")

    if bundle_runbook_frame is not None and not bundle_runbook_frame.empty:
        runbook = bundle_runbook_frame.copy()
        runbook["bundle_name"] = runbook.get("bundle_name", pd.Series(dtype=str)).astype(str)
        matches = runbook.loc[runbook["bundle_name"].eq(str(top_bundle.get("bundle_name", "")))]
        if not matches.empty:
            if "step_order" in matches.columns:
                matches["step_order"] = pd.to_numeric(matches["step_order"], errors="coerce")
                matches = matches.sort_values("step_order")
            if not follow_up_command:
                runbook_commands = [
                    normalize_operator_command(format_missing(row.get("command"), ""))
                    for _, row in matches.iterrows()
                    if format_missing(row.get("command"), "")
                ]
                if runbook_commands:
                    follow_up_command = next(
                        (command for command in runbook_commands if command != primary_command),
                        runbook_commands[0],
                    )
            refresh_labels = {"refresh status outputs", "refresh onboarding outputs"}
            refresh_matches = matches.loc[
                matches.get("step_label", pd.Series(dtype=str)).astype(str).str.lower().isin(refresh_labels)
            ]
            target_row = refresh_matches.iloc[0] if not refresh_matches.empty else matches.iloc[-1]
            refresh_command = normalize_operator_command(format_missing(target_row.get("command"), refresh_command))
            if refresh_command == "make status":
                refresh_command = "make status-check TOP_N=5"
            refresh_step_label = format_missing(target_row.get("step_label"), refresh_step_label)

    if not follow_up_command:
        if target_file in {"data/imports/fundamentals.csv", "data/imports/peers.csv"}:
            follow_up_command = "make imports-validate"
        elif target_file == "data/imports/prices.csv":
            follow_up_command = "make price-validate"

    monthly_refresh_context = " ".join(
        part
        for part in [
            goal_summary,
            compact_reason(top_bundle.get("why_it_matters"), max_sentences=1, max_chars=150),
            staged_summary,
        ]
        if part and part != "Not available"
    ).lower()
    follow_through_summary = compact_reason(top_bundle.get("safe_next_step"), max_sentences=2, max_chars=220)
    if staged_summary not in {"", "Not available"} and (
        follow_through_summary in {"", "Not available"}
        or (
            target_file == "data/imports/prices.csv"
            and (
                "make price-validate" not in follow_through_summary
                or "make price-preview" not in follow_through_summary
                or "make price-apply" not in follow_through_summary
            )
        )
    ):
        follow_through_summary = staged_summary
    if (
        str(top_bundle.get("lane", "")).strip().lower() == "prices"
        and "monthly picks" in monthly_refresh_context
        and refresh_command in {"make status", "make status-check TOP_N=5", "make onboarding"}
    ):
        refresh_command = "make monthly"
        refresh_step_label = "Refresh monthly context"

    return [
        {
            "kicker": f"{lane.upper()} HANDOFF",
            "title": bundle_name,
            "body": (
                f"{bundle_summary}{hint_text}. " if bundle_summary not in {"", "Not available"} else ""
            ) + f"Start with {primary_command} for {ticker_text}. This is the highest-leverage local bundle right now.",
            "badges": ["bundle first", "research only"],
            "command": primary_command,
        },
        {
            "kicker": "FOLLOW-THROUGH",
            "title": follow_up_command or "Data Health",
            "body": (
                (
                    f"After the primary command, use {follow_up_command} and check {first_ticker} first. "
                    f"{follow_through_summary}"
                )
                if follow_up_command and follow_through_summary not in {"", "Not available"}
                else f"After the primary command, use {follow_up_command or 'Data Health'} and check {first_ticker} first "
                "to confirm the bundle moved the expected local blocker."
            ),
            "badges": ["next step", "read-only"],
            "command": follow_up_command,
        },
        {
            "kicker": "REFRESH",
            "title": refresh_step_label,
            "body": (
                f"After the follow-through step, run {refresh_command} and reopen Data Health or Overview to confirm "
                f"that {first_ticker} moved as expected."
            ),
            "badges": ["confirm", "read-only"],
            "command": refresh_command,
        },
    ]


def overview_bundle_runbook_cards(runbook_frame: pd.DataFrame | None, limit: int = 3) -> list[dict[str, object]]:
    if runbook_frame is None or runbook_frame.empty:
        return [
            {
                "kicker": "BUNDLE RUNBOOK",
                "title": "No bundle runbook yet",
                "body": "Run make onboarding to refresh the onboarding outputs and surface ordered prices, SEC fundamentals, and peer-mapping runbook steps.",
                "badges": ["read-only", "data moat"],
                "command": "make onboarding",
            }
        ]

    ordered = runbook_frame.copy()
    ordered["lane"] = ordered.get("lane", pd.Series(dtype=str)).astype(str)
    if "step_order" in ordered.columns:
        ordered["step_order"] = pd.to_numeric(ordered["step_order"], errors="coerce")
        ordered = ordered.sort_values(["lane", "step_order", "bundle_name"], kind="stable")

    cards: list[dict[str, object]] = []
    for lane in ("prices", "fundamentals", "peers"):
        lane_rows = ordered.loc[ordered["lane"].eq(lane)]
        if lane_rows.empty:
            continue
        bundle_name = format_missing(lane_rows.iloc[0].get("bundle_name"), "Local bundle")
        tickers = format_missing(lane_rows.iloc[0].get("tickers"), "No tickers")
        goal_summary = compact_reason(lane_rows.iloc[0].get("goal_summary"), max_sentences=1, max_chars=110)
        target_file = format_missing(lane_rows.iloc[0].get("target_file"), "")
        staged_summary = ""
        default_staged_summary = ""
        if target_file in {"data/imports/fundamentals.csv", "data/imports/peers.csv", "data/imports/prices.csv"}:
            staged_summary = compact_reason(lane_rows.iloc[0].get("safe_next_step"), max_sentences=1, max_chars=150)
            if target_file == "data/imports/fundamentals.csv":
                default_staged_summary = "Run make imports-validate, make imports-preview, and make imports-apply for the staged fundamentals import."
            elif target_file == "data/imports/peers.csv":
                default_staged_summary = "Run make imports-validate, make imports-preview, and make imports-apply for the staged peer import."
            else:
                default_staged_summary = "Run make price-validate, make price-preview, and make price-apply for the staged price import."
            if staged_summary == "Not available":
                staged_summary = default_staged_summary
            elif target_file == "data/imports/prices.csv" and (
                "make price-validate" not in staged_summary
                or "make price-preview" not in staged_summary
                or "make price-apply" not in staged_summary
            ):
                staged_summary = default_staged_summary
        target_history_rows = _target_rows_hint(lane_rows.iloc[0].get("target_history_rows"))
        suggested_start_date = format_missing(lane_rows.iloc[0].get("suggested_start_date"), "")
        hint_text = ""
        if target_history_rows not in {"", "-"} or suggested_start_date not in {"", "-"}:
            parts = []
            if target_history_rows not in {"", "-"}:
                parts.append(f"{target_history_rows} target rows")
            if suggested_start_date not in {"", "-"}:
                parts.append(f"start by {suggested_start_date}")
            hint_text = f" ({'; '.join(parts)})"
        steps: list[str] = []
        first_command = ""
        fallback_first_command = ""
        if target_file == "data/imports/fundamentals.csv":
            fallback_first_command = "make imports-validate"
        elif target_file == "data/imports/peers.csv":
            fallback_first_command = "make imports-validate"
        elif target_file == "data/imports/prices.csv":
            fallback_first_command = "make price-validate"
        for _, row in lane_rows.head(2).iterrows():
            step_label = format_missing(row.get("step_label"), "Step")
            command = format_missing(row.get("command"), "")
            normalized_command = normalize_operator_command(command)
            step_command = normalized_command or command
            if not step_command and fallback_first_command and not first_command:
                step_command = fallback_first_command
            if step_command:
                first_command = first_command or step_command
                steps.append(f"{step_label}: {step_command}")
        surfaced_command = first_command or fallback_first_command
        lane_summary = command_family_fallback(surfaced_command, review_path_fallback(lane))
        if "runbook-" in surfaced_command.lower():
            lane_summary = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
        body_summary = (
            goal_summary
            if goal_summary not in {"", "Not available"}
            else compact_reason(lane_rows.iloc[0].get("why_it_matters") or staged_summary or lane_summary, max_sentences=1, max_chars=150)
        )
        cards.append(
            {
                "kicker": f"{lane.upper()} LANE",
                "title": bundle_name,
                "body": (f"{body_summary}{hint_text}. " if body_summary not in {"", "Not available"} else "") + f"{tickers}. " + " | ".join(steps),
                "badges": [
                    format_missing(lane_rows.iloc[0].get("scope"), "scope").replace("_", " "),
                    "runbook",
                ],
                "command": first_command or fallback_first_command,
            }
        )
        if len(cards) >= limit:
            break

    return cards or [
        {
            "kicker": "BUNDLE RUNBOOK",
            "title": "No bundle runbook yet",
            "body": "Run make onboarding to refresh the onboarding outputs and surface ordered prices, SEC fundamentals, and peer-mapping runbook steps.",
            "badges": ["read-only", "data moat"],
            "command": "make onboarding",
        }
    ]


def overview_workflow_path_cards(
    project_status_payload: dict[str, Any] | None,
    action_queue: pd.DataFrame | None,
) -> list[dict[str, object]]:
    command_rows = project_status_command_rows(project_status_payload)
    top_signal: list[dict[str, object]] = []
    structured_rows = bool(project_status_payload and project_status_payload.get("recommended_next_command_rows"))
    if structured_rows and command_rows:
        cards: list[dict[str, object]] = []
        for index, row in enumerate(command_rows[:3], start=1):
            command = format_missing(row.get("Command"), "make status-check TOP_N=5")
            reason = compact_reason(row.get("Reason"), max_sentences=2, max_chars=220)
            has_reason = bool(reason and reason != "Not available")
            lower_reason = reason.lower() if has_reason else ""
            body = reason or "Repo-native next step from the current local workflow snapshot."
            badges = ["today", "data first"] if index == 1 else ["workflow", "command"]
            lowered = command.lower()
            if "verify" in lowered:
                badges = ["verify", "safe"]
                body = reason if has_reason else "Run deterministic verification so the current CSV outputs and dashboard state are trustworthy."
            elif "dashboard-smoke" in lowered:
                badges = ["ui", "workflow"]
                body = reason if has_reason else "Open or smoke-check the dashboard after the data and verification steps are complete."
            elif "focus-" in lowered:
                badges = ["today", "single name"] if index == 1 else ["single name", "workflow"]
                body = reason if has_reason else "Use the current single-name shortcut first to unblock the highest-leverage local data gap."
            elif "bundle-" in lowered:
                badges = ["today", "bundle first"] if index == 1 else ["bundle first", "workflow"]
                body = reason if has_reason else "Use the highest-leverage local bundle first so price, fundamentals, or peer follow-through stays coordinated."
            elif "imports-" in lowered:
                badges = ["today", "staged flow"] if index == 1 else ["staged flow", "workflow"]
                if has_reason and "make imports-preview" in lower_reason and "make imports-apply" in lower_reason:
                    body = reason
                else:
                    body = "Run make imports-validate, then make imports-preview, then make imports-apply so staged local data is reviewed before apply."
            elif lowered == "make price-validate":
                badges = ["today", "staged flow"] if index == 1 else ["staged flow", "workflow"]
                if has_reason and "make price-preview" in lower_reason and "make price-apply" in lower_reason:
                    body = reason
                else:
                    body = "Run make price-validate, then make price-preview, then make price-apply so staged price rows are reviewed before apply."
            elif "runbook-" in lowered:
                badges = ["today", "staged flow"] if index == 1 else ["staged flow", "workflow"]
                body = reason if has_reason else "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
            cards.append(
                {
                    "kicker": f"STEP {index}",
                    "title": command,
                    "body": body,
                    "badges": badges,
                    "command": command,
                }
            )
        if cards:
            return cards

    commands = [row.get("Command", "") for row in command_rows]
    first_command = "make status-check TOP_N=5"
    if action_queue is not None and not action_queue.empty:
        top_signal = top_priority_signals(action_queue, limit=1)
        if top_signal:
            candidate = format_missing(top_signal[0].get("command"), "")
            if candidate and candidate != "Not available":
                first_command = candidate
    elif commands:
        first_command = str(commands[0])

    second_command = "make verify"
    third_command = "make dashboard-smoke"
    if any("dashboard-smoke" in str(command) for command in commands):
        third_command = "make dashboard-smoke"

    first_body = "Start with the highest-value local data or workflow blocker before interpreting downstream research outputs."
    first_badges = ["today", "data first"]
    lowered_first = first_command.lower()
    if "focus-" in lowered_first:
        first_body = "Use the current single-name shortcut first to unblock the highest-leverage local data gap."
        first_badges = ["today", "single name"]
    elif "bundle-" in lowered_first:
        first_body = "Use the highest-leverage local bundle first so price, fundamentals, or peer follow-through stays coordinated."
        first_badges = ["today", "bundle first"]
    elif "imports-" in lowered_first:
        first_body = "Run make imports-validate, then make imports-preview, then make imports-apply so staged local data is reviewed before apply."
        first_badges = ["today", "staged flow"]
    elif "runbook-" in lowered_first:
        first_body = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
        first_badges = ["today", "staged flow"]
    if top_signal:
        signal_body = compact_reason(top_signal[0].get("body"), max_sentences=2, max_chars=240)
        if signal_body and signal_body != "Not available":
            first_body = signal_body

    return [
        {
            "kicker": "STEP 1",
            "title": first_command,
            "body": first_body,
            "badges": first_badges,
            "command": first_command,
        },
        {
            "kicker": "STEP 2",
            "title": second_command,
            "body": "Run deterministic verification so the current CSV outputs and dashboard state are trustworthy.",
            "badges": ["verify", "safe"],
            "command": second_command,
        },
        {
            "kicker": "STEP 3",
            "title": third_command,
            "body": "Open or smoke-check the dashboard after the data and verification steps are complete.",
            "badges": ["ui", "workflow"],
            "command": third_command,
        },
    ]


def overview_workflow_reason_card(
    project_status_payload: dict[str, Any] | None,
    action_queue: pd.DataFrame | None,
) -> dict[str, object]:
    first_card = overview_workflow_path_cards(project_status_payload, action_queue)[0]
    first_command = first_card["title"]
    reason = f"Run {first_command} first to refresh local blocker triage before verification and UI review."
    badges = ["why now", "research only"]

    if action_queue is not None and not action_queue.empty:
        top_row = action_queue.sort_values(["priority", "ticker", "action_type"], na_position="last").iloc[0]
        dataset = format_missing(top_row.get("action_type"), "data")
        ticker = format_missing(top_row.get("ticker"), "")
        signal = top_priority_signals(action_queue, limit=1)
        signal_command = format_missing(signal[0].get("command"), "") if signal else preferred_row_command(
            top_row,
            ticker_focus_command(top_row.get("action_type"), top_row.get("ticker"), "make action-queue-check TOP_N=10"),
        )
        row_reason = compact_reason(top_row.get("reason"), max_sentences=1, max_chars=170)
        signal_reason = compact_reason(signal[0].get("body"), max_sentences=2, max_chars=240) if signal else row_reason
        if not signal_reason or signal_reason == "Not available":
            signal_reason = command_family_fallback(signal_command, review_path_fallback(top_row.get("action_type")))
        if ticker and ticker != "Not available":
            reason = f"{dataset.title()} pressure is currently led by {ticker}. {signal_reason}"
        else:
            reason = f"{dataset.title()} pressure is currently the top local blocker. {signal_reason}"
        badges = [f"P{format_missing(top_row.get('priority'), '-')}", dataset]
    elif project_status_payload:
        summary = project_status_payload.get("summary", {})
        data_gaps = int(summary.get("data_gaps") or 0)
        critical_actions = int(summary.get("critical_actions") or 0)
        if first_command == "make status":
            first_command = "make status-check TOP_N=5"
        if project_status_payload.get("recommended_next_command_rows") and critical_actions == 0 and data_gaps == 0:
            structured_reason = compact_reason(first_card.get("body"), max_sentences=2, max_chars=240)
            if structured_reason and structured_reason != "Not available":
                reason = structured_reason
                badges = [str(item) for item in first_card.get("badges", [])][:2] or ["workflow", "command"]
            else:
                reason = (
                    f"{critical_actions} critical actions and {data_gaps} visible data gaps are in the current read-only status snapshot, "
                    "so the workflow starts with local coverage before interpretation."
                )
                badges = ["status snapshot", "data first"]
        else:
            reason = (
                f"{critical_actions} critical actions and {data_gaps} visible data gaps are in the current read-only status snapshot, "
                "so the workflow starts with local coverage before interpretation."
            )
            badges = ["status snapshot", "data first"]

    return {
        "kicker": "WHY THIS STEP NOW",
        "title": str(first_command),
        "body": reason,
        "badges": badges,
        "command": str(first_command),
    }


def overview_handoff_cards() -> list[dict[str, object]]:
    return [
        {
            "kicker": "NEXT DEEPER TAB",
            "title": "Data Health",
            "body": "Use this when prices, fundamentals, peers, or staged imports are still blocking the local research workflow. It is the best place to inspect blockers before interpreting deeper outputs.",
            "badges": ["coverage", "read-only"],
            "command": "make onboarding",
        },
        {
            "kicker": "NEXT DEEPER TAB",
            "title": "Stock Report Beta",
            "body": "Use this for a single-name deep dive after local coverage is good enough to support price, valuation, peer, and missing-assumption context in one place.",
            "badges": ["single name", "deep dive"],
            "command": "make verify",
        },
        {
            "kicker": "NEXT DEEPER TAB",
            "title": "Monthly Picks",
            "body": "Use this after core coverage is in place to compare the current local candidate set, visible data gaps, and track-record readiness without turning the workflow into trade advice.",
            "badges": ["candidate view", "research only"],
            "command": "make monthly",
        },
    ]


def overview_best_local_research_path_cards(
    coverage: pd.DataFrame | None,
    holdings: pd.DataFrame | None,
    project_status_payload: dict[str, Any] | None,
    action_queue: pd.DataFrame | None,
) -> list[dict[str, object]]:
    best_name = overview_best_current_name_cards(coverage, holdings, limit=1)[0]
    ready_cards = overview_ready_name_handoff_cards(coverage, holdings, project_status_payload, action_queue)
    next_command = overview_next_command_cards(project_status_payload, action_queue, limit=1)[0]
    next_tab = overview_handoff_cards()[0]

    best_title = str(best_name.get("title", ""))
    if best_title == "Stock Report Beta":
        next_tab = next((card for card in overview_handoff_cards() if card.get("title") == "Stock Report Beta"), next_tab)
    elif best_title == "Monthly Picks":
        next_tab = next((card for card in overview_handoff_cards() if card.get("title") == "Monthly Picks"), next_tab)

    first_name = format_missing(best_name.get("kicker"), "Not available")
    if first_name in {"BEST CURRENT NAMES", "READY NAME STATUS"}:
        first_name = format_missing(best_name.get("title"), first_name)
    command_text = format_missing(next_command.get("title"), "make status")
    tab_text = format_missing(next_tab.get("title"), "Data Health")
    ready_command_text = format_missing(ready_cards[1].get("title"), "")
    if command_text == "make help" and ready_command_text and ready_command_text != "make help":
        command_text = ready_command_text
    if tab_text == "Stock Report Beta" and command_text in {"make help", "make status", "make status-check TOP_N=5", "make onboarding"} and ready_command_text:
        command_text = ready_command_text
    if tab_text == "Monthly Picks" and command_text in {"make help", "make status", "make status-check TOP_N=5", "make onboarding"}:
        command_text = "make monthly"
    if command_text == ready_command_text:
        command_reason = compact_reason(ready_cards[1].get("command_reason"), max_sentences=2, max_chars=220)
    else:
        command_reason = compact_reason(next_command.get("body"), max_sentences=2, max_chars=220)
    queue_signal = top_priority_signals(action_queue, limit=1) if action_queue is not None else []
    queue_reason = compact_reason(queue_signal[0].get("body"), max_sentences=2, max_chars=220) if queue_signal else ""
    generic_reason_markers = (
        "repo-native next step from the current read-only project status snapshot",
        "refresh local data coverage, onboarding outputs, and action guidance before broader research work",
    )
    if queue_reason and any(marker in command_reason.lower() for marker in generic_reason_markers):
        command_reason = queue_reason
    if not command_reason or command_reason == "Not available":
        command_reason = (
            f"Run {command_text} next to improve or confirm the current local research path "
            "before trusting broader downstream interpretation."
        )

    return [
        {
            "kicker": "BEST CURRENT NAME",
            "title": first_name,
            "body": (
                (
                    f"No locally ready name yet. Use {tab_text} next to clear the highest-leverage blocker "
                    "before treating any name as ready."
                )
                if first_name == "No current ready names yet"
                else (
                    f"Start with {first_name} because it is the clearest locally usable name right now. "
                    f"Use {best_title} next for the most appropriate research surface."
                )
            ),
            "badges": [str(item) for item in best_name.get("badges", [])][:2] or ["local coverage"],
            "command": command_text,
        },
        {
            "kicker": "NEXT COMMAND",
            "title": command_text,
            "body": command_reason,
            "badges": [str(item) for item in next_command.get("badges", [])][:2] or ["command", "read-only"],
            "command": command_text,
        },
        {
            "kicker": "NEXT TAB",
            "title": tab_text,
            "body": (
                f"Open {tab_text} after the command step so the next read matches the current local "
                "coverage and workflow state."
            ),
            "badges": [str(item) for item in next_tab.get("badges", [])][:2] or ["guided", "read-only"],
        },
    ]


def overview_ready_name_handoff_cards(
    coverage: pd.DataFrame | None,
    holdings: pd.DataFrame | None,
    project_status_payload: dict[str, Any] | None,
    action_queue: pd.DataFrame | None,
) -> list[dict[str, object]]:
    best_name = overview_best_current_name_cards(coverage, holdings, limit=1)[0]
    next_command = overview_next_command_cards(project_status_payload, action_queue, limit=3)

    surface = str(best_name.get("title", ""))
    if surface == "Stock Report Beta":
        command_text = "make verify"
        badges = ["verification", "ready flow"]
        body = (
            "Run deterministic verification first, then move into Stock Report Beta for the deeper single-name read."
        )
        for row in next_command:
            candidate = str(row.get("title", ""))
            if "verify" in candidate.lower():
                command_text = candidate
                break
    elif surface == "Monthly Picks":
        fallback = next_command[0] if next_command else {"title": "make status", "badges": ["data moat", "command"]}
        command_text = format_missing(fallback.get("title"), "make status")
        if command_text in {"make help", "make status", "make status-check TOP_N=5", "make onboarding"}:
            command_text = "make monthly"
        badges = [str(item) for item in fallback.get("badges", [])][:2] or ["data moat", "command"]
        body = (
            f"Run {command_text} first if this name is still momentum-ready but lighter on deeper valuation or peer context, "
            "then review it in Monthly Picks."
        )
    elif surface == "No current ready names yet":
        command_text = "make onboarding"
        badges = ["data moat", "command"]
        body = "Run make onboarding to refresh local coverage and onboarding outputs before treating any name as ready."
    else:
        fallback = next_command[0] if next_command else {"title": "make help", "badges": ["safe default"]}
        command_text = format_missing(fallback.get("title"), "make help")
        badges = [str(item) for item in fallback.get("badges", [])][:2] or ["safe default"]
        body = "Use the local command map or onboarding flow before treating any name as ready."

    next_tab = next((card for card in overview_handoff_cards() if card.get("title") == surface), overview_handoff_cards()[0])
    ticker = format_missing(best_name.get("kicker"), "Not available")
    if ticker in {"BEST CURRENT NAMES", "READY NAME STATUS"}:
        ticker = format_missing(best_name.get("title"), "Not available")

    return [
        {
            "kicker": "READY NAME",
            "title": ticker,
            "body": (
                (
                    f"No locally ready name yet. Use {str(next_tab.get('title', 'Data Health'))} next "
                    "to clear blockers before treating any name as ready."
                )
                if ticker == "No current ready names yet"
                else f"{ticker} is the strongest currently usable local name and is best reviewed next through {surface}."
            ),
            "badges": [str(item) for item in best_name.get("badges", [])][:2] or ["local coverage"],
            "command": command_text,
        },
        {
            "kicker": "READY NAME COMMAND",
            "title": command_text,
            "body": body,
            "badges": badges,
            "command": command_text,
            "command_reason": body,
        },
        {
            "kicker": "READY NAME TAB",
            "title": str(next_tab.get("title", "Data Health")),
            "body": (
                (
                    f"Open {next_tab.get('title', 'Data Health')} after the command step so the next read "
                    "matches the current local workflow state."
                )
                if ticker == "No current ready names yet"
                else (
                    f"Open {next_tab.get('title', 'Data Health')} after the command step so the next read for {ticker} "
                    "matches the current local workflow state."
                )
            ),
            "badges": [str(item) for item in next_tab.get("badges", [])][:2] or ["guided", "read-only"],
        },
    ]


def overview_current_top_surfaces_cards(
    coverage: pd.DataFrame | None,
    holdings: pd.DataFrame | None,
    sec_stage_queue: pd.DataFrame | None,
    peer_mapping_queue: pd.DataFrame | None,
    project_status_payload: dict[str, Any] | None,
    action_queue: pd.DataFrame | None,
) -> list[dict[str, object]]:
    ready_cards = overview_ready_name_handoff_cards(coverage, holdings, project_status_payload, action_queue)
    deep_cards = overview_deep_research_handoff_cards(
        holdings,
        sec_stage_queue,
        peer_mapping_queue,
        project_status_payload,
        action_queue,
    )
    command_cards = overview_next_command_cards(project_status_payload, action_queue, limit=1)

    ready_name = format_missing(ready_cards[0].get("title"), "Not available")
    blocked_name = format_missing(deep_cards[0].get("title"), "Not available")
    ready_surface_command = format_missing(ready_cards[1].get("title"), "make onboarding")
    blocked_surface_command = format_missing(deep_cards[1].get("title"), "make onboarding") if len(deep_cards) > 1 else "make onboarding"
    base_command_text = format_missing(command_cards[0].get("title"), "make help") if command_cards else "make help"
    command_text = base_command_text
    next_tab = format_missing(ready_cards[2].get("title"), "Data Health")
    ready_command_text = format_missing(ready_cards[1].get("title"), "")
    if command_text == "make help" and ready_command_text and ready_command_text != "make help":
        command_text = ready_command_text
    if next_tab == "Stock Report Beta" and command_text in {"make help", "make status", "make status-check TOP_N=5", "make onboarding"} and ready_command_text:
        command_text = ready_command_text
    if next_tab == "Monthly Picks" and command_text in {"make help", "make status", "make status-check TOP_N=5", "make onboarding"}:
        command_text = "make monthly"
    blocked_summary = compact_reason(deep_cards[0].get("body"), max_sentences=2, max_chars=220)
    blocked_follow_through = compact_reason(deep_cards[1].get("body"), max_sentences=2, max_chars=220) if len(deep_cards) > 1 else ""
    blocked_reason = blocked_summary
    if blocked_follow_through and blocked_follow_through != blocked_summary:
        blocked_reason = f"{blocked_summary} {blocked_follow_through}".strip()
    next_tab_reason = compact_reason(ready_cards[2].get("body"), max_sentences=2, max_chars=220)
    if command_text == ready_command_text:
        command_reason = compact_reason(ready_cards[1].get("command_reason"), max_sentences=2, max_chars=220)
    else:
        command_reason = (
            compact_reason(command_cards[0].get("body"), max_sentences=2, max_chars=220)
            if command_cards
            else "Highest-value repo-native command from the current local workflow state."
        )
    queue_signal = top_priority_signals(action_queue, limit=1) if action_queue is not None else []
    queue_reason = compact_reason(queue_signal[0].get("body"), max_sentences=2, max_chars=220) if queue_signal else ""
    generic_reason_markers = (
        "repo-native next step from the current read-only project status snapshot",
        "refresh local data coverage, onboarding outputs, and action guidance before broader research work",
    )
    if queue_reason and (
        command_text != base_command_text or any(marker in command_reason.lower() for marker in generic_reason_markers)
    ):
        command_reason = queue_reason
    elif (
        not queue_reason
        and len(deep_cards) > 1
        and (not command_reason or command_reason == "Not available" or any(marker in command_reason.lower() for marker in generic_reason_markers))
    ):
        deep_reason = compact_reason(deep_cards[1].get("body"), max_sentences=2, max_chars=220)
        if deep_reason and deep_reason != "Not available":
            command_reason = deep_reason
    if not command_reason or command_reason == "Not available":
        command_reason = "Highest-value repo-native command from the current local workflow state."
    if blocked_name == "No deep-research shortlist yet" and blocked_surface_command in {"", "Not available", "make onboarding"}:
        blocked_surface_command = command_text

    return [
        {
            "kicker": "BEST READY NAME",
            "title": ready_name,
            "body": (
                (
                    f"No locally ready name yet. Next surface: {next_tab} until the highest-leverage blocker is cleared."
                )
                if ready_name == "No current ready names yet"
                else f"Best currently usable local name. Next surface: {next_tab}."
            ),
            "badges": [str(item) for item in ready_cards[0].get("badges", [])][:2] or ["local coverage"],
            "command": ready_surface_command,
        },
        {
            "kicker": "BEST BLOCKED NAME",
            "title": blocked_name,
            "body": (
                (
                    "No deep-research shortlist yet. Refresh the SEC stage and peer-mapping queues before treating any blocker as current."
                )
                if blocked_name == "No deep-research shortlist yet"
                else (
                    f"Top deeper-research blocker from the SEC and peer queues. {blocked_reason}".strip()
                    if blocked_reason
                    else "Top deeper-research blocker from the SEC and peer queues."
                )
            ),
            "badges": [str(item) for item in deep_cards[0].get("badges", [])][:2] or ["coverage", "read-only"],
            "command": blocked_surface_command,
        },
        {
            "kicker": "BEST NEXT COMMAND",
            "title": command_text,
            "body": command_reason,
            "badges": [str(item) for item in command_cards[0].get("badges", [])][:2] if command_cards else ["command"],
            "command": command_text,
        },
        {
            "kicker": "BEST NEXT TAB",
            "title": next_tab,
            "body": next_tab_reason or "Best follow-up surface after the next command for the current daily research pass.",
            "badges": [str(item) for item in ready_cards[2].get("badges", [])][:2] or ["guided", "read-only"],
        },
    ]


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


def monthly_picks_next_step_cards(
    picks_frame: pd.DataFrame | None,
    track_frame: pd.DataFrame | None,
    equity_frame: pd.DataFrame | None,
    top_n: int,
    action_queue: pd.DataFrame | None,
) -> list[dict[str, object]]:
    def _monthly_coverage_command() -> str:
        fallback_command = overview_next_command_cards(None, action_queue, limit=1)[0] if action_queue is not None else {
            "title": "make status",
            "badges": ["data moat", "command"],
        }
        command_text = format_missing(fallback_command.get("title"), "make status")
        if command_text in {"", "Not available", "make help", "make status", "make status-check TOP_N=5", "make onboarding"}:
            return "make data-wizard TOP_N=10"
        return command_text

    candidate_count = 0 if picks_frame is None else len(picks_frame)
    has_candidates = picks_frame is not None and not picks_frame.empty
    has_track_record = track_frame is not None and not track_frame.empty
    has_equity = equity_frame is not None and not equity_frame.empty
    fallback_command = overview_next_command_cards(None, action_queue, limit=1)[0] if action_queue is not None else {
        "title": "make status",
        "badges": ["data moat", "command"],
    }
    command_text = format_missing(fallback_command.get("title"), "make status")
    coverage_command = _monthly_coverage_command()

    if picks_frame is None:
        primary = {
            "kicker": "NEXT STEP",
            "title": "Refresh monthly context",
            "body": "Monthly candidate outputs are unavailable right now. Run make monthly to refresh the monthly research files before interpreting this tab.",
            "badges": ["monthly refresh", "read-only"],
            "command": "make monthly",
        }
    elif picks_frame.empty:
        primary = {
            "kicker": "NEXT STEP",
            "title": "Improve candidate coverage",
            "body": (
                f"Current local filters did not support any monthly candidates. Run {coverage_command} to improve local price or fundamentals coverage instead of forcing weaker names into the list."
            ),
            "badges": ["coverage first", "no forced fills"],
            "command": coverage_command,
        }
    elif candidate_count < top_n:
        primary = {
            "kicker": "NEXT STEP",
            "title": "Improve candidate coverage",
            "body": (
                f"Only {candidate_count} of {top_n} conservative slots are filled. Run {coverage_command} to improve local price or fundamentals coverage before forcing weaker names into the list."
            ),
            "badges": ["coverage first", "no forced fills"],
            "command": coverage_command,
        }
    elif not has_track_record or not has_equity:
        track_record_command = command_text
        if track_record_command in {"", "Not available", "make help", "make status", "make status-check TOP_N=5", "make onboarding"}:
            track_record_command = "make track-record"
        primary = {
            "kicker": "NEXT STEP",
            "title": "Improve track-record coverage",
            "body": (
                f"Candidates exist, but local history is still too short for a fuller benchmark comparison. Run {track_record_command} to refresh or improve track-record coverage before treating performance context as complete."
            ),
            "badges": ["history needed", "sp y benchmark".replace(" ", "")],
            "command": track_record_command,
        }
    else:
        primary = {
            "kicker": "NEXT STEP",
            "title": "Review current candidates",
            "body": "The current monthly list and track record are both present. Run make dashboard-smoke first, then move through the candidate cards, score context, and archive together.",
            "badges": ["ready", "research only"],
            "command": "make dashboard-smoke",
        }

    gap_count = 0
    if picks_frame is not None and not picks_frame.empty and "MissingDataFields" in picks_frame.columns:
        gap_count = non_empty_count(picks_frame, ["MissingDataFields"])
    secondary = {
        "kicker": "DATA GAPS",
        "title": f"{gap_count} rows with gaps",
        "body": "Missing fields remain attached to each candidate so partial confidence is explicit instead of hidden.",
        "badges": ["transparent scoring", "local only"],
    }
    return [primary, secondary]


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
        ("Peer Relative", peer_label, "Requires manually researched peer mappings plus peer fundamentals or peer price/market-cap context"),
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
        command = preferred_row_command(
            row,
            ticker_focus_command(
                row.get("action_type"),
                row.get("ticker"),
                "make action-queue-check TOP_N=10",
            ),
        )
        lowered_command = command.lower()
        reason = normalize_operator_copy(row.get("reason"))
        recommended_action = normalize_operator_copy(row.get("recommended_action"))
        target_file = format_missing(row.get("target_file"), "")
        body_source = command_family_fallback(command, review_path_fallback(row.get("action_type")))
        if "runbook-" in command.lower():
            body_source = "Use the ordered lane runbook as the staged local workflow next so validation and preview safeguards stay in place."
        if recommended_action and recommended_action != reason:
            body_source = f"{reason} {recommended_action}".strip() if reason else recommended_action
        elif reason and reason != "Not available":
            body_source = reason
        if lowered_command == "make imports-validate":
            normalized_body = body_source.lower()
            if "make imports-preview" not in normalized_body or "make imports-apply" not in normalized_body:
                body_source = (
                    f"{reason} Run make imports-validate, then make imports-preview, then make imports-apply so staged local data is reviewed before apply."
                    if reason and reason != "Not available"
                    else "Run make imports-validate, then make imports-preview, then make imports-apply so staged local data is reviewed before apply."
                )
        elif lowered_command == "make price-validate":
            normalized_body = body_source.lower()
            if "make price-preview" not in normalized_body or "make price-apply" not in normalized_body:
                body_source = (
                    f"{reason} Run make price-validate, then make price-preview, then make price-apply so staged price rows are reviewed before apply."
                    if reason and reason != "Not available"
                    else "Run make price-validate, then make price-preview, then make price-apply so staged price rows are reviewed before apply."
                )
        staged_follow_through = ""
        if target_file == "data/imports/fundamentals.csv":
            staged_follow_through = "Run make imports-validate, then make imports-preview, then make imports-apply for the staged fundamentals import."
        elif target_file == "data/imports/peers.csv":
            staged_follow_through = "Run make imports-validate, then make imports-preview, then make imports-apply for the staged peer import."
        elif target_file == "data/imports/prices.csv":
            staged_follow_through = "Run make price-validate, then make price-preview, then make price-apply for the staged price import."
        if staged_follow_through:
            normalized_body = body_source.lower()
            needs_staged_upgrade = False
            if target_file == "data/imports/prices.csv":
                needs_staged_upgrade = (
                    "make price-validate" not in normalized_body
                    or "make price-preview" not in normalized_body
                    or "make price-apply" not in normalized_body
                )
            else:
                needs_staged_upgrade = (
                    "make imports-validate" not in normalized_body
                    or "make imports-preview" not in normalized_body
                    or "make imports-apply" not in normalized_body
                )
            if needs_staged_upgrade:
                body_source = (
                    f"{reason} {staged_follow_through}".strip()
                    if reason and reason != "Not available"
                    else staged_follow_through
                )
        rows.append(
            {
                "kicker": str(row.get("urgency", "Action")).upper(),
                "title": command,
                "body": compact_reason(body_source, max_sentences=2, max_chars=240),
                "badges": [
                    f"P{format_missing(row.get('priority'), '-')}",
                    format_missing(row.get("action_type"), "action"),
                    format_missing(row.get("ticker"), "portfolio-wide"),
                ],
                "command": command,
            }
        )
    return rows


def priority_now_fallback_actions(
    project_status_payload: dict[str, Any] | None,
    *,
    missing_warning_count: int,
    catalog: pd.DataFrame | None,
) -> list[tuple[str, str, str, str]]:
    actions: list[tuple[str, str, str, str]] = project_status_action_cards(project_status_payload)
    dcf_ready_count = _dcf_ready_count(catalog)
    peer_ready_count = _peer_ready_count(catalog)
    only_no_urgent_action = len(actions) == 1 and actions[0][0] == "No urgent onboarding actions"
    if only_no_urgent_action and missing_warning_count == 0 and dcf_ready_count > 0 and peer_ready_count > 0:
        actions = []
    if missing_warning_count:
        actions.append(
            (
                "Data gaps are visible",
                f"{missing_warning_count} ticker/theme names have missing-data warnings. Start with make data-wizard TOP_N=10, then follow the first focus or runbook path before trusting broader rankings.",
                "make data-wizard TOP_N=10",
                "warning",
            )
        )
    if dcf_ready_count == 0:
        actions.append(
            (
                "Valuation coverage is sparse",
                "DCF-ready count is zero. Stage SEC fundamentals or add verified local fundamentals before leaning on valuation context.",
                "make focus-fundamentals TICKER=NVDA",
                "warning",
            )
        )
    if peer_ready_count == 0:
        actions.append(
            (
                "Peer context needs local research",
                "No peer-ready tickers detected. Run make runbook-peers-broader or make focus-peers TICKER=... first. Add verified mappings only when they are missing, and otherwise follow the staged peer-data blocker.",
                "make runbook-peers-broader",
                "neutral",
            )
        )
    if not actions:
        actions.append(
            (
                "Workflow looks ready",
                "Core outputs are present. Run make status-check TOP_N=5 to review the operator snapshot, then make dashboard-smoke before deeper dashboard review.",
                "make status-check TOP_N=5",
                "neutral",
            )
        )
    return actions


def clean_display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    def clean_cell(value: object) -> str:
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, list):
            return ", ".join(str(item) for item in value if str(item).strip()) or "Not available"
        if isinstance(value, dict):
            return ", ".join(f"{key}: {val}" for key, val in value.items()) or "Not available"
        return normalize_operator_copy(value)

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
        "FocusCommand",
        "ExampleCommand",
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
        "FocusCommand",
        "ExampleCommand",
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


def _readiness_columns(frame: pd.DataFrame, preferred: list[str]) -> list[str]:
    return [column for column in preferred if column in frame.columns]


def render_momentum_readiness_tab(frame: pd.DataFrame, show_reason_details: bool) -> None:
    coverage_frame, _ = load_output(OUTPUTS_DIR / "ticker_data_coverage.csv")
    ready_frame, blocked_frame = split_momentum_readiness(frame, coverage_frame)
    render_signal_cards(
        [
            {
                "kicker": "MOMENTUM READINESS",
                "title": f"{len(ready_frame)} ready / {len(blocked_frame)} blocked",
                "body": "Momentum conclusions are shown only for tickers with enough local price coverage. Missing-price rows are listed separately.",
                "badges": ["ready" if not ready_frame.empty else "blocked", "prices required"],
                "command": "make price-coverage",
            }
        ]
    )
    if ready_frame.empty:
        render_notice_card(
            "Momentum analysis is blocked",
            "No tickers currently have enough local price rows for supported momentum conclusions.",
            "make price-coverage",
            tone="warning",
        )
    else:
        for section_title, description, chart_frame, chart_kind in output_tab_chart_sections("Momentum Leaders", ready_frame):
            render_chart_panel(section_title, description, chart_frame, chart_kind=chart_kind)
        render_table(ready_frame, "momentum-leaders", show_reason_details)
    if not blocked_frame.empty:
        with st.expander("Momentum blocked by missing price data", expanded=True):
            columns = _readiness_columns(blocked_frame, ["Ticker", "Theme", "SectorETF", "SetupStatus", "Reason"])
            st.dataframe(style_frame(presentation_frame(blocked_frame[columns])), width="stretch", hide_index=True)


def render_value_readiness_tab(frame: pd.DataFrame) -> None:
    dcf_readiness_frame, dcf_readiness_message = load_dcf_readiness()
    ready_companies, not_ready_companies, excluded = split_dcf_readiness(dcf_readiness_frame)
    render_signal_cards(
        [
            {
                "kicker": "DCF READINESS",
                "title": f"{len(ready_companies)} ready / {len(not_ready_companies)} blocked / {len(excluded)} excluded",
                "body": "Operating-company valuation conclusions are shown only for DCF-ready companies. ETFs/index proxies are excluded from DCF.",
                "badges": ["ready", "blocked", "excluded"],
                "command": "make dcf-readiness",
            }
        ]
    )
    if dcf_readiness_frame is None:
        render_notice_card(
            "DCF readiness has not been generated",
            dcf_readiness_message or "Run make dcf-readiness before reviewing valuation output.",
            "make dcf-readiness",
            tone="warning",
        )
        return
    if ready_companies.empty:
        render_notice_card(
            "DCF conclusions are blocked",
            "No operating-company ticker currently has all required DCF inputs. The table below lists the exact missing fields instead of showing ranked valuation conclusions.",
            "make dcf-readiness",
            tone="warning",
        )
    else:
        ready_tickers = set(ready_companies["ticker"].dropna().astype(str).str.upper())
        value_ready = frame.loc[frame["Ticker"].astype(str).str.upper().isin(ready_tickers)].copy() if "Ticker" in frame.columns else pd.DataFrame()
        render_table(value_ready, "value-re-rating", show_reason_details=False)
    if not not_ready_companies.empty:
        with st.expander("DCF-blocked companies and missing fields", expanded=True):
            columns = _readiness_columns(not_ready_companies, ["ticker", "asset_type", "missing_dcf_fields", "reason_not_ready", "has_price", "has_free_cash_flow", "has_shares_outstanding", "has_revenue", "has_fcf_margin"])
            st.dataframe(clean_display_frame(not_ready_companies[columns]), width="stretch", hide_index=True)
    if not excluded.empty:
        with st.expander("ETF / index proxy exclusions", expanded=True):
            columns = _readiness_columns(excluded, ["ticker", "asset_type", "reason_not_ready"])
            st.dataframe(clean_display_frame(excluded[columns]), width="stretch", hide_index=True)
    with st.expander("Raw valuation output diagnostics", expanded=False):
        diagnostic_columns = _readiness_columns(frame, ["Ticker", "ValuationStatus", "FinalValueCategory", "MissingDataFields", "Reason"])
        st.dataframe(clean_display_frame(frame[diagnostic_columns]), width="stretch", hide_index=True)


def render_final_decision_tab(frame: pd.DataFrame, show_reason_details: bool) -> None:
    decisions, decisions_message = load_output(OUTPUTS_DIR / "research_decisions.csv")
    if decisions is not None and not decisions.empty:
        render_section_header("Research Decisions", "Readiness-aware decision buckets. Blocked tickers are not ranked as weak recommendations.")
        bucket_counts = decisions.get("decision_bucket", pd.Series(dtype=object)).fillna("Unknown").astype(str).value_counts()
        render_metric_cards([(bucket, int(count), "Ticker-level decision bucket") for bucket, count in bucket_counts.items()])
        decision_columns = _readiness_columns(
            decisions,
            [
                "ticker",
                "decision_bucket",
                "confidence",
                "main_reason",
                "supporting_features",
                "blocked_features",
                "excluded_features",
                "missing_data",
                "next_action",
            ],
        )
        st.dataframe(clean_display_frame(decisions[decision_columns]), width="stretch", hide_index=True)
    else:
        render_notice_card(
            "Research decisions are not available yet",
            decisions_message or "Run make research-decisions or make pipeline to generate readiness-aware decision buckets.",
            "make research-decisions",
            tone="warning",
        )
    with st.expander("Legacy final watchlist output", expanded=False):
        render_table(frame, "final-watchlist", show_reason_details)


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
    monthly_tables = load_monthly_outputs()
    monthly_file_count = sum(1 for frame, _message in monthly_tables.values() if frame is not None)
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
    coverage_frame, _ = onboarding_tables["ticker_data_coverage.csv"]
    wizard_frame, _ = onboarding_tables["data_coverage_wizard.csv"]
    price_worklist_frame, _ = onboarding_tables["price_import_worklist.csv"]
    ticker_unlock_ladder_frame, _ = onboarding_tables["ticker_unlock_ladder.csv"]
    unlock_priority_summary_frame, _ = onboarding_tables["unlock_priority_summary.csv"]
    sec_stage_queue_frame, _ = onboarding_tables["sec_stage_queue.csv"]
    peer_mapping_queue_frame, _ = onboarding_tables["peer_mapping_queue.csv"]
    command_bundles_frame, _ = onboarding_tables["command_bundles.csv"]
    command_bundle_details_frame, _ = onboarding_tables["command_bundle_details.csv"]
    command_bundle_runbook_frame, _ = onboarding_tables["command_bundle_runbook.csv"]
    dcf_readiness_frame, _ = load_dcf_readiness()
    optional_readiness_tables = load_optional_context_readiness()
    earnings_readiness_frame, _ = optional_readiness_tables["earnings_readiness"]
    analyst_readiness_frame, _ = optional_readiness_tables["analyst_estimates_readiness"]
    ticker_readiness_frame, _ = load_ticker_readiness_report()
    prior_ticker_readiness_frame, prior_ticker_readiness_message = load_prior_ticker_readiness_report()
    feature_summary_frame, _ = load_feature_readiness_summary()
    latest_price = _latest_local_price_date(catalog)
    watchlist_count = 0 if final_watchlist_frame is None else len(final_watchlist_frame)
    monthly_frame, _ = monthly_tables["monthly_research_picks.csv"]
    monthly_count = 0 if monthly_frame is None else len(monthly_frame)

    render_section_header(
        "Overview",
        "A quick read on whether the local research workflow is ready, partial, or waiting on data.",
    )
    st.markdown(project_status_cockpit_html(project_status_payload, health_score, health_label), unsafe_allow_html=True)
    render_section_header("Data Quality / Readiness", "Read this before interpreting rankings or research conclusions.")
    render_signal_cards(
        readiness_panel_cards(
            dashboard_readiness_summary(
                coverage_frame,
                dcf_readiness_frame,
                earnings_readiness_frame,
                analyst_readiness_frame,
                ticker_readiness_frame,
            )
        )
    )
    render_section_header(
        "What Changed Recently",
        "Current readiness counts, latest generated timestamp, and prior/current deltas when a prior snapshot exists.",
    )
    render_signal_cards(
        readiness_recent_progress_cards(
            ticker_readiness_frame,
            prior_ticker_readiness_frame,
            feature_summary_frame,
            previous_snapshot_label=prior_ticker_readiness_message,
        )
    )
    render_signal_cards(
        overview_landing_cards(
            project_status_payload,
            queue_summary,
            latest_price,
            watchlist_count,
            monthly_count,
        )
    )
    render_signal_cards([overview_interpretation_guardrail_card(project_status_payload, queue_summary, health_summary)])
    render_section_header("Coverage Hotspots", "Which dataset types are currently causing the most research friction across the local workflow.")
    render_signal_cards(overview_coverage_hotspot_cards(action_queue_frame))
    render_section_header("Research Unlock Pressure", "A side-by-side read on whether prices, fundamentals, or peers are currently the main constraint on deeper local research.")
    render_signal_cards(
        overview_research_pressure_cards(
            price_worklist_frame,
            sec_stage_queue_frame,
            peer_mapping_queue_frame,
            unlock_priority_summary_frame,
        )
    )
    render_section_header("Price Targets", "The next exact local history targets for Monthly Picks, track record, or fuller 1Y research coverage.")
    render_signal_cards(overview_price_target_cards(price_worklist_frame))
    render_section_header("Deep Research Targets", "The next exact fundamentals and peer-relative targets for DCF unlocks and manual peer-context completion.")
    render_signal_cards(overview_deep_research_target_cards(sec_stage_queue_frame, peer_mapping_queue_frame))
    render_section_header("Deep Research Priorities", "The specific holdings or universe names that best match the current deep-research lane before you drop into the fuller queue tables.")
    render_signal_cards(
        overview_deep_research_priority_bridge_cards(
            holdings,
            sec_stage_queue_frame,
            peer_mapping_queue_frame,
        )
    )
    render_section_header("Best Current Names", "Which currently usable names best warrant a deeper single-name review or a quick candidate check next.")
    render_signal_cards(overview_best_current_name_cards(coverage_frame, holdings))
    render_section_header("Current Top Surfaces", "A one-row daily summary of the best ready name, the most important blocked deep-research name, the best next command, and the best next tab.")
    render_signal_cards(
        overview_current_top_surfaces_cards(
            coverage_frame,
            holdings,
            sec_stage_queue_frame,
            peer_mapping_queue_frame,
            project_status_payload,
            action_queue_frame,
        )
    )
    render_section_header("Today's Best Local Research Path", "One compact operator path: the strongest locally usable name, the next repo-native command, and the next tab to open after that.")
    render_signal_cards(
        overview_best_local_research_path_cards(
            coverage_frame,
            holdings,
            project_status_payload,
            action_queue_frame,
        )
    )

    with st.expander("More readiness and routing detail", expanded=False):
        render_section_header("Ready Now vs Blocked Now", "A short read on which names are already usable with today’s local coverage and which ones still need unlock work first.")
        render_signal_cards(overview_ready_blocked_cards(coverage_frame, ticker_unlock_ladder_frame, holdings))
        render_section_header("Ready Name Handoff", "For the strongest currently usable name, show the next exact local command when context is still partial and the best follow-up tab.")
        render_signal_cards(
            overview_ready_name_handoff_cards(
                coverage_frame,
                holdings,
                project_status_payload,
                action_queue_frame,
            )
        )
        render_section_header("Holdings First", "Blocked portfolio names and the next local unlock stage before broader universe work.")
        render_signal_cards(holdings_unlock_cards(holdings, ticker_unlock_ladder_frame, unlock_priority_summary_frame))
        render_section_header("Theme First", "Which local themes or sector ETF clusters unlock the most research value next.")
        render_signal_cards(theme_unlock_cards(unlock_priority_summary_frame))

    with st.expander("More deep-research context", expanded=False):
        render_section_header("Deep Research Leverage", "Which deeper research lane currently unlocks the most value next when you weigh holdings impact, theme breadth, and queued ticker count.")
        render_signal_cards(
            overview_deep_research_leverage_cards(
                holdings,
                sec_stage_queue_frame,
                peer_mapping_queue_frame,
            )
        )
        render_section_header("Deep Research Handoff", "For the top deep-research name, show the exact local command to run next and the best tab to use for queue confirmation.")
        render_signal_cards(
            overview_deep_research_handoff_cards(
                holdings,
                sec_stage_queue_frame,
                peer_mapping_queue_frame,
                project_status_payload,
                action_queue_frame,
            )
        )
        render_section_header("Holdings DCF / Peers", "Which portfolio names next benefit from SEC fundamentals staging or manual peer research once price blockers are understood.")
        render_signal_cards(holdings_deep_research_cards(holdings, sec_stage_queue_frame, peer_mapping_queue_frame))
        render_section_header("Theme DCF / Peers", "Which themes next benefit from SEC fundamentals staging or manual peer research once price-led blockers are already understood.")
        render_signal_cards(theme_deep_research_cards(sec_stage_queue_frame, peer_mapping_queue_frame))

    with st.expander("More market and workflow context", expanded=False):
        render_section_header("Market Context", "The strongest locally supported theme and ETF context from current benchmark-relative output rows.")
        render_signal_cards(overview_market_context_cards(market_direction_frame))
        render_section_header("Benchmark Pressure", "Whether weak coverage is mostly a local price-history issue or a broader benchmark-relative context issue.")
        render_signal_cards(overview_benchmark_pressure_cards(market_direction_frame, price_status_frame, project_status_payload))
        render_section_header("Best Next Commands", "A few repo-native commands that best match the current local blockers and verification state.")
        render_signal_cards(overview_next_command_cards(project_status_payload, action_queue_frame))
        render_section_header("Best Data Bundles", "Holdings-first local command bundles for the next price, SEC fundamentals, or peer-mapping pass.")
        render_signal_cards(overview_command_bundle_cards(command_bundles_frame))
        render_section_header("Bundle Lanes", "A lane-by-lane view of the current prices, fundamentals, and peers runbook so the next local pass is easier to follow.")
        render_signal_cards(overview_bundle_runbook_cards(command_bundle_runbook_frame))
        render_section_header("Bundle Handoff", "For the current top bundle, show the primary command, the follow-up step, the refresh step, and the first ticker to verify next.")
        render_signal_cards(overview_bundle_handoff_cards(command_bundles_frame, command_bundle_details_frame, command_bundle_runbook_frame))
        render_section_header("Today's Workflow Path", "A compact local sequence from blocker triage to verification to dashboard review.")
        render_signal_cards(overview_workflow_path_cards(project_status_payload, action_queue_frame))
        render_signal_cards([overview_workflow_reason_card(project_status_payload, action_queue_frame)])
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

    render_section_header("Next Deeper Tabs", "Where to go next after the high-level workflow read, depending on whether you need blocker triage, single-name depth, or broader candidate comparison.")
    render_signal_cards(overview_handoff_cards())

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
            "The same read-only snapshot shown by `make status-check TOP_N=5`, surfaced here so the dashboard and terminal agree.",
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
        actions = priority_now_fallback_actions(
            project_status_payload,
            missing_warning_count=missing_warning_count,
            catalog=catalog,
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
    monthly_tables = load_monthly_outputs()
    for filename, label in MONTHLY_FILES.items():
        frame, message = monthly_tables[filename]
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
    monthly_tables = load_monthly_outputs()
    picks_frame, picks_message = monthly_tables["monthly_research_picks.csv"]
    track_frame, _track_message = monthly_tables["monthly_picks_track_record.csv"]
    equity_frame, _equity_message = monthly_tables["monthly_picks_equity_curve.csv"]
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
    render_signal_cards(
        monthly_picks_next_step_cards(
            picks_frame,
            track_frame,
            equity_frame,
            top_n,
            action_queue_frame,
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
    blocker_command = monthly_picks_next_step_cards(
        pd.DataFrame() if picks_frame is not None and picks_frame.empty else picks_frame,
        track_frame,
        equity_frame,
        top_n,
        action_queue_frame,
    )[0]["command"]

    if picks_frame is None:
        render_notice_card(
            "Monthly context is not available yet",
            picks_message or "Run make monthly to refresh the monthly research files before interpreting this tab. This stays research-only and may still return fewer than five names.",
            "make monthly",
        )
    elif picks_frame.empty:
        render_notice_card(
            "No monthly candidates passed the current filters",
            "The output exists, but the conservative scoring rules did not find supported local candidates. Improve price/fundamental coverage before broadening interpretation.",
            blocker_command,
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
        with st.expander("Candidate scoring and table detail", expanded=False):
            score_chart_frame = monthly_pick_score_chart_frame(ordered_picks)
            if not score_chart_frame.empty:
                render_chart_panel(
                    "Score context",
                    "This chart compares transparent local score components for the current candidate set. Missing components stay blank instead of being inferred.",
                    score_chart_frame,
                    chart_kind="bar",
                )
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
            blocker_command,
        )
    with st.expander("Track-record table and archive detail", expanded=False):
        if track_frame is not None and not track_frame.empty:
            st.dataframe(clean_display_frame(track_frame), width="stretch", hide_index=True)
            render_section_header("Archive", "Prior local monthly pick lists and returns when calculable.")
            archive_columns = [column for column in ["Month", "Picks", "AveragePickReturn", "BenchmarkReturn", "ExcessReturn", "Notes"] if column in track_frame.columns]
            st.dataframe(clean_display_frame(track_frame[archive_columns]), width="stretch", hide_index=True)
        else:
            render_notice_card(
                "Track-record table is not available yet",
                "Track-record files are still unavailable. Run the current blocker path first; if local price history is still short afterward, the track-record output will stay explicit instead of fabricating performance.",
                blocker_command,
            )
            render_notice_card(
                "No monthly archive yet",
                "The archive appears only after enough local monthly pick and price-history rows exist. Nothing is backfilled or invented.",
                blocker_command,
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
            "make verify",
        )
        return
    if message and frame is not None:
        render_notice_card(f"{title} output note", message, "make verify")
    if frame is None:
        return
    render_signal_cards(output_tab_summary_cards(title, frame))
    if title == "Momentum Leaders":
        render_momentum_readiness_tab(frame, show_reason_details)
        return
    if title == "Value / Re-rating":
        render_value_readiness_tab(frame)
        return
    if title == "Final Watchlist":
        render_final_decision_tab(frame, show_reason_details)
        return
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
    coverage = pd.DataFrame()
    peer_summary: dict[str, object] = {}

    if provider is not None and ticker:
        coverage = pd.DataFrame(provider.get_ticker_dataset_coverage(ticker))
        peer_summary = provider.get_peer_summary(ticker)
        with st.expander("Ticker coverage and peer context", expanded=False):
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
    render_signal_cards(stock_report_next_step_cards(report_payload, coverage if provider is not None and ticker else None, peer_summary if provider is not None and ticker else None))
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
                "The report generated, but there is not enough provider-backed daily close history to render a chart. Use make runbook-prices-broader or make focus-price TICKER=... first. For downloaded files, use make price-normalize, then run make price-validate, make price-preview, and make price-apply.",
                "make runbook-prices-broader",
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
            if optional_context_available(
                earnings,
                [
                    "next_earnings_date",
                    "last_earnings_date",
                    "fiscal_period",
                    "eps_estimate",
                    "eps_actual",
                    "revenue_estimate",
                    "revenue_actual",
                    "surprise_pct",
                ],
            ):
                st.dataframe(clean_display_frame(stock_report_key_value_frame(earnings, earnings_fields)), width="stretch", hide_index=True)
                with st.expander("Earnings detail", expanded=False):
                    st.dataframe(stock_report_detail_frame(earnings), width="stretch", hide_index=True)
            else:
                st.info(optional_context_empty_state_message("earnings"))
                st.caption("Use data/staged/earnings/ -> make import-earnings -> make imports-validate -> make imports-preview -> make imports-apply.")
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
            if optional_context_available(
                estimates,
                [
                    "current_quarter_eps",
                    "next_quarter_eps",
                    "current_year_eps",
                    "next_year_eps",
                    "current_quarter_revenue",
                    "next_quarter_revenue",
                    "current_year_revenue",
                    "next_year_revenue",
                    "target_mean_price",
                    "target_high_price",
                    "target_low_price",
                    "recommendation",
                    "revision_trend",
                ],
            ):
                st.dataframe(clean_display_frame(stock_report_key_value_frame(estimates, estimate_fields)), width="stretch", hide_index=True)
                with st.expander("Analyst estimate detail", expanded=False):
                    st.dataframe(stock_report_detail_frame(estimates), width="stretch", hide_index=True)
            else:
                st.info(optional_context_empty_state_message("analyst-estimate"))
                st.caption(
                    "Use data/staged/analyst_estimates/ -> make import-analyst-estimates -> make imports-validate -> make imports-preview -> make imports-apply."
                )

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


def render_market_command_center(
    ticker_readiness_frame: pd.DataFrame | None,
    coverage_frame: pd.DataFrame | None,
    decisions_frame: pd.DataFrame | None,
    action_queue_frame: pd.DataFrame | None,
    project_status_payload: dict[str, Any] | None,
    feature_summary_frame: pd.DataFrame | None,
    peer_readiness_frame: pd.DataFrame | None,
    peer_mapping_queue_frame: pd.DataFrame | None,
    peer_unlock_worklist_frame: pd.DataFrame | None,
    dcf_readiness_frame: pd.DataFrame | None,
    earnings_readiness_frame: pd.DataFrame | None,
    analyst_readiness_frame: pd.DataFrame | None,
) -> None:
    render_section_header(
        "Market-Wide Command Center",
        "Known universe first, analysis-ready subset second, decisions last. Broad metadata can be large; tables are filtered and row-limited by default.",
    )
    summary = market_wide_readiness_summary(ticker_readiness_frame, coverage_frame, decisions_frame)
    render_signal_cards(readiness_panel_cards(summary))
    prior_ticker_readiness_frame, prior_ticker_readiness_message = load_prior_ticker_readiness_report()
    render_section_header(
        "What Changed Recently",
        "Current market-wide readiness, top blocked features, and prior/current comparison when a prior local snapshot exists.",
    )
    render_signal_cards(
        readiness_recent_progress_cards(
            ticker_readiness_frame,
            prior_ticker_readiness_frame,
            feature_summary_frame,
            previous_snapshot_label=prior_ticker_readiness_message,
        )
    )
    render_section_header("Feature Readiness", "Which product modules are usable today, partially usable, blocked, or excluded.")
    render_signal_cards(feature_readiness_cards(feature_summary_frame))
    render_section_header("Decision Workflow", "Readiness-gated decision buckets, primary blockers, and next actions without unsupported recommendations.")
    render_signal_cards(decision_workflow_summary_cards(decisions_frame))
    render_section_header("Peer Readiness Workflow", "Specific peer blockers for mapping, peer prices, peer fundamentals, and peer valuation context.")
    render_signal_cards(peer_readiness_product_cards(peer_readiness_frame, peer_mapping_queue_frame))
    render_section_header("Peer Mapping Studio", "Filtered peer unlock queue for DCF-ready names, missing mappings, and peer metric follow-through.")
    render_signal_cards(peer_mapping_studio_summary_cards(peer_readiness_frame, ticker_readiness_frame))
    render_signal_cards(peer_unlock_operator_cards(peer_unlock_worklist_frame))
    peer_cols = st.columns([1.7, 1.5, 1, 1, 1])
    peer_filter = peer_cols[0].selectbox(
        "Peer workflow filter",
        PEER_STUDIO_FILTERS,
        index=0,
        key="market-command-peer-filter",
    )
    peer_search = peer_cols[1].text_input(
        "Peer ticker / reason search",
        value="",
        placeholder="META, missing_peer_mapping, semis...",
        key="market-command-peer-search",
    )
    peer_limit = int(
        peer_cols[2].selectbox(
            "Peer row limit",
            [25, 50, 100, 200],
            index=1,
            key="market-command-peer-limit",
        )
    )
    active_peer_only = peer_cols[3].checkbox("Active only", value=False, key="market-command-peer-active-only")
    dcf_peer_only = peer_cols[4].checkbox("DCF-ready only", value=False, key="market-command-peer-dcf-only")
    peer_studio = build_peer_mapping_studio_frame(
        peer_readiness_frame,
        ticker_readiness_frame,
        peer_unlock_worklist_frame,
        filter_mode=peer_filter,
        ticker_search=peer_search,
        active_universe_only=active_peer_only,
        dcf_ready_only=dcf_peer_only,
        row_limit=peer_limit,
    )
    if peer_studio.empty:
        st.info("No peer workflow rows match the current filter. Try All peer-blocked or run make readiness.")
    else:
        st.caption(
            f"Showing {len(peer_studio)} peer workflow row(s). Use make peer-mapping-queue TOP_N=25 or focus commands before editing staged peer CSVs."
        )
        peer_columns = peer_mapping_studio_table_columns(peer_studio)
        st.dataframe(clean_display_frame(peer_studio[peer_columns]), width="stretch", hide_index=True)
    render_context_note(
        "Universe scope.",
        "Known universe is not the same as analysis-ready universe. Missing prices, fundamentals, peers, earnings, or estimates block conclusions; ETFs and index proxies stay excluded from operating-company DCF.",
        tone="warning" if summary.get("blocked_by_data", 0) else "neutral",
    )
    render_section_header(
        "Fundamentals / DCF Unlock Diagnostics",
        "Price-ready companies that still need trusted fundamentals, missing DCF fields, and DCF-ready names blocked only by peer context.",
    )
    render_signal_cards(fundamentals_dcf_diagnostic_cards(ticker_readiness_frame, dcf_readiness_frame))
    render_section_header("Next Action Console", "Grouped feature-level actions with source/freshness notes. These cards are copyable commands only; the dashboard does not run them.")
    action_console = build_next_action_console_frame(
        ticker_readiness_frame,
        action_queue_frame,
        project_status_payload,
        limit=8,
    )
    render_signal_cards(next_action_console_cards(action_console))
    if action_console.empty:
        st.info("No grouped action console rows are available. Run make project-status and make onboarding TOP_N=10 to refresh action guidance.")
    else:
        st.caption("Commands are capped, ticker-targeted, or preview/import oriented. Copy them into a terminal only after reviewing the source and safety notes.")
        st.dataframe(clean_display_frame(action_console), width="stretch", hide_index=True)
    render_section_header("Top Blocker Queues", "Small, safe worklist entry points for turning known tickers into analysis-ready tickers.")
    render_signal_cards(market_blocker_summary_cards(ticker_readiness_frame))
    render_section_header("Next Best Actions", "Practical command cards for the next local data unlock. These are copyable CLI commands only; the dashboard does not execute them.")
    render_signal_cards(market_next_action_cards(ticker_readiness_frame, action_queue_frame))

    if ticker_readiness_frame is None or ticker_readiness_frame.empty:
        render_notice_card(
            "Ticker readiness report is not available",
            "Run make readiness to generate data/reports/ticker_readiness_report.csv before using the market-wide filters.",
            "make readiness",
            tone="warning",
        )
        return

    render_section_header("Readiness Explorer", "Filter thousands of tickers without rendering the full market table by default.")
    filter_cols = st.columns([1.4, 1.4, 1.4, 1.4, 1.4])
    scope = filter_cols[0].selectbox(
        "Universe scope",
        ["Active research only", "All master universe"],
        index=0,
        key="market-command-scope",
    )
    readiness_filter = filter_cols[1].selectbox(
        "Readiness filter",
        MARKET_READINESS_FILTERS,
        index=0,
        key="market-command-readiness-filter",
    )
    asset_filter = filter_cols[2].selectbox(
        "Asset filter",
        MARKET_ASSET_FILTERS,
        index=0,
        key="market-command-asset-filter",
    )
    sector_options = ["All"]
    if "sector" in ticker_readiness_frame.columns:
        sector_options += sorted(
            value
            for value in ticker_readiness_frame["sector"].dropna().astype(str).str.strip().unique().tolist()
            if value and value.lower() not in {"nan", "none", "not available"}
        )
    theme_options = ["All"]
    if "theme" in ticker_readiness_frame.columns:
        theme_options += sorted(
            value
            for value in ticker_readiness_frame["theme"].dropna().astype(str).str.strip().unique().tolist()
            if value and value.lower() not in {"nan", "none", "not available"}
        )
    sector = filter_cols[3].selectbox("Sector", sector_options[:500], index=0, key="market-command-sector")
    theme = filter_cols[4].selectbox("Theme", theme_options[:500], index=0, key="market-command-theme")
    search_cols = st.columns([2.5, 1, 1])
    ticker_search = search_cols[0].text_input(
        "Ticker / name / reason search",
        value="",
        placeholder="META, semiconductor, missing fundamentals...",
        key="market-command-search",
    )
    row_limit = int(
        search_cols[1].selectbox(
            "Row limit",
            [50, 100, 200, 500, 1000],
            index=2,
            key="market-command-row-limit",
        )
    )
    show_all = search_cols[2].checkbox("Show all rows", value=False, key="market-command-show-all")
    scoped = filter_market_readiness_frame(
        ticker_readiness_frame,
        scope=scope,
        readiness_filter=readiness_filter,
        asset_filter=asset_filter,
        ticker_search=ticker_search,
        sector=sector,
        theme=theme,
        row_limit=None,
    )
    visible = scoped if show_all else scoped.head(row_limit).copy()
    st.caption(
        f"Showing {len(visible)} of {len(scoped)} filtered rows. Default views stay row-limited so the dashboard remains usable with thousands of known tickers."
    )
    columns = market_readiness_table_columns(visible)
    if columns:
        st.dataframe(clean_display_frame(visible[columns]), width="stretch", hide_index=True)
    else:
        st.info("No readiness rows match the current filters.")

    render_section_header("Single-Stock Drilldown", "Lazy ticker-level readiness, decision, missing-data, and next-action context.")
    ticker_options = sorted(ticker_readiness_frame["ticker"].dropna().astype(str).str.upper().str.strip().unique().tolist()) if "ticker" in ticker_readiness_frame.columns else []
    drill_cols = st.columns([1.4, 2.4])
    selected_ticker = drill_cols[0].selectbox(
        "Ticker",
        ticker_options[:5000] if ticker_options else ["AAPL"],
        index=0,
        key="market-command-single-stock-select",
    )
    manual_ticker = drill_cols[1].text_input(
        "Or type ticker",
        value="",
        placeholder="Type any ticker from the known universe",
        key="market-command-single-stock-manual",
    )
    drill_ticker = manual_ticker.strip().upper() or selected_ticker
    snapshot = single_stock_readiness_snapshot(
        drill_ticker,
        ticker_readiness_frame,
        coverage_frame,
        decisions_frame,
        dcf_readiness_frame,
        peer_readiness_frame,
        earnings_readiness_frame,
        analyst_readiness_frame,
    )
    metric_cols = st.columns(5)
    metric_cols[0].metric("Ticker", format_missing(snapshot.get("ticker")))
    metric_cols[1].metric("State", format_missing(snapshot.get("status")))
    metric_cols[2].metric("Decision", format_missing(snapshot.get("decision_bucket")))
    metric_cols[3].metric("DCF", format_missing(snapshot.get("dcf_status")))
    metric_cols[4].metric("Confidence", format_missing(snapshot.get("confidence")))
    render_signal_cards(single_stock_status_cards(snapshot))
    render_section_header("Single-Stock Source/Freshness Audit", "Local source paths, staged import paths, credential state, and rejected-row reports for the selected ticker.")
    render_signal_cards(single_stock_source_audit_cards(snapshot))
    st.dataframe(clean_display_frame(single_stock_source_audit_frame(snapshot)), width="stretch", hide_index=True)
    detail_frame = pd.DataFrame(
        [
            {"Field": "Asset type", "Value": snapshot.get("asset_type")},
            {"Field": "Price rows / days", "Value": snapshot.get("price_rows")},
            {"Field": "Decision subtype", "Value": snapshot.get("decision_subtype")},
            {"Field": "Primary blocker", "Value": snapshot.get("primary_blocker")},
            {"Field": "DCF reason", "Value": snapshot.get("dcf_reason")},
            {"Field": "Peer blocker type", "Value": snapshot.get("peer_blocker_type")},
            {"Field": "Peer mapping status", "Value": snapshot.get("peer_mapping_status")},
            {"Field": "Peer count / ready peers", "Value": f"{format_missing(snapshot.get('peer_count'))} / {format_missing(snapshot.get('ready_peer_count'))}"},
            {"Field": "Peer trend comparison ready", "Value": snapshot.get("peer_trend_comparison_ready")},
            {"Field": "Peer valuation comparison ready", "Value": snapshot.get("peer_valuation_comparison_ready")},
            {"Field": "Sample peers", "Value": snapshot.get("sample_peers")},
            {"Field": "Next peer action", "Value": snapshot.get("next_peer_action")},
            {"Field": "Earnings ready", "Value": snapshot.get("earnings_ready")},
            {"Field": "Analyst estimates ready", "Value": snapshot.get("analyst_estimates_ready")},
            {"Field": "Missing data", "Value": snapshot.get("missing_data")},
            {"Field": "Next action", "Value": snapshot.get("next_action")},
            {"Field": "Updated at", "Value": snapshot.get("updated_at")},
        ]
    )
    st.dataframe(clean_display_frame(detail_frame), width="stretch", hide_index=True)


def render_data_health(provider, project_status_payload: dict[str, Any] | None = None) -> None:
    render_section_header(
        "Data Health",
        "Validation, source availability, price refresh diagnostics, and onboarding actions in one place.",
    )
    if provider is None:
        st.warning("Local provider could not be initialized.")
        return
    if project_status_payload is None:
        project_status_payload = build_project_status_payload(BASE_DIR, data_dir=DATA_DIR, output_dir=OUTPUTS_DIR, top_n=5)
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
    sec_stage_queue_frame, sec_stage_queue_message = onboarding_tables["sec_stage_queue.csv"]
    peer_mapping_queue_frame, peer_mapping_queue_message = onboarding_tables["peer_mapping_queue.csv"]
    ticker_unlock_ladder_frame, ticker_unlock_ladder_message = onboarding_tables["ticker_unlock_ladder.csv"]
    unlock_priority_summary_frame, unlock_priority_summary_message = onboarding_tables["unlock_priority_summary.csv"]
    command_bundles_frame, command_bundles_message = onboarding_tables["command_bundles.csv"]
    command_bundle_details_frame, command_bundle_details_message = onboarding_tables["command_bundle_details.csv"]
    command_bundle_runbook_frame, command_bundle_runbook_message = onboarding_tables["command_bundle_runbook.csv"]
    dcf_readiness_frame, dcf_readiness_message = load_dcf_readiness()
    optional_readiness_tables = load_optional_context_readiness()
    earnings_readiness_frame, earnings_readiness_message = optional_readiness_tables["earnings_readiness"]
    analyst_readiness_frame, analyst_readiness_message = optional_readiness_tables["analyst_estimates_readiness"]
    ticker_readiness_frame, ticker_readiness_message = load_ticker_readiness_report()
    feature_summary_frame, feature_summary_message = load_feature_readiness_summary()
    peer_readiness_frame, peer_readiness_message = load_peer_readiness_report()
    peer_unlock_worklist_frame, peer_unlock_worklist_message = load_peer_unlock_worklist()
    decisions_frame, decisions_message = load_output(OUTPUTS_DIR / "research_decisions.csv")
    staged_imports = validate_imports(base_dir=BASE_DIR)
    universe_summary = summarize_universe_manager(BASE_DIR)
    staged_universe = universe_summary["staged_universe"]
    readiness_summary = dashboard_readiness_summary(
        coverage_frame,
        dcf_readiness_frame,
        earnings_readiness_frame,
        analyst_readiness_frame,
        ticker_readiness_frame,
    )

    render_section_header(
        "Data Quality / Readiness",
        "One-screen status for available, partial, blocked, and excluded analysis paths before any conclusions.",
    )
    render_market_command_center(
        ticker_readiness_frame,
        coverage_frame,
        decisions_frame,
        action_queue_frame,
        project_status_payload,
        feature_summary_frame,
        peer_readiness_frame,
        peer_mapping_queue_frame,
        peer_unlock_worklist_frame,
        dcf_readiness_frame,
        earnings_readiness_frame,
        analyst_readiness_frame,
    )
    if feature_summary_frame is None and feature_summary_message:
        render_notice_card(
            "Feature readiness summary has not been generated",
            feature_summary_message,
            "make readiness",
            tone="warning",
        )
    if peer_unlock_worklist_frame is None and peer_unlock_worklist_message:
        render_notice_card(
            "Peer unlock worklist has not been generated",
            peer_unlock_worklist_message,
            "make readiness",
            tone="warning",
        )
    if peer_readiness_frame is None and peer_readiness_message:
        render_notice_card(
            "Peer readiness report has not been generated",
            peer_readiness_message,
            "make readiness",
            tone="warning",
        )
    if decisions_frame is None and decisions_message:
        render_notice_card(
            "Research decisions have not been generated",
            decisions_message,
            "make pipeline",
            tone="warning",
        )
    render_signal_cards(readiness_panel_cards(readiness_summary))
    render_signal_cards(data_health_overview_cards(validation_rows, price_status_frame, action_queue_frame, coverage_frame))
    render_section_header("Next Data Unlocks", "What to unlock next for Monthly Picks, track record, DCF, and peer-relative research.")
    render_signal_cards(data_coverage_wizard_cards(wizard_frame))
    if wizard_frame is None:
        wizard_notice_body, wizard_notice_command = onboarding_notice_copy("coverage_wizard", wizard_message)
        render_notice_card(
            "Coverage wizard has not been generated",
            wizard_notice_body,
            wizard_notice_command,
        )
    render_section_header("Priority Fixes", "Highest-priority local data actions. Apply/merge steps remain CLI-only and reviewable.")
    render_action_cards(data_health_fix_first_cards(actions_frame))
    render_section_header("Action Paths", "The clearest local command path for the top overall action and the main prices, fundamentals, and peers lanes.")
    render_signal_cards(data_health_action_path_cards(actions_frame, action_queue_frame))
    render_section_header("Command Bundles", "Holdings-first local command bundles for the next price, SEC fundamentals, and peer-mapping pass.")
    render_signal_cards(data_health_command_bundle_cards(command_bundles_frame))
    render_section_header("Bundle Runbook", "Ordered command steps for each current bundle lane so the local follow-through stays explicit.")
    render_signal_cards(data_health_command_bundle_runbook_cards(command_bundle_runbook_frame))
    if command_bundles_frame is None:
        bundle_notice_body, bundle_notice_command = onboarding_notice_copy("command_bundles", command_bundles_message)
        render_notice_card(
            "Command bundles have not been generated yet",
            bundle_notice_body,
            bundle_notice_command,
        )
    if command_bundle_details_frame is not None and not command_bundle_details_frame.empty:
        with st.expander("Command bundle detail rows", expanded=False):
            detail_columns = [
                column
                for column in [
                    "bundle_name",
                    "lane",
                    "ticker",
                    "is_holding",
                    "theme",
                    "sector_etf",
                    "current_unlock_stage",
                    "target_goal",
                    "rows_needed",
                    "target_history_rows",
                    "suggested_start_date",
                    "exact_next_command",
                    "fallback_manual_command",
                    "recommended_action",
                    "primary_command",
                    "follow_up_command",
                ]
                if column in command_bundle_details_frame.columns
            ]
            st.dataframe(clean_display_frame(command_bundle_details_frame[detail_columns]), width="stretch", hide_index=True)
    elif command_bundle_details_frame is None:
        detail_notice_body, detail_notice_command = onboarding_notice_copy("command_bundle_details", command_bundle_details_message)
        render_notice_card(
            "Command bundle detail rows are not available yet",
            detail_notice_body,
            detail_notice_command,
        )
    if command_bundle_runbook_frame is not None and not command_bundle_runbook_frame.empty:
        with st.expander("Command bundle runbook", expanded=False):
            runbook_columns = [
                column
                for column in [
                    "bundle_name",
                    "lane",
                    "scope",
                    "step_order",
                    "step_label",
                    "command",
                    "tickers",
                    "goal_summary",
                    "target_history_rows",
                    "suggested_start_date",
                    "fallback_manual_command",
                    "target_file",
                ]
                if column in command_bundle_runbook_frame.columns
            ]
            st.dataframe(clean_display_frame(command_bundle_runbook_frame[runbook_columns]), width="stretch", hide_index=True)
    elif command_bundle_runbook_frame is None:
        runbook_notice_body, runbook_notice_command = onboarding_notice_copy("command_bundle_runbook", command_bundle_runbook_message)
        render_notice_card(
            "Command bundle runbook is not available yet",
            runbook_notice_body,
            runbook_notice_command,
        )

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
            "Run make verify to refresh local validation rows and confirm which CSV datasets are present, partial, or missing before relying on broader outputs.",
            "make verify",
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
            action_queue_notice_body, action_queue_notice_command = artifact_notice_copy("action_queue", action_queue_message)
            render_notice_card(
                "Action queue is not available yet",
                action_queue_notice_body,
                action_queue_notice_command,
                tone="warning",
            )
        else:
            queue_summary = action_queue_summary(action_queue_frame)
            metric_cols = st.columns(3)
            metric_cols[0].metric("Critical", queue_summary["critical"])
            metric_cols[1].metric("High", queue_summary["high"])
            metric_cols[2].metric("Medium", queue_summary["medium"])
            render_signal_cards(top_priority_signals(action_queue_frame, limit=3))
            queue_columns = action_queue_table_columns(action_queue_frame)
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
            research_health_notice_body, _ = artifact_notice_copy("research_health")
            st.info(research_health_notice_body)
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
                render_section_header("Price History Targets", "Which tickers need the next exact local history step for Monthly Picks, track record, or a fuller 1Y view.")
                render_signal_cards(data_health_price_target_cards(price_worklist_frame))
            if fundamentals_peer_worklist_frame is not None and not fundamentals_peer_worklist_frame.empty:
                fp_summary = summarize_fundamentals_peer_worklist(fundamentals_peer_worklist_frame)
                metric_cols = st.columns(4)
                metric_cols[0].metric("DCF Ready", fp_summary["dcf_ready"])
                metric_cols[1].metric("Peer Ready", fp_summary["peer_ready"])
                metric_cols[2].metric("Need Fundamentals", fp_summary["fundamentals_priority_1"])
                metric_cols[3].metric("Need Peer Context", fp_summary["peer_priority_2"])
            render_section_header("DCF Readiness", "Operating-company DCF gating, ETF exclusions, SEC setup, and manual fundamentals import availability.")
            metric_cols = st.columns(3)
            sec_configured = bool(os.environ.get("SEC_USER_AGENT", "").strip())
            if dcf_readiness_frame is not None and not dcf_readiness_frame.empty:
                ready_count = int(dcf_readiness_frame.get("is_dcf_ready", pd.Series(dtype=bool)).astype(bool).sum())
                not_ready_count = int(len(dcf_readiness_frame) - ready_count)
                excluded_count = int(dcf_readiness_frame.get("asset_type", pd.Series(dtype=object)).astype(str).ne("company").sum())
            else:
                ready_count = 0
                not_ready_count = 0
                excluded_count = 0
            metric_cols[0].metric("DCF-ready tickers", ready_count)
            metric_cols[1].metric("Not ready / excluded", not_ready_count)
            metric_cols[2].metric("ETF / index excluded", excluded_count)
            st.caption(
                "SEC_USER_AGENT configured: "
                + ("yes" if sec_configured else "no")
                + " | Manual fundamentals import: data/staged/fundamentals/ -> make import-fundamentals -> make imports-validate/preview/apply"
            )
            if dcf_readiness_frame is not None and not dcf_readiness_frame.empty:
                dcf_columns = [
                    column
                    for column in [
                        "ticker",
                        "asset_type",
                        "is_dcf_ready",
                        "missing_dcf_fields",
                        "reason_not_ready",
                        "has_free_cash_flow",
                        "has_shares_outstanding",
                        "has_revenue",
                        "has_fcf_margin",
                        "has_price",
                    ]
                    if column in dcf_readiness_frame.columns
                ]
                st.dataframe(clean_display_frame(dcf_readiness_frame[dcf_columns]), width="stretch", hide_index=True)
            else:
                render_notice_card(
                    "DCF readiness has not been generated",
                    dcf_readiness_message or "Run make dcf-readiness or make onboarding to generate data/dcf_readiness.csv.",
                    "make dcf-readiness",
                    tone="warning",
                )
            if optional_context_worklist_frame is not None and not optional_context_worklist_frame.empty:
                oc_summary = summarize_optional_context_worklist(optional_context_worklist_frame)
                metric_cols = st.columns(4)
                metric_cols[0].metric("Earnings Ready", oc_summary["earnings_ready"])
                metric_cols[1].metric("Estimates Ready", oc_summary["estimates_ready"])
                metric_cols[2].metric("Missing Both Optional", oc_summary["missing_both"])
                metric_cols[3].metric("Missing One Optional", oc_summary["missing_one"])
            render_section_header(
                "Trusted Optional Context",
                "Earnings and analyst estimates stay not available until verified local rows are imported and applied.",
            )
            render_signal_cards(optional_context_unlock_cards())
            optional_cols = st.columns(2)
            with optional_cols[0]:
                st.markdown("#### Earnings Readiness")
                if earnings_readiness_frame is not None and not earnings_readiness_frame.empty:
                    ready_count = int(earnings_readiness_frame.get("has_trusted_earnings", pd.Series(dtype=bool)).astype(bool).sum())
                    st.metric("Trusted earnings rows", f"{ready_count}/{len(earnings_readiness_frame)}")
                    st.caption("Manual import: data/staged/earnings/ -> make import-earnings -> make imports-validate/preview/apply")
                    columns = [
                        column
                        for column in ["ticker", "has_trusted_earnings", "row_count", "latest_report_date", "latest_fiscal_period", "missing_fields", "reason_not_ready"]
                        if column in earnings_readiness_frame.columns
                    ]
                    st.dataframe(clean_display_frame(earnings_readiness_frame[columns]), width="stretch", hide_index=True)
                else:
                    st.info("Not available: missing trusted local CSV input")
                    st.caption(earnings_readiness_message or "Run make optional-context-readiness to generate data/earnings_readiness.csv.")
            with optional_cols[1]:
                st.markdown("#### Analyst Estimate Readiness")
                if analyst_readiness_frame is not None and not analyst_readiness_frame.empty:
                    ready_count = int(analyst_readiness_frame.get("has_trusted_analyst_estimates", pd.Series(dtype=bool)).astype(bool).sum())
                    st.metric("Trusted analyst rows", f"{ready_count}/{len(analyst_readiness_frame)}")
                    st.caption(
                        "Manual import: data/staged/analyst_estimates/ -> make import-analyst-estimates -> make imports-validate/preview/apply"
                    )
                    columns = [
                        column
                        for column in ["ticker", "has_trusted_analyst_estimates", "row_count", "latest_period", "missing_fields", "reason_not_ready"]
                        if column in analyst_readiness_frame.columns
                    ]
                    st.dataframe(clean_display_frame(analyst_readiness_frame[columns]), width="stretch", hide_index=True)
                else:
                    st.info("Not available: missing trusted local CSV input")
                    st.caption(analyst_readiness_message or "Run make optional-context-readiness to generate data/analyst_estimates_readiness.csv.")
            if sec_stage_queue_frame is not None and not sec_stage_queue_frame.empty:
                sec_summary = summarize_sec_stage_queue(sec_stage_queue_frame)
                metric_cols = st.columns(4)
                metric_cols[0].metric("SEC Queue P1", sec_summary["priority_1"])
                metric_cols[1].metric("SEC Queue P2", sec_summary["priority_2"])
                metric_cols[2].metric("Holdings in SEC Queue", sec_summary["holdings"])
                metric_cols[3].metric("Missing Fundamentals Rows", sec_summary["missing_fundamentals"])
            if peer_mapping_queue_frame is not None and not peer_mapping_queue_frame.empty:
                peer_summary = summarize_peer_mapping_queue(peer_mapping_queue_frame)
                metric_cols = st.columns(4)
                metric_cols[0].metric("Peer Queue P1", peer_summary["priority_1"])
                metric_cols[1].metric("Peer Queue P2", peer_summary["priority_2"])
                metric_cols[2].metric("Holdings in Peer Queue", peer_summary["holdings"])
                metric_cols[3].metric("Missing Peer Mappings", peer_summary["missing_peer_mapping"])
                render_section_header("Deep Research Targets", "The next exact fundamentals and peer-relative targets for DCF unlocks and manual peer-context completion.")
                render_signal_cards(data_health_deep_research_target_cards(sec_stage_queue_frame, peer_mapping_queue_frame))
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

            render_section_header("Ticker Readiness Report", "Central per-feature readiness by ticker. Use this before interpreting any downstream analysis table.")
            if ticker_readiness_frame is not None and not ticker_readiness_frame.empty:
                readiness_columns = [
                    column
                    for column in [
                        "ticker",
                        "asset_type",
                        "theme",
                        "overall_readiness_state",
                        "price_ready",
                        "momentum_ready",
                        "liquidity_ready",
                        "correlation_ready",
                        "dcf_ready",
                        "peer_ready",
                        "earnings_ready",
                        "analyst_estimates_ready",
                        "blocked_features",
                        "excluded_features",
                        "missing_data",
                        "next_action",
                    ]
                    if column in ticker_readiness_frame.columns
                ]
                st.dataframe(clean_display_frame(ticker_readiness_frame[readiness_columns].head(200)), width="stretch", hide_index=True)
            else:
                st.info(ticker_readiness_message or "Run make readiness to generate data/reports/ticker_readiness_report.csv.")

            with st.expander("Liquidity Context", expanded=False):
                if liquidity_frame is not None and not liquidity_frame.empty:
                    liquidity_ready, liquidity_unavailable = split_risk_context_by_price_ready(
                        liquidity_frame,
                        {"Insufficient Price Data"},
                    )
                    liquidity_columns = [
                        column
                        for column in [
                            "Ticker",
                            "LiquidityStatus",
                            "LiquidityScore",
                            "LiquidityInputsUsed",
                            "LiquidityBlindSpots",
                            "AvgDollarVolume20D",
                            "AvgVolume20D",
                            "VolumeTrend5DVs20D",
                            "VolatilityProxy20D",
                            "MissingDataFields",
                            "Reason",
                        ]
                        if column in liquidity_frame.columns
                    ]
                    if not liquidity_ready.empty:
                        st.dataframe(style_frame(clean_display_frame(liquidity_ready[liquidity_columns])), width="stretch", hide_index=True)
                    else:
                        st.info("Liquidity analysis is blocked for all tickers until local price and volume rows are available.")
                    if not liquidity_unavailable.empty:
                        st.markdown("##### Liquidity unavailable")
                        st.dataframe(
                            style_frame(clean_display_frame(liquidity_unavailable[_readiness_columns(liquidity_unavailable, ["Ticker", "LiquidityStatus", "MissingDataFields", "Reason"])])),
                            width="stretch",
                            hide_index=True,
                        )
                else:
                    st.info(liquidity_message or "No liquidity rows are available.")

            with st.expander("Correlation Concentration Context", expanded=False):
                if correlation_frame is not None and not correlation_frame.empty:
                    correlation_ready, correlation_unavailable = split_risk_context_by_price_ready(
                        correlation_frame,
                        {"Insufficient Data", "Insufficient Overlap"},
                    )
                    correlation_columns = [
                        column
                        for column in [
                            "Ticker",
                            "CorrelationStatus",
                            "CorrelationMethod",
                            "ReturnType",
                            "MostCorrelatedTicker",
                            "Correlation",
                            "OverlapDays",
                            "MissingDataFields",
                            "Reason",
                        ]
                        if column in correlation_frame.columns
                    ]
                    if not correlation_ready.empty:
                        st.dataframe(style_frame(clean_display_frame(correlation_ready[correlation_columns])), width="stretch", hide_index=True)
                    else:
                        st.info("Correlation analysis is blocked until enough overlapping local return history exists.")
                    if not correlation_unavailable.empty:
                        st.markdown("##### Correlation unavailable")
                        st.dataframe(
                            style_frame(clean_display_frame(correlation_unavailable[_readiness_columns(correlation_unavailable, ["Ticker", "CorrelationStatus", "MissingDataFields", "Reason"])])),
                            width="stretch",
                            hide_index=True,
                        )
                else:
                    st.info(correlation_message or "No correlation rows are available.")

            if actions_frame is not None and not actions_frame.empty:
                with st.expander("Top Onboarding Actions", expanded=False):
                    top_actions = actions_frame.sort_values(["priority", "ticker", "dataset"], na_position="last").head(10)
                    action_columns = [
                        column
                        for column in ["priority", "ticker", "dataset", "status", "reason", "recommended_action", "focus_command", "target_file"]
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
                            "focus_command",
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
                            "next_price_goal",
                            "next_target_history_rows",
                            "rows_needed_for_next_goal",
                            "suggested_start_date",
                            "momentum_ready",
                            "track_record_ready",
                            "preferred_history_ready",
                            "missing_for_momentum",
                            "missing_for_track_record",
                            "missing_for_preferred_history",
                            "focus_command",
                            "example_command",
                        ]
                        if column in price_worklist_frame.columns
                    ]
                    st.dataframe(clean_display_frame(price_worklist_frame[worklist_columns].head(20)), width="stretch", hide_index=True)
            if fundamentals_peer_worklist_frame is not None and not fundamentals_peer_worklist_frame.empty:
                with st.expander("Fundamentals / Peer Worklist", expanded=False):
                    fp_columns = operator_workflow_table_columns(
                        fundamentals_peer_worklist_frame,
                        [
                            "priority",
                            "ticker",
                            "has_fundamentals",
                            "dcf_ready",
                            "has_peer_mapping",
                            "peer_ready",
                            "missing_required_for_dcf",
                            "missing_required_for_peer_relative",
                            "focus_command",
                            "example_command",
                        ],
                    )
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
            if sec_stage_queue_frame is not None and not sec_stage_queue_frame.empty:
                with st.expander("SEC Stage Queue", expanded=False):
                    sec_columns = operator_workflow_table_columns(
                        sec_stage_queue_frame,
                        [
                            "priority",
                            "ticker",
                            "is_holding",
                            "theme",
                            "sector_etf",
                            "price_history_days",
                            "has_fundamentals",
                            "missing_required_for_dcf",
                            "recommended_action",
                            "focus_command",
                            "example_command",
                        ],
                    )
                    st.dataframe(clean_display_frame(sec_stage_queue_frame[sec_columns].head(20)), width="stretch", hide_index=True)
            elif sec_stage_queue_message:
                st.info(sec_stage_queue_message)
            if peer_mapping_queue_frame is not None and not peer_mapping_queue_frame.empty:
                with st.expander("Peer Mapping Queue", expanded=False):
                    peer_columns = operator_workflow_table_columns(
                        peer_mapping_queue_frame,
                        [
                            "priority",
                            "ticker",
                            "is_holding",
                            "theme",
                            "sector_etf",
                            "has_peer_mapping",
                            "dcf_ready",
                            "missing_required_for_peer_relative",
                            "recommended_action",
                            "focus_command",
                            "example_command",
                        ],
                    )
                    st.dataframe(clean_display_frame(peer_mapping_queue_frame[peer_columns].head(20)), width="stretch", hide_index=True)
            elif peer_mapping_queue_message:
                st.info(peer_mapping_queue_message)
            if ticker_unlock_ladder_frame is not None and not ticker_unlock_ladder_frame.empty:
                with st.expander("Ticker Unlock Ladder", expanded=False):
                    ladder_columns = unlock_ladder_table_columns(ticker_unlock_ladder_frame, include_statuses=True)
                    st.dataframe(clean_display_frame(ticker_unlock_ladder_frame[ladder_columns].head(20)), width="stretch", hide_index=True)
            if unlock_priority_summary_frame is not None and not unlock_priority_summary_frame.empty:
                with st.expander("Unlock Priority Summary", expanded=False):
                    summary_columns = unlock_priority_summary_table_columns(unlock_priority_summary_frame)
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
            data_source_notice_body, data_source_notice_command = artifact_notice_copy("data_source_status")
            render_notice_card(
                "Data source status is not generated yet",
                data_source_notice_body,
                data_source_notice_command,
                tone="warning",
            )
        else:
            if status_frame is not None and not status_frame.empty:
                display_status = status_frame.copy()
                if "availability_status" in display_status.columns:
                    display_status["availability_status"] = display_status["availability_status"].map(friendly_data_source_status)
                columns = data_source_status_table_columns(display_status)
                st.dataframe(clean_display_frame(display_status[columns]), width="stretch", hide_index=True)
            else:
                data_source_rows_notice_body, data_source_rows_notice_command = artifact_notice_copy("data_source_rows", status_message)
                render_notice_card(
                    "No data source status rows are available",
                    data_source_rows_notice_body,
                    data_source_rows_notice_command,
                    tone="warning",
                )
            if gap_frame is not None and not gap_frame.empty:
                with st.expander("Data Gap Report", expanded=False):
                    display_gaps = gap_frame.copy()
                    if "status" in display_gaps.columns:
                        display_gaps["status"] = display_gaps["status"].map(friendly_data_source_status)
                    gap_columns = operator_workflow_table_columns(
                        display_gaps,
                        [
                            "dataset",
                            "ticker",
                            "status",
                            "required_for",
                            "recommended_action",
                            "target_file",
                            "focus_command",
                            "example_command",
                            "local_file",
                            "reason",
                            "source_name",
                        ],
                    )
                    display_frame = display_gaps[gap_columns] if gap_columns else display_gaps
                    st.dataframe(clean_display_frame(display_frame), width="stretch", hide_index=True)
            else:
                gap_notice_body, gap_notice_command = data_gap_report_notice(gap_message)
                render_notice_card(
                    "No data gaps were reported",
                    gap_notice_body,
                    gap_notice_command,
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
            st.info((price_status_message or "Price update status is unavailable.") + " " + price_refresh_fallback_message())
        else:
            status_counts = summarize_price_update_status(price_status_frame)
            if status_counts:
                statuses = ["fetched", "skipped_fresh", "parse_error", "source_unavailable", "network_error", "no_rows", "failed"]
                metric_cols = st.columns(4)
                metric_cols[0].metric("Fetched", status_counts.get("fetched", 0))
                metric_cols[1].metric("Skipped Fresh", status_counts.get("skipped_fresh", 0))
                metric_cols[2].metric("Parse / Source Errors", sum(status_counts.get(status, 0) for status in statuses[2:]))
                metric_cols[3].metric("Fallback Used", int(price_status_frame.get("fallback_used", pd.Series(dtype=object)).astype(str).str.lower().isin({"true", "1", "yes"}).sum()))
            display_columns = price_update_status_table_columns(price_status_frame)
            st.dataframe(clean_display_frame(price_status_frame[display_columns]), width="stretch", hide_index=True)
            problematic_statuses = {"parse_error", "source_unavailable", "network_error", "failed"}
            if "status" in price_status_frame.columns and price_status_frame["status"].astype(str).str.lower().isin(problematic_statuses).any():
                st.warning(price_refresh_fallback_message(include_remote_failure_prefix=True))
            render_context_note(
                "Manual fallback.",
                price_refresh_cli_note_message(),
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
            price_worklist_notice_body, price_worklist_notice_command = onboarding_notice_copy("price_worklist", price_worklist_message)
            render_notice_card(
                "Price history worklist is not available yet",
                price_worklist_notice_body,
                price_worklist_notice_command,
                tone="warning",
            )
        if fundamentals_peer_worklist_frame is not None and not fundamentals_peer_worklist_frame.empty:
            render_context_note(
                "Fundamentals and peer worklist.",
                "This local worklist shows which tickers are blocked on SEC-stageable fundamentals versus manual peer mappings and peer context.",
            )
            fp_columns = operator_workflow_table_columns(
                fundamentals_peer_worklist_frame,
                [
                    "priority",
                    "ticker",
                    "has_fundamentals",
                    "dcf_ready",
                    "has_peer_mapping",
                    "peer_ready",
                    "missing_required_for_dcf",
                    "missing_required_for_peer_relative",
                    "example_command",
                ],
            )
            st.dataframe(clean_display_frame(fundamentals_peer_worklist_frame[fp_columns].head(15)), width="stretch", hide_index=True)
        else:
            fundamentals_peer_notice_body, fundamentals_peer_notice_command = onboarding_notice_copy(
                "fundamentals_peer_worklist", fundamentals_peer_worklist_message
            )
            render_notice_card(
                "Fundamentals and peer worklist is not available yet",
                fundamentals_peer_notice_body,
                fundamentals_peer_notice_command,
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
            optional_context_notice_body, optional_context_notice_command = onboarding_notice_copy(
                "optional_context_worklist", optional_context_worklist_message
            )
            render_notice_card(
                "Optional context worklist is not available yet",
                optional_context_notice_body,
                optional_context_notice_command,
                tone="warning",
            )
        if ticker_unlock_ladder_frame is not None and not ticker_unlock_ladder_frame.empty:
            render_context_note(
                "Ticker unlock ladder.",
                "This single table combines prices, DCF, peer-relative, and optional context into one next-step ladder per ticker.",
            )
            ladder_columns = unlock_ladder_table_columns(ticker_unlock_ladder_frame, include_statuses=False)
            st.dataframe(clean_display_frame(ticker_unlock_ladder_frame[ladder_columns].head(15)), width="stretch", hide_index=True)
        else:
            ticker_unlock_notice_body, ticker_unlock_notice_command = onboarding_notice_copy(
                "ticker_unlock_ladder", ticker_unlock_ladder_message
            )
            render_notice_card(
                "Ticker unlock ladder is not available yet",
                ticker_unlock_notice_body,
                ticker_unlock_notice_command,
                tone="warning",
            )
        if unlock_priority_summary_frame is not None and not unlock_priority_summary_frame.empty:
            render_context_note(
                "Unlock priority summary.",
                "This grouped summary rolls the ticker ladders up by holdings, theme, and sector ETF so you can unlock the most research value first.",
            )
            summary_columns = unlock_priority_summary_table_columns(unlock_priority_summary_frame)
            st.dataframe(clean_display_frame(unlock_priority_summary_frame[summary_columns].head(15)), width="stretch", hide_index=True)
        else:
            unlock_priority_notice_body, unlock_priority_notice_command = onboarding_notice_copy(
                "unlock_priority_summary", unlock_priority_summary_message
            )
            render_notice_card(
                "Unlock priority summary is not available yet",
                unlock_priority_notice_body,
                unlock_priority_notice_command,
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
        st.write("- `outputs/project_status*.{json,csv}` stays local and ignored so status refreshes do not dirty the repo.")


def render_universe_manager(universe_summary: dict[str, Any]) -> None:
    render_section_header(
        "Universe Manager",
        "Review current universe coverage and use CLI-only apply commands for safer changes.",
    )
    current = universe_summary["current_universe"]
    staged = universe_summary["staged_universe"]

    render_section_header("Universe Workflow", "Preview-first expansion status. The dashboard stays read-only for safer universe changes.")
    render_action_cards(universe_workflow_cards(universe_summary))
    render_section_header("Universe Action Paths", "The clearest preview-first command path for the current universe file, staged import state, and safer apply flow.")
    render_signal_cards(universe_action_path_cards(universe_summary))

    render_signal_cards(universe_manager_summary_cards(current, staged))

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
                "make universe-preview",
                "make universe-apply",
            ]
        ),
        language="bash",
    )


def main() -> None:
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
        render_context_note("Safe local commands.", "These commands are read-only, verification, or preview-first by default.")
        st.code(
            "make help\nmake status-check TOP_N=5\nmake data-wizard TOP_N=5\nmake focus-price TICKER=AMD\nmake runbook-prices-broader\nmake verify\nmake dashboard-smoke\nmake dashboard",
            language="bash",
        )
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
        render_data_health(provider, project_status_payload)
    with tabs[9]:
        render_universe_manager(universe_summary)


if __name__ == "__main__":
    main()
