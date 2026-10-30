---
description: "Lock the current task_plan.md content with a SHA-256 attestation. Hooks then refuse to inject plan content if the file diverges from the attested hash, blocking silent tampering. Use --show to print the stored hash, --clear to remove the attestation. Available since v2.37.0."
disable-model-invocation: true
allowed-tools: "Bash"
---

Run the plan attestation helper for the active plan.

Steps:
1. Forward the requested operation to the installed helper: `--show` or `--clear` for `attest-plan.sh`, `-Show` or `-Clear` for `attest-plan.ps1`, or no flag to attest.
2. Let that helper resolve the selected plan and storage path. Do not reproduce its selection logic or write an attestation manually.
3. If it reports an invalid explicit selector or multiple named plans, stop and ask for the exact `PLAN_ID`; do not substitute another task.
4. Report the helper's result and storage path to the user, including `Multiple plans are available` when it refuses ambiguity. The shared pointer does not bind a parallel session.

An explicit `${PLAN_ID}` or `${PWF_PLAN_ROOT}` that does not resolve exits with an error. It never falls back to another plan.

Implementation:
- On Linux/macOS/Git Bash: `sh ${CLAUDE_PLUGIN_ROOT}/scripts/attest-plan.sh`
- On Windows PowerShell plugin installs: `& "$env:CLAUDE_PLUGIN_ROOT\scripts\attest-plan.ps1"`
- On Windows PowerShell standalone installs: `& "$env:USERPROFILE\.claude\skills\planning-with-files\scripts\attest-plan.ps1"`

Flags:
- `--show` — print the currently stored hash and where it lives.
- `--clear` — remove the attestation (re-open the plan to free editing).
- Shell `--target root` or `--target <plan-id>` selects an explicit attestation target for this call; forward it when requested. PowerShell has `-Show` and `-Clear`, but no `-Target` parameter.

After running an attestation, every UserPromptSubmit and PreToolUse hook fire compares `task_plan.md` against the stored hash. If they diverge, the hook emits `[PLAN TAMPERED — injection blocked]` instead of feeding plan content into the model. Re-run `/plan-attest` whenever you intentionally edit and re-approve the plan.
