import pandas as pd

from src.config import AppConfig
from src.indicators import build_indicator_snapshot, compute_return, ema, relative_strength, sma


def test_moving_averages():
    series = pd.Series([10.0, 20.0, 30.0, 40.0])
    assert sma(series, 2).tolist() == [10.0, 15.0, 25.0, 35.0]
    ema_result = ema(series, 2).round(4).tolist()
    assert ema_result[0] == 10.0
    assert ema_result[-1] > 30.0


def test_relative_strength():
    stock = pd.Series([100.0, 105.0, 110.0, 120.0])
    benchmark = pd.Series([100.0, 104.0, 108.0, 112.0])
    result = relative_strength(stock, benchmark, 3)
    expected = (120.0 / 100.0 - 1) - (112.0 / 100.0 - 1)
    assert round(result, 6) == round(expected, 6)


def test_compute_return():
    series = pd.Series([100.0, 105.0, 110.0, 120.0])
    result = compute_return(series, 3)
    assert round(result, 6) == round(120.0 / 100.0 - 1, 6)


def test_compute_return_handles_short_or_invalid_history():
    short_series = pd.Series([100.0, 105.0])
    zero_start_series = pd.Series([0.0, 5.0, 10.0])
    nan_start_series = pd.Series([float("nan"), 5.0, 10.0])

    assert pd.isna(compute_return(short_series, 3))
    assert pd.isna(compute_return(zero_start_series, 2))
    assert pd.isna(compute_return(nan_start_series, 2))


def test_relative_strength_aligns_by_shared_dates():
    index_stock = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"])
    index_benchmark = pd.to_datetime(["2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"])
    stock = pd.Series([100.0, 110.0, 120.0, 130.0], index=index_stock)
    benchmark = pd.Series([200.0, 210.0, 220.0, 230.0], index=index_benchmark)
    result = relative_strength(stock, benchmark, 2)
    expected = (130.0 / 110.0 - 1) - (220.0 / 200.0 - 1)
    assert round(result, 6) == round(expected, 6)


def test_indicator_snapshot_preserves_rs_percentile_and_respects_history_windows():
    config = AppConfig.load(__import__("pathlib").Path("config.yaml"))
    dates = pd.date_range("2026-01-01", periods=25, freq="B")
    prices = pd.DataFrame(
        [
            *[
                {"date": date, "ticker": "SPY", "close": 100.0 + idx, "volume": 1000}
                for idx, date in enumerate(dates)
            ],
            *[
                {"date": date, "ticker": "AAA", "close": 50.0 + (idx * 2), "volume": 500}
                for idx, date in enumerate(dates)
            ],
        ]
    )
    universe = pd.DataFrame([{"ticker": "AAA", "theme": "Theme", "sector_etf": "SPY"}])
    snapshot, _ = build_indicator_snapshot(prices, universe, pd.DataFrame(), config)
    aaa = snapshot.loc[snapshot["ticker"] == "AAA"].iloc[0]
    assert pd.notna(aaa["rs_percentile"])
    assert pd.isna(aaa["sma_50"])
