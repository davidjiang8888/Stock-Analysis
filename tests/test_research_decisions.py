import pandas as pd

from src.research_decisions import build_research_decisions_frame


def test_research_decisions_block_missing_price_instead_of_weak_recommendation():
    readiness = pd.DataFrame(
        [
            {
                "ticker": "META",
                "name": "Meta Platforms",
                "asset_type": "company",
                "blocked_features": "price, momentum, dcf",
                "missing_data": "needs at least 5 valid price rows with positive close",
                "next_action": "Import staged price rows or refresh price provider for META.",
            }
        ]
    )

    decisions = build_research_decisions_frame(readiness)
    row = decisions.iloc[0]

    assert row["decision_bucket"] == "Blocked by Data"
    assert row["decision_subtype"] == "Blocked by Data - Missing Price"
    assert row["primary_blocker"] == "price"
    assert "Missing usable price data" in row["main_reason"]
    assert row["confidence"] <= 0.45
    assert "Import staged price rows" in row["next_action"]
    assert row["next_best_action"] == row["next_action"]


def test_research_decisions_monitor_etf_and_exclude_company_dcf():
    readiness = pd.DataFrame(
        [
            {
                "ticker": "QQQ",
                "name": "Invesco QQQ",
                "asset_type": "etf",
                "ready_features": "price, momentum, market_direction",
                "partial_features": "liquidity",
                "blocked_features": "earnings, analyst_estimates",
                "excluded_features": "dcf, portfolio",
                "missing_data": "earnings: trusted local CSV input",
                "next_action": "Review ready analysis outputs for QQQ.",
            }
        ]
    )

    decisions = build_research_decisions_frame(readiness)
    row = decisions.iloc[0]

    assert row["decision_bucket"] == "Monitor"
    assert row["decision_subtype"] == "Monitor - ETF Market Proxy"
    assert row["primary_blocker"] == "optional_context"
    assert "excluded from company DCF" in row["main_reason"]
    assert "dcf" in row["excluded_features"]


def test_research_decisions_etf_peer_blocker_does_not_report_fundamentals_as_primary():
    readiness = pd.DataFrame(
        [
            {
                "ticker": "QQQ",
                "name": "Invesco QQQ",
                "asset_type": "etf",
                "ready_features": "price, momentum, market_direction",
                "partial_features": "liquidity",
                "blocked_features": "fundamentals, peer, earnings, analyst_estimates",
                "excluded_features": "dcf, portfolio",
                "missing_data": "peers: needs at least 2 source-backed peer mappings; earnings: trusted local CSV input",
                "next_action": "Add source-backed peer mappings and peer metrics for QQQ.",
            }
        ]
    )

    decisions = build_research_decisions_frame(readiness)
    row = decisions.iloc[0]

    assert row["decision_bucket"] == "Monitor"
    assert row["decision_subtype"] == "Monitor - ETF Market Proxy"
    assert row["primary_blocker"] == "peers"
    assert "excluded from company DCF" in row["main_reason"]


def test_research_decisions_block_company_when_fundamentals_or_dcf_are_missing():
    readiness = pd.DataFrame(
        [
            {
                "ticker": "AMD",
                "name": "Advanced Micro Devices",
                "asset_type": "company",
                "ready_features": "price, momentum, market_direction",
                "partial_features": "peer",
                "blocked_features": "fundamentals, dcf, earnings, analyst_estimates",
                "excluded_features": "portfolio",
                "missing_data": "dcf: free_cash_flow, shares_outstanding, revenue, fcf_margin",
                "next_action": "Import trusted fundamentals for AMD.",
            }
        ]
    )

    decisions = build_research_decisions_frame(readiness)
    row = decisions.iloc[0]

    assert row["decision_bucket"] == "Blocked by Data"
    assert row["decision_subtype"] == "Blocked by Data - Missing Fundamentals"
    assert row["primary_blocker"] == "fundamentals"
    assert "missing dcf, fundamentals data" in row["main_reason"]
    assert row["confidence"] <= 0.45
    assert "Import trusted fundamentals" in row["next_action"]


