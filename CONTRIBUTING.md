# Contributing

Thank you for considering a contribution to planning-with-files.

This project keeps contribution work small, traceable, and reviewable. Please make one logical change per pull request and keep the tone concise and concrete.

## How to set up locally

Fork the repository, then clone your fork:

```bash
git clone https://github.com/YOUR-USERNAME/planning-with-files.git
cd planning-with-files
```

Add the upstream repository so you can sync your fork with the original project:

```bash
git remote add upstream https://github.com/OthmanAdi/planning-with-files.git
git fetch upstream
```

The canonical skill lives here:

```text
skills/planning-with-files/SKILL.md
```

Before opening a pull request, run the test suite:

```bash
python -m pytest tests/ -q
```

Two pre-existing Windows exec-bit test failures may appear on Windows. If those are the only failures, note that in your pull request description.

## Project layout

The canonical skill source is:

```text
skills/planning-with-files/
```

Language variants live under directories that follow this pattern:

```text
skills/planning-with-files-<lang>/
```

IDE adapter variants live under these directories:

```text
.codebuddy/
.codex/
.cursor/
.factory/
.hermes/
.mastracode/
.opencode/
.pi/
```

The `clawhub-upload/` directory is gitignored and handled manually. Do not rely on it as the source of truth for repository changes.

## Submitting a PR

Use a focused branch name that describes the type of change:

```text
fix/short-description
feat/short-description
docs/short-description
```

Use Conventional Commits for commit messages:

```text
fix: describe the bug fix
feat: describe the new behavior
docs: describe the documentation change
```

Keep each pull request to one logical change. A documentation fix, a language variant update, and a test change should usually be separate pull requests.

When opening the pull request, include:

- What changed
- Why it changed
- How you tested it
- Any known limitations or platform-specific notes

If the pull request closes an issue, include the issue reference in the description:

```text
Closes #123
```

## Authorship and credit

The project maintains contributor credit in `CONTRIBUTORS.md`.

Merged pull requests earn a permanent contributor entry. Keep your Git author information accurate because your commits remain part of the project history and are not treated as disposable metadata.

Small contributions count. Documentation fixes, language variant updates, tests, and adapter improvements all help maintain the project.

## Language variant contributions

Translations and language variant improvements are welcome.

When working on a language variant, compare it against the canonical skill in:

```text
skills/planning-with-files/SKILL.md
```

Keep translated variants in parity with the canonical version. Do not ship a localized description with an English body stub. If a section cannot be translated yet, leave a clear note in the pull request instead of hiding incomplete work in the file.

## Where to ask questions

For general questions, use GitHub Discussions.

For issue-specific questions, comment on the relevant issue. If maintainer attention is needed, tag `@OthmanAdi` and describe the specific point you need help with.

Good questions include context, what you tried, and where you are blocked.
