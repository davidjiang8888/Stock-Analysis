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
        price_worklist=pd.DataFrame(),
        onboarding_actions=pd.DataFrame(
            [
                {
                    "priority": 5,
                    "ticker": "NVDA",
                    "dataset": "analyst_estimates",
                    "status": "optional_missing",
                    "reason": "No analyst row.",
                    "recommended_action": "Run make templates, then fill data/imports/analyst_estimates.csv manually only if you have a trusted source.",
                    "target_file": "data/imports/analyst_estimates.csv",
                    "focus_command": "make templates",
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
    assert rows[0].example_command == "make price-normalize INPUT=data/raw/prices/NVDA.csv TICKER=NVDA SOURCE=yahoo_manual"
    assert "make focus-price TICKER=NVDA" in rows[0].recommended_action
    assert "normalize verified downloaded ohlcv files" in rows[0].recommended_action.lower()
    assert "price-validate" in rows[0].reason.lower()
    assert rows[-1].action_type == "analyst_estimates"
    assert rows[-1].focus_command == "make templates"


def test_action_queue_uses_status_first_fallback_for_price_failures_without_ticker():
    rows = build_action_queue_rows(
        price_status=pd.DataFrame(
            [
                {
                    "ticker": "",
                    "status": "parse_error",
                    "recommended_action": "Use staged manual prices.",
                    "error_message": "Generic provider failure.",
                }
            ]
        ),
        price_worklist=pd.DataFrame(),
        onboarding_actions=pd.DataFrame(),
        data_gaps=pd.DataFrame(),
        data_quality=pd.DataFrame(),
    )

    row = rows[0]
    assert row.action_type == "prices"
    assert row.focus_command == "make status"
    assert row.example_command == "make status"
    assert "run make status" in row.recommended_action.lower()
    assert "data/imports/prices.csv" in row.recommended_action
    assert "ohlcv files" in row.recommended_action.lower()


def test_action_queue_uses_research_health_when_price_data_is_missing():
    rows = build_action_queue_rows(
        price_status=pd.DataFrame(),
        price_worklist=pd.DataFrame(),
        onboarding_actions=pd.DataFrame(),
        data_gaps=pd.DataFrame(),
        data_quality=pd.DataFrame(
            [
                {
                    "Ticker": "AMD",
                    "ReadinessStatus": "Needs Price Data",
                    "NextBestAction": "Refresh or import prices.",
                    "FocusCommand": "make focus-price TICKER=AMD",
                    "ExampleCommand": "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
                    "Reason": "No local prices found.",
                }
            ]
        ),
    )

    assert rows[0].ticker == "AMD"
    assert rows[0].action_type == "prices"
    assert rows[0].focus_command == "make focus-price TICKER=AMD"
    assert "make focus-price TICKER=AMD" in rows[0].recommended_action
    assert rows[0].example_command == "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual"


def test_action_queue_uses_focus_commands_for_enrichment_rows():
    rows = build_action_queue_rows(
        price_status=pd.DataFrame(),
        price_worklist=pd.DataFrame(),
        onboarding_actions=pd.DataFrame(),
        data_gaps=pd.DataFrame(),
        data_quality=pd.DataFrame(
            [
                {
                    "Ticker": "NVDA",
                    "ReadinessStatus": "Needs Enrichment",
                    "NextBestAction": (
                        "Run make focus-fundamentals TICKER=NVDA, or stage explicit local fundamentals with "
                        "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA."
                    ),
                    "FocusCommand": "make focus-fundamentals TICKER=NVDA",
                    "ExampleCommand": "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA",
                    "MissingDataFields": "DCF inputs, peer mapping",
                    "Reason": "Missing DCF and peer coverage.",
                },
                {
                    "Ticker": "TSLA",
                    "ReadinessStatus": "Partial Coverage",
                    "NextBestAction": (
                        "Run make focus-peers TICKER=TSLA, or write templates and fill data/imports/peers.csv "
                        "manually with transparent peer mappings."
                    ),
                    "FocusCommand": "make focus-peers TICKER=TSLA",
                    "ExampleCommand": "make templates",
                    "MissingDataFields": "peer mapping",
                    "Reason": "Missing peer mapping.",
                },
            ]
        ),
    )

    nvda_row = next(row for row in rows if row.ticker == "NVDA")
    assert nvda_row.focus_command == "make focus-fundamentals TICKER=NVDA"
    assert nvda_row.example_command == "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA"
    assert nvda_row.target_file == "data/imports/fundamentals.csv"
    assert nvda_row.source_file == "data/imports/fundamentals.csv"

    tsla_row = next(row for row in rows if row.ticker == "TSLA")
    assert tsla_row.focus_command == "make focus-peers TICKER=TSLA"
    assert tsla_row.example_command == "make templates"
    assert tsla_row.target_file == "data/imports/peers.csv"
    assert tsla_row.source_file == "data/imports/peers.csv"


def test_action_queue_uses_operator_friendly_onboarding_titles():
    rows = build_action_queue_rows(
        price_status=pd.DataFrame(),
        price_worklist=pd.DataFrame(),
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


def test_action_queue_uses_staged_import_titles_for_global_gap_rows():
    rows = build_action_queue_rows(
        price_status=pd.DataFrame(),
        price_worklist=pd.DataFrame(),
        onboarding_actions=pd.DataFrame(),
        data_gaps=pd.DataFrame(
            [
                {
                    "dataset": "fundamentals",
                    "ticker": "",
                    "status": "partial",
                    "reason": (
                        "SEC staging only provides candidate fundamentals; it does not provide prices, peers, earnings, "
                        "or analyst estimates. Staged import rows are present in data/imports/fundamentals.csv; "
                        "validate, preview, apply, then refresh status before relying on canonical local data."
                    ),
                    "recommended_action": (
                        "Run make imports-validate, then make imports-preview, then make imports-apply, then make status "
                        "to confirm the live local fundamentals and DCF inputs."
                    ),
                    "focus_command": "make imports-validate",
                    "example_command": "make imports-preview",
                    "target_file": "data/imports/fundamentals.csv",
                    "local_file": "data/fundamentals.csv",
                    "source_name": "Local fundamentals CSV / SEC Companyfacts staging",
                }
            ]
        ),
        data_quality=pd.DataFrame(),
    )

    row = rows[0]
    assert row.title == "Advance staged fundamentals import"
    assert row.focus_command == "make imports-validate"
    assert "data/imports/fundamentals.csv" in row.reason


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
    pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "DataQualityScore": 20,
                "ReadinessStatus": "Needs Enrichment",
                "MomentumReady": True,
                "MonthlyPicksReady": True,
                "DCFReady": False,
                "PeerReady": False,
                "EarningsAvailable": False,
                "AnalystEstimatesAvailable": False,
                "PriceHistoryDays": 2,
                "MissingDataFields": "DCF inputs;peer mapping",
                "NextBestAction": (
                    "Run make focus-fundamentals TICKER=NVDA, or stage explicit local fundamentals with "
                    "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA."
                ),
                "Reason": "Missing DCF and peer coverage.",
            }
        ]
    ).to_csv(outputs_dir / "data_quality_wizard.csv", index=False)

    payload = build_action_queue_payload(tmp_path, data_dir=data_dir, output_dir=outputs_dir)

    price_rows = [row for row in payload["action_queue"] if row["action_type"] == "prices"]
    assert price_rows
    assert any("at least 21 are needed" in row["reason"].lower() for row in price_rows)
    coverage_rows = [row for row in payload["action_queue"] if row["action_type"] == "coverage" and row["ticker"] == "NVDA"]
    assert not coverage_rows
    fundamentals_rows = [row for row in payload["action_queue"] if row["action_type"] == "fundamentals" and row["ticker"] == "NVDA"]
    assert fundamentals_rows
    assert fundamentals_rows[0]["focus_command"] == "make focus-fundamentals TICKER=NVDA"
    assert fundamentals_rows[0]["example_command"] == "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA"
    assert "make focus-fundamentals TICKER=NVDA" in fundamentals_rows[0]["recommended_action"]


def test_action_queue_payload_refreshes_stale_price_actions_from_data_quality(tmp_path: Path):
    outputs_dir = tmp_path / "outputs"
    data_dir = tmp_path / "data"
    outputs_dir.mkdir()
    data_dir.mkdir()
    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(), encoding="utf-8")
    pd.DataFrame(
        [
            {"ticker": "AMD", "theme": "AI", "sectoretf": "SMH", "defaultpurpose": "Momentum Leader"},
        ]
    ).to_csv(data_dir / "universe.csv", index=False)
    pd.DataFrame(columns=["ticker", "shares", "primarypurpose"]).to_csv(data_dir / "holdings.csv", index=False)
    (outputs_dir / "data_onboarding_actions.csv").write_text(
        "priority,ticker,dataset,status,reason,recommended_action,target_file,focus_command,example_command\n",
        encoding="utf-8",
    )
    (outputs_dir / "data_gap_report.csv").write_text(
        "dataset,ticker,status,reason,required_for,recommended_action,local_file,source_name\n",
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "Ticker": "AMD",
                "DataQualityScore": 0,
                "ReadinessStatus": "Needs Price Data",
                "MomentumReady": False,
                "MonthlyPicksReady": False,
                "DCFReady": False,
                "PeerReady": False,
                "EarningsAvailable": False,
                "AnalystEstimatesAvailable": False,
                "PriceHistoryDays": 0,
                "MissingDataFields": "prices",
                "NextBestAction": "Run python3 -m src.data_update --tickers AMD, or add verified rows to data/imports/prices.csv and run validate/preview/apply.",
                "Reason": "AMD has 0 local price rows.",
            }
        ]
    ).to_csv(outputs_dir / "data_quality_wizard.csv", index=False)

    payload = build_action_queue_payload(tmp_path, data_dir=data_dir, output_dir=outputs_dir)

    amd_row = next(row for row in payload["action_queue"] if row["ticker"] == "AMD" and row["action_type"] == "prices")
    assert amd_row["focus_command"] == "make focus-price TICKER=AMD"
    assert "normalize verified downloaded OHLCV files into data/imports/prices.csv" in amd_row["recommended_action"]
    assert amd_row["example_command"] == "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual"


