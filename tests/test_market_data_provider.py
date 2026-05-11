from datetime import datetime, timezone

import pandas as pd

from src.providers.market_data import (
    AnalystEstimateSummary,
    EarningsSummary,
    FinancialSnapshot,
    OptionsChainSummary,
    QuoteSnapshot,
    make_source_metadata,
)
from src.providers.mock_market_data import MockMarketDataProvider


def test_mock_market_data_provider_returns_seeded_objects():
    source = make_source_metadata(
        provider="mock",
        freshness="seed data",
        official=False,
        notes=["research-only"],
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )
    provider = MockMarketDataProvider(
        quotes={
            "AAPL": QuoteSnapshot(
                ticker="AAPL",
                price=200.0,
                previous_close=198.0,
                open=199.0,
                day_high=201.0,
                day_low=197.0,
                volume=1000,
                currency="USD",
                market_time="2026-05-11T12:00:00Z",
                source=source,
            )
        },
        histories={
            ("AAPL", "1y", "1d"): pd.DataFrame(
                [
                    {"date": "2026-01-01", "close": 180.0},
                    {"date": "2026-05-11", "close": 200.0},
                ]
            )
        },
        financials={"AAPL": FinancialSnapshot(ticker="AAPL", revenue=100.0, source=source)},
        earnings={"AAPL": EarningsSummary(ticker="AAPL", next_earnings_date="2026-07-25", source=source)},
        estimates={"AAPL": AnalystEstimateSummary(ticker="AAPL", current_quarter_eps=1.5, source=source)},
        options_chains={("AAPL", "2026-06-19"): OptionsChainSummary(ticker="AAPL", expiry="2026-06-19", calls_count=10, puts_count=12, source=source)},
    )

    assert provider.get_quote("aapl").ticker == "AAPL"
    assert provider.getQuote("AAPL").ticker == "AAPL"
    assert provider.get_price_history("AAPL", "1y", "1d").iloc[-1]["close"] == 200.0
    assert provider.getPriceHistory("AAPL", "1y", "1d").iloc[-1]["close"] == 200.0
    assert provider.get_financials("AAPL").revenue == 100.0
    assert provider.getFinancials("AAPL").revenue == 100.0
    assert provider.get_earnings("AAPL").next_earnings_date == "2026-07-25"
    assert provider.getEarnings("AAPL").next_earnings_date == "2026-07-25"
    assert provider.get_analyst_estimates("AAPL").current_quarter_eps == 1.5
    assert provider.getAnalystEstimates("AAPL").current_quarter_eps == 1.5
    assert provider.get_options_chain("AAPL", "2026-06-19").calls_count == 10
    assert provider.getOptionsChain("AAPL", "2026-06-19").calls_count == 10
