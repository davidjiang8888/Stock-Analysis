from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from src.providers.market_data import make_source_metadata


@dataclass(frozen=True)
class LocalDatasetSchema:
    dataset_name: str
    required_columns: tuple[str, ...]
    optional_columns: tuple[str, ...]
    numeric_columns: tuple[str, ...] = ()
    date_columns: tuple[str, ...] = ()
    ticker_columns: tuple[str, ...] = ("ticker",)


LOCAL_DATASET_SCHEMAS: dict[str, LocalDatasetSchema] = {
    "prices": LocalDatasetSchema(
        dataset_name="prices",
        required_columns=("date", "ticker"),
        optional_columns=("adj_close", "adjusted_close", "close", "open", "high", "low", "volume", "source", "as_of_date", "notes"),
        numeric_columns=("adj_close", "adjusted_close", "close", "open", "high", "low", "volume"),
        date_columns=("date", "as_of_date"),
    ),
    "fundamentals": LocalDatasetSchema(
        dataset_name="fundamentals",
        required_columns=("ticker",),
        optional_columns=(
            "theme",
            "sector",
            "period",
            "revenue",
            "revenue_growth",
            "net_income",
            "eps",
            "free_cash_flow",
            "fcf",
            "fcf_margin",
            "profit_margin",
            "operating_margin",
            "gross_margin",
            "ebitda",
            "cash",
            "debt",
            "net_debt",
            "shares_outstanding",
            "pe_ratio",
            "trailing_pe",
            "forward_pe",
            "price_to_book",
            "market_cap",
            "enterprise_value",
            "debt_to_equity",
            "source",
            "as_of_date",
            "updated_at",
            "sec_cik",
            "sec_form",
            "sec_filed_date",
            "sec_accession",
            "sec_fact_warnings",
            "sec_entity_name",
        ),
        numeric_columns=(
            "revenue",
            "revenue_growth",
            "net_income",
            "eps",
            "free_cash_flow",
            "fcf",
            "fcf_margin",
            "profit_margin",
            "operating_margin",
            "gross_margin",
            "ebitda",
            "cash",
            "debt",
            "net_debt",
            "shares_outstanding",
            "pe_ratio",
            "trailing_pe",
            "forward_pe",
            "price_to_book",
            "market_cap",
            "enterprise_value",
            "debt_to_equity",
        ),
        date_columns=("as_of_date", "updated_at", "sec_filed_date"),
    ),
    "earnings": LocalDatasetSchema(
        dataset_name="earnings",
        required_columns=("ticker",),
        optional_columns=(
            "next_earnings_date",
            "last_earnings_date",
            "report_date",
            "fiscal_period",
            "eps_estimate",
            "eps_actual",
            "revenue_estimate",
            "revenue_actual",
            "surprise_pct",
            "source",
            "as_of_date",
            "updated_at",
        ),
        numeric_columns=("eps_estimate", "eps_actual", "revenue_estimate", "revenue_actual", "surprise_pct"),
        date_columns=("next_earnings_date", "last_earnings_date", "report_date", "as_of_date", "updated_at"),
    ),
    "analyst_estimates": LocalDatasetSchema(
        dataset_name="analyst_estimates",
        required_columns=("ticker",),
        optional_columns=(
            "period",
            "eps_estimate",
            "revenue_estimate",
            "current_quarter_eps",
            "next_quarter_eps",
            "current_year_eps",
            "next_year_eps",
            "current_quarter_revenue",
            "next_quarter_revenue",
            "current_year_revenue",
            "next_year_revenue",
            "price_target_mean",
            "price_target_high",
            "price_target_low",
            "target_mean_price",
            "target_high_price",
            "target_low_price",
            "rating_consensus",
            "recommendation",
            "revision_trend",
            "source",
            "as_of_date",
            "updated_at",
        ),
        numeric_columns=(
            "eps_estimate",
            "revenue_estimate",
            "current_quarter_eps",
            "next_quarter_eps",
            "current_year_eps",
            "next_year_eps",
            "current_quarter_revenue",
            "next_quarter_revenue",
            "current_year_revenue",
            "next_year_revenue",
            "price_target_mean",
            "price_target_high",
            "price_target_low",
            "target_mean_price",
            "target_high_price",
            "target_low_price",
        ),
        date_columns=("as_of_date", "updated_at"),
    ),
    "peers": LocalDatasetSchema(
        dataset_name="peers",
        required_columns=("ticker", "peer_ticker"),
        optional_columns=("peer_group", "sector", "industry", "source", "as_of_date"),
        date_columns=("as_of_date",),
        ticker_columns=("ticker", "peer_ticker"),
    ),
    "universe": LocalDatasetSchema(
        dataset_name="universe",
        required_columns=("ticker", "theme", "defaultpurpose", "marketcapbucket", "notes"),
        optional_columns=(
            "sectoretf",
            "sector_etf",
            "default_purpose",
            "market_cap_bucket",
            "company_name",
            "universe_source",
            "source_detail",
            "index_membership",
            "etf_membership",
            "exchange",
            "is_etf",
            "as_of_date",
            "in_local_sample",
            "in_sp500",
            "in_nasdaq",
            "in_smh",
            "in_holdings",
            "in_custom",
        ),
        date_columns=("as_of_date",),
    ),
    "custom_universe": LocalDatasetSchema(
        dataset_name="custom_universe",
        required_columns=("ticker",),
        optional_columns=("company_name", "theme", "sector", "sector_etf", "source", "notes"),
    ),
}


