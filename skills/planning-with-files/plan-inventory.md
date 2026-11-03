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

The shell helper expects `--list` first, as in `--list --json`,
`--list --archived` and `--list --json --archived`.

Existing `--list` / `-List` output remains available for humans. Both formats
inspect the current directory. `PWF_PLAN_ROOT` does not redirect inventory.
Read `scope.project_root` before using returned paths. To inspect another
project, deliberately change to that validated project directory first.

## Schema version 1

The shell command writes one UTF-8 JSON line with an LF terminator to stdout.
Started from another process with a literal `-File` argument (`pwsh -File` or
`powershell -File`), the PowerShell script also writes one UTF-8 line with an
LF terminator. Every other call form, including use inside a session,
`-Command "& ... -List -Json"`, `-f` and a positional script path, hands the
same JSON to the pipeline with every non-ASCII character escaped as `\uXXXX`,
so the text is pure ASCII and decodes identically under any console code page;
the line ending is then the host's. Inside a PowerShell session,
`& "<skill-dir>/scripts/set-active-plan.ps1" -List -Json | ConvertFrom-Json`
returns the parsed object with the real characters. No model, service or extra
runtime is required. Invalid arguments fail without selecting or changing any
plan.

| Field | Meaning |
|---|---|
| `schema_version` | `1`; independent of the skill release version |
| `scope` | Absolute inspected `project_root`, with `source: "cwd"` |
| `candidates` | Root triplet first when present, then ASCII-ordered named plans (archived plans only with `--archived`) |
| `shared_default` | `.active_plan` ID and `present`, `missing`, `dangling`, `invalid` or `excluded` state |
| `selection` | Resolver-visible process selection; not a native conversation binding |
| `host_session` | `null`; this helper cannot establish a host's conversation state |
| `archived_count` | Integer count of archived plans under `.planning/.archive/`; `0` when that directory is missing, a link or outside the project |
| `limits` | Requested `limit`/`offset`, `returned`, `truncated`, `next_offset`, and `skipped` count |
| `warnings` | Reasons for partial metadata; inspect these before treating the inventory as complete |

Each candidate contains `kind` (`root`, `named` or `archived`), `plan_id`
(`null` for root), `ownership: "unknown"`, `files`, and `phases`. Each file
entry has its absolute `path`, `status` (`readable`, `missing`, `unreadable` or
`excluded`) and `modified_at` (Unix seconds, or `null`). The inventory does not
print file bodies, derive a summary with an LLM, or decide whether a file is
obsolete.

`archived_count` counts immediate directories in `.planning/.archive/` that
have a valid plan ID, are not links and hold a regular `task_plan.md`.
`--list --json --archived` (PowerShell: `-List -Json -Archived`) lists those
plans instead of the root and named plans. The envelope, schema version,
paging, limits, warnings and `archived_count` stay the same, there is no root
candidate, and each candidate has `kind: "archived"`, its `plan_id`, and file
paths under `<project_root>/.planning/.archive/<id>/`.

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
unknown (an explicit plan pin into that excluded root is rejected). A
`selected` status can name a `PLAN_ID` directory that has no `task_plan.md`,
so `selection.plan_id` is not guaranteed to appear in `candidates`. The shared
default must not be treated as the current session's assigned task.

Default output is up to 20 candidates, with a 16 KiB stdout ceiling. `limit`
accepts 1 through 100; `offset` accepts 0 through 999999. If `truncated` is
true, request `next_offset` to continue. An entry too large to fit is skipped
explicitly rather than producing broken JSON. Paging reflects the filesystem
at each invocation, so concurrent changes can alter page boundaries. A
`next_offset` is valid only for the runtime that returned it: the shell and
PowerShell routes can end pages at different entries because their byte
budgets and path escaping differ. Only immediate plan directories in
`.planning/` (or `.planning/.archive/` with `--archived`) are enumerated; no
recursive project, disk, worktree or agent-session-store scan runs. Links and
unsafe paths are excluded.

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

## Archive and restore

Without `PLAN_ID`, two or more named plans make selection ambiguous and hooks
inject nothing. An agent cannot set `PLAN_ID` for the hook process, but it can
move finished plans out of `.planning/` until one remains, which restores
automatic selection. Archiving tidies the workspace; it does not free disk
space. Archive only plans the user approved.

```sh
sh "<skill-dir>/scripts/set-active-plan.sh" --archive <id>
sh "<skill-dir>/scripts/set-active-plan.sh" --archive <id> --yes
sh "<skill-dir>/scripts/set-active-plan.sh" --list --archived
sh "<skill-dir>/scripts/set-active-plan.sh" --restore <id> --yes
```

```powershell
& "<skill-dir>/scripts/set-active-plan.ps1" -Archive <id>
& "<skill-dir>/scripts/set-active-plan.ps1" -Archive <id> -Yes
& "<skill-dir>/scripts/set-active-plan.ps1" -List -Archived
& "<skill-dir>/scripts/set-active-plan.ps1" -Restore <id> -Yes
```

Both commands act on the current directory's `.planning/` only and ignore
`PWF_PLAN_ROOT`. Without `--yes` (`-Yes`), archive and restore print a preview
and change nothing. The archive preview shows phase counts, the source and
destination paths, a note when not all phases are complete, and whether the
shared default (`.active_plan`) would be cleared. With `--yes`, archive moves
`.planning/<id>/` to `.planning/.archive/<id>/` in one rename and creates
`.planning/.archive/` when needed; if the rename then fails, a
`.planning/.archive/` this call created is removed again while it is still
empty. Attestation, mode and other files inside the plan directory move with
it. If `.planning/.active_plan` names the archived plan's directory (read as
the resolver reads it: BOM and whitespace removed), the pointer file is
removed and the output says so. Restore moves the directory back and never
touches `.active_plan`. Plain `--list` points at archiving in its footer and,
when archived plans exist, gives their number.

An ID must match the directory name exactly, including case: on a
case-insensitive filesystem `ALPHA` does not archive `alpha`, and on Windows
`alpha.` does not archive `alpha`. The `PLAN_ID` guard compares directories,
so a pin spelled `ALPHA` still protects `alpha` where the resolver would
select it.

Both commands exit 1 with an `Error:` line on stderr and change nothing when:

- the ID does not match `^[A-Za-z0-9_][A-Za-z0-9._-]*$`, or the arguments
  do not form one of the commands above;
- `.planning/`, `.planning/.archive/` or the source directory is a link, a
  junction or outside the project;
- the source directory is missing, is not listed under exactly that name, or
  has no regular `task_plan.md`;
- the destination exists in any form, including a dangling link;
- `PLAN_ID` in the current environment names the directory being archived;
- (shell) the source and destination are on different filesystems, or this
  cannot be determined.

Nothing is deleted, copied across volumes or overwritten. Nothing is archived
automatically: hooks, initialization and completion checks never archive, and
no plan is chosen by age or completion. Only named plans can be archived; the
legacy root `task_plan.md` is out of scope.

The helper cannot prove that no session still uses a plan. It cannot see
Hermes profile bindings or a `PLAN_ID` set in another session's process. A
session pinned to an archived ID resolves to nothing, never to another plan;
restore the plan or change the pin.
