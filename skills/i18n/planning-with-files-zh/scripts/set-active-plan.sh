#!/bin/sh
# planning-with-files: set or display the active plan pointer.
#
# Usage:
#   set-active-plan.sh <plan_id>   — pin .planning/.active_plan to plan_id
#   set-active-plan.sh             — print the current active plan (if any)
#
# The active plan is stored in .planning/.active_plan and is read by
# resolve-plan-dir.sh when no $PLAN_ID env var is set.

set -e

PLAN_ROOT="${PWD}/.planning"
ACTIVE_FILE="${PLAN_ROOT}/.active_plan"

# No args → show current active plan
if [ "${1:-}" = "" ]; then
    if [ -f "${ACTIVE_FILE}" ]; then
        plan_id="$(tr -d '\r\n' < "${ACTIVE_FILE}")"
        if [ -n "${plan_id}" ] && [ -d "${PLAN_ROOT}/${plan_id}" ]; then
            echo "Active plan: ${plan_id}"
            echo "Path: ${PLAN_ROOT}/${plan_id}"
        elif [ -n "${plan_id}" ]; then
            echo "Active plan pointer: ${plan_id} (directory not found — stale pointer)"
        else
            echo "No active plan set."
        fi
    else
        echo "No active plan set."
    fi
    exit 0
fi

PLAN_ID="$1"
PLAN_DIR="${PLAN_ROOT}/${PLAN_ID}"

if [ ! -d "${PLAN_DIR}" ]; then
    echo "Error: plan directory not found: ${PLAN_DIR}" >&2
    echo "Run: init-session.sh \"${PLAN_ID}\" to create it, or check .planning/ for available plans." >&2
    exit 1
fi

mkdir -p "${PLAN_ROOT}"
printf "%s\n" "${PLAN_ID}" > "${ACTIVE_FILE}"

echo "Active plan set to: ${PLAN_ID}"
echo "Path: ${PLAN_DIR}"
echo ""
echo "To pin this terminal session only:"
echo "  export PLAN_ID=${PLAN_ID}"
