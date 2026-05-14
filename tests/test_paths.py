from pathlib import Path

from src.paths import PROJECT_ROOT, path_context, resolve_data_dir, resolve_outputs_dir, resolve_project_root


def test_default_paths_resolve_to_repo_root_not_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert resolve_project_root() == PROJECT_ROOT
    assert resolve_data_dir() == PROJECT_ROOT / "data"
    assert resolve_outputs_dir() == PROJECT_ROOT / "outputs"


def test_explicit_project_root_supports_temp_fixtures(tmp_path):
    assert resolve_project_root(tmp_path) == tmp_path.resolve()
    assert resolve_data_dir("alt_data", tmp_path) == tmp_path.resolve() / "alt_data"
    assert resolve_outputs_dir("alt_outputs", tmp_path) == tmp_path.resolve() / "alt_outputs"


def test_path_context_is_json_friendly(tmp_path):
    context = path_context(tmp_path, "data", "outputs")

    assert context == {
        "project_root": str(tmp_path.resolve()),
        "data_dir": str(tmp_path.resolve() / "data"),
        "outputs_dir": str(tmp_path.resolve() / "outputs"),
    }
