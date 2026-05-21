# Changelog

All notable changes to this project will be documented in this file.

## [2.39.0] - 2026-05-22

### Added

- **Pi Coding Agent full hook parity** (`feat/pi-full-adaptation`): Pi integration now matches Claude Code's lifecycle behavior via a bundled TypeScript extension. Six Pi events are mapped: `session_start` (catchup), `before_agent_start` (plan injection), `tool_call` (pre-tool recitation), `tool_result` (post-write reminder), `agent_end` (auto-continue, loop limit 3), and `session_before_compact` (compaction reminder with Plan-SHA256).
- **Mode system**: `PWF_MODE` env var and settings.json config support four modes: `auto` (default, DeepSeek -> cache-safe, other -> parity), `parity` (full dynamic plan injection), `cache-safe` (fixed constant reminder for DeepSeek KV-cache stability), and `notify` (notification-only).
- **Attestation gate**: Extension verifies SHA-256 of `task_plan.md` against trusted hash. Plan injection is blocked with `[PLAN TAMPERED]` warning on mismatch.
- **Pi commands**: `/plan-status`, `/plan-attest [--show|--clear]`, `/plan-goal <text|default|clear>`, `/plan-loop [interval] [prompt]` (use `stop` to cancel).
- **Schema-agnostic plan parsing**: Both `**Status:** complete` and `[complete]` bracket formats supported. Parallel plan directory resolution matches `resolve-plan-dir.sh` semantics (PLAN_ID > .active_plan > newest mtime > legacy root).
- **Package wiring**: `.pi/skills/planning-with-files/package.json` declares `pi.extensions` for automatic extension loading on `pi install`.
- **Contract tests**: 12 new tests for packaging, capabilities, and docs assertions.

### Changed

- `docs/pi-agent.md` rewritten for mode-based behavior; no longer states hooks are unsupported in Pi.
- `.pi/skills/planning-with-files/README.md` updated for new extension and mode system.
- `.gitignore` now excludes `__pycache__/` and `*.pyc`.
- `.pi/skills/planning-with-files/package.json` bumped from `1.0.1` to `1.1.0` (Pi npm scheme).

## [2.38.1] - 2026-05-16

### Fixed

