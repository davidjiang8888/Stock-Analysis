import json
import sys
import urllib.request
from pathlib import Path

import pandas as pd

from src.data_onboarding import (
    COMMAND_BUNDLE_COLUMNS,
    COMMAND_BUNDLE_DETAIL_COLUMNS,
    COMMAND_BUNDLE_RUNBOOK_COLUMNS,
    COVERAGE_COLUMNS,
    FUNDAMENTALS_PEER_WORKLIST_COLUMNS,
    OPTIONAL_CONTEXT_WORKLIST_COLUMNS,
    PEER_MAPPING_QUEUE_COLUMNS,
    PRICE_WORKLIST_COLUMNS,
    SEC_STAGE_QUEUE_COLUMNS,
    TICKER_UNLOCK_LADDER_COLUMNS,
    UNLOCK_PRIORITY_SUMMARY_COLUMNS,
    WIZARD_COLUMNS,
    TickerCoverage,
    build_onboarding_actions,
    build_onboarding_payload,
    build_data_coverage_wizard,
    build_optional_context_worklist,
    build_ticker_unlock_ladder,
    build_unlock_priority_summary,
    build_ticker_coverage,
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
    assert coverage["AMD"]["next_best_action"] == (
        "Run make focus-price TICKER=AMD, or run make price-refresh TICKERS=AMD; "
        "if the free refresh path fails, normalize verified downloaded OHLCV files into data/imports/prices.csv."
    )
    assert "make focus-fundamentals TICKER=AMD" in coverage["NVDA"]["next_best_action"]
    assert "peer-relative context" in coverage["NVDA"]["next_best_action"]


def test_onboarding_actions_prioritize_prices_fundamentals_peers_before_estimates(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    amd_actions = [row for row in payload["onboarding_actions"] if row["ticker"] == "AMD"]
    priorities = [row["priority"] for row in amd_actions]

    assert priorities == sorted(priorities)
    assert priorities[0] == 1
    assert any(row["dataset"] == "prices" and row["focus_command"] == "make focus-price TICKER=AMD" for row in amd_actions)
    assert any(
        row["dataset"] == "prices"
        and (
            "no verified local price history is present" in row["reason"].lower()
            or "at least 21 are needed" in row["reason"].lower()
        )
        for row in amd_actions
    )
    assert any(
        row["dataset"] == "prices"
        and row["recommended_action"] == (
            "Run make focus-price TICKER=AMD, or run make price-refresh TICKERS=AMD; "
            "if the free refresh path fails, normalize verified downloaded OHLCV files into data/imports/prices.csv."
        )
        for row in amd_actions
    )
    assert any(
        row["dataset"] == "prices"
        and row["example_command"] == "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual"
        for row in amd_actions
    )
    assert any(row["dataset"] == "fundamentals" and row["priority"] == 2 for row in amd_actions)
    assert any(row["dataset"] == "fundamentals" and row["focus_command"] == "make focus-fundamentals TICKER=AMD" for row in amd_actions)
    assert any(row["dataset"] == "fundamentals" and "make focus-fundamentals TICKER=AMD" in row["recommended_action"] for row in amd_actions)
    assert any(row["dataset"] == "peers" and row["priority"] == 3 for row in amd_actions)
    assert any(row["dataset"] == "peers" and row["focus_command"] == "make focus-peers TICKER=AMD" for row in amd_actions)
    assert any(row["dataset"] == "peers" and "make focus-peers TICKER=AMD" in row["recommended_action"] for row in amd_actions)
    assert any(row["dataset"] == "earnings" and row["focus_command"] == "make templates" for row in amd_actions)
    assert any(row["dataset"] == "analyst_estimates" and row["focus_command"] == "make templates" for row in amd_actions)
    assert any(row["dataset"] == "analyst_estimates" and row["priority"] == 5 for row in amd_actions)
    smh_action = next(row for row in payload["onboarding_actions"] if row["dataset"] == "smh_holdings")
    assert smh_action["focus_command"] == "make templates"
    assert smh_action["example_command"] == "make templates"
    assert "data/custom_universe.csv" in smh_action["recommended_action"]
    assert "make templates" in smh_action["recommended_action"]


def test_build_ticker_coverage_surfaces_operator_commands(tmp_path: Path):
    _write_fixture(tmp_path)

    coverage = build_ticker_coverage(tmp_path)
    amd = next(row.to_dict() for row in coverage if row.ticker == "AMD")
    nvda = next(row.to_dict() for row in coverage if row.ticker == "NVDA")

    assert list(amd.keys()) == COVERAGE_COLUMNS
    assert amd["focus_command"] == "make focus-price TICKER=AMD"
    assert amd["target_file"] == "data/imports/prices.csv"
    assert "make price-normalize" in amd["example_command"]
    assert nvda["focus_command"] == "make focus-fundamentals TICKER=AMD"
    assert nvda["target_file"] == "data/imports/fundamentals.csv"
    assert nvda["example_command"] == "make sec-stage TICKERS=AMD"
    assert "missing peer fundamentals needed for NVDA" in nvda["next_best_action"]
    assert "If SEC_USER_AGENT is configured" in nvda["next_best_action"]
    assert "stage trusted manual fundamentals" in nvda["next_best_action"]


def test_staged_peer_imports_surface_validate_flow_in_coverage_and_wizard(tmp_path: Path):
    _write_fixture(tmp_path)
    (tmp_path / "data" / "peers.csv").unlink()
    imports_dir = tmp_path / "data" / "imports"
    imports_dir.mkdir()
    (imports_dir / "peers.csv").write_text(
        "ticker,peer_ticker,peer_group,source,as_of_date\n"
        "NVDA,AMD,semis,manual,2026-01-02\n",
        encoding="utf-8",
    )

    payload = build_onboarding_payload(tmp_path)
    coverage = {row["ticker"]: row for row in payload["ticker_coverage"]}
    peer_actions = {
        row["ticker"]: row
        for row in payload["onboarding_actions"]
        if row["dataset"] == "peers"
    }
    peer_wizard_rows = [
        row for row in payload["data_coverage_wizard"] if row["ticker"] == "NVDA" and row["blocking_dataset"] == "peers"
    ]

    nvda = coverage["NVDA"]
    assert nvda["has_peer_mapping"] is True
    assert nvda["peer_ready"] is False
    assert nvda["focus_command"] == "make imports-validate"
    assert nvda["example_command"] == "make imports-preview"
    assert nvda["target_file"] == "data/imports/peers.csv"
    assert "make imports-apply" in nvda["next_best_action"]
    assert "make imports-validate" in nvda["missing_required_for_peer_relative"]
    assert "make imports-preview" in nvda["missing_required_for_peer_relative"]
    assert "make imports-apply" in nvda["missing_required_for_peer_relative"]

    nvda_peer_action = peer_actions["NVDA"]
    assert nvda_peer_action["focus_command"] == "make imports-validate"
    assert nvda_peer_action["example_command"] == "make imports-preview"
    assert "staged peer mappings are present" in nvda_peer_action["reason"].lower()

    assert peer_wizard_rows
    assert peer_wizard_rows[0]["focus_command"] == "make imports-validate"
    assert peer_wizard_rows[0]["example_command"] == "make imports-preview"
    assert "make imports-apply" in peer_wizard_rows[0]["recommended_action"]


def test_staged_fundamentals_surface_validate_flow_in_coverage_and_wizard(tmp_path: Path):
    data_dir = tmp_path / "data"
    outputs_dir = tmp_path / "outputs"
    imports_dir = data_dir / "imports"
    data_dir.mkdir()
    outputs_dir.mkdir()
    imports_dir.mkdir()
    (data_dir / "prices.csv").write_text(
        "date,ticker,adj_close,volume\n"
        "2026-01-01,AMD,100,1000\n"
        "2026-01-02,AMD,101,1000\n"
        "2026-01-03,AMD,102,1000\n"
        "2026-01-04,AMD,103,1000\n"
        "2026-01-05,AMD,104,1000\n"
        "2026-01-06,AMD,105,1000\n"
        "2026-01-07,AMD,106,1000\n"
        "2026-01-08,AMD,107,1000\n"
        "2026-01-09,AMD,108,1000\n"
        "2026-01-10,AMD,109,1000\n"
        "2026-01-11,AMD,110,1000\n"
        "2026-01-12,AMD,111,1000\n"
        "2026-01-13,AMD,112,1000\n"
        "2026-01-14,AMD,113,1000\n"
        "2026-01-15,AMD,114,1000\n"
        "2026-01-16,AMD,115,1000\n"
        "2026-01-17,AMD,116,1000\n"
        "2026-01-18,AMD,117,1000\n"
        "2026-01-19,AMD,118,1000\n"
        "2026-01-20,AMD,119,1000\n"
        "2026-01-21,AMD,120,1000\n"
        "2026-01-22,AMD,121,1000\n",
        encoding="utf-8",
    )
    (data_dir / "fundamentals.csv").write_text(
        "ticker,revenue,source,as_of_date\n"
        "AMD,1000,fixture,2026-01-01\n",
        encoding="utf-8",
    )
    (imports_dir / "fundamentals.csv").write_text(
        "ticker,revenue,free_cash_flow,fcf_margin,shares_outstanding,source,as_of_date\n"
        "AMD,1000,200,0.2,10,sec_companyfacts,2026-01-02\n",
        encoding="utf-8",
    )
    (data_dir / "universe.csv").write_text(
        "ticker,theme,sectoretf,defaultpurpose,marketcapbucket,notes\n"
        "AMD,AI,SMH,Momentum Leader,Large,fixture\n",
        encoding="utf-8",
    )
    (outputs_dir / "final_watchlist.csv").write_text("Ticker,FinalState\nAMD,Watch\n", encoding="utf-8")
    (outputs_dir / "momentum_leaders.csv").write_text("Ticker,SetupStatus\nAMD,Watch\n", encoding="utf-8")

    payload = build_onboarding_payload(tmp_path)
    coverage = {row["ticker"]: row for row in payload["ticker_coverage"]}
    fundamentals_actions = {
        row["ticker"]: row
        for row in payload["onboarding_actions"]
        if row["dataset"] == "fundamentals"
    }
    fundamentals_wizard_rows = [
        row for row in payload["data_coverage_wizard"] if row["ticker"] == "AMD" and row["blocking_dataset"] == "fundamentals"
    ]
    fundamentals_worklist = {row["ticker"]: row for row in payload["fundamentals_peer_worklist"]}
    sec_queue = {row["ticker"]: row for row in payload["sec_stage_queue"]}
    unlock_rows = {row["ticker"]: row for row in payload["ticker_unlock_ladder"]}

    amd = coverage["AMD"]
    assert amd["dcf_ready"] is False
    assert amd["focus_command"] == "make imports-validate"
    assert amd["example_command"] == "make imports-preview"
    assert amd["target_file"] == "data/imports/fundamentals.csv"
    assert "make imports-apply" in amd["next_best_action"]
    assert "make imports-validate" in amd["missing_required_for_dcf"]
    assert "make imports-preview" in amd["missing_required_for_dcf"]
    assert "make imports-apply" in amd["missing_required_for_dcf"]

    amd_action = fundamentals_actions["AMD"]
    assert amd_action["focus_command"] == "make imports-validate"
    assert amd_action["example_command"] == "make imports-preview"
    assert "staged fundamentals" in amd_action["reason"].lower()

    assert fundamentals_wizard_rows
    assert fundamentals_wizard_rows[0]["focus_command"] == "make imports-validate"
    assert fundamentals_wizard_rows[0]["example_command"] == "make imports-preview"
    assert "make imports-apply" in fundamentals_wizard_rows[0]["recommended_action"]

    assert fundamentals_worklist["AMD"]["focus_command"] == "make imports-validate"
    assert fundamentals_worklist["AMD"]["example_command"] == "make imports-preview"
    assert sec_queue["AMD"]["focus_command"] == "make imports-validate"
    assert sec_queue["AMD"]["example_command"] == "make imports-preview"
    assert unlock_rows["AMD"]["focus_command"] == "make imports-validate"
    assert unlock_rows["AMD"]["example_command"] == "make imports-preview"


def test_data_coverage_wizard_normalizes_stale_peer_example_commands():
    coverage = [
        TickerCoverage(
            ticker="NVDA",
            has_prices=True,
            price_history_days=80,
            has_fundamentals=True,
            dcf_ready=True,
            has_peer_mapping=True,
            peer_ready=False,
            has_earnings=False,
            has_analyst_estimates=False,
            usable_for_momentum=True,
            usable_for_monthly_picks=True,
            usable_for_dcf=True,
            usable_for_peer_relative=False,
            missing_required_for_momentum="",
            missing_required_for_dcf="",
            missing_required_for_peer_relative="validate/preview/apply pending",
            next_best_action=(
                "Run make imports-validate, then make imports-preview, then make imports-apply, then make status "
                "to confirm the live local peer mappings."
            ),
            target_file="data/imports/peers.csv",
            focus_command="make imports-validate",
            example_command="make status",
        ),
        TickerCoverage(
            ticker="AMD",
            has_prices=True,
            price_history_days=80,
            has_fundamentals=True,
            dcf_ready=True,
            has_peer_mapping=True,
            peer_ready=False,
            has_earnings=False,
            has_analyst_estimates=False,
            usable_for_momentum=True,
            usable_for_monthly_picks=True,
            usable_for_dcf=True,
            usable_for_peer_relative=False,
            missing_required_for_momentum="",
            missing_required_for_dcf="",
            missing_required_for_peer_relative="peer support data incomplete",
            next_best_action=(
                "Run make focus-peers TICKER=AMD, then add peer fundamentals/prices through the staged local import "
                "workflows so peer-relative valuation can calculate transparently."
            ),
            target_file="data/imports/fundamentals.csv, data/imports/prices.csv",
            focus_command="make focus-peers TICKER=AMD",
            example_command="make onboarding",
        ),
    ]

    rows = build_data_coverage_wizard(coverage)
    nvda_peer_row = next(row for row in rows if row.ticker == "NVDA" and row.blocking_dataset == "peers")
    amd_peer_row = next(row for row in rows if row.ticker == "AMD" and row.blocking_dataset == "peers")

    assert nvda_peer_row.focus_command == "make imports-validate"
    assert nvda_peer_row.example_command == "make imports-preview"
    assert amd_peer_row.focus_command == "make focus-peers TICKER=AMD"
    assert amd_peer_row.example_command == "make templates"


def test_data_coverage_wizard_normalizes_legacy_operator_example_commands():
    coverage = [
        TickerCoverage(
            ticker="NVDA",
            has_prices=True,
            price_history_days=80,
            has_fundamentals=False,
            dcf_ready=False,
            has_peer_mapping=False,
            peer_ready=False,
            has_earnings=False,
            has_analyst_estimates=False,
            usable_for_momentum=True,
            usable_for_monthly_picks=True,
            usable_for_dcf=False,
            usable_for_peer_relative=False,
            missing_required_for_momentum="",
            missing_required_for_dcf="free_cash_flow",
            missing_required_for_peer_relative="peer mapping",
            next_best_action="Run make focus-fundamentals TICKER=NVDA.",
            target_file="data/imports/fundamentals.csv",
            focus_command="make focus-fundamentals TICKER=NVDA",
            example_command="SEC_USER_AGENT='Name email@example.com' make sec-stage TICKERS=nvda, msft",
        ),
        TickerCoverage(
            ticker="AMD",
            has_prices=False,
            price_history_days=0,
            has_fundamentals=False,
            dcf_ready=False,
            has_peer_mapping=False,
            peer_ready=False,
            has_earnings=False,
            has_analyst_estimates=False,
            usable_for_momentum=False,
            usable_for_monthly_picks=False,
            usable_for_dcf=False,
            usable_for_peer_relative=False,
            missing_required_for_momentum="prices",
            missing_required_for_dcf="prices",
            missing_required_for_peer_relative="prices",
            next_best_action="Run make focus-price TICKER=AMD.",
            target_file="data/imports/prices.csv",
            focus_command="make focus-price TICKER=AMD",
            example_command="python3 -m src.data_update --tickers amd, nvda",
        ),
    ]

    rows = build_data_coverage_wizard(coverage)
    nvda_row = next(row for row in rows if row.ticker == "NVDA")
    amd_row = next(row for row in rows if row.ticker == "AMD")

    assert nvda_row.example_command == "make sec-stage TICKERS=NVDA"
    assert amd_row.example_command == "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual"
    assert "make price-validate" in amd_row.safe_next_step
    assert "make price-preview" in amd_row.safe_next_step
    assert "make price-apply" in amd_row.safe_next_step


def test_data_coverage_wizard_normalizes_stale_action_text():
    coverage = [
        TickerCoverage(
            ticker="NVDA",
            has_prices=True,
            price_history_days=80,
            has_fundamentals=False,
            dcf_ready=False,
            has_peer_mapping=False,
            peer_ready=False,
            has_earnings=False,
            has_analyst_estimates=False,
            usable_for_momentum=True,
            usable_for_monthly_picks=True,
            usable_for_dcf=False,
            usable_for_peer_relative=False,
            missing_required_for_momentum="",
            missing_required_for_dcf="free_cash_flow",
            missing_required_for_peer_relative="peer mapping",
            next_best_action="Run make focus-fundamentals TICKER=NVDA.",
            target_file="data/imports/fundamentals.csv",
            focus_command="make focus-fundamentals TICKER=NVDA",
            example_command="make sec-stage TICKERS=NVDA",
        ),
        TickerCoverage(
            ticker="AMD",
            has_prices=False,
            price_history_days=0,
            has_fundamentals=False,
            dcf_ready=False,
            has_peer_mapping=False,
            peer_ready=False,
            has_earnings=False,
            has_analyst_estimates=False,
            usable_for_momentum=False,
            usable_for_monthly_picks=False,
            usable_for_dcf=False,
            usable_for_peer_relative=False,
            missing_required_for_momentum="prices",
            missing_required_for_dcf="prices",
            missing_required_for_peer_relative="prices",
            next_best_action="Run make focus-price TICKER=AMD, or run python3 -m src.data_update --tickers AMD and normalize verified downloaded OHLCV files into data/imports/prices.csv.",
            target_file="data/imports/prices.csv",
            focus_command="make focus-price TICKER=AMD",
            example_command="make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
        ),
        TickerCoverage(
            ticker="TSLA",
            has_prices=True,
            price_history_days=90,
            has_fundamentals=True,
            dcf_ready=True,
            has_peer_mapping=False,
            peer_ready=False,
            has_earnings=False,
            has_analyst_estimates=False,
            usable_for_momentum=True,
            usable_for_monthly_picks=True,
            usable_for_dcf=True,
            usable_for_peer_relative=False,
            missing_required_for_momentum="",
            missing_required_for_dcf="",
            missing_required_for_peer_relative="peer mapping",
            next_best_action="Run make focus-peers TICKER=TSLA.",
            target_file="data/imports/peers.csv",
            focus_command="make focus-peers TICKER=TSLA",
            example_command="make templates",
        ),
    ]

    rows = build_data_coverage_wizard(coverage)
    nvda_row = next(row for row in rows if row.ticker == "NVDA")
    amd_row = next(row for row in rows if row.ticker == "AMD")
    tsla_row = next(row for row in rows if row.ticker == "TSLA")

    assert "make sec-stage TICKERS=NVDA" in nvda_row.recommended_action
    assert "make price-refresh TICKERS=AMD" in amd_row.recommended_action
    assert "python3 -m src.data_update --tickers AMD" not in amd_row.recommended_action
    assert "run make templates" in tsla_row.recommended_action


def test_optional_context_worklist_surfaces_template_focus_command(tmp_path: Path):
    _write_fixture(tmp_path)

    coverage = build_ticker_coverage(tmp_path)
    worklist = build_optional_context_worklist(coverage)
    amd = next(row.to_dict() for row in worklist if row.ticker == "AMD")

    assert amd["focus_command"] == "make templates"
    assert amd["example_command"] == "make templates"
    assert "data/imports/earnings.csv" in amd["target_file"]


def test_build_onboarding_actions_uses_normalize_first_price_workflow(tmp_path: Path):
    _write_fixture(tmp_path)

    coverage = build_ticker_coverage(tmp_path)
    actions = build_onboarding_actions(coverage)
    amd_price_action = next(action for action in actions if action.ticker == "AMD" and action.dataset == "prices")

    assert "normalize verified downloaded OHLCV files into data/imports/prices.csv" in amd_price_action.recommended_action
    assert amd_price_action.example_command == "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual"


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
    assert any(row["focus_command"] == "make focus-price TICKER=AMD" for row in amd_rows if row["blocking_dataset"] == "prices")
    assert any(row["focus_command"] == "make focus-fundamentals TICKER=AMD" for row in amd_rows if row["blocking_dataset"] == "fundamentals")
    assert any(row["focus_command"] == "make focus-peers TICKER=AMD" for row in amd_rows if row["blocking_dataset"] == "peers")
    assert any(row["focus_command"] == "make templates" for row in amd_rows if row["blocking_dataset"] == "earnings")
    assert any(row["focus_command"] == "make templates" for row in amd_rows if row["blocking_dataset"] == "analyst_estimates")
    assert any(
        "make focus-price TICKER=AMD" in row["recommended_action"]
        and row["example_command"] == "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual"
        for row in amd_rows
        if row["blocking_dataset"] == "prices"
    )
    assert any("make focus-fundamentals TICKER=AMD" in row["recommended_action"] for row in amd_rows if row["blocking_dataset"] == "fundamentals")
    assert any("make focus-peers TICKER=AMD" in row["recommended_action"] for row in amd_rows if row["blocking_dataset"] == "peers")
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
    assert Path(output_result["sec_stage_queue_path"]).exists()
    assert Path(output_result["peer_mapping_queue_path"]).exists()
    assert Path(output_result["ticker_unlock_ladder_path"]).exists()
    assert Path(output_result["unlock_priority_summary_path"]).exists()
    assert Path(output_result["command_bundles_path"]).exists()
    assert Path(output_result["command_bundle_details_path"]).exists()
    assert Path(output_result["command_bundle_runbook_path"]).exists()
    wizard_frame = pd.read_csv(output_result["wizard_path"])
    price_worklist_frame = pd.read_csv(output_result["price_worklist_path"])
    fundamentals_peer_frame = pd.read_csv(output_result["fundamentals_peer_worklist_path"])
    optional_context_frame = pd.read_csv(output_result["optional_context_worklist_path"])
    sec_stage_queue_frame = pd.read_csv(output_result["sec_stage_queue_path"])
    peer_mapping_queue_frame = pd.read_csv(output_result["peer_mapping_queue_path"])
    unlock_ladder_frame = pd.read_csv(output_result["ticker_unlock_ladder_path"])
    unlock_summary_frame = pd.read_csv(output_result["unlock_priority_summary_path"])
    command_bundles_frame = pd.read_csv(output_result["command_bundles_path"])
    command_bundle_details_frame = pd.read_csv(output_result["command_bundle_details_path"])
    command_bundle_runbook_frame = pd.read_csv(output_result["command_bundle_runbook_path"])
    assert list(wizard_frame.columns) == WIZARD_COLUMNS
    assert list(price_worklist_frame.columns) == PRICE_WORKLIST_COLUMNS
    assert list(fundamentals_peer_frame.columns) == FUNDAMENTALS_PEER_WORKLIST_COLUMNS
    assert list(optional_context_frame.columns) == OPTIONAL_CONTEXT_WORKLIST_COLUMNS
    assert list(sec_stage_queue_frame.columns) == SEC_STAGE_QUEUE_COLUMNS
    assert list(peer_mapping_queue_frame.columns) == PEER_MAPPING_QUEUE_COLUMNS
    assert list(unlock_ladder_frame.columns) == TICKER_UNLOCK_LADDER_COLUMNS
    assert list(unlock_summary_frame.columns) == UNLOCK_PRIORITY_SUMMARY_COLUMNS
    assert list(command_bundles_frame.columns) == COMMAND_BUNDLE_COLUMNS
    assert list(command_bundle_details_frame.columns) == COMMAND_BUNDLE_DETAIL_COLUMNS
    assert list(command_bundle_runbook_frame.columns) == COMMAND_BUNDLE_RUNBOOK_COLUMNS
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
    assert "focus_command" in payload["data_coverage_wizard"][0]


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
    assert payload["price_import_worklist"][0]["focus_command"] == "make focus-price TICKER=AMD"


def test_data_onboarding_cli_price_worklist_text_surfaces_goal_and_command(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--price-worklist"]
    try:
        main()
        output = capsys.readouterr().out.lower()
    finally:
        sys.argv = previous_argv

    assert "price import worklist" in output
    assert "goal=unlock monthly picks" in output
    assert "target_rows=21" in output
    assert "rows_needed=" in output
    assert "focus: make focus-price ticker=amd" in output
    assert "command:" in output
    assert "make price-normalize" in output


def test_data_onboarding_cli_price_worklist_text_respects_top_n(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--price-worklist", "--top-n", "1"]
    try:
        main()
        output = capsys.readouterr().out.lower()
    finally:
        sys.argv = previous_argv

    assert "price import worklist" in output
    assert output.count("- p") == 1
    assert "amd" in output
    assert "nvda" not in output


def test_price_worklist_prioritizes_sparse_price_history(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    worklist = {row["ticker"]: row for row in payload["price_import_worklist"]}

    assert worklist["AMD"]["priority"] == 1
    assert worklist["AMD"]["momentum_ready"] is False
    assert worklist["AMD"]["next_price_goal"] == "Unlock Monthly Picks"
    assert worklist["AMD"]["next_target_history_rows"] == 21
    assert worklist["AMD"]["rows_needed_for_next_goal"] == 20
    assert worklist["AMD"]["suggested_start_date"]
    assert worklist["AMD"]["focus_command"] == "make focus-price TICKER=AMD"
    assert "more verified rows needed" in worklist["AMD"]["missing_for_momentum"]
    assert worklist["NVDA"]["track_record_ready"] is False
    assert worklist["NVDA"]["next_price_goal"] == "Unlock Track Record"
    assert worklist["NVDA"]["next_target_history_rows"] == 63


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
    assert payload["fundamentals_peer_worklist"][0]["focus_command"] == "make focus-fundamentals TICKER=AMD"


def test_fundamentals_peer_worklist_prioritizes_dcf_then_peer_gaps(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    worklist = {row["ticker"]: row for row in payload["fundamentals_peer_worklist"]}

    assert worklist["AMD"]["priority"] == 1
    assert worklist["AMD"]["dcf_ready"] is False
    assert worklist["AMD"]["focus_command"] == "make focus-fundamentals TICKER=AMD"
    assert "fundamentals row" in worklist["AMD"]["missing_required_for_dcf"]
    assert worklist["NVDA"]["priority"] == 2
    assert worklist["NVDA"]["dcf_ready"] is True
    assert worklist["NVDA"]["peer_ready"] is False
    assert worklist["NVDA"]["focus_command"] == "make focus-fundamentals TICKER=AMD"
    assert worklist["NVDA"]["target_file"] == "data/imports/fundamentals.csv"


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


def test_data_onboarding_cli_sec_stage_queue_json(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--sec-stage-queue", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
    finally:
        sys.argv = previous_argv

    assert "sec_stage_queue" in payload
    assert payload["sec_stage_queue"][0]["ticker"] == "AMD"
    assert "missing_required_for_dcf" in payload["sec_stage_queue"][0]
    assert payload["sec_stage_queue"][0]["focus_command"] == "make focus-fundamentals TICKER=AMD"


def test_data_onboarding_cli_sec_stage_queue_text_surfaces_command_and_target_file(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--sec-stage-queue"]
    try:
        main()
        output = capsys.readouterr().out.lower()
    finally:
        sys.argv = previous_argv

    assert "sec stage queue" in output
    assert "focus: make focus-fundamentals ticker=amd" in output
    assert "command:" in output
    assert "make sec-stage tickers=amd" in output
    assert "target_file: data/imports/fundamentals.csv" in output


def test_sec_stage_queue_prioritizes_holdings_and_price_ready_names(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    queue = {row["ticker"]: row for row in payload["sec_stage_queue"]}

    assert queue["AMD"]["priority"] == 4
    assert queue["AMD"]["has_fundamentals"] is False
    assert queue["AMD"]["focus_command"] == "make focus-fundamentals TICKER=AMD"
    assert "make focus-fundamentals TICKER=AMD" in queue["AMD"]["recommended_action"]


def test_fundamentals_peer_worklist_uses_richer_operator_wording(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    worklist = {row["ticker"]: row for row in payload["fundamentals_peer_worklist"]}

    assert "make focus-fundamentals TICKER=AMD" in worklist["AMD"]["recommended_action"]
    assert "make focus-fundamentals TICKER=AMD" in worklist["NVDA"]["recommended_action"]


def test_onboarding_actions_use_peer_templates_and_transparent_wording(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    peer_actions = {
        row["ticker"]: row
        for row in payload["onboarding_actions"]
        if row["dataset"] == "peers"
    }

    assert peer_actions["AMD"]["example_command"] == "make templates"
    assert "make focus-peers TICKER=AMD" in peer_actions["AMD"]["recommended_action"]


def test_data_onboarding_cli_peer_mapping_queue_json(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--peer-mapping-queue", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
    finally:
        sys.argv = previous_argv

    assert "peer_mapping_queue" in payload
    assert payload["peer_mapping_queue"][0]["ticker"] == "NVDA"
    assert "missing_required_for_peer_relative" in payload["peer_mapping_queue"][0]
    assert payload["peer_mapping_queue"][0]["focus_command"] == "make focus-fundamentals TICKER=AMD"


def test_data_onboarding_cli_peer_mapping_queue_text_surfaces_command_and_target_file(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--peer-mapping-queue"]
    try:
        main()
        output = capsys.readouterr().out.lower()
    finally:
        sys.argv = previous_argv

    assert "peer mapping queue" in output
    assert "group=" in output
    assert "scope=" in output
    assert "validation:" in output
    assert "focus: make focus-peers ticker=amd" in output
    assert "command:" in output
    assert "make sec-stage tickers=amd" in output
    assert "target_file: data/imports/peers.csv" in output


def test_peer_mapping_queue_prioritizes_dcf_ready_holdings(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    queue = {row["ticker"]: row for row in payload["peer_mapping_queue"]}

    assert queue["NVDA"]["priority"] == 1
    assert queue["NVDA"]["is_holding"] is True
    assert queue["NVDA"]["dcf_ready"] is True
    assert queue["NVDA"]["workflow_group"] == "peer_valuation_unlock"
    assert queue["NVDA"]["workflow_scope"] == "master_universe"
    assert "peer fundamentals" in queue["NVDA"]["next_action_summary"].lower()
    assert "make imports-preview" in queue["NVDA"]["validation_sequence"]
    assert queue["NVDA"]["focus_command"] == "make focus-fundamentals TICKER=AMD"
    assert queue["NVDA"]["target_file"] == "data/imports/fundamentals.csv"
    assert "make focus-fundamentals TICKER=AMD" in queue["NVDA"]["recommended_action"]
    assert queue["AMD"]["focus_command"] == "make focus-peers TICKER=AMD"
    assert queue["AMD"]["workflow_group"] == "price_ready_peer_mapping"
    assert queue["AMD"]["next_input_file"] == "data/imports/peers.csv"
    assert "make templates" in queue["AMD"]["safe_next_step"]
    assert "make imports-validate" in queue["AMD"]["safe_next_step"]
    assert "make imports-preview" in queue["AMD"]["safe_next_step"]
    assert "make imports-apply" in queue["AMD"]["safe_next_step"]


def test_optional_context_worklist_keeps_optional_gaps_lower_priority(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    worklist = {row["ticker"]: row for row in payload["optional_context_worklist"]}

    assert worklist["AMD"]["priority"] == 5
    assert "earnings" in worklist["AMD"]["missing_optional_context"]
    assert "analyst_estimates" in worklist["AMD"]["missing_optional_context"]
    assert worklist["AMD"]["example_command"] == "make templates"
    assert "run make templates" in worklist["AMD"]["recommended_action"].lower()
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
    assert "focus_command" in payload["ticker_unlock_ladder"][0]


def test_ticker_unlock_ladder_orders_price_then_peer_then_optional(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    ladder = {row["ticker"]: row for row in payload["ticker_unlock_ladder"]}

    assert ladder["AMD"]["current_unlock_stage"] == "prices"
    assert ladder["AMD"]["next_unlock_goal"] == "Unlock Monthly Picks"
    assert ladder["AMD"]["focus_command"] == "make focus-price TICKER=AMD"
    assert "make focus-price TICKER=AMD" in ladder["AMD"]["recommended_action"]
    assert ladder["AMD"]["example_command"] == "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual"
    assert ladder["NVDA"]["current_unlock_stage"] == "peers"
    assert ladder["NVDA"]["next_unlock_goal"] == "Unlock Peer Relative"
    assert ladder["NVDA"]["focus_command"] == "make focus-fundamentals TICKER=AMD"
    assert "make focus-fundamentals TICKER=AMD" in ladder["NVDA"]["recommended_action"]
    assert ladder["NVDA"]["example_command"] == "make sec-stage TICKERS=AMD"


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
    assert "focus_command" in payload["unlock_priority_summary"][0]
    assert "example_command" in payload["unlock_priority_summary"][0]


def test_unlock_priority_summary_groups_holdings_themes_and_sector_etfs(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    summary = payload["unlock_priority_summary"]

    holdings_row = next(row for row in summary if row["group_type"] == "holdings")
    theme_row = next(row for row in summary if row["group_type"] == "theme" and row["group_name"] == "AI")
    sector_row = next(row for row in summary if row["group_type"] == "sector_etf" and row["group_name"] == "SMH")

    assert holdings_row["holdings_count"] == 1
    assert holdings_row["top_priority_stage"] == "peers"
    assert holdings_row["focus_command"] == "make status"
    assert holdings_row["example_command"] == "make runbook-peers"
    assert "make status" in holdings_row["recommended_action"]
    assert theme_row["ticker_count"] == 2
    assert theme_row["top_priority_stage"] == "prices"
    assert theme_row["focus_command"] == "make status"
    assert theme_row["example_command"] == "make runbook-prices"
    assert sector_row["ticker_count"] == 2
    assert sector_row["example_command"] == "make runbook-prices"


def test_data_onboarding_cli_unlock_summary_text_surfaces_commands(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--unlock-summary"]
    try:
        main()
        output = capsys.readouterr().out.lower()
    finally:
        sys.argv = previous_argv

    assert "unlock priority summary" in output
    assert "focus: make status" in output
    assert "command: make runbook" in output


def test_unlock_priority_summary_uses_status_first_ready_defaults(tmp_path: Path):
    data_dir = tmp_path / "data"
    outputs_dir = tmp_path / "outputs"
    data_dir.mkdir()
    outputs_dir.mkdir()
    pd.DataFrame(
        [
            {"ticker": "NVDA", "theme": "AI", "sectoretf": "SMH", "defaultpurpose": "Momentum Leader"},
        ]
    ).to_csv(data_dir / "universe.csv", index=False)
    pd.DataFrame([{"ticker": "NVDA", "shares": 1, "primarypurpose": "Momentum Leader"}]).to_csv(
        data_dir / "holdings.csv",
        index=False,
    )
    coverage_rows = [
        TickerCoverage(
            ticker="NVDA",
            has_prices=True,
            price_history_days=300,
            has_fundamentals=True,
            dcf_ready=True,
            has_peer_mapping=True,
            peer_ready=True,
            has_earnings=True,
            has_analyst_estimates=True,
            usable_for_momentum=True,
            usable_for_monthly_picks=True,
            usable_for_dcf=True,
            usable_for_peer_relative=True,
            missing_required_for_momentum="",
            missing_required_for_dcf="",
            missing_required_for_peer_relative="",
            next_best_action="Coverage is sufficient for the current CSV-first research workflow.",
            target_file="",
            focus_command="",
            example_command="",
        )
    ]

    summary = build_unlock_priority_summary(
        coverage_rows,
        build_ticker_unlock_ladder(coverage_rows),
        tmp_path,
        data_dir=data_dir,
        output_dir=outputs_dir,
    )

    holdings_row = next(row for row in summary if row.group_type == "holdings")
    assert holdings_row.top_priority_stage == "ready"
    assert holdings_row.focus_command == "make status"
    assert holdings_row.example_command == "make dashboard-smoke"


def test_data_onboarding_cli_command_bundles_json(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--command-bundles", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
    finally:
        sys.argv = previous_argv

    assert "command_bundles" in payload
    assert payload["command_bundles"][0]["lane"] == "prices"
    assert "primary_command" in payload["command_bundles"][0]


def test_data_onboarding_cli_command_bundles_text_surfaces_goal_summary(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--command-bundles"]
    try:
        main()
        output = capsys.readouterr().out.lower()
    finally:
        sys.argv = previous_argv

    assert "price coverage bundle" in output
    assert "goal:" in output
    assert "unlock monthly picks" in output
    assert "target_history_rows:" in output
    assert "suggested_start_date:" in output
    assert "fallback:" not in output


def test_data_onboarding_cli_command_bundles_text_respects_top_n(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--command-bundles", "--top-n", "1"]
    try:
        main()
        output = capsys.readouterr().out.lower()
    finally:
        sys.argv = previous_argv

    assert output.count("bundle: lane=") == 1
    assert "command bundle rows: 4" in output


def test_data_onboarding_cli_command_bundles_can_filter_by_lane_and_holdings(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = [
        "python",
        "--project-root",
        str(tmp_path),
        "--command-bundles",
        "--lane",
        "peers",
        "--holdings-only",
        "--json",
    ]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
    finally:
        sys.argv = previous_argv

    assert len(payload["command_bundles"]) == 1
    assert payload["command_bundles"][0]["lane"] == "peers"
    assert payload["command_bundles"][0]["scope"] == "holdings_first"


def test_data_onboarding_cli_command_bundles_can_filter_by_lane_and_broader_scope(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = [
        "python",
        "--project-root",
        str(tmp_path),
        "--command-bundles",
        "--lane",
        "prices",
        "--scope",
        "broader_queue",
        "--json",
    ]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
    finally:
        sys.argv = previous_argv

    assert len(payload["command_bundles"]) == 1
    assert payload["command_bundles"][0]["lane"] == "prices"
    assert payload["command_bundles"][0]["scope"] == "broader_queue"


def test_command_bundles_surface_holdings_first_price_and_sec_paths(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    bundles = payload["command_bundles"]
    price_bundle = next(row for row in bundles if row["lane"] == "prices" and row["scope"] == "broader_queue")
    fundamentals_bundle = next(row for row in bundles if row["lane"] == "fundamentals" and row["scope"] == "broader_queue")
    peer_bundle = next(row for row in bundles if row["lane"] == "peers" and row["scope"] == "holdings_first")

    assert list(payload["command_bundles"][0].keys()) == COMMAND_BUNDLE_COLUMNS
    assert price_bundle["scope"] == "broader_queue"
    assert "AMD" in price_bundle["tickers"]
    assert "Unlock Monthly Picks" in price_bundle["goal_summary"]
    assert price_bundle["target_history_rows"] >= 21
    assert price_bundle["suggested_start_date"]
    assert price_bundle["primary_command"].startswith("make price-refresh TICKERS=")
    assert "AMD" in price_bundle["primary_command"]
    assert "make price-normalize" in price_bundle["safe_next_step"]
    assert "make price-validate" in price_bundle["safe_next_step"]
    assert "make price-preview" in price_bundle["safe_next_step"]
    assert "make price-apply" in price_bundle["safe_next_step"]
    assert fundamentals_bundle["scope"] == "broader_queue"
    assert "AMD" in fundamentals_bundle["tickers"]
    assert "DCF readiness" in fundamentals_bundle["goal_summary"]
    assert fundamentals_bundle["primary_command"].startswith("make sec-stage TICKERS=")
    assert fundamentals_bundle["follow_up_command"] == "make imports-validate"
    assert "make imports-validate" in fundamentals_bundle["safe_next_step"]
    assert "make imports-preview" in fundamentals_bundle["safe_next_step"]
    assert "make imports-apply" in fundamentals_bundle["safe_next_step"]
    assert peer_bundle["scope"] == "holdings_first"
    assert "NVDA" in peer_bundle["tickers"]
    assert "peer-relative readiness" in peer_bundle["goal_summary"]
    assert peer_bundle["target_file"] == "data/imports/peers.csv"
    assert "make imports-validate" in peer_bundle["safe_next_step"]
    assert "make imports-preview" in peer_bundle["safe_next_step"]
    assert "make imports-apply" in peer_bundle["safe_next_step"]


def test_data_onboarding_cli_command_bundle_details_json(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--command-bundle-details", "--json"]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
    finally:
        sys.argv = previous_argv

    assert "command_bundle_details" in payload
    assert payload["command_bundle_details"][0]["lane"] == "prices"
    assert "ticker" in payload["command_bundle_details"][0]


def test_data_onboarding_cli_command_bundle_details_can_filter_by_lane_and_holdings(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = [
        "python",
        "--project-root",
        str(tmp_path),
        "--command-bundle-details",
        "--lane",
        "peers",
        "--holdings-only",
        "--json",
    ]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
    finally:
        sys.argv = previous_argv

    assert payload["command_bundle_details"]
    assert all(row["lane"] == "peers" for row in payload["command_bundle_details"])
    assert all(row["is_holding"] is True for row in payload["command_bundle_details"])


def test_data_onboarding_cli_command_bundle_details_can_filter_by_lane_and_broader_scope(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = [
        "python",
        "--project-root",
        str(tmp_path),
        "--command-bundle-details",
        "--lane",
        "prices",
        "--scope",
        "broader_queue",
        "--json",
    ]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
    finally:
        sys.argv = previous_argv

    assert payload["command_bundle_details"]
    assert all(row["lane"] == "prices" for row in payload["command_bundle_details"])
    assert all(row["is_holding"] is False for row in payload["command_bundle_details"])


def test_data_onboarding_cli_command_bundle_runbook_can_filter_by_lane_and_holdings(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = [
        "python",
        "--project-root",
        str(tmp_path),
        "--command-bundle-runbook",
        "--lane",
        "peers",
        "--holdings-only",
        "--json",
    ]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
    finally:
        sys.argv = previous_argv

    assert payload["command_bundle_runbook"]
    assert all(row["lane"] == "peers" for row in payload["command_bundle_runbook"])
    assert all(row["scope"] == "holdings_first" for row in payload["command_bundle_runbook"])


def test_data_onboarding_cli_command_bundle_runbook_can_filter_by_lane_and_broader_scope(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = [
        "python",
        "--project-root",
        str(tmp_path),
        "--command-bundle-runbook",
        "--lane",
        "prices",
        "--scope",
        "broader_queue",
        "--json",
    ]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
    finally:
        sys.argv = previous_argv

    assert payload["command_bundle_runbook"]
    assert all(row["lane"] == "prices" for row in payload["command_bundle_runbook"])
    assert all(row["scope"] == "broader_queue" for row in payload["command_bundle_runbook"])


def test_data_onboarding_cli_command_bundle_runbook_text_surfaces_goal_summary(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--command-bundle-runbook", "--lane", "prices"]
    try:
        main()
        output = capsys.readouterr().out.lower()
    finally:
        sys.argv = previous_argv

    assert "price coverage bundle" in output
    assert "goal:" in output
    assert "unlock monthly picks" in output
    assert "if refresh fails, normalize first csv" in output
    assert "fallback:" in output
    assert "if staged imports were used, validate prices" in output
    assert "make price-validate" in output
    assert "make price-preview" in output
    assert "make price-apply" in output


def test_data_onboarding_cli_peer_runbook_text_surfaces_manual_peer_step(tmp_path: Path, capsys):
    _write_fixture(tmp_path)
    previous_argv = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--command-bundle-runbook", "--lane", "peers"]
    try:
        main()
        output = capsys.readouterr().out.lower()
    finally:
        sys.argv = previous_argv

    assert "peer mapping bundle" in output
    assert "fill peer mappings manually" in output
    assert "data/imports/peers.csv" in output
    assert "make imports-validate" in output
    assert "make imports-preview" in output
    assert "make imports-apply" in output


def test_command_bundle_details_expand_bundle_tickers_with_stage_context(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    details = payload["command_bundle_details"]
    price_detail = next(row for row in details if row["lane"] == "prices" and row["ticker"] == "AMD")
    fundamentals_detail = next(row for row in details if row["lane"] == "fundamentals" and row["ticker"] == "AMD")
    peer_detail = next(row for row in details if row["lane"] == "peers" and row["ticker"] == "NVDA")

    assert list(details[0].keys()) == COMMAND_BUNDLE_DETAIL_COLUMNS
    assert price_detail["current_unlock_stage"] == "prices"
    assert price_detail["target_goal"] == "Unlock Monthly Picks"
    assert price_detail["rows_needed"] >= 1
    assert price_detail["target_history_rows"] >= 21
    assert price_detail["suggested_start_date"]
    assert price_detail["exact_next_command"] == "make focus-price TICKER=AMD"
    assert "make price-normalize" in price_detail["fallback_manual_command"]
    assert price_detail["primary_command"].startswith("make price-refresh TICKERS=")
    assert "make focus-fundamentals TICKER=AMD" in fundamentals_detail["recommended_action"]
    assert fundamentals_detail["exact_next_command"] == "make focus-fundamentals TICKER=AMD"
    assert peer_detail["is_holding"] is True
    assert peer_detail["current_unlock_stage"] == "peers"
    assert peer_detail["target_goal"] == "Unlock Peer Relative"
    assert peer_detail["exact_next_command"] == "make focus-fundamentals TICKER=AMD"
    assert "make focus-fundamentals TICKER=AMD" in peer_detail["recommended_action"]


def test_command_bundle_runbook_expands_each_bundle_into_ordered_steps(tmp_path: Path):
    _write_fixture(tmp_path)

    payload = build_onboarding_payload(tmp_path)
    runbook = payload["command_bundle_runbook"]
    price_steps = [row for row in runbook if row["lane"] == "prices"]

    assert list(runbook[0].keys()) == COMMAND_BUNDLE_RUNBOOK_COLUMNS
    assert [row["step_order"] for row in price_steps] == [1, 2, 3, 4, 5, 6, 7]
    assert price_steps[0]["step_label"] == "Run bundle command"
    assert "Unlock Monthly Picks" in price_steps[0]["goal_summary"]
    assert price_steps[0]["target_history_rows"] >= 21
    assert price_steps[0]["suggested_start_date"]
    assert price_steps[0]["command"].startswith("make price-refresh TICKERS=")
    assert price_steps[1]["step_label"] == "If refresh fails, normalize first CSV"
    assert "make price-normalize" in price_steps[1]["command"]
    assert "make price-normalize" in price_steps[1]["fallback_manual_command"]
    assert price_steps[2]["step_label"] == "If staged imports were used, validate prices"
    assert price_steps[2]["command"] == "make price-validate"
    assert price_steps[3]["command"] == "make price-preview"
    assert price_steps[4]["command"] == "make price-apply"
    assert price_steps[5]["command"] == "make price-status"
    assert price_steps[-1]["step_label"] == "Refresh status outputs"
    assert price_steps[-1]["command"] == "make status"
    fundamentals_steps = [
        row
        for row in runbook
        if row["lane"] == "fundamentals"
    ]
    fundamentals_scope = fundamentals_steps[0]["scope"]
    fundamentals_steps = [row for row in fundamentals_steps if row["scope"] == fundamentals_scope]
    assert [row["step_order"] for row in fundamentals_steps] == [1, 2, 3, 4, 5]
    assert fundamentals_steps[1]["step_label"] == "Validate staged fundamentals"
    assert fundamentals_steps[1]["command"] == "make imports-validate"
    assert fundamentals_steps[2]["step_label"] == "Preview fundamentals merge"
    assert fundamentals_steps[2]["command"] == "make imports-preview"
    assert fundamentals_steps[3]["step_label"] == "Apply fundamentals merge"
    assert fundamentals_steps[3]["command"] == "make imports-apply"
    assert fundamentals_steps[4]["step_label"] == "Refresh status outputs"
    assert fundamentals_steps[4]["command"] == "make status"
    peer_steps = [
        row
        for row in runbook
        if row["lane"] == "peers" and row["scope"] == "holdings_first"
    ]
    assert [row["step_order"] for row in peer_steps] == [1, 2, 3, 4, 5, 6]
    assert peer_steps[1]["step_label"] == "Fill peer mappings manually"
    assert peer_steps[1]["command"] == "data/imports/peers.csv"
    assert peer_steps[2]["step_label"] == "Validate staged peer mappings"
    assert peer_steps[2]["command"] == "make imports-validate"
    assert peer_steps[3]["step_label"] == "Preview peer mapping merge"
    assert peer_steps[3]["command"] == "make imports-preview"
    assert peer_steps[4]["step_label"] == "Apply peer mapping merge"
    assert peer_steps[4]["command"] == "make imports-apply"
    assert peer_steps[5]["step_label"] == "Refresh status outputs"
    assert peer_steps[5]["command"] == "make status"


def test_build_data_coverage_wizard_accepts_empty_coverage():
    assert build_data_coverage_wizard([]) == []
