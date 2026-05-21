from __future__ import annotations

import argparse
import json
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
        rows.append(
            PriceWorklistRow(
                priority=priority,
                ticker=coverage.ticker,
                has_prices=coverage.has_prices,
                price_history_days=coverage.price_history_days,
                first_local_date=first_local_date,
                latest_local_date=latest_local_date,
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
    return {
        "ticker_coverage": [row.to_dict() for row in coverage],
        "onboarding_actions": [row.to_dict() for row in actions],
        "data_coverage_wizard": [row.to_dict() for row in wizard],
        "price_import_worklist": [row.to_dict() for row in price_worklist],
        "fundamentals_peer_worklist": [row.to_dict() for row in fundamentals_peer_worklist],
        "optional_context_worklist": [row.to_dict() for row in optional_context_worklist],
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
    return {
        **payload,
        "coverage_path": str(coverage_path),
        "actions_path": str(actions_path),
        "wizard_path": str(wizard_path),
        "price_worklist_path": str(price_worklist_path),
        "fundamentals_peer_worklist_path": str(fundamentals_peer_worklist_path),
        "optional_context_worklist_path": str(optional_context_worklist_path),
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

    if args.json:
        if args.wizard and not args.coverage and not args.write_output and not args.price_worklist and not args.fundamentals_peer_worklist and not args.optional_context_worklist:
            print(json.dumps({"data_coverage_wizard": payload["data_coverage_wizard"]}, indent=2))
        elif args.price_worklist and not args.coverage and not args.write_output and not args.wizard and not args.fundamentals_peer_worklist and not args.optional_context_worklist:
            print(json.dumps({"price_import_worklist": payload["price_import_worklist"]}, indent=2))
        elif args.fundamentals_peer_worklist and not args.coverage and not args.write_output and not args.wizard and not args.price_worklist and not args.optional_context_worklist:
            print(json.dumps({"fundamentals_peer_worklist": payload["fundamentals_peer_worklist"]}, indent=2))
        elif args.optional_context_worklist and not args.coverage and not args.write_output and not args.wizard and not args.price_worklist and not args.fundamentals_peer_worklist:
            print(json.dumps({"optional_context_worklist": payload["optional_context_worklist"]}, indent=2))
        else:
            print(json.dumps(payload, indent=2))
        return

    print(format_path_context(root, data_path, output_path))
    if args.optional_context_worklist and not args.coverage and not args.wizard and not args.price_worklist and not args.fundamentals_peer_worklist:
        _print_optional_context_worklist(payload)
    elif args.fundamentals_peer_worklist and not args.coverage and not args.wizard and not args.price_worklist:
        _print_fundamentals_peer_worklist(payload)
    elif args.price_worklist and not args.coverage and not args.wizard:
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


if __name__ == "__main__":
    main()
