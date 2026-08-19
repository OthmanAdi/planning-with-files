# AGENTS.md — planning-with-files agent reference card

This file is the canonical, session-portable reference for how every agent working in this repo must handle commits, releases, version bumps, CHANGELOG entries, and issue/PR communication.

---

## Commit rules

- **Author**: OthmanAdi only for release/maintenance commits. NEVER add `Co-Authored-By:` trailers.
- **Format**: Conventional Commits — `fix:`, `feat:`, `release:`, `docs:` prefixes.
- **One release commit on top of the contributor commit(s), never a squash of the contributor's work.** `git merge --squash` rewrites the committer as whoever runs the local commit, which reassigns the contributor's authorship to OthmanAdi — this happened once (v2.40.1 cycle) and is exactly what this rule exists to prevent. Squashing is fine only for collapsing your OWN WIP commits before pushing.
- No `--no-verify`. No force push to master except tag ref updates.
- Contributors are credited in CHANGELOG `### Thanks` and `CONTRIBUTORS.md`, never in commit trailers.

---

## Release checklist (12 steps)

1. `gh issue view N` and `gh pr view N` — read both in full.
2. Verify the bug is real: find the exact file/line, grep for the pattern, confirm reporter is correct.
3. `python -m pytest tests/ -q` — all tests pass before touching anything.
4. Merge preserving contributor authorship: `git fetch origin pull/N/head:pr-N && git cherry-pick <pr-head-sha>`, or `gh pr merge --rebase`. Do NOT use `git merge --squash` — it collapses the contributor's commit and reassigns the `Author:` field to whoever runs the local commit, destroying their credit in `git log`.
5. CHANGELOG — new version entry at top, `### Fixed`/`### Added`/`### Changed`, sachlich, no em-dashes.
6. CONTRIBUTORS.md — add reporter/contributor, bump "Total Contributors: N+", update "Last updated" date.
7. Version bump across all 18 tracked targets plus the local ClawHub staging target when present (see table below).
8. README — update version badge and add row to releases table.
9. `git commit`, `git tag vX.Y.Z`, `git push origin master`, `git push origin vX.Y.Z`.
10. `gh release create vX.Y.Z --title "vX.Y.Z - <short description>" --notes "<release notes>"`.
11. Post comment on PR and/or issue via `gh issue comment N --body "..."` (run through /humanizer first).
12. `gh issue close N` if applicable.

---

## Version bump scope

The maintained release set has 19 entries: 18 tracked files plus the gitignored `clawhub-upload/SKILL.md` publish stage. Every present entry must use the same version string. `scripts/bump-version.py` reports the ClawHub stage as optional when it is absent from a fresh clone, but updates and validates it when present. Maintainer releases must rebuild and verify that stage separately before the manual upload.

| File | Notes |
|------|-------|
| `skills/planning-with-files/SKILL.md` | Primary English |
| `skills/i18n/planning-with-files-ar/SKILL.md` | Arabic |
| `skills/i18n/planning-with-files-de/SKILL.md` | German |
| `skills/i18n/planning-with-files-es/SKILL.md` | Spanish |
| `skills/i18n/planning-with-files-zh/SKILL.md` | Simplified Chinese |
| `skills/i18n/planning-with-files-zht/SKILL.md` | Traditional Chinese |
| `.codebuddy/skills/planning-with-files/SKILL.md` | CodeBuddy IDE |
| `.codex/skills/planning-with-files/SKILL.md` | Codex IDE |
| `.cursor/skills/planning-with-files/SKILL.md` | Cursor IDE |
| `.factory/skills/planning-with-files/SKILL.md` | Factory IDE |
| `.hermes/skills/planning-with-files/SKILL.md` | Hermes adapter |
| `.mastracode/skills/planning-with-files/SKILL.md` | Mastra Code |
| `.opencode/skills/planning-with-files/SKILL.md` | OpenCode IDE |
| `.pi/skills/planning-with-files/package.json` | npm package manifest |
| `.agents/skills/planning-with-files/SKILL.md` | Agent Skills standard layout (Zed, Amp, Warp, Devin, Antigravity, Gemini CLI read this path natively; added v3.7.0) |
| `clawhub-upload/SKILL.md` | Gitignored ClawHub marketplace staging; required for maintainer upload, optional in a fresh clone |
| `.claude-plugin/plugin.json` | Plugin manifest |
| `.claude-plugin/marketplace.json` | Marketplace metadata |
| `CITATION.cff` | Citation file |

