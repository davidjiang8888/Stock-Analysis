from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.data_onboarding import build_onboarding_payload
from src.data_sources import build_data_source_payload
from src.paths import format_path_context, resolve_data_dir, resolve_outputs_dir, resolve_project_root


PROBLEM_SOURCE_STATUSES = {"partial", "missing_file", "source_unavailable", "manual_only"}


def _count_true(rows: list[dict[str, Any]], field: str) -> int:
    return sum(1 for row in rows if bool(row.get(field)))


def _first_non_empty(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _recommended_next_command_rows(onboarding_payload: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    actions = onboarding_payload.get("onboarding_actions", [])
    bundles = onboarding_payload.get("command_bundles", [])

    if actions:
        top_action = actions[0]
        command = _first_non_empty(top_action.get("focus_command"), top_action.get("example_command"))
        if command:
            dataset = str(top_action.get("dataset") or "data").replace("_", " ")
            ticker = _first_non_empty(top_action.get("ticker"))
            step = f"Fix top {dataset} blocker" + (f" ({ticker})" if ticker else "")
            reason = _first_non_empty(top_action.get("reason"), top_action.get("recommended_action"))
            rows.append({"Step": step, "Command": command, "Reason": reason})

    if bundles:
        top_bundle = bundles[0]
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
    sources = source_payload["data_sources"]
    gaps = source_payload["data_gaps"]
    coverage = onboarding_payload["ticker_coverage"]
    actions = sorted(
        onboarding_payload["onboarding_actions"],
        key=lambda row: (int(row.get("priority") or 999), str(row.get("ticker") or ""), str(row.get("dataset") or "")),
    )
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
    command_rows = _recommended_next_command_rows(onboarding_payload)
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
    parser.add_argument("--project-root", help="Project root for default data/output directories.")
    parser.add_argument("--data-dir", help="Optional data directory. Relative paths resolve from project root.")
    parser.add_argument("--output-dir", help="Optional output directory. Relative paths resolve from project root.")
    parser.add_argument("--top-n", type=int, default=10, help="Number of gaps/actions to show.")
    args = parser.parse_args()

    root = resolve_project_root(args.project_root)
    data_path = resolve_data_dir(args.data_dir, root)
    output_path = resolve_outputs_dir(args.output_dir, root)
    payload = build_project_status_payload(root, data_dir=data_path, output_dir=output_path, top_n=args.top_n)

    if args.json:
        print(json.dumps(payload, indent=2))
        return

    print(format_path_context(root, data_path, output_path))
    _print_human(payload)


if __name__ == "__main__":
    main()
