from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.indicators import build_indicator_snapshot
from src.dcf_readiness import build_dcf_readiness_frame
from src.loader import load_inputs
from src.market_direction import run as run_market_direction
from src.momentum_engine import run as run_momentum
from src.optional_context_readiness import build_optional_context_readiness_reports
from src.portfolio_review import review_holdings
from src.providers.csv_provider import CSVDataFetcher
from src.paths import format_path_context, resolve_data_dir, resolve_outputs_dir, resolve_project_root
from src.purpose_evaluation import write_purpose_evaluation_summary
from src.purpose_router import route_purposes
from src.readiness_engine import build_ticker_readiness_report
from src.research_decisions import write_research_decisions
from src.research_health import build_research_health_outputs
from src.state_machine import build_final_watchlist
from src.value_engine import run as run_value

NO_DAILY_PRICE_SUFFIX = ": no daily price history was available."
MISSING_OHLCV_PREFIX = "Missing OHLCV data for "
MAX_PRINTED_WARNINGS = 50


def printable_warnings(warnings: list[str], *, max_warnings: int = MAX_PRINTED_WARNINGS) -> list[str]:
    """Summarize repetitive broad-universe warnings for CLI readability."""
    no_price_tickers = sorted(
        warning.removesuffix(NO_DAILY_PRICE_SUFFIX)
        for warning in warnings
        if warning.endswith(NO_DAILY_PRICE_SUFFIX)
    )
    missing_ohlcv_tickers = sorted(
        warning.removeprefix(MISSING_OHLCV_PREFIX)
        for warning in warnings
        if warning.startswith(MISSING_OHLCV_PREFIX)
    )
    other_warnings = [
        warning
        for warning in warnings
        if not warning.endswith(NO_DAILY_PRICE_SUFFIX) and not warning.startswith(MISSING_OHLCV_PREFIX)
    ]

    printable = other_warnings[:max_warnings]
    if missing_ohlcv_tickers:
        sample = ", ".join(missing_ohlcv_tickers[:10])
        printable.append(
            f"{len(missing_ohlcv_tickers)} tickers are missing OHLCV coverage"
            + (f" (sample: {sample})" if sample else "")
            + "; run make price-worklist TOP_N=25 or make price-refresh TOP_N=25."
        )
    if no_price_tickers:
        sample = ", ".join(no_price_tickers[:10])
        printable.append(
            f"{len(no_price_tickers)} tickers have no daily price history available"
            + (f" (sample: {sample})" if sample else "")
            + "; run make price-worklist TOP_N=25 or make price-refresh TOP_N=25."
        )

    total_suppressed = max(len(warnings) - len(printable), 0)
    if total_suppressed:
        printable.append(f"{total_suppressed} additional warnings suppressed; inspect the returned warnings or coverage reports.")
    return printable


def _missing_snapshot_row(ticker: str, universe_row: pd.Series | None = None) -> dict[str, object]:
    universe_row = universe_row if universe_row is not None else pd.Series(dtype=object)
    return {
        "ticker": ticker,
        "date": pd.NaT,
        "history_days": 0,
        "close": float("nan"),
        "ema_10": float("nan"),
        "ema_21": float("nan"),
        "sma_50": float("nan"),
        "sma_200": float("nan"),
        "return_1m": float("nan"),
        "return_3m": float("nan"),
        "return_6m": float("nan"),
        "return_12m": float("nan"),
        "relative_return_vs_spy": float("nan"),
        "relative_return_vs_qqq": float("nan"),
        "relative_return_vs_sector_etf": float("nan"),
        "sector_etf": universe_row.get("sector_etf"),
        "distance_from_10ema": float("nan"),
        "distance_from_21ema": float("nan"),
        "distance_from_50sma": float("nan"),
        "avg_volume_20": float("nan"),
        "volume_ratio": float("nan"),
        "atr_or_volatility_pct": float("nan"),
        "rs_percentile": float("nan"),
        "theme": universe_row.get("theme"),
    }


