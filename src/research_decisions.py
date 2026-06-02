from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.loader import normalize_columns
from src.paths import format_path_context, resolve_data_dir, resolve_outputs_dir, resolve_project_root
from src.readiness_engine import build_ticker_readiness_report


DECISION_COLUMNS = [
    "ticker",
    "name",
    "asset_type",
    "exchange",
    "sector",
    "industry",
    "theme",
    "decision_bucket",
    "decision_subtype",
    "confidence",
    "main_reason",
    "primary_blocker",
    "supporting_features",
    "blocked_features",
    "excluded_features",
    "missing_data",
    "next_action",
    "next_best_action",
    "data_readiness_score",
    "readiness_score",
    "data_confidence",
    "analysis_score",
    "decision_score",
    "purpose_thesis",
    "purpose_alignment",
    "setup_evaluation",
    "valuation_evaluation",
    "supported_analysis",
    "unsupported_analysis",
    "risk_watchpoint",
    "invalidation_condition",
    "next_research_question",
    "review_priority_reason",
    "confidence_explanation",
    "feature_summary",
    "updated_at",
    "Reason",
]

CORE_COMPANY_BLOCKERS = {"fundamentals", "dcf"}


def _now() -> str:
    return pd.Timestamp.now(tz="UTC").isoformat()


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    frame.columns = normalize_columns(list(frame.columns))
    if "ticker" in frame.columns:
        frame["ticker"] = frame["ticker"].astype("string").str.upper().str.strip()
    return frame


def _split_features(value: Any) -> list[str]:
    if value is None:
        return []
    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "null", "<na>"}:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _score_features(ready: list[str], partial: list[str], blocked: list[str], excluded: list[str]) -> float:
    possible = len(ready) + len(partial) + len(blocked)
    if possible <= 0:
        return 0.0
    score = (len(ready) + 0.45 * len(partial)) / possible
    if blocked:
        score *= max(0.35, 1 - 0.07 * len(blocked))
    if excluded and not ready:
        score *= 0.8
    return round(float(max(0, min(score, 1))), 3)


def _data_confidence_label(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.55:
        return "medium"
    if score >= 0.25:
        return "low"
    return "blocked"


def _primary_blocker(blocked: list[str], missing_data: Any) -> str:
    blocked_set = set(blocked)
    missing_text = str(missing_data or "").lower()
    if "price" in blocked_set or "price" in missing_text:
        return "price"
    if {"fundamentals", "dcf"} & blocked_set or any(
        token in missing_text
        for token in ("free_cash_flow", "shares_outstanding", "revenue", "fcf_margin", "fundamental")
    ):
        return "fundamentals"
    if "peer" in blocked_set or "peer" in missing_text:
        return "peers"
    if "earnings" in blocked_set:
        return "earnings"
    if "analyst_estimates" in blocked_set:
        return "analyst_estimates"
    if blocked:
        return blocked[0]
    return "none"


def _decision_subtype(
    bucket: str,
    asset_type: str,
    ready: list[str],
    partial: list[str],
    blocked: list[str],
    excluded: list[str],
    primary_blocker: str,
) -> str:
    if bucket == "Monitor" and asset_type in {"etf", "index_proxy", "fund"}:
        return "Monitor - ETF Market Proxy"
    if bucket == "Monitor" and ("price" in ready or "momentum" in ready):
        return "Monitor - Price/Momentum Ready"
    if bucket == "Research Now" and "dcf" in ready and ("peer" in blocked or "peer" in partial):
        return "Research Candidate - DCF Ready But Peer Blocked"
    if bucket == "Research Now":
        return "Research Candidate - Core Data Ready"
    if bucket == "Blocked by Data":
        labels = {
            "price": "Blocked by Data - Missing Price",
            "fundamentals": "Blocked by Data - Missing Fundamentals",
            "peers": "Blocked by Data - Missing Peer Mapping",
            "earnings": "Blocked by Data - Missing Optional Context",
            "analyst_estimates": "Blocked by Data - Missing Optional Context",
        }
        return labels.get(primary_blocker, "Blocked by Data - Missing Required Inputs")
    if bucket == "Excluded" and "dcf" in excluded:
        return "Excluded - DCF Not Applicable"
    return bucket


def _feature_summary(ready: list[str], partial: list[str], blocked: list[str], excluded: list[str]) -> str:
    parts = [
        f"ready: {', '.join(ready) or '-'}",
        f"partial: {', '.join(partial) or '-'}",
        f"blocked: {', '.join(blocked) or '-'}",
        f"excluded: {', '.join(excluded) or '-'}",
    ]
    return "; ".join(parts)


def _text_value(value: Any, fallback: str = "Not available") -> str:
    if value is None:
        return fallback
    try:
        if pd.isna(value):
            return fallback
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "<na>"}:
        return fallback
    return text


