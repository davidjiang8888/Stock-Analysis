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
    "setup_evaluation",
    "valuation_evaluation",
    "risk_watchpoint",
    "invalidation_condition",
    "next_research_question",
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
    text = str(value or "").strip()
    if not text:
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


def _purpose_thesis(asset_type: str, watch_row: pd.Series, ready: list[str], blocked: list[str]) -> str:
    purpose = _text_value(watch_row.get("primarypurpose"), "ETF / Defensive / Hedge" if asset_type in {"etf", "index_proxy", "fund"} else "Research candidate")
    final_state = _text_value(watch_row.get("finalstate"), "readiness gated")
    if asset_type in {"etf", "index_proxy", "fund"}:
        return f"Purpose: {purpose}. Use as market, theme, liquidity, or risk context; operating-company valuation remains excluded."
    if "dcf" in ready and "fundamentals" in ready:
        return f"Purpose: {purpose}. Current setup is {final_state}; available data supports a research brief, not a recommendation."
    if {"fundamentals", "dcf"} & set(blocked):
        return f"Purpose: {purpose}. Thesis cannot be evaluated fully until trusted fundamentals and DCF inputs are complete."
    return f"Purpose: {purpose}. Current setup is {final_state}; interpretation is limited to ready local features."


def _setup_evaluation(watch_row: pd.Series, ready: list[str], blocked: list[str]) -> str:
    setup = _text_value(watch_row.get("setupstatus"), "Not available")
    final_state = _text_value(watch_row.get("finalstate"), "Not available")
    rank_reason = _text_value(watch_row.get("rankreason"), "")
    if "price" in blocked:
        return "Setup cannot be evaluated because usable price history is missing."
    if setup != "Not available":
        suffix = f" {rank_reason}" if rank_reason else ""
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


def _risk_watchpoint(asset_type: str, watch_row: pd.Series, ready: list[str], blocked: list[str]) -> str:
    final_state = _text_value(watch_row.get("finalstate"), "")
    setup = _text_value(watch_row.get("setupstatus"), "")
    reason = _text_value(watch_row.get("reason"), "")
    if "price" in blocked:
        return "Primary risk is analytical blindness from missing price history; do not interpret trend or volatility yet."
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
    final_state = _text_value(watch_row.get("finalstate"), "")
    if "price" in blocked:
        return "Invalidation cannot be defined from local price data until price history is available."
    if final_state == "Broken":
        return "Already invalidated for trend/purpose review in the current local setup state."
    if asset_type in {"etf", "index_proxy", "fund"}:
        return "Invalidate market-proxy usefulness if liquidity, correlation, or theme trend no longer supports the intended monitoring role."
    if "momentum" in ready:
        return "Invalidate the current setup if price support fails, relative strength deteriorates, or the watchlist final state turns Broken."
    return "Invalidate only after the missing core inputs are available; current data is insufficient for a setup-level condition."


def _next_research_question(
    bucket: str,
    asset_type: str,
    primary_blocker: str,
    ready: list[str],
    partial: list[str],
    blocked: list[str],
) -> str:
    peer_limited = "peer" in blocked or "peer" in partial or primary_blocker == "peers"
    if bucket == "Research Now":
        if peer_limited:
            return "Which source-backed peers and peer metrics would confirm or challenge the standalone DCF and setup read?"
        return "Do purpose, setup, valuation assumptions, and risk watchpoints agree enough to justify deeper manual research?"
    if bucket == "Monitor" and asset_type in {"etf", "index_proxy", "fund"}:
        if peer_limited:
            return "Which source-backed peer mappings or peer metrics would make the market-proxy comparison more trustworthy?"
        return "What market, sector, or hedge signal is this proxy intended to monitor, and is that signal still supported by local price/risk data?"
    if primary_blocker == "price":
        return "Can trusted local price rows be added before interpreting setup, risk, or relative strength?"
    if primary_blocker == "fundamentals":
        return "Which trusted fundamentals or DCF fields are missing, and can SEC staging or manual import fill them?"
    if primary_blocker == "peers":
        return "Which source-backed peer mappings or peer metrics are needed before peer-relative analysis is shown?"
    if primary_blocker in {"earnings", "analyst_estimates", "optional_context"}:
        return "Is there trusted local earnings or estimate data worth importing, or should optional context remain locked?"
    return "Which missing input most improves the next supported research read?"


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
    if not final_watchlist.empty and "ticker" in final_watchlist.columns:
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
                "setup_evaluation": _setup_evaluation(watch_row, ready, blocked),
                "valuation_evaluation": _valuation_evaluation(asset_type, watch_row, ready, blocked, excluded),
                "risk_watchpoint": _risk_watchpoint(asset_type, watch_row, ready, blocked),
                "invalidation_condition": _invalidation_condition(asset_type, watch_row, ready, blocked),
                "next_research_question": _next_research_question(bucket, asset_type, primary_blocker, ready, partial, blocked),
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
