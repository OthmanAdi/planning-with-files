"""Transparency and runtime-authority checks for shipped planning templates."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_TEMPLATES = REPO_ROOT / "skills" / "planning-with-files" / "templates"
ROOT_TEMPLATES = REPO_ROOT / "templates"
INIT_SCRIPTS = (
    REPO_ROOT / "skills" / "planning-with-files" / "scripts" / "init-session.sh",
    REPO_ROOT / "scripts" / "init-session.sh",
)


def tracked_install_facing_templates() -> tuple[Path, ...]:
    """Return every tracked Markdown template shipped on an install surface."""
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    paths: list[Path] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8").replace("\\", "/")
        if relative.endswith(".md") and "templates" in relative.split("/"):
            paths.append(REPO_ROOT / Path(relative))
    return tuple(paths)


class TemplateTransparencyTests(unittest.TestCase):
    def read_template(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_shipped_planning_templates_have_no_hidden_html_instructions(self) -> None:
        paths = tracked_install_facing_templates()
        self.assertGreater(len(paths), 50)
        for path in paths:
            with self.subTest(path=path):
                body = self.read_template(path)
                self.assertNotIn("<!--", body)
                self.assertNotIn("-->", body)
                self.assertNotIn("attention manipulation", body.lower())

    def test_root_template_copies_match_canonical_sources(self) -> None:
        for name in (
            "analytics_findings.md",
            "analytics_task_plan.md",
            "findings.md",
            "progress.md",
            "task_plan.md",
        ):
            with self.subTest(name=name):
                self.assertEqual(
                    (CANONICAL_TEMPLATES / name).read_bytes(),
                    (ROOT_TEMPLATES / name).read_bytes(),
                )

    def test_auxiliary_template_headings_and_placeholders_are_preserved(self) -> None:
        required_by_name = {
            "findings.md": (
                "## Requirements",
                "## Research Findings",
                "## Technical Decisions",
                "## Issues Encountered",
                "## Resources",
                "## Visual/Browser Findings",
                "| Decision | Rationale |",
                "| Issue | Resolution |",
            ),
            "progress.md": (
                "## Session: [DATE]",
                "### Phase 1: [Title]",
                "### Phase 2: [Title]",
                "## Test Results",
                "## Error Log",
                "## 5-Question Reboot Check",
                "| Test | Input | Expected | Actual | Status |",
                "| Timestamp | Error | Attempt | Resolution |",
            ),
            "analytics_findings.md": (
                "## Data Sources",
                "## Hypothesis Log",
                "## Query Results",
                "## Statistical Findings",
                "## Technical Decisions",
                "## Issues Encountered",
                "## Resources",
                "## Visual/Browser Findings",
                "| Source | Location | Size | Key Fields | Quality Notes |",
                "| Hypothesis | Test Method | Result | Confidence |",
                "| Test | p-value | Effect Size | Conclusion |",
            ),
            "analytics_task_plan.md": (
                "[One sentence describing the analytical objective]",
                "## Next Step",
                "[The single next analytical action. Update whenever phase status changes.]",
                "## Current Phase",
                "## Phases",
                "## Hypotheses",
                "## Decisions Made",
                "## Errors Encountered",
                "## Notes",
                "1. [Hypothesis to test]",
                "| Error | Attempt | Resolution |",
            ),
        }
        for name, required_tokens in required_by_name.items():
            body = self.read_template(CANONICAL_TEMPLATES / name)
            for token in required_tokens:
                with self.subTest(name=name, token=token):
                    self.assertIn(token, body)

        analytics_plan = self.read_template(CANONICAL_TEMPLATES / "analytics_task_plan.md")
        self.assertEqual(
            4,
            sum(line.startswith("### Phase ") for line in analytics_plan.splitlines()),
        )
        self.assertEqual(4, analytics_plan.count("- **Status:**"))
        self.assertEqual(1, analytics_plan.count("- **Status:** in_progress"))
        self.assertEqual(3, analytics_plan.count("- **Status:** pending"))

    def test_shipped_task_plan_templates_have_a_nonempty_next_step_section(self) -> None:
        analytics_paths = [
            path
            for path in tracked_install_facing_templates()
            if path.name == "analytics_task_plan.md"
        ]
        self.assertTrue(analytics_paths, "no shipped analytics task plan templates found")
        paths = [CANONICAL_TEMPLATES / "task_plan.md", *analytics_paths]
        for path in paths:
            with self.subTest(path=path):
                body = self.read_template(path)
                section = re.search(
                    r"(?ms)^## Next Step\s*\n(?P<body>.*?)(?=^## |\Z)",
                    body,
                )
                self.assertIsNotNone(section, f"{path} is missing ## Next Step")
                assert section is not None
                self.assertTrue(
                    section.group("body").strip(),
                    f"{path} has an empty ## Next Step section",
                )

    def test_autonomous_template_names_the_real_gate_authority(self) -> None:
        body = self.read_template(CANONICAL_TEMPLATES / "task_plan_autonomous.md")
        for required in (
            ".mode",
            "phase state",
            "Stop hook state",
            "stop block cap",
            "ledger progress",
            "The gate never executes commands declared in this plan.",
        ):
            with self.subTest(required=required):
                self.assertIn(required, body)

    def test_autonomous_template_does_not_advertise_unsupported_gate_fields(self) -> None:
        body = self.read_template(CANONICAL_TEMPLATES / "task_plan_autonomous.md")
        for unsupported in (
            "## Run Contract",
            "## Model Routing",
            "**Owner:**",
            "**DependsOn:**",
            "**AcceptanceCheck:**",
        ):
            with self.subTest(unsupported=unsupported):
                self.assertNotIn(unsupported, body)

    def test_template_phase_and_status_contract_is_preserved(self) -> None:
        for name in ("task_plan.md", "task_plan_autonomous.md"):
            with self.subTest(name=name):
                body = self.read_template(CANONICAL_TEMPLATES / name)
                self.assertEqual(5, sum(line.startswith("### Phase ") for line in body.splitlines()))
                self.assertEqual(5, body.count("- **Status:**"))
                self.assertEqual(1, body.count("- **Status:** in_progress"))
                self.assertEqual(4, body.count("- **Status:** pending"))

    def test_generated_default_plans_contain_no_hidden_instructions(self) -> None:
        for script in INIT_SCRIPTS:
            with self.subTest(script=script), tempfile.TemporaryDirectory() as tmp:
                env = os.environ.copy()
                env.pop("PLAN_ID", None)
                result = subprocess.run(
                    ["sh", str(script)],
                    cwd=tmp,
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    env=env,
                    check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                body = (Path(tmp) / "task_plan.md").read_text(encoding="utf-8")
                self.assertNotIn("<!--", body)
                self.assertNotIn("attention manipulation", body.lower())


if __name__ == "__main__":
    unittest.main()
