# Installation Guide

Complete installation instructions for planning-with-files.

## Quick Install (Recommended)

```bash
/plugin marketplace add OthmanAdi/planning-with-files
/plugin install planning-with-files@planning-with-files
```

That's it! The skill is now active.

---

## Plugin vs Skill-Only: What's the Difference?

Before choosing an installation method, understand what you're getting:

### What is a Plugin?

A **plugin** is a distribution package that bundles multiple components:

| Component | What It Does |
|-----------|--------------|
| Skills | Auto-invoked instructions (the core planning pattern) |
| Hooks | Event handlers (reminders to update files, completion checks) |
| Commands | User-invoked shortcuts (`/planning-with-files`) |
| Scripts | Helper utilities (`init-session.sh`, `create-handoff.sh`) |

Think of it like npm vs copying a single .js file — the plugin system handles installation, updates, and integration automatically.

### What is a Skill?

A **skill** is a single `SKILL.md` file with instructions that Claude loads when relevant. It's the core content — the actual knowledge and workflow patterns.

### Comparison

| Aspect | Full Plugin | Skill-Only |
|--------|-------------|------------|
| **What you get** | Skill + hooks + commands + scripts | Just the skill instructions |
| **Installation** | `/plugin install` | Manual copy to `~/.claude/skills/` |
| **Updates** | `/plugin update` | Manual `git pull` |
| **Hooks** | ✅ PreToolUse, PostToolUse, Stop | ❌ No hooks |
| **Auto-reminders** | ✅ Reminds you to update files | ❌ No reminders |
| **Completion check** | ✅ Verifies all phases done | ❌ Manual verification |
| **Auto-invocation** | ✅ Claude auto-detects when to use | ✅ Same |
| **Core functionality** | ✅ Full 3-file pattern | ✅ Full 3-file pattern |

### Which Should You Choose?

**Choose Plugin (recommended) if:**
- You want automatic updates
- You want hooks (reminders to update files, completion verification)
- You're using Claude Code v2.1+
- Plugin installation works on your system

**Choose Skill-Only if:**
- You hit installation errors (like EXDEV on Linux — see [Troubleshooting](#linux-exdev-error))
- You want minimal footprint
- You're on an older Claude Code version
- You prefer manual control

> **Note:** Skill-only install is fully functional. You get the complete 3-file planning pattern. You just won't get hooks or automatic updates.

---

## Installation Methods

### 1. Claude Code Plugin (Recommended)

Install directly using the Claude Code CLI:

```bash
/plugin marketplace add OthmanAdi/planning-with-files
/plugin install planning-with-files@planning-with-files
```

**Advantages:**
- Automatic updates
- Proper hook integration
- Full feature support

---

### 2. Manual Installation

Clone or copy this repository into your project's `.claude/plugins/` directory:

#### Option A: Clone into plugins directory

```bash
mkdir -p .claude/plugins
git clone https://github.com/OthmanAdi/planning-with-files.git .claude/plugins/planning-with-files
```

#### Option B: Add as git submodule

```bash
git submodule add https://github.com/OthmanAdi/planning-with-files.git .claude/plugins/planning-with-files
```

#### Option C: Use --plugin-dir flag

```bash
git clone https://github.com/OthmanAdi/planning-with-files.git
claude --plugin-dir ./planning-with-files
```

---

### 3. Skill-Only Installation

If you only want the skill without the full plugin structure:

```bash
git clone https://github.com/OthmanAdi/planning-with-files.git
cp -r planning-with-files/skills/planning-with-files ~/.claude/skills/
```

This bypasses the plugin system entirely and works even if plugin installation fails.

---

### 4. One-Line Installer (Skills Only)

Extract just the skill directly:

```bash
curl -L https://github.com/OthmanAdi/planning-with-files/archive/master.tar.gz | tar -xzv --strip-components=2 "planning-with-files-master/skills/planning-with-files"
mv planning-with-files ~/.claude/skills/
```

---

## Verifying Installation

After installation, verify the skill is loaded:

1. Start a new Claude Code session
2. You should see: `[planning-with-files] Ready. Auto-activates for complex tasks, or invoke manually with /planning-with-files`
3. Or type `/planning-with-files` to manually invoke

---

## Updating

### Plugin Installation

```bash
/plugin update planning-with-files@planning-with-files
```

### Manual Installation

```bash
cd .claude/plugins/planning-with-files
git pull origin master
```

### Skills Only

```bash
cd ~/.claude/skills/planning-with-files
git pull origin master
```

---

## Uninstalling

### Plugin

```bash
/plugin uninstall planning-with-files@planning-with-files
```

### Manual

```bash
rm -rf .claude/plugins/planning-with-files
```

### Skills Only

```bash
rm -rf ~/.claude/skills/planning-with-files
```

---

## Troubleshooting

### Linux: EXDEV Error

**Error:**
```
Error: Failed to install: EXDEV: cross-device link not permitted,
rename '/home/user/.claude/plugins/cache/...' -> '/tmp/claude-plugin-temp-...'
```

**Cause:** This is a [known bug in Claude Code](https://github.com/anthropics/claude-code/issues/14799), not this skill. It happens on Linux when `/tmp` is mounted as tmpfs (common on Ubuntu 21.04+, Fedora, Arch) while `~/.claude` is on a different filesystem.

**Workaround 1: Set TMPDIR**

```bash
mkdir -p ~/.claude/tmp
TMPDIR=~/.claude/tmp claude
```

Or add to your shell profile permanently:
```bash
echo 'export TMPDIR="$HOME/.claude/tmp"' >> ~/.bashrc
source ~/.bashrc
```

**Workaround 2: Use skill-only installation**

```bash
git clone https://github.com/OthmanAdi/planning-with-files.git
cp -r planning-with-files/skills/planning-with-files ~/.claude/skills/
```

This bypasses the plugin system and avoids the bug entirely.

### Other Issues

See [docs/troubleshooting.md](troubleshooting.md) for more solutions.

---

## Requirements

- **Claude Code:** v2.1.0 or later (for full hook support)
- **Older versions:** Core functionality works, but hooks may not fire

---

## Platform-Specific Notes

### Windows

See [docs/windows.md](windows.md) for Windows-specific installation notes.

### Cursor

See [docs/cursor.md](cursor.md) for Cursor IDE installation.

---

## Need Help?

If installation fails, check [docs/troubleshooting.md](troubleshooting.md) or open an issue at [github.com/OthmanAdi/planning-with-files/issues](https://github.com/OthmanAdi/planning-with-files/issues).
