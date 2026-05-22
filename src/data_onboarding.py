from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.paths import format_path_context, resolve_data_dir, resolve_outputs_dir, resolve_project_root
from src.providers.local_data_catalog import LocalDataCatalog
from src.providers.local_schemas import LOCAL_DATASET_SCHEMAS


COVERAGE_COLUMNS = [
    "ticker",
    "has_prices",
    "price_history_days",
    "has_fundamentals",
    "dcf_ready",
    "has_peer_mapping",
    "peer_ready",
    "has_earnings",
    "has_analyst_estimates",
    "usable_for_momentum",
    "usable_for_monthly_picks",
    "usable_for_dcf",
    "usable_for_peer_relative",
    "missing_required_for_momentum",
    "missing_required_for_dcf",
    "missing_required_for_peer_relative",
    "next_best_action",
]

ACTION_COLUMNS = [
    "priority",
    "ticker",
    "dataset",
    "status",
    "reason",
    "recommended_action",
    "target_file",
    "example_command",
]

PRICE_WORKLIST_COLUMNS = [
    "priority",
    "ticker",
    "has_prices",
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
    "recommended_action",
    "target_file",
    "example_command",
    "safe_next_step",
]

FUNDAMENTALS_PEER_WORKLIST_COLUMNS = [
    "priority",
    "ticker",
    "has_fundamentals",
    "dcf_ready",
    "has_peer_mapping",
    "peer_ready",
    "missing_required_for_dcf",
    "missing_required_for_peer_relative",
    "recommended_action",
    "target_file",
    "example_command",
    "safe_next_step",
]

OPTIONAL_CONTEXT_WORKLIST_COLUMNS = [
    "priority",
    "ticker",
    "has_earnings",
    "has_analyst_estimates",
    "earnings_context_ready",
    "estimate_context_ready",
    "missing_optional_context",
    "recommended_action",
    "target_file",
    "example_command",
    "safe_next_step",
]

SEC_STAGE_QUEUE_COLUMNS = [
    "priority",
    "ticker",
    "is_holding",
    "theme",
    "sector_etf",
    "price_history_days",
    "has_fundamentals",
    "dcf_ready",
    "missing_required_for_dcf",
    "recommended_action",
    "target_file",
    "example_command",
    "safe_next_step",
]

PEER_MAPPING_QUEUE_COLUMNS = [
    "priority",
    "ticker",
    "is_holding",
    "theme",
    "sector_etf",
    "has_peer_mapping",
    "dcf_ready",
    "peer_ready",
    "missing_required_for_peer_relative",
    "recommended_action",
    "target_file",
    "example_command",
    "safe_next_step",
]

TICKER_UNLOCK_LADDER_COLUMNS = [
    "ticker",
    "price_stage_status",
    "price_history_days",
    "dcf_stage_status",
    "peer_stage_status",
    "optional_context_status",
    "current_unlock_stage",
    "next_unlock_goal",
    "recommended_action",
    "target_file",
    "example_command",
    "safe_next_step",
]

UNLOCK_PRIORITY_SUMMARY_COLUMNS = [
    "group_type",
    "group_name",
    "ticker_count",
    "holdings_count",
    "price_stage_count",
    "fundamentals_stage_count",
    "peer_stage_count",
    "optional_stage_count",
    "ready_stage_count",
    "top_priority_stage",
    "next_unlock_goal",
    "representative_tickers",
    "recommended_action",
]

COMMAND_BUNDLE_COLUMNS = [
    "bundle_name",
    "lane",
    "scope",
    "ticker_count",
    "tickers",
    "goal_summary",
    "target_history_rows",
    "suggested_start_date",
    "primary_command",
    "follow_up_command",
    "target_file",
    "why_it_matters",
    "safe_next_step",
]

COMMAND_BUNDLE_DETAIL_COLUMNS = [
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
    "recommended_action",
    "primary_command",
    "follow_up_command",
    "target_file",
    "safe_next_step",
]

COMMAND_BUNDLE_RUNBOOK_COLUMNS = [
    "bundle_name",
    "lane",
    "scope",
    "step_order",
    "step_label",
    "command",
    "target_file",
    "tickers",
    "goal_summary",
    "target_history_rows",
    "suggested_start_date",
    "why_it_matters",
    "safe_next_step",
]

WIZARD_COLUMNS = [
    "priority",
    "ticker",
    "unlock_goal",
    "blocking_dataset",
    "current_status",
    "why_it_matters",
    "recommended_action",
    "target_file",
    "example_command",
    "safe_next_step",
]

TEMPLATE_DATASETS = ("prices", "peers", "fundamentals", "earnings", "analyst_estimates", "custom_universe")
PRICE_TEMPLATE_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "volume", "adjusted_close", "source", "as_of_date", "notes"]


@dataclass
class TickerCoverage:
    ticker: str
    has_prices: bool
    price_history_days: int
    has_fundamentals: bool
    dcf_ready: bool
    has_peer_mapping: bool
    peer_ready: bool
    has_earnings: bool
    has_analyst_estimates: bool
    usable_for_momentum: bool
    usable_for_monthly_picks: bool
    usable_for_dcf: bool
    usable_for_peer_relative: bool
    missing_required_for_momentum: str
    missing_required_for_dcf: str
    missing_required_for_peer_relative: str
    next_best_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CommandBundleRow:
    bundle_name: str
    lane: str
    scope: str
    ticker_count: int
    tickers: str
    goal_summary: str
    target_history_rows: int
    suggested_start_date: str
    primary_command: str
    follow_up_command: str
    target_file: str
    why_it_matters: str
    safe_next_step: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CommandBundleDetailRow:
    bundle_name: str
    lane: str
    ticker: str
    is_holding: bool
    theme: str
    sector_etf: str
    current_unlock_stage: str
    target_goal: str
    rows_needed: int
    target_history_rows: int
    suggested_start_date: str
    recommended_action: str
    primary_command: str
    follow_up_command: str
    target_file: str
    safe_next_step: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CommandBundleRunbookRow:
    bundle_name: str
    lane: str
    scope: str
    step_order: int
    step_label: str
    command: str
    target_file: str
    tickers: str
    goal_summary: str
    target_history_rows: int
    suggested_start_date: str
    why_it_matters: str
    safe_next_step: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OnboardingAction:
    priority: int
    ticker: str
    dataset: str
    status: str
    reason: str
    recommended_action: str
    target_file: str
    example_command: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PriceWorklistRow:
    priority: int
    ticker: str
    has_prices: bool
    price_history_days: int
    first_local_date: str
    latest_local_date: str
    next_price_goal: str
    next_target_history_rows: int
    rows_needed_for_next_goal: int
    suggested_start_date: str
    momentum_ready: bool
    track_record_ready: bool
    preferred_history_ready: bool
    missing_for_momentum: str
    missing_for_track_record: str
    missing_for_preferred_history: str
    recommended_action: str
    target_file: str
    example_command: str
    safe_next_step: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FundamentalsPeerWorklistRow:
    priority: int
    ticker: str
    has_fundamentals: bool
    dcf_ready: bool
    has_peer_mapping: bool
    peer_ready: bool
    missing_required_for_dcf: str
    missing_required_for_peer_relative: str
    recommended_action: str
    target_file: str
    example_command: str
    safe_next_step: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OptionalContextWorklistRow:
    priority: int
    ticker: str
    has_earnings: bool
    has_analyst_estimates: bool
    earnings_context_ready: bool
    estimate_context_ready: bool
    missing_optional_context: str
    recommended_action: str
    target_file: str
    example_command: str
    safe_next_step: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SecStageQueueRow:
    priority: int
    ticker: str
    is_holding: bool
    theme: str
    sector_etf: str
    price_history_days: int
    has_fundamentals: bool
    dcf_ready: bool
    missing_required_for_dcf: str
    recommended_action: str
    target_file: str
    example_command: str
    safe_next_step: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PeerMappingQueueRow:
    priority: int
    ticker: str
    is_holding: bool
    theme: str
    sector_etf: str
    has_peer_mapping: bool
    dcf_ready: bool
    peer_ready: bool
    missing_required_for_peer_relative: str
    recommended_action: str
    target_file: str
    example_command: str
    safe_next_step: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TickerUnlockLadderRow:
    ticker: str
    price_stage_status: str
    price_history_days: int
    dcf_stage_status: str
    peer_stage_status: str
    optional_context_status: str
    current_unlock_stage: str
    next_unlock_goal: str
    recommended_action: str
    target_file: str
    example_command: str
    safe_next_step: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UnlockPrioritySummaryRow:
    group_type: str
    group_name: str
    ticker_count: int
    holdings_count: int
    price_stage_count: int
    fundamentals_stage_count: int
    peer_stage_count: int
    optional_stage_count: int
    ready_stage_count: int
    top_priority_stage: str
    next_unlock_goal: str
    representative_tickers: str
    recommended_action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DataCoverageWizardRow:
    priority: int
    ticker: str
    unlock_goal: str
    blocking_dataset: str
    current_status: str
    why_it_matters: str
    recommended_action: str
    target_file: str
    example_command: str
    safe_next_step: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_frame(catalog: LocalDataCatalog, dataset_name: str) -> pd.DataFrame:
    frame = catalog.load_dataframe(dataset_name)
    return frame.copy() if frame is not None else pd.DataFrame()


def _ticker_set(frame: pd.DataFrame, column: str = "ticker") -> set[str]:
    if frame.empty or column not in frame.columns:
        return set()
    return set(frame[column].dropna().astype(str).str.upper().str.strip())


def _select_row(frame: pd.DataFrame, ticker: str) -> pd.Series:
    if frame.empty or "ticker" not in frame.columns:
        return pd.Series(dtype=object)
    rows = frame.loc[frame["ticker"].astype(str).str.upper().str.strip() == ticker]
    return rows.iloc[-1] if not rows.empty else pd.Series(dtype=object)


def _has_number(row: pd.Series, *columns: str) -> bool:
    for column in columns:
        if column in row and pd.notna(pd.to_numeric(pd.Series([row[column]]), errors="coerce").iloc[0]):
            return True
    return False


def _dcf_ready(row: pd.Series) -> bool:
    if row.empty:
        return False
    has_fcf_base = _has_number(row, "free_cash_flow", "fcf")
    has_revenue_margin_base = _has_number(row, "revenue") and _has_number(row, "fcf_margin")
    has_shares = _has_number(row, "shares_outstanding")
    return (has_fcf_base or has_revenue_margin_base) and has_shares


def _peer_ready(ticker: str, peers: pd.DataFrame, fundamentals: pd.DataFrame, prices: pd.DataFrame) -> bool:
    if peers.empty or "ticker" not in peers.columns or "peer_ticker" not in peers.columns:
        return False
    peer_rows = peers.loc[peers["ticker"].astype(str).str.upper().str.strip() == ticker].copy()
    if peer_rows.empty:
        return False
    peer_tickers = sorted(set(peer_rows["peer_ticker"].dropna().astype(str).str.upper().str.strip()) - {ticker})
    if not peer_tickers:
        return False
    fundamental_tickers = _ticker_set(fundamentals)
    price_tickers = _ticker_set(prices)
    return any(peer in fundamental_tickers and (peer in price_tickers or _has_number(_select_row(fundamentals, peer), "market_cap")) for peer in peer_tickers)


