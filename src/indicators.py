from __future__ import annotations

import pandas as pd

from src.config import AppConfig


def ema(series: pd.Series, span: int, min_periods: int = 1) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=min_periods).mean()


def sma(series: pd.Series, window: int, min_periods: int = 1) -> pd.Series:
    return series.rolling(window=window, min_periods=min_periods).mean()


def compute_return(series: pd.Series, lookback: int) -> float:
    if series.empty or len(series) <= lookback:
        return float("nan")
    start = float(series.iloc[-(lookback + 1)])
    end = float(series.iloc[-1])
    if pd.isna(start) or pd.isna(end) or start <= 0:
        return float("nan")
    return end / start - 1


def relative_strength(stock_series: pd.Series, benchmark_series: pd.Series, lookback: int) -> float:
    aligned = pd.concat(
        [
            pd.Series(stock_series, copy=False).rename("stock"),
            pd.Series(benchmark_series, copy=False).rename("benchmark"),
        ],
        axis=1,
        join="inner",
    ).dropna()
    if aligned.empty:
        return float("nan")
    stock_return = compute_return(aligned["stock"], lookback)
    benchmark_return = compute_return(aligned["benchmark"], lookback)
    if pd.isna(stock_return) or pd.isna(benchmark_return):
        return float("nan")
    return stock_return - benchmark_return


