"""End-to-end BSD/macOS-userland simulation for the POSIX sh scripts.

The sh entry points (resolve-plan-dir.sh, inject-plan.sh, attest-plan.sh,
ledger-append.sh, ledger-summary.sh) must run on macOS, where the userland
is BSD: no realpath(1), no readlink -f on older systems, no flock(1), no
sha256sum(1) (only shasum), and a stat(1) that rejects the GNU -c flag and
takes -f '%m' instead. A GNU-only flag sneaking into those scripts fails
silently there (the portability helpers swallow stderr and fall through),
so code review alone does not catch the regression.

This harness builds a bin dir containing ONLY a BSD-shaped toolset and runs
each script with PATH pointing at that dir alone:

  absent   realpath, readlink, flock, sha256sum
  present  shasum (host binary, or a wrapper over sha256sum that emulates
           the 'shasum -a 256' call form and output shape), stat rejecting
           -c and serving -f '%m' (translated to GNU stat -c '%Y' first,
           native BSD stat -f '%m' second, python mtime last), date passed
           through, and the POSIX text and filesystem tools the scripts use. Canonicalization
           receives an exact interpreter through PWF_TRUSTED_PYTHON instead
           of exposing Python on PATH.

Absence is real absence, not a failing shadow: PATH is replaced, not
prepended, so `command -v flock` and friends take the no-tool branch exactly
as on macOS. Any GNU-only regression in those scripts fails here on the
ubuntu CI leg instead of surfacing as a macOS-only bug report. Modeled on
the PATH-stub realpath harness in tests/test_containment.py (v3.6.0).

Windows is excluded: replacing PATH wholesale breaks the MSYS runtime
(sh.exe cannot locate its DLLs), and a macOS simulation under Git Bash
proves nothing. The macos-latest CI leg covers the real thing.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "skills" / "planning-with-files" / "scripts"
RESOLVE_SH = SCRIPTS_DIR / "resolve-plan-dir.sh"
INJECT_SH = SCRIPTS_DIR / "inject-plan.sh"
ATTEST_SH = SCRIPTS_DIR / "attest-plan.sh"
LEDGER_APPEND_SH = SCRIPTS_DIR / "ledger-append.sh"
LEDGER_SUMMARY_SH = SCRIPTS_DIR / "ledger-summary.sh"

SLUG = "2026-07-21-bsd-sim"

# Tools the scripts invoke that keep their host behavior. Exposed in the stub
# bin dir as exec wrappers onto the host binaries so the stub dir can be the
# ONLY PATH entry.
PASSTHROUGH_TOOLS = (
    "sh",
    "dirname",
    "basename",
    "tr",
    "sed",
    "awk",
    "grep",
    "head",
    "tail",
    "cut",
    "cat",
    "chmod",
    "mkdir",
    "mktemp",
    "ln",
    "mv",
    "rm",
    "rmdir",
    "sleep",
    "wc",
    "date",
)

BSD_STAT_TEMPLATE = """#!/bin/sh
# BSD stat shape: the GNU -c flag fails the way it does on macOS, and the
# BSD form -f '%%m' answers with the epoch mtime. Served by GNU stat -c '%%Y'
# first (ubuntu leg), native stat -f '%%m' second (macos leg), python last.
case "${1:-}" in
  -c*|--format*|--printf*)
    echo "stat: illegal option -- c" >&2
    exit 1
    ;;
  -f)
    [ "${2:-}" = "%%m" ] || { echo "stat: stub supports only -f %%m" >&2; exit 1; }
    shift 2
    out="$("%(real_stat)s" -c '%%Y' "$@" 2>/dev/null)" && [ -n "$out" ] && { printf '%%s\\n' "$out"; exit 0; }
    out="$("%(real_stat)s" -f '%%m' "$@" 2>/dev/null)" && [ -n "$out" ] && { printf '%%s\\n' "$out"; exit 0; }
    exec "%(python3)s" -c 'import os,sys;[print(int(os.stat(p).st_mtime)) for p in sys.argv[1:]]' "$@"
    ;;
  *)
    echo "stat: unsupported stub invocation: $*" >&2
    exit 1
    ;;
esac
"""

SHASUM_TEMPLATE = """#!/bin/sh
# shasum stand-in backed by sha256sum for hosts without shasum. Accepts the
# 'shasum -a 256' call form the scripts use; with no file arguments it reads
# stdin. Output shape 'HASH  NAME' matches shasum's.
if [ "${1:-}" = "-a" ]; then
  [ "${2:-}" = "256" ] || { echo "shasum: stub supports only -a 256" >&2; exit 1; }
  shift 2
fi
exec "%(real_sha256sum)s" "$@"
"""

PLAN_BODY = """# Task: BSD userland sim fixture

## Goal
Prove the sh pipeline runs on a BSD-only toolset.

## Phases

### Phase 1: setup
**Status:** complete

### Phase 2: verify
**Status:** in_progress
"""

PROGRESS_BODY = """# Progress

