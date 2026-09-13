"""Exercise plan listing through the real shell and PowerShell entry points.

Listing is a read-only inventory of the current directory's named plans. Phase
counts describe actual phase sections, and filesystem links cannot expose plans
outside that inventory. PowerShell is invoked with -File, as documented for users.
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
RUNTIMES = (
    ("sh", shutil.which("sh")),
    ("powershell", shutil.which("powershell.exe") or shutil.which("powershell")),
    ("pwsh", shutil.which("pwsh.exe") or shutil.which("pwsh")),
)


@pytest.fixture(params=RUNTIMES, ids=lambda runtime: runtime[0])
def runtime(request):
    name, executable = request.param
    if executable is None:
        pytest.skip(f"{name} is not installed")
    return name, executable


def run_selector(runtime, root: Path, *args: str, env_extra=None):
    name, executable = runtime
    if name == "sh":
        command = [executable, str(SCRIPTS / "set-active-plan.sh"), *args]
    else:
        command = [
            executable, "-NoLogo", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File",
            str(SCRIPTS / "set-active-plan.ps1"), *args,
        ]
    env = os.environ.copy()
    for key in ("PLAN_ID", "PWF_PLAN_ROOT", "PLANNING_DISABLED"):
        env.pop(key, None)
    env.update(env_extra or {})
    return subprocess.run(
        command, cwd=root, env=env, text=True, encoding="utf-8",
        errors="replace", capture_output=True, timeout=60, check=False,
    )


def listed(runtime, root: Path, option="--list", **kwargs) -> str:
    result = run_selector(runtime, root, option, **kwargs)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not result.stderr.strip(), result.stderr
    return result.stdout


def rejected_root_listing(runtime, root: Path) -> str:
    result = run_selector(runtime, root, "--list")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "outside the project" in result.stderr, result.stdout + result.stderr
    return result.stdout


def plan(root: Path, slug: str, text: str = "") -> Path:
    directory = root / ".planning" / slug
    directory.mkdir(parents=True)
    path = directory / "task_plan.md"
    path.write_text(text, encoding="utf-8")
    return path


def row(output: str, slug: str) -> str:
    matches = [line for line in output.splitlines()
               if re.match(r"^- " + re.escape(slug) + r"(?:\s|$)", line)]
    assert len(matches) == 1, output
    return matches[0]


def assert_counts(output: str, slug: str, complete: int, total: int,
                  in_progress: int = 0, pending: int = 0) -> None:
    expected = f"{complete}/{total} complete, {in_progress} in_progress, {pending} pending"
    assert expected in row(output, slug), output


@pytest.mark.parametrize("option", ["--list", "-l"])
def test_list_aliases_work_through_file_invocation(runtime, tmp_path, option):
    plan(tmp_path, "alpha", "### Phase 1: Inspect [complete]\n")
    assert_counts(listed(runtime, tmp_path, option), "alpha", 1, 1)


def test_powershell_native_list_switch(runtime, tmp_path):
    if runtime[0] == "sh":
        pytest.skip("-List is the native PowerShell spelling")
    plan(tmp_path, "alpha", "### Phase 1: Inspect [complete]\n")
    assert_counts(listed(runtime, tmp_path, "-List"), "alpha", 1, 1)


def test_mixed_inline_and_status_formats_count_each_phase(runtime, tmp_path):
    plan(tmp_path, "mixed", """# Task plan
### Phase 1: Discover [complete]
### Phase 2: Implement
**Status:** complete
### Phase 3: Verify [complete]
**Status:** complete
### Phase 4: Document [in_progress]
### Phase 5: Package
**Status:** pending
### Phase 6: Release [pending]
**Status:** pending
""")
    assert_counts(listed(runtime, tmp_path), "mixed", 3, 6, 1, 2)


def test_duplicate_status_markers_count_one_phase(runtime, tmp_path):
    plan(tmp_path, "duplicates", """### Phase 1: Work [complete] [complete]
