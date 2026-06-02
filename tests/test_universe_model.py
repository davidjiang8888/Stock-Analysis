from pathlib import Path

import pandas as pd

from src.universe_model import ensure_universe_files, infer_asset_type, refresh_universe


def test_ensure_universe_files_preserves_legacy_active_universe(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame(
        [
            {
                "Ticker": "QQQ",
                "Theme": "Market Proxy",
                "SectorETF": "QQQ",
                "DefaultPurpose": "ETF / Defensive / Hedge",
                "MarketCapBucket": "ETF",
                "Notes": "legacy active row",
            }
        ]
    ).to_csv(data_dir / "universe.csv", index=False)

    master, active = ensure_universe_files(tmp_path)

    assert (data_dir / "universe.csv").exists()
    assert master.loc[0, "ticker"] == "QQQ"
    assert master.loc[0, "asset_type"] == "etf"
    assert active.loc[0, "scope"] == "active_research"
    assert active.loc[0, "theme"] == "Market Proxy"


def test_ensure_universe_files_syncs_new_legacy_rows_into_master_without_expanding_active(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame(
        [
            {
                "ticker": "NVDA",
                "name": "NVIDIA",
                "exchange": "NASDAQ",
                "asset_type": "company",
                "security_type": "common_stock",
                "sector": "Technology",
                "industry": "Semiconductors",
                "country": "US",
                "currency": "USD",
                "is_active_listing": True,
                "source": "manual",
                "source_updated_at": "",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        ]
    ).to_csv(data_dir / "universe_master.csv", index=False)
    pd.DataFrame(
        [
            {
                "ticker": "NVDA",
                "scope": "active_research",
                "priority": 1,
                "theme": "AI",
                "research_status": "active",
                "user_notes": "",
                "added_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        ]
    ).to_csv(data_dir / "universe_active.csv", index=False)
    pd.DataFrame(
        [
            {"Ticker": "NVDA", "Theme": "AI", "DefaultPurpose": "Momentum Leader", "Notes": "active"},
            {"Ticker": "AAPL", "CompanyName": "Apple Inc.", "Theme": "Broad Market", "DefaultPurpose": "Core Compounder"},
        ]
    ).to_csv(data_dir / "universe.csv", index=False)

    master, active = ensure_universe_files(tmp_path)

    assert {"NVDA", "AAPL"} <= set(master["ticker"])
    assert set(active["ticker"]) == {"NVDA"}


def test_infer_asset_type_does_not_treat_sector_etf_notes_as_etf():
    row = pd.Series(
        {
            "default_purpose": "Core Compounder",
            "market_cap_bucket": "Large",
            "notes": "Theme and sector ETF metadata were not provided by the Nasdaq directory.",
            "is_etf": False,
        }
    )

    assert infer_asset_type("AMD", row) == "company"


def test_ensure_universe_files_repairs_stale_etf_asset_type_from_legacy_company_row(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame(
        [
            {
                "ticker": "A",
                "company_name": "Agilent Technologies",
                "default_purpose": "Core Compounder",
                "notes": "Theme and sector ETF metadata were not provided by the Nasdaq directory.",
            },
            {"ticker": "QQQ", "default_purpose": "ETF / Defensive / Hedge", "sector_etf": "QQQ"},
        ]
    ).to_csv(data_dir / "universe.csv", index=False)
    pd.DataFrame(
        [
            {"ticker": "A", "name": "Agilent Technologies", "asset_type": "etf", "security_type": ""},
            {"ticker": "QQQ", "name": "Invesco QQQ", "asset_type": "etf", "security_type": ""},
        ]
    ).to_csv(data_dir / "universe_master.csv", index=False)

    master, _active = ensure_universe_files(tmp_path)
    by_ticker = master.set_index("ticker")

    assert by_ticker.loc["A", "asset_type"] == "company"
    assert by_ticker.loc["QQQ", "asset_type"] == "etf"


def test_refresh_universe_imports_valid_rows_rejects_invalid_and_dedupes(tmp_path: Path):
    data_dir = tmp_path / "data"
    staged_dir = data_dir / "staged" / "universe"
    staged_dir.mkdir(parents=True)
    pd.DataFrame(
        [{"Ticker": "NVDA", "Theme": "AI", "DefaultPurpose": "Momentum Leader", "Notes": "legacy"}]
    ).to_csv(data_dir / "universe.csv", index=False)
    (staged_dir / "universe_manual.csv").write_text(
        "ticker,name,exchange,asset_type,sector,is_active_listing,source\n"
        "AMD,Advanced Micro Devices,NASDAQ,company,Semiconductors,true,manual\n"
        "AMD,Advanced Micro Devices Inc,NASDAQ,company,Semiconductors,true,manual_later\n"
        "BAD,Bad Asset,NASDAQ,crypto,Speculative,true,manual\n"
        "NOSOURCE,No Source,NASDAQ,company,Tech,true,\n"
        "BADBOOL,Bad Bool,NASDAQ,company,Tech,maybe,manual\n",
        encoding="utf-8",
    )

    result = refresh_universe(tmp_path)
    master = pd.read_csv(data_dir / "universe_master.csv")
    active = pd.read_csv(data_dir / "universe_active.csv")
    rejected = pd.read_csv(data_dir / "rejected" / "universe_rejected.csv")
    report = pd.read_csv(data_dir / "reports" / "universe_coverage_report.csv")

    assert result.rows_valid == 1
    assert "AMD" in set(master["ticker"])
    assert master.loc[master["ticker"].eq("AMD"), "name"].iloc[0] == "Advanced Micro Devices Inc"
    assert "NVDA" in set(active["ticker"])
    assert {"invalid_asset_type", "missing_source", "is_active_listing_not_boolean"} <= set(rejected["rejection_reason"])
    assert "duplicate_ticker_dropped" in set(rejected["rejection_reason"])
    assert set(report["ticker"]) == set(master["ticker"])
