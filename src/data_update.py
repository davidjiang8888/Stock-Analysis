from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from time import sleep
from typing import Any, Callable, Protocol
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from src.config import AppConfig
from src.paths import format_path_context, resolve_data_dir, resolve_outputs_dir, resolve_project_root


PRICE_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
PRICE_IMPORT_REQUIRED_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "volume"]
PRICE_IMPORT_OPTIONAL_COLUMNS = ["adjusted_close", "adj_close", "source", "as_of_date", "notes"]
PRICE_IMPORT_OUTPUT_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume", "source", "as_of_date", "notes"]
PRICE_STATUS_COLUMNS = [
    "run_timestamp",
    "ticker",
    "requested_start",
    "requested_end",
    "provider",
    "status",
    "rows_fetched",
    "rows_merged",
    "error_category",
    "error_message",
    "fallback_used",
    "recommended_action",
]


def _normalize_columns(columns: list[str]) -> list[str]:
    return [
        column.strip()
        .replace("%", "pct")
        .replace("/", "_")
        .replace(" ", "_")
        .replace("-", "_")
        .lower()
        for column in columns
    ]


def _ensure_price_aliases(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    if "adjusted_close" in normalized.columns and "adj_close" not in normalized.columns:
        normalized["adj_close"] = normalized["adjusted_close"]
    if "adj_close" in normalized.columns and "close" not in normalized.columns:
        normalized["close"] = normalized["adj_close"]
    if "close" in normalized.columns and "adj_close" not in normalized.columns:
        normalized["adj_close"] = normalized["close"]
    return normalized


def _normalize_ticker_series(series: pd.Series) -> pd.Series:
    return series.astype("string").str.upper().str.strip()


def _stooq_symbol(ticker: str) -> str:
    return f"{ticker.lower()}.us"


class PriceHistorySource(Protocol):
    def fetch_history(self, ticker: str) -> tuple[pd.DataFrame, list[str]]:
        ...


@dataclass
class PriceUpdateResult:
    path: Path
    tickers_requested: list[str]
    tickers_updated: list[str] = field(default_factory=list)
    tickers_missing: list[str] = field(default_factory=list)
    tickers_skipped_fresh: list[str] = field(default_factory=list)
    rows_written: int = 0
    chunks_processed: int = 0
    warnings: list[str] = field(default_factory=list)
    status_path: Path | None = None
    status_rows: list[dict[str, Any]] = field(default_factory=list)


class StooqDailyPriceSource:
    def __init__(self, base_url: str = "https://stooq.com/q/d/l/") -> None:
        self.base_url = base_url

    def fetch_history(self, ticker: str) -> tuple[pd.DataFrame, list[str]]:
        symbol = _stooq_symbol(ticker)
        url = f"{self.base_url}?{urlencode({'s': symbol, 'i': 'd'})}"
        try:
            with urlopen(url, timeout=20) as response:
                payload = response.read().decode("utf-8")
        except URLError as exc:
            return pd.DataFrame(columns=PRICE_COLUMNS), [f"{ticker}: update failed from Stooq ({exc})"]

        if not payload.strip() or "No data" in payload:
            return pd.DataFrame(columns=PRICE_COLUMNS), [f"{ticker}: free daily data source returned no rows."]

        frame = pd.read_csv(StringIO(payload))
        frame.columns = _normalize_columns(list(frame.columns))
        required = {"date", "open", "high", "low", "close", "volume"}
        missing = required - set(frame.columns)
        if missing:
            return pd.DataFrame(columns=PRICE_COLUMNS), [f"{ticker}: source response is missing columns {sorted(missing)}."]

        frame["date"] = pd.to_datetime(frame["date"], errors="coerce", format="mixed")
        frame = frame.loc[frame["date"].notna()].copy()
        if frame.empty:
            return pd.DataFrame(columns=PRICE_COLUMNS), [f"{ticker}: source rows had no valid dates."]

        for numeric_column in ("open", "high", "low", "close", "volume"):
            frame[numeric_column] = pd.to_numeric(frame[numeric_column], errors="coerce")
        frame = frame.loc[frame["close"].notna() & frame["close"].gt(0) & frame["volume"].notna() & frame["volume"].ge(0)].copy()
        if frame.empty:
            return pd.DataFrame(columns=PRICE_COLUMNS), [f"{ticker}: source rows were invalid after normalization."]

        frame["ticker"] = ticker.upper()
        frame["adj_close"] = frame["close"]
        return frame[PRICE_COLUMNS].copy(), []


def _read_csv_if_present(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    frame.columns = _normalize_columns(list(frame.columns))
    frame = _ensure_price_aliases(frame)
    return frame


def load_update_tickers(
    base_dir: Path,
    config: AppConfig | None = None,
    universe_file: Path | None = None,
    data_dir: Path | None = None,
) -> list[str]:
    config = config or AppConfig.load(base_dir / "config.yaml")
    data_dir = data_dir or (base_dir / "data")
    universe = _read_csv_if_present(universe_file or (data_dir / "universe.csv"))
    holdings = _read_csv_if_present(data_dir / "holdings.csv")
    theme_map = _read_csv_if_present(data_dir / "theme_map.csv")

    tickers: set[str] = set()
    if "ticker" in universe.columns:
        tickers.update(_normalize_ticker_series(universe["ticker"]).dropna().tolist())
    if "ticker" in holdings.columns:
        tickers.update(_normalize_ticker_series(holdings["ticker"]).dropna().tolist())
    for universe_etf_column in ("sector_etf", "sectoretf"):
        if universe_etf_column in universe.columns:
            tickers.update(_normalize_ticker_series(universe[universe_etf_column]).dropna().tolist())
    if "etf" in theme_map.columns:
        tickers.update(_normalize_ticker_series(theme_map["etf"]).dropna().tolist())

    for benchmark_group in config.benchmarks.values():
        tickers.update(str(ticker).upper().strip() for ticker in benchmark_group if str(ticker).strip())
    return sorted(ticker for ticker in tickers if ticker)


def _load_existing_prices(path: Path) -> pd.DataFrame:
    frame = _read_csv_if_present(path)
    if frame.empty:
        return pd.DataFrame(columns=PRICE_COLUMNS)

    if "adj_close" in frame.columns and "close" not in frame.columns:
        frame["close"] = frame["adj_close"]
    if "close" in frame.columns and "adj_close" not in frame.columns:
        frame["adj_close"] = frame["close"]
    for optional_column in ("open", "high", "low"):
        if optional_column not in frame.columns:
            frame[optional_column] = pd.NA

    if "ticker" in frame.columns:
        frame["ticker"] = _normalize_ticker_series(frame["ticker"])
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce", format="mixed")
    for numeric_column in ("open", "high", "low", "close", "adj_close", "volume"):
        if numeric_column in frame.columns:
            frame[numeric_column] = pd.to_numeric(frame[numeric_column], errors="coerce")

    frame = frame.loc[frame.get("date", pd.Series(dtype="datetime64[ns]")).notna()].copy()
    if frame.empty:
        return pd.DataFrame(columns=PRICE_COLUMNS)
    return frame[PRICE_COLUMNS].copy()


def _chunked(items: list[str], chunk_size: int) -> list[list[str]]:
    if chunk_size <= 0:
        return [items]
    return [items[index : index + chunk_size] for index in range(0, len(items), chunk_size)]


def _ordered_normalized_tickers(tickers: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for ticker in tickers:
        normalized = _normalize_ticker_series(pd.Series([ticker])).dropna().tolist()
        if not normalized:
            continue
        value = normalized[0]
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _fresh_tickers(existing: pd.DataFrame, freshness_days: int) -> set[str]:
    if existing.empty or "ticker" not in existing.columns or "date" not in existing.columns:
        return set()
    cutoff = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize() - pd.Timedelta(days=freshness_days)
    latest_by_ticker = existing.groupby("ticker")["date"].max()
    return {
        ticker
        for ticker, latest_date in latest_by_ticker.items()
        if pd.notna(latest_date) and latest_date >= cutoff
    }


def _latest_price_date(existing: pd.DataFrame, ticker: str) -> str:
    if existing.empty or "ticker" not in existing.columns or "date" not in existing.columns:
        return ""
    rows = existing.loc[existing["ticker"].astype(str).str.upper().str.strip() == ticker]
    if rows.empty:
        return ""
    latest = rows["date"].max()
    if pd.isna(latest):
        return ""
    return pd.Timestamp(latest).date().isoformat()


def _next_requested_start(existing: pd.DataFrame, ticker: str) -> str:
    latest = _latest_price_date(existing, ticker)
    if not latest:
        return ""
    next_date = pd.Timestamp(latest) + pd.Timedelta(days=1)
    return next_date.date().isoformat()


def _categorize_price_error(messages: list[str]) -> tuple[str, str]:
    message = " | ".join(str(item) for item in messages if str(item).strip())
    lowered = message.lower()
    if not message:
        return "failed", ""
    if "tokenizing" in lowered or "parser" in lowered or "parse" in lowered:
        return "parse_error", message
    if "url" in lowered or "timed out" in lowered or "network" in lowered or "connection" in lowered:
        return "network_error", message
    if "no data" in lowered or "no rows" in lowered:
        return "no_rows", message
    if "unavailable" in lowered or "source" in lowered:
        return "source_unavailable", message
    return "failed", message


def _price_recommended_action(status: str, ticker: str, has_local_data: bool) -> str:
    if status == "fetched":
        return "No action needed; remote rows were merged into local prices."
    if status == "skipped_fresh":
        return "Leave unchanged because local data exists and is fresh."
    if status == "no_rows":
        return "Verify ticker symbol or add verified rows to data/imports/prices.csv."
    if status == "parse_error":
        return "Retry later or use staged manual prices in data/imports/prices.csv."
    if status == "network_error":
        return "Retry later, reduce ticker batch size, or use staged manual prices in data/imports/prices.csv."
    if status == "source_unavailable":
        return "Retry later or use staged manual prices in data/imports/prices.csv."
    if has_local_data:
        return "Leave unchanged because local data exists; use staged manual prices if you need fresher rows."
    return f"Add verified rows to data/imports/prices.csv, then validate and preview before applying for {ticker}."


def _price_status_row(
    *,
    run_timestamp: str,
    ticker: str,
    requested_start: str,
    requested_end: str,
    provider: str,
    status: str,
    rows_fetched: int = 0,
    rows_merged: int = 0,
    error_message: str = "",
    fallback_used: bool = False,
    has_local_data: bool = False,
) -> dict[str, Any]:
    return {
        "run_timestamp": run_timestamp,
        "ticker": ticker,
        "requested_start": requested_start,
        "requested_end": requested_end,
        "provider": provider,
        "status": status,
        "rows_fetched": rows_fetched,
        "rows_merged": rows_merged,
        "error_category": "" if status in {"fetched", "skipped_fresh"} else status,
        "error_message": error_message,
        "fallback_used": fallback_used,
        "recommended_action": _price_recommended_action(status, ticker, has_local_data),
    }


def write_price_update_status(rows: list[dict[str, Any]], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "price_update_status.csv"
    pd.DataFrame(rows, columns=PRICE_STATUS_COLUMNS).to_csv(path, index=False)
    return path


def update_local_price_data(
    base_dir: Path | None = None,
    source: PriceHistorySource | None = None,
    tickers: list[str] | None = None,
    *,
    data_dir: Path | None = None,
    output_dir: Path | None = None,
    chunk_size: int = 50,
    max_tickers: int | None = None,
    refresh: bool = False,
    freshness_days: int = 1,
    universe_file: Path | None = None,
    retry_attempts: int = 1,
    retry_backoff_seconds: float = 0.25,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> PriceUpdateResult:
    base_dir = resolve_project_root(base_dir)
    data_dir = resolve_data_dir(data_dir, base_dir)
    output_dir = resolve_outputs_dir(output_dir, base_dir)
    config = AppConfig.load(base_dir / "config.yaml")
    prices_path = data_dir / "prices.csv"
    source = source or StooqDailyPriceSource()
    provider_name = source.__class__.__name__
    run_timestamp = datetime.now(timezone.utc).isoformat()
    requested_end = pd.Timestamp.now(tz="UTC").date().isoformat()
    tickers = tickers or load_update_tickers(base_dir, config, universe_file=universe_file, data_dir=data_dir)
    tickers = _ordered_normalized_tickers(tickers)
    if max_tickers is not None and max_tickers > 0:
        tickers = tickers[:max_tickers]

    existing = _load_existing_prices(prices_path)
    warnings: list[str] = []
    updated: list[str] = []
    missing: list[str] = []
    skipped_fresh: list[str] = []
    combined = existing.copy()
    existing_tickers = set(existing["ticker"].dropna().astype(str).str.upper().str.strip()) if "ticker" in existing.columns else set()
    status_rows: list[dict[str, Any]] = []
    tickers_to_fetch = tickers
    if not refresh:
        fresh_ticker_set = _fresh_tickers(existing, freshness_days)
        skipped_fresh = [ticker for ticker in tickers if ticker in fresh_ticker_set]
        tickers_to_fetch = [ticker for ticker in tickers if ticker not in fresh_ticker_set]
        for ticker in skipped_fresh:
            status_rows.append(
                _price_status_row(
                    run_timestamp=run_timestamp,
                    ticker=ticker,
                    requested_start=_next_requested_start(existing, ticker),
                    requested_end=requested_end,
                    provider=provider_name,
                    status="skipped_fresh",
                    rows_fetched=0,
                    rows_merged=0,
                    fallback_used=False,
                    has_local_data=True,
                )
            )
        if skipped_fresh:
            warnings.append(
                f"Skipped {len(skipped_fresh)} ticker(s) that already have price data within the last {freshness_days} day(s)."
            )

    if not tickers_to_fetch:
        status_path = write_price_update_status(status_rows, output_dir)
        return PriceUpdateResult(
            path=prices_path,
            tickers_requested=tickers,
            tickers_updated=[],
            tickers_missing=missing,
            tickers_skipped_fresh=skipped_fresh,
            rows_written=len(existing),
            chunks_processed=0,
            warnings=warnings + ["No remote price rows were added; kept the existing local CSV fallback."],
            status_path=status_path,
            status_rows=status_rows,
        )

    chunks = _chunked(tickers_to_fetch, chunk_size)
    processed_chunks = 0
    for chunk_index, chunk in enumerate(chunks, start=1):
        fetched_frames: list[pd.DataFrame] = []
        for ticker in chunk:
            last_warning_count = len(warnings)
            frame = pd.DataFrame(columns=PRICE_COLUMNS)
            fetch_warnings: list[str] = []
            for attempt in range(retry_attempts + 1):
                try:
                    frame, fetch_warnings = source.fetch_history(ticker)
                except Exception as exc:  # pragma: no cover - defensive runtime path
                    fetch_warnings = [f"{ticker}: update failed ({exc})"]
                    frame = pd.DataFrame(columns=PRICE_COLUMNS)
                if frame.empty and attempt < retry_attempts:
                    sleep(retry_backoff_seconds * (attempt + 1))
                    continue
                warnings.extend(fetch_warnings)
                break
            if frame.empty:
                missing.append(ticker)
                status, message = _categorize_price_error(fetch_warnings)
                status_rows.append(
                    _price_status_row(
                        run_timestamp=run_timestamp,
                        ticker=ticker,
                        requested_start=_next_requested_start(existing, ticker),
                        requested_end=requested_end,
                        provider=provider_name,
                        status=status,
                        rows_fetched=0,
                        rows_merged=0,
                        error_message=message,
                        fallback_used=ticker in existing_tickers,
                        has_local_data=ticker in existing_tickers,
                    )
                )
                continue
            fetched_frames.append(frame)
            updated.append(ticker)
            status_rows.append(
                _price_status_row(
                    run_timestamp=run_timestamp,
                    ticker=ticker,
                    requested_start=_next_requested_start(existing, ticker),
                    requested_end=requested_end,
                    provider=provider_name,
                    status="fetched",
                    rows_fetched=len(frame),
                    rows_merged=len(frame),
                    fallback_used=False,
                    has_local_data=True,
                )
            )

            if progress_callback is not None:
                progress_callback(
                    {
                        "event": "ticker_complete",
                        "ticker": ticker,
                        "chunk_index": chunk_index,
                        "chunks_total": len(chunks),
                        "warnings_added": len(warnings) - last_warning_count,
                    }
                )

        if fetched_frames:
            combined = pd.concat([combined, *fetched_frames], ignore_index=True)
            combined = (
                combined.drop_duplicates(subset=["date", "ticker"], keep="last")
                .sort_values(["ticker", "date"])
                .reset_index(drop=True)
            )
            combined.to_csv(prices_path, index=False)
        processed_chunks += 1
        if progress_callback is not None:
            progress_callback(
                {
                    "event": "chunk_complete",
                    "chunk_index": chunk_index,
                    "chunks_total": len(chunks),
                    "tickers_in_chunk": len(chunk),
                    "updated_so_far": len(updated),
                    "missing_so_far": len(missing),
                }
            )

    if not updated:
        status_path = write_price_update_status(status_rows, output_dir)
        return PriceUpdateResult(
            path=prices_path,
            tickers_requested=tickers,
            tickers_updated=[],
            tickers_missing=missing,
            tickers_skipped_fresh=skipped_fresh,
            rows_written=len(existing),
            chunks_processed=processed_chunks,
            warnings=warnings + ["No remote price rows were added; kept the existing local CSV fallback."],
            status_path=status_path,
            status_rows=status_rows,
        )

    status_path = write_price_update_status(status_rows, output_dir)
    return PriceUpdateResult(
        path=prices_path,
        tickers_requested=tickers,
        tickers_updated=updated,
        tickers_missing=missing,
        tickers_skipped_fresh=skipped_fresh,
        rows_written=len(combined),
        chunks_processed=processed_chunks,
        warnings=warnings,
        status_path=status_path,
        status_rows=status_rows,
    )


def _resolve_import_dir(data_dir: Path, import_dir: Path | None = None) -> Path:
    return import_dir or (data_dir / "imports")


def _read_price_import(path: Path) -> tuple[pd.DataFrame, list[str]]:
    if not path.exists():
        return pd.DataFrame(), ["Staged price import file is not present."]
    frame = pd.read_csv(path)
    frame.columns = _normalize_columns(list(frame.columns))
    frame = _ensure_price_aliases(frame)
    return frame, []


def _serialize_price_date(value: Any) -> str:
    if pd.isna(value):
        return ""
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return ""
    return timestamp.date().isoformat()


def _normalize_price_import_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    warnings: list[str] = []
    unknown_columns = sorted(set(frame.columns) - set(PRICE_IMPORT_REQUIRED_COLUMNS) - set(PRICE_IMPORT_OPTIONAL_COLUMNS) - {"adj_close"})
    if unknown_columns:
        warnings.append(f"Unknown columns detected and ignored: {', '.join(unknown_columns)}.")

    missing_required = sorted(set(PRICE_IMPORT_REQUIRED_COLUMNS) - set(frame.columns))
    if missing_required:
        return (
            pd.DataFrame(columns=PRICE_IMPORT_OUTPUT_COLUMNS),
            {
                "status": "invalid",
                "missing_required_columns": missing_required,
                "unknown_columns": unknown_columns,
                "warnings": warnings,
                "row_count": len(frame),
                "valid_rows": 0,
                "skipped_rows": len(frame),
                "duplicate_rows": 0,
                "affected_tickers": [],
            },
        )

    normalized = frame.copy()
    normalized["ticker"] = _normalize_ticker_series(normalized["ticker"])
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce", format="mixed")
    if "as_of_date" in normalized.columns:
        normalized["as_of_date"] = pd.to_datetime(normalized["as_of_date"], errors="coerce", format="mixed")
    for numeric_column in ("open", "high", "low", "close", "adj_close", "volume"):
        if numeric_column in normalized.columns:
            before = normalized[numeric_column].notna().sum()
            normalized[numeric_column] = pd.to_numeric(normalized[numeric_column], errors="coerce")
            after = normalized[numeric_column].notna().sum()
            if after < before:
                warnings.append(f"{numeric_column}: {before - after} rows could not be parsed as numeric values.")

    if "adj_close" not in normalized.columns:
        normalized["adj_close"] = normalized["close"]

    valid_mask = pd.Series(True, index=normalized.index)
    valid_mask &= normalized["date"].notna()
    valid_mask &= normalized["ticker"].notna() & normalized["ticker"].astype(str).str.strip().ne("")
    for required_numeric in ("open", "high", "low", "close", "volume"):
        valid_mask &= normalized[required_numeric].notna()
    valid_mask &= normalized["close"].gt(0)
    valid_mask &= normalized["volume"].ge(0)
    valid_mask &= normalized["high"].ge(normalized["low"])
    skipped_invalid = int((~valid_mask).sum())
    if skipped_invalid:
        warnings.append(f"Skipped {skipped_invalid} invalid staged price row(s).")

    valid = normalized.loc[valid_mask].copy()
    if valid.empty:
        return (
            pd.DataFrame(columns=PRICE_IMPORT_OUTPUT_COLUMNS),
            {
                "status": "invalid",
                "missing_required_columns": [],
                "unknown_columns": unknown_columns,
                "warnings": warnings,
                "row_count": len(frame),
                "valid_rows": 0,
                "skipped_rows": skipped_invalid,
                "duplicate_rows": 0,
                "affected_tickers": [],
            },
        )

    duplicate_rows = int(valid.duplicated(subset=["date", "ticker"], keep="last").sum())
    if duplicate_rows:
        warnings.append(f"Deduplicated {duplicate_rows} duplicate date+ticker staged row(s), keeping the last row.")
    valid = valid.drop_duplicates(subset=["date", "ticker"], keep="last").copy()

    valid["date"] = valid["date"].apply(_serialize_price_date)
    if "as_of_date" in valid.columns:
        valid["as_of_date"] = valid["as_of_date"].apply(_serialize_price_date)
    output_columns = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
    for optional_column in ("source", "as_of_date", "notes"):
        if optional_column in valid.columns:
            output_columns.append(optional_column)
    valid = valid.reindex(columns=output_columns)

    status = "valid_with_warnings" if warnings else "valid"
    return (
        valid,
        {
            "status": status,
            "missing_required_columns": [],
            "unknown_columns": unknown_columns,
            "warnings": warnings,
            "row_count": len(frame),
            "valid_rows": len(valid),
            "skipped_rows": skipped_invalid + duplicate_rows,
            "duplicate_rows": duplicate_rows,
            "affected_tickers": sorted(valid["ticker"].dropna().unique().tolist()),
        },
    )


def validate_price_imports(
    base_dir: Path | None = None,
    *,
    data_dir: Path | None = None,
    import_dir: Path | None = None,
) -> dict[str, Any]:
    base_dir = resolve_project_root(base_dir)
    data_dir = resolve_data_dir(data_dir, base_dir)
    import_dir = _resolve_import_dir(data_dir, import_dir)
    staged_path = import_dir / "prices.csv"
    if not staged_path.exists():
        return {
            "status": "no_staged_file",
            "staged_path": str(staged_path),
            "canonical_path": str(data_dir / "prices.csv"),
            "row_count": 0,
            "valid_rows": 0,
            "skipped_rows": 0,
            "duplicate_rows": 0,
            "affected_tickers": [],
            "missing_required_columns": PRICE_IMPORT_REQUIRED_COLUMNS,
            "unknown_columns": [],
            "warnings": ["No staged price import file found."],
        }
    staged_frame, read_warnings = _read_price_import(staged_path)
    valid_frame, summary = _normalize_price_import_frame(staged_frame)
    return {
        **summary,
        "staged_path": str(staged_path),
        "canonical_path": str(data_dir / "prices.csv"),
        "warnings": read_warnings + summary["warnings"],
        "valid_frame": valid_frame,
    }


def _load_canonical_price_frame(path: Path) -> pd.DataFrame:
    frame = _read_csv_if_present(path)
    if frame.empty:
        return pd.DataFrame(columns=PRICE_COLUMNS)
    if "ticker" in frame.columns:
        frame["ticker"] = _normalize_ticker_series(frame["ticker"])
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce", format="mixed").apply(_serialize_price_date)
    return frame


def _price_key_series(frame: pd.DataFrame) -> pd.Series:
    return frame[["date", "ticker"]].astype(str).agg("||".join, axis=1)


def preview_price_import_merge(
    base_dir: Path | None = None,
    *,
    data_dir: Path | None = None,
    import_dir: Path | None = None,
) -> dict[str, Any]:
    base_dir = resolve_project_root(base_dir)
    data_dir = resolve_data_dir(data_dir, base_dir)
    validation = validate_price_imports(base_dir, data_dir=data_dir, import_dir=import_dir)
    valid_frame = validation.pop("valid_frame", pd.DataFrame())
    if validation["status"] == "no_staged_file":
        return {**validation, "new_rows": 0, "updated_rows": 0, "unchanged_rows": 0, "skipped_rows": 0}
    if validation["status"] == "invalid":
        return {**validation, "new_rows": 0, "updated_rows": 0, "unchanged_rows": 0}

    canonical = _load_canonical_price_frame(Path(validation["canonical_path"]))
    canonical_keys = _price_key_series(canonical) if not canonical.empty and {"date", "ticker"}.issubset(canonical.columns) else pd.Series(dtype="object")
    canonical_lookup = canonical.assign(_merge_key=canonical_keys).set_index("_merge_key") if not canonical.empty else pd.DataFrame()
    staged_keys = _price_key_series(valid_frame)
    new_rows = 0
    updated_rows = 0
    unchanged_rows = 0
    overwrite_keys: list[str] = []
    new_keys: list[str] = []
    compare_columns = [column for column in PRICE_IMPORT_OUTPUT_COLUMNS if column not in {"date", "ticker"} and column in valid_frame.columns]
    for _, staged_row in valid_frame.assign(_merge_key=staged_keys).iterrows():
        merge_key = staged_row["_merge_key"]
        key_text = f"date={staged_row['date']}, ticker={staged_row['ticker']}"
        if canonical_lookup.empty or merge_key not in canonical_lookup.index:
            new_rows += 1
            new_keys.append(key_text)
            continue
        canonical_row = canonical_lookup.loc[merge_key]
        if isinstance(canonical_row, pd.DataFrame):
            canonical_row = canonical_row.iloc[-1]
        changed = False
        for column in compare_columns:
            left = staged_row.get(column)
            right = canonical_row.get(column)
            if pd.isna(left) and pd.isna(right):
                continue
            if str(left) != str(right):
                changed = True
                break
        if changed:
            updated_rows += 1
            overwrite_keys.append(key_text)
        else:
            unchanged_rows += 1

    return {
        **validation,
        "new_rows": new_rows,
        "updated_rows": updated_rows,
        "unchanged_rows": unchanged_rows,
        "overwrite_keys": overwrite_keys,
        "new_keys": new_keys,
    }


def _backup_price_file(path: Path, data_dir: Path) -> str | None:
    if not path.exists():
        return None
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = data_dir / "backups" / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / path.name
    shutil.copy2(path, backup_path)
    return str(backup_path)


def apply_price_import_merge(
    base_dir: Path | None = None,
    *,
    data_dir: Path | None = None,
    import_dir: Path | None = None,
    backup: bool = True,
) -> dict[str, Any]:
    base_dir = resolve_project_root(base_dir)
    data_dir = resolve_data_dir(data_dir, base_dir)
    preview = preview_price_import_merge(base_dir, data_dir=data_dir, import_dir=import_dir)
    if preview["status"] in {"no_staged_file", "invalid"}:
        return {**preview, "applied": False, "backup_path": None}

    validation = validate_price_imports(base_dir, data_dir=data_dir, import_dir=import_dir)
    staged = validation.pop("valid_frame", pd.DataFrame())
    canonical_path = Path(preview["canonical_path"])
    canonical = _load_canonical_price_frame(canonical_path)
    output_columns = list(canonical.columns)
    for column in PRICE_IMPORT_OUTPUT_COLUMNS:
        if column in staged.columns and column not in output_columns:
            output_columns.append(column)
    if not output_columns:
        output_columns = PRICE_IMPORT_OUTPUT_COLUMNS
    canonical = canonical.reindex(columns=output_columns)
    staged = staged.reindex(columns=output_columns)

    backup_path = _backup_price_file(canonical_path, data_dir) if backup and (preview["new_rows"] or preview["updated_rows"]) else None
    if canonical.empty:
        merged = staged.copy()
    else:
        canonical_indexed = canonical.set_index(["date", "ticker"], drop=False).astype(object)
        staged_indexed = staged.set_index(["date", "ticker"], drop=False).astype(object)
        overlapping = canonical_indexed.index.intersection(staged_indexed.index)
        update_columns = [column for column in staged_indexed.columns if column not in {"date", "ticker"}]
        if len(overlapping) and update_columns:
            canonical_indexed.loc[overlapping, update_columns] = staged_indexed.loc[overlapping, update_columns]
        new_rows = staged_indexed.loc[~staged_indexed.index.isin(canonical_indexed.index)]
        merged = pd.concat([canonical_indexed, new_rows], axis=0).reset_index(drop=True)
    if {"ticker", "date"}.issubset(merged.columns):
        merged = merged.sort_values(["ticker", "date"]).reset_index(drop=True)
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(canonical_path, index=False)
    return {
        **preview,
        "applied": True,
        "backup_path": backup_path,
        "rows_written": len(merged),
    }


def _print_price_import_summary(summary: dict[str, Any]) -> None:
    printable = {key: value for key, value in summary.items() if key != "valid_frame"}
    for key, value in printable.items():
        print(f"{key}: {value}")


def show_price_update_status(base_dir: Path | None = None, *, output_dir: Path | None = None) -> dict[str, Any]:
    base_dir = resolve_project_root(base_dir)
    output_dir = resolve_outputs_dir(output_dir, base_dir)
    path = output_dir / "price_update_status.csv"
    if not path.exists():
        return {
            "status": "missing_file",
            "path": str(path),
            "rows": [],
            "warnings": [
                "Price update status has not been generated yet. Start with make status, then follow the printed price focus or runbook path. For downloaded files, use make price-normalize before validate/preview/apply."
            ],
        }
    frame = pd.read_csv(path)
    return {
        "status": "available",
        "path": str(path),
        "rows": frame.to_dict(orient="records"),
        "warnings": [],
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Update local CSV price history from a free daily source.")
    parser.add_argument("--project-root", help="Project root for config.yaml and default data directory.")
    parser.add_argument("--data-dir", help="Optional data directory. Relative paths resolve from project root.")
    parser.add_argument("--output-dir", help="Optional output directory. Relative paths resolve from project root.")
    parser.add_argument("--tickers", help="Comma-separated ticker list for targeted updates.")
    parser.add_argument("--max-tickers", type=int, help="Limit the number of tickers updated.")
    parser.add_argument("--chunk-size", type=int, default=50, help="Tickers per chunk during updates.")
    parser.add_argument("--refresh", action="store_true", help="Refresh even if local ticker data already looks fresh.")
    parser.add_argument("--freshness-days", type=int, default=1, help="Skip tickers updated within this many days unless --refresh is used.")
    parser.add_argument("--universe-file", help="Alternate universe file to derive tickers from.")
    parser.add_argument("--validate-price-imports", action="store_true", help="Validate data/imports/prices.csv without mutating data/prices.csv.")
    parser.add_argument("--preview-price-import-merge", action="store_true", help="Preview staged price import changes without mutating data/prices.csv.")
    parser.add_argument("--apply-price-import-merge", action="store_true", help="Apply staged price imports into data/prices.csv with a backup.")
    parser.add_argument("--price-status", action="store_true", help="Display outputs/price_update_status.csv if present.")
    parser.add_argument("--json", action="store_true", help="Print JSON for import/status commands.")
    args = parser.parse_args()

    explicit_tickers = [ticker.strip() for ticker in args.tickers.split(",") if ticker.strip()] if args.tickers else None
    project_root = resolve_project_root(args.project_root)
    data_dir = resolve_data_dir(args.data_dir, project_root)
    output_dir = resolve_outputs_dir(args.output_dir, project_root)

    if args.validate_price_imports:
        summary = validate_price_imports(project_root, data_dir=data_dir)
        if args.json:
            print(json.dumps({key: value for key, value in summary.items() if key != "valid_frame"}, indent=2))
        else:
            print(format_path_context(project_root, data_dir, output_dir))
            _print_price_import_summary(summary)
        return

    if args.preview_price_import_merge:
        summary = preview_price_import_merge(project_root, data_dir=data_dir)
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(format_path_context(project_root, data_dir, output_dir))
            _print_price_import_summary(summary)
        return

    if args.apply_price_import_merge:
        summary = apply_price_import_merge(project_root, data_dir=data_dir)
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(format_path_context(project_root, data_dir, output_dir))
            _print_price_import_summary(summary)
        return

    if args.price_status:
        summary = show_price_update_status(project_root, output_dir=output_dir)
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(format_path_context(project_root, data_dir, output_dir))
            print(f"status: {summary['status']}")
            print(f"path: {summary['path']}")
            rows = summary.get("rows", [])
            if rows:
                frame = pd.DataFrame(rows)
                print(frame[["ticker", "status", "rows_fetched", "rows_merged", "recommended_action"]].to_string(index=False))
            for warning in summary.get("warnings", []):
                print(f"warning: {warning}")
        return

    def print_progress(event: dict[str, object]) -> None:
        if event.get("event") == "chunk_complete":
            print(
                "Chunk "
                f"{event['chunk_index']}/{event['chunks_total']} complete: "
                f"updated={event['updated_so_far']} missing={event['missing_so_far']}"
            )

    result = update_local_price_data(
        base_dir=project_root,
        data_dir=data_dir,
        output_dir=output_dir,
        tickers=explicit_tickers,
        max_tickers=args.max_tickers,
        chunk_size=args.chunk_size,
        refresh=args.refresh,
        freshness_days=args.freshness_days,
        universe_file=Path(args.universe_file) if args.universe_file else None,
        progress_callback=print_progress,
    )
    print(format_path_context(project_root, data_dir, None))
    print(f"Updated local price file: {result.path}")
    print(f"Tickers requested: {len(result.tickers_requested)}")
    print(f"Tickers updated: {len(result.tickers_updated)}")
    print(f"Chunks processed: {result.chunks_processed}")
    print(f"Rows written: {result.rows_written}")
    if result.status_path is not None:
        print(f"Price update status: {result.status_path}")
    if result.tickers_skipped_fresh:
        print("Tickers skipped as fresh:")
        for ticker in result.tickers_skipped_fresh:
            print(f"- {ticker}")
    if result.tickers_missing:
        print("Tickers without remote rows:")
        for ticker in result.tickers_missing:
            print(f"- {ticker}")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
