from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd

from src.providers.local_schemas import LOCAL_DATASET_SCHEMAS, normalize_columns, validate_local_dataset


SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}
MIN_SEC_TICKER_MAP_ROWS = 100
MIN_SEC_COMPANYFACTS_CACHE_BYTES = 100_000


class SECUserAgentError(ValueError):
    pass


@dataclass(frozen=True)
class SecFactRecord:
    taxonomy: str
    concept: str
    unit: str
    value: float | int | str | None
    end: str | None
    start: str | None
    filed: str | None
    form: str | None
    accession: str | None
    fy: int | None
    fp: str | None


def _require_user_agent(user_agent: str | None = None) -> str:
    resolved = (user_agent or os.getenv("SEC_USER_AGENT", "")).strip()
    if not resolved:
        raise SECUserAgentError(
            "SEC requests require an identifying User-Agent. Pass --sec-user-agent "
            "or set SEC_USER_AGENT in the environment."
        )
    return resolved


def _cache_path(cache_dir: Path, name: str) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / name


def _companyfacts_cache_path(cache_dir: Path, cik: str) -> Path:
    path = cache_dir / "companyfacts"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"CIK{cik}.json"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _payload_row_count(payload: Any) -> int:
    if isinstance(payload, dict):
        return len(payload)
    if isinstance(payload, list):
        return len(payload)
    return 0


def _fetch_json(url: str, user_agent: str, sleep_seconds: float = 0.2) -> Any:
    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"SEC request failed with HTTP {exc.code} for {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"SEC request failed for {url}: {exc.reason}") from exc
    time.sleep(max(0.0, sleep_seconds))
    return payload


def load_sec_ticker_map(
    cache_dir: str | Path = "data/cache/sec",
    user_agent: str | None = None,
    refresh: bool = False,
    sleep_seconds: float = 0.2,
    fetcher: Callable[[str, str, float], Any] | None = None,
) -> dict[str, dict[str, Any]]:
    cache_path = _cache_path(Path(cache_dir), "company_tickers.json")
    if cache_path.exists() and not refresh:
        payload = _read_json(cache_path)
        if fetcher is None and _payload_row_count(payload) < MIN_SEC_TICKER_MAP_ROWS:
            resolved_user_agent = _require_user_agent(user_agent)
            payload = _fetch_json(SEC_TICKER_MAP_URL, resolved_user_agent, sleep_seconds)
            _write_json(cache_path, payload)
    else:
        resolved_user_agent = _require_user_agent(user_agent)
        payload = (fetcher or _fetch_json)(SEC_TICKER_MAP_URL, resolved_user_agent, sleep_seconds)
        _write_json(cache_path, payload)

    rows: Iterable[dict[str, Any]]
    if isinstance(payload, dict) and all(isinstance(value, dict) for value in payload.values()):
        rows = payload.values()
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []

    ticker_map: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = str(row.get("ticker", "")).upper().strip()
        if not ticker:
            continue
        cik_value = row.get("cik_str") or row.get("cik") or row.get("cikStr")
        if cik_value in (None, ""):
            continue
        cik = str(int(cik_value)).zfill(10) if str(cik_value).strip().isdigit() else str(cik_value).zfill(10)
        ticker_map[ticker] = {
            "ticker": ticker,
            "cik": cik,
            "title": row.get("title") or row.get("name"),
            "exchange": row.get("exchange"),
        }
    return ticker_map


def resolve_ticker_to_cik(ticker: str, ticker_map: dict[str, dict[str, Any]]) -> str | None:
    return ticker_map.get(ticker.upper().strip(), {}).get("cik")


def fetch_companyfacts(
    cik: str,
    user_agent: str | None,
    cache: bool = True,
    refresh: bool = False,
    cache_dir: str | Path = "data/cache/sec",
    sleep_seconds: float = 0.2,
    fetcher: Callable[[str, str, float], Any] | None = None,
) -> dict[str, Any]:
    resolved_user_agent = _require_user_agent(user_agent)
    normalized_cik = str(cik).zfill(10)
    cache_root = Path(cache_dir)
    cache_path = _companyfacts_cache_path(cache_root, normalized_cik)
    if cache and cache_path.exists() and not refresh:
        if fetcher is not None or cache_path.stat().st_size >= MIN_SEC_COMPANYFACTS_CACHE_BYTES:
            return _read_json(cache_path)
    payload = (fetcher or _fetch_json)(
        SEC_COMPANYFACTS_URL.format(cik=normalized_cik),
        resolved_user_agent,
        sleep_seconds,
    )
    if cache:
        _write_json(cache_path, payload)
    return payload


