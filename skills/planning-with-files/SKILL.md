---
name: planning-with-files
version: "2.16.0"
description: Implements Manus-style file-based planning for complex tasks. Creates isolated plans in ./.planning/{uuid}/ with task_plan.md, findings.md, and progress.md. Supports parallel plans via per-session PLAN_ID pinning.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - WebFetch
  - WebSearch
hooks:
  PreToolUse:
    - matcher: "Write|Edit|Bash|Read|Glob|Grep"
      hooks:
        - type: command
          command: |
            SKILL_ROOT="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/skills/planning-with-files}"
            SCRIPT_DIR="$SKILL_ROOT/scripts"
            PLAN_DIR="$(sh "$SCRIPT_DIR/resolve-plan-dir.sh" 2>/dev/null || true)"
            if [ -n "$PLAN_DIR" ] && [ -f "$PLAN_DIR/task_plan.md" ]; then
              head -30 "$PLAN_DIR/task_plan.md"
            fi
  PostToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: |
            SKILL_ROOT="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/skills/planning-with-files}"
            SCRIPT_DIR="$SKILL_ROOT/scripts"
            PLAN_DIR="$(sh "$SCRIPT_DIR/resolve-plan-dir.sh" 2>/dev/null || true)"
            if [ -n "$PLAN_DIR" ]; then
              echo "[planning-with-files] File updated. If this completes a phase, update $PLAN_DIR/task_plan.md status."
            else
              echo "[planning-with-files] File updated. If this completes a phase, update active plan task_plan.md status."
            fi
  Stop:
    - hooks:
        - type: command
          command: |
            SCRIPT_DIR="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/skills/planning-with-files}/scripts"

            IS_WINDOWS=0
            if [ "${OS-}" = "Windows_NT" ]; then
              IS_WINDOWS=1
            else
              UNAME_S="$(uname -s 2>/dev/null || echo '')"
              case "$UNAME_S" in
                CYGWIN*|MINGW*|MSYS*) IS_WINDOWS=1 ;;
              esac
            fi

            if [ "$IS_WINDOWS" -eq 1 ]; then
              if command -v pwsh >/dev/null 2>&1; then
                pwsh -ExecutionPolicy Bypass -File "$SCRIPT_DIR/check-complete.ps1" 2>/dev/null ||
                powershell -ExecutionPolicy Bypass -File "$SCRIPT_DIR/check-complete.ps1" 2>/dev/null ||
                sh "$SCRIPT_DIR/check-complete.sh"
              else
                powershell -ExecutionPolicy Bypass -File "$SCRIPT_DIR/check-complete.ps1" 2>/dev/null ||
                sh "$SCRIPT_DIR/check-complete.sh"
              fi
            else
              sh "$SCRIPT_DIR/check-complete.sh"
            fi
---

# Planning with Files

Work like Manus: Use persistent markdown files as your "working memory on disk."

## FIRST: Check for Previous Session (v2.2.0)

**Before starting work**, check for unsynced context from a previous session:

```bash
# Linux/macOS
SKILL_ROOT="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/skills/planning-with-files}"
$(command -v python3 || command -v python) "$SKILL_ROOT/scripts/session-catchup.py" "$(pwd)"
```

```powershell
# Windows PowerShell
& (Get-Command python -ErrorAction SilentlyContinue).Source "$env:USERPROFILE\.claude\skills\planning-with-files\scripts\session-catchup.py" (Get-Location)
```

If catchup report shows unsynced context:
1. Run `git diff --stat` to see actual code changes
2. Read current planning files
3. Update planning files based on catchup + git diff
4. Then proceed with task

## Important: Where Files Go

- **Templates** are in `${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/skills/planning-with-files}/templates/`
- **Your planning files** go in **`./.planning/{plan_id}/` under your project directory**

| Location | What Goes There |
|----------|-----------------|
| Skill directory (`${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/skills/planning-with-files}/`) | Templates, scripts, reference docs |
| Your project directory | `.planning/.active_plan` + `.planning/{plan_id}/task_plan.md|findings.md|progress.md` |

## Quick Start

Before ANY complex task:

1. **Generate a new plan ID and create plan files** — Run `SKILL_ROOT="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/skills/planning-with-files}"; sh "$SKILL_ROOT/scripts/init-session.sh"` (or PowerShell script)
2. **Confirm active plan** — `cat .planning/.active_plan` and use `.planning/<plan_id>/...` files for this task
3. **Pin this terminal to the plan (recommended for parallel work)** — `export PLAN_ID=<plan_id>` (PowerShell: `$env:PLAN_ID='<plan_id>'`)
4. **Re-read active `task_plan.md` before decisions** — Refreshes goals in attention window
5. **Update active plan files after each phase** — Mark complete, log errors

