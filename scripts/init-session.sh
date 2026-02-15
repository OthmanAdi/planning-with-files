#!/bin/sh
# Initialize planning files for a new session in ./.planning/{plan_id}
# Usage: ./init-session.sh [project-name]

set -eu

PROJECT_NAME="${1:-project}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE_DIR="${SKILL_ROOT}/templates"
PLAN_ROOT="${PWD}/.planning"
ACTIVE_PLAN_FILE="${PLAN_ROOT}/.active_plan"

generate_uuid() {
    if command -v uuidgen >/dev/null 2>&1; then
        uuidgen | tr '[:upper:]' '[:lower:]'
        return
    fi

    if command -v python3 >/dev/null 2>&1; then
        python3 - <<'PY'
import uuid
print(str(uuid.uuid4()))
PY
        return
    fi

    if command -v python >/dev/null 2>&1; then
        python - <<'PY'
import uuid
print(str(uuid.uuid4()))
PY
        return
    fi

    echo "Error: cannot generate UUID (missing uuidgen/python)." >&2
    exit 1
}

if [ ! -f "${TEMPLATE_DIR}/task_plan.md" ] || [ ! -f "${TEMPLATE_DIR}/findings.md" ] || [ ! -f "${TEMPLATE_DIR}/progress.md" ]; then
    echo "Error: missing templates under ${TEMPLATE_DIR}" >&2
    exit 1
fi

PLAN_ID="$(generate_uuid)"
PLAN_DIR="${PLAN_ROOT}/${PLAN_ID}"

mkdir -p "${PLAN_DIR}"

cp "${TEMPLATE_DIR}/task_plan.md" "${PLAN_DIR}/task_plan.md"
cp "${TEMPLATE_DIR}/findings.md" "${PLAN_DIR}/findings.md"
cp "${TEMPLATE_DIR}/progress.md" "${PLAN_DIR}/progress.md"
printf "%s\n" "${PLAN_ID}" > "${ACTIVE_PLAN_FILE}"

echo "Initialized planning files for: ${PROJECT_NAME}"
echo "PLAN_ID=${PLAN_ID}"
echo "PLAN_DIR=${PLAN_DIR}"
echo "Files:"
echo "  - ${PLAN_DIR}/task_plan.md"
echo "  - ${PLAN_DIR}/findings.md"
echo "  - ${PLAN_DIR}/progress.md"
echo ""
echo "Active plan updated: ${ACTIVE_PLAN_FILE}"
echo "For parallel sessions, pin this terminal to the plan:"
echo "  export PLAN_ID=${PLAN_ID}"
