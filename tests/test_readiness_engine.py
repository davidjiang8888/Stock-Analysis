from pathlib import Path

import pandas as pd

from src.readiness_engine import build_ticker_readiness_report, save_previous_ticker_readiness_snapshot


def _price_rows(ticker: str, periods: int) -> list[dict[str, object]]:
    return [
        {
            "ticker": ticker,
            "date": date.strftime("%Y-%m-%d"),
            "open": 100 + index,
            "high": 101 + index,
            "low": 99 + index,
            "close": 100 + index,
            "volume": 1_000_000 + index,
            "source": "test_fixture",
        }
        for index, date in enumerate(pd.date_range("2026-01-01", periods=periods, freq="D"))
    ]


def test_save_previous_ticker_readiness_snapshot_uses_deterministic_prior_path(tmp_path: Path):
    data_dir = tmp_path / "data"
    reports_dir = data_dir / "reports"
    reports_dir.mkdir(parents=True)
    current = reports_dir / "ticker_readiness_report.csv"
    pd.DataFrame(
        [
            {"ticker": "AAA", "price_ready": True, "updated_at": "2026-05-29T00:00:00+00:00"},
            {"ticker": "BBB", "price_ready": False, "updated_at": "2026-05-29T00:00:00+00:00"},
        ]
    ).to_csv(current, index=False)

    payload = save_previous_ticker_readiness_snapshot(tmp_path, data_dir=data_dir)
    snapshot = reports_dir / "ticker_readiness_report.previous.csv"

    assert payload["status"] == "written"
    assert payload["rows"] == 2
    assert payload["snapshot_path"] == str(snapshot)
    assert snapshot.exists()
    assert pd.read_csv(snapshot).to_dict("records") == pd.read_csv(current).to_dict("records")


def test_save_previous_ticker_readiness_snapshot_is_honest_when_current_report_missing(tmp_path: Path):
    payload = save_previous_ticker_readiness_snapshot(tmp_path, data_dir=tmp_path / "data")

    assert payload["status"] == "missing_current_report"
    assert payload["rows"] == 0
    assert "make readiness" in payload["message"]


