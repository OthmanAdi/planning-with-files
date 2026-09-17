# DeepSeek Harness Support

planning-with-files treats [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) (`dsh`) as a first-class host. Two pieces work together:

- **The skill.** dsh discovers `SKILL.md` files in `<project>/.dsh/skills`, `<project>/.agents/skills`, `~/.dsh/skills` and `~/.agents/skills`, so the workflow instructions load like any other skill, and `/planning-with-files` typed in the composer invokes it.
- **The native plugin** `dsh-planning-with-files`, a Cordis plugin bundle. It subscribes to dsh's lifecycle events to inject the plan on every prompt, remind after writes, re-inject the plan after compaction and hold a gated turn open until the plan reports complete, and it registers `/pwf`, `/pwf-status` and the `pwf_init`, `pwf_status`, `pwf_check` tools. Source: `.dsh/packages/dsh-planning-with-files/` in this repository.

The plugin is built and tested against the published `@deepseek-ai/dsh` 0.1.5-rc.2 and the `@deepseek-ai/*` 0.1.5-rc.2 libraries it installs (Cordis 4.0.2).

## What you get

| Lifecycle point | Behavior |
|---|---|
| `agent/pre-step` | Appends the active plan as one plugin-sourced message to the step that carries your prompt: the framed head of `task_plan.md` (50 lines), the normalized tail of `progress.md` (20 lines), a pointer to `findings.md`. Steps that carry only tool results, steering or the plugin's own messages get nothing, so the plan arrives once per prompt and never twice after a compaction or `/pwf` injection |
| `tools/post-execute` | Attaches the progress reminder as additional context to a successful `write`, `edit` or `str_replace_editor` call with a `create`, `str_replace` or `insert` command, while a plan exists |
| `agent/session-start` with source `compact` | Injects the compaction note (plan pointer, flush instruction, attestation hash) followed by the framed plan, so the continuation resumes at the current phase. `startup`, `resume` and `clear` inject nothing here: the next prompt carries the plan |
| `agent/turn-stopping` | The completion gate in gated mode (below) |

| Command | Behavior |
|---|---|
| `/pwf [--autonomous\|--gated] [--template analytics] [plan name]` | Creates `task_plan.md`, `findings.md` and `progress.md`. A name creates `.planning/YYYY-MM-DD-<slug>/` and points `.planning/.active_plan` at it; `--gated` or `--autonomous` writes the v3 markers and attests the plan. The framed plan is queued for the next model request. The handler runs inside dsh without a model round trip and answers with the created files, the plan id and the mode |
| `/pwf-status` | Plan id, mode, attestation state, current phase, phase counts, and any nested plans below the root |

| Tool | Behavior |
|---|---|
| `pwf_init` | Arguments `name`, `mode` (`autonomous` or `gated`), `template` (`default` or `analytics`): the `/pwf` contract for the model, returns a JSON document |
| `pwf_status` | JSON summary of the active plan (id, mode, attestation, current phase, phase counts) |
| `pwf_check` | JSON: whether every phase of the active plan is complete |

Commands and tools resolve the plan from the calling agent's session workspace, exactly like the listeners. `PLANNING_DISABLED=1` and a broken `PWF_PLAN_ROOT` pin answer with an explicit error instead of a silent fallback.

## Install

### 1. The skill

```bash
npx skills add OthmanAdi/planning-with-files --skill planning-with-files -g
```

With `-g` the installer writes `~/.agents/skills/planning-with-files/`, which dsh reads with zero configuration. Without `-g` it writes `./.agents/skills/planning-with-files/` in the current project, which dsh reads as well. dsh honours the frontmatter keys `name`, `description`, `whenToUse`, `metadata`, `disable-model-invocation` and `user-invocable`; the `hooks:` block is a Claude Code convention that dsh ignores, which is exactly why the plugin exists.

Verify:

```bash
ls ~/.agents/skills/planning-with-files/SKILL.md
```

### 2. The plugin

```bash
dsh plugin --profile web add dsh-planning-with-files
```

Restart `dsh web`. `dsh plugin` forwards to pnpm inside the profile directory (`$DSH_HOME/profiles/web`, `~/.dsh/profiles/web` by default), so pnpm must be on PATH. The package ships built code, so the install asks for no build permission. The same command with `--profile headless`, `--profile sdk` or `--profile acp` adds the plugin to those profiles; restart the matching app afterwards.

Verify without booting:

```bash
dsh --profile web --dump-config
```

The dump prints a `# == dsh-planning-with-files` layer with the `planning-with-files` row.

Configuration is optional. To keep injection and switch the completion gate off, override the row's `config` in the profile's `cordis.patch.yml` (`$DSH_HOME/profiles/web/cordis.patch.yml`). A patch replaces the row's whole `config` value, so restate both keys:

```yaml
- id: planning-with-files
  config:
    enabled: true
    gate: false
```

### 3. First run

Start `dsh web` in a project and type:

```
/pwf My task --gated
```

The command answers with the created files, the plan id (`YYYY-MM-DD-my-task`) and the mode; the next message you send carries the framed plan. `/pwf-status` reports the plan. Asking the model to call `pwf_status` exercises the tool path.

## How plan selection works

Every event resolves the plan again from the session's working directory (the `cwd` on the session header), in this order:

1. `PLAN_ID=<slug>` in the dsh process environment binds one plan. A slug that names no plan ends resolution: nothing is injected, and neither the pointer nor the root plan is used instead.
2. `.planning/.active_plan` (BOM tolerant) names the active slug.
3. The newest `.planning/<slug>/task_plan.md` by modification time.
4. The legacy `task_plan.md` in the project root.

