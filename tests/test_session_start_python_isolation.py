"""An isolated hook parent must also isolate its SessionStart catch-up child."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


INJECTOR = Path(__file__).resolve().parents[1] / "scripts" / "inject-plan.py"


class SessionStartPythonIsolationTests(unittest.TestCase):
    def test_catchup_child_ignores_pythonpath_sitecustomize(self):
        with tempfile.TemporaryDirectory(prefix="pwf-child-isolation-") as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            (project / "task_plan.md").write_text("# Isolated child plan\n", encoding="utf-8")
            poison = root / "poison"
            poison.mkdir()
            marker = root / "startup-executed"
            (poison / "sitecustomize.py").write_text(
                "from pathlib import Path\nPath(%r).write_text('executed')\n" % str(marker),
                encoding="utf-8",
            )
            env = os.environ.copy()
            for name in list(env):
                if name.startswith("PWF_") or name in ("PLAN_ID", "PLANNING_DISABLED", "PYTHONHOME"):
                    env.pop(name)
            env.update(PYTHONPATH=str(poison), XDG_CACHE_HOME=str(root / "cache"), HOME=str(root))

            # Positive control: this harmless startup fixture actually executes
            # in a non-isolated interpreter, so absence below proves isolation.
            control = subprocess.run(
                [sys.executable, "-c", "pass"], cwd=project, env=env,
                capture_output=True, timeout=60,
            )
            self.assertEqual(0, control.returncode, control.stderr)
            self.assertTrue(marker.exists(), "startup fixture did not execute")
            marker.unlink()

            result = subprocess.run(
                [sys.executable, "-I", "-B", str(INJECTOR), "--claude-event=session-start"],
                cwd=project, env=env, input=json.dumps({"session_id": "isolated-parent"}),
                capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            context = json.loads(result.stdout)["hookSpecificOutput"]
            self.assertEqual("SessionStart", context["hookEventName"])
            self.assertIn("Isolated child plan", context["additionalContext"])
            self.assertFalse(marker.exists(), "catch-up child executed PYTHONPATH startup code")
