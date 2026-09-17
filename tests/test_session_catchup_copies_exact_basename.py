"""Every shipped session-catchup.py copy must anchor only on exact planning filenames.

PR #248 replaced suffix matching with an exact-basename rule in the copies the
sync tool maintains. Three more copies live outside that tool: the root
scripts/session-catchup.py (the Claude Code plugin install path) and the five
translated skills/i18n copies. This test loads every copy so the boundary
cannot drift again in one of them.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

# .kiro ships a different program that reads .kiro/plan/*.md and never scans
# transcripts, so it has no planning-path boundary to check.
EXCLUDED_PARTS = {".kiro", "clawhub-upload", "node_modules", "__pycache__"}

LOOKALIKES = (
    "draft_task_plan.md",
    "archive-progress.md",
    "findings.md.bak",
    "task_plan.md/child",
    "nested/my_task_plan.md",
)
EXACT = (
    ("task_plan.md", "task_plan.md"),
    ("nested/findings.md", "findings.md"),
    ("C:" + chr(92) + "proj" + chr(92) + "progress.md", "progress.md"),
)


def shipped_copies() -> list[Path]:
    copies = []
    for path in sorted(REPO_ROOT.rglob("session-catchup.py")):
        relative = path.relative_to(REPO_ROOT)
        if EXCLUDED_PARTS.intersection(relative.parts):
            continue
        copies.append(path)
    return copies


def load_copy(path: Path):
    name = f"_pwf_catchup_copy_{abs(hash(str(path)))}_{path.stat().st_mtime_ns}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, path
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class SessionCatchupCopiesExactBasenameTests(unittest.TestCase):
    def test_inventory_covers_root_and_translations(self) -> None:
        relatives = {copy.relative_to(REPO_ROOT).as_posix() for copy in shipped_copies()}
        self.assertIn("scripts/session-catchup.py", relatives)
        self.assertIn("skills/planning-with-files/scripts/session-catchup.py", relatives)
        for lang in ("ar", "de", "es", "zh", "zht"):
            self.assertIn(f"skills/i18n/planning-with-files-{lang}/scripts/session-catchup.py", relatives)
        self.assertGreaterEqual(len(relatives), 18)

    def test_no_copy_keeps_suffix_matching(self) -> None:
        for copy in shipped_copies():
            text = copy.read_text(encoding="utf-8")
            with self.subTest(copy=copy.relative_to(REPO_ROOT).as_posix()):
                self.assertNotIn(".endswith(pf)", text)
                self.assertNotIn("'%task_plan.md'", text)
                self.assertNotIn("'%findings.md'", text)
                self.assertNotIn("'%progress.md'", text)

    def test_every_copy_matches_exact_basenames_only(self) -> None:
        for copy in shipped_copies():
            module = load_copy(copy)
            helper = getattr(module, "planning_file_from_path")
            with self.subTest(copy=copy.relative_to(REPO_ROOT).as_posix()):
                for lookalike in LOOKALIKES:
                    self.assertIsNone(helper(lookalike), lookalike)
                for path_value, expected in EXACT:
                    self.assertEqual(expected, helper(path_value), path_value)
                self.assertIsNone(helper(None))
                self.assertIsNone(helper(""))

    def test_root_plugin_scanner_ignores_later_lookalike_write(self) -> None:
        module = load_copy(REPO_ROOT / "scripts" / "session-catchup.py")

        def tool_use(file_path: str) -> str:
            return json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Write",
                                "input": {"file_path": file_path},
                            }
                        ]
                    },
                }
            )

        lines = [
            json.dumps({"type": "user", "message": {"content": "start"}}),
            tool_use("/proj/task_plan.md"),
            json.dumps({"type": "assistant", "message": {"content": "later"}}),
            tool_use("/proj/draft_task_plan.md"),
            tool_use("/proj/notes/progress.md.bak"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "session.jsonl"
            session.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.assertEqual((1, "task_plan.md"), module.scan_for_planning_update(session))


if __name__ == "__main__":
    unittest.main()
