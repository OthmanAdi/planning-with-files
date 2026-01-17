# Codex CLI / IDE Setup

This guide explains how to use this repo as a Codex skill without duplicating templates or scripts.

Key facts:
- Codex loads skills from `.codex/skills/<skill-name>` (repo-scoped) or `~/.codex/skills/<skill-name>` (user-scoped).
- Each skill folder must include `SKILL.md` with `name` and `description` in YAML front matter.
- Codex ignores symlinked skill directories.
- Codex does not run Claude-style hooks; treat hook behavior as manual steps.

This repo already includes the canonical templates and scripts at the repo root:
- Templates: `templates/`
- Scripts: `scripts/`

## Option A: User-Scoped Install (Global, Recommended)

If you want a global skill, create it under `~/.codex/skills/`. Because it lives outside the repo, you must point to a stable repo path.

```bash
mkdir -p ~/.codex/skills/planning-with-files
cat > ~/.codex/skills/planning-with-files/SKILL.md <<'EOF'
---
name: planning-with-files
description: File-based planning workflow (task_plan.md, findings.md, progress.md) for complex multi-step tasks and research.
---
Use the templates and scripts from this repo:
- Templates: /absolute/path/to/planning-with-files/templates/
- Scripts: /absolute/path/to/planning-with-files/scripts/

Manual equivalents for Claude hooks:
- Re-read `task_plan.md` before major decisions.
- Update `task_plan.md` and `progress.md` after writes.
- After every 2 browser/search operations, write findings.
- Run `scripts/check-complete.sh` before stopping.
EOF
```

Replace `/absolute/path/to/planning-with-files` with your local clone path.

## Option B: Repo-Scoped Install (Local)

Repo-scoped skills are limited to this repo and can add `.codex/` to your git status. Use this only if you want the skill to be local to a specific project and you’re fine keeping `.codex/` untracked.

Create a small "shim" skill that points at this repo's existing files.

From the repo root:

```bash
mkdir -p .codex/skills/planning-with-files
cat > .codex/skills/planning-with-files/SKILL.md <<'EOF'
---
name: planning-with-files
description: File-based planning workflow (task_plan.md, findings.md, progress.md) for complex multi-step tasks and research.
---
Use the templates and scripts in this repo:
- Templates: `templates/`
- Scripts: `scripts/`

Manual equivalents for Claude hooks:
- Re-read `task_plan.md` before major decisions.
- Update `task_plan.md` and `progress.md` after writes.
- After every 2 browser/search operations, write findings.
- Run `scripts/check-complete.sh` before stopping.
EOF
```

Now, when working in this repo, Codex can load the skill from `.codex/skills/planning-with-files`.

## Using the Skill

1. Create planning files in your project root:
   - Run `scripts/init-session.sh`, or
   - Copy templates manually:
     ```bash
     cp templates/task_plan.md task_plan.md
     cp templates/findings.md findings.md
     cp templates/progress.md progress.md
     ```
2. Use `task_plan.md`, `findings.md`, and `progress.md` throughout the task.
3. Manually apply the “hook” behaviors listed above.
4. Before stopping, run `scripts/check-complete.sh` to verify all phases are complete.