def _purpose_value(asset_type: str, watch_row: pd.Series) -> str:
    return _text_value(
        watch_row.get("primarypurpose"),
        "ETF / Defensive / Hedge" if asset_type in {"etf", "index_proxy", "fund"} else "Research candidate",
    )


def _purpose_family(purpose: str, asset_type: str) -> str:
    normalized = purpose.lower()
    if asset_type in {"etf", "index_proxy", "fund"} or "etf" in normalized or "hedge" in normalized or "defensive" in normalized:
        return "etf_hedge"
    if "momentum" in normalized:
        return "momentum"
    if "pullback" in normalized:
        return "pullback"
    if "compounder" in normalized or "core" in normalized:
        return "compounder"
    if "re-rating" in normalized or "undervalued" in normalized or "value" in normalized:
        return "rerating"
    if "speculative" in normalized or "optionality" in normalized:
        return "speculative"
    if "broken" in normalized or "avoid" in normalized:
        return "broken"
    return "general"


def _purpose_thesis(asset_type: str, watch_row: pd.Series, ready: list[str], blocked: list[str]) -> str:
    purpose = _purpose_value(asset_type, watch_row)
    family = _purpose_family(purpose, asset_type)
    final_state = _text_value(watch_row.get("finalstate"), "readiness gated")
    if asset_type in {"etf", "index_proxy", "fund"}:
        return f"Purpose: {purpose}. Evaluate as market, theme, liquidity, or risk context; operating-company valuation remains excluded."
    if family == "momentum":
        return f"Purpose: {purpose}. Judge the brief through trend, relative strength, extension risk, and setup quality; current state is {final_state}."
    if family == "compounder":
        return f"Purpose: {purpose}. Test whether trend, fundamentals, and DCF support the long-duration thesis; current state is {final_state}."
    if family == "speculative":
        return f"Purpose: {purpose}. Treat the brief as high-uncertainty research; price, volatility, and data gaps matter before thesis quality."
    if family == "rerating":
        return f"Purpose: {purpose}. Require fundamentals, DCF, and peer context before any re-rating interpretation is supported."
    if family == "pullback":
        return f"Purpose: {purpose}. Evaluate pullback quality only when price and momentum data support setup context; current state is {final_state}."
    if family == "broken":
        return f"Purpose: {purpose}. Treat the row as thesis-review context and data triage, not a transaction instruction."
    if "dcf" in ready and "fundamentals" in ready:
        return f"Purpose: {purpose}. Current setup is {final_state}; available data supports a research brief, not a recommendation."
    if {"fundamentals", "dcf"} & set(blocked):
        return f"Purpose: {purpose}. Thesis cannot be evaluated fully until trusted fundamentals and DCF inputs are complete."
    return f"Purpose: {purpose}. Current setup is {final_state}; interpretation is limited to ready local features."


def _purpose_alignment(asset_type: str, watch_row: pd.Series, ready: list[str], blocked: list[str]) -> str:
    purpose = _purpose_value(asset_type, watch_row)
    family = _purpose_family(purpose, asset_type)
    final_state = _text_value(watch_row.get("finalstate"), "")
    review_state = _text_value(watch_row.get("reviewstate"), "")
    setup = _text_value(watch_row.get("setupstatus"), "")
    reason = _text_value(watch_row.get("reason"), "")
    reason_lower = reason.lower()
    if "price" in blocked:
        return f"Purpose alignment for {purpose} cannot be checked until usable price history exists."
    if asset_type in {"etf", "index_proxy", "fund"}:
        return f"Purpose alignment: {purpose} is evaluated as market/risk context when price, liquidity, and correlation data are ready; operating-company valuation is not applicable."
    if family == "momentum" and ("weak rs" in reason_lower or "relative strength is weak" in reason_lower):
        return f"Purpose alignment needs review: {purpose} requires relative strength support, but current local outputs flag weak relative strength."
    if family == "compounder" and ("broken" in final_state.lower() or "trend is broken" in reason_lower or "below the 50sma" in reason_lower):
        return f"Purpose alignment needs review: {purpose} depends on durable thesis support, but current local outputs flag trend/thesis conflict. {reason}"
    if family == "rerating" and ("dcf" in blocked or "fundamentals" in blocked or "peer" in blocked):
        return f"Purpose alignment is blocked: {purpose} requires valuation inputs, but missing fundamentals, DCF, or peer context prevents a supported re-rating read."
    if family == "speculative" and "price" not in ready:
        return f"Purpose alignment for {purpose} is not testable until price, liquidity, and volatility context are available."
    if final_state in {"Broken", "Review Thesis", "Risk Reduce"} or review_state in {"Broken", "Review Thesis", "Risk Reduce"}:
        context = reason if reason != "Not available" else f"final state is {final_state or review_state}"
        return f"Purpose alignment needs review: current local outputs show `{final_state or review_state}` for {purpose}. {context}"
    if "marked as" in reason_lower or "conflict" in reason_lower or "but trend" in reason_lower:
        return f"Purpose alignment needs review: {reason}"
    if setup and setup != "Not available":
        return f"Purpose alignment appears consistent with current setup `{setup}` for {purpose}, subject to the missing-data limits below."
    return f"Purpose alignment is not fully testable yet for {purpose}; use the ready features and blocker list before interpreting thesis quality."