def _price_history_days(prices: pd.DataFrame, ticker: str) -> int:
    if prices.empty or "ticker" not in prices.columns:
        return 0
    return int((prices["ticker"].astype(str).str.upper().str.strip() == ticker).sum())


def _price_date_bounds(prices: pd.DataFrame, ticker: str) -> tuple[str, str]:
    if prices.empty or "ticker" not in prices.columns or "date" not in prices.columns:
        return "", ""
    ticker_rows = prices.loc[prices["ticker"].astype(str).str.upper().str.strip() == ticker].copy()
    if ticker_rows.empty:
        return "", ""
    ticker_rows["date"] = pd.to_datetime(ticker_rows["date"], errors="coerce")
    ticker_rows = ticker_rows.loc[ticker_rows["date"].notna()]
    if ticker_rows.empty:
        return "", ""
    return (
        ticker_rows["date"].min().date().isoformat(),
        ticker_rows["date"].max().date().isoformat(),
    )


def _discover_tickers(catalog: LocalDataCatalog, requested: list[str] | None = None) -> list[str]:
    if requested:
        return sorted({ticker.strip().upper() for ticker in requested if ticker.strip()})
    return catalog.list_tickers(["universe", "holdings"])


def _normalize_column_lookup(frame: pd.DataFrame) -> dict[str, str]:
    return {str(column).strip().lower(): str(column) for column in frame.columns}


def _missing_join(items: list[str]) -> str:
    return ", ".join(items)


def _action_for_coverage(row: TickerCoverage) -> str:
    if not row.has_prices:
        return (
            f"Run python3 -m src.data_update --tickers {row.ticker}, or add verified rows to "
            "data/imports/prices.csv and run validate/preview/apply."
        )
    if row.price_history_days < 21:
        return (
            f"Run python3 -m src.data_update --tickers {row.ticker}, or add more verified local price rows "
            "to data/imports/prices.csv."
        )
    if not row.has_fundamentals or not row.dcf_ready:
        return f"Run SEC staging for fundamentals: python3 -m src.stock_report --sec-stage-fundamentals --tickers {row.ticker}"
    if not row.has_peer_mapping:
        return "Add peer mappings manually to data/imports/peers.csv."
    if not row.peer_ready:
        return "Add peer fundamentals/prices locally so peer-relative valuation can calculate."
    if not row.has_earnings:
        return "Optional: add data/imports/earnings.csv from a trusted source."
    if not row.has_analyst_estimates:
        return "Optional: add analyst estimates only if a trusted source exists."
    return "Coverage is sufficient for the current CSV-first research workflow."


def _ticker_context_lookup(
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, dict[str, Any]]:
    root = resolve_project_root(project_root)
    data_path = resolve_data_dir(data_dir, root)
    output_path = resolve_outputs_dir(output_dir, root)
    catalog = LocalDataCatalog(root, data_dir=data_path, outputs_dir=output_path)
    universe = _load_frame(catalog, "universe")
    holdings = _load_frame(catalog, "holdings")
    universe_lookup = _normalize_column_lookup(universe)
    holdings_lookup = _normalize_column_lookup(holdings)
    universe_ticker_col = universe_lookup.get("ticker")
    theme_col = universe_lookup.get("theme")
    sector_col = universe_lookup.get("sectoretf") or universe_lookup.get("sector_etf")
    holding_tickers = _ticker_set(holdings, holdings_ticker_col) if (holdings_ticker_col := holdings_lookup.get("ticker")) else set()

    context: dict[str, dict[str, Any]] = {}
    if universe_ticker_col and not universe.empty:
        for _, row in universe.iterrows():
            ticker = str(row.get(universe_ticker_col, "")).strip().upper()
            if not ticker:
                continue
            context[ticker] = {
                "is_holding": ticker in holding_tickers,
                "theme": str(row.get(theme_col, "")).strip() if theme_col else "",
                "sector_etf": str(row.get(sector_col, "")).strip() if sector_col else "",
            }

    for ticker in holding_tickers:
        context.setdefault(
            ticker,
            {
                "is_holding": True,
                "theme": "",
                "sector_etf": "",
            },
        )
        context[ticker]["is_holding"] = True

    return context


def build_ticker_coverage(
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
    tickers: list[str] | None = None,
) -> list[TickerCoverage]:
    root = resolve_project_root(project_root)
    data_path = resolve_data_dir(data_dir, root)
    output_path = resolve_outputs_dir(output_dir, root)
    catalog = LocalDataCatalog(root, data_dir=data_path, outputs_dir=output_path)
    prices = _load_frame(catalog, "prices")
    fundamentals = _load_frame(catalog, "fundamentals")
    peers = _load_frame(catalog, "peers")
    earnings = _load_frame(catalog, "earnings")
    estimates = _load_frame(catalog, "analyst_estimates")
    final_watchlist = _load_frame(catalog, "final_watchlist")
    momentum = _load_frame(catalog, "momentum_leaders")

    price_tickers = _ticker_set(prices)
    fundamental_tickers = _ticker_set(fundamentals)
    earnings_tickers = _ticker_set(earnings)
    estimate_tickers = _ticker_set(estimates)
    peer_subject_tickers = _ticker_set(peers)
    output_tickers = _ticker_set(final_watchlist) | _ticker_set(momentum)

    rows: list[TickerCoverage] = []
    for ticker in _discover_tickers(catalog, tickers):
        history_days = _price_history_days(prices, ticker)
        has_prices = ticker in price_tickers
        has_fundamentals = ticker in fundamental_tickers
        financial_row = _select_row(fundamentals, ticker)
        dcf_ready = _dcf_ready(financial_row)
        has_peer_mapping = ticker in peer_subject_tickers
        peer_ready = _peer_ready(ticker, peers, fundamentals, prices)
        has_earnings = ticker in earnings_tickers
        has_estimates = ticker in estimate_tickers
        usable_for_momentum = has_prices and history_days >= 21
        usable_for_monthly_picks = usable_for_momentum and ticker in output_tickers
        usable_for_dcf = dcf_ready
        usable_for_peer_relative = peer_ready

        missing_momentum = []
        if not has_prices:
            missing_momentum.append("prices")
        if has_prices and history_days < 21:
            missing_momentum.append("at least 21 price rows")

        missing_dcf = []
        if not has_fundamentals:
            missing_dcf.append("fundamentals row")
        if has_fundamentals and not (_has_number(financial_row, "free_cash_flow", "fcf") or (_has_number(financial_row, "revenue") and _has_number(financial_row, "fcf_margin"))):
            missing_dcf.append("free_cash_flow or revenue plus fcf_margin")
        if has_fundamentals and not _has_number(financial_row, "shares_outstanding"):
            missing_dcf.append("shares_outstanding")

        missing_peer = []
        if not has_peer_mapping:
            missing_peer.append("peer mapping")
        if has_peer_mapping and not peer_ready:
            missing_peer.append("peer fundamentals or peer price/market-cap context")

        provisional = TickerCoverage(
            ticker=ticker,
            has_prices=has_prices,
            price_history_days=history_days,
            has_fundamentals=has_fundamentals,
            dcf_ready=dcf_ready,
            has_peer_mapping=has_peer_mapping,
            peer_ready=peer_ready,
            has_earnings=has_earnings,
            has_analyst_estimates=has_estimates,
            usable_for_momentum=usable_for_momentum,
            usable_for_monthly_picks=usable_for_monthly_picks,
            usable_for_dcf=usable_for_dcf,
            usable_for_peer_relative=usable_for_peer_relative,
            missing_required_for_momentum=_missing_join(missing_momentum),
            missing_required_for_dcf=_missing_join(missing_dcf),
            missing_required_for_peer_relative=_missing_join(missing_peer),
            next_best_action="",
        )
        provisional.next_best_action = _action_for_coverage(provisional)
        rows.append(provisional)
    return rows


def build_onboarding_actions(coverage_rows: list[TickerCoverage]) -> list[OnboardingAction]:
    actions: list[OnboardingAction] = []
    for row in coverage_rows:
        if not row.has_prices or row.price_history_days < 21:
            actions.append(
                OnboardingAction(
                    priority=1,
                    ticker=row.ticker,
                    dataset="prices",
                    status="missing" if not row.has_prices else "insufficient_history",
                    reason=row.missing_required_for_momentum or "Price coverage is too sparse for stable momentum research.",
                    recommended_action=(
                        f"Run python3 -m src.data_update --tickers {row.ticker}, or add verified rows to "
                        "data/imports/prices.csv and run validate/preview/apply."
                    ),
                    target_file="data/imports/prices.csv",
                    example_command=f"python3 -m src.data_update --tickers {row.ticker}",
                )
            )
        if not row.dcf_ready:
            actions.append(
                OnboardingAction(
                    priority=2,
                    ticker=row.ticker,
                    dataset="fundamentals",
                    status="missing_or_incomplete",
                    reason=row.missing_required_for_dcf or "DCF inputs are incomplete.",
                    recommended_action="Run SEC staging for fundamentals, then validate and preview before applying.",
                    target_file="data/imports/fundamentals.csv",
                    example_command=f"python3 -m src.stock_report --sec-stage-fundamentals --tickers {row.ticker}",
                )
            )
        if not row.has_peer_mapping:
            actions.append(
                OnboardingAction(
                    priority=3,
                    ticker=row.ticker,
                    dataset="peers",
                    status="manual_input_needed",
                    reason="No local peer mapping is configured for this ticker.",
                    recommended_action="Add peer mappings manually to data/imports/peers.csv.",
                    target_file="data/imports/peers.csv",
                    example_command="python3 -m src.stock_report --write-import-staging",
                )
            )
        elif not row.peer_ready:
            actions.append(
                OnboardingAction(
                    priority=3,
                    ticker=row.ticker,
                    dataset="peers",
                    status="partial",
                    reason=row.missing_required_for_peer_relative or "Peer mappings exist but peer valuation inputs are incomplete.",
                    recommended_action="Add local fundamentals and prices or market-cap context for mapped peers.",
                    target_file="data/fundamentals.csv, data/prices.csv",
                    example_command="python3 -m src.stock_report --validate-local-data",
                )
            )
        if not row.has_earnings:
            actions.append(
                OnboardingAction(
                    priority=4,
                    ticker=row.ticker,
                    dataset="earnings",
                    status="optional_missing",
                    reason="No local earnings row is configured.",
                    recommended_action="Add earnings manually only from a trusted source.",
                    target_file="data/imports/earnings.csv",
                    example_command="python3 -m src.data_onboarding --write-templates",
                )
            )
        if not row.has_analyst_estimates:
            actions.append(
                OnboardingAction(
                    priority=5,
                    ticker=row.ticker,
                    dataset="analyst_estimates",
                    status="optional_missing",
                    reason="No local analyst-estimate row is configured.",
                    recommended_action="Leave analyst_estimates missing unless a trusted source exists.",
                    target_file="data/imports/analyst_estimates.csv",
                    example_command="python3 -m src.data_onboarding --write-templates",
                )
            )
    actions.append(
        OnboardingAction(
            priority=6,
            ticker="",
            dataset="smh_holdings",
            status="manual_fallback_available",
            reason="SMH remote holdings can be unavailable because of redirect/cookie/location handling.",
            recommended_action="Use data/custom_universe.csv if the SMH source is unavailable.",
            target_file="data/custom_universe.csv",
            example_command="python3 -m src.data_onboarding --write-templates",
        )
    )
    return sorted(actions, key=lambda item: (item.priority, item.ticker, item.dataset))


