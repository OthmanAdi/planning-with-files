import importlib
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / ".hermes" / "plugins" / "planning-with-files"
MODULE_PATH = PLUGIN_ROOT / "__init__.py"
spec = importlib.util.spec_from_file_location(
    "planning_with_files_plugin",
    MODULE_PATH,
    submodule_search_locations=[str(PLUGIN_ROOT)],
)
plugin = importlib.util.module_from_spec(spec)
import sys
sys.modules["planning_with_files_plugin"] = plugin
assert spec.loader is not None
spec.loader.exec_module(plugin)

tools_module = importlib.import_module("planning_with_files_plugin.tools")
hooks_module = importlib.import_module("planning_with_files_plugin.hooks")


class HermesAdapterTests(unittest.TestCase):
    def test_init_creates_default_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = json.loads(tools_module.planning_with_files_init(cwd=tmpdir))
            self.assertEqual(sorted(("task_plan.md", "findings.md", "progress.md")), sorted(result["existing"]))
            for name in ("task_plan.md", "findings.md", "progress.md"):
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
            result = json.loads(tools_module.planning_with_files_status(cwd=tmpdir))
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
                payload = hooks_module.pre_llm_call(user_message="continue the task", is_first_turn=False)
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
            result = json.loads(tools_module.planning_with_files_check_complete(cwd=tmpdir))
            self.assertTrue(result["ok"])
            self.assertIn("Task in progress", result["stdout"])
            self.assertEqual(str(REPO_ROOT / ".hermes" / "skills" / "planning-with-files"), result["skill_root"])

    def test_post_tool_hook_queues_reminder_for_next_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text("# Task Plan\n", encoding="utf-8")
            old_pwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                hooks_module.post_tool_call(
                    tool_name="write_file",
                    session_id="session-1",
                    args={"path": "app.py", "content": "print('hi')"},
                )
                payload = hooks_module.pre_llm_call(
                    user_message="next step",
                    is_first_turn=False,
                    session_id="session-1",
                )
            finally:
                os.chdir(old_pwd)
            self.assertIsNotNone(payload)
            assert payload is not None
            self.assertIn("Update progress.md", payload["context"])

    def test_post_tool_reminder_survives_empty_next_user_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text("# Task Plan\n", encoding="utf-8")
            old_pwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                hooks_module.post_tool_call(
                    tool_name="patch",
                    session_id="session-empty",
                    args={"path": "app.py", "old_string": "hi", "new_string": "hello"},
                )
                payload = hooks_module.pre_llm_call(
                    user_message="",
                    is_first_turn=False,
                    session_id="session-empty",
                )
            finally:
                os.chdir(old_pwd)
            self.assertIsNotNone(payload)
            assert payload is not None
            self.assertIn("Update progress.md", payload["context"])

    def test_status_supports_table_phase_tracking_without_fake_error_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text(
                "| Phase | Status |\n"
                "|-------|--------|\n"
                "| Discovery | complete |\n"
                "| Build | in_progress |\n"
                "| Verify | pending |\n\n"
                "## Errors Encountered\n"
                "| Error | Attempt | Resolution |\n"
                "|-------|---------|------------|\n"
                "| Timeout | 1 | Retry |\n",
                encoding="utf-8",
            )
            result = json.loads(tools_module.planning_with_files_status(cwd=tmpdir))
            self.assertTrue(result["exists"])
            self.assertEqual(3, result["counts"]["total"])
            self.assertEqual(1, result["counts"]["complete"])
            self.assertEqual(1, result["counts"]["in_progress"])
            self.assertEqual(1, result["counts"]["pending"])
            self.assertEqual(1, result["errors_logged"])

    def test_skill_root_env_override_is_supported(self) -> None:
        skill_root = REPO_ROOT / ".hermes" / "skills" / "planning-with-files"
        old_env = os.environ.get("PLANNING_WITH_FILES_SKILL_ROOT")
        os.environ["PLANNING_WITH_FILES_SKILL_ROOT"] = str(skill_root)
        try:
            import planning_with_files_plugin.paths as env_plugin
            env_plugin = importlib.reload(env_plugin)
        finally:
            if old_env is None:
                os.environ.pop("PLANNING_WITH_FILES_SKILL_ROOT", None)
            else:
                os.environ["PLANNING_WITH_FILES_SKILL_ROOT"] = old_env
        self.assertEqual(skill_root, env_plugin.SKILL_ROOT)
        self.assertTrue(env_plugin.TEMPLATES_DIR.is_dir())
        self.assertTrue(env_plugin.SCRIPTS_DIR.is_dir())

    def test_check_complete_reports_completed_plan_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text(
                "### Phase 1: Discovery\n- **Status:** complete\n\n"
                "### Phase 2: Build\n- **Status:** complete\n",
                encoding="utf-8",
            )
            result = json.loads(tools_module.planning_with_files_check_complete(cwd=tmpdir))
            self.assertTrue(result["ok"])
            self.assertIn("ALL PHASES COMPLETE", result["stdout"])
            self.assertTrue(result["complete"])

    def test_check_complete_reports_incomplete_state_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text(
                "### Phase 1: Discovery\n- **Status:** complete\n\n"
                "### Phase 2: Build\n- **Status:** pending\n",
                encoding="utf-8",
            )
            result = json.loads(tools_module.planning_with_files_check_complete(cwd=tmpdir))
            self.assertTrue(result["ok"])
            self.assertFalse(result["complete"])
            self.assertIn("Task in progress", result["stdout"])

    def test_post_tool_hook_deduplicates_by_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text("# Task Plan\n", encoding="utf-8")
            old_pwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                hooks_module.post_tool_call(
                    tool_name="write_file",
                    session_id="session-dedupe",
                    args={"path": "app.py", "content": "print('hi')"},
                )
                hooks_module.post_tool_call(
                    tool_name="patch",
                    session_id="session-dedupe",
                    args={"path": "app.py", "old_string": "hi", "new_string": "hello"},
                )
                payload = hooks_module.pre_llm_call(
                    user_message="continue",
                    is_first_turn=False,
                    session_id="session-dedupe",
                )
            finally:
                os.chdir(old_pwd)
            self.assertIsNotNone(payload)
            assert payload is not None
            self.assertEqual(1, payload["context"].count("Update progress.md"))

    def test_post_tool_hook_isolates_reminders_per_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text("# Task Plan\n", encoding="utf-8")
            old_pwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                hooks_module.post_tool_call(
                    tool_name="write_file",
                    session_id="session-a",
                    args={"path": "app.py", "content": "print('hi')"},
                )
                payload_a = hooks_module.pre_llm_call(
                    user_message="continue",
                    is_first_turn=False,
                    session_id="session-a",
                )
                payload_b = hooks_module.pre_llm_call(
                    user_message="continue",
                    is_first_turn=False,
                    session_id="session-b",
                )
            finally:
                os.chdir(old_pwd)
            self.assertIsNotNone(payload_a)
            assert payload_a is not None
            self.assertIn("Update progress.md", payload_a["context"])
            self.assertIsNotNone(payload_b)
            assert payload_b is not None
            self.assertNotIn("Update progress.md", payload_b["context"])

    def test_post_tool_hook_ignores_non_target_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text("# Task Plan\n", encoding="utf-8")
            old_pwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                hooks_module.post_tool_call(tool_name="read_file", session_id="session-read", args={})
                payload = hooks_module.pre_llm_call(
                    user_message="continue",
                    is_first_turn=False,
                    session_id="session-read",
                )
            finally:
                os.chdir(old_pwd)
            self.assertIsNotNone(payload)
            assert payload is not None
            self.assertNotIn("Update progress.md", payload["context"])

    def test_post_tool_hook_requires_write_like_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text("# Task Plan\n", encoding="utf-8")
            old_pwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                hooks_module.post_tool_call(tool_name="write_file", session_id="session-empty-args", args={})
                payload = hooks_module.pre_llm_call(
                    user_message="continue",
                    is_first_turn=False,
                    session_id="session-empty-args",
                )
            finally:
                os.chdir(old_pwd)
            self.assertIsNotNone(payload)
            assert payload is not None
            self.assertNotIn("Update progress.md", payload["context"])

    def test_post_tool_hook_accepts_patch_old_and_new_string_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text("# Task Plan\n", encoding="utf-8")
            old_pwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                hooks_module.post_tool_call(
                    tool_name="patch",
                    session_id="session-patch-args",
                    args={"path": "app.py", "old_string": "a", "new_string": "b"},
                )
                payload = hooks_module.pre_llm_call(
                    user_message="continue",
                    is_first_turn=False,
                    session_id="session-patch-args",
                )
            finally:
                os.chdir(old_pwd)
            self.assertIsNotNone(payload)
            assert payload is not None
            self.assertIn("Update progress.md", payload["context"])

    def test_pre_llm_hook_returns_context_on_first_turn_without_user_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text("# Task Plan\n\n### Phase 1: Discovery\n", encoding="utf-8")
            root.joinpath("progress.md").write_text("\n".join(f"line {idx}" for idx in range(40)), encoding="utf-8")
            old_pwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                payload = hooks_module.pre_llm_call(user_message="", is_first_turn=True, session_id="first-turn")
            finally:
                os.chdir(old_pwd)
            self.assertIsNotNone(payload)
            assert payload is not None
            self.assertIn("ACTIVE PLAN", payload["context"])
            self.assertNotIn("line 0", payload["context"])
            self.assertIn("line 39", payload["context"])

    def test_pre_llm_hook_returns_none_on_later_empty_turn_without_reminders(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text("# Task Plan\n\n### Phase 1: Discovery\n", encoding="utf-8")
            old_pwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                payload = hooks_module.pre_llm_call(user_message="", is_first_turn=False, session_id="later-empty")
            finally:
                os.chdir(old_pwd)
            self.assertIsNone(payload)

    def test_pre_llm_hook_omits_findings_reminder_when_findings_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            root.joinpath("task_plan.md").write_text("# Task Plan\n\n### Phase 1: Discovery\n", encoding="utf-8")
            root.joinpath("progress.md").write_text("Started\n", encoding="utf-8")
            old_pwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                payload = hooks_module.pre_llm_call(user_message="continue", is_first_turn=False, session_id="no-findings")
            finally:
                os.chdir(old_pwd)
            self.assertIsNotNone(payload)
            assert payload is not None
            self.assertIn("ACTIVE PLAN", payload["context"])
            self.assertNotIn("Read findings.md", payload["context"])

    def test_plugin_manifest_declares_post_tool_hook(self) -> None:
        plugin_yaml = (PLUGIN_ROOT / "plugin.yaml").read_text(encoding="utf-8")
        self.assertIn("post_tool_call", plugin_yaml)

    def test_installed_plugin_resolves_repo_assets_for_completion_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            plugin_copy = workspace / "plugin-copy"
            shutil.copytree(PLUGIN_ROOT, plugin_copy)
            spec = importlib.util.spec_from_file_location(
                "installed_planning_with_files_plugin",
                plugin_copy / "__init__.py",
                submodule_search_locations=[str(plugin_copy)],
            )
            installed_plugin = importlib.util.module_from_spec(spec)
            sys.modules["installed_planning_with_files_plugin"] = installed_plugin
            assert spec.loader is not None
            spec.loader.exec_module(installed_plugin)
            installed_tools = importlib.import_module("installed_planning_with_files_plugin.tools")

            project_dir = workspace / "project"
            project_dir.mkdir()
            project_dir.joinpath("task_plan.md").write_text(
                "### Phase 1: Discovery\n- **Status:** complete\n\n"
                "### Phase 2: Build\n- **Status:** complete\n",
                encoding="utf-8",
            )
            skill_copy = workspace / "skills" / "planning-with-files"
            shutil.copytree(REPO_ROOT / ".hermes" / "skills" / "planning-with-files", skill_copy)

            result = json.loads(installed_tools.planning_with_files_check_complete(cwd=str(project_dir)))
            self.assertTrue(result["ok"])
            self.assertTrue(result["complete"])
            self.assertEqual(str(skill_copy), result["skill_root"])


if __name__ == "__main__":
    unittest.main()
