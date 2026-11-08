# AGENTS.md, planning-with-files maintainer rules

For any agent doing releases, merges or issue work in this repository. The code and `scripts/` are discoverable; this file holds the decisions that are not.

## Authorship
- Contributor commits keep the contributor as `Author:`. Merge with `git fetch origin pull/N/head:pr-N && git cherry-pick <sha>` or `gh pr merge --rebase`. Never `git merge --squash` a contributor PR: it reassigns their commit to whoever runs the local commit, which happened once in the v2.40.1 cycle. Squash only your own WIP before pushing.
- Release and maintenance commits are authored by OthmanAdi alone, Conventional Commits (`fix:`, `feat:`, `release:`, `docs:`), no `Co-Authored-By`. Contributors are credited in the CHANGELOG `### Thanks` section and in `CONTRIBUTORS.md`, never in trailers.
- No `--no-verify`. No force push to master except tag ref updates and history corrections Adi explicitly authorised.

## Release flow
1. Read the issue and the PR in full (`gh issue view N`, `gh pr view N`). Reproduce the claim against the code. Audit the diff for supply-chain vectors (new dependencies, install scripts, bin shims, files in the install path). Comment on the issue the moment it is confirmed, with the planned fix; the closing comment comes after shipping. Never batch all communication to the end.
2. `python -m pytest tests/ -q` is green before and after the merge.
3. Merge the contributor commits as above, then one release commit on top: CHANGELOG entry, CONTRIBUTORS.md (entry, total count, date), README version badge and releases table row, version bump.
4. Bump with `python scripts/bump-version.py X.Y.Z` (`--dry-run` first), never by hand. `tests/test_skill_md_version_parity.py` defines the parity set (19 tracked files plus the gitignored `clawhub-upload/SKILL.md` when present); the script and the test are the source of truth, not any list in prose. Deliberately lagging: `.continue` and `.gemini` (bump only on an explicit scope decision), `.kiro` (own `-kiro` scheme), `.pi/.../SKILL.md` (no version field; the Pi version is its `package.json`, which is in the set). The bundled Pi extension's own `package.json` moves only when that extension changed. Then run `python scripts/build-npm-readme.py`, which rebuilds the npm README (`.pi/skills/planning-with-files/README.md`) from `README.md` with relative links pinned to the new tag; `tests/test_npm_readme.py` fails until it is current, and `--check` reports what is stale without writing.
5. Tag `vX.Y.Z` on the release commit, push master and the tag, then `gh release create vX.Y.Z --title "vX.Y.Z - <short description>" --notes "<what changed, then Thanks>"`.
6. Distribution is manual after every release. ClawHub: `python scripts/build-clawhub-upload.py`, then `python scripts/build-clawhub-upload.py --verify` (the staged folder must match the tracked inventory), then upload the whole `clawhub-upload/` folder at clawhub.io (its SSL certificate may be expired; proceed through the warning). npm: `npm publish` from `.pi/skills/planning-with-files/` (the unscoped package `planning-with-files`, Adi's account; the abandoned `@tomxprime/planning-with-files` and `pi-planning-with-files` are never touched). skills.sh and `npx skills` pull master on their own; the Anthropic marketplace reflects the ClawHub upload.
7. Comment on the PR and the issue (contributor's @handle, the version that fixes it, root cause and mechanism, "you are in CONTRIBUTORS.md" when true, the commit SHA so it auto-links), then close what GitHub did not close.

## Formats
- CHANGELOG: `## [X.Y.Z] - YYYY-MM-DD`, then `### Added|Fixed|Changed|Security`, then `### Thanks` with one line per contributor (first name or @handle, what they did, issue or PR number).
- CONTRIBUTORS.md: `**[Name](https://github.com/handle)** — [PR #N](link)` plus one bullet per contribution; "Other Contributors" for a single fix, "Major Contributions" for larger work; update the total and the "Last updated" date.
- Release notes start with what changed; Thanks at the bottom.
- All public prose (comments, notes, CHANGELOG) is matter-of-fact: no em-dashes, no "Great report!" or "Thank you so much!", no "I'd like to". Run it through `/humanizer` before posting.

## Repo contracts (orchestrator architecture, locked 2026-04-22)
- `task_plan.md` and `DESIGN.md` are user-owned; agents never edit them directly. Subagent returns go to `progress.md`, never `task_plan.md`. Design tokens and research notes are appended to `findings.md` under a `## Design Context` heading.
- Markdown on disk is the shared state across agents; no runtime-only state.
- The memory layer wraps `code-memory-router`; it does not replace it.
