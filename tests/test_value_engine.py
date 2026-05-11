from pathlib import Path

import pandas as pd

from src.config import AppConfig
from src.value_engine import classify_value_row


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
            "eps_growth": -0.10,
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
