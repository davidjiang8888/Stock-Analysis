from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.config import AppConfig


FUNDAMENTAL_FIELDS = [
    "revenue_growth",
    "eps_growth",
    "fcf_margin",
    "gross_margin",
    "operating_margin",
    "debt_to_equity",
    "pe",
    "forward_pe",
    "ev_to_sales",
    "ev_to_ebitda",
    "price_to_fcf",
    "fcf_yield",
]

DISPLAY_FIELD_NAMES = {
    "revenue_growth": "RevenueGrowth",
    "eps_growth": "EPSGrowth",
    "fcf_margin": "FCFMargin",
    "gross_margin": "GrossMargin",
    "operating_margin": "OperatingMargin",
    "debt_to_equity": "DebtToEquity",
    "pe": "PE",
    "forward_pe": "ForwardPE",
    "ev_to_sales": "EVToSales",
    "ev_to_ebitda": "EVToEBITDA",
    "price_to_fcf": "PriceToFCF",
    "fcf_yield": "FCFYield",
}


@dataclass
class ScoreResult:
    score: float | None
    available_points: float
    earned_points: float


def _scaled_score(earned: float, available: float) -> float | None:
    if available <= 0:
        return None
    return round(100.0 * earned / available, 2)


def _score_quality(fundamentals: pd.Series, config: AppConfig) -> ScoreResult:
    earned = 0.0
    available = 0.0
    min_revenue_growth = float(config.value_rules.get("min_revenue_growth_for_rerating", 0))
    max_debt = float(config.value_rules.get("max_debt_to_equity_for_quality_value", 2.0))
    require_positive_fcf = bool(config.value_rules.get("require_positive_fcf_for_quality_value", True))

    rules = [
        ("revenue_growth", 20.0, lambda x: x >= min_revenue_growth),
        ("eps_growth", 20.0, lambda x: x > 0),
        ("gross_margin", 15.0, lambda x: x >= 0.40),
        ("operating_margin", 15.0, lambda x: x >= 0.15),
        ("debt_to_equity", 15.0, lambda x: x <= max_debt),
    ]
    if require_positive_fcf:
        rules.append(("fcf_margin", 15.0, lambda x: x > 0))

    for field, points, predicate in rules:
        value = fundamentals.get(field)
        if pd.notna(value):
            available += points
            if predicate(float(value)):
                earned += points
    return ScoreResult(score=_scaled_score(earned, available), available_points=available, earned_points=earned)


def _score_valuation(fundamentals: pd.Series) -> ScoreResult:
    earned = 0.0
    available = 0.0
    rules = [
        ("pe", 25.0, lambda x: 0 < x <= 25),
        ("forward_pe", 20.0, lambda x: 0 < x <= 22),
        ("ev_to_sales", 15.0, lambda x: 0 < x <= 8),
        ("ev_to_ebitda", 15.0, lambda x: 0 < x <= 18),
        ("price_to_fcf", 15.0, lambda x: 0 < x <= 25),
        ("fcf_yield", 10.0, lambda x: x >= 0.03),
    ]
    for field, points, predicate in rules:
        value = fundamentals.get(field)
        if pd.notna(value):
            available += points
            if predicate(float(value)):
                earned += points
    return ScoreResult(score=_scaled_score(earned, available), available_points=available, earned_points=earned)


def _score_momentum_confirmation(snapshot_row: pd.Series) -> float | None:
    available = 0.0
    earned = 0.0
    checks = [
        (snapshot_row.get("close"), snapshot_row.get("sma_50"), 30.0, lambda close, avg: close >= avg),
        (snapshot_row.get("close"), snapshot_row.get("sma_200"), 20.0, lambda close, avg: close >= avg),
        (snapshot_row.get("relative_return_vs_spy"), None, 20.0, lambda rs, _: rs > 0),
        (snapshot_row.get("relative_return_vs_qqq"), None, 15.0, lambda rs, _: rs > 0),
        (snapshot_row.get("relative_return_vs_sector_etf"), None, 15.0, lambda rs, _: rs > 0),
    ]
    for left, right, points, predicate in checks:
        if pd.notna(left) and (right is None or pd.notna(right)):
            available += points
            if predicate(float(left), float(right) if right is not None else None):
                earned += points
    return _scaled_score(earned, available)


