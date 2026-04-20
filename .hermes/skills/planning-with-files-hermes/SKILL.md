---
name: planning-with-files-hermes
description: Hermes adaptation of planning-with-files. Use for complex tasks that benefit from persistent markdown planning files, progress tracking, and resumable session context.
---

# Planning with Files for Hermes

Use this skill when a task spans multiple steps, requires research, or will take many tool calls.

## Before You Start

1. Run `planning_with_files_init` in the current project directory if `task_plan.md`, `findings.md`, or `progress.md` do not exist.
2. Pass an explicit `cwd` argument when the target project path is known. This keeps planning files anchored to the intended project root.
3. Read `task_plan.md`, `findings.md`, and `progress.md` before making a plan or resuming work.
4. If the project already has planning files, continue from the current phase instead of restarting the plan.

## Core Workflow

1. Create or update `task_plan.md` before major implementation work.
2. Record discoveries in `findings.md` as soon as they are confirmed.
3. Append meaningful milestones, test results, and blockers to `progress.md` during the session.
4. Re-read `task_plan.md` before major decisions, long tool sequences, or code changes.
5. Run `planning_with_files_check_complete` before you declare the task finished.

## File Roles

- `task_plan.md` stores phases, status, decisions, and errors.
- `findings.md` stores research notes, facts, and references.
- `progress.md` stores the session log and verification notes.

## Hermes Mapping

- Use the `planning_with_files_init` tool to create the files from the canonical templates.
- Use the `planning_with_files_status` tool to get a compact progress summary.
- Hermes project plugin hooks can inject active planning context into later turns.
- Hermes project plugins cannot hard-block session termination, so always run the completion check before closing the task.

## Recovery Pattern

When resuming after a pause:

1. Read all three planning files.
2. Run `git diff --stat` if code may have changed since the last update.
3. Update the planning files first.
4. Continue the next unfinished phase.

## Practical Rules

- Plan first for any task with 3 or more concrete steps.
- Keep statuses current: `pending`, `in_progress`, `complete`, `failed`, or `blocked`.
- Log every confirmed error and its resolution path.
- Change approach after a failed attempt instead of repeating the same step.
- Keep planning files in the project root.