def _setup_evaluation(watch_row: pd.Series, ready: list[str], blocked: list[str]) -> str:
    purpose = _purpose_value("company", watch_row)
    family = _purpose_family(purpose, "company")
    setup = _text_value(watch_row.get("setupstatus"), "Not available")
    final_state = _text_value(watch_row.get("finalstate"), "Not available")
    rank_reason = _text_value(watch_row.get("rankreason"), "")
    if "price" in blocked:
        return "Setup cannot be evaluated because usable price history is missing."
    if setup != "Not available":
        suffix = f" {rank_reason}" if rank_reason else ""
        if family == "momentum":
            return f"Momentum setup: {setup}; final state: {final_state}. Check relative strength, trend, volume context, and extension risk before deeper research.{suffix}".strip()
        if family == "pullback":
            return f"Pullback setup: {setup}; final state: {final_state}. Confirm price support and momentum stabilization before treating the setup as research-ready.{suffix}".strip()
        if family == "compounder":
            if final_state in {"Broken", "Review Thesis", "Risk Reduce"}:
                return f"Compounder setup: {setup}; final state: {final_state}. Trend conflict matters because it can challenge the stated long-duration purpose.{suffix}".strip()
            return f"Compounder setup: {setup}; final state: {final_state}. Track trend quality alongside fundamentals and DCF before treating the long-duration thesis as well supported.{suffix}".strip()
        return f"Setup status: {setup}; final state: {final_state}.{suffix}".strip()
    if "momentum" in ready:
        return "Momentum is ready, but setup detail is not available in the current watchlist output."
    return "Setup interpretation is unavailable until price and momentum inputs are ready."


def _valuation_evaluation(asset_type: str, watch_row: pd.Series, ready: list[str], blocked: list[str], excluded: list[str]) -> str:
    valuation_status = _text_value(watch_row.get("valuationstatus"), "Not available")
    value_category = _text_value(watch_row.get("finalvaluecategory"), "Not available")
    peer_status = _text_value(watch_row.get("peerrelativestatus"), "Not available")
    if asset_type in {"etf", "index_proxy", "fund"} or "dcf" in excluded:
        return "Operating-company DCF is excluded for this asset type; use market/risk context instead of valuation conclusions."
    if "dcf" in ready:
        if value_category.lower() == "insufficient data" or peer_status.lower() in {"insufficient peer data", "peer data unavailable"}:
            return f"DCF inputs are ready, but valuation interpretation is constrained by {value_category} and peer status `{peer_status}`."
        return f"Valuation status: {valuation_status}; value category: {value_category}; peer context: {peer_status}."
    if "dcf" in blocked or "fundamentals" in blocked:
        return "Valuation conclusion is blocked until trusted DCF/fundamental inputs are complete."
    return "Valuation interpretation is not supported by the current local outputs."


