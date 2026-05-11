from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from src.indicators import compute_return
from src.providers.market_data import (
    AnalystEstimateSummary,
    EarningsSummary,
    FinancialSnapshot,
    MarketDataProvider,
    QuoteSnapshot,
    make_source_metadata,
)
from src.providers.local_market_data import LocalCSVMarketDataProvider
from src.providers.mock_market_data import MockMarketDataProvider
from src.valuation import ValuationScaffold, build_default_valuation_scaffold


@dataclass
class PerformanceSummary:
    one_month: float | None
    three_month: float | None
    one_year: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DataFreshnessNote:
    provider: str
    freshness: str
    retrieved_at: str
    official: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StockReport:
    ticker: str
    price_snapshot: dict[str, Any]
    performance: PerformanceSummary
    financial_summary: dict[str, Any]
    valuation_snapshot: dict[str, Any]
    earnings_summary: dict[str, Any]
    analyst_estimate_summary: dict[str, Any]
    key_risks: list[str]
    data_freshness: list[DataFreshnessNote]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "price_snapshot": self.price_snapshot,
            "performance": self.performance.to_dict(),
            "financial_summary": self.financial_summary,
            "valuation_snapshot": self.valuation_snapshot,
            "earnings_summary": self.earnings_summary,
            "analyst_estimate_summary": self.analyst_estimate_summary,
            "key_risks": self.key_risks,
            "data_freshness": [note.to_dict() for note in self.data_freshness],
        }


def _metadata_from_source(source) -> DataFreshnessNote:
    return DataFreshnessNote(
        provider=source.provider,
        freshness=source.freshness,
        retrieved_at=source.retrieved_at,
        official=source.official,
        notes=list(source.notes),
    )


def _clean_number(value: float | int | None) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _performance_from_history(history: pd.DataFrame) -> PerformanceSummary:
    if history.empty or "close" not in history.columns:
        return PerformanceSummary(one_month=None, three_month=None, one_year=None)

    closes = pd.to_numeric(history["close"], errors="coerce").dropna()
    return PerformanceSummary(
        one_month=_clean_number(compute_return(closes, 21)),
        three_month=_clean_number(compute_return(closes, 63)),
        one_year=_clean_number(compute_return(closes, 252)),
    )


def _build_risks(
    performance: PerformanceSummary,
    financials: FinancialSnapshot,
    earnings: EarningsSummary,
    estimates: AnalystEstimateSummary,
) -> list[str]:
    risks: list[str] = []

    if performance.one_year is None:
        risks.append("1Y price performance is unavailable.")
    elif performance.one_year < 0:
        risks.append("1Y price performance is negative.")

    if financials.free_cash_flow is None:
        risks.append("Free-cash-flow coverage is unavailable.")
    elif financials.free_cash_flow < 0:
        risks.append("Free cash flow is negative.")

    if financials.operating_margin is None:
        risks.append("Operating margin coverage is unavailable.")
    elif financials.operating_margin < 0:
        risks.append("Operating margin is negative.")

    if financials.net_debt is not None and financials.net_debt > 0:
        risks.append("Net debt is positive and should be reviewed against cash-flow durability.")

    if earnings.next_earnings_date is None:
        risks.append("Next earnings date is unavailable.")

    if estimates.current_quarter_eps is None and estimates.current_quarter_revenue is None:
        risks.append("Analyst estimate coverage is limited.")

    return risks


def _price_snapshot_dict(quote: QuoteSnapshot) -> dict[str, Any]:
    return {
        "ticker": quote.ticker,
        "price": quote.price,
        "previous_close": quote.previous_close,
        "open": quote.open,
        "day_high": quote.day_high,
        "day_low": quote.day_low,
        "volume": quote.volume,
        "currency": quote.currency,
        "market_time": quote.market_time,
        "source": quote.source.to_dict(),
    }


def _financial_summary_dict(financials: FinancialSnapshot) -> dict[str, Any]:
    return {
        "revenue": financials.revenue,
        "eps": financials.eps,
        "gross_margin": financials.gross_margin,
        "operating_margin": financials.operating_margin,
        "profit_margin": financials.profit_margin,
        "free_cash_flow": financials.free_cash_flow,
        "market_cap": financials.market_cap,
        "enterprise_value": financials.enterprise_value,
        "trailing_pe": financials.trailing_pe,
        "forward_pe": financials.forward_pe,
        "price_to_book": financials.price_to_book,
        "currency": financials.currency,
        "as_of_date": financials.as_of_date,
        "source": financials.source.to_dict() if financials.source else None,
    }


