import datetime as _dt
import hashlib
import os
import re
import secrets
import shutil
from pathlib import Path
from typing import Any

from .constants import PLANNING_FILES, PLAN_PREVIEW_LINES, PROGRESS_TAIL_LINES
from .paths import (
    MULTIPLE_PLANS_MESSAGE,
    attestation_path_for,
    multiple_plans_require_selector,
    plan_id_for,
    resolve_plan_dir,
    resolve_skill_dir,
)


# Wall-clock times inside the injected progress tail move on every fire, which
# costs prompt-cache reuse for the bytes that follow them. The shell hooks have
# normalized them since v2.40; this is the same substitution, kept character for
# character equivalent to the `sed -E` expression in scripts/inject-plan.sh so
# every route emits the same bytes for the same input.
_WALL_CLOCK_UTC = re.compile(r"T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z")
_WALL_CLOCK_OFFSET = re.compile(r"T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?([+-][0-9]{2}:[0-9]{2})")

_CONTROL_CHARS = re.compile(r"[\x01-\x1f]")


def normalize_wall_clock(text: str) -> str:
    """Flatten ISO-8601 clock times to T00:00:00, keeping any UTC offset."""
    text = _WALL_CLOCK_UTC.sub("T00:00:00Z", text)
    return _WALL_CLOCK_OFFSET.sub(r"T00:00:00\2", text)


def tail_lines(path: Path, limit: int) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    return normalize_wall_clock("\n".join(lines[-limit:]))


def head_lines(path: Path, limit: int) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[:limit])


def slugify(name: str) -> str:
    """Same transform as init-session.sh: lowercase, non-alphanumerics to dashes, 40 chars."""
    lowered = name.lower()
    dashed = re.sub(r"[^a-z0-9]", "-", lowered)
    dashed = re.sub(r"-{2,}", "-", dashed).strip("-")
    return dashed[:40]


def _copy_templates(plan_dir: Path, templates_dir: Path, template: str) -> list[str]:
    created: list[str] = []
    for name in PLANNING_FILES:
        dest = plan_dir / name
        if dest.exists():
            continue
        if template != "default":
            prefixed = templates_dir / f"{template}_{name}"
            source = prefixed if prefixed.exists() else templates_dir / name
        else:
            source = templates_dir / name
        if source.exists():
            shutil.copy2(source, dest)
        else:
            dest.write_text("", encoding="utf-8")
        created.append(name)
    return created


def ensure_planning_files(project_dir: Path, template: str = "default") -> dict[str, Any]:
    """Legacy root-mode initialization: the three files in the project root."""
    skill_root = resolve_skill_dir(project_dir)
    created = _copy_templates(project_dir, skill_root / "templates", template)
    return {
        "project_dir": str(project_dir),
        "created": created,
        "existing": [name for name in PLANNING_FILES if (project_dir / name).exists()],
        "skill_root": str(skill_root),
    }


def write_attestation(project_dir: Path, plan_dir: Path) -> str:
    """Lock task_plan.md the way attest-plan.sh does: a lowercase SHA-256 hex line."""
    plan_file = plan_dir / "task_plan.md"
    digest = hashlib.sha256(plan_file.read_bytes()).hexdigest()
    target = attestation_path_for(project_dir, plan_dir)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(digest + "\n", encoding="ascii")
    os.replace(tmp, target)
    return digest


def apply_v3_mode(project_dir: Path, plan_dir: Path, mode: str) -> dict[str, Any]:
    """Write the v3 markers init-session.sh writes: counter reset, nonce, .mode, attestation."""
    if mode not in {"autonomous", "gated"}:
        raise ValueError(f"unknown mode: {mode!r} (expected autonomous or gated)")
    (plan_dir / ".stop_blocks").write_text("0\n", encoding="ascii")
    try:
        (plan_dir / ".gate_last_ledger").unlink()
    except FileNotFoundError:
        pass
    (plan_dir / ".nonce").write_text(secrets.token_hex(8) + "\n", encoding="ascii")
    marker = "autonomous gate\n" if mode == "gated" else "autonomous\n"
    (plan_dir / ".mode").write_text(marker, encoding="ascii")
    digest = write_attestation(project_dir, plan_dir)
    return {"marker": marker.strip(), "attestation": digest}


