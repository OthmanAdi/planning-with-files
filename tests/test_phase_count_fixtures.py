"""Issue #377: every completion consumer reads the same phase fixtures."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "tests/fixtures/phase-counts/cases.json").read_text(encoding="utf-8"))
PWSH = shutil.which("pwsh") or shutil.which("powershell")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


injector = load("pwf_phase_injector", ROOT / "scripts/inject-plan.py")
load("pwf_phase_hermes", ROOT / ".hermes/plugins/planning-with-files/__init__.py")
hermes = importlib.import_module("pwf_phase_hermes.planning_files")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_python_consumers(case):
    expected = {k: case[k] for k in ("total", "complete", "in_progress", "pending")}
    assert hermes.gate_counts(case["plan"]) == expected
    assert {k: hermes.phase_counts(case["plan"])[k] for k in expected} == expected
    view = injector.smart_plan_extract(case["plan"].encode())
    if case["total"]:
        assert f"phases: {case['complete'] or ''}/{case['total']} complete".encode() in view
    else:
        assert view is None


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
@pytest.mark.parametrize("runtime", ["sh", "powershell"])
def test_script_consumers(case, runtime, tmp_path):
    if runtime == "sh" and not shutil.which("sh"):
        pytest.skip("sh unavailable")
    if runtime == "powershell" and not PWSH:
        pytest.skip("PowerShell unavailable")
    env = {k: v for k, v in os.environ.items() if k not in
           {"PLAN_ID", "PWF_PLAN_ROOT", "PLANNING_DISABLED", "PWF_SESSION_ID"}}
    plan = tmp_path / "task_plan.md"
    plan.write_text(case["plan"], encoding="utf-8")
    prefix = ["sh"] if runtime == "sh" else [PWSH, "-NoProfile", "-File"]
    suffix = ".sh" if runtime == "sh" else ".ps1"

    def run(script, *args):
        result = subprocess.run([*prefix, str(ROOT / "scripts" / (script + suffix)), *args],
                                cwd=tmp_path, env=env, capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        assert not result.stderr, result.stderr
        return result

    result = run("check-complete", str(plan))
    assert result.returncode == 0
    if case["total"]:
        assert f"{case['complete']}/{case['total']}" in result.stdout
        assert ("ALL PHASES COMPLETE" in result.stdout) == (case["complete"] == case["total"])
    else:
        assert not result.stdout.strip()
    validated = run("check-complete", str(plan), "--validate" if runtime == "sh" else "-Validate")
    assert (validated.returncode == 0) == case["valid"]
    ledger = run("ledger-summary")
    assert ledger.returncode == 0
    assert f"phases: {case['complete']}/{case['total']} complete" in ledger.stdout
    assert plan.read_text(encoding="utf-8") == case["plan"]


@pytest.mark.parametrize("case", [c for c in CASES if c["valid"]], ids=lambda c: c["name"])
def test_shell_smart_view(case, tmp_path):
    if not shutil.which("sh"):
        pytest.skip("sh unavailable")
    # Extract the existing read-only awk function to test the actual shell view
    # without unrelated selection, attestation or cache setup.
    source = (ROOT / "scripts/inject-plan.sh").read_text(encoding="utf-8")
    function = source[source.index("smart_plan_extract() {"):source.index("# emit_plan_head")]
    plan = tmp_path / "task_plan.md"
    plan.write_text(case["plan"], encoding="utf-8")
    result = subprocess.run(["sh", "-c", function + '\nsmart_plan_extract "$1"', "sh", str(plan)],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert f"phases: {case['complete'] or ''}/{case['total']} complete" in result.stdout
    assert result.stdout.encode() == injector.smart_plan_extract(case["plan"].encode())


@pytest.mark.parametrize("state", ["failed", "blocked"])
def test_hermes_preserves_failed_status_reporting(state):
    counts = hermes.phase_counts("### Phase 1: Repair\n**Status:** " + state + "\n")
    assert counts["total"] == counts["failed"] == 1
    assert counts["complete"] == 0
