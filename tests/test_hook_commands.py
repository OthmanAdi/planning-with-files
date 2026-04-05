import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_FILES = [
    REPO_ROOT / "skills/planning-with-files/SKILL.md",
    REPO_ROOT / "skills/planning-with-files-zh/SKILL.md",
    REPO_ROOT / "skills/planning-with-files-zht/SKILL.md",
]


def extract_commands(skill_path: Path) -> list[str]:
    text = skill_path.read_text(encoding="utf-8")
    return re.findall(r'^\s*command: "(.*)"\s*$', text, re.MULTILINE)


class HookCommandTests(unittest.TestCase):
    def test_all_hook_commands_dispatch_through_sh(self) -> None:
        for skill_path in SKILL_FILES:
            with self.subTest(skill=str(skill_path.relative_to(REPO_ROOT))):
                commands = extract_commands(skill_path)
                self.assertTrue(commands, "expected at least one hook command")
                for command in commands:
                    self.assertTrue(
                        command.startswith("sh -lc "),
                        f"hook command should dispatch through sh -lc: {command}",
                    )


if __name__ == "__main__":
    unittest.main()
