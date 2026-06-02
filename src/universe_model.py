from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from src.loader import normalize_columns
from src.paths import format_path_context, resolve_data_dir, resolve_project_root


MASTER_COLUMNS = [
    "ticker",
    "name",
    "exchange",
    "asset_type",
    "security_type",
    "sector",
    "industry",
    "country",
    "currency",
    "is_active_listing",
    "source",
    "source_updated_at",
    "created_at",
    "updated_at",
]
ACTIVE_COLUMNS = ["ticker", "scope", "priority", "theme", "research_status", "user_notes", "added_at", "updated_at"]
REJECTED_COLUMNS = ["source_file", "source_row", "ticker", "rejection_reason"]
ASSET_TYPES = {"company", "etf", "index_proxy", "adr", "preferred", "fund", "other", "unknown"}


@dataclass
class UniverseRefreshResult:
    status: str
    master_path: str
    active_path: str
    compatibility_path: str
    rejected_path: str
    report_path: str
    files_read: int = 0
    rows_read: int = 0
    rows_valid: int = 0
    rows_rejected: int = 0
    duplicate_rows: int = 0
    master_rows: int = 0
    active_rows: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    frame.columns = normalize_columns(list(frame.columns))
    if "ticker" in frame.columns:
        frame["ticker"] = frame["ticker"].astype("string").str.upper().str.strip()
    return frame


