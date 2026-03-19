import importlib.util
import shutil
import tempfile
import unittest
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
        self.project_path = "/tmp/project"
        self.codex_script = (
            self.root / ".codex/skills/planning-with-files/scripts/session-catchup.py"
        )
        self.codex_script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SCRIPT_SOURCE, self.codex_script)
        self.module = load_module(self.codex_script)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_codex_variant_skips_when_only_codex_sessions_exist(self):
        (self.root / ".codex/sessions").mkdir(parents=True, exist_ok=True)

        with mock.patch("pathlib.Path.home", return_value=self.root):
            project_dir, skip_reason = self.module.get_project_dir(self.project_path)

        self.assertIsNone(project_dir)
        self.assertIn("~/.codex/sessions", skip_reason)
        self.assertIn("not implemented yet", skip_reason)

    def test_codex_variant_uses_claude_path_when_project_exists(self):
        (self.root / ".codex/sessions").mkdir(parents=True, exist_ok=True)
        expected = self.root / ".claude/projects/-tmp-project"
        expected.mkdir(parents=True, exist_ok=True)

        with mock.patch("pathlib.Path.home", return_value=self.root):
            project_dir, skip_reason = self.module.get_project_dir(self.project_path)

        self.assertEqual(expected, project_dir)
        self.assertIsNone(skip_reason)


if __name__ == "__main__":
    unittest.main()
