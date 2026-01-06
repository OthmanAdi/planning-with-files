# Planning with Files

> **Work like Manus** — the AI agent company Meta just acquired for **$2 billion**.

A Claude Code skill that transforms your workflow to use persistent markdown files for planning, progress tracking, and knowledge storage — the exact pattern that made Manus worth billions.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-blue)](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/skills)

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=OthmanAdi/planning-with-files&type=Date)](https://star-history.com/#OthmanAdi/planning-with-files&Date)

---

## Why This Skill?

On December 29, 2025, [Meta acquired Manus for $2 billion](https://techcrunch.com/2025/12/29/meta-just-bought-manus-an-ai-startup-everyone-has-been-talking-about/). In just 8 months, Manus went from launch to $100M+ revenue. Their secret? **Context engineering**.

This skill implements Manus's core workflow pattern:

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
notes.md          → Store research and findings
[deliverable].md  → Final output
```

### The Loop

```
1. Create task_plan.md with goal and phases
2. Research → save to notes.md → update task_plan.md
3. Read notes.md → create deliverable → update task_plan.md
4. Deliver final output
```

**Key insight:** By reading `task_plan.md` before each decision, goals stay in the attention window. This is how Manus handles ~50 tool calls without losing track.

## Installation

### Claude Code

#### Option 1: Clone directly (Recommended)

```bash
# Navigate to your Claude Code skills directory
cd ~/.claude/skills  # or your custom skills path

# Clone this skill
git clone https://github.com/OthmanAdi/planning-with-files.git
```

#### Option 2: Manual installation

1. Download or copy the `planning-with-files` folder
2. Place it in your Claude Code skills directory:
   - macOS/Linux: `~/.claude/skills/`
   - Windows: `%USERPROFILE%\.claude\skills\`

#### Verify Installation

In Claude Code, the skill will automatically activate when you:
- Start complex tasks
- Mention "planning", "organize", or "track progress"
- Ask for structured work

---

### Cursor

Cursor doesn't support SKILL.md format, but this repo includes a Cursor-compatible version using the `.mdc` rules format.

#### Option 1: Copy the rules folder (Recommended)

```bash
# Navigate to your project root
cd /path/to/your/project

# Copy the .cursor/rules folder from this repo
cp -r /path/to/planning-with-files/.cursor .
```

#### Option 2: Manual installation

1. Create a `.cursor/rules/` directory in your project root
2. Copy `.cursor/rules/planning-with-files.mdc` into that directory

#### Verify Installation

In Cursor, the rule will be available for all AI models. You can:
- Reference it by typing `@planning-with-files` in your prompt
- The AI will use it automatically when you ask about planning or complex tasks

#### Rule Configuration

The `.mdc` file is configured with `alwaysApply: false`, meaning it won't bloat your context unless needed. To always include it, edit the file and set `alwaysApply: true`.

## Usage

Once installed, Claude will automatically:

1. **Create `task_plan.md`** before starting complex tasks
2. **Update progress** with checkboxes after each phase
3. **Store findings** in `notes.md` instead of stuffing context
4. **Log errors** for future reference
5. **Re-read plan** before major decisions

### Example

**You:** "Research the benefits of TypeScript and write a summary"

**Claude creates:**

```markdown
# Task Plan: TypeScript Benefits Research

## Goal
Create a research summary on TypeScript benefits.

## Phases
- [x] Phase 1: Create plan ✓
- [ ] Phase 2: Research and gather sources (CURRENT)
- [ ] Phase 3: Synthesize findings
- [ ] Phase 4: Deliver summary

## Status
**Currently in Phase 2** - Searching for sources
```

Then continues through each phase, updating the file as it goes.

## The Manus Principles

This skill implements these key context engineering principles:

| Principle | Implementation |
|-----------|----------------|
| Filesystem as memory | Store in files, not context |
| Attention manipulation | Re-read plan before decisions |
| Error persistence | Log failures in plan file |
| Goal tracking | Checkboxes show progress |
| Append-only context | Never modify history |

## File Structure

```
planning-with-files/
├── .cursor/
│   └── rules/
│       └── planning-with-files.mdc  # Cursor rules file (MDC format)
├── planning-with-files/
│   ├── SKILL.md        # Core instructions (Claude Code format)
│   ├── reference.md    # Manus principles deep dive
│   └── examples.md     # Real usage examples
└── README.md           # This file
```

### Format Support

| Editor | Format | Location |
|--------|--------|----------|
| Claude Code | `SKILL.md` | `~/.claude/skills/planning-with-files/` |
| Cursor | `.mdc` | `.cursor/rules/` in your project |

## When to Use

**Use this pattern for:**
- Multi-step tasks (3+ steps)
- Research tasks
- Building/creating projects
- Tasks spanning many tool calls
- Anything requiring organization

**Skip for:**
- Simple questions
- Single-file edits
- Quick lookups

## Acknowledgments

- **Manus AI** — For pioneering context engineering patterns that made this possible
- **Anthropic** — For Claude Code and the Agent Skills framework
- Based on [Context Engineering for AI Agents](https://manus.im/de/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License — feel free to use, modify, and distribute.

## Thank You

To everyone who starred, forked, and shared this skill — thank you. This project blew up in less than 24 hours, and the support from the community has been incredible.

If this skill helps you work smarter, that's all I wanted.

---

**Author:** [Ahmad Othman Ammar Adi](https://github.com/OthmanAdi)
