"""Gate decision-table tests for scripts/check-complete.sh --gate (v3 C2).

The completion gate is the v3 termination oracle. It blocks a Stop ONLY when
ALL of these hold (architecture "Gate decision table"):

  1. mode is gated (<plan-dir>/.mode contains "gate")
  2. an in_progress phase exists (not merely complete<total)
  3. stop_hook_active is false on the Stop hook stdin
  4. the block count is below the cap (default 20, PWF_GATE_CAP override)
  5. the ledger advanced since the previous block (a stall allows the stop)

Any single failure falls back to advisory output and exits 0. The block decision
is a single line of JSON on stdout: {"decision":"block","reason":"..."}. These
tests parse that JSON to confirm it is well formed, and assert that every
non-block branch emits NO decision JSON.

The v3 scripts live only under skills/planning-with-files/scripts/; check-complete
resolves its siblings (resolve-plan-dir.sh) via its own dir, so we invoke it from
there.
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
CHECK_COMPLETE = SCRIPTS_DIR / "check-complete.sh"


def have_sh() -> bool:
    return shutil.which("sh") is not None


@unittest.skipUnless(have_sh(), "sh not available on this platform")
class GateDecisionTableTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="pwf-gate-"))
        self.plan_dir = self.tmp / ".planning" / "p"
        self.plan_dir.mkdir(parents=True)
        (self.tmp / ".planning" / ".active_plan").write_text("p\n", encoding="utf-8")
        self.env = os.environ.copy()
        self.env.pop("PLAN_ID", None)
        self.env.pop("PWF_GATE_CAP", None)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- helpers ----------------------------------------------------------
    def write_plan(self, phase1_status: str = "in_progress", phase2_status: str = "pending") -> None:
        (self.plan_dir / "task_plan.md").write_text(
            "# Task Plan\n"
            "### Phase 1: Build\n"
            f"- **Status:** {phase1_status}\n"
            "### Phase 2: Test\n"
            f"- **Status:** {phase2_status}\n",
            encoding="utf-8",
        )

    def set_mode(self, mode: str | None) -> None:
        if mode is None:
            return
        (self.plan_dir / ".mode").write_text(mode + "\n", encoding="utf-8")

    def set_blocks(self, n: int) -> None:
        (self.plan_dir / ".stop_blocks").write_text(f"{n}\n", encoding="utf-8")

    def add_ledger_line(self, tick: int) -> None:
        lf = self.plan_dir / "ledger-main.jsonl"
        with lf.open("a", encoding="utf-8") as fh:
            fh.write(
                f'{{"tick":{tick},"ts":"1970-01-01T00:00:00Z","agent":"main",'
                f'"phase":"1","event":"progress","summary":"x","files":[]}}\n'
            )

    def run_gate(self, gate: bool, stop_hook_active: bool = False, cap: int | None = None):
        args = [str(CHECK_COMPLETE)]
        if gate:
            args.append("--gate")
        env = dict(self.env)
        if cap is not None:
            env["PWF_GATE_CAP"] = str(cap)
        return subprocess.run(
            ["sh", *args],
            cwd=str(self.tmp),
            text=True,
            encoding="utf-8",
            capture_output=True,
            input=json.dumps({"stop_hook_active": stop_hook_active}),
            env=env,
            check=False,
        )

    def parse_block(self, stdout: str) -> dict:
        """Find and parse the single decision-JSON line; fail if absent/invalid."""
        line = None
        for candidate in stdout.splitlines():
            if candidate.strip().startswith('{"decision"'):
                line = candidate.strip()
                break
        self.assertIsNotNone(line, f"no decision JSON line in output:\n{stdout}")
        obj = json.loads(line)  # raises if malformed → test fails
        return obj

    def assert_no_block(self, result) -> None:
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn('"decision":"block"', result.stdout)

    # -- decision table ---------------------------------------------------
    def test_advisory_without_gate_flag(self) -> None:
        # No --gate: always advisory, even with a gated mode + in_progress phase.
        self.write_plan(phase1_status="in_progress")
        self.set_mode("autonomous gate")
        self.set_blocks(0)
        result = self.run_gate(gate=False)
        self.assert_no_block(result)
        self.assertIn("Task in progress", result.stdout)

    def test_gate_without_mode_is_advisory(self) -> None:
        # --gate but no .mode file: legacy plans never gate.
        self.write_plan(phase1_status="in_progress")
        self.set_mode(None)
        self.set_blocks(0)
        result = self.run_gate(gate=True)
        self.assert_no_block(result)

    def test_gated_in_progress_blocks_with_valid_json(self) -> None:
        self.write_plan(phase1_status="in_progress")
        self.set_mode("autonomous gate")
        self.set_blocks(0)
        result = self.run_gate(gate=True, stop_hook_active=False)
        self.assertEqual(0, result.returncode, result.stderr)
        obj = self.parse_block(result.stdout)
        self.assertEqual("block", obj["decision"])
        self.assertIn("reason", obj)
        # Reason carries the phase NAME only, never raw plan body.
        self.assertIn("Phase 1: Build", obj["reason"])

    def test_gated_only_pending_does_not_block(self) -> None:
        # complete<total with no in_progress phase is a normal state (issue #178).
        self.write_plan(phase1_status="pending", phase2_status="pending")
        self.set_mode("autonomous gate")
        self.set_blocks(0)
        result = self.run_gate(gate=True)
        self.assert_no_block(result)

    def test_stop_hook_active_does_not_block(self) -> None:
        # Already inside a forced continuation: allow the stop, no recursion.
        self.write_plan(phase1_status="in_progress")
        self.set_mode("autonomous gate")
        self.set_blocks(0)
        result = self.run_gate(gate=True, stop_hook_active=True)
        self.assert_no_block(result)

    def test_cap_reached_stops_blocking(self) -> None:
        self.write_plan(phase1_status="in_progress")
        self.set_mode("autonomous gate")
        self.set_blocks(2)
        result = self.run_gate(gate=True, cap=2)
        self.assert_no_block(result)
        self.assertIn("gate cap reached", result.stdout)

    def test_stall_stops_blocking(self) -> None:
        # First block records the ledger count. A second block with NO new ledger
        # line means the model did not progress, so the gate allows the stop.
        self.write_plan(phase1_status="in_progress")
        self.set_mode("autonomous gate")
        self.set_blocks(0)
        self.add_ledger_line(1)

        first = self.run_gate(gate=True)
        self.parse_block(first.stdout)  # asserts it blocked the first time

        # No new ledger line between the two stops.
        second = self.run_gate(gate=True)
        self.assert_no_block(second)
        self.assertIn("no progress since last gate block", second.stdout)

    def test_progress_since_block_keeps_blocking(self) -> None:
        # Counterpart to the stall test: when the ledger DID advance between two
        # stops, the gate must keep blocking (not misfire the stall guard).
        self.write_plan(phase1_status="in_progress")
        self.set_mode("autonomous gate")
        self.set_blocks(0)
        self.add_ledger_line(1)

        first = self.run_gate(gate=True)
        self.parse_block(first.stdout)

        self.add_ledger_line(2)  # real progress
        second = self.run_gate(gate=True)
        obj = self.parse_block(second.stdout)
        self.assertEqual("block", obj["decision"])

    def test_stop_blocks_increments_on_block(self) -> None:
        self.write_plan(phase1_status="in_progress")
        self.set_mode("autonomous gate")
        self.set_blocks(0)
        self.add_ledger_line(1)

        self.run_gate(gate=True)
        after_first = int((self.plan_dir / ".stop_blocks").read_text().strip())
        self.assertEqual(1, after_first)

        self.add_ledger_line(2)  # keep blocking (advance ledger)
        self.run_gate(gate=True)
        after_second = int((self.plan_dir / ".stop_blocks").read_text().strip())
        self.assertEqual(2, after_second)

    # -- .mode token parse (platform-critical, counterpart to inject-plan.sh) --
    def test_autonomous_gate_token_activates_gate(self) -> None:
        # The gated marker is two space-separated tokens, 'autonomous gate'.
        # check-complete guard 1 must detect the 'gate' token inside it and arm
        # the gate. (inject-plan.sh parses the same marker; that side is pinned in
        # test_hook_body_v240.py ModeTokenParseTests. Both must agree on the token
        # grammar so a gated plan behaves consistently across the two scripts.)
        self.write_plan(phase1_status="in_progress")
        self.set_mode("autonomous gate")
        self.set_blocks(0)
        result = self.run_gate(gate=True, stop_hook_active=False)
        obj = self.parse_block(result.stdout)
        self.assertEqual("block", obj["decision"])

    def test_autonomous_only_token_does_not_gate(self) -> None:
        # 'autonomous' without 'gate' is not gated mode: guard 1 must keep it
        # advisory. This pins that the parse keys off the 'gate' token specifically.
        self.write_plan(phase1_status="in_progress")
        self.set_mode("autonomous")
        self.set_blocks(0)
        result = self.run_gate(gate=True, stop_hook_active=False)
        self.assert_no_block(result)


if __name__ == "__main__":
    unittest.main()
