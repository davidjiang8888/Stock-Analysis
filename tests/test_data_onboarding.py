import json
import sys
import urllib.request
from pathlib import Path

import pandas as pd

from src.data_onboarding import (
    COVERAGE_COLUMNS,
    FUNDAMENTALS_PEER_WORKLIST_COLUMNS,
    OPTIONAL_CONTEXT_WORKLIST_COLUMNS,
    PRICE_WORKLIST_COLUMNS,
    TICKER_UNLOCK_LADDER_COLUMNS,
    UNLOCK_PRIORITY_SUMMARY_COLUMNS,
    WIZARD_COLUMNS,
    build_onboarding_payload,
    build_data_coverage_wizard,
    main,
    write_onboarding_outputs,
    write_onboarding_templates,
)


def _write_fixture(root: Path) -> None:
    data_dir = root / "data"
    outputs_dir = root / "outputs"
    data_dir.mkdir()
    outputs_dir.mkdir()
    (data_dir / "prices.csv").write_text(
        "date,ticker,adj_close,volume\n"
        "2026-01-01,NVDA,100,1000\n"
        "2026-01-02,NVDA,101,1000\n"
        "2026-01-03,NVDA,102,1000\n"
        "2026-01-04,NVDA,103,1000\n"
        "2026-01-05,NVDA,104,1000\n"
        "2026-01-06,NVDA,105,1000\n"
        "2026-01-07,NVDA,106,1000\n"
        "2026-01-08,NVDA,107,1000\n"
        "2026-01-09,NVDA,108,1000\n"
        "2026-01-10,NVDA,109,1000\n"
        "2026-01-11,NVDA,110,1000\n"
        "2026-01-12,NVDA,111,1000\n"
        "2026-01-13,NVDA,112,1000\n"
        "2026-01-14,NVDA,113,1000\n"
        "2026-01-15,NVDA,114,1000\n"
        "2026-01-16,NVDA,115,1000\n"
        "2026-01-17,NVDA,116,1000\n"
        "2026-01-18,NVDA,117,1000\n"
        "2026-01-19,NVDA,118,1000\n"
        "2026-01-20,NVDA,119,1000\n"
        "2026-01-21,NVDA,120,1000\n"
        "2026-01-22,NVDA,121,1000\n"
        "2026-01-01,AMD,50,1000\n",
        encoding="utf-8",
    )
    (data_dir / "fundamentals.csv").write_text(
        "ticker,revenue,fcf_margin,shares_outstanding,eps,free_cash_flow,source,as_of_date\n"
        "NVDA,1000,0.2,10,2,200,fixture,2026-01-01\n",
        encoding="utf-8",
    )
    (data_dir / "peers.csv").write_text(
        "ticker,peer_ticker,peer_group,source,as_of_date\n"
        "NVDA,AMD,semis,fixture,2026-01-01\n",
        encoding="utf-8",
    )
    (data_dir / "earnings.csv").write_text("ticker,next_earnings_date\nNVDA,2026-02-01\n", encoding="utf-8")
    (data_dir / "universe.csv").write_text(
        "ticker,theme,sectoretf,defaultpurpose,marketcapbucket,notes\n"
        "NVDA,AI,SMH,Momentum Leader,Large,fixture\n"
        "AMD,AI,SMH,Momentum Leader,Large,fixture\n",
        encoding="utf-8",
    )
    (data_dir / "holdings.csv").write_text("ticker,primarypurpose\nNVDA,Momentum Leader\n", encoding="utf-8")
    (outputs_dir / "final_watchlist.csv").write_text("Ticker,FinalState\nNVDA,Watch\n", encoding="utf-8")
    (outputs_dir / "momentum_leaders.csv").write_text("Ticker,SetupStatus\nNVDA,Watch\n", encoding="utf-8")


