#!/bin/sh
# Set active plan pointer in ./.planning/.active_plan
# Usage: ./set-active-plan.sh <plan_id>

set -eu

if [ "${1:-}" = "" ]; then
    echo "Usage: $0 <plan_id>" >&2
    exit 1
fi

PLAN_ID="$1"
PLAN_ROOT="${PWD}/.planning"
PLAN_DIR="${PLAN_ROOT}/${PLAN_ID}"
ACTIVE_FILE="${PLAN_ROOT}/.active_plan"

if [ ! -d "${PLAN_DIR}" ]; then
    echo "Error: plan directory not found: ${PLAN_DIR}" >&2
    exit 1
fi

mkdir -p "${PLAN_ROOT}"
printf "%s\n" "${PLAN_ID}" > "${ACTIVE_FILE}"

echo "Active plan set to: ${PLAN_ID}"
echo "Active file: ${ACTIVE_FILE}"
