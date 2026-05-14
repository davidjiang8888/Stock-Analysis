from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.paths import format_path_context, resolve_data_dir, resolve_outputs_dir, resolve_project_root


TRACK_COLUMNS = [
    "Month",
    "Picks",
    "AveragePickReturn",
    "BenchmarkReturn",
    "ExcessReturn",
    "WinRate",
    "NumberOfPicks",
    "MissingDataFields",
    "Notes",
]
EQUITY_COLUMNS = ["Month", "PicksEquity", "BenchmarkEquity"]


@dataclass(frozen=True)
class TrackRecordConfig:
    top_n: int = 5
    benchmark: str = "SPY"
    min_lookback_days: int = 21


def _read_prices(base_dir: Path) -> pd.DataFrame:
    path = base_dir / "prices.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    frame.columns = [column.strip().lower() for column in frame.columns]
    if "close" not in frame.columns and "adj_close" in frame.columns:
        frame["close"] = frame["adj_close"]
    if "ticker" in frame.columns:
        frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce", format="mixed")
    if "close" in frame.columns:
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    return frame.dropna(subset=["date", "ticker", "close"]).sort_values(["ticker", "date"])


def _read_universe_tickers(data_dir: Path) -> list[str]:
    candidates: set[str] = set()
    for path in (data_dir / "universe.csv", data_dir / "holdings.csv"):
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        frame.columns = [column.strip().lower() for column in frame.columns]
        if "ticker" in frame.columns:
            candidates.update(frame["ticker"].dropna().astype(str).str.upper().str.strip())
    return sorted(ticker for ticker in candidates if ticker)


def _price_on_or_before(frame: pd.DataFrame, date: pd.Timestamp) -> float | None:
    subset = frame.loc[frame["date"] <= date]
    if subset.empty:
        return None
    value = subset.iloc[-1]["close"]
    return None if pd.isna(value) else float(value)


