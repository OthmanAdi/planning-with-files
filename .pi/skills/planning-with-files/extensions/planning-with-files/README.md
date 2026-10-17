# planning-with-files Pi Extension

This extension provides lifecycle automation for the `planning-with-files` skill in Pi.

## Events mapped

- `session_start` -> session catchup
- `before_agent_start` -> plan reminder/injection
- `tool_call` -> pre-tool recitation equivalent
- `tool_result` -> post-write reminder
- `agent_end` -> incomplete-task auto-continue (limit 3)
- `session_before_compact` -> compaction reminder and delivery-state invalidation
- `message_end` -> confirm injected planning context
- `session_compact` / `session_tree` -> invalidate stale delivery state

## Modes

- `auto` (default)
- `parity`
- `cache-safe`
- `notify`

### Parity pre-tool reminders

Turn-start injection is unchanged: an approved plan contributes its first 50 lines
and recent progress. Once Pi emits `message_end` for that injection, ordinary
tracked tool calls do not queue the same 30-line pre-tool plan view again, even
as the session leaf advances. A visible edit queues one refresh, including edits
made without a leaf transition. Progress-only edits and edits beyond the first
30 plan lines do not refresh the pre-tool view. Whole-plan attestation is still
checked before suppression; tamper warnings are not suppressed.

Suppression is scoped to the session, selected plan path, and effective mode.
Observed selection/mode changes, missing plans, user input, session start/shutdown,
failed or aborted runs, tree navigation, and compaction invalidate delivery state.
Resume/fork still require `/plan-execute` approval. Compaction invalidates even
when no plan is currently present; canceled compaction may cause an extra reminder.
The `cache-safe` and `notify` modes retain their existing reminder behavior.

To restore the prior per-leaf parity reminder behavior:

```bash
PWF_PRETOOL=always pi
```

This override does not bypass plan selection, execution approval, or attestation.

Delivery bookkeeping is a disposable in-process optimization, not shared planning
state: the authoritative plan remains Markdown on disk, and no persistent cache
or new session metadata is written. Losing bookkeeping permits extra injection.
A queued refresh is distinct from confirmed context and is deduplicated only
while the run remains active; unconfirmed queues are forgotten at `agent_end`.
Pi's `nextTurn` messages enter a fresh run, not the next tool-loop iteration.
Invalidation cannot retract messages already queued by Pi, so recovery can produce
an extra stale reminder before the fresh turn-start plan injection. `message_end`
confirms session-context insertion, not provider receipt or billing. The public
`sendMessage` API exposes synchronous send failures only; these leave no marker.
Context replacement by other extensions (including Observational Memory) without
Pi lifecycle events is not tracked by this patch.

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
