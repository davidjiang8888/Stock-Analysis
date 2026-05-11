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

RELATIVE_MULTIPLE_FIELDS = [
    ("pe", "PE"),
    ("forward_pe", "ForwardPE"),
    ("ev_to_sales", "EVToSales"),
    ("ev_to_ebitda", "EVToEBITDA"),
    ("price_to_fcf", "PriceToFCF"),
]


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


def _median(values: list[float]) -> float | None:
    clean = sorted(float(value) for value in values if pd.notna(value))
    if not clean:
        return None
    midpoint = len(clean) // 2
    if len(clean) % 2 == 1:
        return clean[midpoint]
    return (clean[midpoint - 1] + clean[midpoint]) / 2.0


def _peer_relative_context(
    fundamentals_row: pd.Series,
    peer_rows: pd.DataFrame | None,
) -> dict[str, object]:
    standalone_multiples = {
        field: float(fundamentals_row[field])
        for field, _label in RELATIVE_MULTIPLE_FIELDS
        if pd.notna(fundamentals_row.get(field))
    }
    peer_medians = {
        field: _median(peer_rows[field].tolist()) if peer_rows is not None and not peer_rows.empty and field in peer_rows.columns else None
        for field, _label in RELATIVE_MULTIPLE_FIELDS
    }
    relative_gaps: dict[str, float | None] = {}
    for field, _label in RELATIVE_MULTIPLE_FIELDS:
        current = standalone_multiples.get(field)
        peer_median = peer_medians.get(field)
        if current is None or peer_median in (None, 0):
            relative_gaps[field] = None
        else:
            relative_gaps[field] = (peer_median - current) / peer_median

    comparable_gaps = [gap for gap in relative_gaps.values() if gap is not None]
    score = None
    if comparable_gaps:
        score = round(max(0.0, min(100.0, 50.0 + 100.0 * (sum(comparable_gaps) / len(comparable_gaps)))), 2)

    if comparable_gaps:
        avg_gap = sum(comparable_gaps) / len(comparable_gaps)
        if avg_gap >= 0.15:
            status = "Discount vs Peers"
        elif avg_gap >= 0.05:
            status = "Slight Discount vs Peers"
        elif avg_gap > -0.05:
            status = "Near Peer Median"
        elif avg_gap > -0.15:
            status = "Slight Premium vs Peers"
        else:
            status = "Premium vs Peers"
    elif standalone_multiples:
        status = "Peer Data Unavailable"
    else:
        status = "Insufficient Peer Data"

    notes: list[str] = []
    compared_labels = [label for field, label in RELATIVE_MULTIPLE_FIELDS if relative_gaps.get(field) is not None]
    if compared_labels:
        notes.append("Peer comparison uses " + ", ".join(compared_labels) + ".")
    elif standalone_multiples:
        notes.append("Standalone valuation multiples are available, but peer medians are not.")
    else:
        notes.append("Not enough valuation multiples are available for a peer comparison.")

    return {
        "peer_count": 0 if peer_rows is None or peer_rows.empty else int(len(peer_rows)),
        "peer_relative_status": status,
        "relative_opportunity_score": score,
        "standalone_multiples": standalone_multiples,
        "peer_medians": peer_medians,
        "relative_gaps": relative_gaps,
        "notes": notes,
    }


