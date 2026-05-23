# Attestation Locking and Fallback

`scripts/attest-plan.sh` stores a SHA-256 hash for the active `task_plan.md`.
Hooks compare the current file hash with that stored attestation before they
inject plan content into model context.

## Write path

When you run `sh scripts/attest-plan.sh`, the script:

1. Resolves the active plan directory.
2. Hashes the active `task_plan.md`.
3. Writes the hash to a temporary file beside the attestation file.
4. Renames the temporary file into place.
5. Uses `flock -w 5` around the rename when `flock` is available.

The atomic rename is the correctness guarantee. It prevents readers from seeing
a partially written attestation file. The `flock` call is only a cooperative
gate for concurrent writers on systems that provide it.

## Platform behavior

| Platform | `flock` availability | Behavior |
|----------|----------------------|----------|
| Linux | Usually available | Atomic rename plus advisory `flock` guard. |
| macOS | Not installed by default | Atomic rename still protects correctness. |
| Windows Git Bash | Usually absent | Atomic rename still protects correctness. |
| WSL | Usually available | Same behavior as Linux. |

If `flock` is missing, `attest-plan.sh` skips the advisory lock and still
renames the temporary file into place. This is correct, but less coordinated
for multiple writers in the same directory.

## When fallback matters

The fallback only matters for legacy mode when two sessions write the same root
attestation file:

```text
./task_plan.md
./.plan-attestation
```

In that mode, both sessions share one plan file and one attestation file. The
atomic rename keeps the attestation file valid, but it does not make the shared
plan file a safe parallel workspace.

## Recommended parallel workflow

Use slug-mode for parallel sessions:

```bash
./scripts/init-session.sh "Backend Refactor"
./scripts/init-session.sh "Incident Investigation"
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

Slug-mode avoids same-file contention by giving each session its own
`task_plan.md` and `.attestation` file.
