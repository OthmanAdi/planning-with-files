# Hermes Setup

This repository includes a Hermes-specific adapter built from two pieces:

- `.hermes/skills/planning-with-files-hermes/` for the workflow instructions
- `.hermes/plugins/planning-with-files/` for project-local tools and planning context injection

## What Hermes Users Get

- Persistent `task_plan.md`, `findings.md`, and `progress.md` files in the project root
- Tool helpers to initialize files, summarize status, and run completion checks
- Automatic planning context injection on later turns through a Hermes plugin hook
- Slash-command-style prompt files for `/plan` and `/plan-status`

## What Changes Compared With Claude Code

- Hermes uses a Python plugin instead of Claude Code plugin manifests and hook scripts.
- Hermes can inject planning context before LLM calls.
- Hermes does not provide a stop hook that blocks session termination, so the completion check is a required workflow step.

## Project-Local Install

From the repository root:

```bash
export HERMES_ENABLE_PROJECT_PLUGINS=1
```

Add this repository to the active profile so Hermes can see the skill bundle:

```yaml
skills:
  external_dirs:
    - /absolute/path/to/planning-with-files/.hermes/skills
```

The project plugin lives under `.hermes/plugins/planning-with-files/`. Hermes discovers it automatically when `HERMES_ENABLE_PROJECT_PLUGINS=1` is set and the working directory is this repository.

## End-to-End Test Flow

1. Start Hermes in the target project directory.
2. Run the plan starter command or load the `planning-with-files-hermes` skill.
3. Use `planning_with_files_init` with `cwd` set to the target project root.
4. Make a few edits and run `planning_with_files_status` with the same `cwd`.
5. Run `planning_with_files_check_complete` before closing the task.

## Validation

Run the adapter test file from the repo root:

```bash
python3 -m unittest tests/test_hermes_adapter.py
```
