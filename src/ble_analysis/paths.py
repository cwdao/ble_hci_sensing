"""Project path helpers for BLE analysis notebooks."""

from pathlib import Path

FIGURES_DIR_NAME = "figures"
PROCESSED_DIR_NAME = "processed"
REPORTS_DIR_NAME = "reports"


def find_project_root(start=None, marker="src"):
    """Walk up from *start* until a directory containing *marker* is found."""
    start = Path.cwd().resolve() if start is None else Path(start).resolve()
    for path in [start, *start.parents]:
        if (path / marker).is_dir():
            return path
    raise FileNotFoundError(f"未找到项目根目录（缺少 {marker}/ 目录）")


def ensure_output_dirs(project_root=None):
    """Create standard output directories under the project root."""
    if project_root is None:
        project_root = find_project_root()
    project_root = Path(project_root)
    figures_dir = project_root / "outputs" / FIGURES_DIR_NAME
    processed_dir = project_root / "outputs" / PROCESSED_DIR_NAME
    reports_dir = project_root / "outputs" / REPORTS_DIR_NAME
    for directory in (figures_dir, processed_dir, reports_dir):
        directory.mkdir(parents=True, exist_ok=True)
    return {
        "project_root": project_root,
        "figures_dir": figures_dir,
        "processed_dir": processed_dir,
        "reports_dir": reports_dir,
    }
