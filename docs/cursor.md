# Cursor IDE Setup

How to use planning-with-files with Cursor IDE — now with full hook support.

---

## Installation

### Option 1: Copy .cursor directory (Recommended)

```bash
git clone https://github.com/OthmanAdi/planning-with-files.git
cp -r planning-with-files/.cursor .cursor
```

This copies the skill files, hooks config, and hook scripts to your project.

### Option 2: Manual setup

1. Copy `.cursor/skills/planning-with-files/` to your project
2. Copy `.cursor/hooks.json` to your project
3. Copy `.cursor/hooks/` directory to your project

---

## Hooks Support

Cursor now supports hooks natively via `.cursor/hooks.json`. This skill includes four hooks that mirror the Claude Code experience:

| Hook | Purpose | Cursor Feature |
|------|---------|----------------|
| `userPromptSubmit` | Injects the selected plan and recent progress | Restores state on every prompt |
| `preToolUse` | Re-reads task_plan.md before tool operations | Keeps goals in context |
| `postToolUse` | Reminds to update plan after file edits | Prevents forgetting updates |
| `stop` | Checks if all phases are complete | **Auto-continues** if incomplete |

The native PowerShell hooks (`hooks.windows.json`) resolve the same selected
plan directory as the planning scripts, through the shared
`.cursor/skills/planning-with-files/scripts/resolve-plan-dir.ps1`, which must
therefore be present next to the hooks. The rules are the ones every route
applies: an explicit `PLAN_ID` is binding and fails closed when it names no
plan; `PWF_PLAN_ROOT` pins the project and fails closed when it is not an
absolute local directory; with one named plan, `.active_plan` or the newest
plan selects it; with two or more named plans, `PLAN_ID` is required and
nothing is injected until it is set; a stale pointer falls through to the
root `task_plan.md` like `inject-plan.sh`, while a pointer that is a directory
or a link fails closed. Each refusal prints one notice naming the cause.

The bash hooks (`hooks.json`) read only the root `task_plan.md`; a plan created
with `init-session.sh <name>` is not injected on that route.

Two differences from the Claude Code and Codex routes are deliberate. Session
isolation (`.planning/sessions/` with `.attached` markers) is not implemented on
Cursor, which has no session identity to attach; an armed project injects the
selected plan as if isolation were off. The stop hook answers only in JSON, so
an explicit `PLAN_ID` or `PWF_PLAN_ROOT` that resolves to no plan lets the agent
stop silently where `check-complete.sh` would print a notice.

### How the Stop Hook Works

The stop hook is the most powerful feature. When the agent tries to stop:

1. It checks `task_plan.md` for phase completion status
2. If all phases are complete → allows the agent to stop
3. If phases are incomplete → sends a `followup_message` that auto-prompts the agent to keep working

This means the agent **cannot stop until all phases are done** (up to `loop_limit` of 3 retries).

### Hook Files

```
your-project/
├── .cursor/
│   ├── hooks.json                  ← Hook configuration (bash scripts)
│   ├── hooks.windows.json          ← Hook configuration (PowerShell scripts)
│   ├── hooks/
│   │   ├── user-prompt-submit.sh   ← Plan context injection (root plan only)
│   │   ├── pre-tool-use.sh         ← Pre-tool-use script
│   │   ├── post-tool-use.sh        ← Post-tool-use script
│   │   ├── stop.sh                 ← Completion check script
│   │   ├── user-prompt-submit.ps1  ← PowerShell versions (named plans too)
│   │   ├── pre-tool-use.ps1
│   │   ├── post-tool-use.ps1
│   │   ├── stop.ps1
│   │   └── resolve-plan-context.ps1 ← Shared PowerShell plan selection
│   └── skills/
│       └── planning-with-files/
│           ├── SKILL.md
│           ├── examples.md
│           ├── reference.md
│           ├── scripts/            ← incl. resolve-plan-dir.ps1, used by the .ps1 hooks
│           └── templates/
├── task_plan.md                     ← Your planning files (created per task)
├── findings.md
├── progress.md
└── ...
```

---

## Windows Setup

The default `hooks.json` uses bash scripts (works on macOS, Linux, and Windows with Git Bash).

**If you need native PowerShell**, rename the config files:

```powershell
# Back up the default config
Rename-Item .cursor\hooks.json hooks.unix.json

# Use the PowerShell config
Rename-Item .cursor\hooks.windows.json hooks.json
```

The `.cursor/hooks.windows.json` file uses PowerShell to execute the `.ps1` hook scripts directly.

---

## What Each Hook Does

### PreToolUse Hook

**Triggers:** Before Write, Edit, Shell, or Read operations

**What it does:** Reads the first 30 lines of `task_plan.md` for context (the bash hook writes them to stderr, the PowerShell hook to the host output). Always returns `{"decision": "allow"}` — it never blocks tools, not even when its helper is missing.

**Claude Code equivalent:** `cat task_plan.md 2>/dev/null | head -30 || true`

### PostToolUse Hook

**Triggers:** After Write or Edit operations

**What it does:** Outputs a reminder to update `task_plan.md` if a phase was completed.

**Claude Code equivalent:** `echo '[planning-with-files] File updated...'`

### Stop Hook

**Triggers:** When the agent tries to stop working

**What it does:**
1. Counts total phases (`### Phase` headers) in `task_plan.md`
2. Counts completed phases (supports both `**Status:** complete` and `[complete]` formats)
3. If incomplete, returns `followup_message` to auto-continue
4. Capped at 3 retries via `loop_limit` to prevent infinite loops

**Claude Code equivalent:** `scripts/check-complete.sh` — but Cursor's version is **more powerful** because it can auto-continue the agent instead of just reporting status.

---

## Skill Files

The `.cursor/skills/planning-with-files/SKILL.md` file contains all the planning guidelines:

- Core 3-file planning pattern
- Templates (task_plan.md, findings.md, progress.md)
- The 2-Action Rule
- The 3-Strike Error Protocol
- Read vs Write Decision Matrix

Cursor automatically loads skills from `.cursor/skills/` when you open a project.

---

## Templates

The templates in `.cursor/skills/planning-with-files/templates/` are used when starting a new task:

- `task_plan.md` - Phase tracking template
- `findings.md` - Research storage template
- `progress.md` - Session logging template

The agent copies these to your project root when starting a new planning session.

---

## Tips for Cursor Users

1. **Pin the planning files:** Keep task_plan.md open in a split view for easy reference.

2. **Trust the hooks:** The stop hook will prevent premature completion — you don't need to manually verify phase status.

3. **Use explicit prompts for complex tasks:**
   ```
   This is a complex task. Let's use the planning-with-files pattern.
   Start by creating task_plan.md with the goal and phases.
   ```

4. **Check hook logs:** If hooks aren't working, check Cursor's output panel for hook execution logs.

---

## Compatibility with Claude Code

Your planning files (task_plan.md, findings.md, progress.md) are fully compatible between Cursor and Claude Code. You can switch between them without any changes to your planning files.

---

## Need Help?

Open an issue at [github.com/OthmanAdi/planning-with-files/issues](https://github.com/OthmanAdi/planning-with-files/issues).
