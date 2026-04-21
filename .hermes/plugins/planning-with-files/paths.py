import os
from pathlib import Path

from .constants import PLUGIN_DIR


def has_adapter_assets(candidate: Path) -> bool:
    return (candidate / "templates").is_dir() and (candidate / "scripts" / "check-complete.sh").is_file()


def find_repo_root(start: Path) -> Path:
    explicit = os.environ.get("PLANNING_WITH_FILES_REPO_ROOT", "").strip()
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if has_adapter_assets(candidate):
            return candidate
    for candidate in [start, *start.parents]:
        if has_adapter_assets(candidate):
            return candidate
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if has_adapter_assets(candidate):
            return candidate
    return start


def normalize_cwd(cwd: str | None = None) -> Path:
    candidate = cwd or str(Path.cwd()) or os.environ.get("PWD") or "."
    return Path(candidate).expanduser().resolve()


def resolve_repo_root(project_dir: Path) -> Path:
    explicit = os.environ.get("PLANNING_WITH_FILES_REPO_ROOT", "").strip()
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if has_adapter_assets(candidate):
            return candidate
    plugin_root = find_repo_root(PLUGIN_DIR)
    if has_adapter_assets(plugin_root):
        return plugin_root
    for candidate in [project_dir.resolve(), *project_dir.resolve().parents]:
        if has_adapter_assets(candidate):
            return candidate
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if has_adapter_assets(candidate):
            return candidate
    return plugin_root


REPO_ROOT = find_repo_root(PLUGIN_DIR)
TEMPLATES_DIR = REPO_ROOT / "templates"
SCRIPTS_DIR = REPO_ROOT / "scripts"
