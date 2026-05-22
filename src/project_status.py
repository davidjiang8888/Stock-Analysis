from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.data_onboarding import build_onboarding_payload
from src.data_onboarding import write_onboarding_outputs
from src.data_update import enrich_price_update_status_frame, refresh_price_update_status_output
from src.data_sources import build_data_source_payload, write_data_source_outputs
from src.action_queue import write_action_queue_output
from src.paths import format_path_context, resolve_data_dir, resolve_outputs_dir, resolve_project_root
from src.research_health import run as run_research_health


PROBLEM_SOURCE_STATUSES = {"partial", "missing_file", "source_unavailable", "manual_only"}
PROJECT_STATUS_JSON = "project_status.json"
PROJECT_STATUS_SUMMARY_CSV = "project_status_summary.csv"
PROJECT_STATUS_TOP_ACTIONS_CSV = "project_status_top_actions.csv"
PROJECT_STATUS_NEXT_STEPS_CSV = "project_status_next_steps.csv"


def _count_true(rows: list[dict[str, Any]], field: str) -> int:
    return sum(1 for row in rows if bool(row.get(field)))


def _first_non_empty(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _load_price_status_lookup(output_path: Path) -> dict[str, dict[str, Any]]:
    path = output_path / "price_update_status.csv"
    if not path.exists():
        return {}
    frame = enrich_price_update_status_frame(pd.read_csv(path))
    if frame.empty or "ticker" not in frame.columns:
        return {}
    lookup: dict[str, dict[str, Any]] = {}
    for _, row in frame.iterrows():
        ticker = str(row.get("ticker") or "").strip().upper()
        if ticker:
            lookup[ticker] = row.to_dict()
    return lookup


def _enrich_top_actions(onboarding_payload: dict[str, Any], price_status_lookup: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    actions = [dict(row) for row in onboarding_payload.get("onboarding_actions", [])]
    price_worklist = {
        str(row.get("ticker") or "").strip().upper(): row
        for row in onboarding_payload.get("price_import_worklist", [])
        if str(row.get("ticker") or "").strip()
    }
    sec_stage_queue = {
        str(row.get("ticker") or "").strip().upper(): row
        for row in onboarding_payload.get("sec_stage_queue", [])
        if str(row.get("ticker") or "").strip()
    }
    peer_mapping_queue = {
        str(row.get("ticker") or "").strip().upper(): row
        for row in onboarding_payload.get("peer_mapping_queue", [])
        if str(row.get("ticker") or "").strip()
    }
    holdings_first_price_tickers: set[str] = set()
    for row in onboarding_payload.get("command_bundles", []):
        if str(row.get("lane") or "").strip().lower() != "prices":
            continue
        if str(row.get("scope") or "").strip().lower() != "holdings_first":
            continue
        holdings_first_price_tickers.update(
            {
                ticker.strip().upper()
                for ticker in str(row.get("tickers") or "").split(",")
                if ticker.strip()
            }
        )

    enriched: list[dict[str, Any]] = []
    for row in actions:
        dataset = str(row.get("dataset") or "").strip().lower()
        ticker = str(row.get("ticker") or "").strip().upper()
        source_row: dict[str, Any] | None = None
        if dataset == "prices":
            source_row = price_worklist.get(ticker)
        elif dataset == "fundamentals":
            source_row = sec_stage_queue.get(ticker)
        elif dataset == "peers":
            source_row = peer_mapping_queue.get(ticker)

        if source_row:
            for field in ("reason", "recommended_action", "focus_command", "example_command"):
                value = _first_non_empty(source_row.get(field), row.get(field))
                if value:
                    row[field] = value
            if dataset == "prices" and ticker:
                row["is_holding"] = ticker in holdings_first_price_tickers
            elif "is_holding" in source_row:
                row["is_holding"] = bool(source_row.get("is_holding"))
        elif dataset == "prices" and ticker:
            row["is_holding"] = ticker in holdings_first_price_tickers

        if dataset == "prices" and ticker:
            price_status_row = price_status_lookup.get(ticker)
            if price_status_row:
                for field in ("status", "recommended_action", "focus_command", "example_command", "target_file"):
                    value = _first_non_empty(price_status_row.get(field), row.get(field))
                    if value:
                        row[field] = value
                row["reason"] = _first_non_empty(price_status_row.get("error_message"), row.get("reason"))
        enriched.append(row)
    return enriched


def _action_rank(row: dict[str, Any]) -> tuple[int, int, str, str]:
    return (
        int(row.get("priority") or 999),
        0 if bool(row.get("is_holding")) else 1,
        str(row.get("ticker") or ""),
        str(row.get("dataset") or ""),
    )


def _bundle_rank(bundle: dict[str, Any]) -> tuple[int, int, str]:
    scope = str(bundle.get("scope") or "").strip().lower()
    ticker_count = int(bundle.get("ticker_count") or 0)
    scope_rank = 0 if scope == "broader_queue" else 1 if scope == "holdings_first" else 2
    return (scope_rank, -ticker_count, str(bundle.get("bundle_name") or ""))


def _select_top_bundle(actions: list[dict[str, Any]], bundles: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not bundles:
        return None
    if not actions:
        return min(bundles, key=_bundle_rank)

    top_action = actions[0]
    dataset = str(top_action.get("dataset") or "").strip().lower()
    ticker = str(top_action.get("ticker") or "").strip().upper()

    lane_matches = [
        bundle for bundle in bundles if str(bundle.get("lane") or "").strip().lower() == dataset
    ]
    if not lane_matches:
        return min(bundles, key=_bundle_rank)

    if ticker:
        ticker_matches: list[dict[str, Any]] = []
        for bundle in lane_matches:
            tickers = {
                part.strip().upper()
                for part in str(bundle.get("tickers") or "").split(",")
                if part.strip()
            }
            if ticker in tickers:
                ticker_matches.append(bundle)
        if ticker_matches:
            return min(ticker_matches, key=_bundle_rank)

    return min(lane_matches, key=_bundle_rank)


def _recommended_source_command_rows(problem_sources: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in problem_sources:
        command = _first_non_empty(row.get("focus_command"))
        if not command or command == "make status":
            continue
        dataset = str(row.get("dataset") or "data").replace("_", " ")
        status = str(row.get("availability_status") or "").strip().lower()
        if command == "make imports-validate":
            step = f"Advance staged {dataset} import"
        elif status == "manual_only":
            step = f"Prepare {dataset} input"
        else:
            step = f"Advance {dataset} source"
        reason = _first_non_empty(row.get("fallback_action"), row.get("validation_warnings"), row.get("notes"))
        rows.append({"Step": step, "Command": command, "Reason": reason})
    return rows


def _recommended_next_command_rows(
    actions: list[dict[str, Any]],
    bundles: list[dict[str, Any]],
    problem_sources: list[dict[str, Any]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    if actions:
        top_action = actions[0]
        command = _first_non_empty(top_action.get("focus_command"), top_action.get("example_command"))
        if command:
            dataset = str(top_action.get("dataset") or "data").replace("_", " ")
            ticker = _first_non_empty(top_action.get("ticker"))
            step = f"Fix top {dataset} blocker" + (f" ({ticker})" if ticker else "")
            reason = _first_non_empty(top_action.get("reason"), top_action.get("recommended_action"))
            rows.append({"Step": step, "Command": command, "Reason": reason})

    top_bundle = _select_top_bundle(actions, bundles)
    if top_bundle:
        command = _first_non_empty(
            top_bundle.get("runbook_shortcut_command"),
            top_bundle.get("detail_shortcut_command"),
            top_bundle.get("bundle_shortcut_command"),
            top_bundle.get("primary_command"),
        )
        if command:
            bundle_name = _first_non_empty(top_bundle.get("bundle_name"), "Top bundle")
            reason = _first_non_empty(top_bundle.get("goal_summary"), top_bundle.get("why_it_matters"))
            rows.append({"Step": f"Run {bundle_name}", "Command": command, "Reason": reason})

    problem_source_rows = _recommended_source_command_rows(problem_sources)
    if problem_source_rows:
        rows.append(problem_source_rows[0])

    rows.extend(
        [
            {
                "Step": "Deterministic verification",
                "Command": "make verify",
                "Reason": "Confirm the local CSV outputs and dashboard helpers still pass deterministic checks.",
            },
            {
                "Step": "Dashboard smoke check",
                "Command": "make dashboard-smoke",
                "Reason": "Confirm the Streamlit surface still boots cleanly after the local data and workflow updates.",
            },
        ]
    )

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        command = str(row.get("Command") or "").strip()
        if not command or command in seen:
            continue
        seen.add(command)
        deduped.append(row)
    return deduped


def build_project_status_payload(
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
    top_n: int = 10,
) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    data_path = resolve_data_dir(data_dir, root)
    output_path = resolve_outputs_dir(output_dir, root)
    source_payload = build_data_source_payload(root, data_dir=data_path, output_dir=output_path)
    onboarding_payload = build_onboarding_payload(root, data_dir=data_path, output_dir=output_path)
    price_status_lookup = _load_price_status_lookup(output_path)
    sources = source_payload["data_sources"]
    gaps = source_payload["data_gaps"]
    coverage = onboarding_payload["ticker_coverage"]
    enriched_actions = _enrich_top_actions(onboarding_payload, price_status_lookup)
    actions = sorted(enriched_actions, key=_action_rank)
    problem_sources = [row for row in sources if str(row.get("availability_status")) in PROBLEM_SOURCE_STATUSES]
    summary = {
        "data_sources_total": len(sources),
        "data_sources_available": sum(1 for row in sources if row.get("availability_status") == "available"),
        "data_sources_needing_attention": len(problem_sources),
        "data_gaps": len(gaps),
        "tickers_total": len(coverage),
        "tickers_with_prices": _count_true(coverage, "has_prices"),
        "tickers_usable_for_momentum": _count_true(coverage, "usable_for_momentum"),
        "tickers_dcf_ready": _count_true(coverage, "dcf_ready"),
        "tickers_peer_ready": _count_true(coverage, "peer_ready"),
        "onboarding_actions": len(actions),
        "critical_actions": sum(1 for row in actions if int(row.get("priority") or 999) <= 1),
    }
    command_rows = _recommended_next_command_rows(
        actions,
        onboarding_payload.get("command_bundles", []),
        problem_sources,
    )
    return {
        "project_root": str(root),
        "data_dir": str(data_path),
        "outputs_dir": str(output_path),
        "summary": summary,
        "data_sources_needing_attention": problem_sources[:top_n],
        "top_data_gaps": gaps[:top_n],
        "top_onboarding_actions": actions[:top_n],
        "recommended_next_command_rows": command_rows,
        "recommended_next_commands": [row["Command"] for row in command_rows],
    }


def write_project_status_output(
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
    top_n: int = 10,
    refresh_supporting_outputs: bool = False,
) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    data_path = resolve_data_dir(data_dir, root)
    output_path = resolve_outputs_dir(output_dir, root)
    if refresh_supporting_outputs:
        refresh_price_update_status_output(root, output_dir=output_path)
        write_data_source_outputs(root, data_dir=data_path, output_dir=output_path)
        write_onboarding_outputs(root, data_dir=data_path, output_dir=output_path)
        run_research_health(root, data_dir=data_path, output_dir=output_path)
        write_action_queue_output(root, data_dir=data_path, output_dir=output_path)
    payload = build_project_status_payload(root, data_dir=data_path, output_dir=output_path, top_n=top_n)
    output_path.mkdir(parents=True, exist_ok=True)

    json_path = output_path / PROJECT_STATUS_JSON
    summary_path = output_path / PROJECT_STATUS_SUMMARY_CSV
    top_actions_path = output_path / PROJECT_STATUS_TOP_ACTIONS_CSV
    next_steps_path = output_path / PROJECT_STATUS_NEXT_STEPS_CSV

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    pd.DataFrame([payload["summary"]]).to_csv(summary_path, index=False)
    pd.DataFrame(payload["top_onboarding_actions"]).to_csv(top_actions_path, index=False)
    pd.DataFrame(payload["recommended_next_command_rows"]).to_csv(next_steps_path, index=False)

    return {
        **payload,
        "written_files": {
            "project_status_json": str(json_path),
            "project_status_summary": str(summary_path),
            "project_status_top_actions": str(top_actions_path),
            "project_status_next_steps": str(next_steps_path),
        },
    }


def _print_human(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    print("Project status summary:")
    print(f"- Data sources: {summary['data_sources_available']}/{summary['data_sources_total']} available")
    print(f"- Data sources needing attention: {summary['data_sources_needing_attention']}")
    print(f"- Data gaps: {summary['data_gaps']}")
    print(f"- Tickers with prices: {summary['tickers_with_prices']}/{summary['tickers_total']}")
    print(f"- Tickers usable for momentum: {summary['tickers_usable_for_momentum']}/{summary['tickers_total']}")
    print(f"- DCF-ready tickers: {summary['tickers_dcf_ready']}/{summary['tickers_total']}")
    print(f"- Peer-ready tickers: {summary['tickers_peer_ready']}/{summary['tickers_total']}")
    print(f"- Onboarding actions: {summary['onboarding_actions']} ({summary['critical_actions']} critical)")
    print("Top onboarding actions:")
    for row in payload["top_onboarding_actions"]:
        ticker = f" {row['ticker']}" if row.get("ticker") else ""
        print(f"- P{row['priority']} {row['dataset']}{ticker}: {row['recommended_action']}")
        if row.get("focus_command"):
            print(f"  focus: {row['focus_command']}")
        if row.get("example_command"):
            print(f"  command: {row['example_command']}")
    print("Recommended next commands:")
    command_rows = payload.get("recommended_next_command_rows") or [
        {"Step": f"Next {index}", "Command": command}
        for index, command in enumerate(payload.get("recommended_next_commands", []), start=1)
    ]
    for row in command_rows:
        print(f"- {row.get('Step', 'Next')}: {row.get('Command', '')}")
        if row.get("Reason"):
            print(f"  why: {row['Reason']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Print a read-only local project status snapshot.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--write-output", action="store_true", help="Write machine-readable project status outputs.")
    parser.add_argument(
        "--refresh-artifacts",
        action="store_true",
        help="Refresh supporting read-only operator artifacts before printing status.",
    )
    parser.add_argument("--project-root", help="Project root for default data/output directories.")
    parser.add_argument("--data-dir", help="Optional data directory. Relative paths resolve from project root.")
    parser.add_argument("--output-dir", help="Optional output directory. Relative paths resolve from project root.")
    parser.add_argument("--top-n", type=int, default=10, help="Number of gaps/actions to show.")
    args = parser.parse_args()

    root = resolve_project_root(args.project_root)
    data_path = resolve_data_dir(args.data_dir, root)
    output_path = resolve_outputs_dir(args.output_dir, root)
    should_write_output = args.write_output or args.refresh_artifacts
    payload = (
        write_project_status_output(
            root,
            data_dir=data_path,
            output_dir=output_path,
            top_n=args.top_n,
            refresh_supporting_outputs=args.refresh_artifacts,
        )
        if should_write_output
        else build_project_status_payload(root, data_dir=data_path, output_dir=output_path, top_n=args.top_n)
    )

    if args.json:
        print(json.dumps(payload, indent=2))
        return

    print(format_path_context(root, data_path, output_path))
    _print_human(payload)
    if args.write_output:
        print("Wrote:")
        for path in payload.get("written_files", {}).values():
            print(f"- {path}")


if __name__ == "__main__":
    main()
