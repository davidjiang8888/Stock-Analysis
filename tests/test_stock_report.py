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
from src.stock_report import (
    build_readiness_only_markdown,
    build_stock_report,
    create_stock_report_payload,
    export_stock_report_json,
    export_stock_report_markdown,
    main,
)

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


def test_stock_report_markdown_export_summarizes_readiness_without_advice(tmp_path: Path):
    source = make_source_metadata(
        provider="mock",
        freshness="daily snapshot",
        official=False,
        notes=["Research-grade fixture data."],
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )
    provider = MockMarketDataProvider(
        quotes={
            "QQQ": QuoteSnapshot(
                ticker="QQQ",
                price=500.0,
                previous_close=499.0,
                open=499.5,
                day_high=501.0,
                day_low=498.0,
                volume=1_000_000,
                currency="USD",
                market_time="2026-05-27T16:00:00Z",
                source=source,
            )
        },
        histories={("QQQ", "1y", "1d"): pd.DataFrame([{"date": pd.Timestamp("2026-01-01"), "close": 500.0}] * 30)},
        financials={"QQQ": FinancialSnapshot(ticker="QQQ", source=source)},
        earnings={"QQQ": EarningsSummary(ticker="QQQ", source=source)},
        estimates={"QQQ": AnalystEstimateSummary(ticker="QQQ", source=source)},
    )
    report = build_stock_report("QQQ", provider)
    output_path = tmp_path / "qqq.md"
    markdown = export_stock_report_markdown(
        report,
        output_path,
        local_context={
            "readiness": {"overall_readiness_state": "partial", "price_ready": True, "excluded_features": "dcf"},
            "decision": {
                "decision_bucket": "Monitor",
                "decision_subtype": "Monitor - ETF Market Proxy",
                "primary_blocker": "none",
                "main_reason": "ETF market proxy.",
                "next_best_action": "Use as market/risk context.",
                "purpose_thesis": "Purpose: ETF / Defensive / Hedge. Use as market, theme, liquidity, or risk context; operating-company valuation remains excluded.",
                "setup_evaluation": "Setup status: Setup Forming; final state: Setup Forming.",
                "valuation_evaluation": "Operating-company DCF is excluded for this asset type; use market/risk context instead of valuation conclusions.",
                "risk_watchpoint": "Risk watchpoint: monitor liquidity, correlation, and theme exposure; company-specific DCF does not apply.",
                "invalidation_condition": "Invalidate market-proxy usefulness if liquidity, correlation, or theme trend no longer supports the intended monitoring role.",
                "next_research_question": "What market, sector, or hedge signal is this proxy intended to monitor, and is that signal still supported by local price/risk data?",
                "confidence_explanation": "Confidence is medium: monitoring is supported by price, momentum, market_direction, while optional context remains unavailable.",
            },
            "dcf": {"reason_not_ready": "DCF excluded for etf."},
            "peer": {
                "peer_blocker_type": "missing_peer_mapping",
                "mapping_status": "missing_mapping",
                "peer_count": 0,
                "peer_trend_comparison_ready": False,
                "peer_valuation_comparison_ready": False,
                "next_peer_action": "Add source-backed peer mappings for QQQ.",
            },
        },
    )

    assert output_path.exists()
    assert "# QQQ Research Readiness Report" in markdown
    assert "## One-Minute Status" in markdown
    assert "Decision: Monitor - ETF Market Proxy" in markdown
    assert "Monitor - ETF Market Proxy" in markdown
    assert "Research-only local report" in markdown
    assert "DCF: excluded" in markdown
    assert "Optional earnings or analyst-estimate context is unavailable" in markdown
    assert "## Research Evaluation" in markdown
    assert "Purpose thesis" in markdown
    assert "market, theme, liquidity, or risk context" in markdown
    assert "Operating-company DCF is excluded" in markdown
    assert "Invalidate market-proxy usefulness" in markdown
    assert "## Source/Freshness Audit" in markdown
    assert "data/staged/earnings/" in markdown
    assert "make import-analyst-estimates" in markdown
    assert "STOOQ_API_KEY" in markdown
    assert "DCF excluded for etf" in markdown
    assert "Peer Workflow" in markdown
    assert "missing_peer_mapping" in markdown
    assert "Add source-backed peer mappings for QQQ" in markdown
    assert "buy" not in markdown.lower()
    assert "sell" not in markdown.lower()


