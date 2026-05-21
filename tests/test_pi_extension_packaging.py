"""Tests for Pi full-adaptation package wiring.

TDD RED phase: these tests define the minimum package-level contract:
- The Pi package must ship both skill and extension resources.
- The extension entrypoint must exist inside the package.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_JSON = REPO_ROOT / ".pi" / "skills" / "planning-with-files" / "package.json"
EXT_INDEX = (
    REPO_ROOT
    / ".pi"
    / "skills"
    / "planning-with-files"
    / "extensions"
    / "planning-with-files"
    / "index.ts"
)


class PiExtensionPackagingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pkg = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))

    def test_manifest_declares_pi_extension_entry(self) -> None:
        pi_block = self.pkg.get("pi", {})
        self.assertIn("extensions", pi_block)
        self.assertIn(
            "extensions/planning-with-files/index.ts",
            pi_block.get("extensions", []),
        )

    def test_manifest_files_include_extensions_dir(self) -> None:
        files = self.pkg.get("files", [])
        self.assertIn("extensions/", files)

    def test_extension_entrypoint_exists(self) -> None:
        self.assertTrue(EXT_INDEX.exists(), f"missing extension entrypoint: {EXT_INDEX}")


if __name__ == "__main__":
    unittest.main()
