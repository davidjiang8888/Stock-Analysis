from datetime import datetime, timezone

import pandas as pd

from src.providers.market_data import (
    AnalystEstimateSummary,
    EarningsSummary,
    FinancialSnapshot,
    QuoteSnapshot,
    make_source_metadata,
)
from src.providers.mock_market_data import MockMarketDataProvider
from src.stock_report import build_stock_report


def test_build_stock_report_assembles_expected_sections():
    source = make_source_metadata(
        provider="mock",
        freshness="daily snapshot",
        official=False,
        notes=["Unofficial / research-grade market data."],
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )
    history = pd.DataFrame(
        [{"date": pd.Timestamp("2025-05-12") + pd.Timedelta(days=day), "close": 100.0 + day} for day in range(260)]
    )

    provider = MockMarketDataProvider(
        quotes={
            "MSFT": QuoteSnapshot(
                ticker="MSFT",
                price=360.0,
                previous_close=355.0,
                open=356.0,
                day_high=362.0,
                day_low=354.0,
                volume=1_000_000,
                currency="USD",
                market_time="2026-05-11T15:30:00Z",
                source=source,
            )
        },
        histories={("MSFT", "1y", "1d"): history},
        financials={
            "MSFT": FinancialSnapshot(
                ticker="MSFT",
                revenue=250_000_000_000,
                eps=12.5,
                gross_margin=0.68,
                operating_margin=0.42,
                free_cash_flow=90_000_000_000,
                market_cap=2_700_000_000_000,
                shares_outstanding=7_400_000_000,
                source=source,
            )
        },
        earnings={
            "MSFT": EarningsSummary(
                ticker="MSFT",
                next_earnings_date="2026-07-24",
                last_earnings_date="2026-04-24",
                eps_estimate=3.0,
                eps_actual=3.1,
                surprise_pct=0.03,
                source=source,
            )
        },
        estimates={
            "MSFT": AnalystEstimateSummary(
                ticker="MSFT",
                current_quarter_eps=3.1,
                next_quarter_eps=3.25,
                current_year_eps=13.0,
                next_year_eps=14.1,
                recommendation="buy",
                target_mean_price=390.0,
                source=source,
            )
        },
    )

    report = build_stock_report("MSFT", provider).to_dict()

    assert report["ticker"] == "MSFT"
    assert report["price_snapshot"]["price"] == 360.0
    assert report["performance"]["one_month"] is not None
    assert report["financial_summary"]["revenue"] == 250_000_000_000
    assert report["valuation_snapshot"]["ticker"] == "MSFT"
    assert report["earnings_summary"]["next_earnings_date"] == "2026-07-24"
    assert report["analyst_estimate_summary"]["target_mean_price"] == 390.0
    assert len(report["data_freshness"]) >= 3
    assert any("research-grade" in " ".join(note["notes"]).lower() for note in report["data_freshness"])


def test_build_stock_report_surfaces_missing_data_risks():
    source = make_source_metadata(
        provider="mock",
        freshness="stale",
        official=False,
        notes=["Limited coverage."],
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )
    provider = MockMarketDataProvider(
        quotes={
            "TSLA": QuoteSnapshot(
                ticker="TSLA",
                price=180.0,
                previous_close=179.0,
                open=178.0,
                day_high=181.0,
                day_low=176.0,
                volume=100,
                currency="USD",
                market_time=None,
                source=source,
            )
        },
        histories={("TSLA", "1y", "1d"): pd.DataFrame([{"date": pd.Timestamp("2026-05-11"), "close": 180.0}])},
        financials={"TSLA": FinancialSnapshot(ticker="TSLA", free_cash_flow=None, operating_margin=-0.01, source=source)},
        earnings={"TSLA": EarningsSummary(ticker="TSLA", source=source)},
        estimates={"TSLA": AnalystEstimateSummary(ticker="TSLA", source=source)},
    )

    report = build_stock_report("TSLA", provider)

    assert any("1Y price performance is unavailable" in risk for risk in report.key_risks)
    assert any("Free-cash-flow coverage is unavailable" in risk for risk in report.key_risks)
    assert any("Operating margin is negative" in risk for risk in report.key_risks)
