from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import AppConfig
from src.paths import format_path_context, resolve_data_dir, resolve_outputs_dir, resolve_project_root


OUTPUT_COLUMNS = [
    "Month",
    "Rank",
    "Ticker",
    "CompanyName",
    "Theme",
    "Sector",
    "FinalState",
    "SetupStatus",
    "PrimaryPurpose",
    "CompositeScore",
    "MomentumScore",
    "QualityScore",
    "ValuationContextScore",
    "RiskPenalty",
    "LiquidityScore",
    "TechnicalContextScore",
    "MAStackStatus",
    "RSI14",
    "VolumeTrend",
    "Reason",
    "MissingDataFields",
    "SourceFiles",
    "GeneratedAt",
]


@dataclass(frozen=True)
class MonthlyPickWeights:
    momentum: float = 0.40
    final_state: float = 0.25
    quality: float = 0.15
    valuation: float = 0.10
    liquidity: float = 0.10
    risk_penalty: float = 0.10

    def validate(self) -> None:
        positive_total = self.momentum + self.final_state + self.quality + self.valuation + self.liquidity
        if not math.isclose(positive_total, 1.0, abs_tol=0.001):
            raise ValueError(f"Monthly pick positive weights must sum to 1.0, got {positive_total:.3f}.")
        if self.risk_penalty < 0:
            raise ValueError("Monthly pick risk penalty weight must be non-negative.")


@dataclass(frozen=True)
class MonthlyPickConfig:
    top_n: int = 5
    benchmark: str = "SPY"
    weights: MonthlyPickWeights = MonthlyPickWeights()


STATE_SCORES = {
    "Buyable Area": 100.0,
    "Pullback Add Candidate": 92.0,
    "Watch": 82.0,
    "Setup Forming": 76.0,
    "Extended / No Chase": 60.0,
    "Review Thesis": 48.0,
    "Risk Reduce": 25.0,
    "Broken": 5.0,
    "Ignore": 0.0,
    "Avoid": 0.0,
}

VALUE_CATEGORY_SCORES = {
    "Undervalued Quality": 90.0,
    "Re-rating Candidate": 82.0,
    "Cheap but No Momentum": 55.0,
    "Insufficient Data": 45.0,
    "Possible Value Trap": 20.0,
    "Avoid": 10.0,
}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _clean_ticker(value: object) -> str:
    return str(value or "").strip().upper()


def _score_from_percent(value: object) -> float | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return float(max(0.0, min(100.0, numeric)))


def _score_return(value: object) -> float | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return float(max(0.0, min(100.0, 50.0 + float(numeric) * 250.0)))


def _average_available(values: list[float | None]) -> float | None:
    available = [float(value) for value in values if value is not None and pd.notna(value)]
    if not available:
        return None
    return round(sum(available) / len(available), 2)


def _score_momentum(row: pd.Series, missing: list[str]) -> float | None:
    components = [
        _score_from_percent(row.get("RSPercentile")),
        _score_return(row.get("Return1M")),
        _score_return(row.get("Return3M")),
        _score_return(row.get("Return6M")),
        _score_return(row.get("Return12M")),
    ]
    labels = ["RSPercentile", "Return1M", "Return3M", "Return6M", "Return12M"]
    for label, value in zip(labels, components, strict=True):
        if value is None:
            missing.append(label)
    setup_score = STATE_SCORES.get(str(row.get("SetupStatus", "")))
    if setup_score is not None:
        components.append(setup_score)
    return _average_available(components)


def _score_liquidity(row: pd.Series, missing: list[str]) -> float | None:
    avg_volume = pd.to_numeric(pd.Series([row.get("AvgVolume20D")]), errors="coerce").iloc[0]
    if pd.isna(avg_volume) or float(avg_volume) <= 0:
        missing.append("AvgVolume20D")
        return None
    return round(max(0.0, min(100.0, 20.0 * math.log10(float(avg_volume) / 100_000.0 + 1.0))), 2)


def _calculate_rsi(values: pd.Series, period: int = 14) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if len(clean) <= period:
        return None
    delta = clean.diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    latest_loss = loss.iloc[-1]
    latest_gain = gain.iloc[-1]
    if pd.isna(latest_gain) or pd.isna(latest_loss):
        return None
    if latest_loss == 0:
        return 100.0
    rs = latest_gain / latest_loss
    return round(float(100.0 - (100.0 / (1.0 + rs))), 2)