def test_action_queue_payload_refreshes_stale_staged_fundamentals_gap_reason(tmp_path: Path):
    outputs_dir = tmp_path / "outputs"
    data_dir = tmp_path / "data"
    imports_dir = data_dir / "imports"
    outputs_dir.mkdir()
    data_dir.mkdir()
    imports_dir.mkdir()
    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(), encoding="utf-8")
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
    (outputs_dir / "data_onboarding_actions.csv").write_text(
        "priority,ticker,dataset,status,reason,recommended_action,target_file,focus_command,example_command\n",
        encoding="utf-8",
    )
    (outputs_dir / "data_quality_wizard.csv").write_text(
        "Ticker,ReadinessStatus,NextBestAction,Reason\n",
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "dataset": "fundamentals",
                "ticker": "",
                "status": "partial",
                "reason": "as_of_date column is unavailable, so freshness is file-based only.",
                "required_for": "valuation",
                "recommended_action": (
                    "Run make imports-validate, then make imports-preview, then make imports-apply, "
                    "then make status to confirm the live local fundamentals and DCF inputs."
                ),
                "target_file": "data/imports/fundamentals.csv",
                "focus_command": "make imports-validate",
                "example_command": "make imports-preview",
                "local_file": "data/fundamentals.csv",
                "source_name": "Local fundamentals CSV / SEC Companyfacts staging",
            }
        ]
    ).to_csv(outputs_dir / "data_gap_report.csv", index=False)

    payload = build_action_queue_payload(tmp_path, data_dir=data_dir, output_dir=outputs_dir)

    staged_row = next(
        row
        for row in payload["action_queue"]
        if row["focus_command"] == "make imports-validate" and row["title"] == "Advance staged fundamentals import"
    )
    assert staged_row["title"] == "Advance staged fundamentals import"
    assert "data/imports/fundamentals.csv" in staged_row["reason"]


