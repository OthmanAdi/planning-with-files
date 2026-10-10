"""Focused behavior tests for the release version bumper."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "bump-version.py"
CLAWHUB_SKILL = "clawhub-upload/SKILL.md"
CODEX_PLUGIN_MANIFEST = ".codex-plugin/plugin.json"
QODER_PLUGIN_MANIFEST = ".qoder-plugin/plugin.json"


def load_bump_version():
    spec = importlib.util.spec_from_file_location("pwf_bump_version", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def bumper():
    return load_bump_version()


def test_optional_parity_scope_is_exact_and_maintained(bumper) -> None:
    optional_paths = set(bumper.OPTIONAL_PARITY_FILES)
    parity_paths = {path for path, _kind in bumper.PARITY_FILES}

    assert optional_paths == {CLAWHUB_SKILL}
    assert optional_paths <= parity_paths


def test_codex_plugin_manifest_is_parity_locked(bumper) -> None:
    assert (CODEX_PLUGIN_MANIFEST, "plugin_json") in bumper.PARITY_FILES


def test_qoder_plugin_manifest_is_parity_locked(bumper) -> None:
    assert (QODER_PLUGIN_MANIFEST, "plugin_json") in bumper.PARITY_FILES


def test_absent_optional_clawhub_staging_succeeds(
    bumper, monkeypatch, tmp_path: Path, capsys
) -> None:
    assert (CLAWHUB_SKILL, "skill_md") in bumper.PARITY_FILES
    monkeypatch.setattr(bumper, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(bumper, "PARITY_FILES", [(CLAWHUB_SKILL, "skill_md")])

    result = bumper.main(["9.8.7"])

    output = capsys.readouterr()
    assert result == 0
    assert f"OPTIONAL:  {CLAWHUB_SKILL}" in output.out
    assert "optional gitignored ClawHub publish staging" in output.out
    assert "Optional gitignored publish staging absent: 1" in output.out
    assert output.err == ""


def test_present_optional_clawhub_staging_is_bumped(
    bumper, monkeypatch, tmp_path: Path, capsys
) -> None:
    skill = tmp_path / CLAWHUB_SKILL
    skill.parent.mkdir(parents=True)
    skill.write_text('---\nmetadata:\n  version: "1.2.3"\n---\n', encoding="utf-8")
    monkeypatch.setattr(bumper, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(bumper, "PARITY_FILES", [(CLAWHUB_SKILL, "skill_md")])

    result = bumper.main(["9.8.7"])

    output = capsys.readouterr()
    assert result == 0
    assert 'version: "9.8.7"' in skill.read_text(encoding="utf-8")
    assert f"bumped:    {CLAWHUB_SKILL}  1.2.3 -> 9.8.7" in output.out
    assert "Optional gitignored publish staging absent: 0" in output.out
    assert output.err == ""


def test_present_optional_clawhub_staging_is_validated(
    bumper, monkeypatch, tmp_path: Path, capsys
) -> None:
    skill = tmp_path / CLAWHUB_SKILL
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nmetadata: {}\n---\n", encoding="utf-8")
    monkeypatch.setattr(bumper, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(bumper, "PARITY_FILES", [(CLAWHUB_SKILL, "skill_md")])

    result = bumper.main(["9.8.7"])

    output = capsys.readouterr()
    assert result == 1
    assert f"ERROR:     {CLAWHUB_SKILL}" in output.out
    assert "no version field found" in output.err


def test_absent_required_parity_file_still_fails(
    bumper, monkeypatch, tmp_path: Path, capsys
) -> None:
    required_skill = "skills/planning-with-files/SKILL.md"
    monkeypatch.setattr(bumper, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(bumper, "PARITY_FILES", [(required_skill, "skill_md")])

    result = bumper.main(["9.8.7"])

    output = capsys.readouterr()
    assert result == 1
    assert f"MISSING:   {required_skill}" in output.out
    assert "Optional gitignored publish staging absent: 0" in output.out
    assert f"missing: {required_skill}" in output.err
