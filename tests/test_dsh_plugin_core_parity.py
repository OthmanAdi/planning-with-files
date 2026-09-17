"""The DSH plugin's core is the OpenCode core, byte for byte, and the package
is wired the way dsh expects.

The OpenCode plugin's src/core.ts is the reviewed implementation of plan
resolution, framing, attestation, the gate and init. The DSH plugin ships a
byte-identical copy so a fix lands in both hosts at once and neither copy
can drift into a host-specific fork. The remaining assertions lock the dsh
bundle contract (package.json dsh.bundle.patch, the patch row naming the
package), keep the built dist/ out of git, and keep the command namespace
clean: dsh owns /plan (its plan mode) and the plugin never registers it.
"""
from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DSH_PACKAGE = REPO_ROOT / ".dsh" / "packages" / "dsh-planning-with-files"
OPENCODE_PACKAGE = REPO_ROOT / ".opencode" / "packages" / "opencode-planning-with-files"
DSH_CORE = DSH_PACKAGE / "src" / "core.ts"
OPENCODE_CORE = OPENCODE_PACKAGE / "src" / "core.ts"
PLUGIN_SOURCE = DSH_PACKAGE / "src" / "index.ts"
MANIFEST = DSH_PACKAGE / "package.json"
PATCH = DSH_PACKAGE / "cordis.patch.yml"
DIST_REL = ".dsh/packages/dsh-planning-with-files/dist"


def _run_git(args):
    """stdout of a git command at the repo root, or None when git is
    unavailable, this is not a git checkout, or the command fails."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


class DshPluginCoreParityTests(unittest.TestCase):
    def test_core_is_byte_identical_to_the_opencode_core(self) -> None:
        self.assertTrue(OPENCODE_CORE.is_file(), f"missing OpenCode core: {OPENCODE_CORE}")
        self.assertTrue(DSH_CORE.is_file(), f"missing DSH core: {DSH_CORE}")
        self.assertEqual(
            OPENCODE_CORE.read_bytes(),
            DSH_CORE.read_bytes(),
            "the DSH core drifted from the OpenCode core; copy "
            ".opencode/packages/opencode-planning-with-files/src/core.ts over "
            ".dsh/packages/dsh-planning-with-files/src/core.ts instead of editing it",
        )

    def test_patch_inserts_the_package_by_name(self) -> None:
        text = PATCH.read_text(encoding="utf-8")
        self.assertIn("- insert:", text)
        self.assertIsNotNone(
            re.search(r"^\s*-\s*id:\s*planning-with-files\s*$", text, re.M),
            "cordis.patch.yml lost the planning-with-files row id",
        )
        self.assertIsNotNone(
            re.search(r"^\s*name:\s*dsh-planning-with-files\s*$", text, re.M),
            "cordis.patch.yml must reference the package by its npm name so "
            "Node resolution finds the installed code",
        )

    def test_manifest_declares_the_dsh_bundle_patch(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual("dsh-planning-with-files", manifest.get("name"))
        self.assertEqual(
            "./cordis.patch.yml",
            manifest.get("dsh", {}).get("bundle", {}).get("patch"),
            "without dsh.bundle.patch dsh plugin add installs a plain dependency and activates no layer",
        )
        files = manifest.get("files", [])
        self.assertIn("cordis.patch.yml", files)
        self.assertIn("dist", files)
        self.assertEqual("dist/index.js", manifest.get("main"))

    def test_built_dist_is_not_tracked(self) -> None:
        tracked = _run_git(["ls-files", "--", DIST_REL])
        if tracked is None:
            self.skipTest("git unavailable or not a git checkout")
        self.assertEqual(
            "",
            tracked.strip(),
            "dist/ is a build output; the npm publish ships it, git must not: " + tracked,
        )
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "--", f"{DIST_REL}/index.js"],
            cwd=REPO_ROOT,
            capture_output=True,
        )
        self.assertEqual(0, ignored.returncode, ".gitignore no longer covers .dsh/packages/*/dist/")

    def test_plugin_never_registers_the_dsh_plan_command(self) -> None:
        source = PLUGIN_SOURCE.read_text(encoding="utf-8")
        for taken in ("plan", "plan-status"):
            self.assertIsNone(
                re.search(r"""name:\s*['"]%s['"]""" % re.escape(taken), source),
                f"the plugin must not register /{taken}: dsh owns /plan and the namespace stays pwf-only",
            )
        for shipped in ("pwf", "pwf-status"):
            self.assertIsNotNone(
                re.search(r"""name:\s*['"]%s['"]""" % re.escape(shipped), source),
                f"the plugin lost the documented /{shipped} command",
            )


if __name__ == "__main__":
    unittest.main()
