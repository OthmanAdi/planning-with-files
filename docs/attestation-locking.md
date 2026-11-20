# Attestation Locking and Fallback

`scripts/attest-plan.sh` stores a SHA-256 hash for the active `task_plan.md`.
Hooks compare the current file hash with that stored attestation before they
inject plan content into model context.

## Trust boundary

The saved value is an ordinary local digest, not a keyed signature or proof of
human approval. It detects a changed plan only while that digest remains trusted.
A process that can replace both `task_plan.md` and its attestation can make new
content pass. Automatic attestation during initialization records the generated
bytes without a separate human review step.

Attestation does not make plan content safe to obey. Treat instructions copied
from tools, websites, or other external sources as untrusted even when the file
matches its saved digest. Stronger protection against a writer that controls the
whole planning directory requires a separate trust boundary, such as permissions
that protect the approval record from that writer.

## Routine progress updates

Whole-file attestation includes task checkboxes, phase status and Next Step.
Keep running notes in `progress.md`. After an intentional plan edit, review the
changed content and run `/plan-attest` again. Hooks do not approve edits
automatically, and a checked box is a progress claim, not evidence of completed
work.

### Opt in to checkbox-only updates

On a POSIX Python 3 runtime that supports the helper's file-safety operations,
review the whole plan and enroll it once:

```sh
sh scripts/attest-plan.sh --enable-checkbox-only --target root
```

After completing tasks and changing their checkboxes, refresh the attestation:

```sh
sh scripts/attest-plan.sh --checkbox-only --target root
```

Replace `root` with a named plan ID for a named plan, or omit `--target`
for the active selection. This command accepts only lowercase `[x]` in place
of `[ ]` in a standalone, flush-left `- [ ]` or `* [ ]` task with one
space after the list marker. It skips fenced examples and HTML comments.
Changing a checked box back to unchecked, editing plan text, changing
whitespace or using ambiguous raw HTML requires full re-attestation. The
helper stores checkbox positions and digest identities in a private local cache.
Hooks continue to verify the whole-file digest. The command does not confirm
that a task was completed.

A normal full re-attestation invalidates enrollment. Use `--clear` with the
active selection to remove its attestation. PowerShell continues to attest the
whole file through its native command.

## Write path

When you run `sh scripts/attest-plan.sh`, the script:

1. Resolves the active plan directory.
2. Acquires an exclusive writer lock for that attestation.
3. Hashes the active `task_plan.md`.
4. Writes the hash to a temporary file beside the attestation file.
5. Renames the temporary file into place and releases the lock.

The shell and PowerShell helpers can run from the project root or directly from
a valid `.planning/<slug>/` directory. A direct slug-directory invocation
targets that directory's `task_plan.md` and stores the hash in its `.attestation`
file. It does not create the legacy `.plan-attestation` file beside a slug plan.

`PLAN_ID` and `PWF_PLAN_ROOT` are explicit selectors. If an explicit selector
does not resolve, the helper exits with an error instead of attesting a different
plan through the current-directory fallback.

`--target root` (PowerShell: `-Target root`) explicitly attests the project's root
`task_plan.md` and writes `.plan-attestation`, even while a named plan is active.
`--target <plan-id>` (`-Target <plan-id>`) explicitly attests that named plan. Both
forms override `PLAN_ID` and honor `PWF_PLAN_ROOT`; without a project pin, paths are
relative to the current directory. Neither form changes `.planning/.active_plan`.
Empty, invalid or unresolved targets fail without falling back to another plan.
Named targets retain the shared resolver's containment and linked-directory
checks, and explicit targets reject linked plan files. `--target` selects the
plan for full attestation, enrollment and checkbox-only updates. `--show` and
`--clear` use the active selection. Every attestation write prints its plan and
attestation paths first.

A refusal is one line on stderr that names the selector it rejected. Control
characters in an echoed selector print as `?`, so a selector cannot forge a status
line.

Atomic replacement prevents readers from seeing a partial digest. The Bash,
PowerShell, OpenCode, DSH and Hermes writers share a lock for the selected
attestation. The shell tries an atomic hard link to claim the lock. On volumes
without hard links, POSIX uses exclusive directory creation and Git Bash uses
native PowerShell for exclusive file creation. A competing writer must acquire
the lock before changing the digest. The strict shell path also uses its legacy
`flock` guard when available.

If a command is forcibly terminated, its writer lock can remain in the plan
directory. Confirm that no attestation command is still running for that
plan, then remove only the stale lock file or directory. Its name is
`.plan-attestation.writer-lock` for root or `.attestation.writer-lock` for a named plan.

## Shared root plans

In legacy root mode, sessions sharing a project use the same files:

```text
./task_plan.md
./.plan-attestation
```

The writer lock protects digest updates. Concurrent edits to the shared plan
file can still overwrite each other.

## Recommended parallel workflow

Use slug-mode for parallel sessions:

```bash
./scripts/init-session.sh "Backend Refactor"
./scripts/init-session.sh "Incident Investigation"
```

On Windows PowerShell, the equivalent named-plan flow is:

```powershell
.\scripts\init-session.ps1 "Backend Refactor"
.\scripts\init-session.ps1 "Incident Investigation"
```

Each slug gets its own isolated files:

```text
.planning/2026-01-10-backend-refactor/task_plan.md
.planning/2026-01-10-backend-refactor/.attestation

.planning/2026-01-10-incident-investigation/task_plan.md
.planning/2026-01-10-incident-investigation/.attestation
```

Pin a terminal to one plan when needed:

```bash
export PLAN_ID=2026-01-10-backend-refactor
sh scripts/attest-plan.sh
```

```powershell
$env:PLAN_ID = "2026-01-10-backend-refactor"
.\scripts\attest-plan.ps1
```

Slug-mode avoids same-file contention by giving each session its own
`task_plan.md` and `.attestation` file.
