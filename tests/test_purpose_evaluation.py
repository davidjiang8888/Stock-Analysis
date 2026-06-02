import pandas as pd

from src.purpose_evaluation import (
    build_purpose_evaluation_drilldown,
    build_purpose_evaluation_summary,
    enrich_purpose_evaluation_rows,
)


def test_purpose_evaluation_summary_groups_current_decisions_without_fabricated_context():
    decisions = pd.DataFrame(
        [
            {
                "ticker": "META",
                "asset_type": "stock",
                "decision_bucket": "Research Now",
                "primary_blocker": "peers",
                "purpose_thesis": "Purpose: Core Compounder. Test fundamentals and DCF.",
                "purpose_alignment": "Purpose alignment needs review: peer-relative context is incomplete.",
                "blocked_features": "peer",
                "review_priority_reason": "peer-relative context is incomplete",
                "next_research_question": "Which source-backed peers should be added?",
            },
            {
                "ticker": "QQQ",
                "asset_type": "etf",
                "decision_bucket": "Monitor",
                "primary_blocker": "none",
                "purpose_thesis": "Purpose: ETF / Defensive / Hedge. Use as market context.",
                "purpose_alignment": "Purpose alignment: ETF / Defensive / Hedge is evaluated as market/risk context.",
                "next_research_question": "What market signal is this proxy intended to monitor?",
            },
            {
                "ticker": "BROAD",
                "asset_type": "stock",
                "decision_bucket": "Blocked by Data",
                "primary_blocker": "fundamentals",
                "purpose_thesis": "Purpose: Re-rating / Undervalued. Require fundamentals first.",
                "purpose_alignment": "Purpose alignment is blocked: valuation inputs are missing.",
                "blocked_features": "fundamentals, dcf",
                "missing_data": "free_cash_flow, shares_outstanding",
                "next_research_question": "Which trusted fundamentals are available?",
            },
        ]
    )
    readiness = pd.DataFrame(
        [
            {"ticker": "META", "in_active_universe": True},
            {"ticker": "QQQ", "in_active_universe": True},
            {"ticker": "BROAD", "in_active_universe": False},
        ]
    )

    summary = build_purpose_evaluation_summary(decisions, readiness)
    rendered = " ".join(str(value) for value in summary.to_numpy().ravel()).lower()

    assert {"purpose_family", "decision_bucket", "active_universe_count", "top_unlock_command", "Reason"} <= set(summary.columns)
    assert summary.loc[summary["purpose_family"].eq("Compounder"), "peer_limited_count"].iloc[0] == 1
    assert summary.loc[summary["purpose_family"].eq("Compounder"), "top_unlock_command"].iloc[0] == "make focus-peers TICKER=META"
    assert summary.loc[summary["purpose_family"].eq("ETF / Hedge"), "monitor_count"].iloc[0] == 1
    assert summary.loc[summary["purpose_family"].eq("Re-rating"), "fundamentals_limited_count"].iloc[0] == 1
    assert "source-backed peers" in rendered
    assert "broker" not in rendered
    assert "order" not in rendered
    assert "trading" not in rendered
    assert "buy now" not in rendered
    assert "sell now" not in rendered


def test_purpose_evaluation_enrichment_does_not_match_fundamentals_as_fund_asset():
    decisions = pd.DataFrame(
        [
            {
                "ticker": "A",
                "asset_type": "stock",
                "decision_bucket": "Blocked by Data",
                "primary_blocker": "fundamentals",
                "purpose_thesis": "Purpose: Research candidate. Fundamentals are missing.",
                "purpose_alignment": "Purpose alignment is blocked until fundamentals are complete.",
            }
        ]
    )

    enriched = enrich_purpose_evaluation_rows(decisions)

    assert enriched.iloc[0]["purpose_family"] == "General"
    assert enriched.iloc[0]["unlock_command"] == "make focus-fundamentals TICKER=A"


def test_purpose_evaluation_uses_purpose_classification_when_decisions_are_schema_light():
    decisions = pd.DataFrame(
        [
            {
                "ticker": "NVDA",
                "asset_type": "company",
                "decision_bucket": "Research Now",
                "primary_blocker": "earnings",
                "blocked_features": "earnings, analyst_estimates",
            }
        ]
    )
    purpose_classification = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "FinalPrimaryPurpose": "Momentum Leader",
            }
        ]
    )

    summary = build_purpose_evaluation_summary(decisions, purpose_classification=purpose_classification)

    assert summary.iloc[0]["purpose_family"] == "Momentum"
    assert summary.iloc[0]["optional_context_locked_count"] == 1
    assert summary.iloc[0]["top_unlock_command"] == "make templates"


