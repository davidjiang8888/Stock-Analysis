from __future__ import annotations

import pandas as pd

from src.config import AppConfig
from src.risk import allowed_position_percent, concentration_risk


def review_holdings(
    holdings: pd.DataFrame,
    purpose_df: pd.DataFrame,
    momentum_df: pd.DataFrame,
    config: AppConfig,
) -> pd.DataFrame:
    if holdings.empty:
        return pd.DataFrame(
            columns=[
                "Ticker",
                "PrimaryPurpose",
                "PositionPercent",
                "SetupStatus",
                "ReviewState",
                "ConcentrationRisk",
                "Reason",
            ]
        )

    purpose_map = purpose_df.set_index("Ticker") if not purpose_df.empty else pd.DataFrame()
    momentum_map = momentum_df.set_index("Ticker") if not momentum_df.empty else pd.DataFrame()
    rows: list[dict[str, object]] = []

    for _, holding in holdings.iterrows():
        ticker = holding["ticker"]
        declared_purpose = holding.get("primary_purpose", "")
        purpose_row = purpose_map.loc[ticker] if not purpose_map.empty and ticker in purpose_map.index else pd.Series(dtype=object)
        momentum_row = momentum_map.loc[ticker] if not momentum_map.empty and ticker in momentum_map.index else pd.Series(dtype=object)

        final_purpose = purpose_row.get("FinalPrimaryPurpose", declared_purpose)
        setup_status = momentum_row.get("SetupStatus", "Avoid")
        max_allowed = allowed_position_percent(final_purpose, holding.get("max_position_percent"), config)
        portfolio_threshold = config.get_pct(
            "portfolio_rules",
            "classify_as_concentration_risk_if_position_pct_above",
            0.20,
        )
        is_concentration, concentration_reason = concentration_risk(
            holding.get("position_percent"),
            max_allowed,
            portfolio_threshold=portfolio_threshold,
        )
        reduce_risk_if_oversized = bool(config.risk_rules.get("reduce_risk_if_position_exceeds_max", True))
        reason_parts = [concentration_reason]

        if setup_status == "Broken":
            review_state = "Broken"
            reason_parts.append("Holding trend is broken.")
        elif is_concentration and reduce_risk_if_oversized:
            review_state = "Risk Reduce"
            reason_parts.append("Holding exceeds the configured risk budget.")
        elif bool(purpose_row.get("ConflictFlag")):
            review_state = "Review Thesis"
            reason_parts.append(str(purpose_row.get("ConflictReasons", "Purpose conflicts need review.")))
        elif setup_status == "Pullback Add Candidate":
            add_only_profitable = bool(config.portfolio_rules.get("add_only_to_profitable_positions", True))
            do_not_add_loser = bool(config.portfolio_rules.get("do_not_add_to_losing_trading_positions", True))
            current_close = momentum_row.get("Close")
            cost_basis = holding.get("cost_basis")
            below_cost_basis = cost_basis not in (None, 0) and pd.notna(current_close) and current_close < cost_basis
            if below_cost_basis and (add_only_profitable or do_not_add_loser):
                review_state = "Hold but Do Not Add"
                reason_parts.append("Add-only rule blocked because the position is below cost basis.")
            else:
                review_state = "Add Candidate"
                reason_parts.append("Setup is constructive and aligned with the holding purpose.")
        elif setup_status in {"Watch", "Buyable Area", "Setup Forming"}:
            review_state = "Keep"
            reason_parts.append("Holding purpose and trend remain broadly aligned.")
        elif setup_status == "Extended / No Chase":
            review_state = "Hold but Do Not Add"
            reason_parts.append("Trend is positive but currently extended.")
        else:
            review_state = "Review Thesis"
            reason_parts.append("Current evidence is too weak to keep the thesis on autopilot.")

        rows.append(
            {
                "Ticker": ticker,
                "Shares": holding.get("shares"),
                "CostBasis": holding.get("cost_basis"),
                "PositionPercent": holding.get("position_percent"),
                "PrimaryPurpose": final_purpose,
                "SecondaryTags": holding.get("secondary_tags", ""),
                "OriginalThesis": holding.get("original_thesis", ""),
                "SetupStatus": setup_status,
                "ReviewState": review_state,
                "ConcentrationRisk": is_concentration,
                "MaxAllowedPositionPercent": max_allowed,
                "Reason": " ".join(reason_parts),
            }
        )
    return pd.DataFrame(rows).sort_values("Ticker")
