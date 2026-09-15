"""CLI regressions for read-only IDE sync verification on temporary repositories."""

from __future__ import annotations

import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync-ide-folders.py"


def seed_manifests(root: Path, manifests, ide_names) -> None:
    canonical = root / "skills" / "planning-with-files"
    canonical.mkdir(parents=True, exist_ok=True)
    for ide in ide_names:
        (root / ide).mkdir(parents=True, exist_ok=True)
        for key, target in manifests[ide].items():
            relative_source = key.split("__extra_")[0]
            content = f"fixture: {relative_source}\n".encode("utf-8")
            for path in (canonical / relative_source, root / target):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)


@pytest.fixture
def sync_repo(tmp_path: Path):
    # Exercise the real manifest and CLI, without importing or executing any hooks.
    manifests = runpy.run_path(str(SCRIPT_PATH))["IDE_MANIFESTS"]
    root = tmp_path / "repo with spaces 計畫"
    seed_manifests(root, manifests, (".", ".cursor"))
    skill = root / ".cursor" / "skills" / "planning-with-files" / "SKILL.md"
    skill.write_bytes(b"IDE-specific skill; do not overwrite\n")
    hook = root / ".cursor" / "hooks" / "custom.json"
    hook.parent.mkdir()
    hook.write_bytes(b'{"custom": true}\n')
    return root, root / "skills" / "planning-with-files", manifests


def snapshot(root: Path) -> dict:
    # Reads can update atime; compare paths, bytes, permissions and mtimes instead.
    result = {}
    for path in [root, *root.rglob("*")]:
        stat = path.stat()
        result[path.relative_to(root).as_posix()] = (
            stat.st_mode,
            stat.st_mtime_ns,
            path.read_bytes() if path.is_file() else None,
        )
    return result


def run_sync(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        timeout=15,
        check=False,
    )


def run_read_only(root: Path, *args: str) -> subprocess.CompletedProcess:
    before = snapshot(root)
    result = run_sync(root, *args)
    assert snapshot(root) == before, "Read-only command changed the fixture tree"
    assert result.stderr == "", result.stderr
    return result


@pytest.mark.parametrize("content", [b"canonical\n", b""], ids=["text", "empty-file"])
def test_verify_matching_files_succeeds_without_writes(sync_repo, content) -> None:
    root, canonical, manifests = sync_repo
    key = "templates/findings.md"
    (canonical / key).write_bytes(content)
    (root / manifests[".cursor"][key]).write_bytes(content)
    result = run_read_only(root, "--verify")
    assert result.returncode == 0, result.stdout
    assert "All IDE folders are in sync." in result.stdout


@pytest.mark.parametrize("target_present", [True, False], ids=["target-present", "both-missing"])
def test_verify_missing_source_fails_without_writes(sync_repo, target_present) -> None:
    root, canonical, manifests = sync_repo
    key = "templates/findings.md"
    (canonical / key).unlink()
    if not target_present:
        (root / manifests[".cursor"][key]).unlink()
    result = run_read_only(root, "--verify")
    assert result.returncode == 1, result.stdout
    assert f"MISSING SOURCE: {Path('skills/planning-with-files') / key}" in result.stdout
    assert "All IDE folders are in sync." not in result.stdout
    cursor_section = result.stdout.split("  .cursor/\n", 1)[1].split("\n\n", 1)[0]
    assert "(up to date)" not in cursor_section
    assert "Restore the missing canonical files" in result.stdout


def test_verify_shared_missing_source_reports_each_affected_entry(sync_repo) -> None:
    root, canonical, manifests = sync_repo
    seed_manifests(root, manifests, (".gemini",))
    (canonical / "templates/findings.md").unlink()
    result = run_read_only(root, "--verify")
    assert result.returncode == 1, result.stdout
    assert result.stdout.count("MISSING SOURCE:") == 2
    assert "2 sync entry/entries" in result.stdout


def test_verify_empty_canonical_tree_does_not_report_success(sync_repo) -> None:
    root, canonical, _ = sync_repo
    for path in canonical.rglob("*"):
        if path.is_file():
            path.unlink()
    result = run_read_only(root, "--verify")
    assert result.returncode == 1, result.stdout
    assert "MISSING SOURCE:" in result.stdout
    assert "(up to date)" not in result.stdout
    assert "All IDE folders are in sync." not in result.stdout


