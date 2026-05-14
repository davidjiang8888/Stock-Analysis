from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from time import sleep
from typing import Callable, Protocol
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from src.config import AppConfig
from src.paths import format_path_context, resolve_data_dir, resolve_project_root


PRICE_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]


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


def update_local_price_data(
    base_dir: Path | None = None,
    source: PriceHistorySource | None = None,
    tickers: list[str] | None = None,
    *,
    data_dir: Path | None = None,
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
    config = AppConfig.load(base_dir / "config.yaml")
    prices_path = data_dir / "prices.csv"
    source = source or StooqDailyPriceSource()
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
    tickers_to_fetch = tickers
    if not refresh:
        fresh_ticker_set = _fresh_tickers(existing, freshness_days)
        skipped_fresh = [ticker for ticker in tickers if ticker in fresh_ticker_set]
        tickers_to_fetch = [ticker for ticker in tickers if ticker not in fresh_ticker_set]
        if skipped_fresh:
            warnings.append(
                f"Skipped {len(skipped_fresh)} ticker(s) that already have price data within the last {freshness_days} day(s)."
            )

    if not tickers_to_fetch:
        return PriceUpdateResult(
            path=prices_path,
            tickers_requested=tickers,
            tickers_updated=[],
            tickers_missing=missing,
            tickers_skipped_fresh=skipped_fresh,
            rows_written=len(existing),
            chunks_processed=0,
            warnings=warnings + ["No remote price rows were added; kept the existing local CSV fallback."],
        )

    chunks = _chunked(tickers_to_fetch, chunk_size)
    processed_chunks = 0
    for chunk_index, chunk in enumerate(chunks, start=1):
        fetched_frames: list[pd.DataFrame] = []
        for ticker in chunk:
            last_warning_count = len(warnings)
            frame = pd.DataFrame(columns=PRICE_COLUMNS)
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
                continue
            fetched_frames.append(frame)
            updated.append(ticker)

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
        return PriceUpdateResult(
            path=prices_path,
            tickers_requested=tickers,
            tickers_updated=[],
            tickers_missing=missing,
            tickers_skipped_fresh=skipped_fresh,
            rows_written=len(existing),
            chunks_processed=processed_chunks,
            warnings=warnings + ["No remote price rows were added; kept the existing local CSV fallback."],
        )

    return PriceUpdateResult(
        path=prices_path,
        tickers_requested=tickers,
        tickers_updated=updated,
        tickers_missing=missing,
        tickers_skipped_fresh=skipped_fresh,
        rows_written=len(combined),
        chunks_processed=processed_chunks,
        warnings=warnings,
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Update local CSV price history from a free daily source.")
    parser.add_argument("--project-root", help="Project root for config.yaml and default data directory.")
    parser.add_argument("--data-dir", help="Optional data directory. Relative paths resolve from project root.")
    parser.add_argument("--tickers", help="Comma-separated ticker list for targeted updates.")
    parser.add_argument("--max-tickers", type=int, help="Limit the number of tickers updated.")
    parser.add_argument("--chunk-size", type=int, default=50, help="Tickers per chunk during updates.")
    parser.add_argument("--refresh", action="store_true", help="Refresh even if local ticker data already looks fresh.")
    parser.add_argument("--freshness-days", type=int, default=1, help="Skip tickers updated within this many days unless --refresh is used.")
    parser.add_argument("--universe-file", help="Alternate universe file to derive tickers from.")
    args = parser.parse_args()

    explicit_tickers = [ticker.strip() for ticker in args.tickers.split(",") if ticker.strip()] if args.tickers else None
    project_root = resolve_project_root(args.project_root)
    data_dir = resolve_data_dir(args.data_dir, project_root)

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
