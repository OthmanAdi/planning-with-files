#!/bin/sh
# planning-with-files: set, display, or list the active plan pointer.
#
# Usage:
#   set-active-plan.sh <plan_id>   — pin .planning/.active_plan to plan_id
#   set-active-plan.sh             — print the current active plan (if any)
#   set-active-plan.sh --list      — list available named plans and phase counts
#
# The active plan is stored in .planning/.active_plan and is read by
# resolve-plan-dir.sh when no $PLAN_ID env var is set.

set -e

PLAN_ROOT="${PWD}/.planning"
ACTIVE_FILE="${PLAN_ROOT}/.active_plan"

current_active() {
    if [ -f "${ACTIVE_FILE}" ]; then
        tr -d '\r\n' < "${ACTIVE_FILE}"
    fi
}

phase_status() {
    _plan_file="$1"
    _total=$(grep -c "### Phase" "$_plan_file" || true)
    _complete_primary=$(grep -cF "**Status:** complete" "$_plan_file" || true)
    _in_progress_primary=$(grep -cF "**Status:** in_progress" "$_plan_file" || true)
    _pending_primary=$(grep -cF "**Status:** pending" "$_plan_file" || true)
    _complete_inline=$(grep -c "\[complete\]" "$_plan_file" || true)
    _in_progress_inline=$(grep -c "\[in_progress\]" "$_plan_file" || true)
    _pending_inline=$(grep -c "\[pending\]" "$_plan_file" || true)

    if [ "${_complete_inline:-0}" -gt "${_complete_primary:-0}" ]; then _complete="$_complete_inline"; else _complete="$_complete_primary"; fi
    if [ "${_in_progress_inline:-0}" -gt "${_in_progress_primary:-0}" ]; then _in_progress="$_in_progress_inline"; else _in_progress="$_in_progress_primary"; fi
    if [ "${_pending_inline:-0}" -gt "${_pending_primary:-0}" ]; then _pending="$_pending_inline"; else _pending="$_pending_primary"; fi

    printf "%s/%s complete, %s in_progress, %s pending" "${_complete:-0}" "${_total:-0}" "${_in_progress:-0}" "${_pending:-0}"
}

list_plans() {
    if [ ! -d "${PLAN_ROOT}" ]; then
        echo "No planning directory found."
        return 0
    fi

    _active="$(current_active)"
    _found=0
    echo "Available plans:"
    for _dir in "${PLAN_ROOT}"/*; do
        [ -d "$_dir" ] || continue
        _id="${_dir##*/}"
        case "$_id" in
            .* ) continue ;;
        esac
        [ -f "$_dir/task_plan.md" ] || continue
        _found=1
        _marker=""
        if [ "$_id" = "$_active" ]; then
            _marker=" [active]"
        fi
        printf "%s\n" "- ${_id}${_marker} — $(phase_status "$_dir/task_plan.md")"
    done

    if [ "$_found" -eq 0 ]; then
        echo "No named plans found."
    fi
}

case "${1:-}" in
    --list|-l)
        list_plans
        exit 0
        ;;
    --help|-h)
        echo "Usage: set-active-plan.sh [--list|PLAN_ID]"
        exit 0
        ;;
esac

# No args → show current active plan
if [ "${1:-}" = "" ]; then
    plan_id="$(current_active)"
    if [ -n "${plan_id}" ] && [ -d "${PLAN_ROOT}/${plan_id}" ]; then
        echo "Active plan: ${plan_id}"
        echo "Path: ${PLAN_ROOT}/${plan_id}"
    elif [ -n "${plan_id}" ]; then
        echo "Active plan pointer: ${plan_id} (directory not found — stale pointer)"
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
