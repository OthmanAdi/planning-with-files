---
name: planning-with-files
description: "Manus-style persistent file-based planning for AI coding agents: keeps task_plan.md, findings.md, and progress.md on disk so work survives context loss and /clear. Use when asked to plan out, break down, or organize a multi-step project, research task, or any work requiring 5+ tool calls. Supports automatic session recovery after /clear."
user-invocable: true
allowed-tools: "Read Write Edit Bash Glob Grep"
hooks:
  # Generated dispatch block: the 11 IDE and language variants share one
  # template (parity locked by tests/test_skill_hook_dispatch_parity.py).
  # Candidate order, first existing file wins: PWF_SCRIPT_DIR (explicit user
  # override for workspace or other nonstandard installs), CLAUDE_SKILL_DIR,
  # host env var, host user-level install dirs, then the two .claude paths.
  # Deliberate asymmetry: only UserPromptSubmit reports an unresolved script,
  # once per prompt. PreToolUse and PreCompact fire per tool call and Stop
  # carries no plan body, so a notice there would be spam; they stay silent.
  UserPromptSubmit:
    - hooks:
        - type: command
          command: "SH=\"\"; for c in \"${PWF_SCRIPT_DIR}/inject-plan.sh\" \"${CLAUDE_SKILL_DIR}/scripts/inject-plan.sh\" \"$HOME/.config/opencode/skills/planning-with-files/scripts/inject-plan.sh\" \"$HOME/.opencode/skills/planning-with-files/scripts/inject-plan.sh\" \"$HOME/.claude/skills/planning-with-files/scripts/inject-plan.sh\" \"$HOME/.claude/plugins/marketplaces/planning-with-files/scripts/inject-plan.sh\"; do [ -f \"$c\" ] && { SH=\"$c\"; break; }; done; if [ -n \"$SH\" ]; then sh \"$SH\" --context=userprompt; else echo \"[planning-with-files] hook script not found; plan injection is off. Set PWF_SCRIPT_DIR to the skill's scripts directory, or install the skill to a user-level path.\"; fi; exit 0"
  PreToolUse:
    - matcher: "Write|Edit|Bash|Read|Glob|Grep"
      hooks:
        - type: command
          command: "SH=\"\"; for c in \"${PWF_SCRIPT_DIR}/inject-plan.sh\" \"${CLAUDE_SKILL_DIR}/scripts/inject-plan.sh\" \"$HOME/.config/opencode/skills/planning-with-files/scripts/inject-plan.sh\" \"$HOME/.opencode/skills/planning-with-files/scripts/inject-plan.sh\" \"$HOME/.claude/skills/planning-with-files/scripts/inject-plan.sh\" \"$HOME/.claude/plugins/marketplaces/planning-with-files/scripts/inject-plan.sh\"; do [ -f \"$c\" ] && { SH=\"$c\"; break; }; done; [ -n \"$SH\" ] && sh \"$SH\" --context=pretool; exit 0"
  PostToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "if [ -f task_plan.md ] || [ -f .planning/.active_plan ] || ls .planning/*/task_plan.md >/dev/null 2>&1; then echo '[planning-with-files] Update progress.md with what you just did. If a phase is now complete, update task_plan.md status.'; fi"
  Stop:
    - hooks:
        - type: command
          command: "PS1_T=\"\"; for c in \"${PWF_SCRIPT_DIR}/check-complete.ps1\" \"${CLAUDE_SKILL_DIR}/scripts/check-complete.ps1\" \"$HOME/.config/opencode/skills/planning-with-files/scripts/check-complete.ps1\" \"$HOME/.opencode/skills/planning-with-files/scripts/check-complete.ps1\" \"$HOME/.claude/skills/planning-with-files/scripts/check-complete.ps1\" \"$HOME/.claude/plugins/marketplaces/planning-with-files/scripts/check-complete.ps1\"; do [ -f \"$c\" ] && { PS1_T=\"$c\"; break; }; done; SH_T=\"\"; for c in \"${PWF_SCRIPT_DIR}/check-complete.sh\" \"${CLAUDE_SKILL_DIR}/scripts/check-complete.sh\" \"$HOME/.config/opencode/skills/planning-with-files/scripts/check-complete.sh\" \"$HOME/.opencode/skills/planning-with-files/scripts/check-complete.sh\" \"$HOME/.claude/skills/planning-with-files/scripts/check-complete.sh\" \"$HOME/.claude/plugins/marketplaces/planning-with-files/scripts/check-complete.sh\"; do [ -f \"$c\" ] && { SH_T=\"$c\"; break; }; done; case \"$(uname -s 2>/dev/null)\" in MINGW*|MSYS*|CYGWIN*) if [ -n \"$PS1_T\" ] && [ -f \"$PS1_T\" ]; then powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File \"$PS1_T\" 2>/dev/null; elif [ -n \"$SH_T\" ] && [ -f \"$SH_T\" ]; then sh \"$SH_T\" 2>/dev/null; fi ;; *) if [ -n \"$SH_T\" ] && [ -f \"$SH_T\" ]; then sh \"$SH_T\" 2>/dev/null; elif [ -n \"$PS1_T\" ] && [ -f \"$PS1_T\" ]; then powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File \"$PS1_T\" 2>/dev/null; fi ;; esac; exit 0"
  PreCompact:
    - matcher: "*"
      hooks:
        - type: command
          command: "SH=\"\"; for c in \"${PWF_SCRIPT_DIR}/inject-plan.sh\" \"${CLAUDE_SKILL_DIR}/scripts/inject-plan.sh\" \"$HOME/.config/opencode/skills/planning-with-files/scripts/inject-plan.sh\" \"$HOME/.opencode/skills/planning-with-files/scripts/inject-plan.sh\" \"$HOME/.claude/skills/planning-with-files/scripts/inject-plan.sh\" \"$HOME/.claude/plugins/marketplaces/planning-with-files/scripts/inject-plan.sh\"; do [ -f \"$c\" ] && { SH=\"$c\"; break; }; done; [ -n \"$SH\" ] && sh \"$SH\" --context=precompact; exit 0"
