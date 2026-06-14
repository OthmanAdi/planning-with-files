# Codex Setup

Using planning-with-files with [OpenAI Codex](https://developers.openai.com/codex/).

---

## Overview

Codex discovers skills from `.codex/skills/` and hooks from `.codex/hooks.json` or `~/.codex/hooks.json`.

This integration includes both:

- `.codex/skills/planning-with-files/` for the skill itself
- `.codex/hooks.json` plus `.codex/hooks/` for lifecycle automation

The hook behavior reuses the same mature shell scripts as the Cursor integration, with a thin Codex adapter layer for the differences in hook protocol.

> **Important:** Codex hooks require `hooks = true` in `~/.codex/config.toml`. The older `codex_hooks = true` still works as a deprecated alias.

---

## Installation

### Method 1: Workspace Installation (Recommended)

Share the skill and hooks with your whole team by committing `.codex/` to your repository:

```bash
# In your project repository
git clone https://github.com/OthmanAdi/planning-with-files.git /tmp/planning-with-files

# Copy the Codex integration to your repo
cp -r /tmp/planning-with-files/.codex .

# Commit to share with team
git add .codex/
git commit -m "Add planning-with-files skill for Codex"
git push

# Clean up
rm -rf /tmp/planning-with-files
```

### Method 2: Personal Installation

Install just for yourself:

```bash
# Clone the repo
git clone https://github.com/OthmanAdi/planning-with-files.git /tmp/planning-with-files

# Copy the skill
mkdir -p ~/.codex/skills
cp -r /tmp/planning-with-files/.codex/skills/planning-with-files ~/.codex/skills/

# Copy the hook scripts
mkdir -p ~/.codex/hooks
cp -r /tmp/planning-with-files/.codex/hooks/* ~/.codex/hooks/

# Copy hooks.json
# If you already have ~/.codex/hooks.json, merge the planning-with-files entries manually
cp /tmp/planning-with-files/.codex/hooks.json ~/.codex/hooks.json

# Clean up
rm -rf /tmp/planning-with-files
```

> **Note:** If you already have a `~/.codex/hooks.json`, do not overwrite it blindly. Merge the `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, and `Stop` entries into your existing file.

### Enable Hooks in `config.toml`

Ensure your `~/.codex/config.toml` contains:

```toml
[features]
hooks = true
```

If you already have a `[features]` section, add `hooks = true` under it instead of creating a duplicate section. `codex_hooks = true` is still accepted as a deprecated alias for users on older configs.

### Verification

```bash
codex --version
codex features list | rg '^(hooks|codex_hooks)\s'
ls -la ~/.codex/skills/planning-with-files/SKILL.md
ls -la ~/.codex/hooks.json ~/.codex/hooks/
```

If neither `hooks` nor the deprecated alias `codex_hooks` appears in `codex features list`, upgrade Codex before troubleshooting the skill.

---

## How It Works

### Hooks

Codex reads hooks from:

1. `.codex/hooks.json` in your project root
2. `~/.codex/hooks.json` for your global install

This integration includes the Codex lifecycle hooks used by the adapter:

| Hook | What It Does |
|------|--------------|
| **SessionStart** | Runs `session-catchup.py`, then injects active plan context |
| **UserPromptSubmit** | Re-injects plan and recent progress on every user message |
| **PreToolUse** | Re-reads the first 30 lines of `task_plan.md` before Bash |
| **PostToolUse** | Reminds the agent to update `progress.md` after Bash activity |
| **PreCompact** | Reminds the agent to flush `progress.md` and `task_plan.md` before compaction |
| **Stop** | Blocks once when phases are incomplete, then falls back to a follow-up reminder |

### The Three Files

Once activated, the skill creates and maintains:

| File | Purpose | Location |
|------|---------|----------|
| `task_plan.md` | Phases, progress, decisions | Your project root |
| `findings.md` | Research, discoveries | Your project root |
| `progress.md` | Session log, test results | Your project root |

---

## Team Workflow

### Workspace Installation

With workspace installation (`.codex/` committed to your repo):

- Everyone on the team gets the same skill and hooks
- The Codex setup is version controlled with the project
- Updates ship through normal git review

### Personal Installation

With personal installation (`~/.codex/`):

- You can use the skill across all projects
- You keep your setup even if you change repositories
- Existing global hooks may need manual merging

---

## Troubleshooting

### Hooks Not Running?

1. Check that `hooks = true` (or the deprecated alias `codex_hooks = true`) is present in `~/.codex/config.toml`
2. Verify `.codex/hooks.json` or `~/.codex/hooks.json` exists
3. Restart Codex after adding or changing hooks
4. Run `codex features list | rg '^(hooks|codex_hooks)\s'`

### Already Using Other Global Hooks?

That is fine, but do not overwrite your existing `~/.codex/hooks.json`. Merge the planning-with-files entries instead.

### Seeing Duplicate Hook Messages?

Avoid installing the same planning-with-files hooks in both places at once:

- workspace `.codex/hooks.json`
- global `~/.codex/hooks.json`

If you enable both, Codex may run both sets of hooks and duplicate the reminders.

### Windows Support

OpenAI's current Codex hooks documentation says hooks are disabled on Windows. The skill files can still be installed there, but the hook automation is currently for macOS/Linux Codex environments.

---

## Learn More

- [Installation Guide](installation.md)
- [Quick Start](quickstart.md)
- [Workflow Diagram](workflow.md)

---

## Support

- **GitHub Issues:** https://github.com/OthmanAdi/planning-with-files/issues
- **OpenAI Codex Hooks Docs:** https://developers.openai.com/codex/hooks
- **OpenAI Codex Skills Docs:** https://developers.openai.com/codex/skills
