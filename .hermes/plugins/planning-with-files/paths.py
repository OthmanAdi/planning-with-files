import os
import re
import stat
from pathlib import Path

from .constants import PLUGIN_DIR

SKILL_DIR_NAME = "planning-with-files"

# Same shape the sh resolver enforces (slug_is_valid in resolve-plan-dir.sh):
# first character alphanumeric or underscore, then letters, digits, dot, dash,
# underscore. Rejects traversal, separators, and whitespace by construction.
_SLUG_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]*$")
_REPARSE_ATTR = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
MULTIPLE_PLANS_NOTICE = (
    "[planning-with-files] Multiple plans are available. "
    "Set PLAN_ID=<slug> for this session; nothing injected."
)
MULTIPLE_PLANS_MESSAGE = "Multiple plans are available. Set PLAN_ID=<slug> to select one."


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


def plugin_skill_dir() -> Path | None:
    """Skill assets that ship next to the plugin itself, never a cwd guess.

    Walks up from the plugin directory only: the repository checkout
    (``.hermes/skills/planning-with-files`` beside ``.hermes/plugins``) or a
    user profile (``<HERMES_HOME>/skills/planning-with-files`` beside
    ``<HERMES_HOME>/plugins``). Used for anything registered under the
    plugin's trusted namespace, so an untrusted working directory can never
    supply it.
    """
    explicit = resolve_explicit_skill_dir()
    if explicit is not None:
        return explicit
    start = PLUGIN_DIR.resolve()
    for candidate in [start, *start.parents]:
        resolved = resolve_skill_dir_from(candidate)
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


# ---------------------------------------------------------------------------
# Active plan resolution (slug mode parity with resolve-plan-dir.sh and the
# nested-root conflict rule of inject-plan.sh)
# ---------------------------------------------------------------------------


def _is_link_or_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return True
    if stat.S_ISLNK(info.st_mode):
        return True
    return bool(getattr(info, "st_file_attributes", 0) & _REPARSE_ATTR)