def _extract_records(companyfacts_json: dict[str, Any], taxonomy: str, concept: str) -> list[SecFactRecord]:
    facts_root = companyfacts_json.get("facts", {}).get(taxonomy, {}).get(concept, {})
    units = facts_root.get("units", {})
    records: list[SecFactRecord] = []
    for unit_name, items in units.items():
        for item in items:
            records.append(
                SecFactRecord(
                    taxonomy=taxonomy,
                    concept=concept,
                    unit=unit_name,
                    value=item.get("val"),
                    end=item.get("end"),
                    start=item.get("start"),
                    filed=item.get("filed"),
                    form=item.get("form"),
                    accession=item.get("accn"),
                    fy=item.get("fy"),
                    fp=item.get("fp"),
                )
            )
    return records


def _concept_records(companyfacts_json: dict[str, Any], concepts: list[tuple[str, str]]) -> list[SecFactRecord]:
    records: list[SecFactRecord] = []
    for taxonomy, concept in concepts:
        records.extend(_extract_records(companyfacts_json, taxonomy, concept))
    return records


def _safe_timestamp(value: str | None) -> pd.Timestamp | None:
    if not value:
        return None
    timestamp = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(timestamp) else timestamp


def _fact_sort_key(record: SecFactRecord) -> tuple[pd.Timestamp, pd.Timestamp, int]:
    end = _safe_timestamp(record.end) or pd.Timestamp.min
    filed = _safe_timestamp(record.filed) or pd.Timestamp.min
    annual_priority = 1 if record.form in SEC_ANNUAL_FORMS else 0
    return end, filed, annual_priority


def _is_annual_record(record: SecFactRecord) -> bool:
    if record.form in SEC_ANNUAL_FORMS and (record.fp == "FY" or record.fy is not None):
        return True
    start = _safe_timestamp(record.start)
    end = _safe_timestamp(record.end)
    if start is not None and end is not None:
        return (end - start).days >= 300
    return False


def _numeric_record_value(record: SecFactRecord) -> float | None:
    try:
        value = pd.to_numeric(record.value, errors="coerce")
    except Exception:
        return None
    return None if pd.isna(value) else float(value)


def _latest_record(companyfacts_json: dict[str, Any], concepts: list[tuple[str, str]], *, annual_only: bool = False) -> SecFactRecord | None:
    records = _concept_records(companyfacts_json, concepts)
    if annual_only:
        records = [record for record in records if _is_annual_record(record)]
    numeric_records = [record for record in records if _numeric_record_value(record) is not None]
    if not numeric_records:
        return None
    return sorted(numeric_records, key=_fact_sort_key, reverse=True)[0]


def _annual_series(companyfacts_json: dict[str, Any], concepts: list[tuple[str, str]]) -> list[SecFactRecord]:
    records = [record for record in _concept_records(companyfacts_json, concepts) if _is_annual_record(record)]
    records = [record for record in records if _numeric_record_value(record) is not None and record.end]
    if not records:
        return []
    by_period: dict[str, SecFactRecord] = {}
    for record in sorted(records, key=_fact_sort_key, reverse=True):
        period_key = str(record.end)
        if period_key not in by_period:
            by_period[period_key] = record
    return sorted(by_period.values(), key=lambda record: _safe_timestamp(record.end) or pd.Timestamp.min, reverse=True)


def _sum_latest_records(companyfacts_json: dict[str, Any], concept_groups: list[list[tuple[str, str]]]) -> tuple[float | None, list[SecFactRecord]]:
    selected_records: list[SecFactRecord] = []
    total = 0.0
    found = False
    for concepts in concept_groups:
        record = _latest_record(companyfacts_json, concepts, annual_only=False)
        if record is None:
            continue
        numeric_value = _numeric_record_value(record)
        if numeric_value is None:
            continue
        total += numeric_value
        selected_records.append(record)
        found = True
    return (total if found else None), selected_records


