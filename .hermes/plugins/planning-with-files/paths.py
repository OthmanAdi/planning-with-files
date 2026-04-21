import os
from pathlib import Path

from .constants import PLUGIN_DIR

SKILL_DIR_NAME = "planning-with-files"


def has_skill_assets(candidate: Path) -> bool:
    return (candidate / "templates").is_dir() and (candidate / "scripts" / "check-complete.sh").is_file()


def candidate_skill_dirs(root: Path) -> list[Path]:
    return [
        root,
        root / "skills" / SKILL_DIR_NAME,
        root / ".hermes" / "skills" / SKILL_DIR_NAME,
    ]


def resolve_skill_dir_from(root: Path) -> Path | None:
    for candidate in candidate_skill_dirs(root.resolve()):
        if has_skill_assets(candidate):
            return candidate
    return None


def resolve_explicit_skill_dir() -> Path | None:
    for env_name in ("PLANNING_WITH_FILES_SKILL_ROOT", "PLANNING_WITH_FILES_REPO_ROOT"):
        explicit = os.environ.get(env_name, "").strip()
        if not explicit:
            continue
        resolved = resolve_skill_dir_from(Path(explicit).expanduser())
        if resolved is not None:
            return resolved
    return None


def find_skill_dir(start: Path) -> Path:
    explicit = resolve_explicit_skill_dir()
    if explicit is not None:
        return explicit
    for candidate in [start.resolve(), *start.resolve().parents]:
        resolved = resolve_skill_dir_from(candidate)
        if resolved is not None:
            return resolved
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        resolved = resolve_skill_dir_from(candidate)
        if resolved is not None:
            return resolved
    return start.resolve()


def normalize_cwd(cwd: str | None = None) -> Path:
    candidate = cwd or str(Path.cwd()) or os.environ.get("PWD") or "."
    return Path(candidate).expanduser().resolve()


def resolve_skill_dir(project_dir: Path) -> Path:
    explicit = resolve_explicit_skill_dir()
    if explicit is not None:
        return explicit
    plugin_root = find_skill_dir(PLUGIN_DIR)
    if has_skill_assets(plugin_root):
        return plugin_root
    for candidate in [project_dir.resolve(), *project_dir.resolve().parents]:
        resolved = resolve_skill_dir_from(candidate)
        if resolved is not None:
            return resolved
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        resolved = resolve_skill_dir_from(candidate)
        if resolved is not None:
            return resolved
    return plugin_root


SKILL_ROOT = find_skill_dir(PLUGIN_DIR)
TEMPLATES_DIR = SKILL_ROOT / "templates"
SCRIPTS_DIR = SKILL_ROOT / "scripts"
