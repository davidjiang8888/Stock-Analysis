from pathlib import Path

import pandas as pd

from src.config import AppConfig
from src.dcf_readiness import build_dcf_readiness_frame, build_dcf_readiness_report
from src.manual_fundamentals_import import import_staged_fundamentals
from src.value_engine import classify_value_row


def test_dcf_readiness_reports_missing_fields_and_ready_company():
    universe = pd.DataFrame(
        [
            {"ticker": "NVDA", "default_purpose": "Momentum Leader", "market_cap_bucket": "Large"},
            {"ticker": "AMD", "default_purpose": "Momentum Leader", "market_cap_bucket": "Large"},
        ]
    )
    fundamentals = pd.DataFrame(
        [
            {"ticker": "NVDA", "revenue": 100, "free_cash_flow": 20, "fcf_margin": 0.2, "shares_outstanding": 10},
            {"ticker": "AMD", "revenue": 80, "free_cash_flow": 10},
        ]
    )
    prices = pd.DataFrame([{"ticker": "NVDA", "date": "2026-01-01", "close": 100}])

    frame = build_dcf_readiness_frame(universe=universe, fundamentals=fundamentals, prices=prices)
    by_ticker = frame.set_index("ticker")

    assert bool(by_ticker.loc["NVDA", "is_dcf_ready"]) is True
    assert bool(by_ticker.loc["AMD", "is_dcf_ready"]) is False
    assert by_ticker.loc["AMD", "missing_dcf_fields"] == "shares_outstanding, price"
    assert "missing shares_outstanding, price" in by_ticker.loc["AMD", "reason_not_ready"]


def test_dcf_readiness_excludes_etfs_from_operating_company_dcf():
    universe = pd.DataFrame([{"ticker": "QQQ", "default_purpose": "ETF / Defensive / Hedge", "market_cap_bucket": "ETF"}])
    frame = build_dcf_readiness_frame(universe=universe, fundamentals=pd.DataFrame(), prices=pd.DataFrame())

    row = frame.iloc[0]
    assert row["asset_type"] == "etf"
    assert bool(row["is_dcf_ready"]) is False
    assert "excluded" in row["reason_not_ready"]


def test_dcf_readiness_does_not_treat_sector_etf_notes_as_etf():
    universe = pd.DataFrame(
        [
            {
                "ticker": "A",
                "default_purpose": "Core Compounder",
                "notes": "Theme and sector ETF metadata were not provided by the constituent source.",
                "is_etf": False,
            }
        ]
    )

    frame = build_dcf_readiness_frame(universe=universe, fundamentals=pd.DataFrame(), prices=pd.DataFrame())

    row = frame.iloc[0]
    assert row["asset_type"] == "company"
    assert "missing" in row["reason_not_ready"]


def test_manual_fundamentals_import_validates_and_stages_rows(tmp_path: Path):
    data_dir = tmp_path / "data"
    staged_dir = data_dir / "staged" / "fundamentals"
    staged_dir.mkdir(parents=True)
    pd.DataFrame({"ticker": ["NVDA", "AMD"]}).to_csv(data_dir / "universe.csv", index=False)
    (staged_dir / "fundamentals_manual.csv").write_text(
        "ticker,period,revenue,net_income,free_cash_flow,shares_outstanding,source,updated_at\n"
        "NVDA,FY2026,100,30,25,10,manual_10k,2026-05-01\n"
        "AMD,FY2026,not-number,10,5,8,manual_10k,2026-05-01\n"
        "META,FY2026,100,20,10,9,manual_10k,2026-05-01\n"
        "AMD,FY2026,100,20,10,9,,2026-05-01\n",
        encoding="utf-8",
    )

    result = import_staged_fundamentals(tmp_path)
    staged = pd.read_csv(data_dir / "imports" / "fundamentals.csv")
    rejected = pd.read_csv(data_dir / "fundamentals_import_rejected.csv")

    assert result.status == "imported"
    assert result.rows_valid == 1
    assert staged.iloc[0]["ticker"] == "NVDA"
    assert "source" in staged.columns
    assert set(rejected["rejection_reason"]) == {"revenue_not_numeric", "ticker_not_in_universe", "missing_source"}


def test_dcf_readiness_report_writes_data_file(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame([{"ticker": "NVDA", "default_purpose": "Momentum Leader", "market_cap_bucket": "Large"}]).to_csv(
        data_dir / "universe.csv", index=False
    )
    pd.DataFrame([{"ticker": "NVDA", "revenue": 100, "free_cash_flow": 20, "fcf_margin": 0.2, "shares_outstanding": 10}]).to_csv(
        data_dir / "fundamentals.csv", index=False
    )
    pd.DataFrame([{"ticker": "NVDA", "date": "2026-01-01", "close": 100}]).to_csv(data_dir / "prices.csv", index=False)

    frame = build_dcf_readiness_report(tmp_path)

    assert (data_dir / "dcf_readiness.csv").exists()
    assert bool(frame.iloc[0]["is_dcf_ready"]) is True


def test_value_engine_marks_missing_dcf_inputs_not_ready_without_fake_positive_valuation():
    config = AppConfig.load(Path("config.yaml"))
    snapshot_row = pd.Series(
        {
            "ticker": "NVDA",
            "close": 120.0,
            "sma_50": 115.0,
            "sma_200": 100.0,
            "ema_21": 118.0,
            "relative_return_vs_spy": 0.03,
            "relative_return_vs_qqq": 0.02,
            "relative_return_vs_sector_etf": 0.01,
            "return_3m": 0.05,
        }
    )
    purpose_row = pd.Series({"FinalPrimaryPurpose": "Re-rating / Undervalued"})
    fundamentals_row = pd.Series(
        {
            "revenue_growth": 0.08,
            "eps_growth": 0.10,
            "fcf_margin": 0.15,
            "gross_margin": 0.55,
            "operating_margin": 0.22,
            "debt_to_equity": 0.4,
            "pe": 16.0,
            "forward_pe": 14.0,
            "ev_to_sales": 4.0,
            "ev_to_ebitda": 10.0,
            "price_to_fcf": 18.0,
            "fcf_yield": 0.04,
        }
    )

    result = classify_value_row(snapshot_row, purpose_row, fundamentals_row, config)

    assert result["ValuationStatus"] == "not_ready"
    assert result["FinalValueCategory"] == "Insufficient Data"
    assert "shares_outstanding" in result["MissingDataFields"]
    assert "valuation_status=not_ready" in result["Reason"]