def test_research_decisions_only_research_now_when_core_data_is_ready():
    readiness = pd.DataFrame(
        [
            {
                "ticker": "NVDA",
                "name": "NVIDIA",
                "asset_type": "company",
                "ready_features": "price, momentum, fundamentals, dcf",
                "partial_features": "peer",
                "blocked_features": "",
                "excluded_features": "portfolio",
                "missing_data": "",
                "next_action": "Review ready analysis outputs for NVDA.",
            }
        ]
    )
    watchlist = pd.DataFrame({"ticker": ["NVDA"], "watchlistscore": [80]})

    decisions = build_research_decisions_frame(readiness, watchlist)
    row = decisions.iloc[0]

    assert row["decision_bucket"] == "Research Now"
    assert row["decision_subtype"] == "Research Candidate - DCF Ready But Peer Blocked"
    assert row["confidence"] > 0.5
    assert row["analysis_score"] == 0.8
    assert "ready: price, momentum, fundamentals, dcf" in row["feature_summary"]
    assert "research brief" in row["purpose_thesis"]
    assert "Valuation" in row["valuation_evaluation"] or "DCF inputs are ready" in row["valuation_evaluation"]
    assert "Invalidate" in row["invalidation_condition"]
    assert "Which source-backed peers" in row["next_research_question"]
    assert "core price, fundamentals, and DCF are ready" in row["confidence_explanation"]


def test_research_decisions_add_evaluation_fields_without_recommendation_language():
    readiness = pd.DataFrame(
        [
            {
                "ticker": "QQQ",
                "name": "Invesco QQQ",
                "asset_type": "etf",
                "ready_features": "price, momentum, market_direction",
                "partial_features": "liquidity",
                "blocked_features": "peer, earnings, analyst_estimates",
                "excluded_features": "dcf, portfolio",
                "missing_data": "peers: needs source-backed peer mappings",
                "next_action": "Add source-backed peer mappings and peer metrics for QQQ.",
            },
            {
                "ticker": "APLD",
                "name": "Applied Digital",
                "asset_type": "company",
                "ready_features": "",
                "partial_features": "",
                "blocked_features": "price, momentum, fundamentals, dcf, peer",
                "excluded_features": "portfolio",
                "missing_data": "needs at least 5 valid price rows with positive close",
                "next_action": "Import staged price rows or refresh price provider for APLD.",
            },
        ]
    )
    watchlist = pd.DataFrame(
        {
            "ticker": ["QQQ", "APLD"],
            "primarypurpose": ["ETF / Defensive / Hedge", "Speculative Optionality"],
            "setupstatus": ["Setup Forming", "Not available"],
            "finalstate": ["Setup Forming", "Ignore"],
            "valuationstatus": ["not_ready", "not_ready"],
            "finalvaluecategory": ["Insufficient Data", "Insufficient Data"],
            "peerrelativestatus": ["Insufficient Peer Data", "Insufficient Peer Data"],
            "watchlistscore": [50, None],
            "rankreason": ["ETF proxy context only.", ""],
            "reason": ["ETF/index proxies are excluded from operating-company DCF.", "Price data is missing."],
        }
    )

    decisions = build_research_decisions_frame(readiness, watchlist)
    qqq = decisions.loc[decisions["ticker"].eq("QQQ")].iloc[0]
    apld = decisions.loc[decisions["ticker"].eq("APLD")].iloc[0]
    rendered = " ".join(decisions.astype(str).to_numpy().ravel()).lower()

    assert "market, theme, liquidity, or risk context" in qqq["purpose_thesis"]
    assert "operating-company dcf is excluded" in qqq["valuation_evaluation"].lower()
    assert "market-proxy usefulness" in qqq["invalidation_condition"]
    assert "source-backed peer mappings" in qqq["next_research_question"]
    assert "analytical blindness" in apld["risk_watchpoint"]
    assert "price history is available" in apld["invalidation_condition"]
    assert "primary blocker is price" in apld["confidence_explanation"]
    assert "buy" not in rendered
    assert "sell" not in rendered
    assert "broker" not in rendered
    assert "order" not in rendered
