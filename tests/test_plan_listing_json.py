"""Agent-readable inventory through the shipped shell and PowerShell commands."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from test_plan_listing import runtime, run_selector, plan, make_symlink, listed, SCRIPTS
from test_plan_listing import make_junction, share_lock_blocks_reads


def clean_env(extra=None):
    env = {k: v for k, v in os.environ.items() if k not in ("PLAN_ID", "PWF_PLAN_ROOT", "PLANNING_DISABLED")}
    env.update(extra or {})
    return env


def wire_command(runtime, *args):
    name, executable = runtime
    if name == "sh":
        return [executable, str(SCRIPTS / "set-active-plan.sh"), *args]
    return [executable, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", str(SCRIPTS / "set-active-plan.ps1"), *args]


def inventory(runtime, root, *args, env_extra=None):
    result = run_selector(runtime, root, "--list", "--json", *args, env_extra=env_extra)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not result.stderr.strip(), result.stderr
    assert len(result.stdout.encode("utf-8")) <= 16384
    value = json.loads(result.stdout)
    assert value["schema_version"] == 1
    assert value["scope"]["source"] == "cwd"
    assert Path(value["scope"]["project_root"]).samefile(root)
    assert value["host_session"] is None
    return value


def snapshot(root):
    return {str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
            for p in root.rglob("*") if p.is_file() and not p.is_symlink()}


def test_json_empty_project_creates_nothing(runtime, tmp_path):
    value = inventory(runtime, tmp_path)
    assert value["candidates"] == []
    assert value["selection"]["status"] == "none"
    assert value["shared_default"]["status"] == "missing"
    assert not value["limits"]["truncated"]
    assert list(tmp_path.iterdir()) == []


def test_json_paths_files_and_shared_default_are_not_session_selection(runtime, tmp_path):
    alpha = plan(tmp_path, "alpha", "# Private body must not leak\n### Phase 1: Work\n**Status:** in_progress\n")
    plan(tmp_path, "beta", "### Phase 1: Done [complete]\n")
    (alpha.parent / "progress.md").write_text("private progress", encoding="utf-8")
    (tmp_path / ".planning/.active_plan").write_text("beta\n", encoding="utf-8")
    before = snapshot(tmp_path)
    value = inventory(runtime, tmp_path, env_extra={"PLAN_ID": "alpha"})
    assert value["shared_default"] == {"plan_id": "beta", "status": "present"}
    assert value["selection"]["status"] == "selected"
    assert value["selection"]["plan_id"] == "alpha"
    candidate = value["candidates"][0]
    assert candidate["kind"] == "named" and candidate["plan_id"] == "alpha"
    assert candidate["ownership"] == "unknown"
    assert Path(candidate["files"]["task_plan"]["path"]).samefile(alpha)
    assert candidate["files"]["task_plan"]["status"] == "readable"
    assert isinstance(candidate["files"]["task_plan"]["modified_at"], int)
    assert candidate["files"]["findings"]["status"] == "missing"
    assert candidate["files"]["progress"]["status"] == "readable"
    assert candidate["phases"] == {"status": "parsed", "total": 1, "complete": 0, "in_progress": 1, "pending": 0}
    assert "Private body" not in json.dumps(value) and "private progress" not in json.dumps(value)
    assert snapshot(tmp_path) == before


def test_json_root_and_named_inventory_are_both_visible(runtime, tmp_path):
    (tmp_path / "task_plan.md").write_text("### Phase 1: Root [complete]\n", encoding="utf-8")
    plan(tmp_path, "alpha", "### Phase 1: Work [pending]\n")
    value = inventory(runtime, tmp_path)
    assert [c["kind"] for c in value["candidates"]] == ["root", "named"]
    assert value["candidates"][0]["plan_id"] is None
    assert value["candidates"][0]["phases"]["complete"] == 1


@pytest.mark.parametrize("selector", ["missing", "../alpha", "--json"])
def test_json_rejected_selector_never_becomes_shared_default(runtime, tmp_path, selector):
    plan(tmp_path, "alpha")
    (tmp_path / ".planning/.active_plan").write_text("alpha\n", encoding="utf-8")
    value = inventory(runtime, tmp_path, env_extra={"PLAN_ID": selector})
    assert value["selection"]["status"] == "rejected"
    assert value["selection"]["plan_id"] is None


def test_json_ambiguous_plans_remain_ambiguous(runtime, tmp_path):
    plan(tmp_path, "alpha")
    plan(tmp_path, "beta")
    (tmp_path / ".planning/.active_plan").write_text("beta\n", encoding="utf-8")
    value = inventory(runtime, tmp_path)
    assert value["selection"]["status"] == "ambiguous"
    assert value["shared_default"]["plan_id"] == "beta"


def test_json_inventory_keeps_cwd_scope_with_external_pin(runtime, tmp_path):
    root, other = tmp_path / "here", tmp_path / "other"
    plan(root, "local")
    plan(other, "external")
    value = inventory(runtime, root, env_extra={"PWF_PLAN_ROOT": str(other), "PLAN_ID": "external"})
    assert value["selection"]["status"] == "outside_scope"
    assert [c["plan_id"] for c in value["candidates"]] == ["local"]


@pytest.mark.parametrize("content,state", [("", "empty"), ("### Phase 1: Missing status\n", "malformed"),
    ("```md\n### Phase 1 [complete]\n```\n", "empty"),
    ("### Phase 1: Work [complete]\n**Status:** broken\n", "malformed"),
    ("### Phase 1: Work\n**Status:** complete\n**Status:** pending\n", "malformed")])
def test_json_unknown_phase_state_is_never_completion(runtime, tmp_path, content, state):
    plan(tmp_path, "alpha", content)
    value = inventory(runtime, tmp_path)
    assert value["candidates"][0]["phases"]["status"] == state


def test_json_paging_is_bounded_and_deterministic(runtime, tmp_path):
    for i in range(27):
        plan(tmp_path, f"plan-{i:02}", "### Phase 1: Work [pending]\n")
    seen, offset = [], 0
    for _ in range(8):
        value = inventory(runtime, tmp_path, "--limit", "7", "--offset", str(offset))
        ids = [c["plan_id"] for c in value["candidates"]]
        assert len(ids) <= 7
        seen.extend(ids)
        if not value["limits"]["truncated"]:
            assert value["limits"]["next_offset"] is None
            break
        offset = value["limits"]["next_offset"]
        assert offset > 0
    assert seen == [f"plan-{i:02}" for i in range(27)]


def test_json_unicode_and_literal_paths(runtime, tmp_path):
    root = tmp_path / 'Projekt [test] Gr\u00f6\u00dfe \u2603'
    plan(root, "alpha")
    value = inventory(runtime, root)
    assert Path(value["candidates"][0]["files"]["task_plan"]["path"]).is_file()


def test_json_linked_plan_is_excluded_without_reading_target(runtime, tmp_path):
    plan(tmp_path, "safe")
    target = tmp_path / "external.md"
    target.write_text("### Phase 1: Secret [complete]\n", encoding="utf-8")
    linked = tmp_path / ".planning/linked"
    linked.mkdir()
    make_symlink(linked / "task_plan.md", target, directory=False)
    value = inventory(runtime, tmp_path)
    assert [c["plan_id"] for c in value["candidates"]] == ["safe"]
    assert value["limits"]["skipped"] >= 1


def test_json_large_plan_does_not_parse_or_expose_body(runtime, tmp_path):
    plan(tmp_path, "alpha", "# secret\n" + "x" * 262144)
    value = inventory(runtime, tmp_path)
    assert value["candidates"][0]["phases"]["status"] == "too_large"
    assert "secret" not in json.dumps(value)


def test_json_bom_heading_parses_consistently(runtime, tmp_path):
    plan(tmp_path, "alpha", "\ufeff### Phase 1: Work [pending]\n")
    phases = inventory(runtime, tmp_path)["candidates"][0]["phases"]
    assert phases["status"] == "parsed" and phases["total"] == 1 and phases["pending"] == 1


def test_json_oversized_pointer_is_not_read_as_selection(runtime, tmp_path):
    plan(tmp_path, "alpha")
    (tmp_path / ".planning/.active_plan").write_text("x" * 300000, encoding="utf-8")
    value = inventory(runtime, tmp_path)
    assert value["shared_default"]["status"] == "invalid"
    assert value["selection"]["status"] == "unknown"


def test_json_valid_project_pin_allows_legacy_root(runtime, tmp_path):
    (tmp_path / 'task_plan.md').write_text('### Phase 1: Work [pending]\n', encoding='utf-8')
    value = inventory(runtime, tmp_path, env_extra={'PWF_PLAN_ROOT': str(tmp_path)})
    assert value['selection']['status'] == 'legacy_root'


def test_json_windows_equivalent_pin_spelling_is_same_project(runtime, tmp_path):
    if os.name != 'nt':
        pytest.skip('Windows short-path regression')
    import ctypes
    short = ctypes.create_unicode_buffer(32768)
    length = ctypes.windll.kernel32.GetShortPathNameW(str(tmp_path), short, len(short))
    assert length > 0
    (tmp_path / 'task_plan.md').write_text('### Phase 1: Work [pending]\n', encoding='utf-8')
    value = inventory(runtime, tmp_path, env_extra={'PWF_PLAN_ROOT': short.value})
    assert value['selection']['status'] == 'legacy_root'


def test_json_root_link_does_not_establish_legacy_selection(runtime, tmp_path):
    external = tmp_path / 'external.md'
    external.write_text('### Phase 1: Secret [complete]\n', encoding='utf-8')
    make_symlink(tmp_path / 'task_plan.md', external, directory=False)
    value = inventory(runtime, tmp_path)
    assert value['candidates'][0]['files']['task_plan']['status'] == 'excluded'
    assert value['selection']['status'] != 'legacy_root'


@pytest.mark.parametrize("link_root", [False, True])
def test_json_windows_junction_is_skipped(runtime, tmp_path, link_root):
    project = tmp_path / "project"
    external = plan(tmp_path / "other", "external", "### Phase 1 [complete]\n")
    project.mkdir()
    link = project / ".planning"
    target = external.parent.parent
    if not link_root:
        plan(project, "safe")
        link = project / ".planning/linked"
        target = external.parent
    make_junction(link, target)
    try:
        value = inventory(runtime, project)
        assert all(c["plan_id"] not in ("external", "linked") for c in value["candidates"])
        assert value["limits"]["skipped"] >= 1
        if link_root:
            assert value['selection']['status'] == 'unknown'
    finally:
        link.rmdir()


@pytest.mark.parametrize("args", [("--json",), ("--list", "--json", "alpha"),
    ("--list", "--json", "--limit", "0"), ("--list", "--json", "--offset", "-1")])
def test_json_invalid_invocations_never_write_pointer(runtime, tmp_path, args):
    plan(tmp_path, "alpha")
    before = snapshot(tmp_path)
    result = run_selector(runtime, tmp_path, *args)
    assert result.returncode != 0
    assert snapshot(tmp_path) == before


def test_json_wire_output_is_one_utf8_line_with_lf(runtime, tmp_path):
    name = runtime[0]
    args = wire_command(runtime, '--list', '--json') if name == 'sh' else wire_command(runtime, '-List', '-Json')
    result = subprocess.run(args, cwd=tmp_path, env=clean_env(), capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert len(result.stdout) <= 16384
    assert result.stdout.endswith(b'\n') and result.stdout.count(b'\n') == 1
    assert b'\r' not in result.stdout
    assert json.loads(result.stdout.decode('utf-8'))['schema_version'] == 1


@pytest.mark.parametrize("env_extra", [{}, {"LC_ALL": "C"}], ids=["inherited-locale", "C-locale"])
def test_json_wire_bytes_are_utf8_for_a_non_ascii_project(runtime, tmp_path, env_extra):
    # cygpath converted through the ANSI code page under LC_ALL=C, so the sh
    # route emitted non-UTF-8 bytes for this project name; PowerShell must
    # emit UTF-8 whatever the console code page.
    root = tmp_path / "Übung 计划"
    path = plan(root, "alpha")
    args = wire_command(runtime, '--list', '--json') if runtime[0] == 'sh' else wire_command(runtime, '-List', '-Json')
    result = subprocess.run(args, cwd=root, env=clean_env(env_extra), capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.endswith(b"\n") and result.stdout.count(b"\n") == 1 and b"\r" not in result.stdout
    value = json.loads(result.stdout.decode("utf-8"))
    assert "Übung 计划" in value["scope"]["project_root"]
    assert Path(value["candidates"][0]["files"]["task_plan"]["path"]).samefile(path)


def test_json_in_session_call_feeds_the_pipeline_and_restores_the_console(runtime, tmp_path):
    name, executable = runtime
    if name == "sh":
        pytest.skip("PowerShell session semantics")
    root = tmp_path / "Übung 计划"
    plan(root, "alpha")
    script = str(SCRIPTS / "set-active-plan.ps1").replace("'", "''")
    # Inside a session the document is one ASCII string whose \uXXXX escapes
    # ConvertFrom-Json turns back into the real characters.
    command = ("$before = [Console]::OutputEncoding.CodePage; "
               f"$report = & '{script}' -List -Json; "
               "Write-Output ($report -is [string] -and $report -cmatch '^[\\x00-\\x7F]+$'); "
               "$parsed = $report | ConvertFrom-Json; "
               "Write-Output $parsed.candidates[0].plan_id; "
               "Write-Output ($parsed.scope.project_root.EndsWith([char]0x00DC + 'bung ' + [char]0x8BA1 + [char]0x5212)); "
               "Write-Output ([Console]::OutputEncoding.CodePage -eq $before)")
    result = subprocess.run(
        [executable, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
        cwd=root, env=clean_env(), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.split() == ["True", "alpha", "True", "True"], result.stdout + result.stderr


@pytest.mark.parametrize("form", ["-f", "positional", "-Command"])
def test_json_other_entry_forms_emit_ascii_that_matches_the_file_run(runtime, tmp_path, form):
    name, executable = runtime
    if name == "sh":
        pytest.skip("PowerShell entry forms")
    # Only a literal -File entry writes UTF-8 itself; every other entry goes
    # through the pipeline, which the host encodes with the console code page
    # (cp850 turned U-umlaut into 0x81). Escaped to ASCII, the bytes decode
    # the same everywhere and name the same files as the -File run.
    root = tmp_path / "Übung 计划"
    path = plan(root, "alpha")
    script = str(SCRIPTS / "set-active-plan.ps1")
    base = [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass"]
    if form == "-Command":
        args = base + ["-Command", "& '" + script.replace("'", "''") + "' -List -Json"]
    elif form == "-f":
        args = base + ["-f", script, "-List", "-Json"]
    else:
        args = base + [script, "-List", "-Json"]
    reference = subprocess.run(base + ["-File", script, "-List", "-Json"], cwd=root, env=clean_env(),
                               capture_output=True, timeout=60)
    expected = json.loads(reference.stdout.decode("utf-8"))
    result = subprocess.run(args, cwd=root, env=clean_env(), capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.isascii(), result.stdout[:200]
    assert b"\\u00dc" in result.stdout and b"\\u8ba1\\u5212" in result.stdout
    value = json.loads(result.stdout.decode("ascii"))
    assert value["scope"]["project_root"] == expected["scope"]["project_root"]
    assert value["scope"]["project_root"].endswith("Übung 计划")
    assert value["candidates"] == expected["candidates"]
    assert Path(value["candidates"][0]["files"]["task_plan"]["path"]).samefile(path)


def test_json_escaped_entry_form_stays_within_the_output_ceiling(runtime, tmp_path):
    name, executable = runtime
    if name == "sh":
        pytest.skip("PowerShell entry forms")
    # Escaping turns each U-umlaut into six ASCII bytes, so paging must measure
    # the escaped text, not its UTF-8 form, to keep the documented 16 KiB cap.
    root = tmp_path / ("ü" * 60)
    for index in range(40):
        path = plan(root, f"plan-{index:02d}")
        (path.parent / "findings.md").write_text("notes\n", encoding="utf-8")
    script = str(SCRIPTS / "set-active-plan.ps1")
    args = [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-Command", "& '" + script.replace("'", "''") + "' -List -Json -Limit 100"]
    result = subprocess.run(args, cwd=root, env=clean_env(), capture_output=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert result.stdout.isascii()
    assert len(result.stdout.rstrip(b"\r\n")) <= 16383, len(result.stdout)
    value = json.loads(result.stdout.decode("ascii"))
    assert value["limits"]["truncated"] is True
    assert 0 < value["limits"]["returned"] < 40


def test_json_modified_at_is_the_unix_epoch_second(runtime, tmp_path):
    path = plan(tmp_path, "alpha")
    # A fixed instant far from now: a local-time epoch would show as the UTC offset.
    os.utime(path, (1700000000, 1700000000))
    # GitHub's runners are UTC, where the old PowerShell bug had offset 0 and
    # proved nothing; a zone three hours east shows a regression as 10800 s.
    # Windows ignores TZ and is left to its configured zone.
    env_extra = {"TZ": "Etc/GMT-3"} if runtime[0] != "sh" and os.name != "nt" else None
    value = inventory(runtime, tmp_path, env_extra=env_extra)
    assert value["candidates"][0]["files"]["task_plan"]["modified_at"] == int(os.stat(path).st_mtime) == 1700000000


def test_json_root_and_named_candidates_parse_under_one_locale(runtime, tmp_path):
    body = "### Phase 1: Übung [complete]\n**Status:** complete\n".encode("cp1252")
    (tmp_path / "task_plan.md").write_bytes(body)
    plan(tmp_path, "alpha").write_bytes(body)
    value = inventory(runtime, tmp_path)
    expected = {"status": "parsed", "total": 1, "complete": 1, "in_progress": 0, "pending": 0}
    assert [c["phases"] for c in value["candidates"]] == [expected, expected]


@pytest.mark.skipif(os.name != "nt", reason="Windows share-mode locking")
def test_json_exclusively_locked_plan_file_keeps_the_document_valid(runtime, tmp_path):
    import ctypes
    named = plan(tmp_path, "alpha", "### Phase 1: Work [pending]\n")
    plan(tmp_path, "beta", "### Phase 1: Work [pending]\n")
    root_file = tmp_path / "task_plan.md"
    root_file.write_text("### Phase 1: Root [complete]\n", encoding="utf-8")
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateFileW.restype = ctypes.c_void_p
    kernel32.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                                     ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    # GENERIC_READ, no sharing, OPEN_EXISTING: [ -r ] passes, every open fails.
    handles = [kernel32.CreateFileW(str(p), 0x80000000, 0, None, 3, 0x80, None) for p in (named, root_file)]
    assert all(h not in (None, ctypes.c_void_p(-1).value) for h in handles)
    try:
        if not share_lock_blocks_reads(runtime, named):
            pytest.skip("this host's runtime reads files held open without sharing")
        value = inventory(runtime, tmp_path)
        states = [(c["kind"], c["files"]["task_plan"]["status"], c["phases"]["status"]) for c in value["candidates"]]
        assert states == [("root", "unreadable", "unavailable"), ("named", "unreadable", "unavailable"),
                          ("named", "readable", "parsed")]
        text = listed(runtime, tmp_path)
        assert "- beta" in text and "- alpha" not in text
    finally:
        for handle in handles:
            kernel32.CloseHandle(handle)


@pytest.mark.skipif(os.name != "nt", reason="Windows MAX_PATH regression")
def test_json_plan_beyond_max_path_is_listed_and_selected(runtime, tmp_path):
    overhead = len(str(tmp_path / ".planning")) + len("/x/task_plan.md")
    slug = "p-" + "x" * max(20, 270 - overhead)
    try:
        path = plan(tmp_path, slug)
    except OSError as error:
        pytest.skip(f"long paths are disabled on this host: {error}")
    assert len(str(path)) > 260
    value = inventory(runtime, tmp_path)
    assert [c["plan_id"] for c in value["candidates"]] == [slug]
    assert value["limits"]["skipped"] == 0 and value["warnings"] == []
    assert value["selection"] == {"status": "selected", "plan_id": slug}
    assert f"- {slug}" in listed(runtime, tmp_path)


@pytest.mark.skipif(os.name != "nt", reason="Windows Hidden attribute")
def test_json_hidden_plan_directory_is_a_plan_on_every_route(runtime, tmp_path):
    plan(tmp_path, "alpha")
    hidden = plan(tmp_path, "hidden").parent
    subprocess.run(["attrib", "+H", str(hidden)], check=True, capture_output=True)
    value = inventory(runtime, tmp_path)
    assert [c["plan_id"] for c in value["candidates"]] == ["alpha", "hidden"]
    # The resolver probe behind this status enumerates the same directories.
    assert value["selection"]["status"] == "ambiguous"
    assert "- hidden" in listed(runtime, tmp_path)


# Commands the shell listing may start. Builtins are free; each of these is a
# process, which costs about 30 ms under Git Bash (#356). phase_status stands
# for its awk, which runs with stderr redirected and so never reaches the trace.
EXTERNAL_COMMANDS = {"awk", "cygpath", "dirname", "phase_status", "python", "python3",
                     "readlink", "realpath", "sh", "stat", "tr", "wc"}


def external_commands(root: Path) -> int:
    sh = shutil.which("sh")
    env = clean_env({"PS4": "+ "})
    result = subprocess.run([sh, "-x", str(SCRIPTS / "set-active-plan.sh"), "--list", "--json", "--limit", "100"],
                            cwd=root, env=env, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=120)
    assert result.returncode == 0, result.stderr[-2000:]
    count = 0
    for line in result.stderr.splitlines():
        words = re.sub(r"^\++\s*", "", line).split() if line.startswith("+") else []
        while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
            words.pop(0)
        if words and Path(words[0]).name.removesuffix(".exe") in EXTERNAL_COMMANDS:
            count += 1
    return count


@pytest.mark.skipif(shutil.which("sh") is None, reason="sh is not installed")
def test_json_listing_starts_a_bounded_number_of_commands_per_plan(tmp_path):
    def project(name, plans):
        root = tmp_path / name
        for index in range(plans):
            path = plan(root, f"plan-{index}", "### Phase 1: Work\n**Status:** in_progress\n")
            (path.parent / "findings.md").write_text("f", encoding="utf-8")
            (path.parent / "progress.md").write_text("p", encoding="utf-8")
        return root

    # The difference between two plan counts leaves out the fixed cost of the
    # header, the pointer and the resolver probe.
    per_plan = (external_commands(project("seven", 7)) - external_commands(project("two", 2))) / 5
    # A realpath for the directory and each file, a stat per file, and the phase parse.
    assert per_plan <= 9, per_plan
