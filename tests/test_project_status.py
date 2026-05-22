import json
from pathlib import Path
import sys

import pandas as pd
import pytest

from src.project_status import build_project_status_payload, main, write_project_status_output


def _write_minimal_local_data(root: Path) -> None:
    data_dir = root / "data"
    outputs_dir = root / "outputs"
    data_dir.mkdir()
    outputs_dir.mkdir()
    (root / "config.yaml").write_text(Path("config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    pd.DataFrame(
        [
            {"ticker": "NVDA", "date": "2026-01-01", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 1000},
            {"ticker": "NVDA", "date": "2026-01-02", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 1100},
        ]
    ).to_csv(data_dir / "prices.csv", index=False)
    pd.DataFrame([{"ticker": "NVDA", "theme": "AI", "sectoretf": "SMH", "defaultpurpose": "Momentum Leader"}]).to_csv(
        data_dir / "universe.csv",
        index=False,
    )
    pd.DataFrame([{"ticker": "NVDA", "shares": 1, "primarypurpose": "Momentum Leader"}]).to_csv(
        data_dir / "holdings.csv",
        index=False,
    )
    pd.DataFrame([{"ticker": "NVDA", "theme": "AI"}]).to_csv(data_dir / "fundamentals.csv", index=False)


def test_project_status_payload_is_read_only_and_summarizes_local_gaps(tmp_path: Path):
    _write_minimal_local_data(tmp_path)

    payload = build_project_status_payload(tmp_path, top_n=3)

    assert payload["summary"]["data_sources_total"] >= 1
    assert payload["summary"]["tickers_total"] == 1
    assert payload["summary"]["tickers_with_prices"] == 1
    assert len(payload["top_onboarding_actions"]) <= 3
    assert payload["top_onboarding_actions"][0]["focus_command"] == "make focus-price TICKER=NVDA"
    assert payload["top_onboarding_actions"][0]["example_command"] == "make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual"
    assert payload["recommended_next_command_rows"][0]["Command"] == "make focus-price TICKER=NVDA"
    assert "make runbook-prices" in payload["recommended_next_commands"]
    assert "make verify" in payload["recommended_next_commands"]
    assert not (tmp_path / "outputs" / "project_status.json").exists()


def test_project_status_prefers_live_price_status_context_for_price_actions(tmp_path: Path):
    _write_minimal_local_data(tmp_path)
    pd.DataFrame(
        [
            {
                "run_timestamp": "2026-05-21T00:00:00+00:00",
                "ticker": "NVDA",
                "requested_start": "",
                "requested_end": "2026-05-21",
                "provider": "FakePriceSource",
                "status": "parse_error",
                "rows_fetched": 0,
                "rows_merged": 0,
                "error_category": "parse_error",
                "error_message": "NVDA: parse failed",
                "fallback_used": True,
                "recommended_action": "Run make focus-price TICKER=NVDA, or run python3 -m src.data_update --tickers NVDA and normalize verified downloaded OHLCV files into data/imports/prices.csv.",
                "focus_command": "make focus-price TICKER=NVDA",
                "example_command": "make onboarding",
                "target_file": "data/imports/prices.csv",
            }
        ]
    ).to_csv(tmp_path / "outputs" / "price_update_status.csv", index=False)

    payload = build_project_status_payload(tmp_path, top_n=3)

    top_action = payload["top_onboarding_actions"][0]
    assert top_action["ticker"] == "NVDA"
    assert top_action["status"] == "parse_error"
    assert top_action["reason"] == "NVDA: parse failed"
    assert top_action["example_command"] == "make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual"
    assert payload["recommended_next_command_rows"][0]["Reason"] == "NVDA: parse failed"


def test_project_status_surfaces_staged_fundamentals_follow_through_in_next_steps(tmp_path: Path):
    _write_minimal_local_data(tmp_path)
    imports_dir = tmp_path / "data" / "imports"
    imports_dir.mkdir()
    pd.DataFrame(
        [
            {
                "ticker": "AMD",
                "theme": "AI",
                "sector": "Semis",
                "revenue": 100,
                "revenue_growth": 0.2,
                "eps": 1.0,
                "free_cash_flow": 10,
                "fcf": 10,
                "fcf_margin": 0.1,
                "profit_margin": 0.2,
                "operating_margin": 0.15,
                "gross_margin": 0.3,
                "ebitda": 15,
                "cash": 20,
                "debt": 5,
                "net_debt": -15,
                "shares_outstanding": 100,
                "pe_ratio": 25,
                "trailing_pe": 24,
                "forward_pe": 22,
                "price_to_book": 3,
                "market_cap": 1000,
                "enterprise_value": 1020,
                "debt_to_equity": 0.4,
                "source": "sec_companyfacts",
                "as_of_date": "2025-12-31",
                "sec_cik": "1",
                "sec_form": "10-K",
                "sec_filed_date": "2026-02-01",
                "sec_accession": "0001",
                "sec_fact_warnings": "",
                "sec_entity_name": "AMD INC",
            }
        ]
    ).to_csv(imports_dir / "fundamentals.csv", index=False)

    payload = build_project_status_payload(tmp_path, top_n=4)

    commands = [row["Command"] for row in payload["recommended_next_command_rows"]]
    assert "make imports-validate" in commands
    staged_row = next(row for row in payload["recommended_next_command_rows"] if row["Command"] == "make imports-validate")
    assert staged_row["Step"] == "Advance staged fundamentals import"
    assert "make imports-apply" in staged_row["Reason"]


def test_project_status_combines_staged_fundamentals_and_peer_imports_into_one_follow_through(tmp_path: Path):
    _write_minimal_local_data(tmp_path)
    imports_dir = tmp_path / "data" / "imports"
    imports_dir.mkdir()
    pd.DataFrame(
        [
            {
                "ticker": "AMD",
                "theme": "AI",
                "sector": "Semis",
                "revenue": 100,
                "revenue_growth": 0.2,
                "eps": 1.0,
                "free_cash_flow": 10,
                "fcf": 10,
                "fcf_margin": 0.1,
                "profit_margin": 0.2,
                "operating_margin": 0.15,
                "gross_margin": 0.3,
                "ebitda": 15,
                "cash": 20,
                "debt": 5,
                "net_debt": -15,
                "shares_outstanding": 100,
                "pe_ratio": 25,
                "trailing_pe": 24,
                "forward_pe": 22,
                "price_to_book": 3,
                "market_cap": 1000,
                "enterprise_value": 1020,
                "debt_to_equity": 0.4,
                "source": "sec_companyfacts",
                "as_of_date": "2025-12-31",
                "sec_cik": "1",
                "sec_form": "10-K",
                "sec_filed_date": "2026-02-01",
                "sec_accession": "0001",
                "sec_fact_warnings": "",
                "sec_entity_name": "AMD INC",
            }
        ]
    ).to_csv(imports_dir / "fundamentals.csv", index=False)
    pd.DataFrame(
        [
            {
                "ticker": "NVDA",
                "peer_ticker": "AMD",
                "peer_group": "ai_semis",
                "sector": "Semis",
                "industry": "Semiconductors",
                "source": "manual",
                "as_of_date": "2026-05-22",
            }
        ]
    ).to_csv(imports_dir / "peers.csv", index=False)

    payload = build_project_status_payload(tmp_path, top_n=4)

    staged_rows = [row for row in payload["recommended_next_command_rows"] if row["Command"] == "make imports-validate"]
    assert len(staged_rows) == 1
    staged_row = staged_rows[0]
    assert staged_row["Step"] == "Advance staged imports"
    assert "data/imports/fundamentals.csv" in staged_row["Reason"]
    assert "data/imports/peers.csv" in staged_row["Reason"]
    assert "fundamentals and peers" in staged_row["Reason"]
    assert "make imports-apply" in staged_row["Reason"]


def test_project_status_normalizes_legacy_parse_error_reason_from_price_status(tmp_path: Path):
    _write_minimal_local_data(tmp_path)
    pd.DataFrame(
        [
            {
                "run_timestamp": "2026-05-21T00:00:00+00:00",
                "ticker": "NVDA",
                "requested_start": "",
                "requested_end": "2026-05-21",
                "provider": "FakePriceSource",
                "status": "parse_error",
                "rows_fetched": 0,
                "rows_merged": 0,
                "error_category": "parse_error",
                "error_message": "NVDA: update failed (Error tokenizing data. C error: Expected 1 fields in line 6, saw 2\n)",
                "fallback_used": True,
                "recommended_action": "Retry later or use staged manual prices in data/imports/prices.csv.",
            }
        ]
    ).to_csv(tmp_path / "outputs" / "price_update_status.csv", index=False)

    payload = build_project_status_payload(tmp_path, top_n=3)

    assert payload["recommended_next_command_rows"][0]["Reason"] == "NVDA: provider rows could not be parsed cleanly (Expected 1 fields in line 6, saw 2)"


def test_project_status_write_output_persists_machine_readable_files(tmp_path: Path):
    _write_minimal_local_data(tmp_path)

    payload = write_project_status_output(tmp_path, top_n=3)
    outputs_dir = tmp_path / "outputs"

    json_path = outputs_dir / "project_status.json"
    summary_path = outputs_dir / "project_status_summary.csv"
    top_actions_path = outputs_dir / "project_status_top_actions.csv"
    next_steps_path = outputs_dir / "project_status_next_steps.csv"

    assert json_path.exists()
    assert summary_path.exists()
    assert top_actions_path.exists()
    assert next_steps_path.exists()
    assert payload["written_files"]["project_status_json"] == str(json_path)

    written_payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert written_payload["summary"]["tickers_total"] == 1

    summary_frame = pd.read_csv(summary_path)
    assert summary_frame.iloc[0]["tickers_total"] == 1

    actions_frame = pd.read_csv(top_actions_path)
    assert actions_frame.iloc[0]["focus_command"] == "make focus-price TICKER=NVDA"

    next_steps_frame = pd.read_csv(next_steps_path)
    assert next_steps_frame.iloc[0]["Command"] == "make focus-price TICKER=NVDA"


def test_project_status_human_output_surfaces_focus_and_exact_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    _write_minimal_local_data(tmp_path)

    argv_before = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--top-n", "2"]
    try:
        main()
        output = capsys.readouterr().out.lower()
    finally:
        sys.argv = argv_before

    assert "top onboarding actions" in output
    assert "command: make price-normalize input=data/raw/prices/nvda.csv ticker=nvda source=yahoo_manual" in output
    assert "focus: make focus-fundamentals ticker=nvda" in output
    assert "command: make sec-stage tickers=nvda" in output
    assert "fix top prices blocker (nvda): make focus-price ticker=nvda" in output
    assert "no verified local price history is present for this ticker yet." in output or "at least 21 are needed" in output
    assert "run price coverage bundle: make runbook-prices" in output


def test_project_status_human_write_output_reports_written_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    _write_minimal_local_data(tmp_path)

    argv_before = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--write-output", "--top-n", "2"]
    try:
        main()
        output = capsys.readouterr().out.lower()
    finally:
        sys.argv = argv_before

    assert "wrote:" in output
    assert "project_status.json" in output
    assert "project_status_summary.csv" in output


def test_project_status_refresh_artifacts_writes_supporting_operator_outputs(tmp_path: Path):
    _write_minimal_local_data(tmp_path)
    pd.DataFrame(
        [
            {
                "run_timestamp": "2026-05-21T00:00:00+00:00",
                "ticker": "AMD",
                "requested_start": "",
                "requested_end": "2026-05-21",
                "provider": "FakePriceSource",
                "status": "parse_error",
                "rows_fetched": 0,
                "rows_merged": 0,
                "error_category": "parse_error",
                "error_message": "AMD: parse failed",
                "fallback_used": True,
                "recommended_action": "Retry later or use staged manual prices in data/imports/prices.csv.",
            }
        ]
    ).to_csv(tmp_path / "outputs" / "price_update_status.csv", index=False)

    payload = write_project_status_output(tmp_path, top_n=2, refresh_supporting_outputs=True)
    outputs_dir = tmp_path / "outputs"

    assert (outputs_dir / "data_source_status.csv").exists()
    assert (outputs_dir / "data_gap_report.csv").exists()
    assert (outputs_dir / "ticker_data_coverage.csv").exists()
    assert (outputs_dir / "data_onboarding_actions.csv").exists()
    assert (outputs_dir / "data_quality_wizard.csv").exists()
    assert (outputs_dir / "liquidity_risk.csv").exists()
    assert (outputs_dir / "correlation_risk.csv").exists()
    assert (outputs_dir / "research_action_queue.csv").exists()
    assert (outputs_dir / "project_status.json").exists()
    refreshed_price_status = pd.read_csv(outputs_dir / "price_update_status.csv")
    assert refreshed_price_status.iloc[0]["focus_command"] == "make focus-price TICKER=AMD"
    assert refreshed_price_status.iloc[0]["target_file"] == "data/imports/prices.csv"
    assert payload["recommended_next_command_rows"][0]["Command"] == "make focus-price TICKER=NVDA"


def test_project_status_human_refresh_artifacts_keeps_cli_clean(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    _write_minimal_local_data(tmp_path)

    argv_before = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--refresh-artifacts", "--top-n", "2"]
    try:
        main()
        output = capsys.readouterr().out.lower()
    finally:
        sys.argv = argv_before

    assert "project status summary" in output
    assert "fix top prices blocker (nvda): make focus-price ticker=nvda" in output
    assert "wrote:" not in output
    assert (tmp_path / "outputs" / "project_status.json").exists()


def test_project_status_prefers_bundle_matching_top_blocker_ticker(tmp_path: Path):
    data_dir = tmp_path / "data"
    outputs_dir = tmp_path / "outputs"
    data_dir.mkdir()
    outputs_dir.mkdir()
    pd.DataFrame(
        [
            {
                "ticker": "NVDA",
                "date": f"2026-01-{day:02d}",
                "open": 10 + day,
                "high": 11 + day,
                "low": 9 + day,
                "close": 10 + day,
                "volume": 1000 + day,
            }
            for day in range(1, 23)
        ]
    ).to_csv(data_dir / "prices.csv", index=False)
    pd.DataFrame(
        [
            {"ticker": "NVDA", "theme": "AI", "sectoretf": "SMH", "defaultpurpose": "Momentum Leader"},
            {"ticker": "AMD", "theme": "AI", "sectoretf": "SMH", "defaultpurpose": "Momentum Leader"},
        ]
    ).to_csv(data_dir / "universe.csv", index=False)
    pd.DataFrame([{"ticker": "NVDA", "shares": 1, "primarypurpose": "Momentum Leader"}]).to_csv(
        data_dir / "holdings.csv",
        index=False,
    )
    pd.DataFrame([{"ticker": "NVDA", "theme": "AI"}]).to_csv(data_dir / "fundamentals.csv", index=False)

    payload = build_project_status_payload(tmp_path, top_n=5)

    assert payload["top_onboarding_actions"][0]["ticker"] == "AMD"
    assert payload["recommended_next_command_rows"][1]["Command"] == "make runbook-prices-broader"


def test_project_status_prefers_holdings_first_price_blockers_when_priority_matches(tmp_path: Path):
    data_dir = tmp_path / "data"
    outputs_dir = tmp_path / "outputs"
    data_dir.mkdir()
    outputs_dir.mkdir()
    pd.DataFrame(
        [
            {"ticker": "NVDA", "date": "2026-01-01", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 1000},
            {"ticker": "NVDA", "date": "2026-01-02", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 1100},
        ]
    ).to_csv(data_dir / "prices.csv", index=False)
    pd.DataFrame(
        [
            {"ticker": "META", "theme": "AI", "sectoretf": "QQQ", "defaultpurpose": "Core Compounder"},
            {"ticker": "AMD", "theme": "AI", "sectoretf": "SMH", "defaultpurpose": "Momentum Leader"},
            {"ticker": "NVDA", "theme": "AI", "sectoretf": "SMH", "defaultpurpose": "Momentum Leader"},
        ]
    ).to_csv(data_dir / "universe.csv", index=False)
    pd.DataFrame(
        [
            {"ticker": "NVDA", "shares": 1, "primarypurpose": "Momentum Leader"},
            {"ticker": "META", "shares": 1, "primarypurpose": "Core Compounder"},
        ]
    ).to_csv(data_dir / "holdings.csv", index=False)
    pd.DataFrame([{"ticker": "NVDA", "theme": "AI"}]).to_csv(data_dir / "fundamentals.csv", index=False)

    payload = build_project_status_payload(tmp_path, top_n=5)

    assert payload["top_onboarding_actions"][0]["ticker"] == "META"
    assert payload["top_onboarding_actions"][0]["focus_command"] == "make focus-price TICKER=META"
    assert payload["recommended_next_command_rows"][0]["Command"] == "make focus-price TICKER=META"
    assert payload["recommended_next_command_rows"][1]["Command"] == "make runbook-prices"
