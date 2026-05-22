from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.paths import format_path_context, resolve_data_dir, resolve_outputs_dir, resolve_project_root
from src.providers.local_data_catalog import LocalDataCatalog
from src.providers.local_schemas import validate_local_dataset


AVAILABILITY_STATUSES = {
    "available",
    "partial",
    "missing_file",
    "source_unavailable",
    "manual_only",
    "optional_unofficial",
    "not_supported",
}


@dataclass(frozen=True)
class DataSourceRegistryEntry:
    dataset: str
    source_name: str
    source_type: str
    required_for: str
    is_required: bool
    is_optional: bool
    is_manual_only: bool
    is_unofficial: bool
    requires_network: bool
    requires_user_agent: bool
    requires_api_key: bool
    expected_local_file: str
    fallback_action: str
    notes: str


@dataclass
class DataSourceStatus:
    dataset: str
    source_name: str
    source_type: str
    availability_status: str
    required_for: str
    is_required: bool
    is_optional: bool
    is_manual_only: bool
    is_unofficial: bool
    requires_network: bool
    requires_user_agent: bool
    requires_api_key: bool
    expected_local_file: str
    fallback_action: str
    target_file: str
    focus_command: str
    example_command: str
    notes: str
    local_file: str
    row_count: int
    available_columns: str
    validation_warnings: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DataGap:
    dataset: str
    ticker: str
    status: str
    reason: str
    required_for: str
    recommended_action: str
    target_file: str
    focus_command: str
    example_command: str
    local_file: str
    source_name: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _gap_focus_command(dataset: str, ticker: str) -> str:
    ticker = str(ticker or "").strip().upper()
    if dataset == "prices" and ticker:
        return f"make focus-price TICKER={ticker}"
    if dataset == "fundamentals" and ticker:
        return f"make focus-fundamentals TICKER={ticker}"
    if dataset == "peers" and ticker:
        return f"make focus-peers TICKER={ticker}"
    if dataset == "prices":
        return "make status"
    if dataset == "fundamentals":
        return "make status"
    if dataset == "peers":
        return "make status"
    if dataset in {"earnings", "analyst_estimates", "smh_holdings"}:
        return "make templates"
    if dataset in {"sp500_constituents", "nasdaq_symbols", "universe"}:
        return "make universe-preview"
    return "make status"


def _gap_example_command(dataset: str, ticker: str) -> str:
    ticker = str(ticker or "").strip().upper()
    if dataset == "prices" and ticker:
        return f"make price-normalize INPUT=data/raw/prices/{ticker}.csv TICKER={ticker} SOURCE=yahoo_manual"
    if dataset == "fundamentals" and ticker:
        return f"python3 -m src.stock_report --sec-stage-fundamentals --tickers {ticker}"
    if dataset == "peers" and ticker:
        return "make templates"
    if dataset == "prices":
        return "make runbook-prices-broader"
    if dataset == "fundamentals":
        return "make runbook-fundamentals-broader"
    if dataset == "peers":
        return "make runbook-peers-broader"
    if dataset in {"earnings", "analyst_estimates", "smh_holdings"}:
        return "make templates"
    if dataset == "sp500_constituents":
        return "python3 -m src.universe_builder --preview --preset sp500_smh --max-tickers 50"
    if dataset == "nasdaq_symbols":
        return "python3 -m src.universe_builder --preview --sources sp500,nasdaq,smh,holdings --max-tickers 100"
    if dataset == "universe":
        return "make universe-preview"
    return "make status"


def _gap_target_file(dataset: str, ticker: str) -> str:
    ticker = str(ticker or "").strip().upper()
    if dataset == "prices":
        return "data/imports/prices.csv"
    if dataset == "fundamentals":
        return "data/imports/fundamentals.csv"
    if dataset == "peers":
        return "data/imports/peers.csv"
    if dataset == "earnings":
        return "data/imports/earnings.csv"
    if dataset == "analyst_estimates":
        return "data/imports/analyst_estimates.csv"
    if dataset == "smh_holdings":
        return "data/custom_universe.csv"
    if dataset in {"sp500_constituents", "nasdaq_symbols", "universe"}:
        return "data/imports/universe.csv"
    if dataset == "local_outputs":
        return "outputs/"
    return ""


