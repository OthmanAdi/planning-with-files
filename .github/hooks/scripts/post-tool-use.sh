#!/bin/bash
# planning-with-files: Post-tool-use hook for GitHub Copilot
# Reminds the agent to update task_plan.md after tool use.
# Always exits 0 — outputs JSON to stdout.

# Read stdin (required — Copilot pipes JSON to stdin)
INPUT=$(cat)

[ "${PLANNING_DISABLED:-}" = "1" ] && { echo '{}'; exit 0; }

echo '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"[planning-with-files] Update progress.md with what you just did. If a phase is now complete, update task_plan.md status."}}'
exit 0
