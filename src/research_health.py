from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.data_onboarding import build_ticker_coverage, focus_command_for_ticker
from src.loader import load_inputs
from src.paths import format_path_context, resolve_data_dir, resolve_outputs_dir, resolve_project_root
from src.providers.csv_provider import CSVDataFetcher


DATA_QUALITY_COLUMNS = [
    "Ticker",
    "DataQualityScore",
    "ReadinessStatus",
    "MomentumReady",
    "MonthlyPicksReady",
    "DCFReady",
    "PeerReady",
    "EarningsAvailable",
    "AnalystEstimatesAvailable",
    "PriceHistoryDays",
    "MissingDataFields",
    "NextBestAction",
    "FocusCommand",
    "ExampleCommand",
    "Reason",
]

LIQUIDITY_COLUMNS = [
    "Ticker",
    "LiquidityStatus",
    "AvgVolume20D",
    "AvgDollarVolume20D",
    "LatestClose",
    "LatestVolume",
    "VolumeTrend5DVs20D",
    "VolatilityProxy20D",
    "MissingDataFields",
    "Reason",
]

CORRELATION_COLUMNS = [
    "Ticker",
    "CorrelationStatus",
    "MostCorrelatedTicker",
    "Correlation",
    "OverlapDays",
    "MissingDataFields",
    "Reason",
]


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def _to_float(value: object) -> float:
    converted = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(converted) if pd.notna(converted) else float("nan")


def _missing_join(items: list[str]) -> str:
    return ", ".join(dict.fromkeys(item for item in items if item))


def _normalize_prices(prices: pd.DataFrame) -> pd.DataFrame:
    if prices.empty:
        return pd.DataFrame(columns=["date", "ticker", "close", "volume"])
    frame = prices.copy()
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    if "adj_close" in frame.columns and "close" not in frame.columns:
        frame["close"] = frame["adj_close"]
    required = {"date", "ticker", "close", "volume"}
    if not required.issubset(frame.columns):
        return pd.DataFrame(columns=["date", "ticker", "close", "volume"])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce", format="mixed")
    frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
    frame = frame.dropna(subset=["date", "ticker", "close", "volume"])
    frame = frame.loc[(frame["ticker"] != "") & frame["close"].gt(0) & frame["volume"].ge(0)].copy()
    return frame.sort_values(["ticker", "date"]).drop_duplicates(["date", "ticker"], keep="last")


def _universe_tickers(universe: pd.DataFrame, holdings: pd.DataFrame | None = None) -> list[str]:
    tickers: set[str] = set()
    for frame in (universe, holdings if holdings is not None else pd.DataFrame()):
        if frame is not None and not frame.empty and "ticker" in frame.columns:
            tickers.update(frame["ticker"].dropna().astype(str).str.upper().str.strip())
    return sorted(ticker for ticker in tickers if ticker)