def _metadata_from_record(record: SecFactRecord | None) -> dict[str, str | None]:
    if record is None:
        return {
            "sec_form": None,
            "sec_filed_date": None,
            "sec_accession": None,
            "as_of_date": None,
        }
    return {
        "sec_form": record.form,
        "sec_filed_date": record.filed,
        "sec_accession": record.accession,
        "as_of_date": record.end,
    }


def extract_fundamentals_from_companyfacts(companyfacts_json: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    revenue_concepts = [
        ("us-gaap", "Revenues"),
        ("us-gaap", "SalesRevenueNet"),
        ("us-gaap", "SalesRevenueGoodsNet"),
    ]
    net_income_concepts = [("us-gaap", "NetIncomeLoss")]
    eps_concepts = [
        ("us-gaap", "EarningsPerShareDiluted"),
        ("us-gaap", "EarningsPerShareBasic"),
    ]
    operating_cash_flow_concepts = [
        ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
        ("us-gaap", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
    ]
    capex_concepts = [
        ("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"),
        ("us-gaap", "PaymentsToAcquireProductiveAssets"),
    ]
    cash_concepts = [
        ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
        ("us-gaap", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
    ]
    shares_concepts = [("dei", "EntityCommonStockSharesOutstanding")]
    operating_income_concepts = [("us-gaap", "OperatingIncomeLoss")]
    ebitda_concepts = [("us-gaap", "EarningsBeforeInterestTaxesDepreciationAndAmortization")]
    debt_component_groups = [
        [("us-gaap", "ShortTermBorrowings")],
        [("us-gaap", "LongTermDebtCurrent")],
        [("us-gaap", "LongTermDebtNoncurrent")],
        [("us-gaap", "LongTermDebtAndFinanceLeaseObligationsCurrent")],
        [("us-gaap", "LongTermDebtAndFinanceLeaseObligationsNoncurrent")],
    ]
    total_debt_concepts = [
        ("us-gaap", "LongTermDebtAndCapitalLeaseObligations"),
        ("us-gaap", "LongTermDebt"),
        ("us-gaap", "DebtInstrumentCarryingAmount"),
    ]

    revenue_record = _latest_record(companyfacts_json, revenue_concepts, annual_only=True)
    net_income_record = _latest_record(companyfacts_json, net_income_concepts, annual_only=True)
    eps_record = _latest_record(companyfacts_json, eps_concepts, annual_only=True)
    ocf_record = _latest_record(companyfacts_json, operating_cash_flow_concepts, annual_only=True)
    capex_record = _latest_record(companyfacts_json, capex_concepts, annual_only=True)
    operating_income_record = _latest_record(companyfacts_json, operating_income_concepts, annual_only=True)
    cash_record = _latest_record(companyfacts_json, cash_concepts, annual_only=False)
    shares_record = _latest_record(companyfacts_json, shares_concepts, annual_only=False)
    ebitda_record = _latest_record(companyfacts_json, ebitda_concepts, annual_only=True)

    debt_value, debt_records = _sum_latest_records(companyfacts_json, debt_component_groups)
    if debt_value is None:
        total_debt_record = _latest_record(companyfacts_json, total_debt_concepts, annual_only=False)
        if total_debt_record is not None:
            debt_value = _numeric_record_value(total_debt_record)
            debt_records = [total_debt_record]

    revenue = _numeric_record_value(revenue_record)
    net_income = _numeric_record_value(net_income_record)
    eps = _numeric_record_value(eps_record)
    operating_cash_flow = _numeric_record_value(ocf_record)
    capex = _numeric_record_value(capex_record)
    free_cash_flow = None
    if operating_cash_flow is not None and capex is not None:
        free_cash_flow = operating_cash_flow - abs(capex)
    elif operating_cash_flow is not None or capex is not None:
        warnings.append("Free cash flow could not be calculated because operating cash flow or capex was incomplete.")

    operating_income = _numeric_record_value(operating_income_record)
    cash = _numeric_record_value(cash_record)
    shares_outstanding = _numeric_record_value(shares_record)
    ebitda = _numeric_record_value(ebitda_record)
    if ebitda is None:
        warnings.append("EBITDA was not staged because no direct SEC EBITDA fact was available.")

    revenue_growth = None
    revenue_series = _annual_series(companyfacts_json, revenue_concepts)
    if len(revenue_series) >= 2:
        latest_revenue = _numeric_record_value(revenue_series[0])
        prior_revenue = _numeric_record_value(revenue_series[1])
        if latest_revenue is not None and prior_revenue not in (None, 0):
            revenue_growth = (latest_revenue - prior_revenue) / abs(prior_revenue)

    profit_margin = None
    if revenue not in (None, 0) and net_income is not None:
        profit_margin = net_income / revenue

    operating_margin = None
    if revenue not in (None, 0) and operating_income is not None:
        operating_margin = operating_income / revenue

    fcf_margin = None
    if revenue not in (None, 0) and free_cash_flow is not None:
        fcf_margin = free_cash_flow / revenue

    primary_record = revenue_record or net_income_record or ocf_record or cash_record or shares_record
    metadata = _metadata_from_record(primary_record)

    if revenue is None:
        warnings.append("Revenue was unavailable from annual SEC Companyfacts.")
    if eps is None:
        warnings.append("EPS was unavailable from annual SEC Companyfacts.")
    if shares_outstanding is None:
        warnings.append("Shares outstanding was unavailable from SEC Companyfacts.")
    if cash is None:
        warnings.append("Cash was unavailable from SEC Companyfacts.")
    if debt_value is None:
        warnings.append("Debt was unavailable from SEC Companyfacts.")

    row = {
        "revenue": revenue,
        "revenue_growth": revenue_growth,
        "eps": eps,
        "free_cash_flow": free_cash_flow,
        "fcf_margin": fcf_margin,
        "profit_margin": profit_margin,
        "operating_margin": operating_margin,
        "ebitda": ebitda,
        "cash": cash,
        "debt": debt_value,
        "shares_outstanding": shares_outstanding,
        "source": "sec_companyfacts",
        "as_of_date": metadata["as_of_date"],
        "sec_cik": str(companyfacts_json.get("cik", "")).zfill(10) if companyfacts_json.get("cik") is not None else None,
        "sec_form": metadata["sec_form"],
        "sec_filed_date": metadata["sec_filed_date"],
        "sec_accession": metadata["sec_accession"],
        "sec_fact_warnings": " | ".join(sorted(set(warnings))) if warnings else None,
        "sec_entity_name": companyfacts_json.get("entityName"),
        "_warnings": sorted(set(warnings)),
    }
    return row


def build_sec_fundamentals_rows(
    tickers: Iterable[str],
    *,
    user_agent: str | None,
    cache_dir: str | Path = "data/cache/sec",
    refresh: bool = False,
    sleep_seconds: float = 0.2,
    ticker_map: dict[str, dict[str, Any]] | None = None,
    ticker_map_fetcher: Callable[[str, str, float], Any] | None = None,
    companyfacts_fetcher: Callable[[str, str, float], Any] | None = None,
) -> dict[str, Any]:
    requested_tickers = sorted({ticker.upper().strip() for ticker in tickers if ticker and ticker.strip()})
    if not requested_tickers:
        return {
            "requested_tickers": [],
            "resolved_tickers": [],
            "unresolved_tickers": [],
            "rows": [],
            "warnings": ["No tickers were provided for SEC staging."],
        }

    resolved_user_agent = _require_user_agent(user_agent)
    sec_ticker_map = ticker_map or load_sec_ticker_map(
        cache_dir=cache_dir,
        user_agent=resolved_user_agent,
        refresh=refresh,
        sleep_seconds=sleep_seconds,
        fetcher=ticker_map_fetcher,
    )

    rows: list[dict[str, Any]] = []
    unresolved_tickers: list[str] = []
    warnings: list[str] = []
    row_summaries: list[dict[str, Any]] = []
    for ticker in requested_tickers:
        cik = resolve_ticker_to_cik(ticker, sec_ticker_map)
        if cik is None:
            unresolved_tickers.append(ticker)
            warnings.append(f"{ticker}: no SEC CIK mapping was found.")
            continue
        try:
            companyfacts = fetch_companyfacts(
                cik,
                resolved_user_agent,
                cache=True,
                refresh=refresh,
                cache_dir=cache_dir,
                sleep_seconds=sleep_seconds,
                fetcher=companyfacts_fetcher,
            )
        except RuntimeError as exc:
            unresolved_tickers.append(ticker)
            warnings.append(f"{ticker}: {exc}")
            continue
        extracted = extract_fundamentals_from_companyfacts(companyfacts)
        extracted["ticker"] = ticker
        extracted["source"] = "sec_companyfacts"
        rows.append({key: value for key, value in extracted.items() if not key.startswith("_")})
        populated_fields = sorted(key for key, value in extracted.items() if key not in {"ticker", "source", "_warnings"} and value not in (None, ""))
        missing_fields = sorted(key for key, value in extracted.items() if key not in {"ticker", "source", "_warnings"} and value in (None, ""))
        row_summaries.append(
            {
                "ticker": ticker,
                "sec_cik": cik,
                "populated_fields": populated_fields,
                "missing_fields": missing_fields,
                "warnings": list(extracted.get("_warnings", [])),
            }
        )

    return {
        "requested_tickers": requested_tickers,
        "resolved_tickers": [row["ticker"] for row in rows],
        "unresolved_tickers": unresolved_tickers,
        "rows": rows,
        "row_summaries": row_summaries,
        "warnings": sorted(set(warnings)),
    }


def write_sec_fundamentals_import(
    rows: list[dict[str, Any]],
    output_path: str | Path = "data/imports/fundamentals.csv",
    overwrite: bool = False,
) -> dict[str, Any]:
    output = Path(output_path)
    if output.name != "fundamentals.csv" or output.parent.name != "imports":
        raise ValueError("SEC fundamentals staging may only write to a fundamentals.csv file inside a data/imports directory.")

    canonical_like = output.parent.parent / "fundamentals.csv"
    if output.resolve() == canonical_like.resolve():
        raise ValueError("SEC fundamentals staging must not write directly to canonical data/fundamentals.csv.")

    schema = LOCAL_DATASET_SCHEMAS["fundamentals"]
    columns = list(schema.required_columns)
    for column in schema.optional_columns:
        if column not in columns:
            columns.append(column)

    frame = pd.DataFrame(rows)
    if frame.empty:
        output.parent.mkdir(parents=True, exist_ok=True)
        if overwrite or not output.exists():
            pd.DataFrame(columns=columns).to_csv(output, index=False)
        return {
            "output_path": str(output),
            "rows_written": 0,
            "status": "no_rows",
            "tickers_written": [],
        }

    frame.columns = normalize_columns(list(frame.columns))
    for column in columns:
        if column not in frame.columns:
            frame[column] = pd.NA
    frame = frame[columns].copy()
    frame["ticker"] = frame["ticker"].astype("string").str.upper().str.strip()
    frame = frame.dropna(subset=["ticker"])
    frame = frame.drop_duplicates(subset=["ticker"], keep="last")

    output.parent.mkdir(parents=True, exist_ok=True)
    merged = frame
    if output.exists() and not overwrite:
        existing_validation, existing_frame = validate_local_dataset("fundamentals", output)
        if existing_validation.status == "invalid":
            raise ValueError("Existing staged fundamentals.csv is invalid. Fix or remove it before SEC staging.")
        existing = existing_frame.copy() if existing_frame is not None else pd.DataFrame(columns=columns)
        for column in columns:
            if column not in existing.columns:
                existing[column] = pd.NA
        existing = existing[columns].copy()
        existing["ticker"] = existing["ticker"].astype("string").str.upper().str.strip()
        existing = existing.dropna(subset=["ticker"])
        existing = existing.drop_duplicates(subset=["ticker"], keep="last")
        existing = existing.set_index("ticker", drop=False)
        incoming = frame.set_index("ticker", drop=False)
        overlap = existing.index.intersection(incoming.index)
        if not overlap.empty:
            update_columns = [column for column in columns if column != "ticker"]
            for column in update_columns:
                existing[column] = existing[column].astype("object")
                existing.loc[overlap, column] = incoming.loc[overlap, column].astype("object")
        new_rows = incoming.loc[~incoming.index.isin(existing.index)]
        merged = pd.concat([existing, new_rows], axis=0).reset_index(drop=True)[columns]

    merged.to_csv(output, index=False)
    return {
        "output_path": str(output),
        "rows_written": int(len(frame)),
        "staged_row_count": int(len(merged)),
        "status": "written",
        "tickers_written": sorted(frame["ticker"].dropna().astype(str).tolist()),
        "overwrite": overwrite,
    }
