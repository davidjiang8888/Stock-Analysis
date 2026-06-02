from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.loader import normalize_columns
from src.paths import format_path_context, resolve_data_dir, resolve_project_root


NOT_AVAILABLE_REASON = "Not available: missing trusted local CSV input"
EARNINGS_READINESS_COLUMNS = [
    "ticker",
    "has_trusted_earnings",
    "row_count",
    "latest_report_date",
    "latest_fiscal_period",
    "missing_fields",
    "reason_not_ready",
    "manual_import_available",
    "updated_at",
]
ANALYST_ESTIMATES_READINESS_COLUMNS = [
    "ticker",
    "has_trusted_analyst_estimates",
    "row_count",
    "latest_period",
    "missing_fields",
    "reason_not_ready",
    "manual_import_available",
    "updated_at",
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    frame.columns = normalize_columns(list(frame.columns))
    if "ticker" in frame.columns:
        frame["ticker"] = frame["ticker"].astype("string").str.upper().str.strip()
    return frame


def _universe_tickers(universe: pd.DataFrame) -> list[str]:
    if universe.empty or "ticker" not in universe.columns:
        return []
    tickers = universe["ticker"].dropna().astype(str).str.upper().str.strip()
    return sorted(ticker for ticker in tickers.unique().tolist() if ticker)


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    return str(value).strip() != ""


def _has_any_value(row: pd.Series, columns: tuple[str, ...]) -> bool:
    return any(column in row and _has_value(row.get(column)) for column in columns)


def _latest_date(series: pd.Series) -> str:
    parsed = pd.to_datetime(series, errors="coerce", format="mixed").dropna()
    if parsed.empty:
        return ""
    return parsed.max().date().isoformat()


def _latest_text(series: pd.Series) -> str:
    values = series.dropna().astype(str).str.strip()
    values = values.loc[values.ne("")]
    return values.iloc[-1] if not values.empty else ""


def build_earnings_readiness_frame(
    universe: pd.DataFrame,
    earnings: pd.DataFrame,
    *,
    updated_at: str | None = None,
    manual_import_available: bool = True,
) -> pd.DataFrame:
    timestamp = updated_at or pd.Timestamp.now(tz="UTC").isoformat()
    tickers = _universe_tickers(universe)
    rows: list[dict[str, Any]] = []
    earnings = earnings.copy()
    if not earnings.empty and "ticker" in earnings.columns:
        earnings["ticker"] = earnings["ticker"].astype("string").str.upper().str.strip()

    for ticker in tickers:
        matches = earnings.loc[earnings["ticker"] == ticker].copy() if "ticker" in earnings.columns else pd.DataFrame()
        row_count = int(len(matches))
        trusted_rows = pd.DataFrame()
        if not matches.empty and "source" in matches.columns:
            trusted_rows = matches.loc[matches["source"].map(_has_value)].copy()
        latest_row = trusted_rows.iloc[-1] if not trusted_rows.empty else pd.Series(dtype=object)
        missing_fields: list[str] = []
        if trusted_rows.empty:
            missing_fields.append("trusted_local_earnings_row")
        else:
            if not _has_any_value(latest_row, ("report_date", "last_earnings_date", "next_earnings_date")):
                missing_fields.append("report_date")
            if not _has_any_value(latest_row, ("eps_actual", "eps_estimate", "revenue_actual", "revenue_estimate")):
                missing_fields.append("earnings_metrics")
        ready = not missing_fields
        reason = "" if ready else NOT_AVAILABLE_REASON if "trusted_local_earnings_row" in missing_fields else "missing " + ", ".join(missing_fields)
        rows.append(
            {
                "ticker": ticker,
                "has_trusted_earnings": ready,
                "row_count": row_count,
                "latest_report_date": "",
                "latest_fiscal_period": _latest_text(trusted_rows["fiscal_period"]) if not trusted_rows.empty and "fiscal_period" in trusted_rows.columns else "",
                "missing_fields": ", ".join(missing_fields),
                "reason_not_ready": reason,
                "manual_import_available": manual_import_available,
                "updated_at": timestamp,
            }
        )
    frame = pd.DataFrame(rows, columns=EARNINGS_READINESS_COLUMNS)
    if not frame.empty and not earnings.empty:
        for idx, row in frame.iterrows():
            ticker = str(row["ticker"])
            matches = earnings.loc[earnings["ticker"] == ticker].copy() if "ticker" in earnings.columns else pd.DataFrame()
            if matches.empty:
                continue
            date_columns = [column for column in ("report_date", "last_earnings_date", "next_earnings_date") if column in matches.columns]
            if date_columns:
                dates = pd.concat([matches[column] for column in date_columns], ignore_index=True)
                frame.at[idx, "latest_report_date"] = _latest_date(dates)
    return frame


def build_analyst_estimates_readiness_frame(
    universe: pd.DataFrame,
    estimates: pd.DataFrame,
    *,
    updated_at: str | None = None,
    manual_import_available: bool = True,
) -> pd.DataFrame:
    timestamp = updated_at or pd.Timestamp.now(tz="UTC").isoformat()
    tickers = _universe_tickers(universe)
    rows: list[dict[str, Any]] = []
    estimates = estimates.copy()
    if not estimates.empty and "ticker" in estimates.columns:
        estimates["ticker"] = estimates["ticker"].astype("string").str.upper().str.strip()

    for ticker in tickers:
        matches = estimates.loc[estimates["ticker"] == ticker].copy() if "ticker" in estimates.columns else pd.DataFrame()
        row_count = int(len(matches))
        trusted_rows = pd.DataFrame()
        if not matches.empty and "source" in matches.columns:
            trusted_rows = matches.loc[matches["source"].map(_has_value)].copy()
        latest_row = trusted_rows.iloc[-1] if not trusted_rows.empty else pd.Series(dtype=object)
        missing_fields: list[str] = []
        if trusted_rows.empty:
            missing_fields.append("trusted_local_analyst_estimate_row")
        else:
            if not _has_any_value(latest_row, ("eps_estimate", "current_quarter_eps", "next_quarter_eps", "current_year_eps", "next_year_eps")):
                missing_fields.append("eps_estimate")
            if not _has_any_value(latest_row, ("revenue_estimate", "current_quarter_revenue", "next_quarter_revenue", "current_year_revenue", "next_year_revenue")):
                missing_fields.append("revenue_estimate")
            if not _has_any_value(latest_row, ("price_target_mean", "target_mean_price", "price_target_high", "target_high_price", "price_target_low", "target_low_price")):
                missing_fields.append("price_target")
        ready = not missing_fields
        reason = "" if ready else NOT_AVAILABLE_REASON if "trusted_local_analyst_estimate_row" in missing_fields else "missing " + ", ".join(missing_fields)
        rows.append(
            {
                "ticker": ticker,
                "has_trusted_analyst_estimates": ready,
                "row_count": row_count,
                "latest_period": _latest_text(trusted_rows["period"]) if not trusted_rows.empty and "period" in trusted_rows.columns else "",
                "missing_fields": ", ".join(missing_fields),
                "reason_not_ready": reason,
                "manual_import_available": manual_import_available,
                "updated_at": timestamp,
            }
        )
    return pd.DataFrame(rows, columns=ANALYST_ESTIMATES_READINESS_COLUMNS)


def build_optional_context_readiness_reports(
    base_dir: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
) -> dict[str, pd.DataFrame]:
    root = resolve_project_root(base_dir)
    data_path = resolve_data_dir(data_dir, root)
    universe = _read_csv(data_path / "universe.csv")
    earnings = _read_csv(data_path / "earnings.csv")
    estimates = _read_csv(data_path / "analyst_estimates.csv")
    data_path.mkdir(parents=True, exist_ok=True)
    reports = {
        "earnings_readiness": build_earnings_readiness_frame(universe, earnings),
        "analyst_estimates_readiness": build_analyst_estimates_readiness_frame(universe, estimates),
    }
    reports["earnings_readiness"].to_csv(data_path / "earnings_readiness.csv", index=False)
    reports["analyst_estimates_readiness"].to_csv(data_path / "analyst_estimates_readiness.csv", index=False)
    return reports


def main() -> None:
    parser = argparse.ArgumentParser(description="Write earnings and analyst-estimates trusted-local readiness reports.")
    parser.add_argument("--project-root", help="Project root. Defaults to this repository.")
    parser.add_argument("--data-dir", help="Optional data directory. Relative paths resolve from project root.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = resolve_project_root(args.project_root)
    data_path = resolve_data_dir(args.data_dir, root)
    reports = build_optional_context_readiness_reports(root, data_dir=data_path)
    payload = {
        name: {
            "row_count": len(frame),
            "ready_count": int(frame.filter(like="has_trusted").iloc[:, 0].astype(bool).sum()) if not frame.empty else 0,
        }
        for name, frame in reports.items()
    }
    if args.json:
        print(json.dumps(payload, indent=2))
        return
    print(format_path_context(root, data_path, root / "outputs"))
    print("Optional context readiness:")
    for name, summary in payload.items():
        print(f"- {name}: {summary['ready_count']}/{summary['row_count']} ready")
    print(f"- earnings_readiness: {data_path / 'earnings_readiness.csv'}")
    print(f"- analyst_estimates_readiness: {data_path / 'analyst_estimates_readiness.csv'}")


if __name__ == "__main__":
    main()