def _valuation_snapshot_dict(scaffold: ValuationScaffold) -> dict[str, Any]:
    return {
        "status": "scaffold",
        "notes": ["Valuation remains a Phase 1 scaffold and should not be treated as a finished fair-value model."],
        **scaffold.to_dict(),
    }


def build_stock_report(ticker: str, provider: MarketDataProvider) -> StockReport:
    ticker = ticker.upper()
    quote = provider.get_quote(ticker)
    history = provider.get_price_history(ticker, period="1y", interval="1d")
    financials = provider.get_financials(ticker)
    earnings = provider.get_earnings(ticker)
    estimates = provider.get_analyst_estimates(ticker)

    performance = _performance_from_history(history)
    valuation = build_default_valuation_scaffold(
        ticker=ticker,
        current_price=quote.price,
        shares_outstanding=financials.shares_outstanding,
        net_debt=financials.net_debt,
        free_cash_flow=financials.free_cash_flow,
    )

    data_freshness = [_metadata_from_source(quote.source)]
    if financials.source:
        data_freshness.append(_metadata_from_source(financials.source))
    if earnings.source:
        data_freshness.append(_metadata_from_source(earnings.source))
    if estimates.source:
        data_freshness.append(_metadata_from_source(estimates.source))

    return StockReport(
        ticker=ticker,
        price_snapshot=_price_snapshot_dict(quote),
        performance=performance,
        financial_summary=_financial_summary_dict(financials),
        valuation_snapshot=_valuation_snapshot_dict(valuation),
        earnings_summary=earnings.to_dict(),
        analyst_estimate_summary=estimates.to_dict(),
        key_risks=_build_risks(performance, financials, earnings, estimates),
        data_freshness=data_freshness,
    )


def export_stock_report_json(report: StockReport, output_path: Path | None = None) -> str:
    payload = json.dumps(report.to_dict(), indent=2)
    if output_path is not None:
        output_path.write_text(payload + "\n", encoding="utf-8")
    return payload


def build_provider(provider_name: str, base_dir: Path | None = None) -> MarketDataProvider:
    provider_name = provider_name.lower()
    if provider_name == "local":
        return LocalCSVMarketDataProvider(base_dir=base_dir)
    if provider_name == "mock":
        source = make_source_metadata(
            provider="mock",
            freshness="demo snapshot",
            official=False,
            notes=["Demo-only mock data for smoke tests."],
        )
        history = pd.DataFrame(
            [{"date": pd.Timestamp("2025-05-12") + pd.Timedelta(days=day), "close": 100.0 + day} for day in range(260)]
        )
        return MockMarketDataProvider(
            quotes={
                "AAPL": QuoteSnapshot(
                    ticker="AAPL",
                    price=360.0,
                    previous_close=358.0,
                    open=359.0,
                    day_high=362.0,
                    day_low=357.0,
                    volume=1_000_000,
                    currency="USD",
                    market_time="2026-05-11T15:30:00Z",
                    source=source,
                )
            },
            histories={("AAPL", "1y", "1d"): history},
            financials={"AAPL": FinancialSnapshot(ticker="AAPL", revenue=1_000_000_000, free_cash_flow=100_000_000, source=source)},
            earnings={"AAPL": EarningsSummary(ticker="AAPL", next_earnings_date="2026-07-20", source=source)},
            estimates={"AAPL": AnalystEstimateSummary(ticker="AAPL", current_quarter_eps=1.5, source=source)},
        )
    if provider_name == "yfinance":
        from src.providers.yfinance_provider import YFinanceProvider

        return YFinanceProvider()
    raise ValueError(f"Unsupported stock report provider: {provider_name}")


def create_stock_report_payload(ticker: str, provider_name: str = "local", base_dir: Path | None = None) -> dict[str, Any]:
    report = build_stock_report(ticker, build_provider(provider_name, base_dir=base_dir))
    return report.to_dict()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a structured stock report.")
    parser.add_argument("--ticker", required=True, help="Ticker symbol to analyze")
    parser.add_argument("--provider", default="local", choices=["local", "mock", "yfinance"], help="Research data provider")
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()

    report = build_stock_report(args.ticker, build_provider(args.provider))
    payload = export_stock_report_json(report, Path(args.output) if args.output else None)
    print(payload)


if __name__ == "__main__":
    main()
