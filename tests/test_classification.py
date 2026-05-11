from pathlib import Path

import pandas as pd

from src.config import AppConfig
from src.momentum_engine import classify_momentum
from src.portfolio_review import review_holdings
from src.purpose_router import route_purposes
from src.risk import concentration_risk
from src.state_machine import build_final_watchlist


def test_extended_classification():
    config = AppConfig.load(Path("config.yaml"))
    row = pd.Series(
        {
            "close": 120.0,
            "ema_10": 100.0,
            "ema_21": 101.0,
            "sma_50": 95.0,
            "sma_200": 90.0,
            "distance_from_10ema": 0.20,
            "distance_from_21ema": 0.18,
            "volume_ratio": 1.5,
            "rs_percentile": 95.0,
            "relative_return_vs_spy": 0.12,
        }
    )
    status, _ = classify_momentum(row, config)
    assert status == "Extended / No Chase"


def test_broken_classification():
    config = AppConfig.load(Path("config.yaml"))
    row = pd.Series(
        {
            "close": 90.0,
            "ema_10": 95.0,
            "ema_21": 96.0,
            "sma_50": 100.0,
            "sma_200": 110.0,
            "distance_from_10ema": -0.05,
            "distance_from_21ema": -0.06,
            "volume_ratio": 0.9,
            "rs_percentile": 20.0,
            "relative_return_vs_spy": -0.08,
            "history_days": 30,
        }
    )
    status, _ = classify_momentum(row, config)
    assert status == "Broken"


def test_broken_underperformance_rule_requires_configured_history():
    config = AppConfig.load(Path("config.yaml"))
    config.raw["momentum_rules"]["broken_if_below_50sma"] = False
    config.raw["momentum_rules"]["reject_if_below_50sma"] = False
    row = pd.Series(
        {
            "close": 90.0,
            "ema_10": 95.0,
            "ema_21": 96.0,
            "sma_50": 85.0,
            "sma_200": 110.0,
            "distance_from_10ema": -0.05,
            "distance_from_21ema": -0.06,
            "volume_ratio": 1.0,
            "rs_percentile": 80.0,
            "relative_return_vs_spy": -0.08,
            "history_days": 10,
        }
    )
    status, reason = classify_momentum(row, config)
    assert status != "Broken"
    assert "underperforming SPY" not in reason


def test_reject_if_below_50sma_applies_even_when_not_marked_broken():
    config = AppConfig.load(Path("config.yaml"))
    config.raw["momentum_rules"]["broken_if_below_50sma"] = False
    config.raw["momentum_rules"]["reject_if_below_50sma"] = True
    row = pd.Series(
        {
            "close": 90.0,
            "ema_10": 95.0,
            "ema_21": 96.0,
            "sma_50": 100.0,
            "sma_200": 80.0,
            "distance_from_10ema": -0.05,
            "distance_from_21ema": -0.06,
            "volume_ratio": 1.1,
            "rs_percentile": 92.0,
            "relative_return_vs_spy": 0.04,
        }
    )
    status, reason = classify_momentum(row, config)
    assert status == "Avoid"
    assert "rejected by rule" in reason


def test_pullback_add_candidate_respects_configured_support_ema():
    config = AppConfig.load(Path("config.yaml"))
    config.raw["momentum_rules"]["pullback_support_ema"] = [21]
    row = pd.Series(
        {
            "close": 104.0,
            "ema_10": 100.0,
            "ema_21": 103.5,
            "sma_50": 95.0,
            "sma_200": 90.0,
            "distance_from_10ema": 0.04,
            "distance_from_21ema": 0.0048,
            "volume_ratio": 1.0,
            "rs_percentile": 85.0,
            "relative_return_vs_spy": 0.03,
        }
    )
    status, reason = classify_momentum(row, config)
    assert status == "Pullback Add Candidate"
    assert "21EMA" in reason


def test_weak_volume_ratio_max_pushes_watch_to_setup_forming():
    config = AppConfig.load(Path("config.yaml"))
    row = pd.Series(
        {
            "close": 110.0,
            "ema_10": 108.0,
            "ema_21": 106.0,
            "sma_50": 100.0,
            "sma_200": 95.0,
            "distance_from_10ema": 0.0185,
            "distance_from_21ema": 0.0377,
            "volume_ratio": 0.75,
            "rs_percentile": 80.0,
            "relative_return_vs_spy": 0.02,
        }
    )
    status, reason = classify_momentum(row, config)
    assert status == "Setup Forming"
    assert "weak volume" in reason


def test_portfolio_concentration_risk():
    flagged, reason = concentration_risk(0.20, 0.15)
    assert flagged is True
    assert "exceeds allowed max" in reason


def test_portfolio_concentration_risk_respects_portfolio_threshold():
    flagged, reason = concentration_risk(0.22, 0.25, portfolio_threshold=0.20)
    assert flagged is True
    assert "portfolio concentration threshold" in reason