def _value_trap_flags(snapshot_row: pd.Series, fundamentals: pd.Series, config: AppConfig) -> tuple[list[str], float]:
    flags: list[str] = []
    score = 0.0
    max_debt = float(config.value_rules.get("max_debt_to_equity_for_quality_value", 2.0))

    revenue_growth = fundamentals.get("revenue_growth")
    if pd.notna(revenue_growth) and float(revenue_growth) < 0:
        flags.append("declining revenue")
        score += 20.0

    fcf_margin = fundamentals.get("fcf_margin")
    fcf_yield = fundamentals.get("fcf_yield")
    if (pd.notna(fcf_margin) and float(fcf_margin) < 0) or (pd.notna(fcf_yield) and float(fcf_yield) < 0):
        flags.append("negative FCF")
        score += 20.0

    operating_margin = fundamentals.get("operating_margin")
    gross_margin = fundamentals.get("gross_margin")
    if (pd.notna(operating_margin) and float(operating_margin) < 0.05) or (pd.notna(gross_margin) and float(gross_margin) < 0.20):
        flags.append("deteriorating margin")
        score += 15.0

    debt_to_equity = fundamentals.get("debt_to_equity")
    if pd.notna(debt_to_equity) and float(debt_to_equity) > max_debt:
        flags.append("high debt")
        score += 15.0

    rs_spy = snapshot_row.get("relative_return_vs_spy")
    rs_qqq = snapshot_row.get("relative_return_vs_qqq")
    return_3m = snapshot_row.get("return_3m")
    if all(pd.notna(value) for value in (rs_spy, rs_qqq, return_3m)) and float(rs_spy) < 0 and float(rs_qqq) < 0 and float(return_3m) < 0:
        flags.append("persistent underperformance")
        score += 15.0

    close = snapshot_row.get("close")
    sma_50 = snapshot_row.get("sma_50")
    ema_21 = snapshot_row.get("ema_21")
    if all(pd.notna(value) for value in (close, sma_50, ema_21)) and float(close) < float(sma_50) and float(close) < float(ema_21):
        flags.append("below 50SMA with no recovery")
        score += 15.0

    return flags, min(score, 100.0)


def _missing_fields(fundamentals: pd.Series) -> list[str]:
    return [DISPLAY_FIELD_NAMES[field] for field in FUNDAMENTAL_FIELDS if pd.isna(fundamentals.get(field))]


