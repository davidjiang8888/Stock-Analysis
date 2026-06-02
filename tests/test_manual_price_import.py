from pathlib import Path

import pandas as pd

from src.manual_price_import import build_price_coverage_report, import_staged_prices


def _write_universe(data_dir: Path, tickers: list[str]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"ticker": tickers}).to_csv(data_dir / "universe.csv", index=False)


def test_import_staged_prices_merges_valid_alias_columns_and_preserves_existing_rows(tmp_path: Path):
    data_dir = tmp_path / "data"
    staged_dir = data_dir / "staged" / "prices"
    staged_dir.mkdir(parents=True)
    _write_universe(data_dir, ["AMD", "NVDA"])
    (data_dir / "prices.csv").write_text(
        "date,ticker,adj_close,volume\n"
        "2026-01-02,NVDA,500,1000\n",
        encoding="utf-8",
    )
    (staged_dir / "amd.csv").write_text(
        "symbol,Date,adj_close,volume,source\n"
        "amd,2026-01-02,120,2000,broker_export\n"
        "amd,2026-01-02,121,2100,broker_export_later\n"
        "amd,2026-01-03,122,2200,broker_export\n",
        encoding="utf-8",
    )

    result = import_staged_prices(tmp_path)
    prices = pd.read_csv(data_dir / "prices.csv")
    rejected = pd.read_csv(data_dir / "price_import_rejected.csv")

    assert result.status == "imported"
    assert result.rows_valid == 2
    assert result.duplicate_rows == 1
    assert set(prices["ticker"]) == {"AMD", "NVDA"}
    assert prices.loc[prices["ticker"].eq("NVDA"), "close"].iloc[0] == 500
    assert prices.loc[prices["ticker"].eq("AMD") & prices["date"].eq("2026-01-02"), "close"].iloc[0] == 121
    assert "duplicate_ticker_date_dropped" in set(rejected["rejection_reason"])


def test_import_staged_prices_rejects_invalid_rows_with_report(tmp_path: Path):
    data_dir = tmp_path / "data"
    staged_dir = data_dir / "staged" / "prices"
    staged_dir.mkdir(parents=True)
    _write_universe(data_dir, ["AMD"])
    (staged_dir / "bad_rows.csv").write_text(
        "ticker,date,close,volume,source\n"
        "AMD,not-a-date,120,1000,manual\n"
        "AMD,2026-01-02,-1,1000,manual\n"
        "META,2026-01-02,300,1000,manual\n"
        "AMD,2026-01-03,121,-5,manual\n",
        encoding="utf-8",
    )

    result = import_staged_prices(tmp_path)
    rejected = pd.read_csv(data_dir / "price_import_rejected.csv")

    assert result.status == "no_valid_rows"
    assert result.rows_rejected == 4
    assert set(rejected["rejection_reason"]) == {
        "invalid_date",
        "close_must_be_positive",
        "ticker_not_in_universe",
        "volume_must_be_non_negative",
    }


def test_import_staged_prices_dedupes_across_files_deterministically(tmp_path: Path):
    data_dir = tmp_path / "data"
    staged_dir = data_dir / "staged" / "prices"
    staged_dir.mkdir(parents=True)
    _write_universe(data_dir, ["AMD"])
    (staged_dir / "a_first.csv").write_text(
        "ticker,date,close,volume\nAMD,2026-01-02,120,1000\n",
        encoding="utf-8",
    )
    (staged_dir / "b_second.csv").write_text(
        "ticker,date,close,volume\nAMD,2026-01-02,121,1100\n",
        encoding="utf-8",
    )

    result = import_staged_prices(tmp_path)
    prices = pd.read_csv(data_dir / "prices.csv")
    rejected = pd.read_csv(data_dir / "price_import_rejected.csv")

    assert result.rows_valid == 1
    assert result.duplicate_rows == 1
    assert prices.iloc[0]["close"] == 121
    assert "duplicate_ticker_date_dropped_across_files" in set(rejected["rejection_reason"])
    assert rejected.iloc[0]["source_file"].endswith("a_first.csv")
    assert "source_file" not in prices.columns


def test_price_coverage_report_lists_rows_per_ticker_and_missing_key_status(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    _write_universe(data_dir, ["AMD", "NVDA"])
    rows = [
        {"date": date.strftime("%Y-%m-%d"), "ticker": "NVDA", "adj_close": 100 + index, "volume": 1000 + index}
        for index, date in enumerate(pd.date_range("2026-01-01", periods=21, freq="D"))
    ]
    pd.DataFrame(rows).to_csv(data_dir / "prices.csv", index=False)
    monkeypatch.delenv("STOOQ_API_KEY", raising=False)

    coverage = build_price_coverage_report(tmp_path)
    by_ticker = coverage.set_index("ticker")

    assert by_ticker.loc["NVDA", "price_rows"] == 21
    assert bool(by_ticker.loc["NVDA", "usable_for_momentum"]) is True
    assert by_ticker.loc["AMD", "price_rows"] == 0
    assert bool(by_ticker.loc["AMD", "has_price_coverage"]) is False
    assert "missing STOOQ_API_KEY" in by_ticker.loc["AMD", "remote_price_refresh_status"]
    assert "PROVIDER=yahoo" in by_ticker.loc["AMD", "remote_price_refresh_status"]
    assert "data/staged/prices" in by_ticker.loc["AMD", "manual_staged_price_import"]
    assert (data_dir / "price_coverage_report.csv").exists()
