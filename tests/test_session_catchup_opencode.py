"""Tests for the OpenCode SQLite session catchup path (v2.38.0).

Builds a minimal SQLite DB matching the sst/opencode dev schema
(session, part with JSON `data` column), points the script at it, and
verifies the catchup output picks up the most recent planning-file edit.

The schema reference is sst/opencode @ 2026-05-14:
  session (id, directory, time_created, ...)
  part    (id, session_id, message_id, time_created, data TEXT JSON)
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from contextlib import redirect_stdout


REPO_ROOT = Path(__file__).resolve().parents[1]
# Prefer the canonical (skills/) copy — it is what users get via npx skills add.
SCRIPT_PATH = REPO_ROOT / "skills" / "planning-with-files" / "scripts" / "session-catchup.py"


def load_module():
    spec = importlib.util.spec_from_file_location("_pwf_session_catchup", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class OpenCodeSchemaSeed:
    """Builds an opencode.db with two sessions for a given project directory."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self._init_schema()

    def _init_schema(self) -> None:
        c = self.conn.cursor()
        c.executescript(
            """
            CREATE TABLE session (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                directory TEXT NOT NULL,
                slug TEXT,
                title TEXT,
                version TEXT,
                workspace_id TEXT,
                agent TEXT,
                model TEXT,
                time_created INTEGER,
                time_updated INTEGER,
                time_compacting INTEGER,
                time_archived INTEGER
            );
            CREATE TABLE part (
                id TEXT PRIMARY KEY,
                message_id TEXT,
                session_id TEXT NOT NULL,
                time_created INTEGER,
                time_updated INTEGER,
                data TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def add_session(self, sid: str, directory: str, time_created: int) -> None:
        self.conn.execute(
            "INSERT INTO session (id, directory, time_created) VALUES (?, ?, ?)",
            (sid, directory, time_created),
        )
        self.conn.commit()

    def add_part(self, part_id: str, sid: str, time_created: int, data: dict) -> None:
        self.conn.execute(
            "INSERT INTO part (id, session_id, time_created, data) VALUES (?, ?, ?, ?)",
            (part_id, sid, time_created, json.dumps(data)),
        )
        self.conn.commit()

    def add_raw_part(self, part_id: str, sid: str, time_created: int, data: str) -> None:
        self.conn.execute(
            "INSERT INTO part (id, session_id, time_created, data) VALUES (?, ?, ?, ?)",
            (part_id, sid, time_created, data),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


class OpenCodeCatchupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="pwf-opencode-"))
        self.data_root = self.tmp / "data" / "opencode"
        self.data_root.mkdir(parents=True)
        self.db_path = self.data_root / "opencode.db"
        self.project_dir = self.tmp / "myproject"
        self.project_dir.mkdir()

        # Point the script at our fake xdg path.
        os.environ["XDG_DATA_HOME"] = str(self.tmp / "data")

        self.module = load_module()

        self.seed = OpenCodeSchemaSeed(self.db_path)
        project_abs = str(self.project_dir.resolve())
        # Older "previous" session that wrote to task_plan.md, then made a follow-up edit.
        self.seed.add_session("ses_old", project_abs, 1_000_000)
        self.seed.add_part(
            "prt_0",
            "ses_old",
            1_000_010,
            {
                "type": "tool",
                "tool": "write",
                "callID": "c0",
                "state": {"input": {"filePath": f"{project_abs}/task_plan.md", "content": "x"}},
            },
        )
        self.seed.add_part(
            "prt_1",
            "ses_old",
            1_000_020,
            {
                "type": "tool",
                "tool": "edit",
                "callID": "c1",
                "state": {"input": {"filePath": f"{project_abs}/src/lib.py"}},
            },
        )
        # Current (newest) session — gets skipped by the script.
        self.seed.add_session("ses_current", project_abs, 1_000_100)

    def tearDown(self) -> None:
        self.seed.close()
        os.environ.pop("XDG_DATA_HOME", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_db_path_resolves(self) -> None:
        resolved = self.module.get_opencode_db_path()
        self.assertEqual(resolved, self.db_path)

    def test_catchup_reports_unsynced_edits(self) -> None:
        buf = StringIO()
        with redirect_stdout(buf):
            self.module.opencode_catchup(str(self.project_dir), mode="replay")
        output = buf.getvalue()
        self.assertIn("SESSION CATCHUP DETECTED (IDE: opencode)", output)
        self.assertIn(self.module.safe_session_label("ses_old"), output)
        self.assertNotIn("ses_old", output)
        self.assertIn("Tool edit", output, "follow-up edit after plan write should appear in catchup")

    def test_malformed_tool_shapes_are_skipped_without_hiding_healthy_parts(self) -> None:
        self.seed.add_part(
            "prt_bad_state",
            "ses_old",
            1_000_012,
            {"type": "tool", "tool": "edit", "state": "broken"},
        )
        self.seed.add_part(
            "prt_bad_input",
            "ses_old",
            1_000_015,
            {
                "type": "tool",
                "tool": "edit",
                "state": {"input": "broken"},
            },
        )
        self.seed.add_raw_part("prt_null", "ses_old", 1_000_016, "null")
        self.seed.add_raw_part("prt_array", "ses_old", 1_000_017, "[]")
        self.seed.add_part(
            "prt_nonstring_tool", "ses_old", 1_000_018, {"type": "tool", "tool": 5}
        )
        self.seed.add_part(
            "prt_object_text", "ses_old", 1_000_019, {"type": "text", "text": {"a": 1}}
        )

        buf = StringIO()
        with redirect_stdout(buf):
            self.module.opencode_catchup(str(self.project_dir), mode="replay")

        self.assertIn("SESSION CATCHUP DETECTED (IDE: opencode)", buf.getvalue())
        self.assertIn("Tool edit", buf.getvalue())

    def test_invalid_json_part_is_skipped_without_hiding_healthy_parts(self) -> None:
        self.seed.add_raw_part("prt_bad_json", "ses_old", 1_000_005, "not json")

        buf = StringIO()
        with redirect_stdout(buf):
            self.module.opencode_catchup(str(self.project_dir), mode="replay")

        self.assertIn("SESSION CATCHUP DETECTED (IDE: opencode)", buf.getvalue())
        self.assertIn("Tool edit", buf.getvalue())

    def test_metadata_mode_excludes_session_tool_and_path_bytes(self) -> None:
        buf = StringIO()
        with redirect_stdout(buf):
            self.module.opencode_catchup(str(self.project_dir), mode="metadata")
        output = buf.getvalue()

        self.assertIn("SESSION CATCHUP AVAILABLE", output)
        self.assertIn("Unsynced entries: 1", output)
        for leaked in ("ses_old", "Tool edit", "src/lib.py", str(self.project_dir)):
            self.assertNotIn(leaked, output)
        self.assertNotIn("BEGIN-PWF-DATA", output)

    def test_catchup_silent_when_no_plan_edit(self) -> None:
        # Replace DB with one that has no planning-file edits.
        self.seed.close()
        self.db_path.unlink()
        self.seed = OpenCodeSchemaSeed(self.db_path)
        project_abs = str(self.project_dir.resolve())
        self.seed.add_session("ses_a", project_abs, 1_000_000)
        self.seed.add_part(
            "prt_x",
            "ses_a",
            1_000_010,
            {"type": "tool", "tool": "edit", "state": {"input": {"filePath": "unrelated.py"}}},
        )
        self.seed.add_session("ses_b", project_abs, 1_000_100)

        buf = StringIO()
        with redirect_stdout(buf):
            self.module.opencode_catchup(str(self.project_dir), mode="metadata")
        self.assertEqual("", buf.getvalue().strip())

    def test_lookalike_planning_filename_does_not_anchor_catchup(self) -> None:
        self.seed.close()
        self.db_path.unlink()
        self.seed = OpenCodeSchemaSeed(self.db_path)
        project_abs = str(self.project_dir.resolve())
        self.seed.add_session("ses_a", project_abs, 1_000_000)
        self.seed.add_part(
            "prt_x",
            "ses_a",
            1_000_010,
            {
                "type": "tool",
                "tool": "write",
                "state": {
                    "input": {"filePath": f"{project_abs}/draft_task_plan.md"}
                },
            },
        )
        # A later part makes the case discriminating: suffix matching would
        # anchor on the lookalike and report this part as unsynced context.
        self.seed.add_part(
            "prt_y",
            "ses_a",
            1_000_020,
            {
                "type": "tool",
                "tool": "edit",
                "state": {"input": {"filePath": "src/after.py"}},
            },
        )
        self.seed.add_session("ses_b", project_abs, 1_000_100)

        buf = StringIO()
        with redirect_stdout(buf):
            self.module.opencode_catchup(str(self.project_dir), mode="metadata")
        self.assertEqual("", buf.getvalue().strip())

    def test_windows_separator_planning_path_anchors_catchup(self) -> None:
        self.seed.close()
        self.db_path.unlink()
        self.seed = OpenCodeSchemaSeed(self.db_path)
        project_abs = str(self.project_dir.resolve())
        windows_plan = project_abs.replace("/", chr(92)) + chr(92) + "progress.md"
        self.seed.add_session("ses_a", project_abs, 1_000_000)
        self.seed.add_part(
            "prt_x",
            "ses_a",
            1_000_010,
            {
                "type": "tool",
                "tool": "edit",
                "state": {"input": {"filePath": windows_plan}},
            },
        )
        self.seed.add_part(
            "prt_y",
            "ses_a",
            1_000_020,
            {
                "type": "tool",
                "tool": "edit",
                "state": {"input": {"filePath": "src/after.py"}},
            },
        )
        self.seed.add_session("ses_b", project_abs, 1_000_100)

        buf = StringIO()
        with redirect_stdout(buf):
            self.module.opencode_catchup(str(self.project_dir), mode="metadata")
        self.assertIn("SESSION CATCHUP AVAILABLE", buf.getvalue())
    def test_catchup_silent_when_db_missing(self) -> None:
        os.environ["XDG_DATA_HOME"] = str(self.tmp / "nonexistent")
        # Reload module to pick up the new env path.
        mod = load_module()
        buf = StringIO()
        with redirect_stdout(buf):
            mod.opencode_catchup(str(self.project_dir), mode="metadata")
        self.assertEqual("", buf.getvalue().strip())

    def test_no_history_mode_does_not_resolve_or_open_database(self) -> None:
        original = self.module.get_opencode_db_path

        def forbidden():
            raise AssertionError("OpenCode session database was inspected")

        self.module.get_opencode_db_path = forbidden
        try:
            buf = StringIO()
            with redirect_stdout(buf):
                self.module.opencode_catchup(
                    str(self.project_dir), mode="no-history"
                )
            self.assertEqual("", buf.getvalue())
        finally:
            self.module.get_opencode_db_path = original


if __name__ == "__main__":
    unittest.main()
