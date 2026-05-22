import json
import sys
from pathlib import Path

import pandas as pd

from src.data_sources import (
    DATA_SOURCE_REGISTRY,
    build_data_source_payload,
    main,
    write_data_source_outputs,
)


def _write_minimal_local_data(root: Path) -> None:
    data_dir = root / "data"
    outputs_dir = root / "outputs"
    data_dir.mkdir()
    outputs_dir.mkdir()
    (data_dir / "prices.csv").write_text(
        "date,ticker,adj_close,volume\n"
        "2026-01-02,NVDA,100,1000\n",
        encoding="utf-8",
    )
    (data_dir / "fundamentals.csv").write_text(
        "ticker,theme,sector,pe_ratio,revenue_growth,profit_margin,debt_to_equity\n"
        "NVDA,AI,Semis,30,0.2,0.3,0.4\n",
        encoding="utf-8",
    )
    (data_dir / "universe.csv").write_text(
        "ticker,theme,sectoretf,defaultpurpose,marketcapbucket,notes\n"
        "NVDA,AI,SMH,Momentum Leader,Large,fixture\n"
        "MSFT,Software,QQQ,Core Compounder,Large,fixture\n",
        encoding="utf-8",
    )
    (data_dir / "holdings.csv").write_text(
        "ticker,primarypurpose\n"
        "NVDA,Momentum Leader\n",
        encoding="utf-8",
    )


def test_data_source_registry_contains_required_datasets():
    datasets = {entry.dataset for entry in DATA_SOURCE_REGISTRY}

    assert {
        "prices",
        "fundamentals",
        "peers",
        "earnings",
        "analyst_estimates",
        "universe",
        "smh_holdings",
        "sp500_constituents",
        "nasdaq_symbols",
        "local_outputs",
    }.issubset(datasets)

    prices_entry = next(entry for entry in DATA_SOURCE_REGISTRY if entry.dataset == "prices")
    assert "make status" in prices_entry.fallback_action
    assert "validate/preview/apply" in prices_entry.fallback_action
    fundamentals_entry = next(entry for entry in DATA_SOURCE_REGISTRY if entry.dataset == "fundamentals")
    assert "make status" in fundamentals_entry.fallback_action
    assert "runbook path" in fundamentals_entry.fallback_action
    peers_entry = next(entry for entry in DATA_SOURCE_REGISTRY if entry.dataset == "peers")
    assert "make templates" in peers_entry.fallback_action
    assert "make status" in peers_entry.fallback_action
    earnings_entry = next(entry for entry in DATA_SOURCE_REGISTRY if entry.dataset == "earnings")
    assert "make templates" in earnings_entry.fallback_action
    analyst_entry = next(entry for entry in DATA_SOURCE_REGISTRY if entry.dataset == "analyst_estimates")
    assert "make templates" in analyst_entry.fallback_action
    smh_entry = next(entry for entry in DATA_SOURCE_REGISTRY if entry.dataset == "smh_holdings")
    assert "make templates" in smh_entry.fallback_action
    assert "data/custom_universe.csv" in smh_entry.fallback_action
    universe_entry = next(entry for entry in DATA_SOURCE_REGISTRY if entry.dataset == "universe")
    assert "make universe-preview" in universe_entry.fallback_action
    sp500_entry = next(entry for entry in DATA_SOURCE_REGISTRY if entry.dataset == "sp500_constituents")
    assert "make universe-preview" in sp500_entry.fallback_action
    nasdaq_entry = next(entry for entry in DATA_SOURCE_REGISTRY if entry.dataset == "nasdaq_symbols")
    assert "make universe-preview" in nasdaq_entry.fallback_action
    local_outputs_entry = next(entry for entry in DATA_SOURCE_REGISTRY if entry.dataset == "local_outputs")
    assert "make verify" in local_outputs_entry.fallback_action


