# Codex IDE Support

## Overview

planning-with-files works with Codex as a personal skill in `~/.codex/skills/`.

## Installation

Codex auto-discovers skills from `.codex/skills/` directories. Two installation methods:

### Method 1: Workspace Installation (Recommended)

Share the skill with your entire team by adding it to your repository:

```bash
# In your project repository
git clone https://github.com/OthmanAdi/planning-with-files.git /tmp/planning-with-files

# Copy the Codex skill to your repo
cp -r /tmp/planning-with-files/.codex .

# Commit to share with team
git add .codex/
git commit -m "Add planning-with-files skill for Codex"
git push

# Clean up
rm -rf /tmp/planning-with-files
```

Now everyone on your team using Codex will have access to the skill!

### Method 2: Personal Installation

Install just for yourself:

```bash
# Clone the repo
git clone https://github.com/OthmanAdi/planning-with-files.git /tmp/planning-with-files

# Copy to your personal Codex skills folder
mkdir -p ~/.codex/skills
cp -r /tmp/planning-with-files/.codex/skills/planning-with-files ~/.codex/skills/

# Clean up
rm -rf /tmp/planning-with-files
```

## Usage with Superpowers

If you have [obra/superpowers](https://github.com/obra/superpowers) installed:

```bash
~/.codex/superpowers/.codex/superpowers-codex use-skill planning-with-files
```

## Usage without Superpowers

Add to your `~/.codex/AGENTS.md`:

```markdown
## Planning with Files

<IMPORTANT>
For complex tasks (3+ steps, research, projects):
1. Read skill: `cat ~/.codex/skills/planning-with-files/SKILL.md`
2. Create task_plan.md, findings.md, progress.md in your project directory
3. Follow 3-file pattern throughout the task
</IMPORTANT>
```

## Verification

```bash
ls -la ~/.codex/skills/planning-with-files/SKILL.md
```

## Learn More

- [Installation Guide](installation.md)
- [Quick Start](quickstart.md)
- [Workflow Diagram](workflow.md)
