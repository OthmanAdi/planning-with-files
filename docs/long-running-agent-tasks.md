# Long-running agent tasks: keeping a coding agent on track for hours

A coding agent that runs for hours fails in two characteristic ways: it drifts off the original goal, or it loops without ever deciding it is done. Both are state problems. planning-with-files addresses them with plan files on disk, mechanical re-injection, and, since v3, two opt-in modes built for unattended runs. Overview: [README](../README.md).

## Why agents drift on long runs

After 50+ tool calls the original goals get crowded out of the attention window, errors that were never written down get repeated, and everything crammed into context instead of files eventually falls out of it. The baseline countermeasure is the 3-file pattern: `task_plan.md`, `findings.md`, and `progress.md` on disk, with hooks re-injecting the plan at the start of every turn. The goals stay in the attention window because a mechanism puts them there, not because the model remembers to look.

The same files make context death survivable mid-run. If the session dies at hour three, a fresh session resumes from disk; see [the /clear recovery page](agent-forgets-plan-after-clear.md) and [the compaction page](claude-code-lost-context-after-compaction.md).

## Autonomous mode

Started with `/pwf --autonomous` or `sh scripts/init-session.sh --autonomous "Task name"`. It keeps the turn-start plan injection and omits PreToolUse plan context. Legacy Claude Code mode instead refreshes the tool view when it changes, with repeated injection as a fallback when session identity or private cache storage is unavailable. See [performance notes](perf-notes.md) for that policy and its opt-out. Autonomous mode also turns attestation on by default and replaces the raw `progress.md` tail with a structured ledger summary.

Without a mode marker, hooks retain the legacy content format. Claude Code may suppress repeated unchanged PreToolUse views as described above. Both v3 modes remain opt-in.

## Gated mode and the completion gate

Started with `--gated`. It adds a Stop gate on top of autonomous behavior: the gate judges the plan artifact on disk, not the conversation transcript, so a session cannot talk itself into being finished. The gate blocks a stop ONLY when all of these hold at once:

1. The `.mode` file says `gate`.
2. An `in_progress` phase exists.
3. `stop_hook_active` is false (already inside a forced continuation means allow).
4. The block count is below the cap (default 20, `PWF_GATE_CAP` to override).
5. The ledger progressed since the previous block.

Any single failure allows the stop. An incomplete plan alone never traps a session.

## Runaway guards

An unattended loop needs bounded behavior independent of host quirks:

- a persistent block counter in `.planning/<id>/.stop_blocks`, reset at init-session
- a cap (default 20) on consecutive blocks; at the cap the gate allows the stop
- stall detection: no new ledger line since the previous block means the model is not progressing, so the gate allows the stop

The counter and the stall detector are deterministic; `stop_hook_active` and host block caps are backstops. Enforcement is host-aware: hard block on Claude Code, Codex, and Continue; follow-up injection on Cursor, Pi, and Kiro; notify-only elsewhere.

## The run ledger

In v3 modes the machine record of the run is an append-only JSONL file, `.planning/<id>/ledger-<agent>.jsonl`, one JSON object per line. What reaches the model each turn is a fixed-shape summary from `ledger-summary.sh`: tick count, phases complete/total, the in-progress phase heading, and the last event type per agent. No free text from disk enters context and the block carries no timestamps, so it is KV-cache stable by construction. The gate's stall detector reads the ledger, a semantic signal, rather than file mtimes.

## Attestation for unattended loops

An unattended loop amplifies any single prompt injection on every tick, so v3 modes attest the plan at init: `attest-plan.sh` locks `task_plan.md` with a SHA-256, hooks re-hash on every fire, and a tampered plan body is refused at injection. Autonomous and gated mode go further and refuse to inject an unattested plan at all. Editing the plan mid-run requires an explicit re-attest. Details: the Security Boundary section of the skill and [docs/attestation-locking.md](attestation-locking.md).

## What it costs, measured

Steady state, the hooks re-inject about 330 tokens per user turn plus about 90 per matched tool call (autonomous mode drops the per-tool-call part). In the formal eval the full workflow averaged roughly 68% more tokens and 17% more time than an unstructured run (19,926 tokens vs 11,899). The return: in the project's internal recovery benchmark (v1, author-run, deterministic grading), a session resumed after a hard context wipe in 5.0 turns on average against 13.3 for a raw agent, with every graded run in every arm finishing pytest-green, so the difference is re-orientation cost, not correctness. Full method and disclosed limits: [docs/evals.md](evals.md).

If a task finishes in under 5 tool calls, skip the skill; the structure only pays off on work long enough to lose.

## Related pages

- [Claude Code lost context after compaction: how to recover and prevent it](claude-code-lost-context-after-compaction.md)
- [My coding agent forgets the plan after /clear: the file-based fix](agent-forgets-plan-after-clear.md)

## Install

Claude Code, plugin route (ships the skill, hooks, and slash commands):

```
/plugin marketplace add OthmanAdi/planning-with-files
/plugin install planning-with-files@planning-with-files
```

Every other agent, one line via the Agent Skills standard:

```bash
npx skills add OthmanAdi/planning-with-files --skill planning-with-files -g
```

Full route matrix and verification: [README](../README.md) and [docs/installation.md](installation.md).
