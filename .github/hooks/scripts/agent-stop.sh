#!/bin/bash
# planning-with-files: Agent stop hook for GitHub Copilot
# Checks if all phases in task_plan.md are complete.
# Injects continuation context if phases are incomplete.
# Always exits 0 — outputs JSON to stdout.

# Read stdin (required — Copilot pipes JSON to stdin)
INPUT=$(cat)

[ "${PLANNING_DISABLED:-}" = "1" ] && { echo '{}'; exit 0; }

PLAN_FILE="task_plan.md"

if [ ! -f "$PLAN_FILE" ]; then
    echo '{}'
    exit 0
fi

# Count total phases
TOTAL=$(grep -c "### Phase" "$PLAN_FILE" || true)

# Check for **Status:** format first
COMPLETE=$(grep -cF "**Status:** complete" "$PLAN_FILE" || true)
IN_PROGRESS=$(grep -cF "**Status:** in_progress" "$PLAN_FILE" || true)
PENDING=$(grep -cF "**Status:** pending" "$PLAN_FILE" || true)

# Fallback: check for [complete] inline format
if [ "$COMPLETE" -eq 0 ] && [ "$IN_PROGRESS" -eq 0 ] && [ "$PENDING" -eq 0 ]; then
    COMPLETE=$(grep -c "\[complete\]" "$PLAN_FILE" || true)
    IN_PROGRESS=$(grep -c "\[in_progress\]" "$PLAN_FILE" || true)
    PENDING=$(grep -c "\[pending\]" "$PLAN_FILE" || true)
fi

# Default to 0 if empty
: "${TOTAL:=0}"
: "${COMPLETE:=0}"
: "${IN_PROGRESS:=0}"
: "${PENDING:=0}"

# issue #191: no "### Phase" headings -> not phase-structured. Emit empty JSON
# instead of a false "0/0 phases done" additionalContext.
if [ "$TOTAL" -eq 0 ]; then
    echo '{}'
    exit 0
fi

if [ "$COMPLETE" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
    MSG="[planning-with-files] ALL PHASES COMPLETE ($COMPLETE/$TOTAL). If the user has additional work, add new phases to task_plan.md before starting."
    echo "{\"hookSpecificOutput\":{\"hookEventName\":\"AgentStop\",\"additionalContext\":\"$MSG\"}}"
    exit 0
fi

MSG="[planning-with-files] Task incomplete ($COMPLETE/$TOTAL phases done). Update progress.md, then read task_plan.md and continue working on the remaining phases."
echo "{\"hookSpecificOutput\":{\"hookEventName\":\"AgentStop\",\"additionalContext\":\"$MSG\"}}"
exit 0
