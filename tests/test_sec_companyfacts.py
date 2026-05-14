import json
import os
import sys
from pathlib import Path

import pytest

from src.providers.local_importer import preview_import_merge, validate_imports
from src.providers.sec_companyfacts import (
    SECUserAgentError,
    build_sec_fundamentals_rows,
    extract_fundamentals_from_companyfacts,
    fetch_companyfacts,
    load_sec_ticker_map,
    resolve_ticker_to_cik,
    write_sec_fundamentals_import,
)
from src.stock_report import main


def _sample_ticker_map_payload():
    return {
        "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
        "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
    }


def _sample_companyfacts_payload():
    return {
        "cik": 1045810,
        "entityName": "NVIDIA CORP",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "val": 1000,
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2026-02-20",
                                "accn": "0001045810-26-000001",
                            },
                            {
                                "val": 800,
                                "start": "2024-01-01",
                                "end": "2024-12-31",
                                "fy": 2024,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2025-02-20",
                                "accn": "0001045810-25-000001",
                            },
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "val": 200,
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2026-02-20",
                                "accn": "0001045810-26-000001",
                            }
                        ]
                    }
                },
                "EarningsPerShareDiluted": {
                    "units": {
                        "USD/shares": [
                            {
                                "val": 5,
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2026-02-20",
                                "accn": "0001045810-26-000001",
                            }
                        ]
                    }
                },
                "NetCashProvidedByUsedInOperatingActivities": {
                    "units": {
                        "USD": [
                            {
                                "val": 250,
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2026-02-20",
                                "accn": "0001045810-26-000001",
                            }
                        ]
                    }
                },
                "PaymentsToAcquirePropertyPlantAndEquipment": {
                    "units": {
                        "USD": [
                            {
                                "val": 50,
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2026-02-20",
                                "accn": "0001045810-26-000001",
                            }
                        ]
                    }
                },
                "OperatingIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "val": 250,
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2026-02-20",
                                "accn": "0001045810-26-000001",
                            }
                        ]
                    }
                },
                "CashAndCashEquivalentsAtCarryingValue": {
                    "units": {
                        "USD": [
                            {
                                "val": 300,
                                "end": "2025-12-31",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2026-02-20",
                                "accn": "0001045810-26-000001",
                            }
                        ]
                    }
                },
                "ShortTermBorrowings": {
                    "units": {
                        "USD": [
                            {
                                "val": 30,
                                "end": "2025-12-31",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2026-02-20",
                                "accn": "0001045810-26-000001",
                            }
                        ]
                    }
                },
                "LongTermDebtCurrent": {
                    "units": {
                        "USD": [
                            {
                                "val": 20,
                                "end": "2025-12-31",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2026-02-20",
                                "accn": "0001045810-26-000001",
                            }
                        ]
                    }
                },
                "LongTermDebtNoncurrent": {
                    "units": {
                        "USD": [
                            {
                                "val": 100,
                                "end": "2025-12-31",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2026-02-20",
                                "accn": "0001045810-26-000001",
                            }
                        ]
                    }
                },
            },
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            {
                                "val": 100,
                                "end": "2025-12-31",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2026-02-20",
                                "accn": "0001045810-26-000001",
                            }
                        ]
                    }
                }
            },
        },
    }


def test_resolve_ticker_to_cik():
    ticker_map = load_sec_ticker_map(fetcher=lambda *_: _sample_ticker_map_payload(), user_agent="Test test@example.com", refresh=True)

    assert resolve_ticker_to_cik("NVDA", ticker_map) == "0001045810"
    assert resolve_ticker_to_cik("MISSING", ticker_map) is None


def test_extract_fundamentals_from_companyfacts_maps_supported_fields():
    row = extract_fundamentals_from_companyfacts(_sample_companyfacts_payload())

    assert row["revenue"] == 1000
    assert row["revenue_growth"] == pytest.approx(0.25)
    assert row["eps"] == 5
    assert row["free_cash_flow"] == 200
    assert row["fcf_margin"] == pytest.approx(0.2)
    assert row["profit_margin"] == pytest.approx(0.2)
    assert row["operating_margin"] == pytest.approx(0.25)
    assert row["cash"] == 300
    assert row["debt"] == 150
    assert row["shares_outstanding"] == 100
    assert row["sec_form"] == "10-K"
    assert row["as_of_date"] == "2025-12-31"
    assert any("EBITDA" in warning for warning in row["_warnings"])