def classify_value_row(
    snapshot_row: pd.Series,
    purpose_row: pd.Series,
    fundamentals_row: pd.Series,
    config: AppConfig,
) -> dict[str, object]:
    ticker = snapshot_row["ticker"]
    primary_purpose = purpose_row.get("FinalPrimaryPurpose", "")
    reason_parts: list[str] = []

    has_fundamentals = not fundamentals_row.empty and any(pd.notna(fundamentals_row.get(field)) for field in FUNDAMENTAL_FIELDS)
    missing_fields = _missing_fields(fundamentals_row) if has_fundamentals else ["fundamentals unavailable"]
    quality = _score_quality(fundamentals_row, config) if has_fundamentals else ScoreResult(None, 0.0, 0.0)
    valuation = _score_valuation(fundamentals_row) if has_fundamentals else ScoreResult(None, 0.0, 0.0)
    momentum_score = _score_momentum_confirmation(snapshot_row)
    trap_flags, trap_score = _value_trap_flags(snapshot_row, fundamentals_row, config)

    close = snapshot_row.get("close")
    sma_50 = snapshot_row.get("sma_50")
    price_below_50 = all(pd.notna(value) for value in (close, sma_50)) and float(close) < float(sma_50)
    persistent_underperformance = "persistent underperformance" in trap_flags
    require_momentum = bool(config.value_rules.get("require_momentum_confirmation_for_rerating", True))
    min_revenue_growth = float(config.value_rules.get("min_revenue_growth_for_rerating", 0))
    revenue_growth = fundamentals_row.get("revenue_growth")
    enough_quality_data = quality.available_points >= 50
    enough_valuation_data = valuation.available_points >= 40

    if not has_fundamentals:
        if persistent_underperformance or price_below_50:
            category = "Avoid"
            reason_parts.append("Fundamentals are unavailable and trend confirmation is weak.")
        else:
            category = "Insufficient Data"
            reason_parts.append("Fundamentals are unavailable, so valuation and quality cannot be verified.")
    elif not enough_quality_data or not enough_valuation_data:
        category = "Insufficient Data"
        reason_parts.append("Available fundamentals are too incomplete to support a reliable value classification.")
    elif trap_score >= 50:
        category = "Possible Value Trap"
        reason_parts.append("Value trap risk is elevated based on weak trend or fundamentals.")
    elif quality.score is not None and valuation.score is not None and momentum_score is not None and quality.score >= 65 and valuation.score >= 60 and momentum_score >= 55:
        category = "Undervalued Quality"
        reason_parts.append("Quality, valuation, and momentum all meet the higher bar.")
    elif (
        quality.score is not None
        and valuation.score is not None
        and quality.score >= 45
        and valuation.score >= 45
        and (not require_momentum or (momentum_score is not None and momentum_score >= 45))
        and pd.notna(revenue_growth)
        and float(revenue_growth) >= min_revenue_growth
    ):
        category = "Re-rating Candidate"
        reason_parts.append("Fundamentals look workable and the market may be starting to confirm the rerating.")
    elif valuation.score is not None and valuation.score >= 45 and (momentum_score is None or momentum_score < 45):
        category = "Cheap but No Momentum"
        reason_parts.append("Valuation looks cheaper, but price confirmation is still weak.")
    elif persistent_underperformance or price_below_50:
        category = "Avoid"
        reason_parts.append("Trend and relative performance do not support a rerating case.")
    else:
        category = "Insufficient Data"
        reason_parts.append("Available fundamentals are too incomplete to support a stronger value classification.")

    if trap_flags:
        reason_parts.append("Trap flags: " + ", ".join(trap_flags) + ".")
    if missing_fields:
        reason_parts.append("Missing data: " + ", ".join(missing_fields) + ".")

    return {
        "Ticker": ticker,
        "PrimaryPurpose": primary_purpose,
        "QualityScore": quality.score,
        "ValuationScore": valuation.score,
        "MomentumConfirmationScore": momentum_score,
        "ValueTrapRiskScore": round(trap_score, 2),
        "FinalValueCategory": category,
        "Reason": " ".join(reason_parts),
        "MissingDataFields": ", ".join(missing_fields),
    }


def run(
    snapshot: pd.DataFrame,
    purpose_df: pd.DataFrame,
    fundamentals: pd.DataFrame,
    config: AppConfig,
) -> pd.DataFrame:
    if snapshot.empty or purpose_df.empty:
        return pd.DataFrame(
            columns=[
                "Ticker",
                "PrimaryPurpose",
                "QualityScore",
                "ValuationScore",
                "MomentumConfirmationScore",
                "ValueTrapRiskScore",
                "FinalValueCategory",
                "Reason",
                "MissingDataFields",
            ]
        )

    purpose_map = purpose_df.set_index("Ticker")
    fundamentals_map = fundamentals.set_index("ticker") if not fundamentals.empty and "ticker" in fundamentals.columns else pd.DataFrame()
    rows: list[dict[str, object]] = []

    filtered = purpose_df.loc[purpose_df["InUniverse"] | purpose_df["IsHolding"], "Ticker"].tolist()
    snapshot_subset = snapshot.loc[snapshot["ticker"].isin(filtered)].copy()

    for _, snapshot_row in snapshot_subset.iterrows():
        ticker = snapshot_row["ticker"]
        purpose_row = purpose_map.loc[ticker] if ticker in purpose_map.index else pd.Series(dtype=object)
        fundamentals_row = fundamentals_map.loc[ticker] if not fundamentals_map.empty and ticker in fundamentals_map.index else pd.Series(dtype=object)
        rows.append(classify_value_row(snapshot_row, purpose_row, fundamentals_row, config))

    return pd.DataFrame(rows).sort_values(["FinalValueCategory", "Ticker"])
