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

- **[@lasmarois](https://github.com/lasmarois)** - [PR #33](https://github.com/OthmanAdi/planning-with-files/pull/33)
  - Created session recovery feature for context preservation after `/clear`
  - Built `session-catchup.py` script to analyze previous session JSONL files
  - Enhanced PreToolUse hook to include Read/Glob/Grep operations
  - Restructured SKILL.md for better session recovery workflow
  - **Impact:** Solves context loss problem, enables seamless work resumption

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

### Other Contributors

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

## Community Forks

These developers have created forks that extend the functionality:

- **[@RioTheGreat-ai](https://github.com/RioTheGreat-ai)** - [agentfund-skill](https://github.com/RioTheGreat-ai/agentfund-skill)
  - Crowdfunding platform for AI agents using milestone-based escrow on Base, built with planning-with-files

- **[@kmichels](https://github.com/kmichels)** - [multi-manus-planning](https://github.com/kmichels/multi-manus-planning)
  - Multi-project support
  - SessionStart git sync integration

## Issue Reporters & Testers

Thank you to everyone who reported issues, provided feedback, and helped test fixes:

- [@DorianZheng](https://github.com/DorianZheng) - Issue #84 (BoxLite sandbox integration proposal)
- [@mtuwei](https://github.com/mtuwei) - Issue #32 (Windows hook error)
- [@JianweiWangs](https://github.com/JianweiWangs) - Issue #31 (Skill activation)
- [@tingles2233](https://github.com/tingles2233) - Issue #29 (Plugin update issues)
- [@st01cs](https://github.com/st01cs) - Issue #28 (Devis fork discussion)
- [@wqh17101](https://github.com/wqh17101) - Issue #11 testing and confirmation

And many others who have starred, forked, and shared this project!

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

**Total Contributors:** 24+ and growing!

*Last updated: February 28, 2026*