def test_extract_fundamentals_warns_when_missing_facts():
    payload = {"cik": 1, "entityName": "Test", "facts": {"us-gaap": {"Revenues": {"units": {"USD": [{"val": 10, "end": "2025-12-31", "start": "2025-01-01", "fp": "FY", "fy": 2025, "form": "10-K", "filed": "2026-02-20", "accn": "1"}]}}}}}

    row = extract_fundamentals_from_companyfacts(payload)

    assert row["eps"] is None
    assert row["free_cash_flow"] is None
    assert any("EPS was unavailable" in warning for warning in row["_warnings"])
    assert any("Debt was unavailable" in warning for warning in row["_warnings"])


def test_missing_sec_user_agent_fails_clearly(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    with pytest.raises(SECUserAgentError):
        build_sec_fundamentals_rows(["NVDA"], user_agent=None, ticker_map=_sample_ticker_map_payload())


def test_cache_behavior_avoids_refetch(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    ticker_cache = cache_dir / "company_tickers.json"
    ticker_cache.parent.mkdir(parents=True, exist_ok=True)
    ticker_cache.write_text(json.dumps(_sample_ticker_map_payload()), encoding="utf-8")

    def should_not_fetch(*_args, **_kwargs):
        raise AssertionError("fetcher should not be called when cache exists")

    ticker_map = load_sec_ticker_map(cache_dir=cache_dir, user_agent="Test test@example.com", fetcher=should_not_fetch)
    assert ticker_map["NVDA"]["cik"] == "0001045810"

    companyfacts_cache = cache_dir / "companyfacts" / "CIK0001045810.json"
    companyfacts_cache.parent.mkdir(parents=True, exist_ok=True)
    companyfacts_cache.write_text(json.dumps(_sample_companyfacts_payload()), encoding="utf-8")

    payload = fetch_companyfacts("0001045810", "Test test@example.com", cache_dir=cache_dir, fetcher=should_not_fetch)
    assert payload["entityName"] == "NVIDIA CORP"


def test_build_sec_fundamentals_rows_and_write_import_file(tmp_path: Path):
    result = build_sec_fundamentals_rows(
        ["NVDA"],
        user_agent="Test test@example.com",
        ticker_map={"NVDA": {"ticker": "NVDA", "cik": "0001045810"}},
        companyfacts_fetcher=lambda *_: _sample_companyfacts_payload(),
    )
    output_path = tmp_path / "data" / "imports" / "fundamentals.csv"
    write_result = write_sec_fundamentals_import(result["rows"], output_path=output_path)

    assert result["resolved_tickers"] == ["NVDA"]
    assert write_result["status"] == "written"
    assert output_path.exists()

    validation = validate_imports(base_dir=tmp_path)
    preview = preview_import_merge(base_dir=tmp_path)
    assert validation["status"] in {"valid", "valid_with_warnings"}
    assert preview["preview"][0]["new_rows"] == 1


def test_write_sec_fundamentals_import_refuses_canonical_data_path(tmp_path: Path):
    with pytest.raises(ValueError):
        write_sec_fundamentals_import(
            [{"ticker": "NVDA", "revenue": 1000, "source": "sec_companyfacts"}],
            output_path=tmp_path / "data" / "fundamentals.csv",
        )


def test_stock_report_cli_sec_stage_fundamentals_json(tmp_path: Path, monkeypatch, capsys):
    def fake_build(tickers, **_kwargs):
        return {
            "requested_tickers": tickers,
            "resolved_tickers": ["NVDA"],
            "unresolved_tickers": [],
            "rows": [{"ticker": "NVDA", "revenue": 1000, "source": "sec_companyfacts", "as_of_date": "2025-12-31"}],
            "row_summaries": [
                {"ticker": "NVDA", "sec_cik": "0001045810", "populated_fields": ["revenue"], "missing_fields": ["eps"], "warnings": []}
            ],
            "warnings": [],
        }

    monkeypatch.setattr("src.stock_report.build_sec_fundamentals_rows", fake_build)
    previous_cwd = Path.cwd()
    previous_argv = sys.argv[:]
    os.chdir(tmp_path)
    sys.argv = [
        "python",
        "--project-root",
        str(tmp_path),
        "--sec-stage-fundamentals",
        "--tickers",
        "NVDA",
        "--sec-user-agent",
        "Test test@example.com",
        "--json",
    ]
    try:
        main()
        payload = json.loads(capsys.readouterr().out)
        assert payload["resolved_tickers"] == ["NVDA"]
        assert payload["rows_written"] == 1
        assert (tmp_path / "data" / "imports" / "fundamentals.csv").exists()
    finally:
        sys.argv = previous_argv
        os.chdir(previous_cwd)
