# planning-with-files Pi Extension

This extension provides lifecycle automation for the `planning-with-files` skill in Pi.

## Events mapped

- `session_start` -> session catchup
- `before_agent_start` -> plan reminder/injection
- `tool_call` -> pre-tool recitation equivalent
- `tool_result` -> post-write reminder
- `agent_end` -> incomplete-task auto-continue (limit 3)
- `session_before_compact` -> compaction reminder

## Modes

- `auto` (default)
- `parity`
- `cache-safe`
- `notify`

Configure with:

```bash
PWF_MODE=auto pi
```

or in settings (`.pi/settings.json` / `~/.pi/agent/settings.json`):

```json
{
  "planningWithFiles": {
    "mode": "auto"
  }
}
```
