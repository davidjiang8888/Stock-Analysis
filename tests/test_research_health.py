from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

from src.research_health import (
    _filter_research_health_outputs,
    _filter_research_health_warnings,
    build_correlation_risk,
    build_data_quality_wizard,
    build_liquidity_risk,
    main,
    run,
)


def _price_frame() -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    rows = []
    for index, date in enumerate(dates):
        nvda_close = 100 + index
        msft_close = 200 + index * 1.8
        thin_close = 20 + index * 0.1
        rows.extend(
            [
                {"date": date, "ticker": "NVDA", "close": nvda_close, "volume": 2_000_000},
                {"date": date, "ticker": "MSFT", "close": msft_close, "volume": 1_800_000},
                {"date": date, "ticker": "THIN", "close": thin_close, "volume": 1_000},
            ]
        )
    return pd.DataFrame(rows)


def test_data_quality_wizard_scores_readiness_and_reasons():
    coverage = [
        {
            "ticker": "NVDA",
            "has_prices": True,
            "price_history_days": 80,
            "has_fundamentals": True,
            "dcf_ready": True,
            "has_peer_mapping": True,
            "peer_ready": True,
            "has_earnings": False,
            "has_analyst_estimates": False,
            "usable_for_momentum": True,
            "usable_for_monthly_picks": True,
            "next_best_action": "Optional: add earnings manually.",
        },
        {
            "ticker": "AMD",
            "has_prices": False,
            "price_history_days": 0,
            "has_fundamentals": False,
            "dcf_ready": False,
            "has_peer_mapping": False,
            "peer_ready": False,
            "has_earnings": False,
            "has_analyst_estimates": False,
            "usable_for_momentum": False,
            "usable_for_monthly_picks": False,
            "next_best_action": (
                "Run make price-refresh TICKERS=AMD; if the free refresh path fails, add verified rows to "
                "data/imports/prices.csv and run validate/preview/apply."
            ),
        },
    ]

    frame = build_data_quality_wizard(coverage)

    assert list(frame["Ticker"]) == ["NVDA", "AMD"]
    assert frame.loc[frame["Ticker"] == "NVDA", "ReadinessStatus"].iloc[0] == "Research Ready"
    assert frame.loc[frame["Ticker"] == "AMD", "ReadinessStatus"].iloc[0] == "Needs Price Data"
    assert frame["Reason"].fillna("").str.len().gt(0).all()
    assert "prices" in frame.loc[frame["Ticker"] == "AMD", "MissingDataFields"].iloc[0]
    assert "make focus-price TICKER=AMD" in frame.loc[frame["Ticker"] == "AMD", "NextBestAction"].iloc[0]
    assert "normalize verified downloaded OHLCV files into data/imports/prices.csv" in frame.loc[
        frame["Ticker"] == "AMD", "NextBestAction"
    ].iloc[0]
    assert frame.loc[frame["Ticker"] == "AMD", "FocusCommand"].iloc[0] == "make focus-price TICKER=AMD"
    assert "make price-normalize" in frame.loc[frame["Ticker"] == "AMD", "ExampleCommand"].iloc[0]


def test_data_quality_wizard_uses_staged_peer_follow_through_when_mappings_already_exist():
    coverage = [
        {
            "ticker": "NVDA",
            "has_prices": True,
            "price_history_days": 80,
            "has_fundamentals": True,
            "dcf_ready": True,
            "has_peer_mapping": True,
            "peer_ready": False,
            "has_earnings": False,
            "has_analyst_estimates": False,
            "usable_for_momentum": True,
            "usable_for_monthly_picks": True,
            "next_best_action": (
                "Run make imports-validate, then make imports-preview, then make imports-apply, then make status "
                "to confirm the live local peer mappings."
            ),
            "focus_command": "make imports-validate",
            "example_command": "make imports-preview",
        }
    ]

    frame = build_data_quality_wizard(coverage)

    assert frame.loc[0, "FocusCommand"] == "make imports-validate"
    assert frame.loc[0, "ExampleCommand"] == "make imports-preview"
    assert "make imports-apply" in frame.loc[0, "NextBestAction"]