def test_action_queue_prefers_specific_onboarding_rows_over_broader_data_gap_rows():
    rows = build_action_queue_rows(
        price_status=pd.DataFrame(),
        price_worklist=pd.DataFrame(),
        onboarding_actions=pd.DataFrame(
            [
                {
                    "priority": 2,
                    "ticker": "AMD",
                    "dataset": "fundamentals",
                    "status": "missing_or_incomplete",
                    "reason": "No local fundamentals row is present for this ticker yet.",
                    "recommended_action": "Run SEC staging for fundamentals, then validate and preview before applying.",
                    "target_file": "data/imports/fundamentals.csv",
                    "focus_command": "make focus-fundamentals TICKER=AMD",
                    "example_command": "python3 -m src.stock_report --sec-stage-fundamentals --tickers AMD",
                }
            ]
        ),
        data_gaps=pd.DataFrame(
            [
                {
                    "dataset": "fundamentals",
                    "ticker": "AMD",
                    "status": "partial",
                    "reason": "No local fundamentals row was found for AMD.",
                    "recommended_action": "Run SEC staging for fundamentals, then validate, preview, and apply the staged import.",
                    "local_file": "data/fundamentals.csv",
                }
            ]
        ),
        data_quality=pd.DataFrame(),
    )

    fundamentals_row = next(row for row in rows if row.action_type == "fundamentals" and row.ticker == "AMD")
    assert fundamentals_row.title == "Stage fundamentals for AMD"
    assert fundamentals_row.example_command == "python3 -m src.stock_report --sec-stage-fundamentals --tickers AMD"
    assert fundamentals_row.source_artifact == "outputs/data_onboarding_actions.csv"


