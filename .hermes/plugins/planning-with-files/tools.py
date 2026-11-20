import json
import os
import shutil
import subprocess
from pathlib import Path

from .paths import (
    MULTIPLE_PLANS_MESSAGE,
    effective_project_root,
    multiple_plans_require_selector,
    normalize_cwd,
    plan_id_for,
    resolve_plan_dir,
    resolve_skill_dir,
    slug_is_valid,
)
from .context_frame import _assert_no_reparse_components, read_regular_bytes
from .planning_files import init_plan, phase_counts, summarize_status
from .session_binding import bind, binding_root, clear, current_binding, current_session_id


def _project_dir(cwd: str = "") -> Path | None:
    binding = current_binding()
    if cwd and binding is not None:
        selected = binding_root(binding)
        if selected is None or normalize_cwd(cwd) != selected:
            return None
    if not cwd:
        try:
            from agent.runtime_cwd import resolve_agent_cwd

            runtime = resolve_agent_cwd()
            if isinstance(runtime, Path):
                cwd = str(runtime)
        except (ImportError, OSError, RuntimeError, ValueError):
            pass
    project = effective_project_root(normalize_cwd(cwd))
    if project is not None and binding is not None:
        if validated_plan_path(project / ".planning" / binding.plan_id) is None:
            return None
    if project is not None and current_session_id():
        from .hooks import ATTACH_DETACHED, _session_attachment

        if _session_attachment(project, current_session_id()) == ATTACH_DETACHED:
            return None
    return project


def _project_error() -> str:
    bound = current_binding()
    if bound is not None:
        return (
            f"This session selects project {bound.project_dir}; the selection is invalid, "
            "detached, or conflicts with the supplied cwd. Use planning_with_files_select "
            "to change plans, or planning_with_files_select(plan='') to clear the selection."
        )
    return "The selected project root is invalid or this session is detached."


def validated_plan_path(path: Path) -> tuple[Path, str] | None:
    """An existing, no-link <root>/.planning/<slug> directory with a plan."""
    if (not path.is_absolute() or str(path).startswith(("\\\\", "//"))
            or path.parent.name != ".planning" or not slug_is_valid(path.name)):
        return None
    try:
        _assert_no_reparse_components(path)
        root = path.parent.parent.resolve(strict=True)
        target = resolve_plan_dir(root, plan_id=path.name, explicit=True)
        if target is None:
            return None
        read_regular_bytes(target / "task_plan.md")
        return root, path.name
    except (OSError, RuntimeError, ValueError):
        return None


def planning_with_files_select(plan: str = "", cwd: str = "") -> str:
    """Bind a Hermes session to a named plan, or clear with an empty selector."""
    if not current_session_id():
        return json.dumps({"ok": False, "error": "Hermes did not supply a session identity."})
    if not plan:
        error = clear()
        return json.dumps({"ok": not error, **({"error": error} if error else {"selected": False})})
    requested = Path(plan).expanduser()
    candidates: list[Path] = []
    if requested.is_absolute():
        candidates = [requested]
    elif slug_is_valid(plan):
        # Search only known project roots, never the user's drive or home.
        # An explicit cwd narrows the search; an absolute plan path disambiguates.
        if cwd:
            roots = [normalize_cwd(cwd)]
        else:
            roots = []
            try:
                from agent.runtime_cwd import resolve_agent_cwd

                runtime = resolve_agent_cwd()
                if isinstance(runtime, Path):
                    roots.append(runtime)
            except (ImportError, OSError, RuntimeError, ValueError):
                pass
            bound = current_binding()
            if bound is not None and bound.project_dir is not None:
                roots.append(bound.project_dir)
            pin = os.environ.get("PWF_PLAN_ROOT", "").strip()
            if pin and Path(pin).is_absolute():
                roots.append(Path(pin))
        candidates = [root / ".planning" / plan for root in roots]
    valid: dict[tuple[Path, str], Path] = {}
    for candidate in candidates:
        selected = validated_plan_path(candidate)
        if selected is not None:
            valid[selected] = candidate
    if len(valid) != 1:
        return json.dumps({
            "ok": False,
            "error": "Plan selector is ambiguous; use an absolute plan directory." if valid else "No valid plan matches the selector.",
            "candidates": [str(path) for path in valid.values()],
        })
    (project, slug), _path = next(iter(valid.items()))
    from .hooks import ATTACH_DETACHED, _session_attachment

    if _session_attachment(project, current_session_id()) == ATTACH_DETACHED:
        return json.dumps({"ok": False, "error": "This Hermes session is not attached to the selected project."})
    error = bind(project, slug)
    return json.dumps({"ok": not error, **({"error": error} if error else {
        "selected": True, "project_dir": str(project), "plan_dir": str(project / ".planning" / slug), "plan_id": slug,
    })})


