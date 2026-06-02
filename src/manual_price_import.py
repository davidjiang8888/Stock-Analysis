from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.paths import format_path_context, resolve_data_dir, resolve_project_root


CANONICAL_PRICE_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume", "source"]
REJECTED_PRICE_COLUMNS = [
    "source_file",
    "source_row",
    "ticker",
    "date",
    "close",
    "volume",
    "rejection_reason",
]
PRICE_COVERAGE_COLUMNS = [
    "ticker",
    "in_universe",
    "price_rows",
    "first_date",
    "latest_date",
    "has_price_coverage",
    "usable_for_momentum",
    "remote_price_refresh_status",
    "manual_staged_price_import",
    "recommended_action",
]


@dataclass
class ManualPriceImportResult:
    status: str
    staged_dir: str
    prices_path: str
    rejected_path: str
    coverage_path: str
    files_read: int = 0
    rows_read: int = 0
    rows_valid: int = 0
    rows_rejected: int = 0
    duplicate_rows: int = 0
    rows_written: int = 0
    affected_tickers: list[str] = field(default_factory=list)
    missing_price_tickers: list[str] = field(default_factory=list)
    covered_price_tickers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_header(value: object) -> str:
    normalized = (
        str(value)
        .strip()
        .replace("*", "")
        .replace("%", "pct")
        .replace("/", "_")
        .replace(" ", "_")
        .replace("-", "_")
        .lower()
    )
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized


def _read_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [_normalize_header(column) for column in frame.columns]
    return frame


def _load_universe_tickers(data_dir: Path) -> list[str]:
    tickers: set[str] = set()
    for filename in ("universe_master.csv", "universe_active.csv", "universe.csv"):
        path = data_dir / filename
        if not path.exists():
            continue
        frame = _read_csv(path)
        if "ticker" not in frame.columns:
            continue
        values = frame["ticker"].astype("string").str.upper().str.strip().dropna()
        tickers.update(ticker for ticker in values.unique().tolist() if ticker)
    return sorted(tickers)


def _source_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    return None