- **Description field garbled in Claude Code skill picker** (surfaced by @bmyury via Discussion #153): the canonical SKILL.md frontmatter declares hooks inline as YAML scalars. Several of those scalars contain `'---BEGIN PLAN DATA---'` and `'---END PLAN DATA---'` as plan-injection delimiters (introduced in v2.36.1, reinforced in v2.37 attestation). Frontmatter parsers that split on the literal string `---` to locate the closing fence read the first `---` inside a hook command as the fence, truncating the YAML mid-string. Claude Code's skill-discovery loader behaves this way, so the description shown in the in-product skill list was a fragment of the hook command tail (`BEGIN PLAN DATA---'; head -50 task_plan.md...`) instead of the documented description. Real YAML parsers handled the frontmatter correctly, so hook execution and tamper attestation were never affected; only the displayed metadata was wrong. v2.38.1 swaps the delimiter shape from `---BEGIN PLAN DATA---` / `---END PLAN DATA---` to `===BEGIN PLAN DATA===` / `===END PLAN DATA===` across the canonical SKILL.md, all five language variants, the `.codebuddy`, `.codex`, `.cursor` adapter mirrors, and the `clawhub-upload` bundle. Same delimiter shape, same model-side framing semantics; the `===` substring does not collide with YAML's document separator.

### Changed

- Version bumped to 2.38.1 across 14 SKILL.md variants, `plugin.json`, `marketplace.json`, and `CITATION.cff` via `scripts/bump-version.py`. `.continue`, `.gemini`, `.pi`, `.kiro` lag intentionally.
- Pre-existing line-ending drift in IDE adapter mirrors (`examples.md`, `attest-plan.sh`, `attest-plan.ps1` under `.codex`, `.cursor`, `.gemini`, `.opencode`, `.pi`) normalized to LF via `scripts/sync-ide-folders.py`. 12 files touched, content identical to canonical.

### Thanks

- @bmyury for surfacing the description display bug via Discussion #153.

## [2.38.0] - 2026-05-14

### Added

- **PreCompact hook**: a new hook event fires on Claude Code's autoCompact and manual `/compact`. When `task_plan.md` is present, the hook surfaces a reminder to flush in-context progress to `progress.md` before compaction completes, and prints the active `Plan-SHA256` if an attestation is set. Added to the canonical SKILL.md plus all five language variants plus `clawhub-upload`. Other IDE mirrors fall back to their pre-existing compaction-related hooks (Codex `/compact` callback, OpenCode `session.compacted`, Hermes `pre_llm_call`) until per-IDE PreCompact adapters land in a later release.
- **`/plan-goal` slash command**: composes with Claude Code's new `/goal` primitive (v2.1.139, May 12 2026). Derives a goal condition from the active plan (`all phases in task_plan.md report Status: complete`) and forwards it to `/goal` so the agent keeps working until the plan-file is genuinely done, not just when the conversation looks done. Plan-loop and plan-goal are intentionally composable: cadence + termination criterion.
- **`/plan-loop` slash command**: composes with Claude Code's `/loop` primitive (v2.1.72+). Default 10-minute tick re-reads the planning files, runs `check-complete`, and nudges an entry into `progress.md` if nothing has changed since the last tick. Override interval and prompt as you would with bare `/loop`.
- **`templates/loop.md`**: a planning-aware default prompt users can copy into `.claude/loop.md` (project) or `~/.claude/loop.md` (user) so bare `/loop` runs grounded in the active plan. `/loop` only reads these two paths; copy is required, not auto-wired.
- **OpenCode SQLite session catchup**: the skill's session-catchup script reads OpenCode's new SQLite store at `${XDG_DATA_HOME:-~/.local/share}/opencode/opencode.db` (sst/opencode dev @ 2026-05-14, schema: `session(id, directory, time_created, ...)` + `part(id, session_id, time_created, data TEXT JSON)`). The previous JSON-tree reader silently no-op'd for every OpenCode user since the storage migration. Now opens the DB read-only via URI (`file:<path>?mode=ro`), scopes by `session.directory`, and surfaces the most recent unsynced planning-file edits with the same UX as the Claude Code path. Defensive `PRAGMA table_info` probe degrades cleanly on schema migrations. Verified end-to-end against a real 162 MB OpenCode database on the development machine (94 sessions, correctly extracted 56 unsynced parts from a session with planning-file edits).
- **Codex `PermissionRequest` adapter**: Codex added a `PermissionRequest` hook event for tool-permission prompts. The new `.codex/hooks/permission_request.py` adapter surfaces a one-line reminder to review `task_plan.md` before approving a request, when an active plan is present. Session-attachment gated (legacy default-on, isolation opt-in). Read-only; never blocks the request.
- **SKILL.md body documentation**: a new "Claude Code Turn-Loop Integration (v2.38.0+)" section documents the PreCompact hook, `/plan-goal`, `/plan-loop`, and the `loop.md` template install. Surfaces v2.38 features in user-facing prose, not only frontmatter.
- **`clawhub-upload/` full sync**: the ClawHub upload bundle had drifted from canonical somewhere around v2.32 (missing slug-mode, set-active-plan, resolve-plan-dir, attest-plan scripts, BEGIN/END injection delimiters, hash attestation hook bodies). Re-synced from canonical so the manual ClawHub upload reflects current v2.38 state.
- **`tests/test_precompact_hook.py`** (6 tests): asserts the PreCompact hook is declared with a wildcard matcher, stays silent without `task_plan.md`, emits the reminder when the plan exists, surfaces `Plan-SHA256` only when an attestation file is set, and exits 0 on every code path.
- **`tests/test_v238_command_files.py`** (7 tests): asserts `commands/plan-goal.md`, `commands/plan-loop.md`, and `templates/loop.md` exist, carry the expected frontmatter, document the `/goal` 4000-char limit, and reference all three planning files.
- **`tests/test_session_catchup_opencode.py`** (4 tests): builds a synthetic `opencode.db` matching the live schema, asserts the catchup function finds the most recent planning-file edit, stays silent when no plan edit is present, and degrades silently when the DB is missing.

### Changed

- Version bumped to 2.38.0 across 14 SKILL.md variants, `plugin.json`, `marketplace.json`, and `CITATION.cff` via `scripts/bump-version.py`. `.continue`, `.gemini`, `.pi`, `.kiro` lag intentionally.
- Canonical session-catchup script propagated to `.codebuddy`, `.codex`, `.continue`, `.factory`, `.gemini`, `.opencode`, `.pi` via `scripts/sync-ide-folders.py`.

### Not changed (deliberate)

- **No `paths` glob restriction in the canonical SKILL.md frontmatter.** The Claude Code spec now supports a `paths` field that filters auto-invocation to matching file types. Adding it would silently change auto-invocation behavior for the existing install base. Deferred to a later release with explicit signal data.
- **No bulk replacement of inline hook bodies with `!command` substitution.** That substitution runs at skill-load time, not per hook fire. Wholesale swap would freeze the SHA-256 attestation hash at load time and silently disable v2.37's tamper-detection gate. Inline hook bodies retained for per-fire runtime checks.
- **No native Plan Mode panel integration.** Claude Code's April 14 2026 desktop redesign added a Plan Mode panel with Approve/Reject flow, but no plugin/skill API is publicly documented for rendering plans into that panel. Tracked for a future release.
- **No language variant consolidation.** Issue #130 (consolidate into a single skill with locale parameter) is a separate breaking change and is not bundled into this release. The five locale-specific variants continue to ship.

## [2.37.0] - 2026-05-05

### Security

- **Hash attestation for plan injection** (Issue #150 by @oaabahussain): `task_plan.md` content is auto-injected into the model context on every UserPromptSubmit and PreToolUse fire. v2.36.1 added BEGIN/END delimiters, but the model still parses the bytes. v2.37.0 adds an opt-in second layer: run `/plan-attest` (or `sh scripts/attest-plan.sh`) once a plan is finalised. The script computes a SHA-256 of `task_plan.md` and stores it at `.planning/<active-plan>/.attestation` (parallel-plan mode) or `./.plan-attestation` (legacy mode). On every hook fire, the inline check recomputes the hash and compares. On mismatch, injection is blocked and the model receives `[planning-with-files] [PLAN TAMPERED — injection blocked]` instead of plan content. When attestation is set, the injected context also carries a `Plan-SHA256:` line so the model can log the attested hash for audit. Opt-in: absence of an attestation file preserves the v2.36.x behavior.

### Added

- **`/plan-attest` slash command**: thin wrapper around `attest-plan.sh` with `--show` (print the stored hash) and `--clear` (re-open the plan to free editing).
- **`scripts/attest-plan.sh` and `scripts/attest-plan.ps1`**: SHA-256 attestation helper for both POSIX shell and Windows PowerShell. Resolves the active plan via the same `$PLAN_ID` / `.active_plan` / newest-mtime / legacy chain used by the rest of the skill.
- **`scripts/bump-version.py`** (Issue #151 by @oaabahussain): atomic version bumper for the parity-locked file set (14 SKILL.md variants, `plugin.json`, `marketplace.json`, `CITATION.cff`). Replaces 17 hand edits with one `python scripts/bump-version.py X.Y.Z`. Prevents the "missed one variant" regression class that hit v2.34.1, v2.36.0, v2.36.2, and v2.36.3. `.continue`, `.gemini`, `.pi`, and `.kiro` are intentionally excluded (separate version schemes); the script lists them at the end of every run so the omission stays visible.
- **`tests/test_skill_md_version_parity.py`** (Issue #151): four assertions that fail the build the moment any parity-locked file diverges from the canonical SKILL.md version. Catches drift in CI before it can ship.
- **`tests/test_plan_attestation.py`**: six tests covering legacy and parallel-plan attestation, `--show`, `--clear`, tamper detection, and missing-plan handling.

### Fixed

- **Duplicate test class in `tests/test_canonical_script_sync.py`**: a leftover second copy of `CanonicalScriptSyncTests` (lines 99 to 137) was running the same assertions twice. Removed.

### Changed

- **Security Boundary section in canonical SKILL.md**: now documents the two layers of defense (delimiters + attestation) and adds an explicit rule recommending `/plan-attest` after finalising a plan.
- **`scripts/sync-ide-folders.py`**: SCRIPTS manifest now includes `attest-plan.sh` and `attest-plan.ps1`. The eight pre-existing scripts are unchanged.
- **`tests/test_canonical_script_sync.py`**: `SHARED_SCRIPTS` extended to ten entries (added `attest-plan.sh` and `attest-plan.ps1`). The regression test now covers all user-facing scripts.
- Version bumped to 2.37.0 across 14 SKILL.md variants, `plugin.json`, `marketplace.json`, and `CITATION.cff` via `scripts/bump-version.py`.

### Thanks

- @oaabahussain for two thoughtful, well-scoped P1 reports: Issue #150 turned the v2.36.1 delimiter mitigation into a verifiable cryptographic guarantee, and Issue #151 named the regression class behind four consecutive releases and proposed the right surgical fix.

## [2.36.3] - 2026-05-01

### Fixed

- **Missing parallel planning scripts in canonical skill copy**: `resolve-plan-dir.sh`, `resolve-plan-dir.ps1`, `set-active-plan.sh`, and `set-active-plan.ps1` were added to `scripts/` in v2.36.0 but never propagated to `skills/planning-with-files/scripts/` or the IDE mirror folders. Users installing via `npx skills add` could not use the v2.36.0 parallel planning workflow because the key scripts were not shipped in the install. Same class of gap as PR #149.
- **`sync-ide-folders.py` manifest incomplete**: the sync manifest only listed the original five scripts and did not include the four new v2.36.0 scripts. Running the sync tool after this release propagates all nine user-facing scripts to all IDE mirrors.
- **`test_canonical_script_sync.py` did not cover new scripts**: the SHARED_SCRIPTS tuple in the regression test from PR #149 only listed the original four scripts. Updated to include all eight user-facing scripts that must stay in sync between `scripts/` and `skills/planning-with-files/scripts/`.

### Added

- **Parallel planning documentation in SKILL.md**: the Scripts section now documents `resolve-plan-dir.sh` and `set-active-plan.sh` with usage descriptions and a parallel task workflow example showing how to use slug mode, `set-active-plan.sh`, and `export PLAN_ID` together.

### Changed

- Version bumped to 2.36.3 across 14 SKILL.md variants, `plugin.json`, `marketplace.json`, and `CITATION.cff`

## [2.36.2] - 2026-05-01

### Fixed

- **Canonical skill copy missing slug-mode init-session** (PR #149 by @voidborne-d): `skills/planning-with-files/scripts/init-session.sh` and `init-session.ps1` were not updated when slug mode shipped in v2.36.0. Users installing via `npx skills add` or any of the nine IDE folders received the legacy-only v2.0.0 script, silently missing the parallel plan isolation feature. Fixed by syncing the top-level canonical scripts into the skill directory and all IDE mirrors.
- **Shebang drift in IDE mirror scripts**: `check-complete.sh` in `.codebuddy/`, `.codex/`, `.continue/`, `.factory/`, `.gemini/`, `.pi/` folders still used `#!/bin/bash`. Synced to `#!/usr/bin/env bash` to match the Emin017 fix from v2.35.1.
- **Analytics template gap in canonical PS1**: `init-session.ps1` in the canonical skill copy lacked the `--template analytics` support added in v2.29.0 by @mvanhorn. Included in this sync.

### Added

- **Regression test** `tests/test_canonical_script_sync.py`: asserts `init-session.{sh,ps1}` and `check-complete.{sh,ps1}` are byte-identical between `scripts/` and `skills/planning-with-files/scripts/`. A second assertion invokes `sync-ide-folders.py --verify` to catch IDE mirror drift in CI. Prevents this class of silent version mismatch from recurring.

### Changed

- Version bumped to 2.36.2 across 14 SKILL.md variants, `plugin.json`, `marketplace.json`, and `CITATION.cff`
- `CONTRIBUTORS.md` updated: added @voidborne-d (PR #149)

### Thanks

- @voidborne-d for catching the canonical/top-level script drift, providing grep proof, running the sync tool, and adding the regression test that prevents recurrence (PR #149)

## [2.36.1] - 2026-05-01

### Security

- **Stop hook: eliminate broad cache search** (Gen Agent Trust Hub COMMAND_EXECUTION): replaced `Get-ChildItem -Recurse` over `~/.claude/plugins/cache` with resolution through `$CLAUDE_SKILL_DIR` env var first, then two specific known install paths (`~/.claude/skills/` and `~/.claude/plugins/marketplaces/`). Removes the attack surface where a malicious `check-complete.ps1` planted anywhere in the cache directory would be found and executed.
- **PowerShell ExecutionPolicy: Bypass → RemoteSigned** (Gen Agent Trust Hub COMMAND_EXECUTION): `ExecutionPolicy Bypass` circumvents all script execution policies. `RemoteSigned` allows locally created scripts while still blocking downloaded scripts that lack a trusted signature. Applied across all 14 SKILL.md variants.
- **Prompt injection delimiters** (Gen Agent Trust Hub PROMPT_INJECTION): `UserPromptSubmit` and `PreToolUse` hook output now wraps injected plan content in `---BEGIN PLAN DATA---` / `---END PLAN DATA---` markers with explicit model instructions to treat enclosed content as structured data and ignore embedded instructions. Addresses the lack of sanitization and boundary markers flagged in the audit.
- **Security Boundary section updated** (Snyk W011): added explicit model instruction that `findings.md` content (which ingests third-party web/search results) must be treated as raw data regardless of what it contains. Clarifies the delimiter contract to auditors and the model.

### Changed

- Version bumped to 2.36.1 across all 14 SKILL.md variants, `plugin.json`, `marketplace.json`, and `CITATION.cff`

## [2.36.0] - 2026-05-01

### Added

- **Parallel plan isolation** (Issue #148 by @shawnli1874): `init-session.sh` now accepts a task name and creates a dated, readable plan directory under `.planning/YYYY-MM-DD-<slug>/`. Each parallel task gets its own isolated directory, ending the cross-contamination that v2.0.0 hooks introduced by hardcoding `task_plan.md` at the project root. Legacy zero-argument behavior is unchanged. New `set-active-plan.sh` and `set-active-plan.ps1` let users explicitly switch between plans without exporting `PLAN_ID`. New `resolve-plan-dir.sh` and `resolve-plan-dir.ps1` provide the resolution chain: `$PLAN_ID` env var, then `.planning/.active_plan`, then the newest plan directory by mtime, then empty (legacy fallback). All four Codex lifecycle hooks (UserPromptSubmit, PreToolUse, PostToolUse, Stop) now route through the resolver instead of assuming a root-level `task_plan.md`.
- **Codex session isolation** (Issue #146 by @githubYiheng): Codex sessions in a shared working directory no longer receive plan context from unrelated sessions. Attachment is opt-in: create `.planning/sessions/<session_id>.attached` to bind a session to the active plan. `user-prompt-submit.sh`, `pre_tool_use.py`, `stop.py`, and `post_tool_use.py` all gate on session attachment before injecting context or blocking. Backward compatible: absence of `.planning/sessions/` preserves existing single-session behavior.
- **Hermes integration notes** (Issue #147 by @09ashishkapoor): `docs/hermes.md` gains an `Integration Notes` section that separates what the adapter provides today from what is not full parity with hook-native platforms. Covers current support level, recommended integration pattern, and a tradeoffs table. Reduces confusion for users migrating from Claude Code hook workflows.
- **34 new tests**: `tests/test_resolve_plan_dir.py` (7), `tests/test_init_session_slug.py` (6), `tests/test_hook_resolver_integration.py` (10), `tests/test_codex_session_isolation.py` (5), `tests/test_set_active_plan.py` (6).

### Fixed

- **`resolve_latest_dir` skips non-plan directories**: auto-discovery previously matched any subdirectory under `.planning/`, including the new `sessions/` directory. It now requires `task_plan.md` to be present, preventing session isolation from silently breaking when both features are active.
- **`short_uuid()` bypasses Windows App Execution Aliases**: the function now probes each Python candidate with a test run before trusting `command -v`, avoiding the case where the Windows Store alias reports presence but exits non-zero.

### Changed

- Version bumped to 2.36.0 across 14 SKILL.md variants, `plugin.json`, `marketplace.json`, and `CITATION.cff`
- `CONTRIBUTORS.md` updated: added @githubYiheng (Issue #146), @09ashishkapoor (Issue #147), @shawnli1874 (Issue #148); total count now 39+

### Thanks

- @githubYiheng for tracing the session boundary problem down to its exact code path and proposing the session attachment model (Issue #146)
- @09ashishkapoor for the clear documentation gap report and the four-section structure that made writing the fix straightforward (Issue #147)
- @shawnli1874 for the detailed parallel workflow breakdown, the concrete reproduction case, and the slug naming proposal that shaped the final design (Issue #148)

## [2.35.0] - 2026-04-21

### Added

- **Hermes adapter** (PR #136 by @bailob): new `.hermes/skills/planning-with-files/` bundle, `.hermes/plugins/planning-with-files/` Python adapter, `/plan` and `/plan-status` command wrappers, and `docs/hermes.md` install guide. The adapter registers three tools (`planning_with_files_init`, `planning_with_files_status`, `planning_with_files_check_complete`) plus `pre_llm_call` and `post_tool_call` hooks that mirror the Claude Code hook behavior. Hermes is now platform 17. The PR ships 20 unit tests in `tests/test_hermes_adapter.py` covering status parsing, reminder behavior, installation layout, and completion checks.
- **NLPM audit coverage** (Issue #140 by @xiaolai): static audit of all 25 natural language artifacts, overall score 91/100, zero Critical or High findings. The three verified bugs were filed as separate PRs and merged below.

### Fixed

- **Pi PowerShell session-catchup syntax error** (PR #137 by @xiaolai, closes part of #140): `.pi/skills/planning-with-files/SKILL.md` had a missing opening `"` before the script path in the Windows PowerShell invocation, causing a parse error that silently killed session catchup for Pi users on Windows. Quote restored to balance the closing `"`.
- **Session-catchup context injection now bounded** (PR #138 by @xiaolai, closes part of #140): `.github/hooks/scripts/session-start.sh` piped unbounded `session-catchup.py` output into `additionalContext`, meaning content from a prior session (web results, tool output) could reach the current model context unlabeled and without size limit. Output now passes through `head -100` and is prefixed with `[planning-with-files] Previous session context (truncated to 100 lines):` so the model knows the content is historical.
- **Hook scripts prefer known Python paths** (PR #139 by @xiaolai, closes part of #140): `session-start.sh`, `pre-tool-use.sh`, and `error-occurred.sh` resolved the Python interpreter entirely from the user's PATH. The three scripts now try `/usr/bin/python3`, `/usr/local/bin/python3`, and `/opt/homebrew/bin/python3` before falling back to `command -v python3`, closing a PATH hijack vector without changing behavior on systems that expose Python at those canonical paths.

### Changed

- Version bumped to 2.35.0 across 14 SKILL.md variants, plugin.json, marketplace.json, and CITATION.cff
- `CONTRIBUTORS.md` updated: added @bailob (PR #136, major contribution) and @xiaolai (PRs #137, #138, #139, Issue #140); total count now 36+
- plugin.json description now says "17+ AI coding assistants" and keywords include `hermes`

### Thanks

- @bailob for the Hermes adapter, full test coverage, and the `/plan` and `/plan-status` command wrappers (PR #136)
- @xiaolai for the NLPM audit sweep and three coordinated hardening PRs (PR #137, PR #138, PR #139, Issue #140)

## [2.34.1] - 2026-04-17

### Fixed

- **Stop hook portability failure on Windows Git Bash** (closes #133, reported by @nazeshinjite) — Two independent bugs caused the Stop hook to silently fail on Windows 11 with Git Bash inside Command Prompt: (1) `export SD=` was treated as an external command rather than a shell builtin in certain Windows Git Bash invocation contexts, producing `bash: export: No such file or directory`; (2) the fallback path `$HOME/.claude/plugins/planning-with-files` never exists — the actual install location is `~/.claude/plugins/cache/planning-with-files/planning-with-files/VERSION/`. Fixed across all 13 SKILL.md variants (Claude Code, Codex, CodeBuddy, Cursor, Factory, Mastra Code, OpenCode, all language variants). Claude Code variants now use PowerShell self-discovery via `Get-ChildItem -Recurse` with `~` home expansion (no bash variable needed) and a glob-based sh fallback against the correct cache path. All other IDE variants have `export SD=` replaced with `SD=`.

## [2.34.0] - 2026-04-15

### Added

- **Codex hooks restored** (closes #132) — `.codex/hooks.json` and `.codex/hooks/` scripts are back. Codex users now get the same full lifecycle hook automation as Claude Code, Cursor, and Copilot users: SessionStart runs session catchup and injects plan context; UserPromptSubmit re-injects on every message; PreToolUse re-reads task_plan.md before Bash; PostToolUse reminds the agent to update progress.md; Stop blocks when phases are incomplete then re-prompts. These files were present in v2.31.0 (PR #120 by @Leon-Algo) but were accidentally wiped when master was rewritten during v2.32.0 — now fully restored.
- **Codex hook regression test** (`tests/test_codex_hooks.py`) — 4 test cases covering hooks.json structure, SessionStart context injection, PreToolUse systemMessage emission, PostToolUse progress reminder, and Stop block-then-allow behavior
- **Tessl skill-review-and-optimize CI** (PR #131 by @popey) — `.github/workflows/skill-review.yml` runs on every PR that touches a SKILL.md, posts scores and AI-suggested improvements as a PR comment; `.github/workflows/skill-optimize-apply.yml` lets contributors type `/apply-optimize` to commit the suggestions directly. Non-blocking by default.

### Fixed

- **Canonical shell scripts not executable** (PR #122 by @Leon-Algo) — `skills/planning-with-files/scripts/check-complete.sh` and `init-session.sh` were tracked as `100644` instead of `100755`, breaking Codex and any Unix installer that depends on the executable bit. Fixed to `100755`. Regression test added.
- **Duplicate `version:` key in Codex SKILL.md** — `.codex/skills/planning-with-files/SKILL.md` had two `version: "2.33.0"` entries in the metadata block (same bug fixed for zh/zht in a previous commit but missed here). Deduplicated.
- **Codex docs updated** — `docs/codex.md` rewritten to cover both skills and hooks installation, hooks protocol explanation, workspace vs personal install, and troubleshooting for duplicate hook messages and Windows limitations.

### Changed

- **CONTRIBUTORS.md updated** — Added @Leon-Algo (PRs #119, #120, #122), @YSAA1 (PR #109), @kevinaimonster (PR #108), @wd041216-bit (PR #107); updated @lasmarois entry to include PR #37; bumped total count to 32+

### Thanks

- @Leon-Algo for the Codex hooks design, three separate fix PRs, and patience while the master rewrite wiped his work (PR #119, #120, #122)
- @popey (Alan Pope) for the Tessl CI workflow (PR #131)

## [2.33.0] - 2026-04-09

### Added

- **Multi-language expansion** — New skill variants for international users:
  - Arabic (`planning-with-files-ar`) - Full Arabic localization with proper RTL support
  - German (`planning-with-files-de`) - Complete German localization  
  - Spanish (`planning-with-files-es`) - Comprehensive Spanish localization
  - Enhanced Simplified Chinese (`planning-with-files-zh`) - Fully localized scripts and templates
  - Enhanced Traditional Chinese (`planning-with-files-zht`) - Refined localization
- **New command files** for all languages: `plan-ar.md`, `plan-de.md`, `plan-es.md`
- **International installation commands** added to README with language-specific examples
- **Global keyword support** in plugin metadata for better discoverability

### Fixed

- **Simplified Chinese script localization** — All scripts now properly display Chinese messages instead of English
- **Arabic template consistency** — Template and scripts now use consistent Arabic phase headers (`### المرحلة`) and state labels (`**الحالة:**`)
- **Spanish template consistency** — Template and scripts now use consistent Spanish state labels (`**Estado:**`)
- **Stop hook path corrections** — All language variants now use correct paths in Stop hooks

## [2.32.0] - 2026-04-08

### Added

- **Codex session catchup** (PR #124 by @ebrevdo) — `session-catchup.py` now reads Codex rollout JSONL from `~/.codex/sessions`, prefers `CODEX_THREAD_ID` when skipping the current thread, filters subagent and tiny sessions, and detects planning-file updates from structured Codex `patch_apply_end` events
- **Loaditout security badge** (PR #126, closes #123) — Added A-grade security badge to README (top 20.5% of 20,000+ MCP servers scanned)

### Fixed

- **Stop hook fails on Windows Git Bash (MSYS2)** (PR #126, closes #125)
  - Root cause: MSYS2 treats bare `SD="/c/Users/..."` as a command to execute rather than a variable assignment
  - Fix: changed `SD="..."` to `export SD="..."` across all 9 SKILL.md variants (Claude Code, Codex, CodeBuddy, Cursor, Factory, Gemini, Mastra Code, OpenCode, + zh/zht)

### Changed

- Version bumped to 2.32.0 across all 12 SKILL.md files, plugin.json, marketplace.json, and CITATION.cff

### Thanks

- @ebrevdo (Eugene Brevdo) for the Codex session catchup rewrite (PR #124)

## [2.29.0] - 2026-03-24

### Added

- **Analytics workflow template** (PR #115 by @mvanhorn, addresses #103)
  - New `--template analytics` flag on `init-session.sh` and `init-session.ps1`
  - `templates/analytics_task_plan.md` with 4 analytics-specific phases: Data Discovery, Exploratory Analysis, Hypothesis Testing, Synthesis
  - `templates/analytics_findings.md` with Data Sources table, Hypothesis Log, Query Results, and Statistical Findings sections
  - Analytics-specific `progress.md` generates a Query Log table instead of Test Results
  - Default behavior unchanged; existing users are not affected

### Usage

```bash
./scripts/init-session.sh --template analytics my-project
```

### Thanks

- @mvanhorn (Matt Van Horn) for implementing the analytics template that @sedlukha requested in #103

---

## [2.28.0] - 2026-03-22

### Added

- **Traditional Chinese (zh-TW) skill variant** (PR #113 by @waynelee2048)
  - Fully translated SKILL.md, templates, and scripts under `skills/planning-with-files-zht/`
  - Localized hooks, check-complete, init-session, and session-catchup scripts

### Thanks

- @waynelee2048 for the Traditional Chinese translation

---

## [2.27.0] - 2026-03-20

### Added

- **Kiro Agent Skill support** (PR #112 by @EListenX)
  - Full `.kiro/skills/planning-with-files/` layout with SKILL.md, bootstrap scripts, templates, references
  - Bootstrap creates `.kiro/plan/` for planning files and `.kiro/steering/planning-context.md` with `#[[file:]]` live references
  - Includes session-catchup.py and check-complete scripts adapted for Kiro's `.kiro/plan/` path
  - Replaces the old `.kiro/scripts/` and `.kiro/steering/` approach with proper Agent Skill format

### Changed

- Updated `scripts/sync-ide-folders.py` to skip `.kiro` (Kiro uses its own skill layout)
- Rewrote `docs/kiro.md` to reflect new Agent Skill approach

### Thanks

- @EListenX (Yi Chenxi) for the thorough Kiro integration with proper Agent Skill format

---

## [2.23.0] - 2026-03-16

### Fixed

- **Session catchup not working after `/clear`** (Issue #106 by @tony-stark-eth)
  - Root cause: No hook fired on session start to remind the agent about existing planning files. After `/clear`, the agent started fresh with no awareness of the active plan.
  - Added `UserPromptSubmit` hook across all 7 IDE SKILL.md files. When `task_plan.md` exists, the hook injects a directive to read all three planning files before proceeding. This fires on every user message, ensuring the agent always knows about active plans even after `/clear` or context compaction.
  - Strengthened SKILL.md "FIRST" section: now explicitly says to read all three files immediately, not just run session catchup.

- **Progress not updating consistently** (Issue #106)
  - Root cause: `PostToolUse` hook message only mentioned `task_plan.md`, never `progress.md`. The agent was never reminded to log what it did.
  - Changed PostToolUse message across all 7 IDE SKILL.md files and both Copilot hook scripts to lead with "Update progress.md with what you just did."
  - Added `if [ -f task_plan.md ]` guard so the reminder only fires when a plan is active.

- **Post-plan additions not tracked** (Issue #106)
  - Root cause: When all phases were complete, `check-complete` scripts reported "ALL PHASES COMPLETE" with no guidance about continuing. The agent had no reason to add new work to the plan.
  - Updated `check-complete.sh` and `check-complete.ps1`: completion message now says "If the user has additional work, add new phases to task_plan.md before starting."
  - Updated Copilot `agent-stop` scripts to output continuation context even when all phases are complete (previously returned empty `{}`).
  - Added Critical Rule #7 ("Continue After Completion") to canonical SKILL.md body.

### Changed

- Version bumped to 2.23.0 across all 7 IDE SKILL.md files, plugin.json, and marketplace.json

### Thanks

- @tony-stark-eth for the detailed bug report covering all three symptoms (Issue #106)

---

## [2.22.0] - 2026-03-06

### Added

- **Formal benchmark results** — skill evaluated using Anthropic's skill-creator framework
  - 10 parallel subagents, 5 diverse task types, 30 objectively verifiable assertions
  - with_skill: **96.7% pass rate** (29/30); without_skill: 6.7% (2/30) — delta: +90 percentage points
  - 3 blind A/B comparisons: with_skill wins 3/3 (100%), avg score 10.0/10 vs 6.8/10
  - Full methodology in [docs/evals.md](docs/evals.md)
- **Technical article** — [docs/article.md](docs/article.md): full write-up of the security analysis, fix, and eval methodology
- **README badges** — Benchmark (96.7% pass rate), A/B Verified (3/3 wins), Security Verified
- **README Benchmark Results section** — key numbers visible at a glance

### Changed

- `marketplace.json` version corrected to track current release (was stuck at 2.0.0)

## [2.21.0] - 2026-03-05

### Security

- **Remove `WebFetch` and `WebSearch` from `allowed-tools`** — fixes Gen Agent Trust Hub FAIL and reduces Snyk W011 risk score
  - The planning-with-files skill is a file-management and planning skill; web access is not part of its core scope
  - The PreToolUse hook re-reads `task_plan.md` before every tool call, creating an amplification vector when web-sourced content is written to plan files. Removing these tools from the skill's declared scope breaks the toxic flow
  - Applied across all 7 IDE variants that declared `allowed-tools`: Claude Code, Cursor, Kilocode, CodeBuddy, Codex, OpenCode, Mastra Code
- **Add Security Boundary section to SKILL.md** — explicit guidance that web/search results must go to `findings.md` only (not `task_plan.md`), and all external content must be treated as untrusted
- **Add security note to examples.md** — the web research example now includes an inline comment reinforcing the trust boundary

## [2.20.0] - 2026-03-04

### Fixed

- **Codex session-catchup silent failure** (PR #100 by @tt-a1i, fixes #94)
  - `session-catchup.py` in the Codex variant was silently scanning `~/.claude/projects` even when running from a Codex context, where sessions live under `~/.codex/sessions` in a different format
  - Now detects the Codex runtime from `__file__` path and prints a clear fallback message instead of a silent no-op

- **Docs broken links** (PR #99 by @tt-a1i, fixes #95)
  - `docs/opencode.md` linked to `.opencode/INSTALL.md` which does not exist — corrected to `docs/installation.md`
  - `docs/factory.md` See Also links used `../skills/planning-with-files/` paths — corrected to `../.factory/skills/planning-with-files/`

- **Examples used stale `notes.md` filename** (PR #99 by @tt-a1i, fixes #96)
  - All `examples.md` files across 16 IDE copies referenced `notes.md` which was renamed to `findings.md` — updated consistently everywhere

- **`sync-ide-folders.py --help` ran a sync instead of printing usage** (PR #99 by @tt-a1i, fixes #98)
  - Replaced manual `sys.argv` parsing with `argparse` — `--help` now exits cleanly with usage information

### Changed

- **OpenCode README support label corrected** (PR #99 by @tt-a1i, fixes #97)
  - Changed from `Full Support` to `Partial Support` with a note about session catchup limitations — aligns README with what `docs/opencode.md` actually says

### Thanks

- @tt-a1i for the full consistency sweep (PR #99, PR #100)

---

## [2.19.0] - 2026-03-04

### Fixed

- **Codex Advanced Topics broken links** (PR #92 by @tt-a1i, fixes #91)
  - Corrected two dead links in `.codex/skills/planning-with-files/SKILL.md`
  - `reference.md` → `references/reference.md`
  - `examples.md` → `references/examples.md`

### Thanks

- @tt-a1i for identifying and fixing the broken Codex links (PR #92)

---

## [2.18.3] - 2026-02-28

### Fixed

- **Stop hook multiline YAML command fails under Git Bash on Windows** (PR #86 by @raykuo998)
  - Root cause: YAML `command: |` multiline blocks are not reliably parsed by Git Bash on Windows. The shell received the first line (`SCRIPT_DIR=...`) as a command name rather than a variable assignment, crashing the hook before it could do anything.
  - Replaced 25-line OS detection scripts with a single-line implicit platform fallback chain: `powershell.exe` first, `sh` as fallback. Applied to all 7 SKILL.md variants with Stop hooks.
  - Added `-NoProfile` to PowerShell invocation for faster startup

- **`check-complete.ps1` completely failing on PowerShell 5.1** (PR #88 by @raykuo998)
  - Root cause: Special characters inside double-quoted `Write-Host` strings (`[`, `(`, em-dash) caused parse errors in Windows PowerShell 5.1
  - Replaced double-quoted strings with single-quoted strings plus explicit concatenation for variable interpolation. Applied to all 12 platform copies.

### Thanks

- @raykuo998 for both Windows compatibility fixes (PR #86, PR #88)

---

## [2.18.2] - 2026-02-26

### Fixed

- **Mastra Code hooks were silently doing nothing**
  - Root cause: Mastra Code reads hooks from `.mastracode/hooks.json`, not from SKILL.md frontmatter. The existing integration had hooks defined only in SKILL.md (Claude Code format), which Mastra Code ignores entirely. All three hooks (PreToolUse, PostToolUse, Stop) were non-functional.
  - Added `.mastracode/hooks.json` with proper Mastra Code format including `matcher`, `timeout`, and `description` fields
  - Fixed `MASTRACODE_SKILL_ROOT` env var in SKILL.md Stop hook (variable does not exist in Mastra Code, replaced with `$HOME` fallback to local path)
  - Bumped `.mastracode/skills/planning-with-files/SKILL.md` metadata version from 2.16.1 to 2.18.1
  - Corrected `docs/mastra.md` to accurately describe hooks.json (removed false claim that Mastra Code uses the same hook system as Claude Code)
  - Fixed personal installation instructions to include hooks.json copy step

---

## [2.18.1] - 2026-02-26

### Fixed

- **Copilot hooks garbled characters — still broken after v2.16.1** (Issue #82, confirmed by @Hexiaopi)
  - Root cause: `Get-Content` in all PS1 scripts had no `-Encoding` parameter — PowerShell 5.x reads files using the system ANSI code page (Windows-1252) by default, corrupting any non-ASCII character in `task_plan.md` or `SKILL.md` before it reaches the output pipe. The v2.16.1 fix was correct but fixed only the output side, not the read side.
  - Secondary fix: `[System.Text.Encoding]::UTF8` returns UTF-8 with BOM — replaced with `[System.Text.UTF8Encoding]::new($false)` (UTF-8 without BOM) in all four PS1 scripts to prevent JSON parsers from receiving a stray `0xEF 0xBB 0xBF` preamble
  - Fixed files: `pre-tool-use.ps1`, `session-start.ps1`, `agent-stop.ps1`, `post-tool-use.ps1`
  - Bash scripts were already correct from v2.16.1

### Thanks

- @Hexiaopi for confirming the issue persisted after v2.16.1 (Issue #82)

---

## [2.18.0] - 2026-02-26

### Added

- **BoxLite sandbox runtime integration** (Issue #84 by @DorianZheng)
  - New `docs/boxlite.md` guide for running planning-with-files inside BoxLite micro-VM sandboxes via ClaudeBox
  - New `examples/boxlite/quickstart.py` — working Python example using ClaudeBox's Skill API to inject planning-with-files into a VM
  - New `examples/boxlite/README.md` — example context and requirements
  - README: new "Sandbox Runtimes" section (BoxLite is infrastructure, not an IDE — kept separate from the 16-platform IDE table)
  - README: BoxLite badge and Documentation table entry added
  - BoxLite loads via ClaudeBox (`pip install claudebox`) using its Python Skill object — no `.boxlite/` folder needed

### Thanks

- @DorianZheng for the BoxLite integration proposal (Issue #84)

---

## [2.17.0] - 2026-02-25

### Added

- **Mastra Code support** — new `.mastracode/skills/planning-with-files/` integration with native hooks (PreToolUse, PostToolUse, Stop), full scripts, templates, and installation guide (platform #16)

### Fixed

- **Skill metadata spec compliance** — applied PR #83 fixes across all 12 IDE-specific SKILL.md files:
  - `allowed-tools` YAML list → comma-separated string (Codex, Cursor, Kilocode, CodeBuddy, OpenCode)
  - `version` moved from top-level to `metadata.version` across all applicable files
  - Description updated with trigger terms ("plan out", "break down", "organize", "track progress") in all IDEs
  - Version bumped to 2.16.1 everywhere, including canonical `skills/planning-with-files/SKILL.md`
  - OpenClaw inline JSON metadata expanded to proper block YAML

### Thanks

- @popey for the PR #83 spec fixes that identified the issues

---

## [2.16.1] - 2026-02-25

### Fixed

- **Copilot hooks garbled characters on Windows** (Issue #82, reported by @Hexiaopi)
  - PowerShell scripts now set `$OutputEncoding` and `[Console]::OutputEncoding` to UTF-8 before any output — fixes garbled diamond characters (◆) caused by PowerShell 5.x defaulting to UTF-16LE stdout
  - Bash scripts now use `json.dumps(..., ensure_ascii=False)` — preserves UTF-8 characters (emojis, accented letters, CJK) in `task_plan.md` instead of converting them to raw `XXXX` escape sequences

### Thanks

- @Hexiaopi for reporting the garbled characters issue (Issue #82)

---

## [2.16.0] - 2026-02-22

### Added

- **GitHub Copilot Support** (PR #80 by @lincolnwan)
  - Native GitHub Copilot hooks integration (early 2026 hooks feature)
  - Created `.github/hooks/planning-with-files.json` configuration
  - Added full hook scripts in `.github/hooks/scripts/`
  - Cross-platform support (bash + PowerShell)
  - Added `docs/copilot.md` installation guide
  - Added GitHub Copilot badge to README
  - This brings total supported platforms to 15

### Thanks

- @lincolnwan for GitHub Copilot hooks support (PR #80)

---

## [2.14.0] - 2026-02-04

### Added

- **Pi Agent Support** (PR #67 by @ttttmr)
  - Full Pi Agent (pi.dev) integration
  - Created `.pi/skills/planning-with-files/` skill bundle
  - Added `package.json` for NPM installation (`pi install npm:pi-planning-with-files`)
  - Full templates, scripts, and references included
  - Cross-platform support (macOS, Linux, Windows)
  - Added `docs/pi-agent.md` installation guide
  - Added Pi Agent badge to README
  - Note: Hooks are Claude Code-specific and not supported in Pi Agent

### Fixed

- **Codex Skill Path References** (PR #66 by @codelyc)
  - Replaced broken `CLAUDE_PLUGIN_ROOT` references with correct Codex paths (`~/.codex/skills/planning-with-files/`)
  - Added missing template files to `.codex/skills/planning-with-files/templates/`

### Changed

- **OpenClaw Docs Update** (PR #65 by @AZLabsAI, fixes #64)
  - Renamed `docs/moltbot.md` to `docs/openclaw.md`
  - Updated all paths from `~/.clawdbot/` to `~/.openclaw/`
  - Updated CLI commands from `moltbot` to `openclaw`
  - Updated website link from `molt.bot` to `openclaw.ai`
- Updated README: Moltbot badge and references updated to OpenClaw
- Version badge updated to v2.14.0

### Thanks

- @ttttmr for Pi Agent integration (PR #67)
- @codelyc for Codex path fix (PR #66)
- @AZLabsAI for OpenClaw docs update (PR #65)

---

## [2.11.0] - 2026-01-26

### Added

- **`/plan` Command for Easier Autocomplete** (Issue #39)
  - Added `commands/plan.md` creating `/planning-with-files:plan` command
  - Users can now type `/plan` and see the command in autocomplete
  - Shorter alternative to `/planning-with-files:start`
  - Works immediately after plugin installation - no extra setup required

### Usage

After installing the plugin, you have two command options:

| Command | How to Find | Works Since |
|---------|-------------|-------------|
| `/planning-with-files:plan` | Type `/plan` | v2.11.0 |
| `/planning-with-files:start` | Type `/planning` | v2.6.0 |

### Thanks

- @wqh17101 for persistent reminders in Discussion #36
- @dalisoft, @zoffyzhang, @yyuziyu for feedback and workarounds in Issue #39
- Community for patience while we found the right solution

---

## [2.10.0] - 2026-01-26

### Added

- **Kiro Support** (Issue #55 by @453783374)
  - Native Kiro steering files integration
  - Created `.kiro/steering/` with planning workflow, rules, and templates
  - Added helper scripts in `.kiro/scripts/`
  - Added `docs/kiro.md` installation guide
  - Added Kiro badge to README

### Note

Kiro uses **Steering Files** (`.kiro/steering/*.md`) instead of the standard `SKILL.md` format. The steering files are automatically loaded by Kiro in every interaction.

---

## [2.9.0] - 2026-01-26

### Added

- **Moltbot Support** (formerly Clawd CLI)
  - Added Moltbot integration for workspace and local skills
  - Created `.moltbot/skills/planning-with-files/` skill bundle
  - Full templates, scripts, and references included
  - Cross-platform support (macOS, Linux, Windows)
  - Added `docs/moltbot.md` installation guide
  - Added Moltbot badge to README

### Changed

- Updated plugin.json description to highlight multi-IDE support
- Added new keywords: moltbot, gemini, cursor, continue, multi-ide, agent-skills
- Now supports 10+ AI coding assistants

---

## [2.8.0] - 2026-01-26

### Added

- **Continue IDE Support** (PR #56 by @murphyXu)
  - Added Continue.dev integration for VS Code and JetBrains IDEs
  - Created `.continue/skills/planning-with-files/` skill bundle
  - Created `.continue/prompts/planning-with-files.prompt` slash command (Chinese)
  - Added `docs/continue.md` installation guide
  - Added `scripts/check-continue.sh` validator
  - Full templates, scripts, and references included

### Fixed

- **POSIX sh Compatibility** (PR #57 by @SaladDay)
  - Fixed Stop hook failures on Debian/Ubuntu systems using dash as `/bin/sh`
  - Replaced bash-only syntax (`[[`, `&>`) with POSIX-compliant constructs
  - Added shell-agnostic Windows detection using `uname -s` and `$OS`
  - Applied fix to all 5 IDE-specific SKILL.md files
  - Addresses issue reported by @aqlkzf in #32

### Thanks

- @murphyXu for Continue IDE integration (PR #56)
- @SaladDay for POSIX sh compatibility fix (PR #57)

---

## [2.7.1] - 2026-01-22

### Fixed

- **Dynamic Python Command Detection** (Issue #41 by @wqh17101)
  - Replaced hardcoded `python3` with dynamic detection: `$(command -v python3 || command -v python)`
  - Added Windows PowerShell commands using `python` directly
  - Fixed in all 5 IDE-specific SKILL.md files (Claude Code, Codex, Cursor, Kilocode, OpenCode)
  - Resolves compatibility issues on Windows/Anaconda where only `python` exists

### Thanks

- @wqh17101 for reporting and suggesting the fix (Issue #41)

---

## [2.7.0] - 2026-01-22

### Added

- **Gemini CLI Support** (Issue #52)
  - Native Agent Skills support for Google Gemini CLI v0.23+
  - Created `.gemini/skills/planning-with-files/` directory structure
  - SKILL.md formatted for Gemini CLI compatibility
  - Full templates, scripts, and references included
  - Added `docs/gemini.md` installation guide
  - Added Gemini CLI badge to README

### Documentation

- Updated README with Gemini CLI in supported IDEs table
- Updated file structure diagram
- Added Gemini CLI to documentation table

### Thanks

- @airclear for requesting Gemini CLI support (Issue #52)

---

## [2.6.0] - 2026-01-22

### Added

- **Start Command** (PR #51 by @Guozihong)
  - New `/planning-with-files:start` command for easier activation
  - No longer requires copying skills to `~/.claude/skills/` folder
  - Works directly after plugin installation
  - Added `commands/start.md` file

### Fixed

- **Stop Hook Path Resolution** (PR #49 by @fahmyelraie)
  - Fixed "No such file or directory" error when `CLAUDE_PLUGIN_ROOT` is not set
  - Added fallback path: `$HOME/.claude/plugins/planning-with-files/scripts`
  - Made `check-complete.sh` executable (chmod +x)
  - Applied fix to all IDE-specific SKILL.md files (Codex, Cursor, Kilocode, OpenCode)

### Thanks

- @fahmyelraie for the path resolution fix (PR #49)
- @Guozihong for the start command feature (PR #51)

---

## [2.4.0] - 2026-01-20

### Fixed

- **CRITICAL: Fixed SKILL.md frontmatter to comply with official Agent Skills spec** (Issue #39)
  - Removed invalid `hooks:` field from SKILL.md frontmatter (not supported by spec)
  - Removed invalid top-level `version:` field (moved to `metadata.version`)
  - Removed `user-invocable:` field (not in official spec)
  - Changed `allowed-tools:` from YAML list to space-delimited string per spec
  - This fixes `/planning-with-files` slash command not appearing for users

### Changed

- SKILL.md frontmatter now follows [Agent Skills Specification](https://agentskills.io/specification)
- Version now stored in `metadata.version` field
- Removed `${CLAUDE_PLUGIN_ROOT}` variable references from SKILL.md (use relative paths)
- Updated plugin.json to v2.4.0

### Technical Details

The previous SKILL.md used non-standard frontmatter fields:
```yaml
# OLD (broken)
version: "2.3.0"           # NOT supported at top level
user-invocable: true       # NOT in official spec
hooks:                     # NOT supported in SKILL.md
  PreToolUse: ...
```

Now uses spec-compliant format:
```yaml
# NEW (fixed)
name: planning-with-files
description: ...
license: MIT
metadata:
  version: "2.4.0"
  author: OthmanAdi
allowed-tools: Read Write Edit Bash Glob Grep WebFetch WebSearch
```

### Thanks

- @wqh17101 for identifying the issue in #39
- @dalisoft and @zoffyzhang for reporting the problem

## [2.3.0] - 2026-01-17

### Added

- **Codex IDE Support**
  - Created `.codex/INSTALL.md` with installation instructions
  - Skills install to `~/.codex/skills/planning-with-files/`
  - Works with obra/superpowers or standalone
  - Added `docs/codex.md` for user documentation
  - Based on analysis of obra/superpowers Codex implementation

- **OpenCode IDE Support** (Issue #27)
  - Created `.opencode/INSTALL.md` with installation instructions
  - Global installation: `~/.config/opencode/skills/planning-with-files/`
  - Project installation: `.opencode/skills/planning-with-files/`
  - Works with obra/superpowers plugin or standalone
  - oh-my-opencode compatibility documented
  - Added `docs/opencode.md` for user documentation
  - Based on analysis of obra/superpowers OpenCode plugin

### Changed

- Updated README.md with Supported IDEs table
- Updated README.md file structure diagram
- Updated docs/installation.md with Codex and OpenCode sections
- Version bump to 2.3.0

### Documentation

- Added Codex and OpenCode to IDE support table in README
- Created comprehensive installation guides for both IDEs
- Documented skill priority system for OpenCode
- Documented integration with superpowers ecosystem

### Research

This implementation is based on real analysis of:
- [obra/superpowers](https://github.com/obra/superpowers) repository
- Codex skill system and CLI architecture
- OpenCode plugin system and skill resolution
- Skill priority and override mechanisms

### Thanks

- @Realtyxxx for feedback on Issue #27 about OpenCode support
- obra for the superpowers reference implementation

---

## [2.2.2] - 2026-01-17

### Fixed

- **Restored Skill Activation Language** (PR #34)
  - Restored the activation trigger in SKILL.md description
  - Description now includes: "Use when starting complex multi-step tasks, research projects, or any task requiring >5 tool calls"
  - This language was accidentally removed during the v2.2.1 merge
  - Helps Claude auto-activate the skill when detecting appropriate tasks

### Changed

- Updated version to 2.2.2 in all SKILL.md files and plugin.json

### Thanks

- Community members for catching this issue

---

## [2.2.1] - 2026-01-17

### Added

- **Session Recovery Feature** (PR #33 by @lasmarois)
  - Automatically detect and recover unsynced work from previous sessions after `/clear`
  - New `scripts/session-catchup.py` analyzes previous session JSONL files
  - Finds last planning file update and extracts conversation that happened after
  - Recovery triggered automatically when invoking `/planning-with-files`
  - Pure Python stdlib implementation, no external dependencies

- **PreToolUse Hook Enhancement**
  - Now triggers on Read/Glob/Grep in addition to Write/Edit/Bash
  - Keeps task_plan.md in attention during research/exploration phases
  - Better context management throughout workflow

### Changed

- SKILL.md restructured with session recovery as first instruction
- Description updated to mention session recovery feature
- README updated with session recovery workflow and instructions

### Documentation

- Added "Session Recovery" section to README
- Documented optimal workflow for context window management
- Instructions for disabling auto-compact in Claude Code settings

### Thanks

Special thanks to:
- @lasmarois for session recovery implementation (PR #33)
- Community members for testing and feedback

---

## [2.2.0] - 2026-01-17

### Added

- **Kilo Code Support** (PR #30 by @aimasteracc)
  - Added Kilo Code IDE compatibility for the planning-with-files skill
  - Created `.kilocode/rules/planning-with-files.md` with IDE-specific rules
  - Added `docs/kilocode.md` comprehensive documentation for Kilo Code users
  - Enables seamless integration with Kilo Code's planning workflow

- **Windows PowerShell Support** (Fixes #32, #25)
  - Created `check-complete.ps1` - PowerShell equivalent of bash script
  - Created `init-session.ps1` - PowerShell session initialization
  - Scripts available in all three locations (root, plugin, skills)
  - OS-aware hook execution with automatic fallback
  - Improves Windows user experience with native PowerShell support

- **CONTRIBUTORS.md**
  - Recognizes all community contributors
  - Lists code contributors with their impact
  - Acknowledges issue reporters and testers
  - Documents community forks

### Fixed

- **Stop Hook Windows Compatibility** (Fixes #32)
  - Hook now detects Windows environment automatically
  - Uses PowerShell scripts on Windows, bash on Unix/Linux/Mac
  - Graceful fallback if PowerShell not available
  - Tested on Windows 11 PowerShell and Git Bash

- **Script Path Resolution** (Fixes #25)
  - Improved `${CLAUDE_PLUGIN_ROOT}` handling across platforms
  - Scripts now work regardless of installation method
  - Added error handling for missing scripts

### Changed

- **SKILL.md Hook Configuration**
  - Stop hook now uses multi-line command with OS detection
  - Supports pwsh (PowerShell Core), powershell (Windows PowerShell), and bash
  - Automatic fallback chain for maximum compatibility

- **Documentation Updates**
  - Updated to support both Claude Code and Kilo Code environments
  - Enhanced template compatibility across different AI coding assistants
  - Updated `.gitignore` to include `findings.md` and `progress.md`

### Files Added

- `.kilocode/rules/planning-with-files.md` - Kilo Code IDE rules
- `docs/kilocode.md` - Kilo Code-specific documentation
- `scripts/check-complete.ps1` - PowerShell completion check (root level)
- `scripts/init-session.ps1` - PowerShell session init (root level)
- `planning-with-files/scripts/check-complete.ps1` - PowerShell (plugin level)
- `planning-with-files/scripts/init-session.ps1` - PowerShell (plugin level)
- `skills/planning-with-files/scripts/check-complete.ps1` - PowerShell (skills level)
- `skills/planning-with-files/scripts/init-session.ps1` - PowerShell (skills level)
- `CONTRIBUTORS.md` - Community contributor recognition
- `COMPREHENSIVE_ISSUE_ANALYSIS.md` - Detailed issue research and solutions

### Documentation

- Added Windows troubleshooting guidance
- Recognized community contributors in CONTRIBUTORS.md
- Updated README to reflect Windows and Kilo Code support

### Thanks

Special thanks to:
- @aimasteracc for Kilo Code support and PowerShell script contribution (PR #30)
- @mtuwei for reporting Windows compatibility issues (#32)
- All community members who tested and provided feedback

  - Root cause: `${CLAUDE_PLUGIN_ROOT}` resolves to repo root, but templates were only in subfolders
  - Added `templates/` and `scripts/` directories at repo root level
  - Now templates are accessible regardless of how `CLAUDE_PLUGIN_ROOT` resolves
  - Works for both plugin installs and manual installs

### Structure

After this fix, templates exist in THREE locations for maximum compatibility:
- `templates/` - At repo root (for `${CLAUDE_PLUGIN_ROOT}/templates/`)
- `planning-with-files/templates/` - For plugin marketplace installs
- `skills/planning-with-files/templates/` - For legacy `~/.claude/skills/` installs

### Workaround for Existing Users

If you still experience issues after updating:
1. Uninstall: `/plugin uninstall planning-with-files@planning-with-files`
2. Reinstall: `/plugin marketplace add OthmanAdi/planning-with-files`
3. Install: `/plugin install planning-with-files@planning-with-files`

---

## [2.1.1] - 2026-01-10

### Fixed

- **Plugin Template Path Issue** (Fixes #15)
  - Templates weren't found when installed via plugin marketplace
  - Plugin cache expected `planning-with-files/templates/` at repo root
  - Added `planning-with-files/` folder at root level for plugin installs
  - Kept `skills/planning-with-files/` for legacy `~/.claude/skills/` installs

### Structure

- `planning-with-files/` - For plugin marketplace installs
- `skills/planning-with-files/` - For manual `~/.claude/skills/` installs

---

## [2.1.0] - 2026-01-10

### Added

- **Claude Code v2.1 Compatibility**
  - Updated skill to leverage all new Claude Code v2.1 features
  - Requires Claude Code v2.1.0 or later

- **`user-invocable: true` Frontmatter**
  - Skill now appears in slash command menu
  - Users can manually invoke with `/planning-with-files`
  - Auto-detection still works as before

- **`SessionStart` Hook**
  - Notifies user when skill is loaded and ready
  - Displays message at session start confirming skill availability

- **`PostToolUse` Hook**
  - Runs after every Write/Edit operation
  - Reminds Claude to update `task_plan.md` if a phase was completed
  - Helps prevent forgotten status updates

- **YAML List Format for `allowed-tools`**
  - Migrated from comma-separated string to YAML list syntax
  - Cleaner, more maintainable frontmatter
  - Follows Claude Code v2.1 best practices

### Changed

- Version bumped to 2.1.0 in SKILL.md, plugin.json, and README.md
- README.md updated with v2.1.0 features section
- Versions table updated to reflect new release

### Compatibility

- **Minimum Claude Code Version:** v2.1.0
- **Backward Compatible:** Yes (works with older Claude Code, but new hooks may not fire)

## [2.0.1] - 2026-01-09

### Fixed

- Planning files now correctly created in project directory, not skill installation folder
- Added "Important: Where Files Go" section to SKILL.md
- Added Troubleshooting section to README.md

### Thanks

- @wqh17101 for reporting and confirming the fix

## [2.0.0] - 2026-01-08

### Added

- **Hooks Integration** (Claude Code 2.1.0+)
  - `PreToolUse` hook: Automatically reads `task_plan.md` before Write/Edit/Bash operations
  - `Stop` hook: Verifies all phases are complete before stopping
  - Implements Manus "attention manipulation" principle automatically

- **Templates Directory**
  - `templates/task_plan.md` - Structured phase tracking template
  - `templates/findings.md` - Research and discovery storage template
  - `templates/progress.md` - Session logging with test results template

- **Scripts Directory**
  - `scripts/init-session.sh` - Initialize all planning files at once
  - `scripts/check-complete.sh` - Verify all phases are complete

- **New Documentation**
  - `CHANGELOG.md` - This file

- **Enhanced SKILL.md**
  - The 2-Action Rule (save findings after every 2 view/browser operations)
  - The 3-Strike Error Protocol (structured error recovery)
  - Read vs Write Decision Matrix
  - The 5-Question Reboot Test

- **Expanded reference.md**
  - The 3 Context Engineering Strategies (Reduction, Isolation, Offloading)
  - The 7-Step Agent Loop diagram
  - Critical constraints section
  - Updated Manus statistics

### Changed

- SKILL.md restructured for progressive disclosure (<500 lines)
- Version bumped to 2.0.0 in all manifests
- README.md reorganized (Thank You section moved to top)
- Description updated to mention >5 tool calls threshold

### Preserved

- All v1.0.0 content available in `legacy` branch
- Original examples.md retained (proven patterns)
- Core 3-file pattern unchanged
- MIT License unchanged

## [1.0.0] - 2026-01-07

### Added

- Initial release
- SKILL.md with core workflow
- reference.md with 6 Manus principles
- examples.md with 4 real-world examples
- Plugin structure for Claude Code marketplace
- README.md with installation instructions

---

## Versioning

This project follows [Semantic Versioning](https://semver.org/):
- MAJOR: Breaking changes to skill behavior
- MINOR: New features, backward compatible
- PATCH: Bug fixes, documentation updates