def planning_with_files_init(
    template: str = "default",
    cwd: str = "",
    name: str = "",
    mode: str = "",
) -> str:
    project_dir = _project_dir(cwd)
    if project_dir is None:
        return json.dumps({"ok": False, "error": _project_error()})
    result = init_plan(project_dir, name=name or "", template=template or "default", mode=mode or "")
    if result.get("ok") and name and result.get("plan_id") != "root" and current_session_id():
        target = validated_plan_path(Path(result["plan_dir"]))
        if target is not None:
            error = bind(*target)
            result["session_bound"] = not error
            if error:
                result["binding_error"] = error
    return json.dumps(result, ensure_ascii=False)


def planning_with_files_status(cwd: str = "") -> str:
    project_dir = _project_dir(cwd)
    if project_dir is None:
        return json.dumps({"exists": False, "message": _project_error()})
    result = summarize_status(project_dir)
    return json.dumps(result, ensure_ascii=False)


def _python_completion_report(plan_file: Path) -> dict:
    """Fallback for hosts without ``sh`` (native Windows Hermes Desktop)."""
    try:
        counts = phase_counts(plan_file.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return {"ok": False, "returncode": 1, "stdout": "", "stderr": "Plan read error.",
                "complete": False, "route": "python"}
    if counts.get("invalid_structure"):
        return {"ok": True, "returncode": 0,
                "stdout": "[planning-with-files] Plan format error: phase completion unavailable.",
                "stderr": "", "complete": False, "route": "python"}
    complete = counts["total"] > 0 and counts["complete"] >= counts["total"]
    if complete:
        stdout = (
            f"[planning-with-files] ALL PHASES COMPLETE ({counts['complete']}/{counts['total']}). "
            "If the user has additional work, add new phases to task_plan.md before starting."
        )
    else:
        stdout = (
            f"[planning-with-files] Plan incomplete: {counts['complete']}/{counts['total']} phases complete, "
            f"{counts['in_progress']} in_progress."
        )
    return {"ok": True, "returncode": 0, "stdout": stdout, "stderr": "", "complete": complete, "route": "python"}


def planning_with_files_check_complete(cwd: str = "") -> str:
    project_dir = _project_dir(cwd)
    if project_dir is None:
        return json.dumps({"ok": False, "complete": False, "error": _project_error()})
    skill_root = resolve_skill_dir(project_dir)
    plan_dir = resolve_plan_dir(project_dir)
    if plan_dir is None:
        return json.dumps(
            {
                "ok": False,
                "error": (
                    MULTIPLE_PLANS_MESSAGE
                    if multiple_plans_require_selector(project_dir)
                    else "No task_plan.md found. Run planning_with_files_init first."
                ),
                "skill_root": str(skill_root),
                "complete": False,
            },
            ensure_ascii=False,
        )
    plan_file = plan_dir / "task_plan.md"
    script = skill_root / "scripts" / "check-complete.sh"
    shell = shutil.which("sh")
    if not script.exists() or shell is None:
        payload = _python_completion_report(plan_file)
        payload.update({"skill_root": str(skill_root), "plan_dir": str(plan_dir), "plan_id": plan_id_for(project_dir, plan_dir)})
        if not script.exists():
            payload["note"] = f"Missing script: {script}; evaluated in Python."
        return json.dumps(payload, ensure_ascii=False)
    try:
        completed = subprocess.run(
            [shell, str(script), str(plan_file)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            cwd=str(project_dir),
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        payload = _python_completion_report(plan_file)
        payload.update({"skill_root": str(skill_root), "plan_dir": str(plan_dir), "plan_id": plan_id_for(project_dir, plan_dir)})
        payload["note"] = f"check-complete.sh did not finish ({exc.__class__.__name__}); evaluated in Python."
        return json.dumps(payload, ensure_ascii=False)
    stdout = completed.stdout.strip()
    return json.dumps(
        {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": stdout,
            "stderr": completed.stderr.strip(),
            "skill_root": str(skill_root),
            "plan_dir": str(plan_dir),
            "plan_id": plan_id_for(project_dir, plan_dir),
            "complete": "ALL PHASES COMPLETE" in stdout,
            "route": "sh",
        },
        ensure_ascii=False,
    )
