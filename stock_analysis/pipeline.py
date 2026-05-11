from __future__ import annotations

from pathlib import Path

import pandas as pd

from stock_analysis.config import OUTPUT_DIR
from stock_analysis.data import load_data
from stock_analysis.engines.common import build_market_snapshot
from stock_analysis.engines.market_direction import run as run_market_direction
from stock_analysis.engines.momentum import run as run_momentum
from stock_analysis.engines.portfolio_review import run as run_portfolio_review
from stock_analysis.engines.purpose_router import run as run_purpose_router
from stock_analysis.engines.value import run as run_value


OUTPUT_FILES = {
    "purpose_classification": "purpose_classification.csv",
    "market_direction": "market_direction.csv",
    "momentum_leaders": "momentum_leaders.csv",
    "portfolio_review": "portfolio_review.csv",
    "undervalued_candidates": "undervalued_candidates.csv",
    "final_watchlist": "final_watchlist.csv",
}


def _write(df: pd.DataFrame, path: Path) -> pd.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def build_final_watchlist(purpose_df: pd.DataFrame, momentum_df: pd.DataFrame, value_df: pd.DataFrame) -> pd.DataFrame:
    merged = purpose_df.rename(columns={"reasons": "purpose_reasons"}).merge(
        momentum_df[["ticker", "setup_status", "invalidation_level", "reasons"]].rename(columns={"reasons": "momentum_reasons"}),
        on="ticker",
        how="left",
    ).merge(
        value_df[["ticker", "classification", "reasons"]].rename(columns={"classification": "value_status", "reasons": "value_reasons"}),
        on="ticker",
        how="left",
    )
    merged["watchlist_bucket"] = merged["setup_status"].fillna("Review")
    merged["reasons"] = (
        merged["purpose_reasons"].fillna("")
        + "; "
        + merged["momentum_reasons"].fillna("no momentum overlay")
        + "; "
        + merged["value_reasons"].fillna("no value overlay")
    ).str.strip("; ")
    columns = ["ticker", "primary_purpose", "watchlist_bucket", "setup_status", "value_status", "purpose_conflict", "reasons"]
    return merged[columns]


def run_pipeline() -> dict[str, pd.DataFrame]:
    bundle = load_data()
    snapshot_df = build_market_snapshot(bundle.prices)
    purpose_df = run_purpose_router(snapshot_df, bundle.fundamentals, bundle.holdings)
    market_df = run_market_direction(snapshot_df, bundle.fundamentals)
    momentum_df = run_momentum(snapshot_df, purpose_df)
    portfolio_df = run_portfolio_review(snapshot_df, bundle.holdings, purpose_df)
    value_df = run_value(bundle.fundamentals)
    final_watchlist_df = build_final_watchlist(purpose_df, momentum_df, value_df)

    outputs = {
        "purpose_classification": _write(purpose_df, OUTPUT_DIR / OUTPUT_FILES["purpose_classification"]),
        "market_direction": _write(market_df, OUTPUT_DIR / OUTPUT_FILES["market_direction"]),
        "momentum_leaders": _write(momentum_df, OUTPUT_DIR / OUTPUT_FILES["momentum_leaders"]),
        "portfolio_review": _write(portfolio_df, OUTPUT_DIR / OUTPUT_FILES["portfolio_review"]),
        "undervalued_candidates": _write(value_df, OUTPUT_DIR / OUTPUT_FILES["undervalued_candidates"]),
        "final_watchlist": _write(final_watchlist_df, OUTPUT_DIR / OUTPUT_FILES["final_watchlist"]),
    }
    return outputs
