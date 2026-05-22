from pathlib import Path

import pandas as pd

from src.data_update import (
    apply_price_import_merge,
    enrich_price_update_status_frame,
    load_update_tickers,
    preview_price_import_merge,
    refresh_price_update_status_output,
    show_price_update_status,
    update_local_price_data,
    validate_price_imports,
)


class FakePriceSource:
    def __init__(self, payloads: dict[str, pd.DataFrame | None]) -> None:
        self.payloads = payloads
        self.calls: list[str] = []

    def fetch_history(self, ticker: str) -> tuple[pd.DataFrame, list[str]]:
        self.calls.append(ticker)
        payload = self.payloads.get(ticker)
        if payload is None:
            return pd.DataFrame(), [f"{ticker}: source unavailable"]
        return payload.copy(), []


def test_load_update_tickers_collects_universe_holdings_themes_and_benchmarks(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(), encoding="utf-8")
    (tmp_path / "data" / "universe.csv").write_text(
        "Ticker,Theme,SectorETF,DefaultPurpose,MarketCapBucket\n"
        "NVDA,AI Semiconductors,SMH,Momentum Leader,Large\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "holdings.csv").write_text(
        "Ticker,PrimaryPurpose\n"
        "META,Core Compounder\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "theme_map.csv").write_text(
        "Theme,ETF,Description\n"
        "Fintech,ARKF,Financial technology\n",
        encoding="utf-8",
    )

    tickers = load_update_tickers(tmp_path)

    assert {"NVDA", "META", "SMH", "ARKF", "SPY", "QQQ"}.issubset(set(tickers))


def test_update_local_price_data_merges_fetched_rows_into_existing_csv(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(), encoding="utf-8")
    (tmp_path / "data" / "prices.csv").write_text(
        "date,ticker,adj_close,volume\n"
        "2026-01-02,SPY,100,1000\n",
        encoding="utf-8",
    )

    source = FakePriceSource(
        {
            "SPY": pd.DataFrame(
                [
                    {
                        "date": pd.Timestamp("2026-01-02"),
                        "ticker": "SPY",
                        "open": 99.0,
                        "high": 101.0,
                        "low": 98.0,
                        "close": 100.0,
                        "adj_close": 100.0,
                        "volume": 1000,
                    },
                    {
                        "date": pd.Timestamp("2026-01-03"),
                        "ticker": "SPY",
                        "open": 100.0,
                        "high": 102.0,
                        "low": 99.0,
                        "close": 101.0,
                        "adj_close": 101.0,
                        "volume": 1100,
                    },
                ]
            ),
            "QQQ": pd.DataFrame(
                [
                    {
                        "date": pd.Timestamp("2026-01-03"),
                        "ticker": "QQQ",
                        "open": 200.0,
                        "high": 202.0,
                        "low": 199.0,
                        "close": 201.0,
                        "adj_close": 201.0,
                        "volume": 2100,
                    }
                ]
            ),
        }
    )

    result = update_local_price_data(tmp_path, source=source, tickers=["SPY", "QQQ"])

    updated = pd.read_csv(result.path)
    assert result.tickers_updated == ["SPY", "QQQ"]
    assert result.rows_written == 3
    assert list(updated.columns) == ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
    assert list(updated["ticker"]) == ["QQQ", "SPY", "SPY"]


def test_update_local_price_data_keeps_existing_csv_when_remote_fetch_returns_nothing(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(), encoding="utf-8")
    (tmp_path / "data" / "prices.csv").write_text(
        "date,ticker,adj_close,volume\n"
        "2026-01-02,SPY,100,1000\n",
        encoding="utf-8",
    )

    source = FakePriceSource({"SPY": None})
    result = update_local_price_data(tmp_path, source=source, tickers=["SPY"])

    preserved = pd.read_csv(result.path)
    assert result.tickers_updated == []
    assert result.tickers_missing == ["SPY"]
    assert any("kept the existing local CSV fallback" in warning for warning in result.warnings)
    assert len(preserved) == 1
    assert preserved.iloc[0]["ticker"] == "SPY"


