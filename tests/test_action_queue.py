from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.action_queue import build_action_queue_payload, build_action_queue_rows, write_action_queue_output


def test_action_queue_prioritizes_price_failures_before_optional_gaps():
    rows = build_action_queue_rows(
        price_status=pd.DataFrame(
            [
                {
                    "ticker": "NVDA",
                    "status": "parse_error",
                    "recommended_action": "Use staged manual prices.",
                    "error_message": "Parser failed.",
                }
            ]
        ),
        onboarding_actions=pd.DataFrame(
            [
                {
                    "priority": 5,
                    "ticker": "NVDA",
                    "dataset": "analyst_estimates",
                    "status": "optional_missing",
                    "reason": "No analyst row.",
                    "recommended_action": "Leave missing unless trusted source exists.",
                    "target_file": "data/imports/analyst_estimates.csv",
                    "example_command": "make templates",
                }
            ]
        ),
        data_gaps=pd.DataFrame(),
        data_quality=pd.DataFrame(),
    )

    assert rows[0].action_type == "prices"
    assert rows[0].priority == 1
    assert rows[0].focus_command == "make focus-price TICKER=NVDA"
    assert rows[-1].action_type == "analyst_estimates"


def test_action_queue_uses_research_health_when_price_data_is_missing():
    rows = build_action_queue_rows(
        price_status=pd.DataFrame(),
        onboarding_actions=pd.DataFrame(),
        data_gaps=pd.DataFrame(),
        data_quality=pd.DataFrame(
            [
                {
                    "Ticker": "AMD",
                    "ReadinessStatus": "Needs Price Data",
                    "NextBestAction": "Refresh or import prices.",
                    "Reason": "No local prices found.",
                }
            ]
        ),
    )

    assert rows[0].ticker == "AMD"
    assert rows[0].action_type == "prices"
    assert rows[0].focus_command == "make focus-price TICKER=AMD"
    assert "Refresh or import prices" in rows[0].recommended_action


def test_action_queue_uses_operator_friendly_onboarding_titles():
    rows = build_action_queue_rows(
        price_status=pd.DataFrame(),
        onboarding_actions=pd.DataFrame(
            [
                {
                    "priority": 1,
                    "ticker": "AMD",
                    "dataset": "prices",
                    "status": "missing",
                    "reason": "No verified local price history is present for this ticker yet.",
                    "recommended_action": "Run python3 -m src.data_update --tickers AMD.",
                    "target_file": "data/imports/prices.csv",
                    "focus_command": "make focus-price TICKER=AMD",
                    "example_command": "python3 -m src.data_update --tickers AMD",
                },
                {
                    "priority": 2,
                    "ticker": "NVDA",
                    "dataset": "fundamentals",
                    "status": "missing_or_incomplete",
                    "reason": "No local fundamentals row is present for this ticker yet.",
                    "recommended_action": "Run SEC staging.",
                    "target_file": "data/imports/fundamentals.csv",
                    "focus_command": "make focus-fundamentals TICKER=NVDA",
                    "example_command": "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA",
                },
                {
                    "priority": 3,
                    "ticker": "TSLA",
                    "dataset": "peers",
                    "status": "manual_input_needed",
                    "reason": "No local peer mapping is configured for this ticker.",
                    "recommended_action": "Add peer mappings manually.",
                    "target_file": "data/imports/peers.csv",
                    "focus_command": "make focus-peers TICKER=TSLA",
                    "example_command": "make templates",
                },
            ]
        ),
        data_gaps=pd.DataFrame(),
        data_quality=pd.DataFrame(),
    )

    assert rows[0].title == "Fix price coverage for AMD"
    assert any(row.title == "Stage fundamentals for NVDA" for row in rows)
    assert any(row.title == "Add peer mappings for TSLA" for row in rows)


