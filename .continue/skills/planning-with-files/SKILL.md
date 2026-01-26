---
name: planning-with-files
version: "2.9.0"
description: Implements Manus-style file-based planning for complex tasks. Creates task_plan.md, findings.md, and progress.md. Use when starting complex multi-step tasks, research projects, or any task requiring >5 tool calls. Now with automatic session recovery after /clear.
---

# Planning with Files

Work like Manus: Use persistent markdown files as your "working memory on disk."

## FIRST: Check for Previous Session (v2.2.0)

Before starting work, check for unsynced context from a previous session:

```bash
python3 .continue/skills/planning-with-files/scripts/session-catchup.py "$(pwd)" || python .continue/skills/planning-with-files/scripts/session-catchup.py "$(pwd)"
```

If catchup report shows unsynced context:
1. Run `git diff --stat` to see actual code changes
2. Read current planning files
3. Update planning files based on catchup + git diff
4. Then proceed with task

## Quick Start

Before any complex task:

1. Create `task_plan.md`, `findings.md`, `progress.md` in your project root
2. If they don't exist yet, initialize them using:
   - macOS/Linux: `bash .continue/skills/planning-with-files/scripts/init-session.sh`
   - Windows: `powershell -ExecutionPolicy Bypass -File .continue/skills/planning-with-files/scripts/init-session.ps1`
3. Re-read `task_plan.md` before major decisions
4. Update `task_plan.md` after each phase completes
5. Write discoveries to `findings.md` (especially after web/search/image/PDF viewing)

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
| `findings.md` | Research, discoveries | After any discovery |
| `progress.md` | Session log, test results | Throughout session |

## Critical Rules

### 1. Create Plan First

Never start a complex task without `task_plan.md`.

### 2. The 2-Action Rule

After every 2 view/browser/search operations, save key findings to text files.

### 3. Read Before Decide

Before major decisions, read `task_plan.md` to refresh goals.

### 4. Update After Act

After completing any phase, update statuses and log errors in `task_plan.md`.

### 5. Log ALL Errors

Every error goes in the plan file so you don't repeat it.

### 6. Never Repeat Failures

If an action failed, the next action must be different.

## References

- [reference.md](reference.md)
- [examples.md](examples.md)
