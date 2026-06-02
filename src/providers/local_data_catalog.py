from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from src.providers.local_schemas import LocalSchemaValidationResult, validate_local_dataset


DATASET_CANDIDATES: dict[str, tuple[str, ...]] = {
    "prices": ("data/prices.csv",),
    "fundamentals": ("data/fundamentals.csv",),
    "earnings": ("data/earnings.csv", "data/earnings_calendar.csv", "data/earnings_history.csv"),
    "analyst_estimates": ("data/analyst_estimates.csv", "data/estimates.csv"),
    "peers": ("data/peers.csv",),
    "holdings": ("data/holdings.csv",),
    "universe": ("data/universe.csv",),
    "universe_master": ("data/universe_master.csv",),
    "universe_active": ("data/universe_active.csv",),
    "custom_universe": ("data/custom_universe.csv",),
    "theme_map": ("data/theme_map.csv",),
    "purpose_classification": ("outputs/purpose_classification.csv",),
    "market_direction": ("outputs/market_direction.csv",),
    "momentum_leaders": ("outputs/momentum_leaders.csv",),
    "portfolio_review": ("outputs/portfolio_review.csv",),
    "undervalued_candidates": ("outputs/undervalued_candidates.csv",),
    "final_watchlist": ("outputs/final_watchlist.csv",),
    "research_decisions": ("outputs/research_decisions.csv", "data/outputs/research_decisions.csv"),
    "ticker_readiness": ("data/reports/ticker_readiness_report.csv",),
}


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


def _detect_date_column(columns: list[str]) -> str | None:
    for column in (
        "date",
        "as_of_date",
        "market_time",
        "reported_date",
        "report_date",
        "earnings_date",
        "last_earnings_date",
        "next_earnings_date",
        "timestamp",
    ):
        if column in columns:
            return column
    return None


def _detect_ticker_column(columns: list[str]) -> str | None:
    for column in ("ticker", "symbol"):
        if column in columns:
            return column
    return None


