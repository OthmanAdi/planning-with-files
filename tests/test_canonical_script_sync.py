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
# session-catchup.py is intentionally NOT in this list — the canonical copy carries
# Codex-specific catchup logic that does not (yet) live at the top level.
SHARED_SCRIPTS = (
    "init-session.sh",
    "init-session.ps1",
    "check-complete.sh",
    "check-complete.ps1",
)


class CanonicalScriptSyncTests(unittest.TestCase):
    def test_shared_scripts_match_canonical_copy(self) -> None:
        mismatches = []
        for name in SHARED_SCRIPTS:
            top = TOP_SCRIPTS / name
            skill = SKILL_SCRIPTS / name
            self.assertTrue(top.is_file(), f"missing top-level script: {top}")
            self.assertTrue(skill.is_file(), f"missing canonical skill script: {skill}")
            if not filecmp.cmp(top, skill, shallow=False):
                mismatches.append(name)

        self.assertFalse(
            mismatches,
            "Drift detected between scripts/ and skills/planning-with-files/scripts/. "
            f"Out-of-sync files: {mismatches}. "
            "Update both copies in the same PR (see CHANGELOG v2.36.0 for the original "
            "miss). After updating the canonical skill copy, run "
            "`python scripts/sync-ide-folders.py` to refresh IDE folders.",
        )

    def test_sync_ide_folders_verify_clean(self) -> None:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "sync-ide-folders.py"), "--verify"],
            cwd=str(REPO_ROOT),
            text=True,
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
