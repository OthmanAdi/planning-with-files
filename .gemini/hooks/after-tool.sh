#!/bin/bash
# planning-with-files: AfterTool hook for Gemini CLI
# Reminds the agent to update progress after file writes.
# Reads stdin JSON, outputs JSON to stdout.

INPUT=$(cat)

# issue #329: per-invocation opt-out (PLANNING_DISABLED=1)
[ "${PLANNING_DISABLED:-}" = "1" ] && { echo '{}'; exit 0; }

PLAN_FILE="task_plan.md"

if [ ! -f "$PLAN_FILE" ]; then
    echo '{}'
    exit 0
fi

echo '{"hookSpecificOutput":{"additionalContext":"[planning-with-files] Update progress.md with what you just did. If a phase is now complete, update task_plan.md status."}}'
exit 0