def average_true_range_pct(frame: pd.DataFrame, window: int = 14) -> float:
    needed = {"high", "low", "close"}
    if not needed.issubset(frame.columns):
        return float("nan")

    ohlc = frame[["high", "low", "close"]].copy()
    if ohlc[["high", "low"]].isna().all().all():
        return float("nan")

    prev_close = ohlc["close"].shift(1)
    true_range = pd.concat(
        [
            ohlc["high"] - ohlc["low"],
            (ohlc["high"] - prev_close).abs(),
            (ohlc["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = true_range.rolling(window=window, min_periods=1).mean().iloc[-1]
    close = ohlc["close"].iloc[-1]
    if pd.isna(atr) or pd.isna(close) or close == 0:
        return float("nan")
    return float(atr / close)


def volatility_proxy_pct(series: pd.Series, window: int = 20) -> float:
    returns = series.pct_change().dropna()
    if returns.empty:
        return float("nan")
    sample = returns.tail(window)
    return float(sample.std(ddof=0))


def _distance(close: float, average: float) -> float:
    if pd.isna(close) or pd.isna(average) or average == 0:
        return float("nan")
    return float(close / average - 1)


def build_indicator_snapshot(
    prices: pd.DataFrame,
    universe: pd.DataFrame,
    theme_map: pd.DataFrame,
    config: AppConfig,
) -> tuple[pd.DataFrame, list[str]]:
    if prices.empty:
        return pd.DataFrame(), ["No price data loaded."]

    prices = prices.sort_values(["ticker", "date"]).copy()
    lookbacks = config.returns.get("lookbacks", {})
    one_month = int(lookbacks.get("one_month", 21))
    three_month = int(lookbacks.get("three_month", 63))
    six_month = int(lookbacks.get("six_month", 126))
    twelve_month = int(lookbacks.get("twelve_month", 252))
    avg_volume_window = int(config.volume_rules.get("avg_volume_window", 20))

    benchmark_map = {
        ticker: frame.sort_values("date").set_index("date")["close"]
        for ticker, frame in prices.groupby("ticker")
    }
    universe_map = universe.set_index("ticker") if not universe.empty and "ticker" in universe.columns else pd.DataFrame()
    theme_etf_map = theme_map.set_index("theme")["etf"].to_dict() if not theme_map.empty and {"theme", "etf"}.issubset(theme_map.columns) else {}

    rows: list[dict[str, object]] = []
    warnings: list[str] = []
    ema_windows = sorted(int(value) for value in config.moving_averages.get("ema", [10, 21]))
    sma_windows = sorted(int(value) for value in config.moving_averages.get("sma", [50, 200]))
    short_ema_window = ema_windows[0] if ema_windows else 10
    long_ema_window = ema_windows[1] if len(ema_windows) > 1 else 21
    medium_sma_window = sma_windows[0] if sma_windows else 50
    long_sma_window = sma_windows[1] if len(sma_windows) > 1 else 200

    for ticker, frame in prices.groupby("ticker"):
        frame = frame.sort_values("date").copy()
        frame["ema_10"] = ema(frame["close"], short_ema_window, min_periods=short_ema_window)
        frame["ema_21"] = ema(frame["close"], long_ema_window, min_periods=long_ema_window)
        frame["sma_50"] = sma(frame["close"], medium_sma_window, min_periods=medium_sma_window)
        frame["sma_200"] = sma(frame["close"], long_sma_window, min_periods=long_sma_window)
        frame["avg_volume_20"] = frame["volume"].rolling(window=avg_volume_window, min_periods=1).mean()

        latest = frame.iloc[-1]
        close_series = frame.set_index("date")["close"]

        theme = universe_map.loc[ticker]["theme"] if not universe_map.empty and ticker in universe_map.index else None
        sector_etf = universe_map.loc[ticker]["sector_etf"] if not universe_map.empty and ticker in universe_map.index else None
        if not sector_etf and theme in theme_etf_map:
            sector_etf = theme_etf_map[theme]

        rs_lookback = one_month
        rs_vs_spy = relative_strength(close_series, benchmark_map.get("SPY", pd.Series(dtype=float)), rs_lookback)
        rs_vs_qqq = relative_strength(close_series, benchmark_map.get("QQQ", pd.Series(dtype=float)), rs_lookback)
        rs_vs_sector = relative_strength(close_series, benchmark_map.get(str(sector_etf), pd.Series(dtype=float)), rs_lookback)

        atr_pct = average_true_range_pct(frame)
        volatility_proxy = volatility_proxy_pct(close_series)
        if pd.isna(atr_pct):
            atr_pct = volatility_proxy
            if ticker not in {"SPY", "QQQ"}:
                warnings.append(f"{ticker}: ATR unavailable, using volatility proxy.")

        row = {
            "ticker": ticker,
            "date": latest["date"],
            "history_days": len(frame),
            "close": float(latest["close"]),
            "ema_10": float(latest["ema_10"]),
            "ema_21": float(latest["ema_21"]),
            "sma_50": float(latest["sma_50"]),
            "sma_200": float(latest["sma_200"]),
            "return_1m": compute_return(close_series, one_month),
            "return_3m": compute_return(close_series, three_month),
            "return_6m": compute_return(close_series, six_month),
            "return_12m": compute_return(close_series, twelve_month),
            "relative_return_vs_spy": rs_vs_spy,
            "relative_return_vs_qqq": rs_vs_qqq,
            "relative_return_vs_sector_etf": rs_vs_sector,
            "sector_etf": sector_etf,
            "distance_from_10ema": _distance(float(latest["close"]), float(latest["ema_10"])),
            "distance_from_21ema": _distance(float(latest["close"]), float(latest["ema_21"])),
            "distance_from_50sma": _distance(float(latest["close"]), float(latest["sma_50"])),
            "avg_volume_20": float(latest["avg_volume_20"]),
            "volume_ratio": float(latest["volume"] / latest["avg_volume_20"]) if latest["avg_volume_20"] else float("nan"),
            "atr_or_volatility_pct": atr_pct,
        }
        rows.append(row)

    snapshot = pd.DataFrame(rows)
    if not snapshot.empty:
        snapshot["rs_percentile"] = snapshot["relative_return_vs_spy"].rank(pct=True, method="average") * 100

        missing_universe = set(universe["ticker"].dropna().astype(str)) - set(snapshot["ticker"].dropna().astype(str)) if not universe.empty else set()
        missing_rows: list[dict[str, object]] = []
        for ticker in sorted(missing_universe):
            theme = universe_map.loc[ticker]["theme"] if not universe_map.empty and ticker in universe_map.index else None
            sector_etf = universe_map.loc[ticker]["sector_etf"] if not universe_map.empty and ticker in universe_map.index else None
            missing_rows.append(
                {
                    "ticker": ticker,
                    "date": pd.NaT,
                    "history_days": 0,
                    "close": float("nan"),
                    "ema_10": float("nan"),
                    "ema_21": float("nan"),
                    "sma_50": float("nan"),
                    "sma_200": float("nan"),
                    "return_1m": float("nan"),
                    "return_3m": float("nan"),
                    "return_6m": float("nan"),
                    "return_12m": float("nan"),
                    "relative_return_vs_spy": float("nan"),
                    "relative_return_vs_qqq": float("nan"),
                    "relative_return_vs_sector_etf": float("nan"),
                    "sector_etf": sector_etf,
                    "distance_from_10ema": float("nan"),
                    "distance_from_21ema": float("nan"),
                    "distance_from_50sma": float("nan"),
                    "avg_volume_20": float("nan"),
                    "volume_ratio": float("nan"),
                    "atr_or_volatility_pct": float("nan"),
                    "rs_percentile": float("nan"),
                    "theme": theme,
                }
            )
            warnings.append(f"{ticker}: no daily price history was available.")
        if missing_rows:
            snapshot = pd.concat([snapshot, pd.DataFrame(missing_rows)], ignore_index=True)

    theme_lookup = universe_map["theme"].to_dict() if not universe_map.empty and "theme" in universe_map.columns else {}
    sector_lookup = universe_map["sector_etf"].to_dict() if not universe_map.empty and "sector_etf" in universe_map.columns else {}
    snapshot["theme"] = snapshot.get("theme", pd.Series(index=snapshot.index, dtype=object)).fillna(snapshot["ticker"].map(theme_lookup))
    snapshot["sector_etf"] = snapshot.get("sector_etf", pd.Series(index=snapshot.index, dtype=object)).fillna(snapshot["ticker"].map(sector_lookup))
    return snapshot, sorted(set(warnings))
