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


def build_final_watchlist(
    purpose_df: pd.DataFrame,
    momentum_df: pd.DataFrame,
    portfolio_df: pd.DataFrame,
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
                "Reason",
            ]
        )

    momentum_cols = ["Ticker", "SetupStatus", "Reason"]
    portfolio_cols = ["Ticker", "ReviewState", "Reason"]
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
    merged = purpose_df.merge(
        momentum_subset.rename(columns={"Reason": "MomentumReason"}),
        on="Ticker",
        how="left",
    ).merge(
        portfolio_subset.rename(columns={"Reason": "PortfolioReason"}),
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
    ).str.strip()
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
            "Reason",
        ]
    ].rename(columns={"FinalPrimaryPurpose": "PrimaryPurpose"})
