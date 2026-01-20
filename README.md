# Planning with Files

> **Work like Manus** — the AI agent company Meta acquired for **$2 billion**.

## Thank You

To everyone who starred, forked, and shared this skill — thank you. This project blew up in less than 24 hours, and the support from the community has been incredible.

If this skill helps you work smarter, that's all I wanted.

---

A Claude Code plugin that transforms your workflow to use persistent markdown files for planning, progress tracking, and knowledge storage — the exact pattern that made Manus worth billions.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code Plugin](https://img.shields.io/badge/Claude%20Code-Plugin-blue)](https://code.claude.com/docs/en/plugins)
[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-green)](https://code.claude.com/docs/en/skills)
[![Cursor Skills](https://img.shields.io/badge/Cursor-Skills-purple)](https://docs.cursor.com/context/skills)
[![Kilocode Skills](https://img.shields.io/badge/Kilocode-Skills-orange)](https://kilo.ai/docs/agent-behavior/skills)
[![Version](https://img.shields.io/badge/version-2.5.0-brightgreen)](https://github.com/OthmanAdi/planning-with-files/releases)
[![SkillCheck Validated](https://img.shields.io/badge/SkillCheck-Validated-4c1)](https://getskillcheck.com)

## Quick Install

```bash
# 1. Install plugin
claude plugins install OthmanAdi/planning-with-files

# 2. Copy to skills folder for autocomplete (REQUIRED!)
cp -r ~/.claude/plugins/cache/planning-with-files/planning-with-files/*/skills/planning-with-files ~/.claude/skills/

# 3. Restart Claude Code
```

**Windows (PowerShell):**
```powershell
# 1. Install plugin
claude plugins install OthmanAdi/planning-with-files

# 2. Copy to skills folder for autocomplete
Copy-Item -Recurse -Path "$env:USERPROFILE\.claude\plugins\cache\planning-with-files\planning-with-files\*\skills\planning-with-files" -Destination "$env:USERPROFILE\.claude\skills\"

# 3. Restart Claude Code
```

Now type `/planning-with-files` in Claude Code!

See [docs/installation.md](docs/installation.md) for all installation methods.

## Supported IDEs

| IDE | Status | Installation Guide | Format |
|-----|--------|-------------------|--------|
| Claude Code | ✅ Full Support | [Installation](docs/installation.md) | Plugin + SKILL.md |
| Cursor | ✅ Full Support | [Cursor Setup](docs/cursor.md) | Skills |
| Kilocode | ✅ Full Support | [Kilocode Setup](docs/kilocode.md) | Skills |
| OpenCode | ✅ Full Support | [OpenCode Setup](docs/opencode.md) | Personal/Project Skill |
| Codex | ✅ Full Support | [Codex Setup](docs/codex.md) | Personal Skill |
| FactoryAI Droid | ✅ Full Support | [Factory Setup](docs/factory.md) | Workspace/Personal Skill |
| Antigravity | ✅ Full Support | [Antigravity Setup](docs/antigravity.md) | Workspace/Personal Skill |

> **Note:** If your IDE uses the legacy Rules system instead of Skills, see the [`legacy-rules-support`](https://github.com/OthmanAdi/planning-with-files/tree/legacy-rules-support) branch.

## Documentation

| Document | Description |
|----------|-------------|
| [Installation Guide](docs/installation.md) | All installation methods (plugin, manual, Cursor, Windows) |
| [Quick Start](docs/quickstart.md) | 5-step guide to using the pattern |
| [Workflow Diagram](docs/workflow.md) | Visual diagram of how files and hooks interact |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and solutions |
| [Cursor Setup](docs/cursor.md) | Cursor IDE-specific instructions |
| [Windows Setup](docs/windows.md) | Windows-specific notes |
| [Kilo Code Support](docs/kilocode.md) | Kilo Code integration guide |
| [Codex Setup](docs/codex.md) | Codex IDE installation and usage |
| [OpenCode Setup](docs/opencode.md) | OpenCode IDE installation, oh-my-opencode config |
| [FactoryAI Droid Setup](docs/factory.md) | FactoryAI Droid integration guide |
| [Antigravity Setup](docs/antigravity.md) | Antigravity IDE integration guide |

## Versions

| Version | Features | Install |
|---------|----------|---------|
| **v2.5.0** (current) | Fixed autocomplete - SKILL.md matches Anthropic format | `claude plugins install OthmanAdi/planning-with-files` |
| **v2.3.0** | Codex & OpenCode IDE support | `/plugin install planning-with-files@planning-with-files` |
| **v2.2.2** | Restored skill activation language | See [releases](https://github.com/OthmanAdi/planning-with-files/releases) |
| **v2.2.1** | Session recovery after /clear, enhanced PreToolUse hook | See [releases](https://github.com/OthmanAdi/planning-with-files/releases) |
| **v2.2.0** | Kilo Code IDE support, Windows PowerShell support, OS-aware hooks | See [releases](https://github.com/OthmanAdi/planning-with-files/releases) |
| **v2.1.2** | Fix template cache issue (Issue #18) | See [releases](https://github.com/OthmanAdi/planning-with-files/releases) |
| **v2.1.0** | Claude Code v2.1 compatible, PostToolUse hook, user-invocable | See [releases](https://github.com/OthmanAdi/planning-with-files/releases) |
| **v2.0.x** | Hooks, templates, scripts | See [releases](https://github.com/OthmanAdi/planning-with-files/releases) |
| **v1.0.0** (legacy) | Core 3-file pattern | `git clone -b legacy` |

See [CHANGELOG.md](CHANGELOG.md) for details.

## Why This Skill?

On December 29, 2025, [Meta acquired Manus for $2 billion](https://techcrunch.com/2025/12/29/meta-just-bought-manus-an-ai-startup-everyone-has-been-talking-about/). In just 8 months, Manus went from launch to $100M+ revenue. Their secret? **Context engineering**.

> "Markdown is my 'working memory' on disk. Since I process information iteratively and my active context has limits, Markdown files serve as scratch pads for notes, checkpoints for progress, building blocks for final deliverables."
> — Manus AI

## The Problem

Claude Code (and most AI agents) suffer from:

- **Volatile memory** — TodoWrite tool disappears on context reset
- **Goal drift** — After 50+ tool calls, original goals get forgotten
- **Hidden errors** — Failures aren't tracked, so the same mistakes repeat
- **Context stuffing** — Everything crammed into context instead of stored

## The Solution: 3-File Pattern

For every complex task, create THREE files:

```
task_plan.md      → Track phases and progress
findings.md       → Store research and findings
progress.md       → Session log and test results
```

### The Core Principle

```
Context Window = RAM (volatile, limited)
Filesystem = Disk (persistent, unlimited)

→ Anything important gets written to disk.
```

## Usage

Once installed, Claude will automatically:

1. **Create `task_plan.md`** before starting complex tasks
2. **Re-read plan** before major decisions (via PreToolUse hook)
3. **Remind you** to update status after file writes (via PostToolUse hook)
4. **Store findings** in `findings.md` instead of stuffing context
5. **Log errors** for future reference
6. **Verify completion** before stopping (via Stop hook)

Or invoke manually with `/planning-with-files`.

See [docs/quickstart.md](docs/quickstart.md) for the full 5-step guide.

## Session Recovery (NEW in v2.2.0)

When your context window fills up and you run `/clear`, this skill automatically recovers unsynced work from your previous session.

### Optimal Workflow

For the best experience, we recommend:

1. **Disable auto-compact** in Claude Code settings (use full context window)
2. **Start a fresh session** in your project
3. **Run `/planning-with-files`** when ready to work on a complex task
4. **Work until context fills up** (Claude will warn you)
5. **Run `/clear`** to start fresh
6. **Run `/planning-with-files`** again — it will automatically recover where you left off

### How Recovery Works

When you invoke `/planning-with-files`, the skill:

1. Checks for previous session data (stored in `~/.claude/projects/`)
2. Finds the last time planning files were updated
3. Extracts conversation that happened after (potentially lost context)
4. Shows a catchup report so you can sync planning files

This means even if context filled up before you could update your planning files, the skill will recover that context in your next session.

### Disabling Auto-Compact

To use the full context window without automatic compaction:

```bash
# In your Claude Code settings or .claude/settings.json
{
  "autoCompact": false
}
```

This lets you maximize context usage before manually clearing with `/clear`.

## Key Rules

1. **Create Plan First** — Never start without `task_plan.md`
2. **The 2-Action Rule** — Save findings after every 2 view/browser operations
3. **Log ALL Errors** — They help avoid repetition
4. **Never Repeat Failures** — Track attempts, mutate approach

## File Structure

```
planning-with-files/
├── templates/               # Root-level templates (for CLAUDE_PLUGIN_ROOT)
├── scripts/                 # Root-level scripts (for CLAUDE_PLUGIN_ROOT)
├── docs/                    # Documentation
│   ├── installation.md
│   ├── quickstart.md
│   ├── workflow.md
│   ├── troubleshooting.md
│   ├── cursor.md
│   ├── windows.md
│   ├── kilocode.md
│   ├── codex.md
│   └── opencode.md
├── planning-with-files/     # Plugin skill folder
│   ├── SKILL.md
│   ├── templates/
│   └── scripts/
├── skills/                  # Legacy skill folder
│   └── planning-with-files/
│       ├── SKILL.md
│       ├── examples.md
│       ├── reference.md
│       ├── templates/
│       └── scripts/
│           ├── init-session.sh
│           ├── check-complete.sh
│           ├── init-session.ps1   # Windows PowerShell
│           └── check-complete.ps1 # Windows PowerShell
├── .codex/                  # Codex IDE installation guide
│   └── INSTALL.md
├── .opencode/               # OpenCode IDE installation guide
│   └── INSTALL.md
├── .claude-plugin/          # Plugin manifest
├── .cursor/                 # Cursor rules
├── .kilocode/               # Kilo Code rules
│   └── rules/
│       └── planning-with-files.md
├── CHANGELOG.md
├── LICENSE
└── README.md
```

## The Manus Principles

| Principle | Implementation |
|-----------|----------------|
| Filesystem as memory | Store in files, not context |
| Attention manipulation | Re-read plan before decisions (hooks) |
| Error persistence | Log failures in plan file |
| Goal tracking | Checkboxes show progress |
| Completion verification | Stop hook checks all phases |

## When to Use

**Use this pattern for:**
- Multi-step tasks (3+ steps)
- Research tasks
- Building/creating projects
- Tasks spanning many tool calls

**Skip for:**
- Simple questions
- Single-file edits
- Quick lookups

## Kilo Code Support

This skill also supports Kilo Code AI through the `.kilocode/rules/` directory.

The [`.kilocode/rules/planning-with-files.md`](.kilocode/rules/planning-with-files.md) file contains all the planning guidelines formatted for Kilo Code's rules system, providing the same Manus-style planning workflow for Kilo Code users.

**Windows users:** The skill now includes PowerShell scripts ([`init-session.ps1`](skills/planning-with-files/scripts/init-session.ps1) and [`check-complete.ps1`](skills/planning-with-files/scripts/check-complete.ps1)) for native Windows support.

See [docs/kilocode.md](docs/kilocode.md) for detailed Kilo Code integration guide.

## Community Forks

| Fork | Author | Features |
|------|--------|----------|
| [devis](https://github.com/st01cs/devis) | [@st01cs](https://github.com/st01cs) | Interview-first workflow, `/devis:intv` and `/devis:impl` commands, guaranteed activation |
| [multi-manus-planning](https://github.com/kmichels/multi-manus-planning) | [@kmichels](https://github.com/kmichels) | Multi-project support, SessionStart git sync |

*Built something? Open an issue to get listed!*

## Acknowledgments

- **Manus AI** — For pioneering context engineering patterns
- **Anthropic** — For Claude Code, Agent Skills, and the Plugin system
- **Lance Martin** — For the detailed Manus architecture analysis
- Based on [Context Engineering for AI Agents](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License — feel free to use, modify, and distribute.

---

**Author:** [Ahmad Othman Ammar Adi](https://github.com/OthmanAdi)

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=OthmanAdi/planning-with-files&type=Date)](https://star-history.com/#OthmanAdi/planning-with-files&Date)
