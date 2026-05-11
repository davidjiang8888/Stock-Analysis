from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd


@dataclass
class SourceMetadata:
    provider: str
    freshness: str
    retrieved_at: str
    official: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QuoteSnapshot:
    ticker: str
    price: float | None
    previous_close: float | None
    open: float | None
    day_high: float | None
    day_low: float | None
    volume: float | None
    currency: str | None
    market_time: str | None
    source: SourceMetadata

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = self.source.to_dict()
        return data


@dataclass
class FinancialSnapshot:
    ticker: str
    revenue: float | None = None
    eps: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    profit_margin: float | None = None
    free_cash_flow: float | None = None
    market_cap: float | None = None
    enterprise_value: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    price_to_book: float | None = None
    shares_outstanding: float | None = None
    net_debt: float | None = None
    currency: str | None = None
    as_of_date: str | None = None
    source: SourceMetadata | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.source is not None:
            data["source"] = self.source.to_dict()
        return data


@dataclass
class EarningsSummary:
    ticker: str
    next_earnings_date: str | None = None
    last_earnings_date: str | None = None
    eps_estimate: float | None = None
    eps_actual: float | None = None
    revenue_estimate: float | None = None
    revenue_actual: float | None = None
    surprise_pct: float | None = None
    notes: list[str] = field(default_factory=list)
    source: SourceMetadata | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.source is not None:
            data["source"] = self.source.to_dict()
        return data


@dataclass
class AnalystEstimateSummary:
    ticker: str
    current_quarter_eps: float | None = None
    next_quarter_eps: float | None = None
    current_year_eps: float | None = None
    next_year_eps: float | None = None
    current_quarter_revenue: float | None = None
    next_quarter_revenue: float | None = None
    current_year_revenue: float | None = None
    next_year_revenue: float | None = None
    recommendation: str | None = None
    target_mean_price: float | None = None
    notes: list[str] = field(default_factory=list)
    source: SourceMetadata | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.source is not None:
            data["source"] = self.source.to_dict()
        return data


@dataclass
class OptionsChainSummary:
    ticker: str
    expiry: str
    calls_count: int
    puts_count: int
    source: SourceMetadata | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.source is not None:
            data["source"] = self.source.to_dict()
        return data


class MarketDataProvider(ABC):
    @abstractmethod
    def get_quote(self, ticker: str) -> QuoteSnapshot:
        raise NotImplementedError

    @abstractmethod
    def get_price_history(self, ticker: str, period: str, interval: str) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def get_financials(self, ticker: str) -> FinancialSnapshot:
        raise NotImplementedError

    @abstractmethod
    def get_earnings(self, ticker: str) -> EarningsSummary:
        raise NotImplementedError

    @abstractmethod
    def get_analyst_estimates(self, ticker: str) -> AnalystEstimateSummary:
        raise NotImplementedError

    @abstractmethod
    def get_options_chain(self, ticker: str, expiry: str) -> OptionsChainSummary:
        raise NotImplementedError

    # Compatibility aliases for workflow specs that describe camelCase methods.
    def getQuote(self, ticker: str) -> QuoteSnapshot:
        return self.get_quote(ticker)

    def getPriceHistory(self, ticker: str, period: str, interval: str) -> pd.DataFrame:
        return self.get_price_history(ticker, period, interval)

    def getFinancials(self, ticker: str) -> FinancialSnapshot:
        return self.get_financials(ticker)

    def getEarnings(self, ticker: str) -> EarningsSummary:
        return self.get_earnings(ticker)

    def getAnalystEstimates(self, ticker: str) -> AnalystEstimateSummary:
        return self.get_analyst_estimates(ticker)

    def getOptionsChain(self, ticker: str, expiry: str) -> OptionsChainSummary:
        return self.get_options_chain(ticker, expiry)


def make_source_metadata(
    provider: str,
    freshness: str,
    official: bool,
    notes: list[str] | None = None,
    retrieved_at: str | None = None,
) -> SourceMetadata:
    return SourceMetadata(
        provider=provider,
        freshness=freshness,
        retrieved_at=retrieved_at or datetime.utcnow().isoformat(timespec="seconds") + "Z",
        official=official,
        notes=notes or [],
    )
