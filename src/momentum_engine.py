from __future__ import annotations

import pandas as pd

from src.config import AppConfig


def classify_momentum(row: pd.Series, config: AppConfig) -> tuple[str, str]:
    if pd.isna(row.get("close")):
        return "Avoid", "Price data is missing."

    leader_pct = float(config.momentum_rules.get("min_rs_percentile_for_leader", 90))
    watch_pct = float(config.momentum_rules.get("min_rs_percentile_for_watch", 75))
    ext_10 = config.get_pct("momentum_rules", "extended_distance_from_10ema_pct", 0.10)
    ext_21 = config.get_pct("momentum_rules", "extended_distance_from_21ema_pct", 0.15)
    volume_min = float(config.volume_rules.get("breakout_volume_ratio_min", 1.3))
    weak_volume_max = float(config.volume_rules.get("weak_volume_ratio_max", 0.8))
    reject_if_below_50 = bool(config.momentum_rules.get("reject_if_below_50sma", True))
    broken_if_below_50 = bool(config.momentum_rules.get("broken_if_below_50sma", True))
    broken_underperform_days = int(config.momentum_rules.get("broken_if_underperforming_benchmark_days", 20))
    pullback_support_windows = config.momentum_rules.get("pullback_support_ema", [10, 21])

    rs_percentile = row.get("rs_percentile")
    close = row.get("close")
    ema_10 = row.get("ema_10")
    ema_21 = row.get("ema_21")
    sma_50 = row.get("sma_50")
    sma_200 = row.get("sma_200")
    dist_10 = row.get("distance_from_10ema")
    dist_21 = row.get("distance_from_21ema")
    volume_ratio = row.get("volume_ratio")
    rs_spy = row.get("relative_return_vs_spy")
    history_days = row.get("history_days")
    support_emas = []
    for window in pullback_support_windows:
        try:
            window_int = int(window)
        except (TypeError, ValueError):
            continue
        value = row.get(f"ema_{window_int}")
        if pd.notna(value):
            support_emas.append((window_int, float(value)))

    if pd.notna(sma_50) and close < sma_50:
        if broken_if_below_50:
            return "Broken", "Close is below the 50SMA."
        if reject_if_below_50:
            return "Avoid", "Close is below the 50SMA, so the setup is rejected by rule."
    has_required_underperformance_history = pd.notna(history_days) and float(history_days) >= broken_underperform_days
    if broken_underperform_days > 0 and has_required_underperformance_history and pd.notna(rs_spy) and rs_spy < 0 and pd.notna(sma_200) and close < sma_200:
        return "Broken", "Trend is below the 200SMA and underperforming SPY."
    if pd.notna(dist_10) and dist_10 > ext_10:
        return "Extended / No Chase", "Price is extended too far above the 10EMA."
    if pd.notna(dist_21) and dist_21 > ext_21:
        return "Extended / No Chase", "Price is extended too far above the 21EMA."
    if all(pd.notna(value) for value in (rs_percentile, sma_50, sma_200, volume_ratio)) and rs_percentile >= leader_pct and close >= sma_50 and close >= sma_200 and volume_ratio >= volume_min:
        return "Buyable Area", "Relative strength, trend, and volume are all supportive."
    near_support_emas = [window for window, ema_value in support_emas if close >= ema_value * 0.97 and close <= ema_value * 1.03]
    if all(pd.notna(value) for value in (rs_percentile, sma_50, volume_ratio)) and rs_percentile >= watch_pct and close >= sma_50 and volume_ratio <= weak_volume_max:
        return "Setup Forming", "Trend is constructive, but weak volume suggests the setup still needs confirmation."
    if all(pd.notna(value) for value in (rs_percentile, sma_50)) and rs_percentile >= watch_pct and close >= sma_50 and near_support_emas:
        support_text = ", ".join(f"{window}EMA" for window in near_support_emas)
        return "Pullback Add Candidate", f"Trend is intact and the pullback is near configured support ({support_text})."
    if all(pd.notna(value) for value in (rs_percentile, sma_50)) and rs_percentile >= watch_pct and close >= sma_50:
        return "Watch", "Trend is constructive but not in a cleaner setup zone."
    if all(pd.notna(value) for value in (ema_10, ema_21)) and close >= ema_21 * 0.97 and close <= ema_10 * 1.05:
        return "Setup Forming", "Price is consolidating around short-term support."
    return "Avoid", "The current setup does not meet momentum criteria."


def run(snapshot: pd.DataFrame, config: AppConfig) -> pd.DataFrame:
    if snapshot.empty:
        return pd.DataFrame(
            columns=[
                "Ticker",
                "Theme",
                "SectorETF",
                "Close",
                "Return1M",
                "Return3M",
                "Return6M",
                "Return12M",
                "RelativeReturnVsSPY",
                "RelativeReturnVsQQQ",
                "RelativeReturnVsSectorETF",
                "RSPercentile",
                "EMA10",
                "EMA21",
                "SMA50",
                "SMA200",
                "DistanceFrom10EMA",
                "DistanceFrom21EMA",
                "DistanceFrom50SMA",
                "AvgVolume20D",
                "VolumeRatio",
                "ATRorVolatilityPct",
                "SetupStatus",
                "Reason",
            ]
        )

    rows: list[dict[str, object]] = []
    for _, row in snapshot.iterrows():
        setup_status, reason = classify_momentum(row, config)
        rows.append(
            {
                "Ticker": row["ticker"],
                "Theme": row.get("theme", ""),
                "SectorETF": row.get("sector_etf", ""),
                "Close": row.get("close"),
                "Return1M": row.get("return_1m"),
                "Return3M": row.get("return_3m"),
                "Return6M": row.get("return_6m"),
                "Return12M": row.get("return_12m"),
                "RelativeReturnVsSPY": row.get("relative_return_vs_spy"),
                "RelativeReturnVsQQQ": row.get("relative_return_vs_qqq"),
                "RelativeReturnVsSectorETF": row.get("relative_return_vs_sector_etf"),
                "RSPercentile": row.get("rs_percentile"),
                "EMA10": row.get("ema_10"),
                "EMA21": row.get("ema_21"),
                "SMA50": row.get("sma_50"),
                "SMA200": row.get("sma_200"),
                "DistanceFrom10EMA": row.get("distance_from_10ema"),
                "DistanceFrom21EMA": row.get("distance_from_21ema"),
                "DistanceFrom50SMA": row.get("distance_from_50sma"),
                "AvgVolume20D": row.get("avg_volume_20"),
                "VolumeRatio": row.get("volume_ratio"),
                "ATRorVolatilityPct": row.get("atr_or_volatility_pct"),
                "SetupStatus": setup_status,
                "Reason": reason,
            }
        )
    return pd.DataFrame(rows).sort_values(["SetupStatus", "Ticker"])