## 2026-07-21
- created fixture at 2026-07-21T08:00:00Z
"""


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def write_stub(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    write_text(path, body)
    os.chmod(path, 0o755)


def write_passthrough(bin_dir: Path, name: str, real: str) -> None:
    write_stub(bin_dir, name, '#!/bin/sh\nexec "%s" "$@"\n' % real)


def build_bsd_stub_bin(bin_dir: Path) -> None:
    """Populate bin_dir with the BSD-shaped toolset described in the module
    docstring. Raises SkipTest when the host lacks a required real binary."""
    tools = {name: shutil.which(name) for name in PASSTHROUGH_TOOLS}
    missing = sorted(name for name, real in tools.items() if not real)
    if missing:
        raise unittest.SkipTest("host lacks POSIX tools: %s" % ", ".join(missing))
    for name, real in tools.items():
        write_passthrough(bin_dir, name, real)

    real_stat = shutil.which("stat")
    if not real_stat:
        raise unittest.SkipTest("host lacks stat")
    write_stub(
        bin_dir,
        "stat",
        BSD_STAT_TEMPLATE % {"real_stat": real_stat, "python3": sys.executable},
    )

    real_shasum = shutil.which("shasum")
    if real_shasum:
        write_passthrough(bin_dir, "shasum", real_shasum)
    else:
        real_sha256sum = shutil.which("sha256sum")
        if not real_sha256sum:
            raise unittest.SkipTest("host lacks both shasum and sha256sum")
        write_stub(bin_dir, "shasum", SHASUM_TEMPLATE % {"real_sha256sum": real_sha256sum})

@unittest.skipIf(
    sys.platform == "win32",
    "BSD userland simulation replaces PATH wholesale; MSYS sh cannot run "
    "without its own directories on PATH",
)
class BsdUserlandSimTests(unittest.TestCase):
    def setUp(self) -> None:
        self.real_sh = shutil.which("sh")
        if not self.real_sh:
            self.skipTest("sh not available on this platform")
        tmp = Path(tempfile.mkdtemp(prefix="pwf-bsd-sim-"))
        self.addCleanup(shutil.rmtree, tmp, True)

        self.bin_dir = tmp / "bin"
        self.bin_dir.mkdir()
        build_bsd_stub_bin(self.bin_dir)

        home = tmp / "home"
        home.mkdir()

        self.project = tmp / "project"
        self.plan_dir = self.project / ".planning" / SLUG
        self.plan_dir.mkdir(parents=True)
        write_text(self.plan_dir / "task_plan.md", PLAN_BODY)
        write_text(self.plan_dir / "progress.md", PROGRESS_BODY)
        write_text(self.project / ".planning" / ".active_plan", SLUG + "\n")

        env = os.environ.copy()
        env["PATH"] = str(self.bin_dir)
        # Isolate the SHA cache (inject-plan.sh writes under XDG_CACHE_HOME
        # or HOME) and strip vars that change script behavior.
        env["HOME"] = str(home)
        env["XDG_CACHE_HOME"] = str(home / ".cache")
        env["PWF_TRUSTED_PYTHON"] = str(Path(sys.executable).resolve())
        for var in ("PLAN_ID", "PLANNING_DISABLED"):
            env.pop(var, None)
        env.pop("PYTHON_BIN", None)
        self.env = env

    def run_script(self, script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.real_sh, str(script), *args],
            cwd=str(self.project),
            env=self.env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )

    def run_sh(self, command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.real_sh, "-c", command],
            cwd=str(self.project),
            env=self.env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )

    def test_simulated_userland_shape(self) -> None:
        # Self-check of the harness: if a runner image change or a stub bug
        # lets a GNU tool leak in, coverage would silently weaken. Fail loud.
        for absent in ("realpath", "readlink", "flock", "sha256sum", "python3", "python"):
            result = self.run_sh("command -v %s" % absent)
            self.assertNotEqual(
                0,
                result.returncode,
                "%s must be absent from the stub PATH, found %r"
                % (absent, result.stdout.strip()),
            )
        for present in ("shasum", "stat", "date", "sh"):
            result = self.run_sh("command -v %s" % present)
            self.assertEqual(
                0, result.returncode, "%s must be present in the stub PATH" % present
            )

        result = self.run_sh("stat -c '%Y' .")
        self.assertNotEqual(0, result.returncode, "BSD stat must reject the GNU -c flag")

        result = self.run_sh("stat -f '%m' .")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertRegex(result.stdout.strip(), r"^\d+$")

        result = self.run_sh("date +%s")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertRegex(result.stdout.strip(), r"^\d+$")

        # shasum must produce the real digest in the 'HASH  NAME' shape, in
        # both file and stdin modes (inject-plan.sh uses the stdin form for
        # its cache key).
        probe = self.plan_dir / "task_plan.md"
        expected = hashlib.sha256(probe.read_bytes()).hexdigest()
        result = self.run_sh('shasum -a 256 "%s"' % probe)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(expected, result.stdout.split()[0])
        result = self.run_sh('shasum -a 256 < "%s"' % probe)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(expected, result.stdout.split()[0])

    def test_full_flow_resolve_inject_attest_ledger(self) -> None:
        # 1) Resolver: .active_plan slug fixture must resolve. canonicalize()
        # has only the exact PWF_TRUSTED_PYTHON fallback available; an empty
        # stdout here is the signature of a GNU-only-flag regression
        # (fail-closed containment).
        result = self.run_script(RESOLVE_SH)
        self.assertEqual(0, result.returncode, result.stderr)
        resolved = result.stdout.strip()
        self.assertTrue(
            resolved.endswith(SLUG),
            "resolver must find the slug dir under BSD userland, got %r (stderr=%r)"
            % (result.stdout, result.stderr),
        )

        # 2) Injection, unattested: bounded plan and progress data frames,
        # no attestation line, no tamper branch.
        result = self.run_script(INJECT_SH)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("===BEGIN-PWF-DATA kind=plan nonce=", result.stdout)
        self.assertIn("===END-PWF-DATA kind=plan nonce=", result.stdout)
        self.assertIn("# Task: BSD userland sim fixture", result.stdout)
        self.assertIn("===BEGIN-PWF-DATA kind=progress nonce=", result.stdout)
        self.assertIn("created fixture", result.stdout)
        self.assertNotIn("TAMPERED", result.stdout)
        self.assertNotIn("Plan-SHA256", result.stdout)

        # 3) Attestation: hashing must run through shasum (sha256sum is
        # absent), the write path through the no-flock branch. The stored
        # hash must be the true SHA-256 of the plan file.
        result = self.run_script(ATTEST_SH)
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        self.assertIn("[plan-attest] Locked", result.stdout)
        attestation_file = self.plan_dir / ".attestation"
        self.assertTrue(attestation_file.is_file(), "attestation file missing")
        stored = attestation_file.read_text(encoding="utf-8").strip()
        expected = hashlib.sha256(
            (self.plan_dir / "task_plan.md").read_bytes()
        ).hexdigest()
        self.assertEqual(expected, stored)

        # 4) Injection after attestation: Plan-SHA256 line with the exact
        # hash, still no tamper branch (mtime comes from the BSD stat form).
        result = self.run_script(INJECT_SH)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Plan-SHA256: %s" % expected, result.stdout)
        self.assertIn("===BEGIN-PWF-DATA kind=plan nonce=", result.stdout)
        self.assertNotIn("TAMPERED", result.stdout)

        # 5) Ledger appends: tick counter must increment without flock, the
        # JSONL lines must parse, date passthrough must yield an ISO8601Z ts.
        result = self.run_script(
            LEDGER_APPEND_SH, "phase_complete", "phase one done",
            "--agent", "main", "--phase", "1",
        )
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        self.assertIn("[ledger] tick 1 ->", result.stdout)
        result = self.run_script(
            LEDGER_APPEND_SH, "progress", "phase two started",
            "--agent", "main", "--phase", "2", "--files", "a.md,b.md",
        )
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        self.assertIn("[ledger] tick 2 ->", result.stdout)

        ledger_file = self.plan_dir / "ledger-main.jsonl"
        self.assertTrue(ledger_file.is_file(), "ledger file missing")
        entries = [
            json.loads(line)
            for line in ledger_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual([1, 2], [entry["tick"] for entry in entries])
        self.assertEqual("phase_complete", entries[0]["event"])
        self.assertEqual("progress", entries[1]["event"])
        self.assertEqual(["a.md", "b.md"], entries[1]["files"])
        for entry in entries:
            self.assertRegex(
                entry["ts"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
            )

        # 6) Ledger summary: full valid block synthesized from the plan file
        # and the ledger written above.
        result = self.run_script(LEDGER_SUMMARY_SH)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("=== RUN LEDGER ===", result.stdout)
        self.assertIn("entries: 2", result.stdout)
        self.assertIn("phases: 1/2 complete", result.stdout)
        self.assertIn("in_progress: ### Phase 2: verify", result.stdout)
        self.assertIn("agent main: progress", result.stdout)
        self.assertIn("==================", result.stdout)

    def test_unpinned_discovery_refuses_ambiguity_and_uses_bsd_stat(self) -> None:
        # A newer mtime cannot bind a session to one of two live plans.
        (self.project / ".planning" / ".active_plan").unlink()
        older = self.project / ".planning" / "2026-07-19-older-plan"
        older.mkdir()
        write_text(older / "task_plan.md", "# older plan\n")
        os.utime(older, (1_700_000_000, 1_700_000_000))
        os.utime(self.plan_dir, (1_700_000_100, 1_700_000_100))

        result = self.run_script(RESOLVE_SH)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stdout.strip())

        # With just one live plan, discovery still consumes stat: 'stat -c'
        # must fail and 'stat -f %m' must answer. Keep the planless directory
        # to verify that it is ignored without weakening the BSD fallback.
        (older / "task_plan.md").unlink()
        result = self.run_script(RESOLVE_SH)
        self.assertEqual(0, result.returncode, result.stderr)
        resolved = result.stdout.strip()
        self.assertTrue(
            resolved.endswith(SLUG),
            "single-plan scan must find %s via the BSD stat form, got %r (stderr=%r)"
            % (SLUG, result.stdout, result.stderr),
        )


if __name__ == "__main__":
    unittest.main()
