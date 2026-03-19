#!/bin/bash
# planning-with-files: BeforeTool hook for Gemini CLI
# Reads the first 30 lines of task_plan.md before tool use.
# Receives JSON on stdin, must output ONLY JSON to stdout.

INPUT=$(cat)

PLAN_FILE="task_plan.md"

if [ ! -f "$PLAN_FILE" ]; then
    echo '{}'
    exit 0
fi

CONTEXT=$(head -30 "$PLAN_FILE" 2>/dev/null || echo "")

if [ -z "$CONTEXT" ]; then
    echo '{}'
    exit 0
fi

PYTHON=$(command -v python3 || command -v python)
if [ -n "$PYTHON" ]; then
    ESCAPED=$($PYTHON -c "import sys,json; print(json.dumps(sys.stdin.read(), ensure_ascii=False))" <<< "$CONTEXT" 2>/dev/null)
    if [ -n "$ESCAPED" ] && [ "$ESCAPED" != "\"\"" ]; then
        echo "{\"systemMessage\":$ESCAPED}"
        exit 0
    fi
fi

echo '{}'
exit 0