def test_readiness_only_markdown_handles_blocked_broad_universe_ticker_without_advice():
    markdown = build_readiness_only_markdown(
        "APLD",
        {
            "readiness": {
                "overall_readiness_state": "blocked",
                "asset_type": "company",
                "price_ready": False,
                "blocked_features": "price, momentum, dcf",
                "missing_data": "needs at least 5 valid price rows with positive close",
                "next_action": "Import staged price rows or refresh price provider for APLD.",
            },
            "decision": {
                "decision_bucket": "Blocked by Data",
                "decision_subtype": "Blocked by Data - Missing Price",
                "primary_blocker": "price",
                "main_reason": "Missing usable price data.",
                "next_best_action": "Import staged price rows or refresh price provider for APLD.",
                "purpose_thesis": "Purpose: Speculative Optionality. Interpretation is blocked until price history is available.",
                "setup_evaluation": "Setup cannot be evaluated because usable price history is missing.",
                "valuation_evaluation": "Valuation conclusion is blocked until trusted DCF/fundamental inputs are complete.",
                "risk_watchpoint": "Primary risk is analytical blindness from missing price history; do not interpret trend or volatility yet.",
                "invalidation_condition": "Invalidate any setup read until price history is available and passes readiness checks.",
                "next_research_question": "Can trusted local price rows be staged for APLD so trend, liquidity, and downstream analysis become testable?",
                "confidence_explanation": "Confidence is low because the primary blocker is price; current output is an unlock checklist, not analysis.",
            },
            "price_coverage": {"price_rows": 0, "missing_price_reason": "needs at least 5 valid price rows"},
            "peer": {
                "peer_blocker_type": "missing_peer_mapping",
                "mapping_status": "missing_mapping",
                "peer_count": 0,
                "next_peer_action": "Add source-backed peer mappings after price data exists.",
            },
        },
        "No local price rows were found for APLD.",
    )

    assert "readiness-only report" in markdown
    assert "## One-Minute Status" in markdown
    assert "Decision: Blocked by Data - Missing Price" in markdown
    assert "Primary blocker: price" in markdown
    assert "Blocked by Data - Missing Price" in markdown
    assert "DCF: blocked" in markdown
    assert "## Research Evaluation" in markdown
    assert "Setup cannot be evaluated because usable price history is missing" in markdown
    assert "analytical blindness" in markdown
    assert "primary blocker is price" in markdown
    assert "## Source/Freshness Audit" in markdown
    assert "data/staged/prices/" in markdown
    assert "data/rejected/price_import_rejected.csv" in markdown
    assert "Peer Workflow" in markdown
    assert "missing_peer_mapping" in markdown
    assert "No local price rows were found for APLD" in markdown
    assert "buy" not in markdown.lower()
    assert "sell" not in markdown.lower()


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
    sys.argv = ["python", "--project-root", str(tmp_path), "--ticker", "AAPL", "--provider", "local"]
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
    sys.argv = ["python", "--project-root", str(tmp_path), "--list-local-tickers"]
    try:
        main()
        output = capsys.readouterr().out.strip().splitlines()
        assert f"Project root: {tmp_path}" in output
        assert output[-2:] == ["QQQ", "SPY"]
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)


