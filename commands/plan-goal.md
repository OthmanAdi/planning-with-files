---
description: "Bridge Claude Code's /goal to the active plan. Derives a goal condition from task_plan.md and invokes /goal so Claude keeps working until the plan is complete. Available since v2.38.0."
disable-model-invocation: true
allowed-tools: "Read Bash"
---

Bridge the active plan to Claude Code's `/goal` primitive.

Steps:

1. Validate `${PWF_PLAN_ROOT}` as an absolute existing project root when set; refuse an invalid root pin. Otherwise use cwd as the project root. Resolve the selected plan with `sh ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-plan-dir.sh` (PowerShell: `& "$env:CLAUDE_PLUGIN_ROOT\scripts\resolve-plan-dir.ps1"`). A printed directory is the selected plan. On empty output:
   - With non-empty `${PLAN_ID}`, the plan selector was rejected. Refuse and ask the user to correct the pin; never fall back to another plan.
   - If `resolve-plan-dir.sh --check-ambiguity` (PowerShell: `-CheckAmbiguity`) prints `PWF_PLAN_AMBIGUOUS_V1`, multiple plans exist without a selector. Refuse and ask the user to set `PLAN_ID=<slug>`.
   - Otherwise use legacy `task_plan.md` from the validated project root (`PWF_PLAN_ROOT` when set), if it exists. A valid root pin alone does not reject a legacy root plan.
   The shared `.planning/.active_plan` pointer does not bind a parallel session.
2. Read the selected `task_plan.md` and retain its absolute path for the goal condition and completion check.
3. Derive a goal condition from the plan content:
   - Default: "all phases in the selected task_plan.md report Status: complete and check-complete.sh with that explicit plan path reports ALL PHASES COMPLETE"
   - If user passed an argument: use that as an additional clause (e.g., `/plan-goal until all tests pass`)
4. Issue Claude Code's `/goal <condition>` with the derived text.
5. Confirm to the user: print the goal condition + the active plan ID + remind that `/goal clear` cancels.

If `task_plan.md` does not exist, refuse and direct user to run `/plan` first.

Why this exists:

`/goal` runs the agent until a small fast model confirms the condition is met. It evaluates the transcript only, not files. By deriving the condition from the plan file, this command turns the file-based plan into a measurable termination criterion for `/goal`, so the loop terminates when the plan is actually done, not when the conversation looks done.

Notes:

- `/plan-goal` does not replace `/goal`. It composes with it. Users can still run `/goal "any text"` directly.
- The derived condition stays under the 4000-char limit `/goal` enforces by quoting only phase headers + acceptance criteria, not full task body.
- Combine with `/plan-loop` for a "babysit until done" workflow: `/plan-loop` cadence + `/plan-goal` termination.
