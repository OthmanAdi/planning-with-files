#!/usr/bin/env python3
"""bump-version.py — Atomically bump every parity-locked file to a new version.

The repo intentionally keeps per-IDE frontmatter and per-language prose divergent
across SKILL.md variants, but the `metadata.version` field (plus the version
field in plugin.json, marketplace.json, CITATION.cff) must always agree across
the parity set. Past releases (v2.34.1, v2.36.0, v2.36.2, v2.36.3) repeatedly
hit "missed one variant" regressions because the bump was done by hand.

Run before tagging a release:
    python scripts/bump-version.py 2.37.0
    python scripts/bump-version.py 2.37.0 --dry-run

Maintained targets (19 entries: 18 tracked files plus optional local staging):
    skills/planning-with-files/SKILL.md            (canonical)
    skills/i18n/planning-with-files-{ar,de,es,zh,zht}/SKILL.md
    .{codebuddy,codex,cursor,factory,hermes,mastracode,opencode}/skills/planning-with-files/SKILL.md
    .agents/skills/planning-with-files/SKILL.md    (Agent Skills standard layout)
    clawhub-upload/SKILL.md                        (gitignored; bumped when present)
    .claude-plugin/plugin.json
    .claude-plugin/marketplace.json
    CITATION.cff
    .pi/skills/planning-with-files/package.json    (npm package "planning-with-files"; publish after tagging)

Files intentionally left behind (see LAGGING_FILES; do not bump automatically):
    .continue and .gemini (intentionally behind),
    .pi SKILL.md (no version field; the Pi version lives in its package.json above),
    .kiro (-kiro-suffixed scheme)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


# (path relative to repo root, kind)
# kind: "skill_md", "plugin_json", "marketplace_json", "citation_cff"
PARITY_FILES = [
    ("skills/planning-with-files/SKILL.md", "skill_md"),
    ("skills/i18n/planning-with-files-ar/SKILL.md", "skill_md"),
    ("skills/i18n/planning-with-files-de/SKILL.md", "skill_md"),
    ("skills/i18n/planning-with-files-es/SKILL.md", "skill_md"),
    ("skills/i18n/planning-with-files-zh/SKILL.md", "skill_md"),
    ("skills/i18n/planning-with-files-zht/SKILL.md", "skill_md"),
    (".codebuddy/skills/planning-with-files/SKILL.md", "skill_md"),
    (".codex/skills/planning-with-files/SKILL.md", "skill_md"),
    (".cursor/skills/planning-with-files/SKILL.md", "skill_md"),
    (".factory/skills/planning-with-files/SKILL.md", "skill_md"),
    (".hermes/skills/planning-with-files/SKILL.md", "skill_md"),
    (".mastracode/skills/planning-with-files/SKILL.md", "skill_md"),
    (".opencode/skills/planning-with-files/SKILL.md", "skill_md"),
    (".agents/skills/planning-with-files/SKILL.md", "skill_md"),
    ("clawhub-upload/SKILL.md", "skill_md"),
    (".claude-plugin/plugin.json", "plugin_json"),
    (".claude-plugin/marketplace.json", "marketplace_json"),
    ("CITATION.cff", "citation_cff"),
    # npm package for the Pi channel (issue #213: it sat at a third-party 1.1.0
    # for 15 releases because nothing bumped it). Same single-"version" JSON
    # shape as plugin.json, so the handler is shared. Remember: bumping only
    # changes the file; `npm publish` from .pi/skills/planning-with-files/ is a
    # manual per-release step, like the ClawHub upload.
    (".pi/skills/planning-with-files/package.json", "plugin_json"),
]

# Publish staging that remains parity-locked whenever it exists, but is
# intentionally absent from clean clones because the directory is gitignored.
# Keep these paths in PARITY_FILES so maintainer worktrees still bump and
# validate them as part of the canonical 19-entry release set.
OPTIONAL_PARITY_FILES = {
    "clawhub-upload/SKILL.md": "optional gitignored ClawHub publish staging",
}

# Files left behind on purpose. Documented to make the omission explicit.
LAGGING_FILES = [
    ".continue/skills/planning-with-files/SKILL.md",
    ".gemini/skills/planning-with-files/SKILL.md",
    ".pi/skills/planning-with-files/SKILL.md",       # no version field; npm version lives in its package.json (parity set)
    ".kiro/skills/planning-with-files/SKILL.md",     # kiro scheme (2.32.0-kiro)
]

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?$")


def bump_skill_md(path: Path, new: str, *, dry_run: bool) -> tuple[str | None, str | None]:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r'(version:\s*")([^"]+)(")')
    match = pattern.search(text)
    if not match:
        return None, f"no version field found in {path}"
    old = match.group(2)
    if old == new:
        return old, None
    new_text = pattern.sub(rf'\g<1>{new}\g<3>', text, count=1)
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return old, None


def bump_plugin_or_marketplace(path: Path, new: str, *, dry_run: bool) -> tuple[str | None, str | None]:
    """Bump the version field in plugin.json or marketplace.json.

    Both files keep the canonical plugin version in a single "version": "..."
    pair, but marketplace.json nests it under plugins[0]. We rewrite every
    occurrence in the file (there is only one for our manifests), which keeps
    the script tolerant of either layout.
    """
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r'("version"\s*:\s*")([^"]+)(")')
    matches = list(pattern.finditer(text))
    if not matches:
        return None, f"no version field found in {path}"
    old = matches[0].group(2)
    if all(m.group(2) == new for m in matches):
        return old, None
    new_text = pattern.sub(rf'\g<1>{new}\g<3>', text)
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return old, None


def bump_citation_cff(path: Path, new: str, *, dry_run: bool) -> tuple[str | None, str | None]:
    text = path.read_text(encoding="utf-8")
    # CITATION.cff carries `version: "2.36.3"` (quoted) or `version: 2.36.3`.
    pattern = re.compile(r'^(version:\s*)"?([^"\s#]+)"?(\s*(?:#.*)?)$', re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return None, f"no version field found in {path}"
    old = match.group(2)
    if old == new:
        return old, None
    new_text = pattern.sub(rf'\g<1>"{new}"\g<3>', text, count=1)
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return old, None


HANDLERS = {
    "skill_md": bump_skill_md,
    "plugin_json": bump_plugin_or_marketplace,
    "marketplace_json": bump_plugin_or_marketplace,
    "citation_cff": bump_citation_cff,
}


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("new_version", help="Target semver, e.g. 2.37.0")
    p.add_argument("--dry-run", action="store_true", help="Preview without writing")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    new = args.new_version.lstrip("v")
    if not VERSION_RE.match(new):
        print(f"Error: '{new}' is not a valid semver string.", file=sys.stderr)
        return 2

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Bumping parity set to {new}\n")

    failures: list[str] = []
    changed = 0
    skipped = 0
    optional_missing = 0

    for rel, kind in PARITY_FILES:
        path = REPO_ROOT / rel
        if not path.exists():
            optional_reason = OPTIONAL_PARITY_FILES.get(rel)
            if optional_reason:
                optional_missing += 1
                print(f"  OPTIONAL:  {rel}  (missing; {optional_reason})")
                continue
            failures.append(f"missing: {rel}")
            print(f"  MISSING:   {rel}")
            continue
        handler = HANDLERS[kind]
        old, err = handler(path, new, dry_run=args.dry_run)
        if err:
            failures.append(err)
            print(f"  ERROR:     {rel}  ({err})")
            continue
        if old == new:
            skipped += 1
            print(f"  unchanged: {rel}  (already {new})")
        else:
            changed += 1
            print(f"  bumped:    {rel}  {old} -> {new}")

    print(f"\nChanged: {changed}  Unchanged: {skipped}  Errors: {len(failures)}")
    print(f"Optional gitignored publish staging absent: {optional_missing}")
    print(f"Lagging (not auto-bumped): {len(LAGGING_FILES)}")
    for rel in LAGGING_FILES:
        print(f"  -> {rel}")

    if failures:
        print("\nFAILED:", *failures, sep="\n  ", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