def test_update_local_price_data_processes_chunks_and_max_tickers(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(), encoding="utf-8")

    source = FakePriceSource(
        {
            "AAA": pd.DataFrame(
                [
                    {
                        "date": pd.Timestamp("2026-01-03"),
                        "ticker": "AAA",
                        "open": 10.0,
                        "high": 11.0,
                        "low": 9.0,
                        "close": 10.5,
                        "adj_close": 10.5,
                        "volume": 1000,
                    }
                ]
            ),
            "BBB": pd.DataFrame(
                [
                    {
                        "date": pd.Timestamp("2026-01-03"),
                        "ticker": "BBB",
                        "open": 20.0,
                        "high": 21.0,
                        "low": 19.0,
                        "close": 20.5,
                        "adj_close": 20.5,
                        "volume": 1200,
                    }
                ]
            ),
            "CCC": pd.DataFrame(
                [
                    {
                        "date": pd.Timestamp("2026-01-03"),
                        "ticker": "CCC",
                        "open": 30.0,
                        "high": 31.0,
                        "low": 29.0,
                        "close": 30.5,
                        "adj_close": 30.5,
                        "volume": 1400,
                    }
                ]
            ),
        }
    )

    result = update_local_price_data(
        tmp_path,
        source=source,
        tickers=["AAA", "BBB", "CCC"],
        chunk_size=2,
        max_tickers=2,
    )

    assert result.chunks_processed == 1
    assert result.tickers_updated == ["AAA", "BBB"]
    assert source.calls == ["AAA", "BBB"]


def test_update_local_price_data_skips_fresh_tickers_unless_refresh_requested(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(), encoding="utf-8")
    fresh_date = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize().date().isoformat()
    (tmp_path / "data" / "prices.csv").write_text(
        "date,ticker,adj_close,volume\n"
        f"{fresh_date},SPY,100,1000\n",
        encoding="utf-8",
    )
    source = FakePriceSource({"SPY": None})

    result = update_local_price_data(tmp_path, source=source, tickers=["SPY"], freshness_days=1)

    assert result.tickers_skipped_fresh == ["SPY"]
    assert source.calls == []


def test_show_price_update_status_missing_file_uses_status_flow_guidance(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "outputs").mkdir()
    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(), encoding="utf-8")

    payload = show_price_update_status(tmp_path)

    assert payload["status"] == "missing_file"
    assert "make status" in payload["warnings"][0]
    assert "make price-normalize" in payload["warnings"][0]


def test_show_price_update_status_enriches_legacy_rows_with_commands(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "outputs").mkdir()
    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(), encoding="utf-8")
    pd.DataFrame(
        [
            {
                "run_timestamp": "2026-05-21T00:00:00+00:00",
                "ticker": "AMD",
                "requested_start": "",
                "requested_end": "2026-05-21",
                "provider": "FakePriceSource",
                "status": "parse_error",
                "rows_fetched": 0,
                "rows_merged": 0,
                "error_category": "parse_error",
                "error_message": "AMD: parse failed",
                "fallback_used": True,
                "recommended_action": "Run make focus-price TICKER=AMD, or run python3 -m src.data_update --tickers AMD and normalize verified downloaded OHLCV files into data/imports/prices.csv.",
            }
        ]
    ).to_csv(tmp_path / "outputs" / "price_update_status.csv", index=False)

    payload = show_price_update_status(tmp_path)

    assert payload["status"] == "available"
    row = payload["rows"][0]
    assert row["recommended_action"].startswith("Run make focus-price TICKER=AMD")
    assert row["focus_command"] == "make focus-price TICKER=AMD"
    assert row["example_command"] == "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual"
    assert row["target_file"] == "data/imports/prices.csv"


def test_enrich_price_update_status_frame_refreshes_stale_price_actions():
    frame = pd.DataFrame(
        [
            {
                "ticker": "QQQ",
                "status": "parse_error",
                "requested_start": "2026-03-15",
                "rows_merged": 0,
                "recommended_action": "Retry later or use staged manual prices in data/imports/prices.csv.",
            }
        ]
    )

    enriched = enrich_price_update_status_frame(frame)

    assert enriched.iloc[0]["recommended_action"].startswith("Run make focus-price TICKER=QQQ")
    assert "normalize verified downloaded OHLCV files into data/imports/prices.csv" in enriched.iloc[0]["recommended_action"]


def test_enrich_price_update_status_frame_normalizes_parse_error_messages():
    frame = pd.DataFrame(
        [
            {
                "ticker": "META",
                "status": "parse_error",
                "error_message": "META: update failed (Error tokenizing data. C error: Expected 1 fields in line 6, saw 2\n)",
                "recommended_action": "Run make focus-price TICKER=META, or run python3 -m src.data_update --tickers META and normalize verified downloaded OHLCV files into data/imports/prices.csv.",
            }
        ]
    )

    enriched = enrich_price_update_status_frame(frame)

    assert enriched.iloc[0]["error_message"] == "META: provider rows could not be parsed cleanly (Expected 1 fields in line 6, saw 2)"
    assert "normalize verified downloaded OHLCV files into data/imports/prices.csv" in enriched.iloc[0]["recommended_action"]