def test_data_source_check_handles_missing_optional_files_without_network(tmp_path: Path):
    _write_minimal_local_data(tmp_path)

    payload = build_data_source_payload(tmp_path)
    statuses = {row["dataset"]: row["availability_status"] for row in payload["data_sources"]}
    source_lookup = {row["dataset"]: row for row in payload["data_sources"]}

    assert statuses["prices"] == "available"
    assert statuses["peers"] == "manual_only"
    assert statuses["earnings"] == "manual_only"
    assert statuses["analyst_estimates"] == "manual_only"
    assert source_lookup["fundamentals"]["focus_command"] == "make status"
    assert source_lookup["fundamentals"]["example_command"] == "make runbook-fundamentals-broader"
    assert source_lookup["fundamentals"]["target_file"] == "data/imports/fundamentals.csv"
    assert source_lookup["smh_holdings"]["focus_command"] == "make templates"
    assert source_lookup["smh_holdings"]["target_file"] == "data/custom_universe.csv"
    assert source_lookup["sp500_constituents"]["focus_command"] == "make universe-preview"
    assert source_lookup["sp500_constituents"]["target_file"] == "data/imports/universe.csv"
    assert "make universe-preview" in source_lookup["sp500_constituents"]["fallback_action"]
    assert "make universe-preview" in source_lookup["nasdaq_symbols"]["fallback_action"]
    assert any(gap["dataset"] == "prices" and gap["ticker"] == "MSFT" for gap in payload["data_gaps"])
    gap_lookup = {gap["dataset"]: gap for gap in payload["data_gaps"] if not gap["ticker"]}
    assert "make verify" in gap_lookup["local_outputs"]["recommended_action"]
    assert gap_lookup["local_outputs"]["focus_command"] == "make status"
    assert gap_lookup["local_outputs"]["example_command"] == "make status"
    assert gap_lookup["local_outputs"]["target_file"] == "outputs/"
    assert "make status" in gap_lookup["fundamentals"]["recommended_action"]
    assert gap_lookup["fundamentals"]["focus_command"] == "make status"
    assert gap_lookup["fundamentals"]["example_command"] == "make runbook-fundamentals-broader"
    assert gap_lookup["fundamentals"]["target_file"] == "data/imports/fundamentals.csv"
    assert gap_lookup["peers"]["target_file"] == "data/imports/peers.csv"
    assert "make templates" in gap_lookup["peers"]["recommended_action"]
    assert gap_lookup["peers"]["focus_command"] == "make status"
    assert gap_lookup["peers"]["example_command"] == "make runbook-peers-broader"
    assert "make templates" in gap_lookup["earnings"]["recommended_action"]
    assert gap_lookup["earnings"]["focus_command"] == "make templates"
    assert gap_lookup["earnings"]["example_command"] == "make templates"
    assert gap_lookup["earnings"]["target_file"] == "data/imports/earnings.csv"
    assert "make templates" in gap_lookup["analyst_estimates"]["recommended_action"]
    assert gap_lookup["analyst_estimates"]["focus_command"] == "make templates"
    assert gap_lookup["analyst_estimates"]["example_command"] == "make templates"
    price_gap = next(gap for gap in payload["data_gaps"] if gap["dataset"] == "prices" and gap["ticker"] == "MSFT")
    assert price_gap["recommended_action"] == (
        "Run make focus-price TICKER=MSFT, or run python3 -m src.data_update "
        "--tickers MSFT and normalize verified downloaded OHLCV files into "
        "data/imports/prices.csv."
    )
    assert price_gap["focus_command"] == "make focus-price TICKER=MSFT"
    assert price_gap["example_command"] == "make price-normalize INPUT=data/raw/prices/MSFT.csv TICKER=MSFT SOURCE=yahoo_manual"
    assert price_gap["target_file"] == "data/imports/prices.csv"
    fundamentals_gap = next(gap for gap in payload["data_gaps"] if gap["dataset"] == "fundamentals" and gap["ticker"] == "MSFT")
    assert fundamentals_gap["recommended_action"] == (
        "Run make focus-fundamentals TICKER=MSFT, or stage explicit local "
        "fundamentals with python3 -m src.stock_report --sec-stage-fundamentals "
        "--tickers MSFT."
    )
    assert fundamentals_gap["focus_command"] == "make focus-fundamentals TICKER=MSFT"
    assert fundamentals_gap["example_command"] == "python3 -m src.stock_report --sec-stage-fundamentals --tickers MSFT"
    assert fundamentals_gap["target_file"] == "data/imports/fundamentals.csv"