@dataclass
class LocalDatasetMetadata:
    name: str
    file_path: str
    row_count: int
    available_columns: list[str]
    date_column: str | None
    ticker_column: str | None
    latest_data_timestamp: str | None
    validation_status: str
    missing_required_columns: list[str]
    available_optional_columns: list[str]
    unknown_columns: list[str]
    validation_warnings: list[str]
    source: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LocalTickerDatasetCoverage:
    dataset_name: str
    file_path: str | None
    validation_status: str
    ticker_present: bool
    row_count_for_ticker: int
    latest_data_timestamp: str | None
    notes: list[str]
    available_columns: list[str] = field(default_factory=list)
    missing_required_columns: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LocalDataCatalog:
    def __init__(self, base_dir: Path | None = None, data_dir: Path | None = None, outputs_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent.parent
        self.data_dir = data_dir or (self.base_dir / "data")
        self.outputs_dir = outputs_dir or (self.base_dir / "outputs")
        self._path_cache: dict[str, Path | None] = {}
        self._frame_cache: dict[str, pd.DataFrame | None] = {}
        self._validation_cache: dict[str, LocalSchemaValidationResult] = {}

    def dataset_names(self) -> list[str]:
        return list(DATASET_CANDIDATES.keys())

    def resolve_path(self, dataset_name: str) -> Path | None:
        if dataset_name not in self._path_cache:
            path = None
            for candidate in DATASET_CANDIDATES.get(dataset_name, ()):
                candidate_path = self._candidate_path(candidate)
                if candidate_path.exists():
                    path = candidate_path
                    break
            self._path_cache[dataset_name] = path
        return self._path_cache[dataset_name]

    def _candidate_path(self, candidate: str) -> Path:
        candidate_path = Path(candidate)
        parts = candidate_path.parts
        if parts and parts[0] == "data":
            return self.data_dir.joinpath(*parts[1:])
        if parts and parts[0] == "outputs":
            return self.outputs_dir.joinpath(*parts[1:])
        return self.base_dir / candidate_path

    def load_dataframe(self, dataset_name: str) -> pd.DataFrame | None:
        if dataset_name in self._frame_cache:
            return self._frame_cache[dataset_name]

        path = self.resolve_path(dataset_name)
        validation, frame = validate_local_dataset(dataset_name, path)
        self._validation_cache[dataset_name] = validation
        self._frame_cache[dataset_name] = frame
        return frame

    def validation_result(self, dataset_name: str) -> LocalSchemaValidationResult:
        if dataset_name not in self._validation_cache:
            self.load_dataframe(dataset_name)
        if dataset_name not in self._validation_cache:
            path = self.resolve_path(dataset_name)
            validation, _ = validate_local_dataset(dataset_name, path)
            self._validation_cache[dataset_name] = validation
        return self._validation_cache[dataset_name]

    def dataset_metadata(self, dataset_name: str) -> LocalDatasetMetadata:
        path = self.resolve_path(dataset_name)
        validation = self.validation_result(dataset_name)
        frame = self._frame_cache.get(dataset_name)
        columns = validation.available_columns
        date_column = _detect_date_column(columns)
        ticker_column = _detect_ticker_column(columns)
        path_text = str(path) if path is not None else validation.file_path
        row_count = len(frame) if frame is not None else validation.row_count

        return LocalDatasetMetadata(
            name=dataset_name,
            file_path=path_text,
            row_count=row_count,
            available_columns=columns,
            date_column=date_column,
            ticker_column=ticker_column,
            latest_data_timestamp=validation.latest_data_timestamp,
            validation_status=validation.status,
            missing_required_columns=validation.missing_required_columns,
            available_optional_columns=validation.available_optional_columns,
            unknown_columns=validation.unknown_columns,
            validation_warnings=validation.warnings,
            source=validation.source,
        )

    def discover(self) -> list[LocalDatasetMetadata]:
        datasets: list[LocalDatasetMetadata] = []
        for dataset_name in self.dataset_names():
            metadata = self.dataset_metadata(dataset_name)
            datasets.append(metadata)
        return datasets

    def list_tickers(self, dataset_names: list[str] | None = None) -> list[str]:
        tickers: set[str] = set()
        for dataset_name in dataset_names or self.dataset_names():
            frame = self.load_dataframe(dataset_name)
            if frame is None:
                continue
            ticker_column = _detect_ticker_column(list(frame.columns))
            if ticker_column is None:
                continue
            tickers.update(frame[ticker_column].dropna().astype(str).str.upper().str.strip())
        return sorted(ticker for ticker in tickers if ticker)

    def describe_ticker(self, ticker: str, dataset_names: list[str] | None = None) -> list[LocalTickerDatasetCoverage]:
        ticker = ticker.upper().strip()
        coverage_rows: list[LocalTickerDatasetCoverage] = []
        for dataset_name in dataset_names or self.dataset_names():
            metadata = self.dataset_metadata(dataset_name)
            if metadata.validation_status == "missing_file":
                coverage_rows.append(
                    LocalTickerDatasetCoverage(
                        dataset_name=dataset_name,
                        file_path=None,
                        validation_status=metadata.validation_status,
                        ticker_present=False,
                        row_count_for_ticker=0,
                        latest_data_timestamp=None,
                        notes=["Local CSV dataset is not present."],
                        available_columns=[],
                        missing_required_columns=metadata.missing_required_columns,
                        validation_warnings=metadata.validation_warnings,
                    )
                )
                continue

            frame = self.load_dataframe(dataset_name)
            if frame is None:
                coverage_rows.append(
                    LocalTickerDatasetCoverage(
                        dataset_name=dataset_name,
                        file_path=metadata.file_path,
                        validation_status=metadata.validation_status,
                        ticker_present=False,
                        row_count_for_ticker=0,
                        latest_data_timestamp=metadata.latest_data_timestamp,
                        notes=["Dataset could not be loaded from local CSVs."],
                        available_columns=metadata.available_columns,
                        missing_required_columns=metadata.missing_required_columns,
                        validation_warnings=metadata.validation_warnings,
                    )
                )
                continue
            if metadata.ticker_column is None:
                coverage_rows.append(
                    LocalTickerDatasetCoverage(
                        dataset_name=dataset_name,
                        file_path=metadata.file_path,
                        validation_status=metadata.validation_status,
                        ticker_present=False,
                        row_count_for_ticker=0,
                        latest_data_timestamp=metadata.latest_data_timestamp,
                        notes=["Dataset does not contain a ticker/symbol column."],
                        available_columns=metadata.available_columns,
                        missing_required_columns=metadata.missing_required_columns,
                        validation_warnings=metadata.validation_warnings,
                    )
                )
                continue

            matches = frame.loc[frame[metadata.ticker_column] == ticker].copy()
            latest_timestamp = None
            if metadata.date_column is not None and metadata.date_column in matches.columns and matches[metadata.date_column].notna().any():
                latest_value = matches[metadata.date_column].dropna().max()
                latest_timestamp = latest_value.isoformat() if hasattr(latest_value, "isoformat") else str(latest_value)
            notes = ["Ticker rows found in local dataset."] if not matches.empty else ["Ticker is absent from this local dataset."]
            coverage_rows.append(
                LocalTickerDatasetCoverage(
                    dataset_name=dataset_name,
                    file_path=metadata.file_path,
                    validation_status=metadata.validation_status,
                    ticker_present=not matches.empty,
                    row_count_for_ticker=len(matches),
                    latest_data_timestamp=latest_timestamp or metadata.latest_data_timestamp,
                    notes=notes,
                    available_columns=metadata.available_columns,
                    missing_required_columns=metadata.missing_required_columns,
                    validation_warnings=metadata.validation_warnings,
                )
            )
        return coverage_rows
