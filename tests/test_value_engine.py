from pathlib import Path

import pandas as pd

from src.config import AppConfig
from src.value_engine import classify_value_row, run


def test_value_engine_flags_insufficient_data_when_fundamentals_missing():
    config = AppConfig.load(Path("config.yaml"))
    snapshot_row = pd.Series(
        {
            "ticker": "META",
            "close": 500.0,
            "sma_50": 480.0,
            "sma_200": 430.0,
            "ema_21": 490.0,
            "relative_return_vs_spy": 0.08,
            "relative_return_vs_qqq": 0.04,
            "relative_return_vs_sector_etf": 0.03,
            "return_3m": 0.12,
        }
    )
    purpose_row = pd.Series({"FinalPrimaryPurpose": "Core Compounder"})
    result = classify_value_row(snapshot_row, purpose_row, pd.Series(dtype=object), config)
    assert result["FinalValueCategory"] == "Insufficient Data"
    assert result["MissingDataFields"] == "fundamentals unavailable"


def test_value_engine_does_not_emit_avoid_when_dcf_is_not_ready():
    config = AppConfig.load(Path("config.yaml"))
    snapshot_row = pd.Series(
        {
            "ticker": "META",
            "close": 440.0,
            "sma_50": 500.0,
            "sma_200": 520.0,
            "ema_21": 460.0,
            "relative_return_vs_spy": -0.10,
            "relative_return_vs_qqq": -0.08,
            "relative_return_vs_sector_etf": -0.05,
            "return_3m": -0.20,
        }
    )
    purpose_row = pd.Series({"FinalPrimaryPurpose": "Core Compounder"})

    result = classify_value_row(snapshot_row, purpose_row, pd.Series(dtype=object), config)

    assert result["ValuationStatus"] == "not_ready"
    assert result["FinalValueCategory"] == "Insufficient Data"
    assert "valuation_status=not_ready" in result["Reason"]
    assert "fundamentals unavailable" in result["MissingDataFields"]


def test_value_engine_identifies_possible_value_trap():
    config = AppConfig.load(Path("config.yaml"))
    snapshot_row = pd.Series(
        {
            "ticker": "TSLA",
            "close": 90.0,
            "sma_50": 100.0,
            "sma_200": 120.0,
            "ema_21": 95.0,
            "relative_return_vs_spy": -0.10,
            "relative_return_vs_qqq": -0.08,
            "relative_return_vs_sector_etf": -0.05,
            "return_3m": -0.20,
        }
    )
    purpose_row = pd.Series({"FinalPrimaryPurpose": "Re-rating / Undervalued"})
    fundamentals_row = pd.Series(
        {
            "revenue_growth": -0.05,
            "revenue": 100_000_000,
            "eps_growth": -0.10,
            "free_cash_flow": -2_000_000,
            "fcf_margin": -0.02,
            "gross_margin": 0.18,
            "operating_margin": 0.03,
            "debt_to_equity": 3.2,
            "pe": 10.0,
            "forward_pe": 9.0,
            "ev_to_sales": 2.0,
            "ev_to_ebitda": 7.0,
            "price_to_fcf": 12.0,
            "fcf_yield": -0.01,
            "shares_outstanding": 10_000_000,
        }
    )
    result = classify_value_row(snapshot_row, purpose_row, fundamentals_row, config)
    assert result["FinalValueCategory"] == "Possible Value Trap"
    assert result["ValueTrapRiskScore"] >= 50


def test_value_engine_stays_conservative_with_partial_fundamentals():
    config = AppConfig.load(Path("config.yaml"))
    snapshot_row = pd.Series(
        {
            "ticker": "AVGO",
            "close": 150.0,
            "sma_50": 145.0,
            "sma_200": 130.0,
            "ema_21": 148.0,
            "relative_return_vs_spy": 0.03,
            "relative_return_vs_qqq": 0.02,
            "relative_return_vs_sector_etf": 0.01,
            "return_3m": 0.08,
        }
    )
    purpose_row = pd.Series({"FinalPrimaryPurpose": "Re-rating / Undervalued"})
    fundamentals_row = pd.Series(
        {
            "revenue_growth": 0.06,
            "eps_growth": 0.08,
            "pe": 18.0,
        }
    )

    result = classify_value_row(snapshot_row, purpose_row, fundamentals_row, config)

    assert result["FinalValueCategory"] == "Insufficient Data"
    assert result["QualityScore"] is not None
    assert result["ValuationScore"] is not None
    assert "too incomplete" in result["Reason"]
    assert "DebtToEquity" in result["MissingDataFields"]


