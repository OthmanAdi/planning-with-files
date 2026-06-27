"""Tests for the v3 run-ledger scripts (architecture C3 / C4).

Covers three scripts under skills/planning-with-files/scripts/:
  * ledger-append.sh  — append one structured JSON line per entry, monotonic
    tick across agents, event allowlist, summary truncated at 200 chars.
  * ledger-summary.sh — fixed-shape, cache-stable summary with NO timestamps;
    byte-identical across two consecutive runs (KV-cache stability).
  * phase-status.sh   — the only sanctioned task_plan.md status writer; rewrites
    ONLY the target phase Status line, exits nonzero on a missing phase.

These scripts resolve siblings (resolve-plan-dir.sh) via their own dir, so we
invoke them from skills/planning-with-files/scripts/.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "skills" / "planning-with-files" / "scripts"
LEDGER_APPEND = SCRIPTS_DIR / "ledger-append.sh"
LEDGER_SUMMARY = SCRIPTS_DIR / "ledger-summary.sh"
PHASE_STATUS = SCRIPTS_DIR / "phase-status.sh"


def have_sh() -> bool:
    return shutil.which("sh") is not None


@unittest.skipUnless(have_sh(), "sh not available on this platform")
class LedgerTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="pwf-ledger-"))
        self.plan_dir = self.tmp / ".planning" / "p"
        self.plan_dir.mkdir(parents=True)
        (self.tmp / ".planning" / ".active_plan").write_text("p\n", encoding="utf-8")
        (self.plan_dir / "task_plan.md").write_text(
            "# Task Plan\n"
            "### Phase 1: Build\n"
            "- **Status:** in_progress\n"
            "### Phase 2: Test\n"
            "- **Status:** pending\n",
            encoding="utf-8",
        )
        self.env = os.environ.copy()
        self.env.pop("PLAN_ID", None)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def append(self, *args: str):
        return subprocess.run(
            ["sh", str(LEDGER_APPEND), *args],
            cwd=str(self.tmp),
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=self.env,
            check=False,
        )

    def summary(self):
        return subprocess.run(
            ["sh", str(LEDGER_SUMMARY)],
            cwd=str(self.tmp),
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=self.env,
            check=False,
        )

    def phase_status(self, *args: str):
        return subprocess.run(
            ["sh", str(PHASE_STATUS), *args],
            cwd=str(self.tmp),
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=self.env,
            check=False,
        )


class LedgerAppendTests(LedgerTestBase):
    def test_appends_valid_json_lines(self) -> None:
        self.append("progress", "did a thing", "--agent", "main")
        self.append("phase_complete", "phase 1 done", "--agent", "main", "--phase", "1")
        lf = self.plan_dir / "ledger-main.jsonl"
        self.assertTrue(lf.exists())
        lines = lf.read_text(encoding="utf-8").splitlines()
        self.assertEqual(2, len(lines))
        for line in lines:
            obj = json.loads(line)  # raises if not valid JSON
            for key in ("tick", "ts", "agent", "phase", "event", "summary", "files"):
                self.assertIn(key, obj)
            self.assertIsInstance(obj["files"], list)

    def test_tick_monotonic_across_two_agents(self) -> None:
        self.append("progress", "from main", "--agent", "main")
        self.append("progress", "from worker", "--agent", "worker")
        self.append("progress", "main again", "--agent", "main")
        main_lines = (self.plan_dir / "ledger-main.jsonl").read_text(encoding="utf-8").splitlines()
        worker_lines = (self.plan_dir / "ledger-worker.jsonl").read_text(encoding="utf-8").splitlines()
        ticks = sorted(
            json.loads(line)["tick"] for line in (*main_lines, *worker_lines)
        )
        # Three appends share one monotonic counter: 1, 2, 3 with no collision.
        self.assertEqual([1, 2, 3], ticks)

    def test_event_allowlist_rejects_bad_event(self) -> None:
        result = self.append("not_an_event", "x", "--agent", "main")
        self.assertNotEqual(0, result.returncode)
        self.assertFalse((self.plan_dir / "ledger-main.jsonl").exists())

    def test_event_allowlist_accepts_every_valid_event(self) -> None:
        for event in ("progress", "phase_complete", "error", "gate_block", "attest", "note"):
            result = self.append(event, f"summary for {event}", "--agent", "main")
            self.assertEqual(0, result.returncode, result.stderr)

    def test_summary_truncated_at_200(self) -> None:
        long_summary = "a" * 300
        self.append("progress", long_summary, "--agent", "main")
        line = (self.plan_dir / "ledger-main.jsonl").read_text(encoding="utf-8").strip()
        obj = json.loads(line)
        self.assertEqual(200, len(obj["summary"]))


class LedgerSummaryTests(LedgerTestBase):
    def test_summary_contains_no_timestamps(self) -> None:
        self.append("progress", "step one with a date 2026-06-09T18:40:00Z", "--agent", "main")
        result = self.summary()
        self.assertEqual(0, result.returncode, result.stderr)
        # No ISO8601 timestamp (the date the append recorded) may reach context.
        import re

        self.assertIsNone(
            re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", result.stdout),
            f"timestamp leaked into summary:\n{result.stdout}",
        )

    def test_summary_byte_identical_across_two_runs(self) -> None:
        self.append("progress", "one", "--agent", "main")
        self.append("phase_complete", "two", "--agent", "worker", "--phase", "1")
        first = self.summary()
        second = self.summary()
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(
            first.stdout,
            second.stdout,
            "ledger summary must be byte-stable for KV-cache hygiene",
        )

    def test_summary_reports_counts_and_in_progress_phase(self) -> None:
        self.append("progress", "x", "--agent", "main")
        result = self.summary()
        self.assertIn("phases: 0/2 complete", result.stdout)
        self.assertIn("Phase 1: Build", result.stdout)
        self.assertIn("agent main:", result.stdout)


class PhaseStatusTests(LedgerTestBase):
    def test_rewrites_only_target_status_line(self) -> None:
        before = (self.plan_dir / "task_plan.md").read_text(encoding="utf-8")
        result = self.phase_status("2", "complete")
        self.assertEqual(0, result.returncode, result.stderr)
        after = (self.plan_dir / "task_plan.md").read_text(encoding="utf-8")

        before_lines = before.splitlines()
        after_lines = after.splitlines()
        self.assertEqual(len(before_lines), len(after_lines))
        changed = [
            (b, a) for b, a in zip(before_lines, after_lines) if b != a
        ]
        # Exactly one line changed: Phase 2's status pending -> complete.
        self.assertEqual(1, len(changed), f"expected 1 changed line, got {changed}")
        self.assertEqual("- **Status:** pending", changed[0][0])
        self.assertEqual("- **Status:** complete", changed[0][1])

    def test_first_phase_status_untouched_when_setting_second(self) -> None:
        self.phase_status("2", "complete")
        after = (self.plan_dir / "task_plan.md").read_text(encoding="utf-8")
        # Phase 1 must still read in_progress.
        self.assertIn("### Phase 1: Build\n- **Status:** in_progress", after)

    def test_invalid_phase_exits_nonzero(self) -> None:
        result = self.phase_status("99", "complete")
        self.assertNotEqual(0, result.returncode)
        # Plan file untouched.
        self.assertNotIn("complete", (self.plan_dir / "task_plan.md").read_text(encoding="utf-8"))

    def test_invalid_status_exits_nonzero(self) -> None:
        result = self.phase_status("1", "not_a_status")
        self.assertNotEqual(0, result.returncode)


if __name__ == "__main__":
    unittest.main()
