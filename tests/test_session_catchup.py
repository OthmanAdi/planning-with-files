import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


SCRIPT_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "skills/planning-with-files/scripts/session-catchup.py"
)


def load_module(script_path: Path):
    spec = importlib.util.spec_from_file_location(
        f"session_catchup_{script_path.stat().st_mtime_ns}",
        script_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SessionCatchupCodexTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.project_dir = self.root / "project"
        self.project_dir.mkdir()
        self.project_path = str(self.project_dir)
        self.sessions_dir = self.root / ".codex/sessions"
        self.sessions_dir.mkdir(parents=True)
        self.codex_script = (
            self.root / ".codex/skills/planning-with-files/scripts/session-catchup.py"
        )
        self.codex_script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SCRIPT_SOURCE, self.codex_script)
        self.module = load_module(self.codex_script)

    def tearDown(self):
        self.tempdir.cleanup()

    def write_codex_session(
        self,
        name,
        *,
        cwd=None,
        source="codex",
        records=(),
        substantial=True,
        mtime=100,
    ):
        path = self.sessions_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        session_records = [
            {
                "timestamp": "2026-04-07T00:00:00.000Z",
                "type": "session_meta",
                "payload": {"cwd": cwd or self.project_path, "source": source},
            }
        ]
        if substantial:
            session_records.append(
                {
                    "timestamp": "2026-04-07T00:00:01.000Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {"type": "output_text", "text": "x" * 6000},
                        ],
                    },
                }
            )
        session_records.extend(records)
        with path.open("w", encoding="utf-8") as f:
            for record in session_records:
                f.write(json.dumps(record) + "\n")
        os.utime(path, (mtime, mtime))
        return path

    def codex_candidates(self, *, thread_id=None):
        updates = {"CODEX_SESSIONS_DIR": str(self.sessions_dir)}
        if thread_id is not None:
            updates["CODEX_THREAD_ID"] = thread_id
        with mock.patch.dict(os.environ, updates, clear=False):
            if thread_id is None:
                os.environ.pop("CODEX_THREAD_ID", None)
            with mock.patch("pathlib.Path.home", return_value=self.root):
                runtime, sessions = self.module.get_session_candidates(self.project_path)
                return runtime, list(sessions)

    def test_codex_variant_finds_matching_project_sessions(self):
        session = self.write_codex_session(
            "rollout-2026-04-07T00-00-00-previous-thread.jsonl"
        )

        runtime, sessions = self.codex_candidates()

        self.assertEqual("codex", runtime)
        self.assertEqual([session], sessions)

    def test_codex_variant_prefers_current_thread_for_same_project(self):
        previous = self.write_codex_session(
            "rollout-2026-04-07T00-00-00-previous-thread.jsonl",
            mtime=200,
        )
        current = self.write_codex_session(
            "rollout-2026-04-07T01-00-00-current-thread.jsonl",
            mtime=100,
        )

        runtime, sessions = self.codex_candidates(thread_id="current-thread")

        self.assertEqual("codex", runtime)
        self.assertEqual([current, previous], sessions)

    def test_codex_variant_skips_small_sessions_and_subagents(self):
        valid = self.write_codex_session(
            "rollout-2026-04-07T00-00-00-valid-thread.jsonl",
            mtime=100,
        )
        self.write_codex_session(
            "rollout-2026-04-07T01-00-00-small-thread.jsonl",
            substantial=False,
            mtime=200,
        )
        self.write_codex_session(
            "rollout-2026-04-07T02-00-00-subagent-thread.jsonl",
            source={"subagent": "worker"},
            mtime=300,
        )

        runtime, sessions = self.codex_candidates()

        self.assertEqual("codex", runtime)
        self.assertEqual([valid], sessions)

    def test_codex_structured_patch_event_marks_planning_update(self):
        messages = [
            {
                "_line_num": 7,
                "type": "event_msg",
                "payload": {
                    "type": "patch_apply_end",
                    "success": True,
                    "changes": {"progress.md": {"operation": "modified"}},
                },
            }
        ]

        self.assertEqual(
            (7, "progress.md"),
            self.module.find_last_planning_update(messages),
        )

    def test_messages_without_line_numbers_are_ignored(self):
        messages = [
            {
                "type": "event_msg",
                "payload": {
                    "type": "patch_apply_end",
                    "success": True,
                    "changes": {"progress.md": {"operation": "modified"}},
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "ignored"}],
                },
            },
        ]

        self.assertEqual((-1, None), self.module.find_last_planning_update(messages))
        self.assertEqual([], self.module.extract_messages_after(messages, -1))

    def test_codex_main_prints_catchup_from_matching_session(self):
        for filename in self.module.PLANNING_FILES:
            (self.project_dir / filename).write_text("# test\n", encoding="utf-8")
        self.write_codex_session(
            "rollout-2026-04-07T00-00-00-previous-thread.jsonl",
            records=[
                {
                    "timestamp": "2026-04-07T00:00:02.000Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "patch_apply_end",
                        "success": True,
                        "changes": {"task_plan.md": {"operation": "modified"}},
                    },
                },
                {
                    "timestamp": "2026-04-07T00:00:03.000Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "Codex summary after planning update",
                            }
                        ],
                    },
                },
            ],
        )

        stdout = io.StringIO()
        with mock.patch.dict(
            os.environ,
            {"CODEX_SESSIONS_DIR": str(self.sessions_dir)},
            clear=False,
        ):
            os.environ.pop("CODEX_THREAD_ID", None)
            with mock.patch("pathlib.Path.home", return_value=self.root):
                with mock.patch.object(
                    self.module.sys,
                    "argv",
                    ["session-catchup.py", self.project_path],
                ):
                    with redirect_stdout(stdout):
                        self.module.main()

        output = stdout.getvalue()
        self.assertIn("SESSION CATCHUP DETECTED", output)
        self.assertIn("Runtime: codex", output)
        self.assertIn("Last planning update: task_plan.md", output)
        self.assertIn("CODEX: Codex summary after planning update", output)

    def test_codex_cli_prints_unicode_when_parent_requests_cp1252(self):
        for filename in self.module.PLANNING_FILES:
            (self.project_dir / filename).write_text("# test\n", encoding="utf-8")
        self.write_codex_session(
            "rollout-2026-04-07T00-00-00-unicode-thread.jsonl",
            records=[
                {
                    "timestamp": "2026-04-07T00:00:02.000Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "patch_apply_end",
                        "success": True,
                        "changes": {"task_plan.md": {"operation": "modified"}},
                    },
                },
                {
                    "timestamp": "2026-04-07T00:00:03.000Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {"type": "output_text", "text": "继续完成中文计划"},
                        ],
                    },
                },
            ],
        )
        env = os.environ.copy()
        env["CODEX_SESSIONS_DIR"] = str(self.sessions_dir)
        env["PYTHONIOENCODING"] = "cp1252"
        env.pop("CODEX_THREAD_ID", None)

        result = subprocess.run(
            [sys.executable, str(self.codex_script), self.project_path],
            capture_output=True,
            encoding="utf-8",
            env=env,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("继续完成中文计划", result.stdout)


if __name__ == "__main__":
    unittest.main()
