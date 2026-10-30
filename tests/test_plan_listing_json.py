"""Agent-readable inventory through the shipped shell and PowerShell commands."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from test_plan_listing import runtime, run_selector, plan, make_symlink, SCRIPTS
from test_plan_listing import make_junction


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
    name, executable = runtime
    if name == 'sh':
        args = [executable, str(SCRIPTS/'set-active-plan.sh'), '--list', '--json']
    else:
        args = [executable, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                '-File', str(SCRIPTS/'set-active-plan.ps1'), '-List', '-Json']
    env = {k:v for k,v in os.environ.items() if k not in ('PLAN_ID','PWF_PLAN_ROOT')}
    result = subprocess.run(args, cwd=tmp_path, env=env, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert len(result.stdout) <= 16384
    assert result.stdout.endswith(b'\n') and result.stdout.count(b'\n') == 1
    assert b'\r' not in result.stdout
    assert json.loads(result.stdout.decode('utf-8'))['schema_version'] == 1
