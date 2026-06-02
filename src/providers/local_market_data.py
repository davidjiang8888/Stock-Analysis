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

    def __init__(self, base_dir: Path | None = None, data_dir: Path | None = None, outputs_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent.parent
        self.data_dir = data_dir or (self.base_dir / "data")
        self.outputs_dir = outputs_dir or (self.base_dir / "outputs")
        self.catalog = LocalDataCatalog(self.base_dir, data_dir=self.data_dir, outputs_dir=self.outputs_dir)
        self.prices_path = self.data_dir / "prices.csv"
        self.fundamentals_path = self.data_dir / "fundamentals.csv"

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

    def _row_source(
        self,
        dataset_name: str,
        row: pd.Series,
        default_notes: list[str],
    ):
        metadata = self.catalog.dataset_metadata(dataset_name)
        notes = list(default_notes)
        if "source" in row and pd.notna(row["source"]):
            notes.append(f"Dataset row source: {row['source']}")
        freshness = metadata.source["freshness"]
        if "as_of_date" in row and pd.notna(row["as_of_date"]):
            freshness = f"dataset row as of {pd.Timestamp(row['as_of_date']).date().isoformat()}"
        return make_source_metadata(
            provider=metadata.source["provider"],
            freshness=freshness,
            official=False,
            notes=notes,
            retrieved_at=metadata.source["retrieved_at"],
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
                value = row[column]
                if isinstance(value, pd.Timestamp):
                    return value.date().isoformat() if value.time().isoformat() == "00:00:00" else value.isoformat()
                return str(value)
        return None

    def list_local_tickers(self) -> list[str]:
        return self.catalog.list_tickers(
            ["prices", "fundamentals", "earnings", "analyst_estimates", "peers", "universe", "holdings"]
        )

    def get_local_data_validation(self) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in self.catalog.discover()]

    def get_ticker_dataset_coverage(self, ticker: str) -> list[dict[str, Any]]:
        coverage = self.catalog.describe_ticker(
            ticker,
            [
                "prices",
                "fundamentals",
                "earnings",
                "analyst_estimates",
                "peers",
                "purpose_classification",
                "momentum_leaders",
                "portfolio_review",
                "undervalued_candidates",
                "final_watchlist",
            ],
        )
        return [row.to_dict() for row in coverage]

    def _peer_rows_for_ticker(self, ticker: str) -> tuple[pd.DataFrame, list[str]]:
        peers = self._load_optional_dataset("peers")
        if peers.empty or "ticker" not in peers.columns or "peer_ticker" not in peers.columns:
            return pd.DataFrame(), []
        ticker = ticker.upper()
        selected = peers.loc[peers["ticker"] == ticker].copy()
        if selected.empty:
            return selected, []

        warnings: list[str] = []
        selected["peer_ticker"] = selected["peer_ticker"].astype(str).str.upper().str.strip()
        self_rows = selected.loc[selected["peer_ticker"] == ticker]
        if not self_rows.empty:
            warnings.append(f"Ignored {len(self_rows)} self-peer row(s) for {ticker}.")
            selected = selected.loc[selected["peer_ticker"] != ticker].copy()

        duplicate_mask = selected.duplicated(subset=["ticker", "peer_ticker"], keep="last")
        duplicate_count = int(duplicate_mask.sum())
        if duplicate_count:
            warnings.append(f"Ignored {duplicate_count} duplicate peer mapping row(s) for {ticker}.")
            selected = selected.loc[~duplicate_mask].copy()

        return selected.sort_values(["ticker", "peer_ticker"]).reset_index(drop=True), warnings

    def get_peer_tickers(self, ticker: str) -> list[str]:
        peer_rows, _warnings = self._peer_rows_for_ticker(ticker)
        if peer_rows.empty or "peer_ticker" not in peer_rows.columns:
            return []
        return sorted(peer_rows["peer_ticker"].dropna().astype(str).str.upper().str.strip().unique().tolist())

    def get_peer_summary(self, ticker: str) -> dict[str, Any]:
        ticker = ticker.upper()
        peer_rows, warnings = self._peer_rows_for_ticker(ticker)
        metadata = self.catalog.dataset_metadata("peers")
        peer_tickers = peer_rows["peer_ticker"].dropna().astype(str).str.upper().str.strip().tolist() if not peer_rows.empty else []
        peer_groups = sorted({str(value) for value in peer_rows.get("peer_group", pd.Series(dtype=object)).dropna().astype(str)} )
        peers_with_fundamentals: list[str] = []
        peers_with_quote_or_market_cap: list[str] = []
        for peer_ticker in peer_tickers:
            financials = self.get_financials(peer_ticker)
            has_fundamentals = any(
                value is not None
                for value in (
                    financials.revenue,
                    financials.eps,
                    financials.free_cash_flow,
                    financials.ebitda,
                    financials.trailing_pe,
                    financials.market_cap,
                )
            )
            if has_fundamentals:
                peers_with_fundamentals.append(peer_ticker)
            try:
                quote = self.get_quote(peer_ticker)
            except LookupError:
                quote = None
            if quote is not None or financials.market_cap is not None:
                peers_with_quote_or_market_cap.append(peer_ticker)

        return {
            "peer_dataset_present": metadata.validation_status != "missing_file",
            "peer_dataset_status": metadata.validation_status,
            "peer_group": peer_groups[0] if len(peer_groups) == 1 else None,
            "peer_groups": peer_groups,
            "peer_tickers": peer_tickers,
            "peer_count": len(peer_tickers),
            "peers_with_fundamentals": peers_with_fundamentals,
            "peers_with_quote_or_market_cap": peers_with_quote_or_market_cap,
            "peer_fundamentals_available": len(peers_with_fundamentals),
            "peer_market_context_available": len(peers_with_quote_or_market_cap),
            "warnings": warnings,
            "source_metadata": metadata.source,
        }

    def get_peer_valuation_inputs(self, ticker: str) -> list[dict[str, Any]]:
        peer_inputs: list[dict[str, Any]] = []
        peer_rows, warnings = self._peer_rows_for_ticker(ticker)
        if peer_rows.empty or "peer_ticker" not in peer_rows.columns:
            return peer_inputs
        for peer_ticker in peer_rows["peer_ticker"].dropna().astype(str).str.upper().str.strip().tolist():
            peer_row = peer_rows.loc[peer_rows["peer_ticker"] == peer_ticker].iloc[-1]
            financials = self.get_financials(peer_ticker)
            try:
                quote = self.get_quote(peer_ticker)
            except LookupError:
                quote = None
            peer_inputs.append(
                {
                    "ticker": peer_ticker,
                    "current_price": quote.price if quote is not None else None,
                    "revenue": financials.revenue,
                    "eps": financials.eps,
                    "free_cash_flow": financials.free_cash_flow,
                    "ebitda": financials.ebitda,
                    "shares_outstanding": financials.shares_outstanding,
                    "cash": financials.cash,
                    "debt": financials.debt,
                    "market_cap": financials.market_cap,
                    "trailing_pe": financials.trailing_pe,
                    "forward_pe": financials.forward_pe,
                    "price_to_book": financials.price_to_book,
                    "peer_group": self._string_value(peer_row, "peer_group"),
                    "sector": self._string_value(peer_row, "sector"),
                    "industry": self._string_value(peer_row, "industry"),
                    "mapping_source": self._string_value(peer_row, "source"),
                    "mapping_as_of_date": self._string_value(peer_row, "as_of_date"),
                    "source_metadata": [
                        financials.source.to_dict() if financials.source is not None else None,
                        quote.source.to_dict() if quote is not None else None,
                    ],
                }
            )
        if warnings and peer_inputs:
            peer_inputs[0]["peer_mapping_warnings"] = warnings
        return peer_inputs

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
        source = self._row_source("fundamentals", row, ["Local fundamentals data."]) if not row.empty else (
            self._unavailable_source(
                "local:fundamentals.csv",
                ["No local fundamentals row was found for this ticker."],
            )
            if metadata.validation_status != "missing_file"
            else self._unavailable_source(
                "local:fundamentals.csv",
                ["Fundamentals file is unavailable in the local CSV-first pipeline."],
            )
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
            source=source,
        )

    def get_earnings(self, ticker: str) -> EarningsSummary:
        ticker = ticker.upper()
        earnings = self._load_optional_dataset("earnings")
        row = self._select_ticker_row(earnings, ticker)
        metadata = self.catalog.dataset_metadata("earnings")
        if metadata.validation_status == "missing_file":
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
            last_earnings_date=self._string_value(row, "last_earnings_date", "report_date"),
            fiscal_period=self._string_value(row, "fiscal_period"),
            eps_estimate=self._float_value(row, "eps_estimate"),
            eps_actual=self._float_value(row, "eps_actual"),
            revenue_estimate=self._float_value(row, "revenue_estimate"),
            revenue_actual=self._float_value(row, "revenue_actual"),
            surprise_pct=self._float_value(row, "surprise_pct"),
            notes=[] if not row.empty else [f"No local earnings row was found for {ticker}."],
            source=self._row_source("earnings", row, ["Local earnings data."]) if not row.empty else make_source_metadata(**metadata.source),
        )

    def get_analyst_estimates(self, ticker: str) -> AnalystEstimateSummary:
        ticker = ticker.upper()
        estimates = self._load_optional_dataset("analyst_estimates")
        row = self._select_ticker_row(estimates, ticker)
        metadata = self.catalog.dataset_metadata("analyst_estimates")
        if metadata.validation_status == "missing_file":
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
            current_quarter_eps=self._float_value(row, "current_quarter_eps", "eps_estimate"),
            next_quarter_eps=self._float_value(row, "next_quarter_eps"),
            current_year_eps=self._float_value(row, "current_year_eps"),
            next_year_eps=self._float_value(row, "next_year_eps"),
            current_quarter_revenue=self._float_value(row, "current_quarter_revenue", "revenue_estimate"),
            next_quarter_revenue=self._float_value(row, "next_quarter_revenue"),
            current_year_revenue=self._float_value(row, "current_year_revenue"),
            next_year_revenue=self._float_value(row, "next_year_revenue"),
            recommendation=self._string_value(row, "recommendation", "rating_consensus"),
            target_mean_price=self._float_value(row, "target_mean_price", "price_target_mean"),
            target_high_price=self._float_value(row, "target_high_price", "price_target_high"),
            target_low_price=self._float_value(row, "target_low_price", "price_target_low"),
            revision_trend=self._string_value(row, "revision_trend"),
            notes=[] if not row.empty else [f"No local analyst-estimate row was found for {ticker}."],
            source=self._row_source("analyst_estimates", row, ["Local analyst estimate data."]) if not row.empty else make_source_metadata(**metadata.source),
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
