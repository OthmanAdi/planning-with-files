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

The extra depth also invalidated any install that copies `skills/*` wholesale
into a skills directory: `i18n/` is not a skill, and the five variants land a
level below where the loader and the `/plan-<lang>` commands look for them.
The last check below keeps that shape out of the shipped install docs.
"""
from __future__ import annotations

import re
import subprocess
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


# A copy command whose source is the whole skills/ directory. Prose that
# mentions `skills/*/SKILL.md` (the plugin scan) must not match, so the line
# has to start with the copy verb and the glob has to end the path segment.
WHOLESALE_COPY_RE = re.compile(r"^\s*(?:cp\s|Copy-Item\b).*skills[\\/]\*(?:\s|$)")

MANUAL_SKILL_COPY_COMMANDS = {
    "docs/installation.md": (
        "mkdir -p ~/.claude/skills",
        "cp -r planning-with-files/skills/planning-with-files ~/.claude/skills/",
    ),
    "docs/windows.md": (
        r'New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude\skills" | Out-Null',
        r"Copy-Item -Recurse planning-with-files\skills\planning-with-files",
    ),
}


def _plugin_registered_skills():
    """Directory names the Claude Code plugin scan registers (skills/*/SKILL.md)."""
    return {d.name for d in SKILLS_DIR.iterdir() if (d / "SKILL.md").is_file()}


def _tracked_markdown():
    """Every tracked .md file, via git; glob fallback for non-git checkouts."""
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=off", "ls-files", "--", "*.md"],
            cwd=str(REPO_ROOT),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return [REPO_ROOT / line for line in proc.stdout.splitlines() if line]
    except OSError:
        pass
    return [
        p
        for p in REPO_ROOT.rglob("*.md")
        if ".git" not in p.parts and "node_modules" not in p.parts
    ]


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

    def test_no_doc_installs_by_copying_the_skills_directory(self):
        docs = _tracked_markdown()
        self.assertTrue(docs, "no tracked .md files discovered")
        offenders = []
        for doc in docs:
            if not doc.is_file():
                continue
            for lineno, line in enumerate(
                doc.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if WHOLESALE_COPY_RE.match(line):
                    rel = doc.relative_to(REPO_ROOT).as_posix()
                    offenders.append(f"{rel}:{lineno}: {line.strip()}")
        self.assertFalse(
            offenders,
            "install command copies the whole skills/ directory, which since "
            "v3.11.0 also copies i18n/ (not a skill) and puts the five "
            "variants a level below where the loader and the /plan-<lang> "
            "commands look; name skills/planning-with-files instead: "
            + "; ".join(offenders),
        )

    def test_manual_skill_copies_create_destination_first(self):
        for rel, (create_destination, copy_skill) in MANUAL_SKILL_COPY_COMMANDS.items():
            with self.subTest(doc=rel):
                text = (REPO_ROOT / rel).read_text(encoding="utf-8")
                self.assertIn(create_destination, text)
                self.assertIn(copy_skill, text)
                self.assertLess(
                    text.index(create_destination),
                    text.index(copy_skill),
                    "the skills directory must exist before the canonical skill "
                    "directory is copied into it",
                )


if __name__ == "__main__":
    unittest.main()
