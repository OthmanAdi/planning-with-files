#!/bin/bash
# planning-with-files: SessionEnd hook for Gemini CLI
# Checks all phases are complete before session ends.
# Receives JSON on stdin, must output ONLY JSON to stdout.

INPUT=$(cat)

PLAN_FILE="task_plan.md"
SCRIPT_DIR="${GEMINI_PROJECT_DIR:-.}/.gemini/skills/planning-with-files/scripts"

if [ ! -f "$PLAN_FILE" ]; then
    echo '{}'
    exit 0
fi

# Run check-complete script
if [ -f "$SCRIPT_DIR/check-complete.sh" ]; then
    RESULT=$(sh "$SCRIPT_DIR/check-complete.sh" 2>/dev/null || true)
    if [ -n "$RESULT" ]; then
        PYTHON=$(command -v python3 || command -v python)
        ESCAPED=$($PYTHON -c "import sys,json; print(json.dumps(sys.stdin.read(), ensure_ascii=False))" <<< "$RESULT" 2>/dev/null || echo "\"\"")
        echo "{\"systemMessage\":$ESCAPED}"
        exit 0
    fi
fi

echo '{}'
exit 0
