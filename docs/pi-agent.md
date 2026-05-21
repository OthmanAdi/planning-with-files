# Pi Agent Setup

How to use planning-with-files with [Pi Coding Agent](https://pi.dev).

---

## Installation

### Recommended: Install from npm

```bash
pi install npm:pi-planning-with-files
```

This package now installs **both**:
- Skill: `planning-with-files` (3-file planning workflow)
- Extension: `planning-with-files` hook parity runtime

### Manual Install (repo copy)

```bash
# Clone repo
git clone https://github.com/OthmanAdi/planning-with-files.git
cd planning-with-files

# Copy skill package into your Pi skills directory
mkdir -p ~/.pi/agent/skills/planning-with-files
cp -r .pi/skills/planning-with-files/* ~/.pi/agent/skills/planning-with-files/
```

---

## What Pi Now Supports

Pi integration provides Claude-style lifecycle behavior via extension events:

- Session catchup on `session_start`
- Plan context reminder/injection on `before_agent_start`
- Pre-tool plan recitation equivalent on `tool_call`
- Post-write reminders on `tool_result`
- Auto-continue guard on `agent_end` (limit: 3)
- Pre-compaction reminder on `session_before_compact`
- Plan attestation guard (`[PLAN TAMPERED — injection blocked]`)

---

## Mode System (DeepSeek-aware)

The extension supports four modes:

- `auto` (default):
  - DeepSeek model -> `cache-safe`
  - Other models -> `parity`
- `parity`: maximum Claude-equivalent behavior (dynamic plan injection)
- `cache-safe`: stable fixed reminder for better DeepSeek KV-cache hit rate
- `notify`: UI notifications only, no conversation injection

### Configure via environment variable

```bash
PWF_MODE=auto pi
PWF_MODE=parity pi
PWF_MODE=cache-safe pi
PWF_MODE=notify pi
```

### Configure via settings

Project-level (`.pi/settings.json`) overrides global (`~/.pi/agent/settings.json`):

```json
{
  "planningWithFiles": {
    "mode": "auto"
  }
}
```

---

## Commands

After installation, these extension commands are available:

- `/plan-status` — show current plan counts and paths
- `/plan-attest [--show|--clear]` — manage plan SHA-256 attestation
- `/plan-goal <text|default|clear>` — set/clear continuation goal text
- `/plan-loop [10m] [prompt...]` — periodic planning tick; use `stop` to cancel

---

## Usage

Start with:

```bash
/skill:planning-with-files
```

Then ask Pi to create/update:
- `task_plan.md`
- `findings.md`
- `progress.md`

For long tasks, keep `task_plan.md` as the source of truth and let hooks/extension events enforce the loop.

---

## Troubleshooting

1. Confirm package installed:
   ```bash
   pi list
   ```
2. Reload runtime:
   ```bash
   /reload
   ```
3. Check skill and extension paths:
   - skill: `.pi/skills/planning-with-files/`
   - extension: `extensions/planning-with-files/index.ts`
4. If plan injection is blocked, run:
   ```bash
   /plan-attest --show
   ```
   Then re-attest intentionally changed plans:
   ```bash
   /plan-attest
   ```
