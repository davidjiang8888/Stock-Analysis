from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.providers.local_data_catalog import LocalDataCatalog
from src.providers.market_data import (
    AnalystEstimateSummary,
    EarningsSummary,
    FinancialSnapshot,
    MarketDataProvider,
    OptionsChainSummary,
    QuoteSnapshot,
    make_source_metadata,
)


class LocalCSVMarketDataProvider(MarketDataProvider):
    """Research provider backed by local project CSVs.

    This keeps the new stock-report workflow aligned with the existing
    deterministic CSV-first pipeline.
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent.parent
        self.catalog = LocalDataCatalog(self.base_dir)
        self.prices_path = self.base_dir / "data" / "prices.csv"
        self.fundamentals_path = self.base_dir / "data" / "fundamentals.csv"

    def _source(self, file_path: Path, freshness: str, notes: list[str]) -> object:
        retrieved_at = (
            pd.Timestamp(file_path.stat().st_mtime, unit="s", tz="UTC").isoformat()
            if file_path.exists()
            else pd.Timestamp.now(tz="UTC").isoformat()
        )
        return make_source_metadata(
            provider=f"local:{file_path.name}",
            freshness=freshness,
            official=False,
            notes=notes,
            retrieved_at=retrieved_at,
        )

    def _unavailable_source(self, provider_label: str, notes: list[str]) -> object:
        return make_source_metadata(
            provider=provider_label,
            freshness="not available in local CSVs",
            official=False,
            notes=notes,
        )

    def _load_prices(self) -> pd.DataFrame:
        prices = self.catalog.load_dataframe("prices")
        if prices is None:
            raise FileNotFoundError(f"Local prices file is missing: {self.prices_path}")
        required_columns = {"date", "ticker"}
        missing_columns = sorted(required_columns - set(prices.columns))
        if missing_columns:
            raise ValueError(f"Local prices file is missing required columns: {', '.join(missing_columns)}")
        if "adj_close" in prices.columns and "close" not in prices.columns:
            prices["close"] = prices["adj_close"]
        if "close" not in prices.columns:
            raise ValueError("Local prices file must include either `close` or `adj_close`.")
        for optional_column in ("open", "high", "low"):
            if optional_column not in prices.columns:
                prices[optional_column] = pd.NA
        for column in ("open", "high", "low", "close", "adj_close", "volume"):
            if column in prices.columns:
                prices[column] = pd.to_numeric(prices[column], errors="coerce")
        return prices.loc[prices["date"].notna()].copy()

    def _load_fundamentals(self) -> pd.DataFrame:
        frame = self.catalog.load_dataframe("fundamentals")
        return frame.copy() if frame is not None else pd.DataFrame()

    def _load_optional_dataset(self, dataset_name: str) -> pd.DataFrame:
        frame = self.catalog.load_dataframe(dataset_name)
        return frame.copy() if frame is not None else pd.DataFrame()

    def _select_ticker_row(self, frame: pd.DataFrame, ticker: str) -> pd.Series:
        if frame.empty or "ticker" not in frame.columns:
            return pd.Series(dtype=object)
        matches = frame.loc[frame["ticker"] == ticker]
        return matches.iloc[-1] if not matches.empty else pd.Series(dtype=object)

    def _float_value(self, row: pd.Series, *columns: str) -> float | None:
        for column in columns:
            if column in row and pd.notna(row[column]):
                return float(row[column])
        return None

    def _string_value(self, row: pd.Series, *columns: str) -> str | None:
        for column in columns:
            if column in row and pd.notna(row[column]):
                return str(row[column])
        return None

    def list_local_tickers(self) -> list[str]:
        return self.catalog.list_tickers(
            ["prices", "fundamentals", "earnings", "analyst_estimates", "universe", "holdings"]
        )

    def get_ticker_dataset_coverage(self, ticker: str) -> list[dict[str, Any]]:
        coverage = self.catalog.describe_ticker(
            ticker,
            [
                "prices",
                "fundamentals",
                "earnings",
                "analyst_estimates",
                "purpose_classification",
                "momentum_leaders",
                "portfolio_review",
                "undervalued_candidates",
                "final_watchlist",
            ],
        )
        return [row.to_dict() for row in coverage]

    def get_screener_context(self, ticker: str) -> dict[str, dict[str, Any]]:
        ticker = ticker.upper()
        context: dict[str, dict[str, Any]] = {}
        for dataset_name in (
            "purpose_classification",
            "momentum_leaders",
            "portfolio_review",
            "undervalued_candidates",
            "final_watchlist",
        ):
            frame = self.catalog.load_dataframe(dataset_name)
            if frame is None or "ticker" not in frame.columns:
                continue
            matches = frame.loc[frame["ticker"] == ticker]
            if matches.empty:
                continue
            row = matches.iloc[-1]
            context[dataset_name] = {
                column: (None if pd.isna(value) else value.item() if hasattr(value, "item") else value)
                for column, value in row.to_dict().items()
            }
        return context

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
        row = self._select_ticker_row(fundamentals, ticker)
        metadata = self.catalog.dataset_metadata("fundamentals")
        source = (
            metadata.source
            if metadata is not None
            else self._unavailable_source(
                "local:fundamentals.csv",
                ["Fundamentals file is unavailable in the local CSV-first pipeline."],
            ).to_dict()
        )
        return FinancialSnapshot(
            ticker=ticker,
            revenue=self._float_value(row, "revenue"),
            revenue_growth=self._float_value(row, "revenue_growth"),
            eps=self._float_value(row, "eps"),
            gross_margin=self._float_value(row, "gross_margin"),
            operating_margin=self._float_value(row, "operating_margin"),
            profit_margin=self._float_value(row, "profit_margin"),
            free_cash_flow=self._float_value(row, "free_cash_flow", "fcf"),
            fcf_margin=self._float_value(row, "fcf_margin"),
            ebitda=self._float_value(row, "ebitda"),
            market_cap=self._float_value(row, "market_cap"),
            enterprise_value=self._float_value(row, "enterprise_value"),
            trailing_pe=self._float_value(row, "pe_ratio", "trailing_pe"),
            forward_pe=self._float_value(row, "forward_pe"),
            price_to_book=self._float_value(row, "price_to_book"),
            shares_outstanding=self._float_value(row, "shares_outstanding"),
            cash=self._float_value(row, "cash"),
            debt=self._float_value(row, "debt", "total_debt"),
            net_debt=self._float_value(row, "net_debt"),
            debt_to_equity=self._float_value(row, "debt_to_equity"),
            currency=None,
            as_of_date=self._string_value(row, "as_of_date", "date"),
            source=make_source_metadata(**source),
        )

    def get_earnings(self, ticker: str) -> EarningsSummary:
        ticker = ticker.upper()
        earnings = self._load_optional_dataset("earnings")
        row = self._select_ticker_row(earnings, ticker)
        metadata = self.catalog.dataset_metadata("earnings")
        if metadata is None:
            return EarningsSummary(
                ticker=ticker,
                notes=["No local earnings dataset is configured in the CSV-first pipeline."],
                source=self._unavailable_source(
                    "local:earnings.csv",
                    ["Earnings fields are unavailable from the bundled local sample files."],
                ),
            )
        return EarningsSummary(
            ticker=ticker,
            next_earnings_date=self._string_value(row, "next_earnings_date", "earnings_date"),
            last_earnings_date=self._string_value(row, "last_earnings_date"),
            eps_estimate=self._float_value(row, "eps_estimate"),
            eps_actual=self._float_value(row, "eps_actual"),
            revenue_estimate=self._float_value(row, "revenue_estimate"),
            revenue_actual=self._float_value(row, "revenue_actual"),
            surprise_pct=self._float_value(row, "surprise_pct"),
            notes=[] if not row.empty else [f"No local earnings row was found for {ticker}."],
            source=make_source_metadata(**metadata.source),
        )

    def get_analyst_estimates(self, ticker: str) -> AnalystEstimateSummary:
        ticker = ticker.upper()
        estimates = self._load_optional_dataset("analyst_estimates")
        row = self._select_ticker_row(estimates, ticker)
        metadata = self.catalog.dataset_metadata("analyst_estimates")
        if metadata is None:
            return AnalystEstimateSummary(
                ticker=ticker,
                notes=["No local analyst-estimate dataset is configured in the CSV-first pipeline."],
                source=self._unavailable_source(
                    "local:analyst_estimates.csv",
                    ["Analyst estimate fields are unavailable from the bundled local sample files."],
                ),
            )
        return AnalystEstimateSummary(
            ticker=ticker,
            current_quarter_eps=self._float_value(row, "current_quarter_eps"),
            next_quarter_eps=self._float_value(row, "next_quarter_eps"),
            current_year_eps=self._float_value(row, "current_year_eps"),
            next_year_eps=self._float_value(row, "next_year_eps"),
            current_quarter_revenue=self._float_value(row, "current_quarter_revenue"),
            next_quarter_revenue=self._float_value(row, "next_quarter_revenue"),
            current_year_revenue=self._float_value(row, "current_year_revenue"),
            next_year_revenue=self._float_value(row, "next_year_revenue"),
            recommendation=self._string_value(row, "recommendation"),
            target_mean_price=self._float_value(row, "target_mean_price"),
            notes=[] if not row.empty else [f"No local analyst-estimate row was found for {ticker}."],
            source=make_source_metadata(**metadata.source),
        )

    def get_options_chain(self, ticker: str, expiry: str) -> OptionsChainSummary:
        return OptionsChainSummary(
            ticker=ticker.upper(),
            expiry=expiry,
            calls_count=0,
            puts_count=0,
            notes=["Options-chain data is not configured in the local CSV-first pipeline."],
            source=self._unavailable_source(
                "local:options_chain.csv",
                ["Options chain remains optional and unimplemented for local CSV data."],
            ),
        )
