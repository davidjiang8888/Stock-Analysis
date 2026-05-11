from __future__ import annotations

import pandas as pd

from src.config import AppConfig
from src.risk import allowed_position_percent


PURPOSES = {
    "Momentum Leader",
    "Pullback Add Candidate",
    "Core Compounder",
    "Re-rating / Undervalued",
    "Speculative Optionality",
    "ETF / Defensive / Hedge",
    "Broken / Avoid",
}

VALUE_REQUIRED_FIELDS = {"revenue_growth", "eps_growth", "fcf_margin", "debt_to_equity", "pe", "forward_pe"}


def route_purposes(
    snapshot: pd.DataFrame,
    universe: pd.DataFrame,
    holdings: pd.DataFrame,
    fundamentals: pd.DataFrame,
    config: AppConfig,
) -> pd.DataFrame:
    if snapshot.empty:
        return pd.DataFrame(
            columns=[
                "Ticker",
                "InUniverse",
                "IsHolding",
                "DeclaredPrimaryPurpose",
                "DefaultPurpose",
                "FinalPrimaryPurpose",
                "SecondaryTags",
                "ConflictFlag",
                "ConflictReasons",
                "Theme",
                "SectorETF",
                "Reason",
            ]
        )

    universe_map = universe.set_index("ticker") if not universe.empty else pd.DataFrame()
    holdings_map = holdings.set_index("ticker") if not holdings.empty else pd.DataFrame()
    fundamentals_map = fundamentals.set_index("ticker") if not fundamentals.empty and "ticker" in fundamentals.columns else pd.DataFrame()

    rows: list[dict[str, object]] = []
    for _, row in snapshot.iterrows():
        ticker = row["ticker"]
        in_holdings = not holdings_map.empty and ticker in holdings_map.index
        in_universe = not universe_map.empty and ticker in universe_map.index

        holding = holdings_map.loc[ticker] if in_holdings else pd.Series(dtype=object)
        universe_row = universe_map.loc[ticker] if in_universe else pd.Series(dtype=object)
        fundamentals_row = fundamentals_map.loc[ticker] if not fundamentals_map.empty and ticker in fundamentals_map.index else pd.Series(dtype=object)

        declared = holding.get("primary_purpose") if in_holdings else None
        default_purpose = universe_row.get("default_purpose") if in_universe else None
        computed = declared or default_purpose or "Watch"

        secondary_tags: list[str] = []
        conflict_reasons: list[str] = []
        reason_parts: list[str] = []

        if in_holdings:
            reason_parts.append("Used holding primary purpose.")
        elif default_purpose:
            reason_parts.append("Used universe default purpose.")
        else:
            reason_parts.append("No declared purpose found; left unverified.")

        if pd.notna(row.get("relative_return_vs_spy")) and row.get("rs_percentile", 0) >= config.momentum_rules.get("min_rs_percentile_for_leader", 90):
            secondary_tags.append("Strong RS")
        if pd.notna(row.get("relative_return_vs_spy")) and row.get("relative_return_vs_spy") < 0:
            secondary_tags.append("Weak RS")
        if pd.notna(row.get("distance_from_50sma")) and row.get("distance_from_50sma") > 0:
            secondary_tags.append("Above 50SMA")
        if pd.notna(row.get("atr_or_volatility_pct")) and row.get("atr_or_volatility_pct") > config.get_pct("risk_rules", "high_volatility_atr_pct", 0.08):
            secondary_tags.append("High Volatility")

        final_purpose = computed
        if pd.notna(row.get("distance_from_50sma")) and row.get("distance_from_50sma") < 0 and pd.notna(row.get("close")) and pd.notna(row.get("sma_200")) and row.get("close") < row.get("sma_200"):
            if not in_holdings:
                final_purpose = "Broken / Avoid"
            conflict_reasons.append("Trend is broken below both 50SMA and 200SMA.")

        if computed == "Momentum Leader" and (pd.isna(row.get("relative_return_vs_spy")) or row.get("relative_return_vs_spy") <= 0):
            conflict_reasons.append("Marked as Momentum Leader but relative strength is weak.")
        if computed == "Core Compounder" and pd.notna(row.get("distance_from_50sma")) and row.get("distance_from_50sma") < 0:
            conflict_reasons.append("Marked as Core Compounder but trend is below the 50SMA.")
        fundamentals_available = not fundamentals_row.empty and any(pd.notna(fundamentals_row.get(field)) for field in VALUE_REQUIRED_FIELDS)
        if computed == "Re-rating / Undervalued" and not fundamentals_available:
            conflict_reasons.append("Marked as Re-rating / Undervalued but fundamentals are missing.")
        if computed == "Speculative Optionality":
            max_allowed = allowed_position_percent(computed, holding.get("max_position_percent"), config)
            position_percent = holding.get("position_percent") if in_holdings else None
            if position_percent is not None and pd.notna(position_percent) and position_percent > max_allowed:
                conflict_reasons.append("Marked as Speculative Optionality but position size is too large.")

        if final_purpose not in PURPOSES:
            final_purpose = declared or default_purpose or "Broken / Avoid"
            conflict_reasons.append("Purpose was outside the allowed purpose set and was normalized.")

        if row.get("history_days", 0) < 50:
            reason_parts.append(f"Only {int(row.get('history_days', 0))} days of price history are available.")
        if pd.isna(row.get("close")):
            conflict_reasons.append("Price data is missing, so purpose could not be fully verified.")

        reason_parts.extend(conflict_reasons or ["Purpose is aligned with available data."])
        rows.append(
            {
                "Ticker": ticker,
                "InUniverse": bool(in_universe),
                "IsHolding": bool(in_holdings),
                "DeclaredPrimaryPurpose": declared or "",
                "DefaultPurpose": default_purpose or "",
                "FinalPrimaryPurpose": final_purpose,
                "SecondaryTags": ", ".join(sorted(set(tag for tag in secondary_tags if tag))),
                "ConflictFlag": bool(conflict_reasons),
                "ConflictReasons": " | ".join(conflict_reasons),
                "Theme": universe_row.get("theme", ""),
                "SectorETF": universe_row.get("sector_etf", row.get("sector_etf", "")),
                "Reason": " ".join(reason_parts),
            }
        )
    return pd.DataFrame(rows).sort_values("Ticker")