@dataclass
class LocalSchemaValidationResult:
    dataset_name: str
    file_path: str
    status: str
    row_count: int
    available_columns: list[str]
    missing_required_columns: list[str]
    available_optional_columns: list[str]
    unknown_columns: list[str]
    warnings: list[str]
    source: dict[str, Any]
    date_columns: list[str] = field(default_factory=list)
    ticker_columns: list[str] = field(default_factory=list)
    latest_data_timestamp: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_columns(columns: list[str]) -> list[str]:
    return [
        column.strip()
        .replace("%", "pct")
        .replace("/", "_")
        .replace(" ", "_")
        .replace("-", "_")
        .lower()
        for column in columns
    ]


ALIASED_DATASET_COLUMNS: dict[str, dict[str, str]] = {
    "universe": {
        "sector_etf": "sectoretf",
        "default_purpose": "defaultpurpose",
        "market_cap_bucket": "marketcapbucket",
    },
    "custom_universe": {
        "sectoretf": "sector_etf",
    },
}


def _freshness_source(path: Path, latest_timestamp: str | None, notes: list[str]) -> dict[str, Any]:
    freshness = f"local CSV through {latest_timestamp}" if latest_timestamp else "local CSV file"
    return make_source_metadata(
        provider=f"local:{path.name}",
        freshness=freshness,
        official=False,
        notes=notes,
        retrieved_at=pd.Timestamp(path.stat().st_mtime, unit="s", tz="UTC").isoformat() if path.exists() else pd.Timestamp.now(tz="UTC").isoformat(),
    ).to_dict()


def _coerce_date_column(frame: pd.DataFrame, column: str, warnings: list[str]) -> None:
    if column not in frame.columns:
        return
    original_non_null = frame[column].notna().sum()
    frame[column] = pd.to_datetime(frame[column], errors="coerce", format="mixed")
    parsed_non_null = frame[column].notna().sum()
    if parsed_non_null < original_non_null:
        warnings.append(f"{column}: {original_non_null - parsed_non_null} rows could not be parsed as dates.")


def _coerce_numeric_column(frame: pd.DataFrame, column: str, warnings: list[str]) -> None:
    if column not in frame.columns:
        return
    original_non_null = frame[column].notna().sum()
    frame[column] = pd.to_numeric(frame[column], errors="coerce")
    parsed_non_null = frame[column].notna().sum()
    if parsed_non_null < original_non_null:
        warnings.append(f"{column}: {original_non_null - parsed_non_null} rows could not be parsed as numeric values.")


