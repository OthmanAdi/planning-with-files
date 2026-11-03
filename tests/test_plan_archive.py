"""Archive and restore named plans through the shipped shell and PowerShell commands (#355).

Archiving renames `.planning/<id>` to `.planning/.archive/<id>`; restoring renames
it back. Both routes preview by default, change nothing on any refusal, never
copy and never delete. Every test runs the real entry points on each runtime
present (sh always; Windows PowerShell 5.1 and pwsh when installed).
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from test_plan_listing import (RUNTIMES, SCRIPTS, flat, make_junction, make_symlink,
                               plan, run_selector, runtime, share_lock_blocks_reads)


def is_link(path: Path) -> bool:
    return path.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(path))


def tree(root: Path) -> dict:
    """Every directory, and the bytes and mtime of every file, without following links."""
    state = {}
    for current, dirs, files in os.walk(root):
        here = Path(current)
        for name in list(dirs):
            child = here / name
            state[str(child.relative_to(root))] = "link" if is_link(child) else "dir"
            if is_link(child):
                dirs.remove(name)
        for name in files:
            child = here / name
            if is_link(child):
                state[str(child.relative_to(root))] = "link"
                continue
            state[str(child.relative_to(root))] = (hashlib.sha256(child.read_bytes()).hexdigest(),
                                                   child.stat().st_mtime_ns)
    return state


def contents(directory: Path) -> dict:
    """Relative file paths with bytes and mtimes: a rename must keep all of them."""
    return {key: value for key, value in tree(directory).items() if value not in ("dir", "link")}


def fixture(root: Path, *ids: str, pointer: bytes | None = None) -> None:
    for index, plan_id in enumerate(ids):
        directory = plan(root, plan_id, "### Phase 1: Work [complete]\n" if index == 0
                         else "### Phase 1: Work [pending]\n").parent
        (directory / "findings.md").write_text("findings " + plan_id, encoding="utf-8")
        (directory / "progress.md").write_text("progress " + plan_id, encoding="utf-8")
        (directory / ".attestation").write_text("sha256:0123abcd\n", encoding="utf-8")
        (directory / ".mode").write_text("gated\n", encoding="utf-8")
        (directory / "artifacts").mkdir()
        (directory / "artifacts" / "note.bin").write_bytes(b"\x00\x01\xff binary")
    if pointer is not None:
        (root / ".planning" / ".active_plan").write_bytes(pointer)


def ok(result) -> str:
    assert result.returncode == 0, result.stdout + result.stderr
    assert not result.stderr.strip(), result.stderr
    return result.stdout


def refused(result, root: Path, before: dict) -> str:
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Error" in flat(result.stderr), result.stderr
    assert not result.stdout.strip(), result.stdout
    assert tree(root) == before
    return flat(result.stderr)


def same_path(line: str, suffix: str) -> bool:
    return line.replace("\\", "/").rstrip("/").endswith(suffix)


def resolve(runtime, root: Path, *args: str, env_extra=None) -> str:
    name, executable = runtime
    if name == "sh":
        command = [executable, str(SCRIPTS / "resolve-plan-dir.sh"), *args]
    else:
        command = [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                   "Bypass", "-File", str(SCRIPTS / "resolve-plan-dir.ps1"), *args]
    env = os.environ.copy()
    for key in ("PLAN_ID", "PWF_PLAN_ROOT", "PLANNING_DISABLED"):
        env.pop(key, None)
    env.update(env_extra or {})
    result = subprocess.run(command, cwd=root, env=env, text=True, encoding="utf-8",
                            errors="replace", capture_output=True, timeout=60, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def test_preview_changes_nothing(runtime, tmp_path):
    fixture(tmp_path, "alpha", "beta", pointer=b"alpha\n")
    before = tree(tmp_path)
    output = ok(run_selector(runtime, tmp_path, "--archive", "beta"))
    lines = output.splitlines()
    assert lines[0] == "Would archive plan: beta (0/1 complete, 0 in_progress, 1 pending)"
    assert lines[1].startswith("  from: ") and same_path(lines[1], "/.planning/beta")
    assert lines[2].startswith("  to:   ") and same_path(lines[2], "/.planning/.archive/beta")
    assert "  Note: not all phases are complete." in lines
    assert "will be cleared" not in output
    assert "The plan is moved, never deleted. Restore with:" in output
    assert lines[-1] == "Run again with --yes to apply." or lines[-1] == "Run again with -Yes to apply."
    assert tree(tmp_path) == before
    assert not (tmp_path / ".planning" / ".archive").exists()

    output = ok(run_selector(runtime, tmp_path, "--archive", "alpha"))
    assert output.splitlines()[0] == "Would archive plan: alpha (1/1 complete, 0 in_progress, 0 pending)"
    assert "Note:" not in output
    assert "The shared default (.active_plan) names this plan and will be cleared." in output
    assert tree(tmp_path) == before


def test_yes_renames_the_whole_plan_tree(runtime, tmp_path):
    fixture(tmp_path, "alpha", "beta")
    original = contents(tmp_path / ".planning" / "alpha")
    other = contents(tmp_path / ".planning" / "beta")
    assert {".attestation", ".mode", "artifacts/note.bin".replace("/", os.sep)} <= set(original)
    output = ok(run_selector(runtime, tmp_path, "--archive", "alpha", "--yes"))
    lines = output.splitlines()
    assert lines[0] == "Archived plan: alpha"
    assert lines[1].startswith("  to: ") and same_path(lines[1], "/.planning/.archive/alpha")
    assert "Restore with:" in lines[-1] and "alpha" in lines[-1]
    assert "Cleared" not in output
    assert not (tmp_path / ".planning" / "alpha").exists()
    assert contents(tmp_path / ".planning" / ".archive" / "alpha") == original
    assert contents(tmp_path / ".planning" / "beta") == other
    # One named plan is left, so automatic selection works again on this route.
    assert same_path(resolve(runtime, tmp_path), "/.planning/beta")
    # A session still pinned to the archived plan resolves to nothing, never to beta.
    assert resolve(runtime, tmp_path, env_extra={"PLAN_ID": "alpha"}) == ""


def test_restore_round_trip_is_byte_identical(runtime, tmp_path):
    fixture(tmp_path, "alpha")
    original = contents(tmp_path / ".planning" / "alpha")
    ok(run_selector(runtime, tmp_path, "--archive", "alpha", "--yes"))
    archived = tree(tmp_path)
    preview = ok(run_selector(runtime, tmp_path, "--restore", "alpha"))
    assert preview.splitlines()[0] == "Would restore plan: alpha (1/1 complete, 0 in_progress, 0 pending)"
    assert same_path(preview.splitlines()[1], "/.planning/.archive/alpha")
    assert same_path(preview.splitlines()[2], "/.planning/alpha")
    assert "The plan is moved, never deleted." in preview
    assert tree(tmp_path) == archived
    output = ok(run_selector(runtime, tmp_path, "--restore", "alpha", "--yes"))
    lines = output.splitlines()
    assert lines[0] == "Restored plan: alpha"
    assert same_path(lines[1], "/.planning/alpha")
    assert lines[-1].startswith("To make it the default:") and "PLAN_ID" in lines[-1] and "alpha" in lines[-1]
    assert contents(tmp_path / ".planning" / "alpha") == original
    assert not (tmp_path / ".planning" / ".archive" / "alpha").exists()
    assert same_path(resolve(runtime, tmp_path), "/.planning/alpha")


def link_directory(link: Path, target: Path) -> None:
    if os.name == "nt":
        make_junction(link, target)
    else:
        make_symlink(link, target, directory=True)


REFUSALS = {
    "slug-dotdot": ("--archive", ".."),
    "slug-dot-prefixed": ("--archive", ".x"),
    "slug-slash": ("--archive", "a/b"),
    "missing-plan": ("--archive", "ghost"),
    "no-plan-file": ("--archive", "bare"),
    "plan-is-symlink": ("--archive", "linked"),
    "plan-is-junction": ("--archive", "linked"),
    "archive-dir-is-link": ("--archive", "alpha"),
    "destination-exists": ("--archive", "alpha"),
    "destination-is-file": ("--archive", "alpha"),
    "plan-id-pinned": ("--archive", "alpha"),
    "restore-target-exists": ("--restore", "alpha"),
    "restore-missing": ("--restore", "ghost"),
    "restore-without-archive-dir": ("--restore", "alpha"),
    "no-planning-dir": ("--archive", "alpha"),
    "planning-root-is-link": ("--archive", "alpha"),
}


@pytest.mark.parametrize("case", sorted(REFUSALS))
@pytest.mark.parametrize("apply", [False, True], ids=["preview", "yes"])
def test_refusals_change_nothing(runtime, tmp_path, case, apply):
    project = tmp_path / "project"
    external = tmp_path / "external"
    env_extra = None
    if case == "no-planning-dir":
        project.mkdir()
    elif case == "planning-root-is-link":
        project.mkdir()
        plan(external, "alpha")
        link_directory(project / ".planning", external / ".planning")
    else:
        fixture(project, "alpha")
    planning = project / ".planning"
    if case == "no-plan-file":
        (planning / "bare").mkdir()
    elif case == "plan-is-symlink":
        make_symlink(planning / "linked", plan(external, "alpha").parent, directory=True)
    elif case == "plan-is-junction":
        make_junction(planning / "linked", plan(external, "alpha").parent)
    elif case == "archive-dir-is-link":
        external.mkdir()
        link_directory(planning / ".archive", external)
    elif case == "destination-exists":
        (planning / ".archive" / "alpha").mkdir(parents=True)
        (planning / ".archive" / "alpha" / "task_plan.md").write_text("old", encoding="utf-8")
    elif case == "destination-is-file":
        (planning / ".archive").mkdir()
        (planning / ".archive" / "alpha").write_text("not a directory", encoding="utf-8")
    elif case == "plan-id-pinned":
        env_extra = {"PLAN_ID": "alpha"}
    elif case in ("restore-target-exists", "restore-missing"):
        (planning / ".archive" / "alpha").mkdir(parents=True)
        (planning / ".archive" / "alpha" / "task_plan.md").write_text("archived", encoding="utf-8")
    before = tree(tmp_path)
    args = REFUSALS[case] + (("--yes",) if apply else ())
    message = refused(run_selector(runtime, project, *args, env_extra=env_extra), tmp_path, before)
    if case == "plan-id-pinned":
        assert "PLAN_ID" in message
    if case in ("destination-exists", "destination-is-file"):
        assert "already exists; restore or rename it first." in message
    if case == "restore-target-exists":
        assert "already exists; archive or rename it first." in message
    if not case.startswith("restore") and case not in ("destination-exists", "destination-is-file", "archive-dir-is-link"):
        assert not (planning / ".archive").exists()


@pytest.mark.parametrize("pointer,cleared", [
    (b"alpha\n", True), (b"\xef\xbb\xbfalpha\r\n", True), (b"alpha  \n", True),
    (b"beta\n", False), (b"", False), (b"alpha beta\n", False),
], ids=["names-plan", "bom-crlf", "padded", "names-other", "empty", "two-words"])
def test_pointer_is_cleared_only_when_it_names_the_archived_plan(runtime, tmp_path, pointer, cleared):
    fixture(tmp_path, "alpha", "beta", pointer=pointer)
    pointer_file = tmp_path / ".planning" / ".active_plan"
    before = pointer_file.stat().st_mtime_ns
    preview = ok(run_selector(runtime, tmp_path, "--archive", "alpha"))
    assert ("will be cleared" in preview) is cleared
    assert pointer_file.read_bytes() == pointer and pointer_file.stat().st_mtime_ns == before
    output = ok(run_selector(runtime, tmp_path, "--archive", "alpha", "--yes"))
    assert ("Cleared the shared default (.active_plan), which named this plan." in output) is cleared
    if cleared:
        assert not pointer_file.exists()
    else:
        assert pointer_file.read_bytes() == pointer and pointer_file.stat().st_mtime_ns == before


@pytest.mark.parametrize("args", [
    ("--yes",), ("--archived",), ("--archive",), ("--restore",),
    ("--archive", "alpha", "extra"), ("--archive", "alpha", "--list"), ("--archive", "alpha", "--json"),
    ("--archive", "alpha", "--restore", "beta"), ("--list", "--archived", "alpha"),
    ("--archive", "alpha", "--yes", "--yes"), ("alpha", "--yes"),
])
def test_argument_errors_change_nothing(runtime, tmp_path, args):
    fixture(tmp_path, "alpha", "beta")
    before = tree(tmp_path)
    result = run_selector(runtime, tmp_path, *args)
    assert result.returncode != 0, result.stdout + result.stderr
    assert result.stderr.strip(), result.stdout
    assert tree(tmp_path) == before


def test_text_listings_show_archived_plans(runtime, tmp_path):
    fixture(tmp_path, "alpha", "beta")
    assert ok(run_selector(runtime, tmp_path, "--list", "--archived")).strip() == "No archived plans found."
    listing = ok(run_selector(runtime, tmp_path, "--list"))
    assert "Archive a finished plan with" in listing and "archived plan(s)" not in listing
    ok(run_selector(runtime, tmp_path, "--archive", "alpha", "--yes"))
    archived = ok(run_selector(runtime, tmp_path, "--list", "--archived")).splitlines()
    assert archived[0] == "Archived plans:"
    assert archived[1] == "- alpha - 1/1 complete, 0 in_progress, 0 pending"
    assert archived[2].startswith("Restore with")
    listing = ok(run_selector(runtime, tmp_path, "--list"))
    assert "- beta" in listing and "- alpha" not in listing
    assert "1 archived plan(s):" in listing and "Archive a finished plan with" in listing


def inventory(runtime, root, *args):
    result = run_selector(runtime, root, "--list", "--json", *args)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not result.stderr.strip(), result.stderr
    value = json.loads(result.stdout)
    assert value["schema_version"] == 1
    return value


def test_json_listings_count_and_list_archived_plans(runtime, tmp_path):
    fixture(tmp_path, "alpha", "beta", "gamma")
    value = inventory(runtime, tmp_path)
    assert value["archived_count"] == 0
    assert list(value)[list(value).index("host_session") + 1] == "archived_count"
    assert inventory(runtime, tmp_path, "--archived")["candidates"] == []
    for plan_id in ("alpha", "gamma"):
        ok(run_selector(runtime, tmp_path, "--archive", plan_id, "--yes"))
    value = inventory(runtime, tmp_path)
    assert value["archived_count"] == 2
    assert [c["plan_id"] for c in value["candidates"]] == ["beta"]
    assert value["selection"] == {"status": "selected", "plan_id": "beta"}
    archived = inventory(runtime, tmp_path, "--archived")
    assert archived["archived_count"] == 2
    assert [(c["kind"], c["plan_id"]) for c in archived["candidates"]] == [("archived", "alpha"), ("archived", "gamma")]
    first = archived["candidates"][0]
    assert Path(first["files"]["task_plan"]["path"]).samefile(tmp_path / ".planning/.archive/alpha/task_plan.md")
    assert first["files"]["progress"]["status"] == "readable"
    assert first["phases"] == {"status": "parsed", "total": 1, "complete": 1, "in_progress": 0, "pending": 0}
    assert archived["selection"] == value["selection"] and archived["limits"]["returned"] == 2
    page = inventory(runtime, tmp_path, "--archived", "--limit", "1", "--offset", "1")
    assert [c["plan_id"] for c in page["candidates"]] == ["gamma"] and not page["limits"]["truncated"]


def test_json_archived_count_ignores_a_linked_archive_directory(runtime, tmp_path):
    project = tmp_path / "project"
    fixture(project, "alpha")
    external = plan(tmp_path / "external", "secret", "### Phase 1 [complete]\n").parent.parent
    link_directory(project / ".planning" / ".archive", external)
    try:
        value = inventory(runtime, project)
        assert value["archived_count"] == 0
        archived = inventory(runtime, project, "--archived")
        assert archived["candidates"] == [] and archived["limits"]["skipped"] >= 1
    finally:
        link = project / ".planning" / ".archive"
        # A Windows junction is removed with rmdir; a POSIX symlink with unlink.
        link.rmdir() if os.name == "nt" else link.unlink()


def normalized(value):
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalized(item) for item in value]
    if isinstance(value, str) and (value.startswith("/") or (len(value) > 2 and value[1] == ":")):
        return os.path.normcase(os.path.realpath(value))
    return value


def test_routes_agree_on_archived_json(tmp_path):
    runtimes = [(name, executable) for name, executable in RUNTIMES if executable]
    if len(runtimes) < 2:
        pytest.skip("needs two runtimes to compare")
    fixture(tmp_path, "alpha", "beta", "gamma")
    ok(run_selector(runtimes[0], tmp_path, "--archive", "alpha", "--yes"))
    ok(run_selector(runtimes[-1], tmp_path, "--archive", "gamma", "--yes"))
    reports = {name: normalized(inventory(rt, tmp_path, "--archived")) for name, rt in ((r[0], r) for r in runtimes)}
    reference = reports.pop(runtimes[0][0])
    for name, report in reports.items():
        assert report == reference, name


def test_powershell_native_spellings(runtime, tmp_path):
    if runtime[0] == "sh":
        pytest.skip("native PowerShell parameter names")
    fixture(tmp_path, "alpha", "beta")
    assert ok(run_selector(runtime, tmp_path, "-Archive", "alpha")).startswith("Would archive plan: alpha")
    assert ok(run_selector(runtime, tmp_path, "-Archive", "alpha", "-Yes")).startswith("Archived plan: alpha")
    assert ok(run_selector(runtime, tmp_path, "-List", "-Archived")).startswith("Archived plans:")
    assert inventory(runtime, tmp_path, "-Archived")["candidates"][0]["plan_id"] == "alpha"
    assert ok(run_selector(runtime, tmp_path, "-Restore", "alpha", "-Yes")).startswith("Restored plan: alpha")
    assert (tmp_path / ".planning" / "alpha" / "task_plan.md").is_file()


def case_insensitive(root: Path) -> bool:
    (root / "case-probe" / "a").mkdir(parents=True)
    return (root / "case-probe" / "A").is_dir()


def test_case_variant_id_never_moves_a_plan(runtime, tmp_path):
    if not case_insensitive(tmp_path):
        pytest.skip("case-sensitive filesystem")
    # NTFS and default APFS find alpha for ALPHA; the ID must match the entry.
    fixture(tmp_path, "alpha", "beta", pointer=b"alpha\n")
    before = tree(tmp_path)
    for args in (("--archive", "ALPHA"), ("--archive", "ALPHA", "--yes")):
        assert "no plan to archive" in refused(run_selector(runtime, tmp_path, *args), tmp_path, before)
    assert not (tmp_path / ".planning" / ".archive").exists()
    ok(run_selector(runtime, tmp_path, "--archive", "alpha", "--yes"))
    before = tree(tmp_path)
    for args in (("--restore", "ALPHA"), ("--restore", "ALPHA", "--yes")):
        assert "no archived plan" in refused(run_selector(runtime, tmp_path, *args), tmp_path, before)


def test_plan_id_guard_compares_directories_not_strings(runtime, tmp_path):
    if not case_insensitive(tmp_path):
        pytest.skip("case-sensitive filesystem")
    fixture(tmp_path, "alpha", "beta")
    before = tree(tmp_path)
    # A session pinned to ALPHA resolves .planning/alpha on this filesystem.
    message = refused(run_selector(runtime, tmp_path, "--archive", "alpha", "--yes",
                                   env_extra={"PLAN_ID": "ALPHA"}), tmp_path, before)
    assert "PLAN_ID" in message
    assert not (tmp_path / ".planning" / ".archive").exists()
    ok(run_selector(runtime, tmp_path, "--archive", "alpha", "--yes", env_extra={"PLAN_ID": "beta"}))


@pytest.mark.parametrize("pointer", [b"ALPHA\n", b"\xef\xbb\xbf  Alpha \r\n"], ids=["upper", "bom-padded-mixed"])
def test_pointer_naming_the_same_directory_is_cleared(runtime, tmp_path, pointer):
    if not case_insensitive(tmp_path):
        pytest.skip("case-sensitive filesystem")
    fixture(tmp_path, "alpha", "beta", pointer=pointer)
    assert "will be cleared" in ok(run_selector(runtime, tmp_path, "--archive", "alpha"))
    assert "Cleared the shared default" in ok(run_selector(runtime, tmp_path, "--archive", "alpha", "--yes"))
    assert not (tmp_path / ".planning" / ".active_plan").exists()


@pytest.mark.skipif(os.name != "nt", reason="Win32 drops a trailing dot")
def test_trailing_dot_id_never_moves_a_plan(runtime, tmp_path):
    fixture(tmp_path, "alpha", "beta")
    before = tree(tmp_path)
    for args in (("--archive", "alpha."), ("--archive", "alpha.", "--yes")):
        assert "no plan to archive" in refused(run_selector(runtime, tmp_path, *args), tmp_path, before)
    if runtime[0] != "sh":
        # The PowerShell resolver selects .planning\alpha for PLAN_ID=alpha. here.
        assert "PLAN_ID" in refused(run_selector(runtime, tmp_path, "--archive", "alpha", "--yes",
                                                 env_extra={"PLAN_ID": "alpha."}), tmp_path, before)
    ok(run_selector(runtime, tmp_path, "--archive", "alpha", "--yes"))
    before = tree(tmp_path)
    for args in (("--restore", "alpha."), ("--restore", "alpha.", "--yes")):
        assert "no archived plan" in refused(run_selector(runtime, tmp_path, *args), tmp_path, before)


@contextlib.contextmanager
def held_open(path: Path):
    """GENERIC_READ with no sharing: every other open fails, and so does renaming its directory."""
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateFileW.restype = ctypes.c_void_p
    kernel32.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                                     ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel32.CreateFileW(str(path), 0x80000000, 0, None, 3, 0x80, None)
    assert handle not in (None, ctypes.c_void_p(-1).value)
    try:
        yield
    finally:
        kernel32.CloseHandle(handle)


@pytest.mark.skipif(os.name != "nt", reason="Windows share-mode locking")
def test_text_listing_skips_a_locked_archived_plan_quietly(runtime, tmp_path):
    fixture(tmp_path, "alpha", "beta", "gamma")
    for plan_id in ("alpha", "beta"):
        ok(run_selector(runtime, tmp_path, "--archive", plan_id, "--yes"))
    archive = tmp_path / ".planning" / ".archive"
    with held_open(archive / "alpha" / "task_plan.md"):
        if not share_lock_blocks_reads(runtime, archive / "alpha" / "task_plan.md"):
            pytest.skip("this host's runtime reads files held open without sharing")
        # ok() requires an empty stderr: no shell error for the locked file.
        listing = ok(run_selector(runtime, tmp_path, "--list", "--archived"))
        assert "- beta" in listing and "- alpha" not in listing
        assert inventory(runtime, tmp_path, "--archived")["archived_count"] == 2
        with held_open(archive / "beta" / "task_plan.md"):
            assert ok(run_selector(runtime, tmp_path, "--list", "--archived")).strip() == "No archived plans found."


@pytest.mark.skipif(os.name != "nt", reason="Windows share-mode locking")
@pytest.mark.parametrize("existing", [False, True], ids=["archive-dir-created", "archive-dir-existed"])
def test_failed_move_leaves_no_archive_directory_it_created(runtime, tmp_path, existing):
    fixture(tmp_path, "alpha", "beta")
    if existing:
        ok(run_selector(runtime, tmp_path, "--archive", "beta", "--yes"))
    before = tree(tmp_path)
    with held_open(tmp_path / ".planning" / "alpha" / "task_plan.md"):
        result = run_selector(runtime, tmp_path, "--archive", "alpha", "--yes")
    # The snapshot comparison reads every file, so it runs after the release.
    message = refused(result, tmp_path, before)
    assert "could not move" in message
    assert (tmp_path / ".planning" / ".archive").exists() is existing


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def test_powershell_move_errors_use_the_top_level_error_shape(runtime, tmp_path):
    if runtime[0] == "sh":
        pytest.skip("PowerShell error rendering")
    fixture(tmp_path, "alpha")
    before = tree(tmp_path)
    moved = refused(run_selector(runtime, tmp_path, "--archive", "ghost"), tmp_path, before)
    plain = refused(run_selector(runtime, tmp_path, "--yes"), tmp_path, before)
    moved, plain = ANSI.sub("", moved), ANSI.sub("", plain)
    # pwsh 7 renders an error raised inside a function as a multi-line
    # "Line | N |" block naming the function; the move errors must look
    # like every other error of the script.
    assert "Invoke-PlanMove" not in moved and "Line |" not in moved
    assert "Error: no plan to archive at" in moved
    assert moved.split("Error: ")[0] == plain.split("Error: ")[0]
