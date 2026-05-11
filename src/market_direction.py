from __future__ import annotations

from typing import Iterable

import pandas as pd

from src.config import AppConfig


THEME_STATUSES = {
    "Strong Rotation",
    "Early Rotation",
    "Overextended",
    "Weak",
    "Broken",
    "Insufficient Data",
}

OUTPUT_COLUMNS = [
    "Theme",
    "ETF",
    "Description",
    "Source",
    "MemberTickers",
    "TickersWithData",
    "HistoryDays",
    "Return1M",
    "Return3M",
    "Return6M",
    "RelativeReturnVsSPY",
    "RelativeReturnVsQQQ",
    "DistanceFrom50SMA",
    "ThemeStatus",
    "MissingDataFields",
    "Reason",
]

STATUS_SORT_ORDER = {
    "Strong Rotation": 0,
    "Early Rotation": 1,
    "Overextended": 2,
    "Weak": 3,
    "Broken": 4,
    "Insufficient Data": 5,
}


def _empty_output() -> pd.DataFrame:
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def _first_non_blank(values: Iterable[object]) -> str:
    for value in values:
        if pd.notna(value) and str(value).strip():
            return str(value).strip()
    return ""


def _format_pct(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value:.1%}"


def _collect_metric(valid_frame: pd.DataFrame, column: str) -> float:
    if valid_frame.empty or column not in valid_frame.columns:
        return float("nan")
    series = pd.to_numeric(valid_frame[column], errors="coerce").dropna()
    if series.empty:
        return float("nan")
    return float(series.median())


def classify_theme_direction(
    history_days: int,
    return_1m: float,
    return_3m: float,
    rs_spy: float,
    rs_qqq: float,
    distance_from_50sma: float,
    config: AppConfig,
) -> tuple[str, str]:
    one_month = int(config.returns.get("lookbacks", {}).get("one_month", 21))
    extension_threshold = config.get_pct("momentum_rules", "extended_distance_from_10ema_pct", 0.10)

    if history_days < one_month and pd.isna(return_1m) and pd.isna(rs_spy):
        return "Insufficient Data", "not enough price history was available to judge theme direction"
    if pd.notna(distance_from_50sma) and distance_from_50sma <= -0.02 and pd.notna(rs_spy) and rs_spy <= -0.05:
        return "Broken", "theme is below its 50SMA and underperforming SPY"
    if pd.notna(distance_from_50sma) and distance_from_50sma >= extension_threshold and (
        (pd.notna(rs_spy) and rs_spy > 0) or (pd.notna(return_1m) and return_1m > 0)
    ):
        return "Overextended", "theme is strong but stretched well above the 50SMA"
    if (
        pd.notna(rs_spy)
        and rs_spy > 0.05
        and pd.notna(rs_qqq)
        and rs_qqq > 0.03
        and pd.notna(return_1m)
        and return_1m > 0
        and (pd.isna(return_3m) or return_3m > 0)
    ):
        return "Strong Rotation", "theme is outperforming both SPY and QQQ with positive momentum"
    if (
        ((pd.notna(rs_spy) and rs_spy > 0) or (pd.notna(return_1m) and return_1m > 0))
        and (pd.isna(distance_from_50sma) or distance_from_50sma >= -0.02)
    ):
        return "Early Rotation", "theme is improving but not yet decisively extended"
    if pd.notna(rs_spy) and rs_spy <= -0.05:
        return "Broken", "theme is materially underperforming SPY"
    if (
        (pd.notna(rs_spy) and rs_spy < 0)
        or (pd.notna(return_1m) and return_1m < 0)
        or (pd.notna(distance_from_50sma) and distance_from_50sma < 0)
    ):
        return "Weak", "theme is lagging or losing trend support"
    if pd.isna(return_1m) and pd.isna(rs_spy) and pd.isna(distance_from_50sma):
        return "Insufficient Data", "theme lacks enough comparable data to classify safely"
    return "Weak", "theme does not yet show decisive rotation"


