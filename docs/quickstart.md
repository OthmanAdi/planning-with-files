# Quick Start Guide

Follow these 5 steps to use the planning-with-files pattern.

---

## Step 1: Invoke the Skill and Describe Your Task

**When:** Before starting any work on a complex task

**Action:** Invoke the skill (e.g., `/plan` or `/planning-with-files:start`) and describe what you want to accomplish. The AI will create all three planning files in your project directory:

- `task_plan.md` — Phases and progress tracking
- `findings.md` — Research and discoveries
- `progress.md` — Session log and test results

If you invoke the skill without a task description, the AI will ask you what you'd like to plan.

**Manual alternative:** If you prefer to create files yourself:
```bash
# Use the init script
./scripts/init-session.sh
# Then fill in the Goal section in task_plan.md
```

---

## Step 2: Plan Your Phases

**When:** Right after creating the files

**Action:** Break your task into 3-7 phases in `task_plan.md`

**Example:**
```markdown
### Phase 1: Requirements & Discovery
- [ ] Understand user intent
- [ ] Research existing solutions
- **Status:** in_progress

### Phase 2: Implementation
- [ ] Write core code
- **Status:** pending
```

**Update:**
- `task_plan.md`: Define your phases
- `progress.md`: Note that planning is complete

---

## Step 3: Work and Document

**When:** Throughout the task

**Action:** As you work, update files:

| What Happens | Which File to Update | What to Add |
|--------------|---------------------|-------------|
| You research something | `findings.md` | Add to "Research Findings" |
| You view 2 browser/search results | `findings.md` | **MUST update** (2-Action Rule) |
| You make a technical decision | `findings.md` | Add to "Technical Decisions" with rationale |
| You complete a phase | `task_plan.md` | Change status: `in_progress` → `complete` |
| You complete a phase | `progress.md` | Log actions taken, files modified |
| An error occurs | `task_plan.md` | Add to "Errors Encountered" table |
| An error occurs | `progress.md` | Add to "Error Log" with timestamp |

**Example workflow:**
```
1. Research → Update findings.md
2. Research → Update findings.md (2nd time - MUST update now!)
3. Make decision → Update findings.md "Technical Decisions"
4. Implement code → Update progress.md "Actions taken"
5. Complete phase → Update task_plan.md status to "complete"
6. Complete phase → Update progress.md with phase summary
```

---

## Optional: Split Large or Unrelated Topics

For one focused task, the three root files are enough. For several unrelated
tasks in the same repository, use an isolated plan directory so each topic has
its own `task_plan.md`, `findings.md`, and `progress.md`:

```bash
./scripts/init-session.sh backend-refactor
./scripts/init-session.sh production-incident
./scripts/set-active-plan.sh 2026-01-10-backend-refactor
```

For a long-running operational topic that shares the same root plan, keep
`progress.md` concise and move durable details into a topic handoff file:

```text
progress.md
  Runtime-wide timeline and short pointers

handoffs/backend-refactor.md
  Current state, commands, validation, risks, rollback, PR links
```

Use this pattern when a discussion spans multiple sessions, has many commands,
or needs a clean resume point without scanning the full timeline. Add one short
line to `progress.md` whenever the topic handoff changes, then put the details
in the handoff file.

For GitHub work, `progress.md` should usually record only the branch, commit,
PR URL, validation summary, and handoff file. Put the longer PR context,
remaining risks, and rollback notes in the topic handoff.

---

## Step 4: Re-read Before Decisions

**When:** Before making major decisions (automatic with hooks in Claude Code)

**Action:** The PreToolUse hook automatically reads `task_plan.md` before Write/Edit/Bash operations

**Manual reminder (if not using hooks):** Before important choices, read `task_plan.md` to refresh your goals

**Why:** After many tool calls, original goals can be forgotten. Re-reading brings them back into attention.

---

## Step 5: Complete and Verify

**When:** When you think the task is done

**Action:** Verify completion:

1. **Check `task_plan.md`**: All phases should have `**Status:** complete`
2. **Check `progress.md`**: All phases should be logged with actions taken
3. **Run completion check** (if using hooks, this happens automatically):
   ```bash
   ./scripts/check-complete.sh
   ```

**If not complete:** The Stop hook (or script) will prevent stopping. Continue working until all phases are done.

**If complete:** Deliver your work! All three planning files document your process.

---

## Quick Reference: When to Update Which File

```
┌─────────────────────────────────────────────────────────┐
│  task_plan.md                                            │
│  Update when:                                            │
│  • Starting task (create it first!)                      │
│  • Completing a phase (change status)                    │
│  • Making a major decision (add to Decisions table)     │
│  • Encountering an error (add to Errors table)          │
│  • Re-reading before decisions (automatic via hook)      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  findings.md                                             │
│  Update when:                                            │
│  • Discovering something new (research, exploration)    │
│  • After 2 view/browser/search operations (2-Action!)   │
│  • Making a technical decision (with rationale)          │
│  • Finding useful resources (URLs, docs)                 │
│  • Viewing images/PDFs (capture as text immediately!)   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  progress.md                                             │
│  Update when:                                            │
│  • Starting a new phase (log start time)                 │
│  • Completing a phase (log actions, files modified)      │
│  • Running tests (add to Test Results table)            │
│  • Encountering errors (add to Error Log with timestamp)│
│  • Resuming after a break (update 5-Question Check)     │
└─────────────────────────────────────────────────────────┘
```

---

## Common Mistakes to Avoid

| Don't | Do Instead |
|-------|------------|
| Start work without creating `task_plan.md` | Always create the plan file first |
| Forget to update `findings.md` after 2 browser operations | Set a reminder: "2 view/browser ops = update findings.md" |
| Skip logging errors because you fixed them quickly | Log ALL errors, even ones you resolved immediately |
| Repeat the same failed action | If something fails, log it and try a different approach |
| Only update one file | The three files work together - update them as a set |

---

## Next Steps

- See [examples/README.md](../examples/README.md) for complete walkthrough examples
- See [workflow.md](workflow.md) for the visual workflow diagram
- See [troubleshooting.md](troubleshooting.md) if you encounter issues
