# dsh-planning-with-files

Native [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) (`dsh`) plugin for [planning-with-files](https://github.com/OthmanAdi/planning-with-files): persistent file-based planning for AI coding agents. The plan lives on disk in `task_plan.md`, `findings.md` and `progress.md`; this plugin keeps it in the model's context on every prompt and can hold a gated turn open until the plan reports complete.

## Install

```bash
npx skills add OthmanAdi/planning-with-files --skill planning-with-files -g
dsh plugin --profile web add dsh-planning-with-files
```

The first line installs the skill text into `~/.agents/skills/planning-with-files/`, one of the paths dsh reads natively. The second adds this bundle to the `web` profile; restart `dsh web` afterwards. The same `dsh plugin --profile <name> add dsh-planning-with-files` works for the `headless`, `sdk` and `acp` profiles. `dsh --profile web --dump-config` shows the `dsh-planning-with-files` layer.

Built against the published `@deepseek-ai/dsh` 0.1.5-rc.2 and the `@deepseek-ai/*` 0.1.5-rc.2 libraries it installs.

## What the plugin does

| Lifecycle point | Behavior |
|---|---|
| `agent/pre-step` | Appends the active plan to the step that carries the user's prompt: the framed head of `task_plan.md`, the normalized tail of `progress.md`, a pointer to `findings.md`. Resolves `PLAN_ID`, then `.planning/.active_plan`, then the newest `.planning/<slug>/task_plan.md`, then the legacy root file. Steps that carry only tool results, steering or the plugin's own messages get nothing |
| `tools/post-execute` | Attaches a progress reminder to successful `write`, `edit` and mutating `str_replace_editor` calls (`create`, `str_replace`, `insert`) while a plan exists |
| `session/event` with a successful `compaction/end` | The next step of that agent (the continuation of an automatically compacted turn, or the prompt after a manual `/compact`) carries the compaction note (plan pointer, flush instruction, attestation hash) and the framed plan as one message, so the continuation resumes at the current phase |
| `agent/turn-stopping` | Completion gate in gated mode: while an `in_progress` phase remains, the plugin steers the agent into another step with the gate reason. Block cap `PWF_GATE_CAP` (default 20) and ledger stall detection release the turn; subagent children are never held |

Commands: `/pwf [--autonomous|--gated] [--template analytics] [plan name]` creates the planning files (a name creates `.planning/YYYY-MM-DD-<slug>/` and makes it active; `--gated` or `--autonomous` writes the v3 markers and attests the plan) and queues the framed plan for the next model request; `/pwf-status` reports the active plan. Tools: `pwf_init`, `pwf_status`, `pwf_check` with the same contract as the OpenCode plugin, resolving the plan from the calling agent's session workspace.

Environment, read from the `dsh` process: `PLAN_ID=<slug>` binds a plan and ends resolution when the slug names none; `PWF_PLAN_ROOT=<absolute path>` pins the project root and fails closed when it does not resolve; `PLANNING_DISABLED=1` silences every listener, command and tool; `PWF_GATE_CAP=<n>` caps the gate blocks. Autonomous and gated plans inject only when `.attestation` (slug) or `.plan-attestation` (root) matches the SHA-256 of `task_plan.md`. A live plan in a direct child project makes a cwd guess ambiguous and nothing is injected, with a one-line notice.

Row configuration: `enabled` (default `true`) and `gate` (default `true`, set `false` to keep injection and drop the completion gate).

Full guide: [docs/deepseek-harness.md](https://github.com/OthmanAdi/planning-with-files/blob/master/docs/deepseek-harness.md).

## License

MIT