def test_action_queue_payload_refreshes_stale_onboarding_actions(tmp_path: Path):
    outputs_dir = tmp_path / "outputs"
    data_dir = tmp_path / "data"
    outputs_dir.mkdir()
    data_dir.mkdir()
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
    (outputs_dir / "data_onboarding_actions.csv").write_text(
        "priority,ticker,dataset,status,reason,recommended_action,target_file,focus_command,example_command\n"
        "1,NVDA,prices,insufficient_history,prices,Refresh prices,data/imports/prices.csv,make focus-price TICKER=NVDA,python3 -m src.data_update --tickers NVDA\n",
        encoding="utf-8",
    )
    (outputs_dir / "data_gap_report.csv").write_text(
        "dataset,ticker,status,reason,required_for,recommended_action,local_file,source_name\n",
        encoding="utf-8",
    )
    (outputs_dir / "data_quality_wizard.csv").write_text(
        "Ticker,DataQualityScore,ReadinessStatus,MomentumReady,MonthlyPicksReady,DCFReady,PeerReady,EarningsAvailable,AnalystEstimatesAvailable,PriceHistoryDays,MissingDataFields,NextBestAction,Reason\n"
        "NVDA,20,Needs Enrichment,true,true,false,false,false,false,2,DCF inputs;peer mapping,Run SEC staging,Missing DCF and peer coverage.\n",
        encoding="utf-8",
    )

    payload = build_action_queue_payload(tmp_path, data_dir=data_dir, output_dir=outputs_dir)

    price_rows = [row for row in payload["action_queue"] if row["action_type"] == "prices"]
    assert price_rows
    assert any("at least 21 are needed" in row["reason"].lower() for row in price_rows)


def test_action_queue_write_output_creates_csv_from_existing_outputs(tmp_path: Path):
    outputs_dir = tmp_path / "outputs"
    data_dir = tmp_path / "data"
    outputs_dir.mkdir()
    data_dir.mkdir()
    (outputs_dir / "price_update_status.csv").write_text(
        "run_timestamp,ticker,requested_start,requested_end,provider,status,rows_fetched,rows_merged,error_category,error_message,fallback_used,recommended_action\n"
        "2026-05-21T00:00:00Z,NVDA,,2026-05-21,stooq,parse_error,0,0,parse_error,Parser failed,false,Use staged manual prices.\n",
        encoding="utf-8",
    )
    (outputs_dir / "data_onboarding_actions.csv").write_text(
        "priority,ticker,dataset,status,reason,recommended_action,target_file,focus_command,example_command\n"
        "2,NVDA,fundamentals,missing_or_incomplete,DCF inputs incomplete,Run SEC staging,data/imports/fundamentals.csv,make focus-fundamentals TICKER=NVDA,make sec-stage TICKERS=NVDA\n",
        encoding="utf-8",
    )
    (outputs_dir / "data_gap_report.csv").write_text(
        "dataset,ticker,status,reason,required_for,recommended_action,local_file,source_name\n"
        "peers,NVDA,manual_only,No peers configured,peer-relative valuation,Add peers manually,data/peers.csv,Manual local peer mappings\n",
        encoding="utf-8",
    )
    (outputs_dir / "data_quality_wizard.csv").write_text(
        "Ticker,DataQualityScore,ReadinessStatus,MomentumReady,MonthlyPicksReady,DCFReady,PeerReady,EarningsAvailable,AnalystEstimatesAvailable,PriceHistoryDays,MissingDataFields,NextBestAction,Reason\n"
        "NVDA,20,Needs Enrichment,true,true,false,false,false,false,40,DCF inputs;peer mapping,Run SEC staging,Missing DCF and peer coverage.\n",
        encoding="utf-8",
    )

    payload = write_action_queue_output(tmp_path, data_dir=data_dir, output_dir=outputs_dir)

    queue_path = Path(payload["queue_path"])
    assert queue_path.exists()
    frame = pd.read_csv(queue_path)
    assert list(frame.columns)
    assert {"priority", "action_type", "recommended_action", "reason"} <= set(frame.columns)
    assert "focus_command" in frame.columns
    assert frame.iloc[0]["action_type"] == "prices"
