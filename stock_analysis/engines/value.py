from __future__ import annotations

import pandas as pd


def classify_value(row: pd.Series) -> tuple[str, str]:
    pe = row.get("pe_ratio")
    margin = row.get("profit_margin")
    growth = row.get("revenue_growth")
    leverage = row.get("debt_to_equity")

    if any(pd.isna(value) for value in (pe, margin, growth)):
        return "Insufficient Data", "fundamental data is incomplete and was not fabricated"
    if pe < 20 and margin > 0.1 and growth >= 0 and (pd.isna(leverage) or leverage < 1.5):
        return "Re-rating Candidate", "quality profile is intact while valuation remains reasonable"
    if pe < 15 and growth < 0:
        return "Cheap but Weak", "valuation is cheap but growth is deteriorating"
    if pe < 12 and margin < 0.05:
        return "Possible Value Trap", "low valuation is not supported by business quality"
    return "Watch", "valuation setup is mixed and needs more evidence"


def run(fundamentals: pd.DataFrame) -> pd.DataFrame:
    if fundamentals.empty:
        return pd.DataFrame(columns=["ticker", "classification", "reasons"])

    rows = []
    for _, row in fundamentals.iterrows():
        status, reason = classify_value(row)
        rows.append(
            {
                "ticker": row["ticker"],
                "classification": status,
                "theme": row.get("theme"),
                "pe_ratio": row.get("pe_ratio"),
                "revenue_growth": row.get("revenue_growth"),
                "profit_margin": row.get("profit_margin"),
                "reasons": reason,
            }
        )
    return pd.DataFrame(rows)
