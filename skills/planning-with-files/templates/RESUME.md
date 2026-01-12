# Session Resumption
<!--
  WHAT: Ready-to-use prompt and context snapshot for continuing in a new session.
  WHY: When context fills up (~140K+ tokens), you need to switch sessions cleanly.
  WHEN: Update this BEFORE context gets too full. Use /context to check.
  
  Based on: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
-->

## Ready-to-Use Prompt

Copy and paste this into a **new Claude session**:

```
Read the following files to restore context and continue execution:
- task_plan.md (phases and progress)
- findings.md (research and decisions)
- progress.md (session log)

Resume from Phase [CURRENT_PHASE]. Do not re-do completed work.
Current focus: [NEXT_ACTION]
```

## Session Snapshot
<!--
  Update these before switching sessions.
  This is your "volatile context" that might not be in the planning files.
-->

| Field | Value |
|-------|-------|
| **Last Updated** | [YYYY-MM-DD HH:MM] |
| **Current Phase** | [X] of [Y] |
| **Context Usage** | [LOW / MEDIUM / HIGH / CRITICAL] |
| **Blocker** | [None / Description] |

## Volatile Context
<!--
  CRITICAL: Capture anything important that's NOT already in the planning files.
  These are things mentioned verbally or assumed but not written down.
-->

- [ ] [User preference or requirement mentioned in conversation]
- [ ] [Assumption made but not documented]
- [ ] [Decision discussed but not logged in findings.md]
- [ ] [Error encountered but not logged]

## Next Action
<!--
  Be specific. What exactly should the next session do first?
-->

[Describe the exact next step to take when resuming]

## Git Checkpoint
<!--
  Before switching sessions, commit your progress:
  
  git add task_plan.md findings.md progress.md RESUME.md
  git commit -m "checkpoint: Phase X complete, switching sessions"
-->

- [ ] Planning files updated
- [ ] Changes committed
- [ ] Ready to switch sessions

---
<!--
  WORKFLOW:
  1. Check context usage with /context
  2. At ~80%, update this file
  3. Commit checkpoint
  4. Start new session
  5. Paste the prompt above
  6. Continue working
-->
*Update this file before context fills up. Check with `/context` command.*
