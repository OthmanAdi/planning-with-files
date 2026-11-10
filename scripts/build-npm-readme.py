#!/usr/bin/env python3
"""Build the npm package README from the repository README.

npm cannot resolve repository-relative links, so the bundled
`.pi/skills/planning-with-files/README.md` is the root `README.md` with every
relative link pinned to the release named in that package's `package.json`:

    src="media/x.svg"  -> https://raw.githubusercontent.com/OthmanAdi/planning-with-files/vX.Y.Z/media/x.svg
    ![alt](media/x.png) -> https://raw.githubusercontent.com/OthmanAdi/planning-with-files/vX.Y.Z/media/x.png
    href="docs/a.md"   -> https://github.com/OthmanAdi/planning-with-files/blob/vX.Y.Z/docs/a.md
    [a](docs/a.md)     -> https://github.com/OthmanAdi/planning-with-files/blob/vX.Y.Z/docs/a.md
    [docs/](docs/)     -> https://github.com/OthmanAdi/planning-with-files/tree/vX.Y.Z/docs/

Absolute URLs, in-page anchors and fenced code blocks are copied unchanged, so
historical release links, benchmark citations and third-party URLs keep their
targets. The output depends only on README.md and the package version, and
running the script twice changes nothing.

Run after `bump-version.py` and before `npm pack` or `npm publish`:
    python scripts/build-npm-readme.py
    python scripts/build-npm-readme.py --check   # read-only; exits 1 and lists what is stale
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "README.md"
PACKAGE_DIR = REPO_ROOT / ".pi" / "skills" / "planning-with-files"
TARGET = PACKAGE_DIR / "README.md"
PACKAGE_JSON = PACKAGE_DIR / "package.json"

REPO_SLUG = "OthmanAdi/planning-with-files"
BLOB = f"https://github.com/{REPO_SLUG}/blob/"
TREE = f"https://github.com/{REPO_SLUG}/tree/"
RAW = f"https://raw.githubusercontent.com/{REPO_SLUG}/"

LINK_RE = re.compile(
    r'(?P<lead>!\[[^\]\n]*\]\(|\]\(|\b(?:src|href)=")(?P<url>[^)"\s]+)'
)
NOT_RELATIVE_RE = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.-]*:|//|/|#)")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
PINNED_RE = re.compile(
    "(?:%s|%s|%s)(?P<tag>[^/\\s]+)/(?P<path>[^)\"\\s#]*)"
    % (re.escape(BLOB), re.escape(TREE), re.escape(RAW))
)


def package_version(package_json: Path = PACKAGE_JSON) -> str:
    return json.loads(package_json.read_text(encoding="utf-8"))["version"]


def _pin(lead: str, url: str, tag: str) -> str:
    if NOT_RELATIVE_RE.match(url):
        return url
    if lead.startswith("!") or lead == 'src="':
        return f"{RAW}{tag}/{url}"
    if url.split("#", 1)[0].endswith("/"):
        return f"{TREE}{tag}/{url}"
    return f"{BLOB}{tag}/{url}"


def render(source: str, version: str) -> str:
    """Return the npm README for `source` pinned to release `version`."""
    tag = f"v{version}"
    out: list[str] = []
    fence: str | None = None
    for line in source.splitlines(keepends=True):
        match = FENCE_RE.match(line)
        if fence is None:
            if match:
                fence = match.group(1)
            else:
                line = LINK_RE.sub(
                    lambda m: m.group("lead") + _pin(m.group("lead"), m.group("url"), tag),
                    line,
                )
        elif match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence):
            fence = None
        out.append(line)
    return "".join(out)


def stale_report(current: str, expected: str, version: str) -> list[str]:
    """Describe how `current` differs from `expected`; empty when it is current."""
    if current == expected:
        return []
    tag = f"v{version}"
    problems: list[str] = []
    stale = sorted(
        {
            f"{m.group('path') or '/'} ({m.group('tag')})"
            for m in PINNED_RE.finditer(current)
            if m.group("tag") != tag
        }
    )
    if stale:
        shown = ", ".join(stale[:10]) + (f", and {len(stale) - 10} more" if len(stale) > 10 else "")
        problems.append(f"{len(stale)} links not pinned to {tag}: {shown}")

    def unpinned(text: str) -> list[str]:
        return PINNED_RE.sub(r"<pinned>/\g<path>", text).splitlines()

    changed = [
        line
        for line in difflib.unified_diff(unpinned(expected), unpinned(current), lineterm="", n=0)
        if line.startswith("@@")
    ]
    if changed:
        first = changed[0].split()[1].lstrip("-").split(",")[0]
        problems.append(
            f"{len(changed)} sections differ from README.md beyond link pins (first at README.md line {first})"
        )
    if not problems:
        problems.append("contents differ from the generated README")
    return problems


def _read(path: Path) -> str:
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="report a stale README without writing")
    args = parser.parse_args(argv)

    version = package_version(PACKAGE_JSON)
    expected = render(_read(SOURCE), version)
    current = _read(TARGET) if TARGET.exists() else ""
    rel = TARGET.relative_to(REPO_ROOT).as_posix()

    if args.check:
        problems = stale_report(current, expected, version)
        if not problems:
            print(f"{rel} is current for package version {version}")
            return 0
        print(f"{rel} is stale for package version {version}:")
        for problem in problems:
            print(f"  {problem}")
        print("Run: python scripts/build-npm-readme.py")
        return 1

    if current == expected:
        print(f"{rel} already current for package version {version}")
        return 0
    with TARGET.open("w", encoding="utf-8", newline="") as handle:
        handle.write(expected)
    print(f"wrote {rel} for package version {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