def test_enrich_price_update_status_frame_refreshes_stale_example_command():
    frame = pd.DataFrame(
        [
            {
                "ticker": "AMD",
                "status": "parse_error",
                "requested_start": "",
                "rows_merged": 0,
                "recommended_action": "Run make focus-price TICKER=AMD, or run python3 -m src.data_update --tickers AMD and normalize verified downloaded OHLCV files into data/imports/prices.csv.",
                "example_command": "make onboarding",
            }
        ]
    )

    enriched = enrich_price_update_status_frame(frame)

    assert enriched.iloc[0]["example_command"] == "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual"


def test_refresh_price_update_status_output_rewrites_legacy_file(tmp_path: Path):
    (tmp_path / "outputs").mkdir()
    path = tmp_path / "outputs" / "price_update_status.csv"
    pd.DataFrame(
        [
            {
                "run_timestamp": "2026-05-21T00:00:00+00:00",
                "ticker": "AMD",
                "requested_start": "",
                "requested_end": "2026-05-21",
                "provider": "FakePriceSource",
                "status": "parse_error",
                "rows_fetched": 0,
                "rows_merged": 0,
                "error_category": "parse_error",
                "error_message": "AMD: parse failed",
                "fallback_used": True,
                "recommended_action": "Retry later or use staged manual prices in data/imports/prices.csv.",
            }
        ]
    ).to_csv(path, index=False)

    written_path = refresh_price_update_status_output(tmp_path)

    assert written_path == path
    refreshed = pd.read_csv(path)
    assert refreshed.iloc[0]["focus_command"] == "make focus-price TICKER=AMD"
    assert refreshed.iloc[0]["example_command"] == "make price-normalize INPUT=data/raw/prices/AMD.csv TICKER=AMD SOURCE=yahoo_manual"
    assert refreshed.iloc[0]["target_file"] == "data/imports/prices.csv"
    assert refreshed.iloc[0]["recommended_action"].startswith("Run make focus-price TICKER=AMD")


def test_refresh_price_update_status_output_rewrites_legacy_parse_error_message(tmp_path: Path):
    (tmp_path / "outputs").mkdir()
    path = tmp_path / "outputs" / "price_update_status.csv"
    pd.DataFrame(
        [
            {
                "run_timestamp": "2026-05-21T00:00:00+00:00",
                "ticker": "META",
                "requested_start": "",
                "requested_end": "2026-05-21",
                "provider": "FakePriceSource",
                "status": "parse_error",
                "rows_fetched": 0,
                "rows_merged": 0,
                "error_category": "parse_error",
                "error_message": "META: update failed (Error tokenizing data. C error: Expected 1 fields in line 6, saw 2\n)",
                "fallback_used": True,
                "recommended_action": "Retry later or use staged manual prices in data/imports/prices.csv.",
            }
        ]
    ).to_csv(path, index=False)

    refresh_price_update_status_output(tmp_path)

    refreshed = pd.read_csv(path)
    assert refreshed.iloc[0]["error_message"] == "META: provider rows could not be parsed cleanly (Expected 1 fields in line 6, saw 2)"
    assert "normalize verified downloaded OHLCV files into data/imports/prices.csv" in refreshed.iloc[0]["recommended_action"]


class FlakyPriceSource(FakePriceSource):
    def __init__(self, payloads: dict[str, pd.DataFrame | None]) -> None:
        super().__init__(payloads)
        self.fail_once = {"BBB"}

    def fetch_history(self, ticker: str) -> tuple[pd.DataFrame, list[str]]:
        self.calls.append(ticker)
        if ticker in self.fail_once:
            self.fail_once.remove(ticker)
            raise RuntimeError("temporary failure")
        return super().fetch_history(ticker)


def test_update_local_price_data_retries_and_continues_when_one_ticker_fails(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(), encoding="utf-8")
    source = FlakyPriceSource(
        {
            "AAA": pd.DataFrame(
                [
                    {
                        "date": pd.Timestamp("2026-01-03"),
                        "ticker": "AAA",
                        "open": 10.0,
                        "high": 11.0,
                        "low": 9.0,
                        "close": 10.5,
                        "adj_close": 10.5,
                        "volume": 1000,
                    }
                ]
            ),
            "BBB": pd.DataFrame(
                [
                    {
                        "date": pd.Timestamp("2026-01-03"),
                        "ticker": "BBB",
                        "open": 20.0,
                        "high": 21.0,
                        "low": 19.0,
                        "close": 20.5,
                        "adj_close": 20.5,
                        "volume": 1200,
                    }
                ]
            ),
        }
    )

    result = update_local_price_data(tmp_path, source=source, tickers=["AAA", "BBB"], retry_attempts=1)

    assert set(result.tickers_updated) == {"AAA", "BBB"}
    assert source.calls.count("BBB") >= 2


