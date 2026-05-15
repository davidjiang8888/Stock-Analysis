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


def build_onboarding_payload(
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
    tickers: list[str] | None = None,
) -> dict[str, Any]:
    coverage = build_ticker_coverage(project_root, data_dir=data_dir, output_dir=output_dir, tickers=tickers)
    actions = build_onboarding_actions(coverage)
    return {
        "ticker_coverage": [row.to_dict() for row in coverage],
        "onboarding_actions": [row.to_dict() for row in actions],
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
    pd.DataFrame(payload["ticker_coverage"], columns=COVERAGE_COLUMNS).to_csv(coverage_path, index=False)
    pd.DataFrame(payload["onboarding_actions"], columns=ACTION_COLUMNS).to_csv(actions_path, index=False)
    return {
        **payload,
        "coverage_path": str(coverage_path),
        "actions_path": str(actions_path),
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect local ticker-level coverage and onboarding actions.")
    parser.add_argument("--coverage", action="store_true", help="Print ticker-level local data coverage.")
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
        print(json.dumps(payload, indent=2))
        return

    print(format_path_context(root, data_path, output_path))
    _print_coverage(payload)
    if args.write_output:
        print(f"Wrote: {payload['coverage_path']}")
        print(f"Wrote: {payload['actions_path']}")


if __name__ == "__main__":
    main()