def test_action_queue_drops_redundant_coverage_rows_when_specific_action_matches():
    rows = build_action_queue_rows(
        price_status=pd.DataFrame(),
        price_worklist=pd.DataFrame(),
        onboarding_actions=pd.DataFrame(
            [
                {
                    "priority": 2,
                    "ticker": "NVDA",
                    "dataset": "fundamentals",
                    "status": "missing_or_incomplete",
                    "reason": "DCF inputs are still incomplete: shares_outstanding.",
                    "recommended_action": "Stage or add richer verified fundamentals to close the remaining DCF input gaps.",
                    "target_file": "data/imports/fundamentals.csv",
                    "focus_command": "make focus-fundamentals TICKER=NVDA",
                    "example_command": "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA",
                }
            ]
        ),
        data_gaps=pd.DataFrame(),
        data_quality=pd.DataFrame(
            [
                {
                    "Ticker": "NVDA",
                    "ReadinessStatus": "Needs Enrichment",
                    "NextBestAction": (
                        "Run make focus-fundamentals TICKER=NVDA, or stage explicit local fundamentals with "
                        "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA."
                    ),
                    "MissingDataFields": "DCF inputs, peer mapping",
                    "Reason": "Missing DCF and peer coverage.",
                }
            ]
        ),
    )

    nvda_rows = [row for row in rows if row.ticker == "NVDA"]
    assert len(nvda_rows) == 1
    assert nvda_rows[0].action_type == "fundamentals"
    assert nvda_rows[0].focus_command == "make focus-fundamentals TICKER=NVDA"