def build_data_coverage_wizard(coverage_rows: list[TickerCoverage]) -> list[DataCoverageWizardRow]:
    rows: list[DataCoverageWizardRow] = []
    for row in coverage_rows:
        price_command = f"python3 -m src.data_update --tickers {row.ticker}"
        price_action = (
            f"Refresh {row.ticker} prices, or normalize verified downloaded OHLCV rows into "
            "data/imports/prices.csv before validate/preview/apply."
        )
        if not row.usable_for_momentum:
            rows.append(
                DataCoverageWizardRow(
                    priority=1,
                    ticker=row.ticker,
                    unlock_goal="Unlock Monthly Picks",
                    blocking_dataset="prices",
                    current_status=row.missing_required_for_momentum or f"{row.price_history_days} local price rows",
                    why_it_matters="Monthly ranking needs enough verified local price history for momentum and setup context.",
                    recommended_action=price_action,
                    target_file="data/imports/prices.csv",
                    example_command=price_command,
                    safe_next_step="Use make price-normalize for downloaded CSVs, then make price-validate and make price-preview before applying.",
                )
            )
        if row.price_history_days < 63:
            rows.append(
                DataCoverageWizardRow(
                    priority=1,
                    ticker=row.ticker,
                    unlock_goal="Unlock Track Record",
                    blocking_dataset="prices",
                    current_status=f"{row.price_history_days} local price rows",
                    why_it_matters="Track-record comparisons need longer dated local history for picks and benchmark returns.",
                    recommended_action=price_action,
                    target_file="data/imports/prices.csv",
                    example_command=price_command,
                    safe_next_step="Add verified historical OHLCV rows locally; do not infer or backfill synthetic returns.",
                )
            )
        if not row.usable_for_dcf:
            rows.append(
                DataCoverageWizardRow(
                    priority=2,
                    ticker=row.ticker,
                    unlock_goal="Unlock DCF",
                    blocking_dataset="fundamentals",
                    current_status=row.missing_required_for_dcf or "DCF inputs incomplete",
                    why_it_matters="DCF needs free cash flow or revenue plus FCF margin, and shares outstanding.",
                    recommended_action="Run SEC staging for candidate fundamentals, then validate and preview before applying.",
                    target_file="data/imports/fundamentals.csv",
                    example_command=f"python3 -m src.stock_report --sec-stage-fundamentals --tickers {row.ticker}",
                    safe_next_step="Review staged SEC-derived fields before import merge; leave unavailable fields blank.",
                )
            )
        if not row.usable_for_peer_relative:
            rows.append(
                DataCoverageWizardRow(
                    priority=3,
                    ticker=row.ticker,
                    unlock_goal="Unlock Peer Relative",
                    blocking_dataset="peers",
                    current_status=row.missing_required_for_peer_relative or "Peer-relative inputs incomplete",
                    why_it_matters="Peer-relative valuation needs manual peer mappings plus peer fundamentals and price or market-cap context.",
                    recommended_action="Add manually researched peer mappings and peer data through local CSV imports.",
                    target_file="data/imports/peers.csv",
                    example_command="python3 -m src.data_onboarding --write-templates",
                    safe_next_step="Use data/imports/peers.csv for mappings; never fabricate peer relationships.",
                )
            )
        if not row.has_earnings:
            rows.append(
                DataCoverageWizardRow(
                    priority=4,
                    ticker=row.ticker,
                    unlock_goal="Add Earnings Context",
                    blocking_dataset="earnings",
                    current_status="optional local earnings row missing",
                    why_it_matters="Earnings context improves the stock report but does not block core ranking or valuation.",
                    recommended_action="Add earnings rows manually only from a trusted source.",
                    target_file="data/imports/earnings.csv",
                    example_command="python3 -m src.data_onboarding --write-templates",
                    safe_next_step="Leave earnings blank when no trusted local source exists.",
                )
            )
        if not row.has_analyst_estimates:
            rows.append(
                DataCoverageWizardRow(
                    priority=5,
                    ticker=row.ticker,
                    unlock_goal="Add Analyst Estimate Context",
                    blocking_dataset="analyst_estimates",
                    current_status="optional local analyst-estimate row missing",
                    why_it_matters="Estimate context is optional and should not be treated as a recommendation.",
                    recommended_action="Add analyst estimates only if you have a trusted local source.",
                    target_file="data/imports/analyst_estimates.csv",
                    example_command="python3 -m src.data_onboarding --write-templates",
                    safe_next_step="It is safe to leave analyst estimates missing.",
                )
            )
    return sorted(rows, key=lambda item: (item.priority, item.unlock_goal, item.ticker, item.blocking_dataset))