def test_ticker_readiness_report_tracks_ready_blocked_and_excluded_states(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("STOOQ_API_KEY", raising=False)
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    data_dir = tmp_path / "data"
    outputs_dir = tmp_path / "outputs"
    data_dir.mkdir()
    outputs_dir.mkdir()
    pd.DataFrame(
        [
            {"ticker": "NVDA", "name": "NVIDIA", "exchange": "NASDAQ", "asset_type": "company", "sector": "Tech", "source": "test"},
            {"ticker": "AMD", "name": "AMD", "exchange": "NASDAQ", "asset_type": "company", "sector": "Tech", "source": "test"},
            {"ticker": "QQQ", "name": "Invesco QQQ", "exchange": "NASDAQ", "asset_type": "etf", "sector": "ETF", "source": "test"},
        ]
    ).to_csv(data_dir / "universe_master.csv", index=False)
    pd.DataFrame(
        [
            {"ticker": "NVDA", "scope": "active_research", "theme": "AI"},
            {"ticker": "AMD", "scope": "active_research", "theme": "AI"},
            {"ticker": "QQQ", "scope": "active_research", "theme": "Market Proxy"},
        ]
    ).to_csv(data_dir / "universe_active.csv", index=False)
    pd.DataFrame(_price_rows("NVDA", 60) + _price_rows("QQQ", 20)).to_csv(data_dir / "prices.csv", index=False)
    pd.DataFrame(
        [
            {
                "ticker": "NVDA",
                "revenue": 100_000_000,
                "free_cash_flow": 25_000_000,
                "fcf_margin": 0.25,
                "shares_outstanding": 2_000_000,
                "source": "test_fixture",
            }
        ]
    ).to_csv(data_dir / "fundamentals.csv", index=False)
    pd.DataFrame(columns=["ticker", "peer_ticker", "peer_group", "source"]).to_csv(data_dir / "peers.csv", index=False)
    pd.DataFrame(columns=["ticker", "source"]).to_csv(data_dir / "earnings.csv", index=False)
    pd.DataFrame(columns=["ticker", "source"]).to_csv(data_dir / "analyst_estimates.csv", index=False)
    pd.DataFrame(columns=["ticker", "shares"]).to_csv(data_dir / "holdings.csv", index=False)

    reports = build_ticker_readiness_report(tmp_path, data_dir=data_dir, output_dir=outputs_dir)
    readiness = reports["ticker_readiness_report"].set_index("ticker")
    feature_summary = reports["feature_readiness_summary"].set_index("feature")
    source_status = reports["data_source_status"].set_index("source_name")
    peer_unlock = reports["peer_unlock_worklist"].set_index("ticker")

    assert bool(readiness.loc["NVDA", "price_ready"]) is True
    assert bool(readiness.loc["NVDA", "momentum_ready"]) is True
    assert bool(readiness.loc["NVDA", "liquidity_ready"]) is True
    assert bool(readiness.loc["NVDA", "dcf_ready"]) is True
    assert bool(readiness.loc["AMD", "price_ready"]) is False
    assert readiness.loc["AMD", "overall_readiness_state"] == "blocked"
    assert "price" in readiness.loc["AMD", "blocked_features"]
    assert "dcf" in readiness.loc["QQQ", "excluded_features"]
    assert bool(readiness.loc["QQQ", "dcf_ready"]) is False
    assert source_status.loc["remote_price_provider", "status"] == "credential_missing"
    assert source_status.loc["remote_price_provider", "manual_import_path"] == "data/staged/prices/"
    assert source_status.loc["yahoo_price_provider", "status"] == "available"
    assert source_status.loc["yahoo_price_provider", "manual_import_path"] == "make price-refresh PROVIDER=yahoo"
    assert int(feature_summary.loc["price", "ready_count"]) == 2
    assert int(feature_summary.loc["price", "blocked_count"]) == 1
    assert int(feature_summary.loc["dcf", "ready_count"]) == 1
    assert int(feature_summary.loc["dcf", "excluded_count"]) == 1
    assert "AMD" in feature_summary.loc["price", "sample_blocked_tickers"]
    assert "NVDA" in feature_summary.loc["dcf", "sample_ready_tickers"]
    assert feature_summary.loc["dcf", "unlock_command"] == "make dcf-readiness"
    assert feature_summary.loc["price", "next_action"] == "make price-worklist TOP_N=25"
    assert peer_unlock.loc["NVDA", "unlock_stage"] == "add_source_backed_peer_mappings"
    assert peer_unlock.loc["NVDA", "workflow_group"] == "dcf_ready_peer_mapping"
    assert peer_unlock.loc["NVDA", "workflow_scope"] == "active_universe"
    assert "source-backed peer rows" in peer_unlock.loc["NVDA", "next_action_summary"]
    assert peer_unlock.loc["NVDA", "peer_trend_status"] == "peer_trend_blocked"
    assert peer_unlock.loc["NVDA", "peer_valuation_status"] == "peer_valuation_blocked"
    assert peer_unlock.loc["NVDA", "next_input_file"] == "data/imports/peers.csv"
    assert "imports-preview" in peer_unlock.loc["NVDA", "validation_sequence"]
    assert "Copy commands only" in peer_unlock.loc["NVDA", "copy_only_note"]
    assert (data_dir / "reports" / "ticker_readiness_report.csv").exists()
    assert (data_dir / "reports" / "feature_readiness_summary.csv").exists()
    assert (data_dir / "reports" / "peer_unlock_worklist.csv").exists()
    assert (outputs_dir / "feature_readiness_summary.csv").exists()
    assert (outputs_dir / "peer_unlock_worklist.csv").exists()
    assert (data_dir / "reports" / "data_source_status.csv").exists()


def test_peer_unlock_worklist_sorts_active_dcf_ready_rows_before_master_rows(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("STOOQ_API_KEY", raising=False)
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    data_dir = tmp_path / "data"
    outputs_dir = tmp_path / "outputs"
    data_dir.mkdir()
    outputs_dir.mkdir()
    pd.DataFrame(
        [
            {"ticker": "A", "name": "Agilent", "asset_type": "company", "source": "fixture"},
            {"ticker": "META", "name": "Meta", "asset_type": "company", "source": "fixture"},
        ]
    ).to_csv(data_dir / "universe_master.csv", index=False)
    pd.DataFrame([{"ticker": "META", "scope": "active_research", "theme": "Platforms"}]).to_csv(
        data_dir / "universe_active.csv",
        index=False,
    )
    pd.DataFrame(_price_rows("A", 60) + _price_rows("META", 60)).to_csv(data_dir / "prices.csv", index=False)
    pd.DataFrame(
        [
            {"ticker": "A", "revenue": 100, "free_cash_flow": 20, "fcf_margin": 0.2, "shares_outstanding": 10, "source": "fixture"},
            {"ticker": "META", "revenue": 100, "free_cash_flow": 20, "fcf_margin": 0.2, "shares_outstanding": 10, "source": "fixture"},
        ]
    ).to_csv(data_dir / "fundamentals.csv", index=False)
    pd.DataFrame(columns=["ticker", "peer_ticker", "peer_group", "source"]).to_csv(data_dir / "peers.csv", index=False)
    pd.DataFrame(columns=["ticker", "source"]).to_csv(data_dir / "earnings.csv", index=False)
    pd.DataFrame(columns=["ticker", "source"]).to_csv(data_dir / "analyst_estimates.csv", index=False)
    pd.DataFrame(columns=["ticker", "shares"]).to_csv(data_dir / "holdings.csv", index=False)

    reports = build_ticker_readiness_report(tmp_path, data_dir=data_dir, output_dir=outputs_dir)
    worklist = reports["peer_unlock_worklist"]

    assert list(worklist["ticker"].head(2)) == ["META", "A"]
    assert list(worklist["workflow_scope"].head(2)) == ["active_universe", "master_universe"]
    assert set(worklist["workflow_group"]) == {"dcf_ready_peer_mapping"}
    assert set(["workflow_group", "workflow_scope", "next_action_summary", "next_input_file", "validation_sequence"]).issubset(worklist.columns)
    assert worklist["next_input_file"].eq("data/imports/peers.csv").all()
    assert worklist["validation_sequence"].str.contains("make imports-preview", regex=False).all()
    assert worklist["copy_only_note"].str.contains("Copy commands only", regex=False).all()


def test_readiness_requires_source_and_minimum_ready_peer_metrics(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("STOOQ_API_KEY", raising=False)
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    data_dir = tmp_path / "data"
    outputs_dir = tmp_path / "outputs"
    data_dir.mkdir()
    outputs_dir.mkdir()
    pd.DataFrame(
        [
            {"ticker": "AAA", "name": "A Corp", "asset_type": "company", "source": "fixture"},
            {"ticker": "BBB", "name": "B Corp", "asset_type": "company", "source": "fixture"},
            {"ticker": "CCC", "name": "C Corp", "asset_type": "company", "source": "fixture"},
        ]
    ).to_csv(data_dir / "universe_master.csv", index=False)
    pd.DataFrame(
        [
            {"ticker": "AAA", "scope": "active_research", "theme": "Test"},
            {"ticker": "BBB", "scope": "active_research", "theme": "Test"},
            {"ticker": "CCC", "scope": "active_research", "theme": "Test"},
        ]
    ).to_csv(data_dir / "universe_active.csv", index=False)
    pd.DataFrame(_price_rows("AAA", 60) + _price_rows("BBB", 60) + _price_rows("CCC", 60)).to_csv(data_dir / "prices.csv", index=False)
    pd.DataFrame(
        [
            {"ticker": "AAA", "revenue": 100, "source": ""},
            {"ticker": "BBB", "revenue": 100, "source": "fixture"},
            {"ticker": "CCC", "theme": "Metadata only", "sector": "Test", "source": ""},
        ]
    ).to_csv(data_dir / "fundamentals.csv", index=False)
    pd.DataFrame(
        [
            {"ticker": "AAA", "peer_ticker": "BBB", "peer_group": "Test", "source": "fixture"},
            {"ticker": "AAA", "peer_ticker": "CCC", "peer_group": "Test", "source": "fixture"},
        ]
    ).to_csv(data_dir / "peers.csv", index=False)
    pd.DataFrame(columns=["ticker", "source"]).to_csv(data_dir / "earnings.csv", index=False)
    pd.DataFrame(columns=["ticker", "source"]).to_csv(data_dir / "analyst_estimates.csv", index=False)
    pd.DataFrame(columns=["ticker", "shares"]).to_csv(data_dir / "holdings.csv", index=False)

    reports = build_ticker_readiness_report(tmp_path, data_dir=data_dir, output_dir=outputs_dir)
    readiness = reports["ticker_readiness_report"].set_index("ticker")
    fundamentals = reports["fundamentals_coverage_report"].set_index("ticker")
    peers = reports["peer_readiness_report"].set_index("ticker")

    assert bool(fundamentals.loc["AAA", "has_fundamentals"]) is True
    assert bool(fundamentals.loc["AAA", "fundamentals_ready"]) is False
    assert bool(fundamentals.loc["BBB", "has_fundamentals"]) is True
    assert bool(fundamentals.loc["BBB", "fundamentals_ready"]) is False
    assert "free_cash_flow" in fundamentals.loc["BBB", "missing_fundamentals_fields"]
    assert bool(fundamentals.loc["CCC", "has_fundamentals"]) is False
    assert bool(readiness.loc["AAA", "fundamentals_ready"]) is False
    assert "manual fundamentals import workflow" in readiness.loc["AAA", "next_action"]
    assert "missing fields: free_cash_flow" in readiness.loc["AAA", "next_action"]
    assert "make focus-fundamentals TICKER=AAA" in readiness.loc["AAA", "next_action"]
    assert int(peers.loc["AAA", "peer_count"]) == 2
    assert int(peers.loc["AAA", "ready_peer_count"]) == 2
    assert bool(peers.loc["AAA", "peer_price_ready"]) is True
    assert bool(peers.loc["AAA", "peer_momentum_ready"]) is True
    assert bool(peers.loc["AAA", "peer_fundamentals_ready"]) is False
    assert bool(peers.loc["AAA", "peer_valuation_ready"]) is False
    assert peers.loc["AAA", "peer_blocker_type"] == "peer_fundamentals_missing"
    assert "CCC" in peers.loc["AAA", "peer_missing_fundamentals_tickers"]
    assert bool(peers.loc["AAA", "peer_trend_comparison_ready"]) is True
    assert bool(peers.loc["AAA", "peer_valuation_comparison_ready"]) is False
    assert "fundamentals" in peers.loc["AAA", "next_peer_action"].lower()
    assert bool(peers.loc["AAA", "peer_ready"]) is True
    assert bool(readiness.loc["AAA", "peer_ready"]) is True
