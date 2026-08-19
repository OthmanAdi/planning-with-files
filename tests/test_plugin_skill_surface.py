"""Guard: the Claude Code plugin route registers the canonical skill only.

Claude Code discovers a plugin's skills by scanning `skills/*/SKILL.md` at one
level, so every directory placed directly under `skills/` is registered for
every plugin user and pays its description in the system prompt of every
session. Measured with `claude plugin details` at v3.10.1, the five language
variants cost about 1,010 of the plugin's roughly 2,254 always-on tokens.

The variants therefore live at `skills/i18n/planning-with-files-<lang>/`, which
the plugin scan does not reach. Nothing about the skill-route install changes:
`npx skills add ... --skill planning-with-files-de` resolves by skill name over
a recursive scan of the repository, and still installs to
`~/.claude/skills/planning-with-files-de/`.

This test fails if a variant is moved (or a new one is added) directly under
`skills/`, which would silently put those descriptions back into every session.
"""
from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"
I18N_DIR = SKILLS_DIR / "i18n"
CANONICAL = "planning-with-files"
EXPECTED_VARIANTS = {
    "planning-with-files-ar",
    "planning-with-files-de",
    "planning-with-files-es",
    "planning-with-files-zh",
    "planning-with-files-zht",
}


def _plugin_registered_skills():
    """Directory names the Claude Code plugin scan registers (skills/*/SKILL.md)."""
    return {d.name for d in SKILLS_DIR.iterdir() if (d / "SKILL.md").is_file()}


class PluginSkillSurfaceTests(unittest.TestCase):
    def test_plugin_registers_canonical_skill_only(self):
        self.assertEqual(
            {CANONICAL},
            _plugin_registered_skills(),
            "every skills/<name>/SKILL.md is registered for all plugin users and "
            "costs its description in every session; language variants belong in "
            "skills/i18n/",
        )

    def test_language_variants_present_and_installable(self):
        found = {d.name for d in I18N_DIR.iterdir() if (d / "SKILL.md").is_file()}
        self.assertEqual(EXPECTED_VARIANTS, found)

    def test_variant_skill_name_matches_its_directory(self):
        # `npx skills add --skill <name>` resolves by the frontmatter name, so
        # the two must not drift apart now that the path no longer states it.
        for name in sorted(EXPECTED_VARIANTS):
            with self.subTest(variant=name):
                text = (I18N_DIR / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn(f"\nname: {name}\n", text)


if __name__ == "__main__":
    unittest.main()