def _supported_analysis(bucket: str, asset_type: str, ready: list[str], partial: list[str], excluded: list[str]) -> str:
    supported: list[str] = []
    if "price" in ready:
        supported.append("price history")
    if "momentum" in ready:
        supported.append("setup and momentum context")
    if "market_direction" in ready:
        supported.append("market/theme context")
    if "liquidity" in ready:
        supported.append("liquidity context")
    if "correlation" in ready:
        supported.append("correlation/risk context")
    if asset_type not in {"etf", "index_proxy", "fund"} and "fundamentals" in ready:
        supported.append("fundamental context")
    if asset_type not in {"etf", "index_proxy", "fund"} and "dcf" in ready:
        supported.append("standalone DCF scenario analysis")
    if "peer" in ready:
        supported.append("peer-relative comparison")
    if asset_type in {"etf", "index_proxy", "fund"} or "dcf" in excluded:
        supported.append("ETF/index monitoring, not operating-company valuation")
    if not supported:
        return "Supported analysis: none yet; this row is an unlock checklist until core inputs are available."
    partial_text = f" Partial inputs present: {', '.join(partial)}." if partial else ""
    return f"Supported analysis: {', '.join(supported)}.{partial_text}"


def _purpose_supported_analysis(asset_type: str, watch_row: pd.Series, ready: list[str]) -> str:
    purpose = _purpose_value(asset_type, watch_row)
    family = _purpose_family(purpose, asset_type)
    if family == "momentum" and {"price", "momentum"} <= set(ready):
        return "Purpose-specific support: momentum review can use trend, setup, and relative-strength context, while valuation remains secondary."
    if family == "compounder" and "fundamentals" in ready and "dcf" in ready:
        return "Purpose-specific support: compounder review can use fundamentals and standalone DCF, but thesis quality still depends on trend and source freshness."
    if family == "etf_hedge" and "price" in ready:
        return "Purpose-specific support: ETF/hedge review can use market, theme, liquidity, and correlation context; company valuation is excluded."
    if family == "speculative" and "price" in ready:
        return "Purpose-specific support: speculative review can use price and volatility context, but missing fundamentals keep thesis quality uncertain."
    if family == "rerating" and "dcf" in ready and "fundamentals" in ready:
        return "Purpose-specific support: re-rating review can use standalone DCF/fundamentals, but peer and optional context still constrain interpretation."
    if family == "pullback" and {"price", "momentum"} <= set(ready):
        return "Purpose-specific support: pullback review can use setup, price support, and momentum stabilization context."
    if family == "broken":
        return "Purpose-specific support: broken/avoid rows support thesis review and blocker diagnosis only."
    return ""


def _unsupported_analysis(asset_type: str, watch_row: pd.Series, blocked: list[str], excluded: list[str]) -> str:
    purpose = _purpose_value(asset_type, watch_row)
    family = _purpose_family(purpose, asset_type)
    unsupported: list[str] = []
    if "price" in blocked:
        unsupported.append("trend, setup, liquidity, volatility, and relative strength")
    if "fundamentals" in blocked:
        unsupported.append("fundamental quality and operating-company valuation")
    if "dcf" in blocked:
        unsupported.append("DCF interpretation")
    if "peer" in blocked:
        unsupported.append("peer-relative valuation or opportunity-cost comparison")
    if "earnings" in blocked:
        unsupported.append("earnings timing or surprise context")
    if "analyst_estimates" in blocked:
        unsupported.append("analyst estimate trend context")
    if asset_type in {"etf", "index_proxy", "fund"} or "dcf" in excluded:
        unsupported.append("operating-company DCF conclusions")
    if family == "momentum" and ("price" in blocked or "momentum" in blocked):
        unsupported.append("momentum leadership assessment")
    if family == "compounder" and ("fundamentals" in blocked or "dcf" in blocked):
        unsupported.append("compounder thesis confirmation")
    if family == "rerating" and ("fundamentals" in blocked or "dcf" in blocked or "peer" in blocked):
        unsupported.append("re-rating or undervaluation conclusion")
    if family == "pullback" and ("price" in blocked or "momentum" in blocked):
        unsupported.append("pullback setup quality")
    if family == "speculative" and "price" in blocked:
        unsupported.append("speculative setup and volatility read")
    if not unsupported:
        return "Unsupported analysis: no major blocked analysis areas are listed, but conclusions still depend on source freshness and assumptions."
    return f"Unsupported analysis: {', '.join(dict.fromkeys(unsupported))}."


