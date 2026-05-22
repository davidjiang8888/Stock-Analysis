from __future__ import annotations

import argparse
import json
import re
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
STALE_PRICE_RECOMMENDED_ACTIONS = {
    "use staged manual prices.",
    "retry later or use staged manual prices in data/imports/prices.csv.",
    "use staged manual prices in data/imports/prices.csv.",
}
STALE_ONBOARDING_REASONS = {
    "prices",
    "at least 21 price rows",
    "fundamentals row",
    "free_cash_flow or revenue plus fcf_margin",
    "shares_outstanding",
    "peer mapping",
    "peer fundamentals or peer price/market-cap context",
}
STALE_DATA_GAP_ACTIONS = {
    "fundamentals": {
        "run sec staging for fundamentals, then validate, preview, and apply the staged import.",
    },
    "peers": {
        "add data/imports/peers.csv manually with real peer mappings, then validate and apply imports.",
    },
    "earnings": {
        "add data/imports/earnings.csv manually if you want local earnings coverage.",
    },
    "analyst_estimates": {
        "add data/imports/analyst_estimates.csv manually if you want estimate coverage.",
    },
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
    if normalized_reasons.isin(STALE_ONBOARDING_REASONS).any():
        return True
    if "ticker" not in core_rows.columns or "recommended_action" not in core_rows.columns:
        return True
    for _, row in core_rows.iterrows():
        dataset = str(row.get("dataset", "")).strip().lower()
        ticker = _normalized_ticker(row.get("ticker"))
        recommended_action = str(row.get("recommended_action", "")).strip()
        if not ticker or dataset not in {"prices", "fundamentals", "peers"}:
            continue
        expected_focus = focus_command_for_ticker(dataset, ticker)
        if expected_focus and expected_focus not in recommended_action:
            return True
    return False


def _data_quality_needs_refresh(frame: pd.DataFrame) -> bool:
    if frame.empty:
        return True
    if "ReadinessStatus" not in frame.columns or "NextBestAction" not in frame.columns:
        return True

    stale_price_rows = frame.loc[frame["ReadinessStatus"].astype(str).str.strip() == "Needs Price Data"]
    if not stale_price_rows.empty:
        if not stale_price_rows["NextBestAction"].astype(str).str.contains(r"make focus-price\s+TICKER=", regex=True).all():
            return True

    enrichment_rows = frame.loc[frame["ReadinessStatus"].astype(str).str.strip().isin({"Needs Enrichment", "Partial Coverage"})]
    if enrichment_rows.empty:
        return False
    return not enrichment_rows["NextBestAction"].astype(str).str.contains(r"make focus-(?:fundamentals|peers|price)\s+TICKER=", regex=True).all()


def _data_gaps_need_refresh(frame: pd.DataFrame) -> bool:
    if frame.empty:
        return True
    if "dataset" not in frame.columns or "recommended_action" not in frame.columns:
        return True

    for dataset, stale_actions in STALE_DATA_GAP_ACTIONS.items():
        dataset_rows = frame.loc[frame["dataset"].astype(str).str.strip() == dataset]
        if dataset_rows.empty:
            continue
        normalized_actions = dataset_rows["recommended_action"].astype(str).str.strip().str.lower()
        if normalized_actions.isin(stale_actions).any():
            return True
    return False


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


def _price_normalize_command(ticker: str) -> str:
    ticker = _normalized_ticker(ticker)
    if not ticker:
        return "make status"
    return f"make price-normalize INPUT=data/raw/prices/{ticker}.csv TICKER={ticker} SOURCE=yahoo_manual"


def _price_focus_recommended_action(ticker: str) -> str:
    ticker = _normalized_ticker(ticker)
    if not ticker:
        return "Run make status, then follow the printed price focus or runbook path."
    return (
        f"Run make focus-price TICKER={ticker}, or run python3 -m src.data_update --tickers {ticker} and "
        "normalize verified downloaded OHLCV files into data/imports/prices.csv."
    )


def _focus_command_from_action_text(action_text: str, ticker: str) -> str:
    ticker = _normalized_ticker(ticker)
    text = str(action_text or "").strip()
    if not ticker or not text:
        return ""
    match = re.search(rf"\bmake focus-(price|fundamentals|peers) TICKER={re.escape(ticker)}\b", text)
    return match.group(0) if match else ""


def _example_command_for_focus_command(focus_command: str, ticker: str) -> str:
    ticker = _normalized_ticker(ticker)
    normalized_focus = str(focus_command or "").strip().lower()
    if normalized_focus.startswith("make focus-price") and ticker:
        return _price_normalize_command(ticker)
    if normalized_focus.startswith("make focus-fundamentals") and ticker:
        return f"python3 -m src.stock_report --sec-stage-fundamentals --tickers {ticker}"
    if normalized_focus.startswith("make focus-peers"):
        return "python3 -m src.data_onboarding --write-templates"
    return ""


def _source_file_for_focus_command(focus_command: str) -> str:
    normalized_focus = str(focus_command or "").strip().lower()
    if normalized_focus.startswith("make focus-price"):
        return "data/imports/prices.csv"
    if normalized_focus.startswith("make focus-fundamentals"):
        return "data/imports/fundamentals.csv"
    if normalized_focus.startswith("make focus-peers"):
        return "data/imports/peers.csv"
    return "outputs/data_quality_wizard.csv"


def _bundle_runbook_shortcut(command_bundles: pd.DataFrame, lane: str) -> str:
    if command_bundles.empty or "lane" not in command_bundles.columns or "runbook_shortcut_command" not in command_bundles.columns:
        return ""
    lane_rows = command_bundles.loc[command_bundles["lane"].astype(str).str.strip() == lane].copy()
    if lane_rows.empty:
        return ""
    if "scope" in lane_rows.columns:
        scope_rank = {"broader_queue": 0, "holdings_first": 1}
        lane_rows["_scope_rank"] = lane_rows["scope"].astype(str).map(scope_rank).fillna(9)
        lane_rows = lane_rows.sort_values(["_scope_rank", "bundle_name"] if "bundle_name" in lane_rows.columns else ["_scope_rank"])
    row = lane_rows.iloc[0]
    return str(row.get("runbook_shortcut_command", "")).strip()


def _global_gap_command(dataset: str, command_bundles: pd.DataFrame) -> str:
    if dataset == "fundamentals":
        return _bundle_runbook_shortcut(command_bundles, "fundamentals") or "make sec-preview"
    if dataset == "peers":
        return _bundle_runbook_shortcut(command_bundles, "peers") or "make templates"
    if dataset in {"earnings", "analyst_estimates"}:
        return "make templates"
    return "make daily"


def _global_gap_source_file(dataset: str, source_file: str) -> str:
    if dataset == "peers":
        return "data/imports/peers.csv"
    if dataset == "earnings":
        return "data/imports/earnings.csv"
    if dataset == "analyst_estimates":
        return "data/imports/analyst_estimates.csv"
    return source_file


def _dedupe(items: list[ActionQueueItem]) -> list[ActionQueueItem]:
    best_by_key: dict[tuple[str, str], ActionQueueItem] = {}
    for item in items:
        key = (item.action_type, item.ticker or item.title)
        current = best_by_key.get(key)
        item_rank = (item.priority, _source_rank(item), _example_command_rank(item), item.urgency, item.title)
        current_rank = None if current is None else (current.priority, _source_rank(current), _example_command_rank(current), current.urgency, current.title)
        if current is None or item_rank < current_rank:
            best_by_key[key] = item
    deduped_items = list(best_by_key.values())
    explicit_by_ticker: dict[str, set[tuple[str, str]]] = {}
    for item in deduped_items:
        if item.action_type == "coverage" or not item.ticker:
            continue
        explicit_by_ticker.setdefault(item.ticker, set()).add(
            ((item.focus_command or "").strip(), (item.example_command or "").strip())
        )

    filtered_items: list[ActionQueueItem] = []
    for item in deduped_items:
        if item.action_type == "coverage" and item.ticker:
            item_key = ((item.focus_command or "").strip(), (item.example_command or "").strip())
            if item_key in explicit_by_ticker.get(item.ticker, set()):
                continue
        filtered_items.append(item)

    return sorted(filtered_items, key=lambda item: (item.priority, item.ticker or "ZZZ", item.action_type, item.title))


def build_action_queue_rows(
    *,
    price_status: pd.DataFrame,
    price_worklist: pd.DataFrame,
    onboarding_actions: pd.DataFrame,
    data_gaps: pd.DataFrame,
    data_quality: pd.DataFrame,
    command_bundles: pd.DataFrame | None = None,
) -> list[ActionQueueItem]:
    command_bundles = command_bundles if command_bundles is not None else pd.DataFrame()
    items: list[ActionQueueItem] = []

    if not price_status.empty:
        for _, row in price_status.iterrows():
            status = str(row.get("status", "")).strip().lower()
            if status not in PROBLEM_PRICE_STATUSES:
                continue
            ticker = _normalized_ticker(row.get("ticker"))
            worklist_row = _worklist_lookup(price_worklist, ticker)
            fallback_recommended_action = (
                _price_focus_recommended_action(ticker)
                if ticker
                else "Use staged manual prices in data/imports/prices.csv."
            )
            row_recommended_action = str(row.get("recommended_action", "")).strip()
            if row_recommended_action.lower() in STALE_PRICE_RECOMMENDED_ACTIONS:
                row_recommended_action = ""
            recommended_action = (
                str(worklist_row.get("recommended_action", "")).strip()
                or row_recommended_action
                or fallback_recommended_action
            )
            if ticker and "make focus-price" not in recommended_action:
                recommended_action = _price_focus_recommended_action(ticker)
            fallback_command = _price_normalize_command(ticker)
            example_command = str(worklist_row.get("example_command", "")).strip() or fallback_command
            safe_next_step = str(worklist_row.get("safe_next_step", "")).strip() or (
                "Run make price-validate and make price-preview before make price-apply; do not fabricate missing history."
                if ticker
                else ""
            )
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
                recommended_action = str(row.get("NextBestAction", "")).strip()
                if ticker and "make focus-price" not in recommended_action:
                    recommended_action = _price_focus_recommended_action(ticker)
                items.append(
                    ActionQueueItem(
                        priority=1,
                        urgency="critical",
                        action_type="prices",
                        ticker=ticker,
                        title=f"Add enough local price history for {ticker}",
                        status=status,
                        recommended_action=recommended_action or "Refresh or manually import prices for this ticker.",
                        focus_command=focus_command_for_ticker("prices", ticker),
                        example_command=_price_normalize_command(ticker),
                        source_file="data/imports/prices.csv",
                        source_artifact="outputs/data_quality_wizard.csv",
                        reason=str(row.get("Reason", "")).strip(),
                    )
                )
            elif status in {"Needs Enrichment", "Partial Coverage"} and ticker:
                recommended_action = (
                    str(row.get("NextBestAction", "")).strip()
                    or "Review the local missing-data fields and enrich what matters most."
                )
                focus_command = _focus_command_from_action_text(recommended_action, ticker)
                example_command = _example_command_for_focus_command(focus_command, ticker) or "make onboarding"
                items.append(
                    ActionQueueItem(
                        priority=2,
                        urgency="high" if status == "Needs Enrichment" else "medium",
                        action_type="coverage",
                        ticker=ticker,
                        title=f"Improve research coverage for {ticker}",
                        status=status,
                        recommended_action=recommended_action,
                        focus_command=focus_command,
                        example_command=example_command,
                        source_file=_source_file_for_focus_command(focus_command),
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
            focus_command = (
                focus_command_for_ticker("prices", ticker)
                if dataset == "prices" and ticker
                else focus_command_for_ticker("fundamentals", ticker)
                if dataset == "fundamentals" and ticker
                else focus_command_for_ticker("peers", ticker)
                if dataset == "peers" and ticker
                else ""
            )
            if not ticker:
                focus_command = _global_gap_command(dataset, command_bundles)
            example_command = (
                _global_gap_command(dataset, command_bundles)
                if not ticker
                else "make onboarding"
                if dataset in {"fundamentals", "peers", "earnings", "analyst_estimates"}
                else "make daily"
            )
            items.append(
                ActionQueueItem(
                    priority=priority,
                    urgency="critical" if priority == 1 else "high" if priority <= 3 else "medium",
                    action_type=dataset or "data_gap",
                    ticker=ticker,
                    title=f"Resolve {dataset} gap for {ticker}".strip() if ticker else f"Resolve {dataset} gap".strip(),
                    status=status or "gap",
                    recommended_action=str(row.get("recommended_action", "")).strip(),
                    focus_command=focus_command,
                    example_command=example_command,
                    source_file=_global_gap_source_file(dataset, str(row.get("local_file", "")).strip()),
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
    command_bundles = _load_csv(output_path / "command_bundles.csv")

    onboarding_payload: dict[str, Any] | None = None
    if _onboarding_actions_need_refresh(onboarding_actions) or price_worklist.empty or command_bundles.empty:
        onboarding_payload = build_onboarding_payload(root, data_dir=data_path, output_dir=output_path)
        onboarding_actions = pd.DataFrame(onboarding_payload["onboarding_actions"])
        price_worklist = pd.DataFrame(onboarding_payload["price_import_worklist"])
        command_bundles = pd.DataFrame(onboarding_payload["command_bundles"])
    if _data_gaps_need_refresh(data_gaps):
        data_gaps = pd.DataFrame(build_data_source_payload(root, data_dir=data_path, output_dir=output_path)["data_gaps"])
    if _data_quality_needs_refresh(data_quality):
        run_research_health(root, data_dir=data_path, output_dir=output_path)
        data_quality = _load_csv(output_path / "data_quality_wizard.csv")

    items = build_action_queue_rows(
        price_status=price_status,
        price_worklist=price_worklist,
        onboarding_actions=onboarding_actions,
        data_gaps=data_gaps,
        data_quality=data_quality,
        command_bundles=command_bundles,
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