def run(
    base_dir: Path | None = None,
    *,
    data_dir: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, object]:
    base_dir = resolve_project_root(base_dir)
    data_dir = resolve_data_dir(data_dir, base_dir)
    output_dir = resolve_outputs_dir(output_dir, base_dir)
    fetcher = CSVDataFetcher(data_dir / "prices.csv")
    loaded = load_inputs(base_dir, fetcher, data_dir=data_dir)
    snapshot, indicator_warnings = build_indicator_snapshot(
        prices=loaded.prices,
        universe=loaded.universe,
        theme_map=loaded.theme_map,
        config=loaded.config,
    )
    backfill_warnings: list[str] = []
    screen_tickers = set()
    if not loaded.universe.empty and "ticker" in loaded.universe.columns:
        screen_tickers.update(loaded.universe["ticker"].dropna().astype(str))
    if not loaded.holdings.empty and "ticker" in loaded.holdings.columns:
        screen_tickers.update(loaded.holdings["ticker"].dropna().astype(str))
    if screen_tickers and not snapshot.empty and "ticker" in snapshot.columns:
        snapshot = snapshot.loc[snapshot["ticker"].isin(screen_tickers)].copy()
    if screen_tickers:
        existing_snapshot_tickers = set(snapshot["ticker"].dropna().astype(str)) if not snapshot.empty and "ticker" in snapshot.columns else set()
        universe_map = loaded.universe.set_index("ticker") if not loaded.universe.empty and "ticker" in loaded.universe.columns else pd.DataFrame()
        missing_screen_rows = []
        for ticker in sorted(screen_tickers - existing_snapshot_tickers):
            universe_row = universe_map.loc[ticker] if not universe_map.empty and ticker in universe_map.index else pd.Series(dtype=object)
            missing_screen_rows.append(_missing_snapshot_row(ticker, universe_row))
            backfill_warnings.append(f"{ticker}: no daily price history was available.")
        if missing_screen_rows:
            snapshot = pd.concat([snapshot, pd.DataFrame(missing_screen_rows)], ignore_index=True)

    purpose_df = route_purposes(
        snapshot=snapshot,
        universe=loaded.universe,
        holdings=loaded.holdings,
        fundamentals=loaded.fundamentals,
        config=loaded.config,
    )
    market_direction_df = run_market_direction(snapshot, loaded.universe, loaded.theme_map, loaded.config)
    momentum_df = run_momentum(snapshot, loaded.config)
    dcf_readiness_df = build_dcf_readiness_frame(universe=loaded.universe, fundamentals=loaded.fundamentals, prices=loaded.prices)
    value_df = run_value(snapshot, purpose_df, loaded.fundamentals, loaded.config, peers=loaded.peers)
    portfolio_df = review_holdings(loaded.holdings, purpose_df, momentum_df, loaded.config)
    final_watchlist_df = build_final_watchlist(purpose_df, momentum_df, portfolio_df, value_df=value_df)
    coverage_rows = []
    try:
        from src.data_onboarding import build_ticker_coverage

        coverage_rows = [
            row.to_dict()
            for row in build_ticker_coverage(base_dir, data_dir=data_dir, output_dir=output_dir)
        ]
    except Exception as exc:  # pragma: no cover - defensive reporting path
        backfill_warnings.append(f"Research health coverage could not be assembled: {exc}")
    research_health_outputs = build_research_health_outputs(
        loaded.prices,
        loaded.universe,
        loaded.holdings,
        coverage_rows,
    )

    outputs_dir = output_dir
    outputs_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "purpose_classification": outputs_dir / "purpose_classification.csv",
        "market_direction": outputs_dir / "market_direction.csv",
        "momentum_leaders": outputs_dir / "momentum_leaders.csv",
        "portfolio_review": outputs_dir / "portfolio_review.csv",
        "undervalued_candidates": outputs_dir / "undervalued_candidates.csv",
        "final_watchlist": outputs_dir / "final_watchlist.csv",
        "research_decisions": outputs_dir / "research_decisions.csv",
        "purpose_evaluation_summary": outputs_dir / "purpose_evaluation_summary.csv",
        "data_quality_wizard": outputs_dir / "data_quality_wizard.csv",
        "liquidity_risk": outputs_dir / "liquidity_risk.csv",
        "correlation_risk": outputs_dir / "correlation_risk.csv",
    }
    data_files = {
        "dcf_readiness": data_dir / "dcf_readiness.csv",
        "earnings_readiness": data_dir / "earnings_readiness.csv",
        "analyst_estimates_readiness": data_dir / "analyst_estimates_readiness.csv",
    }
    purpose_df.to_csv(files["purpose_classification"], index=False)
    market_direction_df.to_csv(files["market_direction"], index=False)
    momentum_df.to_csv(files["momentum_leaders"], index=False)
    portfolio_df.to_csv(files["portfolio_review"], index=False)
    value_df.to_csv(files["undervalued_candidates"], index=False)
    final_watchlist_df.to_csv(files["final_watchlist"], index=False)
    for output_name, output_frame in research_health_outputs.items():
        output_frame.to_csv(files[output_name], index=False)
    dcf_readiness_df.to_csv(data_files["dcf_readiness"], index=False)
    optional_context_readiness = build_optional_context_readiness_reports(base_dir, data_dir=data_dir)
    readiness_reports = build_ticker_readiness_report(base_dir, data_dir=data_dir, output_dir=output_dir)
    research_decisions_df = write_research_decisions(base_dir, data_dir=data_dir, output_dir=output_dir)
    purpose_evaluation_summary_df = write_purpose_evaluation_summary(base_dir, data_dir=data_dir, output_dir=output_dir)

    warnings = sorted(set(loaded.warnings + indicator_warnings + backfill_warnings))
    return {
        "files": files,
        "data_files": data_files,
        "warnings": warnings,
        "row_counts": {
            "purpose_classification": len(purpose_df),
            "market_direction": len(market_direction_df),
            "momentum_leaders": len(momentum_df),
            "portfolio_review": len(portfolio_df),
            "undervalued_candidates": len(value_df),
            "final_watchlist": len(final_watchlist_df),
            "research_decisions": len(research_decisions_df),
            "purpose_evaluation_summary": len(purpose_evaluation_summary_df),
            **{name: len(frame) for name, frame in research_health_outputs.items()},
            "dcf_readiness": len(dcf_readiness_df),
            **{name: len(frame) for name, frame in optional_context_readiness.items()},
            "ticker_readiness_report": len(readiness_reports["ticker_readiness_report"]),
            "feature_readiness_summary": len(readiness_reports.get("feature_readiness_summary", pd.DataFrame())),
            "peer_readiness_report": len(readiness_reports.get("peer_readiness_report", pd.DataFrame())),
            "peer_unlock_worklist": len(readiness_reports.get("peer_unlock_worklist", pd.DataFrame())),
        },
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate the core CSV research reports.")
    parser.add_argument("--project-root", help="Project root for config.yaml and default data/output directories.")
    parser.add_argument("--data-dir", help="Optional data directory. Relative paths resolve from project root.")
    parser.add_argument("--output-dir", help="Optional output directory. Relative paths resolve from project root.")
    args = parser.parse_args()

    result = run(
        Path(args.project_root) if args.project_root else None,
        data_dir=Path(args.data_dir) if args.data_dir else None,
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )
    print(
        format_path_context(
            project_root=Path(args.project_root) if args.project_root else None,
            data_dir=Path(args.data_dir) if args.data_dir else None,
            output_dir=Path(args.output_dir) if args.output_dir else None,
        )
    )
    print("Generated outputs:")
    for name, path in result["files"].items():
        print(f"- {name}: {path}")
    for name, path in result.get("data_files", {}).items():
        print(f"- {name}: {path}")
    print("Row counts:")
    for name, count in result["row_counts"].items():
        print(f"- {name}: {count}")
    if result["warnings"]:
        print("Warnings:")
        for warning in printable_warnings(result["warnings"]):
            print(f"- {warning}")


if __name__ == "__main__":
    main()