def test_value_engine_uses_peer_discount_when_peer_fundamentals_are_available():
    config = AppConfig.load(Path("config.yaml"))
    snapshot_row = pd.Series(
        {
            "ticker": "ALFA",
            "close": 120.0,
            "sma_50": 115.0,
            "sma_200": 100.0,
            "ema_21": 118.0,
            "relative_return_vs_spy": 0.03,
            "relative_return_vs_qqq": 0.02,
            "relative_return_vs_sector_etf": 0.01,
            "return_3m": 0.05,
        }
    )
    purpose_row = pd.Series({"FinalPrimaryPurpose": "Re-rating / Undervalued"})
    fundamentals_row = pd.Series(
        {
            "revenue_growth": 0.08,
            "eps_growth": 0.10,
            "fcf_margin": 0.15,
            "gross_margin": 0.55,
            "operating_margin": 0.22,
            "debt_to_equity": 0.4,
            "pe": 16.0,
            "forward_pe": 14.0,
            "ev_to_sales": 4.0,
            "ev_to_ebitda": 10.0,
            "price_to_fcf": 18.0,
            "fcf_yield": 0.04,
        }
    )
    peer_rows = pd.DataFrame(
        [
            {"pe": 20.0, "forward_pe": 18.0, "ev_to_sales": 5.0, "ev_to_ebitda": 12.0, "price_to_fcf": 22.0},
            {"pe": 22.0, "forward_pe": 19.0, "ev_to_sales": 6.0, "ev_to_ebitda": 13.0, "price_to_fcf": 24.0},
        ]
    )

    result = classify_value_row(snapshot_row, purpose_row, fundamentals_row, config, peer_rows=peer_rows)

    assert result["PeerCount"] == 2
    assert result["PeerRelativeStatus"] == "Discount vs Peers"
    assert result["RelativeOpportunityScore"] is not None
    assert result["PeerMedianPE"] == 21.0
    assert "discount versus local peers" in result["Reason"]


def test_value_engine_reports_peer_data_unavailable_when_no_peer_rows_exist():
    config = AppConfig.load(Path("config.yaml"))
    snapshot_row = pd.Series(
        {
            "ticker": "NVDA",
            "close": 120.0,
            "sma_50": 115.0,
            "sma_200": 100.0,
            "ema_21": 118.0,
            "relative_return_vs_spy": 0.03,
            "relative_return_vs_qqq": 0.02,
            "relative_return_vs_sector_etf": 0.01,
            "return_3m": 0.05,
        }
    )
    purpose_row = pd.Series({"FinalPrimaryPurpose": "Re-rating / Undervalued"})
    fundamentals_row = pd.Series(
        {
            "revenue_growth": 0.08,
            "eps_growth": 0.10,
            "fcf_margin": 0.15,
            "gross_margin": 0.55,
            "operating_margin": 0.22,
            "debt_to_equity": 0.4,
            "pe": 16.0,
        }
    )

    result = classify_value_row(snapshot_row, purpose_row, fundamentals_row, config, peer_rows=pd.DataFrame())

    assert result["PeerRelativeStatus"] == "Peer Data Unavailable"
    assert result["RelativeOpportunityScore"] is None


def test_value_engine_run_sorts_by_relative_opportunity_when_categories_match():
    config = AppConfig.load(Path("config.yaml"))
    snapshot = pd.DataFrame(
        [
            {
                "ticker": "ALFA",
                "close": 120.0,
                "sma_50": 115.0,
                "sma_200": 100.0,
                "ema_21": 118.0,
                "relative_return_vs_spy": 0.03,
                "relative_return_vs_qqq": 0.02,
                "relative_return_vs_sector_etf": 0.01,
                "return_3m": 0.05,
            },
            {
                "ticker": "BETA",
                "close": 120.0,
                "sma_50": 115.0,
                "sma_200": 100.0,
                "ema_21": 118.0,
                "relative_return_vs_spy": 0.03,
                "relative_return_vs_qqq": 0.02,
                "relative_return_vs_sector_etf": 0.01,
                "return_3m": 0.05,
            },
        ]
    )
    purpose_df = pd.DataFrame(
        [
            {"Ticker": "ALFA", "FinalPrimaryPurpose": "Re-rating / Undervalued", "InUniverse": True, "IsHolding": False},
            {"Ticker": "BETA", "FinalPrimaryPurpose": "Re-rating / Undervalued", "InUniverse": True, "IsHolding": False},
        ]
    )
    fundamentals = pd.DataFrame(
        [
            {
                "ticker": "ALFA",
                "revenue_growth": 0.08,
                "eps_growth": 0.10,
                "fcf_margin": 0.15,
                "gross_margin": 0.55,
                "operating_margin": 0.22,
                "debt_to_equity": 0.4,
                "pe": 16.0,
                "forward_pe": 14.0,
                "ev_to_sales": 4.0,
                "ev_to_ebitda": 10.0,
                "price_to_fcf": 18.0,
                "fcf_yield": 0.04,
            },
            {
                "ticker": "BETA",
                "revenue_growth": 0.08,
                "eps_growth": 0.10,
                "fcf_margin": 0.15,
                "gross_margin": 0.55,
                "operating_margin": 0.22,
                "debt_to_equity": 0.4,
                "pe": 20.0,
                "forward_pe": 18.0,
                "ev_to_sales": 5.0,
                "ev_to_ebitda": 12.0,
                "price_to_fcf": 22.0,
                "fcf_yield": 0.04,
            },
        ]
    )
    peers = pd.DataFrame(
        [
            {"ticker": "ALFA", "peer_ticker": "BETA"},
            {"ticker": "BETA", "peer_ticker": "ALFA"},
        ]
    )

    result = run(snapshot, purpose_df, fundamentals, config, peers=peers)

    assert result.iloc[0]["Ticker"] == "ALFA"
    assert result.iloc[0]["RelativeOpportunityScore"] > result.iloc[1]["RelativeOpportunityScore"]