**Status:** complete
**Status:** complete
### Phase 2: Next [pending] [pending]
**Status:** pending
**Status:** pending
""")
    assert_counts(listed(runtime, tmp_path), "duplicates", 1, 2, 0, 1)


def test_first_recognized_status_line_overrides_heading_status(runtime, tmp_path):
    plan(tmp_path, "updated", """### Phase 1: Work [pending]
**Status:** unknown
**Status:** complete
**Status:** pending
### Phase 2: Continue [complete]
**Status:** in_progress
""")
    assert_counts(listed(runtime, tmp_path), "updated", 1, 2, 1, 0)


def test_non_phase_prose_and_fenced_examples_do_not_count(runtime, tmp_path):
    plan(tmp_path, "examples", """# Task plan
**Status:** complete
An unrelated [pending] reference.
```markdown
### Phase 99: Example [complete]
**Status:** complete
```
### Phase 1: Real work [in_progress]
A prose reference to [complete] does not finish this phase.
~~~markdown
### Phase 98: Another example [pending]
**Status:** pending
~~~
### Phase 2: No status yet
````markdown
### Phase 97: Nested example [complete]
```
**Status:** complete
````
## Notes
**Status:** complete
### An unrelated heading
**Status:** pending
""")
    assert_counts(listed(runtime, tmp_path), "examples", 0, 2, 1, 0)


@pytest.mark.parametrize("example", [
    "\n    **Status:** complete\n",
    "###\n**Status:** complete\n",
], ids=["indented-code", "empty-section-heading"])
def test_status_outside_phase_text_does_not_override_inline_status(runtime, tmp_path, example):
    plan(tmp_path, "pending", "### Phase 1: Work [pending]\n" + example)
    assert_counts(listed(runtime, tmp_path), "pending", 0, 1, 0, 1)


def test_empty_plan_has_zero_counts(runtime, tmp_path):
    plan(tmp_path, "empty")
    assert_counts(listed(runtime, tmp_path), "empty", 0, 0)


@pytest.mark.parametrize("language", ["en", "ar", "de", "es", "zh", "zht"])
def test_real_shipped_templates_have_five_phase_counts(runtime, tmp_path, language):
    if language == "en":
        source = REPO_ROOT / "templates" / "task_plan.md"
    else:
        source = (REPO_ROOT / "skills" / "i18n" / f"planning-with-files-{language}"
                  / "templates" / "task_plan.md")
    plan(tmp_path, f"template-{language}", source.read_text(encoding="utf-8"))
    assert_counts(listed(runtime, tmp_path), f"template-{language}", 0, 5, 1, 4)


def test_missing_planning_directory_is_read_only(runtime, tmp_path):
    output = listed(runtime, tmp_path)
    assert "No planning directory found" in output
    assert not (tmp_path / ".planning").exists()


def test_empty_planning_directory_and_pointer_are_read_only(runtime, tmp_path):
    planning = tmp_path / ".planning"
    planning.mkdir()
    pointer = planning / ".active_plan"
    pointer.write_bytes(b"")
    output = listed(runtime, tmp_path)
    assert "No named plans found" in output
    assert pointer.read_bytes() == b""
    assert sorted(path.name for path in planning.iterdir()) == [".active_plan"]


@pytest.mark.parametrize("pointer_bytes,active", [
    (b"alpha\r\n", True), (b"missing\n", False),
    (b"../alpha\n", False), (b"", False),
])
def test_listing_preserves_read_only_pointer(runtime, tmp_path, pointer_bytes, active):
    plan_file = plan(tmp_path, "alpha", "### Phase 1: Work [pending]\n")
    pointer = tmp_path / ".planning" / ".active_plan"
    pointer.write_bytes(pointer_bytes)
    before_plan = plan_file.read_bytes()
    before_mtime = pointer.stat().st_mtime_ns
    original_mode = pointer.stat().st_mode
    pointer.chmod(stat.S_IREAD)
    try:
        output = listed(runtime, tmp_path)
        assert ("[active]" in row(output, "alpha")) is active
        assert pointer.read_bytes() == pointer_bytes
        assert pointer.stat().st_mtime_ns == before_mtime
        assert plan_file.read_bytes() == before_plan
    finally:
        pointer.chmod(original_mode)


def test_listing_does_not_create_a_pointer(runtime, tmp_path):
    plan(tmp_path, "alpha")
    listed(runtime, tmp_path)
    assert not (tmp_path / ".planning" / ".active_plan").exists()


def test_inventory_accepts_safe_slugs_and_requires_a_plan_file(runtime, tmp_path):
    accepted = ("Alpha", "9-work", "with.dot", "with_under_score", "_legacy")
    rejected = (".hidden", "-option", "space name")
    for slug in (*accepted, *rejected):
        plan(tmp_path, slug)
    (tmp_path / ".planning" / "no-plan").mkdir()
    (tmp_path / ".planning" / "file-only").write_text("not a directory")
    output = listed(runtime, tmp_path)
    for slug in accepted:
        assert_counts(output, slug, 0, 0)
    for slug in (*rejected, "no-plan", "file-only"):
        assert f"- {slug}" not in output


def test_listing_uses_cwd_even_when_a_session_selector_is_set(runtime, tmp_path):
    project = tmp_path / "project"
    external = tmp_path / "external"
    plan(project, "local-plan")
    plan(external, "external-plan")
    output = listed(runtime, project, env_extra={
        "PWF_PLAN_ROOT": str(external), "PLAN_ID": "external-plan",
    })
    assert_counts(output, "local-plan", 0, 0)
    assert "external-plan" not in output


def test_literal_workspace_path_characters(runtime, tmp_path):
    project = tmp_path / "workspace [sample]"
    plan(project, "alpha")
    assert_counts(listed(runtime, project), "alpha", 0, 0)


def make_symlink(link: Path, target: Path, directory: bool) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"filesystem symlinks unavailable: {error}")


def test_directory_symlink_cannot_list_an_external_plan(runtime, tmp_path):
    project = tmp_path / "project"
    external = tmp_path / "external"
    plan(project, "safe")
    external_file = plan(external, "private", "### Phase 1 [complete]\n")
    link = project / ".planning" / "escape"
    make_symlink(link, external_file.parent, directory=True)
    output = listed(runtime, project)
    assert_counts(output, "safe", 0, 0)
    assert "escape" not in output


def test_plan_file_symlink_cannot_read_an_external_plan(runtime, tmp_path):
    project = tmp_path / "project"
    plan(project, "safe")
    external_file = tmp_path / "private.md"
    external_file.write_text("### Phase 1 [complete]\n", encoding="utf-8")
    escaped_plan = project / ".planning" / "escape"
    escaped_plan.mkdir()
    make_symlink(escaped_plan / "task_plan.md", external_file, directory=False)
    output = listed(runtime, project)
    assert_counts(output, "safe", 0, 0)
    assert "escape" not in output


def test_pointer_symlink_does_not_mark_a_local_plan_active(runtime, tmp_path):
    project = tmp_path / "project"
    plan(project, "safe")
    external_pointer = tmp_path / "private-pointer"
    external_pointer.write_text("safe\n", encoding="utf-8")
    make_symlink(project / ".planning" / ".active_plan", external_pointer, directory=False)
    output = listed(runtime, project)
    assert "[active]" not in row(output, "safe")
    assert external_pointer.read_text(encoding="utf-8") == "safe\n"


def test_planning_root_symlink_cannot_list_external_plans(runtime, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    external_file = plan(tmp_path / "external", "private", "### Phase 1 [complete]\n")
    make_symlink(project / ".planning", external_file.parent.parent, directory=True)
    output = rejected_root_listing(runtime, project)
    assert "private" not in output
    assert "1/1" not in output


def make_junction(link: Path, target: Path) -> None:
    if os.name != "nt":
        pytest.skip("Windows junction regression")
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if powershell is None:
        pytest.skip("junction setup needs PowerShell")
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    command = (
        "$ErrorActionPreference = 'Stop'; "
        f"New-Item -ItemType Junction -Path {quote(link)} -Target {quote(target)} | Out-Null"
    )
    result = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("link_root", [False, True], ids=["plan-directory", "planning-root"])
def test_windows_junction_cannot_list_external_plans(runtime, tmp_path, link_root):
    project = tmp_path / "project"
    external_file = plan(tmp_path / "external", "private", "### Phase 1 [complete]\n")
    if link_root:
        project.mkdir()
        link = project / ".planning"
        target = external_file.parent.parent
    else:
        plan(project, "safe")
        link = project / ".planning" / "escape"
        target = external_file.parent
    make_junction(link, target)
    try:
        output = (rejected_root_listing(runtime, project) if link_root
                  else listed(runtime, project))
        assert "private" not in output
        assert "escape" not in output
        assert "1/1" not in output
        if not link_root:
            assert_counts(output, "safe", 0, 0)
    finally:
        # Remove only the junction created above, never recurse into its target.
        link.rmdir()
    assert external_file.is_file()


def test_existing_set_and_show_semantics(runtime, tmp_path):
    initial = run_selector(runtime, tmp_path)
    assert initial.returncode == 0, initial.stderr
    assert "No active plan set" in initial.stdout
    # Setting an existing directory does not require task_plan.md.
    (tmp_path / ".planning" / "selected").mkdir(parents=True)
    selected = run_selector(runtime, tmp_path, "selected")
    assert selected.returncode == 0, selected.stderr
    pointer = tmp_path / ".planning" / ".active_plan"
    assert pointer.read_bytes().rstrip(b"\r\n") == b"selected"
    shown = run_selector(runtime, tmp_path)
    assert shown.returncode == 0, shown.stderr
    assert "Active plan: selected" in shown.stdout
    pointer.write_bytes(b"stale\n")
    stale = run_selector(runtime, tmp_path)
    assert stale.returncode == 0, stale.stderr
    assert "stale pointer" in stale.stdout
    missing = run_selector(runtime, tmp_path, "absent")
    assert missing.returncode != 0
    assert "not found" in missing.stderr
    assert pointer.read_bytes() == b"stale\n"


def test_read_only_pointer_never_reports_success_without_switching(runtime, tmp_path):
    plan(tmp_path, "selected")
    pointer = tmp_path / ".planning" / ".active_plan"
    before = b"previous\n"
    pointer.write_bytes(before)
    original_mode = pointer.stat().st_mode
    pointer.chmod(stat.S_IREAD)
    try:
        result = run_selector(runtime, tmp_path, "selected")
        if result.returncode == 0:
            # POSIX can atomically replace a read-only file when its directory
            # is writable; Windows may instead refuse. Neither may lie.
            assert pointer.read_bytes().rstrip(b"\r\n") == b"selected", result.stdout + result.stderr
            assert "Active plan set to: selected" in result.stdout
        else:
            assert pointer.read_bytes() == before
            assert "Active plan set to" not in result.stdout
    finally:
        pointer.chmod(original_mode)


def test_switching_a_hardlinked_pointer_does_not_overwrite_external_file(runtime, tmp_path):
    project = tmp_path / "project"
    plan(project, "selected")
    external = tmp_path / "external-canary"
    before = b"private-file-contents\n"
    external.write_bytes(before)
    pointer = project / ".planning" / ".active_plan"
    try:
        os.link(external, pointer)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"filesystem hardlinks unavailable: {error}")
    result = run_selector(runtime, project, "selected")
    assert external.read_bytes() == before, result.stdout + result.stderr
    assert result.returncode == 0, result.stdout + result.stderr
    assert pointer.read_bytes().rstrip(b"\r\n") == b"selected"
