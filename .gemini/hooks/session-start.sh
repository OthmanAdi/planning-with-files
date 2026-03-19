#!/bin/bash
# planning-with-files: SessionStart hook for Gemini CLI
# Checks for previous session and recovers context.
# Receives JSON on stdin, must output ONLY JSON to stdout.
# Stderr is for logging only.

INPUT=$(cat)

PLAN_FILE="task_plan.md"
SCRIPT_DIR="${GEMINI_PROJECT_DIR:-.}/.gemini/skills/planning-with-files/scripts"

# If no plan file, nothing to recover
if [ ! -f "$PLAN_FILE" ]; then
    echo '{}'
    exit 0
fi

# Try session catchup
PYTHON=$(command -v python3 || command -v python)
CATCHUP=""
if [ -n "$PYTHON" ] && [ -f "$SCRIPT_DIR/session-catchup.py" ]; then
    CATCHUP=$($PYTHON "$SCRIPT_DIR/session-catchup.py" "$(pwd)" 2>/dev/null || true)
fi

if [ -n "$CATCHUP" ]; then
    ESCAPED=$($PYTHON -c "import sys,json; print(json.dumps(sys.stdin.read(), ensure_ascii=False))" <<< "$CATCHUP" 2>/dev/null || echo "\"[planning-with-files] Session recovery data available. Read task_plan.md, progress.md, and findings.md.\"")
    echo "{\"hookSpecificOutput\":{\"additionalContext\":$ESCAPED}}"
else
    echo '{"hookSpecificOutput":{"additionalContext":"[planning-with-files] Active plan detected. Read task_plan.md, progress.md, and findings.md before proceeding."}}'
fi

exit 0
