from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from src.loader import normalize_columns
from src.paths import format_path_context, resolve_data_dir, resolve_project_root
from src.providers.local_schemas import LOCAL_DATASET_SCHEMAS


DATASET_CONFIG: dict[str, dict[str, Any]] = {
    "earnings": {
        "staged_dir": "earnings",
        "output_file": "earnings.csv",
        "rejected_file": "earnings_import_rejected.csv",
        "expected_columns": (
            "ticker",
            "fiscal_period",
            "report_date",
            "eps_actual",
            "eps_estimate",
            "revenue_actual",
            "revenue_estimate",
            "source",
            "updated_at",
        ),
        "numeric_columns": ("eps_actual", "eps_estimate", "revenue_actual", "revenue_estimate"),
        "date_columns": ("report_date", "updated_at"),
        "dedupe_keys": ("ticker", "fiscal_period", "report_date"),
        "canonical_aliases": {"report_date": "last_earnings_date", "updated_at": "as_of_date"},
    },
    "analyst_estimates": {
        "staged_dir": "analyst_estimates",
        "output_file": "analyst_estimates.csv",
        "rejected_file": "analyst_estimates_import_rejected.csv",
        "expected_columns": (
            "ticker",
            "period",
            "eps_estimate",
            "revenue_estimate",
            "price_target_mean",
            "price_target_high",
            "price_target_low",
            "rating_consensus",
            "source",
            "updated_at",
        ),
        "numeric_columns": (
            "eps_estimate",
            "revenue_estimate",
            "price_target_mean",
            "price_target_high",
            "price_target_low",
        ),
        "date_columns": ("updated_at",),
        "dedupe_keys": ("ticker", "period"),
        "canonical_aliases": {
            "eps_estimate": "current_quarter_eps",
            "revenue_estimate": "current_quarter_revenue",
            "price_target_mean": "target_mean_price",
            "price_target_high": "target_high_price",
            "price_target_low": "target_low_price",
            "rating_consensus": "recommendation",
            "updated_at": "as_of_date",
        },
    },
}
REJECTED_COLUMNS = ["source_file", "source_row", "ticker", "rejection_reason"]


@dataclass
class ManualOptionalContextImportResult:
    dataset_name: str
    status: str
    staged_dir: str
    output_path: str
    rejected_path: str
    files_read: int = 0
    rows_read: int = 0
    rows_valid: int = 0
    rows_rejected: int = 0
    duplicate_rows: int = 0
    staged_row_count: int = 0
    affected_tickers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = normalize_columns(list(frame.columns))
    return frame


def _load_universe_tickers(data_dir: Path) -> set[str]:
    tickers: set[str] = set()
    for filename in ("universe_master.csv", "universe_active.csv", "universe.csv"):
        path = data_dir / filename
        if not path.exists():
            continue
        frame = _read_csv(path)
        if "ticker" not in frame.columns:
            continue
        values = frame["ticker"].dropna().astype(str).str.upper().str.strip()
        tickers.update(ticker for ticker in values.unique().tolist() if ticker)
    return tickers


def _allowed_columns(dataset_name: str) -> list[str]:
    schema = LOCAL_DATASET_SCHEMAS[dataset_name]
    columns = list(schema.required_columns)
    for column in schema.optional_columns:
        if column not in columns:
            columns.append(column)
    return columns


def _has_raw_value(value: Any) -> bool:
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    return str(value).strip() != ""


