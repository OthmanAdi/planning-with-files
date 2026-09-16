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

## Write path

When you run `sh scripts/attest-plan.sh`, the script:

1. Resolves the active plan directory.
2. Hashes the active `task_plan.md`.
3. Writes the hash to a temporary file beside the attestation file.
4. Renames the temporary file into place.
5. Uses `flock -w 5` around the rename when `flock` is available.

The shell and PowerShell helpers can run from the project root or directly from
a valid `.planning/<slug>/` directory. A direct slug-directory invocation
targets that directory's `task_plan.md` and stores the hash in its `.attestation`
file. It does not create the legacy `.plan-attestation` file beside a slug plan.

`PLAN_ID` and `PWF_PLAN_ROOT` are explicit selectors. If an explicit selector
does not resolve, the helper exits with an error instead of attesting a different
plan through the current-directory fallback.

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
