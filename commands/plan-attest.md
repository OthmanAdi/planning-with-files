---
description: "Lock the current task_plan.md content with a SHA-256 attestation. Hooks then refuse to inject plan content if the file diverges from the attested hash, blocking silent tampering. Use --show to print the stored hash, --clear to remove the attestation. Available since v2.37.0."
disable-model-invocation: true
allowed-tools: "Bash"
---

Run the plan attestation helper for the active plan.

Steps:
1. Resolve the selected plan with the installed resolver (`resolve-plan-dir.sh`, or `resolve-plan-dir.ps1`); the helper below applies the same rules. A set `${PLAN_ID}` binds that plan. Without it, multiple plans refuse selection: the helper exits with `Multiple plans are available. Set PLAN_ID=<slug>; nothing was attested.` A single plan may use `.planning/.active_plan` or the newest `.planning/<dir>/`; the shared pointer does not bind a parallel session. If the current directory is itself a valid `.planning/<slug>/` directory, use its `task_plan.md`. With no selector and no named plan, use legacy `./task_plan.md`.
2. Compute the SHA-256 of the resolved `task_plan.md`.
3. Write the hex digest to `.planning/<active-plan>/.attestation` (parallel-plan mode) or `./.plan-attestation` (legacy mode).
4. Confirm to the user with the short hash (first 12 hex chars) and the storage path.

An explicit `${PLAN_ID}` or `${PWF_PLAN_ROOT}` that does not resolve exits with an error. It never falls back to another plan.

Implementation:
- On Linux/macOS/Git Bash: `sh ${CLAUDE_PLUGIN_ROOT}/scripts/attest-plan.sh`
- On Windows PowerShell plugin installs: `& "$env:CLAUDE_PLUGIN_ROOT\scripts\attest-plan.ps1"`
- On Windows PowerShell standalone installs: `& "$env:USERPROFILE\.claude\skills\planning-with-files\scripts\attest-plan.ps1"`

Flags:
- `--show` — print the currently stored hash and where it lives.
- `--clear` — remove the attestation (re-open the plan to free editing).

After running this command, every UserPromptSubmit and PreToolUse hook fire compares `task_plan.md` against the stored hash. If they diverge, the hook emits `[PLAN TAMPERED — injection blocked]` instead of feeding plan content into the model. Re-run `/plan-attest` whenever you intentionally edit and re-approve the plan.