def test_data_quality_wizard_normalizes_stale_peer_example_commands():
    coverage = [
        {
            "ticker": "NVDA",
            "has_prices": True,
            "price_history_days": 80,
            "has_fundamentals": True,
            "dcf_ready": True,
            "has_peer_mapping": True,
            "peer_ready": False,
            "has_earnings": False,
            "has_analyst_estimates": False,
            "usable_for_momentum": True,
            "usable_for_monthly_picks": True,
            "next_best_action": (
                "Run make imports-validate, then make imports-preview, then make imports-apply, then make status "
                "to confirm the live local peer mappings."
            ),
            "focus_command": "make imports-validate",
            "example_command": "make status",
        },
        {
            "ticker": "AMD",
            "has_prices": True,
            "price_history_days": 80,
            "has_fundamentals": True,
            "dcf_ready": True,
            "has_peer_mapping": True,
            "peer_ready": False,
            "has_earnings": False,
            "has_analyst_estimates": False,
            "usable_for_momentum": True,
            "usable_for_monthly_picks": True,
            "next_best_action": (
                "Run make focus-peers TICKER=AMD, then add peer fundamentals/prices through the staged local import "
                "workflows so peer-relative valuation can calculate transparently."
            ),
            "focus_command": "make focus-peers TICKER=AMD",
            "example_command": "make onboarding",
        },
    ]

    frame = build_data_quality_wizard(coverage)

    nvda = frame.loc[frame["Ticker"] == "NVDA"].iloc[0]
    amd = frame.loc[frame["Ticker"] == "AMD"].iloc[0]

    assert nvda["FocusCommand"] == "make imports-validate"
    assert nvda["ExampleCommand"] == "make imports-preview"
    assert amd["FocusCommand"] == "make focus-peers TICKER=AMD"
    assert amd["ExampleCommand"] == "make templates"


def test_data_quality_wizard_normalizes_legacy_operator_example_commands():
    coverage = [
        {
            "ticker": "NVDA",
            "has_prices": True,
            "price_history_days": 80,
            "has_fundamentals": False,
            "dcf_ready": False,
            "has_peer_mapping": False,
            "peer_ready": False,
            "has_earnings": False,
            "has_analyst_estimates": False,
            "usable_for_momentum": True,
            "usable_for_monthly_picks": True,
            "next_best_action": "Run make focus-fundamentals TICKER=NVDA.",
            "focus_command": "make focus-fundamentals TICKER=NVDA",
            "example_command": "SEC_USER_AGENT='Name email@example.com' make sec-stage TICKERS=nvda, msft",
            "missing_required_for_dcf": "free_cash_flow",
            "missing_required_for_peer_relative": "peer mapping",
        },
        {
            "ticker": "AMD",
            "has_prices": False,
            "price_history_days": 0,
            "has_fundamentals": False,
            "dcf_ready": False,
            "has_peer_mapping": False,
            "peer_ready": False,
            "has_earnings": False,
            "has_analyst_estimates": False,
            "usable_for_momentum": False,
            "usable_for_monthly_picks": False,
            "next_best_action": "Run make focus-price TICKER=AMD.",
            "focus_command": "make focus-price TICKER=AMD",
            "example_command": "python3 -m src.data_update --tickers amd, nvda",
            "missing_required_for_momentum": "prices",
            "missing_required_for_dcf": "prices",
            "missing_required_for_peer_relative": "prices",
        },
    ]

    frame = build_data_quality_wizard(coverage)

    nvda = frame.loc[frame["Ticker"] == "NVDA"].iloc[0]
    amd = frame.loc[frame["Ticker"] == "AMD"].iloc[0]

    assert nvda["ExampleCommand"] == "make sec-stage TICKERS=NVDA"
    assert amd["ExampleCommand"] == "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual"


