from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from stock_analysis.config import DATA_DIR, FUNDAMENTALS_FILE, HOLDINGS_FILE, PRICE_FILE


@dataclass
class DataBundle:
    prices: pd.DataFrame
    fundamentals: pd.DataFrame
    holdings: pd.DataFrame
    universe: pd.DataFrame
    theme_map: pd.DataFrame


def _read_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, **kwargs)


def _normalize_holdings(holdings: pd.DataFrame) -> pd.DataFrame:
    if holdings.empty:
        return holdings

    rename_map = {
        "Ticker": "ticker",
        "Shares": "shares",
        "CostBasis": "cost_basis",
        "PositionPercent": "weight",
        "PrimaryPurpose": "primary_purpose",
        "SecondaryTags": "secondary_tags",
        "OriginalThesis": "original_thesis",
        "MaxPositionPercent": "max_position_percent",
        "InvalidationOverride": "invalidation_override",
    }
    holdings = holdings.rename(columns=rename_map)
    if "weight" in holdings.columns:
        holdings["weight"] = pd.to_numeric(holdings["weight"], errors="coerce")
        if holdings["weight"].dropna().gt(1).any():
            holdings["weight"] = holdings["weight"] / 100.0
    return holdings


def load_data() -> DataBundle:
    prices = _read_csv(PRICE_FILE, parse_dates=["date"])
    fundamentals = _read_csv(FUNDAMENTALS_FILE)
    holdings = _normalize_holdings(_read_csv(HOLDINGS_FILE))
    universe = _read_csv(DATA_DIR / "universe.csv")
    theme_map = _read_csv(DATA_DIR / "theme_map.csv")
    return DataBundle(
        prices=prices,
        fundamentals=fundamentals,
        holdings=holdings,
        universe=universe,
        theme_map=theme_map,
    )