def _ticker_gap_recommended_action(dataset: str, ticker: str) -> str:
    ticker = str(ticker or "").strip().upper()
    if dataset == "prices" and ticker:
        return (
            f"Run make focus-price TICKER={ticker}, or run python3 -m src.data_update "
            f"--tickers {ticker} and normalize verified downloaded OHLCV files into "
            "data/imports/prices.csv."
        )
    if dataset == "fundamentals" and ticker:
        return (
            f"Run make focus-fundamentals TICKER={ticker}, or stage explicit local "
            f"fundamentals with python3 -m src.stock_report --sec-stage-fundamentals "
            f"--tickers {ticker}."
        )
    return ""


def _staged_import_file_name(dataset: str) -> str | None:
    if dataset == "fundamentals":
        return "fundamentals.csv"
    if dataset == "peers":
        return "peers.csv"
    if dataset == "earnings":
        return "earnings.csv"
    if dataset == "analyst_estimates":
        return "analyst_estimates.csv"
    return None


def _staged_import_status(dataset: str, root: Path, data_path: Path) -> dict[str, Any] | None:
    file_name = _staged_import_file_name(dataset)
    if not file_name:
        return None
    staged_path = data_path / "imports" / file_name
    if not staged_path.exists():
        return None
    validation, frame = validate_local_dataset(dataset, staged_path)
    row_count = len(frame) if frame is not None else validation.row_count
    return {
        "path": staged_path,
        "row_count": row_count,
        "status": validation.status,
        "available_columns": validation.available_columns,
        "warnings": validation.warnings,
    }


def _staged_import_follow_up(dataset: str) -> str:
    if dataset == "fundamentals":
        return (
            "Run make imports-validate, then make imports-preview, then make imports-apply, "
            "then make status to confirm the live local fundamentals and DCF inputs."
        )
    if dataset == "peers":
        return (
            "Run make imports-validate, then make imports-preview, then make imports-apply, "
            "then make status to confirm the live peer mappings."
        )
    if dataset == "earnings":
        return (
            "Run make imports-validate, then make imports-preview, then make imports-apply, "
            "then make status to confirm the live local earnings context."
        )
    if dataset == "analyst_estimates":
        return (
            "Run make imports-validate, then make imports-preview, then make imports-apply, "
            "then make status to confirm the live local analyst-estimate context."
        )
    return "Run make imports-validate, then make imports-preview, then make imports-apply, then make status."


