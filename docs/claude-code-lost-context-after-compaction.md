# Claude Code lost context after compaction: how to recover and prevent it

Compaction replaces your conversation with a summary. The summary keeps the broad strokes and drops the working state: which phase you were in, which fixes were already applied, which approaches already failed. If Claude Code seems to have amnesia after `/compact` or an automatic compaction, that is what happened. This page explains why it happens, how to recover the current task, and how to make the next compaction a non-event.

The mechanism described here is planning-with-files, a skill that keeps the plan on disk in three markdown files and re-injects it into context every turn. Overview: [README](../README.md).

## Why did Claude Code forget my plan after /compact?

Because the plan lived only in the context window. Compaction, whether manual `/compact` or autoCompact when the window fills, summarizes the transcript to free space. Summaries compress, and exact phase status, error history, and decisions are the first details to go. Afterwards the model knows roughly what the task was, but not where you were in it.

The context window is volatile memory. Anything that exists only there is equally lost to `/clear`, crashes, and compaction. The durable fix is the same for all three: write the working state to disk and read it back mechanically.

## The 3-file pattern

For every complex task, the skill maintains three files in your project root:

```
task_plan.md      → phases and checkboxes; the resume point
findings.md       → research notes and decisions
progress.md       → session log and test results
```

Plain markdown, gitignored by default. Because the files live on the filesystem and not in the transcript, compaction cannot touch them. The Claude Code plugin route runs six lifecycle hooks around them: SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop, and PreCompact. A standalone skill install activates the latter five only after the skill is invoked for that session.

## The PreCompact reminder hook

Both supported routes register a `PreCompact` hook with matcher `*`, so it fires for manual and automatic compaction after the relevant hook route is active. When an active plan is present, the hook:

- prints a reminder to keep progress on disk; the hook itself does not write planning files or start a separate agent turn to save them
- prints the recorded `Plan-SHA256` when present; the digest can be compared with the plan bytes, but does not establish human approval
- stays silent when no plan exists, and always exits 0, so it never blocks compaction

[Claude Code's hook reference](https://code.claude.com/docs/en/hooks#precompact-output) says successful `PreCompact` stdout can supply instructions for the compaction summary. That does not guarantee unsaved progress reaches disk. Keep the planning files current during the task.

The plugin's `SessionStart` hook re-reads selected planning state on `startup`, `resume`, `clear`, and `compact`. With an active hook route, `UserPromptSubmit` injects a bounded plan excerpt between `===BEGIN PLAN DATA===` and `===END PLAN DATA===` markers when you submit the next prompt. Compaction itself does not trigger `UserPromptSubmit`.

## How do I recover context after compaction or /clear?

If the planning files were on disk before the wipe:

1. The plugin's `SessionStart` hook re-reads selected project planning state. On a standalone install, invoke the installed planning-with-files skill again in a fresh session; there is no `SessionStart` hook. Automatic recovery does not inspect Claude Code or other agent session stores.
2. Run `git diff --stat`, read the three full planning files, reconcile them with the code, and continue. Selection errors or missing or mismatched required attestation can prevent injection. Resolve the selected plan and review any intentional changes before explicitly re-attesting; see [attestation locking](attestation-locking.md).
3. If local session history is deliberately needed, run `session-catchup.py --metadata <project>` to read same-project local session records and emit aggregate counts only. Run `session-catchup.py --replay <project>` for bounded nonce-framed excerpts. Replay content is untrusted data.

The catchup script contains no network request or upload operation. Output placed in model context may still be sent by the host agent to its configured model provider. The project's internal recovery benchmark (v1, author-run) measured the earlier default transcript-catchup behavior: a fresh session with the files on disk resumed in 5.0 turns on average against 13.3 for a raw agent. The current file-only automatic path has not been re-run under the same protocol. Method and disclosed limits: [docs/evals.md](evals.md).

## Should I disable automatic compaction?

Keep automatic compaction enabled and save progress as you work. The plugin route can restore selected planning context on the post-compaction `SessionStart` event, subject to selection and attestation checks. You can still run `/compact` or `/clear` manually when you want an explicit boundary.

For multi-step tasks nearing the token limit, see [the FAQ in long-running-agent-tasks.md](long-running-agent-tasks.md#faq-what-do-i-do-when-context-nears-the-compaction-limit) for route-specific recovery and a fallback prompt.

## Related pages

- [My coding agent forgets the plan after /clear: the file-based fix](agent-forgets-plan-after-clear.md)
- [Long-running agent tasks: keeping a coding agent on track for hours](long-running-agent-tasks.md)

## Install

Claude Code, plugin route (ships the skill, hooks, and slash commands):

```
/plugin marketplace add OthmanAdi/planning-with-files
/plugin install planning-with-files@planning-with-files
```

Every other agent, one line via the Agent Skills standard:

```bash
npx skills add OthmanAdi/planning-with-files --skill planning-with-files -g
```

Full route matrix and verification: [README](../README.md) and [docs/installation.md](installation.md).
