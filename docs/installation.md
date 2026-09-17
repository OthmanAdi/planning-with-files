# Installation Guide

Complete installation instructions for planning-with-files.

## Quick Install (Recommended)

```bash
/plugin marketplace add OthmanAdi/planning-with-files
/plugin install planning-with-files@planning-with-files
```

The plugin is now installed. When a project has no active plan, its startup hook is intentionally silent.

---

## What Each Install Route Actually Ships

Not every route delivers every surface. This matrix is the difference between "installed" and "fully working":

| Route | SKILL.md + scripts + templates | Slash commands (`/plan-goal`, `/plan-loop`, `/plan-attest`, `/plan-doctor`) | Hooks (plan injection, Stop check, PreCompact) |
|---|---|---|---|
| Plugin: `/plugin marketplace add` + `/plugin install` | Yes | **Yes** | **Yes**, through plugin-level lifecycle hooks, including quiet `SessionStart` recovery |
| `npx skills add OthmanAdi/planning-with-files` | Yes | No (`commands/` is not copied) | Activation-scoped frontmatter hooks after the skill is invoked; no `SessionStart` |
| ClawHub / manual skill copy to `~/.claude/skills/` | Yes | No | Activation-scoped frontmatter hooks after the skill is invoked; no `SessionStart` |
| OpenCode: `npx skills add OthmanAdi/planning-with-files --skill planning-with-files -g` (lands in `~/.agents/skills/`, which OpenCode reads) + `"plugin": ["opencode-planning-with-files"]` in `opencode.json` | Yes | `/pwf`, `/pwf-status` after copying the two command files from `.opencode/commands/` | **Yes**, native plugin hooks `chat.message`, `tool.execute.after`, `experimental.session.compacting`, `session.idle` gate; see [docs/opencode.md](opencode.md) |
| Hermes Agent: `hermes skills install OthmanAdi/planning-with-files/.hermes/skills/planning-with-files` + `hermes plugins install OthmanAdi/planning-with-files/.hermes/plugins/planning-with-files` | Yes (the `.hermes` bundle; the canonical path is refused by Hermes' skills-guard scanner) | Hermes commands `/pwf`, `/pwf-status`, `/plan-status` | **Yes**, native plugin hooks `pre_llm_call`, `post_tool_call`, `pre_verify` (gate); see [docs/hermes.md](hermes.md) |
| DeepSeek Harness: `npx skills add OthmanAdi/planning-with-files --skill planning-with-files -g` (lands in `~/.agents/skills/`, which dsh reads) + `dsh plugin --profile web add dsh-planning-with-files` | Yes | `/pwf`, `/pwf-status`, registered by the plugin | **Yes**, native plugin listeners `agent/pre-step`, `tools/post-execute`, `agent/session-start` (compaction), `agent/turn-stopping` gate; see [docs/deepseek-harness.md](deepseek-harness.md) |

Two conditions can leave a standalone skill route without active hooks:

1. **Project trust.** A project-level install (`.claude/skills/` inside the repo) only activates after the project's trust dialog is accepted (`hasTrustDialogAccepted`). Headless or scripted sessions that never accepted trust load no project skills, and nothing prints an error.
2. **Skill invocation.** Standalone `SKILL.md` hooks are activation-scoped. They register after Claude invokes the skill for that session. The plugin route registers its lifecycle descriptor at startup.

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

### 2. Local Plugin Development

For a local checkout, use Claude Code's supported session-only plugin path:

```bash
git clone https://github.com/OthmanAdi/planning-with-files.git
claude --plugin-dir ./planning-with-files
```

---

### 3. Standalone Installation (Skill Only)

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

After installation, verify the intended route:

1. For a plugin install, run `claude plugin list`, then inspect the plugin in `/plugin` or `/hooks`.
2. Start a new Claude Code session in a project with an active plan and confirm that planning context is restored.
3. In a project without an active plan, expect no startup message.
4. For a standalone skill install, invoke `/planning-with-files`; its hooks are activation-scoped to that session.

---

## Updating

### Plugin Installation

```bash
/plugin update planning-with-files@planning-with-files
```

### Local Plugin Checkout

Update the checkout you pass to `claude --plugin-dir`, then start a new session.

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

### Skills Only

```bash
rm -rf ~/.claude/skills/planning-with-files
```

---

## Requirements

- **Claude Code plugin lifecycle:** tested against the current stable release. No older minimum is claimed without a compatibility receipt.
- **Standalone skill:** core file-based planning remains available, but hooks register only after the skill is invoked.

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

### DeepSeek Harness

See [docs/deepseek-harness.md](deepseek-harness.md) for DeepSeek Harness (`dsh`) installation.

---

## Need Help?

If installation fails, check [docs/troubleshooting.md](troubleshooting.md) or open an issue at [github.com/OthmanAdi/planning-with-files/issues](https://github.com/OthmanAdi/planning-with-files/issues).