def test_action_queue_uses_runbook_and_template_commands_for_global_gap_rows():
    rows = build_action_queue_rows(
        price_status=pd.DataFrame(),
        price_worklist=pd.DataFrame(),
        onboarding_actions=pd.DataFrame(),
        data_gaps=pd.DataFrame(
            [
                {
                    "dataset": "fundamentals",
                    "ticker": "",
                    "status": "partial",
                    "reason": "Freshness metadata is file-based only.",
                    "recommended_action": "Run SEC staging for fundamentals, then validate, preview, and apply the staged import.",
                    "local_file": "data/fundamentals.csv",
                },
                {
                    "dataset": "peers",
                    "ticker": "",
                    "status": "manual_only",
                    "reason": "Local CSV file is not present.",
                    "recommended_action": "Add peers manually.",
                    "local_file": "data/peers.csv",
                },
                {
                    "dataset": "earnings",
                    "ticker": "",
                    "status": "manual_only",
                    "reason": "Local CSV file is not present.",
                    "recommended_action": "Add earnings manually.",
                    "local_file": "data/earnings.csv",
                },
                {
                    "dataset": "smh_holdings",
                    "ticker": "",
                    "status": "partial",
                    "reason": "Remote page unavailable.",
                    "recommended_action": "Use custom universe fallback.",
                    "local_file": "data/custom_universe.csv or data/imports/universe.csv",
                },
                {
                    "dataset": "sp500_constituents",
                    "ticker": "",
                    "status": "partial",
                    "reason": "Preview before apply.",
                    "recommended_action": "Preview S&P expansion before applying.",
                    "local_file": "data/imports/universe.csv",
                },
                {
                    "dataset": "nasdaq_symbols",
                    "ticker": "",
                    "status": "partial",
                    "reason": "Broad preview only.",
                    "recommended_action": "Preview broad universe before applying.",
                    "local_file": "data/imports/universe.csv",
                },
            ]
        ),
        data_quality=pd.DataFrame(),
        command_bundles=pd.DataFrame(
            [
                {
                    "lane": "fundamentals",
                    "scope": "broader_queue",
                    "bundle_name": "SEC Fundamentals Bundle (Broader Queue)",
                    "runbook_shortcut_command": "make runbook-fundamentals-broader",
                },
                {
                    "lane": "peers",
                    "scope": "broader_queue",
                    "bundle_name": "Peer Mapping Bundle (Broader Queue)",
                    "runbook_shortcut_command": "make runbook-peers-broader",
                },
            ]
        ),
    )

    fundamentals_row = next(row for row in rows if row.action_type == "fundamentals" and not row.ticker)
    assert fundamentals_row.focus_command == "make runbook-fundamentals-broader"
    assert fundamentals_row.example_command == "make runbook-fundamentals-broader"

    peers_row = next(row for row in rows if row.action_type == "peers" and not row.ticker)
    assert peers_row.focus_command == "make runbook-peers-broader"
    assert peers_row.example_command == "make runbook-peers-broader"
    assert peers_row.target_file == "data/imports/peers.csv"
    assert peers_row.source_file == "data/imports/peers.csv"

    earnings_row = next(row for row in rows if row.action_type == "earnings" and not row.ticker)
    assert earnings_row.focus_command == "make templates"
    assert earnings_row.example_command == "make templates"
    assert earnings_row.target_file == "data/imports/earnings.csv"
    assert earnings_row.source_file == "data/imports/earnings.csv"

    smh_row = next(row for row in rows if row.action_type == "smh_holdings" and not row.ticker)
    assert smh_row.focus_command == "make templates"
    assert smh_row.example_command == "make templates"
    assert smh_row.target_file == "data/custom_universe.csv"
    assert smh_row.source_file == "data/custom_universe.csv"

    sp500_row = next(row for row in rows if row.action_type == "sp500_constituents" and not row.ticker)
    assert sp500_row.focus_command == "make universe-preview"
    assert sp500_row.example_command == "python3 -m src.universe_builder --preview --preset sp500_smh --max-tickers 50"

    nasdaq_row = next(row for row in rows if row.action_type == "nasdaq_symbols" and not row.ticker)
    assert nasdaq_row.focus_command == "make universe-preview"
    assert nasdaq_row.example_command == "python3 -m src.universe_builder --preview --sources sp500,nasdaq,smh,holdings --max-tickers 100"


def test_action_queue_prefers_explicit_data_gap_commands_when_present():
    rows = build_action_queue_rows(
        price_status=pd.DataFrame(),
        price_worklist=pd.DataFrame(),
        onboarding_actions=pd.DataFrame(),
        data_gaps=pd.DataFrame(
            [
                {
                    "dataset": "fundamentals",
                    "ticker": "NVDA",
                    "status": "partial",
                    "reason": "No local fundamentals row was found for NVDA.",
                    "required_for": "valuation",
                    "recommended_action": "Start with make status, then follow the printed fundamentals focus or runbook path.",
                    "focus_command": "make focus-fundamentals TICKER=NVDA",
                    "example_command": "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA",
                    "local_file": "data/fundamentals.csv",
                    "source_name": "Local fundamentals CSV / SEC Companyfacts staging",
                }
            ]
        ),
        data_quality=pd.DataFrame(),
        command_bundles=pd.DataFrame(),
    )

    row = rows[0]
    assert row.focus_command == "make focus-fundamentals TICKER=NVDA"
    assert row.example_command == "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA"


def test_action_queue_derives_ticker_gap_example_command_from_focus_command():
    rows = build_action_queue_rows(
        price_status=pd.DataFrame(),
        price_worklist=pd.DataFrame(),
        onboarding_actions=pd.DataFrame(),
        data_gaps=pd.DataFrame(
            [
                {
                    "dataset": "fundamentals",
                    "ticker": "NVDA",
                    "status": "partial",
                    "reason": "No local fundamentals row was found for NVDA.",
                    "recommended_action": "Start with make status, then follow the printed fundamentals focus or runbook path.",
                    "local_file": "data/fundamentals.csv",
                }
            ]
        ),
        data_quality=pd.DataFrame(),
        command_bundles=pd.DataFrame(),
    )

    row = rows[0]
    assert row.focus_command == "make focus-fundamentals TICKER=NVDA"
    assert row.example_command == "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA"


