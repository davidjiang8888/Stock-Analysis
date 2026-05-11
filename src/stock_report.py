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
from src.providers.local_templates import write_local_data_templates
from src.providers.mock_market_data import MockMarketDataProvider
from src.valuation import ValuationInput, ValuationResult, build_valuation_result


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
    generated_at: str
    provider_name: str
    price_snapshot: dict[str, Any]
    performance: PerformanceSummary
    financial_summary: dict[str, Any]
    valuation_snapshot: dict[str, Any]
    earnings_summary: dict[str, Any]
    analyst_estimate_summary: dict[str, Any]
    key_risks: list[str]
    missing_data_warnings: list[str]
    data_freshness: list[DataFreshnessNote]
    valuation_readiness: dict[str, Any] = field(default_factory=dict)
    dataset_coverage: list[dict[str, Any]] = field(default_factory=list)
    local_data_validation: list[dict[str, Any]] = field(default_factory=list)
    screener_context: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "generated_at": self.generated_at,
            "provider_name": self.provider_name,
            "price_snapshot": self.price_snapshot,
            "performance": self.performance.to_dict(),
            "financial_summary": self.financial_summary,
            "valuation_snapshot": self.valuation_snapshot,
            "earnings_summary": self.earnings_summary,
            "analyst_estimate_summary": self.analyst_estimate_summary,
            "key_risks": self.key_risks,
            "missing_data_warnings": self.missing_data_warnings,
            "data_freshness": [note.to_dict() for note in self.data_freshness],
            "valuation_readiness": self.valuation_readiness,
            "dataset_coverage": self.dataset_coverage,
            "local_data_validation": self.local_data_validation,
            "screener_context": self.screener_context,
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


def _build_missing_data_warnings(
    performance: PerformanceSummary,
    financials: FinancialSnapshot,
    earnings: EarningsSummary,
    estimates: AnalystEstimateSummary,
    dataset_coverage: list[dict[str, Any]],
    valuation: ValuationResult,
) -> list[str]:
    warnings: list[str] = []
    core_datasets = {"prices", "fundamentals", "earnings", "analyst_estimates"}
    if performance.one_month is None:
        warnings.append("1M performance is unavailable from the current local price history.")
    if performance.three_month is None:
        warnings.append("3M performance is unavailable from the current local price history.")
    if performance.one_year is None:
        warnings.append("1Y performance is unavailable from the current local price history.")
    if financials.revenue is None:
        warnings.append("Revenue is unavailable from the current local fundamentals dataset.")
    if financials.eps is None:
        warnings.append("EPS is unavailable from the current local fundamentals dataset.")
    if financials.free_cash_flow is None:
        warnings.append("Free cash flow is unavailable from the current local fundamentals dataset.")
    warnings.extend(earnings.notes)
    warnings.extend(estimates.notes)
    warnings.extend(valuation.warnings)
    warnings.extend([f"Valuation missing field: {field}" for field in valuation.missing_fields])
    for row in dataset_coverage:
        if row.get("dataset_name") in core_datasets and not row.get("ticker_present"):
            warnings.append(f"{row['dataset_name']} has no local row for this ticker.")
    return sorted(set(warnings))


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
        "revenue_growth": financials.revenue_growth,
        "eps": financials.eps,
        "gross_margin": financials.gross_margin,
        "operating_margin": financials.operating_margin,
        "profit_margin": financials.profit_margin,
        "free_cash_flow": financials.free_cash_flow,
        "fcf_margin": financials.fcf_margin,
        "ebitda": financials.ebitda,
        "market_cap": financials.market_cap,
        "enterprise_value": financials.enterprise_value,
        "trailing_pe": financials.trailing_pe,
        "forward_pe": financials.forward_pe,
        "price_to_book": financials.price_to_book,
        "shares_outstanding": financials.shares_outstanding,
        "cash": financials.cash,
        "debt": financials.debt,
        "net_debt": financials.net_debt,
        "debt_to_equity": financials.debt_to_equity,
        "currency": financials.currency,
        "as_of_date": financials.as_of_date,
        "source": financials.source.to_dict() if financials.source else None,
    }