def build_price_import_worklist(
    coverage_rows: list[TickerCoverage],
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> list[PriceWorklistRow]:
    root = resolve_project_root(project_root)
    data_path = resolve_data_dir(data_dir, root)
    output_path = resolve_outputs_dir(output_dir, root)
    catalog = LocalDataCatalog(root, data_dir=data_path, outputs_dir=output_path)
    prices = _load_frame(catalog, "prices")

    rows: list[PriceWorklistRow] = []
    for coverage in coverage_rows:
        first_local_date, latest_local_date = _price_date_bounds(prices, coverage.ticker)
        momentum_ready = coverage.price_history_days >= 21
        track_record_ready = coverage.price_history_days >= 63
        preferred_history_ready = coverage.price_history_days >= 252
        missing_for_momentum = "" if momentum_ready else f"{max(0, 21 - coverage.price_history_days)} more verified rows needed"
        missing_for_track_record = "" if track_record_ready else f"{max(0, 63 - coverage.price_history_days)} more verified rows needed"
        missing_for_preferred_history = "" if preferred_history_ready else f"{max(0, 252 - coverage.price_history_days)} more verified rows needed"
        priority = 1 if not momentum_ready else 2 if not track_record_ready else 3 if not preferred_history_ready else 4
        if not momentum_ready:
            next_price_goal = "Unlock Monthly Picks"
            next_target_history_rows = 21
        elif not track_record_ready:
            next_price_goal = "Unlock Track Record"
            next_target_history_rows = 63
        elif not preferred_history_ready:
            next_price_goal = "Reach Preferred 1Y History"
            next_target_history_rows = 252
        else:
            next_price_goal = "Maintain Coverage"
            next_target_history_rows = coverage.price_history_days
        rows_needed_for_next_goal = max(0, next_target_history_rows - coverage.price_history_days)
        suggested_start_date = ""
        buffer_days = max(30, int(next_target_history_rows * 1.5))
        if latest_local_date:
            latest_ts = pd.to_datetime(latest_local_date, errors="coerce")
            if pd.notna(latest_ts):
                suggested_start_date = str((latest_ts - pd.Timedelta(days=buffer_days)).date())
        if not suggested_start_date and next_target_history_rows > 0:
            suggested_start_date = str((pd.Timestamp.today().normalize() - pd.Timedelta(days=buffer_days)).date())
        rows.append(
            PriceWorklistRow(
                priority=priority,
                ticker=coverage.ticker,
                has_prices=coverage.has_prices,
                price_history_days=coverage.price_history_days,
                first_local_date=first_local_date,
                latest_local_date=latest_local_date,
                next_price_goal=next_price_goal,
                next_target_history_rows=next_target_history_rows,
                rows_needed_for_next_goal=rows_needed_for_next_goal,
                suggested_start_date=suggested_start_date,
                momentum_ready=momentum_ready,
                track_record_ready=track_record_ready,
                preferred_history_ready=preferred_history_ready,
                missing_for_momentum=missing_for_momentum,
                missing_for_track_record=missing_for_track_record,
                missing_for_preferred_history=missing_for_preferred_history,
                recommended_action=(
                    f"Run python3 -m src.data_update --tickers {coverage.ticker}, or normalize verified downloaded OHLCV files into data/imports/prices.csv."
                ),
                target_file="data/imports/prices.csv",
                example_command=f"make price-normalize INPUT=data/raw/prices/{coverage.ticker}.csv TICKER={coverage.ticker} SOURCE=yahoo_manual",
                safe_next_step="Run make price-validate and make price-preview before make price-apply; do not fabricate missing history.",
            )
        )
    return sorted(rows, key=lambda item: (item.priority, item.price_history_days, item.ticker))


def build_fundamentals_peer_worklist(coverage_rows: list[TickerCoverage]) -> list[FundamentalsPeerWorklistRow]:
    rows: list[FundamentalsPeerWorklistRow] = []
    for coverage in coverage_rows:
        if coverage.dcf_ready and coverage.peer_ready:
            priority = 4
            recommended_action = "Coverage is already sufficient for DCF and peer-relative local research."
        elif not coverage.dcf_ready:
            priority = 1
            recommended_action = "Run SEC staging for fundamentals, then validate and preview before applying."
        elif not coverage.has_peer_mapping or not coverage.peer_ready:
            priority = 2
            recommended_action = "Add manually researched peer mappings and fill peer fundamentals/prices through local CSV imports."
        else:
            priority = 3
            recommended_action = "Review local fundamentals and peer inputs for completeness."

        target_file = "data/imports/fundamentals.csv" if not coverage.dcf_ready else "data/imports/peers.csv"
        example_command = (
            f"python3 -m src.stock_report --sec-stage-fundamentals --tickers {coverage.ticker}"
            if not coverage.dcf_ready
            else "python3 -m src.data_onboarding --write-templates"
        )
        safe_next_step = (
            "Review staged SEC-derived fundamentals before import merge; keep unavailable fields blank."
            if not coverage.dcf_ready
            else "Use data/imports/peers.csv for manual peer mappings and keep peer-relative gaps explicit."
        )
        rows.append(
            FundamentalsPeerWorklistRow(
                priority=priority,
                ticker=coverage.ticker,
                has_fundamentals=coverage.has_fundamentals,
                dcf_ready=coverage.dcf_ready,
                has_peer_mapping=coverage.has_peer_mapping,
                peer_ready=coverage.peer_ready,
                missing_required_for_dcf=coverage.missing_required_for_dcf,
                missing_required_for_peer_relative=coverage.missing_required_for_peer_relative,
                recommended_action=recommended_action,
                target_file=target_file,
                example_command=example_command,
                safe_next_step=safe_next_step,
            )
        )
    return sorted(rows, key=lambda item: (item.priority, item.ticker))


def build_optional_context_worklist(coverage_rows: list[TickerCoverage]) -> list[OptionalContextWorklistRow]:
    rows: list[OptionalContextWorklistRow] = []
    for coverage in coverage_rows:
        missing_context: list[str] = []
        if not coverage.has_earnings:
            missing_context.append("earnings")
        if not coverage.has_analyst_estimates:
            missing_context.append("analyst_estimates")

        if not missing_context:
            priority = 7
            recommended_action = "Optional context is already available locally."
            target_file = ""
            example_command = ""
            safe_next_step = "No optional context action is required for this ticker."
        else:
            priority = 5 if len(missing_context) == 2 else 6
            if missing_context == ["earnings"]:
                recommended_action = "Add local earnings rows only if you have a trusted source."
                target_file = "data/imports/earnings.csv"
            elif missing_context == ["analyst_estimates"]:
                recommended_action = "Add analyst estimates only if you have a trusted local source."
                target_file = "data/imports/analyst_estimates.csv"
            else:
                recommended_action = "Optional earnings and analyst-estimate context are missing; add them only from trusted local sources."
                target_file = "data/imports/earnings.csv and data/imports/analyst_estimates.csv"
            example_command = "python3 -m src.data_onboarding --write-templates"
            safe_next_step = "It is safe to leave optional context missing until you have verified local data."

        rows.append(
            OptionalContextWorklistRow(
                priority=priority,
                ticker=coverage.ticker,
                has_earnings=coverage.has_earnings,
                has_analyst_estimates=coverage.has_analyst_estimates,
                earnings_context_ready=coverage.has_earnings,
                estimate_context_ready=coverage.has_analyst_estimates,
                missing_optional_context=", ".join(missing_context),
                recommended_action=recommended_action,
                target_file=target_file,
                example_command=example_command,
                safe_next_step=safe_next_step,
            )
        )
    return sorted(rows, key=lambda item: (item.priority, item.ticker))


def build_sec_stage_queue(
    coverage_rows: list[TickerCoverage],
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> list[SecStageQueueRow]:
    context_lookup = _ticker_context_lookup(project_root, data_dir=data_dir, output_dir=output_dir)
    rows: list[SecStageQueueRow] = []
    for coverage in coverage_rows:
        if coverage.dcf_ready:
            continue
        context = context_lookup.get(coverage.ticker, {})
        is_holding = bool(context.get("is_holding", False))
        theme = str(context.get("theme", "") or "Unclassified")
        sector_etf = str(context.get("sector_etf", "") or "Unclassified")
        if is_holding and coverage.usable_for_momentum:
            priority = 1
        elif coverage.usable_for_momentum:
            priority = 2
        elif is_holding:
            priority = 3
        else:
            priority = 4
        recommended_action = (
            "Run SEC staging for fundamentals so DCF assumptions can be reviewed from explicit local inputs."
            if not coverage.has_fundamentals
            else "Stage or add richer verified fundamentals to close the remaining DCF input gaps."
        )
        rows.append(
            SecStageQueueRow(
                priority=priority,
                ticker=coverage.ticker,
                is_holding=is_holding,
                theme=theme,
                sector_etf=sector_etf,
                price_history_days=coverage.price_history_days,
                has_fundamentals=coverage.has_fundamentals,
                dcf_ready=coverage.dcf_ready,
                missing_required_for_dcf=coverage.missing_required_for_dcf,
                recommended_action=recommended_action,
                target_file="data/imports/fundamentals.csv",
                example_command=f"python3 -m src.stock_report --sec-stage-fundamentals --tickers {coverage.ticker}",
                safe_next_step="Validate and preview staged fundamentals before apply; keep unavailable valuation fields blank.",
            )
        )
    return sorted(rows, key=lambda item: (item.priority, -item.price_history_days, item.ticker))


def build_peer_mapping_queue(
    coverage_rows: list[TickerCoverage],
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> list[PeerMappingQueueRow]:
    context_lookup = _ticker_context_lookup(project_root, data_dir=data_dir, output_dir=output_dir)
    rows: list[PeerMappingQueueRow] = []
    for coverage in coverage_rows:
        if coverage.peer_ready:
            continue
        context = context_lookup.get(coverage.ticker, {})
        is_holding = bool(context.get("is_holding", False))
        theme = str(context.get("theme", "") or "Unclassified")
        sector_etf = str(context.get("sector_etf", "") or "Unclassified")
        if coverage.dcf_ready and is_holding:
            priority = 1
        elif coverage.dcf_ready:
            priority = 2
        elif coverage.has_peer_mapping:
            priority = 3
        else:
            priority = 4
        recommended_action = (
            "Add manually researched peer mappings for this ticker and keep peer-relative comparison transparent."
            if not coverage.has_peer_mapping
            else "Peer mappings exist, but local peer fundamentals or price context are still missing."
        )
        rows.append(
            PeerMappingQueueRow(
                priority=priority,
                ticker=coverage.ticker,
                is_holding=is_holding,
                theme=theme,
                sector_etf=sector_etf,
                has_peer_mapping=coverage.has_peer_mapping,
                dcf_ready=coverage.dcf_ready,
                peer_ready=coverage.peer_ready,
                missing_required_for_peer_relative=coverage.missing_required_for_peer_relative,
                recommended_action=recommended_action,
                target_file="data/imports/peers.csv",
                example_command="python3 -m src.data_onboarding --write-templates",
                safe_next_step="Use only manually researched peers, then validate and preview before apply; do not guess peer sets.",
            )
        )
    return sorted(rows, key=lambda item: (item.priority, not item.is_holding, item.ticker))


def build_ticker_unlock_ladder(coverage_rows: list[TickerCoverage]) -> list[TickerUnlockLadderRow]:
    rows: list[TickerUnlockLadderRow] = []
    for coverage in coverage_rows:
        if coverage.usable_for_momentum and coverage.price_history_days >= 252:
            price_stage_status = "preferred_history_ready"
        elif coverage.usable_for_momentum:
            price_stage_status = "momentum_ready_short_history"
        elif coverage.has_prices:
            price_stage_status = "partial_price_history"
        else:
            price_stage_status = "missing_prices"

        dcf_stage_status = "dcf_ready" if coverage.dcf_ready else "dcf_blocked"
        if coverage.peer_ready:
            peer_stage_status = "peer_ready"
        elif coverage.has_peer_mapping:
            peer_stage_status = "peer_mapping_present_context_missing"
        else:
            peer_stage_status = "peer_mapping_missing"

        if coverage.has_earnings and coverage.has_analyst_estimates:
            optional_context_status = "fully_available"
        elif coverage.has_earnings or coverage.has_analyst_estimates:
            optional_context_status = "partially_available"
        else:
            optional_context_status = "missing_optional_context"

        if not coverage.usable_for_momentum:
            current_unlock_stage = "prices"
            next_unlock_goal = "Unlock Monthly Picks"
            recommended_action = "Add more verified local price history before working on deeper research context."
            target_file = "data/imports/prices.csv"
            example_command = f"python3 -m src.data_update --tickers {coverage.ticker}"
            safe_next_step = "Use data/raw/prices/ plus price normalize/validate/preview/apply when the free source is unreliable."
        elif not coverage.dcf_ready:
            current_unlock_stage = "fundamentals"
            next_unlock_goal = "Unlock DCF"
            recommended_action = "Stage or add verified fundamentals so DCF inputs are explicit and reviewable."
            target_file = "data/imports/fundamentals.csv"
            example_command = f"python3 -m src.stock_report --sec-stage-fundamentals --tickers {coverage.ticker}"
            safe_next_step = "Review staged SEC-derived fundamentals before import merge and keep unavailable fields blank."
        elif not coverage.peer_ready:
            current_unlock_stage = "peers"
            next_unlock_goal = "Unlock Peer Relative"
            recommended_action = "Add manual peer mappings and make sure peer price/fundamental context exists locally."
            target_file = "data/imports/peers.csv"
            example_command = "python3 -m src.data_onboarding --write-templates"
            safe_next_step = "Use manually researched peers only; missing peer context should stay explicit."
        elif not coverage.has_earnings or not coverage.has_analyst_estimates:
            current_unlock_stage = "optional_context"
            next_unlock_goal = "Add Optional Context"
            recommended_action = "Add earnings or analyst-estimate rows only if you have trusted local sources."
            target_file = (
                "data/imports/earnings.csv"
                if not coverage.has_earnings and coverage.has_analyst_estimates
                else "data/imports/analyst_estimates.csv"
                if coverage.has_earnings and not coverage.has_analyst_estimates
                else "data/imports/earnings.csv and data/imports/analyst_estimates.csv"
            )
            example_command = "python3 -m src.data_onboarding --write-templates"
            safe_next_step = "It is safe to leave optional context missing until you have verified local data."
        else:
            current_unlock_stage = "ready"
            next_unlock_goal = "Maintain Coverage"
            recommended_action = "Core local research coverage is already in place for this ticker."
            target_file = ""
            example_command = ""
            safe_next_step = "Refresh prices and staged fundamentals only as real local data changes."

        rows.append(
            TickerUnlockLadderRow(
                ticker=coverage.ticker,
                price_stage_status=price_stage_status,
                price_history_days=coverage.price_history_days,
                dcf_stage_status=dcf_stage_status,
                peer_stage_status=peer_stage_status,
                optional_context_status=optional_context_status,
                current_unlock_stage=current_unlock_stage,
                next_unlock_goal=next_unlock_goal,
                recommended_action=recommended_action,
                target_file=target_file,
                example_command=example_command,
                safe_next_step=safe_next_step,
            )
        )
    stage_rank = {"prices": 1, "fundamentals": 2, "peers": 3, "optional_context": 4, "ready": 5}
    return sorted(rows, key=lambda item: (stage_rank.get(item.current_unlock_stage, 99), item.ticker))


def build_unlock_priority_summary(
    coverage_rows: list[TickerCoverage],
    ticker_unlock_ladder: list[TickerUnlockLadderRow],
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> list[UnlockPrioritySummaryRow]:
    root = resolve_project_root(project_root)
    data_path = resolve_data_dir(data_dir, root)
    output_path = resolve_outputs_dir(output_dir, root)
    catalog = LocalDataCatalog(root, data_dir=data_path, outputs_dir=output_path)
    universe = _load_frame(catalog, "universe")
    holdings = _load_frame(catalog, "holdings")

    universe_lookup = _normalize_column_lookup(universe)
    holdings_lookup = _normalize_column_lookup(holdings)
    universe_ticker_col = universe_lookup.get("ticker")
    holdings_ticker_col = holdings_lookup.get("ticker")
    theme_col = universe_lookup.get("theme")
    sector_col = universe_lookup.get("sectoretf") or universe_lookup.get("sector_etf")

    holding_tickers = _ticker_set(holdings, holdings_ticker_col or "ticker")
    context_rows: list[dict[str, Any]] = []
    ladder_map = {row.ticker: row for row in ticker_unlock_ladder}

    for coverage in coverage_rows:
        ladder = ladder_map[coverage.ticker]
        universe_row = (
            universe.loc[universe[universe_ticker_col].astype(str).str.upper().str.strip() == coverage.ticker].iloc[-1]
            if universe_ticker_col and not universe.empty and not universe.loc[universe[universe_ticker_col].astype(str).str.upper().str.strip() == coverage.ticker].empty
            else pd.Series(dtype=object)
        )
        theme = str(universe_row.get(theme_col, "")).strip() if theme_col else ""
        sector_etf = str(universe_row.get(sector_col, "")).strip() if sector_col else ""
        context_rows.append(
            {
                "ticker": coverage.ticker,
                "is_holding": coverage.ticker in holding_tickers,
                "theme": theme or "Unclassified",
                "sector_etf": sector_etf or "Unclassified",
                "stage": ladder.current_unlock_stage,
            }
        )

    context_frame = pd.DataFrame(context_rows)
    if context_frame.empty:
        return []

    stage_goal = {
        "prices": "Unlock Monthly Picks",
        "fundamentals": "Unlock DCF",
        "peers": "Unlock Peer Relative",
        "optional_context": "Add Optional Context",
        "ready": "Maintain Coverage",
    }
    stage_action = {
        "prices": "Fill verified local price history first; it unlocks the broadest research workflow.",
        "fundamentals": "Stage or add verified fundamentals for the blocked names in this group.",
        "peers": "Add manually researched peer mappings and peer context for this group.",
        "optional_context": "Add earnings or analyst estimates only if you have trusted local sources.",
        "ready": "Coverage in this group is already broadly usable; maintain it with normal refreshes.",
    }
    stage_order = ["prices", "fundamentals", "peers", "optional_context", "ready"]

    summaries: list[UnlockPrioritySummaryRow] = []

    def add_group(group_type: str, group_name: str, frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        stage_counts = {stage: int(frame["stage"].eq(stage).sum()) for stage in stage_order}
        top_stage = next((stage for stage in stage_order if stage_counts[stage] > 0), "ready")
        representative = ", ".join(frame.sort_values(["is_holding", "ticker"], ascending=[False, True])["ticker"].head(5).tolist())
        summaries.append(
            UnlockPrioritySummaryRow(
                group_type=group_type,
                group_name=group_name,
                ticker_count=int(len(frame)),
                holdings_count=int(frame["is_holding"].sum()),
                price_stage_count=stage_counts["prices"],
                fundamentals_stage_count=stage_counts["fundamentals"],
                peer_stage_count=stage_counts["peers"],
                optional_stage_count=stage_counts["optional_context"],
                ready_stage_count=stage_counts["ready"],
                top_priority_stage=top_stage,
                next_unlock_goal=stage_goal[top_stage],
                representative_tickers=representative,
                recommended_action=stage_action[top_stage],
            )
        )

    if context_frame["is_holding"].any():
        add_group("holdings", "Current Holdings", context_frame.loc[context_frame["is_holding"]].copy())
    for theme, frame in context_frame.groupby("theme", dropna=False):
        add_group("theme", str(theme), frame.copy())
    for sector_etf, frame in context_frame.groupby("sector_etf", dropna=False):
        add_group("sector_etf", str(sector_etf), frame.copy())

    group_rank = {"holdings": 1, "theme": 2, "sector_etf": 3}
    stage_rank = {stage: index + 1 for index, stage in enumerate(stage_order)}
    return sorted(
        summaries,
        key=lambda item: (
            group_rank.get(item.group_type, 99),
            stage_rank.get(item.top_priority_stage, 99),
            -item.holdings_count,
            -item.ticker_count,
            item.group_name,
        ),
    )


def build_command_bundles(
    coverage_rows: list[TickerCoverage],
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> list[CommandBundleRow]:
    context_lookup = _ticker_context_lookup(project_root, data_dir=data_dir, output_dir=output_dir)
    price_worklist = build_price_import_worklist(coverage_rows, project_root, data_dir=data_dir, output_dir=output_dir)
    sec_queue = build_sec_stage_queue(coverage_rows, project_root, data_dir=data_dir, output_dir=output_dir)
    peer_queue = build_peer_mapping_queue(coverage_rows, project_root, data_dir=data_dir, output_dir=output_dir)

    holdings_first_prices: list[PriceWorklistRow] = []
    broader_price_queue: list[PriceWorklistRow] = []
    for price_row in price_worklist:
        if price_row.momentum_ready:
            continue
        context = context_lookup.get(price_row.ticker, {})
        if bool(context.get("is_holding", False)):
            holdings_first_prices.append(price_row)
        else:
            broader_price_queue.append(price_row)

    holdings_first_prices.sort(key=lambda item: (item.price_history_days > 0, item.price_history_days, item.ticker))
    broader_price_queue.sort(key=lambda item: (item.price_history_days > 0, item.price_history_days, item.ticker))
    price_targets = holdings_first_prices[:5] or broader_price_queue[:5]

    holdings_sec = [row for row in sec_queue if row.is_holding][:5]
    sec_targets = holdings_sec or sec_queue[:5]
    holdings_peer = [row for row in peer_queue if row.is_holding][:5]
    peer_targets = holdings_peer or peer_queue[:5]

    bundles: list[CommandBundleRow] = []

    if price_targets:
        tickers = ",".join(row.ticker for row in price_targets)
        scope = "holdings_first" if any(bool(context_lookup.get(row.ticker, {}).get("is_holding", False)) for row in price_targets) else "broader_queue"
        goal_counts = Counter(row.next_price_goal for row in price_targets if row.next_price_goal and row.next_price_goal != "Maintain Coverage")
        target_history_rows = max((int(row.next_target_history_rows) for row in price_targets), default=0)
        start_dates = sorted(date for date in (str(row.suggested_start_date or "").strip() for row in price_targets) if date)
        suggested_start_date = start_dates[0] if start_dates else ""
        if goal_counts:
            goal_parts = [f"{goal} for {count} ticker{'s' if count != 1 else ''}" for goal, count in goal_counts.items()]
            total_rows_needed = sum(max(0, row.rows_needed_for_next_goal) for row in price_targets)
            goal_summary = "; ".join(goal_parts)
            if total_rows_needed:
                goal_summary = f"{goal_summary}; {total_rows_needed} verified rows still needed across this bundle"
        else:
            goal_summary = "Maintain local price coverage for this bundle"
        bundles.append(
            CommandBundleRow(
                bundle_name="Price Coverage Bundle",
                lane="prices",
                scope=scope,
                ticker_count=len(price_targets),
                tickers=tickers,
                goal_summary=goal_summary,
                target_history_rows=target_history_rows,
                suggested_start_date=suggested_start_date,
                primary_command=f"python3 -m src.data_update --tickers {tickers}",
                follow_up_command="make price-status",
                target_file="data/imports/prices.csv",
                why_it_matters="These tickers are still blocking monthly picks or broader local research because price history is missing or too short.",
                safe_next_step="If the free refresh fails, use data/raw/prices/ plus make price-normalize before price validate/preview/apply.",
            )
        )

    if sec_targets:
        tickers = ",".join(row.ticker for row in sec_targets)
        scope = "holdings_first" if any(row.is_holding for row in sec_targets) else "broader_queue"
        bundles.append(
            CommandBundleRow(
                bundle_name="SEC Fundamentals Bundle",
                lane="fundamentals",
                scope=scope,
                ticker_count=len(sec_targets),
                tickers=tickers,
                goal_summary="Advance explicit local DCF readiness for the listed tickers",
                target_history_rows=0,
                suggested_start_date="",
                primary_command=f"SEC_USER_AGENT='Name email@example.com' make sec-stage TICKERS={tickers}",
                follow_up_command="make sec-preview",
                target_file="data/imports/fundamentals.csv",
                why_it_matters="These tickers are the best next candidates for explicit local DCF inputs once price coverage is good enough.",
                safe_next_step="Keep SEC enrichment staged and review-only until validate/preview/apply confirms the merge.",
            )
        )

    if peer_targets:
        tickers = ",".join(row.ticker for row in peer_targets)
        scope = "holdings_first" if any(row.is_holding for row in peer_targets) else "broader_queue"
        bundles.append(
            CommandBundleRow(
                bundle_name="Peer Mapping Bundle",
                lane="peers",
                scope=scope,
                ticker_count=len(peer_targets),
                tickers=tickers,
                goal_summary="Advance transparent peer-relative readiness for the listed tickers",
                target_history_rows=0,
                suggested_start_date="",
                primary_command="make templates",
                follow_up_command="make onboarding",
                target_file="data/imports/peers.csv",
                why_it_matters="These tickers are closest to peer-relative coverage once manually researched peer mappings are added locally.",
                safe_next_step="Fill only manually researched peers for the listed tickers, then rerun onboarding to refresh readiness and action outputs.",
            )
        )

    lane_rank = {"prices": 1, "fundamentals": 2, "peers": 3}
    scope_rank = {"holdings_first": 1, "broader_queue": 2}
    return sorted(bundles, key=lambda item: (lane_rank.get(item.lane, 99), scope_rank.get(item.scope, 99), item.bundle_name))


def build_command_bundle_details(
    coverage_rows: list[TickerCoverage],
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> list[CommandBundleDetailRow]:
    context_lookup = _ticker_context_lookup(project_root, data_dir=data_dir, output_dir=output_dir)
    coverage_map = {row.ticker: row for row in coverage_rows}
    bundles = build_command_bundles(coverage_rows, project_root, data_dir=data_dir, output_dir=output_dir)
    ladder_map = {row.ticker: row for row in build_ticker_unlock_ladder(coverage_rows)}
    price_worklist_map = {
        row.ticker: row
        for row in build_price_import_worklist(coverage_rows, project_root, data_dir=data_dir, output_dir=output_dir)
    }

    details: list[CommandBundleDetailRow] = []
    for bundle in bundles:
        tickers = [ticker.strip().upper() for ticker in str(bundle.tickers).split(",") if ticker.strip()]
        for ticker in tickers:
            coverage = coverage_map.get(ticker)
            context = context_lookup.get(ticker, {})
            ladder = ladder_map.get(ticker)
            recommended_action = ""
            target_goal = ""
            rows_needed = 0
            if coverage is not None:
                if bundle.lane == "prices":
                    recommended_action = coverage.next_best_action
                    price_target = price_worklist_map.get(ticker)
                    if price_target is not None:
                        target_goal = price_target.next_price_goal
                        rows_needed = max(0, int(price_target.rows_needed_for_next_goal))
                        target_history_rows = max(0, int(price_target.next_target_history_rows))
                        suggested_start_date = str(price_target.suggested_start_date or "")
                    else:
                        target_history_rows = 0
                        suggested_start_date = ""
                elif bundle.lane == "fundamentals":
                    recommended_action = (
                        "Run SEC staging for fundamentals so DCF assumptions can be reviewed from explicit local inputs."
                        if not coverage.has_fundamentals
                        else "Stage or add richer verified fundamentals to close the remaining DCF input gaps."
                    )
                    target_goal = "Unlock DCF"
                    target_history_rows = 0
                    suggested_start_date = ""
                elif bundle.lane == "peers":
                    recommended_action = (
                        "Add manually researched peer mappings for this ticker and keep peer-relative comparison transparent."
                        if not coverage.has_peer_mapping
                        else "Peer mappings exist, but local peer fundamentals or price context are still missing."
                    )
                    target_goal = "Unlock Peer Relative"
                    target_history_rows = 0
                    suggested_start_date = ""
                else:
                    target_history_rows = 0
                    suggested_start_date = ""
            else:
                target_history_rows = 0
                suggested_start_date = ""
            details.append(
                CommandBundleDetailRow(
                    bundle_name=bundle.bundle_name,
                    lane=bundle.lane,
                    ticker=ticker,
                    is_holding=bool(context.get("is_holding", False)),
                    theme=str(context.get("theme", "") or "Unclassified"),
                    sector_etf=str(context.get("sector_etf", "") or "Unclassified"),
                    current_unlock_stage=str(getattr(ladder, "current_unlock_stage", "")),
                    target_goal=target_goal,
                    rows_needed=rows_needed,
                    target_history_rows=target_history_rows,
                    suggested_start_date=suggested_start_date,
                    recommended_action=recommended_action or bundle.why_it_matters,
                    primary_command=bundle.primary_command,
                    follow_up_command=bundle.follow_up_command,
                    target_file=bundle.target_file,
                    safe_next_step=bundle.safe_next_step,
                )
            )

    lane_rank = {"prices": 1, "fundamentals": 2, "peers": 3}
    return sorted(details, key=lambda item: (lane_rank.get(item.lane, 99), not item.is_holding, item.ticker))


def build_command_bundle_runbook(
    coverage_rows: list[TickerCoverage],
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> list[CommandBundleRunbookRow]:
    bundles = build_command_bundles(coverage_rows, project_root, data_dir=data_dir, output_dir=output_dir)
    runbook: list[CommandBundleRunbookRow] = []

    for bundle in bundles:
        steps = [
            (1, "Run bundle command", bundle.primary_command, bundle.safe_next_step),
            (2, "Review follow-up output", bundle.follow_up_command, bundle.safe_next_step),
            (
                3,
                "Refresh onboarding outputs",
                "make onboarding",
                "After the bundle flow finishes, reopen Data Health or Overview to confirm the updated local coverage state.",
            ),
        ]
        for step_order, step_label, command, safe_next_step in steps:
            runbook.append(
                CommandBundleRunbookRow(
                    bundle_name=bundle.bundle_name,
                    lane=bundle.lane,
                    scope=bundle.scope,
                    step_order=step_order,
                    step_label=step_label,
                    command=command,
                    target_file=bundle.target_file,
                    tickers=bundle.tickers,
                    goal_summary=bundle.goal_summary,
                    target_history_rows=bundle.target_history_rows,
                    suggested_start_date=bundle.suggested_start_date,
                    why_it_matters=bundle.why_it_matters,
                    safe_next_step=safe_next_step,
                )
            )

    lane_rank = {"prices": 1, "fundamentals": 2, "peers": 3}
    return sorted(runbook, key=lambda item: (lane_rank.get(item.lane, 99), item.step_order, item.bundle_name))


def build_onboarding_payload(
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
    tickers: list[str] | None = None,
) -> dict[str, Any]:
    coverage = build_ticker_coverage(project_root, data_dir=data_dir, output_dir=output_dir, tickers=tickers)
    actions = build_onboarding_actions(coverage)
    wizard = build_data_coverage_wizard(coverage)
    price_worklist = build_price_import_worklist(coverage, project_root, data_dir=data_dir, output_dir=output_dir)
    fundamentals_peer_worklist = build_fundamentals_peer_worklist(coverage)
    optional_context_worklist = build_optional_context_worklist(coverage)
    sec_stage_queue = build_sec_stage_queue(coverage, project_root, data_dir=data_dir, output_dir=output_dir)
    peer_mapping_queue = build_peer_mapping_queue(coverage, project_root, data_dir=data_dir, output_dir=output_dir)
    ticker_unlock_ladder = build_ticker_unlock_ladder(coverage)
    unlock_priority_summary = build_unlock_priority_summary(
        coverage,
        ticker_unlock_ladder,
        project_root,
        data_dir=data_dir,
        output_dir=output_dir,
    )
    command_bundles = build_command_bundles(coverage, project_root, data_dir=data_dir, output_dir=output_dir)
    command_bundle_details = build_command_bundle_details(coverage, project_root, data_dir=data_dir, output_dir=output_dir)
    command_bundle_runbook = build_command_bundle_runbook(coverage, project_root, data_dir=data_dir, output_dir=output_dir)
    return {
        "ticker_coverage": [row.to_dict() for row in coverage],
        "onboarding_actions": [row.to_dict() for row in actions],
        "data_coverage_wizard": [row.to_dict() for row in wizard],
        "price_import_worklist": [row.to_dict() for row in price_worklist],
        "fundamentals_peer_worklist": [row.to_dict() for row in fundamentals_peer_worklist],
        "optional_context_worklist": [row.to_dict() for row in optional_context_worklist],
        "sec_stage_queue": [row.to_dict() for row in sec_stage_queue],
        "peer_mapping_queue": [row.to_dict() for row in peer_mapping_queue],
        "ticker_unlock_ladder": [row.to_dict() for row in ticker_unlock_ladder],
        "unlock_priority_summary": [row.to_dict() for row in unlock_priority_summary],
        "command_bundles": [row.to_dict() for row in command_bundles],
        "command_bundle_details": [row.to_dict() for row in command_bundle_details],
        "command_bundle_runbook": [row.to_dict() for row in command_bundle_runbook],
    }


def write_onboarding_outputs(
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
    tickers: list[str] | None = None,
) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    output_path = resolve_outputs_dir(output_dir, root)
    payload = build_onboarding_payload(root, data_dir=data_dir, output_dir=output_path, tickers=tickers)
    output_path.mkdir(parents=True, exist_ok=True)
    coverage_path = output_path / "ticker_data_coverage.csv"
    actions_path = output_path / "data_onboarding_actions.csv"
    wizard_path = output_path / "data_coverage_wizard.csv"
    price_worklist_path = output_path / "price_import_worklist.csv"
    fundamentals_peer_worklist_path = output_path / "fundamentals_peer_worklist.csv"
    optional_context_worklist_path = output_path / "optional_context_worklist.csv"
    sec_stage_queue_path = output_path / "sec_stage_queue.csv"
    peer_mapping_queue_path = output_path / "peer_mapping_queue.csv"
    ticker_unlock_ladder_path = output_path / "ticker_unlock_ladder.csv"
    unlock_priority_summary_path = output_path / "unlock_priority_summary.csv"
    command_bundles_path = output_path / "command_bundles.csv"
    command_bundle_details_path = output_path / "command_bundle_details.csv"
    command_bundle_runbook_path = output_path / "command_bundle_runbook.csv"
    pd.DataFrame(payload["ticker_coverage"], columns=COVERAGE_COLUMNS).to_csv(coverage_path, index=False)
    pd.DataFrame(payload["onboarding_actions"], columns=ACTION_COLUMNS).to_csv(actions_path, index=False)
    pd.DataFrame(payload["data_coverage_wizard"], columns=WIZARD_COLUMNS).to_csv(wizard_path, index=False)
    pd.DataFrame(payload["price_import_worklist"], columns=PRICE_WORKLIST_COLUMNS).to_csv(price_worklist_path, index=False)
    pd.DataFrame(payload["fundamentals_peer_worklist"], columns=FUNDAMENTALS_PEER_WORKLIST_COLUMNS).to_csv(
        fundamentals_peer_worklist_path, index=False
    )
    pd.DataFrame(payload["optional_context_worklist"], columns=OPTIONAL_CONTEXT_WORKLIST_COLUMNS).to_csv(
        optional_context_worklist_path, index=False
    )
    pd.DataFrame(payload["sec_stage_queue"], columns=SEC_STAGE_QUEUE_COLUMNS).to_csv(sec_stage_queue_path, index=False)
    pd.DataFrame(payload["peer_mapping_queue"], columns=PEER_MAPPING_QUEUE_COLUMNS).to_csv(peer_mapping_queue_path, index=False)
    pd.DataFrame(payload["ticker_unlock_ladder"], columns=TICKER_UNLOCK_LADDER_COLUMNS).to_csv(
        ticker_unlock_ladder_path, index=False
    )
    pd.DataFrame(payload["unlock_priority_summary"], columns=UNLOCK_PRIORITY_SUMMARY_COLUMNS).to_csv(
        unlock_priority_summary_path, index=False
    )
    pd.DataFrame(payload["command_bundles"], columns=COMMAND_BUNDLE_COLUMNS).to_csv(command_bundles_path, index=False)
    pd.DataFrame(payload["command_bundle_details"], columns=COMMAND_BUNDLE_DETAIL_COLUMNS).to_csv(command_bundle_details_path, index=False)
    pd.DataFrame(payload["command_bundle_runbook"], columns=COMMAND_BUNDLE_RUNBOOK_COLUMNS).to_csv(
        command_bundle_runbook_path, index=False
    )
    return {
        **payload,
        "coverage_path": str(coverage_path),
        "actions_path": str(actions_path),
        "wizard_path": str(wizard_path),
        "price_worklist_path": str(price_worklist_path),
        "fundamentals_peer_worklist_path": str(fundamentals_peer_worklist_path),
        "optional_context_worklist_path": str(optional_context_worklist_path),
        "sec_stage_queue_path": str(sec_stage_queue_path),
        "peer_mapping_queue_path": str(peer_mapping_queue_path),
        "ticker_unlock_ladder_path": str(ticker_unlock_ladder_path),
        "unlock_priority_summary_path": str(unlock_priority_summary_path),
        "command_bundles_path": str(command_bundles_path),
        "command_bundle_details_path": str(command_bundle_details_path),
        "command_bundle_runbook_path": str(command_bundle_runbook_path),
    }


def _template_columns(dataset_name: str) -> list[str]:
    if dataset_name == "prices":
        return PRICE_TEMPLATE_COLUMNS
    schema = LOCAL_DATASET_SCHEMAS[dataset_name]
    columns = list(schema.required_columns)
    for column in schema.optional_columns:
        if column not in columns:
            columns.append(column)
    return columns


def write_onboarding_templates(
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
) -> list[dict[str, Any]]:
    root = resolve_project_root(project_root)
    data_path = resolve_data_dir(data_dir, root)
    template_dir = data_path / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for dataset_name in TEMPLATE_DATASETS:
        path = template_dir / f"{dataset_name}.csv"
        columns = _template_columns(dataset_name)
        created = False
        if not path.exists():
            path.write_text(",".join(columns) + "\n", encoding="utf-8")
            created = True
        results.append(
            {
                "dataset_name": dataset_name,
                "path": str(path),
                "status": "created" if created else "skipped_existing",
                "columns": columns,
                "notes": "Header-only template; fill with verified local research data only.",
            }
        )
    return results


def _parse_tickers(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [ticker.strip().upper() for ticker in value.split(",") if ticker.strip()]


def _print_coverage(payload: dict[str, Any]) -> None:
    print("Ticker coverage:")
    for row in payload["ticker_coverage"]:
        print(
            f"- {row['ticker']}: prices={row['has_prices']} days={row['price_history_days']} "
            f"dcf_ready={row['dcf_ready']} peer_ready={row['peer_ready']} next={row['next_best_action']}"
        )
    print(f"Onboarding actions: {len(payload['onboarding_actions'])}")
    for row in payload["onboarding_actions"][:20]:
        ticker = f" {row['ticker']}" if row["ticker"] else ""
        print(f"- P{row['priority']} {row['dataset']}{ticker}: {row['recommended_action']}")


def _print_wizard(payload: dict[str, Any]) -> None:
    print("Data coverage wizard:")
    for row in payload["data_coverage_wizard"][:30]:
        ticker = f" {row['ticker']}" if row["ticker"] else ""
        print(
            f"- P{row['priority']} {row['unlock_goal']}{ticker}: "
            f"{row['blocking_dataset']} - {row['recommended_action']}"
        )
    print(f"Wizard rows: {len(payload['data_coverage_wizard'])}")


def _print_price_worklist(payload: dict[str, Any]) -> None:
    print("Price import worklist:")
    for row in payload["price_import_worklist"][:30]:
        print(
            f"- P{row['priority']} {row['ticker']}: {row['price_history_days']} rows, "
            f"momentum_ready={row['momentum_ready']} track_record_ready={row['track_record_ready']} "
            f"preferred_history_ready={row['preferred_history_ready']}"
        )
        print(f"  next: {row['recommended_action']}")
    print(f"Price worklist rows: {len(payload['price_import_worklist'])}")


def _print_fundamentals_peer_worklist(payload: dict[str, Any]) -> None:
    print("Fundamentals and peer worklist:")
    for row in payload["fundamentals_peer_worklist"][:30]:
        print(
            f"- P{row['priority']} {row['ticker']}: dcf_ready={row['dcf_ready']} "
            f"peer_ready={row['peer_ready']} missing_dcf={row['missing_required_for_dcf'] or '-'} "
            f"missing_peer={row['missing_required_for_peer_relative'] or '-'}"
        )
        print(f"  next: {row['recommended_action']}")
    print(f"Fundamentals/peer worklist rows: {len(payload['fundamentals_peer_worklist'])}")


def _print_optional_context_worklist(payload: dict[str, Any]) -> None:
    print("Optional context worklist:")
    for row in payload["optional_context_worklist"][:30]:
        print(
            f"- P{row['priority']} {row['ticker']}: earnings={row['has_earnings']} "
            f"estimates={row['has_analyst_estimates']} missing={row['missing_optional_context'] or '-'}"
        )
        print(f"  next: {row['recommended_action']}")
    print(f"Optional context worklist rows: {len(payload['optional_context_worklist'])}")


def _print_sec_stage_queue(payload: dict[str, Any]) -> None:
    print("SEC stage queue:")
    for row in payload["sec_stage_queue"][:30]:
        print(
            f"- P{row['priority']} {row['ticker']}: holding={row['is_holding']} "
            f"days={row['price_history_days']} has_fundamentals={row['has_fundamentals']} "
            f"missing_dcf={row['missing_required_for_dcf'] or '-'}"
        )
        print(f"  next: {row['recommended_action']}")
    print(f"SEC stage queue rows: {len(payload['sec_stage_queue'])}")


def _print_peer_mapping_queue(payload: dict[str, Any]) -> None:
    print("Peer mapping queue:")
    for row in payload["peer_mapping_queue"][:30]:
        print(
            f"- P{row['priority']} {row['ticker']}: holding={row['is_holding']} "
            f"dcf_ready={row['dcf_ready']} has_peer_mapping={row['has_peer_mapping']} "
            f"missing_peer={row['missing_required_for_peer_relative'] or '-'}"
        )
        print(f"  next: {row['recommended_action']}")
    print(f"Peer mapping queue rows: {len(payload['peer_mapping_queue'])}")


def _print_ticker_unlock_ladder(payload: dict[str, Any]) -> None:
    print("Ticker unlock ladder:")
    for row in payload["ticker_unlock_ladder"][:30]:
        print(
            f"- {row['ticker']}: stage={row['current_unlock_stage']} "
            f"goal={row['next_unlock_goal']} price={row['price_stage_status']} "
            f"dcf={row['dcf_stage_status']} peer={row['peer_stage_status']} optional={row['optional_context_status']}"
        )
        print(f"  next: {row['recommended_action']}")
    print(f"Ticker unlock ladder rows: {len(payload['ticker_unlock_ladder'])}")


def _print_unlock_priority_summary(payload: dict[str, Any]) -> None:
    print("Unlock priority summary:")
    for row in payload["unlock_priority_summary"][:30]:
        print(
            f"- {row['group_type']} {row['group_name']}: top_stage={row['top_priority_stage']} "
            f"goal={row['next_unlock_goal']} tickers={row['ticker_count']} holdings={row['holdings_count']}"
        )
        print(f"  next: {row['recommended_action']}")
    print(f"Unlock priority summary rows: {len(payload['unlock_priority_summary'])}")


def _print_command_bundles(payload: dict[str, Any]) -> None:
    for row in payload["command_bundles"]:
        print(
            f"{row['bundle_name']}: lane={row['lane']} scope={row['scope']} "
            f"tickers={row['tickers']} count={row['ticker_count']}"
        )
        if row.get("goal_summary"):
            print(f"  goal: {row['goal_summary']}")
        if row.get("target_history_rows"):
            print(
                f"  target_history_rows: {row['target_history_rows']} "
                f"suggested_start_date: {row.get('suggested_start_date') or '-'}"
            )
        print(f"  command: {row['primary_command']}")
        print(f"  follow-up: {row['follow_up_command']}")
    print(f"Command bundle rows: {len(payload['command_bundles'])}")


def _print_command_bundle_details(payload: dict[str, Any]) -> None:
    for row in payload["command_bundle_details"][:30]:
        print(
            f"{row['bundle_name']}: lane={row['lane']} ticker={row['ticker']} "
            f"holding={row['is_holding']} stage={row['current_unlock_stage']} "
            f"goal={row.get('target_goal') or '-'} rows_needed={row.get('rows_needed', 0)} "
            f"target_rows={row.get('target_history_rows', 0)} start={row.get('suggested_start_date') or '-'}"
        )
        print(f"  next: {row['recommended_action']}")
    print(f"Command bundle detail rows: {len(payload['command_bundle_details'])}")


def _print_command_bundle_runbook(payload: dict[str, Any]) -> None:
    for row in payload["command_bundle_runbook"][:60]:
        print(
            f"{row['bundle_name']}: lane={row['lane']} step={row['step_order']} "
            f"{row['step_label']} -> {row['command']}"
        )
        if row.get("goal_summary"):
            print(f"  goal: {row['goal_summary']}")
        if row.get("target_history_rows"):
            print(
                f"  target_history_rows: {row['target_history_rows']} "
                f"suggested_start_date: {row.get('suggested_start_date') or '-'}"
            )
    print(f"Command bundle runbook rows: {len(payload['command_bundle_runbook'])}")


def _normalized_lane(value: str | None) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _filter_command_bundle_payload(
    payload: dict[str, Any],
    *,
    lane: str | None = None,
    holdings_only: bool = False,
) -> dict[str, Any]:
    lane_value = _normalized_lane(lane)

    bundles = payload.get("command_bundles", [])
    details = payload.get("command_bundle_details", [])
    runbook = payload.get("command_bundle_runbook", [])

    if lane_value:
        bundles = [row for row in bundles if _normalized_lane(row.get("lane")) == lane_value]
        details = [row for row in details if _normalized_lane(row.get("lane")) == lane_value]
        runbook = [row for row in runbook if _normalized_lane(row.get("lane")) == lane_value]

    if holdings_only:
        bundles = [
            row
            for row in bundles
            if _normalized_lane(row.get("scope")) == "holdings_first"
        ]
        bundle_names = {str(row.get("bundle_name", "")) for row in bundles}
        details = [
            row
            for row in details
            if str(row.get("bundle_name", "")) in bundle_names and bool(row.get("is_holding", False))
        ]
        runbook = [row for row in runbook if str(row.get("bundle_name", "")) in bundle_names]
    elif bundles:
        bundle_names = {str(row.get("bundle_name", "")) for row in bundles}
        details = [row for row in details if str(row.get("bundle_name", "")) in bundle_names]
        runbook = [row for row in runbook if str(row.get("bundle_name", "")) in bundle_names]

    filtered = dict(payload)
    filtered["command_bundles"] = bundles
    filtered["command_bundle_details"] = details
    filtered["command_bundle_runbook"] = runbook
    return filtered


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect local ticker-level coverage and onboarding actions.")
    parser.add_argument("--coverage", action="store_true", help="Print ticker-level local data coverage.")
    parser.add_argument("--wizard", action="store_true", help="Print prioritized data coverage wizard rows.")
    parser.add_argument("--price-worklist", action="store_true", help="Print prioritized local price-history worklist rows.")
    parser.add_argument(
        "--fundamentals-peer-worklist",
        action="store_true",
        help="Print prioritized fundamentals and peer-readiness worklist rows.",
    )
    parser.add_argument(
        "--optional-context-worklist",
        action="store_true",
        help="Print prioritized optional earnings and analyst-estimate worklist rows.",
    )
    parser.add_argument(
        "--sec-stage-queue",
        action="store_true",
        help="Print prioritized SEC fundamentals staging candidates for DCF coverage.",
    )
    parser.add_argument(
        "--peer-mapping-queue",
        action="store_true",
        help="Print prioritized manual peer-mapping candidates for peer-relative coverage.",
    )
    parser.add_argument(
        "--unlock-ladder",
        action="store_true",
        help="Print one row per ticker showing the next core local data unlock stage.",
    )
    parser.add_argument(
        "--unlock-summary",
        action="store_true",
        help="Print grouped unlock priorities by holdings, theme, and sector ETF.",
    )
    parser.add_argument(
        "--command-bundles",
        action="store_true",
        help="Print holdings-first local command bundles for prices, SEC staging, and peer mapping.",
    )
    parser.add_argument(
        "--command-bundle-details",
        action="store_true",
        help="Print ticker-level detail rows for the current local command bundles.",
    )
    parser.add_argument(
        "--command-bundle-runbook",
        action="store_true",
        help="Print ordered runbook rows for the current local command bundles.",
    )
    parser.add_argument(
        "--lane",
        choices=["prices", "fundamentals", "peers"],
        help="Optional lane filter for command bundle views.",
    )
    parser.add_argument(
        "--holdings-only",
        action="store_true",
        help="Limit command bundle views to holdings-first rows when available.",
    )
    parser.add_argument("--write-output", action="store_true", help="Write ticker coverage and onboarding action CSVs.")
    parser.add_argument("--write-templates", action="store_true", help="Write header-only onboarding templates under data/templates.")
    parser.add_argument("--tickers", help="Comma-separated tickers to inspect. Defaults to universe and holdings tickers.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--project-root", help="Project root for default data/output directories.")
    parser.add_argument("--data-dir", help="Optional data directory. Relative paths resolve from project root.")
    parser.add_argument("--output-dir", help="Optional output directory. Relative paths resolve from project root.")
    args = parser.parse_args()

    root = resolve_project_root(args.project_root)
    data_path = resolve_data_dir(args.data_dir, root)
    output_path = resolve_outputs_dir(args.output_dir, root)
    tickers = _parse_tickers(args.tickers)

    if args.write_templates:
        results = write_onboarding_templates(root, data_dir=data_path)
        if args.json:
            print(json.dumps(results, indent=2))
            return
        print(format_path_context(root, data_path, output_path))
        for item in results:
            print(f"{item['dataset_name']}: {item['status']} -> {item['path']}")
        return

    if args.write_output:
        payload = write_onboarding_outputs(root, data_dir=data_path, output_dir=output_path, tickers=tickers)
    else:
        payload = build_onboarding_payload(root, data_dir=data_path, output_dir=output_path, tickers=tickers)

    if args.command_bundles or args.command_bundle_details or args.command_bundle_runbook:
        payload = _filter_command_bundle_payload(payload, lane=args.lane, holdings_only=args.holdings_only)

    if args.json:
        if args.wizard and not args.coverage and not args.write_output and not args.price_worklist and not args.fundamentals_peer_worklist and not args.optional_context_worklist and not args.sec_stage_queue and not args.peer_mapping_queue and not args.unlock_ladder and not args.unlock_summary and not args.command_bundles and not args.command_bundle_details and not args.command_bundle_runbook:
            print(json.dumps({"data_coverage_wizard": payload["data_coverage_wizard"]}, indent=2))
        elif args.price_worklist and not args.coverage and not args.write_output and not args.wizard and not args.fundamentals_peer_worklist and not args.optional_context_worklist and not args.sec_stage_queue and not args.peer_mapping_queue and not args.unlock_ladder and not args.unlock_summary and not args.command_bundles and not args.command_bundle_details and not args.command_bundle_runbook:
            print(json.dumps({"price_import_worklist": payload["price_import_worklist"]}, indent=2))
        elif args.fundamentals_peer_worklist and not args.coverage and not args.write_output and not args.wizard and not args.price_worklist and not args.optional_context_worklist and not args.sec_stage_queue and not args.peer_mapping_queue and not args.unlock_ladder and not args.unlock_summary and not args.command_bundles and not args.command_bundle_details and not args.command_bundle_runbook:
            print(json.dumps({"fundamentals_peer_worklist": payload["fundamentals_peer_worklist"]}, indent=2))
        elif args.optional_context_worklist and not args.coverage and not args.write_output and not args.wizard and not args.price_worklist and not args.fundamentals_peer_worklist and not args.sec_stage_queue and not args.peer_mapping_queue and not args.unlock_ladder and not args.unlock_summary and not args.command_bundles and not args.command_bundle_details and not args.command_bundle_runbook:
            print(json.dumps({"optional_context_worklist": payload["optional_context_worklist"]}, indent=2))
        elif args.sec_stage_queue and not args.coverage and not args.write_output and not args.wizard and not args.price_worklist and not args.fundamentals_peer_worklist and not args.optional_context_worklist and not args.peer_mapping_queue and not args.unlock_ladder and not args.unlock_summary and not args.command_bundles and not args.command_bundle_details and not args.command_bundle_runbook:
            print(json.dumps({"sec_stage_queue": payload["sec_stage_queue"]}, indent=2))
        elif args.peer_mapping_queue and not args.coverage and not args.write_output and not args.wizard and not args.price_worklist and not args.fundamentals_peer_worklist and not args.optional_context_worklist and not args.sec_stage_queue and not args.unlock_ladder and not args.unlock_summary and not args.command_bundles and not args.command_bundle_details and not args.command_bundle_runbook:
            print(json.dumps({"peer_mapping_queue": payload["peer_mapping_queue"]}, indent=2))
        elif args.unlock_ladder and not args.coverage and not args.write_output and not args.wizard and not args.price_worklist and not args.fundamentals_peer_worklist and not args.optional_context_worklist and not args.sec_stage_queue and not args.peer_mapping_queue and not args.unlock_summary and not args.command_bundles and not args.command_bundle_details and not args.command_bundle_runbook:
            print(json.dumps({"ticker_unlock_ladder": payload["ticker_unlock_ladder"]}, indent=2))
        elif args.unlock_summary and not args.coverage and not args.write_output and not args.wizard and not args.price_worklist and not args.fundamentals_peer_worklist and not args.optional_context_worklist and not args.sec_stage_queue and not args.peer_mapping_queue and not args.unlock_ladder and not args.command_bundles and not args.command_bundle_details and not args.command_bundle_runbook:
            print(json.dumps({"unlock_priority_summary": payload["unlock_priority_summary"]}, indent=2))
        elif args.command_bundles and not args.coverage and not args.write_output and not args.wizard and not args.price_worklist and not args.fundamentals_peer_worklist and not args.optional_context_worklist and not args.sec_stage_queue and not args.peer_mapping_queue and not args.unlock_ladder and not args.unlock_summary and not args.command_bundle_details and not args.command_bundle_runbook:
            print(json.dumps({"command_bundles": payload["command_bundles"]}, indent=2))
        elif args.command_bundle_details and not args.coverage and not args.write_output and not args.wizard and not args.price_worklist and not args.fundamentals_peer_worklist and not args.optional_context_worklist and not args.sec_stage_queue and not args.peer_mapping_queue and not args.unlock_ladder and not args.unlock_summary and not args.command_bundles and not args.command_bundle_runbook:
            print(json.dumps({"command_bundle_details": payload["command_bundle_details"]}, indent=2))
        elif args.command_bundle_runbook and not args.coverage and not args.write_output and not args.wizard and not args.price_worklist and not args.fundamentals_peer_worklist and not args.optional_context_worklist and not args.sec_stage_queue and not args.peer_mapping_queue and not args.unlock_ladder and not args.unlock_summary and not args.command_bundles and not args.command_bundle_details:
            print(json.dumps({"command_bundle_runbook": payload["command_bundle_runbook"]}, indent=2))
        else:
            print(json.dumps(payload, indent=2))
        return

    print(format_path_context(root, data_path, output_path))
    if args.command_bundle_runbook and not args.coverage and not args.wizard and not args.price_worklist and not args.fundamentals_peer_worklist and not args.optional_context_worklist and not args.sec_stage_queue and not args.peer_mapping_queue and not args.unlock_ladder and not args.unlock_summary and not args.command_bundles and not args.command_bundle_details:
        _print_command_bundle_runbook(payload)
    elif args.command_bundle_details and not args.coverage and not args.wizard and not args.price_worklist and not args.fundamentals_peer_worklist and not args.optional_context_worklist and not args.sec_stage_queue and not args.peer_mapping_queue and not args.unlock_ladder and not args.unlock_summary and not args.command_bundles:
        _print_command_bundle_details(payload)
    elif args.command_bundles and not args.coverage and not args.wizard and not args.price_worklist and not args.fundamentals_peer_worklist and not args.optional_context_worklist and not args.sec_stage_queue and not args.peer_mapping_queue and not args.unlock_ladder and not args.unlock_summary:
        _print_command_bundles(payload)
    elif args.unlock_summary and not args.coverage and not args.wizard and not args.price_worklist and not args.fundamentals_peer_worklist and not args.optional_context_worklist and not args.sec_stage_queue and not args.peer_mapping_queue and not args.unlock_ladder:
        _print_unlock_priority_summary(payload)
    elif args.unlock_ladder and not args.coverage and not args.wizard and not args.price_worklist and not args.fundamentals_peer_worklist and not args.optional_context_worklist and not args.sec_stage_queue and not args.peer_mapping_queue:
        _print_ticker_unlock_ladder(payload)
    elif args.peer_mapping_queue and not args.coverage and not args.wizard and not args.price_worklist and not args.fundamentals_peer_worklist and not args.optional_context_worklist and not args.sec_stage_queue:
        _print_peer_mapping_queue(payload)
    elif args.sec_stage_queue and not args.coverage and not args.wizard and not args.price_worklist and not args.fundamentals_peer_worklist and not args.optional_context_worklist:
        _print_sec_stage_queue(payload)
    elif args.optional_context_worklist and not args.coverage and not args.wizard and not args.price_worklist and not args.fundamentals_peer_worklist and not args.sec_stage_queue and not args.peer_mapping_queue:
        _print_optional_context_worklist(payload)
    elif args.fundamentals_peer_worklist and not args.coverage and not args.wizard and not args.price_worklist and not args.sec_stage_queue and not args.peer_mapping_queue:
        _print_fundamentals_peer_worklist(payload)
    elif args.price_worklist and not args.coverage and not args.wizard and not args.sec_stage_queue and not args.peer_mapping_queue:
        _print_price_worklist(payload)
    elif args.wizard and not args.coverage:
        _print_wizard(payload)
    else:
        _print_coverage(payload)
    if args.write_output:
        print(f"Wrote: {payload['coverage_path']}")
        print(f"Wrote: {payload['actions_path']}")
        print(f"Wrote: {payload['wizard_path']}")
        print(f"Wrote: {payload['price_worklist_path']}")
        print(f"Wrote: {payload['fundamentals_peer_worklist_path']}")
        print(f"Wrote: {payload['optional_context_worklist_path']}")
        print(f"Wrote: {payload['sec_stage_queue_path']}")
        print(f"Wrote: {payload['peer_mapping_queue_path']}")
        print(f"Wrote: {payload['ticker_unlock_ladder_path']}")
        print(f"Wrote: {payload['unlock_priority_summary_path']}")
        print(f"Wrote: {payload['command_bundles_path']}")
        print(f"Wrote: {payload['command_bundle_details_path']}")
        print(f"Wrote: {payload['command_bundle_runbook_path']}")


if __name__ == "__main__":
    main()
