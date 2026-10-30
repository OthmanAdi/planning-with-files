"""Ensure every applicable install surface ships the standalone listing helpers."""
from __future__ import annotations

import os
import json
import runpy
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "skills/planning-with-files/scripts"
HELPERS = ("set-active-plan.sh", "set-active-plan.ps1")
IDE_SURFACES = (
    ".agents", ".codebuddy", ".codex", ".continue", ".cursor", ".factory",
    ".gemini", ".hermes", ".mastracode", ".opencode", ".pi",
)
SURFACES = (
    (".", "scripts"),
    ("canonical", "skills/planning-with-files/scripts"),
    *((ide, f"{ide}/skills/planning-with-files/scripts") for ide in IDE_SURFACES),
    *((f"skills/i18n/planning-with-files-{lang}",
       f"skills/i18n/planning-with-files-{lang}/scripts")
      for lang in ("ar", "de", "es", "zh", "zht")),
)
MANIFESTS = runpy.run_path(str(ROOT / "scripts/sync-ide-folders.py"))["IDE_MANIFESTS"]
RUNTIMES = (
    ("sh", shutil.which("sh")),
    ("powershell", shutil.which("powershell.exe") or shutil.which("powershell")),
    ("pwsh", shutil.which("pwsh.exe") or shutil.which("pwsh")),
)


@pytest.mark.parametrize("manifest_key,relative_scripts", SURFACES)
def test_listing_helpers_are_shipped_and_synced(manifest_key, relative_scripts):
    """An IDE can have a different adapter without losing the listing feature."""
    for helper in HELPERS:
        shipped = ROOT / relative_scripts / helper
        assert shipped.is_file(), f"Missing listing helper: {shipped}"
        assert shipped.read_bytes() == (CANONICAL / helper).read_bytes()
        if manifest_key != "canonical":
            target = MANIFESTS[manifest_key][f"scripts/{helper}"]
            assert ROOT / target == shipped


@pytest.mark.parametrize("manifest_key,relative_scripts", SURFACES)
def test_json_listing_reference_is_installed_and_discoverable(manifest_key, relative_scripts):
    if manifest_key == ".":
        return  # root scripts are dev/plugin entry points, not an installed skill
    skill_root = (ROOT / relative_scripts).parent
    if manifest_key == "canonical":
        reference = ROOT / "skills/planning-with-files/plan-inventory.md"
    else:
        reference = ROOT / MANIFESTS[manifest_key]["plan-inventory.md"]
    assert reference.read_bytes() == (ROOT / "skills/planning-with-files/plan-inventory.md").read_bytes()
    skill = skill_root / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert "--json" in text and "plan-inventory.md" in text
    relative_reference = reference.relative_to(skill_root).as_posix()
    assert f"]({relative_reference})" in text


@pytest.mark.parametrize("ide", (".hermes", ".mastracode", ".opencode"))
@pytest.mark.parametrize("runtime", RUNTIMES, ids=lambda runtime: runtime[0])
@pytest.mark.parametrize("structured", [False, True], ids=["text", "json"])
def test_listing_runs_without_sibling_scripts(ide, runtime, tmp_path, structured):
    """Partial script bundles must remain usable from the project directory."""
    name, executable = runtime
    if executable is None:
        pytest.skip(f"{name} is not installed")
    helper = "set-active-plan.sh" if name == "sh" else "set-active-plan.ps1"
    install = tmp_path / "installed skill"
    install.mkdir()
    script = install / helper
    shutil.copy2(ROOT / ide / "skills/planning-with-files/scripts" / helper, script)
    project = tmp_path / "user project"
    plan_dir = project / ".planning/alpha"
    plan_dir.mkdir(parents=True)
    (plan_dir / "task_plan.md").write_text(
        "# Task\n### Phase 1: Review [complete]\n"
        "### Phase 2: Verify\n**Status:** pending\n", encoding="utf-8",
    )
    (project / ".planning/.active_plan").write_text("alpha\n", encoding="utf-8")
    if name == "sh":
        command = [executable, str(script), "--list"]
    else:
        command = [
            executable, "-NoLogo", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(script), "-List",
        ]
    env = os.environ.copy()
    for key in ("PLAN_ID", "PWF_PLAN_ROOT", "PLANNING_DISABLED"):
        env.pop(key, None)
    if structured:
        command.append("--json" if name == "sh" else "-Json")
    result = subprocess.run(
        command, cwd=project, env=env, text=True, encoding="utf-8",
        errors="replace", capture_output=True, check=False, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not result.stderr.strip(), result.stderr
    if structured:
        report = json.loads(result.stdout)
        assert report["selection"]["status"] == "unknown"
        assert report["host_session"] is None
        assert report["candidates"][0]["plan_id"] == "alpha"
        assert report["candidates"][0]["phases"]["complete"] == 1
        return
    assert "alpha" in result.stdout
    assert "[active]" in result.stdout
    assert "1/2 complete, 0 in_progress, 1 pending" in result.stdout