def test_action_queue_uses_status_for_unknown_global_gap_fallback():
    rows = build_action_queue_rows(
        price_status=pd.DataFrame(),
        price_worklist=pd.DataFrame(),
        onboarding_actions=pd.DataFrame(),
        data_gaps=pd.DataFrame(
            [
                {
                    "dataset": "local_outputs",
                    "ticker": "",
                    "status": "partial",
                    "reason": "Generated outputs need a refresh.",
                    "recommended_action": "Refresh the operator outputs.",
                    "local_file": "outputs/final_watchlist.csv",
                }
            ]
        ),
        data_quality=pd.DataFrame(),
        command_bundles=pd.DataFrame(),
    )

    row = rows[0]
    assert row.focus_command == "make status"
    assert row.example_command == "make status"


def test_action_queue_uses_validate_first_fundamentals_global_gap_fallback_without_bundles():
    rows = build_action_queue_rows(
        price_status=pd.DataFrame(),
        price_worklist=pd.DataFrame(),
        onboarding_actions=pd.DataFrame(),
        data_gaps=pd.DataFrame(
            [
                {
                    "dataset": "fundamentals",
                    "ticker": "",
                    "status": "partial",
                    "reason": "Staged fundamentals need follow-through.",
                    "recommended_action": "Run staged fundamentals follow-through.",
                    "local_file": "data/imports/fundamentals.csv",
                }
            ]
        ),
        data_quality=pd.DataFrame(),
        command_bundles=pd.DataFrame(),
    )

    row = rows[0]
    assert row.focus_command == "make sec-validate"
    assert row.example_command == "make sec-validate"


def test_action_queue_payload_refreshes_stale_data_gap_actions(tmp_path: Path):
    outputs_dir = tmp_path / "outputs"
    data_dir = tmp_path / "data"
    outputs_dir.mkdir()
    data_dir.mkdir()
    pd.DataFrame(
        [
            {"date": "2026-01-01", "ticker": "NVDA", "adj_close": 100, "volume": 1000},
        ]
    ).to_csv(data_dir / "prices.csv", index=False)
    pd.DataFrame(
        [
            {"ticker": "NVDA", "theme": "AI", "sectoretf": "SMH", "defaultpurpose": "Momentum Leader", "marketcapbucket": "Large", "notes": "fixture"},
        ]
    ).to_csv(data_dir / "universe.csv", index=False)
    pd.DataFrame([{"ticker": "NVDA", "primarypurpose": "Momentum Leader"}]).to_csv(data_dir / "holdings.csv", index=False)
    pd.DataFrame([{"ticker": "NVDA", "theme": "AI"}]).to_csv(data_dir / "fundamentals.csv", index=False)
    (outputs_dir / "data_onboarding_actions.csv").write_text(
        "priority,ticker,dataset,status,reason,recommended_action,target_file,focus_command,example_command\n",
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "dataset": "earnings",
                "ticker": "",
                "status": "manual_only",
                "reason": "Local CSV file is not present.",
                "required_for": "earnings summary",
                "recommended_action": "Add data/imports/earnings.csv manually if you want local earnings coverage.",
                "local_file": "data/earnings.csv",
                "source_name": "Manual local earnings CSV",
            },
            {
                "dataset": "analyst_estimates",
                "ticker": "",
                "status": "manual_only",
                "reason": "Local CSV file is not present.",
                "required_for": "analyst estimate summary",
                "recommended_action": "Add data/imports/analyst_estimates.csv manually if you want estimate coverage.",
                "local_file": "data/analyst_estimates.csv",
                "source_name": "Manual local analyst estimates CSV",
            },
        ]
    ).to_csv(outputs_dir / "data_gap_report.csv", index=False)
    pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "DataQualityScore": 20,
                "ReadinessStatus": "Needs Enrichment",
                "MomentumReady": True,
                "MonthlyPicksReady": True,
                "DCFReady": False,
                "PeerReady": False,
                "EarningsAvailable": False,
                "AnalystEstimatesAvailable": False,
                "PriceHistoryDays": 1,
                "MissingDataFields": "DCF inputs;peer mapping",
                "NextBestAction": (
                    "Run make focus-fundamentals TICKER=NVDA, or stage explicit local fundamentals with "
                    "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA."
                ),
                "Reason": "Missing DCF and peer coverage.",
            }
        ]
    ).to_csv(outputs_dir / "data_quality_wizard.csv", index=False)

    payload = build_action_queue_payload(tmp_path, data_dir=data_dir, output_dir=outputs_dir)

    earnings_row = next(row for row in payload["action_queue"] if row["action_type"] == "earnings" and not row["ticker"])
    analyst_row = next(row for row in payload["action_queue"] if row["action_type"] == "analyst_estimates" and not row["ticker"])
    assert earnings_row["focus_command"] == "make templates"
    assert earnings_row["recommended_action"].startswith("Run make templates")
    assert analyst_row["focus_command"] == "make templates"
    assert analyst_row["recommended_action"].startswith("Run make templates")


