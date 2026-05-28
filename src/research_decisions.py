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
                "data_confidence": _data_confidence_label(data_score),
                "analysis_score": round(float(analysis_score_normalized), 3),
                "decision_score": decision_score,
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
