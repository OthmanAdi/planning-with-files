# Installation Guide

Complete installation instructions for planning-with-files.

## Quick Install (Recommended)

```bash
/plugin marketplace add OthmanAdi/planning-with-files
/plugin install planning-with-files@planning-with-files
```

That's it! The skill is now active.

---

## What Each Install Route Actually Ships

Not every route delivers every surface. This matrix is the difference between "installed" and "fully working":

| Route | SKILL.md + scripts + templates | Slash commands (`/plan-goal`, `/plan-loop`, `/plan-attest`, `/plan-doctor`) | Hooks (plan injection, Stop check, PreCompact) |
|---|---|---|---|
| Plugin: `/plugin marketplace add` + `/plugin install` | Yes | **Yes** | **Yes** |
| `npx skills add OthmanAdi/planning-with-files` | Yes | No (`commands/` is not copied) | Frontmatter hooks; see the two silent killers below |
| ClawHub / manual skill copy to `~/.claude/skills/` | Yes | No | Frontmatter hooks; see below |

Two conditions can leave a skill-route install **silently hook-less** — everything looks installed, but no plan context is ever injected:

1. **Project trust.** A project-level install (`.claude/skills/` inside the repo) only activates after the project's trust dialog is accepted (`hasTrustDialogAccepted`). Headless or scripted sessions that never accepted trust load no project skills, and nothing prints an error.
2. **Hook registration.** SKILL.md frontmatter hooks have been observed not to register on some project-level skill installs (observed on headless Claude Code 2.1.201 during the July 2026 benchmark). The plugin route registers hooks reliably.

If hooks matter to you (they are the differentiating mechanism of this skill), install via the plugin route. Either way, verify with the doctor:

```bash
sh scripts/plan-doctor.sh    # from your project root; reports resolution, injection, latency
```

---

## Reliability Tip: Belt-and-Suspenders Trigger

Skill descriptions trigger probabilistically — in our July 2026 benchmark, unforced engagement was 60-67%, while an always-loaded rules-file instruction engaged 100% of the time. If you want the skill to fire every time a task is complex, add one line to your project's `CLAUDE.md` (or global `~/.claude/CLAUDE.md`):

```markdown
When a task needs 3+ steps or 5+ tool calls, invoke the planning-with-files skill first and keep task_plan.md current.
```

The skill description still handles discovery; the rules line makes engagement deterministic. Both together cost nothing when no complex task is running.

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

### 3. Legacy Installation (Skills Only)

If you only want the skill without the full plugin structure:

```bash
git clone https://github.com/OthmanAdi/planning-with-files.git
mkdir -p ~/.claude/skills
cp -r planning-with-files/skills/planning-with-files ~/.claude/skills/
```

---

### 4. One-Line Installer (Skills Only)

Extract just the skill directly into your current directory:

```bash
curl -L https://github.com/OthmanAdi/planning-with-files/archive/master.tar.gz | tar -xzv --strip-components=2 "planning-with-files-master/skills/planning-with-files"
```

Then move `planning-with-files/` to `~/.claude/skills/`.

---

## Installing a language variant

The workflow ships in Arabic, German, Spanish and both Chinese scripts alongside English. Each is its own skill, installed by name:

```bash
npx skills add OthmanAdi/planning-with-files --skill planning-with-files-de -g
```

Installing a translation does not install the English skill, and installing English does not pull in any translation. See [languages.md](languages.md) for the full table, the repository layout, and how the language commands behave on the plugin route.

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

## Requirements

- **Claude Code:** v2.1.0 or later (for full hook support)
- **Older versions:** Core functionality works, but hooks may not fire

---

## Platform-Specific Notes

### Windows

See [docs/windows.md](windows.md) for Windows-specific installation notes.

### Cursor

See [docs/cursor.md](cursor.md) for Cursor IDE installation.

### Codex

See [docs/codex.md](codex.md) for Codex IDE installation.

### OpenCode

See [docs/opencode.md](opencode.md) for OpenCode IDE installation.

---

## Need Help?

If installation fails, check [docs/troubleshooting.md](troubleshooting.md) or open an issue at [github.com/OthmanAdi/planning-with-files/issues](https://github.com/OthmanAdi/planning-with-files/issues).