def test_data_onboarding_coverage_works_with_local_fixtures(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    coverage = {row["ticker"]: row for row in payload["ticker_coverage"]}

    assert list(coverage["NVDA"].keys()) == COVERAGE_COLUMNS
    assert coverage["NVDA"]["has_prices"] is True
    assert coverage["NVDA"]["price_history_days"] == 22
    assert coverage["NVDA"]["dcf_ready"] is True
    assert coverage["AMD"]["usable_for_momentum"] is False


def test_onboarding_actions_prioritize_prices_fundamentals_peers_before_estimates(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    amd_actions = [row for row in payload["onboarding_actions"] if row["ticker"] == "AMD"]
    priorities = [row["priority"] for row in amd_actions]

    assert priorities == sorted(priorities)
    assert priorities[0] == 1
    assert any(row["dataset"] == "fundamentals" and row["priority"] == 2 for row in amd_actions)
    assert any(row["dataset"] == "peers" and row["priority"] == 3 for row in amd_actions)
    assert any(row["dataset"] == "analyst_estimates" and row["priority"] == 5 for row in amd_actions)


def test_data_coverage_wizard_ranks_core_unlocks_before_optional_context(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    amd_rows = [row for row in payload["data_coverage_wizard"] if row["ticker"] == "AMD"]
    goals = [row["unlock_goal"] for row in amd_rows]

    assert list(payload["data_coverage_wizard"][0].keys()) == WIZARD_COLUMNS
    assert amd_rows[0]["priority"] == 1
    assert "Unlock Monthly Picks" in goals
    assert "Unlock DCF" in goals
    assert "Unlock Peer Relative" in goals
    assert goals.index("Add Earnings Context") > goals.index("Unlock Peer Relative")
    assert goals.index("Add Analyst Estimate Context") > goals.index("Unlock Peer Relative")


def test_data_coverage_wizard_includes_track_record_for_short_history(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    nvda_goals = [row["unlock_goal"] for row in payload["data_coverage_wizard"] if row["ticker"] == "NVDA"]

    assert "Unlock Track Record" in nvda_goals
    assert "Unlock Monthly Picks" not in nvda_goals


def test_onboarding_missing_optional_files_do_not_crash(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "prices.csv").write_text("date,ticker,adj_close\n2026-01-01,NVDA,100\n", encoding="utf-8")
    (data_dir / "universe.csv").write_text(
        "ticker,theme,sectoretf,defaultpurpose,marketcapbucket,notes\nNVDA,AI,SMH,Momentum Leader,Large,fixture\n",
        encoding="utf-8",
    )
    (data_dir / "holdings.csv").write_text("ticker,primarypurpose\n", encoding="utf-8")

    payload = build_onboarding_payload(tmp_path)

    assert payload["ticker_coverage"][0]["ticker"] == "NVDA"
    assert any(row["dataset"] == "earnings" for row in payload["onboarding_actions"])


def test_onboarding_coverage_does_not_make_network_calls(tmp_path: Path, monkeypatch):
    _write_fixture(tmp_path)

    def fail_network(*_args, **_kwargs):
        raise AssertionError("data onboarding should inspect local CSV files only")

    monkeypatch.setattr(urllib.request, "urlopen", fail_network)

    payload = build_onboarding_payload(tmp_path)

    assert payload["ticker_coverage"]


def test_write_onboarding_outputs_and_templates(tmp_path: Path):
    _write_fixture(tmp_path)

    output_result = write_onboarding_outputs(tmp_path)
    template_result = write_onboarding_templates(tmp_path)

    assert Path(output_result["coverage_path"]).exists()
    assert Path(output_result["actions_path"]).exists()
    assert Path(output_result["wizard_path"]).exists()
    assert Path(output_result["price_worklist_path"]).exists()
    assert Path(output_result["fundamentals_peer_worklist_path"]).exists()
    assert Path(output_result["optional_context_worklist_path"]).exists()
    assert Path(output_result["ticker_unlock_ladder_path"]).exists()
    assert Path(output_result["unlock_priority_summary_path"]).exists()
    wizard_frame = pd.read_csv(output_result["wizard_path"])
    price_worklist_frame = pd.read_csv(output_result["price_worklist_path"])
    fundamentals_peer_frame = pd.read_csv(output_result["fundamentals_peer_worklist_path"])
    optional_context_frame = pd.read_csv(output_result["optional_context_worklist_path"])
    unlock_ladder_frame = pd.read_csv(output_result["ticker_unlock_ladder_path"])
    unlock_summary_frame = pd.read_csv(output_result["unlock_priority_summary_path"])
    assert list(wizard_frame.columns) == WIZARD_COLUMNS
    assert list(price_worklist_frame.columns) == PRICE_WORKLIST_COLUMNS
    assert list(fundamentals_peer_frame.columns) == FUNDAMENTALS_PEER_WORKLIST_COLUMNS
    assert list(optional_context_frame.columns) == OPTIONAL_CONTEXT_WORKLIST_COLUMNS
    assert list(unlock_ladder_frame.columns) == TICKER_UNLOCK_LADDER_COLUMNS
    assert list(unlock_summary_frame.columns) == UNLOCK_PRIORITY_SUMMARY_COLUMNS
    assert (tmp_path / "data" / "templates" / "peers.csv").exists()
    assert (tmp_path / "data" / "templates" / "prices.csv").exists()
    assert (tmp_path / "data" / "templates" / "custom_universe.csv").exists()
    assert (tmp_path / "data" / "templates" / "prices.csv").read_text(encoding="utf-8").startswith(
        "date,ticker,open,high,low,close,volume"
    )
    assert any(item["dataset_name"] == "analyst_estimates" for item in template_result)


def test_data_onboarding_cli_coverage_json(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--coverage", "--tickers", "NVDA,AMD", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
    finally:
        sys.argv = previous_argv

    assert [row["ticker"] for row in payload["ticker_coverage"]] == ["AMD", "NVDA"]


def test_data_onboarding_cli_wizard_json(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--wizard", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
    finally:
        sys.argv = previous_argv

    assert "data_coverage_wizard" in payload
    assert any(row["unlock_goal"] == "Unlock DCF" for row in payload["data_coverage_wizard"])


def test_data_onboarding_cli_price_worklist_json(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--price-worklist", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
    finally:
        sys.argv = previous_argv

    assert "price_import_worklist" in payload
    assert payload["price_import_worklist"][0]["ticker"] == "AMD"
    assert "price_history_days" in payload["price_import_worklist"][0]


def test_price_worklist_prioritizes_sparse_price_history(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    worklist = {row["ticker"]: row for row in payload["price_import_worklist"]}

    assert worklist["AMD"]["priority"] == 1
    assert worklist["AMD"]["momentum_ready"] is False
    assert "more verified rows needed" in worklist["AMD"]["missing_for_momentum"]
    assert worklist["NVDA"]["track_record_ready"] is False


def test_data_onboarding_cli_fundamentals_peer_worklist_json(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--fundamentals-peer-worklist", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
    finally:
        sys.argv = previous_argv

    assert "fundamentals_peer_worklist" in payload
    assert payload["fundamentals_peer_worklist"][0]["ticker"] == "AMD"
    assert "missing_required_for_dcf" in payload["fundamentals_peer_worklist"][0]


def test_fundamentals_peer_worklist_prioritizes_dcf_then_peer_gaps(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    worklist = {row["ticker"]: row for row in payload["fundamentals_peer_worklist"]}

    assert worklist["AMD"]["priority"] == 1
    assert worklist["AMD"]["dcf_ready"] is False
    assert "fundamentals row" in worklist["AMD"]["missing_required_for_dcf"]
    assert worklist["NVDA"]["priority"] == 2
    assert worklist["NVDA"]["dcf_ready"] is True
    assert worklist["NVDA"]["peer_ready"] is False


def test_data_onboarding_cli_optional_context_worklist_json(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--optional-context-worklist", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
    finally:
        sys.argv = previous_argv

    assert "optional_context_worklist" in payload
    assert payload["optional_context_worklist"][0]["ticker"] == "AMD"
    assert "missing_optional_context" in payload["optional_context_worklist"][0]


def test_optional_context_worklist_keeps_optional_gaps_lower_priority(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    worklist = {row["ticker"]: row for row in payload["optional_context_worklist"]}

    assert worklist["AMD"]["priority"] == 5
    assert "earnings" in worklist["AMD"]["missing_optional_context"]
    assert "analyst_estimates" in worklist["AMD"]["missing_optional_context"]
    assert worklist["NVDA"]["priority"] == 6
    assert worklist["NVDA"]["has_earnings"] is True
    assert worklist["NVDA"]["has_analyst_estimates"] is False


def test_data_onboarding_cli_unlock_ladder_json(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--unlock-ladder", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
    finally:
        sys.argv = previous_argv

    assert "ticker_unlock_ladder" in payload
    assert payload["ticker_unlock_ladder"][0]["ticker"] == "AMD"
    assert "current_unlock_stage" in payload["ticker_unlock_ladder"][0]


def test_ticker_unlock_ladder_orders_price_then_peer_then_optional(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    ladder = {row["ticker"]: row for row in payload["ticker_unlock_ladder"]}

    assert ladder["AMD"]["current_unlock_stage"] == "prices"
    assert ladder["AMD"]["next_unlock_goal"] == "Unlock Monthly Picks"
    assert ladder["NVDA"]["current_unlock_stage"] == "peers"
    assert ladder["NVDA"]["next_unlock_goal"] == "Unlock Peer Relative"


def test_data_onboarding_cli_unlock_summary_json(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--unlock-summary", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
    finally:
        sys.argv = previous_argv

    assert "unlock_priority_summary" in payload
    assert payload["unlock_priority_summary"][0]["group_type"] == "holdings"
    assert "top_priority_stage" in payload["unlock_priority_summary"][0]


def test_unlock_priority_summary_groups_holdings_themes_and_sector_etfs(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    summary = payload["unlock_priority_summary"]

    holdings_row = next(row for row in summary if row["group_type"] == "holdings")
    theme_row = next(row for row in summary if row["group_type"] == "theme" and row["group_name"] == "AI")
    sector_row = next(row for row in summary if row["group_type"] == "sector_etf" and row["group_name"] == "SMH")

    assert holdings_row["holdings_count"] == 1
    assert holdings_row["top_priority_stage"] == "peers"
    assert theme_row["ticker_count"] == 2
    assert theme_row["top_priority_stage"] == "prices"
    assert sector_row["ticker_count"] == 2


def test_build_data_coverage_wizard_accepts_empty_coverage():
    assert build_data_coverage_wizard([]) == []
