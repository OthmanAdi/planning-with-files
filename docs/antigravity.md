# Antigravity IDE Setup

Using planning-with-files with [Google Antigravity](https://antigravity.google/).

---

## Installation

Antigravity auto-discovers skills from `.agent/skills/` directories. Two installation methods:

### Method 1: Workspace Installation (Recommended)

Share the skill with your entire team by adding it to your repository:

```bash
# In your project repository
git clone https://github.com/OthmanAdi/planning-with-files.git /tmp/planning-with-files

# Copy the planning-with-files skill to your repo
mkdir -p .agent/skills
cp -r /tmp/planning-with-files/skills/planning-with-files .agent/skills/

# Commit to share with team
git add .agent/
git commit -m "Add planning-with-files skill for Antigravity"
git push

# Clean up
rm -rf /tmp/planning-with-files
```

Now everyone on your team using Antigravity will have access to the skill!

### Method 2: Personal Installation

Install just for yourself:

```bash
# Clone the repo
git clone https://github.com/OthmanAdi/planning-with-files.git /tmp/planning-with-files

# Copy to your personal Antigravity skills folder
mkdir -p ~/.gemini/antigravity/skills
cp -r /tmp/planning-with-files/skills/planning-with-files ~/.gemini/antigravity/skills/

# Clean up
rm -rf /tmp/planning-with-files
```

### Verification

Restart your Antigravity session, then the skill will auto-activate when you work on complex tasks.

No slash command needed - Antigravity automatically invokes skills based on your task description!

---

## How It Works

### Auto-Activation

Antigravity scans your task and automatically activates the skill when you:
- Mention "complex task" or "multi-step project"
- Request planning or organization
- Start research tasks
- Work on projects requiring >5 steps

### Trigger Phrases

Increase auto-activation likelihood by using these phrases:
- "Create a task plan for..."
- "This is a multi-step project..."
- "I need planning for..."
- "Help me organize this complex task..."

### Example Request

```
I need to build a REST API with authentication,
database integration, and comprehensive testing.
This is a complex multi-step project that will
require careful planning.
```

Antigravity will automatically invoke `planning-with-files` and create the three planning files.

---

## The Three Files

Once activated, the skill creates:

| File | Purpose | Location |
|------|---------|----------|
| `task_plan.md` | Phases, progress, decisions | Your project root |
| `findings.md` | Research, discoveries | Your project root |
| `progress.md` | Session log, test results | Your project root |

### Templates

The skill includes starter templates in `.agent/skills/planning-with-files/templates/`:
- `task_plan.md` — Phase tracking template
- `findings.md` — Research storage template
- `progress.md` — Session logging template

---

## Usage Pattern

### 1. Start Complex Task

Describe your task with complexity indicators:

```
I'm building a user authentication system.
This is a multi-phase project requiring database
setup, API endpoints, testing, and documentation.
```

### 2. Skill Auto-Activates

Antigravity invokes `planning-with-files` and creates the planning files.

### 3. Work Through Phases

The AI will:
- ✅ Create `task_plan.md` with phases
- ✅ Update progress as work completes
- ✅ Store research in `findings.md`
- ✅ Log actions in `progress.md`
- ✅ Re-read plans before major decisions

### 4. Track Everything

All important information gets written to disk, not lost in context window.

---

## Skill Features

### The 3-Strike Error Protocol

When errors occur, the AI:
1. **Attempt 1:** Diagnose and fix
2. **Attempt 2:** Try alternative approach
3. **Attempt 3:** Broader rethink
4. **After 3 failures:** Escalate to you

### The 2-Action Rule

After every 2 search/view operations, findings are saved to `findings.md`.

Prevents losing visual/multimodal information.

### Read Before Decide

Before major decisions, the AI re-reads planning files to refresh goals.

Prevents goal drift in long sessions.

---

## Team Workflow

### Workspace Skills (Recommended)

With workspace installation (`.agent/skills/`):
- ✅ Everyone on team has the skill
- ✅ Consistent planning across projects
- ✅ Version controlled with your repo
- ✅ Changes sync via git

### Personal Skills

With personal installation (`~/.gemini/antigravity/skills/`):
- ✅ Use across all your projects
- ✅ Keep it even if you switch teams
- ❌ Not shared with teammates

---

## Why This Works

This pattern is why Manus AI (acquired by Meta for $2 billion) succeeded:

> "Markdown is my 'working memory' on disk. Since I process information iteratively and my active context has limits, Markdown files serve as scratch pads for notes, checkpoints for progress, building blocks for final deliverables."
> — Manus AI

**Key insight:** Context window = RAM (volatile). Filesystem = Disk (persistent).

Write important information to disk, not context.

---

## Troubleshooting

### Skill Not Activating?

1. **Add trigger phrases:** Use "complex task", "multi-step", "planning" in your request
2. **Be explicit:** Mention number of phases or complexity
3. **Restart Antigravity:** Agent rescans skills on restart

### Files Not Created?

Check:
- Current directory is writable
- No file permission issues
- Agent has file system access

### Need Templates?

Check:
- **Workspace:** `.agent/skills/planning-with-files/templates/`
- **Personal:** `~/.gemini/antigravity/skills/planning-with-files/templates/`

Copy them to your project root and customize.

---

## Advanced: Customization

### Modify the Skill

Edit `.agent/skills/planning-with-files/SKILL.md` to customize:
- Change trigger phrases in description
- Adjust planning patterns
- Add team-specific rules

### Add Custom Templates

Place custom templates in:
```
.agent/skills/planning-with-files/templates/
```

Antigravity will reference them automatically.

---

## Agent Skills Standard

This skill follows the [Agent Skills Specification](https://agentskills.io/specification), an open standard for AI coding assistants.

The same skill format works across:
- Google Antigravity
- Claude Code
- Cursor
- And other Agent Skills-compatible IDEs

---

## Support

- **GitHub Issues:** https://github.com/OthmanAdi/planning-with-files/issues
- **Antigravity Docs:** https://antigravity.google/docs/skills
- **Agent Skills Spec:** https://agentskills.io/specification
- **Author:** [@OthmanAdi](https://github.com/OthmanAdi)

---

## See Also

- [Quick Start Guide](quickstart.md)
- [Workflow Diagram](workflow.md)
- [Manus Principles](../skills/planning-with-files/reference.md)
- [Real Examples](../skills/planning-with-files/examples.md)
