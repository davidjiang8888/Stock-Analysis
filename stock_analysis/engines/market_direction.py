from __future__ import annotations

import pandas as pd


def classify_theme(rs_spy: float, rs_qqq: float, extension: float) -> tuple[str, str]:
    if pd.notna(extension) and extension > 0.1:
        return "Overextended", "price is stretched well above the 50-day moving average"
    if pd.notna(rs_spy) and pd.notna(rs_qqq) and rs_spy > 0.05 and rs_qqq > 0.03:
        return "Strong Rotation", "relative strength is beating both SPY and QQQ"
    if pd.notna(rs_spy) and rs_spy > 0:
        return "Early Rotation", "relative strength is improving versus SPY"
    if pd.notna(rs_spy) and rs_spy < -0.05:
        return "Broken", "relative strength is weak and failing versus SPY"
    return "Weak", "theme does not yet show decisive leadership"


def run(snapshot_df: pd.DataFrame, fundamentals: pd.DataFrame) -> pd.DataFrame:
    if snapshot_df.empty:
        return pd.DataFrame(columns=["theme", "tickers", "classification", "rs_vs_spy", "rs_vs_qqq", "reasons"])

    fundamentals_map = fundamentals.set_index("ticker") if not fundamentals.empty and "ticker" in fundamentals.columns else pd.DataFrame()
    theme_rows = []
    for theme, frame in snapshot_df.groupby(snapshot_df["ticker"].map(lambda ticker: fundamentals_map.loc[ticker].get("theme", "Unclassified") if not fundamentals_map.empty and ticker in fundamentals_map.index else "Unclassified")):
        rs_spy = frame["rs_vs_spy"].mean()
        rs_qqq = frame["rs_vs_qqq"].mean()
        extension = ((frame["close"] / frame["ma50"]) - 1).mean()
        status, reason = classify_theme(rs_spy, rs_qqq, extension)
        theme_rows.append(
            {
                "theme": theme,
                "tickers": ", ".join(frame["ticker"].tolist()),
                "classification": status,
                "rs_vs_spy": round(rs_spy, 4) if pd.notna(rs_spy) else None,
                "rs_vs_qqq": round(rs_qqq, 4) if pd.notna(rs_qqq) else None,
                "reasons": reason,
            }
        )
    return pd.DataFrame(theme_rows).sort_values(["classification", "rs_vs_spy"], ascending=[True, False])
