from __future__ import annotations

import pandas as pd

from stock_analysis.engines.risk import build_risk_notes


def classify_review(snapshot: pd.Series, purpose: str, weight: float) -> tuple[str, str]:
    if all(pd.notna(value) for value in (snapshot.get("close"), snapshot.get("ma200"))) and snapshot["close"] < snapshot["ma200"]:
        return "Broken", "holding is below the 200-day moving average"
    if pd.notna(weight) and weight > 0.15:
        return "Risk Reduce", "position size exceeds the max portfolio allocation"
    if purpose == "Momentum Leader" and pd.notna(snapshot.get("rs_vs_spy")) and snapshot["rs_vs_spy"] > 0.05:
        return "Keep", "leadership remains intact for the stated purpose"
    if purpose == "Pullback Add Candidate" and all(pd.notna(value) for value in (snapshot.get("close"), snapshot.get("ma50"))) and snapshot["close"] >= snapshot["ma50"]:
        return "Add Candidate", "pullback purpose still aligns with support"
    if purpose == "Core Compounder":
        return "Hold but Do Not Add", "quality thesis may remain valid but this engine does not force adds"
    return "Review Thesis", "current data no longer clearly matches the original purpose"


def run(snapshot_df: pd.DataFrame, holdings: pd.DataFrame, purpose_df: pd.DataFrame) -> pd.DataFrame:
    if holdings.empty:
        return pd.DataFrame(columns=["ticker", "review_status", "declared_purpose", "risk_status", "invalidation_level", "reasons"])

    snapshot_map = snapshot_df.set_index("ticker") if not snapshot_df.empty else pd.DataFrame()
    purpose_map = purpose_df.set_index("ticker") if not purpose_df.empty else pd.DataFrame()

    rows = []
    for _, holding in holdings.iterrows():
        ticker = holding["ticker"]
        if snapshot_map.empty or ticker not in snapshot_map.index:
            rows.append(
                {
                    "ticker": ticker,
                    "review_status": "Review Thesis",
                    "declared_purpose": holding.get("primary_purpose", ""),
                    "risk_status": "Unknown",
                    "invalidation_level": None,
                    "reasons": "price data missing for holding",
                }
            )
            continue

        snapshot = snapshot_map.loc[ticker]
        purpose = purpose_map.loc[ticker].get("primary_purpose", holding.get("primary_purpose", "")) if not purpose_map.empty and ticker in purpose_map.index else holding.get("primary_purpose", "")
        review_status, review_reason = classify_review(snapshot, purpose, holding.get("weight"))
        risk_status, risk_notes = build_risk_notes(snapshot, purpose, holding.get("weight"))
        rows.append(
            {
                "ticker": ticker,
                "review_status": review_status,
                "declared_purpose": holding.get("primary_purpose", ""),
                "risk_status": risk_status,
                "invalidation_level": round(snapshot["ma50"] * 0.97, 2) if pd.notna(snapshot.get("ma50")) else None,
                "reasons": f"{review_reason}; {risk_notes}",
            }
        )
    return pd.DataFrame(rows)