**NOT bumped automatically**: `scripts/bump-version.py`'s `LAGGING_FILES` list currently excludes four files, not two — this table only tracked two until this correction:
- `.continue/skills/planning-with-files/SKILL.md`, `.gemini/skills/planning-with-files/SKILL.md` — intentionally behind. Do not bump without an explicit scope decision.
- `.pi/skills/planning-with-files/SKILL.md` — carries no `version` field at all; the Pi channel's version lives in `.pi/skills/planning-with-files/package.json` (the npm package `planning-with-files`), which since v3.9.0 IS part of the parity set and bumped by `bump-version.py`. Publishing to npm (`npm publish` from that folder) is a manual step after each release, like the ClawHub upload.
- `.kiro/skills/planning-with-files/SKILL.md` — carries its own `-kiro`-suffixed scheme (e.g. `3.0.0-kiro`), bumped on Kiro-relevant changes rather than every canonical release.

Recent CHANGELOG entries (v3.1.1–v3.1.3) already describe this 4-file exclusion as "per AGENTS.md release scope" — this section previously did not actually say so. It does now.

---

## CHANGELOG format

```
## [X.Y.Z] - YYYY-MM-DD

### Fixed
- Short description of what was wrong and how it was fixed.

### Thanks
- @handle — what they contributed (issue #N / PR #N)
```

Rules:
- Sachlich (matter-of-fact). No em-dashes. No hype.
- Contributor line: first name or @handle, one sentence, issue/PR reference.
- Run any prose through /humanizer before publishing anywhere public.

---

## CONTRIBUTORS.md format

```markdown
### Other Contributors

**[Name](https://github.com/handle)** — [PR #N](link) / [Issue #N](link)
- What they did (one bullet per contribution)
- Impact or context
```

- Update "Total Contributors: N+" count.
- Update "Last updated: YYYY-MM-DD" date.
- Scope determines section: "Other Contributors" for single-issue fix, "Major Contributions" for larger work.

---

## Issue/PR comment style

After a fix ships, comment on the issue or PR:

- Address by `@handle`.
- One sentence: fix confirmed in vX.Y.Z.
- Specific: what the root cause was, what mechanism changed.
- If they are now in CONTRIBUTORS.md, say so.
- Run through /humanizer before posting.

NOT acceptable in any public comment:
- "Great report!"
- "Thank you so much!"
- Em-dashes (do not use — this style)
- "I'd like to"
- Performative warmth of any kind

---

## Release notes format (gh release create --notes)

```
What changed:

- <Bug description> — <what the fix does>
- <Feature description> — <how it works>

Thanks: @handle for reporting issue #N.
```

- Start with what changed, not who did it.
- No em-dashes.
- Thanks at the bottom.

---

## ClawHub distribution

- ClawHub does NOT auto-sync with GitHub.
- After every release: manually upload `clawhub-upload/SKILL.md` at clawhub.io.
- SSL cert on clawhub.io may be expired — proceed through the browser warning.
- skills.sh / `npx skills`: pulls from GitHub master automatically on next crawl.
- Anthropic plugin marketplace: requires ClawHub upload to reflect the new version.

---

## Quick reference: what NOT to do

- Do not add Co-Authored-By to any commit.
- Do not bump `.continue` or `.gemini` without explicit instruction. `.kiro` has its own version scheme, and `.pi/skills/planning-with-files/SKILL.md` has no version field. The Pi npm version in `.pi/skills/planning-with-files/package.json` is part of the canonical parity set.
- Do not `git merge --squash` a contributor PR — it reassigns their commit authorship. Use cherry-pick or `gh pr merge --rebase`.
- Do not edit `task_plan.md` or `DESIGN.md` directly (user-owned contracts).
- Do not log subagent returns into `task_plan.md` — use `progress.md`.
- Do not use em-dashes in any user-facing prose.
- Do not skip ClawHub upload after a release.
