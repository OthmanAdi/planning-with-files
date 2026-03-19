# Gemini CLI Setup

This guide explains how to install and use planning-with-files with [Gemini CLI](https://geminicli.com/).

## Prerequisites

- Gemini CLI v0.23 or later
- Agent Skills enabled in settings

## Enable Agent Skills

Agent Skills is an experimental feature. Enable it first:

```bash
# Open settings
gemini /settings

# Search for "Skills" → Toggle "Agent Skills" to true → Press Esc to save
```

Or edit `~/.gemini/settings.json`:

```json
{
  "experimental": {
    "skills": true
  }
}
```

## Installation Methods

### Method 1: Install from GitHub (Recommended)

```bash
gemini skills install https://github.com/OthmanAdi/planning-with-files --path .gemini/skills/planning-with-files
```

### Method 2: Manual Installation (User-level)

```bash
# Clone the repository
git clone https://github.com/OthmanAdi/planning-with-files.git

# Copy to Gemini skills folder
cp -r planning-with-files/.gemini/skills/planning-with-files ~/.gemini/skills/
```

### Method 3: Manual Installation (Workspace-level)

For project-specific installation:

```bash
# In your project directory
mkdir -p .gemini/skills

# Copy skill
cp -r /path/to/planning-with-files/.gemini/skills/planning-with-files .gemini/skills/
```

## Verify Installation

```bash
# List all skills
gemini skills list

# Should show:
# - planning-with-files: Implements Manus-style file-based planning...
```

Or in an interactive session:

```
/skills list
```

## Skill Discovery Tiers

Skills are loaded from three locations with this precedence:

| Tier | Location | Scope |
|------|----------|-------|
| Workspace | `.gemini/skills/` | Project-specific (highest priority) |
| User | `~/.gemini/skills/` | All projects |
| Extension | Bundled with extensions | Lowest priority |

Higher-precedence locations override lower ones when names conflict.

## Usage

### Automatic Activation

Gemini will automatically detect when to use this skill based on the task description. For complex multi-step tasks, it will prompt you:

```
Gemini wants to activate skill: planning-with-files
Purpose: Implements Manus-style file-based planning for complex tasks
Allow? [y/n]
```

### Manual Activation

You can also manually enable/disable skills:

```
/skills enable planning-with-files
/skills disable planning-with-files
/skills reload
```

## Hooks (v2.24.0)

Gemini CLI supports [hooks](https://geminicli.com/docs/hooks/) — lifecycle events that run shell scripts automatically. This skill ships with a `settings.json` that configures 4 hooks:

| Hook Event | What It Does |
|------------|-------------|
| **SessionStart** | Recovers context from previous session via `session-catchup.py` |
| **BeforeTool** | Reads first 30 lines of `task_plan.md` before write/read/shell operations |
| **AfterTool** | Reminds to update `progress.md` after file changes |
| **BeforeModel** | Injects current phase awareness before every model call (unique to Gemini!) |

### Installing Hooks

Copy the hooks configuration to your project:

```bash
# Copy settings.json (merges with existing settings)
cp /path/to/planning-with-files/.gemini/settings.json .gemini/settings.json

# Copy hook scripts
cp -r /path/to/planning-with-files/.gemini/hooks .gemini/hooks
```

Or for user-level hooks:

```bash
# Copy to user settings (applies to all projects)
cp /path/to/planning-with-files/.gemini/settings.json ~/.gemini/settings.json
cp -r /path/to/planning-with-files/.gemini/hooks ~/.gemini/hooks
```

> **Note:** If you already have a `settings.json`, merge the `"hooks"` key manually.

---

## How It Works

1. **Session Start**: Gemini loads skill names and descriptions, hooks run session recovery
2. **Task Detection**: When you describe a complex task, Gemini matches it to the skill
3. **Activation Prompt**: You approve the skill activation
4. **Instructions Loaded**: Full SKILL.md content is added to context
5. **Execution**: Gemini follows the planning workflow with hooks enforcing discipline

## Skill Structure

```
.gemini/
├── settings.json             # Hook configuration (v2.24.0)
├── hooks/                    # Hook scripts
│   ├── session-start.sh      # Session recovery
│   ├── before-tool.sh        # Plan context injection
│   ├── after-tool.sh         # Progress update reminder
│   └── before-model.sh       # Phase awareness (unique to Gemini)
└── skills/planning-with-files/
    ├── SKILL.md              # Main skill instructions
    ├── templates/
    │   ├── task_plan.md      # Phase tracking template
    │   ├── findings.md       # Research storage template
    │   └── progress.md       # Session logging template
    ├── scripts/
    │   ├── init-session.sh   # Initialize planning files
    │   ├── check-complete.sh # Verify completion
    │   ├── init-session.ps1  # Windows PowerShell version
    │   └── check-complete.ps1
    └── references/
        ├── reference.md      # Manus principles
        └── examples.md       # Real-world examples
```

## Sharing Skills with Claude Code

If you use both Gemini CLI and Claude Code, you can share skills:

```bash
# Create symlink (Linux/macOS)
ln -s ~/.claude/skills ~/.gemini/skills

# Or copy between them
cp -r ~/.claude/skills/planning-with-files ~/.gemini/skills/
```

## Troubleshooting

### Skill not appearing

1. Check skills are enabled: `gemini /settings` → Search "Skills"
2. Verify installation: `gemini skills list`
3. Reload skills: `/skills reload`

### Skill not activating

- Make sure your task description matches the skill's purpose
- Try manually enabling: `/skills enable planning-with-files`

### Path issues on Windows

Use PowerShell:

```powershell
# Copy to user skills
Copy-Item -Recurse -Path ".\.gemini\skills\planning-with-files" -Destination "$env:USERPROFILE\.gemini\skills\"
```

## Resources

- [Gemini CLI Documentation](https://geminicli.com/docs/)
- [Agent Skills Guide](https://geminicli.com/docs/cli/skills/)
- [Hooks Guide](https://geminicli.com/docs/hooks/)
- [Skills Tutorial](https://geminicli.com/docs/cli/tutorials/skills-getting-started/)
