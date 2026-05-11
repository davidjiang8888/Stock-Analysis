from pathlib import Path

import pandas as pd

from src.providers.csv_provider import CSVDataFetcher


def test_csv_data_fetcher_handles_title_case_headers(tmp_path: Path):
    prices_path = tmp_path / "prices.csv"
    prices_path.write_text(
        "Date,Ticker,Adj Close,Volume\n"
        "2026-01-02,SPY,100,1000\n"
        "2026-01-03,SPY,101,1100\n",
        encoding="utf-8",
    )

    result = CSVDataFetcher(prices_path).load_ohlcv(["SPY"])

    assert result.warnings == []
    assert list(result.prices["ticker"]) == ["SPY", "SPY"]
    assert pd.api.types.is_datetime64_any_dtype(result.prices["date"])
    assert list(result.prices["close"]) == [100, 101]


def test_csv_data_fetcher_drops_invalid_date_rows_with_warning(tmp_path: Path):
    prices_path = tmp_path / "prices.csv"
    prices_path.write_text(
        "Date,Ticker,Adj Close,Volume\n"
        "not-a-date,SPY,100,1000\n"
        "2026-01-03,SPY,101,1100\n",
        encoding="utf-8",
    )

    result = CSVDataFetcher(prices_path).load_ohlcv(["SPY"])

    assert any("Dropped 1 price rows with invalid dates" in warning for warning in result.warnings)
    assert len(result.prices) == 1
    assert result.prices.iloc[0]["date"] == pd.Timestamp("2026-01-03")
    assert result.prices.iloc[0]["close"] == 101


def test_csv_data_fetcher_drops_invalid_required_rows_with_warning(tmp_path: Path):
    prices_path = tmp_path / "prices.csv"
    prices_path.write_text(
        "Date,Ticker,Adj Close,Volume\n"
        "2026-01-02,,100,1000\n"
        "2026-01-03,SPY,bad-close,1100\n"
        "2026-01-04,SPY,101,good-volume\n"
        "2026-01-05,SPY,102,1200\n",
        encoding="utf-8",
    )

    result = CSVDataFetcher(prices_path).load_ohlcv(["SPY"])

    assert any("Dropped 3 price rows with missing or invalid ticker/close/volume" in warning for warning in result.warnings)
    assert len(result.prices) == 1
    assert result.prices.iloc[0]["ticker"] == "SPY"
    assert result.prices.iloc[0]["close"] == 102
    assert result.prices.iloc[0]["volume"] == 1200


def test_csv_data_fetcher_drops_non_positive_close_and_negative_volume(tmp_path: Path):
    prices_path = tmp_path / "prices.csv"
    prices_path.write_text(
        "Date,Ticker,Adj Close,Volume\n"
        "2026-01-02,SPY,0,1000\n"
        "2026-01-03,SPY,-5,1000\n"
        "2026-01-04,SPY,101,-1\n"
        "2026-01-05,SPY,102,1200\n",
        encoding="utf-8",
    )

    result = CSVDataFetcher(prices_path).load_ohlcv(["SPY"])

    assert any("Dropped 3 price rows with missing or invalid ticker/close/volume" in warning for warning in result.warnings)
    assert len(result.prices) == 1
    assert result.prices.iloc[0]["close"] == 102
    assert result.prices.iloc[0]["volume"] == 1200


def test_csv_data_fetcher_drops_duplicate_date_ticker_rows_with_warning(tmp_path: Path):
    prices_path = tmp_path / "prices.csv"
    prices_path.write_text(
        "Date,Ticker,Adj Close,Volume\n"
        "2026-01-02,SPY,100,1000\n"
        "2026-01-02,SPY,105,1200\n"
        "2026-01-03,SPY,106,1300\n",
        encoding="utf-8",
    )

    result = CSVDataFetcher(prices_path).load_ohlcv(["SPY"])

    assert any("Dropped 1 duplicate price rows by date/ticker" in warning for warning in result.warnings)
    assert len(result.prices) == 2
    assert list(result.prices["close"]) == [105, 106]
    assert list(result.prices["volume"]) == [1200, 1300]
