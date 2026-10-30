---
description: "Show current planning status at a glance - phases, progress, and any logged errors."
---

Resolve the selected task, then read `task_plan.md` from that one directory and display a compact status summary.

## Resolve the Selected Task

Run `sh ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-plan-dir.sh` (PowerShell: `& "$env:CLAUDE_PLUGIN_ROOT\scripts\resolve-plan-dir.ps1"`):
- A printed directory is the selected task. Read its `task_plan.md`, `findings.md`, and `progress.md`. A root `task_plan.md` must not override it.
- Empty output with `PLAN_ID` or `PWF_PLAN_ROOT` set means the selector was rejected. Report that the pin did not resolve and read nothing else.
- Empty output where `resolve-plan-dir.sh --check-ambiguity` (PowerShell: `-CheckAmbiguity`) prints `PWF_PLAN_AMBIGUOUS_V1` means multiple plans exist without a selector. Report that and ask the user to set `PLAN_ID=<slug>`; do not pick one.
- Otherwise empty output is the legacy project-root convention: use the root planning files.

`.planning/.active_plan` is a shared default; it does not bind a parallel session.

## What to Show

1. **Current Phase**: Extract from "## Current Phase" section
2. **Phase Progress**: Count phases and their status (pending/in_progress/complete)
3. **Phase List**: Show each phase with status icon
4. **Errors**: Count entries in "## Errors Encountered" table if present
5. **Files Check**: Confirm which planning files exist

## Status Icons

- `[ ]` or "pending" → ⏸️
- "in_progress" → 🔄
- `[x]` or "complete" → ✅
- "failed" or "blocked" → ❌

## Output Format

```
📋 Planning Status

Current: Phase {N} of {total} ({percent}%)
Status: {status_icon} {status_text}

  {icon} Phase 1: {name}
  {icon} Phase 2: {name} ← you are here
  {icon} Phase 3: {name}
  ...

Files: task_plan.md {✓|✗} | findings.md {✓|✗} | progress.md {✓|✗}
Errors logged: {count}
```

## If No Planning Files Exist

```
📋 No planning files found

Run /plan to start a new planning session.
```

## Keep It Brief

This is a quick status check, not a full report. Show just enough to answer "where am I?" without re-reading all the files.