def _normalize_staged_file(path: Path, dataset_name: str, universe_tickers: set[str]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    config = DATASET_CONFIG[dataset_name]
    raw = _read_csv(path)
    working = raw.copy()
    rows_read = len(working)
    for column in config["expected_columns"]:
        if column not in working.columns:
            working[column] = pd.NA

    working["ticker"] = working["ticker"].astype("string").str.upper().str.strip()
    for column in config["date_columns"]:
        if column in working.columns:
            working[column] = pd.to_datetime(working[column], errors="coerce", format="mixed")
    for column in config["numeric_columns"]:
        if column in working.columns:
            working[column] = pd.to_numeric(working[column], errors="coerce")

    rejected_rows: list[dict[str, Any]] = []
    valid_mask = pd.Series(True, index=working.index)
    for idx, row in working.iterrows():
        reasons: list[str] = []
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker:
            reasons.append("missing_ticker")
        elif ticker not in universe_tickers:
            reasons.append("ticker_not_in_universe")
        source_value = row.get("source")
        if pd.isna(source_value) or not str(source_value).strip():
            reasons.append("missing_source")
        raw_row = raw.loc[idx] if idx in raw.index else pd.Series(dtype=object)
        for column in config["date_columns"]:
            if column in raw.columns and _has_raw_value(raw_row.get(column)) and pd.isna(row.get(column)):
                reasons.append(f"{column}_not_parseable")
        for column in config["numeric_columns"]:
            if column in raw.columns and _has_raw_value(raw_row.get(column)) and pd.isna(row.get(column)):
                reasons.append(f"{column}_not_numeric")
        if reasons:
            valid_mask.loc[idx] = False
            rejected_rows.append(
                {
                    "source_file": str(path),
                    "source_row": int(idx + 2),
                    "ticker": ticker,
                    "rejection_reason": ";".join(reasons),
                }
            )

    valid = working.loc[valid_mask].copy()
    duplicate_rows = 0
    dedupe_keys = [column for column in config["dedupe_keys"] if column in valid.columns]
    if dedupe_keys and not valid.empty:
        duplicate_mask = valid.duplicated(subset=dedupe_keys, keep="last")
        duplicate_rows = int(duplicate_mask.sum())
        for idx, row in valid.loc[duplicate_mask].iterrows():
            rejected_rows.append(
                {
                    "source_file": str(path),
                    "source_row": int(idx + 2),
                    "ticker": str(row.get("ticker") or ""),
                    "rejection_reason": "duplicate_row_dropped",
                }
            )
        valid = valid.loc[~duplicate_mask].copy()

    aliases: dict[str, str] = config["canonical_aliases"]
    for source_column, canonical_column in aliases.items():
        if source_column in valid.columns and canonical_column not in valid.columns:
            valid[canonical_column] = valid[source_column]
    for column in [*config["date_columns"], *aliases.values()]:
        if column in valid.columns and pd.api.types.is_datetime64_any_dtype(valid[column]):
            valid[column] = valid[column].dt.date.astype("string")

    valid = valid.reindex(columns=_allowed_columns(dataset_name))
    rejected = pd.DataFrame(rejected_rows, columns=REJECTED_COLUMNS)
    return valid, rejected, {"rows_read": rows_read, "duplicate_rows": duplicate_rows}


def _load_existing(path: Path, dataset_name: str) -> pd.DataFrame:
    allowed = _allowed_columns(dataset_name)
    if not path.exists():
        return pd.DataFrame(columns=allowed)
    frame = _read_csv(path)
    for column in allowed:
        if column not in frame.columns:
            frame[column] = pd.NA
    frame["ticker"] = frame["ticker"].astype("string").str.upper().str.strip()
    return frame.reindex(columns=allowed).dropna(subset=["ticker"])


def import_staged_optional_context(
    dataset_name: str,
    base_dir: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    staged_dir: Path | str | None = None,
    output_path: Path | str | None = None,
    rejected_path: Path | str | None = None,
) -> ManualOptionalContextImportResult:
    if dataset_name not in DATASET_CONFIG:
        raise ValueError(f"Unsupported optional context dataset: {dataset_name}")
    config = DATASET_CONFIG[dataset_name]
    root = resolve_project_root(base_dir)
    data_path = resolve_data_dir(data_dir, root)
    staged_path = Path(staged_dir) if staged_dir is not None else data_path / "staged" / str(config["staged_dir"])
    output = Path(output_path) if output_path is not None else data_path / "imports" / str(config["output_file"])
    rejected_output = Path(rejected_path) if rejected_path is not None else data_path / str(config["rejected_file"])
    staged_path = staged_path if staged_path.is_absolute() else root / staged_path
    output = output if output.is_absolute() else root / output
    rejected_output = rejected_output if rejected_output.is_absolute() else root / rejected_output
    staged_path.mkdir(parents=True, exist_ok=True)
    universe_tickers = _load_universe_tickers(data_path)

    files = sorted(path for path in staged_path.glob("*.csv") if path.is_file())
    valid_frames: list[pd.DataFrame] = []
    rejected_frames: list[pd.DataFrame] = []
    rows_read = 0
    duplicate_rows = 0
    for path in files:
        valid, rejected, summary = _normalize_staged_file(path, dataset_name, universe_tickers)
        valid_frames.append(valid)
        rejected_frames.append(rejected)
        rows_read += int(summary["rows_read"])
        duplicate_rows += int(summary["duplicate_rows"])

    valid_all = pd.concat(valid_frames, ignore_index=True) if valid_frames else pd.DataFrame(columns=_allowed_columns(dataset_name))
    rejected_all = pd.concat(rejected_frames, ignore_index=True) if rejected_frames else pd.DataFrame(columns=REJECTED_COLUMNS)
    dedupe_keys = [column for column in config["dedupe_keys"] if column in valid_all.columns]
    if dedupe_keys and not valid_all.empty:
        duplicate_mask = valid_all.duplicated(subset=dedupe_keys, keep="last")
        duplicate_rows += int(duplicate_mask.sum())
        valid_all = valid_all.loc[~duplicate_mask].copy()

    existing = _load_existing(output, dataset_name)
    if not valid_all.empty:
        combined = pd.concat([existing, valid_all], ignore_index=True)
        if dedupe_keys:
            combined = combined.drop_duplicates(subset=dedupe_keys, keep="last")
        combined = combined.sort_values([column for column in ("ticker", "period", "fiscal_period", "report_date") if column in combined.columns]).reset_index(drop=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(output, index=False)
    else:
        combined = existing

    rejected_output.parent.mkdir(parents=True, exist_ok=True)
    rejected_all.to_csv(rejected_output, index=False)
    rejected_reports_output = data_path / "rejected" / str(config["rejected_file"])
    rejected_reports_output.parent.mkdir(parents=True, exist_ok=True)
    rejected_all.to_csv(rejected_reports_output, index=False)
    status = "no_staged_files" if not files else "imported"
    if files and valid_all.empty:
        status = "no_valid_rows"
    return ManualOptionalContextImportResult(
        dataset_name=dataset_name,
        status=status,
        staged_dir=str(staged_path),
        output_path=str(output),
        rejected_path=str(rejected_output),
        files_read=len(files),
        rows_read=rows_read,
        rows_valid=int(len(valid_all)),
        rows_rejected=int(len(rejected_all)),
        duplicate_rows=duplicate_rows,
        staged_row_count=int(len(combined)),
        affected_tickers=sorted(valid_all["ticker"].dropna().astype(str).unique().tolist()) if not valid_all.empty else [],
    )


def _print_result(result: ManualOptionalContextImportResult, root: Path, data_path: Path) -> None:
    print(format_path_context(root, data_path, root / "outputs"))
    for key, value in result.to_dict().items():
        print(f"{key}: {value}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import verified manual earnings or analyst-estimate CSVs into data/imports.")
    parser.add_argument("dataset_name", choices=sorted(DATASET_CONFIG))
    parser.add_argument("--project-root", help="Project root. Defaults to this repository.")
    parser.add_argument("--data-dir", help="Optional data directory. Relative paths resolve from project root.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = resolve_project_root(args.project_root)
    data_path = resolve_data_dir(args.data_dir, root)
    result = import_staged_optional_context(args.dataset_name, root, data_dir=data_path)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return
    _print_result(result, root, data_path)


if __name__ == "__main__":
    main()