def init_plan(
    project_dir: Path,
    *,
    name: str = "",
    template: str = "default",
    mode: str = "",
) -> dict[str, Any]:
    """Create planning files in root mode or, with a name, in an isolated slug directory.

    Mirrors init-session.sh: a name creates ``.planning/YYYY-MM-DD-<slug>/``
    and records it in ``.planning/.active_plan``; ``mode`` (``autonomous`` or
    ``gated``) writes the v3 markers and attests the fresh plan. Existing
    files are never overwritten.
    """
    skill_root = resolve_skill_dir(project_dir)
    templates_dir = skill_root / "templates"
    if template not in {"default", "analytics"}:
        template = "default"
    normalized_mode = (mode or "").strip().lower()
    if normalized_mode in {"", "legacy", "none"}:
        normalized_mode = ""
    elif normalized_mode == "gate":
        normalized_mode = "gated"
    if normalized_mode not in {"", "autonomous", "gated"}:
        return {"ok": False, "error": f"unknown mode: {mode}", "project_dir": str(project_dir)}

    slug = slugify(name) if name else ""
    if slug:
        planning_root = project_dir / ".planning"
        planning_root.mkdir(parents=True, exist_ok=True)
        plan_id = f"{_dt.date.today().isoformat()}-{slug}"
        plan_dir = planning_root / plan_id
        plan_dir.mkdir(exist_ok=True)
        (planning_root / ".active_plan").write_text(plan_id + "\n", encoding="utf-8")
    else:
        plan_dir = project_dir
        plan_id = "root"

    created = _copy_templates(plan_dir, templates_dir, template)
    result: dict[str, Any] = {
        "ok": True,
        "project_dir": str(project_dir),
        "plan_dir": str(plan_dir),
        "plan_id": plan_id,
        "created": created,
        "existing": [n for n in PLANNING_FILES if (plan_dir / n).exists()],
        "skill_root": str(skill_root),
        "mode": normalized_mode or "legacy",
    }
    if normalized_mode:
        result.update(apply_v3_mode(project_dir, plan_dir, normalized_mode))
    return result


def phase_counts(task_plan: str) -> dict[str, int]:
    counts = {"complete": 0, "in_progress": 0, "pending": 0, "failed": 0, "total": 0}
    for line in task_plan.splitlines():
        normalized = line.strip().lower()
        if normalized.startswith("### phase"):
            counts["total"] += 1
        if "**status:**" not in normalized:
            continue
        if "complete" in normalized:
            counts["complete"] += 1
        elif "in_progress" in normalized:
            counts["in_progress"] += 1
        elif "failed" in normalized or "blocked" in normalized:
            counts["failed"] += 1
        elif "pending" in normalized:
            counts["pending"] += 1
    if counts["total"] == 0:
        for line in task_plan.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("|") and stripped.endswith("|")):
                continue
            cells = [cell.strip().lower() for cell in stripped.strip("|").split("|")]
            if len(cells) < 2 or cells[0] in {"phase", "error"} or set(cells[0]) == {"-"}:
                continue
            status = cells[1]
            if status in counts:
                counts[status] += 1
                counts["total"] += 1
        if counts["total"] == 0:
            for marker, key in (("[complete]", "complete"), ("[in_progress]", "in_progress"), ("[pending]", "pending")):
                counts[key] = task_plan.count(marker)
            counts["total"] = counts["complete"] + counts["in_progress"] + counts["pending"]
    return counts


def count_error_rows(task_plan: str) -> int:
    in_errors_section = False
    rows = 0
    for line in task_plan.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered.startswith("## errors encountered"):
            in_errors_section = True
            continue
        if in_errors_section and stripped.startswith("## "):
            break
        if not in_errors_section:
            continue
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = [cell.strip().lower() for cell in stripped.strip("|").split("|")]
        if not cells or cells[0] == "error" or set(cells[0]) == {"-"}:
            continue
        rows += 1
    return rows


def extract_current_phase(task_plan: str) -> str:
    lines = task_plan.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower() == "## current phase":
            for next_line in lines[idx + 1 :]:
                candidate = next_line.strip()
                if not candidate or candidate.startswith("<!--"):
                    continue
                if candidate.endswith("-->") or candidate.startswith("WHAT:") or candidate.startswith("WHY:") or candidate.startswith("EXAMPLE:"):
                    continue
                return candidate
            return stripped
    current_phase_name = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### Phase"):
            current_phase_name = stripped
        if "**status:**" in stripped.lower() and "in_progress" in stripped.lower() and current_phase_name:
            return current_phase_name
    if current_phase_name is None:
        for line in lines:
            stripped = line.strip()
            if not (stripped.startswith("|") and stripped.endswith("|")):
                continue
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if len(cells) < 2 or cells[0].lower() == "phase" or set(cells[0]) == {"-"}:
                continue
            if cells[1].lower() == "in_progress":
                return cells[0]
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### Phase"):
            return stripped
    return "No phase found"