def test_update_local_price_data_writes_status_when_remote_parse_errors(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "outputs").mkdir()
    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(), encoding="utf-8")
    (tmp_path / "data" / "prices.csv").write_text(
        "date,ticker,adj_close,volume\n2026-01-02,SPY,100,1000\n",
        encoding="utf-8",
    )
    source = FakePriceSource({"SPY": pd.DataFrame()})

    def fetch_history(_ticker: str):
        return pd.DataFrame(), ["SPY: update failed (Error tokenizing data)"]

    source.fetch_history = fetch_history
    result = update_local_price_data(tmp_path, source=source, tickers=["SPY"])

    status = pd.read_csv(result.status_path)
    assert status.iloc[0]["status"] == "parse_error"
    assert status.iloc[0]["fallback_used"] in {True, "True", "true"}
    assert "normalize verified downloaded ohlcv files into data/imports/prices.csv" in status.iloc[0]["recommended_action"].lower()
    assert status.iloc[0]["focus_command"] == "make focus-price TICKER=SPY"
    assert status.iloc[0]["example_command"] == "make price-normalize INPUT=data/raw/prices/SPY.csv TICKER=SPY SOURCE=yahoo_manual"
    assert status.iloc[0]["target_file"] == "data/imports/prices.csv"


def _write_price_import_fixture(root: Path) -> None:
    data_dir = root / "data"
    import_dir = data_dir / "imports"
    data_dir.mkdir()
    import_dir.mkdir(parents=True)
    (root / "config.yaml").write_text(Path("config.yaml").read_text(), encoding="utf-8")
    (data_dir / "prices.csv").write_text(
        "date,ticker,open,high,low,close,adj_close,volume,source\n"
        "2026-01-02,NVDA,99,101,98,100,100,1000,canonical\n"
        "2026-01-02,MSFT,199,201,198,200,200,2000,canonical\n",
        encoding="utf-8",
    )
    (import_dir / "prices.csv").write_text(
        "date,ticker,open,high,low,close,volume,adjusted_close,source,as_of_date,notes,extra\n"
        "2026-01-02,nvda,100,103,99,102,1500,102,manual,2026-01-03,updated,row-extra\n"
        "2026-01-03,NVDA,102,104,101,103,1600,103,manual,2026-01-03,new,row-extra\n"
        "2026-01-02,NVDA,100,103,99,102,1500,102,manual,2026-01-03,duplicate,row-extra\n"
        "2026-01-04,BAD,10,9,11,10,100,10,manual,2026-01-03,bad-high-low,row-extra\n",
        encoding="utf-8",
    )


def test_price_import_validation_valid_fixture_and_duplicates(tmp_path: Path):
    _write_price_import_fixture(tmp_path)

    summary = validate_price_imports(tmp_path)

    assert summary["status"] == "valid_with_warnings"
    assert summary["valid_rows"] == 2
    assert summary["duplicate_rows"] == 1
    assert summary["affected_tickers"] == ["NVDA"]
    assert "extra" in summary["unknown_columns"]


def test_price_import_validation_rejects_missing_required_columns(tmp_path: Path):
    data_dir = tmp_path / "data"
    import_dir = data_dir / "imports"
    import_dir.mkdir(parents=True)
    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(), encoding="utf-8")
    (import_dir / "prices.csv").write_text("date,ticker,close\n2026-01-01,NVDA,100\n", encoding="utf-8")

    summary = validate_price_imports(tmp_path)

    assert summary["status"] == "invalid"
    assert {"open", "high", "low", "volume"}.issubset(set(summary["missing_required_columns"]))


def test_preview_price_import_merge_reports_new_updated_and_skipped(tmp_path: Path):
    _write_price_import_fixture(tmp_path)

    preview = preview_price_import_merge(tmp_path)

    assert preview["new_rows"] == 1
    assert preview["updated_rows"] == 1
    assert preview["skipped_rows"] == 2
    assert preview["unchanged_rows"] == 0


def test_apply_price_import_merge_backs_up_and_never_deletes_rows(tmp_path: Path):
    _write_price_import_fixture(tmp_path)

    result = apply_price_import_merge(tmp_path)
    prices = pd.read_csv(tmp_path / "data" / "prices.csv")

    assert result["applied"] is True
    assert result["backup_path"] is not None
    assert Path(result["backup_path"]).exists()
    assert len(prices) == 3
    assert set(prices["ticker"]) == {"NVDA", "MSFT"}
    updated = prices.loc[(prices["ticker"] == "NVDA") & (prices["date"] == "2026-01-02")].iloc[0]
    assert updated["close"] == 102