def test_stock_report_cli_validate_local_data_json(tmp_path: Path, capsys):
    _copy_rich_fixture(tmp_path)
    previous_cwd = Path.cwd()
    os.chdir(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--validate-local-data", "--json"]
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
    sys.argv = ["python", "--project-root", str(tmp_path), "--validate-local-data"]
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
    sys.argv = ["python", "--project-root", str(tmp_path), "--write-local-data-templates"]
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
    sys.argv = ["python", "--project-root", str(tmp_path), "--write-local-data-templates", "--json"]
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
    sys.argv = ["python", "--project-root", str(tmp_path), "--write-import-staging"]
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
    sys.argv = ["python", "--project-root", str(tmp_path), "--validate-imports"]
    try:
        main()
        output = capsys.readouterr().out.strip()
        assert "no_staged_files:" in output
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
    sys.argv = ["python", "--project-root", str(tmp_path), "--validate-imports", "--json"]
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
    sys.argv = ["python", "--project-root", str(tmp_path), "--preview-import-merge"]
    try:
        main()
        output = capsys.readouterr().out.strip()
        assert "no_staged_files:" in output
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
    sys.argv = ["python", "--project-root", str(tmp_path), "--apply-import-merge"]
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
    sys.argv = ["python", "--project-root", str(tmp_path), "--preview-import-merge", "--json"]
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
    sys.argv = ["python", "--project-root", str(tmp_path), "--apply-import-merge", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "applied"
        assert payload["applied"][0]["file_name"] == "fundamentals.csv"
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)


def test_stock_report_cli_sec_stage_json_surfaces_make_based_follow_up(monkeypatch, tmp_path: Path, capsys):
    (tmp_path / "data").mkdir()
    previous_cwd = Path.cwd()
    os.chdir(tmp_path)
    previous_argv = sys.argv[:]

    monkeypatch.setattr(
        "src.stock_report.build_sec_fundamentals_rows",
        lambda requested_tickers, user_agent, cache_dir, refresh: {
            "requested_tickers": requested_tickers,
            "resolved_tickers": requested_tickers,
            "unresolved_tickers": [],
            "rows": [{"ticker": requested_tickers[0], "revenue": 1000}],
            "warnings": [],
            "row_summaries": [{"ticker": requested_tickers[0], "populated_fields": ["revenue"], "missing_fields": [], "warnings": []}],
        },
    )
    monkeypatch.setattr(
        "src.stock_report.write_sec_fundamentals_import",
        lambda rows, output_path, overwrite: {
            "rows_written": len(rows),
            "staged_row_count": len(rows),
            "output_path": str(output_path),
        },
    )

    sys.argv = ["python", "--project-root", str(tmp_path), "--sec-stage-fundamentals", "--tickers", "NVDA", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
        assert payload["recommended_next_commands"] == [
            "make imports-validate",
            "make imports-preview",
            "make imports-apply",
        ]
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)


def test_stock_report_from_rich_local_fixture_is_serializable_and_includes_validation(tmp_path: Path):
    payload = create_stock_report_payload("ALFA", provider_name="local", base_dir=_copy_rich_fixture(tmp_path))

    assert payload["valuation_snapshot"]["dcf_result"]["status"] == "calculated"
    assert payload["valuation_snapshot"]["relative_valuation"]["status"] == "calculated"
    assert payload["valuation_readiness"]["dcf_ready"] is True
    assert payload["valuation_readiness"]["peer_ready"] is True
    assert payload["valuation_snapshot"]["relative_valuation"]["peer_group"] == "fixture_group"
    assert payload["valuation_snapshot"]["relative_valuation"]["peer_tickers"] == ["BETA", "GAMMA"]
    assert payload["valuation_snapshot"]["relative_valuation"]["relative_discount_premium_by_metric"]["pe"] is not None
    assert payload["valuation_readiness"]["peer_count"] == 2
    assert payload["valuation_readiness"]["earnings_available"] is True
    assert payload["valuation_readiness"]["analyst_estimates_available"] is True
    assert payload["local_data_validation"]
    assert any(item["name"] == "peers" for item in payload["local_data_validation"])