def test_action_queue_payload_refreshes_stale_smh_onboarding_row(tmp_path: Path):
    outputs_dir = tmp_path / "outputs"
    data_dir = tmp_path / "data"
    outputs_dir.mkdir()
    data_dir.mkdir()
    (tmp_path / "config.yaml").write_text("{}", encoding="utf-8")
    pd.DataFrame(
        [
            {"date": "2026-01-01", "ticker": "NVDA", "adj_close": 100, "volume": 1000},
        ]
    ).to_csv(data_dir / "prices.csv", index=False)
    pd.DataFrame(
        [
            {"ticker": "NVDA", "theme": "AI", "sectoretf": "SMH", "defaultpurpose": "Momentum Leader", "marketcapbucket": "Large", "notes": "fixture"},
        ]
    ).to_csv(data_dir / "universe.csv", index=False)
    pd.DataFrame([{"ticker": "NVDA", "primarypurpose": "Momentum Leader"}]).to_csv(data_dir / "holdings.csv", index=False)
    (outputs_dir / "data_onboarding_actions.csv").write_text(
        "priority,ticker,dataset,status,reason,recommended_action,target_file,focus_command,example_command\n"
        "6,,smh_holdings,manual_fallback_available,SMH remote holdings can be unavailable because of redirect/cookie/location handling.,Use data/custom_universe.csv if the SMH source is unavailable.,data/custom_universe.csv,,python3 -m src.data_onboarding --write-templates\n",
        encoding="utf-8",
    )

    payload = build_action_queue_payload(tmp_path, data_dir=data_dir, output_dir=outputs_dir)

    smh_row = next(row for row in payload["action_queue"] if row["action_type"] == "smh_holdings")
    assert smh_row["focus_command"] == "make templates"
    assert smh_row["example_command"] == "make templates"
    assert "make templates" in smh_row["recommended_action"]
    assert "data/custom_universe.csv" in smh_row["recommended_action"]


