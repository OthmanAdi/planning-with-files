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

## Key Interactions

### Hooks

| Hook | When It Fires | What It Does |
|------|---------------|--------------|
| **SessionStart** | When Claude Code session begins | Notifies skill is ready |
| **PreToolUse** | Before Write/Edit/Bash operations | Reads `task_plan.md` to refresh goals |
| **PostToolUse** | After Write/Edit operations | Reminds to update phase status |
| **Stop** | When Claude tries to stop | Verifies all phases are complete |

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

Use `scripts/init-session.sh <slug>` to create a scoped plan and
`scripts/set-active-plan.sh <plan-id>` to switch the active plan. Hooks resolve
the active plan from `$PLAN_ID`, `.planning/.active_plan`, the newest scoped
plan, then the legacy root files.

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