def _scalar_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _normalize_staged_file(path: Path, universe_tickers: set[str]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    raw = _read_csv(path)
    rows_read = len(raw)
    working = pd.DataFrame(index=raw.index)
    rejected_rows: list[dict[str, Any]] = []

    ticker_column = _source_column(raw, ("ticker", "symbol"))
    date_column = _source_column(raw, ("date",))
    close_column = _source_column(raw, ("close", "adj_close", "adjusted_close"))
    volume_column = _source_column(raw, ("volume",))

    working["ticker"] = raw[ticker_column] if ticker_column else pd.NA
    working["date"] = raw[date_column] if date_column else pd.NA
    working["close"] = raw[close_column] if close_column else pd.NA
    working["volume"] = raw[volume_column] if volume_column else pd.NA
    for column in ("open", "high", "low"):
        source = _source_column(raw, (column,))
        working[column] = raw[source] if source else pd.NA
    adj_source = _source_column(raw, ("adj_close", "adjusted_close"))
    working["adj_close"] = raw[adj_source] if adj_source else working["close"]
    source_source = _source_column(raw, ("source",))
    working["source"] = raw[source_source] if source_source else f"manual_staged:{path.name}"

    working["source_file"] = str(path)
    working["source_row"] = working.index + 2
    working["ticker"] = working["ticker"].astype("string").str.upper().str.strip()
    working["date"] = pd.to_datetime(working["date"], errors="coerce", format="mixed")
    for column in ("open", "high", "low", "close", "adj_close", "volume"):
        working[column] = pd.to_numeric(working[column], errors="coerce")

    for idx, row in working.iterrows():
        reasons: list[str] = []
        ticker = _scalar_text(row.get("ticker")).upper()
        if not ticker:
            reasons.append("missing_ticker")
        elif ticker not in universe_tickers:
            reasons.append("ticker_not_in_universe")
        if pd.isna(row.get("date")):
            reasons.append("invalid_date")
        close = row.get("close")
        if pd.isna(close):
            reasons.append("missing_close")
        elif close <= 0:
            reasons.append("close_must_be_positive")
        volume = row.get("volume")
        if not pd.isna(volume) and volume < 0:
            reasons.append("volume_must_be_non_negative")
        if reasons:
            rejected_rows.append(
                {
                    "source_file": str(path),
                    "source_row": int(row.get("source_row", idx + 2)),
                    "ticker": ticker,
                    "date": "" if pd.isna(row.get("date")) else pd.Timestamp(row["date"]).date().isoformat(),
                    "close": "" if pd.isna(close) else close,
                    "volume": "" if pd.isna(volume) else volume,
                    "rejection_reason": ";".join(reasons),
                }
            )

    valid_mask = pd.Series(True, index=working.index)
    valid_mask &= working["ticker"].notna() & working["ticker"].isin(universe_tickers)
    valid_mask &= working["date"].notna()
    valid_mask &= working["close"].notna() & working["close"].gt(0)
    valid_mask &= working["volume"].isna() | working["volume"].ge(0)
    valid = working.loc[valid_mask].copy()
    rejected = pd.DataFrame(rejected_rows, columns=REJECTED_PRICE_COLUMNS)
    if valid.empty:
        return pd.DataFrame(columns=CANONICAL_PRICE_COLUMNS), rejected, {"rows_read": rows_read, "duplicate_rows": 0}

    valid["_source_order"] = range(len(valid))
    duplicate_mask = valid.duplicated(subset=["ticker", "date"], keep="last")
    duplicate_rows = int(duplicate_mask.sum())
    if duplicate_rows:
        duplicate_rejections = []
        for _, row in valid.loc[duplicate_mask].iterrows():
            duplicate_rejections.append(
                {
                    "source_file": str(row["source_file"]),
                    "source_row": int(row["source_row"]),
                    "ticker": str(row["ticker"]),
                    "date": pd.Timestamp(row["date"]).date().isoformat(),
                    "close": row["close"],
                    "volume": "" if pd.isna(row["volume"]) else row["volume"],
                    "rejection_reason": "duplicate_ticker_date_dropped",
                }
            )
        rejected = pd.concat([rejected, pd.DataFrame(duplicate_rejections, columns=REJECTED_PRICE_COLUMNS)], ignore_index=True)
    valid = valid.loc[~duplicate_mask].copy()
    valid["date"] = valid["date"].dt.date.astype(str)
    valid = valid.reindex(columns=[*CANONICAL_PRICE_COLUMNS, "source_file", "source_row"])
    return valid, rejected, {"rows_read": rows_read, "duplicate_rows": duplicate_rows}


def _load_existing_prices(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=CANONICAL_PRICE_COLUMNS)
    frame = _read_csv(path)
    if "adjusted_close" in frame.columns and "adj_close" not in frame.columns:
        frame["adj_close"] = frame["adjusted_close"]
    if "adj_close" in frame.columns and "close" not in frame.columns:
        frame["close"] = frame["adj_close"]
    if "close" in frame.columns and "adj_close" not in frame.columns:
        frame["adj_close"] = frame["close"]
    for column in CANONICAL_PRICE_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA
    frame["ticker"] = frame["ticker"].astype("string").str.upper().str.strip()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce", format="mixed")
    for column in ("open", "high", "low", "close", "adj_close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.loc[frame["ticker"].notna() & frame["date"].notna()].copy()
    frame["date"] = frame["date"].dt.date.astype(str)
    return frame.reindex(columns=CANONICAL_PRICE_COLUMNS)


def _write_rejected(rejected: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if rejected.empty:
        pd.DataFrame(columns=REJECTED_PRICE_COLUMNS).to_csv(path, index=False)
        return
    rejected.reindex(columns=REJECTED_PRICE_COLUMNS).to_csv(path, index=False)


def _remote_status() -> str:
    if os.environ.get("STOOQ_API_KEY"):
        return "Stooq remote price refresh configured: STOOQ_API_KEY is set; Yahoo provider also available with PROVIDER=yahoo"
    return (
        "Stooq remote price refresh unavailable: missing STOOQ_API_KEY; "
        "Yahoo provider available with make price-refresh PROVIDER=yahoo; manual staged price import available"
    )


def build_price_coverage_report(
    base_dir: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_path: Path | str | None = None,
) -> pd.DataFrame:
    root = resolve_project_root(base_dir)
    data_path = resolve_data_dir(data_dir, root)
    output = Path(output_path) if output_path is not None else data_path / "price_coverage_report.csv"
    if not output.is_absolute():
        output = root / output
    universe_tickers = _load_universe_tickers(data_path)
    universe_set = set(universe_tickers)
    prices = _load_existing_prices(data_path / "prices.csv")
    rows: list[dict[str, Any]] = []
    remote_status = _remote_status()
    for ticker in universe_tickers:
        ticker_rows = prices.loc[prices["ticker"].astype(str).str.upper().str.strip() == ticker].copy()
        if not ticker_rows.empty:
            ticker_rows["date"] = pd.to_datetime(ticker_rows["date"], errors="coerce", format="mixed")
            ticker_rows = ticker_rows.loc[ticker_rows["date"].notna()]
        price_rows = int(len(ticker_rows))
        first_date = ticker_rows["date"].min().date().isoformat() if price_rows else ""
        latest_date = ticker_rows["date"].max().date().isoformat() if price_rows else ""
        has_coverage = price_rows > 0
        usable = price_rows >= 21
        if usable:
            recommended_action = "No immediate price import needed; maintain coverage."
        else:
            recommended_action = (
                f"Add verified local OHLCV rows to data/staged/prices/ for {ticker}, then run make import-prices. "
                f"Remote fallback: set STOOQ_API_KEY and run make price-refresh TICKERS={ticker}."
            )
        rows.append(
            {
                "ticker": ticker,
                "in_universe": ticker in universe_set,
                "price_rows": price_rows,
                "first_date": first_date,
                "latest_date": latest_date,
                "has_price_coverage": has_coverage,
                "usable_for_momentum": usable,
                "remote_price_refresh_status": remote_status,
                "manual_staged_price_import": "available: place CSV files in data/staged/prices/ and run make import-prices",
                "recommended_action": recommended_action,
            }
        )
    frame = pd.DataFrame(rows, columns=PRICE_COVERAGE_COLUMNS)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    return frame


def import_staged_prices(
    base_dir: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    staged_dir: Path | str | None = None,
    prices_path: Path | str | None = None,
    rejected_path: Path | str | None = None,
    coverage_path: Path | str | None = None,
) -> ManualPriceImportResult:
    root = resolve_project_root(base_dir)
    data_path = resolve_data_dir(data_dir, root)
    staged_path = Path(staged_dir) if staged_dir is not None else data_path / "staged" / "prices"
    prices_output = Path(prices_path) if prices_path is not None else data_path / "prices.csv"
    rejected_output = Path(rejected_path) if rejected_path is not None else data_path / "price_import_rejected.csv"
    coverage_output = Path(coverage_path) if coverage_path is not None else data_path / "price_coverage_report.csv"
    staged_path = staged_path if staged_path.is_absolute() else root / staged_path
    prices_output = prices_output if prices_output.is_absolute() else root / prices_output
    rejected_output = rejected_output if rejected_output.is_absolute() else root / rejected_output
    coverage_output = coverage_output if coverage_output.is_absolute() else root / coverage_output
    staged_path.mkdir(parents=True, exist_ok=True)
    universe_tickers = set(_load_universe_tickers(data_path))
    warnings: list[str] = []
    if not universe_tickers:
        warnings.append("No universe tickers were found; staged price rows cannot be trusted without data/universe.csv.")

    files = sorted(path for path in staged_path.glob("*.csv") if path.is_file())
    valid_frames: list[pd.DataFrame] = []
    rejected_frames: list[pd.DataFrame] = []
    rows_read = 0
    duplicate_rows = 0
    for path in files:
        valid, rejected, summary = _normalize_staged_file(path, universe_tickers)
        valid_frames.append(valid)
        rejected_frames.append(rejected)
        rows_read += int(summary["rows_read"])
        duplicate_rows += int(summary["duplicate_rows"])

    valid_all = pd.concat(valid_frames, ignore_index=True) if valid_frames else pd.DataFrame(columns=CANONICAL_PRICE_COLUMNS)
    rejected_all = pd.concat(rejected_frames, ignore_index=True) if rejected_frames else pd.DataFrame(columns=REJECTED_PRICE_COLUMNS)
    if not valid_all.empty:
        cross_duplicate_mask = valid_all.duplicated(subset=["ticker", "date"], keep="last")
        cross_duplicates = int(cross_duplicate_mask.sum())
        if cross_duplicates:
            dropped = valid_all.loc[cross_duplicate_mask].copy()
            rejected_all = pd.concat(
                [
                    rejected_all,
                    pd.DataFrame(
                        [
                            {
                                "source_file": row.get("source_file", ""),
                                "source_row": row.get("source_row", ""),
                                "ticker": row["ticker"],
                                "date": row["date"],
                                "close": row["close"],
                                "volume": "" if pd.isna(row["volume"]) else row["volume"],
                                "rejection_reason": "duplicate_ticker_date_dropped_across_files",
                            }
                            for _, row in dropped.iterrows()
                        ],
                        columns=REJECTED_PRICE_COLUMNS,
                    ),
                ],
                ignore_index=True,
            )
            duplicate_rows += cross_duplicates
        valid_all = valid_all.loc[~cross_duplicate_mask].copy()

    valid_canonical = valid_all.reindex(columns=CANONICAL_PRICE_COLUMNS)
    existing = _load_existing_prices(prices_output)
    if not valid_canonical.empty:
        combined = pd.concat([existing, valid_canonical], ignore_index=True)
        combined = combined.drop_duplicates(subset=["ticker", "date"], keep="last")
        combined = combined.sort_values(["ticker", "date"]).reset_index(drop=True)
        prices_output.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(prices_output, index=False)
    else:
        combined = existing.copy()

    _write_rejected(rejected_all, rejected_output)
    rejected_reports_output = data_path / "rejected" / "price_import_rejected.csv"
    _write_rejected(rejected_all, rejected_reports_output)
    coverage = build_price_coverage_report(root, data_dir=data_path, output_path=coverage_output)
    covered = sorted(coverage.loc[coverage["has_price_coverage"].astype(bool), "ticker"].astype(str).tolist())
    missing = sorted(coverage.loc[~coverage["has_price_coverage"].astype(bool), "ticker"].astype(str).tolist())
    status = "no_staged_files" if not files else "imported"
    if files and valid_all.empty:
        status = "no_valid_rows"
    return ManualPriceImportResult(
        status=status,
        staged_dir=str(staged_path),
        prices_path=str(prices_output),
        rejected_path=str(rejected_output),
        coverage_path=str(coverage_output),
        files_read=len(files),
        rows_read=rows_read,
        rows_valid=int(len(valid_all)),
        rows_rejected=int(len(rejected_all)),
        duplicate_rows=duplicate_rows,
        rows_written=int(len(combined)),
        affected_tickers=sorted(valid_all["ticker"].astype(str).unique().tolist()) if not valid_all.empty else [],
        missing_price_tickers=missing,
        covered_price_tickers=covered,
        warnings=warnings,
    )


def _print_result(result: ManualPriceImportResult) -> None:
    payload = result.to_dict()
    for key, value in payload.items():
        print(f"{key}: {value}")


def _format_ticker_summary(tickers: list[str], *, label: str, limit: int) -> str:
    sample = tickers[:limit]
    suffix = f" (sample: {', '.join(sample)})" if sample else ""
    suppressed = len(tickers) - len(sample)
    if suppressed > 0:
        suffix += f"; {suppressed} more in data/price_coverage_report.csv"
    return f"{label}: {len(tickers)}{suffix}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Import verified local staged price CSVs and report price coverage.")
    parser.add_argument("--project-root", help="Project root. Defaults to this repository.")
    parser.add_argument("--data-dir", help="Optional data directory. Relative paths resolve from project root.")
    parser.add_argument("--staged-dir", default="data/staged/prices", help="Directory containing verified local price CSV files.")
    parser.add_argument("--coverage-only", action="store_true", help="Only regenerate data/price_coverage_report.csv.")
    parser.add_argument("--top-n", type=int, default=25, help="Number of covered/missing tickers to sample in terminal output.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()

    root = resolve_project_root(args.project_root)
    data_path = resolve_data_dir(args.data_dir, root)
    staged_path = Path(args.staged_dir)
    if not staged_path.is_absolute():
        staged_path = root / staged_path
    if args.coverage_only:
        coverage = build_price_coverage_report(root, data_dir=data_path)
        payload = {
            "status": "coverage_written",
            "coverage_path": str(data_path / "price_coverage_report.csv"),
            "missing_price_tickers": sorted(coverage.loc[~coverage["has_price_coverage"].astype(bool), "ticker"].astype(str).tolist()),
            "covered_price_tickers": sorted(coverage.loc[coverage["has_price_coverage"].astype(bool), "ticker"].astype(str).tolist()),
            "remote_price_refresh_status": _remote_status(),
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(format_path_context(root, data_path, root / "outputs"))
            print(f"status: {payload['status']}")
            print(f"coverage_path: {payload['coverage_path']}")
            print(_format_ticker_summary(payload["missing_price_tickers"], label="missing_price_tickers", limit=max(args.top_n, 0)))
            print(_format_ticker_summary(payload["covered_price_tickers"], label="covered_price_tickers", limit=max(args.top_n, 0)))
            print(f"remote_price_refresh_status: {payload['remote_price_refresh_status']}")
        return

    result = import_staged_prices(root, data_dir=data_path, staged_dir=staged_path)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return
    print(format_path_context(root, data_path, root / "outputs"))
    _print_result(result)


if __name__ == "__main__":
    main()
