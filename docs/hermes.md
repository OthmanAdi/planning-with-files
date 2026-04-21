# Hermes Setup

This repository ships a Hermes adapter for planning-with-files.

The adapter has two parts:

- `.hermes/skills/planning-with-files-hermes/` contains the Hermes-facing workflow skill
- `.hermes/plugins/planning-with-files/` contains the project plugin that provides planning tools and context injection

## What the Adapter Provides

- `planning_with_files_init` creates `task_plan.md`, `findings.md`, and `progress.md` in the target project
- `planning_with_files_status` summarizes the current planning state
- `planning_with_files_check_complete` runs the completion check helper
- The project plugin injects active planning context on later turns and reminds the agent to update planning files after write-like actions

## Install

### 1. Enable project plugins

```bash
export HERMES_ENABLE_PROJECT_PLUGINS=1
```

### 2. Add the skill directory to your Hermes profile

```yaml
skills:
  external_dirs:
    - /absolute/path/to/planning-with-files/.hermes/skills
```

### 3. Start Hermes from the target project directory

The project plugin lives under `.hermes/plugins/planning-with-files/`. Hermes discovers it automatically when project plugins are enabled and the working directory is this repository.

## Usage

- Run `/plan` to start the planning workflow in the current project
- Run `/plan-status` to inspect the current planning state
- Load `planning-with-files-hermes` directly when you want the workflow instructions without the command wrapper

## Validation

```bash
python3 -m unittest tests/test_hermes_adapter.py
```
