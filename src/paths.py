from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_project_root(project_root: Path | str | None = None) -> Path:
    """Return the repository root used for config and default data paths."""
    if project_root is None:
        return PROJECT_ROOT
    return Path(project_root).expanduser().resolve()


def resolve_data_dir(data_dir: Path | str | None = None, project_root: Path | str | None = None) -> Path:
    root = resolve_project_root(project_root)
    if data_dir is None:
        return root / "data"
    path = Path(data_dir).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def resolve_outputs_dir(output_dir: Path | str | None = None, project_root: Path | str | None = None) -> Path:
    root = resolve_project_root(project_root)
    if output_dir is None:
        return root / "outputs"
    path = Path(output_dir).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def path_context(
    project_root: Path | str | None = None,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, str]:
    root = resolve_project_root(project_root)
    return {
        "project_root": str(root),
        "data_dir": str(resolve_data_dir(data_dir, root)),
        "outputs_dir": str(resolve_outputs_dir(output_dir, root)),
    }


def format_path_context(
    project_root: Path | str | None = None,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> str:
    context = path_context(project_root=project_root, data_dir=data_dir, output_dir=output_dir)
    return (
        f"Project root: {context['project_root']}\n"
        f"Data dir: {context['data_dir']}\n"
        f"Outputs dir: {context['outputs_dir']}"
    )