def test_data_quality_wizard_normalizes_stale_action_text():
    coverage = [
        {
            "ticker": "NVDA",
            "has_prices": True,
            "price_history_days": 80,
            "has_fundamentals": False,
            "dcf_ready": False,
            "has_peer_mapping": False,
            "peer_ready": False,
            "has_earnings": False,
            "has_analyst_estimates": False,
            "usable_for_momentum": True,
            "usable_for_monthly_picks": True,
            "next_best_action": "Run make focus-fundamentals TICKER=NVDA.",
            "focus_command": "make focus-fundamentals TICKER=NVDA",
            "example_command": "make sec-stage TICKERS=NVDA",
            "missing_required_for_dcf": "free_cash_flow",
            "missing_required_for_peer_relative": "peer mapping",
        },
        {
            "ticker": "AMD",
            "has_prices": False,
            "price_history_days": 0,
            "has_fundamentals": False,
            "dcf_ready": False,
            "has_peer_mapping": False,
            "peer_ready": False,
            "has_earnings": False,
            "has_analyst_estimates": False,
            "usable_for_momentum": False,
            "usable_for_monthly_picks": False,
            "next_best_action": "Run make focus-price TICKER=AMD, or run python3 -m src.data_update --tickers AMD and normalize verified downloaded OHLCV files into data/imports/prices.csv.",
            "focus_command": "make focus-price TICKER=AMD",
            "example_command": "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual",
            "missing_required_for_momentum": "prices",
            "missing_required_for_dcf": "prices",
            "missing_required_for_peer_relative": "prices",
        },
        {
            "ticker": "TSLA",
            "has_prices": True,
            "price_history_days": 90,
            "has_fundamentals": True,
            "dcf_ready": True,
            "has_peer_mapping": False,
            "peer_ready": False,
            "has_earnings": False,
            "has_analyst_estimates": False,
            "usable_for_momentum": True,
            "usable_for_monthly_picks": True,
            "next_best_action": "Run make focus-peers TICKER=TSLA.",
            "focus_command": "make focus-peers TICKER=TSLA",
            "example_command": "make templates",
            "missing_required_for_peer_relative": "peer mapping",
        },
    ]

    frame = build_data_quality_wizard(coverage)

    nvda = frame.loc[frame["Ticker"] == "NVDA"].iloc[0]
    amd = frame.loc[frame["Ticker"] == "AMD"].iloc[0]
    tsla = frame.loc[frame["Ticker"] == "TSLA"].iloc[0]

    assert "make sec-stage TICKERS=NVDA" in nvda["NextBestAction"]
    assert "make price-refresh TICKERS=AMD" in amd["NextBestAction"]
    assert "python3 -m src.data_update --tickers AMD" not in amd["NextBestAction"]
    assert "run make templates" in tsla["NextBestAction"]


def test_data_quality_wizard_normalizes_stale_enrichment_actions():
    coverage = [
        {
            "ticker": "NVDA",
            "has_prices": True,
            "price_history_days": 80,
            "has_fundamentals": False,
            "dcf_ready": False,
            "has_peer_mapping": True,
            "peer_ready": False,
            "has_earnings": False,
            "has_analyst_estimates": False,
            "usable_for_momentum": True,
            "usable_for_monthly_picks": True,
            "next_best_action": "Run SEC staging for fundamentals: make sec-stage TICKERS=NVDA",
        },
        {
            "ticker": "AMD",
            "has_prices": True,
            "price_history_days": 80,
            "has_fundamentals": True,
            "dcf_ready": True,
            "has_peer_mapping": False,
            "peer_ready": False,
            "has_earnings": False,
            "has_analyst_estimates": False,
            "usable_for_momentum": True,
            "usable_for_monthly_picks": True,
            "next_best_action": "Add data/imports/peers.csv manually with real peer mappings.",
        },
    ]

    frame = build_data_quality_wizard(coverage)

    nvda = frame.loc[frame["Ticker"] == "NVDA"].iloc[0]
    amd = frame.loc[frame["Ticker"] == "AMD"].iloc[0]

    assert nvda["ReadinessStatus"] == "Partial Coverage"
    assert nvda["FocusCommand"] == "make focus-fundamentals TICKER=NVDA"
    assert "make focus-fundamentals TICKER=NVDA" in nvda["NextBestAction"]
    assert "make sec-stage TICKERS=NVDA" in nvda["ExampleCommand"]

    assert amd["ReadinessStatus"] == "Partial Coverage"
    assert amd["FocusCommand"] == "make focus-peers TICKER=AMD"
    assert "make focus-peers TICKER=AMD" in amd["NextBestAction"]
    assert amd["ExampleCommand"] == "make templates"