def _valuation_snapshot_dict(result: ValuationResult) -> dict[str, Any]:
    return result.to_dict()


def _valuation_readiness_dict(
    valuation: ValuationResult,
    earnings: EarningsSummary,
    estimates: AnalystEstimateSummary,
) -> dict[str, Any]:
    dcf_missing = list(valuation.dcf_result.missing_fields)
    relative_missing = list(valuation.relative_valuation.missing_fields)
    return {
        "dcf_ready": valuation.dcf_result.status == "calculated",
        "relative_ready": valuation.relative_valuation.status in {"calculated", "peer_data_unavailable"},
        "peer_ready": valuation.relative_valuation.status == "calculated",
        "peer_count": valuation.relative_valuation.peer_count,
        "earnings_available": any(
            value is not None
            for value in (
                earnings.next_earnings_date,
                earnings.last_earnings_date,
                earnings.eps_estimate,
                earnings.eps_actual,
                earnings.revenue_estimate,
                earnings.revenue_actual,
            )
        ),
        "analyst_estimates_available": any(
            value is not None
            for value in (
                estimates.current_quarter_eps,
                estimates.next_quarter_eps,
                estimates.current_year_eps,
                estimates.next_year_eps,
                estimates.target_mean_price,
            )
        ),
        "dcf_missing_fields": dcf_missing,
        "relative_missing_fields": relative_missing,
        "notes": [
            "DCF readiness requires either direct free cash flow or revenue plus FCF margin.",
            "Peer-relative readiness requires local peers plus enough peer fundamentals to form median multiples.",
        ],
    }


def build_stock_report(ticker: str, provider: MarketDataProvider) -> StockReport:
    ticker = ticker.upper()
    quote = provider.get_quote(ticker)
    history = provider.get_price_history(ticker, period="1y", interval="1d")
    financials = provider.get_financials(ticker)
    earnings = provider.get_earnings(ticker)
    estimates = provider.get_analyst_estimates(ticker)

    performance = _performance_from_history(history)
    data_freshness = [_metadata_from_source(quote.source)]
    if financials.source:
        data_freshness.append(_metadata_from_source(financials.source))
    if earnings.source:
        data_freshness.append(_metadata_from_source(earnings.source))
    if estimates.source:
        data_freshness.append(_metadata_from_source(estimates.source))

    dataset_coverage = provider.get_ticker_dataset_coverage(ticker) if hasattr(provider, "get_ticker_dataset_coverage") else []
    local_data_validation = provider.get_local_data_validation() if hasattr(provider, "get_local_data_validation") else []
    screener_context = provider.get_screener_context(ticker) if hasattr(provider, "get_screener_context") else {}
    valuation = build_valuation_result(
        ValuationInput(
            ticker=ticker,
            current_price=quote.price,
            revenue=financials.revenue,
            revenue_growth=financials.revenue_growth,
            free_cash_flow=financials.free_cash_flow,
            fcf_margin=financials.fcf_margin,
            operating_margin=financials.operating_margin,
            profit_margin=financials.profit_margin,
            eps=financials.eps,
            ebitda=financials.ebitda,
            shares_outstanding=financials.shares_outstanding,
            cash=financials.cash,
            debt=financials.debt,
            net_debt=financials.net_debt,
            market_cap=financials.market_cap,
            trailing_pe=financials.trailing_pe,
            forward_pe=financials.forward_pe,
            price_to_book=financials.price_to_book,
            peer_inputs=provider.get_peer_valuation_inputs(ticker) if hasattr(provider, "get_peer_valuation_inputs") else [],
            source_metadata=[note.to_dict() for note in data_freshness],
            screener_context=screener_context,
        )
    )
    missing_data_warnings = _build_missing_data_warnings(
        performance,
        financials,
        earnings,
        estimates,
        dataset_coverage,
        valuation,
    )

    return StockReport(
        ticker=ticker,
        generated_at=pd.Timestamp.now(tz="UTC").isoformat(),
        provider_name=type(provider).__name__,
        price_snapshot=_price_snapshot_dict(quote),
        performance=performance,
        financial_summary=_financial_summary_dict(financials),
        valuation_snapshot=_valuation_snapshot_dict(valuation),
        earnings_summary=earnings.to_dict(),
        analyst_estimate_summary=estimates.to_dict(),
        key_risks=_build_risks(performance, financials, earnings, estimates),
        missing_data_warnings=missing_data_warnings,
        data_freshness=data_freshness,
        valuation_readiness=_valuation_readiness_dict(valuation, earnings, estimates),
        dataset_coverage=dataset_coverage,
        local_data_validation=local_data_validation,
        screener_context=screener_context,
    )


