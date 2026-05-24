import json
from pathlib import Path

import pandas as pd

from src.providers.local_importer import apply_import_merge, preview_import_merge, validate_imports


def _setup_dirs(tmp_path: Path) -> tuple[Path, Path]:
    data_dir = tmp_path / "data"
    imports_dir = data_dir / "imports"
    data_dir.mkdir()
    imports_dir.mkdir()
    return data_dir, imports_dir


def test_validate_imports_handles_missing_import_directory(tmp_path: Path):
    result = validate_imports(base_dir=tmp_path)

    assert result["status"] == "no_staged_files"
    assert "Import directory does not exist." in result["warnings"]


def test_validate_imports_accepts_valid_staged_fundamentals(tmp_path: Path):
    data_dir, imports_dir = _setup_dirs(tmp_path)
    (imports_dir / "fundamentals.csv").write_text(
        "ticker,revenue,eps,free_cash_flow,source,as_of_date\n"
        "NVDA,1000,5,200,manual,2026-05-01\n",
        encoding="utf-8",
    )

    result = validate_imports(base_dir=tmp_path)

    assert result["status"] == "valid"
    file_result = result["files"][0]
    assert file_result["dataset_name"] == "fundamentals"
    assert file_result["validation"]["status"] == "valid"
    assert file_result["ticker_count"] == 1


def test_validate_imports_flags_missing_required_ticker_column(tmp_path: Path):
    _data_dir, imports_dir = _setup_dirs(tmp_path)
    (imports_dir / "fundamentals.csv").write_text("revenue,eps\n1000,5\n", encoding="utf-8")

    result = validate_imports(base_dir=tmp_path)

    assert result["status"] == "invalid"
    assert result["files"][0]["validation"]["missing_required_columns"] == ["ticker"]


def test_validate_imports_warns_on_unknown_extra_and_invalid_values(tmp_path: Path):
    _data_dir, imports_dir = _setup_dirs(tmp_path)
    (imports_dir / "fundamentals.csv").write_text(
        "ticker,revenue,as_of_date,mystery\n"
        "NVDA,not_numeric,not_a_date,x\n",
        encoding="utf-8",
    )

    result = validate_imports(base_dir=tmp_path)
    warnings = result["files"][0]["validation"]["warnings"]

    assert result["status"] == "valid_with_warnings"
    assert any("numeric" in warning for warning in warnings)
    assert any("dates" in warning for warning in warnings)
    assert any("Unknown columns" in warning for warning in warnings)


def test_preview_import_merge_reports_new_updated_and_unchanged_rows_without_mutation(tmp_path: Path):
    data_dir, imports_dir = _setup_dirs(tmp_path)
    canonical = data_dir / "fundamentals.csv"
    canonical.write_text(
        "ticker,revenue,eps,source,as_of_date\n"
        "MSFT,1000,5,old,2026-01-01\n"
        "AAPL,900,4,old,2026-01-01\n",
        encoding="utf-8",
    )
    before = canonical.read_text(encoding="utf-8")
    (imports_dir / "fundamentals.csv").write_text(
        "ticker,revenue,eps,source,as_of_date\n"
        "MSFT,1100,5.5,new,2026-05-01\n"
        "AAPL,900,4,old,2026-01-01\n"
        "NVDA,1200,6,new,2026-05-01\n",
        encoding="utf-8",
    )

    result = preview_import_merge(base_dir=tmp_path)
    preview = result["preview"][0]

    assert result["status"] == "valid"
    assert preview["updated_rows"] == 1
    assert preview["unchanged_rows"] == 1
    assert preview["new_rows"] == 1
    assert canonical.read_text(encoding="utf-8") == before


def test_preview_import_merge_handles_peers_by_ticker_and_peer_ticker(tmp_path: Path):
    data_dir, imports_dir = _setup_dirs(tmp_path)
    (data_dir / "peers.csv").write_text(
        "ticker,peer_ticker,peer_group\n"
        "NVDA,AMD,semis\n",
        encoding="utf-8",
    )
    (imports_dir / "peers.csv").write_text(
        "ticker,peer_ticker,peer_group\n"
        "NVDA,AMD,ai_semis\n"
        "NVDA,AVGO,ai_semis\n",
        encoding="utf-8",
    )

    result = preview_import_merge(base_dir=tmp_path)
    preview = result["preview"][0]

    assert preview["updated_rows"] == 1
    assert preview["new_rows"] == 1


def test_apply_import_merge_creates_backup_and_updates_and_appends_rows(tmp_path: Path):
    data_dir, imports_dir = _setup_dirs(tmp_path)
    (data_dir / "fundamentals.csv").write_text(
        "ticker,revenue,eps,source,as_of_date\n"
        "MSFT,1000,5,old,2026-01-01\n",
        encoding="utf-8",
    )
    (imports_dir / "fundamentals.csv").write_text(
        "ticker,revenue,eps,source,as_of_date\n"
        "MSFT,1100,5.5,new,2026-05-01\n"
        "NVDA,1200,6,new,2026-05-01\n",
        encoding="utf-8",
    )

    result = apply_import_merge(base_dir=tmp_path)

    assert result["status"] == "applied"
    applied = result["applied"][0]
    assert applied["applied"] is True
    assert applied["backup_path"] is not None
    merged = pd.read_csv(data_dir / "fundamentals.csv")
    assert set(merged["ticker"]) == {"MSFT", "NVDA"}
    msft = merged.loc[merged["ticker"] == "MSFT"].iloc[0]
    nvda = merged.loc[merged["ticker"] == "NVDA"].iloc[0]
    assert msft["revenue"] == 1100
    assert msft["source"] == "new"
    assert nvda["as_of_date"] == "2026-05-01"


