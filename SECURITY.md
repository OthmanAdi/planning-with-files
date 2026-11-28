# Security Policy

## Reporting a Vulnerability

Report suspected vulnerabilities privately through [GitHub Private Vulnerability Reporting](https://github.com/OthmanAdi/planning-with-files/security/advisories/new) (Security tab -> Report a vulnerability). This opens a private advisory visible only to the maintainer until a fix ships.

Include what you'd include in a normal bug report, plus:

- The affected hook, script, or file (e.g. `scripts/inject-plan.sh`, a specific IDE's `hooks/stop.sh`).
- The data flow: what untrusted input reaches what trusted context.
- Reproduction steps.
- Suggested mitigation, if you have one.

Do not open a public issue for a suspected vulnerability before it's been triaged privately.

## Scope

This repository ships markdown-based planning templates plus shell/PowerShell/Python hook scripts that several AI coding agents (Claude Code, Codex, Cursor, GitHub Copilot, and others) execute automatically during a session. Relevant security concerns include:

- Prompt injection via plan file content reaching model context (see the delimiter and attestation mechanisms in `scripts/inject-plan.sh` and `scripts/attest-plan.sh`).
- Path traversal or symlink escapes in plan directory resolution (`scripts/resolve-plan-dir.sh`, `scripts/inject-plan.sh`'s containment guard).
- Supply-chain concerns in any dependency, install script, or bin shim (this repo currently has none; flag if that changes).

## Data and Control Boundary

- Automatic lifecycle hooks read project planning state and may inject selected plan data into model context. Treat planning content copied from external sources as untrusted.
- Automatic recovery and bare `session-catchup.py` do not inspect host agent session stores.
- Explicit `session-catchup.py --metadata` reads same-project local session records and emits aggregate counts only. Explicit `--replay` may read and emit bounded nonce-framed same-project excerpts.
- The shipped catchup path contains no network request or upload operation. Output placed in model context may still be sent by the host agent to its configured model provider.
- Default Stop behavior is advisory. Optional gated mode can request continuation only on capable hosts. It evaluates runtime mode, phase status, Stop-hook state, block count, and plan progress. It never executes commands declared in Markdown planning files.

Not in scope: vulnerabilities in the AI agents/IDEs themselves (Claude Code, Codex, etc.) — report those to their respective maintainers.

## Response

Expect an initial response within a few days. Confirmed fixes ship as a patch release with a CHANGELOG `### Security` entry; credit is given in `CONTRIBUTORS.md` unless you ask to stay anonymous.

## Supported Versions

Only the latest released version is supported. Update to the current release before reporting if you're on an older one.
