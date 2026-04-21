#!/bin/bash
# planning-with-files: Error hook for GitHub Copilot
# Logs errors to task_plan.md when the agent encounters an error.
# Always exits 0 — outputs JSON to stdout.

# Read stdin (required — Copilot pipes JSON to stdin)
INPUT=$(cat)

PLAN_FILE="task_plan.md"

if [ ! -f "$PLAN_FILE" ]; then
    echo '{}'
    exit 0
fi

# Extract error message from input JSON
PYTHON=""
for _p in /usr/bin/python3 /usr/local/bin/python3 /opt/homebrew/bin/python3; do
    [ -x "$_p" ] && { PYTHON="$_p"; break; }
done
[ -z "$PYTHON" ] && PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
ERROR_MSG=$($PYTHON -c "
import sys, json
try:
    data = json.load(sys.stdin)
    msg = data.get('error', {}).get('message', '') if isinstance(data.get('error'), dict) else str(data.get('error', ''))
    print(msg[:200])
except:
    print('')
" <<< "$INPUT" 2>/dev/null || echo "")

if [ -n "$ERROR_MSG" ]; then
    CONTEXT="[planning-with-files] Error detected: ${ERROR_MSG}. Log this error in task_plan.md under Errors Encountered with the attempt number and resolution."
    ESCAPED=$($PYTHON -c "import sys,json; print(json.dumps(sys.stdin.read(), ensure_ascii=False))" <<< "$CONTEXT" 2>/dev/null || echo "\"\"")
    echo "{\"hookSpecificOutput\":{\"hookEventName\":\"ErrorOccurred\",\"additionalContext\":$ESCAPED}}"
else
    echo '{}'
fi

exit 0
