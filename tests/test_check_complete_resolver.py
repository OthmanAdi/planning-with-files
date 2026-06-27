"""Tests for scripts/check-complete.sh resolver integration (v2.40).

Before v2.40, check-complete.sh defaulted to `./task_plan.md` when invoked
without arguments. Any caller running in pure-slug-mode (no root plan, only
`.planning/<slug>/task_plan.md` + `.active_plan`) would receive the
"No task_plan.md found" message even though an active plan existed.

The Stop hook in SKILL.md frontmatter passes the resolved plan path
explicitly, so this was silent: only user-driven invocations or third-party
tooling that called check-complete with no args hit the bug.

v2.40 wires check-complete.sh into resolve-plan-dir.sh when no explicit path is
passed, restoring slug-mode parity.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_COMPLETE = REPO_ROOT / "scripts" / "check-complete.sh"


PLAN_WITH_FIVE_PHASES = """# Task Plan: Smoke

## Phases

### Phase 1
- **Status:** in_progress

### Phase 2
- **Status:** pending

### Phase 3
- **Status:** pending

### Phase 4
- **Status:** pending

### Phase 5
- **Status:** pending
"""

PLAN_ALL_COMPLETE = """# Task Plan: Done

## Phases

### Phase 1
- **Status:** complete

### Phase 2
- **Status:** complete
"""


class CheckCompleteResolverTests(unittest.TestCase):
    def run_check(self, cwd: Path, plan_id: str | None = None, arg: str | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.pop("PLAN_ID", None)
        if plan_id is not None:
            env["PLAN_ID"] = plan_id
        cmd = ["sh", str(CHECK_COMPLETE)]
        if arg is not None:
            cmd.append(arg)
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=env,
            check=False,
        )

    def test_explicit_path_arg_still_works(self) -> None:
        # Backward compat: passing the plan-file path directly bypasses the
        # resolver and operates on that file. The Stop hook in SKILL.md does
        # this; the contract must not change.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "task_plan.md").write_text(PLAN_WITH_FIVE_PHASES, encoding="utf-8")
            result = self.run_check(root, arg="task_plan.md")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("0/5 phases complete", result.stdout)

    def test_no_args_resolves_slug_plan_via_active_pointer(self) -> None:
        # Regression for v2.40: with only .planning/<slug>/task_plan.md and an
        # .active_plan pointer, no-args invocation must resolve the slug plan
        # instead of falling back to "no task_plan.md".
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_dir = root / ".planning" / "2026-05-21-smoke"
            plan_dir.mkdir(parents=True)
            (plan_dir / "task_plan.md").write_text(PLAN_WITH_FIVE_PHASES, encoding="utf-8")
            (root / ".planning" / ".active_plan").write_text("2026-05-21-smoke\n", encoding="utf-8")
            result = self.run_check(root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("0/5 phases complete", result.stdout)
            self.assertNotIn("No task_plan.md found", result.stdout)

    def test_no_args_resolves_via_plan_id_env(self) -> None:
        # PLAN_ID env takes precedence over .active_plan in the resolver. The
        # check-complete script should honor that exact chain.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            alpha = root / ".planning" / "alpha"
            beta = root / ".planning" / "beta"
            alpha.mkdir(parents=True)
            beta.mkdir(parents=True)
            (alpha / "task_plan.md").write_text(PLAN_ALL_COMPLETE, encoding="utf-8")
            (beta / "task_plan.md").write_text(PLAN_WITH_FIVE_PHASES, encoding="utf-8")
            (root / ".planning" / ".active_plan").write_text("beta\n", encoding="utf-8")
            # PLAN_ID env should override .active_plan, pointing at alpha (all complete).
            result = self.run_check(root, plan_id="alpha")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("ALL PHASES COMPLETE", result.stdout)

    def test_no_args_legacy_root_plan_still_works(self) -> None:
        # Backward compat: when no slug-mode plans exist but a root-level
        # task_plan.md does, the resolver returns empty and we fall back to the
        # legacy root path. v1.x users keep working.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "task_plan.md").write_text(PLAN_WITH_FIVE_PHASES, encoding="utf-8")
            result = self.run_check(root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("0/5 phases complete", result.stdout)

    def test_no_args_no_plan_anywhere_clean_message(self) -> None:
        # If no plan exists in either location, the script must say so and exit
        # 0 (Stop hook contract).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_check(root)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("No task_plan.md found", result.stdout)


if __name__ == "__main__":
    unittest.main()
