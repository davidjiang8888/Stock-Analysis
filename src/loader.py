from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.config import AppConfig
from src.providers.base import DataFetcher


def normalize_columns(columns: list[str]) -> list[str]:
    return [
        column.strip()
        .replace("%", "pct")
        .replace("/", "_")
        .replace(" ", "_")
        .replace("-", "_")
        .lower()
        for column in columns
    ]


@dataclass
class LoadedData:
    config: AppConfig
    universe: pd.DataFrame
    holdings: pd.DataFrame
    theme_map: pd.DataFrame
    fundamentals: pd.DataFrame
    peers: pd.DataFrame
    prices: pd.DataFrame
    warnings: list[str] = field(default_factory=list)


def _read_csv(path: Path, required: set[str] | None = None) -> tuple[pd.DataFrame, list[str]]:
    if not path.exists():
        return pd.DataFrame(), [f"Missing file: {path.name}"]

    frame = pd.read_csv(path)
    frame.columns = normalize_columns(list(frame.columns))
    warnings: list[str] = []
    if required:
        missing = required - set(frame.columns)
        if missing:
            warnings.append(f"{path.name} is missing columns: {sorted(missing)}")
    return frame, warnings


def _normalize_ticker_column(frame: pd.DataFrame) -> pd.DataFrame:
    if "ticker" in frame.columns:
        frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()
    return frame


def _normalize_percent_column(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    if column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype(float)
        mask = frame[column].notna() & frame[column].abs().gt(1)
        frame.loc[mask, column] = frame.loc[mask, column] / 100.0
    return frame


def _normalize_fundamentals(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    frame = frame.rename(
        columns={
            "revenuegrowth": "revenue_growth",
            "revenue_growth": "revenue_growth",
            "epsgrowth": "eps_growth",
            "eps_growth": "eps_growth",
            "fcfmargin": "fcf_margin",
            "fcf_margin": "fcf_margin",
            "grossmargin": "gross_margin",
            "gross_margin": "gross_margin",
            "operatingmargin": "operating_margin",
            "operating_margin": "operating_margin",
            "debttoequity": "debt_to_equity",
            "debt_to_equity": "debt_to_equity",
            "pe": "pe",
            "pe_ratio": "pe",
            "forwardpe": "forward_pe",
            "forward_pe": "forward_pe",
            "evtosales": "ev_to_sales",
            "ev_to_sales": "ev_to_sales",
            "evtoebitda": "ev_to_ebitda",
            "ev_to_ebitda": "ev_to_ebitda",
            "pricetofcf": "price_to_fcf",
            "price_to_fcf": "price_to_fcf",
            "fcfyield": "fcf_yield",
            "fcf_yield": "fcf_yield",
        }
    )

    numeric_columns = [
        "revenue_growth",
        "eps_growth",
        "fcf_margin",
        "gross_margin",
        "operating_margin",
        "debt_to_equity",
        "pe",
        "forward_pe",
        "ev_to_sales",
        "ev_to_ebitda",
        "price_to_fcf",
        "fcf_yield",
    ]
    for column in numeric_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _normalize_peers(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    if "peer_ticker" in frame.columns:
        frame["peer_ticker"] = frame["peer_ticker"].astype(str).str.upper().str.strip()
    return frame


def _read_optional_csv(path: Path) -> tuple[pd.DataFrame, list[str]]:
    if not path.exists():
        return pd.DataFrame(), []
    return _read_csv(path)


def load_inputs(base_dir: Path, fetcher: DataFetcher) -> LoadedData:
    config = AppConfig.load(base_dir / "config.yaml")
    warnings: list[str] = []

    universe, universe_warnings = _read_csv(
        base_dir / "data" / "universe.csv",
        required={"ticker", "theme", "sectoretf", "defaultpurpose", "marketcapbucket"},
    )
    holdings, holdings_warnings = _read_csv(
        base_dir / "data" / "holdings.csv",
        required={"ticker", "primarypurpose"},
    )
    theme_map, theme_map_warnings = _read_csv(
        base_dir / "data" / "theme_map.csv",
        required={"theme", "etf", "description"},
    )
    fundamentals, fundamentals_warnings = _read_csv(base_dir / "data" / "fundamentals.csv")
    peers, peers_warnings = _read_optional_csv(base_dir / "data" / "peers.csv")

    warnings.extend(universe_warnings + holdings_warnings + theme_map_warnings + fundamentals_warnings + peers_warnings)

    holdings = holdings.rename(
        columns={
            "primarypurpose": "primary_purpose",
            "secondarytags": "secondary_tags",
            "originalthesis": "original_thesis",
            "positionpercent": "position_percent",
            "costbasis": "cost_basis",
            "maxpositionpercent": "max_position_percent",
            "invalidationoverride": "invalidation_override",
        }
    )
    universe = universe.rename(
        columns={
            "defaultpurpose": "default_purpose",
            "marketcapbucket": "market_cap_bucket",
            "sectoretf": "sector_etf",
        }
    )

    for frame in (universe, holdings, theme_map, fundamentals, peers):
        _normalize_ticker_column(frame)
    fundamentals = _normalize_fundamentals(fundamentals)
    peers = _normalize_peers(peers)

    for column in ("position_percent", "max_position_percent"):
        holdings = _normalize_percent_column(holdings, column)
    for numeric_column in ("shares", "cost_basis"):
        if numeric_column in holdings.columns:
            holdings[numeric_column] = pd.to_numeric(holdings[numeric_column], errors="coerce")

    tickers: set[str] = set()
    if not universe.empty and "ticker" in universe.columns:
        tickers.update(universe["ticker"].dropna().astype(str))
    if not holdings.empty and "ticker" in holdings.columns:
        tickers.update(holdings["ticker"].dropna().astype(str))

    for benchmark_group in config.benchmarks.values():
        tickers.update(str(ticker).upper() for ticker in benchmark_group)

    if not universe.empty and "sector_etf" in universe.columns:
        tickers.update(universe["sector_etf"].dropna().astype(str))
    if not theme_map.empty and "etf" in theme_map.columns:
        tickers.update(theme_map["etf"].dropna().astype(str))

    fetch_result = fetcher.load_ohlcv(sorted(tickers))
    warnings.extend(fetch_result.warnings)

    return LoadedData(
        config=config,
        universe=universe,
        holdings=holdings,
        theme_map=theme_map,
        fundamentals=fundamentals,
        peers=peers,
        prices=fetch_result.prices,
        warnings=warnings,
    )
