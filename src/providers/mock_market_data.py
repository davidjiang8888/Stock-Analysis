from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.providers.market_data import (
    AnalystEstimateSummary,
    EarningsSummary,
    FinancialSnapshot,
    MarketDataProvider,
    OptionsChainSummary,
    QuoteSnapshot,
)


@dataclass
class MockMarketDataProvider(MarketDataProvider):
    quotes: dict[str, QuoteSnapshot] = field(default_factory=dict)
    histories: dict[tuple[str, str, str], pd.DataFrame] = field(default_factory=dict)
    financials: dict[str, FinancialSnapshot] = field(default_factory=dict)
    earnings: dict[str, EarningsSummary] = field(default_factory=dict)
    estimates: dict[str, AnalystEstimateSummary] = field(default_factory=dict)
    options_chains: dict[tuple[str, str], OptionsChainSummary] = field(default_factory=dict)

    def get_quote(self, ticker: str) -> QuoteSnapshot:
        return self.quotes[ticker.upper()]

    def get_price_history(self, ticker: str, period: str, interval: str) -> pd.DataFrame:
        return self.histories[(ticker.upper(), period, interval)].copy()

    def get_financials(self, ticker: str) -> FinancialSnapshot:
        return self.financials[ticker.upper()]

    def get_earnings(self, ticker: str) -> EarningsSummary:
        return self.earnings[ticker.upper()]

    def get_analyst_estimates(self, ticker: str) -> AnalystEstimateSummary:
        return self.estimates[ticker.upper()]

    def get_options_chain(self, ticker: str, expiry: str) -> OptionsChainSummary:
        return self.options_chains[(ticker.upper(), expiry)]