def test_action_queue_merges_price_status_with_price_worklist_guidance():
    rows = build_action_queue_rows(
        price_status=pd.DataFrame(
            [
                {
                    "ticker": "AMD",
                    "status": "parse_error",
                    "recommended_action": "Retry later or use staged manual prices in data/imports/prices.csv.",
                    "error_message": "AMD: update failed (parse error).",
                }
            ]
        ),
        price_worklist=pd.DataFrame(
            [
                {
                    "ticker": "AMD",
                    "recommended_action": "Run python3 -m src.data_update --tickers AMD, or normalize verified downloaded OHLCV files into data/imports/prices.csv.",
                    "example_command": "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
                    "safe_next_step": "Run make price-validate and make price-preview before make price-apply; do not fabricate missing history.",
                }
            ]
        ),
        onboarding_actions=pd.DataFrame(),
        data_gaps=pd.DataFrame(),
        data_quality=pd.DataFrame(),
    )

    row = rows[0]
    assert row.action_type == "prices"
    assert "make focus-price TICKER=AMD" in row.recommended_action
    assert "normalize verified downloaded ohlcv files" in row.recommended_action.lower()
    assert row.example_command == "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual"
    assert "price-validate" in row.reason.lower()


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
    pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "DataQualityScore": 20,
                "ReadinessStatus": "Needs Enrichment",
                "MomentumReady": True,
                "MonthlyPicksReady": True,
                "DCFReady": False,
                "PeerReady": False,
                "EarningsAvailable": False,
                "AnalystEstimatesAvailable": False,
                "PriceHistoryDays": 40,
                "MissingDataFields": "DCF inputs;peer mapping",
                "NextBestAction": (
                    "Run make focus-fundamentals TICKER=NVDA, or stage explicit local fundamentals with "
                    "python3 -m src.stock_report --sec-stage-fundamentals --tickers NVDA."
                ),
                "Reason": "Missing DCF and peer coverage.",
            }
        ]
    ).to_csv(outputs_dir / "data_quality_wizard.csv", index=False)

    payload = write_action_queue_output(tmp_path, data_dir=data_dir, output_dir=outputs_dir)

    queue_path = Path(payload["queue_path"])
    assert queue_path.exists()
    frame = pd.read_csv(queue_path)
    assert list(frame.columns)
    assert {"priority", "action_type", "recommended_action", "reason"} <= set(frame.columns)
    assert "focus_command" in frame.columns
    assert frame.iloc[0]["action_type"] == "prices"


def test_action_queue_payload_normalizes_legacy_parse_error_reason_from_price_status(tmp_path: Path):
    outputs_dir = tmp_path / "outputs"
    data_dir = tmp_path / "data"
    outputs_dir.mkdir()
    data_dir.mkdir()
    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(), encoding="utf-8")
    pd.DataFrame(
        [
            {"ticker": "META", "theme": "AI", "sectoretf": "XLK", "defaultpurpose": "Core Compounder"},
        ]
    ).to_csv(data_dir / "universe.csv", index=False)
    pd.DataFrame(columns=["ticker", "shares", "primarypurpose"]).to_csv(data_dir / "holdings.csv", index=False)
    (outputs_dir / "data_onboarding_actions.csv").write_text(
        "priority,ticker,dataset,status,reason,recommended_action,target_file,focus_command,example_command\n",
        encoding="utf-8",
    )
    (outputs_dir / "data_gap_report.csv").write_text(
        "dataset,ticker,status,reason,required_for,recommended_action,local_file,source_name\n",
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "Ticker": "META",
                "DataQualityScore": 0,
                "ReadinessStatus": "Needs Price Data",
                "MomentumReady": False,
                "MonthlyPicksReady": False,
                "DCFReady": False,
                "PeerReady": False,
                "EarningsAvailable": False,
                "AnalystEstimatesAvailable": False,
                "PriceHistoryDays": 0,
                "MissingDataFields": "prices",
                "NextBestAction": (
                    "Run make focus-price TICKER=META, or run python3 -m src.data_update --tickers META and "
                    "normalize verified downloaded OHLCV files into data/imports/prices.csv."
                ),
                "FocusCommand": "make focus-price TICKER=META",
                "ExampleCommand": "make price-normalize INPUT=data/raw/prices/META.csv TICKER=META SOURCE=yahoo_manual",
                "Reason": "META has 0 local price rows.",
            }
        ]
    ).to_csv(outputs_dir / "data_quality_wizard.csv", index=False)
    (outputs_dir / "price_update_status.csv").write_text(
        "run_timestamp,ticker,requested_start,requested_end,provider,status,rows_fetched,rows_merged,error_category,error_message,fallback_used,recommended_action\n"
        "2026-05-21T00:00:00Z,META,,2026-05-21,stooq,parse_error,0,0,parse_error,\"META: update failed (Error tokenizing data. C error: Expected 1 fields in line 6, saw 2\n)\",false,Retry later or use staged manual prices in data/imports/prices.csv.\n",
        encoding="utf-8",
    )

    payload = build_action_queue_payload(tmp_path, data_dir=data_dir, output_dir=outputs_dir)

    price_row = next(row for row in payload["action_queue"] if row["action_type"] == "prices")
    assert price_row["ticker"] == "META"
    assert price_row["focus_command"] == "make focus-price TICKER=META"
    assert "provider rows could not be parsed cleanly" in price_row["reason"]
    assert "Expected 1 fields in line 6, saw 2" in price_row["reason"]