DATA_SOURCE_REGISTRY: tuple[DataSourceRegistryEntry, ...] = (
    DataSourceRegistryEntry(
        dataset="prices",
        source_name="Local prices CSV / optional free daily updater",
        source_type="local_csv",
        required_for="momentum, market direction, stock reports, track record",
        is_required=True,
        is_optional=False,
        is_manual_only=False,
        is_unofficial=False,
        requires_network=False,
        requires_user_agent=False,
        requires_api_key=False,
        expected_local_file="data/prices.csv",
        fallback_action="Start with make status, then follow the printed price focus or runbook path. For downloaded files, normalize verified local OHLCV rows before validate/preview/apply.",
        notes="The app never fabricates missing price history; short history reduces long-horizon metrics.",
    ),
    DataSourceRegistryEntry(
        dataset="fundamentals",
        source_name="Local fundamentals CSV / SEC Companyfacts staging",
        source_type="local_csv_or_sec_staging",
        required_for="valuation, quality context, value/re-rating review",
        is_required=False,
        is_optional=True,
        is_manual_only=False,
        is_unofficial=False,
        requires_network=False,
        requires_user_agent=True,
        requires_api_key=False,
        expected_local_file="data/fundamentals.csv",
        fallback_action=(
            "Start with make status, then follow the printed fundamentals focus or runbook path. "
            "Keep SEC staging staged and review-only through validate/preview/apply."
        ),
        notes="SEC staging only provides candidate fundamentals; it does not provide prices, peers, earnings, or analyst estimates.",
    ),
    DataSourceRegistryEntry(
        dataset="peers",
        source_name="Manual local peer mappings",
        source_type="manual_csv",
        required_for="peer-relative valuation",
        is_required=False,
        is_optional=True,
        is_manual_only=True,
        is_unofficial=False,
        requires_network=False,
        requires_user_agent=False,
        requires_api_key=False,
        expected_local_file="data/peers.csv",
        fallback_action=(
            "Start with make status, then follow the printed peer focus or runbook path. "
            "Use make templates and fill data/imports/peers.csv manually with researched mappings."
        ),
        notes="Peer mappings require local research and are never guessed.",
    ),
    DataSourceRegistryEntry(
        dataset="earnings",
        source_name="Manual local earnings CSV",
        source_type="manual_csv",
        required_for="earnings summary",
        is_required=False,
        is_optional=True,
        is_manual_only=True,
        is_unofficial=False,
        requires_network=False,
        requires_user_agent=False,
        requires_api_key=False,
        expected_local_file="data/earnings.csv",
        fallback_action="Run make templates, then fill data/imports/earnings.csv manually only if you want local earnings coverage.",
        notes="Missing earnings files are expected until the user supplies verified local data.",
    ),
    DataSourceRegistryEntry(
        dataset="analyst_estimates",
        source_name="Manual local analyst estimates CSV",
        source_type="manual_csv",
        required_for="analyst estimate summary",
        is_required=False,
        is_optional=True,
        is_manual_only=True,
        is_unofficial=False,
        requires_network=False,
        requires_user_agent=False,
        requires_api_key=False,
        expected_local_file="data/analyst_estimates.csv",
        fallback_action="Run make templates, then fill data/imports/analyst_estimates.csv manually only if you want estimate coverage.",
        notes="Analyst estimates are not created by SEC staging and are never inferred.",
    ),
    DataSourceRegistryEntry(
        dataset="universe",
        source_name="Local universe CSV",
        source_type="local_csv",
        required_for="screening universe and purpose routing",
        is_required=True,
        is_optional=False,
        is_manual_only=False,
        is_unofficial=False,
        requires_network=False,
        requires_user_agent=False,
        requires_api_key=False,
        expected_local_file="data/universe.csv",
        fallback_action=(
            "Run make universe-preview first, then apply the staged universe only "
            "after previewing the source-driven build."
        ),
        notes="Missing theme/sector metadata is labeled Unclassified rather than fabricated.",
    ),
    DataSourceRegistryEntry(
        dataset="smh_holdings",
        source_name="VanEck SMH holdings",
        source_type="remote_optional",
        required_for="optional semiconductor ETF universe expansion",
        is_required=False,
        is_optional=True,
        is_manual_only=False,
        is_unofficial=False,
        requires_network=True,
        requires_user_agent=False,
        requires_api_key=False,
        expected_local_file="data/custom_universe.csv or data/imports/universe.csv",
        fallback_action=(
            "Run make templates, then fill data/custom_universe.csv with verified tickers only if the remote "
            "SMH page is unavailable. Use staged universe import only after previewing the source-driven build."
        ),
        notes="The remote SMH page can require redirect/cookie/location handling; this check does not fetch it.",
    ),
    DataSourceRegistryEntry(
        dataset="sp500_constituents",
        source_name="datasets/s-and-p-500-companies constituents.csv",
        source_type="remote_optional",
        required_for="optional S&P 500 universe expansion",
        is_required=False,
        is_optional=True,
        is_manual_only=False,
        is_unofficial=True,
        requires_network=True,
        requires_user_agent=False,
        requires_api_key=False,
        expected_local_file="data/imports/universe.csv",
        fallback_action=(
            "Run make universe-preview first, then review the staged S&P 500 / SMH "
            "preset universe before applying."
        ),
        notes="Open-source/community source, not the official paid S&P feed; no live check is performed here.",
    ),
    DataSourceRegistryEntry(
        dataset="nasdaq_symbols",
        source_name="Nasdaq Trader symbol directory",
        source_type="remote_optional",
        required_for="optional broad universe expansion",
        is_required=False,
        is_optional=True,
        is_manual_only=False,
        is_unofficial=False,
        requires_network=True,
        requires_user_agent=False,
        requires_api_key=False,
        expected_local_file="data/imports/universe.csv",
        fallback_action=(
            "Run make universe-preview first, then review the broader staged universe "
            "before applying; all-Nasdaq mode can be large."
        ),
        notes="No live check is performed by data_sources; universe_builder handles parsing when explicitly invoked.",
    ),
    DataSourceRegistryEntry(
        dataset="local_outputs",
        source_name="Generated screener outputs",
        source_type="generated_csv",
        required_for="dashboard, monthly picks, stock report screener context",
        is_required=True,
        is_optional=False,
        is_manual_only=False,
        is_unofficial=False,
        requires_network=False,
        requires_user_agent=False,
        requires_api_key=False,
        expected_local_file="outputs/*.csv",
        fallback_action=(
            "Run make verify to regenerate the core local research outputs and "
            "supporting operator artifacts before reopening the dashboard."
        ),
        notes="Generated CSVs are explainable local research outputs, not trading instructions.",
    ),
)