def _risk_watchpoint(asset_type: str, watch_row: pd.Series, ready: list[str], blocked: list[str]) -> str:
    purpose = _purpose_value(asset_type, watch_row)
    family = _purpose_family(purpose, asset_type)
    final_state = _text_value(watch_row.get("finalstate"), "")
    setup = _text_value(watch_row.get("setupstatus"), "")
    reason = _text_value(watch_row.get("reason"), "")
    if "price" in blocked:
        return "Primary risk is analytical blindness from missing price history; do not interpret trend or volatility yet."
    if family == "momentum":
        return "Risk watchpoint: momentum purpose is sensitive to relative-strength deterioration, extension risk, and trend breaks."
    if family == "compounder" and final_state in {"Broken", "Review Thesis", "Risk Reduce"}:
        return f"Risk watchpoint: compounder purpose is under thesis review because final state is `{final_state}`. {reason}".strip()
    if family == "speculative":
        return "Risk watchpoint: speculative optionality has high uncertainty; missing fundamentals, volatility context, or liquidity gaps reduce interpretability."
    if family == "rerating":
        return "Risk watchpoint: re-rating analysis can overclaim when DCF, peer, or optional context is incomplete."
    if family == "pullback":
        return "Risk watchpoint: pullback purpose depends on support holding and momentum stabilizing; unsupported setup reads should stay locked."
    if family == "broken":
        return "Risk watchpoint: broken/avoid purpose is a thesis-review label, not a transaction instruction."
    if final_state in {"Broken", "Risk Reduce", "Review Thesis"}:
        return f"Risk watchpoint: final state is `{final_state}`. {reason}".strip()
    if setup == "Extended / No Chase":
        return "Risk watchpoint: setup is extended; avoid over-interpreting momentum without a pullback or consolidation context."
    if asset_type in {"etf", "index_proxy", "fund"}:
        return "Risk watchpoint: monitor liquidity, correlation, and theme exposure; company-specific DCF does not apply."
    if "peer" in blocked:
        return "Risk watchpoint: peer-relative context is incomplete, so valuation comparison and opportunity cost remain uncertain."
    return "Risk watchpoint: monitor setup deterioration, valuation-input quality, and missing optional context."


def _invalidation_condition(asset_type: str, watch_row: pd.Series, ready: list[str], blocked: list[str]) -> str:
    purpose = _purpose_value(asset_type, watch_row)
    family = _purpose_family(purpose, asset_type)
    final_state = _text_value(watch_row.get("finalstate"), "")
    if "price" in blocked:
        return "Invalidation cannot be defined from local price data until price history is available."
    if final_state == "Broken":
        return "Already invalidated for trend/purpose review in the current local setup state."
    if asset_type in {"etf", "index_proxy", "fund"}:
        return "Invalidate market-proxy usefulness if liquidity, correlation, or theme trend no longer supports the intended monitoring role."
    if family == "momentum":
        return "Invalidate the momentum research setup if relative strength weakens, trend support fails, or extension risk dominates the setup."
    if family == "compounder":
        return "Invalidate the compounder thesis review if trend conflict persists and updated fundamentals/DCF no longer support the stated purpose."
    if family == "speculative":
        return "Invalidate speculative research framing if price/liquidity context is missing or the setup cannot be distinguished from data noise."
    if family == "rerating":
        return "Invalidate any re-rating interpretation until fundamentals, DCF assumptions, and peer context are complete enough to support it."
    if family == "pullback":
        return "Invalidate pullback setup framing if price support fails or momentum does not stabilize after the pullback."
    if family == "broken":
        return "Keep broken/avoid rows in thesis-review mode until data and setup evidence justify a different research classification."
    if "momentum" in ready:
        return "Invalidate the current setup if price support fails, relative strength deteriorates, or the watchlist final state turns Broken."
    return "Invalidate only after the missing core inputs are available; current data is insufficient for a setup-level condition."


