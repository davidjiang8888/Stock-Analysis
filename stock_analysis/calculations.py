from __future__ import annotations

import numpy as np
import pandas as pd


def moving_average(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=1).mean()


def relative_strength(stock_prices: pd.Series, benchmark_prices: pd.Series, periods: int = 20) -> float:
    aligned = pd.concat([stock_prices, benchmark_prices], axis=1, join="inner").dropna()
    if len(aligned) < 2:
        return float("nan")
    recent = aligned.tail(min(periods + 1, len(aligned)))
    stock_return = recent.iloc[-1, 0] / recent.iloc[0, 0] - 1
    benchmark_return = recent.iloc[-1, 1] / recent.iloc[0, 1] - 1
    return float(stock_return - benchmark_return)


def annualized_volatility(series: pd.Series) -> float:
    returns = series.pct_change().dropna()
    if returns.empty:
        return float("nan")
    return float(returns.std(ddof=0))


def safe_ratio(numerator: float | int | None, denominator: float | int | None) -> float:
    if numerator is None or denominator in (None, 0):
        return float("nan")
    return float(numerator) / float(denominator)


def first_valid(*values: float | str | None) -> float | str | None:
    for value in values:
        if value is None:
            continue
        if isinstance(value, float) and np.isnan(value):
            continue
        return value
    return None
