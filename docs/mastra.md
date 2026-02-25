# Mastra Code Setup

Using planning-with-files with [Mastra Code](https://code.mastra.ai/).

---

## Overview

Mastra Code auto-discovers skills from `.mastracode/skills/` directories. It also has built-in Claude Code compatibility, so it reads `.claude/skills/` too — but the dedicated `.mastracode/` integration gives you native hooks support.

## Installation

### Method 1: Workspace Installation (Recommended)

Share the skill with your entire team by adding it to your repository:

```bash
# In your project repository
git clone https://github.com/OthmanAdi/planning-with-files.git /tmp/planning-with-files

# Copy the Mastra Code skill to your repo
cp -r /tmp/planning-with-files/.mastracode .

# Commit to share with team
git add .mastracode/
git commit -m "Add planning-with-files skill for Mastra Code"
git push

# Clean up
rm -rf /tmp/planning-with-files
```

Now everyone on your team using Mastra Code will have access to the skill.

### Method 2: Personal Installation

Install just for yourself:

```bash
# Clone the repo
git clone https://github.com/OthmanAdi/planning-with-files.git /tmp/planning-with-files

# Copy to your personal Mastra Code skills folder
mkdir -p ~/.mastracode/skills
cp -r /tmp/planning-with-files/.mastracode/skills/planning-with-files ~/.mastracode/skills/

# Clean up
rm -rf /tmp/planning-with-files
```

### Verification

```bash
ls -la ~/.mastracode/skills/planning-with-files/SKILL.md
```

Restart your Mastra Code session. The skill auto-activates when you work on complex tasks.

---

## How It Works

### Hooks (Native Support)

Mastra Code supports the same hook system as Claude Code. This integration includes:

| Hook | Trigger | What It Does |
|------|---------|--------------|
| **PreToolUse** | Before Write, Edit, Bash, Read, Glob, Grep | Reads first 30 lines of `task_plan.md` — keeps goals in attention |
| **PostToolUse** | After Write, Edit | Reminds you to update plan status |
| **Stop** | When agent finishes | Runs completion check script |

### Auto-Activation

The skill activates when you:
- Mention "complex task" or "multi-step project"
- Ask to "plan out" or "break down" work
- Request help organizing or tracking progress
- Start research tasks requiring >5 tool calls

### The Three Files

Once activated, the skill creates:

| File | Purpose | Location |
|------|---------|----------|
| `task_plan.md` | Phases, progress, decisions | Your project root |
| `findings.md` | Research, discoveries | Your project root |
| `progress.md` | Session log, test results | Your project root |

---

## Claude Code Compatibility

Mastra Code reads from `.claude/skills/` as a fallback. If you already have planning-with-files installed for Claude Code, it will work — but the dedicated `.mastracode/` installation gives you:

- Native hooks integration (PreToolUse, PostToolUse, Stop)
- Correct script path resolution
- No path conflicts with Claude Code plugin root

---

## Session Recovery

When your context fills up and you run `/clear`, the skill can recover your previous session.

Run manually:

```bash
# Linux/macOS
python3 ~/.mastracode/skills/planning-with-files/scripts/session-catchup.py "$(pwd)"
```

```powershell
# Windows PowerShell
python "$env:USERPROFILE\.mastracode\skills\planning-with-files\scripts\session-catchup.py" (Get-Location)
```

---

## Team Workflow

### Workspace Skills (Recommended)

With workspace installation (`.mastracode/skills/`):
- Everyone on team has the skill
- Consistent planning across projects
- Version controlled with your repo
- Changes sync via git

### Personal Skills

With personal installation (`~/.mastracode/skills/`):
- Use across all your projects
- Keep it even if you switch teams
- Not shared with teammates

---

## Troubleshooting

### Skill Not Activating?

1. Verify the file exists: `ls ~/.mastracode/skills/planning-with-files/SKILL.md`
2. Restart Mastra Code — skills are scanned on startup
3. Use trigger phrases: "plan out", "break down", "organize", "track progress"

### Hooks Not Running?

Check `.mastracode/hooks.json` for conflicts. The skill's hooks are defined in SKILL.md frontmatter and should work automatically.

### Already Using Claude Code?

No conflict. Mastra Code checks `.mastracode/skills/` first, then falls back to `.claude/skills/`. You can have both installed.

---

## Support

- **GitHub Issues:** https://github.com/OthmanAdi/planning-with-files/issues
- **Mastra Code Docs:** https://code.mastra.ai/configuration
- **Author:** [@OthmanAdi](https://github.com/OthmanAdi)

---

## See Also

- [Quick Start Guide](quickstart.md)
- [Workflow Diagram](workflow.md)
- [Manus Principles](../skills/planning-with-files/reference.md)
- [Real Examples](../skills/planning-with-files/examples.md)