def _next_research_question(
    watch_row: pd.Series,
    bucket: str,
    asset_type: str,
    primary_blocker: str,
    ready: list[str],
    partial: list[str],
    blocked: list[str],
) -> str:
    purpose = _purpose_value(asset_type, watch_row)
    family = _purpose_family(purpose, asset_type)
    peer_limited = "peer" in blocked or "peer" in partial or primary_blocker == "peers"
    if bucket == "Research Now":
        if family == "momentum":
            return "Does relative strength, trend quality, and extension risk still support the momentum purpose after reviewing the latest local price context?"
        if family == "compounder":
            return "Do trend, fundamentals, DCF assumptions, and thesis conflict notes still support the compounder purpose?"
        if family == "rerating":
            return "Are DCF assumptions, peer context, and missing valuation fields sufficient before considering a re-rating thesis?"
        if peer_limited:
            return "Which source-backed peers and peer metrics would confirm or challenge the standalone DCF and setup read?"
        return "Do purpose, setup, valuation assumptions, and risk watchpoints agree enough to justify deeper manual research?"
    if bucket == "Monitor" and asset_type in {"etf", "index_proxy", "fund"}:
        if peer_limited:
            return "Which source-backed peer mappings or peer metrics would make the market-proxy comparison more trustworthy?"
        return "What market, sector, or hedge signal is this proxy intended to monitor, and is that signal still supported by local price/risk data?"
    if primary_blocker == "price":
        if family == "speculative":
            return "Can trusted price rows be added so speculative optionality can be separated from missing-data noise?"
        return "Can trusted local price rows be added before interpreting setup, risk, or relative strength?"
    if primary_blocker == "fundamentals":
        if family == "compounder":
            return "Which trusted fundamentals or DCF fields are needed to confirm whether the compounder thesis remains supported?"
        if family == "rerating":
            return "Which trusted fundamentals, DCF fields, or peer inputs are missing before a re-rating read is supportable?"
        return "Which trusted fundamentals or DCF fields are missing, and can SEC staging or manual import fill them?"
    if primary_blocker == "peers":
        return "Which source-backed peer mappings or peer metrics are needed before peer-relative analysis is shown?"
    if primary_blocker in {"earnings", "analyst_estimates", "optional_context"}:
        return "Is there trusted local earnings or estimate data worth importing, or should optional context remain locked?"
    return "Which missing input most improves the next supported research read?"


def _review_priority_reason(
    bucket: str,
    subtype: str,
    primary_blocker: str,
    asset_type: str,
    watch_row: pd.Series,
    ready: list[str],
    partial: list[str],
    blocked: list[str],
) -> str:
    purpose = _purpose_value(asset_type, watch_row)
    family = _purpose_family(purpose, asset_type)
    final_state = _text_value(watch_row.get("finalstate"), "")
    score = _text_value(watch_row.get("watchlistscore"), "")
    if family == "momentum" and bucket == "Research Now":
        return "High review priority: momentum purpose has enough core data for trend/relative-strength review, but confirm setup quality manually."
    if family == "compounder" and final_state in {"Broken", "Review Thesis", "Risk Reduce"}:
        return "High review priority: compounder purpose conflicts with current trend/thesis state and needs manual thesis review."
    if family == "rerating" and ("peer" in blocked or "fundamentals" in blocked or "dcf" in blocked):
        return "Unlock priority: re-rating purpose is valuation-gated until fundamentals, DCF, and peer context are sufficiently complete."
    if family == "speculative" and "price" in blocked:
        return "Unlock priority: speculative optionality cannot be evaluated until trusted price history exists."
    if family == "pullback" and ("price" in blocked or "momentum" in blocked):
        return "Unlock priority: pullback purpose requires price and momentum context before setup quality can be reviewed."
    if family == "broken":
        return "Review priority: broken/avoid purpose should remain thesis-review context until readiness supports a different classification."
    if bucket == "Research Now" and ("peer" in blocked or "peer" in partial):
        return "High review priority: core company data is ready, but peer-relative context is still limiting valuation interpretation."
    if bucket == "Research Now":
        return f"High review priority: core data supports a research brief for {purpose}; confirm assumptions, setup, and risk notes manually."
    if bucket == "Monitor" and asset_type in {"etf", "index_proxy", "fund"}:
        return "Monitor priority: use this proxy for market, theme, liquidity, or risk context; do not treat it as operating-company valuation."
    if bucket == "Blocked by Data" and "price" not in blocked and "price" in ready:
        return f"Unlock priority: price context exists, but {primary_blocker} blocks deeper analysis."
    if bucket == "Blocked by Data":
        return f"Unlock priority: {primary_blocker} is the first blocker before setup, valuation, or risk interpretation should be trusted."
    if final_state != "Not available":
        suffix = f" with watchlist score {score}" if score != "Not available" else ""
        return f"Review priority is current-state driven: final state `{final_state}`{suffix}; use readiness before drawing conclusions."
    return f"Review priority follows `{subtype}` and the current readiness blockers."


def _confidence_explanation(bucket: str, data_label: str, primary_blocker: str, ready: list[str], blocked: list[str], excluded: list[str]) -> str:
    if bucket == "Research Now":
        return f"Confidence is {data_label}: core price, fundamentals, and DCF are ready; blockers still reduce breadth: {', '.join(blocked) or 'none'}."
    if bucket == "Monitor":
        return f"Confidence is {data_label}: monitoring is supported by {', '.join(ready) or 'limited ready features'}, while {', '.join(blocked) or 'no blocked features'} remains unavailable."
    if bucket == "Blocked by Data":
        return f"Confidence is {data_label}: primary blocker is {primary_blocker}; blocked features are {', '.join(blocked) or 'not specified'}."
    if bucket == "Excluded":
        return f"Confidence is {data_label}: excluded features are {', '.join(excluded) or 'not specified'}, so unsupported analysis is intentionally omitted."
    return f"Confidence is {data_label}: current readiness does not support a stronger classification."


