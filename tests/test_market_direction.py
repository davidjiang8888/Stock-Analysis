from pathlib import Path

import pandas as pd

from src.config import AppConfig
from src.market_direction import run


def test_market_direction_falls_back_to_constituents_when_theme_etf_is_missing():
    config = AppConfig.load(Path("config.yaml"))
    snapshot = pd.DataFrame(
        [
            {
                "ticker": "NVDA",
                "history_days": 63,
                "close": 110.0,
                "return_1m": 0.12,
                "return_3m": 0.25,
                "return_6m": float("nan"),
                "relative_return_vs_spy": 0.08,
                "relative_return_vs_qqq": 0.05,
                "distance_from_50sma": 0.04,
            }
        ]
    )
    universe = pd.DataFrame(
        [
            {
                "ticker": "NVDA",
                "theme": "AI Semiconductors",
                "sector_etf": "SMH",
            }
        ]
    )
    theme_map = pd.DataFrame(
        [
            {
                "theme": "AI Semiconductors",
                "etf": "SMH",
                "description": "Semiconductor leaders exposed to AI compute",
            }
        ]
    )

    result = run(snapshot, universe, theme_map, config)
    row = result.iloc[0]

    assert row["Theme"] == "AI Semiconductors"
    assert row["Source"] == "Constituent median"
    assert row["ThemeStatus"] == "Strong Rotation"
    assert "theme_etf_price" in row["MissingDataFields"]
    assert "Used constituent median data" in row["Reason"]


def test_market_direction_marks_missing_themes_as_insufficient_data():
    config = AppConfig.load(Path("config.yaml"))
    universe = pd.DataFrame(
        [
            {
                "ticker": "CRDO",
                "theme": "AI Infrastructure",
                "sector_etf": "SMH",
            }
        ]
    )
    theme_map = pd.DataFrame(
        [
            {
                "theme": "AI Infrastructure",
                "etf": "SMH",
                "description": "Optical networking and AI infrastructure",
            }
        ]
    )

    result = run(pd.DataFrame(), universe, theme_map, config)
    row = result.iloc[0]

    assert row["Theme"] == "AI Infrastructure"
    assert row["ThemeStatus"] == "Insufficient Data"
    assert "constituent_prices" in row["MissingDataFields"]
    assert "theme_etf_price" in row["MissingDataFields"]
    reason = row["Reason"].lower()
    assert "lacks enough comparable data" in reason or "not enough price history" in reason
