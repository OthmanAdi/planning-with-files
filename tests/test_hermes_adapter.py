import json
import os
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / ".hermes" / "plugins" / "planning-with-files"
MODULE_PATH = PLUGIN_ROOT / "__init__.py"

import importlib.util

spec = importlib.util.spec_from_file_location("planning_with_files_plugin", MODULE_PATH)
plugin = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(plugin)


class HermesAdapterTests(unittest.TestCase):
    def test_init_creates_default_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = json.loads(plugin.planning_with_files_init(cwd=tmpdir))
            self.assertEqual(sorted(plugin.PLANNING_FILES), sorted(result["existing"]))
            for name in plugin.PLANNING_FILES:
                self.assertTrue(Path(tmpdir, name).exists(), name)

    def test_status_summarizes_phase_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text(
                "### Phase 1: Discovery\n- **Status:** complete\n\n"
                "### Phase 2: Build\n- **Status:** in_progress\n\n"
                "### Phase 3: Verify\n- **Status:** pending\n",
                encoding="utf-8",
            )
            root.joinpath("progress.md").write_text("# Progress\n\nValidated setup\n", encoding="utf-8")
            root.joinpath("findings.md").write_text("# Findings\n", encoding="utf-8")
            result = json.loads(plugin.planning_with_files_status(cwd=tmpdir))
            self.assertTrue(result["exists"])
            self.assertEqual(3, result["counts"]["total"])
            self.assertEqual(1, result["counts"]["complete"])
            self.assertEqual(1, result["counts"]["in_progress"])
            self.assertEqual(1, result["counts"]["pending"])
            self.assertIn("Validated setup", result["recent_progress"])

    def test_pre_llm_hook_injects_context_when_plan_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text("# Task Plan\n\n### Phase 1: Discovery\n", encoding="utf-8")
            root.joinpath("progress.md").write_text("# Progress\n\nStarted\n", encoding="utf-8")
            root.joinpath("findings.md").write_text("# Findings\n\n- Confirmed repo structure\n", encoding="utf-8")
            old_pwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                payload = plugin._pre_llm_call(user_message="continue the task", is_first_turn=False)
            finally:
                os.chdir(old_pwd)
            self.assertIsNotNone(payload)
            assert payload is not None
            self.assertIn("ACTIVE PLAN", payload["context"])
            self.assertIn("Started", payload["context"])

    def test_check_complete_reports_incomplete_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text(
                "### Phase 1: Discovery\n- **Status:** complete\n\n"
                "### Phase 2: Build\n- **Status:** pending\n",
                encoding="utf-8",
            )
            result = json.loads(plugin.planning_with_files_check_complete(cwd=tmpdir))
            self.assertTrue(result["ok"])
            self.assertIn("Task in progress", result["stdout"])

    def test_repo_root_env_override_is_supported(self) -> None:
        old_env = os.environ.get("PLANNING_WITH_FILES_REPO_ROOT")
        os.environ["PLANNING_WITH_FILES_REPO_ROOT"] = str(REPO_ROOT)
        try:
            spec = importlib.util.spec_from_file_location(
                "planning_with_files_env_plugin", MODULE_PATH
            )
            env_plugin = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(env_plugin)
        finally:
            if old_env is None:
                os.environ.pop("PLANNING_WITH_FILES_REPO_ROOT", None)
            else:
                os.environ["PLANNING_WITH_FILES_REPO_ROOT"] = old_env
        self.assertEqual(REPO_ROOT, env_plugin.REPO_ROOT)
        self.assertTrue(env_plugin.TEMPLATES_DIR.is_dir())
        self.assertTrue(env_plugin.SCRIPTS_DIR.is_dir())


if __name__ == "__main__":
    unittest.main()
