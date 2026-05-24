from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.providers.local_schemas import LOCAL_DATASET_SCHEMAS, validate_local_dataset


IMPORT_FILE_SPECS: dict[str, dict[str, Any]] = {
    "fundamentals.csv": {"dataset_name": "fundamentals", "merge_keys": ("ticker",)},
    "earnings.csv": {"dataset_name": "earnings", "merge_keys": ("ticker",)},
    "earnings_history.csv": {"dataset_name": "earnings", "merge_keys": ("ticker",)},
    "analyst_estimates.csv": {"dataset_name": "analyst_estimates", "merge_keys": ("ticker",)},
    "estimates.csv": {"dataset_name": "analyst_estimates", "merge_keys": ("ticker",)},
    "peers.csv": {"dataset_name": "peers", "merge_keys": ("ticker", "peer_ticker")},
}


def _resolve_import_dir(base_dir: Path, import_dir: Path | None = None) -> Path:
    return import_dir or (base_dir / "data" / "imports")


def _resolve_data_dir(base_dir: Path, data_dir: Path | None = None) -> Path:
    return data_dir or (base_dir / "data")


def _dataset_allowed_columns(dataset_name: str) -> list[str]:
    schema = LOCAL_DATASET_SCHEMAS[dataset_name]
    columns = list(schema.required_columns)
    for column in schema.optional_columns:
        if column not in columns:
            columns.append(column)
    return columns


