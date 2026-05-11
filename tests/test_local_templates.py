from pathlib import Path

from src.providers.local_templates import template_columns, write_import_staging_files, write_local_data_templates


def test_template_columns_include_required_and_optional_fields():
    columns = template_columns("fundamentals")

    assert columns[0] == "ticker"
    assert "revenue" in columns
    assert "as_of_date" in columns


def test_write_local_data_templates_creates_header_only_csvs(tmp_path: Path):
    results = write_local_data_templates(tmp_path)

    created = {item["dataset_name"]: item for item in results}
    fundamentals_path = Path(created["fundamentals"]["path"])
    peers_path = Path(created["peers"]["path"])

    assert created["fundamentals"]["created"] is True
    assert fundamentals_path.exists()
    assert peers_path.exists()
    assert fundamentals_path.read_text(encoding="utf-8").startswith("ticker,")
    assert peers_path.read_text(encoding="utf-8").startswith("ticker,peer_ticker")


def test_write_local_data_templates_does_not_overwrite_existing_files(tmp_path: Path):
    template_dir = tmp_path / "custom_templates"
    template_dir.mkdir()
    existing = template_dir / "fundamentals.csv"
    existing.write_text("ticker,custom_field\n", encoding="utf-8")

    results = write_local_data_templates(tmp_path, template_dir=template_dir)
    fundamentals = next(item for item in results if item["dataset_name"] == "fundamentals")

    assert fundamentals["created"] is False
    assert existing.read_text(encoding="utf-8") == "ticker,custom_field\n"


def test_write_import_staging_files_creates_header_only_staging_csvs(tmp_path: Path):
    results = write_import_staging_files(tmp_path)

    peers = next(item for item in results if item["dataset_name"] == "peers")
    peers_path = Path(peers["path"])

    assert peers["created"] is True
    assert peers_path.exists()
    assert peers_path.read_text(encoding="utf-8").startswith("ticker,peer_ticker")
