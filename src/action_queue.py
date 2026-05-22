from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.data_onboarding import build_onboarding_payload, focus_command_for_ticker
from src.data_sources import build_data_source_payload
from src.paths import format_path_context, resolve_data_dir, resolve_outputs_dir, resolve_project_root
from src.research_health import run as run_research_health


ACTION_QUEUE_COLUMNS = [
    "priority",
    "urgency",
    "action_type",
    "ticker",
    "title",
    "status",
    "recommended_action",
    "focus_command",
    "example_command",
    "source_file",
    "source_artifact",
    "reason",
]

PROBLEM_PRICE_STATUSES = {"parse_error", "source_unavailable", "network_error", "no_rows", "failed"}
STALE_ONBOARDING_REASONS = {
    "prices",
    "at least 21 price rows",
    "fundamentals row",
    "free_cash_flow or revenue plus fcf_margin",
    "shares_outstanding",
    "peer mapping",
    "peer fundamentals or peer price/market-cap context",
}


@dataclass
class ActionQueueItem:
    priority: int
    urgency: str
    action_type: str
    ticker: str
    title: str
    status: str
    recommended_action: str
    focus_command: str
    example_command: str
    source_file: str
    source_artifact: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _normalized_ticker(value: object) -> str:
    text = str(value or "").strip().upper()
    return "" if text in {"", "NAN", "NONE"} else text


def _onboarding_actions_need_refresh(frame: pd.DataFrame) -> bool:
    if frame.empty:
        return True
    if "dataset" not in frame.columns or "reason" not in frame.columns:
        return True
    core_rows = frame.loc[frame["dataset"].astype(str).isin({"prices", "fundamentals", "peers"})]
    if core_rows.empty:
        return False
    normalized_reasons = core_rows["reason"].astype(str).str.strip().str.lower()
    return bool(normalized_reasons.isin(STALE_ONBOARDING_REASONS).any())


def _onboarding_title(dataset: str, ticker: str, status: str) -> str:
    ticker_suffix = f" for {ticker}" if ticker else ""
    if dataset == "prices":
        return f"Fix price coverage{ticker_suffix}"
    if dataset == "fundamentals":
        return f"Stage fundamentals{ticker_suffix}" if status == "missing_or_incomplete" else f"Improve fundamentals{ticker_suffix}"
    if dataset == "peers":
        return f"Add peer mappings{ticker_suffix}" if status == "manual_input_needed" else f"Complete peer-relative context{ticker_suffix}"
    return f"Improve {dataset} coverage{ticker_suffix}".strip()


def _worklist_lookup(frame: pd.DataFrame, ticker: str) -> dict[str, Any]:
    if frame.empty or not ticker or "ticker" not in frame.columns:
        return {}
    rows = frame.loc[frame["ticker"].astype(str).str.upper().str.strip() == ticker]
    return rows.iloc[0].to_dict() if not rows.empty else {}


def _source_rank(item: ActionQueueItem) -> int:
    source_order = {
        "outputs/price_update_status.csv": 0,
        "outputs/data_onboarding_actions.csv": 1,
        "outputs/data_quality_wizard.csv": 2,
        "outputs/data_gap_report.csv": 3,
    }
    return source_order.get(item.source_artifact, 9)


def _example_command_rank(item: ActionQueueItem) -> int:
    command = (item.example_command or "").strip().lower()
    if not command:
        return 9
    if command == "make onboarding":
        return 4
    if command == "make daily":
        return 5
    return 0


def _dedupe(items: list[ActionQueueItem]) -> list[ActionQueueItem]:
    best_by_key: dict[tuple[str, str], ActionQueueItem] = {}
    for item in items:
        key = (item.action_type, item.ticker or item.title)
        current = best_by_key.get(key)
        item_rank = (item.priority, _source_rank(item), _example_command_rank(item), item.urgency, item.title)
        current_rank = None if current is None else (current.priority, _source_rank(current), _example_command_rank(current), current.urgency, current.title)
        if current is None or item_rank < current_rank:
            best_by_key[key] = item
    return sorted(best_by_key.values(), key=lambda item: (item.priority, item.ticker or "ZZZ", item.action_type, item.title))


