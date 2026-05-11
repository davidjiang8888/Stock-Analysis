from __future__ import annotations

import pandas as pd

from stock_analysis.calculations import annualized_volatility, moving_average, relative_strength


def build_market_snapshot(prices: pd.DataFrame) -> pd.DataFrame:
    if prices.empty:
        return pd.DataFrame()

    required = {"date", "ticker", "adj_close", "volume"}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"prices.csv is missing required columns: {sorted(missing)}")

    snapshots = []
    for ticker, frame in prices.sort_values("date").groupby("ticker"):
        frame = frame.copy()
        frame["ma20"] = moving_average(frame["adj_close"], 20)
        frame["ma50"] = moving_average(frame["adj_close"], 50)
        frame["ma200"] = moving_average(frame["adj_close"], 200)
        last = frame.iloc[-1]
        snapshots.append(
            {
                "ticker": ticker,
                "date": last["date"],
                "close": float(last["adj_close"]),
                "ma20": float(last["ma20"]),
                "ma50": float(last["ma50"]),
                "ma200": float(last["ma200"]),
                "avg_volume_20": float(frame["volume"].tail(20).mean()),
                "volume": float(last["volume"]),
                "price_20d_high": float(frame["adj_close"].tail(20).max()),
                "price_20d_low": float(frame["adj_close"].tail(20).min()),
                "volatility": annualized_volatility(frame["adj_close"]),
                "return_20d": float(frame["adj_close"].pct_change(20).iloc[-1]) if len(frame) > 20 else float("nan"),
                "return_60d": float(frame["adj_close"].pct_change(60).iloc[-1]) if len(frame) > 60 else float("nan"),
            }
        )

    snapshot_df = pd.DataFrame(snapshots)
    benchmark_map = {
        ticker: frame.sort_values("date").set_index("date")["adj_close"]
        for ticker, frame in prices.groupby("ticker")
    }
    for benchmark in ("SPY", "QQQ"):
        snapshot_df[f"rs_vs_{benchmark.lower()}"] = snapshot_df["ticker"].map(
            lambda ticker: relative_strength(
                prices.loc[prices["ticker"] == ticker].sort_values("date").set_index("date")["adj_close"],
                benchmark_map.get(benchmark, pd.Series(dtype=float)),
            )
        )
    return snapshot_df
