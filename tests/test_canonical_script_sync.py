"""Regression test: keep top-level scripts/ in sync with canonical skills/.../scripts/.

Background — the repo ships two parallel copies of the helper scripts:

  * `scripts/...`                              — top-level (used by tests, CI, dev)
  * `skills/planning-with-files/scripts/...`   — canonical for the shipped skill;
                                                 sync-ide-folders.py copies this one
                                                 into all `.<ide>/skills/.../scripts/`.

Past PRs (analytics template in v2.29.0, slug-mode in v2.36.0) edited only the
top-level copy and forgot the canonical, so users installing the skill via any IDE
folder ended up with the previous-version script. This test catches that class of
drift up front.

It also exercises sync-ide-folders.py --verify so the IDE-folder mirrors stay
honest after every commit.
"""
from __future__ import annotations

import filecmp
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOP_SCRIPTS = REPO_ROOT / "scripts"
SKILL_SCRIPTS = REPO_ROOT / "skills" / "planning-with-files" / "scripts"

# Files that exist in both locations and must stay byte-identical.
# Excluded intentionally:
#   session-catchup.py — canonical carries Codex-specific logic not in top-level
#   check-continue.sh  — repo CI/validation script, not a user-facing skill script
#   sync-ide-folders.py — repo maintenance tool, not a user-facing skill script
SHARED_SCRIPTS = (
    "init-session.sh",
    "init-session.ps1",
    "check-complete.sh",
    "check-complete.ps1",
    "resolve-plan-dir.sh",
    "resolve-plan-dir.ps1",
    "set-active-plan.sh",
    "set-active-plan.ps1",
    "attest-plan.sh",
    "attest-plan.ps1",
)


class CanonicalScriptSyncTests(unittest.TestCase):
    def test_shared_scripts_match_canonical_copy(self) -> None:
        mismatches = []
        missing_canonical = []
        for name in SHARED_SCRIPTS:
            top = TOP_SCRIPTS / name
            skill = SKILL_SCRIPTS / name
            self.assertTrue(top.is_file(), f"missing top-level script: {top}")
            if not skill.is_file():
                missing_canonical.append(name)
                continue
            if not filecmp.cmp(top, skill, shallow=False):
                mismatches.append(name)

        self.assertFalse(
            missing_canonical,
            "Script(s) exist in scripts/ but not in skills/planning-with-files/scripts/. "
            f"Missing: {missing_canonical}. "
            "Add the missing files to the canonical skill location and re-run "
            "`python scripts/sync-ide-folders.py`.",
        )
        self.assertFalse(
            mismatches,
            "Drift detected between scripts/ and skills/planning-with-files/scripts/. "
            f"Out-of-sync files: {mismatches}. "
            "Update both copies in the same commit, then run "
            "`python scripts/sync-ide-folders.py` to refresh IDE folders.",
        )

    def test_sync_ide_folders_verify_clean(self) -> None:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "sync-ide-folders.py"), "--verify"],
            cwd=str(REPO_ROOT),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            0,
            result.returncode,
            "sync-ide-folders.py --verify reported drift. "
            "Run `python scripts/sync-ide-folders.py` from the repo root to fix.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
