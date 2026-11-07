"""Guard: every SKILL.md frontmatter must be valid, loadable YAML.

Regression test for the v3.1.2 -> v3.1.3 break: an unquoted description that
contained ': ' (colon followed by space) turned the frontmatter into an invalid
YAML mapping ("mapping values are not allowed here"), which breaks skill loading
and the model-triggering description field. The version-parity check is a regex
and did not catch it, so this validates the frontmatter as actual YAML.

Discovery includes hidden adapter directories, which glob.glob skips.

clawhub-upload/SKILL.md is gitignored publish staging: absent on a fresh clone is
fine, but when present it must still be validated (tracked inventory + walk).
"""
import contextlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


_EXCLUDED_PARTS = {".git", "node_modules", "__pycache__", ".planning"}


@contextlib.contextmanager
def ignored_scratch_dir():
    """Unique directory under the gitignored .planning/; removes only what it made."""
    planning = REPO_ROOT / ".planning"
    created_planning = not planning.exists()
    planning.mkdir(exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="_pwf352_", dir=planning))
    try:
        yield scratch
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        if created_planning:
            try:
                planning.rmdir()
            except OSError:
                pass


def _skill_md_files(root=None):
    """Discover SKILL.md files for validation.

    Prefer the tracked inventory when ``root`` is the repository (so an ignored
    scratch tree under ``.planning/`` cannot fail shipped validation, #352).
    Fall back to a filtered walk for source archives without Git metadata, and
    always walk when ``root`` is a fixture tree (hidden-adapter discovery).
    """
    if root is None:
        root = REPO_ROOT
    else:
        root = Path(root).resolve()
    out = []
    if root.resolve() == REPO_ROOT.resolve():
        try:
            proc = subprocess.run(
                ["git", "-c", "core.quotepath=off", "ls-files", "-z", "--", "*SKILL.md"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                check=False,
            )
        except OSError:
            proc = None
        if proc is not None and proc.returncode == 0 and proc.stdout:
            for rel in proc.stdout.decode("utf-8").split(chr(0)):
                if not rel:
                    continue
                path = REPO_ROOT / rel
                if path.is_file() and path.name == "SKILL.md":
                    out.append(path)
            # Optional gitignored publish staging: validate when present.
            clawhub = REPO_ROOT / "clawhub-upload" / "SKILL.md"
            if clawhub.is_file() and clawhub not in out:
                out.append(clawhub)
            if out:
                return sorted(out)
    for p in root.rglob("SKILL.md"):
        try:
            relative_parts = p.relative_to(root).parts
        except ValueError:
            relative_parts = p.parts
        if _EXCLUDED_PARTS.intersection(relative_parts):
            continue
        out.append(p)
    return sorted(out)


def _frontmatter(text):
    if not text.startswith("---"):
        return None
    segments = text.split("---", 2)
    if len(segments) < 3:
        return None
    return segments[1]


def _description_line(frontmatter):
    for line in frontmatter.splitlines():
        if line.startswith("description:"):
            return line
    return None


class SkillFrontmatterTests(unittest.TestCase):
    def test_discovers_all_tracked_skills(self):
        # Git supplies an independent inventory, including future adapters.
        # Source archives still run the filesystem and fixture validations.
        try:
            top = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
        except OSError:
            self.skipTest("Git is unavailable; source-archive checks still run")
        if top.returncode != 0 or Path(top.stdout.strip()).resolve() != REPO_ROOT.resolve():
            self.skipTest("No Git metadata for this source tree")
        tracked = subprocess.check_output(
            ["git", "ls-files", "-z", "*SKILL.md"],
            cwd=REPO_ROOT,
        )
        expected = {REPO_ROOT / p for p in tracked.decode("utf-8").split("\0") if p}
        self.assertTrue(expected, "Git returned no tracked SKILL.md files")
        missing = expected - set(_skill_md_files())
        self.assertFalse(missing, f"tracked SKILL.md files not discovered: {sorted(missing)}")

    def test_files_found(self):
        files = _skill_md_files()
        self.assertTrue(files, "no SKILL.md files discovered")
        adapter_dirs = {".agents", ".codex", ".cursor", ".hermes", ".pi"}
        found_dirs = {
            part
            for f in files
            for part in f.relative_to(REPO_ROOT).parts
            if part.startswith(".")
        }
        self.assertTrue(
            adapter_dirs.issubset(found_dirs),
            f"missing adapter directories in discovery: {adapter_dirs - found_dirs}",
        )

    def test_every_skill_has_frontmatter_and_description(self):
        for f in _skill_md_files():
            fm = _frontmatter(f.read_text(encoding="utf-8"))
            self.assertIsNotNone(fm, f"{f} has no '---' frontmatter block")
            self.assertIsNotNone(
                _description_line(fm), f"{f} frontmatter has no description:"
            )

    def test_ignored_scratch_skill_does_not_join_shipped_inventory(self):
        with ignored_scratch_dir() as scratch:
            bad = scratch / "SKILL.md"
            bad.write_text("name: scratch\n", encoding="utf-8")
            discovered = {p.resolve() for p in _skill_md_files()}
            self.assertNotIn(bad.resolve(), discovered)
            for f in discovered:
                fm = _frontmatter(f.read_text(encoding="utf-8"))
                self.assertIsNotNone(fm, f"{f} has no '---' frontmatter block")

    def test_unquoted_description_has_no_colon_space(self):
        # Dependency-free guard for the exact v3.1.2 break.
        for f in _skill_md_files():
            fm = _frontmatter(f.read_text(encoding="utf-8"))
            if fm is None:
                continue
            line = _description_line(fm)
            if line is None:
                continue
            value = line[len("description:"):].strip()
            if value[:1] in ('"', "'"):
                continue  # quoted scalars may safely contain colons
            self.assertNotIn(
                ": ",
                value,
                f"{f}: unquoted description contains ': ', which YAML parses as a "
                f"mapping and breaks frontmatter loading. Quote the value.",
            )

    def test_frontmatter_parses_as_yaml(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        for f in _skill_md_files():
            fm = _frontmatter(f.read_text(encoding="utf-8"))
            if fm is None:
                continue
            try:
                data = yaml.safe_load(fm)
            except Exception as exc:  # noqa: BLE001
                self.fail(f"{f}: frontmatter is not valid YAML: {exc}")
            self.assertIsInstance(data, dict, f"{f}: frontmatter is not a mapping")
            self.assertIsInstance(
                data.get("description"),
                str,
                f"{f}: description missing or not a string after YAML parse",
            )
            self.assertTrue(
                data["description"].strip(), f"{f}: description is empty"
            )

    def test_temporary_fixture_hidden_skill_discovery_and_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir).resolve()

            # Hidden valid skill
            hidden_valid = tmp_root / ".agents" / "skills" / "planning-with-files" / "SKILL.md"
            hidden_valid.parent.mkdir(parents=True)
            hidden_valid.write_text(
                "---\nname: valid-hidden-skill\ndescription: \"Valid hidden description\"\n---\n# Body\n",
                encoding="utf-8",
            )

            # Hidden malformed skill (unquoted colon-space description)
            hidden_malformed_unquoted = (
                tmp_root / ".cursor" / "skills" / "planning-with-files" / "SKILL.md"
            )
            hidden_malformed_unquoted.parent.mkdir(parents=True)
            hidden_malformed_unquoted.write_text(
                "---\nname: malformed-hidden-skill\ndescription: unquoted: colon space\n---\n# Body\n",
                encoding="utf-8",
            )

            # Hidden malformed skill (invalid YAML syntax)
            hidden_malformed_yaml = (
                tmp_root / ".codex" / "skills" / "planning-with-files" / "SKILL.md"
            )
            hidden_malformed_yaml.parent.mkdir(parents=True)
            hidden_malformed_yaml.write_text(
                "---\nname: [unclosed\ndescription: bad syntax\n---\n# Body\n",
                encoding="utf-8",
            )

            # Excluded directories (.git and node_modules)
            git_file = tmp_root / ".git" / "skills" / "SKILL.md"
            git_file.parent.mkdir(parents=True)
            git_file.write_text("---\nname: git\ndescription: git\n---\n", encoding="utf-8")

            node_file = tmp_root / "node_modules" / "skills" / "SKILL.md"
            node_file.parent.mkdir(parents=True)
            node_file.write_text("---\nname: node\ndescription: node\n---\n", encoding="utf-8")

            # Discovery should find hidden files and exclude .git / node_modules
            discovered = _skill_md_files(root=tmp_root)
            self.assertIn(hidden_valid, discovered)
            self.assertIn(hidden_malformed_unquoted, discovered)
            self.assertIn(hidden_malformed_yaml, discovered)
            self.assertNotIn(git_file, discovered)
            self.assertNotIn(node_file, discovered)

            # Valid hidden skill passes frontmatter extraction
            valid_fm = _frontmatter(hidden_valid.read_text(encoding="utf-8"))
            self.assertIsNotNone(valid_fm)
            valid_desc = _description_line(valid_fm)
            self.assertIsNotNone(valid_desc)

            # Malformed unquoted skill is caught by colon-space rule
            unquoted_fm = _frontmatter(hidden_malformed_unquoted.read_text(encoding="utf-8"))
            unquoted_desc = _description_line(unquoted_fm)
            val = unquoted_desc[len("description:"):].strip()
            self.assertIn(": ", val)

            # If PyYAML is available, verify validation behavior
            try:
                import yaml
            except ImportError:
                return

            # Valid passes YAML parse
            data = yaml.safe_load(valid_fm)
            self.assertIsInstance(data, dict)
            self.assertEqual(data.get("name"), "valid-hidden-skill")

            # Malformed YAML fails YAML parse
            bad_yaml_fm = _frontmatter(hidden_malformed_yaml.read_text(encoding="utf-8"))
            with self.assertRaises(yaml.YAMLError):
                yaml.safe_load(bad_yaml_fm)

    def test_no_git_fallback_keeps_hidden_adapters_excludes_scratch_keeps_clawhub(self):
        """Source-archive walk: hidden adapters + optional clawhub; skip .planning scratch."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            hidden = root / ".agents" / "skills" / "planning-with-files" / "SKILL.md"
            hidden.parent.mkdir(parents=True)
            hidden.write_text(
                "---\nname: hidden\ndescription: \"ok\"\n---\n",
                encoding="utf-8",
            )
            scratch = root / ".planning" / "_scratch" / "SKILL.md"
            scratch.parent.mkdir(parents=True)
            scratch.write_text("name: scratch\n", encoding="utf-8")
            clawhub = root / "clawhub-upload" / "SKILL.md"
            clawhub.parent.mkdir(parents=True)
            clawhub.write_text(
                "---\nname: claw\ndescription: \"staging\"\n---\n",
                encoding="utf-8",
            )
            git_noise = root / ".git" / "skills" / "SKILL.md"
            git_noise.parent.mkdir(parents=True)
            git_noise.write_text("---\nname: g\ndescription: g\n---\n", encoding="utf-8")

            discovered = _skill_md_files(root=root)
            self.assertIn(hidden, discovered)
            self.assertIn(clawhub, discovered)
            self.assertNotIn(scratch, discovered)
            self.assertNotIn(git_noise, discovered)

    def test_repo_root_failed_git_listing_falls_back_to_the_walk(self):
        """A source archive has git but no repository: rc 128 must not empty the list."""
        from unittest import mock

        not_a_repo = subprocess.CompletedProcess([], 128, stdout=b"", stderr=b"not a repository")
        with mock.patch("subprocess.run", return_value=not_a_repo):
            discovered = {p.resolve() for p in _skill_md_files()}
        found_dirs = {
            part
            for f in discovered
            for part in f.relative_to(REPO_ROOT).parts
            if part.startswith(".")
        }
        self.assertLessEqual({".agents", ".codex", ".cursor", ".hermes", ".pi"}, found_dirs)

    def test_repo_root_no_git_fallback_retains_adapters_and_excludes_scratch(self):
        """When Git metadata is unavailable, REPO_ROOT discovery falls back to the walk."""
        from unittest import mock

        with ignored_scratch_dir() as scratch:
            bad = scratch / "SKILL.md"
            bad.write_text("name: scratch\n", encoding="utf-8")
            with mock.patch("subprocess.run", side_effect=OSError("no git")):
                discovered = {p.resolve() for p in _skill_md_files()}
            self.assertNotIn(bad.resolve(), discovered)
            adapter_dirs = {".agents", ".codex", ".cursor", ".hermes", ".pi"}
            found_dirs = {
                part
                for f in discovered
                for part in f.relative_to(REPO_ROOT).parts
                if part.startswith(".")
            }
            self.assertTrue(
                adapter_dirs.issubset(found_dirs),
                f"missing adapters in no-Git fallback: {adapter_dirs - found_dirs}",
            )
            clawhub = REPO_ROOT / "clawhub-upload" / "SKILL.md"
            if clawhub.is_file():
                self.assertIn(clawhub.resolve(), discovered)


if __name__ == "__main__":
    unittest.main()