def build_research_decisions_frame(readiness: pd.DataFrame, final_watchlist: pd.DataFrame | None = None) -> pd.DataFrame:
    final_watchlist = final_watchlist if final_watchlist is not None else pd.DataFrame()
    if not final_watchlist.empty:
        final_watchlist = final_watchlist.copy()
        final_watchlist.columns = normalize_columns(list(final_watchlist.columns))
    if not final_watchlist.empty and "ticker" in final_watchlist.columns:
        final_watchlist["ticker"] = final_watchlist["ticker"].astype("string").str.upper().str.strip()
        watch_lookup = final_watchlist.set_index("ticker", drop=False)
    else:
        watch_lookup = pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for _, row in readiness.iterrows():
        ticker = str(row.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        ready = _split_features(row.get("ready_features"))
        partial = _split_features(row.get("partial_features"))
        blocked = _split_features(row.get("blocked_features"))
        excluded = _split_features(row.get("excluded_features"))
        asset_type = str(row.get("asset_type") or "unknown").lower()
        company_like = asset_type in {"company", "adr", "preferred", "unknown", "other"}
        core_company_blockers = sorted(CORE_COMPANY_BLOCKERS & set(blocked))
        watch_row = watch_lookup.loc[ticker] if not watch_lookup.empty and ticker in watch_lookup.index else pd.Series(dtype=object)
        if isinstance(watch_row, pd.DataFrame):
            watch_row = watch_row.iloc[-1]
        analysis_score = pd.to_numeric(pd.Series([watch_row.get("watchlistscore")]), errors="coerce").iloc[0] if not watch_row.empty else pd.NA
        analysis_score_normalized = 0.0 if pd.isna(analysis_score) else min(max(float(analysis_score) / 100.0, 0), 1)
        data_score = _score_features(ready, partial, blocked, excluded)
        primary_blocker = _primary_blocker(blocked, row.get("missing_data", ""))

        if "price" in blocked:
            bucket = "Blocked by Data"
            main_reason = "Missing usable price data."
        elif asset_type in {"etf", "index_proxy", "fund"} and "price" in ready:
            bucket = "Monitor"
            main_reason = f"{asset_type} is usable for market/risk monitoring and excluded from company DCF."
        elif "dcf" in excluded and not ready:
            bucket = "Excluded"
            main_reason = "Ticker is excluded from the relevant company analysis."
        elif company_like and core_company_blockers:
            bucket = "Blocked by Data"
            main_reason = f"Company research is blocked by missing {', '.join(core_company_blockers)} data."
        elif asset_type == "company" and "momentum" in ready and "dcf" in ready and "fundamentals" in ready:
            bucket = "Research Now"
            main_reason = "Core data is ready for a supported research pass."
        elif "momentum" in ready or "price" in ready:
            bucket = "Monitor"
            main_reason = "Price-supported monitoring is available, but deeper data is still partial or blocked."
        elif blocked:
            bucket = "Blocked by Data"
            main_reason = "Required research data is missing."
        else:
            bucket = "Review Later"
            main_reason = "Ticker is known but not currently supported by enough analysis-ready data."

        if bucket == "Monitor" and asset_type in {"etf", "index_proxy", "fund"}:
            if "peer" in blocked:
                primary_blocker = "peers"
            elif "earnings" in blocked or "analyst_estimates" in blocked:
                primary_blocker = "optional_context"
            else:
                primary_blocker = "none"

        if bucket == "Research Now":
            confidence = min(0.9, 0.55 * data_score + 0.45 * analysis_score_normalized)
        elif bucket == "Monitor":
            confidence = min(0.75, 0.65 * data_score + 0.25 * analysis_score_normalized)
        elif bucket == "Blocked by Data":
            confidence = min(0.45, 0.2 + 0.15 * data_score)
        elif bucket == "Excluded":
            confidence = 0.7
        else:
            confidence = min(0.55, 0.3 + 0.2 * data_score)
        decision_score = round(float(confidence) * 100, 1)
        subtype = _decision_subtype(bucket, asset_type, ready, partial, blocked, excluded, primary_blocker)
        next_action = row.get("next_action", "")
        data_confidence = _data_confidence_label(data_score)
        rows.append(
            {
                "ticker": ticker,
                "name": row.get("name", ""),
                "asset_type": asset_type,
                "exchange": row.get("exchange", ""),
                "sector": row.get("sector", ""),
                "industry": row.get("industry", ""),
                "theme": row.get("theme", ""),
                "decision_bucket": bucket,
                "decision_subtype": subtype,
                "confidence": round(float(confidence), 3),
                "main_reason": main_reason,
                "primary_blocker": primary_blocker,
                "supporting_features": ", ".join(ready),
                "blocked_features": row.get("blocked_features", ""),
                "excluded_features": row.get("excluded_features", ""),
                "missing_data": row.get("missing_data", ""),
                "next_action": next_action,
                "next_best_action": next_action,
                "data_readiness_score": data_score,
                "readiness_score": data_score,
                "data_confidence": data_confidence,
                "analysis_score": round(float(analysis_score_normalized), 3),
                "decision_score": decision_score,
                "purpose_thesis": _purpose_thesis(asset_type, watch_row, ready, blocked),
                "purpose_alignment": _purpose_alignment(asset_type, watch_row, ready, blocked),
                "setup_evaluation": _setup_evaluation(watch_row, ready, blocked),
                "valuation_evaluation": _valuation_evaluation(asset_type, watch_row, ready, blocked, excluded),
                "supported_analysis": " ".join(
                    part
                    for part in [
                        _supported_analysis(bucket, asset_type, ready, partial, excluded),
                        _purpose_supported_analysis(asset_type, watch_row, ready),
                    ]
                    if part
                ),
                "unsupported_analysis": _unsupported_analysis(asset_type, watch_row, blocked, excluded),
                "risk_watchpoint": _risk_watchpoint(asset_type, watch_row, ready, blocked),
                "invalidation_condition": _invalidation_condition(asset_type, watch_row, ready, blocked),
                "next_research_question": _next_research_question(watch_row, bucket, asset_type, primary_blocker, ready, partial, blocked),
                "review_priority_reason": _review_priority_reason(bucket, subtype, primary_blocker, asset_type, watch_row, ready, partial, blocked),
                "confidence_explanation": _confidence_explanation(bucket, data_confidence, primary_blocker, ready, blocked, excluded),
                "feature_summary": _feature_summary(ready, partial, blocked, excluded),
                "updated_at": _now(),
                "Reason": main_reason,
            }
        )
    return pd.DataFrame(rows, columns=DECISION_COLUMNS)


def write_research_decisions(
    base_dir: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> pd.DataFrame:
    root = resolve_project_root(base_dir)
    data_path = resolve_data_dir(data_dir, root)
    output_path = resolve_outputs_dir(output_dir, root)
    reports = build_ticker_readiness_report(root, data_dir=data_path, output_dir=output_path)
    readiness = reports["ticker_readiness_report"]
    final_watchlist = _read_csv(output_path / "final_watchlist.csv")
    decisions = build_research_decisions_frame(readiness, final_watchlist)
    data_output = data_path / "outputs" / "research_decisions.csv"
    output_copy = output_path / "research_decisions.csv"
    data_output.parent.mkdir(parents=True, exist_ok=True)
    output_path.mkdir(parents=True, exist_ok=True)
    decisions.to_csv(data_output, index=False)
    decisions.to_csv(output_copy, index=False)
    return decisions


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate readiness-aware ticker research decisions.")
    parser.add_argument("--project-root", help="Project root. Defaults to this repository.")
    parser.add_argument("--data-dir", help="Optional data directory. Relative paths resolve from project root.")
    parser.add_argument("--output-dir", help="Optional output directory. Relative paths resolve from project root.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = resolve_project_root(args.project_root)
    data_path = resolve_data_dir(args.data_dir, root)
    output_path = resolve_outputs_dir(args.output_dir, root)
    decisions = write_research_decisions(root, data_dir=data_path, output_dir=output_path)
    payload = {
        "status": "written",
        "rows": len(decisions),
        "data_output": str(data_path / "outputs" / "research_decisions.csv"),
        "output_copy": str(output_path / "research_decisions.csv"),
        "buckets": decisions["decision_bucket"].value_counts().to_dict() if not decisions.empty else {},
    }
    if args.json:
        print(json.dumps(payload, indent=2))
        return
    print(format_path_context(root, data_path, output_path))
    for key, value in payload.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