CORE_OUTPUT_FILES = (
    "purpose_classification.csv",
    "market_direction.csv",
    "momentum_leaders.csv",
    "portfolio_review.csv",
    "undervalued_candidates.csv",
    "final_watchlist.csv",
)


def _display_path(path: str | Path, root: Path) -> str:
    text_path = Path(path)
    try:
        return str(text_path.relative_to(root))
    except ValueError:
        return str(path)


def registry_entries() -> list[dict[str, Any]]:
    return [asdict(entry) for entry in DATA_SOURCE_REGISTRY]


def _metadata_lookup(catalog: LocalDataCatalog) -> dict[str, Any]:
    return {metadata.name: metadata for metadata in catalog.discover()}


def _status_for_local_dataset(entry: DataSourceRegistryEntry, metadata: Any) -> str:
    if metadata.validation_status == "missing_file":
        return "manual_only" if entry.is_manual_only else "missing_file"
    if metadata.validation_status == "valid_with_warnings":
        return "partial"
    if metadata.validation_status == "valid":
        return "available"
    return "partial"


def _output_status(outputs_dir: Path) -> tuple[str, int, list[str], list[str]]:
    present = [name for name in CORE_OUTPUT_FILES if (outputs_dir / name).exists()]
    missing = [name for name in CORE_OUTPUT_FILES if name not in present]
    if len(present) == len(CORE_OUTPUT_FILES):
        return "available", len(present), present, missing
    if present:
        return "partial", len(present), present, missing
    return "missing_file", 0, present, missing


def _remote_source_status(entry: DataSourceRegistryEntry, data_dir: Path) -> tuple[str, str, int]:
    custom_universe = data_dir / "custom_universe.csv"
    staged_universe = data_dir / "imports" / "universe.csv"
    if entry.dataset == "smh_holdings":
        if custom_universe.exists() or staged_universe.exists():
            return "partial", "Manual universe fallback file is present.", 1
        return "source_unavailable", "Remote SMH source is not checked here; use the documented manual fallback if it fails.", 0
    if staged_universe.exists():
        return "partial", "A staged universe file exists; validate and preview before applying.", 1
    return "optional_unofficial" if entry.is_unofficial else "partial", "Remote source is available only when universe_builder is explicitly run.", 0


