# Codex Setup

Using planning-with-files with [OpenAI Codex](https://developers.openai.com/codex/).

---

## Overview

Codex discovers repository skills from `.agents/skills/` and personal skills from `~/.agents/skills/`. It discovers standalone hooks from `.codex/hooks.json` or `~/.codex/hooks.json`.

This integration includes both:

- `.agents/skills/planning-with-files/` for the canonical standalone skill
- `.codex/hooks.json` plus `.codex/hooks/` for lifecycle automation
- `.codex-plugin/plugin.json` plus `hooks/codex-hooks.json` for a cache-safe plugin package

The hook behavior reuses the same shell scripts as the Cursor integration, with a thin Codex adapter layer for the differences in hook protocol. The three shell-backed context events run through `run_sh.py` on every platform so their output is serialized as event-appropriate JSON. On Windows the adapter also resolves Git Bash automatically (see [Windows Support](#windows-support)).

Hooks are enabled by default in current Codex. A user or administrator can explicitly disable them with `[features] hooks = false`. New or changed non-managed hooks must still be reviewed and trusted through `/hooks`.

---

## Installation

### Method 1: Workspace Installation (Recommended)

Share the canonical skill and standalone hooks with your team by committing `.agents/skills/planning-with-files/`, `.codex/hooks.json`, and `.codex/hooks/` to your repository:

```bash
# In your project repository
git clone https://github.com/OthmanAdi/planning-with-files.git /tmp/planning-with-files

# Copy the canonical skill
mkdir -p .agents/skills
cp -r /tmp/planning-with-files/.agents/skills/planning-with-files .agents/skills/

# Copy the standalone hook integration
mkdir -p .codex
cp /tmp/planning-with-files/.codex/hooks.json .codex/hooks.json
cp -r /tmp/planning-with-files/.codex/hooks .codex/hooks

# Commit to share with team
git add .agents/skills/planning-with-files .codex/hooks.json .codex/hooks
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

# Copy the canonical skill
mkdir -p ~/.agents/skills
cp -r /tmp/planning-with-files/.agents/skills/planning-with-files ~/.agents/skills/

# Copy the hook scripts
mkdir -p ~/.codex/hooks
cp -r /tmp/planning-with-files/.codex/hooks/* ~/.codex/hooks/

# Copy hooks.json
# If you already have ~/.codex/hooks.json, merge the planning-with-files entries manually
cp /tmp/planning-with-files/.codex/hooks.json ~/.codex/hooks.json

# Clean up
rm -rf /tmp/planning-with-files
```

> **Note:** If you already have a `~/.codex/hooks.json`, do not overwrite it blindly. Merge all seven entries: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PreCompact`, and `Stop`.

### Plugin Package

The repository also ships a Codex plugin package. Its manifest selects `hooks/codex-hooks.json`, so cached plugin commands resolve only through `${PLUGIN_ROOT}`. Plugin mode and standalone `.codex/hooks.json` mode are alternatives. Do not enable both for the same installation because Codex runs every matching hook from every active source.

### Verification

```bash
codex --version
ls -la ~/.agents/skills/planning-with-files/SKILL.md
ls -la ~/.codex/hooks.json ~/.codex/hooks/
```

Use `/hooks` to review the source, matcher, and resolved command for each loaded hook.

---

## How It Works

### Hooks

Codex reads hooks from:

1. `.codex/hooks.json` in your project root
2. `~/.codex/hooks.json` for your global install

This integration includes the Codex lifecycle hooks used by the adapter:

| Hook | What It Does |
|------|--------------|
| **SessionStart** | Reads project planning state and injects selected active-plan context; it does not inspect Codex session stores |
| **UserPromptSubmit** | Re-injects plan and recent progress on every user message |
| **PreToolUse** | Refreshes plan context before Bash and direct edit paths |
| **PermissionRequest** | Adds bounded plan context when Codex is about to request approval |
| **PostToolUse** | Reminds the agent to update `progress.md` after Bash or direct edits |
| **PreCompact** | Reminds the agent to flush `progress.md` and `task_plan.md` before compaction |
| **Stop** | Continues once when every opt-in gated-mode condition passes; otherwise emits advisory status and allows the stop |

Local Codex session history is not part of the automatic hook path. Explicit `session-catchup.py --metadata <project>` reads same-project local session records and emits aggregate counts only. Use `--replay` for bounded nonce-framed excerpts. The catchup path contains no network request or upload operation.

### The Three Files

Once activated, the skill creates and maintains:

| File | Purpose | Location |
|------|---------|----------|
| `task_plan.md` | Phases, progress, decisions | Your project root |
| `findings.md` | Research, discoveries | Your project root |
| `progress.md` | Session log, test results | Your project root |

### Opting out for one-shot runs (CI, `codex exec`)

A one-shot session that shares a working directory with an active plan gets the
plan context injected even though it never opted in: a CI review bot, a
read-only research agent, or a nested orchestrator can end up "reconciling the
plan" instead of doing its own job, and may mutate `task_plan.md` and
`progress.md` that belong to another session (issue #195).

Set `PLANNING_DISABLED=1` to disable all planning-with-files hooks for that
invocation only:

```bash
PLANNING_DISABLED=1 codex exec -o review.md '$code-review review this branch'
PLANNING_DISABLED=1 codex exec -C <repo> -s read-only '<research prompt>'
```

With the variable set, every hook (SessionStart, UserPromptSubmit, PreToolUse,
PermissionRequest, PostToolUse, PreCompact, Stop) exits before reading the plan: no context
injection, no follow-up messages, no plan-file writes. PreToolUse exits silently
without adding planning context or a permission decision; Codex's normal permission
handling remains unchanged. Interactive sessions in
the same directory are unaffected. The same variable is honored by the
canonical Claude Code dispatchers (`inject-plan.sh`, `gate-stop.sh`,
`check-complete.sh`/`.ps1`), so it works for CI automation on any platform
whose hooks route through those scripts.

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

1. Check that neither user nor managed configuration explicitly sets `[features] hooks = false`.
2. Verify `.codex/hooks.json`, `~/.codex/hooks.json`, or an enabled plugin descriptor exists.
3. Restart Codex after adding or changing hooks.
4. Review and trust new or changed definitions through `/hooks`.

### Already Using Other Global Hooks?

That is fine, but do not overwrite your existing `~/.codex/hooks.json`. Merge the planning-with-files entries instead.

### Seeing Duplicate Hook Messages?

Avoid installing the same planning-with-files hooks in both places at once:

- workspace `.codex/hooks.json`
- global `~/.codex/hooks.json`
- the planning-with-files Codex plugin

If you enable both, Codex may run both sets of hooks and duplicate the reminders.

### macOS and Linux requirements

The POSIX hook commands require `python3` and `sh` on PATH. The other Codex Python hooks already use `python3`, so a working Python 3 installation is required for the full integration.

Upgrading from v3.10.0 or earlier changes three command definitions in `.codex/hooks.json`. Review and trust the updated definitions with `/hooks` before expecting `SessionStart`, `UserPromptSubmit`, or `PreCompact` to run.

### Windows Support

Hooks run on Windows. Codex reads a per-hook `commandWindows` override from `.codex/hooks.json` on Windows and the POSIX `command` everywhere else. The three shell-backed context events use `run_sh.py` on every platform so Codex receives event-appropriate JSON.

On Windows every hook routes through `.codex\hooks\pwf-hook.cmd`, which finds a real Python (`py -3`, falling back to `python`) and never the Microsoft Store `python3` alias. Plugin installs use a quote-free PowerShell entry command before that launcher so cache paths containing spaces work with Codex's Windows hook runner. The four Python hooks run their `.py` entry point directly. The three shell hooks (SessionStart, UserPromptSubmit, PreCompact) route through `run_sh.py`, which locates the Git for Windows `sh.exe` and runs the same shell scripts the macOS/Linux hooks use.

Requirements on Windows:

- Hooks must not be explicitly disabled in user or managed configuration.
- Python reachable through the `py` launcher (installed by the python.org installer) or on PATH as `python`. If you only have `python`, the launcher falls back to it automatically. The Microsoft Store `python3` alias is skipped on purpose.
- Git for Windows installed, for the three shell-backed hooks. The launcher finds `sh.exe` even when Git's `usr\bin` is not on your PATH, which is the default install layout. Without Git for Windows those three hooks stay silent and the four Python hooks still work.

Use the workspace install (Method 1) on Windows: the `commandWindows` entries use relative `.codex\...` paths resolved against your project directory. A global `~/.codex` install needs absolute paths in `commandWindows`.

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

### Multiple named plans in one project

As of v3.17.1, a project with more than one live named plan requires `PLAN_ID` for each Codex session, whether or not `.planning/sessions/` exists. Set the pin in the environment that launches the host. Exporting it inside a tool subprocess cannot change an already-running host. A shared `.planning/.active_plan` pointer cannot select a plan for that session.

When no pin is available, UserPromptSubmit explains the ambiguity and injects no plan. Per-tool and PreCompact hooks remain quiet, and Stop allows the session to end without evaluating a guessed plan. Explicit pins, single named plans and legacy root plans remain supported.