> **Note:** Planning files are isolated per task in `./.planning/{uuid}/` to avoid conflicts across parallel plans.
> **Parallel safety:** `.planning/.active_plan` is a shared default pointer; set `PLAN_ID` per terminal/session to avoid cross-session pointer collisions.
> **Switch shared default pointer (optional):** run `SKILL_ROOT="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/skills/planning-with-files}"; sh "$SKILL_ROOT/scripts/set-active-plan.sh" <plan_id>` (or PowerShell script).

## The Core Pattern

```
Context Window = RAM (volatile, limited)
Filesystem = Disk (persistent, unlimited)

→ Anything important gets written to disk.
```

## File Purposes

| File | Purpose | When to Update |
|------|---------|----------------|
| `.planning/{plan_id}/task_plan.md` | Phases, progress, decisions | After each phase |
| `.planning/{plan_id}/findings.md` | Research, discoveries | After ANY discovery |
| `.planning/{plan_id}/progress.md` | Session log, test results | Throughout session |

## Critical Rules

### 1. Create Plan First
Never start a complex task without creating a new `.planning/{uuid}/task_plan.md`. Non-negotiable.

### 2. The 2-Action Rule
> "After every 2 view/browser/search operations, IMMEDIATELY save key findings to text files."

This prevents visual/multimodal information from being lost.

### 3. Read Before Decide
Before major decisions, read the plan file. This keeps goals in your attention window.

### 4. Update After Act
After completing any phase:
- Mark phase status: `in_progress` → `complete`
- Log any errors encountered
- Note files created/modified

### 5. Log ALL Errors
Every error goes in the plan file. This builds knowledge and prevents repetition.

```markdown
## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| FileNotFoundError | 1 | Created default config |
| API timeout | 2 | Added retry logic |
```

### 6. Never Repeat Failures
```
if action_failed:
    next_action != same_action
```
Track what you tried. Mutate the approach.

## The 3-Strike Error Protocol

```
ATTEMPT 1: Diagnose & Fix
  → Read error carefully
  → Identify root cause
  → Apply targeted fix

ATTEMPT 2: Alternative Approach
  → Same error? Try different method
  → Different tool? Different library?
  → NEVER repeat exact same failing action

ATTEMPT 3: Broader Rethink
  → Question assumptions
  → Search for solutions
  → Consider updating the plan

AFTER 3 FAILURES: Escalate to User
  → Explain what you tried
  → Share the specific error
  → Ask for guidance
```

## Read vs Write Decision Matrix

| Situation | Action | Reason |
|-----------|--------|--------|
| Just wrote a file | DON'T read | Content still in context |
| Viewed image/PDF | Write findings NOW | Multimodal → text before lost |
| Browser returned data | Write to file | Screenshots don't persist |
| Starting new phase | Read plan/findings | Re-orient if context stale |
| Error occurred | Read relevant file | Need current state to fix |
| Resuming after gap | Read all planning files | Recover state |

## The 5-Question Reboot Test

If you can answer these, your context management is solid:

| Question | Answer Source |
|----------|---------------|
| Where am I? | Current phase in active `.planning/{plan_id}/task_plan.md` |
| Where am I going? | Remaining phases |
| What's the goal? | Goal statement in plan |
| What have I learned? | active `.planning/{plan_id}/findings.md` |
| What have I done? | active `.planning/{plan_id}/progress.md` |

## When to Use This Pattern

**Use for:**
- Multi-step tasks (3+ steps)
- Research tasks
- Building/creating projects
- Tasks spanning many tool calls
- Anything requiring organization

**Skip for:**
- Simple questions
- Single-file edits
- Quick lookups

## Templates

Copy these templates to start:

- [templates/task_plan.md](templates/task_plan.md) — Phase tracking
- [templates/findings.md](templates/findings.md) — Research storage
- [templates/progress.md](templates/progress.md) — Session logging

## Scripts

Helper scripts for automation:

- `scripts/init-session.sh` — Create a new UUID plan under `./.planning/{plan_id}/`
- `scripts/check-complete.sh` — Verify all phases complete
- `scripts/session-catchup.py` — Recover context from previous session (v2.2.0)
- `scripts/resolve-plan-dir.sh` — Resolve active plan directory (`$PLAN_ID` > `.planning/.active_plan` > latest plan dir)
- `scripts/set-active-plan.sh` — Switch shared `.planning/.active_plan` pointer manually

## Advanced Topics

- **Manus Principles:** See [reference.md](reference.md)
- **Real Examples:** See [examples.md](examples.md)

## Anti-Patterns

| Don't | Do Instead |
|-------|------------|
| Use TodoWrite for persistence | Run `init-session` to create `.planning/{uuid}` files |
| State goals once and forget | Re-read plan before decisions |
| Hide errors and retry silently | Log errors to plan file |
| Stuff everything in context | Store large content in files |
| Start executing immediately | Create plan file FIRST |
| Repeat failed actions | Track attempts, mutate approach |
| Create files in skill directory | Create files in your project |
