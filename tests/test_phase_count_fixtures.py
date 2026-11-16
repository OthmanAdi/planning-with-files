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
    if case["total"] and not case.get("smart_fallback"):
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


@pytest.mark.skipif(not PWSH, reason="PowerShell unavailable")
@pytest.mark.parametrize("route,phase_label,status_label", [
    ("scripts/check-complete.ps1", "Phase", "Status:"),
    (".kiro/skills/planning-with-files/assets/scripts/check-complete.ps1", "Phase", "Status:"),
    *[(f"skills/i18n/planning-with-files-{lang}/scripts/check-complete.ps1", phase, status)
      for lang, phase, status in [("ar", "المرحلة", "الحالة:"), ("de", "Phase", "Status:"),
                                 ("es", "Phase", "Estado:"), ("zh", "阶段", "状态："), ("zht", "階段", "狀態：")]],
])
def test_powershell_selected_path_is_literal(route, phase_label, status_label, tmp_path):
    selected = tmp_path / "plan[1].md"
    decoy = tmp_path / "plan1.md"
    selected.write_text(f"### {phase_label} 1: Real\n**{status_label}** pending\n"
                        f"### {phase_label} 2: Verify\n**{status_label}** pending\n", encoding="utf-8-sig")
    decoy.write_text(f"### {phase_label} 1: Wrong file\n**{status_label}** complete\n", encoding="utf-8-sig")
    for flags in ([], ["-Validate"]):
        result = subprocess.run([PWSH, "-NoProfile", "-File", str(ROOT / route), "-PlanFile", str(selected), *flags],
                                cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0, result.stderr
        assert ("valid (2 phases)" if flags else "0/2") in result.stdout
    selected.write_text("# No native phases\n", encoding="utf-8-sig")
    invalid = subprocess.run([PWSH, "-NoProfile", "-File", str(ROOT / route), "-PlanFile", str(selected), "-Validate"],
                             cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
    assert invalid.returncode == 1, invalid.stdout


def test_hermes_keeps_unfenced_legacy_table_support():
    assert hermes.phase_counts("| 1 | complete |\n")["complete"] == 1


@pytest.mark.parametrize("label", ["Estado:", "Unrecognized:"])
def test_smart_view_preserves_raw_fallback_for_unrecognized_statuses(label, tmp_path):
    plan = (f"### Phase 1: Done\n**{label}** complete\n"
            f"### Phase 2: Active\n**{label}** in_progress\n").encode()
    assert injector.smart_plan_extract(plan) is None
    if not shutil.which("sh"):
        pytest.skip("sh unavailable")
    source = (ROOT / "scripts/inject-plan.sh").read_text(encoding="utf-8")
    function = source[source.index("smart_plan_extract() {"):source.index("# emit_plan_head")]
    selected = tmp_path / "task_plan.md"
    selected.write_bytes(plan)
    result = subprocess.run(["sh", "-c", function + '\nsmart_plan_extract "$1"', "sh", str(selected)],
                            capture_output=True)
    assert result.returncode == 9, result.stderr
    assert result.stdout == b""
    assert selected.read_bytes() == plan


@pytest.mark.parametrize("runtime", ["python", "sh"])
def test_localized_statuses_remain_visible_in_smart_injection(runtime, tmp_path):
    if runtime == "sh" and not shutil.which("sh"):
        pytest.skip("sh unavailable")
    plan = "### Phase 1: Done\n**Estado:** complete\n### Phase 2: Active\n**Estado:** in_progress\n"
    (tmp_path / "task_plan.md").write_text(plan, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in
           {"PLAN_ID", "PWF_PLAN_ROOT", "PLANNING_DISABLED", "PWF_SESSION_ID"}}
    env.update(PWF_INJECT="smart", XDG_CACHE_HOME=str(tmp_path / "cache"))
    command = ([sys.executable, str(ROOT / "scripts/inject-plan.py")] if runtime == "python" else
               ["sh", str(ROOT / "scripts/inject-plan.sh")])
    result = subprocess.run([*command, "--context=userprompt"], cwd=tmp_path, env=env,
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert plan in result.stdout
    assert "phases:" not in result.stdout
