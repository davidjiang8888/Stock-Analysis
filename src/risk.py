from __future__ import annotations

import pandas as pd

from src.config import AppConfig


def allowed_position_percent(primary_purpose: str, max_position_percent: float | None, config: AppConfig) -> float:
    if max_position_percent is not None and pd.notna(max_position_percent) and max_position_percent > 0:
        return float(max_position_percent)
    if primary_purpose == "Speculative Optionality":
        return config.get_pct("risk_rules", "max_speculative_position_pct", 0.05)
    return config.get_pct("risk_rules", "max_single_position_pct_default", 0.15)


def concentration_risk(
    position_percent: float | None,
    max_allowed: float,
    portfolio_threshold: float | None = None,
) -> tuple[bool, str]:
    if position_percent is None or pd.isna(position_percent):
        return False, "Position size unavailable."
    thresholds = [("allowed max", max_allowed)]
    if portfolio_threshold is not None and pd.notna(portfolio_threshold) and portfolio_threshold > 0:
        thresholds.append(("portfolio concentration threshold", float(portfolio_threshold)))

    breached = [(label, threshold) for label, threshold in thresholds if position_percent > threshold]
    if breached:
        label, threshold = min(breached, key=lambda item: item[1])
        return True, f"Position percent {position_percent:.2%} exceeds {label} {threshold:.2%}."

    threshold_text = ", ".join(f"{label} {threshold:.2%}" for label, threshold in thresholds)
    return False, f"Position percent {position_percent:.2%} is within {threshold_text}."
