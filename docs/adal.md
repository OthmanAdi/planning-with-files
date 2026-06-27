# AdaL CLI / Sylph AI Setup

How to use planning-with-files with AdaL CLI (Sylph AI).

---

## About AdaL

[AdaL](https://docs.sylph.ai/) is a CLI tool from SylphAI that brings AI-powered coding assistance to your terminal. AdaL skills are **compatible with Claude Code skills**, so you can use the same skill format.

---

## Installation

### Option 1: Via Plugin Marketplace (Recommended)

```bash
# Add the marketplace (one-time setup)
/plugin marketplace add OthmanAdi/planning-with-files

# Browse and install via dialog
/plugin

# Or install directly
/plugin install planning-with-files@planning-with-files
```

### Option 2: Copy to personal skills directory

```bash
git clone https://github.com/OthmanAdi/planning-with-files.git
mkdir -p ~/.adal/skills
cp -r planning-with-files/skills/planning-with-files ~/.adal/skills/
```

### Option 3: Copy to project skills directory

```bash
git clone https://github.com/OthmanAdi/planning-with-files.git
mkdir -p .adal/skills
cp -r planning-with-files/skills/planning-with-files .adal/skills/
```

### Option 4: Windows (PowerShell)

```powershell
git clone https://github.com/OthmanAdi/planning-with-files.git
New-Item -ItemType Directory -Force -Path $env:USERPROFILE\.adal\skills
Copy-Item -Recurse -Path "planning-with-files\skills\planning-with-files" -Destination "$env:USERPROFILE\.adal\skills\"
```

---

## Skill Locations

AdaL supports three skill sources:

| Source | Location | Use Case |
|--------|----------|----------|
| Personal | `~/.adal/skills/` | Your custom skills (highest priority) |
| Project | `.adal/skills/` | Team skills shared via git |
| Plugin | `~/.adal/plugin-cache/` | External skills from GitHub (lowest priority) |

---

## Using /skills Command

In AdaL, view all active skills with:

```
/skills
```

This shows skills from all sources (personal, project, plugins):

```
> Skills (Page 1/1)

Personal (~/.adal/skills/):
  planning-with-files

Project (.adal/skills/):
  (none)

Plugins:
  (none)
```

---

## Using /plugin Commands

Manage external skills from GitHub:

| Command | Description |
|---------|-------------|
| `/plugin marketplace add <owner/repo>` | Add a marketplace (one-time setup) |
| `/plugin` | Browse available plugins and marketplaces |
| `/plugin install <plugin>@<marketplace>` | Install a plugin |
| `/plugin uninstall <plugin>@<marketplace>` | Uninstall a plugin |
| `/plugin marketplace remove <name>` | Remove a marketplace |

---

## File Structure

```
your-project/
├── .adal/
│   └── skills/
│       └── planning-with-files/
│           ├── SKILL.md
│           ├── templates/
│           │   ├── task_plan.md
│           │   ├── findings.md
│           │   └── progress.md
│           ├── scripts/
│           │   ├── init-session.sh
│           │   ├── init-session.ps1
│           │   ├── check-complete.sh
│           │   ├── check-complete.ps1
│           │   └── session-catchup.py
│           └── references/
│               ├── examples.md
│               └── reference.md
├── task_plan.md        ← Your planning files go here
├── findings.md
├── progress.md
└── ...
```

---

## Templates

The templates in `.adal/skills/planning-with-files/templates/` work in AdaL:

- `task_plan.md` - Phase tracking template
- `findings.md` - Research storage template
- `progress.md` - Session logging template

Copy them to your project root when starting a new task.

---

## Scripts

Helper scripts for manual execution (AdaL executes scripts via bash):

```bash
# Initialize planning files
bash ~/.adal/skills/planning-with-files/scripts/init-session.sh

# Check task completion
bash ~/.adal/skills/planning-with-files/scripts/check-complete.sh

# Session recovery
python ~/.adal/skills/planning-with-files/scripts/session-catchup.py $(pwd)
```

Windows PowerShell:
```powershell
# Initialize planning files
powershell -File "$env:USERPROFILE\.adal\skills\planning-with-files\scripts\init-session.ps1"

# Check task completion
powershell -File "$env:USERPROFILE\.adal\skills\planning-with-files\scripts\check-complete.ps1"
```

---

## Tips for AdaL Users

1. **Use /skills command:** Verify planning-with-files is active after installation.

2. **Use explicit prompts:** Be explicit when starting complex tasks:
   ```
   This is a complex task. Let's use the planning-with-files pattern.
   Start by creating task_plan.md with the goal and phases.
   ```

3. **Pin planning files:** Keep task_plan.md open for easy reference.

4. **Re-read plan before decisions:** Periodically ask AdaL to read task_plan.md to refresh goals.

5. **Check status regularly:** Verify all phases are complete before finishing.

---

## Need Help?

- AdaL Documentation: [docs.sylph.ai](https://docs.sylph.ai/)
- Open an issue at [github.com/OthmanAdi/planning-with-files/issues](https://github.com/OthmanAdi/planning-with-files/issues)
