from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.providers.base import DataFetcher, FetchResult


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


class CSVDataFetcher(DataFetcher):
    def __init__(self, path: Path) -> None:
        self.path = path

    def load_ohlcv(self, tickers: list[str]) -> FetchResult:
        if not self.path.exists():
            return FetchResult(prices=pd.DataFrame(), warnings=[f"Price file not found: {self.path}"])

        prices = pd.read_csv(self.path)
        prices.columns = _normalize_columns(list(prices.columns))

        warnings: list[str] = []
        if "date" in prices.columns:
            prices["date"] = pd.to_datetime(prices["date"], errors="coerce", format="mixed")
            invalid_dates = int(prices["date"].isna().sum())
            if invalid_dates:
                warnings.append(f"Dropped {invalid_dates} price rows with invalid dates from {self.path.name}")
                prices = prices.loc[prices["date"].notna()].copy()
        if "adj_close" in prices.columns and "close" not in prices.columns:
            prices["close"] = prices["adj_close"]

        for optional_column in ("open", "high", "low", "adj_close"):
            if optional_column not in prices.columns:
                prices[optional_column] = np.nan

        required = {"date", "ticker", "close", "volume"}
        missing = required - set(prices.columns)
        if missing:
            return FetchResult(
                prices=pd.DataFrame(),
                warnings=[f"Price file is missing required columns: {sorted(missing)}"],
            )

        prices["ticker"] = prices["ticker"].astype("string").str.upper().str.strip()
        prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
        prices["volume"] = pd.to_numeric(prices["volume"], errors="coerce")
        for numeric_column in ("open", "high", "low", "adj_close"):
            prices[numeric_column] = pd.to_numeric(prices[numeric_column], errors="coerce")

        invalid_required_mask = (
            prices["ticker"].isna()
            | prices["ticker"].eq("")
            | prices["close"].isna()
            | prices["close"].le(0)
            | prices["volume"].isna()
            | prices["volume"].lt(0)
        )
        invalid_required_rows = int(invalid_required_mask.sum())
        if invalid_required_rows:
            warnings.append(
                f"Dropped {invalid_required_rows} price rows with missing or invalid ticker/close/volume from {self.path.name}"
            )
            prices = prices.loc[~invalid_required_mask].copy()

        duplicate_rows = int(prices.duplicated(subset=["date", "ticker"], keep="last").sum())
        if duplicate_rows:
            warnings.append(
                f"Dropped {duplicate_rows} duplicate price rows by date/ticker from {self.path.name}"
            )
            prices = prices.drop_duplicates(subset=["date", "ticker"], keep="last").copy()

        requested = sorted({ticker.upper().strip() for ticker in tickers if ticker})
        filtered = prices.loc[prices["ticker"].isin(requested)].copy()

        available = set(filtered["ticker"].unique())
        for ticker in requested:
            if ticker not in available:
                warnings.append(f"Missing OHLCV data for {ticker}")

        return FetchResult(prices=filtered, warnings=warnings)
