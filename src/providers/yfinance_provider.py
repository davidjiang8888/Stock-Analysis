from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

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


class YFinanceProvider(MarketDataProvider):
    """Research-grade Yahoo/yfinance adapter.

    This provider is optional and should be used through the MarketDataProvider
    interface only. It is intentionally not part of the core screener pipeline.
    """

    def __init__(self) -> None:
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise RuntimeError(
                "yfinance is not installed. Add it to the environment before using YFinanceProvider."
            ) from exc
        self._yf = yf
        self._base_notes = [
            "Unofficial / research-grade market data via yfinance.",
            "Not affiliated with Yahoo.",
        ]

    def _ticker(self, ticker: str):
        return self._yf.Ticker(ticker.upper())

    def _source(self, freshness: str, extra_notes: list[str] | None = None):
        notes = [*self._base_notes, *(extra_notes or [])]
        return make_source_metadata(
            provider="yfinance",
            freshness=freshness,
            official=False,
            notes=notes,
            retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    @staticmethod
    def _clean_float(value: Any) -> float | None:
        try:
            if value is None or pd.isna(value):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clean_str(value: Any) -> str | None:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        text = str(value).strip()
        return text or None

    def get_quote(self, ticker: str) -> QuoteSnapshot:
        asset = self._ticker(ticker)
        info = getattr(asset, "info", {}) or {}
        fast_info = getattr(asset, "fast_info", {}) or {}

        return QuoteSnapshot(
            ticker=ticker.upper(),
            price=self._clean_float(fast_info.get("lastPrice") or info.get("currentPrice")),
            previous_close=self._clean_float(fast_info.get("previousClose") or info.get("previousClose")),
            open=self._clean_float(fast_info.get("open") or info.get("open")),
            day_high=self._clean_float(fast_info.get("dayHigh") or info.get("dayHigh")),
            day_low=self._clean_float(fast_info.get("dayLow") or info.get("dayLow")),
            volume=self._clean_float(fast_info.get("lastVolume") or info.get("volume")),
            currency=self._clean_str(info.get("currency")),
            market_time=self._clean_str(info.get("regularMarketTime")),
            source=self._source("intraday/last quote"),
        )

    def get_price_history(self, ticker: str, period: str, interval: str) -> pd.DataFrame:
        asset = self._ticker(ticker)
        history = asset.history(period=period, interval=interval, auto_adjust=False)
        if history.empty:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        history = history.reset_index().rename(
            columns={
                "Date": "date",
                "Datetime": "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Adj Close": "adj_close",
                "Volume": "volume",
            }
        )
        if "date" in history.columns:
            history["date"] = pd.to_datetime(history["date"], errors="coerce")
        return history[[column for column in ["date", "open", "high", "low", "close", "volume"] if column in history.columns]].copy()

    def get_financials(self, ticker: str) -> FinancialSnapshot:
        asset = self._ticker(ticker)
        info = getattr(asset, "info", {}) or {}
        return FinancialSnapshot(
            ticker=ticker.upper(),
            revenue=self._clean_float(info.get("totalRevenue")),
            revenue_growth=self._clean_float(info.get("revenueGrowth")),
            eps=self._clean_float(info.get("trailingEps")),
            gross_margin=self._clean_float(info.get("grossMargins")),
            operating_margin=self._clean_float(info.get("operatingMargins")),
            profit_margin=self._clean_float(info.get("profitMargins")),
            free_cash_flow=self._clean_float(info.get("freeCashflow")),
            fcf_margin=self._clean_float(info.get("freeCashflow"))
            / self._clean_float(info.get("totalRevenue"))
            if self._clean_float(info.get("freeCashflow")) is not None and self._clean_float(info.get("totalRevenue")) not in (None, 0)
            else None,
            ebitda=self._clean_float(info.get("ebitda")),
            market_cap=self._clean_float(info.get("marketCap")),
            enterprise_value=self._clean_float(info.get("enterpriseValue")),
            trailing_pe=self._clean_float(info.get("trailingPE")),
            forward_pe=self._clean_float(info.get("forwardPE")),
            price_to_book=self._clean_float(info.get("priceToBook")),
            shares_outstanding=self._clean_float(info.get("sharesOutstanding")),
            cash=self._clean_float(info.get("totalCash")),
            debt=self._clean_float(info.get("totalDebt")),
            net_debt=self._clean_float(info.get("totalDebt"))
            - self._clean_float(info.get("totalCash"))
            if self._clean_float(info.get("totalDebt")) is not None and self._clean_float(info.get("totalCash")) is not None
            else None,
            debt_to_equity=self._clean_float(info.get("debtToEquity")),
            currency=self._clean_str(info.get("financialCurrency") or info.get("currency")),
            as_of_date=self._clean_str(info.get("mostRecentQuarter")),
            source=self._source("latest available fundamentals"),
        )

    def get_earnings(self, ticker: str) -> EarningsSummary:
        asset = self._ticker(ticker)
        info = getattr(asset, "info", {}) or {}
        notes: list[str] = []

        eps_actual = None
        eps_estimate = None
        revenue_actual = None
        revenue_estimate = None
        surprise_pct = None
        last_earnings_date = None

        try:
            earnings_dates = asset.get_earnings_dates(limit=4)
        except Exception:  # pragma: no cover - upstream instability
            earnings_dates = pd.DataFrame()
            notes.append("Earnings history was unavailable from yfinance.")

        if isinstance(earnings_dates, pd.DataFrame) and not earnings_dates.empty:
            earnings_dates = earnings_dates.reset_index()
            latest = earnings_dates.iloc[0]
            last_earnings_date = self._clean_str(latest.get("Earnings Date") or latest.get("date"))
            eps_actual = self._clean_float(latest.get("Reported EPS"))
            eps_estimate = self._clean_float(latest.get("EPS Estimate"))
            surprise_pct = self._clean_float(latest.get("Surprise(%)"))

        next_date = None
        calendar = getattr(asset, "calendar", None)
        if isinstance(calendar, pd.DataFrame) and not calendar.empty:
            possible = calendar.iloc[0].to_dict()
            next_date = self._clean_str(possible.get("Earnings Date"))
        if next_date is None:
            next_date = self._clean_str(info.get("earningsTimestampStart"))

        return EarningsSummary(
            ticker=ticker.upper(),
            next_earnings_date=next_date,
            last_earnings_date=last_earnings_date,
            eps_estimate=eps_estimate,
            eps_actual=eps_actual,
            revenue_estimate=revenue_estimate,
            revenue_actual=revenue_actual,
            surprise_pct=surprise_pct,
            notes=notes,
            source=self._source("latest available earnings metadata", notes),
        )

    def get_analyst_estimates(self, ticker: str) -> AnalystEstimateSummary:
        asset = self._ticker(ticker)
        notes: list[str] = []

        target_mean_price = None
        recommendation = None
        current_quarter_eps = None
        next_quarter_eps = None
        current_year_eps = None
        next_year_eps = None

        info = getattr(asset, "info", {}) or {}
        target_mean_price = self._clean_float(info.get("targetMeanPrice"))
        recommendation = self._clean_str(info.get("recommendationKey"))

        try:
            earnings_trend = getattr(asset, "earnings_trend", None)
        except Exception:  # pragma: no cover - upstream instability
            earnings_trend = None
            notes.append("Analyst estimate trend data was unavailable from yfinance.")

        if isinstance(earnings_trend, pd.DataFrame) and not earnings_trend.empty:
            trend_map = {str(row.get("period")): row for _, row in earnings_trend.iterrows()}
            current_quarter_eps = self._clean_float((trend_map.get("0q") or {}).get("epsTrend"))
            next_quarter_eps = self._clean_float((trend_map.get("+1q") or {}).get("epsTrend"))
            current_year_eps = self._clean_float((trend_map.get("0y") or {}).get("epsTrend"))
            next_year_eps = self._clean_float((trend_map.get("+1y") or {}).get("epsTrend"))
        else:
            notes.append("Analyst estimate fields are partially stubbed in this first pass.")

        return AnalystEstimateSummary(
            ticker=ticker.upper(),
            current_quarter_eps=current_quarter_eps,
            next_quarter_eps=next_quarter_eps,
            current_year_eps=current_year_eps,
            next_year_eps=next_year_eps,
            recommendation=recommendation,
            target_mean_price=target_mean_price,
            notes=notes,
            source=self._source("latest available analyst metadata", notes),
        )

    def get_options_chain(self, ticker: str, expiry: str) -> OptionsChainSummary:
        asset = self._ticker(ticker)
        try:
            chain = asset.option_chain(expiry)
            calls_count = len(chain.calls) if hasattr(chain, "calls") else 0
            puts_count = len(chain.puts) if hasattr(chain, "puts") else 0
            notes: list[str] = []
        except Exception as exc:  # pragma: no cover - upstream instability
            calls_count = 0
            puts_count = 0
            notes = [f"Options chain was unavailable: {exc}"]

        return OptionsChainSummary(
            ticker=ticker.upper(),
            expiry=expiry,
            calls_count=calls_count,
            puts_count=puts_count,
            notes=notes,
            source=self._source("current options chain snapshot", notes),
        )