def _write_csv(frame: pd.DataFrame, path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = frame.copy()
    for column in columns:
        if column not in output.columns:
            output[column] = pd.NA
    output.reindex(columns=columns).to_csv(path, index=False)


def _now() -> str:
    return pd.Timestamp.now(tz="UTC").isoformat()


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return str(value)


def infer_asset_type(ticker: str, row: pd.Series | None = None) -> str:
    ticker = str(ticker or "").strip().upper()
    row = row if row is not None else pd.Series(dtype=object)
    raw = _text(row.get("asset_type", "")).strip().lower()
    if raw in ASSET_TYPES:
        return raw
    purpose = _text(row.get("defaultpurpose", row.get("default_purpose", ""))).lower()
    bucket = _text(row.get("marketcapbucket", row.get("market_cap_bucket", ""))).lower()
    security_type = _text(row.get("security_type", "")).lower()
    is_etf = row.get("is_etf")
    try:
        has_explicit_etf_flag = pd.notna(is_etf) and str(is_etf).strip() != ""
    except (TypeError, ValueError):
        has_explicit_etf_flag = False
    if has_explicit_etf_flag and str(is_etf).strip().lower() in {"1", "true", "yes", "y"}:
        return "etf"
    if ticker in {"SPY", "DIA", "IWM"} or "index" in security_type:
        return "index_proxy"
    if ticker in {"QQQ", "SMH"} or "etf" in purpose or "etf" in bucket or "etf" in security_type:
        return "etf"
    if "fund" in security_type:
        return "fund"
    if "preferred" in security_type:
        return "preferred"
    if "adr" in security_type:
        return "adr"
    return "company" if ticker else "unknown"


def _legacy_universe_to_master(legacy: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    timestamp = _now()
    for _, row in legacy.iterrows():
        ticker = str(row.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        rows.append(
            {
                "ticker": ticker,
                "name": row.get("name", row.get("company_name", "")),
                "exchange": row.get("exchange", ""),
                "asset_type": infer_asset_type(ticker, row),
                "security_type": row.get("security_type", ""),
                "sector": row.get("sector", row.get("sectoretf", row.get("sector_etf", ""))),
                "industry": row.get("industry", ""),
                "country": row.get("country", "US"),
                "currency": row.get("currency", "USD"),
                "is_active_listing": True,
                "source": row.get("source", row.get("universe_source", "legacy_universe_csv")),
                "source_updated_at": row.get("as_of_date", ""),
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )
    return pd.DataFrame(rows, columns=MASTER_COLUMNS)


def _legacy_universe_to_active(legacy: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    timestamp = _now()
    for idx, row in legacy.iterrows():
        ticker = str(row.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        rows.append(
            {
                "ticker": ticker,
                "scope": "active_research",
                "priority": int(idx + 1),
                "theme": row.get("theme", ""),
                "research_status": "active",
                "user_notes": row.get("notes", ""),
                "added_at": timestamp,
                "updated_at": timestamp,
            }
        )
    return pd.DataFrame(rows, columns=ACTIVE_COLUMNS)


def ensure_universe_files(base_dir: Path | str | None = None, *, data_dir: Path | str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    root = resolve_project_root(base_dir)
    data_path = resolve_data_dir(data_dir, root)
    master_path = data_path / "universe_master.csv"
    active_path = data_path / "universe_active.csv"
    legacy = _read_csv(data_path / "universe.csv")
    master = _read_csv(master_path)
    active = _read_csv(active_path)
    if master.empty and not legacy.empty:
        master = _legacy_universe_to_master(legacy)
        _write_csv(master, master_path, MASTER_COLUMNS)
    elif not legacy.empty:
        legacy_master = _legacy_universe_to_master(legacy)
        missing_legacy = legacy_master.loc[~legacy_master["ticker"].isin(set(master.get("ticker", pd.Series(dtype=str))))]
        if not missing_legacy.empty:
            master = (
                pd.concat([master, missing_legacy], ignore_index=True)
                .drop_duplicates(subset=["ticker"], keep="first")
                .sort_values("ticker")
                .reset_index(drop=True)
            )
            _write_csv(master, master_path, MASTER_COLUMNS)
        if not legacy_master.empty and "ticker" in master.columns:
            master = master.copy()
            legacy_by_ticker = legacy_master.set_index("ticker", drop=False)
            repaired = False
            for idx, row in master.iterrows():
                ticker = str(row.get("ticker") or "").strip().upper()
                if ticker not in legacy_by_ticker.index:
                    continue
                legacy_row = legacy_by_ticker.loc[ticker]
                if isinstance(legacy_row, pd.DataFrame):
                    legacy_row = legacy_row.iloc[-1]
                current_asset_type = str(row.get("asset_type") or "").strip().lower()
                legacy_asset_type = str(legacy_row.get("asset_type") or "").strip().lower()
                security_type = str(row.get("security_type") or "").strip().lower()
                explicit_etf_marker = (
                    ticker in {"QQQ", "SMH", "SPY", "DIA", "IWM"}
                    or "etf" in security_type
                    or "fund" in security_type
                    or "index" in security_type
                )
                if current_asset_type in {"etf", "index_proxy", "fund"} and legacy_asset_type == "company" and not explicit_etf_marker:
                    master.at[idx, "asset_type"] = "company"
                    if not str(row.get("name") or "").strip():
                        master.at[idx, "name"] = legacy_row.get("name", "")
                    repaired = True
            if repaired:
                _write_csv(master, master_path, MASTER_COLUMNS)
    if active.empty and not legacy.empty:
        active = _legacy_universe_to_active(legacy)
        _write_csv(active, active_path, ACTIVE_COLUMNS)
    return master, active


def _normalize_bool(value: Any) -> bool | pd.NA:
    if pd.isna(value):
        return pd.NA
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return pd.NA


def _normalize_staged_master(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    raw = _read_csv(path)
    working = raw.copy()
    raw_asset_type = working["asset_type"].copy() if "asset_type" in working.columns else pd.Series(pd.NA, index=working.index)
    for column in MASTER_COLUMNS:
        if column not in working.columns:
            working[column] = pd.NA
    working["ticker"] = working["ticker"].astype("string").str.upper().str.strip()
    if "is_active_listing" in working.columns:
        working["is_active_listing"] = working["is_active_listing"].map(_normalize_bool)
    timestamp = _now()
    working["asset_type"] = [infer_asset_type(str(row.get("ticker") or ""), row) for _, row in working.iterrows()]
    working["updated_at"] = working["updated_at"].fillna(timestamp)
    working["created_at"] = working["created_at"].fillna(timestamp)

    rejected_rows: list[dict[str, Any]] = []
    valid_mask = pd.Series(True, index=working.index)
    for idx, row in working.iterrows():
        reasons: list[str] = []
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker:
            reasons.append("missing_ticker")
        provided_asset_type = raw_asset_type.loc[idx] if idx in raw_asset_type.index else pd.NA
        if pd.notna(provided_asset_type) and str(provided_asset_type).strip() and str(provided_asset_type).strip().lower() not in ASSET_TYPES:
            reasons.append("invalid_asset_type")
        if str(row.get("asset_type") or "").strip().lower() not in ASSET_TYPES:
            reasons.append("invalid_asset_type")
        source_value = row.get("source")
        if pd.isna(source_value) or not str(source_value).strip():
            reasons.append("missing_source")
        if "is_active_listing" in raw.columns and pd.isna(row.get("is_active_listing")) and str(raw.loc[idx].get("is_active_listing") or "").strip():
            reasons.append("is_active_listing_not_boolean")
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
    if not valid.empty:
        duplicate_mask = valid.duplicated(subset=["ticker"], keep="last")
        duplicate_rows = int(duplicate_mask.sum())
        for idx, row in valid.loc[duplicate_mask].iterrows():
            rejected_rows.append(
                {
                    "source_file": str(path),
                    "source_row": int(idx + 2),
                    "ticker": str(row.get("ticker") or ""),
                    "rejection_reason": "duplicate_ticker_dropped",
                }
            )
        valid = valid.loc[~duplicate_mask].copy()
    return valid.reindex(columns=MASTER_COLUMNS), pd.DataFrame(rejected_rows, columns=REJECTED_COLUMNS), {
        "rows_read": len(raw),
        "duplicate_rows": duplicate_rows,
    }


def build_universe_coverage_report(
    base_dir: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_path: Path | str | None = None,
) -> pd.DataFrame:
    root = resolve_project_root(base_dir)
    data_path = resolve_data_dir(data_dir, root)
    master, active = ensure_universe_files(root, data_dir=data_path)
    output = Path(output_path) if output_path is not None else data_path / "reports" / "universe_coverage_report.csv"
    output = output if output.is_absolute() else root / output
    active_tickers = set(active.get("ticker", pd.Series(dtype=str)).dropna().astype(str).str.upper())
    rows = []
    for _, row in master.iterrows():
        ticker = str(row.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        missing = []
        if not str(row.get("name") or "").strip():
            missing.append("name")
        if not str(row.get("exchange") or "").strip():
            missing.append("exchange")
        if str(row.get("asset_type") or "unknown").strip().lower() == "unknown":
            missing.append("asset_type")
        rows.append(
            {
                "ticker": ticker,
                "name": row.get("name", ""),
                "exchange": row.get("exchange", ""),
                "asset_type": row.get("asset_type", "unknown"),
                "sector": row.get("sector", ""),
                "industry": row.get("industry", ""),
                "in_active_universe": ticker in active_tickers,
                "metadata_ready": not missing,
                "missing_metadata": ", ".join(missing),
                "source": row.get("source", ""),
                "updated_at": _now(),
            }
        )
    report = pd.DataFrame(rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(output, index=False)
    return report


def refresh_universe(
    base_dir: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    import_staged: bool = True,
) -> UniverseRefreshResult:
    root = resolve_project_root(base_dir)
    data_path = resolve_data_dir(data_dir, root)
    master_path = data_path / "universe_master.csv"
    active_path = data_path / "universe_active.csv"
    compatibility_path = data_path / "universe.csv"
    rejected_path = data_path / "rejected" / "universe_rejected.csv"
    report_path = data_path / "reports" / "universe_coverage_report.csv"
    staged_path = data_path / "staged" / "universe"
    staged_path.mkdir(parents=True, exist_ok=True)
    master, active = ensure_universe_files(root, data_dir=data_path)

    files = sorted(path for path in staged_path.glob("*.csv") if path.is_file())
    valid_frames: list[pd.DataFrame] = []
    rejected_frames: list[pd.DataFrame] = []
    rows_read = 0
    duplicate_rows = 0
    if import_staged:
        for path in files:
            valid, rejected, summary = _normalize_staged_master(path)
            valid_frames.append(valid)
            rejected_frames.append(rejected)
            rows_read += int(summary["rows_read"])
            duplicate_rows += int(summary["duplicate_rows"])
    valid_all = pd.concat(valid_frames, ignore_index=True) if valid_frames else pd.DataFrame(columns=MASTER_COLUMNS)
    rejected_all = pd.concat(rejected_frames, ignore_index=True) if rejected_frames else pd.DataFrame(columns=REJECTED_COLUMNS)
    if not valid_all.empty:
        combined = pd.concat([master, valid_all], ignore_index=True)
        duplicate_rows += int(combined.duplicated(subset=["ticker"], keep="last").sum())
        master = combined.drop_duplicates(subset=["ticker"], keep="last").sort_values("ticker").reset_index(drop=True)
        _write_csv(master, master_path, MASTER_COLUMNS)
    else:
        _write_csv(master, master_path, MASTER_COLUMNS)
    _write_csv(active, active_path, ACTIVE_COLUMNS)
    rejected_path.parent.mkdir(parents=True, exist_ok=True)
    rejected_all.to_csv(rejected_path, index=False)
    report = build_universe_coverage_report(root, data_dir=data_path, output_path=report_path)
    status = "refreshed"
    if import_staged and not files:
        status = "no_staged_files"
    elif import_staged and valid_all.empty and files:
        status = "no_valid_rows"
    return UniverseRefreshResult(
        status=status,
        master_path=str(master_path),
        active_path=str(active_path),
        compatibility_path=str(compatibility_path),
        rejected_path=str(rejected_path),
        report_path=str(report_path),
        files_read=len(files) if import_staged else 0,
        rows_read=rows_read,
        rows_valid=int(len(valid_all)),
        rows_rejected=int(len(rejected_all)),
        duplicate_rows=duplicate_rows,
        master_rows=int(len(master)),
        active_rows=int(len(active)),
        warnings=[] if compatibility_path.exists() else ["Compatibility data/universe.csv is missing; existing pipeline may not run."],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage master/active universe files and reports.")
    parser.add_argument("--project-root", help="Project root. Defaults to this repository.")
    parser.add_argument("--data-dir", help="Optional data directory. Relative paths resolve from project root.")
    parser.add_argument("--report-only", action="store_true", help="Only write the universe coverage report.")
    parser.add_argument("--ensure-only", action="store_true", help="Only ensure universe_master/universe_active files exist.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = resolve_project_root(args.project_root)
    data_path = resolve_data_dir(args.data_dir, root)
    if args.report_only:
        report = build_universe_coverage_report(root, data_dir=data_path)
        payload = {"status": "report_written", "rows": len(report), "report_path": str(data_path / "reports" / "universe_coverage_report.csv")}
    elif args.ensure_only:
        master, active = ensure_universe_files(root, data_dir=data_path)
        payload = {"status": "ensured", "master_rows": len(master), "active_rows": len(active)}
    else:
        payload = refresh_universe(root, data_dir=data_path).to_dict()
    if args.json:
        print(json.dumps(payload, indent=2))
        return
    print(format_path_context(root, data_path, root / "outputs"))
    for key, value in payload.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
