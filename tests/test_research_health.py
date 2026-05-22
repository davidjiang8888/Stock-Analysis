from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.research_health import (
    build_correlation_risk,
    build_data_quality_wizard,
    build_liquidity_risk,
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
                "Run make focus-price TICKER=AMD, or run python3 -m src.data_update --tickers AMD and "
                "normalize verified downloaded OHLCV files into data/imports/prices.csv."
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


def test_liquidity_risk_calculates_context_without_recommendations():
    frame = build_liquidity_risk(_price_frame(), tickers=["NVDA", "THIN", "MISSING"])

    nvda = frame.loc[frame["Ticker"] == "NVDA"].iloc[0]
    thin = frame.loc[frame["Ticker"] == "THIN"].iloc[0]
    missing = frame.loc[frame["Ticker"] == "MISSING"].iloc[0]

    assert nvda["LiquidityStatus"] == "Liquid"
    assert thin["LiquidityStatus"] == "Thin / Needs Review"
    assert missing["LiquidityStatus"] == "Insufficient Price Data"
    assert frame["Reason"].str.contains("trade", case=False).sum() == 0


def test_correlation_risk_reports_high_comovement_and_insufficient_overlap():
    frame = build_correlation_risk(_price_frame(), tickers=["NVDA", "MSFT", "MISSING"], min_overlap_days=20)

    nvda = frame.loc[frame["Ticker"] == "NVDA"].iloc[0]
    missing = frame.loc[frame["Ticker"] == "MISSING"].iloc[0]

    assert nvda["CorrelationStatus"] == "High Co-movement"
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
