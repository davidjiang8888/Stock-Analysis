from __future__ import annotations

import pandas as pd

from stock_analysis.calculations import first_valid
from stock_analysis.config import ETF_PURPOSES


def classify_purpose(snapshot: pd.Series, fundamentals_row: pd.Series | None = None) -> tuple[str, list[str], list[str]]:
    tags: list[str] = []
    reasons: list[str] = []

    ticker = snapshot["ticker"]
    if ticker in ETF_PURPOSES:
        return "ETF / Defensive / Hedge", ["ETF"], ["recognized ETF or hedge proxy"]

    close = snapshot.get("close")
    ma50 = snapshot.get("ma50")
    ma200 = snapshot.get("ma200")
    rs = first_valid(snapshot.get("rs_vs_spy"), snapshot.get("rs_vs_qqq"))
    volatility = snapshot.get("volatility")

    pe = fundamentals_row.get("pe_ratio") if fundamentals_row is not None else None
    revenue_growth = fundamentals_row.get("revenue_growth") if fundamentals_row is not None else None
    profitability = fundamentals_row.get("profit_margin") if fundamentals_row is not None else None
    debt_to_equity = fundamentals_row.get("debt_to_equity") if fundamentals_row is not None else None

    if pd.notna(close) and pd.notna(ma200) and close < ma200 * 0.93:
        return "Broken / Avoid", ["Trend Damage"], ["price is materially below the 200-day moving average"]

    if pd.notna(volatility) and volatility > 0.05 and (profitability is None or pd.isna(profitability) or profitability < 0):
        tags.append("High Volatility")
        reasons.append("high volatility with weak or missing profitability")
        return "Speculative Optionality", tags, reasons

    if all(pd.notna(value) for value in (close, ma50, ma200, rs)) and close > ma50 > ma200 and rs > 0.08:
        tags.append("Trend Leader")
        reasons.append("price and moving averages support leadership")
        return "Momentum Leader", tags, reasons

    if all(pd.notna(value) for value in (close, ma50, ma200, rs)) and close >= ma200 and close <= ma50 * 1.03 and rs > 0:
        tags.append("Trend Support")
        reasons.append("trend remains intact near support")
        return "Pullback Add Candidate", tags, reasons

    if all(value is not None and pd.notna(value) for value in (revenue_growth, profitability, debt_to_equity)):
        if revenue_growth > 0.08 and profitability > 0.12 and debt_to_equity < 1:
            return "Core Compounder", ["Quality"], ["quality growth and balance sheet profile"]

    if all(value is not None and pd.notna(value) for value in (pe, revenue_growth, profitability)):
        if pe < 20 and profitability > 0.08 and revenue_growth >= 0:
            return "Re-rating / Undervalued", ["Value"], ["valuation is reasonable relative to quality"]
        if pe < 15 and revenue_growth < 0:
            return "Re-rating / Undervalued", ["Deep Value"], ["valuation is cheap but growth is weak"]

    return "Core Compounder", tags or ["Fallback"], reasons or ["defaulted to durable business profile because stronger evidence was unavailable"]


def run(snapshot_df: pd.DataFrame, fundamentals: pd.DataFrame, holdings: pd.DataFrame) -> pd.DataFrame:
    if snapshot_df.empty:
        return pd.DataFrame(columns=["ticker", "primary_purpose", "secondary_tags", "purpose_conflict", "reasons"])

    fundamentals_map = fundamentals.set_index("ticker") if not fundamentals.empty and "ticker" in fundamentals.columns else pd.DataFrame()
    holdings_map = holdings.set_index("ticker") if not holdings.empty and "ticker" in holdings.columns else pd.DataFrame()

    rows = []
    for _, snapshot in snapshot_df.iterrows():
        fundamentals_row = fundamentals_map.loc[snapshot["ticker"]] if not fundamentals_map.empty and snapshot["ticker"] in fundamentals_map.index else None
        primary, tags, reasons = classify_purpose(snapshot, fundamentals_row)

        declared = None
        conflict = ""
        if not holdings_map.empty and snapshot["ticker"] in holdings_map.index:
            declared = holdings_map.loc[snapshot["ticker"]].get("primary_purpose")
            if pd.notna(declared):
                if declared != primary:
                    conflict = f"user purpose is '{declared}' but current data maps to '{primary}'"
                primary = str(declared)
                reasons = reasons + ["user-provided holding purpose was respected"]

        rows.append(
            {
                "ticker": snapshot["ticker"],
                "primary_purpose": primary,
                "secondary_tags": ", ".join(tags),
                "purpose_conflict": conflict,
                "reasons": "; ".join(reasons),
            }
        )
    return pd.DataFrame(rows)
