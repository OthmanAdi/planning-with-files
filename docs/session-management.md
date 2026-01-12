# Session Management Guide

How to handle long-running tasks that exceed context limits.

## The Problem

Claude Code has a context window limit (~200K tokens). Complex tasks can fill this quickly:
- Research-heavy tasks
- Multi-file implementations  
- Tasks with many tool calls

When context fills up, you have two choices:
1. **Auto-compact** — Claude summarizes and loses some details
2. **Manual handoff** — You switch sessions with full context preserved in files

This guide covers option 2.

## The Solution: File-Based Handoff

Based on [Anthropic's engineering recommendations](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents):

> "Each new session begins with no memory of what came before"

Your planning files ARE your memory. When context fills up:
1. Update planning files with current state
2. Create handoff prompt
3. Start fresh session
4. Resume from files

## When to Switch Sessions

Check context usage with `/context` command.

| Usage | Action |
|-------|--------|
| < 60% | Continue normally |
| 60-80% | Start preparing handoff |
| 80-90% | Create handoff, consider switching |
| > 90% | Switch now before auto-compact |

## Quick Handoff

### Option 1: Use the Script

```bash
./scripts/create-handoff.sh
```

This generates `RESUME.md` with a ready-to-paste prompt.

### Option 2: Manual Handoff

1. Update your planning files
2. Copy this prompt into a **new session**:

```
Read the following files to restore context and continue execution:
- task_plan.md (phases and progress)
- findings.md (research and decisions)
- progress.md (session log)

Resume from Phase [X]. Do not re-do completed work.
```

## Git Checkpoint Workflow

After completing each phase, commit your progress:

```bash
git add task_plan.md findings.md progress.md
git commit -m "checkpoint: Phase 1 complete"
```

Before switching sessions:

```bash
git add task_plan.md findings.md progress.md RESUME.md
git commit -m "checkpoint: switching sessions at Phase 2"
```

This gives you recovery points if something goes wrong.

## Why Not Use /resume?

| Approach | Problem |
|----------|---------|
| `/resume` | Restores full message history — same context problem |
| Auto-compact | Lossy summarization — details get compressed away |
| File handoff | Clean slate with full context preserved in files ✅ |

## Why Not Use Sub-Agents?

Sub-agents have isolated context windows, but:
- `general-purpose` agents inherit parent context
- `plan` agents inherit parent context
- Only `Explore` agents start fresh (but they're read-only)

Custom subagents might work, but file-based handoff is simpler and guaranteed.

## Session Management in task_plan.md

Track session switches in your task plan:

```markdown
## Session Management
| Session | Date | Phases Completed | Notes |
|---------|------|------------------|-------|
| 1       | 2026-01-12 | 1, 2 | Initial session, hit 85% context |
| 2       | 2026-01-12 | 3, 4 | Resumed, completed implementation |
| 3       | 2026-01-13 | 5 | Final delivery |
```

## Volatile Context

Before switching, capture anything NOT in your planning files:
- User preferences mentioned verbally
- Assumptions made but not documented
- Decisions discussed but not logged

Add these to RESUME.md or directly to findings.md.

## The 5-Question Reboot Test

If you can answer these from your files, your handoff is solid:

| Question | Answer Source |
|----------|---------------|
| Where am I? | Current phase in task_plan.md |
| Where am I going? | Remaining phases in task_plan.md |
| What's the goal? | Goal statement in task_plan.md |
| What have I learned? | findings.md |
| What have I done? | progress.md |

## Files Reference

| File | Purpose |
|------|---------|
| `task_plan.md` | Phases, progress, decisions, session tracking |
| `findings.md` | Research, discoveries, technical decisions |
| `progress.md` | Session log, test results, error history |
| `RESUME.md` | Handoff prompt and volatile context |

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `./scripts/init-session.sh` | Initialize planning files |
| `./scripts/create-handoff.sh` | Generate RESUME.md for session switch |
| `./scripts/check-complete.sh` | Verify all phases complete |

---

## Further Reading

- [Anthropic: Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Manus: Context Engineering for AI Agents](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)
