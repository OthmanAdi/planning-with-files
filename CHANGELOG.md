# Changelog

All notable changes to this project will be documented in this file.

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