def classify_value_row(
    snapshot_row: pd.Series,
    purpose_row: pd.Series,
    fundamentals_row: pd.Series,
    config: AppConfig,
    peer_rows: pd.DataFrame | None = None,
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
    peer_context = _peer_relative_context(fundamentals_row, peer_rows) if has_fundamentals else _peer_relative_context(pd.Series(dtype=object), None)
    peer_support = peer_context["relative_opportunity_score"] is not None and float(peer_context["relative_opportunity_score"]) >= 55
    peer_premium_risk = peer_context["relative_opportunity_score"] is not None and float(peer_context["relative_opportunity_score"]) <= 40

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
    if peer_context["peer_relative_status"] != "Insufficient Peer Data":
        reason_parts.append(
            f"Peer comparison status: {peer_context['peer_relative_status']}."
        )
    if peer_support:
        reason_parts.append("Available peer multiples indicate a discount versus local peers.")
    elif peer_premium_risk:
        reason_parts.append("Available peer multiples indicate a premium versus local peers.")
    reason_parts.extend(peer_context["notes"])
    if missing_fields:
        reason_parts.append("Missing data: " + ", ".join(missing_fields) + ".")

    return {
        "Ticker": ticker,
        "PrimaryPurpose": primary_purpose,
        "QualityScore": quality.score,
        "ValuationScore": valuation.score,
        "MomentumConfirmationScore": momentum_score,
        "ValueTrapRiskScore": round(trap_score, 2),
        "PeerCount": peer_context["peer_count"],
        "PeerRelativeStatus": peer_context["peer_relative_status"],
        "RelativeOpportunityScore": peer_context["relative_opportunity_score"],
        "StandalonePE": peer_context["standalone_multiples"].get("pe"),
        "PeerMedianPE": peer_context["peer_medians"].get("pe"),
        "StandaloneForwardPE": peer_context["standalone_multiples"].get("forward_pe"),
        "PeerMedianForwardPE": peer_context["peer_medians"].get("forward_pe"),
        "StandaloneEVToSales": peer_context["standalone_multiples"].get("ev_to_sales"),
        "PeerMedianEVToSales": peer_context["peer_medians"].get("ev_to_sales"),
        "StandaloneEVToEBITDA": peer_context["standalone_multiples"].get("ev_to_ebitda"),
        "PeerMedianEVToEBITDA": peer_context["peer_medians"].get("ev_to_ebitda"),
        "StandalonePriceToFCF": peer_context["standalone_multiples"].get("price_to_fcf"),
        "PeerMedianPriceToFCF": peer_context["peer_medians"].get("price_to_fcf"),
        "FinalValueCategory": category,
        "Reason": " ".join(reason_parts),
        "MissingDataFields": ", ".join(missing_fields),
    }


def run(
    snapshot: pd.DataFrame,
    purpose_df: pd.DataFrame,
    fundamentals: pd.DataFrame,
    config: AppConfig,
    peers: pd.DataFrame | None = None,
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
                "PeerCount",
                "PeerRelativeStatus",
                "RelativeOpportunityScore",
                "StandalonePE",
                "PeerMedianPE",
                "StandaloneForwardPE",
                "PeerMedianForwardPE",
                "StandaloneEVToSales",
                "PeerMedianEVToSales",
                "StandaloneEVToEBITDA",
                "PeerMedianEVToEBITDA",
                "StandalonePriceToFCF",
                "PeerMedianPriceToFCF",
                "FinalValueCategory",
                "Reason",
                "MissingDataFields",
            ]
        )

    purpose_map = purpose_df.set_index("Ticker")
    fundamentals_map = fundamentals.set_index("ticker") if not fundamentals.empty and "ticker" in fundamentals.columns else pd.DataFrame()
    peers_map = peers.set_index("ticker") if peers is not None and not peers.empty and "ticker" in peers.columns else pd.DataFrame()
    rows: list[dict[str, object]] = []

    filtered = purpose_df.loc[purpose_df["InUniverse"] | purpose_df["IsHolding"], "Ticker"].tolist()
    snapshot_subset = snapshot.loc[snapshot["ticker"].isin(filtered)].copy()

    for _, snapshot_row in snapshot_subset.iterrows():
        ticker = snapshot_row["ticker"]
        purpose_row = purpose_map.loc[ticker] if ticker in purpose_map.index else pd.Series(dtype=object)
        fundamentals_row = fundamentals_map.loc[ticker] if not fundamentals_map.empty and ticker in fundamentals_map.index else pd.Series(dtype=object)
        peer_rows = pd.DataFrame()
        if not peers_map.empty and ticker in peers_map.index and not fundamentals_map.empty:
            peer_entries = peers_map.loc[[ticker]] if isinstance(peers_map.loc[ticker], pd.Series) else peers_map.loc[ticker]
            if isinstance(peer_entries, pd.Series):
                peer_entries = peer_entries.to_frame().T
            peer_tickers = peer_entries["peer_ticker"].dropna().astype(str).str.upper().str.strip().tolist() if "peer_ticker" in peer_entries.columns else []
            if peer_tickers:
                peer_rows = fundamentals_map.loc[fundamentals_map.index.intersection(peer_tickers)].copy()
        rows.append(classify_value_row(snapshot_row, purpose_row, fundamentals_row, config, peer_rows=peer_rows))

    return pd.DataFrame(rows).sort_values(
        ["FinalValueCategory", "RelativeOpportunityScore", "Ticker"],
        ascending=[True, False, True],
        na_position="last",
    )
