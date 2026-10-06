# Workflow Diagram

This diagram shows how the three files work together and how hooks interact with them.

---

## Visual Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    TASK START                                    │
│  User requests a complex task (>5 tool calls expected)          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │  STEP 1: Create task_plan.md │
         │  (NEVER skip this step!)      │
         └───────────────┬───────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │  STEP 2: Create findings.md   │
         │  STEP 3: Create progress.md   │
         └───────────────┬───────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────┐
    │         WORK LOOP (Iterative)              │
    │                                            │
    │  ┌──────────────────────────────────────┐ │
    │  │  PreToolUse Hook (Automatic)         │ │
    │  │  → Reads task_plan.md before        │ │
    │  │    Write/Edit/Bash operations       │ │
    │  │  → Refreshes goals in attention      │ │
    │  └──────────────┬───────────────────────┘ │
    │                 │                          │
    │                 ▼                          │
    │  ┌──────────────────────────────────────┐ │
    │  │  Perform work (tool calls)          │ │
    │  │  - Research → Update findings.md    │ │
    │  │  - Implement → Update progress.md    │ │
    │  │  - Make decisions → Update both     │ │
    │  └──────────────┬───────────────────────┘ │
    │                 │                          │
    │                 ▼                          │
    │  ┌──────────────────────────────────────┐ │
    │  │  PostToolUse Hook (Automatic)        │ │
    │  │  → Reminds to update task_plan.md   │ │
    │  │    if phase completed               │ │
    │  └──────────────┬───────────────────────┘ │
    │                 │                          │
    │                 ▼                          │
    │  ┌──────────────────────────────────────┐ │
    │  │  After 2 view/browser operations:    │ │
    │  │  → MUST update findings.md           │ │
    │  │    (2-Action Rule)                   │ │
    │  └──────────────┬───────────────────────┘ │
    │                 │                          │
    │                 ▼                          │
    │  ┌──────────────────────────────────────┐ │
    │  │  After completing a phase:            │ │
    │  │  → Update task_plan.md status        │ │
    │  │  → Update progress.md with details   │ │
    │  └──────────────┬───────────────────────┘ │
    │                 │                          │
    │                 ▼                          │
    │  ┌──────────────────────────────────────┐ │
    │  │  If error occurs:                    │ │
    │  │  → Log in task_plan.md               │ │
    │  │  → Log in progress.md                │ │
    │  │  → Document resolution               │ │
    │  └──────────────┬───────────────────────┘ │
    │                 │                          │
    │                 └──────────┐               │
    │                            │               │
    │                            ▼               │
    │              ┌──────────────────────┐     │
    │              │  More work to do?    │     │
    │              └──────┬───────────────┘     │
    │                     │                     │
    │              YES ───┘                     │
    │              │                            │
    │              └──────────┐                 │
    │                         │                 │
    └─────────────────────────┘                 │
                                                 │
                         NO                      │
                         │                       │
                         ▼                       │
         ┌──────────────────────────────────────┐
         │  Stop Hook (Automatic)               │
         │  → Checks if all phases complete     │
         │  → Verifies task_plan.md status      │
         └──────────────┬───────────────────────┘
                         │
                         ▼
         ┌──────────────────────────────────────┐
         │  All phases complete?                │
         └──────────────┬───────────────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
            YES                    NO
              │                     │
              ▼                     ▼
    ┌─────────────────┐    ┌─────────────────┐
    │  TASK COMPLETE  │    │  Continue work  │
    │  Deliver files  │    │  (back to loop) │
    └─────────────────┘    └─────────────────┘
