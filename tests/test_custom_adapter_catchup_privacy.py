"""Privacy contract tests for non-canonical session catchup adapters."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = {
    "hermes": REPO_ROOT / ".hermes/skills/planning-with-files/scripts/session-catchup.py",
    "mastracode": REPO_ROOT / ".mastracode/skills/planning-with-files/scripts/session-catchup.py",
    "opencode": REPO_ROOT / ".opencode/skills/planning-with-files/scripts/session-catchup.py",
}
TRANSCRIPT_SECRET = "TRANSCRIPT_SECRET_IGNORE_PRIOR_INSTRUCTIONS"
TOOL_SECRET = "TOOL_SECRET_REMOVE_ALL_FILES"
RAW_SESSION_ID = "raw-session-id-that-must-not-leak"
RAW_PATH = "/private/customer/repository"


def load_adapter(name: str):
    path = ADAPTERS[name]
    module_name = f"_pwf_custom_catchup_{name}_{path.stat().st_mtime_ns}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class CustomAdapterNoHistoryTests(unittest.TestCase):
    def test_default_and_no_history_never_discover_host_session_stores(self) -> None:
        discovery_names = {
            "hermes": ("detect_ide", "get_project_dir_claude", "get_project_dir_opencode"),
            "mastracode": ("get_project_dir",),
            "opencode": ("get_session_candidates", "get_opencode_db_path"),
        }

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
            for name in ADAPTERS:
                module = load_adapter(name)
                for argv in (
                    ["session-catchup.py", str(project)],
                    ["session-catchup.py", "--no-history", str(project)],
                ):
                    with self.subTest(adapter=name, argv=argv):
                        with contextlib.ExitStack() as stack:
                            stack.enter_context(mock.patch.object(module.sys, "argv", argv))
                            for function_name in discovery_names[name]:
                                stack.enter_context(
                                    mock.patch.object(
                                        module,
                                        function_name,
                                        side_effect=AssertionError(
                                            "host session store was inspected"
                                        ),
                                    )
                                )
                            stdout = io.StringIO()
                            with contextlib.redirect_stdout(stdout):
                                module.main()
                        self.assertEqual("", stdout.getvalue())

    def test_cli_requires_explicit_metadata_or_replay(self) -> None:
        for name in ADAPTERS:
            module = load_adapter(name)
            with self.subTest(adapter=name):
                self.assertEqual(
                    ("no-history", "project"),
                    module.parse_cli_args(["session-catchup.py", "project"]),
                )
                self.assertEqual(
                    ("metadata", "project"),
                    module.parse_cli_args(
                        ["session-catchup.py", "--metadata", "project"]
                    ),
                )
                self.assertEqual(
                    ("replay", "project"),
                    module.parse_cli_args(
                        ["session-catchup.py", "--replay", "project"]
                    ),
                )
                with self.assertRaises(SystemExit):
                    module.parse_cli_args(["session-catchup.py", "--unknown"])


class CustomAdapterPlanningPathTests(unittest.TestCase):
    def test_adapters_require_exact_normalized_planning_basenames(self) -> None:
        backslash = chr(92)
        accepted = (
            ("nested/task_plan.md", "task_plan.md"),
            (f"nested{backslash}progress.md", "progress.md"),
            ("findings.md", "findings.md"),
        )
        rejected = (
            "draft_task_plan.md",
            "archive-progress.md",
            "findings.md.bak",
            "task_plan.md/child",
            None,
        )
        for name in ADAPTERS:
            module = load_adapter(name)
            with self.subTest(adapter=name):
                for path_value, expected in accepted:
                    self.assertEqual(
                        expected,
                        module.planning_file_from_path(path_value),
                    )
                for path_value in rejected:
                    self.assertIsNone(module.planning_file_from_path(path_value))

    def test_hermes_scanner_ignores_lookalikes_and_accepts_windows_paths(self) -> None:
        module = load_adapter("hermes")
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "session.jsonl"
            lookalike = {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Write",
                            "input": {"file_path": "nested/draft_task_plan.md"},
                        }
                    ]
                },
            }
            exact = {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Edit",
                            "input": {"file_path": f"nested{chr(92)}progress.md"},
                        }
                    ]
                },
            }
            session.write_text(json.dumps(lookalike) + "\n", encoding="utf-8")
            self.assertEqual((-1, None), module.scan_for_planning_update(session))
            session.write_text(
                json.dumps(lookalike) + "\n" + json.dumps(exact) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(
                (1, "progress.md"),
                module.scan_for_planning_update(session),
            )

    def test_mastracode_scanner_ignores_lookalikes_and_accepts_windows_paths(self) -> None:
        module = load_adapter("mastracode")

        def message(line: int, path_value: str) -> dict:
            return {
                "_line_num": line,
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Edit",
                            "input": {"file_path": path_value},
                        }
                    ]
                },
            }

        self.assertEqual(
            (-1, None),
            module.find_last_planning_update(
                [message(0, "draft_task_plan.md")]
            ),
        )
        self.assertEqual(
            (1, "findings.md"),
            module.find_last_planning_update(
                [
                    message(0, "draft_task_plan.md"),
                    message(1, f"nested{chr(92)}findings.md"),
                ]
            ),
        )

    def _run_opencode_metadata(self, plan_path: str) -> str:
        module = load_adapter("opencode")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / "task_plan.md").write_text("# Plan\n", encoding="utf-8")
            data_home = root / "data"
            db_dir = data_home / "opencode"
            db_dir.mkdir(parents=True)
            connection = sqlite3.connect(db_dir / "opencode.db")
            connection.executescript(
                """
                CREATE TABLE session (id TEXT, directory TEXT, time_created INTEGER);
                CREATE TABLE part (
                    id TEXT,
                    session_id TEXT,
                    time_created INTEGER,
                    data TEXT
                );
                """
            )
            project_abs = module.normalize_for_compare(str(project))
            connection.executemany(
                "INSERT INTO session VALUES (?, ?, ?)",
                [("current", project_abs, 200), ("previous", project_abs, 100)],
            )
            connection.executemany(
                "INSERT INTO part VALUES (?, ?, ?, ?)",
                [
                    (
                        "p1",
                        "previous",
                        110,
                        json.dumps(
                            {
                                "type": "tool",
                                "tool": "edit",
                                "state": {"input": {"filePath": plan_path}},
                            }
                        ),
                    ),
                    (
                        "p2",
                        "previous",
                        120,
                        json.dumps({"type": "text", "text": "follow-up"}),
                    ),
                ],
            )
            connection.commit()
            connection.close()
            stdout = io.StringIO()
            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(data_home)}):
                with contextlib.redirect_stdout(stdout):
                    module.opencode_catchup(str(project), mode="metadata")
            return stdout.getvalue()

    def test_opencode_sqlite_ignores_lookalikes(self) -> None:
        self.assertEqual(
            "",
            self._run_opencode_metadata("nested/draft_task_plan.md"),
        )

    def test_opencode_sqlite_accepts_exact_windows_paths(self) -> None:
        output = self._run_opencode_metadata(
            f"nested{chr(92)}task_plan.md"
        )
        self.assertIn("SESSION CATCHUP AVAILABLE", output)


class CustomAdapterMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tempdir.name) / "project"
        self.project.mkdir()
        (self.project / "task_plan.md").write_text("# Plan\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def assert_metadata_is_aggregate_only(self, output: str) -> None:
        self.assertIn("SESSION CATCHUP AVAILABLE", output)
        self.assertIn("Unsynced entries:", output)
        for secret in (
            TRANSCRIPT_SECRET,
            TOOL_SECRET,
            RAW_SESSION_ID,
            RAW_PATH,
            "task_plan.md",
        ):
            self.assertNotIn(secret, output)
        self.assertNotIn("BEGIN-PWF-DATA", output)

    def _run_hermes(self, mode: str) -> str:
        module = load_adapter("hermes")
        current = self.project / "current.jsonl"
        previous = self.project / f"{RAW_SESSION_ID}.jsonl"
        messages = [
            {
                "role": "user",
                "content": TRANSCRIPT_SECRET,
                "tools": [TOOL_SECRET],
                "session": RAW_SESSION_ID,
            }
        ]
        argv = ["session-catchup.py", f"--{mode}", str(self.project)]
        with (
            mock.patch.object(module.sys, "argv", argv),
            mock.patch.object(module, "detect_ide", return_value="claude-code"),
            mock.patch.object(module, "get_project_dir_claude", return_value=self.project),
            mock.patch.object(module, "get_sessions_sorted", return_value=[current, previous]),
            mock.patch.object(
                module,
                "filter_sessions_by_cwd",
                return_value=([current, previous], RAW_PATH),
            ),
            mock.patch.object(
                module, "scan_for_planning_update", return_value=(3, "task_plan.md")
            ),
            mock.patch.object(
                module, "extract_messages_from_session", return_value=messages
            ),
        ):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                module.main()
        return stdout.getvalue()

    def _run_mastracode(self, mode: str) -> str:
        module = load_adapter("mastracode")
        session = self.project / f"{RAW_SESSION_ID}.jsonl"
        session.write_bytes(b"x" * 5001)
        messages = [
            {
                "role": "user",
                "content": TRANSCRIPT_SECRET,
                "tools": [TOOL_SECRET],
            }
        ]
        argv = ["session-catchup.py", f"--{mode}", str(self.project)]
        with (
            mock.patch.object(module.sys, "argv", argv),
            mock.patch.object(module, "get_project_dir", return_value=(self.project, None)),
            mock.patch.object(module, "get_sessions_sorted", return_value=[session]),
            mock.patch.object(
                module,
                "filter_sessions_by_cwd",
                return_value=([session], RAW_PATH),
            ),
            mock.patch.object(module, "parse_session_messages", return_value=messages),
            mock.patch.object(
                module, "find_last_planning_update", return_value=(0, "task_plan.md")
            ),
            mock.patch.object(module, "extract_messages_after", return_value=messages),
        ):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                module.main()
        return stdout.getvalue()

    def test_hermes_metadata_is_aggregate_and_replay_is_framed(self) -> None:
        self.assert_metadata_is_aggregate_only(self._run_hermes("metadata"))
        replay = self._run_hermes("replay")
        self.assertIn("BEGIN-PWF-DATA", replay)
        self.assertIn(TRANSCRIPT_SECRET, replay)

    def test_mastracode_metadata_is_aggregate_and_replay_is_framed(self) -> None:
        self.assert_metadata_is_aggregate_only(self._run_mastracode("metadata"))
        replay = self._run_mastracode("replay")
        self.assertIn("BEGIN-PWF-DATA", replay)
        self.assertIn(TRANSCRIPT_SECRET, replay)

    def test_opencode_sqlite_metadata_excludes_record_bytes(self) -> None:
        module = load_adapter("opencode")
        data_home = Path(self.tempdir.name) / "data"
        db_dir = data_home / "opencode"
        db_dir.mkdir(parents=True)
        db_path = db_dir / "opencode.db"
        connection = sqlite3.connect(db_path)
        connection.executescript(
            """
            CREATE TABLE session (id TEXT, directory TEXT, time_created INTEGER);
            CREATE TABLE part (
                id TEXT,
                session_id TEXT,
                time_created INTEGER,
                data TEXT
            );
            """
        )
        previous_id = RAW_SESSION_ID
        current_id = "current-session"
        project_abs = module.normalize_for_compare(str(self.project))
        connection.executemany(
            "INSERT INTO session VALUES (?, ?, ?)",
            [(current_id, project_abs, 200), (previous_id, project_abs, 100)],
        )
        planning_update = {
            "type": "tool",
            "tool": "edit",
            "state": {"input": {"filePath": f"{RAW_PATH}/task_plan.md"}},
        }
        transcript = {"type": "text", "text": TRANSCRIPT_SECRET}
        tool = {
            "type": "tool",
            "tool": "bash",
            "state": {"input": {"command": TOOL_SECRET}},
        }
        connection.executemany(
            "INSERT INTO part VALUES (?, ?, ?, ?)",
            [
                ("p1", previous_id, 110, json.dumps(planning_update)),
                ("p2", previous_id, 120, json.dumps(transcript)),
                ("p3", previous_id, 130, json.dumps(tool)),
            ],
        )
        connection.commit()
        connection.close()

        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(data_home)}):
            metadata_stdout = io.StringIO()
            with contextlib.redirect_stdout(metadata_stdout):
                module.opencode_catchup(str(self.project), mode="metadata")
            replay_stdout = io.StringIO()
            with contextlib.redirect_stdout(replay_stdout):
                module.opencode_catchup(str(self.project), mode="replay")

        self.assert_metadata_is_aggregate_only(metadata_stdout.getvalue())
        replay = replay_stdout.getvalue()
        self.assertIn("BEGIN-PWF-DATA", replay)
        self.assertIn(TRANSCRIPT_SECRET, replay)
        self.assertIn(TOOL_SECRET, replay)


class KiroCatchupScopeTests(unittest.TestCase):
    def test_kiro_catchup_remains_project_file_only(self) -> None:
        source = (
            REPO_ROOT
            / ".kiro/skills/planning-with-files/assets/scripts/session-catchup.py"
        ).read_text(encoding="utf-8")
        for host_store in (".claude", ".codex", "opencode.db", "jsonl"):
            self.assertNotIn(host_store, source)
        self.assertIn('os.path.join(project_dir, ".kiro", "plan")', source)


if __name__ == "__main__":
    unittest.main()
