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
    assert any(gap["dataset"] == "prices" and gap["ticker"] == "MSFT" for gap in payload["data_gaps"])
    gap_lookup = {gap["dataset"]: gap for gap in payload["data_gaps"] if not gap["ticker"]}
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
