<div align="center">
<img src="media/v3-banner.png" alt="planning-with-files" width="100%">
</div>

# Planning with Files

> 📣 **New in [v3.0.0](https://github.com/OthmanAdi/planning-with-files/releases/tag/v3.0.0):** opt-in autonomous and gated modes for long-running agent runs, with a completion gate that holds the agent until the plan is actually done. Existing setups change nothing.

> **Work like Manus** — the AI agent company Meta acquired for **$2 billion**.
>
> **planning-with-files** is a persistent file-based planning skill for **AI coding agents**. It keeps `task_plan.md`, `findings.md`, and `progress.md` on disk so the agent survives **context loss**, `/clear`, and crashes, with an opt-in completion gate that holds the agent until the plan is actually done. It installs across 60+ agents via the SKILL.md standard.

[![Benchmark](https://img.shields.io/badge/Benchmark-96.7%25_pass_rate_(v2.21.0%2C_sonnet--4--6)-brightgreen)](docs/evals.md)
[![A/B Verified](https://img.shields.io/badge/A%2FB_Blind-3%2F3_wins-brightgreen)](docs/evals.md)
[![SkillCheck Validated](https://img.shields.io/badge/SkillCheck-Validated-4c1)](https://getskillcheck.com)
[![Security Verified](https://img.shields.io/badge/Security-Audited_%26_Fixed_v2.21.0-blue)](docs/evals.md)

[![Skills Playground](https://skillsplayground.com/badges/installs/othmanadi-planning-with-files-planning-with-files.svg)](https://skillsplayground.com/skills/othmanadi-planning-with-files-planning-with-files/)
[![Downloads](https://skill-history.com/badge/othmanadi/planning-with-files.svg)](https://skill-history.com/othmanadi/planning-with-files)
[![Version](https://img.shields.io/badge/version-3.1.3-brightgreen)](https://github.com/OthmanAdi/planning-with-files/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Closed Issues](https://img.shields.io/github/issues-closed/OthmanAdi/planning-with-files?color=success)](https://github.com/OthmanAdi/planning-with-files/issues?q=is%3Aissue+is%3Aclosed)
[![Closed PRs](https://img.shields.io/github/issues-pr-closed/OthmanAdi/planning-with-files?color=success)](https://github.com/OthmanAdi/planning-with-files/pulls?q=is%3Apr+is%3Aclosed)

<details>
<summary><strong>💬 A Note from the Author</strong></summary>

To everyone who starred, forked, and shared this skill — thank you. This project blew up in less than 24 hours, and the support from the community has been incredible.

If this skill helps you work smarter, that's all I wanted.

</details>

<details>
<summary><strong>🌍 What the community shipped</strong></summary>

### Forks & Extensions

| Fork | Author | What They Built |
|------|--------|-----------------|
| [devis](https://github.com/st01cs/devis) | [@st01cs](https://github.com/st01cs) | Interview-first workflow, `/devis:intv` and `/devis:impl` commands, guaranteed activation |
| [multi-manus-planning](https://github.com/kmichels/multi-manus-planning) | [@kmichels](https://github.com/kmichels) | Multi-project support, SessionStart git sync |
| [plan-cascade](https://github.com/Taoidle/plan-cascade) | [@Taoidle](https://github.com/Taoidle) | Multi-level task orchestration, parallel execution, multi-agent collaboration |
| [agentfund-skill](https://github.com/RioTheGreat-ai/agentfund-skill) | [@RioTheGreat-ai](https://github.com/RioTheGreat-ai) | Crowdfunding for AI agents with milestone-based escrow on Base |
| [openclaw-github-repo-commander](https://github.com/wd041216-bit/openclaw-github-repo-commander) | [@wd041216-bit](https://github.com/wd041216-bit) | 7-stage GitHub repo audit, optimization, and cleanup workflow for OpenClaw |

### Used in the Wild

| Project | What It Is |
|---------|-----------|
| [lincolnwan/Planning-with-files-copilot-agent](https://github.com/lincolnwan/Planning-with-files-copilot-agent) | Entire Copilot agent repo built around the planning-with-files skill |
| [cooragent/ClarityFinance](https://github.com/cooragent/ClarityFinance) | AI finance agent framework — Planning-with-Files approach directly credited |
| [oeftimie/vv-claude-harness](https://github.com/oeftimie/vv-claude-harness) | Claude Code harness built on Manus-style persistent markdown planning |
| [jessepwj/CCteam-creator](https://github.com/jessepwj/CCteam-creator) | Multi-agent team orchestration skill using file-based planning |

### Skill Registries & Hubs

| Registry | What It Is |
|----------|-----------|
| [buzhangsan/skill-manager](https://github.com/buzhangsan/skill-manager) | Bilingual (EN/中文) skill hub indexing 31,000+ Claude Code skills — planning-with-files installable one-click. |

*Built something? [Open an issue](https://github.com/OthmanAdi/planning-with-files/issues) to get listed!*

</details>

<details>
<summary><strong>🤝 Contributors</strong></summary>

See the full list of everyone who made this project better in [CONTRIBUTORS.md](./CONTRIBUTORS.md).

</details>

<details>
<summary><strong>📦 Releases & Session Recovery</strong></summary>

### Current Version: v3.1.3

| Version | Highlights |
|---------|------------|
| **v3.1.3** | **Hotfix: SKILL.md frontmatter was invalid YAML in v3.1.2.** The v3.1.2 description refresh added a colon, and the English SKILL.md keep `description` unquoted, so YAML rejected the frontmatter ("mapping values are not allowed here"), which could break skill loading and the model-triggering description. v3.1.3 quotes the description (matching the already-quoted translated variants; the parsed value is identical) across the canonical file and the seven English IDE variants, and adds `tests/test_skill_frontmatter_valid.py` to validate every SKILL.md frontmatter as YAML. Suite at 184 passed. |
| **v3.1.2** | **Session-catchup command works outside the plugin runtime, `.hermes` parity, refreshed skill description** (PR #186 by @shunfeng8421 closes #185, reported by @xwang118). The documented Restore Context command used `${CLAUDE_PLUGIN_ROOT}`, which the plugin runtime sets only inside hook execution, so a skill-only install (`npx skills add`, Codex, Cursor) running it in a shell got an empty variable and a broken `/scripts/...` path. Now `SKILL_DIR="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/skills/planning-with-files}"` on the canonical file, `.codebuddy`, and the five language variants; the `.hermes` variant got the same fallback for `$HERMES_HOME`. The eight English SKILL.md descriptions were refreshed to lead with planning for AI coding agents and context-loss survival, with the `Use when` trigger and translated variants unchanged. Documentation only; suite at 180 passed. |
| **v3.1.1** | **Codex verification command checks the canonical `hooks` feature flag** (PR #184 by @Fat-Jan). The `docs/codex.md` verify block ran `codex features list \| rg '^codex_hooks\s'`, but Codex moved its canonical feature key from `codex_hooks` to `hooks` in 0.129.0 (openai/codex#20522). The alias still resolves in config, yet `codex features list` prints only `hooks`, so the old pattern matched nothing on current Codex and routed correctly configured users to the upgrade path. The command now greps `^(hooks\|codex_hooks)\s` and the troubleshooting sentence covers both names, matching the `hooks = true` guidance carried in the file since v2.39.0. Documentation only; suite at 180 passed. |
| **v3.1.0** | **Codex Stop hook no longer blocks on an incomplete plan, native Codex PreCompact parity, Pi extension test suite, and accurate SHA-cache docs** (PR #180 by @2023Anita closes #178, PR #181 by @GongYuanCaiJi, PR #175 and PR #174 by @mvanhorn close #163 and #164). The `.codex` Stop adapter dropped the `{"decision":"block"}` path that pushed Codex agents to auto-continue unfinished phases; it now emits an advisory progress-sync reminder only, matching the v3 principle that an incomplete plan alone never blocks a stop. The native `.codex/hooks.json` route gained the PreCompact hook (`pre-compact.sh`) it was missing relative to the canonical SKILL.md, dormant on runtimes that never fire the event. The Pi extension gained a TypeScript integration suite covering all eight lifecycle handlers, the four runtime modes, and the attestation gate. `docs/perf-notes.md` documents the attestation SHA cache, corrected to the v3 `$XDG_CACHE_HOME/pwf-sha` location. Suite at 180 passed. |
| **v3.0.0** | **Autonomous and gated modes for long-running agentic runs, structured run ledger, opt-in completion gate** (no breaking changes: with no mode marker the hooks produce byte-identical v2.43 output). `init-session --autonomous` drops the per-tool-call plan re-injection for strong models and keeps the turn-start injection; `--gated` adds a deliberate Stop-hook completion gate that blocks only when five conditions hold (gated mode, an `in_progress` phase, `stop_hook_active` false, block count under the cap, ledger progressed since the last block), so an incomplete plan alone never traps a session. New append-only JSONL run ledger (`ledger-append`, `ledger-summary`, `phase-status`, sh + ps1) replaces the raw `progress.md` tail in v3 modes with a fixed-shape summary. Attestation is default-on in v3 modes and unattested plan bodies are refused at injection. Per-session nonce delimiters, SHA cache moved to `$XDG_CACHE_HOME/pwf-sha`, realpath containment in the plan-dir resolver. Hook scalars replaced by thin dispatchers (`inject-plan.sh`, `gate-stop.sh`) shipped in both `scripts/` locations. New `templates/task_plan_autonomous.md` with `DependsOn`/`Owner`/`AcceptanceCheck` fields, v2-to-v3 migration guide in `MIGRATION.md`, host capability tiers documented (hard block, follow-up inject, notify only). Suite at 178 passed plus location-parity and gate/ledger/init-mode/containment tests. |
| **v2.43.0** | **CONTRIBUTING.md + OpenCode docs fix + `.continue`/`.gemini`/`.kiro` variant sync to parity** (PR #171 by @Skulli485, issue #172 by @luyanfeng, issues #159/#160/#161): first `CONTRIBUTING.md` at repo root, auto-surfaced by GitHub in the PR creation flow. `docs/opencode.md` Quick Install switched from \`git clone\` to \`npx skills add\` after the manual-install block was found referencing a doubled path (`planning-with-files/planning-with-files/SKILL.md`). Three historically lagging IDE SKILL.md variants brought to v2.43.0 parity: `.continue` from v2.34.0 (9 versions behind), `.gemini` from v2.34.0 (9 versions behind), `.kiro` from v2.32.0-kiro (11 versions behind), preserving IDE-specific frontmatter, hook shapes, and Kiro Agent Skill layout. |
| **v2.42.0** | **POSIX `init-session.sh` portability + plugin-vs-skill install transparency + Topic Handoff docs** (PR #169 and PR #170 by @carterusedulm2-maker): `init-session.sh` and its 7 mirrors swap the `[[ ]]` bashism for POSIX `[ ]` so `tests/test_init_session_slug.py` runs cleanly under `dash` (Ubuntu) when the test invokes the script via `sh` rather than the `bash` shebang. Canonical SKILL.md gains an install-scope clarification: `/plugin install` ships the `commands/` folder with `/plan-goal` and `/plan-loop`, but `npx skills add` (and ClawHub) do not. A manual fallback procedure for both wrappers is documented inline so skill-only sessions can produce the same effect by invoking Claude Code's native `/goal` and `/loop` primitives directly. `docs/quickstart.md` and `docs/workflow.md` add an optional Topic Handoff Pattern for very long-running operational topics (`handoffs/<topic>.md` alongside `progress.md`). |
| **v2.41.0** | **Windows exec-bit test skip + attestation-locking docs** (PR #167 by @gauravvojha, Issue #166; PR #168 by @CleanDev-Fix, Issue #165): `test_script_permissions.py` now skips on Windows with a class-level `pytest.mark.skipif(sys.platform == "win32")` since NTFS does not store POSIX executable bits; the 2 pre-existing Windows exec-bit failures (present since v2.34.1) are resolved. New dedicated `docs/attestation-locking.md` page documents the `attest-plan.sh` write path, the atomic temp-rename guarantee, the optional `flock` advisory lock, and the recommended slug-mode workflow for parallel sessions. |
| **v2.40.1** | **Pi adapter SKILL.md sync gap + npm scope correction** (PR #158 by @TomXPRIME): the `.pi` SKILL.md lagged the canonical Claude Code copy after v2.39.0; v2.40.1 backports Rule 7 (Continue After Completion), the Security Boundary section, the expanded Scripts section covering `set-active-plan.sh`/`resolve-plan-dir.sh`/`attest-plan.sh` plus the parallel task workflow, and the "Write web content to task_plan.md" anti-pattern row. The Pi npm package is renamed from the unscoped `pi-planning-with-files` to `@tomxprime/planning-with-files`, matching the package author's namespace; install docs updated accordingly. Author, repository, license, and bugs URLs preserved. |
| **v2.40.0** | **Slug-mode resolution fixes + perf cache + KV-cache hygiene + Pi false-positive fix** (9 items from the v2.40 R&D experiment): hook resolution order inverted so slug-mode wins over legacy root, `.active_plan` target dir + content validated against a safe-identifier regex, `check-complete.sh` honors `$PLAN_ID` and `.active_plan`, Pi extension `isDangerousBashCommand` swapped to a word-boundary regex array so benign `git push origin <branch>` no longer fires the warning, mtime-keyed SHA-256 cache cuts attestation-hook latency on Windows Git Bash, `progress.md` tail timestamps normalized for KV-cache prefix stability, `resolve-plan-dir.sh` mtime resolution made portable across GNU/BSD/macOS/Alpine/Git Bash with python+perl fallbacks, `attest-plan.sh` uses atomic temp-rename with optional `flock` to close the concurrent-writer race. 130 pass / 2 pre-existing Windows exec-bit fails, +20 new tests. |
| **v2.39.0** | **Pi Coding Agent full hook parity extension + Codex hooks flag fix** (PR #157 by @TomXPRIME, Issue #154 by @DLI1996): the `.pi` adapter ships a bundled TypeScript extension mapping eight Pi lifecycle events to the same behavior the skill provides on Claude Code, with a four-mode system (`auto`/`parity`/`cache-safe`/`notify`) that auto-detects DeepSeek and keeps the KV-cache prefix stable. Pi runtime reads the same `.attestation` file the canonical v2.37 `attest-plan.sh` writes, so attesting once locks the plan across both runtimes. Four slash commands (`/plan-status`, `/plan-attest`, `/plan-goal`, `/plan-loop`) mirror their Claude Code counterparts. Separately, `docs/codex.md` swaps from `codex_hooks = true` to `hooks = true` to match the current OpenAI canonical key, with an alias note so users on older configs are not pushed to migrate. |
| **v2.38.1** | **Description field garbled in Claude Code skill picker** (surfaced via Discussion #153 by @bmyury): hook commands embedded `'---BEGIN PLAN DATA---'` plan-injection delimiters; Claude Code's skill-discovery loader split frontmatter on the first `---` and read the truncated value as the description. Swapped to `===BEGIN PLAN DATA===` / `===END PLAN DATA===` across canonical SKILL.md, all five language variants, the `.codebuddy/.codex/.cursor` adapter mirrors, and `clawhub-upload`. Hook execution and tamper attestation never affected; only the displayed metadata. |
| **v2.38.0** | **Claude Code turn-loop integration + OpenCode SQLite fix**: new PreCompact hook fires on `/compact` and autoCompact, surfaces a reminder to flush progress before compaction completes and prints the active Plan-SHA256 when attested. New `/plan-goal` slash command composes with Claude Code's `/goal` (v2.1.139, May 12 2026): derives a termination condition from the active plan. New `/plan-loop` composes with `/loop` (v2.1.72+): default 10-minute tick re-reads planning files and runs check-complete. New `templates/loop.md` for the bare `/loop` planning-aware default. Session-catchup rewritten for OpenCode's SQLite migration. Codex gets a `PermissionRequest` adapter that surfaces plan context at permission prompts. |
| **v2.37.0** | **Hash attestation + parity bumper** (closes #150, #151): `/plan-attest` locks `task_plan.md` with a SHA-256; hooks block injection on tamper. `scripts/bump-version.py` + parity test kill the "missed one variant" regression class behind v2.34.1, v2.36.0, v2.36.2, and v2.36.3. (thanks @oaabahussain!) |
| **v2.36.3** | **Parallel planning scripts now ship in the skill**: `resolve-plan-dir.sh` and `set-active-plan.sh` were missing from the installed skill in v2.36.0; now in canonical + all IDE mirrors + SKILL.md docs updated |
| **v2.36.2** | **Canonical script sync** (PR #149): `skills/planning-with-files/scripts/init-session.sh` was missing slug mode from v2.36.0; now synced with IDE mirrors + regression test. (thanks @voidborne-d!) |
| **v2.36.1** | **Security hardening**: Stop hook cache search removed, ExecutionPolicy Bypass changed to RemoteSigned, prompt injection delimiters added. (Gen Agent Trust Hub FAIL resolved) |
| **v2.36.0** | **Parallel plan isolation + Codex session isolation** (closes #146, #148): `init-session.sh` slug mode, `set-active-plan.sh`, `resolve-plan-dir.sh`, all Codex hooks route through resolver, session attachment gating. **Hermes docs** (closes #147): integration notes added to `docs/hermes.md`. 34 new tests. (thanks @githubYiheng, @09ashishkapoor, @shawnli1874!) |
| **v2.35.1** | **Shebang portability fix**: changed `/bin/bash` to `/usr/bin/env bash` in hook scripts, fixing compatibility on NixOS and other systems where bash is not at `/bin/bash`. (thanks @Emin017!) |
| **v2.35.0** | **Hermes adapter + NLPM audit hardening**: Hermes platform 17 support (thanks @bailob!), NLPM audit fixed Python PATH resolution, session-catchup injection cap, Pi PowerShell syntax (thanks @xiaolai!) |
| **v2.34.1** | **Stop hook Windows portability fix** (closes #133): `export SD=` failed in Windows Git Bash hook context; fallback path was wrong for plugin cache structure. Fixed across all 13 SKILL.md variants. (thanks @nazeshinjite!) |
| **v2.34.0** | **Codex hooks fully restored** (closes #132): `.codex/hooks.json` + lifecycle scripts back — SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop. Tessl CI for SKILL.md quality reviews. Exec bit fix. 4 missing contributors added. (thanks @Leon-Algo, @popey!) |
| **v2.33.0** | **Multi-language expansion**: Arabic, German, and Spanish skill variants added (thanks to community contributors!) |
| **v2.32.0** | Codex session catchup rewrite (thanks @ebrevdo!), Loaditout A-grade security badge, Stop hook Git Bash fix |
| **v2.31.0** | Codex hooks.json integration with full lifecycle hooks (thanks @Leon-Algo!) |
| **v2.30.1** | Fix: Codex script executable bits restored (thanks @Leon-Algo!) |
| **v2.30.0** | `CLAUDE_SKILL_DIR` variable, IDE configs moved to per-IDE branches, plugin.json bumped from 2.23.0 |
| **v2.29.0** | Analytics workflow template: `--template analytics` flag for data exploration sessions (thanks @mvanhorn!) |
| **v2.28.0** | Traditional Chinese (zh-TW) skill variant (thanks @waynelee2048!) |
| **v2.26.2** | Fix: `---` in hook commands broke YAML frontmatter parsing, hooks now register correctly |
| **v2.26.1** | Fix: session catchup after `/clear`, path sanitization on Windows + content injection (thanks @tony-stark-eth!) |
| **v2.26.0** | IDE audit: Factory hooks, Copilot errorOccurred hook, Gemini hooks, bug fixes |
| **v2.18.2** | Mastra Code hooks fix (hooks.json + docs accuracy) |
| **v2.18.1** | Copilot garbled characters complete fix |
| **v2.18.0** | BoxLite sandbox runtime integration |
| **v2.17.0** | Mastra Code support + all IDE SKILL.md spec fixes |
| **v2.16.1** | Copilot garbled characters fix: PS1 UTF-8 encoding + bash ensure_ascii (thanks @Hexiaopi!) |
| **v2.16.0** | GitHub Copilot hooks support (thanks @lincolnwan!) |
| **v2.27.0** | Kiro Agent Skill layout (thanks @EListenX!) |
| **v2.15.1** | Session catchup false-positive fix (thanks @gydx6!) |
| **v2.15.0** | `/plan:status` command, OpenCode compatibility fix |
| **v2.14.0** | Pi Agent support, OpenClaw docs update, Codex path fix |
| **v2.11.0** | `/plan` command for easier autocomplete |
| **v2.10.0** | Kiro steering files support |
| **v2.7.0** | Gemini CLI support |
| **v2.2.0** | Session recovery, Windows PowerShell, OS-aware hooks |

[View all releases](https://github.com/OthmanAdi/planning-with-files/releases) · [CHANGELOG](CHANGELOG.md)

> Parallel plan isolation (`.planning/YYYY-MM-DD-slug/` directories) and Codex session isolation shipped in v2.36.0. The `experimental/isolated-planning` branch was the earlier prototype; master is now the canonical location.

---

### Session Recovery

When your context fills up and you run `/clear`, this skill **automatically recovers** your previous session.

**How it works:**
1. Checks for previous session data in the active IDE's session store (`~/.claude/projects/` for Claude Code, `~/.codex/sessions/` for Codex)
2. Finds when planning files were last updated
3. Extracts conversation that happened after (potentially lost context)
4. Shows a catchup report so you can sync

**Pro tip:** Disable auto-compact to maximize context before clearing:
```json
{ "autoCompact": false }
```

</details>

<details>
<summary><strong>🛠️ Supported IDEs (18+ Platforms)</strong></summary>

#### Enhanced Support (hooks + lifecycle automation)

These IDEs have dedicated hook configurations that automatically re-read your plan before tool use, remind you to update progress, and verify completion before stopping:

| IDE | Installation Guide | Integration |
|-----|-------------------|-------------|
| Claude Code | [Installation](docs/installation.md) | Plugin + SKILL.md + Hooks |
| Cursor | [Cursor Setup](docs/cursor.md) | Skills + [hooks.json](https://cursor.com/docs/hooks) |
| GitHub Copilot | [Copilot Setup](docs/copilot.md) | [Hooks](https://docs.github.com/en/copilot/reference/hooks-configuration) (incl. errorOccurred) |
| Mastra Code | [Mastra Setup](docs/mastra.md) | Skills + [Hooks](https://mastra.ai/docs/mastra-code/configuration) |
| Gemini CLI | [Gemini Setup](docs/gemini.md) | Skills + [Hooks](https://geminicli.com/docs/hooks/) |
| Kiro | [Kiro Setup](docs/kiro.md) | [Agent Skills](https://kiro.dev/docs/skills/) |
| Codex | [Codex Setup](docs/codex.md) | [Skills + Hooks](https://developers.openai.com/codex/skills) |
| Hermes Agent | [Hermes Setup](docs/hermes.md) | Skill + Project Plugin |
| CodeBuddy | [CodeBuddy Setup](docs/codebuddy.md) | [Skills + Hooks](https://www.codebuddy.ai/docs/cli/skills) |
| FactoryAI Droid | [Factory Setup](docs/factory.md) | [Skills + Hooks](https://docs.factory.ai/cli/configuration/skills) |
| OpenCode | [OpenCode Setup](docs/opencode.md) | Skills + Custom session storage |

#### Standard Agent Skills Support

These IDEs implement the [Agent Skills](https://agentskills.io) open specification. Install with `npx skills add` — the installer places the skill in each IDE's discovery path automatically:

| IDE | Installation Guide | Skill Discovery Path |
|-----|-------------------|---------------------|
| Continue | [Continue Setup](docs/continue.md) | `.continue/skills/` + [.prompt files](https://docs.continue.dev/customize/deep-dives/prompts) |
| Pi Agent | [Pi Agent Setup](docs/pi-agent.md) | `.pi/skills/` ([npm package](https://www.npmjs.com/package/@mariozechner/pi-coding-agent)) |
| OpenClaw | [OpenClaw Setup](docs/openclaw.md) | `.openclaw/skills/` ([docs](https://docs.openclaw.ai/tools/skills)) |
| Autohand Code | [Autohand Code Setup](docs/autohand.md) | `~/.autohand/skills/` or `.autohand/skills/` |
| Antigravity | [Antigravity Setup](docs/antigravity.md) | `.agent/skills/` ([docs](https://codelabs.developers.google.com/getting-started-with-antigravity-skills)) |
| Kilocode | [Kilocode Setup](docs/kilocode.md) | `.kilocode/skills/` ([docs](https://kilo.ai/docs/agent-behavior/skills)) |
| AdaL CLI (Sylph AI) | [AdaL Setup](docs/adal.md) | `.adal/skills/` ([docs](https://docs.sylph.ai/features/plugins-and-skills)) |

> **Note:** If your IDE uses the legacy Rules system instead of Skills, see the [`legacy-rules-support`](https://github.com/OthmanAdi/planning-with-files/tree/legacy-rules-support) branch.

</details>

<details>
<summary><strong>🧱 Sandbox Runtimes (1 Platform)</strong></summary>

| Runtime | Status | Guide | Notes |
|---------|--------|-------|-------|
| BoxLite | ✅ Documented | [BoxLite Setup](docs/boxlite.md) | Run Claude Code + planning-with-files inside hardware-isolated micro-VMs |

> **Note:** BoxLite is a sandbox runtime, not an IDE. Skills load via [ClaudeBox](https://github.com/boxlite-ai/claudebox) — BoxLite’s official Claude Code integration layer.

</details>

---

A Claude Code plugin that transforms your workflow to use persistent markdown files for planning, progress tracking, and knowledge storage — the exact pattern that made Manus worth billions.

[![Claude Code Plugin](https://img.shields.io/badge/Claude%20Code-Plugin-blue)](https://code.claude.com/docs/en/plugins)
[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-green)](https://code.claude.com/docs/en/skills)
[![Cursor Skills](https://img.shields.io/badge/Cursor-Skills-purple)](https://docs.cursor.com/context/skills)
[![Kilocode Skills](https://img.shields.io/badge/Kilocode-Skills-orange)](https://kilo.ai/docs/agent-behavior/skills)
[![Gemini CLI](https://img.shields.io/badge/Gemini%20CLI-Skills-4285F4)](https://geminicli.com/docs/cli/skills/)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-Skills-FF6B6B)](https://openclaw.ai)
[![Kiro](https://img.shields.io/badge/Kiro-Agent_Skill-00D4AA)](https://kiro.dev/docs/skills/)
[![AdaL CLI](https://img.shields.io/badge/AdaL%20CLI-Skills-9B59B6)](https://docs.sylph.ai/features/plugins-and-skills)
[![Pi Agent](https://img.shields.io/badge/Pi%20Agent-Skills-FF4081)](https://pi.dev)
[![GitHub Copilot](https://img.shields.io/badge/GitHub%20Copilot-Hooks-000000)](https://docs.github.com/en/copilot/reference/hooks-configuration)
[![Mastra Code](https://img.shields.io/badge/Mastra%20Code-Skills-00BCD4)](https://code.mastra.ai)
[![Hermes](https://img.shields.io/badge/Hermes-Agent_Skill-5C7CFA)](docs/hermes.md)
[![BoxLite](https://img.shields.io/badge/BoxLite-Sandbox-6C3483)](https://boxlite.ai)

## Quick Install

```bash
npx skills add OthmanAdi/planning-with-files --skill planning-with-files -g
```

<details>
<summary><strong>🌐 Available in 5 other languages</strong></summary>

**🇸🇦 العربية / Arabic**
```bash
npx skills add OthmanAdi/planning-with-files --skill planning-with-files-ar -g
```

**🇩🇪 Deutsch / German**
```bash
npx skills add OthmanAdi/planning-with-files --skill planning-with-files-de -g
```

**🇪🇸 Español / Spanish**
```bash
npx skills add OthmanAdi/planning-with-files --skill planning-with-files-es -g
```

**🇨🇳 中文版 / Chinese (Simplified)**
```bash
npx skills add OthmanAdi/planning-with-files --skill planning-with-files-zh -g
```

**🇹🇼 正體中文版 / Chinese (Traditional)**
```bash
npx skills add OthmanAdi/planning-with-files --skill planning-with-files-zht -g
```

</details>

Works with Claude Code, Cursor, Codex, Gemini CLI, Autohand Code, and 40+ agents supporting the [Agent Skills](https://agentskills.io) spec.

<details>
<summary><strong>🔧 Claude Code Plugin (Advanced Features)</strong></summary>

For Claude Code-specific features like `/plan` autocomplete commands:

```
/plugin marketplace add OthmanAdi/planning-with-files
/plugin install planning-with-files@planning-with-files
```

</details>

That's it! Now use one of these commands in Claude Code:

| Command | Autocomplete | Description |
|---------|--------------|-------------|
| `/planning-with-files:plan` | Type `/plan` | Start planning session (v2.11.0+) |
| `/planning-with-files:status` | Type `/plan:status` | Show planning progress at a glance (v2.15.0+) |
| `/planning-with-files:start` | Type `/planning` | Original start command |

**Alternative:** If you want `/planning-with-files` (without prefix), copy skills to your local folder:

**macOS/Linux:**
```bash
cp -r ~/.claude/plugins/cache/planning-with-files/planning-with-files/*/skills/planning-with-files ~/.claude/skills/
```

**Windows (PowerShell):**
```powershell
Copy-Item -Recurse -Path "$env:USERPROFILE\.claude\plugins\cache\planning-with-files\planning-with-files\*\skills\planning-with-files" -Destination "$env:USERPROFILE\.claude\skills\"
```

See [docs/installation.md](docs/installation.md) for all installation methods.

## Why This Skill?

On December 29, 2025, [Meta acquired Manus for $2 billion](https://techcrunch.com/2025/12/29/meta-just-bought-manus-an-ai-startup-everyone-has-been-talking-about/). In just 8 months, Manus went from launch to $100M+ revenue. Their secret? **Context engineering**.

> "Markdown is my 'working memory' on disk. Since I process information iteratively and my active context has limits, Markdown files serve as scratch pads for notes, checkpoints for progress, building blocks for final deliverables."
> — Manus AI

## The Problem

Claude Code (and most AI agents) suffer from:

- **Volatile memory** — TodoWrite tool disappears on context reset
- **Goal drift** — After 50+ tool calls, original goals get forgotten
- **Hidden errors** — Failures aren't tracked, so the same mistakes repeat
- **Context stuffing** — Everything crammed into context instead of stored

## The Solution: 3-File Pattern

For every complex task, create THREE files:

```
task_plan.md      → Track phases and progress
findings.md       → Store research and findings
progress.md       → Session log and test results
```

### The Core Principle

```
Context Window = RAM (volatile, limited)
Filesystem = Disk (persistent, unlimited)

→ Anything important gets written to disk.
```

## The Manus Principles

| Principle | Implementation |
|-----------|----------------|
| Filesystem as memory | Store in files, not context |
| Attention manipulation | Re-read plan before decisions (hooks) |
| Error persistence | Log failures in plan file |
| Goal tracking | Checkboxes show progress |
| Completion verification | Stop hook checks all phases |

## Usage

Once installed, the AI agent will:

1. **Ask for your task** if no description is provided
2. **Create `task_plan.md`, `findings.md`, and `progress.md`** in your project directory
3. **Re-read plan** before major decisions (via PreToolUse hook in legacy mode; autonomous mode injects at session start and phase transitions instead, dropping the per-tool-call tax on strong models)
4. **Remind you** to update status after file writes (via PostToolUse hook)
5. **Store findings** in `findings.md` instead of stuffing context
6. **Log errors** for future reference
7. **Verify completion** before stopping (via Stop hook)

Invoke with:
- `/planning-with-files:plan` - Type `/plan` to find in autocomplete (v2.11.0+)
- `/planning-with-files:start` - Type `/planning` to find in autocomplete
- `/planning-with-files` - Only if you copied skills to `~/.claude/skills/`

See [docs/quickstart.md](docs/quickstart.md) for the full 5-step guide.

## Benchmark Results

> **Methodology note:** the 96.7% figure comes from the v2.21.0 evaluation run on `claude-sonnet-4-6` (2026-03-06). It measures file-pattern fidelity (does the agent create and maintain the 3-file structure), not goal-drift over long autonomous runs. Newer models and the autonomous-mode work are not yet covered by this number. Full methodology, dataset, and assertion list: [docs/evals.md](docs/evals.md).

Formally evaluated using Anthropic's [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) framework (v2.22.0), model `claude-sonnet-4-6`, 2026-03-06. 10 parallel subagents, 5 task types, 30 objectively verifiable assertions, 3 blind A/B comparisons.

| Test | with_skill | without_skill |
|------|-----------|---------------|
| Pass rate (30 assertions) | **96.7%** (29/30) | 6.7% (2/30) |
| 3-file pattern followed | 5/5 evals | 0/5 evals |
| Blind A/B wins | **3/3 (100%)** | 0/3 |
| Avg rubric score | **10.0/10** | 6.8/10 |

[Full methodology and results](docs/evals.md) · [Technical write-up](docs/article.md)

## Key Rules

1. **Create Plan First** — Never start without `task_plan.md`
2. **The 2-Action Rule** — Save findings after every 2 view/browser operations
3. **Log ALL Errors** — They help avoid repetition
4. **Never Repeat Failures** — Track attempts, mutate approach

## When to Use

**Use this pattern for:**
- Multi-step tasks (3+ steps)
- Research tasks
- Building/creating projects
- Tasks spanning many tool calls

**Skip for:**
- Simple questions
- Single-file edits
- Quick lookups

## File Structure

```
planning-with-files/
├── commands/                # Plugin commands
│   ├── plan.md              # /planning-with-files:plan command (v2.11.0+)
│   ├── plan-ar.md           # Arabic /plan command (v2.33.0+)
│   ├── plan-de.md           # German /plan command (v2.33.0+)
│   ├── plan-es.md           # Spanish /plan command (v2.33.0+)
│   └── start.md             # /planning-with-files:start command
├── templates/               # Root-level templates (for CLAUDE_PLUGIN_ROOT)
├── scripts/                 # Root-level scripts (for CLAUDE_PLUGIN_ROOT)
├── docs/                    # Documentation
│   ├── installation.md
│   ├── quickstart.md
│   ├── workflow.md
│   ├── troubleshooting.md
│   ├── gemini.md            # Gemini CLI setup
│   ├── cursor.md
│   ├── windows.md
│   ├── kilocode.md
│   ├── codex.md
│   ├── opencode.md
│   ├── mastra.md             # Mastra Code setup
│   └── boxlite.md            # BoxLite sandbox setup
├── examples/                # Integration examples
│   └── boxlite/             # BoxLite quickstart
│       ├── README.md
│       └── quickstart.py
├── planning-with-files/     # Plugin skill folder
│   ├── SKILL.md
│   ├── templates/
│   └── scripts/
├── skills/                  # Skill variants
│   ├── planning-with-files/     # English (default)
│   │   ├── SKILL.md
│   │   ├── examples.md
│   │   ├── reference.md
│   │   ├── templates/
│   │   └── scripts/
│   │       ├── init-session.sh
│   │       ├── check-complete.sh
│   │       ├── init-session.ps1   # Windows PowerShell
│   │       └── check-complete.ps1 # Windows PowerShell
│   ├── planning-with-files-ar/   # Arabic (v2.33.0+)
│   │   ├── SKILL.md
│   │   ├── templates/
│   │   └── scripts/
│   ├── planning-with-files-de/   # German (v2.33.0+)
│   │   ├── SKILL.md
│   │   ├── templates/
│   │   └── scripts/
│   ├── planning-with-files-es/   # Spanish (v2.33.0+)
│   │   ├── SKILL.md
│   │   ├── templates/
│   │   └── scripts/
│   ├── planning-with-files-zh/   # Chinese Simplified (v2.25.0+)
│   └── planning-with-files-zht/  # Chinese Traditional (v2.28.0+)
├── .gemini/                 # Gemini CLI skills + hooks
│   ├── settings.json        # Hook configuration (v2.26.0)
│   ├── hooks/               # Hook scripts (SessionStart, BeforeTool, AfterTool, BeforeModel, SessionEnd)
│   └── skills/
│       └── planning-with-files/
├── .codex/                  # Codex CLI skills + hooks
│   └── skills/
├── .opencode/               # OpenCode skills (custom session storage)
│   └── skills/
├── .claude-plugin/          # Plugin manifest
├── .cursor/                 # Cursor skills + hooks
│   ├── hooks.json           # Hook configuration
│   ├── hooks/               # Hook scripts (bash + PowerShell)
│   └── skills/
├── .codebuddy/              # CodeBuddy skills + hooks
│   └── skills/
├── .factory/                # FactoryAI Droid skills + hooks (v2.26.0)
│   └── skills/
├── .pi/                     # Pi Agent skills (npm package)
│   └── skills/
│       └── planning-with-files/
├── .continue/               # Continue.dev skills + prompt files
│   ├── prompts/             # .prompt file for slash commands
│   └── skills/
├── .github/                 # GitHub Copilot hooks (incl. errorOccurred)
│   └── hooks/
│       ├── planning-with-files.json  # Hook configuration
│       └── scripts/         # Hook scripts (bash + PowerShell)
├── .mastracode/             # Mastra Code skills + hooks
│   └── skills/
├── .kiro/                   # Kiro Agent Skills (v2.27.0+)
│   └── skills/
├── CHANGELOG.md
├── CITATION.cff
├── LICENSE
└── README.md
```

## FAQ

### How do I stop my coding agent from losing its plan after /clear or a crash?

The plan lives on disk in `task_plan.md`, `findings.md`, and `progress.md`, not only in the context window. At the start of each turn the `UserPromptSubmit` hook re-injects the active plan, and after a `/clear` or a new session the skill re-reads the files from disk (session recovery), so the agent recovers its goals and progress automatically.

### What is the difference between planning-with-files and an agent memory tool?

Agent memory tools (vector stores, knowledge graphs) help an agent recall facts from past sessions. planning-with-files manages active execution state: the phases, status, dependencies, and completion check for the task the agent is working on right now. The problem it solves is planning continuity, not retrieval, and the two are complementary.

### How does this prevent context rot?

Context rot is the drift that sets in as the context window fills and earlier instructions get crowded out. Because the plan is re-injected at the start of each turn from disk, the goals and phase status stay in the model's attention window as the conversation grows. This is an implementation of what Anthropic calls structured note-taking: write durable state to files outside the window, then read it back in when needed.

### Which coding agents does this work with?

Claude Code, OpenAI Codex CLI, Cursor, GitHub Copilot, Kiro, OpenCode, Continue, Pi, CodeBuddy, Factory, Mastra, and 60+ others via the SKILL.md open standard. Installation is one command; see [Quick Install](#quick-install) above.

## Documentation

All platform setup guides and documentation are in the [docs/](./docs/) folder.


## Acknowledgments

- **Manus AI** — For pioneering context engineering patterns
- **Anthropic** — For Claude Code, Agent Skills, and the Plugin system
- **Lance Martin** — For the detailed Manus architecture analysis
- Based on [Context Engineering for AI Agents](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License — feel free to use, modify, and distribute.

---

**Author:** [Ahmad Othman Ammar Adi](https://github.com/OthmanAdi)

## Star History

<a href="https://repostars.dev/?repos=OthmanAdi%2Fplanning-with-files&theme=copper"><img src="https://repostars.dev/api/embed?repo=OthmanAdi%2Fplanning-with-files&theme=copper" width="100%" alt="Star History Chart" /></a>