`PWF_PLAN_ROOT=<absolute path>` pins the project root; a pin that does not resolve to a real directory fails closed. When a direct child project carries its own live plan, a cwd guess is ambiguous: the plugin injects a one-line notice instead of a plan until you pin the session with `PWF_PLAN_ROOT` or `PLAN_ID`. `PLANNING_DISABLED=1` silences every listener, command and tool.

Autonomous and gated plans inject only when `.attestation` (slug plan) or `.plan-attestation` (root plan) matches the SHA-256 of `task_plan.md`; a tampered or unattested v3 plan is refused with a `context blocked` line. `/pwf --gated` and `pwf_init` with `mode: gated` attest the plan they create. After editing the plan, re-attest it (`sh scripts/attest-plan.sh` from the installed skill) or recreate it.

The environment variables are read from the `dsh` process, because the plugin runs inside it: set them before starting `dsh web`, not in a shell inside the session.

## The completion gate

dsh cannot refuse to end a turn, but `agent/turn-stopping` is awaited before the turn closes, and a listener that steers the agent makes the machine run another step. The gate uses that: when a gated plan still has an `in_progress` phase, the plugin steers the agent with the same reason the Claude Code Stop gate prints, and the agent continues. Decision table, shared with `check-complete.sh --gate` and the OpenCode plugin:

1. `<plan-dir>/.mode` contains the `gate` token (`/pwf --gated`, `pwf_init` with `mode: gated`, or `init-session.sh --gated`).
2. An `in_progress` phase exists, counted as the per-field maximum of `**Status:** in_progress` lines and inline `[in_progress]` markers.
3. The block counter `<plan-dir>/.stop_blocks` is below `PWF_GATE_CAP` (default 20).
4. The ledger (`<plan-dir>/ledger-*.jsonl`) advanced since the previous block; a stall releases the turn.

Each block increments the counter and records the ledger size, so the shell gate and the dsh gate share one state. Subagent children are never held: the gate applies to the delegating agent only. This is Tier 2 in the host capability tiers (follow-up inject): the continuation is a new step, not a refusal, and a user who wants the turn to stop can edit the plan, clear the `.mode` file, set `PLANNING_DISABLED=1`, or set `gate: false` on the row.

## What is not covered

- **No per-tool-call recitation.** dsh's `tools/pre-execute` decision carries no context field, so the plan reaches the model once per prompt through `agent/pre-step`. This matches the autonomous-mode injection shape on Claude Code.
- **No session catchup adapter yet.** Automatic recovery reads the planning files on disk; `session-catchup.py` does not open dsh's session store under `~/.dsh/sessions/`.
- **`hooks:` frontmatter.** dsh ignores the `hooks:` block in `SKILL.md`; the plugin is the replacement.
- **dsh's own `/plan`.** That command is dsh plan mode and stays untouched; the plugin registers only `/pwf` and `/pwf-status`.
- **Prompts from other plugins.** Only a step that carries a user-sourced message gets the plan. A turn driven by another plugin's message (a `/goal` round, for example) is a continuation and gets nothing.
- **dsh 0.1.6 (alpha).** The alpha line folds `agent/session-start` into `agent/created` with a `source` field. On that line the compaction re-injection does not fire; the next prompt still carries the plan.

## Windows notes

- Plan paths, `.planning/.active_plan` and the attestation files use Windows paths; a UTF-8 BOM in `.active_plan` (a PowerShell redirect) is tolerated.
- `PWF_PLAN_ROOT` must be an absolute path with a drive letter (`C:\projects\app`); a rootless `\projects\app` and a UNC path are refused.
- `dsh plugin` needs pnpm on PATH (`npm install -g pnpm`).
- Set the environment variables for the `dsh` process, for example `$env:PLAN_ID = "2026-09-17-my-task"; dsh web` in PowerShell.

## Troubleshooting

- **The plugin is missing from `--dump-config`.** `dsh plugin --profile web why dsh-planning-with-files` shows whether pnpm installed it; re-run the `add`. A package without `dsh.bundle` in its `package.json` installs as a plain dependency and activates no layer; the published package declares it.
- **Nothing is injected.** Check `PLANNING_DISABLED`, then `/pwf-status`: no plan, a `context blocked` line (attestation), or the ambiguity notice each name their fix. A `planning-with-files: <point> skipped after an error` warning in the dsh log means the plugin contained an error and the turn proceeded without planning context.
- **Ambiguous plans.** A live plan in a direct child project competes with the cwd plan; pin the session with `PWF_PLAN_ROOT=<absolute path>` or `PLAN_ID=<slug>`.
- **The gate keeps steering.** The cap (`PWF_GATE_CAP`, default 20) and the ledger stall rule bound it; mark the phase complete in `task_plan.md`, remove `.mode`, or set `gate: false` on the row.

## From source (contributors)

```bash
git clone https://github.com/OthmanAdi/planning-with-files.git
cd planning-with-files/.dsh/packages/dsh-planning-with-files
npm ci && npm run build && npm test
```

To load the checkout into a profile, build it first (a linked checkout has no `dist/` until you do) and link it by absolute path:

```bash
dsh plugin --profile web add /absolute/path/to/planning-with-files/.dsh/packages/dsh-planning-with-files
```

`src/core.ts` is a byte-identical copy of the OpenCode plugin's core and `tests/test_dsh_plugin_core_parity.py` locks the two together: a fix goes into the OpenCode copy and is copied over.

## Learn More

- [Installation Guide](installation.md)
- [Quick Start](quickstart.md)
- [Workflow Diagram](workflow.md)
- [OpenCode Support](opencode.md), the sibling plugin this one mirrors