def test_sparse_staged_import_preserves_existing_canonical_values(tmp_path: Path):
    data_dir, imports_dir = _setup_dirs(tmp_path)
    (data_dir / "fundamentals.csv").write_text(
        "ticker,theme,sector,pe_ratio,revenue,source,as_of_date\n"
        "NVDA,AI Infrastructure,Technology,34,,manual,2026-01-01\n",
        encoding="utf-8",
    )
    (imports_dir / "fundamentals.csv").write_text(
        "ticker,theme,sector,pe_ratio,revenue,source,as_of_date\n"
        "NVDA,,,,1000,sec_companyfacts,2025-12-31\n",
        encoding="utf-8",
    )

    preview = preview_import_merge(base_dir=tmp_path)
    assert preview["preview"][0]["updated_rows"] == 1

    result = apply_import_merge(base_dir=tmp_path)
    merged = pd.read_csv(data_dir / "fundamentals.csv")
    nvda = merged.loc[merged["ticker"] == "NVDA"].iloc[0]

    assert result["status"] == "applied"
    assert nvda["theme"] == "AI Infrastructure"
    assert nvda["sector"] == "Technology"
    assert nvda["pe_ratio"] == 34
    assert nvda["revenue"] == 1000
    assert nvda["source"] == "sec_companyfacts"
    assert nvda["as_of_date"] == "2025-12-31"


def test_blank_staged_import_is_unchanged_for_existing_canonical_row(tmp_path: Path):
    data_dir, imports_dir = _setup_dirs(tmp_path)
    (data_dir / "fundamentals.csv").write_text(
        "ticker,theme,source,as_of_date\n"
        "NVDA,AI Infrastructure,manual,2026-01-01\n",
        encoding="utf-8",
    )
    (imports_dir / "fundamentals.csv").write_text(
        "ticker,theme,source,as_of_date\n"
        "NVDA,,,\n",
        encoding="utf-8",
    )

    preview = preview_import_merge(base_dir=tmp_path)

    assert preview["preview"][0]["updated_rows"] == 0
    assert preview["preview"][0]["unchanged_rows"] == 1


def test_apply_import_merge_preserves_canonical_when_validation_fails(tmp_path: Path):
    data_dir, imports_dir = _setup_dirs(tmp_path)
    canonical = data_dir / "fundamentals.csv"
    canonical.write_text(
        "ticker,revenue\n"
        "MSFT,1000\n",
        encoding="utf-8",
    )
    before = canonical.read_text(encoding="utf-8")
    (imports_dir / "fundamentals.csv").write_text("revenue\n2000\n", encoding="utf-8")

    result = apply_import_merge(base_dir=tmp_path)

    assert result["status"] == "refused_invalid_imports"
    assert canonical.read_text(encoding="utf-8") == before


def test_apply_import_merge_handles_peer_composite_keys(tmp_path: Path):
    data_dir, imports_dir = _setup_dirs(tmp_path)
    (data_dir / "peers.csv").write_text(
        "ticker,peer_ticker,peer_group,source,as_of_date\n"
        "NVDA,AMD,semis,old,2026-01-01\n",
        encoding="utf-8",
    )
    (imports_dir / "peers.csv").write_text(
        "ticker,peer_ticker,peer_group,source,as_of_date\n"
        "NVDA,AMD,ai_semis,new,2026-05-01\n"
        "NVDA,AVGO,ai_semis,new,2026-05-01\n",
        encoding="utf-8",
    )

    result = apply_import_merge(base_dir=tmp_path)
    merged = pd.read_csv(data_dir / "peers.csv")

    assert result["status"] == "applied"
    assert len(merged) == 2
    assert set(zip(merged["ticker"], merged["peer_ticker"])) == {("NVDA", "AMD"), ("NVDA", "AVGO")}
    amd = merged.loc[merged["peer_ticker"] == "AMD"].iloc[0]
    assert amd["peer_group"] == "ai_semis"
    assert amd["source"] == "new"


def test_apply_import_merge_preserves_existing_unknown_canonical_columns(tmp_path: Path):
    data_dir, imports_dir = _setup_dirs(tmp_path)
    (data_dir / "fundamentals.csv").write_text(
        "ticker,revenue,legacy_note\n"
        "MSFT,1000,keep_me\n",
        encoding="utf-8",
    )
    (imports_dir / "fundamentals.csv").write_text(
        "ticker,revenue,source,as_of_date\n"
        "MSFT,1100,new,2026-05-01\n",
        encoding="utf-8",
    )

    apply_import_merge(base_dir=tmp_path)
    merged = pd.read_csv(data_dir / "fundamentals.csv")

    assert "legacy_note" in merged.columns
    assert merged.loc[0, "legacy_note"] == "keep_me"


def test_importer_json_output_is_serializable(tmp_path: Path):
    _data_dir, imports_dir = _setup_dirs(tmp_path)
    (imports_dir / "fundamentals.csv").write_text(
        "ticker,revenue,source,as_of_date\n"
        "NVDA,1000,manual,2026-05-01\n",
        encoding="utf-8",
    )

    result = preview_import_merge(base_dir=tmp_path)
    payload = json.dumps(result)

    assert "fundamentals.csv" in payload