def test_data_quality_wizard_routes_etfs_away_from_company_dcf():
    coverage = [
        {
            "ticker": "QQQ",
            "asset_type": "etf",
            "has_prices": True,
            "price_history_days": 80,
            "has_fundamentals": False,
            "dcf_ready": False,
            "has_peer_mapping": False,
            "peer_ready": False,
            "has_earnings": False,
            "has_analyst_estimates": False,
            "usable_for_momentum": True,
            "usable_for_monthly_picks": True,
            "next_best_action": "QQQ is etf; skip company DCF and use market/risk monitoring instead.",
        },
    ]

    frame = build_data_quality_wizard(coverage)
    qqq = frame.loc[frame["Ticker"] == "QQQ"].iloc[0]

    assert qqq["ReadinessStatus"] == "Partial Coverage"
    assert "company DCF excluded for etf" in qqq["MissingDataFields"]
    assert "fundamentals" not in qqq["MissingDataFields"]
    assert qqq["FocusCommand"] == "make focus-peers TICKER=QQQ"
    assert qqq["ExampleCommand"] == "make templates"
    assert "make focus-peers TICKER=QQQ" in qqq["NextBestAction"]
    assert "make sec-stage" not in qqq["NextBestAction"]


def test_data_quality_wizard_preserves_staged_fundamentals_follow_through():
    coverage = [
        {
            "ticker": "NVDA",
            "has_prices": True,
            "price_history_days": 80,
            "has_fundamentals": False,
            "dcf_ready": False,
            "has_peer_mapping": False,
            "peer_ready": False,
            "has_earnings": False,
            "has_analyst_estimates": False,
            "usable_for_momentum": True,
            "usable_for_monthly_picks": True,
            "missing_required_for_dcf": "staged fundamentals still need validate/preview/apply",
            "next_best_action": (
                "Run make imports-validate, then make imports-preview, then make imports-apply, then make status "
                "to confirm the live local fundamentals and DCF inputs."
            ),
            "focus_command": "make imports-validate",
            "example_command": "make status",
        }
    ]

    frame = build_data_quality_wizard(coverage)

    nvda = frame.loc[frame["Ticker"] == "NVDA"].iloc[0]

    assert nvda["FocusCommand"] == "make imports-validate"
    assert nvda["ExampleCommand"] == "make imports-preview"
    assert "make imports-apply" in nvda["NextBestAction"]


def test_liquidity_risk_calculates_context_without_recommendations():
    frame = build_liquidity_risk(_price_frame(), tickers=["NVDA", "THIN", "MISSING"])

    nvda = frame.loc[frame["Ticker"] == "NVDA"].iloc[0]
    thin = frame.loc[frame["Ticker"] == "THIN"].iloc[0]
    missing = frame.loc[frame["Ticker"] == "MISSING"].iloc[0]

    assert nvda["LiquidityStatus"] == "Liquid"
    assert thin["LiquidityStatus"] == "Thin / Needs Review"
    assert missing["LiquidityStatus"] == "Insufficient Price Data"
    assert nvda["LiquidityScore"] >= thin["LiquidityScore"]
    assert "local close and volume" in nvda["LiquidityInputsUsed"]
    assert "bid-ask spread" in nvda["LiquidityBlindSpots"]
    assert frame["Reason"].str.contains("trade", case=False).sum() == 0


def test_correlation_risk_reports_high_comovement_and_insufficient_overlap():
    frame = build_correlation_risk(_price_frame(), tickers=["NVDA", "MSFT", "MISSING"], min_overlap_days=20)

    nvda = frame.loc[frame["Ticker"] == "NVDA"].iloc[0]
    missing = frame.loc[frame["Ticker"] == "MISSING"].iloc[0]

    assert nvda["CorrelationStatus"] == "High Co-movement"
    assert nvda["CorrelationMethod"] == "Pearson"
    assert nvda["ReturnType"] == "daily_pct_return"
    assert nvda["MostCorrelatedTicker"] == "MSFT"
    assert nvda["OverlapDays"] >= 20
    assert missing["CorrelationStatus"] == "Insufficient Data"
    assert "not a trade instruction" in nvda["Reason"]


