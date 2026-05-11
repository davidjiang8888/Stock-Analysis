import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from src.providers.market_data import (
    AnalystEstimateSummary,
    EarningsSummary,
    FinancialSnapshot,
    QuoteSnapshot,
    make_source_metadata,
)
from src.providers.local_market_data import LocalCSVMarketDataProvider
from src.providers.mock_market_data import MockMarketDataProvider
from src.stock_report import build_stock_report, create_stock_report_payload, export_stock_report_json, main

RICH_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "rich_local_data"


def _copy_rich_fixture(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for path in RICH_FIXTURE_DIR.glob("*.csv"):
        (data_dir / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


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
                revenue_growth=0.10,
                eps=12.5,
                gross_margin=0.68,
                operating_margin=0.42,
                free_cash_flow=90_000_000_000,
                fcf_margin=0.36,
                cash=90_000_000_000,
                debt=40_000_000_000,
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
                recommendation="outperform",
                target_mean_price=390.0,
                source=source,
            )
        },
    )

    report = build_stock_report("MSFT", provider).to_dict()

    assert report["ticker"] == "MSFT"
    assert report["provider_name"] == "MockMarketDataProvider"
    assert report["generated_at"] is not None
    assert report["price_snapshot"]["price"] == 360.0
    assert report["performance"]["one_month"] is not None
    assert report["financial_summary"]["revenue"] == 250_000_000_000
    assert report["valuation_snapshot"]["status"] == "calculated"
    assert report["valuation_snapshot"]["dcf_result"]["fair_value_per_share"] is not None
    assert report["earnings_summary"]["next_earnings_date"] == "2026-07-24"
    assert report["analyst_estimate_summary"]["target_mean_price"] == 390.0
    assert "missing_data_warnings" in report
    assert report["valuation_readiness"]["dcf_ready"] is True
    assert report["local_data_validation"] == []
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
    assert report.valuation_snapshot["status"] == "insufficient_data"


def test_stock_report_json_export_is_serializable_and_contains_freshness_metadata(tmp_path: Path):
    source = make_source_metadata(
        provider="mock",
        freshness="daily snapshot",
        official=False,
        notes=["Unofficial / research-grade market data."],
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
        histories={("AAPL", "1y", "1d"): pd.DataFrame([{"date": pd.Timestamp("2026-01-01"), "close": 100.0}] * 260)},
        financials={"AAPL": FinancialSnapshot(ticker="AAPL", source=source)},
        earnings={"AAPL": EarningsSummary(ticker="AAPL", source=source)},
        estimates={"AAPL": AnalystEstimateSummary(ticker="AAPL", source=source)},
    )

    report = build_stock_report("AAPL", provider)
    output_path = tmp_path / "report.json"
    payload = export_stock_report_json(report, output_path)
    parsed = json.loads(payload)

    assert output_path.exists()
    assert parsed["ticker"] == "AAPL"
    assert parsed["data_freshness"][0]["provider"] == "mock"
    assert parsed["provider_name"] == "MockMarketDataProvider"
    assert "missing_data_warnings" in parsed
    assert "valuation_readiness" in parsed
    assert "status" in parsed["valuation_snapshot"]
    assert parsed["valuation_snapshot"]["status"] == "insufficient_data"


def test_create_stock_report_payload_uses_local_provider_when_csvs_are_available(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "prices.csv").write_text(
        "date,ticker,adj_close,volume\n"
        "2026-01-02,MSFT,100,1000\n"
        "2026-05-11,MSFT,130,1100\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "fundamentals.csv").write_text(
        "ticker,profit_margin,operating_margin,pe_ratio\n"
        "MSFT,0.30,0.35,28\n",
        encoding="utf-8",
    )

    payload = create_stock_report_payload("MSFT", provider_name="local", base_dir=tmp_path)

    assert payload["ticker"] == "MSFT"
    assert payload["price_snapshot"]["price"] == 130.0
    assert payload["financial_summary"]["profit_margin"] == 0.30
    assert payload["data_freshness"][0]["provider"] == "local:prices.csv"
    assert payload["dataset_coverage"]
    assert "local_data_validation" in payload
    assert "valuation_readiness" in payload
    assert payload["valuation_snapshot"]["status"] == "calculated"
    assert payload["valuation_snapshot"]["coverage"] == "partial"


def test_stock_report_cli_fails_gracefully_for_missing_local_ticker(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "prices.csv").write_text(
        "date,ticker,adj_close,volume\n"
        "2026-01-02,SPY,100,1000\n",
        encoding="utf-8",
    )
    previous_cwd = Path.cwd()
    os.chdir(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--ticker", "AAPL", "--provider", "local"]
    try:
        with pytest.raises(SystemExit, match="Stock report generation failed: No local price rows were found for AAPL"):
            main()
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)


def test_stock_report_cli_lists_local_tickers(tmp_path: Path, capsys):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "prices.csv").write_text(
        "date,ticker,adj_close,volume\n"
        "2026-01-02,SPY,100,1000\n"
        "2026-01-03,QQQ,101,1001\n",
        encoding="utf-8",
    )
    previous_cwd = Path.cwd()
    os.chdir(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--list-local-tickers"]
    try:
        main()
        output = capsys.readouterr().out.strip().splitlines()
        assert output == ["QQQ", "SPY"]
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)


def test_stock_report_cli_validate_local_data_json(tmp_path: Path, capsys):
    _copy_rich_fixture(tmp_path)
    previous_cwd = Path.cwd()
    os.chdir(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--validate-local-data", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
        assert any(item["name"] == "fundamentals" for item in payload)
        assert any(item["name"] == "peers" for item in payload)
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)


