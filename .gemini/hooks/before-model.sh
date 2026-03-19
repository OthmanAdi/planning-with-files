#!/bin/bash
# planning-with-files: BeforeModel hook for Gemini CLI
# Injects plan awareness before every model call.
# This is UNIQUE to Gemini CLI — no other IDE has a BeforeModel event.
# Reads stdin JSON, outputs JSON to stdout.

INPUT=$(cat)

PLAN_FILE="task_plan.md"

if [ ! -f "$PLAN_FILE" ]; then
    echo '{}'
    exit 0
fi

# Only inject a lightweight reminder (not the full plan — that's BeforeTool's job)
CURRENT_PHASE=$(grep -m1 "^## Current Phase" "$PLAN_FILE" 2>/dev/null || grep -m1 "in_progress" "$PLAN_FILE" 2>/dev/null || echo "")

if [ -n "$CURRENT_PHASE" ]; then
    PYTHON=$(command -v python3 || command -v python)
    ESCAPED=$($PYTHON -c "import sys,json; print(json.dumps(sys.stdin.read(), ensure_ascii=False))" <<< "[planning-with-files] Current: $CURRENT_PHASE" 2>/dev/null || echo "\"\"")
    echo "{\"additionalContext\":$ESCAPED}"
else
    echo '{}'
fi

exit 0