def run(
    snapshot: pd.DataFrame,
    universe: pd.DataFrame,
    theme_map: pd.DataFrame,
    config: AppConfig,
) -> pd.DataFrame:
    theme_rows: list[dict[str, object]] = []
    universe = universe if not universe.empty else pd.DataFrame(columns=["ticker", "theme", "sector_etf"])
    theme_map = theme_map if not theme_map.empty else pd.DataFrame(columns=["theme", "etf", "description"])
    snapshot = snapshot if not snapshot.empty else pd.DataFrame(columns=["ticker", "close"])

    all_themes = sorted(
        {
            str(value).strip()
            for value in pd.concat(
                [
                    universe["theme"] if "theme" in universe.columns else pd.Series(dtype=object),
                    theme_map["theme"] if "theme" in theme_map.columns else pd.Series(dtype=object),
                ],
                ignore_index=True,
            ).dropna()
            if str(value).strip()
        }
    )
    if not all_themes:
        return _empty_output()
    benchmark_tickers = {
        str(ticker).upper()
        for ticker in config.benchmarks.get("market", [])
    }

    for theme in all_themes:
        universe_rows = universe.loc[universe.get("theme", pd.Series(dtype=object)) == theme].copy()
        theme_map_rows = theme_map.loc[theme_map.get("theme", pd.Series(dtype=object)) == theme].copy()

        member_tickers = sorted(universe_rows.get("ticker", pd.Series(dtype=object)).dropna().astype(str).unique().tolist())
        etf = _first_non_blank(
            list(theme_map_rows.get("etf", pd.Series(dtype=object)).tolist())
            + list(universe_rows.get("sector_etf", pd.Series(dtype=object)).tolist())
        )
        description = _first_non_blank(theme_map_rows.get("description", pd.Series(dtype=object)).tolist())

        constituent_rows = snapshot.loc[snapshot.get("ticker", pd.Series(dtype=object)).isin(member_tickers)].copy()
        constituent_rows = constituent_rows.loc[constituent_rows.get("close", pd.Series(dtype=float)).notna()].copy()
        etf_rows = snapshot.loc[snapshot.get("ticker", pd.Series(dtype=object)) == etf].copy() if etf else pd.DataFrame()
        etf_rows = etf_rows.loc[etf_rows.get("close", pd.Series(dtype=float)).notna()].copy() if not etf_rows.empty else etf_rows

        missing_fields: list[str] = []
        if etf and etf_rows.empty:
            missing_fields.append("theme_etf_price")
        if not etf:
            missing_fields.append("theme_etf_mapping")
        if constituent_rows.empty:
            missing_fields.append("constituent_prices")

        prefer_constituents = bool(etf) and etf.upper() in benchmark_tickers and not constituent_rows.empty

        if not etf_rows.empty and not prefer_constituents:
            source = "Theme ETF"
            source_rows = etf_rows
            source_label = etf
            history_days = int(pd.to_numeric(etf_rows["history_days"], errors="coerce").fillna(0).max())
            tickers_with_data = etf
        elif not constituent_rows.empty:
            source = "Constituent median"
            source_rows = constituent_rows
            source_label = f"{len(constituent_rows)} constituent(s)"
            history_days = int(pd.to_numeric(constituent_rows["history_days"], errors="coerce").fillna(0).median())
            tickers_with_data = ", ".join(sorted(constituent_rows["ticker"].astype(str).unique().tolist()))
        else:
            source = "Unavailable"
            source_rows = pd.DataFrame()
            source_label = "no price source"
            history_days = 0
            tickers_with_data = ""

        return_1m = _collect_metric(source_rows, "return_1m")
        return_3m = _collect_metric(source_rows, "return_3m")
        return_6m = _collect_metric(source_rows, "return_6m")
        rs_spy = _collect_metric(source_rows, "relative_return_vs_spy")
        rs_qqq = _collect_metric(source_rows, "relative_return_vs_qqq")
        distance_from_50sma = _collect_metric(source_rows, "distance_from_50sma")

        if pd.isna(return_1m):
            missing_fields.append("one_month_return")
        if pd.isna(return_3m):
            missing_fields.append("three_month_return")
        if pd.isna(return_6m):
            missing_fields.append("six_month_return")
        if pd.isna(rs_spy):
            missing_fields.append("spy_comparison")
        if pd.isna(rs_qqq):
            missing_fields.append("qqq_comparison")
        if pd.isna(distance_from_50sma):
            missing_fields.append("fifty_day_trend")

        status, status_reason = classify_theme_direction(
            history_days=history_days,
            return_1m=return_1m,
            return_3m=return_3m,
            rs_spy=rs_spy,
            rs_qqq=rs_qqq,
            distance_from_50sma=distance_from_50sma,
            config=config,
        )

        if status == "Insufficient Data" and source == "Constituent median" and len(constituent_rows) < 2:
            missing_fields.append("sparse_constituents")

        reason_parts = [
            f"Used {source.lower()} data from {source_label}.",
            f"1M {_format_pct(return_1m)}, 3M {_format_pct(return_3m)}, 6M {_format_pct(return_6m)}.",
            f"Relative performance vs SPY {_format_pct(rs_spy)} and vs QQQ {_format_pct(rs_qqq)}.",
            f"Distance from 50SMA {_format_pct(distance_from_50sma)}.",
            status_reason.capitalize() + ".",
        ]
        unique_missing = sorted(set(field for field in missing_fields if field))
        if unique_missing:
            reason_parts.append("Missing data fields: " + ", ".join(unique_missing) + ".")

        theme_rows.append(
            {
                "Theme": theme,
                "ETF": etf,
                "Description": description,
                "Source": source,
                "MemberTickers": ", ".join(member_tickers),
                "TickersWithData": tickers_with_data,
                "HistoryDays": history_days,
                "Return1M": return_1m,
                "Return3M": return_3m,
                "Return6M": return_6m,
                "RelativeReturnVsSPY": rs_spy,
                "RelativeReturnVsQQQ": rs_qqq,
                "DistanceFrom50SMA": distance_from_50sma,
                "ThemeStatus": status,
                "MissingDataFields": ", ".join(unique_missing),
                "Reason": " ".join(reason_parts),
            }
        )

    market_df = pd.DataFrame(theme_rows, columns=OUTPUT_COLUMNS)
    market_df["_sort_order"] = market_df["ThemeStatus"].map(STATUS_SORT_ORDER).fillna(len(STATUS_SORT_ORDER))
    market_df = market_df.sort_values(["_sort_order", "Theme"]).drop(columns="_sort_order").reset_index(drop=True)
    return market_df