```

---

## After Completion: What Happens to the Plan Files

The planning files are working memory for one task, not a deliverable. `task_plan.md`, `findings.md`, `progress.md`, and any `.planning/<slug>/` directory are gitignored by default, and nothing archives them when a task finishes. In root mode the next task overwrites `task_plan.md`; in slug mode the old directory just stops being the active plan. There is no automatic "completed" or "archived" state, and `check-complete` reports completion without moving or extracting anything.

The behavior is consistent and intentional, though it was never stated as a rule until now (see [#14](https://github.com/OthmanAdi/planning-with-files/issues/14) and [#202](https://github.com/OthmanAdi/planning-with-files/issues/202)). The model is the Manus one the skill is built on: the context window is RAM and the filesystem is disk, so work survives `/clear` and a crash *during* a task. Anything meant to outlive the task belongs somewhere durable already, in code, in a commit, in a spec or doc, or in a `findings.md` you deliberately keep out of the gitignore.

If you want a completed plan to persist, keep it yourself:

- Copy the decisions and errors you care about into code comments, a commit message, an ADR, or a `docs/` note.
- Move the `.planning/<slug>/` directory outside the ignored path, or drop `.planning/` from `.gitignore` in a repo where you want plans tracked.
- For personal reuse, keep the directory as a cache for a future related task and pin it with `PLAN_ID` or `.active_plan`.

A completion-triggered archive step (move `.planning/<slug>/` into an archive directory and extract the decisions and errors tables into a git-tracked record) is a reasonable opt-in extension. It would sit on top of the three-file default the way attestation, gated mode, and topic handoffs already do, without changing the ephemeral default. It is not built in today. If you want it, a focused issue or PR is welcome.

---

## Key Interactions

### Hooks

| Hook | When It Fires | What It Does |
|------|---------------|--------------|
| **SessionStart** | When a Claude Code plugin session begins | Quietly restores the active plan; emits nothing when no plan is active |
| **PreToolUse** | Before matched tool operations | Refreshes the active plan context |
| **PostToolUse** | After matched write operations | Reminds the agent to update phase status |
| **Stop** | When the host tries to stop | Applies the opt-in gate only when every gate condition is satisfied |

The Claude plugin registers these lifecycle hooks at startup. A standalone Claude skill install has no `SessionStart`; its frontmatter hooks become active only after the skill is invoked for that session.

### The 2-Action Rule

After every 2 view/browser/search operations, you MUST update `findings.md`.

```
Operation 1: WebSearch → Note results
Operation 2: WebFetch → MUST UPDATE findings.md NOW
Operation 3: Read file → Note findings
Operation 4: Grep search → MUST UPDATE findings.md NOW
```

### Phase Completion

When a phase is complete:

1. Update `task_plan.md`:
   - Change status: `in_progress` → `complete`
   - Mark checkboxes: `[ ]` → `[x]`

2. Update `progress.md`:
   - Log actions taken
   - List files created/modified
   - Note any issues encountered

### Error Handling

When an error occurs:

1. Log in `task_plan.md` → Errors Encountered table
2. Log in `progress.md` → Error Log with timestamp
3. Document the resolution
4. Never repeat the same failed action

---

## File Relationships

```
┌─────────────────────────────────────────────────────────────────┐
│                         task_plan.md                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Goal: What you're trying to achieve                    │   │
│  │  Phases: 3-7 steps with status tracking                 │   │
│  │  Decisions: Major choices made                          │   │
│  │  Errors: Problems encountered                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│              PreToolUse hook reads this                         │
│              before every Write/Edit/Bash                       │
└─────────────────────────────────────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    │                    ▼
┌─────────────────┐            │          ┌─────────────────┐
│   findings.md   │            │          │   progress.md   │
│                 │            │          │                 │
│  Research       │◄───────────┘          │  Session log    │
│  Discoveries    │                       │  Actions taken  │
│  Tech decisions │                       │  Test results   │
│  Resources      │                       │  Error log      │
└─────────────────┘                       └─────────────────┘
```

---

## Topic Handoff Pattern

The three root files work best for one active task. When work splits into
multiple unrelated topics, prefer isolated planning directories:

```text
.planning/
  2026-01-10-backend-refactor/
    task_plan.md
    findings.md
    progress.md
  2026-01-10-production-incident/
    task_plan.md
    findings.md
    progress.md
```

Use the installed `scripts/init-session.sh <slug>` to create a scoped plan.
Resolve it with the installed `scripts/resolve-plan-dir.sh` (or `.ps1`). If
set, validate `PWF_PLAN_ROOT` as an absolute, existing project root. When
`PLAN_ID` is set, stop if the resolver returns no directory because the
explicit pin was rejected. With `PLAN_ID` unset, first run the resolver with
`--check-ambiguity` (`-CheckAmbiguity` in PowerShell); if it returns `PWF_PLAN_AMBIGUOUS_V1`, stop and set a
task-specific `PLAN_ID`. Then run the resolver normally and read the selected
directory. If it returns no directory and the project root has `task_plan.md`,
use the legacy root files; otherwise stop recovery.

Pin each parallel host with its task's `PLAN_ID` before starting it, or use
separate worktrees. Set `PWF_PLAN_ROOT` when the project root differs from the
host's working directory. `scripts/set-active-plan.sh <plan-id>` switches
`.planning/.active_plan`, but `.planning/.active_plan` is a shared default;
switching it does not bind parallel sessions to their tasks.

Some teams also keep durable topic handoffs alongside the root planning files:

```text
progress.md
  Short runtime timeline, plus links to topic handoffs

handoffs/<topic>.md
  Detailed current state, commands, validation, risks, rollback, PR links
```

This is useful when a topic spans many sessions or many chat threads. Keep
`progress.md` as the index and put details in the topic handoff. A good
handoff section answers:

| Question | Where to put it |
|----------|-----------------|
| What is running now? | `handoffs/<topic>.md` |
| How do I check it? | `handoffs/<topic>.md` |
| What changed today? | Short pointer in `progress.md` |
| What branch, commit, or PR matters? | Pointer in `progress.md`, details in the handoff |
| What risk remains? | `handoffs/<topic>.md` |

---

## The 5-Question Reboot Test

If you can answer these questions, your context management is solid:

| Question | Answer Source |
|----------|---------------|
| Where am I? | Current phase in `task_plan.md` |
| Where am I going? | Remaining phases in `task_plan.md` |
| What's the goal? | Goal statement in `task_plan.md` |
| What have I learned? | `findings.md` |
| What have I done? | `progress.md` |

---

## Next Steps

- [Quick Start Guide](quickstart.md) - Step-by-step tutorial
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
