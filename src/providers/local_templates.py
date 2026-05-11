from __future__ import annotations

from pathlib import Path
from typing import Any

from src.providers.local_schemas import LOCAL_DATASET_SCHEMAS


TEMPLATE_DATASETS = ("fundamentals", "earnings", "analyst_estimates", "peers")


def template_columns(dataset_name: str) -> list[str]:
    schema = LOCAL_DATASET_SCHEMAS[dataset_name]
    columns = list(schema.required_columns)
    for column in schema.optional_columns:
        if column not in columns:
            columns.append(column)
    return columns


def write_local_data_templates(base_dir: Path, template_dir: Path | None = None) -> list[dict[str, Any]]:
    destination = template_dir or (base_dir / "data" / "templates")
    destination.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for dataset_name in TEMPLATE_DATASETS:
        path = destination / f"{dataset_name}.csv"
        columns = template_columns(dataset_name)
        created = False
        if not path.exists():
            path.write_text(",".join(columns) + "\n", encoding="utf-8")
            created = True
        results.append(
            {
                "dataset_name": dataset_name,
                "path": str(path),
                "created": created,
                "status": "created" if created else "skipped_existing",
                "columns": columns,
            }
        )
    return results


def write_import_staging_files(base_dir: Path, import_dir: Path | None = None) -> list[dict[str, Any]]:
    destination = import_dir or (base_dir / "data" / "imports")
    destination.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for dataset_name in TEMPLATE_DATASETS:
        path = destination / f"{dataset_name}.csv"
        columns = template_columns(dataset_name)
        created = False
        if not path.exists():
            path.write_text(",".join(columns) + "\n", encoding="utf-8")
            created = True
        results.append(
            {
                "dataset_name": dataset_name,
                "path": str(path),
                "created": created,
                "status": "created" if created else "skipped_existing",
                "columns": columns,
            }
        )
    return results
