from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.indicators import build_indicator_snapshot
from src.loader import load_inputs
from src.market_direction import run as run_market_direction
from src.momentum_engine import run as run_momentum
from src.portfolio_review import review_holdings
from src.providers.csv_provider import CSVDataFetcher
from src.purpose_router import route_purposes
from src.state_machine import build_final_watchlist
from src.value_engine import run as run_value


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


def run(base_dir: Path | None = None) -> dict[str, object]:
    base_dir = base_dir or Path(__file__).resolve().parent.parent
    fetcher = CSVDataFetcher(base_dir / "data" / "prices.csv")
    loaded = load_inputs(base_dir, fetcher)
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
    value_df = run_value(snapshot, purpose_df, loaded.fundamentals, loaded.config)
    portfolio_df = review_holdings(loaded.holdings, purpose_df, momentum_df, loaded.config)
    final_watchlist_df = build_final_watchlist(purpose_df, momentum_df, portfolio_df)

    outputs_dir = base_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "purpose_classification": outputs_dir / "purpose_classification.csv",
        "market_direction": outputs_dir / "market_direction.csv",
        "momentum_leaders": outputs_dir / "momentum_leaders.csv",
        "portfolio_review": outputs_dir / "portfolio_review.csv",
        "undervalued_candidates": outputs_dir / "undervalued_candidates.csv",
        "final_watchlist": outputs_dir / "final_watchlist.csv",
    }
    purpose_df.to_csv(files["purpose_classification"], index=False)
    market_direction_df.to_csv(files["market_direction"], index=False)
    momentum_df.to_csv(files["momentum_leaders"], index=False)
    portfolio_df.to_csv(files["portfolio_review"], index=False)
    value_df.to_csv(files["undervalued_candidates"], index=False)
    final_watchlist_df.to_csv(files["final_watchlist"], index=False)

    warnings = sorted(set(loaded.warnings + indicator_warnings + backfill_warnings))
    return {
        "files": files,
        "warnings": warnings,
        "row_counts": {
            "purpose_classification": len(purpose_df),
            "market_direction": len(market_direction_df),
            "momentum_leaders": len(momentum_df),
            "portfolio_review": len(portfolio_df),
            "undervalued_candidates": len(value_df),
            "final_watchlist": len(final_watchlist_df),
        },
    }


def main() -> None:
    result = run()
    print("Generated outputs:")
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