def test_stock_report_cli_validate_local_data_human_output(tmp_path: Path, capsys):
    _copy_rich_fixture(tmp_path)
    previous_cwd = Path.cwd()
    os.chdir(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--validate-local-data"]
    try:
        main()
        output = capsys.readouterr().out
        assert "prices: status=valid" in output
        assert "fundamentals: status=valid" in output
        assert "peers: status=valid" in output
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)


def test_stock_report_cli_write_local_data_templates(tmp_path: Path, capsys):
    previous_cwd = Path.cwd()
    os.chdir(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--write-local-data-templates"]
    try:
        main()
        output = capsys.readouterr().out
        assert "fundamentals: created" in output
        assert "peers: created" in output
        assert (tmp_path / "data" / "templates" / "fundamentals.csv").exists()
        assert (tmp_path / "data" / "templates" / "peers.csv").exists()
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)


def test_stock_report_cli_write_local_data_templates_json(tmp_path: Path, capsys):
    previous_cwd = Path.cwd()
    os.chdir(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--write-local-data-templates", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
        assert any(item["dataset_name"] == "fundamentals" for item in payload)
        assert any(item["dataset_name"] == "analyst_estimates" for item in payload)
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)


def test_stock_report_cli_write_import_staging(tmp_path: Path, capsys):
    previous_cwd = Path.cwd()
    os.chdir(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--write-import-staging"]
    try:
        main()
        output = capsys.readouterr().out
        assert "fundamentals: created" in output
        assert (tmp_path / "data" / "imports" / "fundamentals.csv").exists()
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)


def test_stock_report_cli_validate_imports_handles_no_staged_files(tmp_path: Path, capsys):
    (tmp_path / "data").mkdir()
    previous_cwd = Path.cwd()
    os.chdir(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--validate-imports"]
    try:
        main()
        output = capsys.readouterr().out.strip()
        assert output.startswith("no_staged_files:")
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)


def test_stock_report_cli_validate_imports_json(tmp_path: Path, capsys):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "imports").mkdir()
    (tmp_path / "data" / "imports" / "fundamentals.csv").write_text(
        "ticker,revenue,source,as_of_date\n"
        "NVDA,1000,manual,2026-05-01\n",
        encoding="utf-8",
    )
    previous_cwd = Path.cwd()
    os.chdir(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--validate-imports", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "valid"
        assert payload["files"][0]["file_name"] == "fundamentals.csv"
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)


def test_stock_report_cli_preview_import_merge_handles_no_staged_files(tmp_path: Path, capsys):
    (tmp_path / "data").mkdir()
    previous_cwd = Path.cwd()
    os.chdir(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--preview-import-merge"]
    try:
        main()
        output = capsys.readouterr().out.strip()
        assert output.startswith("no_staged_files:")
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)


def test_stock_report_cli_apply_import_merge_updates_canonical_file(tmp_path: Path, capsys):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "imports").mkdir()
    (tmp_path / "data" / "fundamentals.csv").write_text(
        "ticker,revenue,source,as_of_date\n"
        "MSFT,1000,old,2026-01-01\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "imports" / "fundamentals.csv").write_text(
        "ticker,revenue,source,as_of_date\n"
        "MSFT,1100,new,2026-05-01\n",
        encoding="utf-8",
    )
    previous_cwd = Path.cwd()
    os.chdir(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--apply-import-merge"]
    try:
        main()
        output = capsys.readouterr().out
        assert "fundamentals.csv: applied=True" in output
        payload = pd.read_csv(tmp_path / "data" / "fundamentals.csv")
        assert payload.loc[0, "revenue"] == 1100
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)


def test_stock_report_cli_preview_import_merge_json(tmp_path: Path, capsys):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "imports").mkdir()
    (tmp_path / "data" / "imports" / "fundamentals.csv").write_text(
        "ticker,revenue,source,as_of_date\n"
        "NVDA,1000,manual,2026-05-01\n",
        encoding="utf-8",
    )
    previous_cwd = Path.cwd()
    os.chdir(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--preview-import-merge", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "valid"
        assert payload["preview"][0]["file_name"] == "fundamentals.csv"
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)


def test_stock_report_cli_apply_import_merge_json(tmp_path: Path, capsys):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "imports").mkdir()
    (tmp_path / "data" / "fundamentals.csv").write_text(
        "ticker,revenue,source,as_of_date\n"
        "MSFT,1000,old,2026-01-01\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "imports" / "fundamentals.csv").write_text(
        "ticker,revenue,source,as_of_date\n"
        "MSFT,1100,new,2026-05-01\n",
        encoding="utf-8",
    )
    previous_cwd = Path.cwd()
    os.chdir(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--apply-import-merge", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "applied"
        assert payload["applied"][0]["file_name"] == "fundamentals.csv"
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)


def test_stock_report_from_rich_local_fixture_is_serializable_and_includes_validation(tmp_path: Path):
    payload = create_stock_report_payload("ALFA", provider_name="local", base_dir=_copy_rich_fixture(tmp_path))

    assert payload["valuation_snapshot"]["dcf_result"]["status"] == "calculated"
    assert payload["valuation_snapshot"]["relative_valuation"]["status"] == "calculated"
    assert payload["valuation_readiness"]["dcf_ready"] is True
    assert payload["valuation_readiness"]["peer_ready"] is True
    assert payload["local_data_validation"]
    assert any(item["name"] == "peers" for item in payload["local_data_validation"])
