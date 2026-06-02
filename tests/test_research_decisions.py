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
                "blocked_features": "earnings, analyst_estimates",
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
    assert "Purpose alignment" in row["purpose_alignment"]
    assert "Valuation" in row["valuation_evaluation"] or "DCF inputs are ready" in row["valuation_evaluation"]
    assert "standalone DCF scenario analysis" in row["supported_analysis"]
    assert "earnings timing" in row["unsupported_analysis"]
    assert "Invalidate" in row["invalidation_condition"]
    assert "Which source-backed peers" in row["next_research_question"]
    assert "peer-relative context is still limiting" in row["review_priority_reason"]
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
    assert "operating-company valuation is not applicable" in qqq["purpose_alignment"]
    assert "operating-company dcf is excluded" in qqq["valuation_evaluation"].lower()
    assert "ETF/index monitoring" in qqq["supported_analysis"]
    assert "operating-company DCF conclusions" in qqq["unsupported_analysis"]
    assert "market-proxy usefulness" in qqq["invalidation_condition"]
    assert "source-backed peer mappings" in qqq["next_research_question"]
    assert "Monitor priority" in qqq["review_priority_reason"]
    assert "analytical blindness" in apld["risk_watchpoint"]
    assert "none yet" in apld["supported_analysis"]
    assert "trend, setup, liquidity" in apld["unsupported_analysis"]
    assert "price history is available" in apld["invalidation_condition"]
    assert "primary blocker is price" in apld["confidence_explanation"]
    assert "buy" not in rendered
    assert "sell" not in rendered
    assert "broker" not in rendered
    assert "order" not in rendered


def test_research_decisions_surface_purpose_conflict_as_review_context_not_recommendation():
    readiness = pd.DataFrame(
        [
            {
                "ticker": "META",
                "name": "Meta Platforms",
                "asset_type": "company",
                "ready_features": "price, momentum, market_direction, liquidity, correlation",
                "partial_features": "",
                "blocked_features": "fundamentals, dcf, peer, earnings, analyst_estimates",
                "excluded_features": "portfolio",
                "missing_data": "dcf: shares_outstanding",
                "next_action": "Import trusted fundamentals for META.",
            }
        ]
    )
    watchlist = pd.DataFrame(
        {
            "ticker": ["META"],
            "primarypurpose": ["Core Compounder"],
            "setupstatus": ["Broken"],
            "reviewstate": ["Broken"],
            "finalstate": ["Broken"],
            "watchlistscore": [13],
            "rankreason": ["Base score from final state Broken."],
            "reason": ["Marked as Core Compounder but trend is below the 50SMA. Holding trend is broken."],
        }
    )

    row = build_research_decisions_frame(readiness, watchlist).iloc[0]
    rendered = " ".join(str(value) for value in row.to_numpy()).lower()

    assert row["decision_bucket"] == "Blocked by Data"
    assert row["primary_blocker"] == "fundamentals"
    assert "Purpose alignment needs review" in row["purpose_alignment"]
    assert "Core Compounder" in row["purpose_alignment"]
    assert "fundamental quality" in row["unsupported_analysis"]
    assert "compounder purpose conflicts" in row["review_priority_reason"]
    assert "confirm whether the compounder thesis remains supported" in row["next_research_question"]
    assert "buy" not in rendered
    assert "sell" not in rendered
    assert "broker" not in rendered
    assert "order" not in rendered


def test_research_decisions_normalize_watchlist_columns_for_evaluation_fields():
    readiness = pd.DataFrame(
        [
            {
                "ticker": "A",
                "name": "Agilent",
                "asset_type": "company",
                "ready_features": "price, momentum, fundamentals, dcf",
                "partial_features": float("nan"),
                "blocked_features": "peer, earnings, analyst_estimates",
                "excluded_features": "portfolio",
                "missing_data": "peers: source-backed mappings required",
                "next_action": "Review ready analysis outputs for A.",
            }
        ]
    )
    watchlist = pd.DataFrame(
        {
            "Ticker": ["A"],
            "PrimaryPurpose": ["Core Compounder"],
            "SetupStatus": ["Setup Forming"],
            "FinalState": ["Setup Forming"],
            "ValuationStatus": ["ready"],
            "FinalValueCategory": ["Insufficient Data"],
            "PeerRelativeStatus": ["Insufficient Peer Data"],
            "WatchlistScore": [68],
            "RankReason": ["Base score from final state Setup Forming."],
            "Reason": ["Purpose is aligned with available data."],
        }
    )

    row = build_research_decisions_frame(readiness, watchlist).iloc[0]

    assert "Core Compounder" in row["purpose_thesis"]
    assert "Setup Forming" in row["purpose_alignment"]
    assert "Partial inputs present: nan" not in row["supported_analysis"]
    assert row["analysis_score"] == 0.68


