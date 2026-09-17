"""Nested plan-root isolation for the Cursor hook route (issue #212).

The Cursor UserPromptSubmit hooks can still hit the issue #212 failure in the
legacy-root shape: a root task_plan.md at a shared parent cwd plus a nested
project below it carrying its own .planning plan. The PowerShell route also
resolves named plans through resolve-plan-dir.ps1; the shell route retains its
legacy-root-only behavior. Shared semantics:

  * PWF_PLAN_ROOT — every planning-state read goes through the pin; a
    broken pin fails CLOSED with one notice; unset stays byte-identical.
  * Depth-1 nested-root conflict detection — the legacy root plan is always
    a cwd GUESS on this route, so a competing direct-child .planning
    (.active_plan or a <slug>/task_plan.md) refuses injection with the
    warning. The PowerShell warning may also advertise PLAN_ID because that
    route now implements the named-plan selector.

Legacy-root scenarios run against both interpreters through a shared contract;
PowerShell's named-plan capability is asserted explicitly where the routes now
differ.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CURSOR_SH = REPO_ROOT / ".cursor" / "hooks" / "user-prompt-submit.sh"
CURSOR_PS1 = REPO_ROOT / ".cursor" / "hooks" / "user-prompt-submit.ps1"

ROOT_TITLE = "ROOT-LEGACY-PARENT-PLAN"
NESTED_TITLE = "NESTED-PROJECT-PLAN"

SCRUB_VARS = ("PLAN_ID", "PWF_PLAN_ROOT", "PWF_SESSION_ID", "PLANNING_DISABLED")


def pwsh_exe() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def have_sh() -> bool:
    return shutil.which("sh") is not None


class CursorHookContract:
    """Shared scenarios. NOT a TestCase: concrete twins mix this in and
    provide _run, so every assertion runs once per interpreter."""

    SUPPORTS_NAMED_PLAN_PIN = False

    def setUp(self) -> None:  # noqa: N802 (unittest naming)
        self.tmp = Path(tempfile.mkdtemp(prefix="pwf-cursor-nested-"))
        self.workspace = self.tmp / "workspace"
        self.project = self.workspace / "project"
        self.workspace.mkdir(parents=True)

    def tearDown(self) -> None:  # noqa: N802
        shutil.rmtree(self.tmp, ignore_errors=True)

    def build_tree(self, nested: bool = True, nested_pointer: bool = True) -> None:
        (self.workspace / "task_plan.md").write_text(
            f"# {ROOT_TITLE}\n", encoding="utf-8"
        )
        (self.workspace / "progress.md").write_text("# root progress\n", encoding="utf-8")
        if nested:
            plan_b = self.project / ".planning" / "plan-b"
            plan_b.mkdir(parents=True)
            (plan_b / "task_plan.md").write_text(f"# {NESTED_TITLE}\n", encoding="utf-8")
            if nested_pointer:
                (self.project / ".planning" / ".active_plan").write_text(
                    "plan-b\n", encoding="utf-8"
                )

    def build_inner_legacy(self) -> Path:
        # A pinnable root carrying its own legacy-shape plan.
        inner = self.workspace / "inner"
        inner.mkdir(parents=True)
        (inner / "task_plan.md").write_text(f"# {NESTED_TITLE}\n", encoding="utf-8")
        (inner / "progress.md").write_text("# inner progress\n", encoding="utf-8")
        return inner

    def scrubbed_env(self, env_extra: dict | None = None) -> dict:
        env = os.environ.copy()
        for var in SCRUB_VARS:
            env.pop(var, None)
        if env_extra:
            env.update(env_extra)
        return env

    def _run(self, env_extra: dict | None = None) -> subprocess.CompletedProcess[str]:
        raise NotImplementedError

    # -- conflict detection -------------------------------------------------
    def test_parent_cwd_with_nested_plan_injects_nothing(self) -> None:
        self.build_tree(nested=True)
        result = self._run()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn(ROOT_TITLE, result.stdout, "root plan body must not inject")
        self.assertNotIn(NESTED_TITLE, result.stdout)
        self.assertIn("Ambiguous plan", result.stdout)
        self.assertIn("project", result.stdout, "warning must name the nested root")
        self.assertIn("PWF_PLAN_ROOT", result.stdout)

    def test_nested_slug_plan_without_pointer_still_competes(self) -> None:
        self.build_tree(nested=True, nested_pointer=False)
        result = self._run()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Ambiguous plan", result.stdout)
        self.assertNotIn(ROOT_TITLE, result.stdout)

    def test_bare_nested_planning_is_no_conflict(self) -> None:
        self.build_tree(nested=False)
        (self.project / ".planning").mkdir(parents=True)
        result = self._run()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(ROOT_TITLE, result.stdout)
        self.assertNotIn("Ambiguous plan", result.stdout)

    # -- PWF_PLAN_ROOT ------------------------------------------------------
    def test_pin_injects_the_pinned_legacy_root(self) -> None:
        self.build_tree(nested=True)
        inner = self.build_inner_legacy()
        result = self._run({"PWF_PLAN_ROOT": str(inner)})
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(NESTED_TITLE, result.stdout, "pinned root's plan must inject")
        self.assertNotIn(ROOT_TITLE, result.stdout, "cwd plan must not leak through")
        self.assertNotIn("Ambiguous plan", result.stdout, "a pin is explicit")

    def test_pin_with_only_a_named_plan_matches_route_capability(self) -> None:
        self.build_tree(nested=True)
        result = self._run({"PWF_PLAN_ROOT": str(self.project)})
        self.assertEqual(0, result.returncode, result.stderr)
        if self.SUPPORTS_NAMED_PLAN_PIN:
            self.assertIn(NESTED_TITLE, result.stdout)
            self.assertNotIn(ROOT_TITLE, result.stdout)
        else:
            self.assertEqual("", result.stdout.strip())

    def test_broken_pin_notices_and_injects_nothing(self) -> None:
        self.build_tree(nested=True)
        result = self._run({"PWF_PLAN_ROOT": str(self.workspace / "does-not-exist")})
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotEqual("", result.stdout.strip(), "broken pin must emit a notice")
        self.assertIn("PWF_PLAN_ROOT", result.stdout)
        self.assertNotIn(ROOT_TITLE, result.stdout, "must not fall back to cwd plan")
        self.assertNotIn(NESTED_TITLE, result.stdout)

    # -- legacy invariant ---------------------------------------------------
    def test_no_nested_plan_injects_exactly_as_before(self) -> None:
        self.build_tree(nested=False)
        result = self._run()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ACTIVE PLAN", result.stdout)
        self.assertIn(ROOT_TITLE, result.stdout)
        self.assertNotIn("Ambiguous plan", result.stdout)


@unittest.skipUnless(have_sh(), "requires a POSIX sh")
class CursorShNestedRootTests(CursorHookContract, unittest.TestCase):
    def _run(self, env_extra: dict | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["sh", str(CURSOR_SH)],
            cwd=str(self.workspace),
            env=self.scrubbed_env(env_extra),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            timeout=60,
        )


@unittest.skipUnless(pwsh_exe(), "requires PowerShell")
class CursorPs1NestedRootTests(CursorHookContract, unittest.TestCase):
    SUPPORTS_NAMED_PLAN_PIN = True

    def _run(self, env_extra: dict | None = None) -> subprocess.CompletedProcess[str]:
        exe = pwsh_exe()
        assert exe is not None
        return subprocess.run(
            [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(CURSOR_PS1)],
            cwd=str(self.workspace),
            env=self.scrubbed_env(env_extra),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            timeout=120,
        )

if __name__ == "__main__":
    unittest.main()
