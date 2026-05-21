# Pi Planning With Files

> **Work like Manus** - Use persistent markdown files as your "working memory on disk."

A [Pi Coding Agent](https://pi.dev) package that ships both:
- the planning skill (task_plan.md / findings.md / progress.md)
- a Pi extension that provides Claude-style lifecycle automation

## Installation

### Pi Install

```bash
pi install npm:pi-planning-with-files
```

### Manual Install

1. Navigate to your project root.
2. Copy `.pi/skills/planning-with-files/` into your Pi skills directory.
3. Reload Pi (`/reload`) if already running.

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
- `before_agent_start` - plan reminder/injection
- `tool_call` - pre-tool recitation equivalent
- `tool_result` - post-write reminder
- `agent_end` - incomplete-task auto-continue (limit 3)
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
- `/plan-goal <text|default|clear>`
- `/plan-loop [interval] [prompt]` (`stop` to cancel)

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
