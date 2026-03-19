# FactoryAI Droid Setup

Using planning-with-files with [FactoryAI Droid](https://docs.factory.ai/).

---

## Installation

FactoryAI Droid auto-discovers skills from `.factory/skills/` directories. Two installation methods:

### Method 1: Workspace Installation (Recommended)

Share the skill with your entire team by adding it to your repository:

```bash
# In your project repository
git clone https://github.com/OthmanAdi/planning-with-files.git /tmp/planning-with-files

# Copy the Factory skill to your repo
cp -r /tmp/planning-with-files/.factory .

# Commit to share with team
git add .factory/
git commit -m "Add planning-with-files skill for Factory Droid"
git push

# Clean up
rm -rf /tmp/planning-with-files
```

Now everyone on your team using Factory Droid will have access to the skill!

### Method 2: Personal Installation

Install just for yourself:

```bash
# Clone the repo
git clone https://github.com/OthmanAdi/planning-with-files.git /tmp/planning-with-files

# Copy to your personal Factory skills folder
mkdir -p ~/.factory/skills
cp -r /tmp/planning-with-files/.factory/skills/planning-with-files ~/.factory/skills/

# Clean up
rm -rf /tmp/planning-with-files
```

### Verification

Restart your Factory Droid session, then the skill will auto-activate when you work on complex tasks.

No slash command needed - Factory Droid automatically invokes skills based on your task description!

---

## How It Works

### Auto-Activation

Factory Droid scans your task and automatically activates the skill when you:
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

Factory Droid will automatically invoke `planning-with-files` and create the three planning files.

---

## The Three Files

Once activated, the skill creates:

| File | Purpose | Location |
|------|---------|----------|
| `task_plan.md` | Phases, progress, decisions | Your project root |
| `findings.md` | Research, discoveries | Your project root |
| `progress.md` | Session log, test results | Your project root |

### Templates

The skill includes starter templates in `.factory/skills/planning-with-files/templates/`:
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

Factory Droid invokes `planning-with-files` and creates the planning files.

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

## Hooks (v2.23.0)

Factory Droid supports hooks — lifecycle events that run shell commands automatically. The SKILL.md includes hooks that:

| Hook Event | What It Does |
|------------|-------------|
| **UserPromptSubmit** | Detects active plan and reminds to read planning files |
| **PreToolUse** | Reads first 30 lines of `task_plan.md` before Write/Edit/Bash/Read operations |
| **PostToolUse** | Reminds to update `progress.md` after file changes |
| **Stop** | Runs `check-complete.sh` to verify all phases are done before stopping |

These hooks work automatically — no configuration needed beyond copying the `.factory/` directory.

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

With workspace installation (`.factory/skills/`):
- ✅ Everyone on team has the skill
- ✅ Consistent planning across projects
- ✅ Version controlled with your repo
- ✅ Changes sync via git

### Personal Skills

With personal installation (`~/.factory/skills/`):
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
3. **Restart Droid:** Factory Droid rescans skills on restart

### Files Not Created?

Check:
- Current directory is writable
- No file permission issues
- Droid has file system access

### Need Templates?

Templates are in:
- **Workspace:** `.factory/skills/planning-with-files/templates/`
- **Personal:** `~/.factory/skills/planning-with-files/templates/`

Copy them to your project root and customize.

---

## Advanced: Customization

### Modify the Skill

Edit `.factory/skills/planning-with-files/SKILL.md` to customize:
- Change trigger phrases in description
- Adjust planning patterns
- Add team-specific rules

### Add Custom Templates

Place custom templates in:
```
.factory/skills/planning-with-files/templates/
```

Factory Droid will reference them automatically.

---

## Support

- **GitHub Issues:** https://github.com/OthmanAdi/planning-with-files/issues
- **Factory Docs:** https://docs.factory.ai/cli/configuration/skills
- **Author:** [@OthmanAdi](https://github.com/OthmanAdi)

---

## See Also

- [Quick Start Guide](quickstart.md)
- [Workflow Diagram](workflow.md)
- [Manus Principles](../.factory/skills/planning-with-files/references.md)
- [Real Examples](../.factory/skills/planning-with-files/examples.md)