def test_research_decisions_tailor_momentum_leader_brief_without_recommendation_language():
    readiness = pd.DataFrame(
        [
            {
                "ticker": "NVDA",
                "name": "NVIDIA",
                "asset_type": "company",
                "ready_features": "price, momentum, market_direction, liquidity, correlation, fundamentals, dcf",
                "partial_features": "peer",
                "blocked_features": "earnings, analyst_estimates",
                "excluded_features": "portfolio",
                "missing_data": "analyst_estimates: trusted local CSV input",
                "next_action": "Review ready analysis outputs for NVDA.",
            }
        ]
    )
    watchlist = pd.DataFrame(
        {
            "ticker": ["NVDA"],
            "primarypurpose": ["Momentum Leader"],
            "setupstatus": ["Setup Forming"],
            "finalstate": ["Review Thesis"],
            "reviewstate": ["Review Thesis"],
            "watchlistscore": [48],
            "reason": ["Marked as Momentum Leader but relative strength is weak."],
        }
    )

    row = build_research_decisions_frame(readiness, watchlist).iloc[0]
    rendered = " ".join(str(value) for value in row.to_numpy()).lower()

    assert "trend, relative strength, extension risk" in row["purpose_thesis"]
    assert "weak relative strength" in row["purpose_alignment"]
    assert "Momentum setup" in row["setup_evaluation"]
    assert "momentum review can use trend" in row["supported_analysis"]
    assert "relative-strength deterioration" in row["risk_watchpoint"]
    assert "extension risk" in row["invalidation_condition"]
    assert "relative strength, trend quality" in row["next_research_question"]
    assert "momentum purpose has enough core data" in row["review_priority_reason"]
    assert "buy" not in rendered
    assert "sell" not in rendered
    assert "broker" not in rendered
    assert "order" not in rendered


def test_research_decisions_tailor_rerating_and_speculative_boundaries():
    readiness = pd.DataFrame(
        [
            {
                "ticker": "VALUE",
                "name": "Value Example",
                "asset_type": "company",
                "ready_features": "price, momentum",
                "partial_features": "",
                "blocked_features": "fundamentals, dcf, peer, earnings, analyst_estimates",
                "excluded_features": "portfolio",
                "missing_data": "dcf: free_cash_flow",
                "next_action": "Import trusted fundamentals for VALUE.",
            },
            {
                "ticker": "SPEC",
                "name": "Spec Example",
                "asset_type": "company",
                "ready_features": "",
                "partial_features": "",
                "blocked_features": "price, momentum, fundamentals, dcf, peer",
                "excluded_features": "portfolio",
                "missing_data": "needs at least 5 valid price rows",
                "next_action": "Import staged price rows for SPEC.",
            },
        ]
    )
    watchlist = pd.DataFrame(
        {
            "ticker": ["VALUE", "SPEC"],
            "primarypurpose": ["Re-rating / Undervalued", "Speculative Optionality"],
            "setupstatus": ["Watch", "Not available"],
            "finalstate": ["Watch", "Ignore"],
            "reason": ["Valuation inputs are incomplete.", "Price data is missing."],
        }
    )

    decisions = build_research_decisions_frame(readiness, watchlist)
    value = decisions.loc[decisions["ticker"].eq("VALUE")].iloc[0]
    spec = decisions.loc[decisions["ticker"].eq("SPEC")].iloc[0]
    rendered = " ".join(decisions.astype(str).to_numpy().ravel()).lower()

    assert "fundamentals, DCF, and peer context" in value["purpose_thesis"]
    assert "re-rating read" in value["purpose_alignment"]
    assert "re-rating or undervaluation conclusion" in value["unsupported_analysis"]
    assert "overclaim" in value["risk_watchpoint"]
    assert "re-rating interpretation" in value["invalidation_condition"]
    assert "re-rating read is supportable" in value["next_research_question"]
    assert "valuation-gated" in value["review_priority_reason"]
    assert "high-uncertainty research" in spec["purpose_thesis"]
    assert "speculative setup and volatility read" in spec["unsupported_analysis"]
    assert "trusted price rows" in spec["next_research_question"]
    assert "speculative optionality cannot be evaluated" in spec["review_priority_reason"]
    assert "buy" not in rendered
    assert "sell" not in rendered
    assert "broker" not in rendered
    assert "order" not in rendered
