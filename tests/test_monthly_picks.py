import json
from pathlib import Path

import pandas as pd

from src.monthly_picks import (
    MonthlyPickWeights,
    build_monthly_research_picks,
)


def _write_monthly_fixture(base: Path) -> None:
    (base / "data").mkdir()
    (base / "outputs").mkdir()
    (base / "config.yaml").write_text(Path("config.yaml").read_text(), encoding="utf-8")
    (base / "data" / "universe.csv").write_text(
        "Ticker,Theme,SectorETF,DefaultPurpose,MarketCapBucket,company_name\n"
        "AAA,AI,QQQ,Momentum Leader,Large,Alpha Analytics\n"
        "BBB,Cloud,QQQ,Core Compounder,Large,Beta Cloud\n"
        "CCC,Semis,SMH,Momentum Leader,Large,Cedar Chips\n"
        "DDD,Fintech,ARKF,Re-rating / Undervalued,Mid,Delta Pay\n"
        "EEE,Software,QQQ,Core Compounder,Large,Echo Apps\n"
        "FFF,EV,QQQ,Speculative Optionality,Mid,Falcon EV\n",
        encoding="utf-8",
    )
    price_rows = ["date,ticker,adj_close,volume"]
    for day in range(1, 31):
        price_rows.append(f"2026-01-{day:02d},AAA,{100 + day},1000000")
        price_rows.append(f"2026-01-{day:02d},BBB,{90 + day * 0.5},400000")
        price_rows.append(f"2026-01-{day:02d},SPY,{100 + day * 0.2},2000000")
    (base / "data" / "prices.csv").write_text("\n".join(price_rows) + "\n", encoding="utf-8")
    (base / "data" / "fundamentals.csv").write_text(
        "Ticker,pe_ratio,revenue_growth,profit_margin\nAAA,22,0.2,0.3\nBBB,28,0.1,0.2\n",
        encoding="utf-8",
    )
    (base / "outputs" / "final_watchlist.csv").write_text(
        "Ticker,Theme,SectorETF,PrimaryPurpose,SetupStatus,FinalState,ValuationStatus,WatchlistScore,WatchlistRank,RankReason,Reason\n"
        "AAA,AI,QQQ,Momentum Leader,Watch,Watch,ready,82,1,Strong local rank,Transparent reason\n"
        "BBB,Cloud,QQQ,Core Compounder,Setup Forming,Setup Forming,ready,70,2,Constructive setup,Transparent reason\n"
        "CCC,Semis,SMH,Momentum Leader,Avoid,Review Thesis,ready,42,3,Needs review,Transparent reason\n"
        "DDD,Fintech,ARKF,Re-rating / Undervalued,Watch,Watch,ready,61,4,Watchlist context,Transparent reason\n"
        "EEE,Software,QQQ,Core Compounder,Extended / No Chase,Extended / No Chase,ready,58,5,Extended,Transparent reason\n"
        "FFF,EV,QQQ,Speculative Optionality,Broken,Broken,ready,5,6,Broken,Transparent reason\n",
        encoding="utf-8",
    )
    (base / "outputs" / "momentum_leaders.csv").write_text(
        "Ticker,Return1M,Return3M,Return6M,Return12M,RSPercentile,SetupStatus,Close,EMA10,EMA21,SMA50,SMA200,AvgVolume20D,VolumeRatio,ATRorVolatilityPct\n"
        "AAA,0.15,0.3,0.5,0.8,96,Watch,130,125,120,110,100,1000000,1.4,0.04\n"
        "BBB,0.08,0.12,0.2,0.3,80,Setup Forming,105,103,101,99,95,400000,1.0,0.03\n"
        "CCC,,,,,Avoid,,,,,,,,\n"
        "DDD,0.04,,,,70,Watch,50,49,48,,,250000,0.9,0.05\n"
        "EEE,0.02,0.05,,,65,Extended / No Chase,75,70,68,60,,100000,0.7,0.09\n"
        "FFF,-0.2,-0.3,-0.4,-0.5,5,Broken,10,12,13,15,20,50000,0.4,0.12\n",
        encoding="utf-8",
    )
    (base / "outputs" / "undervalued_candidates.csv").write_text(
        "Ticker,QualityScore,ValuationScore,ValueTrapRiskScore,RelativeOpportunityScore,FinalValueCategory,MissingDataFields,Reason\n"
        "AAA,90,75,0,60,Re-rating Candidate,,Value context\n"
        "BBB,75,55,5,,Insufficient Data,ForwardPE,Value context\n"
        "CCC,,,,0,,fundamentals unavailable,Value context\n"
        "DDD,60,80,10,70,Re-rating Candidate,FCFMargin,Value context\n"
        "EEE,70,50,20,45,Insufficient Data,EVToSales,Value context\n"
        "FFF,20,10,80,20,Possible Value Trap,EPSGrowth,Value context\n",
        encoding="utf-8",
    )


def test_monthly_picks_generates_top_five_with_reasons_and_missing_data(tmp_path: Path):
    _write_monthly_fixture(tmp_path)

    result = build_monthly_research_picks(tmp_path, top_n=5)

    assert result["row_count"] == 5
    frame = pd.read_csv(tmp_path / "outputs" / "monthly_research_picks.csv")
    assert list(frame["Rank"]) == [1, 2, 3, 4, 5]
    assert frame["Reason"].fillna("").str.len().gt(0).all()
    assert "MissingDataFields" in frame.columns
    assert "AAA" == frame.iloc[0]["Ticker"]


def test_monthly_picks_are_json_serializable_and_avoid_direct_advice(tmp_path: Path):
    _write_monthly_fixture(tmp_path)

    result = build_monthly_research_picks(tmp_path, top_n=5)
    payload = json.dumps(result, default=str).lower()

    assert "research candidate" in payload
    assert "buy now" not in payload
    assert "sell now" not in payload
    assert "strong buy" not in payload


def test_monthly_pick_weights_validate_positive_weights():
    MonthlyPickWeights().validate()

    bad = MonthlyPickWeights(momentum=0.5)
    try:
        bad.validate()
    except ValueError as exc:
        assert "sum to 1.0" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected invalid weights to raise")


def test_missing_data_reduces_monthly_pick_confidence(tmp_path: Path):
    _write_monthly_fixture(tmp_path)

    result = build_monthly_research_picks(tmp_path, top_n=6)
    rows = {row["Ticker"]: row for row in result["picks"]}

    assert rows["CCC"]["CompositeScore"] < rows["AAA"]["CompositeScore"]
    assert "fundamentals unavailable" in rows["CCC"]["MissingDataFields"]


def test_monthly_picks_skip_unranked_or_not_ready_final_watchlist_rows(tmp_path: Path):
    _write_monthly_fixture(tmp_path)
    (tmp_path / "outputs" / "final_watchlist.csv").write_text(
        "Ticker,Theme,SectorETF,PrimaryPurpose,SetupStatus,FinalState,ValuationStatus,WatchlistScore,WatchlistRank,RankReason,Reason\n"
        "AAA,AI,QQQ,Momentum Leader,Watch,Watch,not_ready,50,,Blocked valuation,Transparent reason\n"
        "BBB,Cloud,QQQ,Core Compounder,Setup Forming,Setup Forming,ready,70,,Unranked,Transparent reason\n",
        encoding="utf-8",
    )

    result = build_monthly_research_picks(tmp_path, top_n=5)

    assert result["row_count"] == 0
    assert "No monthly research candidates" in result["warnings"][0]