def _technical_context(momentum_row: pd.Series, price_history: pd.DataFrame) -> dict[str, object]:
    close = pd.to_numeric(pd.Series([momentum_row.get("Close")]), errors="coerce").iloc[0]
    ema10 = pd.to_numeric(pd.Series([momentum_row.get("EMA10")]), errors="coerce").iloc[0]
    ema21 = pd.to_numeric(pd.Series([momentum_row.get("EMA21")]), errors="coerce").iloc[0]
    sma50 = pd.to_numeric(pd.Series([momentum_row.get("SMA50")]), errors="coerce").iloc[0]
    sma200 = pd.to_numeric(pd.Series([momentum_row.get("SMA200")]), errors="coerce").iloc[0]
    volume_ratio = pd.to_numeric(pd.Series([momentum_row.get("VolumeRatio")]), errors="coerce").iloc[0]

    stack_checks = [close, ema10, ema21, sma50, sma200]
    if all(pd.notna(value) for value in stack_checks) and close > ema10 > ema21 > sma50 > sma200:
        ma_stack = "Bullish stack"
        ma_points = 100.0
    elif all(pd.notna(value) for value in (close, ema10, ema21)) and close > ema10 > ema21:
        ma_stack = "Short-term constructive"
        ma_points = 75.0
    elif pd.notna(close) and pd.notna(sma50) and close < sma50:
        ma_stack = "Below 50SMA"
        ma_points = 25.0
    else:
        ma_stack = "Not enough moving-average history"
        ma_points = None

    rsi = _calculate_rsi(price_history["close"]) if not price_history.empty and "close" in price_history.columns else None
    volume_trend = "Not available"
    volume_points = None
    if pd.notna(volume_ratio):
        volume_trend = "Above average" if float(volume_ratio) >= 1.2 else "Normal" if float(volume_ratio) >= 0.8 else "Below average"
        volume_points = max(0.0, min(100.0, float(volume_ratio) * 50.0))

    score = _average_available([ma_points, None if rsi is None else max(0.0, min(100.0, 100.0 - abs(rsi - 55.0) * 2.0)), volume_points])
    return {
        "technical_score": score,
        "ma_stack_status": ma_stack,
        "rsi14": rsi,
        "volume_trend": volume_trend,
    }


def _risk_penalty(row: pd.Series, value_row: pd.Series, missing_fields: list[str]) -> float:
    penalty = 0.0
    setup = str(row.get("SetupStatus", ""))
    final_state = str(row.get("FinalState", ""))
    if setup in {"Avoid", "Broken"}:
        penalty += 25.0
    if final_state in {"Risk Reduce", "Broken", "Ignore"}:
        penalty += 35.0
    trap_score = pd.to_numeric(pd.Series([value_row.get("ValueTrapRiskScore")]), errors="coerce").iloc[0]
    if pd.notna(trap_score):
        penalty += min(40.0, float(trap_score) * 0.4)
    atr = pd.to_numeric(pd.Series([row.get("ATRorVolatilityPct")]), errors="coerce").iloc[0]
    if pd.notna(atr) and float(atr) > 0.08:
        penalty += 10.0
    penalty += min(20.0, len(set(missing_fields)) * 1.5)
    return round(min(100.0, penalty), 2)


def _source_files(*frames: tuple[str, pd.DataFrame]) -> str:
    return ", ".join(name for name, frame in frames if not frame.empty)