def test_write_data_source_outputs_creates_csvs(tmp_path: Path):
    _write_minimal_local_data(tmp_path)

    result = write_data_source_outputs(tmp_path)

    status_path = Path(result["status_path"])
    gap_path = Path(result["gap_report_path"])
    assert status_path.exists()
    assert gap_path.exists()
    assert "dataset" in pd.read_csv(status_path).columns
    assert "target_file" in pd.read_csv(status_path).columns
    assert "focus_command" in pd.read_csv(status_path).columns
    assert "example_command" in pd.read_csv(status_path).columns
    assert "recommended_action" in pd.read_csv(gap_path).columns
    assert "target_file" in pd.read_csv(gap_path).columns
    assert "focus_command" in pd.read_csv(gap_path).columns
    assert "example_command" in pd.read_csv(gap_path).columns


def test_missing_universe_gap_uses_preview_first_flow(tmp_path: Path):
    data_dir = tmp_path / "data"
    outputs_dir = tmp_path / "outputs"
    data_dir.mkdir()
    outputs_dir.mkdir()
    (data_dir / "holdings.csv").write_text(
        "ticker,primarypurpose\n"
        "NVDA,Momentum Leader\n",
        encoding="utf-8",
    )

    payload = build_data_source_payload(tmp_path)

    universe_status = next(row for row in payload["data_sources"] if row["dataset"] == "universe")
    assert universe_status["availability_status"] == "missing_file"
    assert "make universe-preview" in universe_status["fallback_action"]
    universe_gap = next(gap for gap in payload["data_gaps"] if gap["dataset"] == "universe" and not gap["ticker"])
    assert "make universe-preview" in universe_gap["recommended_action"]
    assert universe_gap["focus_command"] == "make universe-preview"
    assert universe_gap["example_command"] == "make universe-preview"
    assert universe_gap["target_file"] == "data/imports/universe.csv"


def test_staged_peer_import_changes_data_source_status_and_gap_flow(tmp_path: Path):
    data_dir = tmp_path / "data"
    outputs_dir = tmp_path / "outputs"
    imports_dir = data_dir / "imports"
    data_dir.mkdir()
    outputs_dir.mkdir()
    imports_dir.mkdir()
    (data_dir / "prices.csv").write_text(
        "date,ticker,adj_close,volume\n"
        "2026-01-02,NVDA,100,1000\n",
        encoding="utf-8",
    )
    (data_dir / "fundamentals.csv").write_text(
        "ticker,theme,sector,pe_ratio,revenue_growth,profit_margin,debt_to_equity\n"
        "NVDA,AI,Semis,30,0.2,0.3,0.4\n",
        encoding="utf-8",
    )
    (data_dir / "universe.csv").write_text(
        "ticker,theme,sectoretf,defaultpurpose,marketcapbucket,notes\n"
        "NVDA,AI,SMH,Momentum Leader,Large,fixture\n",
        encoding="utf-8",
    )
    (data_dir / "holdings.csv").write_text(
        "ticker,primarypurpose\n"
        "NVDA,Momentum Leader\n",
        encoding="utf-8",
    )
    (imports_dir / "peers.csv").write_text(
        "ticker,peer_ticker,peer_group,source,as_of_date\n"
        "NVDA,AMD,ai_semis,manual,2026-05-22\n",
        encoding="utf-8",
    )

    payload = build_data_source_payload(tmp_path)

    peers_status = next(row for row in payload["data_sources"] if row["dataset"] == "peers")
    assert peers_status["availability_status"] == "partial"
    assert peers_status["local_file"] == "data/imports/peers.csv"
    assert peers_status["row_count"] == 1
    assert peers_status["focus_command"] == "make imports-validate"
    assert peers_status["example_command"] == "make imports-preview"
    assert "make imports-apply" in peers_status["fallback_action"]
    peers_gap = next(gap for gap in payload["data_gaps"] if gap["dataset"] == "peers" and not gap["ticker"])
    assert peers_gap["status"] == "partial"
    assert peers_gap["focus_command"] == "make imports-validate"
    assert peers_gap["example_command"] == "make imports-preview"
    assert "make imports-apply" in peers_gap["recommended_action"]
    assert peers_gap["local_file"] == "data/imports/peers.csv"


