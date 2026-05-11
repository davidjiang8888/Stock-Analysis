from __future__ import annotations

import pandas as pd

from stock_analysis.config import HIGH_VOLATILITY_THRESHOLD, MAX_POSITION_SIZE


def evaluate_portfolio_concentration(weight: float) -> str:
    if pd.isna(weight):
        return "weight unavailable"
    if weight > MAX_POSITION_SIZE:
        return "position exceeds max size"
    if weight > MAX_POSITION_SIZE * 0.8:
        return "position is approaching max size"
    return "position size is within risk budget"


def build_risk_notes(snapshot: pd.Series, purpose: str | None, weight: float | None) -> tuple[str, str]:
    notes = []
    status = "Normal"

    if pd.notna(snapshot.get("volatility")) and snapshot["volatility"] > HIGH_VOLATILITY_THRESHOLD:
        notes.append("high volatility name")
        status = "Elevated"
    if all(pd.notna(value) for value in (snapshot.get("close"), snapshot.get("ma200"))) and snapshot["close"] < snapshot["ma200"]:
        notes.append("trend is below the 200-day moving average")
        status = "High"
    concentration = evaluate_portfolio_concentration(weight)
    if "exceeds" in concentration:
        status = "High"
    notes.append(concentration)
    if purpose == "Speculative Optionality":
        notes.append("speculative purpose requires smaller sizing discipline")
        status = "Elevated" if status == "Normal" else status
    invalidation = round(snapshot["ma50"] * 0.97, 2) if pd.notna(snapshot.get("ma50")) else None
    return status, f"{'; '.join(notes)}; invalidation near {invalidation}" if invalidation is not None else "; ".join(notes)
