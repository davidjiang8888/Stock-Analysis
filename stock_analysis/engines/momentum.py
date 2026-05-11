from __future__ import annotations

import pandas as pd

from stock_analysis.config import EXTENSION_THRESHOLD, PIVOT_PROXIMITY_THRESHOLD


def classify_momentum(snapshot: pd.Series) -> tuple[str, list[str]]:
    reasons: list[str] = []
    close = snapshot.get("close")
    ma20 = snapshot.get("ma20")
    ma50 = snapshot.get("ma50")
    ma200 = snapshot.get("ma200")
    rs = snapshot.get("rs_vs_spy")
    volume = snapshot.get("volume")
    avg_volume = snapshot.get("avg_volume_20")
    pivot = snapshot.get("price_20d_high")

    if all(pd.notna(value) for value in (close, ma200)) and close < ma200:
        return "Broken", ["price is below the 200-day moving average"]

    if all(pd.notna(value) for value in (close, ma50)) and close > ma50 * (1 + EXTENSION_THRESHOLD):
        return "Extended / No Chase", ["price is extended beyond the 50-day moving average"]

    if all(pd.notna(value) for value in (close, ma50, ma200, rs)) and close > ma50 > ma200 and rs > 0.05:
        if all(pd.notna(value) for value in (volume, avg_volume)) and volume > avg_volume * 1.1:
            reasons.append("volume is confirming the move")
        if pd.notna(pivot) and abs(close / pivot - 1) <= PIVOT_PROXIMITY_THRESHOLD:
            return "Buyable Area", reasons + ["price is near a recent pivot without being extended"]
        return "Watch", reasons + ["trend is healthy but pivot timing is not ideal"]

    if all(pd.notna(value) for value in (close, ma20, ma50, rs)) and close >= ma50 and close <= ma20 * 1.02 and rs > 0:
        return "Pullback Add Candidate", ["pullback remains constructive above support"]

    if all(pd.notna(value) for value in (close, ma20, ma50)) and close >= ma50 * 0.98 and close <= ma20 * 1.03:
        return "Setup Forming", ["consolidation is forming near moving average support"]

    return "Avoid", ["trend leadership is not strong enough"]


def run(snapshot_df: pd.DataFrame, purpose_df: pd.DataFrame) -> pd.DataFrame:
    if snapshot_df.empty:
        return pd.DataFrame(columns=["ticker", "setup_status", "primary_purpose", "invalidation_level", "reasons"])

    purpose_map = purpose_df.set_index("ticker") if not purpose_df.empty else pd.DataFrame()
    rows = []
    for _, snapshot in snapshot_df.iterrows():
        status, reasons = classify_momentum(snapshot)
        invalidation = round(snapshot["ma50"] * 0.97, 2) if pd.notna(snapshot.get("ma50")) else None
        rows.append(
            {
                "ticker": snapshot["ticker"],
                "setup_status": status,
                "primary_purpose": purpose_map.loc[snapshot["ticker"]].get("primary_purpose", "") if not purpose_map.empty and snapshot["ticker"] in purpose_map.index else "",
                "relative_strength_vs_spy": round(snapshot["rs_vs_spy"], 4) if pd.notna(snapshot["rs_vs_spy"]) else None,
                "extension_pct_vs_ma50": round(snapshot["close"] / snapshot["ma50"] - 1, 4) if pd.notna(snapshot["ma50"]) and snapshot["ma50"] else None,
                "invalidation_level": invalidation,
                "reasons": "; ".join(reasons),
            }
        )
    return pd.DataFrame(rows).sort_values(["setup_status", "relative_strength_vs_spy"], ascending=[True, False])
