# GitHub Copilot Setup

Setting up planning-with-files for GitHub Copilot (CLI, VS Code, and Coding Agent).

---

## Prerequisites

- GitHub Copilot with hooks support enabled
- For VS Code: Copilot Chat extension v1.109.3+
- For CLI: GitHub Copilot CLI with agent mode
- For Coding Agent: Works automatically with `.github/hooks/`

---

## Installation Methods

### Method 1: Repository-Level (Recommended)
Copy both the `.github/hooks/` directory and the `skills/planning-with-files/` directory into your project:

```bash
# Copy hooks (required — Copilot hook configuration and scripts)
cp -r .github/hooks/ your-project/.github/hooks/

# Copy skills (required — templates, session-catchup script, and SKILL.md)
cp -r skills/planning-with-files/ your-project/.github/skills/planning-with-files/

# Make scripts executable (macOS/Linux)
chmod +x your-project/.github/hooks/scripts/*.sh
```

Hooks will auto-activate for all team members. This works across Copilot CLI, VS Code, and the Coding Agent.

### Method 2: Manual Setup
1. Create `.github/hooks/planning-with-files.json`
2. Copy hook scripts to `.github/hooks/scripts/`
3. Copy `skills/planning-with-files/` to `.github/skills/planning-with-files/` (templates, session-catchup script)
4. Ensure all scripts are executable (`chmod +x .github/hooks/scripts/*.sh`)

---

## What the Hooks Do

| Hook | Purpose | Behavior |
|------|---------|----------|
| `sessionStart` | Initialization | Recovers selected context from project planning files without reading agent session stores |
| `preToolUse` | No-op (contract alignment) | Emits `{}`; does not inject plan text or permission decisions |
| `postToolUse` | Update reminders | Prompts to update plan after file edits |
| `agentStop` | Completion check | Verifies if all phases are complete before stopping |

Local agent session history is not part of automatic startup. Explicit `session-catchup.py --metadata <project>` reads same-project local session records and emits aggregate counts only. Use `--replay` for bounded nonce-framed excerpts. The catchup path contains no network request or upload operation.

---

## File Structure

```
.github/
└── hooks/
    ├── planning-with-files.json    # Hook configuration
    └── scripts/
        ├── session-start.sh        # Session initialization
        ├── session-start.ps1
        ├── pre-tool-use.sh         # Empty object (no PreToolUse context API)
        ├── pre-tool-use.ps1
        ├── post-tool-use.sh        # Update reminders
        ├── post-tool-use.ps1
        ├── agent-stop.sh           # Completion verification
        └── agent-stop.ps1
```

---

## How It Works

1. **Session starts**: The hooks recover selected context from project planning files. Automatic startup does not inspect agent session stores.
2. **Before tool use**: The `pre-tool-use` hook emits `{}`. Copilot's PreToolUse command-hook contract documents permission decisions and argument rewriting, not plan-context injection, so this route leaves the host's normal permission handling unchanged. Plan text is delivered on `sessionStart` and the post-tool reminder path instead. A JSON shape alone is not proof that a model received context.
3. **After file edits**: A reminder appears after any write or edit operations. This helps ensure the plan stays updated.
4. **Agent tries to stop**: The `agent-stop` hook checks the phase status in `task_plan.md`. It prevents stopping if tasks remain.

---

## Differences from Claude Code Plugin

- **Hook Configuration**: Claude Code uses `SKILL.md` frontmatter hooks. Copilot uses the `.github/hooks/` JSON configuration file.
- **Stop Hook**: Claude's `Stop` hook corresponds to Copilot's `agentStop`.
- **Planning Files**: Both use the same core files (task_plan.md, findings.md, progress.md).
- **Protocol**: Hook scripts are adapted for Copilot's stdin JSON and stdout JSON protocol.

---

## Troubleshooting

- **Hooks not running**: Check file permissions. Ensure the `.github/hooks/` directory is committed to your repository.
- **Scripts failing**: Verify that `bash` and `python3` are available in your system PATH.
- **Windows**: PowerShell scripts (.ps1) are used automatically on Windows systems.
- **VS Code**: You might need to enable hooks in your Copilot Chat extension settings.

---

## Compatibility

These hooks target the current Copilot harness, which these clients share:

- GitHub Copilot CLI (terminal)
- VS Code Copilot Chat (agent mode)
- GitHub Copilot Coding Agent (github.com)

`sessionStart` and `postToolUse` return their context in the top-level `additionalContext` field, as the [Copilot hooks reference](https://docs.github.com/en/copilot/reference/hooks-reference) documents:

```json
{"additionalContext": "..."}
```

The legacy VS Code Local hook harness is not supported. It reads context from a nested `hookSpecificOutput` object, so it does not receive startup or post-tool context from these scripts. The VS Code [migration guide](https://code.visualstudio.com/docs/agent-customization/migrate-customizations) explains how to move hooks to the Copilot harness.
