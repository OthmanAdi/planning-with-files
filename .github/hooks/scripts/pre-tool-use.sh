#!/bin/bash
# planning-with-files: Pre-tool-use hook for GitHub Copilot
# Reads the first 30 lines of task_plan.md to keep goals in context.
# Always allows tool execution — this hook never blocks tools.
# Always exits 0 — outputs JSON to stdout.

# Read stdin (required — Copilot pipes JSON to stdin)
INPUT=$(cat)

PLAN_FILE="task_plan.md"

if [ ! -f "$PLAN_FILE" ]; then
    echo '{}'
    exit 0
fi

CONTEXT=$(head -30 "$PLAN_FILE" 2>/dev/null || echo "")

if [ -z "$CONTEXT" ]; then
    echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'
    exit 0
fi

# Escape context for JSON
PYTHON=""
for _p in /usr/bin/python3 /usr/local/bin/python3 /opt/homebrew/bin/python3; do
    [ -x "$_p" ] && { PYTHON="$_p"; break; }
done
[ -z "$PYTHON" ] && PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
ESCAPED=$(echo "$CONTEXT" | $PYTHON -c "import sys,json; print(json.dumps(sys.stdin.read(), ensure_ascii=False))" 2>/dev/null || echo "\"\"")

echo "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"allow\",\"additionalContext\":$ESCAPED}}"
exit 0
