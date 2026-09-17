# Contributors

Thank you to everyone who has contributed to making `planning-with-files` better!

## Project Author

- **[Ahmad Othman Ammar Adi](https://github.com/OthmanAdi)** - Original creator and maintainer

## Code Contributors

These amazing people have contributed code, documentation, or significant improvements to the project:

### Major Contributions

- **[@kaichen](https://github.com/kaichen)** - [PR #9](https://github.com/OthmanAdi/planning-with-files/pull/9)
  - Converted the repository to Claude Code plugin structure
  - Enabled marketplace installation
  - Followed official plugin standards
  - **Impact:** Made the skill accessible to the masses

- **[@fuahyo](https://github.com/fuahyo)** - [PR #12](https://github.com/OthmanAdi/planning-with-files/pull/12)
  - Added "Build a todo app" walkthrough with 4 phases
  - Created inline comments for templates (WHAT/WHY/WHEN/EXAMPLE)
  - Developed Quick Start guide with ASCII reference tables
  - Created workflow diagram showing task lifecycle
  - **Impact:** Dramatically improved beginner onboarding

- **[@lasmarois](https://github.com/lasmarois)** - [PR #33](https://github.com/OthmanAdi/planning-with-files/pull/33), [PR #37](https://github.com/OthmanAdi/planning-with-files/pull/37)
  - Created session recovery feature for context preservation after `/clear`
  - Built `session-catchup.py` script to analyze previous session JSONL files
  - Enhanced PreToolUse hook to include Read/Glob/Grep operations
  - Restructured SKILL.md for better session recovery workflow (PR #33)
  - Extended catchup scanning to all sessions, not just the most recent one (PR #37)
  - **Impact:** Solves context loss problem, enables seamless work resumption across any session

- **[@aimasteracc](https://github.com/aimasteracc)** - [PR #30](https://github.com/OthmanAdi/planning-with-files/pull/30)
  - Added Kilocode IDE support and documentation
  - Created PowerShell scripts for Windows compatibility
  - Added `.kilocode/rules/` configuration
  - Updated documentation for multi-IDE support
  - **Impact:** Windows compatibility and IDE ecosystem expansion

- **[@SaladDay](https://github.com/SaladDay)** - [PR #57](https://github.com/OthmanAdi/planning-with-files/pull/57)
  - Fixed Stop hook POSIX sh compatibility for Debian/Ubuntu
  - Replaced bashisms (`[[`, `&>`) with POSIX constructs
  - Added shell-agnostic Windows detection using `uname -s`
  - **Impact:** Fixes hook failures on systems using dash as `/bin/sh`

- **[@murphyXu](https://github.com/murphyXu)** - [PR #56](https://github.com/OthmanAdi/planning-with-files/pull/56)
  - Added Continue IDE integration (VS Code / JetBrains)
  - Created `.continue/skills/` and `.continue/prompts/` structure
  - Added Chinese language slash command prompt
  - Created `docs/continue.md` installation guide
  - **Impact:** Expands IDE support to Continue.dev ecosystem

- **[@ZWkang](https://github.com/ZWkang)** - [PR #60](https://github.com/OthmanAdi/planning-with-files/pull/60)
  - Added CodeBuddy IDE integration (Tencent Cloud AI coding assistant)
  - Created `.codebuddy/skills/` folder with full skill structure
  - Added templates, scripts, and references for CodeBuddy
  - Created `docs/codebuddy.md` installation guide
  - **Impact:** Expands IDE support to CodeBuddy ecosystem

- **[@EListenX](https://github.com/EListenX)** (Yi Chenxi) - [PR #112](https://github.com/OthmanAdi/planning-with-files/pull/112)
  - Added full Kiro Agent Skill support under `.kiro/skills/planning-with-files/`
  - Created bootstrap scripts, steering integration with `#[[file:]]` live references
  - Replaced old `.kiro/scripts/` and `.kiro/steering/` with proper Agent Skill layout
  - Updated Cursor and Mastra Code hooks, improved docs/kiro.md
  - **Impact:** Brings Kiro IDE support to production quality with native Agent Skill format

- **[@lincolnwan](https://github.com/lincolnwan)** - [PR #80](https://github.com/OthmanAdi/planning-with-files/pull/80)
  - Added native GitHub Copilot hooks integration using the early 2026 hooks system
  - Created `.github/hooks/planning-with-files.json` with full hook scripts in `.github/hooks/scripts/`
  - Full cross-platform support (bash + PowerShell) and `docs/copilot.md` installation guide
  - **Impact:** Brought total supported platforms to 15, expanding the skill to the GitHub Copilot ecosystem

- **[@ciberponk](https://github.com/ciberponk)** - [PR #77](https://github.com/OthmanAdi/planning-with-files/pull/77)
  - Added isolated `.planning/{uuid}/` plan sessions with UUID generation and PLAN_ID pinning
  - Enables parallel planning sessions in separate terminals without state collision
  - Cross-platform scripts (bash + PowerShell) with full backward compatibility for single-session users
  - **Impact:** Unlocks parallel planning workflows, shipped to experimental branch ahead of master

- **[@ttttmr](https://github.com/ttttmr)** - [PR #67](https://github.com/OthmanAdi/planning-with-files/pull/67)
  - Added Pi Agent support with full skill integration
  - **Impact:** Expands the skill to the Pi Agent ecosystem

- **[@mvanhorn](https://github.com/mvanhorn)** (Matt Van Horn) - [PR #115](https://github.com/OthmanAdi/planning-with-files/pull/115), [PR #174](https://github.com/OthmanAdi/planning-with-files/pull/174), [PR #175](https://github.com/OthmanAdi/planning-with-files/pull/175)
  - Added analytics workflow template with `--template analytics` flag on `init-session.sh` and `init-session.ps1`
  - Created `analytics_task_plan.md` with 4 analytics-specific phases (Data Discovery, Exploratory Analysis, Hypothesis Testing, Synthesis)
  - Created `analytics_findings.md` with Data Sources table, Hypothesis Log, Query Results, and Statistical Findings sections
  - Analytics-specific `progress.md` with Query Log replacing Test Results
  - PR #175: added a TypeScript integration test suite for the Pi extension under `.pi/skills/planning-with-files/extensions/planning-with-files/__tests__/`, covering all eight lifecycle handlers, the four runtime modes (auto, parity, cache-safe, notify), and the SHA-256 attestation gate (match, mismatch, invalid hash); a maintainer follow-up aligned one parity-mode assertion with the runtime's lowercase banner text (closes #163)
  - PR #174: documented the attestation SHA cache (location priority, keying, container and CI behavior, and how to clear it) in `docs/perf-notes.md`; a maintainer follow-up updated the documented path from the v2.40 `/tmp` location to the v3 `$XDG_CACHE_HOME/pwf-sha` path (closes #164)
  - **Impact:** Extends the planning pattern to data analytics workflows (addresses #103), and closes two v2.x good-first-issue follow-ups with real Pi extension test coverage and accurate cache documentation

- **[@ebrevdo](https://github.com/ebrevdo)** (Eugene Brevdo) - [PR #124](https://github.com/OthmanAdi/planning-with-files/pull/124)
  - Rewrote `session-catchup.py` to support Codex rollout JSONL session format
  - Added `CODEX_THREAD_ID` preference, subagent/tiny session filtering, and structured `patch_apply_end` event detection
  - Updated tests and docs for the new Codex catchup behavior
  - **Impact:** Brings session recovery parity to Codex users

- **[@bailob](https://github.com/bailob)** - [PR #136](https://github.com/OthmanAdi/planning-with-files/pull/136)
  - Added Hermes adapter with project plugin, Hermes facing `planning-with-files` skill, and `/plan` plus `/plan-status` command wrappers
  - Bundled Hermes skill templates and scripts inside `.hermes/skills/planning-with-files/` and resolved them through the active profile's `HERMES_HOME`
  - Added 20 unit tests covering status parsing, reminder behavior, installation layout, and completion checks
  - **Impact:** Brings planning-with-files to the Hermes ecosystem as platform 17

### Other Contributors

- **[Shaun Lin](https://github.com/ShaunLinTW)**, [PR #245](https://github.com/OthmanAdi/planning-with-files/pull/245), [PR #247](https://github.com/OthmanAdi/planning-with-files/pull/247)
  - Isolated Python calls in the Codex, Gemini, and GitHub Copilot shell adapters and added regression coverage for project-local import shadowing.
  - Added named-plan slug mode to the PowerShell initializer with root-mode policy inheritance, host-aware attestation, and Windows PowerShell regression coverage.

- **[@kuei51307-hub](https://github.com/kuei51307-hub)**, [PR #243](https://github.com/OthmanAdi/planning-with-files/pull/243), [PR #244](https://github.com/OthmanAdi/planning-with-files/pull/244), [PR #248](https://github.com/OthmanAdi/planning-with-files/pull/248), [PR #249](https://github.com/OthmanAdi/planning-with-files/pull/249)
  - Fixed active-plan display and listing for UTF-8 BOM-prefixed pointers, with regression coverage across the synchronized shell helpers.
  - Made IDE sync verification report missing canonical sources, with subprocess tests for read-only verification and unchanged sync behavior.
  - Bounded session catchup to exact planning filenames across the canonical scanners and the Hermes, MastraCode, and OpenCode adapters, with lookalike regression coverage.
  - Replaced the shell initializer's active-pointer write with the selector's contained atomic update and added hardlink, symlink, and junction regressions.

- **[@Dphoshoba](https://github.com/Dphoshoba)**, [PR #242](https://github.com/OthmanAdi/planning-with-files/pull/242)
  - Proposed and implemented named-plan listing with phase counts and a shared active-pointer marker.

- **[@sunznx](https://github.com/sunznx)**, [Issue #240](https://github.com/OthmanAdi/planning-with-files/issues/240), [Issue #241](https://github.com/OthmanAdi/planning-with-files/issues/241)
  - Reported and reproduced named-plan crossover between Codex sessions sharing a working directory after compaction.
  - Reported the 13 duplicate Codex command skills, traced the legacy command fallback, and proposed the native manifest setting that disables it.

- **[@hzura](https://github.com/hzura)**, [Issue #50](https://github.com/OthmanAdi/planning-with-files/issues/50)
  - Raised the same-repository parallel-task workflow that led to explicit plan selection and shared-file ownership guidance.

- **[@wangxiaodong1021](https://github.com/wangxiaodong1021)**, [Issue #50](https://github.com/OthmanAdi/planning-with-files/issues/50)
  - Reported session crossover during parallel Codex work, prompting reproduction with two attached sessions and separate plan pins.

- **[Raymond Manaloto](https://github.com/sortakool)** - [Issue #234](https://github.com/OthmanAdi/planning-with-files/issues/234), [Issue #236](https://github.com/OthmanAdi/planning-with-files/issues/236), [Issue #237](https://github.com/OthmanAdi/planning-with-files/issues/237), [Issue #238](https://github.com/OthmanAdi/planning-with-files/issues/238), [Issue #239](https://github.com/OthmanAdi/planning-with-files/issues/239)
  - Reproduced the nested attestation failure and traced it to the fallback from slug mode to legacy mode when the helper runs inside `.planning/<slug>/`
  - Found that `plan-doctor.sh` matched its control strings against the injected plan body, so a plan quoting one of them reported a false tamper warning, and that a stale literal at `:92` made a fully dark-hooks state report PASS. Supplied the structural alternative that replaced the string matching, and the four test arms
  - Showed that a `PLAN_ID` of valid slug shape naming no directory fell through to another plan, which then got attested at rc=0, with a control arm proving the probe could return the right plan
  - Showed that a slug plan with no `.mode` bypassed a project's committed root `.mode`, with a control arm removing the slug directory to prove it was a bypass rather than a mode that was never armed
  - Traced the PostToolUse progress reminder to `systemMessage`, a field Claude Code delivers to the user, so an instruction written for the model reached the person instead on every matching tool call, and checked the Codex adapter for the same defect before filing
  - **Impact:** Attestation and injection follow the plan the operator named or refuse; a project's `.mode` is a floor a plan cannot start below; `/plan-doctor` classifies on the data framing, so a reworded banner degrades to a warning instead of a silent PASS; and the progress reminder reaches the model, once per turn, without firing on read-only shell commands

- **[@lowmiaq-gmail](https://github.com/lowmiaq-gmail)** - [PR #233](https://github.com/OthmanAdi/planning-with-files/pull/233) / [Issue #232](https://github.com/OthmanAdi/planning-with-files/issues/232)
  - Reported that direct help flags were parsed as project names, then supplied a focused POSIX-shell fix and regression covering both `-h` and `--help` against an empty working directory
  - **Impact:** Direct help queries print usage and return successfully without creating planning files or replacing `.planning/.active_plan`

- **[@webwww123](https://github.com/webwww123)** - [Issue #212](https://github.com/OthmanAdi/planning-with-files/issues/212)
  - Reported that a Codex thread whose cwd is a shared parent injects an unrelated nested project's plan on every hook fire, with a working reproduction, a correct trace of the `PLAN_ID` to `.active_plan` to newest-by-mtime chain, and the observation that the Agent Skills route never received the session-attachment mechanism the `.codex` hooks got in #146
  - **Impact:** v3.9.0 adds `PWF_PLAN_ROOT` for an absolute plan root binding that a cwd relative slug could not express, refuses to inject on an ambiguous cwd instead of guessing, and moves all eleven stale hook bearing SKILL.md variants onto the hardened dispatcher. Verifying the report also exposed that `PLANNING_DISABLED=1` was inoperative on those eleven routes, that the Stop hook could never find its script on six hosts, and that eight shipped PowerShell scripts could not be parsed by Windows PowerShell 5.1 at all

- **[@killianMei](https://github.com/killianMei)** - [Issue #211](https://github.com/OthmanAdi/planning-with-files/issues/211)
  - Traced the Pi extension's follow-up amplification to an `agent_end` handler that ignores its event argument entirely, and the stale status bar to the specific handlers that never publish once a plan is execution approved, citing every call site
  - **Impact:** v3.9.0 returns from `agent_end` on a trailing assistant `stopReason` of `error` or `aborted` before the auto continue counter is touched, so a provider outage costs no retry budget, and publishes the phase count from all four active handlers including the all-phases-complete branch where the final transition never reached the bar; bundled Pi extension bumped to 1.2.3

- **[@GlitterKill](https://github.com/GlitterKill)** - [Issue #210](https://github.com/OthmanAdi/planning-with-files/issues/210)
  - Asked whether plan injection is deterministic enough not to break prompt caching, a question the project had never actually measured for the injection script itself
  - **Impact:** v3.9.0 asserts byte-identical injection across fires in every context and mode, normalizes wall clock timestamps on the five routes that had never received the v2.40 pass, and corrects the skill text that attributed a whole-workflow token measurement to per tool call recitation

- **[@seathatflowsinourveins](https://github.com/seathatflowsinourveins)** - [Issue #209](https://github.com/OthmanAdi/planning-with-files/issues/209)
  - Reported that `session-catchup.py` never folded `.` while Claude Code does, so any project path containing a dot resolved to a `~/.claude/projects` directory that is never written, citing the exact blob, the two sanitize branches, and the `main()` line where the miss returns exit 0 with no output
  - **Impact:** v3.8.2 folds every character Claude Code folds in the three remaining copies (one of them the copy every `/plugin install` runs on Linux, macOS and Git Bash), counts UTF-16 code units so emoji folder names resolve, and adds a per-session `cwd` filter so two projects sharing one folded directory name cannot read each other's transcripts

- **[@fd44fdg](https://github.com/fd44fdg)** - [Issue #208](https://github.com/OthmanAdi/planning-with-files/issues/208)
  - Reported that a stale `.planning/<id>/` directory silently shadowed a fresh root `task_plan.md` in the Pi extension while a false "No task_plan.md found" warning fired on every write and edit, with a root-cause trace against `resolvePlanPaths` and the `runtime.ts` warning path
  - **Impact:** v3.8.1 anchors Pi plan resolution on the nearest ancestor with planning state (bounded by the `.git` repository boundary), labels every injection with the resolved plan id so shadowing is visible, and kills the subdirectory warning loop; bundled Pi extension bumped to 1.2.2

- **[@jschmied](https://github.com/jschmied)** - [Issue #206](https://github.com/OthmanAdi/planning-with-files/issues/206)
  - Diagnosed that pre-tool recitations and the tamper notice queued by the Pi extension's `tool_call` hook were delivered as steer, and that an interactive tool such as AskUserQuestion blocking the turn on its own custom UI consumed that steer text as the dialog's answer instead of letting it reach the model, pinning down the precise runtime location of the collision and the `nextTurn` delivery fix that shipped
  - **Impact:** v3.5.1 delivers Pi extension recitations and the tamper notice as `nextTurn` instead of steer, so interactive tool dialogs no longer swallow injected planning text; bundled Pi extension bumped to 1.2.1

- **[@yolo0731](https://github.com/yolo0731)** (yoloyq) - [PR #205](https://github.com/OthmanAdi/planning-with-files/pull/205), closes [Issue #204](https://github.com/OthmanAdi/planning-with-files/issues/204)
  - Fixed the Codex hooks on Windows emitting invalid JSON and failing on Unicode: plain `[planning-with-files]` stdout where Codex expects `hookSpecificOutput.additionalContext` or a common-fields object, UTF-8 shell output decoded through the Windows code page, and `ensure_ascii=False` JSON written through cmd.exe
  - Serialized each event in its supported Codex JSON shape with ASCII-safe output, decoded shell output as UTF-8, routed PreToolUse plan text through model-visible `additionalContext`, resolved scoped plans in PermissionRequest, added `clear|compact` SessionStart sources, wrote the `.active_plan` pointer without a BOM, and hardened the containment resolver to fail closed
  - **Impact:** v3.5.0 makes the full Codex hook surface work on Windows across active-plan, no-plan, disabled, malformed-input, and Unicode scenarios

- **[@ziyu4huang](https://github.com/ziyu4huang)** (Ziyu Huang) - [Issue #203](https://github.com/OthmanAdi/planning-with-files/issues/203)
  - Reported that a closed and complete plan kept emitting "Task incomplete" nags for many turns, with a root-cause trace against the Pi extension's own exported `resolvePlanPaths`, `readPlanStatus`, and `isPlanIncomplete`
  - **Impact:** v3.5.0 ranks newest-plan resolution by `task_plan.md` file mtime, adds close-marker awareness, and gates the nag on `status.closed`

- **[@kcinzgg](https://github.com/kcinzgg)** (Kcinzgg) - [Issue #202](https://github.com/OthmanAdi/planning-with-files/issues/202)
  - Asked for a direct statement of the plan-file lifecycle and why there is no archiving step, noting the earlier #14 had no visible resolution
  - **Impact:** v3.5.0 documents the ephemeral-working-memory lifecycle in `docs/workflow.md`, with pointers from `quickstart.md` and the README FAQ

- **[@mahdiit](https://github.com/mahdiit)** (Mahdi) - [Issue #201](https://github.com/OthmanAdi/planning-with-files/issues/201), [PR #207](https://github.com/OthmanAdi/planning-with-files/pull/207)
  - Reported that Codex hooks failed on Windows with `hook exited with code 1`: the `.codex/hooks.json` commands were POSIX only, so the Windows command interpreter choked on `python3` (the Store alias), `2>/dev/null`, and the `|| true` success guard whose `true` is not a Windows command
  - PR #207: after v3.4.1 still did not clear the hook errors on his machine, traced the remaining failure to the shell resolver preferring the WSL bash launcher over Git Bash whenever `usr\bin` was off PATH, and to `pwf-hook.cmd` losing the Python interpreter under Codex's reduced PATH; produced the fix with Codex Terra, having the resolver skip WSL launchers and adding a `PYTHON_BIN` override plus standard install-location probing to the launcher
  - **Impact:** v3.4.1 adds per-hook `commandWindows` overrides, a `pwf-hook.cmd` launcher, a `run_sh.py` front door, and a git-bash resolver so all seven Codex hooks run on Windows; v3.5.1 closes the remaining WSL-launcher and Python-discovery gaps that PR #207 found

- **[@Dikshj](https://github.com/Dikshj)** (diksha) - [PR #193](https://github.com/OthmanAdi/planning-with-files/pull/193), closes [Issue #190](https://github.com/OthmanAdi/planning-with-files/issues/190)
  - Added the `/plan-execute` approval command to the Pi extension: hooks previously activated the moment `task_plan.md` existed, so plan injection, pre-tool recitation, post-write reminders, and auto-continue could start while the user was still reviewing a draft plan
  - The extension now stays passive (status line only) until the user approves the active plan; approval is scoped to the current session and plan path, resets on session lifecycle events, and `/plan-execute reset` returns to passive review mode
  - A plan with a tampered SHA-256 attestation cannot be approved, and the runtime test suite plus Python docs guards cover the passive review flow
  - **Impact:** Pi users can draft and review a plan without the extension pushing execution before they have confirmed it, closing the workflow gap reported in #190

- **[@2023Anita](https://github.com/2023Anita)** - [PR #180](https://github.com/OthmanAdi/planning-with-files/pull/180), [Issue #178](https://github.com/OthmanAdi/planning-with-files/issues/178)
  - Made the Codex Stop hook non-blocking for incomplete plans: `.codex/hooks/stop.py` previously emitted `{"decision": "block"}` on the first stop while phases were still pending, which pushed the agent to continue into the next phase without the user asking
  - Collapsed the conditional block path to a single advisory `systemMessage` and rewrote `.codex/hooks/stop.sh` to drop the imperative "continue working on the remaining phases" wording, keeping only the progress-sync reminder
  - **Impact:** Codex users no longer get trapped in auto-continuation. An incomplete plan is treated as a normal state, matching the v3 principle that an incomplete plan alone never blocks a stop (closes #178)

- **[@GongYuanCaiJi](https://github.com/GongYuanCaiJi)** - [PR #181](https://github.com/OthmanAdi/planning-with-files/pull/181)
  - Closed the Codex `hooks.json` PreCompact parity gap: the native Codex lifecycle wiring declared every event except PreCompact, while the canonical SKILL.md has carried PreCompact since v3.0.0
  - Added `.codex/hooks/pre-compact.sh` (POSIX sh, reuses `resolve-plan-dir.sh`, emits the same flush reminder and `Plan-SHA256` line as the canonical hook), wired it into `.codex/hooks.json`, corrected the `docs/codex.md` hook table, and added two targeted tests
  - **Impact:** Codex users on the native `hooks.json` route now get the pre-compaction progress-flush reminder. The hook stays dormant on runtimes that never fire a PreCompact event, with `|| true` wiring that cannot break a session

- **[@Fat-Jan](https://github.com/Fat-Jan)** (Alonso) - [PR #184](https://github.com/OthmanAdi/planning-with-files/pull/184)
  - Updated the `docs/codex.md` verification block to grep `^(hooks|codex_hooks)\s` instead of the bare `^codex_hooks\s`, and aligned the follow-up troubleshooting sentence with the `hooks = true` guidance stated earlier in the same document
  - The bare pattern stopped matching once Codex moved its canonical feature key from `codex_hooks` to `hooks` in 0.129.0 (openai/codex#20522); the alias still resolves in `config.toml`, but `codex features list` prints only the canonical `hooks`, so the verify step was telling correctly configured users to upgrade
  - **Impact:** the documented verification command matches on current Codex versions again, and `docs/codex.md` is internally consistent across the six places that reference the feature flag

- **[@shunfeng8421](https://github.com/shunfeng8421)** - [PR #186](https://github.com/OthmanAdi/planning-with-files/pull/186), [Issue #185](https://github.com/OthmanAdi/planning-with-files/issues/185)
  - Fixed the session-catchup command for skill-only installs: the documented Restore Context command used `${CLAUDE_PLUGIN_ROOT}`, which the plugin runtime sets only inside hook execution, so a user who installed via `npx skills add` or on Codex or Cursor and ran it in a normal shell got an empty variable and a broken `/scripts/...` path
  - Switched to `SKILL_DIR="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/skills/planning-with-files}"` across the canonical file, the `.codebuddy` variant, and the five language variants, keeping the plugin path as priority and the Windows PowerShell block unchanged
  - **Impact:** skill-only installs can run the documented catchup command and get a working path, with no behavior change for plugin users. The same fallback was extended to the `.hermes` variant in the release commit. The underlying problem was surfaced by @xwang118 in PR #183 and tracked in #185

- **[@Skulli485](https://github.com/Skulli485)** - [PR #171](https://github.com/OthmanAdi/planning-with-files/pull/171), [Issue #162](https://github.com/OthmanAdi/planning-with-files/issues/162)
   - Authored the first `CONTRIBUTING.md` at the repo root, covering local setup, project layout, PR submission conventions, authorship and credit policy, language variant contribution rules, and where to ask questions
   - A pre-merge follow-up commit by the maintainer removed a duplicated intro and a broken four-backtick code fence from the original diff
   - **Impact:** new contributors now land on a dedicated guide auto-surfaced by GitHub in the PR creation flow, replacing the previous inference-based onboarding from `CLAUDE.md` and prior merged PRs

- **[@carterusedulm2-maker](https://github.com/carterusedulm2-maker)** - [PR #169](https://github.com/OthmanAdi/planning-with-files/pull/169), [PR #170](https://github.com/OthmanAdi/planning-with-files/pull/170)
  - PR #169: replaced the `[[ $# -gt 0 ]]` bashism in `init-session.sh` with POSIX `[ $# -gt 0 ]` across the 8 mirrored copies (canonical, `.codebuddy`, `.codex`, `.continue`, `.factory`, `.gemini`, `.pi`, top-level `scripts/`). The script's shebang is `#!/usr/bin/env bash`, but `tests/test_init_session_slug.py` invokes it via `["sh", str(INIT_SH), ...]` which bypasses the shebang and runs under `dash` on Ubuntu, where the `[[ ]]` syntax fails before any slug-mode logic can execute
  - PR #170: documented a Topic Handoff Pattern in `docs/quickstart.md` and `docs/workflow.md` for splitting unrelated topics across `.planning/<slug>/` directories or a manual `handoffs/<topic>.md` detail layer alongside `progress.md`
  - **Impact:** the test invocation through `sh` now runs cleanly across Linux distributions with non-bash `/bin/sh`; the documentation surfaces the slug-mode and handoff convention as the recommended workflow for parallel and long-running topics

- **[@gauravvojha](https://github.com/gauravvojha)** - [PR #167](https://github.com/OthmanAdi/planning-with-files/pull/167), [Issue #166](https://github.com/OthmanAdi/planning-with-files/issues/166)
  - Reported that `test_script_permissions.py` always failed on Windows because NTFS does not preserve POSIX executable bits
  - Supplied the initial `pytest.mark.skipif(sys.platform == "win32")` patch for the two exec-bit tests
  - **Impact:** The two pre-existing Windows exec-bit failures (present since v2.34.1) now skip cleanly on Windows, keeping the test suite green across all platforms

- **[@CleanDev-Fix](https://github.com/CleanDev-Fix)** (CleanFix-Dev) - [PR #168](https://github.com/OthmanAdi/planning-with-files/pull/168), [Issue #165](https://github.com/OthmanAdi/planning-with-files/issues/165)
  - Authored `docs/attestation-locking.md`, a dedicated page documenting the `attest-plan.sh` write path, the atomic temp-rename guarantee, the optional `flock` advisory lock, platform-specific fallback behavior, and the recommended slug-mode parallel workflow
  - Wired the new page into the canonical `SKILL.md` Security Boundary section for discoverability
  - **Impact:** Users on macOS and Windows Git Bash who hit the "flock not found" code path now have a clear explanation of why attestation still works and why slug-mode is preferred for concurrent sessions

- **[@bmyury](https://github.com/bmyury)** - [Discussion #153](https://github.com/OthmanAdi/planning-with-files/discussions/153)
  - Reported that the installed skill's description field appeared garbled in Claude Code, surfacing fragments of hook command output instead of the documented description
  - Root cause: the `'---BEGIN PLAN DATA---'` and `'---END PLAN DATA---'` plan-injection delimiters embedded in hook commands collided with the `---` YAML document separator; Claude Code's skill-discovery loader split frontmatter on the literal `---` substring and truncated the description mid-string
  - **Impact:** v2.38.1 swaps the delimiter shape to `===BEGIN PLAN DATA===` / `===END PLAN DATA===` across the canonical SKILL.md, all five language variants, the `.codebuddy/.codex/.cursor` adapter mirrors, and the `clawhub-upload` bundle. Same model-side framing semantics, no collision with the YAML separator

- **[@oaabahussain](https://github.com/oaabahussain)** - [Issue #150](https://github.com/OthmanAdi/planning-with-files/issues/150), [Issue #151](https://github.com/OthmanAdi/planning-with-files/issues/151)
  - Issue #150: pointed out that the v2.36.1 BEGIN/END delimiters were a mitigation, not a guarantee, and proposed SHA-256 hash attestation so any silent edit to `task_plan.md` between user approval and hook injection trips a verifiable check
  - Issue #151: named the regression class behind v2.34.1, v2.36.0, v2.36.2, and v2.36.3 (parity-locked files updated by hand across 19 destinations) and proposed the right surgical fix: a single bumper script plus a CI parity test
  - **Impact:** v2.37.0 ships `/plan-attest`, `attest-plan.sh/.ps1`, `bump-version.py`, and two new test files that turn both report classes into things that fail the build instead of shipping silently

- **[@gavinlinasd](https://github.com/gavinlinasd)** - [PR #135](https://github.com/OthmanAdi/planning-with-files/pull/135)
  - Added ClawHub download history chart to README, tracking skill download growth over time
  - **Impact:** Visitors can now see download traction at a glance

- **[@xiaolai](https://github.com/xiaolai)** - [PR #137](https://github.com/OthmanAdi/planning-with-files/pull/137), [PR #138](https://github.com/OthmanAdi/planning-with-files/pull/138), [PR #139](https://github.com/OthmanAdi/planning-with-files/pull/139), [Issue #140](https://github.com/OthmanAdi/planning-with-files/issues/140)
  - Ran the NLPM (Natural Language Programming Manager) audit on the plugin and filed 3 targeted fix PRs plus a full audit summary issue (overall score 91/100)
  - PR #137: fixed a missing quote in the Pi variant PowerShell session-catchup invocation that caused the command to fail silently on Windows
  - PR #138: capped session-catchup output at 100 lines with a labeled prefix before injecting into model context, closing a prompt injection vector from stored session content
  - PR #139: preferred known system Python paths over unqualified PATH resolution in `session-start.sh`, `pre-tool-use.sh`, and `error-occurred.sh`
  - **Impact:** Hardened the Copilot hook scripts and the Pi variant in one coordinated audit pass

- **[@githubYiheng](https://github.com/githubYiheng)** - [Issue #146](https://github.com/OthmanAdi/planning-with-files/issues/146)
  - Reported Codex session isolation failure: any Codex session in a shared working directory received the active plan context from an unrelated session, because the hooks keyed only on `task_plan.md` presence
  - Traced the code path through `user-prompt-submit.sh`, `pre_tool_use.py`, and `stop.py`, and proposed the session attachment model as a fix direction
  - **Impact:** Led to `$PWF_SESSION_ID` + sentinel file isolation, backward-compatible upgrade path, and 5 new targeted tests

- **[@09ashishkapoor](https://github.com/09ashishkapoor)** - [Issue #147](https://github.com/OthmanAdi/planning-with-files/issues/147)
  - Filed a detailed Hermes documentation gap report: the integration worked but docs implied feature parity with hook-native platforms, leading to user confusion when stop/block behavior differed
  - Outlined the four sections needed (what works, what is not equivalent, recommended pattern, tradeoffs) with enough specificity to write from directly
  - **Impact:** `docs/hermes.md` now has an `Integration Notes` section that sets accurate expectations for Hermes adopters

- **[@shawnli1874](https://github.com/shawnli1874)** - [Issue #148](https://github.com/OthmanAdi/planning-with-files/issues/148)
  - Reported that v2.0.0 hooks broke parallel multi-task workflows by hardcoding `task_plan.md` at the project root, removing the placement flexibility that CLAUDE.md conventions had previously allowed
  - Provided a concrete reproduction with anonymized task files showing how parallel sessions contaminated each other after a few hours of work
  - Proposed the `YYYY-MM-DD-<slug>/` naming convention as a human-readable alternative to the UUID approach in `experimental/isolated-planning`
  - **Impact:** Slug-based `init-session.sh`, `set-active-plan.sh`, `resolve-plan-dir.sh`, and the full Codex hook resolver wire-up all trace back to this report

- **[@Leon-Algo](https://github.com/Leon-Algo)** - [PR #119](https://github.com/OthmanAdi/planning-with-files/pull/119), [PR #120](https://github.com/OthmanAdi/planning-with-files/pull/120), [PR #122](https://github.com/OthmanAdi/planning-with-files/pull/122)
  - Made planning scripts executable in `.codex` skill install, fixing Codex installer breakage (PR #119)
  - Added official Codex hooks.json integration with full lifecycle hooks — SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop — bringing Codex to full hook parity with other IDEs (PR #120)
  - Fixed canonical script execute bits for `check-complete.sh` and `init-session.sh` with regression test (PR #122)
  - **Impact:** Codex users now get the same automatic context injection and lifecycle automation as Claude Code and Cursor users

- **[@YSAA1](https://github.com/YSAA1)** - [PR #109](https://github.com/OthmanAdi/planning-with-files/pull/109)
  - Fixed Codex session-catchup fallback that was silently broken after the session path changes

- **[@kevinaimonster](https://github.com/kevinaimonster)** - [PR #108](https://github.com/OthmanAdi/planning-with-files/pull/108)
  - Added Simplified Chinese localization support, extending the skill to Chinese-language users

- **[@wd041216-bit](https://github.com/wd041216-bit)** - [PR #107](https://github.com/OthmanAdi/planning-with-files/pull/107)
  - Added openclaw-github-repo-commander to the Community Built section, expanding the ecosystem showcase

- **[@popey](https://github.com/popey)** - [PR #83](https://github.com/OthmanAdi/planning-with-files/pull/83)
  - Fixed `allowed-tools` YAML list (invalid per Anthropic skill spec, silently killing discoverability)
  - Fixed `metadata.version` placement and added trigger terms for better skill matching
  - Applied across the canonical SKILL.md file

- **[@jonthebeef](https://github.com/jonthebeef)** - [PR #75](https://github.com/OthmanAdi/planning-with-files/pull/75)
  - Added `/plan:status` command for quick planning progress display without reading through all planning files

- **[@codelyc](https://github.com/codelyc)** - [PR #66](https://github.com/OthmanAdi/planning-with-files/pull/66), [PR #70](https://github.com/OthmanAdi/planning-with-files/pull/70), [PR #76](https://github.com/OthmanAdi/planning-with-files/pull/76)
  - Fixed Codex skill path references and replaced CLAUDE_PLUGIN_ROOT with correct absolute paths (PR #66)
  - Fixed CodeBuddy skill path references and environment variables (PR #70)
  - Added OpenCode scripts for the planning-with-files skill (PR #76)

- **[@Guozihong](https://github.com/Guozihong)** - [PR #51](https://github.com/OthmanAdi/planning-with-files/pull/51)
  - Added `/planning-with-files:start` command, enabling skill activation without copying files manually

- **[@fahmyelraie](https://github.com/fahmyelraie)** - [PR #49](https://github.com/OthmanAdi/planning-with-files/pull/49)
  - Fixed Stop hook path resolution when CLAUDE_PLUGIN_ROOT is not set in the environment

- **[@olgasafonova](https://github.com/olgasafonova)** - [PR #46](https://github.com/OthmanAdi/planning-with-files/pull/46)
  - Added SkillCheck validation badge after running the skill through spec validation

- **[@AZLabsAI](https://github.com/AZLabsAI)** - [PR #65](https://github.com/OthmanAdi/planning-with-files/pull/65)
  - Updated OpenClaw docs to reflect the product rename from Moltbot, correcting all paths and CLI commands

- **[@raykuo998](https://github.com/raykuo998)** - [PR #88](https://github.com/OthmanAdi/planning-with-files/pull/88), [PR #86](https://github.com/OthmanAdi/planning-with-files/pull/86)
  - Fixed `check-complete.ps1` completely failing on PowerShell 5.1 due to special character parse errors in double-quoted strings; switched to single-quoted strings with concatenation across all 12 platform copies (PR #88)
  - Fixed Stop hook YAML multiline command block failing under Git Bash on Windows; collapsed 25-line OS detection to single-line implicit platform fallback chain across all 7 SKILL.md variants (PR #86)

- **[@gydx6](https://github.com/gydx6)** - [PR #79](https://github.com/OthmanAdi/planning-with-files/pull/79)
  - Fixed session-catchup false positives in all 9 skill-distributed copies
  - Added early return guards for non-planning projects
  - Thorough bug report with root cause analysis
  - **Impact:** Eliminates noise from false catchup reports

- **[@waynelee2048](https://github.com/waynelee2048)** - [PR #113](https://github.com/OthmanAdi/planning-with-files/pull/113)
  - Added Traditional Chinese (zh-TW) skill variant with fully translated SKILL.md, templates, and scripts
  - Includes localized hooks, check-complete, init-session, and session-catchup scripts

- **[@tobrun](https://github.com/tobrun)** - [PR #3](https://github.com/OthmanAdi/planning-with-files/pull/3)
  - Early directory structure improvements
  - Helped identify optimal repository layout

- **[@markocupic024](https://github.com/markocupic024)** - [PR #4](https://github.com/OthmanAdi/planning-with-files/pull/4)
  - Cursor IDE support contribution
  - Helped establish multi-IDE pattern

- **Copilot SWE Agent** - [PR #16](https://github.com/OthmanAdi/planning-with-files/pull/16)
  - Fixed template bundling in plugin.json
  - Added `assets` field to ensure templates copy to cache
  - **Impact:** Resolved template path issues

- **[@tt-a1i](https://github.com/tt-a1i)** - [PR #92](https://github.com/OthmanAdi/planning-with-files/pull/92), [PR #99](https://github.com/OthmanAdi/planning-with-files/pull/99), [PR #100](https://github.com/OthmanAdi/planning-with-files/pull/100)
  - Fixed broken Advanced Topics links in Codex SKILL.md (PR #92)
  - Fixed 5 consistency issues across docs: broken links in opencode.md and factory.md, stale `notes.md` references replaced with `findings.md` across all 16 IDE copies, OpenCode support label corrected in README, `--help` in sync-ide-folders.py no longer runs a sync (PR #99)
  - Fixed Codex session-catchup silently scanning Claude session paths; now prints an explicit fallback message when running from Codex context (PR #100)
  - **Impact:** Significant docs and tooling consistency sweep across the entire multi-IDE surface

- **[@Emin017](https://github.com/Emin017)** (Qiming Chu) - [PR #145](https://github.com/OthmanAdi/planning-with-files/pull/145)
  - Changed shebangs from `/bin/bash` to `/usr/bin/env bash` across hook scripts
  - Fixes compatibility on systems like NixOS where bash is not at `/bin/bash`

- **[@TomXPRIME](https://github.com/TomXPRIME)** - [PR #157](https://github.com/OthmanAdi/planning-with-files/pull/157), [PR #158](https://github.com/OthmanAdi/planning-with-files/pull/158)
  - PR #157: brought the `.pi` adapter up to full hook parity with Claude Code by shipping a bundled TypeScript extension under `.pi/skills/planning-with-files/extensions/planning-with-files/`
  - Mapped eight Pi lifecycle events to the same behavior the skill provides on Claude Code: `session_start` runs session catchup, `before_agent_start` injects plan context, `tool_call` adds pre-tool recitation, `tool_result` appends the post-write reminder, `agent_end` auto-continues incomplete plans with a per-session+plan limit of three, `session_before_compact` flushes the plan reminder with the active `Plan-SHA256`, `session_shutdown` clears loop timers and per-session state, `input` resets the auto-continue counter
  - Added a four-mode system (`auto`, `parity`, `cache-safe`, `notify`) with DeepSeek auto-detection from `ctx.model.provider` and `ctx.model.id`, so cache-prefix-sensitive models keep their KV-cache stable
  - Wired the existing v2.37 SHA-256 attestation gate into the Pi runtime so the same `.attestation` file locks the plan across both Claude Code and Pi
  - Registered four slash commands (`/plan-status`, `/plan-attest`, `/plan-goal`, `/plan-loop`) mirroring their Claude Code counterparts
  - Added 12 contract tests covering packaging, declared capabilities, and documentation strings; iterated through PRs #155 and #156 to land code-only and version-clean in #157
  - PR #158: closed the Pi SKILL.md sync gap after v2.39.0 shipped. Backported Rule 7 (Continue After Completion), the Security Boundary section, the expanded Scripts section covering `set-active-plan.sh`/`resolve-plan-dir.sh`/`attest-plan.sh` and the parallel task workflow, and the "Write web content to task_plan.md" anti-pattern row. Renamed the npm package from the unscoped `pi-planning-with-files` to `@tomxprime/planning-with-files`, matching the package author's npm namespace. Rewrote the install docs to point at the scoped package and to use `pi install ./.pi/skills/planning-with-files` (local path) for manual installs. Removed the redundant manual session-catchup instruction since the Pi extension handles that lifecycle event automatically
  - **Impact:** Pi adapter now ships at parity with Claude Code in both runtime behavior (PR #157) and instruction surface (PR #158). DeepSeek+Pi users get a cache-safe reminder path that does not invalidate the KV-cache prefix on every turn, and the npm publishing chain is now under the scoped namespace of the package author

- **[@DLI1996](https://github.com/DLI1996)** - [Issue #154](https://github.com/OthmanAdi/planning-with-files/issues/154)
  - Caught that `docs/codex.md` instructed users to set `codex_hooks = true` in `~/.codex/config.toml`, while OpenAI's current Codex hooks docs (developers.openai.com/codex/hooks) now make `hooks` the canonical key and `codex_hooks` a deprecated alias
  - Linked the upstream OpenAI page so the canonical key change was easy to verify
  - **Impact:** v2.39.0 swaps the docs to `hooks = true` in four sites with an alias note, so new users get the canonical key while users on older configs are not pushed to migrate

- **[@Stephen-abc](https://github.com/Stephen-abc)** (Wang Jun) - [PR #187](https://github.com/OthmanAdi/planning-with-files/pull/187)
  - Fixed `UnicodeDecodeError` across 15 test files by adding explicit `encoding="utf-8"` to `subprocess.run`/`Popen` calls, which fail on Windows accounts whose default codepage isn't UTF-8
  - Corrected `docs/adal.md`, `docs/antigravity.md`, `docs/kilocode.md`, and `docs/openclaw.md`, which referenced IDE-specific source folders (`.adal/`, `.agent/`, `.kilocode/`) removed in v2.24.0, and fixed a `references/` versus `templates/` mislabel in antigravity.md
  - **Impact:** v3.2.0 test suite is now robust on non-UTF-8-default Windows accounts, and four installation guides point at paths that actually exist

- **[@igorcosta](https://github.com/igorcosta)** (Igor Costa, Autohand) - [PR #192](https://github.com/OthmanAdi/planning-with-files/pull/192)
  - Added `docs/autohand.md`, a setup guide for Autohand Code covering user-level and project-level Agent Skills installs
  - Added Autohand Code to the README's supported-IDEs table
  - **Impact:** planning-with-files now documents a supported install path for Autohand Code alongside the other 17+ platforms

- **[@Yigtwxx](https://github.com/Yigtwxx)** (Yiğit Erdoğan) - [PR #198](https://github.com/OthmanAdi/planning-with-files/pull/198), [PR #199](https://github.com/OthmanAdi/planning-with-files/pull/199), [Issue #197](https://github.com/OthmanAdi/planning-with-files/issues/197)
  - Filed #197 after running the suite on GitHub-hosted runners from a fork: the repo had a 200+ test pytest suite and a 21-test Pi vitest suite that CONTRIBUTING.md asks contributors to run, but no workflow ran either; the only CI was the Tessl skill-prose review
  - PR #199 added `.github/workflows/tests.yml`: pytest on `ubuntu-latest` and `windows-latest` (Python 3.12) plus the Pi extension vitest suite (Node 22), on every pull request and push to master, with `contents: read` permissions, `fail-fast: false`, and an explicit `sh`-on-PATH assertion so hook tests cannot silently skip
  - PR #198 fixed the two latent test-portability failures the first hosted run exposed, test-side only: a `host_realpath()` helper that maps the resolver's Git Bash POSIX path back with `cygpath` before the containment comparison, and `skipUnless(os.name == "nt")` on two Windows-shaped path vectors that fail on POSIX where `Path.resolve()` treats `C:/...` as relative
  - **Impact:** every PR now runs the real test suite on both Linux and Windows, catching the recurring Windows regression class (the v3.2.0 audit found `session-catchup.py` silently broken on Windows) at PR time instead of at release audit time

## Community Forks

These developers have created forks that extend the functionality:

- **[@RioTheGreat-ai](https://github.com/RioTheGreat-ai)** - [agentfund-skill](https://github.com/RioTheGreat-ai/agentfund-skill)
  - Crowdfunding platform for AI agents using milestone-based escrow on Base, built with planning-with-files

- **[@kmichels](https://github.com/kmichels)** - [multi-manus-planning](https://github.com/kmichels/multi-manus-planning)
  - Multi-project support
  - SessionStart git sync integration

## Issue Reporters & Testers

Thank you to everyone who reported issues, provided feedback, and helped test fixes:

- [@nazeshinjite](https://github.com/nazeshinjite) - Issue #133 (Stop hook portability failure on Windows Git Bash — two-root-cause diagnosis with full Claude output, fixed in v2.34.1)
- [@msuadOf](https://github.com/msuadOf) - Issue #93 (TMPDIR environment fix for plugin install)
- [@DorianZheng](https://github.com/DorianZheng) - Issue #84 (BoxLite sandbox integration proposal)
- [@mtuwei](https://github.com/mtuwei) - Issue #32 (Windows hook error)
- [@JianweiWangs](https://github.com/JianweiWangs) - Issue #31 (Skill activation)
- [@tingles2233](https://github.com/tingles2233) - Issue #29 (Plugin update issues)
- [@st01cs](https://github.com/st01cs) - Issue #28 (Devis fork discussion)
- [@wqh17101](https://github.com/wqh17101) - Issue #11 testing and confirmation
- [@luyanfeng](https://github.com/luyanfeng) - Issue #172 (OpenCode install/verify paths doubled the folder segment in docs/opencode.md; fixed in v2.43.0) and Issue #235 (docs/opencode.md claimed `npx skills add -g` installs to `~/.config/opencode/skills/` while it installs to `~/.agents/skills/`; the report triggered the v3.14.0 OpenCode rewrite with the native plugin)
- [@mixian939](https://github.com/mixian939) - Issue #191 (Codex hooks reporting a false "0/0 phases complete" status for an unstructured task_plan.md, with a full root-cause diagnosis and suggested fix; the audit this triggered found and fixed the same defect in the canonical scripts and two other IDE adapters, fixed in v3.2.0)
- [@AvitalAviv](https://github.com/AvitalAviv) - Issue #188 (flagged that the repo had no private vulnerability disclosure channel; private vulnerability reporting is now enabled and documented in SECURITY.md)
- [@lazyst](https://github.com/lazyst) - Issue #190 (feature request describing the Pi extension activating hooks on a draft plan before user confirmation, with the exact passive-until-confirmed behavior that shipped as `/plan-execute` in v3.3.0)
- [@dubes394](https://github.com/dubes394) (Kunal Dubey) - Issue #217 (two agents sharing one plan directory can both write `task_plan.md` from the same read, and the later write silently discards the earlier one's work; the report's simpler option, a reread nudge rather than a lock, is what shipped as the parallel-write guard in v3.10.0)
- [@popey](https://github.com/popey) (Alan Pope) - [PR #215](https://github.com/OthmanAdi/planning-with-files/pull/215) (bumped the pinned Tessl action SHA past a migration that had silently stopped reviews from running; the range it moves across also closes a marker-spoofing hole in the commit this repo had been pinned to)
- [@SomSamantray](https://github.com/SomSamantray) (Som Samantray) - [PR #216](https://github.com/OthmanAdi/planning-with-files/pull/216) (audited the language variants against the canonical skill and proved the drift issue #130 predicted: 12 missing scripts, a missing Windows UTF-8 fix, and sync tooling that covered only 3 dispatch targets; that analysis is what v3.10.0 acted on, closing the gap additively instead of by deletion)
- [@marcmuon](https://github.com/marcmuon) (Marc Kelechava) - Issue #195 (one-shot `codex exec` sessions sharing a cwd with an incomplete plan got hijacked and mutated orchestrator-owned plan files; the report's reproductions, root-cause file list, and acceptance criteria shipped directly as the `PLANNING_DISABLED=1` opt-out in v3.4.0)
- [@mfehlhaber](https://github.com/mfehlhaber): Issue #220 (identified that the Codex POSIX `SessionStart` and `UserPromptSubmit` routes bypassed the JSON adapter, causing planning context beginning with `[` to be rejected as invalid event JSON; fixed in v3.10.1), Issue #231 (traced Pi's generic attestation failure to six CRLF shell scripts in the npm `3.10.2` tarball, separated the clean repository source from the broken package artifact, and identified the missing package-time validation boundary)

- [@Whxuan0701](https://github.com/Whxuan0701) (WeiHaoxuan) - [PR #223](https://github.com/OthmanAdi/planning-with-files/pull/223), [PR #222](https://github.com/OthmanAdi/planning-with-files/pull/222), [PR #224](https://github.com/OthmanAdi/planning-with-files/pull/224) (found that the `PLANNING_DISABLED=1` opt-out from #195 had never reached any of the ten GitHub Copilot hook entry points, that the #191 zero-phase guard was missing from the Copilot PowerShell stop hook, and that the Hermes determinism probe hardcoded `python` so it could not run where only `python3` exists; three single-commit PRs, each with a test that executes the real script. Auditing them surfaced three further defects fixed in the same release: the Cursor route had the same opt-out gap across all eight of its hooks, the disabled `PreToolUse` branch was widening Copilot's permissions rather than staying neutral, and `error-occurred.ps1` had never logged an error on Windows because it read stdin into PowerShell's automatic `$input` variable)

- [@dylanpulver](https://github.com/dylanpulver) (Dylan Pulver) - [PR #226](https://github.com/OthmanAdi/planning-with-files/pull/226) (answered issue #130 after two earlier attempts could not be taken: moved the five language variants one directory deeper so the Claude Code plugin scan, which reads `skills/*/SKILL.md` without recursing, stops registering them, while every `npx skills add --skill` command keeps resolving because that resolver matches by skill name across a recursive scan. Cut the plugin's always-on cost by roughly half without deleting, renaming or breaking a single install. Verified the install route rather than assuming it, carried the literal English status-token warning into all five language commands where an earlier attempt had not, and named the one cost he could not remove), [PR #228](https://github.com/OthmanAdi/planning-with-files/pull/228) (fixed the Copilot error hook, which fed its Python helpers with bash here-strings that dash cannot parse, so master CI had failed on the ubuntu leg for five consecutive runs. Reproduced the ubuntu condition locally instead of working from the log, and confirmed the suite genuinely exercises the path by reverting his own change. Declined the fix that would have looked right: copying the four sibling hooks' `echo` form clears the syntax error but silently corrupts JSON under dash, and he wrote that into the pull request rather than leaving it for review), [PR #229](https://github.com/OthmanAdi/planning-with-files/pull/229) (found the two manual install commands still copying `skills/*` after the translations moved under `skills/i18n/`, corrected both to name the canonical skill, and added a tracked-Markdown guard against the old install shape)
- [@sean3808](https://github.com/sean3808) (Sean) - [Issue #130](https://github.com/OthmanAdi/planning-with-files/issues/130) (opened the consolidation report in April 2026 with the analysis that framed the problem for every later attempt: identical scripts and templates, prose the only real difference, and five skill descriptions injected into every session that most users would never invoke; resolved in v3.11.0)

And many others who have starred, forked, and shared this project!

- **[@voidborne-d](https://github.com/voidborne-d)** - [PR #149](https://github.com/OthmanAdi/planning-with-files/pull/149)
  - Caught that `skills/planning-with-files/scripts/init-session.sh` was not updated when slug mode shipped in v2.36.0, meaning users installing via npx or IDE folders silently received the old script
  - Identified the same gap in the analytics template (v2.29.0) and the shebang drift from v2.35.1 across IDE mirror folders
  - Synced the canonical skill copy and all IDE mirrors using the existing `sync-ide-folders.py` tool, and added a byte-comparison regression test plus a `--verify` CI assertion to prevent recurrence
  - **Impact:** v2.36.0 headline feature (parallel plan isolation) now actually reaches users who install via the skill; regression test closes the drift class permanently

## How to Contribute

We welcome contributions! Here's how you can help:

1. **Report Issues** - Found a bug? Open an issue with details
2. **Suggest Features** - Have an idea? Share it in discussions
3. **Submit PRs** - Code improvements, documentation, examples
4. **Share** - Tell others about planning-with-files
5. **Create Forks** - Build on this work (with attribution)

See our [repository](https://github.com/OthmanAdi/planning-with-files) for more details.

## Recognition

If you've contributed and don't see your name here, please open an issue! We want to recognize everyone who helps make this project better.

---

**Total Contributors:** 62+ and growing!

*Last updated: 2026-09-17*