def build_data_quality_wizard(coverage_rows: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    coverage = pd.DataFrame(coverage_rows)
    if coverage.empty:
        return pd.DataFrame(columns=DATA_QUALITY_COLUMNS)

    rows: list[dict[str, object]] = []
    for _, row in coverage.iterrows():
        ticker = str(row.get("ticker", "")).upper().strip()
        history_days = int(_to_float(row.get("price_history_days")) if pd.notna(_to_float(row.get("price_history_days"))) else 0)
        has_prices = _bool_value(row.get("has_prices"))
        momentum_ready = _bool_value(row.get("usable_for_momentum"))
        monthly_ready = _bool_value(row.get("usable_for_monthly_picks"))
        has_fundamentals = _bool_value(row.get("has_fundamentals"))
        dcf_ready = _bool_value(row.get("dcf_ready"))
        has_peer_mapping = _bool_value(row.get("has_peer_mapping"))
        peer_ready = _bool_value(row.get("peer_ready"))
        has_earnings = _bool_value(row.get("has_earnings"))
        has_estimates = _bool_value(row.get("has_analyst_estimates"))

        score = 0
        score += 20 if has_prices else 0
        score += 15 if history_days >= 21 else 5 if history_days > 0 else 0
        score += 10 if history_days >= 63 else 0
        score += 15 if has_fundamentals else 0
        score += 15 if dcf_ready else 0
        score += 10 if has_peer_mapping else 0
        score += 10 if peer_ready else 0
        score += 3 if has_earnings else 0
        score += 2 if has_estimates else 0
        score = min(score, 100)

        missing_fields: list[str] = []
        if not has_prices:
            missing_fields.append("prices")
        if has_prices and history_days < 21:
            missing_fields.append("at least 21 price rows")
        if not has_fundamentals:
            missing_fields.append("fundamentals")
        if has_fundamentals and not dcf_ready:
            missing_fields.append("DCF inputs")
        if not has_peer_mapping:
            missing_fields.append("peer mapping")
        elif not peer_ready:
            missing_fields.append("peer fundamentals or peer price context")
        if not has_earnings:
            missing_fields.append("earnings.csv optional")
        if not has_estimates:
            missing_fields.append("analyst_estimates.csv optional")

        if not momentum_ready:
            status = "Needs Price Data"
        elif score >= 80:
            status = "Research Ready"
        elif score >= 55:
            status = "Partial Coverage"
        else:
            status = "Needs Enrichment"

        missing_text = _missing_join(missing_fields)
        focus_command = ""
        example_command = ""
        if not momentum_ready:
            focus_command = focus_command_for_ticker("prices", ticker)
            example_command = f"make price-normalize INPUT=data/raw/prices/{ticker}.csv TICKER={ticker} SOURCE=yahoo_manual"
        elif not dcf_ready:
            focus_command = focus_command_for_ticker("fundamentals", ticker)
            example_command = f"python3 -m src.stock_report --sec-stage-fundamentals --tickers {ticker}"
        elif not peer_ready:
            if has_peer_mapping:
                focus_command = str(row.get("focus_command", "") or "").strip() or focus_command_for_ticker("peers", ticker)
                example_command = str(row.get("example_command", "") or "").strip() or "make templates"
            else:
                focus_command = focus_command_for_ticker("peers", ticker)
                example_command = "make templates"
        elif not has_earnings:
            focus_command = "make templates"
            example_command = "make templates"
        elif not has_estimates:
            focus_command = "make templates"
            example_command = "make templates"
        reason = (
            f"{ticker} has {history_days} local price rows. "
            f"Momentum ready={momentum_ready}, DCF ready={dcf_ready}, peer ready={peer_ready}. "
            f"Missing or optional gaps: {missing_text or 'none reported'}."
        )
        rows.append(
            {
                "Ticker": ticker,
                "DataQualityScore": score,
                "ReadinessStatus": status,
                "MomentumReady": momentum_ready,
                "MonthlyPicksReady": monthly_ready,
                "DCFReady": dcf_ready,
                "PeerReady": peer_ready,
                "EarningsAvailable": has_earnings,
                "AnalystEstimatesAvailable": has_estimates,
                "PriceHistoryDays": history_days,
                "MissingDataFields": missing_text,
                "NextBestAction": row.get("next_best_action", ""),
                "FocusCommand": focus_command,
                "ExampleCommand": example_command,
                "Reason": reason,
            }
        )
    return pd.DataFrame(rows, columns=DATA_QUALITY_COLUMNS)


def build_liquidity_risk(prices: pd.DataFrame, tickers: list[str] | None = None) -> pd.DataFrame:
    normalized = _normalize_prices(prices)
    target_tickers = sorted({ticker.upper().strip() for ticker in (tickers or normalized.get("ticker", pd.Series(dtype=str)).unique()) if ticker})
    rows: list[dict[str, object]] = []

    for ticker in target_tickers:
        frame = normalized.loc[normalized["ticker"] == ticker].sort_values("date")
        missing_fields: list[str] = []
        if frame.empty:
            missing_fields.append("prices")
            rows.append(
                {
                    "Ticker": ticker,
                    "LiquidityStatus": "Insufficient Price Data",
                    "AvgVolume20D": float("nan"),
                    "AvgDollarVolume20D": float("nan"),
                    "LatestClose": float("nan"),
                    "LatestVolume": float("nan"),
                    "VolumeTrend5DVs20D": float("nan"),
                    "VolatilityProxy20D": float("nan"),
                    "MissingDataFields": _missing_join(missing_fields),
                    "Reason": f"{ticker} has no valid local price/volume rows, so liquidity context is unavailable.",
                }
            )
            continue

        window = frame.tail(20)
        if len(window) < 20:
            missing_fields.append("20 price/volume rows")
        latest = frame.iloc[-1]
        avg_volume = float(window["volume"].mean()) if not window.empty else float("nan")
        avg_dollar_volume = float((window["volume"] * window["close"]).mean()) if not window.empty else float("nan")
        five_day_avg = float(frame.tail(5)["volume"].mean()) if len(frame) >= 5 else float("nan")
        volume_trend = five_day_avg / avg_volume - 1 if avg_volume and pd.notna(five_day_avg) and pd.notna(avg_volume) else float("nan")
        volatility = float(frame["close"].pct_change().dropna().tail(20).std(ddof=0)) if len(frame) >= 2 else float("nan")

        if len(window) < 20:
            status = "Insufficient Price Data"
        elif avg_dollar_volume >= 50_000_000:
            status = "Liquid"
        elif avg_dollar_volume >= 5_000_000:
            status = "Moderate Liquidity"
        else:
            status = "Thin / Needs Review"

        rows.append(
            {
                "Ticker": ticker,
                "LiquidityStatus": status,
                "AvgVolume20D": avg_volume,
                "AvgDollarVolume20D": avg_dollar_volume,
                "LatestClose": float(latest["close"]),
                "LatestVolume": float(latest["volume"]),
                "VolumeTrend5DVs20D": volume_trend,
                "VolatilityProxy20D": volatility,
                "MissingDataFields": _missing_join(missing_fields),
                "Reason": (
                    f"{ticker} liquidity status is {status} using local close and volume rows only. "
                    f"Average 20-day dollar volume is {avg_dollar_volume:,.0f} when calculable."
                ),
            }
        )
    return pd.DataFrame(rows, columns=LIQUIDITY_COLUMNS)


def build_correlation_risk(
    prices: pd.DataFrame,
    tickers: list[str] | None = None,
    *,
    min_overlap_days: int = 20,
) -> pd.DataFrame:
    normalized = _normalize_prices(prices)
    target_tickers = sorted({ticker.upper().strip() for ticker in (tickers or normalized.get("ticker", pd.Series(dtype=str)).unique()) if ticker})
    if normalized.empty or not target_tickers:
        return pd.DataFrame(
            [
                {
                    "Ticker": ticker,
                    "CorrelationStatus": "Insufficient Data",
                    "MostCorrelatedTicker": "",
                    "Correlation": float("nan"),
                    "OverlapDays": 0,
                    "MissingDataFields": "prices",
                    "Reason": f"{ticker} correlation context is unavailable because local price history is missing.",
                }
                for ticker in target_tickers
            ],
            columns=CORRELATION_COLUMNS,
        )

    pivot = normalized.loc[normalized["ticker"].isin(target_tickers)].pivot(index="date", columns="ticker", values="close").sort_index()
    returns = pivot.pct_change().dropna(how="all")
    rows: list[dict[str, object]] = []

    for ticker in target_tickers:
        if ticker not in returns.columns:
            rows.append(
                {
                    "Ticker": ticker,
                    "CorrelationStatus": "Insufficient Data",
                    "MostCorrelatedTicker": "",
                    "Correlation": float("nan"),
                    "OverlapDays": 0,
                    "MissingDataFields": "price returns",
                    "Reason": f"{ticker} has no local return series for correlation context.",
                }
            )
            continue

        best_peer = ""
        best_corr = float("nan")
        best_overlap = 0
        for peer in target_tickers:
            if peer == ticker or peer not in returns.columns:
                continue
            aligned = returns[[ticker, peer]].dropna()
            overlap = len(aligned)
            if overlap < min_overlap_days:
                continue
            corr = float(aligned[ticker].corr(aligned[peer]))
            if pd.isna(corr):
                continue
            if pd.isna(best_corr) or abs(corr) > abs(best_corr):
                best_peer = peer
                best_corr = corr
                best_overlap = overlap

        if not best_peer:
            status = "Insufficient Overlap"
            missing = f"{min_overlap_days} overlapping return days"
            reason = f"{ticker} does not have at least {min_overlap_days} overlapping local return days with another ticker."
        else:
            abs_corr = abs(best_corr)
            if abs_corr >= 0.8:
                status = "High Co-movement"
            elif abs_corr >= 0.5:
                status = "Moderate Co-movement"
            else:
                status = "Low Co-movement"
            missing = ""
            reason = (
                f"{ticker} is most correlated with {best_peer} at {best_corr:.2f} over {best_overlap} overlapping "
                "local return days. This is concentration context, not a trade instruction."
            )

        rows.append(
            {
                "Ticker": ticker,
                "CorrelationStatus": status,
                "MostCorrelatedTicker": best_peer,
                "Correlation": best_corr,
                "OverlapDays": best_overlap,
                "MissingDataFields": missing,
                "Reason": reason,
            }
        )
    return pd.DataFrame(rows, columns=CORRELATION_COLUMNS)


def build_research_health_outputs(
    prices: pd.DataFrame,
    universe: pd.DataFrame,
    holdings: pd.DataFrame,
    coverage_rows: list[dict[str, Any]] | pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    tickers = _universe_tickers(universe, holdings)
    return {
        "data_quality_wizard": build_data_quality_wizard(coverage_rows),
        "liquidity_risk": build_liquidity_risk(prices, tickers=tickers),
        "correlation_risk": build_correlation_risk(prices, tickers=tickers),
    }


def run(
    base_dir: Path | str | None = None,
    *,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    root = resolve_project_root(base_dir)
    data_path = resolve_data_dir(data_dir, root)
    output_path = resolve_outputs_dir(output_dir, root)
    fetcher = CSVDataFetcher(data_path / "prices.csv")
    loaded = load_inputs(root, fetcher, data_dir=data_path)
    coverage_rows = [row.to_dict() for row in build_ticker_coverage(root, data_dir=data_path, output_dir=output_path)]
    outputs = build_research_health_outputs(loaded.prices, loaded.universe, loaded.holdings, coverage_rows)
    output_path.mkdir(parents=True, exist_ok=True)
    files = {
        "data_quality_wizard": output_path / "data_quality_wizard.csv",
        "liquidity_risk": output_path / "liquidity_risk.csv",
        "correlation_risk": output_path / "correlation_risk.csv",
    }
    for name, frame in outputs.items():
        frame.to_csv(files[name], index=False)
    return {
        "files": files,
        "row_counts": {name: len(frame) for name, frame in outputs.items()},
        "warnings": loaded.warnings,
    }


def _json_ready(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "files": {key: str(value) for key, value in payload["files"].items()},
        "row_counts": payload["row_counts"],
        "warnings": payload["warnings"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate local-only research health CSVs.")
    parser.add_argument("--write-output", action="store_true", help="Write data quality, liquidity, and correlation CSVs.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--project-root", help="Project root for config.yaml and default data/output directories.")
    parser.add_argument("--data-dir", help="Optional data directory. Relative paths resolve from project root.")
    parser.add_argument("--output-dir", help="Optional output directory. Relative paths resolve from project root.")
    args = parser.parse_args()

    result = run(
        Path(args.project_root) if args.project_root else None,
        data_dir=Path(args.data_dir) if args.data_dir else None,
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )
    if args.json:
        print(json.dumps(_json_ready(result), indent=2))
        return
    print(
        format_path_context(
            project_root=Path(args.project_root) if args.project_root else None,
            data_dir=Path(args.data_dir) if args.data_dir else None,
            output_dir=Path(args.output_dir) if args.output_dir else None,
        )
    )
    print("Generated research health outputs:")
    for name, path in result["files"].items():
        print(f"- {name}: {path}")
    print("Row counts:")
    for name, count in result["row_counts"].items():
        print(f"- {name}: {count}")
    if result["warnings"]:
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
