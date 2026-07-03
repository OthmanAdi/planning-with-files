# Autohand Code Setup

How to use planning-with-files with [Autohand Code](https://github.com/autohandai/code-cli/).

---

## What This Integration Adds

- Standard Agent Skill loading through Autohand Code skill discovery.
- Full templates, scripts, and reference documentation from the canonical skill.
- User-level or project-level installs.

Autohand Code discovers skills from multiple locations, including:

1. **User-level skills:** `~/.autohand/skills/`
2. **Project-level skills:** `<project>/.autohand/skills/`
3. **Shared Agent Skills:** `~/.agents/skills/`

---

## Installation (standard Agent Skills)

Install with the shared Agent Skills installer:

```bash
npx skills add OthmanAdi/planning-with-files --skill planning-with-files -g
```

This installs into the shared Agent Skills convention that Autohand Code can scan.

---

## Installation (Autohand-native user scope)

Install just for your user account:

```bash
git clone https://github.com/OthmanAdi/planning-with-files.git /tmp/planning-with-files
mkdir -p ~/.autohand/skills
cp -r /tmp/planning-with-files/skills/planning-with-files ~/.autohand/skills/
rm -rf /tmp/planning-with-files
```

---

## Installation (Autohand-native project scope)

Commit the skill to a project so the whole team gets the same planning workflow:

```bash
git clone https://github.com/OthmanAdi/planning-with-files.git /tmp/planning-with-files
mkdir -p .autohand/skills
cp -r /tmp/planning-with-files/skills/planning-with-files .autohand/skills/
git add .autohand/skills/planning-with-files
git commit -m "Add planning-with-files skill for Autohand Code"
rm -rf /tmp/planning-with-files
```

---

## Autohand Catalog Skills

Autohand Code can browse its community catalog with:

```bash
autohand --skill-install
```

Project-scoped catalog installs use:

```bash
autohand --skill-install <skill-name> --project
```

For this repository, use `npx skills add` or the direct clone paths above unless the skill appears in the Autohand catalog.

---

## Usage

Start Autohand Code in your project. For complex tasks, the skill guides the agent to create and maintain:

- `task_plan.md` — phases, progress, and decisions
- `findings.md` — research and discoveries
- `progress.md` — session log and test results

The planning files live in your project root, not inside the skill directory.

---

## Notes

- This is standard Agent Skills support. Claude Code plugin commands and Claude-specific hooks are not installed by this path.
- The underlying planning files are tool-agnostic and work across Claude Code, Cursor, Codex, Autohand Code, and other agents.
- If you use both shared `~/.agents/skills/` and Autohand-native directories, avoid installing duplicate copies of the same skill.