def build_action_queue_rows(
    *,
    price_status: pd.DataFrame,
    price_worklist: pd.DataFrame,
    onboarding_actions: pd.DataFrame,
    data_gaps: pd.DataFrame,
    data_quality: pd.DataFrame,
) -> list[ActionQueueItem]:
    items: list[ActionQueueItem] = []

    if not price_status.empty:
        for _, row in price_status.iterrows():
            status = str(row.get("status", "")).strip().lower()
            if status not in PROBLEM_PRICE_STATUSES:
                continue
            ticker = _normalized_ticker(row.get("ticker"))
            worklist_row = _worklist_lookup(price_worklist, ticker)
            fallback_recommended_action = "Use staged manual prices in data/imports/prices.csv."
            recommended_action = (
                str(worklist_row.get("recommended_action", "")).strip()
                or str(row.get("recommended_action", "")).strip()
                or fallback_recommended_action
            )
            fallback_command = f"python3 -m src.data_update --tickers {ticker}" if ticker else "make price-refresh"
            example_command = str(worklist_row.get("example_command", "")).strip() or fallback_command
            safe_next_step = str(worklist_row.get("safe_next_step", "")).strip()
            error_message = str(row.get("error_message", "")).strip() or "Remote price refresh failed for this ticker."
            reason = f"{error_message} {safe_next_step}".strip() if safe_next_step else error_message
            items.append(
                ActionQueueItem(
                    priority=1,
                    urgency="critical",
                    action_type="prices",
                    ticker=ticker,
                    title=f"Repair price history for {ticker}" if ticker else "Repair price history",
                    status=status,
                    recommended_action=recommended_action,
                    focus_command=focus_command_for_ticker("prices", ticker),
                    example_command=example_command,
                    source_file="data/imports/prices.csv",
                    source_artifact="outputs/price_update_status.csv",
                    reason=reason,
                )
            )

    if not data_quality.empty:
        for _, row in data_quality.iterrows():
            status = str(row.get("ReadinessStatus", "")).strip()
            ticker = _normalized_ticker(row.get("Ticker"))
            if status == "Needs Price Data":
                items.append(
                    ActionQueueItem(
                        priority=1,
                        urgency="critical",
                        action_type="prices",
                        ticker=ticker,
                        title=f"Add enough local price history for {ticker}",
                        status=status,
                        recommended_action=str(row.get("NextBestAction", "")).strip() or "Refresh or manually import prices for this ticker.",
                        focus_command=focus_command_for_ticker("prices", ticker),
                        example_command=f"python3 -m src.data_update --tickers {ticker}" if ticker else "make price-refresh",
                        source_file="data/imports/prices.csv",
                        source_artifact="outputs/data_quality_wizard.csv",
                        reason=str(row.get("Reason", "")).strip(),
                    )
                )
            elif status in {"Needs Enrichment", "Partial Coverage"} and ticker:
                items.append(
                    ActionQueueItem(
                        priority=2,
                        urgency="high" if status == "Needs Enrichment" else "medium",
                        action_type="coverage",
                        ticker=ticker,
                        title=f"Improve research coverage for {ticker}",
                        status=status,
                        recommended_action=str(row.get("NextBestAction", "")).strip() or "Review the local missing-data fields and enrich what matters most.",
                        focus_command="",
                        example_command="make onboarding",
                        source_file="outputs/data_quality_wizard.csv",
                        source_artifact="outputs/data_quality_wizard.csv",
                        reason=str(row.get("MissingDataFields", "")).strip() or str(row.get("Reason", "")).strip(),
                    )
                )

    if not onboarding_actions.empty:
        for _, row in onboarding_actions.iterrows():
            dataset = str(row.get("dataset", "")).strip()
            ticker = _normalized_ticker(row.get("ticker"))
            status = str(row.get("status", "")).strip() or "pending"
            priority_value = int(pd.to_numeric(pd.Series([row.get("priority")]), errors="coerce").fillna(5).iloc[0])
            urgency = "critical" if priority_value == 1 else "high" if priority_value <= 3 else "medium"
            focus_command = str(row.get("focus_command", "")).strip()
            if not focus_command and ticker and dataset in {"prices", "fundamentals", "peers"}:
                focus_command = focus_command_for_ticker(dataset, ticker)
            items.append(
                ActionQueueItem(
                    priority=priority_value,
                    urgency=urgency,
                    action_type=dataset or "onboarding",
                    ticker=ticker,
                    title=_onboarding_title(dataset, ticker, status),
                    status=status,
                    recommended_action=str(row.get("recommended_action", "")).strip(),
                    focus_command=focus_command,
                    example_command=str(row.get("example_command", "")).strip(),
                    source_file=str(row.get("target_file", "")).strip(),
                    source_artifact="outputs/data_onboarding_actions.csv",
                    reason=str(row.get("reason", "")).strip(),
                )
            )

    if not data_gaps.empty:
        for _, row in data_gaps.iterrows():
            dataset = str(row.get("dataset", "")).strip()
            ticker = _normalized_ticker(row.get("ticker"))
            status = str(row.get("status", "")).strip()
            priority = 2 if dataset == "fundamentals" else 3 if dataset == "peers" else 4
            if dataset == "prices":
                priority = 1
            if dataset == "analyst_estimates":
                priority = 5
            if dataset == "earnings":
                priority = 4
            items.append(
                ActionQueueItem(
                    priority=priority,
                    urgency="critical" if priority == 1 else "high" if priority <= 3 else "medium",
                    action_type=dataset or "data_gap",
                    ticker=ticker,
                    title=f"Resolve {dataset} gap for {ticker}".strip() if ticker else f"Resolve {dataset} gap".strip(),
                    status=status or "gap",
                    recommended_action=str(row.get("recommended_action", "")).strip(),
                    focus_command=(
                        focus_command_for_ticker("prices", ticker)
                        if dataset == "prices" and ticker
                        else focus_command_for_ticker("fundamentals", ticker)
                        if dataset == "fundamentals" and ticker
                        else focus_command_for_ticker("peers", ticker)
                        if dataset == "peers" and ticker
                        else ""
                    ),
                    example_command="make onboarding" if dataset in {"fundamentals", "peers", "earnings", "analyst_estimates"} else "make daily",
                    source_file=str(row.get("local_file", "")).strip(),
                    source_artifact="outputs/data_gap_report.csv",
                    reason=str(row.get("reason", "")).strip(),
                )
            )

    return _dedupe(items)