def _return_between(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> float | None:
    start_price = _price_on_or_before(frame, start)
    end_price = _price_on_or_before(frame, end)
    if start_price is None or end_price is None or start_price <= 0:
        return None
    return end_price / start_price - 1.0


def _momentum_score_as_of(frame: pd.DataFrame, selection_date: pd.Timestamp, lookback_days: int) -> float | None:
    start = selection_date - pd.Timedelta(days=lookback_days)
    lookback_return = _return_between(frame, start, selection_date)
    if lookback_return is None:
        return None
    return max(0.0, min(100.0, 50.0 + lookback_return * 250.0))


def calculate_monthly_track_record(
    base_dir: Path | None = None,
    *,
    data_dir: Path | None = None,
    output_dir: Path | None = None,
    top_n: int = 5,
    benchmark: str = "SPY",
    write_output: bool = True,
) -> dict[str, object]:
    base_dir = resolve_project_root(base_dir)
    data_dir = resolve_data_dir(data_dir, base_dir)
    output_dir = resolve_outputs_dir(output_dir, base_dir)
    config = TrackRecordConfig(top_n=top_n, benchmark=benchmark)
    prices = _read_prices(data_dir)
    outputs_dir = output_dir
    track_path = outputs_dir / "monthly_picks_track_record.csv"
    equity_path = outputs_dir / "monthly_picks_equity_curve.csv"
    if prices.empty:
        track = pd.DataFrame(
            [
                {
                    "Month": "",
                    "Picks": "",
                    "AveragePickReturn": pd.NA,
                    "BenchmarkReturn": pd.NA,
                    "ExcessReturn": pd.NA,
                    "WinRate": pd.NA,
                    "NumberOfPicks": 0,
                    "MissingDataFields": "prices",
                    "Notes": "Insufficient local history to calculate a monthly track record.",
                }
            ],
            columns=TRACK_COLUMNS,
        )
        equity = pd.DataFrame(columns=EQUITY_COLUMNS)
    else:
        tickers = [ticker for ticker in _read_universe_tickers(data_dir) if ticker != benchmark.upper()]
        benchmark_frame = prices.loc[prices["ticker"] == benchmark.upper()].copy()
        periods = sorted(prices["date"].dt.to_period("M").unique())
        rows: list[dict[str, object]] = []
        picks_equity = 1.0
        benchmark_equity = 1.0
        equity_rows: list[dict[str, object]] = []
        for period, next_period in zip(periods, periods[1:], strict=False):
            selection_date = prices.loc[prices["date"].dt.to_period("M") == period, "date"].max()
            forward_end = prices.loc[prices["date"].dt.to_period("M") == next_period, "date"].max()
            ranked: list[tuple[str, float, float]] = []
            missing: list[str] = []
            for ticker in tickers:
                frame = prices.loc[prices["ticker"] == ticker].copy()
                if frame.empty:
                    continue
                score = _momentum_score_as_of(frame, selection_date, config.min_lookback_days)
                forward_return = _return_between(frame, selection_date, forward_end)
                if score is None or forward_return is None:
                    missing.append(ticker)
                    continue
                ranked.append((ticker, score, forward_return))
            selected = sorted(ranked, key=lambda item: (-item[1], item[0]))[:top_n]
            benchmark_return = _return_between(benchmark_frame, selection_date, forward_end)
            if not selected or benchmark_return is None:
                rows.append(
                    {
                        "Month": str(period),
                        "Picks": "",
                        "AveragePickReturn": pd.NA,
                        "BenchmarkReturn": benchmark_return,
                        "ExcessReturn": pd.NA,
                        "WinRate": pd.NA,
                        "NumberOfPicks": 0,
                    "MissingDataFields": ", ".join(sorted(value for value in set(missing + ([benchmark] if benchmark_return is None else [])) if value)),
                        "Notes": "Insufficient local history for this month.",
                    }
                )
                continue
            returns = [item[2] for item in selected]
            average_pick_return = sum(returns) / len(returns)
            win_rate = sum(1 for value in returns if value > benchmark_return) / len(returns)
            excess_return = average_pick_return - benchmark_return
            picks_equity *= 1.0 + average_pick_return
            benchmark_equity *= 1.0 + benchmark_return
            rows.append(
                {
                    "Month": str(period),
                    "Picks": ", ".join(item[0] for item in selected),
                    "AveragePickReturn": average_pick_return,
                    "BenchmarkReturn": benchmark_return,
                    "ExcessReturn": excess_return,
                    "WinRate": win_rate,
                    "NumberOfPicks": len(selected),
                    "MissingDataFields": ", ".join(sorted(set(missing))),
                    "Notes": "Equal-weight forward return from local price history only.",
                }
            )
            equity_rows.append(
                {
                    "Month": str(period),
                    "PicksEquity": picks_equity,
                    "BenchmarkEquity": benchmark_equity,
                }
            )
        track = pd.DataFrame(rows, columns=TRACK_COLUMNS)
        if track.empty:
            track = pd.DataFrame(
                [
                    {
                        "Month": "",
                        "Picks": "",
                        "AveragePickReturn": pd.NA,
                        "BenchmarkReturn": pd.NA,
                        "ExcessReturn": pd.NA,
                        "WinRate": pd.NA,
                        "NumberOfPicks": 0,
                        "MissingDataFields": "price history",
                        "Notes": "Insufficient local history to calculate a monthly track record.",
                    }
                ],
                columns=TRACK_COLUMNS,
            )
        equity = pd.DataFrame(equity_rows, columns=EQUITY_COLUMNS)

    if write_output:
        outputs_dir.mkdir(parents=True, exist_ok=True)
        track.to_csv(track_path, index=False)
        equity.to_csv(equity_path, index=False)
    return {
        "output_path": str(track_path),
        "equity_curve_path": str(equity_path),
        "row_count": int(len(track)),
        "equity_curve_rows": int(len(equity)),
        "track_record": _records(track),
        "equity_curve": _records(equity),
    }


def _json_value(value: object) -> object:
    if value is pd.NA:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for record in frame.to_dict(orient="records"):
        records.append({key: _json_value(value) for key, value in record.items()})
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate local monthly-picks track record from price history.")
    parser.add_argument("--monthly-picks", action="store_true", help="Calculate monthly picks track record.")
    parser.add_argument("--benchmark", default="SPY", help="Benchmark ticker for comparison.")
    parser.add_argument("--top-n", type=int, default=5, help="Number of candidates per month.")
    parser.add_argument("--project-root", help="Project root for config.yaml and default data/output directories.")
    parser.add_argument("--data-dir", help="Optional data directory. Relative paths resolve from project root.")
    parser.add_argument("--output-dir", help="Optional output directory. Relative paths resolve from project root.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()

    project_root = resolve_project_root(args.project_root)
    data_dir = resolve_data_dir(args.data_dir, project_root)
    output_dir = resolve_outputs_dir(args.output_dir, project_root)
    result = calculate_monthly_track_record(
        project_root,
        data_dir=data_dir,
        output_dir=output_dir,
        top_n=args.top_n,
        benchmark=args.benchmark,
    )
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return
    print(format_path_context(project_root, data_dir, output_dir))
    print(f"Generated monthly picks track record: {result['output_path']}")
    print(f"Generated monthly picks equity curve: {result['equity_curve_path']}")
    print(f"Rows: {result['row_count']}")
    if result["equity_curve_rows"] == 0:
        print("Warning: insufficient local history for an equity curve.")


if __name__ == "__main__":
    main()
