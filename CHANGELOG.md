# Changelog

All notable changes to this project will be documented in this file.

## [3.10.0] - 2026-08-07

### Changed

- **BREAKING: removed the `-ar`/`-de`/`-es`/`-zh`/`-zht` language-variant skills (closes #130).** The plugin registered 6 separate skills purely to vary the natural-language prose in `SKILL.md`, when the assistant already responds in the user's language regardless of the skill's source language. Worse, the 5 variants had quietly drifted out of feature parity with the canonical skill: they were missing 12 script files (`attest-plan`, `gate-stop`, `ledger-append`, `ledger-summary.ps1`, `phase-status`, `plan-doctor`, `resolve-plan-dir.ps1`, `set-active-plan`) and the v3.2.0 fix for a Windows encoding bug in `session-catchup.py`, so non-English users on Windows were still exposed to a bug English users had fixed under them. `skills/planning-with-files-{ar,de,es,zh,zht}/` are gone; only `skills/planning-with-files/` remains.
- **`/plan-ar`, `/plan-de`, `/plan-es`, `/plan-zh`, and `/plan-zht` are unaffected** — they now invoke the single canonical skill directly with an inline instruction to plan and respond in that language, instead of invoking a dedicated skill. Everyone using these commands keeps the same experience.
- If you installed a language skill directly by its id (e.g. `npx skills add OthmanAdi/planning-with-files --skill planning-with-files-zht`) rather than through a `/plan-*` command, reinstall the base skill: `npx skills add OthmanAdi/planning-with-files --skill planning-with-files -g`.

## [3.9.0] - 2026-08-01

### Fixed
- **A Codex thread whose cwd was a shared parent injected an unrelated project's plan on every hook fire (closes #212, reported by @webwww123).** Plan resolution was cwd relative with no notion of a thread: `PLAN_ID`, then `.planning/.active_plan`, then the newest plan directory by mtime, every read relative to the process cwd. With `/workspace` holding one plan and `/workspace/project` holding the real one, the parent's pointer was the only pointer the hook could see, so the wrong plan arrived as high priority context on every prompt and every matched tool call, competing with the user's own corrections. Reproduced against the reporter's tree before any code changed: the parent's plan won on the canonical dispatcher and on the `.codex` Agent Skills route.
- **`PLANNING_DISABLED=1` did nothing on eleven of the thirteen hook bearing install routes.** The opt out from #195 lives in `scripts/inject-plan.sh`, and only the canonical and `.agents` SKILL.md dispatched to that script. The other eleven, the reporter's `.codex` route included, still carried the v2.43 hook body inlined in their YAML scalars. Besides missing the opt out they lacked the symlink containment guard, the SHA cache key fix, nonce delimiters, the v3 attestation refusal, the ledger summary and `PWF_INJECT=smart`, and they still wrote the SHA cache to the world writable `${TMPDIR:-/tmp}/pwf-sha` that moved to `$XDG_CACHE_HOME` in v3.0.0. All eleven now dispatch to the same versioned script.
- **The Stop hook could never find its script on Codex, Cursor, Factory, CodeBuddy, Mastra or OpenCode.** Those variants inherited a discovery list naming only `${CLAUDE_SKILL_DIR}` and two `$HOME/.claude/...` paths, none of which exists on those hosts, so completion checking silently did nothing.
- **Script discovery sorted its candidates instead of honoring their order.** `ls a b c | head -1` returns the alphabetically first hit, so a stale marketplace copy outranked the host native one. Discovery is now a first match wins loop.
- **A provider error made the Pi extension queue a new request (closes #211, reported by @killianMei).** `agent_end` never read its event, so a turn that ended with the provider returning an error was treated as a completed turn and got the normal auto continue follow up. That follow up started another request against the same failing provider, up to `AUTO_CONTINUE_LIMIT`, burying the original error and spending the user's retry budget. The handler now reads the trailing assistant message and returns on `stopReason` `error` or `aborted` before the counter is read or incremented. Verified against the published host packages at 0.80.3 and 0.82.1: there is no top level `stopReason`, so a guard reading one would have been undefined at runtime and would never have fired.
- **The Pi status bar stopped tracking the plan once execution was approved.** Every route to `ctx.ui.setStatus` sat on a pre approval or notify only path, so in `parity` and `cache-safe`, which `deriveEffectiveMode` selects for every non DeepSeek model, the bar kept whatever `session_start` wrote. The count is now published from `before_agent_start`, `tool_result`, `agent_end` and `session_before_compact` in every mode, including the all phases complete branch where the N/M to M/M transition reached the notification but never the bar. Bundled Pi extension 1.2.2 to 1.2.3.
- **Eight shipped PowerShell scripts could not be parsed by Windows PowerShell 5.1, so they silently did nothing on the default Windows shell.** `powershell.exe` reads a `.ps1` as ANSI unless the file carries a UTF-8 BOM, and the UTF-8 bytes for an em dash end in `0x94`, which CP1252 maps to a closing curly quote. That opens a string literal that never closes, and every dispatcher wraps its PowerShell call in fallbacks that swallow the parse error. Dead on Windows: the Cursor plan injection hook, both `.kiro` asset scripts, the Arabic `check-complete.ps1`, and `check-complete` plus `init-session` for both Chinese variants, which meant a Windows user of those variants could not create a plan at all. Every `.ps1` holding non-ASCII now carries a BOM.
- **Wall clock timestamps reached the model unnormalized on five routes** (raised in #210 by @GlitterKill): the Cursor hook and its PowerShell twin, the Codex hook, `.mastracode/hooks.json`, the Hermes plugin, and the Pi extension. The v2.40 normalization that keeps the injected `progress.md` tail stable had never been applied to any of them, because each builds its injection independently.
- **An attested plan under an absolute pin reported `[PLAN TAMPERED]` on every fire.** GNU `sha256sum` prefixes its output line with a backslash when the filename needs escaping, which any Windows style path triggers, so the parsed digest never matched the attestation.

### Added
- **`PWF_PLAN_ROOT`**, an absolute plan root binding. `PLAN_ID` is a cwd relative slug, so a thread sitting at a shared parent had no way to name a nested project's plan at all. `PWF_PLAN_ROOT=/workspace/project` pins the thread regardless of where its cwd sits. A pin that does not resolve fails closed with a notice rather than falling back to the ambiguous plan the caller was escaping. Supported by the canonical dispatcher, the Codex hook route, the Cursor hooks, and the shared resolver in both shell and PowerShell.
- **Session attachment on the SKILL.md routes**, matching the semantics the Codex adapter has carried since #146. With no `.planning/sessions/` directory present nothing changes. Honest limitation: nothing on those routes supplies a per thread `PWF_SESSION_ID`, so on hosts that never set it the guard can refuse but cannot bind.
- **Fail closed on an ambiguous cwd.** When the plan was chosen by the shared pointer or by the newest by mtime fallback rather than named explicitly, and a project directly below the root carries its own live plan, nothing is injected and the notice names both escape hatches. An explicit `PLAN_ID`, a `PWF_PLAN_ROOT` pin or an attached session stays authoritative and skips the check. Detection is one shell glob at depth one. A nested pointer that is empty or names a deleted directory does not count as competing, so an abandoned subproject cannot kill injection at the root.
- **`PWF_SCRIPT_DIR`**, an opt in override naming the skill's scripts directory, for workspace installs that no user level path can reach.
- An environment variable reference table in the README covering all seven knobs, several of which had never been documented anywhere.

### Changed
- Refusals are never silent. The session guard, the ambiguity refusal, a broken pin and a script that cannot be found each emit one line per turn naming the way out. Per tool call and precompact fires stay quiet so the notice cannot become spam. This came out of an adversarial pass: an earlier build of the session guard exited silently, which on any host that never sets `PWF_SESSION_ID` would have let a stale `.planning/sessions/` directory kill injection permanently with no symptom, and `.planning/` is gitignored so that state is invisible to review.
- `plan-doctor` reports a refusal as its own state with the remedy. It previously counted the refusal notice as bytes of plan context and printed PASS, so the one tool a dark user is pointed at gave a green light.
- `ledger-summary.sh` accepts the resolved plan directory as an argument, so a pinned autonomous run reports the pinned plan rather than the parent's phase counts. Without it a pinned loop could read `1/1 complete` while its own plan had an open phase. When no plan directory is determinable it now says so instead of reporting a confident `0/0 complete`.
- The skill text described per tool call re injection as "the +68% token tax measured in the v2.21 eval". That eval measured total tokens for a whole task with the skill against the same task without it, which is mostly the cost of writing three structured files. It never isolated recitation, and the wording now states the measured per call figure.

### Verification
- Suite 311 to 411 passing, 282 to 453 subtests, plus 48 Pi extension tests and `sync-ide-folders.py --verify` clean.
- Determinism is asserted rather than assumed: `inject-plan.sh` fired twice against an untouched fixture is byte identical in every context and every mode, including attested and autonomous. The suite proved this for the ledger summary and never for the injection script itself.
- New suites cover the nested project tree from #212 including a two thread case, injection determinism, PowerShell parseability under the real Windows interpreter, hook dispatch parity across every SKILL.md, the Codex and Cursor hook routes, and the resolver pin in both shell and PowerShell.
- The legacy invariant was verified by diffing old against new output for slug, legacy root and autonomous fixtures across all three contexts on every route touched.
- Built by Fable agents, reviewed by Opus, with a Sonnet fleet on recon and a four agent adversarial pass that returned a do not ship verdict on the first build. Four blockers, two of them introduced by the fix itself, were closed before release.

### Thanks
- webwww123 reported the shared cwd plan leak with a working reproduction, a correct reading of the resolution chain, and a fix list that shaped the order this shipped in (#212).
- killianMei traced the follow up amplification to the ignored `agent_end` event and the stale status bar to the exact handlers that never publish, with call sites (#211).
- GlitterKill asked whether plan injection breaks prompt caching, which turned up three more unnormalized routes, a token figure attached to the wrong measurement, and the Windows PowerShell parse failures (#210).

## [3.8.2] - 2026-07-24

### Fixed
- **Session recovery silently found nothing for any project path containing a dot, a space, or any other non-alphanumeric character (closes #209, reported by @seathatflowsinourveins).** Claude Code names `~/.claude/projects/` entries by folding every character outside `[A-Za-z0-9-]` to `-`, but three copies of `session-catchup.py` still used a manual replace chain that handled only `/`, `\` and `:`. Those copies computed a directory name Claude Code never writes, no candidate matched, and `main()` returned at the `exists()` check with exit 0, so catchup after `/clear` produced nothing and reported nothing. Hidden directories such as `~/.dotfiles` were the common case. One of the three sits on a live install route: `marketplace.json` declares `"source": "./"`, so the plugin root is the repository root and the SKILL.md restore block resolves `${CLAUDE_PLUGIN_ROOT}/scripts/session-catchup.py` for every plugin user on Linux, macOS or Git Bash. Measured against a real store holding 89 sessions, the shipped resolver produced 0 bytes where the fixed one produces 11336 and recovers 166 messages. The root, `.hermes` and `.mastracode` copies now share the same normalize, sanitize and candidate helpers as the canonical copy, keeping their existing function names, signatures and the `.mastracode` Codex guard (`tests/test_catchup_store_resolution_parity.py`).
- **An emoji in a folder name made a project unresolvable in every copy, including the canonical one.** Claude Code walks the directory name as UTF-16, so a non-BMP character costs two dashes, while the sanitizer counted codepoints and produced one. Folding is now counted in UTF-16 code units. The rules were measured against 24 real stores whose recorded `cwd` could be read: one model matches all 24, and it also showed that current versions fold `_` while older stores kept it, so both spellings stay in the probe chain and the exact spelling is still probed first.
- The 15 copies that already folded dots keep that behavior unchanged. `.kiro` is untouched because it ships a different program that reads `.kiro/plan/` and never looks at `~/.claude/projects`.

### Security
- **Two projects whose paths fold to the same `~/.claude/projects` name could read each other's transcripts.** The mapping is lossy, so `client.acme` and `client-acme` share one directory. Until this release the resolver did not fold those characters and simply missed the directory; folding the way Claude Code folds means it now finds it, so catchup filters transcripts by the `cwd` they record. A transcript is skipped only when it positively records a different project, transcripts that record none are kept because the field is not present in every generation of the format, and a directory whose transcripts all belong to another project is reported instead of used. The filter works per session rather than rejecting the whole directory, because in a collision both projects live there permanently and rejecting it would cost the project its own history. Reproduced with a planted canary against the preceding commit and again after the fix (`tests/test_catchup_cross_project_guard.py`).

### Verification
- Suite 305 to 311 passing, 282 subtests, plus `sync-ide-folders.py --verify` clean. The new parity suite discovers the copies with `git ls-files` and runs one vector table through each, so the drift that produced #209 fails the suite instead of hiding in a single file.

### Thanks
- seathatflowsinourveins reported the dot-folding mismatch with an exact blob reference, a working reproduction, and a correct reading of the silent return path (#209).

## [3.8.1] - 2026-07-21

### Fixed
- **Pi extension: plan resolution no longer depends on the live shell cwd (closes #208, reported by @fd44fdg).** The Pi session cwd follows the shell, so an agent that changed into a subdirectory lost the project's plan entirely: resolution found nothing, the recitation went dark, and the "No task_plan.md found" warning fired on every write and edit. Resolution now anchors on the nearest ancestor directory that carries planning state (`.planning/` or `task_plan.md`), bounded by a `.git` repository boundary and a depth cap so a plan outside the repository can never leak into a session. Explicit `PLAN_ID` pins keep working from any subdirectory. New vitest suite covers the walk, the boundary, and the preserved precedence (`__tests__/plan-anchor.test.ts`).
- **Pi extension: every injection now states which plan it resolved** (`plan: <id>` or `plan: root`). A stale `.planning/<id>/` directory shadows a root `task_plan.md` by documented precedence (slug beats root since v2.40.0); without a visible label that shadowing was silent and users debugged the wrong plan. The label makes it visible; `set-active-plan` or deleting the stale directory remains the cure.
- **`init-session` created plans without the v3.8.0 `## Next Step` section.** The scripts write plans from an inline heredoc, not from `templates/task_plan.md`, so the section shipped in the templates never reached created plans. All 26 heredoc copies (sh and PowerShell, canonical plus every mirror) now carry it, and a regression test asserts the created output rather than the template (`test_init_session_output_contains_next_step`).

### Security
- The Pi extension resolver reached slug-validation and containment parity with the sh resolver. A traversal `PLAN_ID` such as `../../outside` resolved a plan outside `.planning/` (the sh resolver already blocked it), slug-invalid `.active_plan` targets and directory names were accepted, and a scoped winner canonicalizing outside the project (a junctioned slug directory) was followed. All four now match the sh behavior: `SLUG_RE` on every branch, `realpathSync` containment fail-closed on the resolved winner. Found independently by the Opus verification pass and the Sonnet reliability fleet that gate this release.
- Every Pi runtime consumer that takes a directory (the session-attachment gate, project mode config, attest and catchup script working directories) now routes through the same anchor as plan resolution, and the injected plan label is sanitized to `[A-Za-z0-9._-]` capped at 64 characters.

### Thanks
- fd44fdg reported the Pi cwd resolution split-brain with a precise root-cause analysis (#208).

## [3.8.0] - 2026-07-21

### Fixed
- **The Stop hook never fired on macOS or Linux, and was a silent no-op on every platform when `CLAUDE_SKILL_DIR` was unset.** Two dispatch bugs stacked in the SKILL.md Stop scalar: the install-path fallback used a `:-` default that can never substitute (the probed variable is always a non-empty string even when the env var is unset), and the PowerShell branch was selected on every platform because `check-complete.ps1` ships everywhere, so `powershell.exe ... 2>/dev/null` swallowed the dispatch with a suppressed exit 127 wherever PowerShell is absent. Both the legacy completion advisory and the v3 completion gate were dead in those environments. The scalar now selects targets by file existence and dispatches by platform: PowerShell only under MINGW/MSYS/CYGWIN, `sh` elsewhere, with an explicit `exit 0`. Windows output is unchanged. Patched in all 14 SKILL.md variants that carry the scalar. New tests execute the scalar end to end on both CI legs instead of string-matching its shape (`tests/test_stop_hook_dispatch.py`).
- **session-catchup looked for a `~/.claude/projects/` directory that does not exist on macOS/Linux installs, nor for any project path containing an underscore.** Claude Code keeps underscores and the leading dash of POSIX absolute paths when naming session stores; the mapper replaced `_` with `-` and stripped the leading dash, so recovery after `/clear` silently found nothing in those cases. The mapper now probes the exact spelling first, keeps both legacy spellings as fallbacks for stores created by older versions, and settles ambiguity via the cwd recorded in the newest session file. Fixed in the canonical script and every shipped copy; the drifted older-generation copies (root `scripts/`, `.hermes`, `.mastracode`) received a targeted underscore fix preserving their shape (`tests/test_catchup_project_dir.py`).
- **A stale SHA-cache hit could report a false `[PLAN TAMPERED]` for a different project.** The attestation cache key was the relative plan path, so every legacy-root project on a machine shared one slot. The key now includes the absolute project root; the cache self-heals with one extra re-hash per plan after upgrade (`tests/test_inject_smart.py`).
- **`resolve-plan-dir.ps1` reached parity with the sh resolver.** The PowerShell mirror had no slug validation on any branch, its newest-dir scan could resolve a directory without `task_plan.md` (a `sessions/` dir could win), and containment failed open when canonicalization failed. All three now match the sh resolver, including fail-closed containment. A new sh-vs-ps1 parity suite runs the same fixture trees through both resolvers on both CI legs (`tests/test_resolver_parity.py`).
- **`ledger-append.sh` could write invalid UTF-8 into the run ledger.** The summary was truncated with `cut -c1-200`, which counts bytes and can cut a CJK, Arabic, or emoji codepoint in half, producing a JSONL line that strict readers reject. Truncation now strips a trailing incomplete UTF-8 sequence, via `iconv -c` where available with a pure-sh byte-level fallback; a complete multibyte character ending exactly at the boundary survives. The PowerShell twin was confirmed character-based and aligned to the same 200 budget (`tests/test_ledger_utf8.py`).
- Line endings are now pinned: new root `.gitattributes` forces LF for `.sh`, `.py`, `.ps1`, and `.svg`, CRLF for `.cmd` and `.bat`. A CRLF-converted shell script fails under `sh` with errors that read like code bugs; the index was audited (all 175 tracked `.sh`/`.py` files already stored LF, no renormalization needed) and a regression test keeps it that way (`tests/test_line_endings.py`).

### Added
- **Opt-in structure-aware plan injection** (`PWF_INJECT=smart`, or an `inject-smart` token in `.mode`). The default `head -50` injection is position-blind: late in a long plan the in_progress phase, the decision journal, and the errors table all sit past the injected window, so every turn pays the token cost while the window no longer carries the active phase. The smart shape emits the plan title, the Goal / Next Step / Current Phase sections, a phase count, the full first in_progress phase section, and the last 3 Decisions rows, extracted in a single POSIX-awk pass. Plans without `### Phase` headings fall back to the plain head. With no opt-in the output stays byte-identical to v2.43 (`tests/test_inject_smart.py`).
- **Next Step pointer.** Both task_plan templates now carry a `## Next Step` section directly after `## Goal`, inside every head-50/head-30 injection window, and the 5-Question Reboot Test gained a sixth row: What am I about to do? A fresh session resumes at the named action instead of re-deriving it (`TemplateNextStepTests`).
- **Tool-result outcomes in session catchup.** The catchup report annotated what the previous session tried but not what happened. Tool lines now carry the matched result: `-> ok`, or `-> FAILED (first error line)`, for both Claude Code sessions (tool_result/is_error) and the OpenCode SQLite path (state.status). Result-free sessions produce byte-identical output to before, proven by a golden test captured prior to the change.
- **macOS CI leg plus a BSD-userland simulation.** The pytest matrix now includes macos-latest, and a new Linux-leg harness runs the resolver, injection, attestation, and ledger scripts end to end under a simulated BSD userland (no realpath, no readlink, no flock, no sha256sum, BSD-style stat), so a GNU-only-flag regression fails CI before it reaches a Mac (`tests/test_bsd_userland_sim.py`).
- Three problem-query documentation pages: `docs/claude-code-lost-context-after-compaction.md`, `docs/agent-forgets-plan-after-clear.md`, and `docs/long-running-agent-tasks.md`, each answering the search question in its title from repo facts only, cross-linked, with install routes (`tests/test_seo_docs_pages.py`).
- `.github/FUNDING.yml` (GitHub Sponsors listing verified active) and a social preview asset (`media/social-preview.svg` + `.png`; the upload under repository Settings remains a manual step).

### Changed
- **README rebuilt around the product's strongest evidence.** Hero tagline, seven badges in two rows replacing twenty-five in three (the hand-maintained version badge, stale at 3.5.1, is now the dynamic release badge), a before/after `/clear` demo using the skill's real injection format, two committed SVG charts built only from numbers already published in `docs/evals.md` with the internal-v1 framing baked into the images, a mermaid diagram of the hook loop, the install-route matrix at the decision point, one consolidated command table that finally lists `/plan-doctor`, a promoted three-tier platform table, a cost-honesty admonition with the real overhead numbers, a new overhead FAQ entry, and a compact repository map. The unframed comparative badge was removed; recovery numbers appear only with the internal benchmark framing. The 7.6MB banner was downscaled to a 220KB JPEG. The plan-mode FAQ answer no longer asserts anything about plan-mode internals.
- `llms.txt` rewritten as a Q&A-bearing AI-search surface mirroring the README FAQ, with the same honesty constraints enforced by a new guard test (`tests/test_llms_txt.py`).
- SEO surface: repository topics swapped (context-rot, session-recovery, claude-code-skills in; pi, copilot, developer-tools out), repository description refreshed around session recovery, compaction, and context rot, `plugin.json` keywords cleaned (clawd, clawdbot, clawdhub out; long-running-agents, session-recovery, context-rot, agent-planning in), and the CITATION.cff abstract broadened to the 60+ agent Agent Skills story.

## [3.7.0] - 2026-07-18

### Added

- **The repo now ships the cross-tool Agent Skills standard layout in-tree: `.agents/skills/planning-with-files/`.** Tools that read the standard path natively (Zed, Amp, Warp, Devin, Antigravity, Gemini CLI, Cursor, and the wider agentskills.io adopter list) discover the current skill from a plain `git clone` with no per-tool setup. The mirror carries the full canonical surface: SKILL.md, references, all six templates including the autonomous plan template, and the complete script set (hook dispatchers, ledger tooling, doctor). It is wired into both maintenance systems so it cannot silently rot: `sync-ide-folders.py` gained a `.agents` manifest, and the SKILL.md joined the `bump-version.py` parity set and the version-parity test (now 18 locked entries).

- **`plan-doctor.sh` now ships in every synced IDE skill folder** (`.codebuddy`, `.codex`, `.continue`, `.factory`, `.gemini`, `.pi`, and the new `.agents`), not only the two canonical `scripts/` locations.

### Changed

- **`docs/gemini.md` now recommends the Agent Skills standard path.** Gemini CLI reads `.agents/skills/` natively and that alias takes precedence, so new installs get the current, version-locked skill instead of the intentionally version-lagged `.gemini/skills/` variant, which stays in place for existing installs. Manual install methods now copy from the standard layout as well.

- `AGENTS.md` and the `bump-version.py` docstring now describe the actual parity set (18 entries including `.agents`), replacing the stale 19-file wording that predated the `.pi` and `.kiro` scheme split.

### Verification

- Full suite green (217 passed) with the `.agents` SKILL.md under version-parity lock. `sync-ide-folders.py --verify` covers the mirror's shared files from this release on.

## [3.6.0] - 2026-07-18

### Fixed

- **Plan resolution and hook injection went silently dark on machines with Windows-native coreutils on PATH.** A native coreutils build (for example `C:\Program Files\coreutils`, increasingly common via winget or uutils) shadows Git Bash's tools inside `sh`, and its `realpath` canonicalizes MSYS `/c/...` input to `C:\`-style backslash output. The containment guard in `resolve-plan-dir.sh` and `inject-plan.sh` compares canonical paths with a forward-slash prefix pattern, so every comparison failed: the resolver resolved nothing, `inject-plan.sh` emitted nothing, and every hook fire exited 0 with no error. The plan mechanisms this skill is built on were fully disabled on such machines with no visible symptom, and Linux CI could never reproduce it. Canonical paths are now backslash-normalized (pure-shell, no extra process) before comparison. Found live during a repo audit on a machine where 33 local tests failed while CI stayed green.

- **The resolver's containment root still canonicalized `$PWD` instead of `.`.** The v3.2.0 fix for 8.3 short-name and `/tmp`-alias mismatches landed in `inject-plan.sh` only; `resolve-plan-dir.sh` kept the old form and additionally canonicalized absolute candidates built from the `$PWD` string, which a Windows-native `realpath` does not spell the same way as a short-form process cwd. The resolver now canonicalizes the root via `.` and checks candidates through their cwd-relative form, so both sides resolve through the same physical-cwd base. Emitted output is unchanged.

- **The local `test_ledger.py` hang on Windows is gone.** Known since v3.4.1 as "hangs locally, green on CI"; it stopped reproducing once the containment comparison was fixed. The ledger suite (12 tests) now passes locally in under 15 seconds.

### Added

- **`/plan-doctor` self-check command** (`commands/plan-doctor.md`, `scripts/plan-doctor.sh`, dual-shipped and parity-tested). Every failure in this class is silent by design (hooks always exit 0), so a broken install looks identical to "no plan yet". The doctor answers, in one pass: does resolution work here and which plan wins, does injection actually emit plan context, what path shape does the canonicalizer produce (warns about the pre-v3.6.0 dark condition), is the plan attested, which install surfaces exist on this machine, and what one hook fire costs in wall-clock. From the July 2026 benchmark improvement backlog.

- **Install-route matrix and trust prerequisite in `docs/installation.md`.** The plugin route ships `commands/` and registers hooks reliably; `npx skills add` and manual skill copies ship no slash commands, and SKILL.md frontmatter hooks have been observed unregistered on project-level installs (headless Claude Code 2.1.201, July 2026 benchmark). Project trust (`hasTrustDialogAccepted`) silently gates project-level skills. Both conditions are now documented with the doctor as the verification step.

- **Belt-and-suspenders trigger line for CLAUDE.md.** The July 2026 benchmark measured unforced skill engagement at 60-67% while always-loaded rules-file instructions engaged 100%. Install docs now offer a one-line CLAUDE.md snippet that makes engagement deterministic while the skill description keeps handling discovery.

- **Regression tests for the backslash-canonicalizer class** (`tests/test_containment.py`): a PATH-prepended stub `realpath` reproduces the Windows-native output shape on every platform, so ubuntu CI now guards a Windows-only field failure.

### Changed

- **Hook fire cost dropped.** Per-candidate `grep -Eq` slug checks and `basename` calls in `resolve-plan-dir.sh` and `inject-plan.sh` were replaced with equivalent shell builtins (case patterns and parameter expansion), and the resolver computes its containment root once per run instead of once per candidate. One `inject-plan.sh` fire measures 289ms wall-clock on the same machine that measured 2.0-2.4s at v3.4.0 (July 2026 benchmark, F4). Output is byte-identical; the legacy invariant holds.

- README documents v3.6.0, adds a plan-mode handoff FAQ (how an accepted plan-mode plan becomes `task_plan.md` phases, answering the open question in #19), and updates the supported-agents answer to the current `.agents/skills/` standard landscape. The stale Manus-2025 "one tool call per turn" guidance was replaced with the 2026 parallel-host update in the last two variant copies that still carried it (`.factory`, `.mastracode`).

### Verification

- Full suite green locally on the machine that reproduced the bug: 205 passed plus 12 ledger tests, 5 skipped, 0 failed (was 33 failed before the fix). Live smoke: `sh scripts/inject-plan.sh` emits plan context in a repo with an active plan, `scripts/plan-doctor.sh` reports PASS on resolution and injection with the Windows-native canonicalizer present.

## [3.5.1] - 2026-07-14

### Fixed

- **Codex Windows hook resolver defaulted to the WSL bash launcher** (extracted from PR #207 by @mahdiit). The shell resolver in `codex_hook_adapter` preferred `C:\Windows\System32\bash.exe`, the WSL launcher, whenever Git Bash's `usr\bin` was not on PATH, the default Git for Windows install layout. On machines where WSL is present but no distro is installed, a common Docker Desktop setup, that launcher exists on disk but fails immediately, so every shell hook silently failed. This is why #201 and #204 kept resurfacing on some Windows machines even after those releases shipped. The resolver now skips WSL launchers, both the System32 binary and the Microsoft Store WindowsApps alias, and continues on to the Git for Windows probe.

- **`pwf-hook.cmd` lost the Python interpreter under Codex's reduced PATH** (also from PR #207). Codex starts hooks with a trimmed environment, so the launcher's plain `py -3` / `python` lookup often found nothing. `pwf-hook.cmd` now honors a `PYTHON_BIN` override, probes the standard `uv` and CPython install locations, and quotes the interpreter path so installs under a path containing spaces still resolve.

- **Pi extension 1.2.1: pre-tool recitations and the tamper notice were consumed by interactive tool dialogs** (#206, diagnosed with the exact mechanism by @jschmied). The `tool_call` hook delivered queued planning text as steer, but when an interactive tool such as AskUserQuestion blocked the turn on its own custom UI, the steer text was read as the dialog's answer instead of reaching the model. Recitations and the tamper notice are now delivered as `nextTurn`, landing after the interactive tool releases the turn instead of being swallowed by it. Bundled Pi extension bumped to 1.2.1.

- **Two test-portability failures surfaced by the first hosted-runner run** (PR #198 by @Yigtwxx, test files only, no production script changes). `tests/test_containment.py` canonicalized the resolver's Git Bash POSIX path with `os.path.realpath`, which read `/tmp/...` as `C:\tmp` and failed the escaping-symlink containment assertion on symlink-capable `windows-latest`; a `host_realpath()` helper now maps the path back with `cygpath` before comparing. `tests/test_path_fix.py` ran two Windows-shaped path vectors on `ubuntu-latest`, where `Path.resolve()` treats `C:/...` as relative and prepends the CWD; both now skip unless `os.name == "nt"`, the only platform where that input shape is meaningful. In both cases the resolver rejected the escape correctly and only the test comparison was wrong.

### Added

- **CI test workflow** (`.github/workflows/tests.yml`, PR #199 by @Yigtwxx, closes #197). Runs the pytest suite on `ubuntu-latest` and `windows-latest` (Python 3.12) plus the Pi extension vitest suite on `ubuntu-latest` (Node 22), on every pull request and push to master. Until now the only CI was the Tessl skill-prose review, so nothing ran the 200+ pytest tests or the 21 Pi vitest tests that CONTRIBUTING.md asks contributors to run before opening a PR. The `windows-latest` leg targets the recurring Windows regression class (the v3.2.0 audit found `session-catchup.py` silently non-functional on Windows). Workflow permissions are `contents: read` only, `fail-fast: false` keeps a Windows-only failure visible instead of masked by a cancel, and an explicit step asserts `sh` is on PATH so the roughly ten hook tests that skip without it cannot silently drop coverage.

### Verification

- Python suite green on master before merge (200 passed, 5 skipped on a non-symlink-capable Windows host). Contributor's hosted-runner run on PR #199 green on all three jobs: pytest on ubuntu with symlink containment tests running, the equivalent profile on windows, and 21 vitest.
- Supply-chain review on PR #198 and #199: no new runtime dependencies, no install scripts, no bin shims. The workflow installs `pytest` and `pyyaml` for the pytest job and runs `npm install` against the Pi extension's existing devDependencies (vitest, typescript, @types/node). It uses `pull_request` (not `pull_request_target`), so fork PRs run with a read-only token and no secret access.

### Thanks

- Mahdi (@mahdiit) for producing the Codex Windows WSL bash launcher fix and the Windows Python discovery hardening (PR #207), using Codex Terra after v3.4.1 still failed to clear the hook errors on his own machine.
- jschmied for diagnosing #206 down to the exact runtime location, steer delivered recitations consumed by AskUserQuestion's interactive dialog, and for the `nextTurn` delivery fix that shipped.
- Yigtwxx (Yiğit) for filing the CI gap (#197) and landing both the test-portability fixes (#198) and the pytest plus vitest workflow (#199).

## [3.5.0] - 2026-07-13

### Fixed

- **Codex hooks on Windows emitted invalid JSON and failed on Unicode** (PR #205 by @yolo0731, closes #204). On Windows the Codex front door forwarded plain `[planning-with-files]` stdout where Codex expects `hookSpecificOutput.additionalContext` (SessionStart, UserPromptSubmit) or a common-fields object (PreCompact), so those hooks were rejected. UTF-8 plan text also broke twice, once decoding shell output through the Windows code page in `subprocess.run(text=True)` and again writing `ensure_ascii=False` JSON through cmd.exe. The fix serializes each event in its supported Codex JSON shape with ASCII-safe output, decodes shell output as UTF-8 with `errors="replace"`, routes PreToolUse plan text through model-visible `additionalContext`, resolves scoped `.planning/<slug>/` plans in PermissionRequest, adds `clear|compact` to the SessionStart matcher, and writes the `.active_plan` pointer as UTF-8 without a BOM. The containment resolver also now fails closed when canonicalization is unavailable. 34 files, with the three-file script triple applied identically across every adapter copy. Scope is Windows Codex, matching the report.

- **Closed and complete plans kept nagging "Task incomplete" in the Pi extension** (#203, reported by @ziyu4huang). `resolveNewestPlanDir` ranked plan directories by directory mtime, which does not change when a `task_plan.md`'s contents are edited, so a finished plan lost to an older incomplete sibling and `agent_end` nagged with that sibling's stale count. Resolution now ranks by the `task_plan.md` file mtime. The extension also had no close-marker awareness: `readPlanStatus` now parses the pwf close marker and exposes `status.closed`, `agent_end` returns early on a closed plan, and the auto-continue loop stops on close. A `PWF_DEBUG` diagnostic logs the resolved cwd, plan id, closed state, and phase count before the nag. Bundled Pi extension bumped to 1.2.0.

- **Four language commands invoked a skill namespace that does not exist.** `commands/plan-ar.md`, `plan-de.md`, `plan-es.md`, and `plan-zh.md` referenced `planning-with-files-<lang>:planning-with-files-<lang>`; the skills are registered under the single plugin namespace `planning-with-files:planning-with-files-<lang>`, which the English commands already used. Corrected all four.

### Added

- **Traditional Chinese slash command** (`commands/plan-zht.md`, `/plan-zht`). The `planning-with-files-zht` skill shipped without a matching command; this closes the ar/de/es/zh/zht command parity gap.

- **README now documents the full v3 command, hook, and mode surface.** The visible command table listed only three commands with v2.11.0 and v2.15.0 tags while the plugin ships `plan-goal`, `plan-loop`, `plan-attest`, `pwf`, and the language commands. Added visible sections for the Claude Code and Pi command tables, a v3 long-running-agent features section, a hooks-and-modes reference across Claude Code, Codex, and Pi, and a "command names vs skill names" note that states there is no `/pwf-de` or `/planning-with-files:planning-with-files-goal`. All additive.

- **Plan lifecycle is now documented** (#202, asked by @kcinzgg). `docs/workflow.md` gains an "After Completion" section stating that planning files are ephemeral working memory, gitignored by default, and not archived automatically, with guidance on retaining a completed plan and a note that a completion-triggered archive step is a welcome opt-in extension. Pointers added in `docs/quickstart.md` and the README FAQ. This writes down the intent that issue #14 answered informally.

### Security

- Independent supply-chain audit of PR #205 before merge (a classifier plus two adversarial containment passes, all clean): no new dependencies, no install scripts, no bin shims, no network calls, no eval of untrusted input. The one security-relevant change (containment moving from fail-open to fail-closed) is a hardening, covered by an added junction-escape rejection test.

### Thanks

- @yolo0731 for the Codex Windows hook fix (#204, PR #205), the protocol-safe JSON serialization and the UTF-8 handling.
- @ziyu4huang for the precise #203 diagnosis, verified against the extension's own exported functions.
- @kcinzgg for the #202 question that surfaced the undocumented plan lifecycle.

## [3.4.1] - 2026-07-12

### Fixed

- **Codex hooks failed on Windows with "hook exited with code 1"** (closes #201, reported by @mahdiit). Every hook in `.codex/hooks.json` carried only a POSIX `command` (`sh`, `python3`, `2>/dev/null`, `$HOME`, a trailing `|| true`). Codex on Windows runs that string through the native command interpreter, not a POSIX shell, so `python3` hit the Microsoft Store alias, `2>/dev/null` was an invalid path, and the `|| true` success guard itself failed because `true` is not a Windows command. The chain exited non-zero and Codex reported the hook as failed on every Bash call. Reproduced on Windows: the PostToolUse command exits 1 when Git's `usr\bin` (home of `sh` and `true`) is not on PATH, which is the default Git for Windows layout.

### Added

- **Windows hook execution for Codex** via the per-hook `commandWindows` override, the mechanism OpenAI's hooks documentation sanctions. The POSIX `command` is untouched, so macOS and Linux stay byte-for-byte unchanged. On Windows all seven hooks route through a new launcher, `.codex/hooks/pwf-hook.cmd`, which selects a real Python (`py -3`, falling back to `python`, never the Store `python3` alias) and always exits 0 so an advisory hook cannot surface an error. The four Python hooks run their entry point directly; the three shell hooks route through a new front door, `.codex/hooks/run_sh.py`. `codex_hook_adapter.run_shell_script` now resolves the Git for Windows `sh.exe` by anchoring on `git.exe` and the standard install roots, so the shell scripts run even when Git's `usr\bin` is off PATH, and it hands `session-catchup.py` a real interpreter through `PYTHON_BIN`. Without Git for Windows the three shell hooks degrade to a silent no-op instead of an error, and the four Python hooks still work. The `docs/codex.md` Windows section was rewritten (it previously stated hooks were disabled on Windows).

### Verification

- Codex hook suites green: `tests/test_codex_hooks.py` (11 tests, including a cross-platform guard that every hook declares a `commandWindows` free of the POSIX tokens that break on Windows, and a Windows-only end-to-end test of the `run_sh.py` front door) and `tests/test_codex_session_isolation.py` (6 tests). Version parity and frontmatter suites green after the bump. End-to-end on Windows: PostToolUse, SessionStart, and PreToolUse all exit 0 with correct output, including a simulation of the reporter's environment (Git installed, `usr\bin` off PATH) where the `git.exe` anchor resolves `sh`, and a no-Git case that degrades to a silent no-op.
- Supply-chain review: no new runtime dependencies, no install scripts, no bin shims. Two new files under `.codex/hooks/` (`pwf-hook.cmd`, `run_sh.py`), both Windows-only entry points that reuse the existing adapter and shell scripts.

### Thanks

- @mahdiit (Mahdi) for reporting the Codex Windows hook failure (#201) with the exact error and environment.

## [3.4.0] - 2026-07-06

### Added

- **`PLANNING_DISABLED=1` per-invocation opt-out** (closes #195, reported by @marcmuon). One-shot sessions that share a working directory with an active plan (a CI review bot run via `codex exec`, a read-only research agent, a nested orchestrator) were hijacked by the hooks: plan context injected, the actual output redirected into `progress.md`, and a fabricated completed phase appended to `task_plan.md`. All Codex hook entry points (`session-start.sh`, `user-prompt-submit.sh`, `pre-tool-use.sh`, `post-tool-use.sh`, `stop.sh`, `pre-compact.sh`, plus the Python adapter route via `codex_hook_adapter.is_session_attached`) and the canonical dispatchers (`inject-plan.sh`, `gate-stop.sh`, `check-complete.sh`/`.ps1`) now exit before reading the plan when `PLANNING_DISABLED=1` is set in the environment. PreToolUse still emits its allow decision so tool calls proceed normally. The guard ships in every distributed copy: canonical scripts, the skill package, all sync-managed IDE mirrors, the five language variants, the standalone `.kiro` copy, and the `clawhub-upload` bundle. Usage documented in `docs/codex.md`. New `tests/test_planning_disabled_optout.py` (12 tests) covers baseline behavior, disabled behavior, the #195 acceptance criterion (plan files byte-for-byte unchanged after a full disabled hook pass), and a guard-presence sweep across every copy.

### Fixed

- **`docs/codex.md` still described the pre-v3.1.0 blocking Stop hook.** The hook table said Stop "blocks once when phases are incomplete"; that block path was removed in v3.1.0 (PR #180) and the installed hook has emitted an advisory reminder since. The row now matches the shipped behavior. The `decision: block` half of #195 was reported against a v2.41.0 bundle shipped by oh-my-codex; current releases do not block.

### Verification

- Python suite: 200 passed, 5 skipped, 0 failed (12 new opt-out tests).
- Functional smoke test on a live temp plan: baseline injection unchanged without the variable; with it set, no hook output, tool calls still allowed, plan files byte-identical afterwards.
- `scripts/sync-ide-folders.py --verify`: all IDE folders in sync. All modified `.sh` files pass `sh -n`; all modified `.ps1` files parse clean.

### Thanks

- @marcmuon (Marc Kelechava) for the precise report separating this failure from #178 and #146, with reproductions for both symptoms, the root-cause file list, and acceptance criteria this release implements directly (#195).

## [3.3.0] - 2026-07-06

### Added

- **`/plan-execute` approval gate for the Pi extension** (PR #193 by @Dikshj, closes #190, requested by @lazyst). The Pi extension hooks previously activated as soon as `task_plan.md` existed on disk: plan injection on `before_agent_start`, pre-tool recitation on `tool_call`, post-write reminders on `tool_result`, and auto-continue on `agent_end` could all start while the user was still reviewing a draft plan. The extension now stays passive until the user approves the active plan with `/plan-execute`; before approval it shows a status line ("run /plan-execute to activate hooks") and nothing else. Approval is scoped to the current session and plan path, is cleared on session lifecycle events, and `/plan-execute reset` returns the plan to passive review mode. A plan whose SHA-256 attestation shows tampering cannot be approved. This gates initial hook activation only; the v3 gate mode (which gates stopping on an incomplete plan) is unchanged. Pi docs, Pi skill docs, and runtime tests cover the passive review flow.

### Verification

- Python suite: 188 passed, 5 skipped, 0 failed.
- Pi extension vitest suite: 21 passed (2 files).
- `scripts/sync-ide-folders.py --verify`: all IDE folders in sync.
- Supply-chain review on PR #193: no new dependencies, no install scripts, no bin shims, no network calls; changes confined to the Pi extension runtime, its tests, and documentation. The gate itself tightens the injection path, since a tampered or unreviewed plan can no longer reach model context automatically.

### Thanks

- @Dikshj (diksha) for implementing the /plan-execute approval gate with runtime and docs test coverage (PR #193).
- @lazyst for the feature request and the precise passive-until-confirmed workflow description (#190).

## [3.2.0] - 2026-07-03

A repository health audit covering the v3 long-running-session mechanism, the
open issue backlog, and two community pull requests. The headline finding:
`session-catchup.py`, the mechanism behind "resume after /clear," did nothing
on Windows. Both that and a related silent-injection bug are fixed here,
along with the false "0/0 phases" status reported in #191.

### Fixed

- **`session-catchup.py` was non-functional on Windows** (the "resume after /clear" feature). `get_project_dir_claude` only replaced forward slashes, so a Windows-style path (`C:\Users\...` or Git Bash's `/c/Users/...`) never sanitized to Claude's actual project-directory name, and the function always returned early with no output and no error. Three `open()` calls also had no explicit encoding, so a session log containing any non-ASCII text raised `UnicodeDecodeError` on Windows' default `cp1252` codec, an error the surrounding `except` clauses swallowed silently. Fixed by detecting Windows-shaped paths before sanitizing and adding `encoding='utf-8', errors='replace'` to the three reads; genuine Unix absolute paths take the same code path as before. `tests/test_path_fix.py` previously reimplemented the sanitizer instead of importing the real module, so the suite stayed green while the shipped script stayed broken; it now imports and exercises the actual function.
- **`inject-plan.sh`'s containment guard silently dropped plan injection and tamper detection under aliased paths.** `is_within_root()` canonicalized the project root from the `$PWD` string but canonicalized candidates from a relative path, and on a Windows account with an 8.3 short-name `TEMP` (or any path reached through the MSYS `/tmp` mount), the two resolve to differently-spelled versions of the same directory. The prefix-match check then failed and the hook exited with zero output: no plan re-injection, no tamper warning, nothing visible. Fixed by canonicalizing the root the same way candidates already are.
- **Task plans without `### Phase` headings falsely reported "0/0 phases complete"** (#191, reported by @mixian939 against Codex). `check-complete.sh`/`.ps1` and several IDE-specific Stop hooks counted `### Phase` headings but never checked whether the count was zero before reporting a status, so an unstructured `task_plan.md` produced a false "Task in progress (0/0 phases complete)" message, or in Cursor and GitHub Copilot's adapters an auto-continue nudge to keep working on a plan that was never structured to begin with. Fixed with a `TOTAL=0` guard everywhere the pattern appeared: the canonical Claude Code scripts, `.codex`, `.cursor`, GitHub Copilot's `agent-stop.sh`, all `sync-ide-folders.py`-managed IDE mirrors, the five language-variant skills, and the standalone `.kiro` copy.
- **`--template analytics` silently produced the default templates instead of the analytics-specific ones** (addresses #103). `templates/analytics_task_plan.md` and `templates/analytics_findings.md` (added v2.29.0) were never copied into `skills/planning-with-files/templates/`, the directory the installed skill package actually reads, so every plugin or skill-only install fell back to the generic templates. Copied both files into the canonical templates directory and added them to `sync-ide-folders.py`'s sync list, backfilling seven IDE mirrors.
- **Windows test suite encoding errors and stale installation docs** (PR #187 by @Stephen-abc). `subprocess.run`/`Popen` calls across 15 test files had no explicit encoding, which raises `UnicodeDecodeError` on Windows accounts whose default codepage isn't UTF-8. `docs/adal.md`, `docs/antigravity.md`, `docs/kilocode.md`, and `docs/openclaw.md` also referenced `.adal/`, `.agent/`, and `.kilocode/` source paths removed in v2.24.0, and antigravity.md's templates were mislabeled as living in `references/` instead of `templates/`. Fixed the same mislabel in `docs/codebuddy.md`, which was outside PR #187's scope.
- **Hermes adapter test failed on Windows accounts with an 8.3-short-name `TEMP`.** The test compared a `Path.resolve()`-canonicalized production result against an unresolved expected path, so accounts where `TEMP` itself resolves to a short-name alias (`OASRVA~1` vs the real account name) failed a test that was actually passing correctly. Resolved the expected side the same way.
- **`AGENTS.md` told agents to squash-merge contributor PRs.** `git merge --squash` reassigns the contributor's commit authorship to whoever runs the local commit: the exact mistake this project's release protocol already exists to prevent (v2.40.1 cycle). Replaced with cherry-pick / `gh pr merge --rebase` guidance, matching CLAUDE.md. Also documented that `.pi` and `.kiro` lag the parity-locked version bump alongside `.continue` and `.gemini`, which recent CHANGELOG entries already assumed AGENTS.md said.

### Added

- **`docs/autohand.md`** (PR #192 by @igorcosta): setup guide for Autohand Code, added to the supported-IDEs table (18+ platforms).
- **`SECURITY.md`** and GitHub private vulnerability reporting enabled (closes #188, requested by @AvitalAviv).

### Changed

- Version bumped to 3.2.0 across the 17 parity-locked files via `scripts/bump-version.py`. `.continue`, `.gemini`, `.pi`, and `.kiro` lag intentionally, now documented in AGENTS.md itself.

### Verification

- Python suite: 186 passed, 5 skipped, 0 failed (up from 184/4/0; two new path-sanitizer tests in `test_path_fix.py`).
- `scripts/sync-ide-folders.py --verify`: all IDE folders in sync.
- Functionally re-verified the long-running-session mechanism end to end on Windows after the fixes: init, check-complete, attestation lock/tamper-detect/clear, parallel-plan resolution, and session-catchup all confirmed working in both sh and PowerShell.
- Supply-chain review on both merged PRs: docs and test files only, no dependency, install script, or bin shim in either.

### Thanks

- @mixian939 for the detailed #191 report and root-cause diagnosis against Codex, which led to finding and fixing the same defect in the canonical scripts and two other IDE adapters.
- @Stephen-abc (Wang Jun) for the Windows test encoding fix and installation doc corrections (PR #187).
- @igorcosta (Igor Costa, Autohand) for the Autohand Code setup docs (PR #192).
- @AvitalAviv for flagging the missing private vulnerability disclosure channel (#188).
- @mvanhorn for the original analytics templates (v2.29.0, #103) that this release finally ships into the installed skill package.

## [3.1.3] - 2026-06-16

A hotfix for a frontmatter regression introduced in v3.1.2. The refreshed description shipped in v3.1.2 contains a colon, and the English SKILL.md carry the `description` field unquoted, so the frontmatter became invalid YAML. This release quotes the description and adds a test that validates every SKILL.md frontmatter as YAML, so the class cannot ship again.

### Fixed

- **SKILL.md frontmatter was invalid YAML in v3.1.2** (regression from the v3.1.2 description refresh). The new description "Manus-style persistent file-based planning for AI coding agents: keeps ..." contains a colon followed by a space. The English SKILL.md carry `description` unquoted, so a YAML loader reads the `: ` as a nested mapping and rejects the frontmatter with "mapping values are not allowed here". This affected the canonical file and the seven English IDE variants (`.codebuddy`, `.codex`, `.cursor`, `.factory`, `.hermes`, `.mastracode`, `.opencode`) and could break skill loading and the model-triggering description field. The description is now wrapped in double quotes, matching the already-quoted translated variants. The parsed value is identical, so model triggering is unchanged. The `clawhub-upload` staging bundle was corrected the same way.

### Added

- **Frontmatter validation test** (`tests/test_skill_frontmatter_valid.py`): loads every `SKILL.md` frontmatter as YAML and asserts a non-empty string description, plus a dependency-free check that no unquoted description contains `: `. The version-parity check is a regex and could not catch this regression.

### Changed

- Version bumped to 3.1.3 across the 17 parity-locked files via `scripts/bump-version.py`. `.continue`, `.gemini`, `.pi`, and `.kiro` lag intentionally per AGENTS.md release scope.

### Verification

- Python suite: 184 passed, 4 skipped, 0 failed, up from 180 with the four new frontmatter assertions.
- Every SKILL.md in the repo, including the translated variants and the lagging `.continue`, `.gemini`, `.pi`, and `.kiro` variants, parses as valid YAML.

## [3.1.2] - 2026-06-16

A documentation patch. The session-catchup command in the skill body assumed the plugin runtime had set `${CLAUDE_PLUGIN_ROOT}`, so a skill-only install that ran the documented command in a normal shell got an empty variable and a broken path. This release adds a fallback across the affected variants, fixes the same class of bug in the `.hermes` variant, and refreshes the skill description to lead with the current positioning.

### Fixed

- **Session-catchup command works outside the plugin runtime** (PR #186 by @shunfeng8421, closes #185). The documented Restore Context command ran `${CLAUDE_PLUGIN_ROOT}/scripts/session-catchup.py`, but `CLAUDE_PLUGIN_ROOT` is only set when the plugin runtime executes a hook, not in an interactive shell. A skill-only install (via `npx skills add`, or on Codex or Cursor) collapsed the command to an absolute `/scripts/...` path that does not exist. The fix uses `SKILL_DIR="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/skills/planning-with-files}"`, so plugin users keep the variable and skill-only users fall back to the default install path. Applied to the canonical file, the `.codebuddy` variant (with its own `${CODEBUDDY_PLUGIN_ROOT}`), and the five language variants. The Windows PowerShell block and plugin behavior are unchanged.
- **`.hermes` variant carried the same unset-variable bug** (maintainer follow-up to #186). `.hermes` used `$HERMES_HOME` in bash and `$env:HERMES_HOME` in PowerShell with no fallback, so its catchup command failed the same way outside the Hermes runtime. Both blocks now fall back to `$HOME/.hermes` and `$env:USERPROFILE\.hermes` while keeping the runtime variable as the priority.

### Changed

- **Skill description refreshed for discoverability.** The eight English SKILL.md files (canonical plus the `.codebuddy`, `.codex`, `.cursor`, `.factory`, `.hermes`, `.mastracode`, `.opencode` adapters) now lead with "persistent file-based planning for AI coding agents" and name context-loss survival explicitly. The `Use when` trigger clause is unchanged, so model invocation behavior is identical. The five translated variants keep their localized descriptions.
- Version bumped to 3.1.2 across the 17 parity-locked files via `scripts/bump-version.py`. `.continue`, `.gemini`, `.pi`, and `.kiro` lag intentionally per AGENTS.md release scope.

### Verification

- Python suite: 180 passed, 4 skipped, 0 failed, unchanged. The change is documentation prose with no test dependency.
- Supply-chain review: the changed files are SKILL.md documentation only. No dependency, install hook, bin shim, or new install-path file. PR #186's diff was reviewed line by line before adoption.

### Thanks

- @shunfeng8421 for the session-catchup fallback fix (PR #186), which resolves the #185 report.
- @xwang118 for surfacing the underlying problem in PR #183 that became #185.

## [3.1.1] - 2026-06-15

A documentation-only patch. The Codex verification command in `docs/codex.md` checked for a feature-flag name that current Codex no longer prints, so a correctly configured user running the documented check was told to upgrade. This release fixes the command and its follow-up sentence to match the canonical `hooks` flag already documented elsewhere in the same file. No code, hook, script, or test changed; the parity set is bumped to 3.1.1.

### Fixed

- **Codex verification command checks the canonical `hooks` feature flag** (PR #184 by @Fat-Jan). The Verification block ran `codex features list | rg '^codex_hooks\s'`, but Codex moved its canonical feature key from `codex_hooks` to `hooks` in 0.129.0 (openai/codex#20522). The old key still resolves as a deprecated alias inside `config.toml`, yet `codex features list` prints only the canonical `hooks`, so the bare `^codex_hooks\s` pattern matched nothing on any current Codex and routed correctly configured users to the "upgrade Codex" path. The command is now `rg '^(hooks|codex_hooks)\s'` and the troubleshooting sentence reads "If neither `hooks` nor the deprecated alias `codex_hooks` appears". This aligns the Verification block with the `hooks = true` configuration guidance and the deprecated-alias note already carried in the same document since v2.39.0.

### Changed

- Version bumped to 3.1.1 across the 17 parity-locked files via `scripts/bump-version.py`. `.continue`, `.gemini`, `.pi`, and `.kiro` lag intentionally per AGENTS.md release scope.

### Verification

- Python suite: 180 passed, 4 skipped, 0 failed, unchanged from v3.1.0. A documentation-only change touches no test path.
- Supply-chain review: the single changed file is `docs/codex.md`, a two-line edit to a fenced shell command and one prose sentence. No dependency, install hook, bin shim, or new file in the install path.

### Thanks

- @Fat-Jan for catching that the Codex verification command checked a feature-flag name current Codex no longer emits (PR #184).

## [3.1.0] - 2026-06-13

This release adopts four community contributions filed against the v3.0.0 cycle, each preserving the contributor as commit author. The Codex adapter gets the Stop-hook behavior fix that issue #178 asked for plus the PreCompact parity it was missing, the Pi extension gains a real test suite, and the SHA-cache documentation is corrected to the v3 path. With no v3 mode marker on disk the canonical hooks remain byte-identical to v2.43.0.

### Fixed

- **Codex Stop hook no longer blocks a normal stop on an incomplete plan** (PR #180 by @2023Anita, closes #178). `.codex/hooks/stop.py` previously emitted `{"decision": "block"}` on the first stop while phases were still pending and `stop_hook_active` was false, which pushed the Codex agent to continue into the next phase without the user asking. The conditional block path is removed: the adapter now emits a single advisory `systemMessage`, and `.codex/hooks/stop.sh` drops the imperative "continue working on the remaining phases" wording in favor of a plain progress-sync reminder. This matches the v3 design principle that an incomplete plan alone never blocks a stop. The standalone `.codex` Stop adapter performs only phase counting, with no attestation or tamper gate to preserve, so removing the block path is the complete fix for the reported behavior.
- **SHA-cache documentation corrected to the v3 location** (PR #174 by @mvanhorn, closes #164). The new `docs/perf-notes.md` documents the attestation SHA cache: location priority, key derivation, container and CI behavior, and the clear command. A maintainer follow-up updated the documented path from the v2.40 `${TMPDIR:-/tmp}/pwf-sha` location to the v3 priority chain (`$XDG_CACHE_HOME/pwf-sha`, then `$HOME/.cache/pwf-sha`, then the `/tmp` fallback only when HOME is unset, per `scripts/inject-plan.sh`), corrected the clear command and the container premise, and clarified that the cache key is the first 16 hex characters of the SHA-256 of the plan file path. The canonical SKILL.md cross-link that repeated the stale `/tmp` path was fixed in the same pass.

### Added

- **Native Codex PreCompact hook** (PR #181 by @GongYuanCaiJi). The `.codex/hooks.json` lifecycle wiring declared every event except PreCompact, while the canonical SKILL.md has carried PreCompact since v3.0.0. This adds `.codex/hooks/pre-compact.sh` (POSIX sh, reuses `resolve-plan-dir.sh`, emits the same progress-flush reminder and `Plan-SHA256` line as the canonical hook), wires it into `.codex/hooks.json`, corrects the `docs/codex.md` hook table, and adds two targeted tests. This is parity for the native `hooks.json` route, not a new user-visible capability: the hook stays dormant on a runtime that never fires a PreCompact event, and the `|| true` wiring cannot break a session.
- **Pi extension integration test suite** (PR #175 by @mvanhorn, closes #163). A TypeScript (vitest) suite under `.pi/skills/planning-with-files/extensions/planning-with-files/__tests__/` exercises all eight Pi lifecycle handlers, the four runtime modes (auto, parity, cache-safe, notify), and the SHA-256 attestation gate across match, mismatch, and invalid-hash cases. A maintainer follow-up aligned one parity-mode assertion with the runtime's lowercase injection banner in `runtime.ts`.

### Changed

- Version bumped to 3.1.0 across the 17 parity-locked files via `scripts/bump-version.py`. `.continue`, `.gemini`, `.pi`, and `.kiro` lag intentionally per AGENTS.md release scope.

### Verification

- Python suite: 180 passed, 4 skipped (the pre-existing Windows exec-bit and symlink-containment skips), 0 failed, up from 178 with the two new Codex PreCompact tests. `tests/test_codex_hooks.py` reports 9 passed.
- The Pi extension vitest suite (PR #175) was added and statically reviewed against `runtime.ts` source, but was not executed in this release environment; `python -m pytest` does not run the `.test.ts` files. Run `npm install && npm test` inside `.pi/skills/planning-with-files/extensions/planning-with-files/` to execute it. The `package.json` is `private`, declares only `vitest`, `typescript`, and `@types/node` as devDependencies, and carries no install lifecycle scripts.
- Supply-chain review of the two new shipped files: `.codex/hooks/pre-compact.sh` is POSIX sh with no network calls, no install hooks, and no writes outside the plan directory; `docs/perf-notes.md` is documentation only.

### Thanks

- @2023Anita for the Codex Stop hook fix (PR #180) that resolves the issue #178 auto-continuation complaint.
- @GongYuanCaiJi for the native Codex PreCompact parity hook (PR #181).
- @mvanhorn for the Pi extension integration test suite (PR #175, closes #163) and the SHA-cache documentation (PR #174, closes #164).

## [3.0.0] - 2026-06-10

v3 targets long-running agentic runs on strong models (Opus 4.8, Fable 5, GPT 5.5 class). Everything new is opt-in. With no mode marker on disk, the hooks produce byte-identical v2.43.0 output: same delimiters, same raw progress tail, same advisory Stop behavior. Existing workflows need no changes.

### Added

- **Autonomous mode** (`init-session.sh --autonomous`): keeps the turn-start plan injection, drops the per-tool-call re-injection that the v2.21 eval measured as a 68 percent token tax. The plan file on disk stays the source of truth. Recitation is reduced, not removed: published evidence on goal drift in long runs still supports one injection per turn.
- **Gated mode** (`init-session.sh --gated`): adds a deliberate completion gate on the Stop hook. The gate blocks a stop only when all five conditions hold: the plan opted into gated mode, a phase is `in_progress`, `stop_hook_active` is false, the block count is under the cap (default 20, `PWF_GATE_CAP` to override, reset at init), and the run ledger advanced since the previous block. Any single failure lets the stop through. An incomplete plan alone never blocks a session, which is the design lesson from issue #178.
- **Run ledger**: `ledger-append`, `ledger-summary`, and `phase-status` scripts (sh and ps1). Workers append one JSON line per event to a per-agent `ledger-<agent>.jsonl`; the injected context becomes a fixed-shape synthesized summary (tick count, phases complete, in-progress phase, last event per agent) instead of a raw `progress.md` tail. The block carries no timestamps and no free text from disk, so it stays stable for the host prompt cache.
- **Autonomous plan template** (`templates/task_plan_autonomous.md`) with optional per-phase `DependsOn`, `Owner`, and `AcceptanceCheck` fields next to the existing `Status` line, so v2 completion counting is unchanged.
- **Migration guide**: MIGRATION.md gains a v2-to-v3 section with the host capability tiers (hard block: Claude Code, Codex CLI, Continue.dev; follow-up inject: Cursor, Pi, Kiro; notify only: OpenCode, Gemini CLI) and an honest note that OpenCode cannot enforce the gate until upstream ships Stop-hook re-activation.
- **Tests**: new suites for the gate decision table, ledger append and summary, init modes, realpath containment, and script location parity. Suite total: 178 passed, 4 skipped.

### Changed

- The four giant hook one-liners in SKILL.md frontmatter are now thin dispatchers that call `scripts/inject-plan.sh` and `scripts/gate-stop.sh`. In legacy mode the dispatcher output is byte-identical to the v2.43 inline commands, verified by diffing both against the same fixtures.
- The mtime-keyed SHA cache moved from the shared `${TMPDIR:-/tmp}/pwf-sha` to the user-private `$XDG_CACHE_HOME/pwf-sha` (default `~/.cache/pwf-sha`). The first session after upgrade rehashes attested plans once, then the cache repopulates.
- The version parity test no longer fails on fresh clones that lack the gitignored `clawhub-upload/` staging folder. Contributors hit this as a phantom failure when running the full suite against a clean checkout.

### Security

- v3 modes refuse to inject an unattested plan body. Autonomous and gated sessions attest the plan at init, and editing the plan afterward requires an explicit re-attest. An unattended loop never feeds an unverified plan into context.
- Per-session nonce delimiters in v3 modes (`===BEGIN-PLAN-DATA-<nonce>===`) replace the static markers, which makes delimiter-confusion injection harder. The limitation is documented in SKILL.md: an attacker with plan-write access can read the nonce, so attestation, not the nonce, is the defense there.
- The raw `progress.md` tail is no longer injected in v3 modes. `progress.md` is not covered by attestation, so instruction-like text appended there during an unattended run used to reach the model context every turn.
- Realpath containment in the plan-dir resolver: a symlinked plan directory that escapes the project root is treated as unresolved instead of being hashed and injected.
- The attestation writer closes a read-then-write integrity gap and handles the PowerShell 5.1 BOM case that could brick attestation files written on stock Windows.

### Fixed

- All 12 findings from the pre-release adversarial review, including control characters in gate block reasons breaking the Stop-hook JSON, a `stop_hook_active` false positive, mode token parsing, and missing dispatcher scripts on the plugin-marketplace path.
- The ledger script trio now ships in root `scripts/` as well, so the plugin-marketplace fallback route gets the structured ledger summary instead of silently falling back to the raw progress tail. A new location-parity test pins the full dual-shipped script set byte-identical in both locations.

## [2.43.0] - 2026-05-26

### Added

- **CONTRIBUTING.md at repo root** (PR #171 by @Skulli485, closes issue #162): first-time contributor guide covering local setup, project layout, PR submission conventions, authorship and credit policy, language variant contribution rules, and where to ask questions. Pre-merge follow-up commit removed a duplicated intro and a broken code fence that the original diff carried. GitHub auto-surfaces the file in the PR creation flow now.

### Fixed

- **OpenCode docs broken install/verify paths** (Issue #172 by @luyanfeng): `docs/opencode.md` referenced `planning-with-files/planning-with-files/SKILL.md` (doubled folder segment) in the manual-install block, the `cat` usage block, and both verification `ls` commands. The path assumed a full-repo clone into the skills directory rather than a direct file copy of the `.opencode/skills/planning-with-files/` subtree. v2.43.0 replaces the manual-install Quick Install with `npx skills add` (matching every other IDE doc) and rewrites the manual-install and verification commands so the path resolves to the single-level location where the skill actually lands. OpenCode session-catchup note updated to point at the SQLite store path the v2.38.0 rewrite introduced, replacing the stale "Full ... support is planned for a future release" line.

- **`.continue` variant SKILL.md sync gap from v2.34.0 to v2.43.0** (Issue #159): nine versions behind canonical. v2.43.0 ports Rule 7 (Continue After Completion), the Security Boundary section with delimiter framing and hash attestation, the expanded Scripts section listing `init-session.sh`/`set-active-plan.sh`/`resolve-plan-dir.sh`/`check-complete.sh`/`session-catchup.py`/`attest-plan.sh` plus the parallel task workflow block, the "Write web content to task_plan.md" Anti-Pattern row, and the 5-Question Reboot Test. Continue-specific items preserved: `.continue/skills/...` script paths, session-catchup invocation shape. The v2.34.0 Security Boundary table removed (canonical version supersedes it with delimiter/attestation coverage). File grew from 92 to 179 lines.

- **`.gemini` variant SKILL.md sync gap from v2.34.0 to v2.43.0** (Issue #160): nine versions behind canonical. v2.43.0 ports the same canonical content as `.continue` plus the parallel task workflow and 5-Question Reboot Test. Gemini-specific items preserved: `hooks: "Configured in .gemini/settings.json (SessionStart, BeforeTool, AfterTool, BeforeModel)"` metadata key. The Claude-specific Turn-Loop Integration section is omitted because Gemini CLI has no `/plan-goal`, `/plan-loop`, or `PreCompact` hook primitive; the Gemini-specific Security Boundary section references Gemini lifecycle hooks instead. File grew from 179 to 199 lines.

- **`.kiro` variant SKILL.md sync gap from v2.32.0-kiro to v2.43.0-kiro** (Issue #161): eleven versions behind canonical. v2.43.0 ports Rule 7, the expanded Scripts section (bootstrap, session-catchup, check-complete), the Anti-Patterns table, and the 5-Question Reboot Test. Kiro-specific items preserved: `metadata.integration: kiro` field, Agent Skill layout, `compatibility:` frontmatter key, STEP 0/1/2/3 structure, `.kiro/steering/` references, `#[[file:.kiro/plan/…]]` live references, and `assets/scripts/` path convention. Version kept as `2.43.0-kiro` per the original suffix convention.

### Changed

- Version bumped to 2.43.0 across 17 parity-locked files via `scripts/bump-version.py`. The three lagging variants (`.continue`, `.gemini`, `.kiro`) were synced manually in this release; `.pi` remains intentionally on the npm scheme (`1.1.0` in `package.json`) per AGENTS.md.

### Verification

- Test count: 130 pass, 2 skip (Windows exec-bit, pre-existing baseline since v2.34.1), 0 fail. PR #171 adds markdown only; the v2.43.0 fix for `docs/opencode.md` touches no executable paths; `.continue`, `.gemini`, and `.kiro` SKILL.md rewrites are read by the model at runtime, not parsed by the test suite. The parity test (`test_skill_md_version_parity.py`) continues to validate the 17-file parity set without drift.

### Thanks

- @Skulli485 for the CONTRIBUTING.md draft (PR #171), first contribution to the repo.
- @luyanfeng for reporting the OpenCode docs path bug (issue #172), first contribution to the repo.

## [2.42.0] - 2026-05-25

### Fixed

- **POSIX `init-session.sh` portability across the 8 mirrors** (PR #169 by @carterusedulm2-maker): the script's shebang is `#!/usr/bin/env bash`, but `tests/test_init_session_slug.py:27` invokes it via `["sh", str(INIT_SH), *args]` which bypasses the shebang and runs the body under whatever `sh` resolves to. On Ubuntu and Debian where `/bin/sh` is `dash`, the `while [[ $# -gt 0 ]]` bashism failed with a syntax error before any slug-mode argument parsing could run. v2.42.0 swaps to POSIX `while [ $# -gt 0 ]` in the 8 mirrored copies: `scripts/init-session.sh` (top level), `skills/planning-with-files/scripts/init-session.sh` (canonical), and the `.codebuddy`, `.codex`, `.continue`, `.factory`, `.gemini`, `.pi` adapter copies. Behavior is identical under bash; the change only restores compatibility under dash so the slug-mode test suite runs portably.

### Added

- **Install-scope transparency block in canonical `SKILL.md`** (Turn-Loop Integration section). Documents which install route ships which surface: `/plugin install` includes the `commands/` folder with `/plan-goal` and `/plan-loop`, but `npx skills add` (and ClawHub) install only the contents of `skills/planning-with-files/` and therefore do not register the wrapper slash commands. The `PreCompact` hook is registered in the SKILL.md frontmatter and works for both routes. Also notes the `disable-model-invocation: true` interaction tracked in upstream issues anthropics/claude-code #26251 and #41417, where some Claude Code sessions refuse to execute the slash command even when the user types it directly.
- **Manual fallback procedure** for `/plan-goal` and `/plan-loop` inline in the canonical `SKILL.md`. The procedures mirror what the `commands/plan-goal.md` and `commands/plan-loop.md` files would have fed the model when invoked: resolve the active plan, compose the goal condition or loop tick prompt, then issue Claude Code's native `/goal` or `/loop` primitive (always available, not plugin-scoped). Lets skill-only installs and sessions affected by the disable-model-invocation refusal pattern produce the same effect by following the steps inline.

### Docs

- **Topic Handoff Pattern documentation in `docs/quickstart.md` and `docs/workflow.md`** (PR #170 by @carterusedulm2-maker): documents an optional convention for splitting unrelated topics across `.planning/<slug>/` directories or a manual `handoffs/<topic>.md` detail layer alongside `progress.md`. The pattern is documentation-only; no shipped script reads `handoffs/`. Recommended for long-running operational topics that span multiple sessions, where keeping `progress.md` concise as a timeline index and putting durable detail (current state, commands, validation, risks, rollback, PR links) in a per-topic handoff file is easier to navigate after a `/clear`.
- **README releases table row for v2.42.0** plus version badge bumped to 2.42.0.

### Changed

- Version bumped to 2.42.0 across 17 parity-locked files (14 SKILL.md variants plus `plugin.json`, `marketplace.json`, `CITATION.cff`) via `scripts/bump-version.py`. `.continue`, `.gemini`, `.pi`, `.kiro` lag intentionally per AGENTS.md release scope.

### Verification

- Test count: 130 pass, 2 skip (Windows exec-bit, pre-existing baseline since v2.34.1), 0 fail. PR #169 changes shell-only string syntax across mirrored scripts; PR #170 adds markdown only. Neither touches hooks, attestation, the resolver, or any script-execution path. Security audit completed 2026-05-25 (see `.planning/2026-05-25-security-audit/findings.md`): semgrep 0 findings, no preinstall/postinstall hooks anywhere, no remote fetches, SLUG_RE path-traversal defense parity confirmed across the 14 SKILL.md variants.
- Web research basis for the transparency block: Anthropic skill docs at `code.claude.com/docs/en/skills` confirm that prompt-based slash commands are the blessed Claude Code pattern (matches bundled skills like `/loop`, `/goal`, `/run`, `/verify`, `/debug`). Quote: "Unlike most built-in commands, which execute fixed logic directly, bundled skills are prompt-based: they give Claude detailed instructions and let it orchestrate the work using its tools." The `commands/` and `skills/` directories are now unified per Anthropic: "Custom commands have been merged into skills." Plugin scope still distinguishes installation surface from `npx skills add`.

### Thanks

- @carterusedulm2-maker for both the POSIX init-session compatibility fix (PR #169) and the Topic Handoff workflow documentation (PR #170). Both filed on 2026-05-25, first contributions to the repo.

## [2.41.0] - 2026-05-24

### Fixed

- **Windows POSIX exec-bit tests now skip on NTFS** (PR #167 by @gauravvojha, Issue #166): `test_script_permissions.py` relied on POSIX executable bits which NTFS does not preserve. The two tests in the `CanonicalScriptPermissionsTests` class (`test_shell_scripts_are_executable`, `test_session_catchup_is_executable`) ran fine on Linux and macOS but always failed on Windows with `mode: 0o100666`. v2.41.0 adds a class-level `@pytest.mark.skipif(sys.platform == "win32")` decorator so the tests skip cleanly on Windows while still running on POSIX file systems. The upstream PR patch introduced a malformed duplicate standalone function at module scope and a nested method inside it; the fix was corrected to class-level granularity during merge.
- **Post-merge test-file repair** (follow-up to PR #167): the squash-merged patch from PR #167 left `tests/test_script_permissions.py` in a broken state at `ed43a71`. The standalone-function duplicate and nested class method were removed, imports re-sorted, and the class-level `pytest.mark.skipif` re-applied correctly. No test logic changed.

### Added

- **`docs/attestation-locking.md`**: new documentation page covering the `scripts/attest-plan.sh` write path, the atomic temp-rename correctness guarantee, the optional `flock` advisory lock, a platform behavior table (Linux, macOS, Windows Git Bash, WSL), and the recommended slug-mode workflow for parallel sessions. Linked from the canonical `SKILL.md` Security Boundary section for discoverability. (PR #168 by @CleanDev-Fix, Issue #165)

### Changed

- Version bumped to 2.41.0 across 17 parity-locked files (14 SKILL.md variants plus `plugin.json`, `marketplace.json`, `CITATION.cff`) via `scripts/bump-version.py`. `.continue`, `.gemini`, `.pi`, `.kiro` lag intentionally per AGENTS.md release scope.

### Verification

- Test count: 130 pass, 2 skip (Windows exec-bit tests), 0 fail. PR #167 touches only `tests/test_script_permissions.py`; PR #168 adds `docs/attestation-locking.md` plus a two-line SKILL.md link. Neither PR touches hook bodies, canonical scripts, or the attestation mechanism.

### Thanks

- @gauravvojha for reporting the Windows exec-bit failure in Issue #166 and supplying the first-pass fix in PR #167.
- @CleanDev-Fix (CleanFix-Dev) for the attestation-locking documentation in PR #168, which closes Issue #165.

## [2.40.1] - 2026-05-22

### Fixed

- **Pi adapter SKILL.md sync gap** (PR #158 by @TomXPRIME): the `.pi/skills/planning-with-files/SKILL.md` variant lagged the canonical Claude Code copy after v2.39.0 shipped. Four pieces of surface were missing on Pi: Rule 7 (Continue After Completion) covering multi-cycle plan extension when the user requests additional work, the Security Boundary section documenting the BEGIN/END delimiter framing plus the v2.37 hash attestation defense layers, the expanded Scripts section covering `set-active-plan.sh`, `resolve-plan-dir.sh`, `attest-plan.sh`, and the parallel task workflow, and the "Write web content to task_plan.md" anti-pattern row. v2.40.1 backports all four items so Pi users get the same instruction surface as Claude Code users. The redundant manual session-catchup instruction in the Pi SKILL.md is removed because the Pi extension shipped in v2.39.0 handles that lifecycle event automatically.
- **Pi npm package scope correction** (PR #158): `.pi/skills/planning-with-files/package.json` `name` field was set to the unscoped `pi-planning-with-files`. Tom owns the npm publishing chain for the Pi package; the unscoped form had ownership ambiguity. v2.40.1 renames to `@tomxprime/planning-with-files`, matching the package author's npm namespace. Author "Ahmad Othman Ammar Adi", repository URL, license, and bugs URL are preserved. No new dependencies, no preinstall or postinstall scripts, no new bin entries, no new files; only the `name` field changed.
- **Pi install docs updated** (PR #158): `.pi/skills/planning-with-files/README.md` install command updated to `pi install npm:@tomxprime/planning-with-files`. The manual install section is rewritten to use `pi install ./.pi/skills/planning-with-files` (local path) or a `.pi/settings.json` `packages` entry, replacing the previous "copy the folder into your skills dir then `/reload`" prose. SKILL.md cross-references updated to match.

### Changed

- Version bumped to 2.40.1 across the 14 SKILL.md variants, `plugin.json`, `marketplace.json`, and `CITATION.cff` via `scripts/bump-version.py`. `.continue`, `.gemini`, `.pi`, `.kiro` lag intentionally per CLAUDE.md release scope.

### Verification

- Test count: 130 pass / 2 pre-existing Windows exec-bit failures (test_script_permissions, unchanged from v2.40.0 and unrelated to this release). PR #158 changes the Pi adapter doc surface and `package.json` `name`; the Pi extension TypeScript runtime, hook bodies, and canonical Claude Code surface are not touched. Safety audit on the PR confirmed no supply-chain attack vectors: no new dependencies, no install hooks, no bin shims, no new files, author and repository metadata preserved.

### Thanks

- @TomXPRIME: second contribution after the Pi full hook parity extension in v2.39.0. The Pi adapter is now actively maintained by its author, with the npm publishing chain pointing at his scoped namespace and the SKILL.md surface kept in sync with the canonical Claude Code copy.

## [2.40.0] - 2026-05-21

### Fixed

- **Hook resolution order inverted: slug-mode now wins over legacy root** (item #1 in `proposal_v2_40.md`). Before v2.40, every hook body in `SKILL.md` checked `if [ -f task_plan.md ]` at the project root FIRST and only consulted `.planning/.active_plan` for attestation lookup, never for content lookup. When both a root `task_plan.md` and a slug-mode plan existed, the root plan silently won and the user's explicitly-active slug plan was bypassed. v2.40 rewrites the resolution chain across `UserPromptSubmit`, `PreToolUse`, and `PreCompact` so they consult `$PLAN_ID` env, then `.planning/.active_plan`, then newest `.planning/<slug>/` by mtime, and only fall back to root `task_plan.md` if no slug-mode plan resolves. Legacy single-file users keep working; parallel-plan users get the plan they actually pinned.
- **`.active_plan` target dir validated before use** (item #2). If `.active_plan` content points to a deleted plan dir, the hook used to silently no-op because the outer `if [ -f task_plan.md ]` only checked root. v2.40 falls through to the newest-mtime resolution path, then root, instead of leaving the model with no context.
- **`.active_plan` content validated against a safe-identifier regex** (item #3). `tr -d '[:space:]'` normalized whitespace-only content to an empty string, which the hook then concatenated into `.planning//task_plan.md` (an empty plan id). v2.40 enforces `^[A-Za-z0-9_][A-Za-z0-9._-]*$` on both `$PLAN_ID` env and `.active_plan` content, so corruption (whitespace, path traversal like `../escape`, leading-dot dotfile names) falls through to the next resolution step instead of producing weird path lookups.
- **`check-complete.sh` honors `$PLAN_ID` and `.active_plan`** (item #4). The Stop hook passed `.planning/$AP/task_plan.md` explicitly so the bug was silent there, but any user invocation or third-party tooling that called `check-complete.sh` with no args saw "No task_plan.md found" even with an active slug plan. v2.40 wires the script into `resolve-plan-dir.sh` when no explicit path argument is passed, restoring slug-mode parity. Behavior with an explicit path argument is unchanged.
- **Pi extension dangerous-command list uses word-boundary regex** (item #5). `runtime.ts` `isDangerousBashCommand` used substring matching against a flat list including `"git push"`. Every benign `git push origin <branch>` fired the warning, training users to ignore it. v2.40 replaces the substring list with a `DANGEROUS_BASH_PATTERNS` regex array: `\brm\s+-[a-z]*r[a-z]*f\b`, `\bsudo\b`, `\bchmod\s+(0?777|a\+rwx)\b`, `\bgit\s+push\s+.*(--force|-f\b|--mirror|\+)`, `\bgit\s+reset\s+--hard\b`, `\bgit\s+clean\s+-[a-z]*[fdx]`, a shell fork-bomb pattern, and `\bdd\s+.*of=/dev/[sh]d[a-z]`. Benign `git push` no longer triggers the notify; only destructive variants do.

### Performance

- **mtime-keyed SHA-256 cache in attestation hook** (item #6). Each `UserPromptSubmit` and `PreToolUse` hook previously ran a fresh `sha256sum` on `task_plan.md` to compare against the stored attestation. On Windows Git Bash this is ~800ms per fire dominated by bash spawn and disk I/O; over a 60-event session that is ~48 seconds of cumulative latency. v2.40 caches the result under `${TMPDIR:-/tmp}/pwf-sha/<key>` keyed by the absolute plan-file path, storing `mtime` and the hash. On the next fire, if the plan file's mtime is unchanged, the cached hash is reused without re-running `sha256sum`. The cache is per-system, transient, and invalidated automatically by any plan edit.
- **KV-cache hygiene on injected progress.md tail** (item #7). The Manus-aligned auto-injection feature is most valuable when the Claude / Sonnet / Opus prefix cache stays warm across turns. The previous injection embedded the literal `tail -20 progress.md`, including sub-second timestamps and timezone-suffix forms that change every fire. Those bytes mid-prefix prevented cache reuse. v2.40 pipes the tail through `sed -E` to normalize `T<HH:MM:SS>(.<frac>)?Z` and `T<HH:MM:SS>(.<frac>)?(+|-)HH:MM` to a stable `T00:00:00Z` / `T00:00:00<TZ>` form before injection. The model still sees recent progress structure; only the volatile sub-fields are collapsed.

### Portability

- **`resolve-plan-dir.sh` uses portable mtime fallback chain** (item #19). The old `date -r FILE +%s || stat -c '%Y' FILE || echo 0` chain silently fell to `0` on systems lacking GNU coreutils (some Windows Git Bash builds, alpine busybox, restricted CI containers). When mtime resolves to `0` for every dir in `.planning/*/`, the newest-by-mtime resolution becomes order-dependent on directory listing rather than actual recency. v2.40 extends the chain to: GNU `stat -c '%Y'`, BSD `stat -f '%m'`, `date -r FILE +%s`, `python3 -c ... os.stat`, `python -c ... os.stat`, `perl -e ... (stat $f)[9]`, then `0`. The earlier paths cover GNU + BSD + macOS + Windows Git Bash + Alpine + WSL; the python/perl fallbacks cover everything else with a runtime cost only paid when the native shell tools are absent.
- **`attest-plan.sh` uses atomic temp-rename with optional `flock` guard** (item #20). Concurrent legacy-mode attestations (two sessions in the same cwd with no `PLAN_ID`) used to race on a non-atomic `> .plan-attestation` redirect, occasionally producing a truncated or zero-length attestation that the hook then read as the expected hash and threw a false `[PLAN TAMPERED]` on the next prompt. v2.40 writes to a `.plan-attestation.tmp.<pid>` and renames into place, with `flock -w 5` around the rename when `flock` is available. The atomic-rename guarantee is the real fix; the flock is the cooperative gate against multi-writer disk-stall edge cases. The script also surfaces a one-line note when legacy-mode attestation activity is detected within 30 seconds of a prior write, pointing users to slug-mode for parallel sessions.

### Verification

- Test count: 130 pass / 2 pre-existing Windows exec-bit failures (test_script_permissions, unchanged from v2.39.0 and unrelated to this release). +20 new tests vs v2.39.0: 5 in `tests/test_resolve_plan_dir.py` covering corruption + dead-target + invalid-slug-scan, 5 in `tests/test_check_complete_resolver.py` covering the resolver wire-up, 1 concurrent-writer test in `tests/test_plan_attestation.py`, 1 word-boundary contract test in `tests/test_pi_extension_capabilities.py`, 8 hook-body behavioral tests in `tests/test_hook_body_v240.py` covering slug-beats-root, legacy-root, silent no-plan, corrupt-active-plan fall-through, SHA cache population, tamper-still-blocks, progress-timestamp normalization, and PreToolUse injection.
- Hook body now ~3.2 KB single-line bash per event (up from ~1 KB in v2.39.0). Same idiom as the existing inline pattern. Long-term extract to `scripts/inject-plan-context.sh` is tracked as v2.41-class work in `proposal_v2_40.md`.

### Changed

- Version bumped to 2.40.0 across 14 SKILL.md variants, `plugin.json`, `marketplace.json`, `CITATION.cff` via `scripts/bump-version.py`. `.continue`, `.gemini`, `.pi`, `.kiro` lag intentionally.

### Not changed (deliberate)

- No brainstorm-before-plan gate (item #8 in `proposal_v2_40.md`). Deferred to a later release because it changes user-facing workflow shape and deserves its own focused cycle.
- No new sidecar files (`decisions.md`, `lessons.md`, `await_approval.md`, dispatch queue, checkpoints). All deferred to v2.41 or v3.0 per the proposal.
- No refactor of the canonical hook body into a dedicated script (item #17). The inline pattern is preserved; the new logic ships within the same single-line idiom. This is acknowledged as maintenance debt and tracked for v2.41.

## [2.39.0] - 2026-05-21

### Added

- **Pi Coding Agent full hook parity extension** (PR #157 by @TomXPRIME): the `.pi/skills/planning-with-files/` adapter previously shipped only the markdown skill, with a docs note that hook-style automation was Claude Code specific and not available on Pi. v2.39.0 ships a bundled TypeScript extension under `.pi/skills/planning-with-files/extensions/planning-with-files/` that maps Pi lifecycle events onto the same behavior the skill provides on Claude Code. Event surface: `session_start` runs session catchup, `before_agent_start` injects plan context, `tool_call` adds pre-tool recitation, `tool_result` appends the post-write reminder to write/edit outputs, `agent_end` auto-continues incomplete plans (limit 3 per session+plan), `session_before_compact` flushes the plan reminder with the active `Plan-SHA256`, `session_shutdown` clears loop timers and per-session state, `input` resets the auto-continue counter on user activity. The extension declares itself via `pi.extensions` in `.pi/skills/planning-with-files/package.json` so `pi install npm:pi-planning-with-files` auto-loads it.
- **Pi mode system** (PR #157): four modes select how the extension talks to the model. `auto` (default) reads the active model's provider plus id, picks `cache-safe` when DeepSeek is detected, picks `parity` otherwise. `parity` reproduces the full Claude-style dynamic injection (plan content varies per fire). `cache-safe` swaps the dynamic content for fixed reminder strings so the DeepSeek KV-cache prefix stays stable across turns. `notify` surfaces the reminder via `ctx.ui.notify` only, never adds tokens to the model input. Configurable via `PWF_MODE` env var, project `.pi/settings.json`, or global `~/.pi/agent/settings.json` under the `planningWithFiles.mode` key.
- **Pi attestation gate** (PR #157): the Pi extension reads the same `.planning/<active-plan>/.attestation` file the canonical v2.37 `attest-plan.sh` writes. On every hook fire it recomputes the SHA-256 of `task_plan.md` and compares against the stored hash. On mismatch the extension blocks injection and emits the `[PLAN TAMPERED]` warning with the expected and actual hashes plus the path to re-approve. Source of truth is shared with Claude Code, so attesting once locks the plan across both runtimes.
- **Pi slash commands** (PR #157): four commands registered through `pi.registerCommand` mirror their Claude Code counterparts. `/plan-status` prints active plan path, scope, phase totals. `/plan-attest [--show|--clear]` runs the canonical attest helper (`.ps1` on Windows, `.sh` on POSIX), surfacing the result through `ctx.ui.notify`. `/plan-goal <text|default|clear>` sets a termination criterion that the auto-continue path appends to its prompt; `default` resolves to the canonical "all phases complete" condition. `/plan-loop [interval] [prompt|stop]` sets up a `setInterval` tick that re-reads the plan and nudges progress, with `stop` and `session_shutdown` both clearing the timer.
- **`.pi/skills/planning-with-files/package.json`**: declares the new `pi.extensions` array, adds `peerDependencies` for `@earendil-works/pi-coding-agent`, bumps the npm scheme to `1.1.0` to reflect the extension surface addition (npm scheme remains independent of the canonical 2.x version).
- **`docs/cache-safe-diagram.md`**: ASCII diagram showing how cache-safe mode keeps the KV-cache prefix stable across turns for DeepSeek and other prefix-sensitive models.
- **`tests/test_pi_extension_packaging.py`** (3 tests): asserts the `.pi` package.json declares `pi.extensions`, the extension entrypoint exists, and the extension directory carries all required source files.
- **`tests/test_pi_extension_capabilities.py`** (5 tests): asserts the runtime registers the four documented commands, declares all eight expected event handlers, and exposes the documented mode enum.
- **`tests/test_pi_docs_hook_support.py`** (4 tests): asserts the Pi docs no longer carry the "hooks are Claude Code specific" disclaimer, the SKILL.md surface lists the new commands, and the README documents the mode system.

### Fixed

- **Codex `[features]` flag name** (Issue #154 by @DLI1996): `docs/codex.md` instructed users to add `codex_hooks = true` under `[features]` in `~/.codex/config.toml`. OpenAI updated the canonical Codex hooks docs (developers.openai.com/codex/hooks) to make `hooks` the canonical key and `codex_hooks` a deprecated alias. v2.39.0 swaps the docs to `hooks = true` in four sites (introductory callout, the "Enable Hooks in config.toml" code block plus its follow-up prose, and the troubleshooting checklist), and adds a one-line note in each spot that `codex_hooks = true` still works as a deprecated alias so users on older configs are not pushed to migrate. Verification command updated to `rg '^(hooks|codex_hooks)\s'`.

### Changed

- Version bumped to 2.39.0 across 14 SKILL.md variants, `plugin.json`, `marketplace.json`, and `CITATION.cff` via `scripts/bump-version.py`. `.continue`, `.gemini`, `.pi`, `.kiro` lag intentionally; `.pi` carries its own npm scheme bump (1.0.1 to 1.1.0) inside `.pi/skills/planning-with-files/package.json` for the extension surface addition.

### Verification scope

- Python contract tests (110 pass, 2 pre-existing Windows exec-bit fails unrelated to this release) cover the Pi extension's packaging, declared event surface, declared command surface, and documentation. The TypeScript runtime itself runs only when loaded by a live Pi Coding Agent process. Behavior under Pi was validated by the PR author; no CI runtime test exists for the Pi extension code path. Pi-specific regressions should be filed as new issues against `.pi/skills/planning-with-files/extensions/`.

### Thanks

- @TomXPRIME for the Pi full hook parity extension (PR #157). Lifecycle event mappings, mode system, attestation gate, four slash commands, and 12 contract tests, iterated through PRs #155 and #156 to land code-only in #157.
- @DLI1996 for catching the Codex `[features]` flag drift against OpenAI's canonical docs (Issue #154).

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