def first_in_progress_phase(task_plan: str) -> str:
    """Heading of the first phase whose status is in_progress, '### ' stripped."""
    heading = ""
    for line in task_plan.splitlines():
        if line.startswith("### "):
            heading = line[4:]
            continue
        if "**Status:** in_progress" in line or "[in_progress]" in line:
            return heading
    return ""


def gate_counts(task_plan: str) -> dict[str, int]:
    """Phase counts the way check-complete.sh --gate counts them.

    ``total`` is the number of lines containing ``### Phase``. Each status is
    the per-field maximum of the primary ``**Status:** <state>`` form and the
    inline ``[<state>]`` marker form, so a plan that mixes both formats can
    never let an in_progress phase slip past the gate.
    """
    lines = task_plan.splitlines()
    total = sum(1 for line in lines if "### Phase" in line)
    counts: dict[str, int] = {"total": total}
    for state in ("complete", "in_progress", "pending"):
        primary = sum(1 for line in lines if f"**Status:** {state}" in line)
        inline = sum(1 for line in lines if f"[{state}]" in line)
        counts[state] = max(primary, inline)
    return counts


# The strictness-LOWERING mode tokens. Everything else raises strictness, and
# the root .mode floor (issue #238) treats the two halves in opposite
# directions, so a new token must be classified here deliberately.
_LOWERING_MODE_TOKENS = frozenset({"plan-guard-off"})


def _read_mode_file(directory: Path) -> list[str]:
    """Tokens of one directory's .mode; empty when absent or unreadable."""
    try:
        raw = (directory / ".mode").read_text(encoding="ascii", errors="strict")
    except (OSError, UnicodeError):
        return []
    return raw.split()


def mode_tokens(project_dir: Path, plan_dir: Path) -> list[str]:
    """Effective mode: the slug's .mode raised by the project root .mode FLOOR.

    A project makes attestation mandatory by committing a root .mode, which is
    a reviewed project setting. Reading only <plan-dir>/.mode let a slug plan
    silently exempt itself (issue #238): init_plan writes no .mode unless the
    operator asked for a mode, so creating a plan turned the project policy off
    in one agent-invocable call.

    Strictness-RAISING tokens (autonomous, gate, inject-smart) count when
    EITHER file carries them: a slug may go stricter than the project asked, it
    can never go looser. The strictness-LOWERING token (plan-guard-off) survives
    only when the slug carries it AND, where a root .mode exists, that file
    carries it too, so a slug cannot switch off a protection the project kept
    on.

    With no root .mode the result is exactly the slug's tokens, in the slug's
    own order, which is the invariant existing projects depend on. Root scope
    has no second source at all: <root>/.mode already IS the plan's .mode
    there.
    """
    slug = _read_mode_file(plan_dir)
    if plan_dir == project_dir:
        return slug
    # Presence of the file is what makes the root a policy statement, not the
    # tokens in it. A committed but empty root .mode still says "this project
    # reviewed its mode and asked for no relaxations", so a slug's
    # plan-guard-off does not survive it. Testing `not floor` instead would
    # treat an empty file like a missing one and diverge from inject-plan.sh,
    # which checks `[ -f "$ROOT_MODE_FILE" ]`.
    if not (project_dir / ".mode").is_file():
        return slug
    floor = _read_mode_file(project_dir)
    effective = [t for t in slug if t not in _LOWERING_MODE_TOKENS or t in floor]
    effective.extend(t for t in floor if t not in _LOWERING_MODE_TOKENS and t not in effective)
    return effective


def _read_counter(path: Path) -> int:
    try:
        raw = path.read_text(encoding="ascii", errors="strict").strip()
    except (OSError, UnicodeError):
        return 0
    return int(raw) if (raw.isascii() and raw.isdigit()) else 0


def ledger_line_count(plan_dir: Path) -> int:
    """Total lines across <plan-dir>/ledger-*.jsonl, 0 when none exist."""
    total = 0
    try:
        ledgers = sorted(plan_dir.glob("ledger-*.jsonl"))
    except OSError:
        return 0
    for ledger in ledgers:
        try:
            with ledger.open("rb") as handle:
                total += sum(1 for _ in handle)
        except OSError:
            continue
    return total


