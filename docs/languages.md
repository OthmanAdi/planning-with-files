# Language variants

`planning-with-files` ships the planning workflow in six languages. The English skill is the canonical one. Arabic, German, Spanish, Simplified Chinese and Traditional Chinese are full translations: the SKILL.md body, the three templates, and the user-facing output of `check-complete`, `init-session` and `session-catchup` are all translated, and each variant carries the same 22 scripts as the canonical skill. See the [canonical scripts directory](../skills/planning-with-files/scripts/) for the current inventory.

All language variants use the same recovery consent boundary. Automatic recovery reads project planning files only. Explicit `session-catchup.py --metadata` reads same-project local session records and emits aggregate counts only, without transcript bytes; explicit `--replay` may emit bounded nonce-framed excerpts. The catchup path contains no network upload operation.

| Language | Skill name | Command |
|---|---|---|
| English | `planning-with-files` | `/plan` |
| العربية | `planning-with-files-ar` | `/plan-ar` |
| Deutsch | `planning-with-files-de` | `/plan-de` |
| Español | `planning-with-files-es` | `/plan-es` |
| 简体中文 | `planning-with-files-zh` | `/plan-zh` |
| 繁體中文 | `planning-with-files-zht` | `/plan-zht` |

## Installing one

Pass the skill name with `--skill`. Add `-g` to install globally rather than into the current project.

```bash
npx skills add OthmanAdi/planning-with-files --skill planning-with-files-ar -g
npx skills add OthmanAdi/planning-with-files --skill planning-with-files-de -g
npx skills add OthmanAdi/planning-with-files --skill planning-with-files-es -g
npx skills add OthmanAdi/planning-with-files --skill planning-with-files-zh -g
npx skills add OthmanAdi/planning-with-files --skill planning-with-files-zht -g
```

Each lands in its own directory, for example `~/.claude/skills/planning-with-files-de/`, and registers under its own name. Installing a translation does not install the English skill, and installing the English skill does not install any translation.

Running `npx skills add OthmanAdi/planning-with-files` with no `--skill` opens a picker listing all available skills with none preselected, so nothing is installed that you did not choose.

## Where they live in the repository

```
skills/
├── planning-with-files/          canonical English skill
└── i18n/
    ├── planning-with-files-ar/
    ├── planning-with-files-de/
    ├── planning-with-files-es/
    ├── planning-with-files-zh/
    └── planning-with-files-zht/
```

Since v3.11.0 the translations sit one directory deeper than the canonical skill. `npx skills add` resolves `--skill` by skill name across a recursive scan, so every install command above is unchanged by that layout and every skill remains individually installable.

## On the Claude Code plugin route

The plugin scan reads `skills/*/SKILL.md` at a single level and does not recurse, so the plugin registers the canonical skill alone. That is deliberate. Before v3.11.0 the plugin registered all six, and every session paid for five skill descriptions in its system prompt whether or not the user had any use for them.

The five language commands still work on the plugin route. `/plan-de` and its siblings read the translated SKILL.md from disk, trying `$HOME/.claude/skills/planning-with-files-<lang>/SKILL.md` first and then `${CLAUDE_PLUGIN_ROOT}/skills/i18n/planning-with-files-<lang>/SKILL.md`. If neither exists, the command falls back to the canonical skill with an instruction to keep working in that language.

Because the plugin no longer registers them, there is no `planning-with-files:planning-with-files-de` skill id to invoke by name on that route. Reach a translation through its command, or install it as its own skill with the command above.

## Status tokens stay in English

Every translated `task_plan.md` template keeps the status values as literal English: `pending`, `in_progress`, and `complete`. The field label may be translated to match the language, but only when that translation's own checker runs. Canonical fallback (`scripts/check-complete.sh`) matches a `**Status:**` line; a phase labeled `**Estado:**` is not that match. For example, the Spanish template ships one status line per phase:

```markdown
- **Estado:** pending
```

The other allowed values are `in_progress` and `complete`. Put exactly one native status line in each phase, and use the phase heading from your language's template. Arabic and both Chinese templates use localized headings (`### المرحلة`, `### 阶段`, and `### 階段`). Copying several status lines into one phase makes the checker mark it invalid.

The checker accepts a recognized English marker such as `[complete]` in the phase, so the presence of a translated value alone does not determine the result. That marker counts as the one status for the phase. On the canonical checker, a `**Estado:**` phase with no such marker is invalid / untrackable with `--validate`. Surrounding prose is translated and the tokens are not. The five language commands state this explicitly so the model does not translate them either.

## Reporting a translation problem

Open an issue naming the language and quoting the text. Translations are contributed and reviewed by speakers, not machine generated, so corrections from native speakers are welcome and land in the next release.
