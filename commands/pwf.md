---
description: "Short alias for /plan. Starts Manus-style file-based planning: task_plan.md, findings.md, progress.md. Available since v3.0.0."
---

Invoke the planning-with-files:planning-with-files skill and follow it exactly as presented to you. Treat any arguments as the task to plan.

Restore before creating. If `PWF_PLAN_ROOT` is set, validate it as an absolute existing project root; refuse an invalid root pin before reading or creating files. Otherwise the project root is the current directory. Resolve the selected task with `sh ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-plan-dir.sh` (PowerShell: `& "$env:CLAUDE_PLUGIN_ROOT\scripts\resolve-plan-dir.ps1"`):
- A printed directory is the selected task. Resume it: read its `task_plan.md`, `findings.md`, and `progress.md` and preserve them; never overwrite existing planning files.
- Empty output with non-empty `PLAN_ID` means the plan selector was rejected. Stop and ask the user to correct the pin. Do not fall back to the root or another plan.
- Empty output where `resolve-plan-dir.sh --check-ambiguity` (PowerShell: `-CheckAmbiguity`) prints `PWF_PLAN_AMBIGUOUS_V1` means multiple plans exist without a selector. Stop and ask the user to set `PLAN_ID=<slug>`.
- Otherwise empty output is the legacy project-root convention: resume `task_plan.md` from the validated project root (`PWF_PLAN_ROOT` when set), if it exists. A valid root pin alone does not reject a legacy root plan.

Only for a new task, run the initializer from the validated project root, including when `PWF_PLAN_ROOT` points away from the host cwd: `sh ${CLAUDE_PLUGIN_ROOT}/scripts/init-session.sh` (PowerShell: `init-session.ps1`). Pass a task name for an isolated `.planning/<id>/` plan and pin the host with its printed `PLAN_ID`. `.planning/.active_plan` is a shared default; it does not bind a parallel session.
- `task_plan.md`: for phases, progress, and decisions
- `findings.md`: for research and discoveries
- `progress.md`: for session logging

If the user asked for autonomous or gated mode in their words (for example "autonomous", "gated", "don't stop until done"), initialize with `init-session.sh --autonomous` or `init-session.sh --gated` accordingly; otherwise initialize the default way.

Keep each `### Phase N: Name` heading with exactly one `**Status:**` line, then validate the selected plan's explicit path with `sh ${CLAUDE_PLUGIN_ROOT}/scripts/check-complete.sh --validate path/to/task_plan.md` (PowerShell: `check-complete.ps1 -Validate -PlanFile path/to/task_plan.md`). If an existing plan fails validation, report it instead of rewriting it.

Then guide the user through the planning workflow.