def test_research_health_run_writes_csv_outputs(tmp_path: Path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "outputs"
    data_dir.mkdir()
    output_dir.mkdir()
    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(), encoding="utf-8")
    (data_dir / "prices.csv").write_text(_price_frame().to_csv(index=False), encoding="utf-8")
    (data_dir / "universe.csv").write_text(
        "Ticker,Theme,SectorETF,DefaultPurpose,MarketCapBucket,Notes\n"
        "NVDA,AI,SMH,Momentum Leader,Large,\n"
        "MSFT,Software,QQQ,Core Compounder,Large,\n",
        encoding="utf-8",
    )
    (data_dir / "holdings.csv").write_text(
        "Ticker,Shares,CostBasis,PositionPercent,PrimaryPurpose,SecondaryTags,OriginalThesis,MaxPositionPercent,InvalidationOverride\n",
        encoding="utf-8",
    )
    (data_dir / "theme_map.csv").write_text("Theme,ETF,Description\nAI,SMH,Semiconductors\nSoftware,QQQ,Software\n", encoding="utf-8")
    (data_dir / "fundamentals.csv").write_text("ticker,free_cash_flow,shares_outstanding\nNVDA,1000000,100000\n", encoding="utf-8")

    result = run(tmp_path, data_dir=data_dir, output_dir=output_dir)

    assert set(result["files"]) == {"data_quality_wizard", "liquidity_risk", "correlation_risk"}
    for path in result["files"].values():
        assert path.exists()
        frame = pd.read_csv(path)
        assert "Reason" in frame.columns
        assert frame["Reason"].fillna("").str.len().gt(0).all()


def test_filter_research_health_outputs_respects_ticker_slice():
    outputs = {
        "data_quality_wizard": pd.DataFrame(
            [
                {"Ticker": "AMD", "DataQualityScore": 10},
                {"Ticker": "NVDA", "DataQualityScore": 90},
            ]
        ),
        "liquidity_risk": pd.DataFrame(
            [
                {"Ticker": "AMD", "LiquidityStatus": "Thin / Needs Review"},
                {"Ticker": "NVDA", "LiquidityStatus": "Liquid"},
            ]
        ),
        "correlation_risk": pd.DataFrame(
            [
                {"Ticker": "AMD", "CorrelationStatus": "Insufficient Data"},
                {"Ticker": "NVDA", "CorrelationStatus": "Moderate"},
            ]
        ),
    }

    filtered = _filter_research_health_outputs(outputs, ["nvda"])

    assert list(filtered["data_quality_wizard"]["Ticker"]) == ["NVDA"]
    assert list(filtered["liquidity_risk"]["Ticker"]) == ["NVDA"]
    assert list(filtered["correlation_risk"]["Ticker"]) == ["NVDA"]


def test_filter_research_health_warnings_respects_ticker_slice():
    warnings = [
        "Missing OHLCV data for AMD",
        "Missing OHLCV data for NVDA",
        "General loader warning",
    ]

    filtered = _filter_research_health_warnings(warnings, ["nvda"])

    assert filtered == ["Missing OHLCV data for NVDA", "General loader warning"]


def test_research_health_cli_check_uses_read_only_summary_wording(tmp_path: Path, capsys):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "outputs"
    data_dir.mkdir()
    output_dir.mkdir()
    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(), encoding="utf-8")
    (data_dir / "prices.csv").write_text(_price_frame().to_csv(index=False), encoding="utf-8")
    (data_dir / "universe.csv").write_text(
        "Ticker,Theme,SectorETF,DefaultPurpose,MarketCapBucket,Notes\n"
        "NVDA,AI,SMH,Momentum Leader,Large,\n",
        encoding="utf-8",
    )
    (data_dir / "holdings.csv").write_text(
        "Ticker,Shares,CostBasis,PositionPercent,PrimaryPurpose,SecondaryTags,OriginalThesis,MaxPositionPercent,InvalidationOverride\n",
        encoding="utf-8",
    )
    (data_dir / "theme_map.csv").write_text("Theme,ETF,Description\nAI,SMH,Semiconductors\n", encoding="utf-8")
    (data_dir / "fundamentals.csv").write_text("ticker,free_cash_flow,shares_outstanding\nNVDA,1000000,100000\n", encoding="utf-8")

    argv_before = sys.argv[:]
    sys.argv = ["python", "--project-root", str(tmp_path), "--check", "--top-n", "1"]
    try:
        main()
        output = capsys.readouterr().out.lower()
    finally:
        sys.argv = argv_before

    assert "research health summary:" in output
    assert "generated research health outputs:" not in output