metadata:
  version: "3.10.0"

---

# Planning with Files

Work like Manus: Use persistent markdown files as your "working memory on disk."

## FIRST: Check for Previous Session (v2.2.0)

**Before starting work**, check for unsynced context from a previous session:

```bash
# Linux/macOS (auto-detects python3 or python)
$(command -v python3 || command -v python) ~/.config/opencode/skills/planning-with-files/scripts/session-catchup.py "$(pwd)"
```

```powershell
# Windows PowerShell
python "$env:USERPROFILE\.opencode\skills\planning-with-files\scripts\session-catchup.py" (Get-Location)
```

If catchup report shows unsynced context:
1. Run `git diff --stat` to see actual code changes
2. Read current planning files
3. Update planning files based on catchup + git diff
4. Then proceed with task

## Important: Where Files Go

- **Templates** are in `~/.config/opencode/skills/planning-with-files/templates/`
- **Your planning files** go in **your project directory**

| Location | What Goes There |
|----------|-----------------|
| Skill directory (`~/.config/opencode/skills/planning-with-files/`) | Templates, scripts, reference docs |
| Your project directory | `task_plan.md`, `findings.md`, `progress.md` |

## Quick Start

Before ANY complex task:

1. **Create `task_plan.md`** — Use [templates/task_plan.md](templates/task_plan.md) as reference
2. **Create `findings.md`** — Use [templates/findings.md](templates/findings.md) as reference
3. **Create `progress.md`** — Use [templates/progress.md](templates/progress.md) as reference
4. **Re-read plan before decisions** — Refreshes goals in attention window
5. **Update after each phase** — Mark complete, log errors

> **Note:** Planning files go in your project root, not the skill installation folder.

## The Core Pattern

```
Context Window = RAM (volatile, limited)
Filesystem = Disk (persistent, unlimited)

→ Anything important gets written to disk.
```

## File Purposes

| File | Purpose | When to Update |
|------|---------|----------------|
| `task_plan.md` | Phases, progress, decisions | After each phase |
| `findings.md` | Research, discoveries | After ANY discovery |
| `progress.md` | Session log, test results | Throughout session |

## Critical Rules

### 1. Create Plan First
Never start a complex task without `task_plan.md`. Non-negotiable.

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
| Where am I? | Current phase in task_plan.md |
| Where am I going? | Remaining phases |
| What's the goal? | Goal statement in plan |
| What have I learned? | findings.md |
| What have I done? | progress.md |

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

- `scripts/init-session.sh` — Initialize all planning files
- `scripts/check-complete.sh` — Verify all phases complete
- `scripts/session-catchup.py` — Recover context from previous session (v2.2.0)

## Advanced Topics

- **Manus Principles:** See [reference.md](reference.md)
- **Real Examples:** See [examples.md](examples.md)

## Anti-Patterns

| Don't | Do Instead |
|-------|------------|
| Use TodoWrite for persistence | Create task_plan.md file |
| State goals once and forget | Re-read plan before decisions |
| Hide errors and retry silently | Log errors to plan file |
| Stuff everything in context | Store large content in files |
| Start executing immediately | Create plan file FIRST |
| Repeat failed actions | Track attempts, mutate approach |
| Create files in skill directory | Create files in your project |