def test_purpose_router_handles_missing_price_data_gracefully():
    config = AppConfig.load(Path("config.yaml"))
    snapshot = pd.DataFrame(
        [
            {
                "ticker": "META",
                "history_days": 0,
                "close": float("nan"),
                "sma_200": float("nan"),
                "distance_from_50sma": float("nan"),
                "relative_return_vs_spy": float("nan"),
                "rs_percentile": float("nan"),
                "atr_or_volatility_pct": float("nan"),
                "sector_etf": "QQQ",
            }
        ]
    )
    universe = pd.DataFrame(
        [
            {
                "ticker": "META",
                "theme": "AI / Ads / Platforms",
                "sector_etf": "QQQ",
                "default_purpose": "Core Compounder",
            }
        ]
    )
    holdings = pd.DataFrame(
        [
            {
                "ticker": "META",
                "primary_purpose": "Core Compounder",
                "position_percent": 0.10,
                "max_position_percent": 0.15,
            }
        ]
    )

    result = route_purposes(snapshot, universe, holdings, pd.DataFrame(), config)
    row = result.iloc[0]

    assert row["Ticker"] == "META"
    assert bool(row["ConflictFlag"]) is True
    assert "Price data is missing" in row["ConflictReasons"]
    assert "Price data is missing" in row["Reason"]


def test_portfolio_review_handles_missing_engine_context_gracefully():
    config = AppConfig.load(Path("config.yaml"))
    holdings = pd.DataFrame(
        [
            {
                "ticker": "NVDA",
                "primary_purpose": "Momentum Leader",
                "position_percent": 0.10,
                "max_position_percent": 0.15,
            }
        ]
    )

    result = review_holdings(holdings, pd.DataFrame(), pd.DataFrame(), config)
    row = result.iloc[0]

    assert row["Ticker"] == "NVDA"
    assert row["PrimaryPurpose"] == "Momentum Leader"
    assert row["SetupStatus"] == "Avoid"
    assert row["ReviewState"] == "Review Thesis"
    assert bool(row["ConcentrationRisk"]) is False
    assert "within allowed max" in row["Reason"]
    assert "too weak to keep the thesis on autopilot" in row["Reason"]


def test_do_not_add_to_losing_trading_positions_applies_independently():
    config = AppConfig.load(Path("config.yaml"))
    config.raw["portfolio_rules"]["add_only_to_profitable_positions"] = False
    config.raw["portfolio_rules"]["do_not_add_to_losing_trading_positions"] = True

    holdings = pd.DataFrame(
        [
            {
                "ticker": "NVDA",
                "primary_purpose": "Momentum Leader",
                "position_percent": 0.10,
                "max_position_percent": 0.15,
                "cost_basis": 120.0,
            }
        ]
    )
    purpose_df = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "FinalPrimaryPurpose": "Momentum Leader",
                "ConflictFlag": False,
            }
        ]
    )
    momentum_df = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "SetupStatus": "Pullback Add Candidate",
                "Close": 110.0,
            }
        ]
    )

    result = review_holdings(holdings, purpose_df, momentum_df, config)
    row = result.iloc[0]

    assert row["ReviewState"] == "Hold but Do Not Add"
    assert "below cost basis" in row["Reason"]


def test_reduce_risk_if_position_exceeds_max_can_be_disabled():
    config = AppConfig.load(Path("config.yaml"))
    config.raw["risk_rules"]["reduce_risk_if_position_exceeds_max"] = False

    holdings = pd.DataFrame(
        [
            {
                "ticker": "NVDA",
                "primary_purpose": "Momentum Leader",
                "position_percent": 0.22,
                "max_position_percent": 0.15,
            }
        ]
    )

    result = review_holdings(holdings, pd.DataFrame(), pd.DataFrame(), config)
    row = result.iloc[0]

    assert bool(row["ConcentrationRisk"]) is True
    assert row["ReviewState"] == "Review Thesis"
    assert "exceeds allowed max" in row["Reason"]


def test_final_watchlist_handles_missing_merged_context_gracefully():
    purpose_df = pd.DataFrame(
        [
            {
                "Ticker": "TSLA",
                "Theme": "EV / AI / Robotics",
                "SectorETF": "QQQ",
                "FinalPrimaryPurpose": "Core Compounder",
                "SecondaryTags": "High Volatility",
                "IsHolding": True,
                "ConflictFlag": True,
                "Reason": "Purpose conflicts with the latest data.",
            }
        ]
    )

    result = build_final_watchlist(purpose_df, pd.DataFrame(), pd.DataFrame())
    row = result.iloc[0]

    assert row["Ticker"] == "TSLA"
    assert row["PrimaryPurpose"] == "Core Compounder"
    assert bool(row["IsHolding"]) is True
    assert row["FinalState"] == "Review Thesis"
    assert pd.isna(row["SetupStatus"])
    assert pd.isna(row["ReviewState"])
    assert row["Reason"] == "Purpose conflicts with the latest data."
