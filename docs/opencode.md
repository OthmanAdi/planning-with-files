# OpenCode Support

planning-with-files treats [OpenCode](https://opencode.ai) as a first-class host. Two pieces work together:

- **The skill.** OpenCode reads `SKILL.md` natively from its own discovery paths, so the workflow instructions load through the `skill` tool like any other skill.
- **The native plugin** `opencode-planning-with-files`. It hooks OpenCode's plugin API to inject the plan on every turn, remind after writes, keep the plan in the compaction summary, hold a gated session open until the plan reports complete, and expose `pwf_init`, `pwf_status` and `pwf_check` as tools. Source: `.opencode/packages/opencode-planning-with-files/` in this repository.

Everything on this page was verified against OpenCode 1.18.21: the plugin loaded from a project config directory, the three tools appeared in the tool list, `/pwf` and `/pwf-status` in the command list, and a real session message received the framed plan as a synthetic part.

## Install

### 1. The skill

```bash
npx skills add OthmanAdi/planning-with-files --skill planning-with-files -g
```

With `-g` the installer writes `~/.agents/skills/planning-with-files/` (issue #235: earlier versions of this page named `~/.config/opencode/skills/`, which is not where the installer puts it). Without `-g` it writes `./.agents/skills/planning-with-files/` in the current project. OpenCode discovers both, because its skill search covers these paths:

| Scope | Paths OpenCode reads |
|---|---|
| Project (walking up to the git worktree) | `.opencode/skills/<name>/SKILL.md`, `.claude/skills/<name>/SKILL.md`, `.agents/skills/<name>/SKILL.md` |
| Global | `~/.config/opencode/skills/<name>/SKILL.md`, `~/.claude/skills/<name>/SKILL.md`, `~/.agents/skills/<name>/SKILL.md` |

A manual copy into `~/.config/opencode/skills/planning-with-files/` also works. The repository carries an OpenCode-shaped bundle at `.opencode/skills/planning-with-files/` (skill text, templates, scripts); its `hooks:` frontmatter is a Claude Code convention that OpenCode ignores, which is exactly why the plugin exists.

Verify:

```bash
ls ~/.agents/skills/planning-with-files/SKILL.md      # after -g
ls .agents/skills/planning-with-files/SKILL.md        # project install
```

### 2. The plugin

Add the package to `opencode.json` (project) or `~/.config/opencode/opencode.json` (global):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["opencode-planning-with-files"]
}
```

OpenCode installs npm plugins on its next start. Nothing else is required: the plugin has no configuration and reads only the planning files of the project a session works in.

### 3. The commands (optional)

Copy the two command files from the repository into `~/.config/opencode/commands/` (global) or `.opencode/commands/` (project):

```bash
curl -fsSL https://raw.githubusercontent.com/OthmanAdi/planning-with-files/master/.opencode/commands/pwf.md -o ~/.config/opencode/commands/pwf.md
curl -fsSL https://raw.githubusercontent.com/OthmanAdi/planning-with-files/master/.opencode/commands/pwf-status.md -o ~/.config/opencode/commands/pwf-status.md
```

`/pwf [--gated|--autonomous] [--template analytics] [plan name]` tells the agent to call `pwf_init` and fill in the plan; `/pwf-status` calls `pwf_status`. Both are Markdown templates in OpenCode's own command format.

### 4. Verify

Start OpenCode in a project and ask: "Call pwf_status." With no plan it answers that none exists; run `/pwf Night run` and the next message carries the injected plan block. `opencode serve` users can check `GET /experimental/tool/ids` for `pwf_init`, `pwf_status`, `pwf_check` and `GET /command` for `pwf`.

## What the plugin does

| Hook | Behavior |
|---|---|
| `chat.message` | Appends the active plan to every user message as a synthetic part: the framed head of `task_plan.md` (50 lines), the normalized tail of `progress.md` (20 lines), a pointer to `findings.md`. Resolves `PLAN_ID`, then a single named plan through `.planning/.active_plan` (BOM tolerant) or the plan directory itself, then the legacy root file; two or more named plans without `PLAN_ID` are ambiguous and get the `Multiple plans are available` notice instead of a plan (v3.20.0, matching `inject-plan.sh`), with the same slug validation and containment rules as `resolve-plan-dir.sh` and the same nested-root ambiguity rule as `inject-plan.sh` |
| `tool.execute.after` | Appends the progress reminder to the output of `write`, `edit`, `patch`, `multiedit` and `apply_patch` while a plan exists |
| `experimental.session.compacting` | Adds the plan pointer, the flush instruction, and the attestation hash to the compaction context, so the continuation resumes from the file on disk |
| `event` on `session.idle` | The completion gate in gated mode (below) |
| tools | `pwf_init` (root plan, or `.planning/YYYY-MM-DD-<slug>/` with a name; `mode: autonomous` or `gated` writes `.mode`, `.nonce`, resets the gate counter and attests the plan), `pwf_status`, `pwf_check` |

Attestation: autonomous and gated plans inject only when `.attestation` (slug) or `.plan-attestation` (root) matches the SHA-256 of `task_plan.md`; a tampered or unattested v3 plan is refused with a `context blocked` line. `PLANNING_DISABLED=1` silences every hook. `PWF_PLAN_ROOT=<absolute path>` pins the project root and fails closed when it does not resolve. When a direct child project carries its own live plan, a cwd guess is ambiguous and the plugin injects a one-line notice instead of a plan; pin with `PWF_PLAN_ROOT` or `PLAN_ID`.

Each session is resolved from its own directory (OpenCode's session `directory`), so two sessions in two projects inject two different plans, and child sessions (subagents) are never re-prompted by the gate.

## The completion gate on OpenCode

OpenCode has no Stop hook that can refuse to end a turn. It does emit `session.idle` when a session finishes, and a plugin can send a new user message through the SDK. The gate uses that: when a gated plan still has an `in_progress` phase, the plugin re-prompts the session with the same reason the Claude Code Stop gate prints, and the agent continues. Decision table, shared with `check-complete.sh --gate`:

1. `<plan-dir>/.mode` contains the `gate` token (`/pwf --gated`, `pwf_init` with `mode: gated`, or `init-session.sh --gated`).
2. An `in_progress` phase exists, counted as the per-field maximum of `**Status:** in_progress` lines and inline `[in_progress]` markers.
3. The block counter `<plan-dir>/.stop_blocks` is below `PWF_GATE_CAP` (default 20).
4. The ledger (`<plan-dir>/ledger-*.jsonl`) advanced since the previous block; a stall releases the session.

Each block increments the counter and records the ledger size, so the shell gate and the OpenCode gate share one state. This is Tier 2 in the host capability tiers (follow-up inject): the continuation is a new message, not a refusal, and a user who wants the session to stop can edit the plan, clear the `.mode` file, or set `PLANNING_DISABLED=1`.

## Working with modes

- `/pwf Night run` creates `.planning/YYYY-MM-DD-night-run/` and points `.planning/.active_plan` at it.
- `/pwf --gated Night run` also writes the v3 markers and the attestation. Editing the plan afterwards requires a re-attest (`sh scripts/attest-plan.sh` from the canonical skill, or recreate the plan); an unattested v3 plan is refused at injection by design.
- Parallel sessions: `PLAN_ID=<slug>` pins a terminal to one plan; `PWF_PLAN_ROOT=<absolute path>` pins a session whose directory is a shared parent.

## From source (contributors)

```bash
git clone https://github.com/OthmanAdi/planning-with-files.git
cd planning-with-files/.opencode/packages/opencode-planning-with-files
npm ci && npm run build && npm test
```

Opening the repository itself in OpenCode loads the plugin from source through `.opencode/plugins/planning-with-files.ts`, which re-exports the package (`.opencode/package.json` carries the `@opencode-ai/plugin` dependency OpenCode installs at startup). To load a built copy elsewhere, drop a one-line plugin file into `~/.config/opencode/plugins/` that re-exports the build: a relative import (`export { PlanningWithFiles } from "../pwf/dist/index.js"`) or a file URL (`from "file:///C:/path/to/dist/index.js"`, verified on Windows). A bare Windows path such as `C:/path/...` is not a valid import specifier and the loader skips the file silently.

## Usage with Superpowers Plugin

If you have [obra/superpowers](https://github.com/obra/superpowers) OpenCode plugin:

```
Use the use_skill tool with skill_name: "planning-with-files"
```

## Usage without a plugin

OpenCode's own `skill` tool loads the skill by name. Manually reading the file works as well:

```bash
cat ~/.agents/skills/planning-with-files/SKILL.md
```

## oh-my-opencode Compatibility

oh-my-opencode has Claude Code compatibility for skills. To use planning-with-files with oh-my-opencode:

### Step 1: Install the skill

```bash
npx skills add OthmanAdi/planning-with-files --skill planning-with-files -g
```

### Step 2: Configure oh-my-opencode

Add the skill to your `~/.config/opencode/oh-my-opencode.json` (or `.opencode/oh-my-opencode.json` for project-level):

```json
{
  "skills": {
    "sources": [
      { "path": "~/.agents/skills/planning-with-files", "recursive": false }
    ],
    "enable": ["planning-with-files"]
  },
  "disabled_skills": []
}
```

### Step 3: Verify loading

Ask the agent: "Do you have access to the planning-with-files skill? Can you create task_plan.md?"

### Troubleshooting

If the agent forgets the planning rules:

1. **Check skill is loaded**: The skill should appear in oh-my-opencode's recognized skills
2. **Explicit invocation**: Tell the agent "Use the planning-with-files skill for this task"
3. **Check for conflicts**: If using superpowers plugin alongside oh-my-opencode, choose one method:
   - Use oh-my-opencode's native skill loading (recommended)
   - OR use superpowers' `use_skill` tool, but not both

The native plugin works alongside either of them: it reads the planning files, not the skill loader.

## Known Limitations

### No per-tool-call recitation

OpenCode's `tool.execute.before` hook returns permission and argument changes, not context, so the plan reaches the model once per turn through `chat.message`. This matches the autonomous-mode injection shape on Claude Code.

### The gate is a follow-up, not a refusal

See the gate section: OpenCode cannot refuse to end a turn, so the gate re-prompts. The cap and the stall rule bound it.

### Session Catchup

Automatic recovery reads project planning files only and does not open OpenCode's session database. Optional explicit catchup supports these local stores:

- **Claude Code**: Uses `.jsonl` files at `~/.claude/projects/`
- **OpenCode**: Uses the SQLite store at `${XDG_DATA_HOME:-~/.local/share}/opencode/opencode.db` (v2.38.0+)

Run `session-catchup.py --metadata <project>` to open OpenCode's SQLite database read-only, read same-project local session records, and emit aggregate counts only without transcript bytes. Run `session-catchup.py --replay <project>` only for a deliberate bounded nonce-framed replay. If the query fails, read `task_plan.md`, `progress.md`, and `findings.md` directly. The catchup path contains no network request or upload operation. The script ships in the skill directory the installer created (`~/.agents/skills/planning-with-files/scripts/session-catchup.py` after `-g`).

## Verification

```bash
ls -la ~/.agents/skills/planning-with-files/SKILL.md
cd .opencode/packages/opencode-planning-with-files && npm test
```

## Learn More

- [Installation Guide](installation.md)
- [Quick Start](quickstart.md)
- [Workflow Diagram](workflow.md)