def _price_history_for_ticker(prices: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if prices.empty or "ticker" not in prices.columns:
        return pd.DataFrame()
    frame = prices.loc[prices["ticker"].astype(str).str.upper() == ticker].copy()
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce", format="mixed")
        frame = frame.sort_values("date")
    if "close" not in frame.columns and "adj_close" in frame.columns:
        frame["close"] = frame["adj_close"]
    return frame


def build_monthly_research_picks(
    base_dir: Path | None = None,
    *,
    data_dir: Path | None = None,
    output_dir: Path | None = None,
    top_n: int | None = None,
    benchmark: str | None = None,
    weights: MonthlyPickWeights | None = None,
    write_output: bool = True,
) -> dict[str, object]:
    base_dir = resolve_project_root(base_dir)
    data_dir = resolve_data_dir(data_dir, base_dir)
    output_dir = resolve_outputs_dir(output_dir, base_dir)
    config_raw = AppConfig.load(base_dir / "config.yaml").raw.get("monthly_picks", {})
    weights_raw = config_raw.get("weights", {})
    weights = weights or MonthlyPickWeights(
        momentum=float(weights_raw.get("momentum", 0.40)),
        final_state=float(weights_raw.get("final_state", 0.25)),
        quality=float(weights_raw.get("quality", 0.15)),
        valuation=float(weights_raw.get("valuation", 0.10)),
        liquidity=float(weights_raw.get("liquidity", 0.10)),
        risk_penalty=float(weights_raw.get("risk_penalty", 0.10)),
    )
    weights.validate()
    top_n = int(top_n if top_n is not None else config_raw.get("top_n", 5))
    benchmark = str(benchmark if benchmark is not None else config_raw.get("benchmark", "SPY"))
    config = MonthlyPickConfig(top_n=top_n, benchmark=benchmark, weights=weights)
    generated_at = datetime.now(UTC).isoformat()
    outputs_dir = output_dir

    final = _read_csv(outputs_dir / "final_watchlist.csv")
    momentum = _read_csv(outputs_dir / "momentum_leaders.csv")
    value = _read_csv(outputs_dir / "undervalued_candidates.csv")
    universe = _read_csv(data_dir / "universe.csv")
    fundamentals = _read_csv(data_dir / "fundamentals.csv")
    prices = _read_csv(data_dir / "prices.csv")

    if final.empty:
        rows = pd.DataFrame(columns=OUTPUT_COLUMNS)
    else:
        for frame in (final, momentum, value, universe, fundamentals, prices):
            if "ticker" in frame.columns:
                frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()
            if "Ticker" in frame.columns:
                frame["Ticker"] = frame["Ticker"].astype(str).str.upper().str.strip()
        merged = final.merge(momentum, on="Ticker", how="left", suffixes=("", "_Momentum"))
        merged = merged.merge(value, on="Ticker", how="left", suffixes=("", "_Value"))
        universe_key = "Ticker" if "Ticker" in universe.columns else "ticker" if "ticker" in universe.columns else None
        if universe_key:
            universe_subset = universe.rename(columns={universe_key: "Ticker"})
            merged = merged.merge(universe_subset, on="Ticker", how="left", suffixes=("", "_Universe"))

        month = _infer_month(prices)
        rows_list: list[dict[str, object]] = []
        for _, row in merged.iterrows():
            ticker = _clean_ticker(row.get("Ticker"))
            if not ticker:
                continue
            final_state = str(row.get("FinalState", "") or "")
            if final_state in {"Ignore", "Broken", "Risk Reduce"}:
                continue
            missing: list[str] = []
            missing.extend(_split_missing(row.get("MissingDataFields")))
            missing.extend(_split_missing(row.get("MissingDataFields_Value")))
            momentum_score = _score_momentum(row, missing)
            final_state_score = STATE_SCORES.get(str(row.get("FinalState", "")), 0.0)
            quality_score = _score_from_percent(row.get("QualityScore"))
            valuation_score = _score_from_percent(row.get("ValuationScore"))
            relative_score = _score_from_percent(row.get("RelativeOpportunityScore"))
            valuation_context_score = _average_available([valuation_score, relative_score])
            liquidity_score = _score_liquidity(row, missing)
            technical = _technical_context(row, _price_history_for_ticker(prices, ticker))
            technical_score = technical["technical_score"]
            if momentum_score is not None and technical_score is not None:
                momentum_score = round(momentum_score * 0.75 + float(technical_score) * 0.25, 2)
            elif momentum_score is None:
                momentum_score = technical_score
            value_row = row
            risk_penalty = _risk_penalty(row, value_row, missing)
            weighted_components = {
                "momentum": momentum_score,
                "final_state": final_state_score,
                "quality": quality_score,
                "valuation": valuation_context_score,
                "liquidity": liquidity_score,
            }
            composite = _weighted_score(weighted_components, weights) - risk_penalty * weights.risk_penalty
            composite = round(max(0.0, min(100.0, composite)), 2)
            source_files = _source_files(
                ("outputs/final_watchlist.csv", final),
                ("outputs/momentum_leaders.csv", momentum),
                ("outputs/undervalued_candidates.csv", value),
                ("data/universe.csv", universe),
                ("data/fundamentals.csv", fundamentals),
                ("data/prices.csv", prices),
            )
            reason = _build_reason(row, weighted_components, risk_penalty, missing)
            rows_list.append(
                {
                    "Month": month,
                    "Rank": pd.NA,
                    "Ticker": ticker,
                    "CompanyName": row.get("company_name") or row.get("CompanyName") or "",
                    "Theme": row.get("Theme") or row.get("theme") or "Unclassified",
                    "Sector": row.get("SectorETF") or row.get("sector_etf") or row.get("sectoretf") or "",
                    "FinalState": final_state or "Not available",
                    "SetupStatus": row.get("SetupStatus") or "Not available",
                    "PrimaryPurpose": row.get("PrimaryPurpose") or row.get("FinalPrimaryPurpose") or "Not available",
                    "CompositeScore": composite,
                    "MomentumScore": momentum_score,
                    "QualityScore": quality_score,
                    "ValuationContextScore": valuation_context_score,
                    "RiskPenalty": risk_penalty,
                    "LiquidityScore": liquidity_score,
                    "TechnicalContextScore": technical_score,
                    "MAStackStatus": technical["ma_stack_status"],
                    "RSI14": technical["rsi14"],
                    "VolumeTrend": technical["volume_trend"],
                    "Reason": reason,
                    "MissingDataFields": ", ".join(sorted(set(value for value in missing if value))),
                    "SourceFiles": source_files,
                    "GeneratedAt": generated_at,
                }
            )
        rows = pd.DataFrame(rows_list, columns=OUTPUT_COLUMNS)
        if not rows.empty:
            rows = rows.sort_values(["CompositeScore", "Ticker"], ascending=[False, True]).head(top_n).copy()
            rows["Rank"] = range(1, len(rows) + 1)

    output_path = outputs_dir / "monthly_research_picks.csv"
    if write_output:
        outputs_dir.mkdir(parents=True, exist_ok=True)
        rows.to_csv(output_path, index=False)
    return {
        "config": asdict(config),
        "output_path": str(output_path),
        "row_count": int(len(rows)),
        "picks": _records(rows),
        "warnings": _result_warnings(rows, top_n),
    }


def _infer_month(prices: pd.DataFrame) -> str:
    if prices.empty or "date" not in prices.columns:
        return datetime.now(UTC).strftime("%Y-%m")
    dates = pd.to_datetime(prices["date"], errors="coerce", format="mixed").dropna()
    if dates.empty:
        return datetime.now(UTC).strftime("%Y-%m")
    return dates.max().strftime("%Y-%m")


def _split_missing(value: object) -> list[str]:
    if value is None or pd.isna(value):
        return []
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return []
    return [item.strip() for item in text.replace(";", ",").split(",") if item.strip()]


def _json_value(value: object) -> object:
    if value is pd.NA:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for record in frame.to_dict(orient="records"):
        records.append({key: _json_value(value) for key, value in record.items()})
    return records


def _result_warnings(rows: pd.DataFrame, top_n: int) -> list[str]:
    if rows.empty:
        return ["No monthly research candidates could be generated from the current local outputs."]
    if len(rows) < top_n:
        return [f"Only {len(rows)} research candidate(s) met the conservative inclusion filters for top_n={top_n}."]
    return []


def _weighted_score(components: dict[str, float | None], weights: MonthlyPickWeights) -> float:
    score = 0.0
    missing_weight = 0.0
    for name, value in components.items():
        weight = getattr(weights, name)
        if value is None or pd.isna(value):
            missing_weight += weight
        else:
            score += float(value) * weight
    if missing_weight:
        score -= missing_weight * 15.0
    return score


def _build_reason(
    row: pd.Series,
    components: dict[str, float | None],
    risk_penalty: float,
    missing: list[str],
) -> str:
    component_text = {
        name: "Not available" if value is None or pd.isna(value) else f"{float(value):.2f}"
        for name, value in components.items()
    }
    parts = [
        f"Composite score uses transparent local components: momentum {component_text['momentum']}, final-state {component_text['final_state']}, quality {component_text['quality']}, valuation {component_text['valuation']}, liquidity {component_text['liquidity']}.",
        f"Risk penalty is {risk_penalty:.1f}.",
        "This row is a research candidate, not a trade instruction.",
    ]
    rank_reason = row.get("RankReason")
    if pd.notna(rank_reason) and str(rank_reason).strip():
        parts.append(str(rank_reason).strip())
    if missing:
        parts.append("Missing or incomplete fields reduced confidence: " + ", ".join(sorted(set(missing))) + ".")
    return " ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate monthly research candidates from local screener outputs.")
    parser.add_argument("--generate", action="store_true", help="Write outputs/monthly_research_picks.csv.")
    parser.add_argument("--top-n", type=int, help="Number of monthly research candidates.")
    parser.add_argument("--benchmark", help="Benchmark ticker used for downstream track-record comparison.")
    parser.add_argument("--project-root", help="Project root for config.yaml and default data/output directories.")
    parser.add_argument("--data-dir", help="Optional data directory. Relative paths resolve from project root.")
    parser.add_argument("--output-dir", help="Optional output directory. Relative paths resolve from project root.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()

    project_root = resolve_project_root(args.project_root)
    data_dir = resolve_data_dir(args.data_dir, project_root)
    output_dir = resolve_outputs_dir(args.output_dir, project_root)
    result = build_monthly_research_picks(
        project_root,
        data_dir=data_dir,
        output_dir=output_dir,
        top_n=args.top_n,
        benchmark=args.benchmark,
        write_output=True,
    )
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return
    print(format_path_context(project_root, data_dir, output_dir))
    print(f"Generated monthly research picks: {result['output_path']}")
    print(f"Rows: {result['row_count']}")
    for warning in result["warnings"]:
        print(f"Warning: {warning}")


if __name__ == "__main__":
    main()