def validate_local_dataset(dataset_name: str, file_path: Path | None) -> tuple[LocalSchemaValidationResult, pd.DataFrame | None]:
    schema = LOCAL_DATASET_SCHEMAS.get(dataset_name)
    if file_path is None or not file_path.exists():
        result = LocalSchemaValidationResult(
            dataset_name=dataset_name,
            file_path=str(file_path) if file_path is not None else "",
            status="missing_file",
            row_count=0,
            available_columns=[],
            missing_required_columns=list(schema.required_columns) if schema else [],
            available_optional_columns=[],
            unknown_columns=[],
            warnings=["Local CSV file is not present."],
            source=make_source_metadata(
                provider=f"local:{dataset_name}",
                freshness="missing file",
                official=False,
                notes=["Local CSV file is not present."],
            ).to_dict(),
        )
        return result, None

    frame = pd.read_csv(file_path)
    frame.columns = normalize_columns(list(frame.columns))
    if dataset_name in ALIASED_DATASET_COLUMNS:
        frame = frame.rename(columns=ALIASED_DATASET_COLUMNS[dataset_name])
    warnings: list[str] = []

    if schema is not None:
        for column in schema.ticker_columns:
            if column in frame.columns:
                frame[column] = frame[column].astype("string").str.upper().str.strip()
        for column in schema.date_columns:
            _coerce_date_column(frame, column, warnings)
        for column in schema.numeric_columns:
            _coerce_numeric_column(frame, column, warnings)

        missing_required = sorted(set(schema.required_columns) - set(frame.columns))
        available_optional = sorted(set(schema.optional_columns).intersection(frame.columns))
        unknown_columns = sorted(set(frame.columns) - set(schema.required_columns) - set(schema.optional_columns))
        if unknown_columns:
            warnings.append(f"Unknown columns detected: {', '.join(unknown_columns)}.")
        if "as_of_date" in schema.optional_columns and "as_of_date" not in frame.columns and dataset_name in {"fundamentals", "earnings", "analyst_estimates", "peers"}:
            warnings.append("as_of_date column is unavailable, so freshness is file-based only.")
        status = "valid"
        if missing_required:
            status = "invalid"
        elif warnings:
            status = "valid_with_warnings"
        latest_timestamp = None
        date_candidates = [column for column in schema.date_columns if column in frame.columns and frame[column].notna().any()]
        if date_candidates:
            latest_value = frame[date_candidates[0]].dropna().max()
            latest_timestamp = latest_value.isoformat() if hasattr(latest_value, "isoformat") else str(latest_value)

        result = LocalSchemaValidationResult(
            dataset_name=dataset_name,
            file_path=str(file_path),
            status=status,
            row_count=len(frame),
            available_columns=list(frame.columns),
            missing_required_columns=missing_required,
            available_optional_columns=available_optional,
            unknown_columns=unknown_columns,
            warnings=warnings,
            source=_freshness_source(file_path, latest_timestamp, ["Local CSV-backed research data."]),
            date_columns=[column for column in schema.date_columns if column in frame.columns],
            ticker_columns=[column for column in schema.ticker_columns if column in frame.columns],
            latest_data_timestamp=latest_timestamp,
        )
        return result, frame

    ticker_columns = [column for column in ("ticker", "symbol") if column in frame.columns]
    for column in ticker_columns:
        frame[column] = frame[column].astype("string").str.upper().str.strip()
    date_columns = [column for column in ("date", "as_of_date") if column in frame.columns]
    for column in date_columns:
        _coerce_date_column(frame, column, warnings)
    latest_timestamp = None
    if date_columns and frame[date_columns[0]].notna().any():
        latest_value = frame[date_columns[0]].dropna().max()
        latest_timestamp = latest_value.isoformat() if hasattr(latest_value, "isoformat") else str(latest_value)
    result = LocalSchemaValidationResult(
        dataset_name=dataset_name,
        file_path=str(file_path),
        status="valid_with_warnings" if warnings else "valid",
        row_count=len(frame),
        available_columns=list(frame.columns),
        missing_required_columns=[],
        available_optional_columns=[],
        unknown_columns=[],
        warnings=warnings,
        source=_freshness_source(file_path, latest_timestamp, ["Local CSV-backed research data."]),
        date_columns=date_columns,
        ticker_columns=ticker_columns,
        latest_data_timestamp=latest_timestamp,
    )
    return result, frame