def evaluate_gate(project_dir: Path, plan_dir: Path) -> str | None:
    """The v3 completion gate decision table, in Python, for the Hermes pre_verify hook.

    Returns the continuation message when the stop must be held, otherwise
    None. Byte-for-byte the same guards as check-complete.sh --gate:

    1. The effective mode contains the ``gate`` token (explicit opt-in):
       <plan-dir>/.mode, or the project root .mode floor the slug cannot
       opt out of (issue #238), which is why the project root is a parameter.
    2. An in_progress phase exists; complete < total alone never blocks.
    3. (Hermes has no stop_hook_active field; the host bounds re-entry itself
       through agent.max_verify_nudges.)
    4. The block counter <plan-dir>/.stop_blocks is below the cap
       (PWF_GATE_CAP, default 20).
    5. The ledger advanced since the previous block; a stall allows the stop.

    A block increments the counter and records the ledger size, exactly as
    the shell gate does, so both routes share one state.
    """
    if os.environ.get("PLANNING_DISABLED", "") == "1":
        return None
    if "gate" not in mode_tokens(project_dir, plan_dir):
        return None
    try:
        task_plan = (plan_dir / "task_plan.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    counts = gate_counts(task_plan)
    if counts["total"] <= 0 or counts["in_progress"] <= 0:
        return None
    cap_raw = os.environ.get("PWF_GATE_CAP", "").strip()
    cap = int(cap_raw) if (cap_raw.isascii() and cap_raw.isdigit()) else 20
    blocks = _read_counter(plan_dir / ".stop_blocks")
    ledger_prev = _read_counter(plan_dir / ".gate_last_ledger")
    ledger_now = ledger_line_count(plan_dir)
    if blocks >= cap:
        return None
    if blocks > 0 and ledger_now == ledger_prev:
        return None
    phase_name = first_in_progress_phase(task_plan) or "unknown phase"
    phase_name = _CONTROL_CHARS.sub(" ", phase_name)
    new_blocks = blocks + 1
    try:
        (plan_dir / ".stop_blocks").write_text(f"{new_blocks}\n", encoding="ascii")
        (plan_dir / ".gate_last_ledger").write_text(f"{ledger_now}\n", encoding="ascii")
    except OSError:
        pass
    return (
        "[planning-with-files] Gated plan incomplete: phase '"
        f"{phase_name}' is in_progress ({counts['complete']}/{counts['total']} complete, "
        f"gate block {new_blocks}/{cap}). Finish or update the plan, then stop."
    )


def summarize_status(project_dir: Path) -> dict[str, Any]:
    plan_dir = resolve_plan_dir(project_dir)
    if plan_dir is None:
        message = (
            MULTIPLE_PLANS_MESSAGE
            if multiple_plans_require_selector(project_dir)
            else "No planning files found. Run planning_with_files_init first."
        )
        return {
            "exists": False,
            "message": message,
            "project_dir": str(project_dir),
            "files": {
                "task_plan.md": False,
                "findings.md": (project_dir / "findings.md").exists(),
                "progress.md": (project_dir / "progress.md").exists(),
            },
        }
    task_plan_path = plan_dir / "task_plan.md"
    findings_path = plan_dir / "findings.md"
    progress_path = plan_dir / "progress.md"
    task_plan = task_plan_path.read_text(encoding="utf-8")
    counts = phase_counts(task_plan)
    tokens = mode_tokens(project_dir, plan_dir)
    return {
        "exists": True,
        "project_dir": str(project_dir),
        "plan_dir": str(plan_dir),
        "plan_id": plan_id_for(project_dir, plan_dir),
        "mode": " ".join(tokens) if tokens else "legacy",
        "attested": attestation_path_for(project_dir, plan_dir).is_file(),
        "current_phase": extract_current_phase(task_plan),
        "counts": counts,
        "files": {
            "task_plan.md": task_plan_path.exists(),
            "findings.md": findings_path.exists(),
            "progress.md": progress_path.exists(),
        },
        "recent_progress": tail_lines(progress_path, PROGRESS_TAIL_LINES),
        "plan_preview": head_lines(task_plan_path, PLAN_PREVIEW_LINES),
        "errors_logged": count_error_rows(task_plan),
    }
