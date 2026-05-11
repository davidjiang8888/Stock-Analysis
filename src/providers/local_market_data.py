from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.providers.market_data import (
    AnalystEstimateSummary,
    EarningsSummary,
    FinancialSnapshot,
    MarketDataProvider,
    OptionsChainSummary,
    QuoteSnapshot,
    make_source_metadata,
)


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


class LocalCSVMarketDataProvider(MarketDataProvider):
    """Research provider backed by local project CSVs.

    This keeps the new stock-report workflow aligned with the existing
    deterministic CSV-first pipeline.
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent.parent
        self.prices_path = self.base_dir / "data" / "prices.csv"
        self.fundamentals_path = self.base_dir / "data" / "fundamentals.csv"

    def _source(self, file_path: Path, freshness: str, notes: list[str]) -> object:
        retrieved_at = (
            pd.Timestamp(file_path.stat().st_mtime, unit="s", tz="UTC").isoformat()
            if file_path.exists()
            else pd.Timestamp.utcnow().isoformat()
        )
        return make_source_metadata(
            provider=f"local:{file_path.name}",
            freshness=freshness,
            official=False,
            notes=notes,
            retrieved_at=retrieved_at,
        )

    def _load_prices(self) -> pd.DataFrame:
        if not self.prices_path.exists():
            raise FileNotFoundError(f"Local prices file is missing: {self.prices_path}")
        prices = pd.read_csv(self.prices_path)
        prices.columns = _normalize_columns(list(prices.columns))
        if "adj_close" in prices.columns and "close" not in prices.columns:
            prices["close"] = prices["adj_close"]
        for optional_column in ("open", "high", "low"):
            if optional_column not in prices.columns:
                prices[optional_column] = pd.NA
        prices["date"] = pd.to_datetime(prices["date"], errors="coerce", format="mixed")
        prices["ticker"] = prices["ticker"].astype("string").str.upper().str.strip()
        for column in ("open", "high", "low", "close", "adj_close", "volume"):
            if column in prices.columns:
                prices[column] = pd.to_numeric(prices[column], errors="coerce")
        return prices.loc[prices["date"].notna()].copy()

    def _load_fundamentals(self) -> pd.DataFrame:
        if not self.fundamentals_path.exists():
            return pd.DataFrame()
        frame = pd.read_csv(self.fundamentals_path)
        frame.columns = _normalize_columns(list(frame.columns))
        if "ticker" in frame.columns:
            frame["ticker"] = frame["ticker"].astype("string").str.upper().str.strip()
        return frame

    def get_quote(self, ticker: str) -> QuoteSnapshot:
        ticker = ticker.upper()
        prices = self._load_prices()
        frame = prices.loc[prices["ticker"] == ticker].sort_values("date")
        if frame.empty:
            raise LookupError(f"No local price rows were found for {ticker}.")

        latest = frame.iloc[-1]
        previous = frame.iloc[-2] if len(frame) > 1 else None
        source = self._source(
            self.prices_path,
            freshness=f"daily CSV through {latest['date'].date().isoformat()}",
            notes=["Local CSV-backed research data."],
        )
        return QuoteSnapshot(
            ticker=ticker,
            price=float(latest["close"]) if pd.notna(latest["close"]) else None,
            previous_close=float(previous["close"]) if previous is not None and pd.notna(previous["close"]) else None,
            open=float(latest["open"]) if pd.notna(latest["open"]) else None,
            day_high=float(latest["high"]) if pd.notna(latest["high"]) else None,
            day_low=float(latest["low"]) if pd.notna(latest["low"]) else None,
            volume=float(latest["volume"]) if pd.notna(latest["volume"]) else None,
            currency=None,
            market_time=latest["date"].isoformat() if pd.notna(latest["date"]) else None,
            source=source,
        )

    def get_price_history(self, ticker: str, period: str, interval: str) -> pd.DataFrame:
        if interval != "1d":
            raise ValueError("Local CSV market-data provider only supports 1d interval.")

        ticker = ticker.upper()
        prices = self._load_prices()
        frame = prices.loc[prices["ticker"] == ticker].sort_values("date").copy()
        if frame.empty:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        period_map = {
            "1mo": 31,
            "3mo": 93,
            "1y": 366,
        }
        if period in period_map:
            cutoff = frame["date"].max() - pd.Timedelta(days=period_map[period])
            frame = frame.loc[frame["date"] >= cutoff].copy()

        return frame[[column for column in ["date", "open", "high", "low", "close", "volume"] if column in frame.columns]].copy()

    def get_financials(self, ticker: str) -> FinancialSnapshot:
        ticker = ticker.upper()
        fundamentals = self._load_fundamentals()
        frame = fundamentals.loc[fundamentals.get("ticker", pd.Series(dtype=object)) == ticker] if not fundamentals.empty else pd.DataFrame()
        row = frame.iloc[0] if not frame.empty else pd.Series(dtype=object)
        source = self._source(
            self.fundamentals_path,
            freshness="local fundamentals CSV",
            notes=["Local sample fundamentals; fields may be sparse."],
        )
        return FinancialSnapshot(
            ticker=ticker,
            revenue=float(row["revenue"]) if "revenue" in row and pd.notna(row["revenue"]) else None,
            eps=float(row["eps"]) if "eps" in row and pd.notna(row["eps"]) else None,
            gross_margin=float(row["gross_margin"]) if "gross_margin" in row and pd.notna(row["gross_margin"]) else None,
            operating_margin=float(row["operating_margin"]) if "operating_margin" in row and pd.notna(row["operating_margin"]) else None,
            profit_margin=float(row["profit_margin"]) if "profit_margin" in row and pd.notna(row["profit_margin"]) else None,
            free_cash_flow=float(row["free_cash_flow"]) if "free_cash_flow" in row and pd.notna(row["free_cash_flow"]) else None,
            market_cap=float(row["market_cap"]) if "market_cap" in row and pd.notna(row["market_cap"]) else None,
            enterprise_value=float(row["enterprise_value"]) if "enterprise_value" in row and pd.notna(row["enterprise_value"]) else None,
            trailing_pe=float(row["pe_ratio"]) if "pe_ratio" in row and pd.notna(row["pe_ratio"]) else None,
            forward_pe=float(row["forward_pe"]) if "forward_pe" in row and pd.notna(row["forward_pe"]) else None,
            price_to_book=float(row["price_to_book"]) if "price_to_book" in row and pd.notna(row["price_to_book"]) else None,
            shares_outstanding=float(row["shares_outstanding"]) if "shares_outstanding" in row and pd.notna(row["shares_outstanding"]) else None,
            net_debt=float(row["net_debt"]) if "net_debt" in row and pd.notna(row["net_debt"]) else None,
            currency=None,
            as_of_date=None,
            source=source,
        )

    def get_earnings(self, ticker: str) -> EarningsSummary:
        return EarningsSummary(
            ticker=ticker.upper(),
            notes=["No local earnings dataset is configured in the CSV-first pipeline."],
            source=self._source(
                self.fundamentals_path,
                freshness="not available in local CSVs",
                notes=["Earnings fields are unavailable from the bundled local sample files."],
            ),
        )

    def get_analyst_estimates(self, ticker: str) -> AnalystEstimateSummary:
        return AnalystEstimateSummary(
            ticker=ticker.upper(),
            notes=["No local analyst-estimate dataset is configured in the CSV-first pipeline."],
            source=self._source(
                self.fundamentals_path,
                freshness="not available in local CSVs",
                notes=["Analyst estimate fields are unavailable from the bundled local sample files."],
            ),
        )

    def get_options_chain(self, ticker: str, expiry: str) -> OptionsChainSummary:
        return OptionsChainSummary(
            ticker=ticker.upper(),
            expiry=expiry,
            calls_count=0,
            puts_count=0,
            notes=["Options-chain data is not configured in the local CSV-first pipeline."],
            source=self._source(
                self.prices_path,
                freshness="not available in local CSVs",
                notes=["Options chain remains optional and unimplemented for local CSV data."],
            ),
        )
