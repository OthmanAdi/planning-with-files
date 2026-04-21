#!/usr/bin/env python3
"""
sync-ide-folders.py — Syncs shared files from the canonical source
(skills/planning-with-files/) to all IDE-specific folders.

Run this from the repo root before releases:
    python scripts/sync-ide-folders.py

What it syncs:
  - Templates   (findings.md, progress.md, task_plan.md)
  - References  (examples.md, reference.md)
  - Scripts     (check-complete.sh/.ps1, init-session.sh/.ps1, session-catchup.py)

What it NEVER touches:
  - SKILL.md           (IDE-specific frontmatter differs per IDE)
  - IDE-specific files  (hooks, prompts, package.json, steering files)

Use --dry-run to preview changes without writing anything.
Use --verify  to check for drift without making changes (exits 1 if drift found).
"""

import argparse
import shutil
import sys
import hashlib
from pathlib import Path

# ─── Canonical source ──────────────────────────────────────────────
CANONICAL = Path("skills/planning-with-files")

# ─── Shared source files (relative to CANONICAL) ──────────────────
TEMPLATES = [
    "templates/findings.md",
    "templates/progress.md",
    "templates/task_plan.md",
]

REFERENCES = [
    "examples.md",
    "reference.md",
]

SCRIPTS = [
    "scripts/check-complete.sh",
    "scripts/check-complete.ps1",
    "scripts/init-session.sh",
    "scripts/init-session.ps1",
    "scripts/session-catchup.py",
]

# ─── IDE sync manifests ───────────────────────────────────────────
# Each IDE maps: canonical_source_file -> target_path (relative to repo root)
# Only files listed here are synced. Everything else is untouched.

def _build_manifest(base, *, ref_style="flat", template_dirs=None,
                    include_scripts=True, extra_template_dirs=None):
    """Build a sync manifest for an IDE folder.

    Args:
        base: IDE skill folder path (e.g. ".gemini/skills/planning-with-files")
        ref_style: "flat" = examples.md at root, "subdir" = references/examples.md
        template_dirs: list of template subdirs (default: ["templates/"])
        include_scripts: whether to sync scripts
        extra_template_dirs: additional dirs to also receive template copies
    """
    manifest = {}
    b = Path(base)

    # Templates
    if template_dirs is None:
        template_dirs = ["templates/"]
    for tdir in template_dirs:
        for t in TEMPLATES:
            filename = Path(t).name  # e.g. "findings.md"
            manifest[t] = str(b / tdir / filename)

    # Extra template locations (e.g. assets/templates/ in codex, codebuddy)
    if extra_template_dirs:
        for tdir in extra_template_dirs:
            for t in TEMPLATES:
                filename = Path(t).name
                manifest[f"{t}__extra_{tdir}"] = str(b / tdir / filename)

    # References
    if ref_style == "flat":
        for r in REFERENCES:
            manifest[r] = str(b / r)
    elif ref_style == "subdir":
        for r in REFERENCES:
            manifest[r] = str(b / "references" / r)
    # ref_style == "skip" means don't sync references (IDE uses custom format)

    # Scripts
    if include_scripts:
        for s in SCRIPTS:
            manifest[s] = str(b / s)

    return manifest


IDE_MANIFESTS = {
    ".cursor": _build_manifest(
        ".cursor/skills/planning-with-files",
        ref_style="flat",
        include_scripts=False,
        # Cursor hooks are IDE-specific, not synced
    ),

    ".gemini": _build_manifest(
        ".gemini/skills/planning-with-files",
        ref_style="subdir",
        include_scripts=True,
    ),

    ".codex": _build_manifest(
        ".codex/skills/planning-with-files",
        ref_style="subdir",
        include_scripts=True,
    ),

    # .openclaw, .kilocode, .adal, .agent removed in v2.24.0 (IDE audit)
    # These IDEs use the standard Agent Skills spec — install via npx skills add

    ".pi": _build_manifest(
        ".pi/skills/planning-with-files",
        ref_style="flat",
        include_scripts=True,
        # package.json and README.md are IDE-specific, not synced
    ),

    ".continue": _build_manifest(
        ".continue/skills/planning-with-files",
        ref_style="flat",
        template_dirs=[],  # Continue has no templates dir
        include_scripts=True,
        # .continue/prompts/ is IDE-specific, not synced
    ),

    ".codebuddy": _build_manifest(
        ".codebuddy/skills/planning-with-files",
        ref_style="subdir",
        include_scripts=True,
    ),

    ".factory": _build_manifest(
        ".factory/skills/planning-with-files",
        ref_style="skip",  # Uses combined references.md, not synced
        include_scripts=True,
    ),

    ".opencode": _build_manifest(
        ".opencode/skills/planning-with-files",
        ref_style="flat",
        include_scripts=False,
    ),

    # Kiro: maintained under .kiro/ (skill + wrappers); not synced from canonical scripts/.
    ".kiro": {},
}


