# Migration Guide: v1.x to v2.0.0

## Overview

Version 2.0.0 adds hooks integration and enhanced templates while maintaining backward compatibility with existing workflows.

## What's New

### 1. Hooks (Automatic Behaviors)

v2.0.0 adds Claude Code hooks that automate key Manus principles:

| Hook | Trigger | Behavior |
|------|---------|----------|
| `PreToolUse` | Before Write/Edit/Bash | Reads `task_plan.md` to refresh goals |
| `Stop` | Before stopping | Verifies all phases are complete |

**Benefit:** You no longer need to manually remember to re-read your plan. The hook does it automatically.

### 2. Templates Directory

New templates provide structured starting points:

```
templates/
├── task_plan.md    # Phase tracking with status fields
├── findings.md     # Research storage with 2-action reminder
└── progress.md     # Session log with 5-question reboot test
```

### 3. Scripts Directory

Helper scripts for common operations:

```
scripts/
├── init-session.sh     # Creates all 3 planning files
└── check-complete.sh   # Verifies task completion
```

## Migration Steps

### Step 1: Update the Plugin

```bash
# If installed via marketplace
/plugin update planning-with-files

# If installed manually
cd .claude/plugins/planning-with-files
git pull origin master
```

### Step 2: Existing Files Continue Working

Your existing `task_plan.md` files will continue to work. The hooks look for this file and gracefully handle its absence.

### Step 3: Adopt New Templates (Optional)

To use the new structured templates, you can either:

1. **Start fresh** with `./scripts/init-session.sh`
2. **Copy templates** from `templates/` directory
3. **Keep your existing format** - it still works

### Step 4: Update Phase Status Format (Recommended)

v2.0.0 templates use a more structured status format:

**v1.x format:**
```markdown
- [x] Phase 1: Setup ✓
- [ ] Phase 2: Implementation (CURRENT)
```

**v2.0.0 format:**
```markdown
### Phase 1: Setup
- **Status:** complete

### Phase 2: Implementation
- **Status:** in_progress
```

The new format enables the `check-complete.sh` script to automatically verify completion.

## Breaking Changes

**None.** v2.0.0 is fully backward compatible.

If you prefer the v1.x behavior without hooks, use the `legacy` branch:

```bash
git checkout legacy
```

## New Features to Adopt

### The 2-Action Rule

After every 2 view/browser/search operations, save findings to files:

```
WebSearch → WebSearch → MUST Write findings.md
```

### The 3-Strike Error Protocol

Structured error recovery:

1. Diagnose & Fix
2. Alternative Approach
3. Broader Rethink
4. Escalate to User

### The 5-Question Reboot Test

Your planning files should answer:

1. Where am I? → Current phase
2. Where am I going? → Remaining phases
3. What's the goal? → Goal statement
4. What have I learned? → findings.md
5. What have I done? → progress.md

---

# Migration Guide: v2.x to v3.0.0

## Overview

Version 3.0.0 adds opt-in modes for long-running and multi-agent runs: autonomous mode (less
recitation), gated mode (a deliberate completion gate), a structured run-ledger, and phase
coordination fields. None of this changes how v2 behaves. With no new flags and no `.mode`
marker, v3 runs exactly like v2.43.0.

Current recovery behavior is stricter than the original v3.0.0 path. Automatic hooks and bare
`session-catchup.py` recover from project planning files without inspecting host session stores.
Reading same-project local session records and emitting aggregate counts requires explicit
`--metadata`; bounded nonce-framed excerpts require explicit `--replay`. The catchup path has no
network upload operation.

## What changes by default

Nothing. The default path is byte-for-byte v2.43 behavior. The hooks stay advisory, the Stop
hook never blocks, and your existing `task_plan.md`, `findings.md`, and `progress.md` keep
working without edits. Every v3 behavior is keyed off an explicit opt-in, so an unmodified
install behaves identically to v2.43.0.

## What's new (opt-in)

### Autonomous mode

For strong models on long runs. Recitation drops to once per turn (session start) instead of
before every tool call, which removes the per-tool-call token tax. The plan on disk stays the
source of truth; the model re-reads it when it needs detail. There is no completion gate in
this mode. Recitation is reduced, not removed: published evidence still shows goal drift on
long runs, so autonomous mode is opt-in, never the default.

### Gated mode

Adds a deliberate completion gate. When a phase is left `in_progress` and the run was tasked
with executing the plan, the Stop hook can hold the turn and feed back a fixed reminder naming
the pending phase. This is the opposite of the accidental gate from issue #178: it fires only
in gated mode, never for any incomplete plan, and the reminder text is a fixed template plus
the phase name, never raw plan content. Guards keep it safe: a block cap (default 20, counted
in `.planning/<id>/.stop_blocks`, reset at init and restarted when a phase completes), a stall
detector (no change in the plan's phase statuses or `progress.md` since the last block means the
run is allowed to stop), and the host's own `stop_hook_active` and block-cap backstops.