def _staged_entries(import_path: Path, data_path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not import_path.exists():
        return entries
    for file_name, spec in IMPORT_FILE_SPECS.items():
        staged_path = import_path / file_name
        if not staged_path.exists():
            continue
        entries.append(
            {
                "file_name": file_name,
                "dataset_name": spec["dataset_name"],
                "merge_keys": list(spec["merge_keys"]),
                "staged_path": staged_path,
                "canonical_path": data_path / file_name,
            }
        )
    return entries


def _normalize_merge_frame(
    dataset_name: str,
    frame: pd.DataFrame,
    *,
    preserve_unknown_columns: bool = False,
) -> tuple[pd.DataFrame, list[str], int]:
    schema = LOCAL_DATASET_SCHEMAS[dataset_name]
    allowed_columns = _dataset_allowed_columns(dataset_name)
    dropped_columns = [column for column in frame.columns if column not in allowed_columns]
    if preserve_unknown_columns:
        normalized = frame.copy()
    else:
        normalized = frame[[column for column in frame.columns if column in allowed_columns]].copy()

    valid_mask = pd.Series(True, index=normalized.index)
    for key in schema.ticker_columns:
        if key in normalized.columns:
            valid_mask &= normalized[key].notna()
            valid_mask &= normalized[key].astype(str).str.strip().ne("")
    skipped_missing_key_rows = int((~valid_mask).sum())
    normalized = normalized.loc[valid_mask].copy()

    duplicate_rows = 0
    merge_keys = [key for key in schema.ticker_columns if key in normalized.columns]
    if merge_keys:
        duplicate_rows = int(normalized.duplicated(subset=merge_keys, keep="last").sum())
        normalized = normalized.drop_duplicates(subset=merge_keys, keep="last").copy()

    for column in schema.date_columns:
        if column not in normalized.columns:
            continue
        normalized[column] = normalized[column].apply(_serialize_date_value)

    return normalized, dropped_columns, skipped_missing_key_rows + duplicate_rows


def _serialize_date_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return value
    if timestamp.hour == 0 and timestamp.minute == 0 and timestamp.second == 0 and timestamp.microsecond == 0:
        return timestamp.date().isoformat()
    return timestamp.isoformat()


def _has_import_value(value: Any) -> bool:
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    return not (isinstance(value, str) and value.strip() == "")


def _values_match(left: Any, right: Any) -> bool:
    if not _has_import_value(left) and not _has_import_value(right):
        return True
    if _has_import_value(left) != _has_import_value(right):
        return False
    return left == right


def _key_series(frame: pd.DataFrame, merge_keys: list[str]) -> pd.Series:
    return frame[merge_keys].astype(str).agg("||".join, axis=1)


def validate_imports(import_dir: Path | str | None = None, data_dir: Path | str | None = None, base_dir: Path | None = None) -> dict[str, Any]:
    base_dir = base_dir or Path(__file__).resolve().parent.parent.parent
    data_path = _resolve_data_dir(base_dir, Path(data_dir) if isinstance(data_dir, str) else data_dir)
    import_path = _resolve_import_dir(base_dir, Path(import_dir) if isinstance(import_dir, str) else import_dir)
    entries = _staged_entries(import_path, data_path)

    if not import_path.exists():
        return {
            "status": "no_staged_files",
            "import_dir": str(import_path),
            "files": [],
            "warnings": ["Import directory does not exist."],
        }
    if not entries:
        return {
            "status": "no_staged_files",
            "import_dir": str(import_path),
            "files": [],
            "warnings": ["No staged files found in the import directory."],
        }

    file_results: list[dict[str, Any]] = []
    overall_status = "valid"
    for entry in entries:
        validation, frame = validate_local_dataset(entry["dataset_name"], entry["staged_path"])
        ticker_count = 0
        if frame is not None:
            ticker_column = "ticker" if "ticker" in frame.columns else None
            if ticker_column is not None:
                ticker_count = int(frame[ticker_column].dropna().nunique())
        if validation.status == "invalid":
            overall_status = "invalid"
        elif validation.status == "valid_with_warnings" and overall_status != "invalid":
            overall_status = "valid_with_warnings"
        file_results.append(
            {
                "file_name": entry["file_name"],
                "dataset_name": entry["dataset_name"],
                "merge_keys": entry["merge_keys"],
                "staged_path": str(entry["staged_path"]),
                "canonical_path": str(entry["canonical_path"]),
                "ticker_count": ticker_count,
                "validation": validation.to_dict(),
            }
        )
    return {
        "status": overall_status,
        "import_dir": str(import_path),
        "files": file_results,
        "warnings": [],
    }


def preview_import_merge(import_dir: Path | str | None = None, data_dir: Path | str | None = None, base_dir: Path | None = None) -> dict[str, Any]:
    base_dir = base_dir or Path(__file__).resolve().parent.parent.parent
    data_path = _resolve_data_dir(base_dir, Path(data_dir) if isinstance(data_dir, str) else data_dir)
    import_path = _resolve_import_dir(base_dir, Path(import_dir) if isinstance(import_dir, str) else import_dir)
    validation_summary = validate_imports(import_path, data_path, base_dir=base_dir)
    if validation_summary["status"] == "no_staged_files":
        return {
            **validation_summary,
            "preview": [],
        }

    preview_rows: list[dict[str, Any]] = []
    overall_status = validation_summary["status"]
    for item in validation_summary["files"]:
        dataset_name = item["dataset_name"]
        merge_keys = item["merge_keys"]
        staged_path = Path(item["staged_path"])
        canonical_path = Path(item["canonical_path"])
        staged_validation = item["validation"]

        preview = {
            "file_name": item["file_name"],
            "dataset_name": dataset_name,
            "merge_keys": merge_keys,
            "staged_path": str(staged_path),
            "canonical_path": str(canonical_path),
            "status": staged_validation["status"],
            "missing_required_columns": list(staged_validation["missing_required_columns"]),
            "new_rows": 0,
            "updated_rows": 0,
            "unchanged_rows": 0,
            "skipped_rows": 0,
            "overwrite_keys": [],
            "new_keys": [],
            "warnings": list(staged_validation["warnings"]),
            "dropped_unknown_columns": list(staged_validation["unknown_columns"]),
        }
        if staged_validation["status"] == "invalid":
            preview_rows.append(preview)
            continue

        staged_result, staged_frame = validate_local_dataset(dataset_name, staged_path)
        canonical_result, canonical_frame = validate_local_dataset(dataset_name, canonical_path)
        staged_frame = staged_frame if staged_frame is not None else pd.DataFrame()
        canonical_frame = canonical_frame if canonical_frame is not None else pd.DataFrame()

        staged_normalized, dropped_columns, skipped_rows = _normalize_merge_frame(dataset_name, staged_frame)
        preview["dropped_unknown_columns"] = sorted(set(preview["dropped_unknown_columns"] + dropped_columns))
        preview["skipped_rows"] = skipped_rows

        if staged_normalized.empty:
            preview_rows.append(preview)
            continue

        canonical_normalized, _canonical_dropped, _canonical_skipped = _normalize_merge_frame(
            dataset_name,
            canonical_frame,
            preserve_unknown_columns=True,
        )
        staged_keys = _key_series(staged_normalized, merge_keys)
        canonical_keys = _key_series(canonical_normalized, merge_keys) if not canonical_normalized.empty else pd.Series(dtype="object")

        canonical_lookup = canonical_normalized.assign(_merge_key=canonical_keys).set_index("_merge_key") if not canonical_normalized.empty else pd.DataFrame()
        allowed_columns = _dataset_allowed_columns(dataset_name)
        compare_columns = [column for column in allowed_columns if column not in merge_keys and column in staged_normalized.columns]

        for idx, staged_row in staged_normalized.assign(_merge_key=staged_keys).iterrows():
            merge_key = staged_row["_merge_key"]
            key_text = ", ".join(f"{key}={staged_row[key]}" for key in merge_keys)
            if canonical_lookup.empty or merge_key not in canonical_lookup.index:
                preview["new_rows"] += 1
                preview["new_keys"].append(key_text)
                continue
            canonical_row = canonical_lookup.loc[merge_key]
            if isinstance(canonical_row, pd.DataFrame):
                canonical_row = canonical_row.iloc[-1]
            changed = False
            for column in compare_columns:
                left = staged_row.get(column)
                right = canonical_row.get(column)
                if not _has_import_value(left):
                    continue
                if not _values_match(left, right):
                    changed = True
                    break
            if changed:
                preview["updated_rows"] += 1
                preview["overwrite_keys"].append(key_text)
            else:
                preview["unchanged_rows"] += 1

        preview["canonical_status"] = canonical_result.status
        preview_rows.append(preview)

    return {
        "status": overall_status,
        "import_dir": str(import_path),
        "preview": preview_rows,
        "warnings": validation_summary["warnings"],
    }


def _backup_file(path: Path, backups_dir: Path) -> str | None:
    if not path.exists():
        return None
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = backups_dir / timestamp
    destination.mkdir(parents=True, exist_ok=True)
    backup_path = destination / path.name
    shutil.copy2(path, backup_path)
    return str(backup_path)


def _merge_frames(dataset_name: str, canonical_frame: pd.DataFrame, staged_frame: pd.DataFrame, merge_keys: list[str]) -> pd.DataFrame:
    allowed_columns = _dataset_allowed_columns(dataset_name)
    supported_stage_columns = [column for column in staged_frame.columns if column in allowed_columns]
    output_columns = list(canonical_frame.columns)
    for column in supported_stage_columns:
        if column not in output_columns:
            output_columns.append(column)
    if not output_columns:
        output_columns = supported_stage_columns

    canonical_frame = canonical_frame.reindex(columns=output_columns)
    staged_output_frame = staged_frame.reindex(columns=output_columns)

    if canonical_frame.empty:
        return staged_output_frame.reset_index(drop=True)

    canonical_indexed = canonical_frame.set_index(merge_keys, drop=False).astype(object)
    staged_indexed = staged_frame.set_index(merge_keys, drop=False).astype(object)
    staged_output_indexed = staged_output_frame.set_index(merge_keys, drop=False).astype(object)

    overlapping = canonical_indexed.index.intersection(staged_indexed.index)
    if not overlapping.empty:
        update_columns = [
            column
            for column in staged_indexed.columns
            if column in canonical_indexed.columns and column not in merge_keys
        ]
        if update_columns:
            for column in update_columns:
                staged_values = staged_indexed.loc[overlapping, column]
                import_value_mask = staged_values.map(_has_import_value)
                if not import_value_mask.any():
                    continue
                target_index = staged_values.index[import_value_mask]
                canonical_indexed.loc[target_index, column] = staged_values.loc[target_index]
    new_rows = staged_output_indexed.loc[~staged_output_indexed.index.isin(canonical_indexed.index)]
    merged = pd.concat([canonical_indexed, new_rows], axis=0)
    return merged.reset_index(drop=True)[output_columns]


def apply_import_merge(
    import_dir: Path | str | None = None,
    data_dir: Path | str | None = None,
    base_dir: Path | None = None,
    backup: bool = True,
) -> dict[str, Any]:
    base_dir = base_dir or Path(__file__).resolve().parent.parent.parent
    data_path = _resolve_data_dir(base_dir, Path(data_dir) if isinstance(data_dir, str) else data_dir)
    import_path = _resolve_import_dir(base_dir, Path(import_dir) if isinstance(import_dir, str) else import_dir)
    preview = preview_import_merge(import_path, data_path, base_dir=base_dir)
    if preview["status"] == "no_staged_files":
        return {
            **preview,
            "applied": [],
        }
    if preview["status"] == "invalid":
        return {
            **preview,
            "status": "refused_invalid_imports",
            "applied": [],
        }

    applied_rows: list[dict[str, Any]] = []
    backups_dir = data_path / "backups"
    for item in preview["preview"]:
        if item["status"] == "invalid":
            continue
        staged_path = Path(item["staged_path"])
        canonical_path = Path(item["canonical_path"])
        dataset_name = item["dataset_name"]
        merge_keys = item["merge_keys"]
        _staged_validation, staged_frame = validate_local_dataset(dataset_name, staged_path)
        _canonical_validation, canonical_frame = validate_local_dataset(dataset_name, canonical_path)
        staged_frame = staged_frame if staged_frame is not None else pd.DataFrame()
        canonical_frame = canonical_frame if canonical_frame is not None else pd.DataFrame()
        staged_normalized, dropped_columns, skipped_rows = _normalize_merge_frame(dataset_name, staged_frame)
        if staged_normalized.empty:
            applied_rows.append(
                {
                    **item,
                    "applied": False,
                    "backup_path": None,
                    "dropped_unknown_columns": sorted(set(item["dropped_unknown_columns"] + dropped_columns)),
                    "skipped_rows": skipped_rows,
                }
            )
            continue

        canonical_normalized, _canonical_dropped, _canonical_skipped = _normalize_merge_frame(
            dataset_name,
            canonical_frame,
            preserve_unknown_columns=True,
        )
        backup_path = _backup_file(canonical_path, backups_dir) if backup and (item["new_rows"] or item["updated_rows"]) else None
        merged = _merge_frames(dataset_name, canonical_normalized, staged_normalized, merge_keys)
        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(canonical_path, index=False)
        applied_rows.append(
            {
                **item,
                "applied": True,
                "backup_path": backup_path,
                "dropped_unknown_columns": sorted(set(item["dropped_unknown_columns"] + dropped_columns)),
                "skipped_rows": skipped_rows,
            }
        )

    return {
        "status": "applied",
        "import_dir": str(import_path),
        "applied": applied_rows,
        "warnings": preview["warnings"],
    }