def test_purpose_evaluation_drilldown_prioritizes_active_rows_and_separates_peer_status():
    decisions = pd.DataFrame(
        [
            {
                "ticker": "META",
                "asset_type": "company",
                "decision_bucket": "Research Now",
                "decision_subtype": "Research Candidate - DCF Ready But Peer Blocked",
                "primary_blocker": "peers",
                "purpose_thesis": "Purpose: Core Compounder. Test fundamentals and DCF.",
                "purpose_alignment": "Purpose alignment needs review: peer-relative context is incomplete.",
                "supported_analysis": "Supported analysis: standalone DCF scenario analysis.",
                "unsupported_analysis": "Unsupported analysis: peer-relative valuation or opportunity-cost comparison.",
                "next_research_question": "Which source-backed peers should be added?",
                "risk_watchpoint": "Risk watchpoint: peer valuation is unavailable.",
                "invalidation_condition": "Invalidate only if local evidence no longer supports the thesis.",
                "confidence_explanation": "Confidence is medium because peer context is missing.",
                "data_confidence": "medium",
                "readiness_score": 0.61,
            },
            {
                "ticker": "BROAD",
                "asset_type": "company",
                "decision_bucket": "Blocked by Data",
                "primary_blocker": "price",
                "purpose_thesis": "Purpose: Core Compounder.",
            },
        ]
    )
    readiness = pd.DataFrame(
        [
            {"ticker": "META", "in_active_universe": True, "overall_readiness_state": "partial", "updated_at": "2026-06-01"},
            {"ticker": "BROAD", "in_active_universe": False, "overall_readiness_state": "blocked", "updated_at": "2026-06-01"},
        ]
    )
    peers = pd.DataFrame(
        [
            {
                "ticker": "META",
                "peer_trend_comparison_ready": True,
                "peer_valuation_comparison_ready": False,
            }
        ]
    )

    drilldown = build_purpose_evaluation_drilldown(decisions, readiness, peer_readiness=peers, active_only=True)
    rendered = " ".join(str(value) for value in drilldown.to_numpy().ravel()).lower()

    assert list(drilldown["ticker"]) == ["META"]
    assert drilldown.iloc[0]["purpose_family"] == "Compounder"
    assert drilldown.iloc[0]["unlock_command"] == "make focus-peers TICKER=META"
    assert drilldown.iloc[0]["peer_trend_status"] == "peer trend possible"
    assert drilldown.iloc[0]["peer_valuation_status"] == "peer valuation blocked"
    assert "source-backed peers" in rendered
    assert "copy-only command" in rendered
    assert "broker" not in rendered
    assert "order" not in rendered
    assert "trading" not in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered


def test_purpose_evaluation_drilldown_filters_and_limits_rows():
    decisions = pd.DataFrame(
        [
            {"ticker": "META", "asset_type": "company", "decision_bucket": "Research Now", "primary_blocker": "peers", "purpose_thesis": "Purpose: Core Compounder."},
            {"ticker": "NVDA", "asset_type": "company", "decision_bucket": "Research Now", "primary_blocker": "earnings", "purpose_thesis": "Purpose: Momentum Leader."},
            {"ticker": "QQQ", "asset_type": "etf", "decision_bucket": "Monitor", "primary_blocker": "none", "purpose_thesis": "Purpose: ETF / Defensive / Hedge."},
        ]
    )
    readiness = pd.DataFrame(
        [
            {"ticker": "META", "in_active_universe": True},
            {"ticker": "NVDA", "in_active_universe": True},
            {"ticker": "QQQ", "in_active_universe": True},
        ]
    )

    drilldown = build_purpose_evaluation_drilldown(
        decisions,
        readiness,
        active_only=True,
        purpose_family="Momentum",
        limit=1,
    )

    assert list(drilldown["ticker"]) == ["NVDA"]
    assert len(drilldown) == 1
    assert drilldown.iloc[0]["unlock_command"] == "make templates"


def test_purpose_evaluation_drilldown_keeps_etf_monitor_on_stock_report_when_peer_blocked():
    decisions = pd.DataFrame(
        [
            {
                "ticker": "QQQ",
                "asset_type": "etf",
                "decision_bucket": "Monitor",
                "decision_subtype": "Monitor - ETF Market Proxy",
                "primary_blocker": "peers",
                "purpose_thesis": "Purpose: ETF / Defensive / Hedge. Use as market context.",
            },
            {
                "ticker": "META",
                "asset_type": "company",
                "decision_bucket": "Research Now",
                "decision_subtype": "Research Candidate - DCF Ready But Peer Blocked",
                "primary_blocker": "peers",
                "purpose_thesis": "Purpose: Core Compounder.",
            },
        ]
    )
    readiness = pd.DataFrame(
        [
            {"ticker": "QQQ", "in_active_universe": True},
            {"ticker": "META", "in_active_universe": True},
        ]
    )

    drilldown = build_purpose_evaluation_drilldown(decisions, readiness, active_only=True)
    rendered = " ".join(str(value) for value in drilldown.to_numpy().ravel()).lower()

    qqq = drilldown.loc[drilldown["ticker"].eq("QQQ")].iloc[0]
    meta = drilldown.loc[drilldown["ticker"].eq("META")].iloc[0]

    assert qqq["purpose_family"] == "ETF / Hedge"
    assert qqq["unlock_command"] == "make stock-report TICKER=QQQ"
    assert meta["unlock_command"] == "make focus-peers TICKER=META"
    assert "copy-only command" in rendered
    assert "broker" not in rendered
    assert "order" not in rendered
    assert "trading" not in rendered
    assert "buy" not in rendered
    assert "sell" not in rendered
