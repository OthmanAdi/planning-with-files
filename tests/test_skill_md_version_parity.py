"""Regression test: parity-locked SKILL.md and plugin manifests must share a version (v2.37.0+).

Background — the repo ships 14 SKILL.md variants plus plugin.json, marketplace.json
and CITATION.cff. Past releases (v2.34.1, v2.36.0, v2.36.2, v2.36.3) repeatedly
shipped with one or more variants stuck on the old version because the bump was
done by hand across 19 files. This test fails the build the moment that drifts.

Source of truth = canonical English SKILL.md. Every file in PARITY_FILES below
must report the same `metadata.version` (or `version` for JSON/CFF). Lagging
SKILL.md variants (.continue, .gemini, .pi, .kiro) are intentionally on
different schemes and excluded from the lock; the Pi channel's npm package.json
IS locked (see PARITY_JSON_LIKE).

Use `python scripts/bump-version.py X.Y.Z` to bump the entire parity set in one
shot, which is what the release protocol expects.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SKILL = REPO_ROOT / "skills" / "planning-with-files" / "SKILL.md"


PARITY_SKILL_MD = [
    "skills/planning-with-files/SKILL.md",
    "skills/i18n/planning-with-files-ar/SKILL.md",
    "skills/i18n/planning-with-files-de/SKILL.md",
    "skills/i18n/planning-with-files-es/SKILL.md",
    "skills/i18n/planning-with-files-zh/SKILL.md",
    "skills/i18n/planning-with-files-zht/SKILL.md",
    ".codebuddy/skills/planning-with-files/SKILL.md",
    ".codex/skills/planning-with-files/SKILL.md",
    ".cursor/skills/planning-with-files/SKILL.md",
    ".factory/skills/planning-with-files/SKILL.md",
    ".hermes/skills/planning-with-files/SKILL.md",
    ".mastracode/skills/planning-with-files/SKILL.md",
    ".opencode/skills/planning-with-files/SKILL.md",
    ".agents/skills/planning-with-files/SKILL.md",
    "clawhub-upload/SKILL.md",
]

# JSON manifests + citation file
PARITY_JSON_LIKE = [
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    # npm package for the Pi channel (issue #213: stayed at a third-party
    # 1.1.0 for 15 releases because no test locked it to the release version)
    ".pi/skills/planning-with-files/package.json",
]

CITATION_CFF = "CITATION.cff"


SKILL_VERSION_RE = re.compile(r'version:\s*"([^"]+)"')
CFF_VERSION_RE = re.compile(r'^version:\s*([^\s#]+)', re.MULTILINE)


def read_skill_version(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = SKILL_VERSION_RE.search(text)
    if not match:
        raise AssertionError(f"no metadata.version found in {path}")
    return match.group(1)


def read_json_version(path: Path) -> str:
    """Extract the plugin version from plugin.json or marketplace.json.

    plugin.json keeps the version at the top level; marketplace.json carries it
    nested under plugins[0].version. We accept either shape.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if "version" in data:
        return str(data["version"])
    plugins = data.get("plugins") or []
    if plugins and "version" in plugins[0]:
        return str(plugins[0]["version"])
    raise AssertionError(f"no version field found in {path}")


def read_cff_version(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = CFF_VERSION_RE.search(text)
    if not match:
        raise AssertionError(f"no version: line found in {path}")
    return match.group(1).strip().strip('"')


class SkillMdVersionParityTests(unittest.TestCase):
    def test_canonical_version_extractable(self) -> None:
        self.assertTrue(CANONICAL_SKILL.is_file(), CANONICAL_SKILL)
        version = read_skill_version(CANONICAL_SKILL)
        self.assertRegex(version, r"^\d+\.\d+\.\d+")

    def test_all_parity_skill_md_share_canonical_version(self) -> None:
        canonical = read_skill_version(CANONICAL_SKILL)
        drift = []
        missing = []
        for rel in PARITY_SKILL_MD:
            path = REPO_ROOT / rel
            if not path.is_file():
                # clawhub-upload/ is gitignored publish staging: present on the
                # maintainer machine, absent in a fresh clone. Skipping keeps
                # the suite green for contributors (it failed for them before,
                # see PR #181's test notes) while still locking the version
                # whenever the folder exists.
                if rel.startswith("clawhub-upload/"):
                    continue
                missing.append(rel)
                continue
            actual = read_skill_version(path)
            if actual != canonical:
                drift.append((rel, actual))

        self.assertFalse(
            missing,
            f"parity-set SKILL.md files missing on disk: {missing}",
        )
        self.assertFalse(
            drift,
            "Version drift detected. Run "
            "`python scripts/bump-version.py "
            f"{canonical}` to relock the parity set. "
            f"Out-of-sync: {drift}",
        )

    def test_plugin_manifests_match_canonical_version(self) -> None:
        canonical = read_skill_version(CANONICAL_SKILL)
        drift = []
        for rel in PARITY_JSON_LIKE:
            path = REPO_ROOT / rel
            self.assertTrue(path.is_file(), rel)
            actual = read_json_version(path)
            if actual != canonical:
                drift.append((rel, actual))
        self.assertFalse(
            drift,
            "Manifest version drift. "
            f"Run `python scripts/bump-version.py {canonical}` to relock. "
            f"Out-of-sync: {drift}",
        )

    def test_citation_cff_matches_canonical_version(self) -> None:
        canonical = read_skill_version(CANONICAL_SKILL)
        path = REPO_ROOT / CITATION_CFF
        self.assertTrue(path.is_file(), CITATION_CFF)
        actual = read_cff_version(path)
        self.assertEqual(
            canonical,
            actual,
            f"CITATION.cff at {actual!r} drifted from canonical SKILL.md at {canonical!r}. "
            f"Run `python scripts/bump-version.py {canonical}`.",
        )


if __name__ == "__main__":
    unittest.main()