def test_staged_fundamentals_import_changes_data_source_status_and_gap_flow(tmp_path: Path):
    data_dir = tmp_path / "data"
    outputs_dir = tmp_path / "outputs"
    imports_dir = data_dir / "imports"
    data_dir.mkdir()
    outputs_dir.mkdir()
    imports_dir.mkdir()
    (data_dir / "prices.csv").write_text(
        "date,ticker,adj_close,volume\n"
        "2026-01-02,NVDA,100,1000\n",
        encoding="utf-8",
    )
    (data_dir / "fundamentals.csv").write_text(
        "ticker,theme,sector,pe_ratio,revenue_growth,profit_margin,debt_to_equity\n"
        "NVDA,AI,Semis,30,0.2,0.3,0.4\n",
        encoding="utf-8",
    )
    (data_dir / "universe.csv").write_text(
        "ticker,theme,sectoretf,defaultpurpose,marketcapbucket,notes\n"
        "NVDA,AI,SMH,Momentum Leader,Large,fixture\n",
        encoding="utf-8",
    )
    (data_dir / "holdings.csv").write_text(
        "ticker,primarypurpose\n"
        "NVDA,Momentum Leader\n",
        encoding="utf-8",
    )
    (imports_dir / "fundamentals.csv").write_text(
        "ticker,theme,sector,revenue,revenue_growth,eps,free_cash_flow,fcf,fcf_margin,profit_margin,operating_margin,gross_margin,ebitda,cash,debt,net_debt,shares_outstanding,pe_ratio,trailing_pe,forward_pe,price_to_book,market_cap,enterprise_value,debt_to_equity,source,as_of_date,sec_cik,sec_form,sec_filed_date,sec_accession,sec_fact_warnings,sec_entity_name\n"
        "AMD,AI,Semis,100,0.2,1.0,10,10,0.1,0.2,0.15,0.3,15,20,5,-15,100,25,24,22,3,1000,1020,0.4,sec_companyfacts,2025-12-31,1,10-K,2026-02-01,0001,,AMD INC\n",
        encoding="utf-8",
    )

    payload = build_data_source_payload(tmp_path)

    fundamentals_status = next(row for row in payload["data_sources"] if row["dataset"] == "fundamentals")
    assert fundamentals_status["availability_status"] == "available" or fundamentals_status["availability_status"] == "partial"
    assert fundamentals_status["focus_command"] == "make imports-validate"
    assert fundamentals_status["example_command"] == "make imports-preview"
    assert "data/imports/fundamentals.csv" in fundamentals_status["notes"]
    assert "make imports-apply" in fundamentals_status["fallback_action"]
    fundamentals_gap = next(gap for gap in payload["data_gaps"] if gap["dataset"] == "fundamentals" and not gap["ticker"])
    assert fundamentals_gap["focus_command"] == "make imports-validate"
    assert fundamentals_gap["example_command"] == "make imports-preview"
    assert "make imports-apply" in fundamentals_gap["recommended_action"]
    assert "data/imports/fundamentals.csv" in fundamentals_gap["reason"]


def test_data_sources_cli_check_json(tmp_path: Path, capsys):
    _write_minimal_local_data(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--check", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
    finally:
        sys.argv = previous_argv

    assert "data_sources" in payload
    assert "data_gaps" in payload
    assert "target_file" in payload["data_sources"][0]
    assert "focus_command" in payload["data_sources"][0]
    assert "example_command" in payload["data_sources"][0]
    assert "target_file" in payload["data_gaps"][0]
    assert "focus_command" in payload["data_gaps"][0]
    assert "example_command" in payload["data_gaps"][0]