# ─── Utility functions ─────────────────────────────────────────────

def file_hash(path):
    """Return SHA-256 hash of a file, or None if it doesn't exist."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def sync_file(src, dst, *, dry_run=False):
    """Copy src to dst. Returns (action, detail) tuple.

    Actions: "updated", "created", "skipped" (already identical), "missing_src"
    """
    if not src.exists():
        return "missing_src", f"Canonical file not found: {src}"

    src_hash = file_hash(src)
    dst_hash = file_hash(dst)

    if src_hash == dst_hash:
        return "skipped", "Already up to date"

    action = "created" if dst_hash is None else "updated"

    if not dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    return action, f"{'Would ' if dry_run else ''}{action}: {dst}"


# ─── Main ──────────────────────────────────────────────────────────

def parse_args(argv=None):
    """Parse CLI arguments for sync behavior."""
    parser = argparse.ArgumentParser(
        description=(
            "Sync shared planning-with-files assets from canonical source "
            "to IDE-specific folders."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Check for drift only; exit with code 1 if drift is found.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    dry_run = args.dry_run
    verify = args.verify

    # Must run from repo root
    if not CANONICAL.exists():
        print(f"Error: Canonical source not found at {CANONICAL}/")
        print("Run this script from the repo root.")
        sys.exit(1)

    print(f"{'[DRY RUN] ' if dry_run else ''}{'[VERIFY] ' if verify else ''}"
          f"Syncing from {CANONICAL}/\n")

    stats = {"updated": 0, "created": 0, "skipped": 0, "missing_src": 0, "drift": 0}

    for ide_name, manifest in sorted(IDE_MANIFESTS.items()):
        # Skip IDEs whose base directory doesn't exist
        ide_root = Path(ide_name)
        if not ide_root.exists():
            continue

        print(f"  {ide_name}/")
        ide_changes = 0

        for canonical_key, target_path in sorted(manifest.items()):
            # Handle __extra_ keys (canonical key contains __extra_ suffix)
            canonical_rel = canonical_key.split("__extra_")[0]
            src = CANONICAL / canonical_rel
            dst = Path(target_path)

            if verify:
                # Verify mode: just check for drift
                src_hash = file_hash(src)
                dst_hash = file_hash(dst)
                if src_hash and dst_hash and src_hash != dst_hash:
                    print(f"    DRIFT: {dst}")
                    stats["drift"] += 1
                    ide_changes += 1
                elif src_hash and not dst_hash:
                    print(f"    MISSING: {dst}")
                    stats["drift"] += 1
                    ide_changes += 1
            else:
                action, detail = sync_file(src, dst, dry_run=dry_run)
                stats[action] += 1
                if action in ("updated", "created"):
                    print(f"    {action.upper()}: {dst}")
                    ide_changes += 1

        if ide_changes == 0:
            print("    (up to date)")

    # Summary
    print(f"\n{'-' * 50}")
    if verify:
        total_drift = stats["drift"]
        if total_drift > 0:
            print(f"DRIFT DETECTED: {total_drift} file(s) out of sync.")
            print("Run 'python scripts/sync-ide-folders.py' to fix.")
            sys.exit(1)
        else:
            print("All IDE folders are in sync.")
            sys.exit(0)
    else:
        print(f"  Updated:  {stats['updated']}")
        print(f"  Created:  {stats['created']}")
        print(f"  Skipped:  {stats['skipped']} (already up to date)")
        if stats["missing_src"] > 0:
            print(f"  Missing:  {stats['missing_src']} (canonical source not found)")
        if dry_run:
            print("\n  This was a dry run. No files were modified.")
            print("  Run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