@pytest.mark.parametrize("remove_parent", [False, True], ids=["file", "parent-directory"])
def test_verify_missing_destination_fails_without_recreating_it(sync_repo, remove_parent) -> None:
    root, _, manifests = sync_repo
    target = root / manifests[".cursor"]["templates/findings.md"]
    if remove_parent:
        shutil.rmtree(target.parent)
    else:
        target.unlink()
    result = run_read_only(root, "--verify")
    assert result.returncode == 1, result.stdout
    assert f"MISSING: {target.relative_to(root)}" in result.stdout
    assert "DRIFT DETECTED:" in result.stdout


def test_verify_content_drift_fails_without_repairing_it(sync_repo) -> None:
    root, _, manifests = sync_repo
    target = root / manifests[".cursor"]["templates/findings.md"]
    target.write_bytes(b"stale mirror\n")
    result = run_read_only(root, "--verify")
    assert result.returncode == 1, result.stdout
    assert f"DRIFT: {target.relative_to(root)}" in result.stdout
    assert "DRIFT DETECTED: 1 file(s) out of sync." in result.stdout


def test_verify_still_skips_absent_ide_directories(sync_repo) -> None:
    root, canonical, _ = sync_repo
    shutil.rmtree(root / ".cursor")
    # Only the absent IDE references this source in the remaining fixture.
    (canonical / "templates/findings.md").unlink()
    result = run_read_only(root, "--verify")
    assert result.returncode == 0, result.stdout
    assert "All IDE folders are in sync." in result.stdout
    assert not (root / ".cursor").exists()


def test_verify_reports_other_problems_alongside_missing_sources(sync_repo) -> None:
    root, canonical, manifests = sync_repo
    (canonical / "templates/findings.md").unlink()
    missing = Path(manifests[".cursor"]["templates/progress.md"])
    drifted = Path(manifests[".cursor"]["templates/task_plan.md"])
    (root / missing).unlink()
    (root / drifted).write_bytes(b"stale plan template\n")
    result = run_read_only(root, "--verify")
    assert result.returncode == 1, result.stdout
    assert "MISSING SOURCE:" in result.stdout
    assert f"MISSING: {missing}" in result.stdout
    assert f"DRIFT: {drifted}" in result.stdout
    assert "Run 'python scripts/sync-ide-folders.py' to fix." not in result.stdout


def test_verify_with_dry_run_still_rejects_missing_sources(sync_repo) -> None:
    root, canonical, _ = sync_repo
    (canonical / "templates/findings.md").unlink()
    result = run_read_only(root, "--verify", "--dry-run")
    assert result.returncode == 1, result.stdout
    assert "MISSING SOURCE:" in result.stdout


def test_verify_missing_canonical_directory_keeps_existing_error(sync_repo) -> None:
    root, canonical, _ = sync_repo
    shutil.rmtree(canonical)
    result = run_read_only(root, "--verify")
    assert result.returncode == 1, result.stdout
    assert "Error: Canonical source not found" in result.stdout


@pytest.mark.parametrize("dry_run", [False, True], ids=["sync", "dry-run"])
def test_non_verify_modes_keep_existing_copy_behavior(sync_repo, dry_run) -> None:
    root, canonical, manifests = sync_repo
    missing_key, stale_key = "templates/findings.md", "templates/progress.md"
    missing = root / manifests[".cursor"][missing_key]
    stale = root / manifests[".cursor"][stale_key]
    missing.unlink()
    stale.write_bytes(b"stale\n")
    if dry_run:
        result = run_read_only(root, "--dry-run")
        assert result.returncode == 0, result.stdout
        assert "This was a dry run. No files were modified." in result.stdout
    else:
        result = run_sync(root)
        assert result.returncode == 0, result.stdout + result.stderr
        assert missing.read_bytes() == (canonical / missing_key).read_bytes()
        assert stale.read_bytes() == (canonical / stale_key).read_bytes()
        skill = root / ".cursor" / "skills" / "planning-with-files" / "SKILL.md"
        hook = root / ".cursor" / "hooks" / "custom.json"
        assert skill.read_bytes() == b"IDE-specific skill; do not overwrite\n"
        assert hook.read_bytes() == b'{"custom": true}\n'
        assert run_read_only(root, "--verify").returncode == 0