def _is_regular_file(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & _REPARSE_ATTR:
        return False
    return stat.S_ISREG(info.st_mode)


def _is_real_dir(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & _REPARSE_ATTR:
        return False
    return stat.S_ISDIR(info.st_mode)


def slug_is_valid(slug: str) -> bool:
    return bool(slug) and _SLUG_RE.match(slug) is not None


def plan_root_is_pinned() -> bool:
    """True when PWF_PLAN_ROOT is set; the pin itself is validated by effective_project_root."""
    return bool(os.environ.get("PWF_PLAN_ROOT", "").strip())


def effective_project_root(project_dir: Path) -> Path | None:
    """Apply the PWF_PLAN_ROOT pin (issue #212); a broken pin fails closed.

    With the variable unset the runtime project passes through untouched.
    A pin must be an absolute path to an existing directory that is not a
    UNC path and carries no link component; anything else returns None so
    the hooks inject nothing rather than falling back to an unrelated plan.
    """
    pin = os.environ.get("PWF_PLAN_ROOT", "").strip()
    if not pin:
        return project_dir
    pin_path = Path(pin)
    if not pin_path.is_absolute() or pin.startswith(("\\\\", "//")):
        return None
    try:
        pin_real = pin_path.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not pin_real.is_dir() or _is_link_or_reparse(pin_path):
        return None
    return pin_real


def _slug_plan_dir(planning_root: Path, slug: str) -> Path | None:
    """Return .planning/<slug> when it is a contained, real directory with a plan."""
    if not slug_is_valid(slug):
        return None
    candidate = planning_root / slug
    if _is_link_or_reparse(candidate) or not candidate.is_dir():
        return None
    try:
        candidate.resolve(strict=True).relative_to(planning_root.resolve(strict=True))
    except (OSError, RuntimeError, ValueError):
        return None
    if not _is_regular_file(candidate / "task_plan.md"):
        return None
    return candidate


def _read_active_pointer(planning_root: Path) -> str:
    """The single slug named by .planning/.active_plan, BOM and whitespace stripped."""
    pointer = planning_root / ".active_plan"
    if not _is_regular_file(pointer):
        return ""
    try:
        raw = pointer.read_text(encoding="utf-8-sig", errors="strict")
    except (OSError, UnicodeError):
        return ""
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    return lines[0] if len(lines) == 1 else ""


def count_selectable_plans(project_dir: Path) -> int:
    """Count plans exactly as inject-plan.sh does before guessing a selection.

    A legacy root plan counts only after session isolation is armed. Every
    contained valid slug directory with a regular task_plan.md counts. The
    caller only needs to distinguish zero/one from "more than one", so stop at
    two.
    """
    planning_root = project_dir / ".planning"
    count = 0
    if _is_real_dir(planning_root / "sessions") and _is_regular_file(project_dir / "task_plan.md"):
        count = 1
    try:
        entries = list(planning_root.iterdir())
    except OSError:
        return count
    for entry in entries:
        if not slug_is_valid(entry.name):
            continue
        if _slug_plan_dir(planning_root, entry.name) is None:
            continue
        count += 1
        if count > 1:
            break
    return count


def multiple_plans_require_selector(project_dir: Path, *, plan_id: str | None = None) -> bool:
    """True when shared pointer/mtime guesses cannot identify this session's plan."""
    requested = plan_id if plan_id is not None else os.environ.get("PLAN_ID", "").strip()
    return not requested and count_selectable_plans(project_dir) > 1


def nested_live_plans(root: Path) -> list[str]:
    """Direct children whose own .planning holds a live plan (<slug>/task_plan.md).

    Mirrors the ``*/.planning/*/task_plan.md`` probe in inject-plan.sh: depth
    one only, dotted children skipped like the shell glob, and only a LIVE
    nested plan competes. An empty nested ``.planning`` or a loose nested
    ``task_plan.md`` never counts, because a thread working in that child
    could not inject anything from it either.
    """
    found: list[str] = []
    try:
        children = sorted(root.iterdir())
    except OSError:
        return found
    for child in children:
        if child.name.startswith("."):
            continue
        try:
            if not child.is_dir() or _is_link_or_reparse(child):
                continue
            planning = child / ".planning"
            if not planning.is_dir():
                continue
            for slug_dir in planning.iterdir():
                if slug_dir.name.startswith("."):
                    continue
                if slug_dir.is_dir() and _is_regular_file(slug_dir / "task_plan.md"):
                    found.append(child.name)
                    break
        except OSError:
            continue
    return found


def resolve_plan(
    project_dir: Path, *, plan_id: str | None = None, explicit: bool = False
) -> tuple[Path | None, list[str]]:
    """Resolve the active plan directory; return it with any nested conflicts.

    Precedence mirrors resolve-plan-dir.sh: a non-empty explicit plan id (the
    PLAN_ID environment variable when not passed) is binding. Without one,
    more than one selectable same-root plan is refused; otherwise resolution
    continues through .planning/.active_plan, the newest
    .planning/<slug>/task_plan.md by modification time, then the legacy root
    task_plan.md. Slugs are validated and the chosen directory must stay
    inside .planning (no symlink or junction escape).

    A cwd guess (pointer, newest, or legacy root) is refused when a direct
    child of the root carries its own live plan (issue #212): the result is
    ``(None, [child names])`` so the caller can say why. ``explicit`` marks a
    project-root selection that skips only that nested-root check, exactly as
    inject-plan.sh does for a valid ``PWF_PLAN_ROOT`` pin. It never selects one
    of several same-root plans; that still requires ``PLAN_ID``.
    """
    planning_root = project_dir / ".planning"
    requested = plan_id if plan_id is not None else os.environ.get("PLAN_ID", "").strip()
    if requested:
        # A set PLAN_ID is a BINDING, not a hint (issue #237).
        #
        # A slug that resolves is authoritative and skips the nested check. One
        # that does NOT resolve ends resolution right here. Falling through to
        # the pointer, the newest slug and the legacy root turned a
        # one-character typo into a silent switch: the operator asked for plan
        # A, .active_plan or newest-by-mtime answered with plan B, and B was
        # what got attested and injected at rc=0. Every rejection route ends the
        # same way, whether the selector failed slug validation (traversal
        # shapes included), named no directory, or failed containment. The
        # caller receives "no plan" and takes its own fail-closed path rather
        # than a plan nobody selected.
        #
        # An EMPTY PLAN_ID still means "no selector": resolution continues below
        # exactly as before, which is what the legacy root path depends on.
        explicit_dir = _slug_plan_dir(planning_root, requested)
        if explicit_dir is not None:
            return explicit_dir, []
        return None, []

    # A shared .active_plan pointer or directory mtime cannot identify which
    # same-root task this session owns. PWF_PLAN_ROOT selects the project, not
    # one of its plans, so even an explicit root pin does not lift this refusal.
    if count_selectable_plans(project_dir) > 1:
        return None, []

    chosen: Path | None = None
    if planning_root.is_dir() and not _is_link_or_reparse(planning_root):
        pointed = _read_active_pointer(planning_root)
        if pointed:
            chosen = _slug_plan_dir(planning_root, pointed)
        if chosen is None:
            newest_mtime = -1.0
            try:
                entries = list(planning_root.iterdir())
            except OSError:
                entries = []
            for entry in entries:
                candidate = _slug_plan_dir(planning_root, entry.name)
                if candidate is None:
                    continue
                try:
                    mtime = (candidate / "task_plan.md").stat().st_mtime
                except OSError:
                    continue
                if mtime > newest_mtime:
                    newest_mtime = mtime
                    chosen = candidate
    if chosen is None and _is_regular_file(project_dir / "task_plan.md"):
        chosen = project_dir
    if chosen is None:
        return None, []
    if not explicit:
        conflicts = nested_live_plans(project_dir)
        if conflicts:
            return None, conflicts
    return chosen, []


def resolve_plan_dir(
    project_dir: Path, *, plan_id: str | None = None, explicit: bool = False
) -> Path | None:
    """The directory that owns the active task_plan.md, or None (see resolve_plan)."""
    return resolve_plan(project_dir, plan_id=plan_id, explicit=explicit)[0]


def ambiguity_notice(conflicts: list[str]) -> str:
    """The once-per-turn refusal line, same wording as inject-plan.sh."""
    listed = ", ".join(conflicts[:3])
    return (
        "[planning-with-files] Ambiguous plan: this cwd has an active plan and a nested project "
        f"below it has its own ({listed}). Nothing injected. Pin the thread with "
        "PWF_PLAN_ROOT=<absolute path> or PLAN_ID=<slug>."
    )


def plan_id_for(project_dir: Path, plan_dir: Path) -> str:
    """Human-readable plan identity: the slug, or 'root' for legacy mode."""
    if plan_dir == project_dir:
        return "root"
    return plan_dir.name


def attestation_path_for(project_dir: Path, plan_dir: Path) -> Path:
    """Legacy root plans attest to ./.plan-attestation; slug plans to <dir>/.attestation."""
    if plan_dir == project_dir:
        return project_dir / ".plan-attestation"
    return plan_dir / ".attestation"
