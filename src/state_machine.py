from __future__ import annotations

import pandas as pd


def resolve_final_state(setup_status: str, review_state: str | None, conflict_flag: bool, is_holding: bool) -> str:
    if review_state == "Broken" or setup_status == "Broken":
        return "Broken"
    if review_state == "Risk Reduce":
        return "Risk Reduce"
    if setup_status == "Extended / No Chase":
        return "Extended / No Chase"
    if review_state == "Review Thesis" or (is_holding and conflict_flag):
        return "Review Thesis"
    if setup_status in {"Buyable Area", "Pullback Add Candidate", "Setup Forming", "Watch"}:
        return setup_status
    return "Ignore" if not is_holding else "Review Thesis"


def _empty_with_columns(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


STATE_BASE_SCORES = {
    "Buyable Area": 85.0,
    "Pullback Add Candidate": 80.0,
    "Watch": 72.0,
    "Setup Forming": 68.0,
    "Extended / No Chase": 60.0,
    "Review Thesis": 45.0,
    "Risk Reduce": 30.0,
    "Broken": 10.0,
    "Ignore": 0.0,
}

VALUE_CATEGORY_BONUSES = {
    "Undervalued Quality": 12.0,
    "Re-rating Candidate": 8.0,
    "Cheap but No Momentum": 3.0,
    "Possible Value Trap": -8.0,
    "Avoid": -10.0,
    "Insufficient Data": 0.0,
}


def _score_watchlist_row(row: pd.Series) -> tuple[float | None, str]:
    final_state = str(row.get("FinalState", "Ignore"))
    if final_state == "Ignore":
        return None, "Ignored names are left unranked."

    score = STATE_BASE_SCORES.get(final_state, 0.0)
    reasons = [f"Base score {score:.0f} from final state `{final_state}`."]

    if bool(row.get("IsHolding")):
        score += 3.0
        reasons.append("Added 3 points because the ticker is already a holding.")

    value_category = row.get("FinalValueCategory")
    if pd.notna(value_category) and str(value_category) in VALUE_CATEGORY_BONUSES:
        bonus = VALUE_CATEGORY_BONUSES[str(value_category)]
        score += bonus
        reasons.append(f"Adjusted {bonus:+.0f} points for value category `{value_category}`.")

    relative_opportunity = row.get("RelativeOpportunityScore")
    if pd.notna(relative_opportunity):
        relative_adjustment = max(-10.0, min(10.0, (float(relative_opportunity) - 50.0) / 5.0))
        score += relative_adjustment
        reasons.append(
            f"Adjusted {relative_adjustment:+.1f} points from relative opportunity score {float(relative_opportunity):.2f}."
        )

    if row.get("SetupStatus") == "Avoid":
        score -= 8.0
        reasons.append("Subtracted 8 points because the current setup is `Avoid`.")

    score = round(max(0.0, min(100.0, score)), 2)
    if str(row.get("ValuationStatus", "") or "").strip().lower() == "not_ready":
        score = min(score, 50.0)
        reasons.append("Capped score at 50 because valuation readiness is `not_ready`; treat as monitor-only until missing data is resolved.")
    return score, " ".join(reasons)


def build_final_watchlist(
    purpose_df: pd.DataFrame,
    momentum_df: pd.DataFrame,
    portfolio_df: pd.DataFrame,
    value_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if purpose_df.empty:
        return pd.DataFrame(
            columns=[
                "Ticker",
                "Theme",
                "SectorETF",
                "PrimaryPurpose",
                "SecondaryTags",
                "IsHolding",
                "SetupStatus",
                "ReviewState",
                "FinalState",
                "ValuationStatus",
                "FinalValueCategory",
                "PeerRelativeStatus",
                "RelativeOpportunityScore",
                "WatchlistScore",
                "WatchlistRank",
                "RankReason",
                "Reason",
            ]
        )

    momentum_cols = ["Ticker", "SetupStatus", "Reason"]
    portfolio_cols = ["Ticker", "ReviewState", "Reason"]
    value_cols = [
        "Ticker",
        "ValuationStatus",
        "FinalValueCategory",
        "PeerRelativeStatus",
        "RelativeOpportunityScore",
        "Reason",
    ]
    momentum_subset = (
        momentum_df[momentum_cols].copy()
        if set(momentum_cols).issubset(momentum_df.columns)
        else _empty_with_columns(momentum_cols)
    )
    portfolio_subset = (
        portfolio_df[portfolio_cols].copy()
        if set(portfolio_cols).issubset(portfolio_df.columns)
        else _empty_with_columns(portfolio_cols)
    )
    value_subset = (
        value_df[value_cols].copy()
        if value_df is not None and set(value_cols).issubset(value_df.columns)
        else _empty_with_columns(value_cols)
    )
    merged = purpose_df.merge(
        momentum_subset.rename(columns={"Reason": "MomentumReason"}),
        on="Ticker",
        how="left",
    ).merge(
        portfolio_subset.rename(columns={"Reason": "PortfolioReason"}),
        on="Ticker",
        how="left",
    ).merge(
        value_subset.rename(columns={"Reason": "ValueReason"}),
        on="Ticker",
        how="left",
    )

    merged["FinalState"] = merged.apply(
        lambda row: resolve_final_state(
            setup_status=row.get("SetupStatus", "Avoid"),
            review_state=row.get("ReviewState"),
            conflict_flag=bool(row.get("ConflictFlag")),
            is_holding=bool(row.get("IsHolding")),
        ),
        axis=1,
    )
    merged["Reason"] = (
        merged["Reason"].fillna("")
        + " "
        + merged["MomentumReason"].fillna("")
        + " "
        + merged["PortfolioReason"].fillna("")
        + " "
        + merged["ValueReason"].fillna("")
    ).str.strip()
    score_and_reason = merged.apply(_score_watchlist_row, axis=1)
    merged["WatchlistScore"] = score_and_reason.apply(lambda item: item[0])
    merged["RankReason"] = score_and_reason.apply(lambda item: item[1])
    rank_mask = merged["WatchlistScore"].notna() & (
        merged.get("ValuationStatus", pd.Series(index=merged.index, dtype=object)).fillna("").astype(str).str.lower() != "not_ready"
    )
    merged["WatchlistRank"] = pd.NA
    if rank_mask.any():
        merged.loc[rank_mask, "WatchlistRank"] = (
            merged.loc[rank_mask, "WatchlistScore"]
            .rank(method="dense", ascending=False)
            .astype("Int64")
        )
    merged = merged.sort_values(
        ["WatchlistRank", "WatchlistScore", "Ticker"],
        ascending=[True, False, True],
        na_position="last",
    )
    return merged[
        [
            "Ticker",
            "Theme",
            "SectorETF",
            "FinalPrimaryPurpose",
            "SecondaryTags",
            "IsHolding",
            "SetupStatus",
            "ReviewState",
            "FinalState",
            "ValuationStatus",
            "FinalValueCategory",
            "PeerRelativeStatus",
            "RelativeOpportunityScore",
            "WatchlistScore",
            "WatchlistRank",
            "RankReason",
            "Reason",
        ]
    ].rename(columns={"FinalPrimaryPurpose": "PrimaryPurpose"})
