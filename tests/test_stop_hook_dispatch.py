"""Stop-hook dispatch tests (v3.8.0).

The Stop scalar in SKILL.md frontmatter is the dispatcher for the completion
advisory (legacy) and the v3 completion gate. Before v3.8.0 it had two silent
failure modes that these tests pin forever:

  1. Dead fallback: ``TARGET_PS1="${SKILL_PS1:-$KNOWN_PS1}"`` never substituted
     because ``SKILL_PS1="${CLAUDE_SKILL_DIR}/scripts/check-complete.ps1"`` is a
     non-empty string even when ``CLAUDE_SKILL_DIR`` is unset. With the env var
     unset the whole hook was a silent no-op even with the skill installed at a
     known path.
  2. ps1-first on every platform: ``check-complete.ps1`` ships in the skill dir
     on all platforms, so the PowerShell branch was always chosen and
     ``powershell.exe ... 2>/dev/null`` silently did nothing on macOS/Linux
     (exit 127, stderr discarded). The POSIX ``gate-stop.sh`` branch was
     unreachable: the completion gate never fired on macOS or Linux.

The v3.8.0 scalar selects by file existence (``[ -f ] || ls-fallback``, the
same pattern the other hooks use) and dispatches by platform: PowerShell only
on native Windows (uname MINGW*/MSYS*/CYGWIN*), ``sh`` elsewhere.

These tests EXECUTE the scalar end-to-end, which the pre-v3.8.0 suite never
did (it only string-matched the scalar shape).
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SKILL = REPO_ROOT / "skills" / "planning-with-files" / "SKILL.md"
SKILL_DIR = REPO_ROOT / "skills" / "planning-with-files"

# Every SKILL.md that carries a Stop scalar (canonical + language variants +
# IDE mirrors). Kept in sync with the parity surfaces.
ALL_STOP_SKILL_FILES = [
    REPO_ROOT / "skills" / "planning-with-files" / "SKILL.md",
    REPO_ROOT / "skills" / "i18n" / "planning-with-files-ar" / "SKILL.md",
    REPO_ROOT / "skills" / "i18n" / "planning-with-files-de" / "SKILL.md",
    REPO_ROOT / "skills" / "i18n" / "planning-with-files-es" / "SKILL.md",
    REPO_ROOT / "skills" / "i18n" / "planning-with-files-zh" / "SKILL.md",
    REPO_ROOT / "skills" / "i18n" / "planning-with-files-zht" / "SKILL.md",
    REPO_ROOT / ".agents" / "skills" / "planning-with-files" / "SKILL.md",
    REPO_ROOT / ".codebuddy" / "skills" / "planning-with-files" / "SKILL.md",
    REPO_ROOT / ".codex" / "skills" / "planning-with-files" / "SKILL.md",
    REPO_ROOT / ".cursor" / "skills" / "planning-with-files" / "SKILL.md",
    REPO_ROOT / ".factory" / "skills" / "planning-with-files" / "SKILL.md",
    REPO_ROOT / ".mastracode" / "skills" / "planning-with-files" / "SKILL.md",
    REPO_ROOT / ".opencode" / "skills" / "planning-with-files" / "SKILL.md",
]
# clawhub-upload/SKILL.md is gitignored and may be absent on a fresh clone
# (same convention as test_skill_frontmatter_valid.py); cover it only when
# present so CI and local runs agree.
_CLAWHUB_SKILL = REPO_ROOT / "clawhub-upload" / "SKILL.md"
if _CLAWHUB_SKILL.is_file():
    ALL_STOP_SKILL_FILES.append(_CLAWHUB_SKILL)

HOOK_RE = r'Stop:\n(?:.*?\n)*?\s*command: "((?:[^"\\]|\\.)*)"'

IS_WINDOWS = sys.platform == "win32"


def extract_stop_scalar(skill_file: Path) -> str:
    text = skill_file.read_text(encoding="utf-8")
    match = re.search(HOOK_RE, text)
    assert match, f"Stop hook scalar not found in {skill_file}"
    raw = match.group(1)
    return raw.replace('\\"', '"').replace("\\\\", "\\")


def have_sh() -> bool:
    return shutil.which("sh") is not None


def run_scalar(
    scalar: str,
    cwd: Path,
    env_overrides: dict,
    stdin_data: str = "",
    drop_vars: tuple = (),
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    for var in drop_vars:
        env.pop(var, None)
    env.update(env_overrides)
    return subprocess.run(
        ["sh", "-c", scalar],
        cwd=str(cwd),
        env=env,
        input=stdin_data,
        capture_output=True,
        text=True,
        timeout=60,
    )


def make_plan(tmp: Path) -> None:
    (tmp / "task_plan.md").write_text(
        "# Task Plan: dispatch test\n\n"
        "### Phase 1: Verify\n"
        "- [ ] run the hook\n"
        "- **Status:** in_progress\n",
        encoding="utf-8",
    )


@unittest.skipUnless(have_sh(), "requires a POSIX sh")
class StopScalarShapeTests(unittest.TestCase):
    """Static shape of every Stop scalar in the fleet."""

    def test_no_dead_colon_dash_fallback(self) -> None:
        # "${SKILL_PS1:-$KNOWN_PS1}" can never substitute: SKILL_PS1 is a
        # non-empty string even with CLAUDE_SKILL_DIR unset. The v3.8.0 form
        # selects by file existence instead.
        for skill_file in ALL_STOP_SKILL_FILES:
            scalar = extract_stop_scalar(skill_file)
            self.assertNotIn(
                ":-$KNOWN",
                scalar,
                f"{skill_file}: dead ':-' fallback pattern present; "
                "existence-based selection required",
            )

    def test_platform_gated_dispatch(self) -> None:
        # PowerShell must be chosen only on native Windows shells; POSIX gets
        # the sh path first.
        for skill_file in ALL_STOP_SKILL_FILES:
            scalar = extract_stop_scalar(skill_file)
            self.assertIn("uname", scalar, f"{skill_file}: no platform gate")
            self.assertIn("MINGW", scalar, f"{skill_file}: no MINGW match")

    def test_probes_both_install_paths(self) -> None:
        for skill_file in ALL_STOP_SKILL_FILES:
            scalar = extract_stop_scalar(skill_file)
            self.assertIn(".claude/skills/planning-with-files", scalar)
            self.assertIn(".claude/plugins/marketplaces/planning-with-files", scalar)

    def test_no_yaml_delimiter_collision(self) -> None:
        # A literal --- inside a hook scalar corrupts frontmatter parsing
        # (Discussion #153 class).
        for skill_file in ALL_STOP_SKILL_FILES:
            scalar = extract_stop_scalar(skill_file)
            self.assertNotIn("---", scalar, f"{skill_file}: '---' in scalar")

    def test_exits_zero_explicitly(self) -> None:
        for skill_file in ALL_STOP_SKILL_FILES:
            scalar = extract_stop_scalar(skill_file)
            self.assertTrue(
                scalar.rstrip().endswith("exit 0"),
                f"{skill_file}: scalar must end with exit 0",
            )


@unittest.skipUnless(have_sh(), "requires a POSIX sh")
class StopScalarBehaviorTests(unittest.TestCase):
    """Execute the canonical scalar end-to-end."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="pwf-stop-"))
        make_plan(self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_advisory_fires_with_skill_dir_set(self) -> None:
        # The day-one regression: on macOS/Linux this produced NO output
        # because the ps1 branch swallowed the dispatch.
        scalar = extract_stop_scalar(CANONICAL_SKILL)
        result = run_scalar(
            scalar, self.tmp, {"CLAUDE_SKILL_DIR": str(SKILL_DIR)}
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(
            "[planning-with-files]",
            result.stdout,
            "Stop hook produced no advisory output with an in_progress plan "
            f"(stderr: {result.stderr!r})",
        )

    def test_fires_when_skill_dir_unset(self) -> None:
        # The dead-fallback regression: with CLAUDE_SKILL_DIR unset the
        # ls-discovered install path must be used.
        fake_home = self.tmp / "home"
        stub_scripts = fake_home / ".claude" / "skills" / "planning-with-files" / "scripts"
        stub_scripts.mkdir(parents=True)
        for name in (
            "gate-stop.sh",
            "check-complete.sh",
            "check-complete.ps1",
            "resolve-plan-dir.sh",
        ):
            src = SKILL_DIR / "scripts" / name
            dst = stub_scripts / name
            shutil.copy2(src, dst)
            dst.chmod(dst.stat().st_mode | stat.S_IEXEC)

        scalar = extract_stop_scalar(CANONICAL_SKILL)
        env = {"HOME": str(fake_home)}
        if IS_WINDOWS:
            # Git Bash maps $HOME from HOME when set; USERPROFILE is the
            # Windows-native twin some layers consult.
            env["USERPROFILE"] = str(fake_home)
        result = run_scalar(
            scalar,
            self.tmp,
            env,
            drop_vars=("CLAUDE_SKILL_DIR",),
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(
            "[planning-with-files]",
            result.stdout,
            "Stop hook silent with CLAUDE_SKILL_DIR unset despite a stub "
            f"install under $HOME (stderr: {result.stderr!r})",
        )

    @unittest.skipIf(IS_WINDOWS, "POSIX-only dispatch preference")
    def test_posix_prefers_sh_over_powershell(self) -> None:
        # Even with a powershell.exe on PATH (e.g. PowerShell Core on Linux),
        # the POSIX branch must dispatch the sh gate, not the ps1.
        bindir = self.tmp / "bin"
        bindir.mkdir()
        sentinel = self.tmp / "ps1-ran"
        fake_ps = bindir / "powershell.exe"
        fake_ps.write_text(f"#!/bin/sh\ntouch '{sentinel}'\n", encoding="utf-8")
        fake_ps.chmod(0o755)

        scalar = extract_stop_scalar(CANONICAL_SKILL)
        env = {
            "CLAUDE_SKILL_DIR": str(SKILL_DIR),
            "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
        }
        result = run_scalar(scalar, self.tmp, env)
        self.assertEqual(result.returncode, 0)
        self.assertIn("[planning-with-files]", result.stdout)
        self.assertFalse(
            sentinel.exists(),
            "POSIX dispatch ran powershell.exe instead of the sh gate",
        )

    @unittest.skipIf(IS_WINDOWS, "gate JSON path exercised via sh on POSIX")
    def test_gated_mode_emits_block_json(self) -> None:
        (self.tmp / ".mode").write_text("autonomous gate\n", encoding="utf-8")
        scalar = extract_stop_scalar(CANONICAL_SKILL)
        result = run_scalar(
            scalar,
            self.tmp,
            {"CLAUDE_SKILL_DIR": str(SKILL_DIR)},
            stdin_data='{"stop_hook_active": false}',
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(
            '"decision":"block"',
            result.stdout,
            f"gated mode did not block (stdout: {result.stdout!r})",
        )

    def test_variant_scalar_fires_end_to_end(self) -> None:
        # Group-B scalars (language variants + IDE mirrors) dispatch to
        # check-complete.sh; one representative execution proves the shape.
        # (.codebuddy ships its own scripts/; .cursor relies on the install-path
        # fallback and cannot be executed hermetically here.)
        variant = REPO_ROOT / ".codebuddy" / "skills" / "planning-with-files" / "SKILL.md"
        scalar = extract_stop_scalar(variant)
        variant_skill_dir = REPO_ROOT / ".codebuddy" / "skills" / "planning-with-files"
        result = run_scalar(
            scalar, self.tmp, {"CLAUDE_SKILL_DIR": str(variant_skill_dir)}
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(
            "[planning-with-files]",
            result.stdout,
            f"variant Stop scalar silent (stderr: {result.stderr!r})",
        )


if __name__ == "__main__":
    unittest.main()
