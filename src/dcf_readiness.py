from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import pandas as pd

from src.loader import normalize_columns
from src.paths import format_path_context, resolve_data_dir, resolve_project_root
from src.universe_model import infer_asset_type as infer_universe_asset_type


DCF_READINESS_COLUMNS = [
    "ticker",
    "asset_type",
    "has_free_cash_flow",
    "has_shares_outstanding",
    "has_revenue",
    "has_fcf_margin",
    "has_price",
    "is_dcf_ready",
    "missing_dcf_fields",
    "reason_not_ready",
    "sec_user_agent_configured",
    "manual_fundamentals_import_available",
    "updated_at",
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    frame.columns = normalize_columns(list(frame.columns))
    return frame


def _ticker_set(frame: pd.DataFrame) -> set[str]:
    if frame.empty or "ticker" not in frame.columns:
        return set()
    return set(frame["ticker"].dropna().astype(str).str.upper().str.strip())


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return str(value)


def _numeric_value(row: pd.Series, *columns: str) -> float | None:
    for column in columns:
        if column not in row:
            continue
        value = pd.to_numeric(pd.Series([row[column]]), errors="coerce").iloc[0]
        if pd.notna(value):
            return float(value)
    return None


def _has_number(row: pd.Series, *columns: str) -> bool:
    return _numeric_value(row, *columns) is not None


def infer_asset_type(ticker: str, universe_row: pd.Series | None = None) -> str:
    return infer_universe_asset_type(ticker, universe_row)


def _select_row(frame: pd.DataFrame, ticker: str) -> pd.Series:
    if frame.empty or "ticker" not in frame.columns:
        return pd.Series(dtype=object)
    rows = frame.loc[frame["ticker"].astype(str).str.upper().str.strip() == ticker]
    return rows.iloc[-1] if not rows.empty else pd.Series(dtype=object)


def build_dcf_readiness_frame(
    *,
    universe: pd.DataFrame,
    fundamentals: pd.DataFrame,
    prices: pd.DataFrame,
    updated_at: str | None = None,
) -> pd.DataFrame:
    updated_at = updated_at or pd.Timestamp.now(tz="UTC").isoformat()
    universe = universe.copy()
    fundamentals = fundamentals.copy()
    prices = prices.copy()
    for frame in (universe, fundamentals, prices):
        if not frame.empty:
            frame.columns = normalize_columns(list(frame.columns))
        if not frame.empty and "ticker" in frame.columns:
            frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()

    universe_tickers = sorted(_ticker_set(universe))
    price_tickers = _ticker_set(prices)
    universe_map = universe.set_index("ticker", drop=False) if not universe.empty and "ticker" in universe.columns else pd.DataFrame()
    sec_user_agent_configured = bool(os.environ.get("SEC_USER_AGENT", "").strip())

    rows: list[dict[str, Any]] = []
    for ticker in universe_tickers:
        universe_row = universe_map.loc[ticker] if not universe_map.empty and ticker in universe_map.index else pd.Series(dtype=object)
        fundamentals_row = _select_row(fundamentals, ticker)
        asset_type = infer_asset_type(ticker, universe_row)
        free_cash_flow = _numeric_value(fundamentals_row, "free_cash_flow", "fcf")
        revenue = _numeric_value(fundamentals_row, "revenue")
        fcf_margin = _numeric_value(fundamentals_row, "fcf_margin")
        has_free_cash_flow = free_cash_flow is not None
        has_shares = _has_number(fundamentals_row, "shares_outstanding")
        has_revenue = revenue is not None
        has_fcf_margin = fcf_margin is not None or (free_cash_flow is not None and revenue not in (None, 0))
        has_price = ticker in price_tickers
        missing: list[str] = []
        if asset_type != "company":
            reason = f"DCF excluded for {asset_type}; use ETF/rotation analysis instead of operating-company DCF."
            is_ready = False
        else:
            if not has_free_cash_flow:
                missing.append("free_cash_flow")
            if not has_shares:
                missing.append("shares_outstanding")
            if not has_revenue:
                missing.append("revenue")
            if not has_fcf_margin:
                missing.append("fcf_margin")
            if not has_price:
                missing.append("price")
            is_ready = not missing
            reason = "" if is_ready else "missing " + ", ".join(missing)
        rows.append(
            {
                "ticker": ticker,
                "asset_type": asset_type,
                "has_free_cash_flow": has_free_cash_flow,
                "has_shares_outstanding": has_shares,
                "has_revenue": has_revenue,
                "has_fcf_margin": has_fcf_margin,
                "has_price": has_price,
                "is_dcf_ready": is_ready,
                "missing_dcf_fields": ", ".join(missing),
                "reason_not_ready": reason,
                "sec_user_agent_configured": sec_user_agent_configured,
                "manual_fundamentals_import_available": "available: place CSV files in data/staged/fundamentals/ and run make import-fundamentals",
                "updated_at": updated_at,
            }
        )
    return pd.DataFrame(rows, columns=DCF_READINESS_COLUMNS)


def build_dcf_readiness_report(
    base_dir: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_path: Path | str | None = None,
) -> pd.DataFrame:
    root = resolve_project_root(base_dir)
    data_path = resolve_data_dir(data_dir, root)
    output = Path(output_path) if output_path is not None else data_path / "dcf_readiness.csv"
    if not output.is_absolute():
        output = root / output
    frame = build_dcf_readiness_frame(
        universe=_read_csv(data_path / "universe.csv"),
        fundamentals=_read_csv(data_path / "fundamentals.csv"),
        prices=_read_csv(data_path / "prices.csv"),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Write deterministic DCF readiness diagnostics.")
    parser.add_argument("--project-root", help="Project root. Defaults to this repository.")
    parser.add_argument("--data-dir", help="Optional data directory. Relative paths resolve from project root.")
    parser.add_argument("--top-n", type=int, default=20, help="Number of not-ready rows to print.")
    args = parser.parse_args()
    root = resolve_project_root(args.project_root)
    data_path = resolve_data_dir(args.data_dir, root)
    frame = build_dcf_readiness_report(root, data_dir=data_path)
    print(format_path_context(root, data_path, root / "outputs"))
    print(f"Wrote: {data_path / 'dcf_readiness.csv'}")
    print(f"DCF-ready tickers: {int(frame['is_dcf_ready'].sum())}/{len(frame)}")
    missing = frame.loc[~frame["is_dcf_ready"].astype(bool), ["ticker", "reason_not_ready"]]
    for _, row in missing.head(max(args.top_n, 0)).iterrows():
        print(f"- {row['ticker']}: {row['reason_not_ready']}")
    if len(missing) > max(args.top_n, 0):
        print(f"- {len(missing) - max(args.top_n, 0)} additional not-ready tickers suppressed; inspect data/dcf_readiness.csv.")


if __name__ == "__main__":
    main()