### Run-ledger

A structured, append-only progress record. Workers append one JSON line per tick to a per-agent
ledger; the orchestrator keeps `progress.md` as the human-readable tick log. The injected
context is a synthesized fixed-shape summary, not a raw tail of `progress.md`, which keeps it
stable for the host's prompt cache and removes a raw-text injection surface.

### Phase coordination fields

`task_plan_autonomous.md` originally documented optional per-phase `DependsOn`, `Owner`, and
`AcceptanceCheck` fields. These fields are coordination notes for people and agents; the runtime
gate does not parse them, enforce dependencies, route work, or execute commands from Markdown.
Only the existing `**Status:**` markers participate in phase completion checks.

### Attestation default-on in the new modes

In autonomous and gated modes, `task_plan.md` is hashed at init and the hooks refuse to inject
plan content that diverges from the attested hash. Re-run `scripts/attest-plan.sh` after any
intentional edit. In multi-agent runs the orchestrator re-attests at phase boundaries, since a
worker editing the plan would break the hash by design. Attestation controls plan injection; it
does not authorize or execute commands written in the plan.

### SHA cache location moved

The hook's mtime-SHA cache moved from `${TMPDIR:-/tmp}/pwf-sha` (v2) to `$HOME/.cache/pwf-sha`
(or `$XDG_CACHE_HOME/pwf-sha` when set). This removes the shared-tmp poisoning surface. The
move is silent: a warm v2 cache under `/tmp/pwf-sha` is never read by v3, so the first session
after upgrade rehashes every attested plan once. That is the correct behavior (no stale reads),
and the cache repopulates immediately. On a large collection of attested plans on slow Windows
Git Bash, that first rehash can show as a one-time per-turn latency bump; subsequent sessions are
back to cache speed. No action is needed, and the old `/tmp/pwf-sha` directory can be deleted.

## Quickstart: try gated mode in two commands

```bash
# 1. Start a gated session (writes the .mode marker, attests the plan, resets the block counter)
./scripts/init-session.sh --gated "my-feature"

# 2. Plan as usual
# Fill in task_plan.md (or start from templates/task_plan_autonomous.md), set phase statuses,
# and work. The gate holds the turn while a phase is in_progress, up to the block cap.
```

For autonomous mode, swap `--gated` for `--autonomous`. To return to plain v2 behavior, start a
session with no flag (no `.mode` file is written).

## Host capability tiers

The completion gate is host-aware: not every host can hard-block a stop. The tiers below
summarize what each host enforces. In every tier the plan file on disk is still the shared,
durable state; only the gate's enforcement strength differs.

| Tier | Mechanism | Hosts |
|------|-----------|-------|
| Hard block | `decision:block` / exit 2 holds the turn | Claude Code, Codex CLI, OpenAI Codex API, Continue.dev |
| Follow-up inject | continuation via an injected follow-up message plus the host's own counter | Cursor, Pi, Kiro, Hermes Agent, OpenCode (native plugin) |
| Notify only | a system message is shown, no enforcement | Gemini CLI and the remaining adapters |

On hard-block hosts, gated mode enforces the gate. On follow-up hosts, the gate becomes a
follow-up message capped by a counter (Pi's AUTO_CONTINUE_LIMIT is the reference). On
notify-only hosts, gated mode degrades to a non-blocking notice; autonomous mode still works
because it needs no gate.

### OpenCode: honest note

OpenCode has no Stop-hook re-activation (upstream issue #12472 is still open), so nothing can
refuse to end a turn there. Since v3.14.0 the native plugin `opencode-planning-with-files` uses
what OpenCode does offer: it listens for `session.idle` and, while a gated plan still has an
`in_progress` phase, sends the gate reason back as a new user message through the SDK. That is
the follow-up-inject tier, bounded by the shared block counter (`PWF_GATE_CAP`) and the ledger
stall rule, and never applied to child sessions. Without the plugin (skill-only installs) OpenCode
stays notify-only: the skill's `hooks:` frontmatter is a Claude Code convention OpenCode ignores.
Autonomous mode and the run ledger work either way because they do not depend on blocking the stop.

## Breaking changes

**None.** v3.0.0 is fully backward compatible. Default behavior with no mode marker is exactly
v2.43 semantics.

## Questions?

Open an issue: https://github.com/OthmanAdi/planning-with-files/issues
