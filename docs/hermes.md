# Hermes Agent Setup

planning-with-files treats [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research as a first-class host: the Hermes CLI, the Hermes TUI and gateway sessions, and the Hermes Desktop app all run the same adapter. Everything on this page was verified against the Hermes v0.19.1 source and a live Hermes install on Windows; the POSIX paths follow Hermes' own defaults.

The adapter has two parts:

- `.hermes/skills/planning-with-files/` is the Hermes-facing skill bundle: `SKILL.md`, the three templates, and the scripts the workflow references.
- `.hermes/plugins/planning-with-files/` is a native Hermes plugin (Python, `plugin.yaml` plus `register(ctx)`). It provides the tools, the slash commands, the per-turn plan injection, the progress reminders, and the completion gate.

## What you get

| Surface | Provided by the plugin |
|---|---|
| Tools | `planning_with_files_init` (root plan, or `.planning/YYYY-MM-DD-<slug>/` when given a name; `mode: autonomous` or `gated` writes the v3 markers and attests the plan), `planning_with_files_status`, `planning_with_files_check_complete` |
| Slash commands | `/pwf [--autonomous\|--gated] [--template analytics] [plan name]`, `/pwf-status`, `/plan-status` |
| `pre_llm_call` | Injects the active plan at the start of every turn: the framed head of `task_plan.md`, the normalized tail of `progress.md`, and a pointer to `findings.md`. A non-empty `PLAN_ID` binds one named plan. Without it, one selectable plan may resolve through `.planning/.active_plan`, the newest named plan, or the legacy root; two or more selectable same-root plans are ambiguous and get the one-line `Multiple plans are available` notice instead of plan content. A shared pointer or timestamp never binds a Hermes session. The same slug validation, containment checks and nested-root ambiguity rule as `inject-plan.sh` apply: `PWF_PLAN_ROOT` pins only the project root, an attached session only admits that session, and neither chooses one of several same-root plans |
| `post_tool_call` | After `write_file` and `patch`, queues a reminder to update `progress.md` and the phase status; delivered with the next injection |
| `pre_verify` | The completion gate in gated mode: while an `in_progress` phase remains, the plugin asks Hermes to keep going instead of finishing the turn. Legacy and autonomous plans are never held |
| Attestation | Autonomous and gated plans inject only when `.attestation` (slug) or `.plan-attestation` (root) matches the SHA-256 of `task_plan.md`; a tampered or unattested v3 plan is refused with a `context blocked` line |
| Opt-outs and pins | `PLANNING_DISABLED=1` silences every hook for the invocation; `PWF_PLAN_ROOT=<absolute path>` pins the project root and fails closed when the pin does not resolve, but does not replace `PLAN_ID` when that root has several selectable plans; `PWF_GATE_CAP` caps consecutive gate blocks (default 20) |

The plugin is self-contained: plan resolution, injection, attestation checks, the gate and `/pwf` initialization run in Python, so nothing depends on `sh`, `bash` or PowerShell being present. The completion check tool prefers the bundled `check-complete.sh` when `sh` exists and evaluates the plan in Python otherwise.

## Install on the Hermes CLI

Two commands, both from the Hermes hub and both verified on Hermes 0.19.1.

### 1. Install the skill bundle

```bash
hermes skills install OthmanAdi/planning-with-files/.hermes/skills/planning-with-files --yes
```

Install this path, not `skills/planning-with-files`. The canonical `SKILL.md` carries Claude Code hook frontmatter (`allowed-tools`, hook scalars with command substitution, deep relative links) that Hermes' `skills-guard` scanner classifies as dangerous, and the hub refuses a dangerous verdict even with `--force`. The `.hermes` bundle scans `SAFE`. The hub delivers `SKILL.md`, `scripts/check-complete.sh`, `scripts/init-session.sh`, `scripts/session-catchup.py` and the three templates into `<HERMES_HOME>/skills/planning-with-files/`.

### 2. Install and enable the plugin

```bash
hermes plugins install OthmanAdi/planning-with-files/.hermes/plugins/planning-with-files
hermes plugins enable planning-with-files
```

`hermes plugins install` accepts the `owner/repo/path` shorthand and copies only that subdirectory into `<HERMES_HOME>/plugins/planning-with-files/`. Plugins are opt-in: the second command adds the plugin to `plugins.enabled` in `config.yaml`. Restart any running gateway (`hermes gateway restart`) or start a new `hermes chat` session.

### 3. Verify

```bash
hermes plugins list        # planning-with-files ... enabled ... 0.2.0
hermes chat
> /pwf Night run
> /pwf-status
```

`/pwf Night run` creates `.planning/2026-09-01-night-run/` with the three files and makes it the active plan. The next turn starts with the injected plan block.

### Project-local plugin (optional)

A repository that vendors the plugin under `./.hermes/plugins/planning-with-files/` can load it without a user-level install:

```bash
export HERMES_ENABLE_PROJECT_PLUGINS=1
hermes plugins enable planning-with-files   # project plugins go through the same plugins.enabled opt-in
hermes chat                                 # started from the repository root
```

Project plugin discovery reads the process working directory when Hermes starts, so this route is for the CLI started inside the repository. Hermes Desktop does not see project plugins; use the user-level install there.

## Hermes Desktop

Hermes Desktop runs the same backend (`hermes serve`) and therefore the same plugin system. Install the plugin as a user plugin with the two commands above, then restart the app. Each Desktop session pins its own project folder, and the plugin resolves the plan from that folder, so two Desktop sessions in two projects inject two different plans. `hermes desktop --cwd <project>` sets the initial project directory; Desktop Projects (`hermes project`) group sessions per workspace. `/pwf`, `/pwf-status` and the tools work in Desktop chats exactly as in the CLI.

## Windows

- The Hermes home on native Windows is `%LOCALAPPDATA%\hermes`, not `~\.hermes`. `hermes skills install` and `hermes plugins install` place files there.
- `sh` is optional. With Git for Windows on `PATH` the completion check runs the bundled `check-complete.sh`; without it the plugin evaluates the plan in Python and reports `"route": "python"`.
- The hub does not deliver the PowerShell scripts; nothing in the adapter needs them.
- Short-name paths (`C:\Users\OASRVA~1\...`) in `HERMES_HOME` make `hermes skills install` fail its subpath check. Use the long form.

## Usage

- `/pwf` creates `task_plan.md`, `findings.md` and `progress.md` in the project root. `/pwf Night run` creates an isolated `.planning/YYYY-MM-DD-night-run/` plan and points `.planning/.active_plan` at it. `/pwf --gated Night run` also writes `.mode`, `.nonce`, resets the gate counter and attests the plan, mirroring `init-session.sh --gated`.
- `/pwf-status` (alias `/plan-status`) prints the active plan id, mode, attestation state, current phase, phase counts and logged errors.
- The model can call `planning_with_files_init`, `planning_with_files_status` and `planning_with_files_check_complete` itself; the skill text tells it when.
- Load the skill text with `/planning-with-files` or `skill_view("planning-with-files")` when you want the workflow instructions in context. With the plugin enabled the skill is also reachable as `planning-with-files:planning-with-files` through `skill_view`, even when the hub install was skipped.
- Edit the plan after `/pwf --gated` or `/pwf --autonomous`? Re-attest it: `sh scripts/attest-plan.sh` from the canonical skill, or delete and re-create the plan with `/pwf`. An unattested v3 plan is refused at injection by design.

## The completion gate on Hermes

Hermes fires `pre_verify` once per turn when the agent changed files and is about to finish. The plugin answers with a continuation request when all of these hold, the same decision table `check-complete.sh --gate` applies on Claude Code:

1. `<plan-dir>/.mode` contains the `gate` token (only `/pwf --gated` or `init-session.sh --gated` write it).
2. An `in_progress` phase exists, counted as the per-field maximum of `**Status:** in_progress` lines and inline `[in_progress]` markers, exactly as the shell gate counts. An incomplete plan without an active phase never blocks.
3. The block counter `<plan-dir>/.stop_blocks` is below `PWF_GATE_CAP` (default 20).
4. The ledger (`<plan-dir>/ledger-*.jsonl`) advanced since the previous block; a stall releases the turn.

Every block increments the counter and records the ledger size, so the shell gate and the Hermes gate share one state. Limits that come from Hermes itself:

- The hook fires only on turns where the agent modified files. A turn that ends without edits is not gated.
- Hermes caps continuations per turn at `agent.max_verify_nudges` (default 3). Raise it in `config.yaml` (`agent: { max_verify_nudges: 10 }`) for long autonomous runs.
- The continuation is a follow-up message to the model, not a platform-level refusal to stop. In the host capability tiers this is Tier 2 (follow-up inject), next to Cursor, Pi and Kiro.

## Shell-hook route (advanced, CLI only)

Hermes also runs shell-script hooks declared in `config.yaml`. If you already have the canonical skill installed (for example `~/.claude/skills/planning-with-files` from the Claude Code route, or `npx skills add OthmanAdi/planning-with-files --skill planning-with-files -g`), the bridge script shipped with the plugin drives the canonical `inject-plan.sh` and `gate-stop.sh` instead of the plugin's Python injection:

```yaml
hooks:
  pre_llm_call:
    - command: "python3 ~/.hermes/plugins/planning-with-files/shell_hook.py"
      timeout: 30
  pre_verify:
    - command: "python3 ~/.hermes/plugins/planning-with-files/shell_hook.py"
      timeout: 60
```

Hermes asks for consent on first use (`hermes hooks list` shows the allowlist state; `hermes hooks test pre_llm_call` fires it against a synthetic payload). Set `PLANNING_WITH_FILES_SKILL_ROOT=/path/to/skills/planning-with-files` when the canonical skill lives somewhere unusual. Requirements and limits: `sh` must be on `PATH`; the shell hook payload carries the Hermes process working directory, so this route is correct for `hermes chat` started in the project directory and not for Desktop or gateway sessions; do not enable both the plugin hooks and the shell hooks for the same event, or the plan is injected twice.

## Migrating from Claude Code

`hermes import-agent claude-code --dry-run` previews what Hermes would import from `~/.claude`: `CLAUDE.md`, permission allowlists, MCP servers, memories and `~/.claude/skills/*` (copied to `<HERMES_HOME>/skills/claude-code/<name>/`). Credentials are never imported. Run it without `--dry-run` to apply, then install and enable the plugin as above. The planning files in your projects need no migration: `task_plan.md`, `findings.md`, `progress.md`, `.planning/` and their attestations are read as they are.

## Validation

```bash
python -m pytest tests/test_hermes_adapter.py tests/test_hermes_first_class.py -q
```

`tests/test_hermes_first_class.py` covers slug resolution, the `PWF_PLAN_ROOT` pin, the ambiguity rule, `PLANNING_DISABLED`, slug attestation, the `pre_verify` gate (block, counter, stall, cap), `/pwf` and `/pwf-status`, bundled-skill registration, the Python completion fallback and the shell-hook bridge.

## Integration Notes

### What works today

- Initialization in root and slug mode, with the v3 modes and attestation, from the tool, from `/pwf`, or from the model.
- Turn-start injection of the active plan with attestation checks, KV-cache-stable progress tail, and per-session reminder delivery.
- Progress reminders after write-like tools.
- The completion gate through `pre_verify` in gated mode.
- Status and completion checks as tools and as slash commands.
- Hermes Desktop with the same plugin.

### What is not a full equivalent of Claude Code

- No per-tool-call plan recitation. Hermes' `pre_tool_call` hook returns permission directives, not context, so the plan reaches the model once per turn. This matches the autonomous-mode injection shape; the legacy per-tool-call `head -30` has no Hermes counterpart.
- The gate is a bounded follow-up, not a hard block. See the limits above.
- No `PreCompact` equivalent. Hermes' compression fires `session:compress` on the gateway only; the next turn re-injects the plan from disk, which is the recovery model on every host.
- Markdown command files under `.hermes/commands/` are not loaded by Hermes. The plugin registers the commands; the Markdown files remain as documentation of the original intent.

### Tradeoffs

| Aspect | Detail |
|---|---|
| Install | Two hub commands plus `hermes plugins enable`; the plugin is opt-in like every Hermes plugin. |
| Planning discipline | Injection every turn plus reminders after writes keep `task_plan.md` and `progress.md` in sync across long sessions. |
| Completion enforcement | Real in gated mode, bounded by `agent.max_verify_nudges` and by the edit-only trigger. Advisory otherwise. |
| Portability | Pure Python inside Hermes' own interpreter; no shell dependency on Windows. |
| Parity | Same plan files, same attestation format, same gate state files as the Claude Code and Codex routes, so one project can be driven from several hosts in turn. |