def build_action_queue_payload(
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    data_path = resolve_data_dir(data_dir, root)
    output_path = resolve_outputs_dir(output_dir, root)

    price_status = _load_csv(output_path / "price_update_status.csv")
    price_worklist = _load_csv(output_path / "price_import_worklist.csv")
    onboarding_actions = _load_csv(output_path / "data_onboarding_actions.csv")
    data_gaps = _load_csv(output_path / "data_gap_report.csv")
    data_quality = _load_csv(output_path / "data_quality_wizard.csv")

    onboarding_payload: dict[str, Any] | None = None
    if _onboarding_actions_need_refresh(onboarding_actions) or price_worklist.empty:
        onboarding_payload = build_onboarding_payload(root, data_dir=data_path, output_dir=output_path)
        onboarding_actions = pd.DataFrame(onboarding_payload["onboarding_actions"])
        price_worklist = pd.DataFrame(onboarding_payload["price_import_worklist"])
    if data_gaps.empty:
        data_gaps = pd.DataFrame(build_data_source_payload(root, data_dir=data_path, output_dir=output_path)["data_gaps"])
    if data_quality.empty:
        run_research_health(root, data_dir=data_path, output_dir=output_path)
        data_quality = _load_csv(output_path / "data_quality_wizard.csv")

    items = build_action_queue_rows(
        price_status=price_status,
        price_worklist=price_worklist,
        onboarding_actions=onboarding_actions,
        data_gaps=data_gaps,
        data_quality=data_quality,
    )
    return {
        "action_queue": [item.to_dict() for item in items],
        "action_count": len(items),
    }


def write_action_queue_output(
    project_root: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    output_path = resolve_outputs_dir(output_dir, root)
    payload = build_action_queue_payload(root, data_dir=data_dir, output_dir=output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    queue_path = output_path / "research_action_queue.csv"
    pd.DataFrame(payload["action_queue"], columns=ACTION_QUEUE_COLUMNS).to_csv(queue_path, index=False)
    return {
        **payload,
        "queue_path": str(queue_path),
    }


def _print_human(payload: dict[str, Any]) -> None:
    print(f"Action queue rows: {payload['action_count']}")
    for row in payload["action_queue"][:20]:
        ticker = f" {row['ticker']}" if row["ticker"] else ""
        print(f"- P{row['priority']} {row['action_type']}{ticker}: {row['recommended_action']}")
        print(f"  focus: {row.get('focus_command') or '-'}")
        print(f"  command: {row['example_command']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a unified local research action queue.")
    parser.add_argument("--check", action="store_true", help="Print the current action queue summary.")
    parser.add_argument("--write-output", action="store_true", help="Write outputs/research_action_queue.csv.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--project-root", help="Project root for default data/output directories.")
    parser.add_argument("--data-dir", help="Optional data directory. Relative paths resolve from project root.")
    parser.add_argument("--output-dir", help="Optional output directory. Relative paths resolve from project root.")
    args = parser.parse_args()

    root = resolve_project_root(args.project_root)
    data_path = resolve_data_dir(args.data_dir, root)
    output_path = resolve_outputs_dir(args.output_dir, root)
    payload = (
        write_action_queue_output(root, data_dir=data_path, output_dir=output_path)
        if args.write_output
        else build_action_queue_payload(root, data_dir=data_path, output_dir=output_path)
    )

    if args.json:
        print(json.dumps(payload, indent=2))
        return

    print(format_path_context(root, data_path, output_path))
    _print_human(payload)
    if args.write_output:
        print(f"Wrote: {payload['queue_path']}")


if __name__ == "__main__":
    main()
