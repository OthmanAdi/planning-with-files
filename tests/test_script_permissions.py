import stat
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "skills" / "planning-with-files" / "scripts"


class CanonicalScriptPermissionsTests(unittest.TestCase):
    def assert_executable(self, path: Path) -> None:
        mode = path.stat().st_mode
        self.assertTrue(
            mode & stat.S_IXUSR,
            f"{path} is not executable (mode: {oct(mode)})",
        )

    def test_shell_scripts_are_executable(self) -> None:
        self.assert_executable(SCRIPTS_DIR / "check-complete.sh")
        self.assert_executable(SCRIPTS_DIR / "init-session.sh")

    def test_session_catchup_is_executable(self) -> None:
        self.assert_executable(SCRIPTS_DIR / "session-catchup.py")


if __name__ == "__main__":
    unittest.main()
