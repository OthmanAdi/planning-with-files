# Pi Planning With Files

> **Work like Manus** - Use persistent markdown files as your "working memory on disk."

A [Pi Coding Agent](https://pi.dev) package that ships both:
- the planning skill (task_plan.md / findings.md / progress.md)
- a Pi extension that provides Claude-style lifecycle automation

## Installation

### Pi Install

```bash
pi install npm:@tomxprime/planning-with-files
```

### Manual Install

```bash
# From the planning-with-files repo root
pi install ./.pi/skills/planning-with-files
```

Or add to `.pi/settings.json`:
```json
{
  "packages": ["./path/to/planning-with-files/.pi/skills/planning-with-files"]
}
```

---

## Usage

Pi discovers the skill and extension from the installed package.

Start with:

```text
Use the planning-with-files skill to help me with this task.
```

Or:

```text
/skill:planning-with-files
```

---

## Hook Parity in Pi

The bundled extension maps Claude-style behavior onto Pi events:

- `session_start` - session catchup
- passive plan status before approval
- `before_agent_start` - plan reminder/injection after `/plan-execute`
- `tool_call` - pre-tool recitation equivalent after `/plan-execute`
- `tool_result` - post-write reminder after `/plan-execute`
- `agent_end` - incomplete-task auto-continue after `/plan-execute` (limit 3)
- `session_before_compact` - pre-compaction reminder

Attestation is supported. If `task_plan.md` differs from approved hash, plan injection is blocked with:

```text
[planning-with-files] [PLAN TAMPERED - injection blocked]
```

---

## Mode System

`planningWithFiles.mode` supports:

- `auto` (default): DeepSeek -> `cache-safe`, others -> `parity`
- `parity`: full dynamic hook-equivalent behavior
- `cache-safe`: fixed reminder strings for KV-cache stability
- `notify`: notification-only mode

Configure via env:

```bash
PWF_MODE=cache-safe pi
```

Or settings:

```json
{
  "planningWithFiles": {
    "mode": "auto"
  }
}
```

---

## Commands

- `/plan-status`
- `/plan-attest [--show|--clear]`
- `/plan-execute`
- `/plan-execute reset`
- `/plan-goal <text|default|clear>`
- `/plan-loop [interval] [prompt]` (`stop` to cancel)

Draft and review `task_plan.md` first. The extension stays passive until you
approve the active plan with `/plan-execute`; after that, plan injection,
pre-tool reminders, post-write reminders, and auto-continue are enabled for the
current session and plan.

---

## Session Recovery

If needed, run catchup manually:

```bash
python3 .pi/skills/planning-with-files/scripts/session-catchup.py .
```

## File Structure

The skill workflow still centers on three files in your project:

```text
your-project/
├── task_plan.md
├── findings.md
└── progress.md
```
