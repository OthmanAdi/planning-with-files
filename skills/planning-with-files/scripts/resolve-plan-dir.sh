#!/bin/sh
# Resolve active plan directory under ./.planning/{plan_id}
# Prints resolved directory path to stdout, or nothing if unavailable.

set -eu

PLAN_ROOT="${1:-${PWD}/.planning}"
ACTIVE_FILE="${PLAN_ROOT}/.active_plan"

resolve_from_env() {
    plan_id="${PLAN_ID:-}"
    if [ -z "${plan_id}" ]; then
        return 1
    fi

    candidate="${PLAN_ROOT}/${plan_id}"
    if [ -d "${candidate}" ]; then
        printf "%s\n" "${candidate}"
        return 0
    fi
    return 1
}

resolve_from_active_file() {
    if [ ! -f "${ACTIVE_FILE}" ]; then
        return 1
    fi

    plan_id="$(tr -d '\r\n' < "${ACTIVE_FILE}")"
    if [ -z "${plan_id}" ]; then
        return 1
    fi

    candidate="${PLAN_ROOT}/${plan_id}"
    if [ -d "${candidate}" ]; then
        printf "%s\n" "${candidate}"
        return 0
    fi
    return 1
}

resolve_latest_dir() {
    if [ ! -d "${PLAN_ROOT}" ]; then
        return 1
    fi

    latest="$(ls -1dt "${PLAN_ROOT}"/*/ 2>/dev/null | head -n1 || true)"
    latest="${latest%/}"
    if [ -n "${latest}" ] && [ -d "${latest}" ]; then
        printf "%s\n" "${latest}"
        return 0
    fi
    return 1
}

if resolve_from_env; then
    exit 0
fi

if resolve_from_active_file; then
    exit 0
fi

if resolve_latest_dir; then
    exit 0
fi

exit 0