def build_data_source_status(
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> list[DataSourceStatus]:
    root = resolve_project_root(project_root)
    data_path = resolve_data_dir(data_dir, root)
    output_path = resolve_outputs_dir(output_dir, root)
    catalog = LocalDataCatalog(root, data_dir=data_path, outputs_dir=output_path)
    metadata_by_name = _metadata_lookup(catalog)
    rows: list[DataSourceStatus] = []

    for entry in DATA_SOURCE_REGISTRY:
        local_file = entry.expected_local_file
        row_count = 0
        columns = ""
        warnings = ""
        notes = entry.notes
        status = "not_supported"
        fallback_action = entry.fallback_action
        focus_command = _gap_focus_command(entry.dataset, "")
        example_command = _gap_example_command(entry.dataset, "")

        if entry.dataset in metadata_by_name:
            metadata = metadata_by_name[entry.dataset]
            status = _status_for_local_dataset(entry, metadata)
            local_file = _display_path(metadata.file_path, root) if metadata.file_path else local_file
            row_count = int(metadata.row_count)
            columns = ", ".join(metadata.available_columns)
            warnings = "; ".join(metadata.validation_warnings)
            staged = _staged_import_status(entry.dataset, root, data_path)
            staged_ready = staged and staged["row_count"] > 0 and staged["status"] in {"valid", "valid_with_warnings"}
            if entry.dataset == "fundamentals" and staged_ready:
                notes = (
                    f"{entry.notes} Staged import rows are present in "
                    f"{_display_path(staged['path'], root)}; validate, preview, apply, "
                    "then refresh status before relying on canonical local data."
                )
                fallback_action = _staged_import_follow_up(entry.dataset)
                focus_command = "make imports-validate"
                example_command = "make imports-preview"
            if entry.dataset in {"peers", "earnings", "analyst_estimates"} and metadata.validation_status == "missing_file":
                if staged_ready:
                    status = "partial"
                    local_file = _display_path(staged["path"], root)
                    row_count = int(staged["row_count"])
                    columns = ", ".join(staged["available_columns"])
                    warnings = "; ".join(staged["warnings"])
                    notes = (
                        f"{entry.notes} Staged import rows are present; validate, preview, apply, "
                        "then refresh status before relying on canonical local data."
                    )
                    fallback_action = _staged_import_follow_up(entry.dataset)
                    focus_command = "make imports-validate"
                    example_command = "make imports-preview"
        elif entry.dataset == "local_outputs":
            status, row_count, present, missing = _output_status(output_path)
            local_file = _display_path(output_path, root)
            columns = ", ".join(present)
            warnings = f"Missing generated outputs: {', '.join(missing)}" if missing else ""
        elif entry.dataset in {"smh_holdings", "sp500_constituents", "nasdaq_symbols"}:
            status, remote_note, row_count = _remote_source_status(entry, data_path)
            notes = f"{entry.notes} {remote_note}"

        if status not in AVAILABILITY_STATUSES:
            status = "partial"

        rows.append(
            DataSourceStatus(
                dataset=entry.dataset,
                source_name=entry.source_name,
                source_type=entry.source_type,
                availability_status=status,
                required_for=entry.required_for,
                is_required=entry.is_required,
                is_optional=entry.is_optional,
                is_manual_only=entry.is_manual_only,
                is_unofficial=entry.is_unofficial,
                requires_network=entry.requires_network,
                requires_user_agent=entry.requires_user_agent,
                requires_api_key=entry.requires_api_key,
                expected_local_file=entry.expected_local_file,
                fallback_action=fallback_action,
                target_file=_gap_target_file(entry.dataset, ""),
                focus_command=focus_command,
                example_command=example_command,
                notes=notes,
                local_file=local_file,
                row_count=row_count,
                available_columns=columns,
                validation_warnings=warnings,
            )
        )
    return rows


def _read_tickers(catalog: LocalDataCatalog) -> list[str]:
    return catalog.list_tickers(["universe", "holdings"])


def _ticker_set(catalog: LocalDataCatalog, dataset_name: str) -> set[str]:
    frame = catalog.load_dataframe(dataset_name)
    if frame is None or "ticker" not in frame.columns:
        return set()
    return set(frame["ticker"].dropna().astype(str).str.upper().str.strip())


def build_data_gap_report(
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> list[DataGap]:
    root = resolve_project_root(project_root)
    data_path = resolve_data_dir(data_dir, root)
    output_path = resolve_outputs_dir(output_dir, root)
    catalog = LocalDataCatalog(root, data_dir=data_path, outputs_dir=output_path)
    statuses = build_data_source_status(root, data_dir=data_path, output_dir=output_path)
    status_by_dataset = {row.dataset: row for row in statuses}
    gaps: list[DataGap] = []

    for row in statuses:
        if row.availability_status == "available":
            continue
        reason = row.validation_warnings or row.notes
        if str(row.focus_command).strip() == "make imports-validate":
            reason = row.notes or row.validation_warnings
        gaps.append(
            DataGap(
                dataset=row.dataset,
                ticker="",
                status=row.availability_status,
                reason=reason,
                required_for=row.required_for,
                recommended_action=row.fallback_action,
                target_file=row.target_file,
                focus_command=row.focus_command,
                example_command=row.example_command,
                local_file=row.local_file,
                source_name=row.source_name,
            )
        )

    tickers = _read_tickers(catalog)
    price_tickers = _ticker_set(catalog, "prices")
    fundamentals_tickers = _ticker_set(catalog, "fundamentals")
    price_status = status_by_dataset["prices"]
    fundamentals_status = status_by_dataset["fundamentals"]
    for ticker in tickers:
        if ticker not in price_tickers:
            gaps.append(
                DataGap(
                    dataset="prices",
                    ticker=ticker,
                    status="missing_file" if not price_tickers else "partial",
                    reason=f"No local price rows were found for {ticker}.",
                    required_for=price_status.required_for,
                    recommended_action=_ticker_gap_recommended_action("prices", ticker),
                    target_file=_gap_target_file("prices", ticker),
                    focus_command=_gap_focus_command("prices", ticker),
                    example_command=_gap_example_command("prices", ticker),
                    local_file=price_status.local_file,
                    source_name=price_status.source_name,
                )
            )
        if fundamentals_status.availability_status != "missing_file" and ticker not in fundamentals_tickers:
            gaps.append(
                DataGap(
                    dataset="fundamentals",
                    ticker=ticker,
                    status="partial",
                    reason=f"No local fundamentals row was found for {ticker}.",
                    required_for=fundamentals_status.required_for,
                    recommended_action=_ticker_gap_recommended_action("fundamentals", ticker),
                    target_file=_gap_target_file("fundamentals", ticker),
                    focus_command=_gap_focus_command("fundamentals", ticker),
                    example_command=_gap_example_command("fundamentals", ticker),
                    local_file=fundamentals_status.local_file,
                    source_name=fundamentals_status.source_name,
                )
            )
    return gaps


def build_data_source_payload(
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    status_rows = build_data_source_status(project_root, data_dir=data_dir, output_dir=output_dir)
    gap_rows = build_data_gap_report(project_root, data_dir=data_dir, output_dir=output_dir)
    return {
        "data_sources": [row.to_dict() for row in status_rows],
        "data_gaps": [row.to_dict() for row in gap_rows],
    }


def write_data_source_outputs(
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    output_path = resolve_outputs_dir(output_dir, root)
    payload = build_data_source_payload(root, data_dir=data_dir, output_dir=output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    status_path = output_path / "data_source_status.csv"
    gap_path = output_path / "data_gap_report.csv"
    pd.DataFrame(payload["data_sources"]).to_csv(status_path, index=False)
    pd.DataFrame(payload["data_gaps"]).to_csv(gap_path, index=False)
    return {
        **payload,
        "status_path": str(status_path),
        "gap_report_path": str(gap_path),
    }


def _print_human(payload: dict[str, Any]) -> None:
    print("Data source status:")
    for row in payload["data_sources"]:
        print(
            f"- {row['dataset']}: {row['availability_status']} "
            f"rows={row['row_count']} source={row['source_name']}"
        )
        if row.get("focus_command"):
            print(f"  focus: {row['focus_command']}")
        if row.get("example_command"):
            print(f"  command: {row['example_command']}")
    print(f"Data gaps: {len(payload['data_gaps'])}")
    for row in payload["data_gaps"][:20]:
        ticker = f" {row['ticker']}" if row["ticker"] else ""
        print(f"- {row['dataset']}{ticker}: {row['status']} - {row['recommended_action']}")
        if row.get("focus_command"):
            print(f"  focus: {row['focus_command']}")
        if row.get("example_command"):
            print(f"  command: {row['example_command']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect local data-source availability without live network calls.")
    parser.add_argument("--check", action="store_true", help="Print data-source status and gap summary.")
    parser.add_argument("--write-output", action="store_true", help="Write outputs/data_source_status.csv and outputs/data_gap_report.csv.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--project-root", help="Project root for default data/output directories.")
    parser.add_argument("--data-dir", help="Optional data directory. Relative paths resolve from project root.")
    parser.add_argument("--output-dir", help="Optional output directory. Relative paths resolve from project root.")
    args = parser.parse_args()

    root = resolve_project_root(args.project_root)
    data_path = resolve_data_dir(args.data_dir, root)
    output_path = resolve_outputs_dir(args.output_dir, root)

    if args.write_output:
        payload = write_data_source_outputs(root, data_dir=data_path, output_dir=output_path)
    else:
        payload = build_data_source_payload(root, data_dir=data_path, output_dir=output_path)

    if args.json:
        print(json.dumps(payload, indent=2))
        return

    print(format_path_context(root, data_path, output_path))
    _print_human(payload)
    if args.write_output:
        print(f"Wrote: {payload['status_path']}")
        print(f"Wrote: {payload['gap_report_path']}")


if __name__ == "__main__":
    main()
