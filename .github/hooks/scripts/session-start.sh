#!/bin/bash
# planning-with-files: Session start hook for GitHub Copilot
# When task_plan.md exists: runs session-catchup or reads plan header.
# When task_plan.md doesn't exist: injects SKILL.md so Copilot knows the planning workflow.
# Always exits 0 — outputs JSON to stdout.

# Read stdin (required — Copilot pipes JSON to stdin)
INPUT=$(cat)

PLAN_FILE="task_plan.md"
SKILL_DIR=".github/skills/planning-with-files"
PYTHON=$(command -v python3 || command -v python)

if [ -f "$PLAN_FILE" ]; then
    # Plan exists — try session catchup, fall back to reading plan header
    CATCHUP=""
    if [ -n "$PYTHON" ] && [ -f "$SKILL_DIR/scripts/session-catchup.py" ]; then
        CATCHUP=$($PYTHON "$SKILL_DIR/scripts/session-catchup.py" "$(pwd)" 2>/dev/null | head -100)
    fi

    if [ -n "$CATCHUP" ]; then
        CONTEXT="[planning-with-files] Previous session context (truncated to 100 lines):
$CATCHUP"
    else
        CONTEXT=$(head -5 "$PLAN_FILE" 2>/dev/null || echo "")
    fi
else
    # No plan yet — inject SKILL.md so Copilot knows the planning workflow and templates
    if [ -f "$SKILL_DIR/SKILL.md" ]; then
        CONTEXT=$(cat "$SKILL_DIR/SKILL.md" 2>/dev/null || echo "")
    fi
fi

if [ -z "$CONTEXT" ]; then
    echo '{}'
    exit 0
fi

# Escape context for JSON
ESCAPED=$(echo "$CONTEXT" | $PYTHON -c "import sys,json; print(json.dumps(sys.stdin.read(), ensure_ascii=False))" 2>/dev/null || echo "\"\"")

echo "{\"hookSpecificOutput\":{\"hookEventName\":\"SessionStart\",\"additionalContext\":$ESCAPED}}"
exit 0