def export_stock_report_json(report: StockReport, output_path: Path | None = None) -> str:
    payload = json.dumps(report.to_dict(), indent=2)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
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
            financials={
                "AAPL": FinancialSnapshot(
                    ticker="AAPL",
                    revenue=1_000_000_000,
                    revenue_growth=0.10,
                    eps=12.0,
                    free_cash_flow=100_000_000,
                    fcf_margin=0.10,
                    operating_margin=0.22,
                    ebitda=180_000_000,
                    shares_outstanding=1_000_000,
                    cash=50_000_000,
                    debt=20_000_000,
                    source=source,
                )
            },
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
    parser.add_argument("--ticker", help="Ticker symbol to analyze")
    parser.add_argument("--provider", default="local", choices=["local", "mock", "yfinance"], help="Research data provider")
    parser.add_argument("--output", help="Optional JSON output path")
    parser.add_argument("--list-local-tickers", action="store_true", help="List tickers discoverable from local CSV datasets.")
    parser.add_argument("--validate-local-data", action="store_true", help="Validate local CSV datasets and report schema coverage.")
    parser.add_argument("--write-local-data-templates", action="store_true", help="Write header-only local enrichment CSV templates under data/templates.")
    parser.add_argument("--template-dir", help="Optional destination directory for local CSV templates.")
    parser.add_argument("--json", action="store_true", help="Print validation output as JSON when used with --validate-local-data.")
    args = parser.parse_args()
    cli_base_dir = Path.cwd()

    if args.write_local_data_templates:
        template_results = write_local_data_templates(
            base_dir=cli_base_dir,
            template_dir=Path(args.template_dir) if args.template_dir else None,
        )
        if args.json:
            print(json.dumps(template_results, indent=2))
        else:
            for item in template_results:
                print(
                    f"{item['dataset_name']}: {item['status']} -> {item['path']} "
                    f"columns={','.join(item['columns'])}"
                )
        return

    if args.validate_local_data:
        provider = LocalCSVMarketDataProvider(base_dir=cli_base_dir)
        validation = provider.get_local_data_validation()
        if args.json:
            print(json.dumps(validation, indent=2))
        else:
            for item in validation:
                print(
                    f"{item['name']}: status={item['validation_status']} rows={item['row_count']} "
                    f"required_missing={','.join(item['missing_required_columns']) or '-'} "
                    f"warnings={'; '.join(item['validation_warnings']) or '-'}"
                )
        return

    if args.list_local_tickers:
        provider = LocalCSVMarketDataProvider(base_dir=cli_base_dir)
        tickers = provider.list_local_tickers()
        print("\n".join(tickers))
        return

    if not args.ticker:
        raise SystemExit("--ticker is required unless --list-local-tickers is used.")

    try:
        report = build_stock_report(args.ticker, build_provider(args.provider, base_dir=cli_base_dir))
        payload = export_stock_report_json(report, Path(args.output) if args.output else None)
    except (FileNotFoundError, LookupError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"Stock report generation failed: {exc}") from exc
    print(payload)


if __name__ == "__main__":
    main()
