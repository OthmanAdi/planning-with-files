# Agent-readable plan inventory

Use this when an agent needs to find saved planning files before resuming,
reviewing or handing off a task. It is optional; ordinary skill activation and
planning do not run inventory.

Run from the project you want to inspect, using the installed skill directory:

```sh
sh "<skill-dir>/scripts/set-active-plan.sh" --list --json
sh "<skill-dir>/scripts/set-active-plan.sh" --list --json --limit 10 --offset 0
```

```powershell
& "<skill-dir>/scripts/set-active-plan.ps1" -List -Json
& "<skill-dir>/scripts/set-active-plan.ps1" -List -Json -Limit 10 -Offset 0
```

Existing `--list` / `-List` output remains available for humans. Both formats
inspect the current directory. `PWF_PLAN_ROOT` does not redirect inventory.
Read `scope.project_root` before using returned paths. To inspect another
project, deliberately change to that validated project directory first.

## Schema version 1

The command emits one UTF-8 JSON line with an LF terminator on stdout. No model, service or extra runtime
is required. Invalid arguments fail without selecting or changing any plan.

| Field | Meaning |
|---|---|
| `schema_version` | `1`; independent of the skill release version |
| `scope` | Absolute inspected `project_root`, with `source: "cwd"` |
| `candidates` | Root triplet first when present, then ASCII-ordered named plans |
| `shared_default` | `.active_plan` ID and `present`, `missing`, `dangling`, `invalid` or `excluded` state |
| `selection` | Resolver-visible process selection; not a native conversation binding |
| `host_session` | `null`; this helper cannot establish a host's conversation state |
| `limits` | Requested `limit`/`offset`, `returned`, `truncated`, `next_offset`, and `skipped` count |
| `warnings` | Reasons for partial metadata; inspect these before treating the inventory as complete |

Each candidate contains `kind` (`root` or `named`), `plan_id` (`null` for root),
`ownership: "unknown"`, `files`, and `phases`. Each file entry has its absolute
`path`, `status` (`readable`, `missing`, `unreadable` or `excluded`) and
`modified_at` (Unix seconds, or `null`). The inventory does not print file
bodies, derive a summary with an LLM, or decide whether a file is obsolete.

`phases` includes `total`, `complete`, `in_progress`, `pending`, and `status`:
`parsed`, `empty`, `malformed`, `unavailable` or `too_large`. Counts use the
existing native phase conventions and ignore fenced examples. Empty or
malformed structure is not completion. Phase reads are limited to 256 KiB per
plan; larger files retain file metadata without a phase summary.

`selection.status` can be `selected`, `legacy_root`, `none`, `ambiguous`,
`rejected`, `outside_scope` or `unknown`. An invalid explicit pin never becomes
another plan. A pin naming another project is outside the cwd inventory.
Partial installs without a sibling resolver report selection as unknown.
Oversized pointer metadata or an excluded planning root also leaves selection
unknown (an explicit plan pin into that excluded root is rejected). The shared default
must not be treated as the current session's assigned task.

Default output is up to 20 candidates, with a 16 KiB stdout ceiling. `limit`
accepts 1 through 100; `offset` accepts 0 through 999999. If `truncated` is
true, request `next_offset` to continue. An entry too large to fit is skipped
explicitly rather than producing broken JSON. Paging reflects the filesystem
at each invocation, so concurrent changes can alter page boundaries. Only
immediate named-plan directories are enumerated; no recursive project, disk,
worktree or agent-session-store scan runs. Links and unsafe paths are excluded.

## Worker handoff

The parent can use these paths to send a worker a compact assignment:

```text
Project: <scope.project_root>
Assigned plan: <explicit selected plan ID>
Planning files: <the three files.*.path values>
Write scope: <worker-owned files or ledger>
Plan owner: <orchestrator>
```

Resolve rejected or ambiguous selection before assigning work. Inventory does
not bind a host, initialize a plan, edit a pointer, attest, archive or delete
anything. Keep the existing single-owner rule for shared summaries. File age,
reported completion and candidate discovery do not authorize cleanup.
