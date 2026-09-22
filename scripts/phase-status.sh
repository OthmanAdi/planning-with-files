#!/bin/sh
# planning-with-files: set the status of one phase in task_plan.md (v3).
#
# This is the ONLY sanctioned concurrent-safe writer of task_plan.md status
# lines. The orchestrator owns task_plan.md; workers NEVER edit it directly.
# All status edits go through this read-modify-write under the portable
# <plan-dir>/.pwf-locks/phase-status.lock namespace. Lock ownership is the
# atomic no-clobber creation of its .owner file; the directory's mkdir exit
# status is only provisional because some Windows-native implementations can
# report success to two simultaneous creators. The plan rewrite still uses an
# atomic temp-file + mv swap so a torn write can never leave a half-rewritten
# plan on disk (architecture C4).
#
# Note: editing task_plan.md changes its SHA, so the orchestrator must
# re-attest at phase boundaries (see attest-plan.sh).
#
# Plan-dir resolution (via resolve-plan-dir.sh):
#   1. $PLAN_ID env var -> ./.planning/$PLAN_ID/
#   2. ./.planning/.active_plan
#   3. Newest ./.planning/<dir>/ by mtime
#   4. Legacy: project root ./task_plan.md
#
# Usage:
#   sh scripts/phase-status.sh <phase-number> <pending|in_progress|complete>
#
# Exits 1 with a message if the phase does not exist or the status is invalid.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESOLVER="${SCRIPT_DIR}/resolve-plan-dir.sh"

usage() {
    printf "Usage: %s <phase-number> <pending|in_progress|complete>\n" "$0" >&2
}

resolve_plan_file() {
    plan_dir=""
    if [ -f "${RESOLVER}" ]; then
        plan_dir="$(sh "${RESOLVER}" 2>/dev/null)"
    fi
    if [ -n "${plan_dir}" ] && [ -f "${plan_dir}/task_plan.md" ]; then
        printf "%s\n" "${plan_dir}/task_plan.md"
        return 0
    fi
    # Explicit selectors are bindings, not hints (issue #237). This script
    # WRITES a phase status into the plan it picks, so a cwd fallback after a
    # rejected selector edits a different plan than the operator named.
    if [ -n "${PLAN_ID:-}" ] || [ -n "${PWF_PLAN_ROOT:-}" ]; then
        return 1
    fi
    if [ -f "./task_plan.md" ]; then
        printf "%s\n" "./task_plan.md"
        return 0
    fi
    return 1
}

PHASE_NUM="${1:-}"
NEW_STATUS="${2:-}"

if [ -z "${PHASE_NUM}" ] || [ -z "${NEW_STATUS}" ]; then
    usage
    exit 1
fi

# Validate phase number is a positive integer.
case "${PHASE_NUM}" in
    ''|*[!0-9]*)
        printf "[phase-status] phase number must be a positive integer, got '%s'.\n" "${PHASE_NUM}" >&2
        exit 1
        ;;
esac

# Validate status value against the allowlist.
case "${NEW_STATUS}" in
    pending|in_progress|complete) : ;;
    *)
        printf "[phase-status] invalid status '%s' (allowed: pending, in_progress, complete).\n" "${NEW_STATUS}" >&2
        exit 1
        ;;
esac

PLAN_FILE="$(resolve_plan_file)" || {
    if [ -n "${PLAN_ID:-}" ] || [ -n "${PWF_PLAN_ROOT:-}" ]; then
        printf "[phase-status] An explicit PLAN_ID or PWF_PLAN_ROOT did not resolve to a plan; nothing was written and no other plan was substituted.\n" >&2
    else
        printf "[phase-status] No task_plan.md found. Create a plan first.\n" >&2
    fi
    exit 1
}

PLAN_DIR="$(dirname "${PLAN_FILE}")"
LOCK_ROOT="${PLAN_DIR}/.pwf-locks"
LOCK_DIR="${LOCK_ROOT}/phase-status.lock"
LOCK_TOKEN=""
LOCK_ACQUIRED=0

release_lock() {
    if [ "${LOCK_ACQUIRED}" -ne 1 ] || [ -z "${LOCK_TOKEN}" ]; then
        return 0
    fi
    owner_file="${LOCK_DIR}/.owner"
    owner_value="$(cat "${owner_file}" 2>/dev/null || true)"
    if [ "${owner_value}" = "${LOCK_TOKEN}" ]; then
        rm -f "${owner_file}" 2>/dev/null || true
        rmdir "${LOCK_DIR}" 2>/dev/null || true
    fi
    LOCK_ACQUIRED=0
}

claim_lock_owner() {
    owner_file="${LOCK_DIR}/.owner"
    # POSIX noclobber makes this redirection an exclusive create. This is the
    # actual ownership decision: a Windows-native mkdir may report success
    # after another process won the directory-creation race (issue #281).
    if (
        umask 077
        set -C
        printf '%s\n' "${LOCK_TOKEN}" > "${owner_file}"
    ) 2>/dev/null; then
        LOCK_ACQUIRED=1
        return 0
    fi
    return 1
}

acquire_lock() {
    mkdir -p "${LOCK_ROOT}" 2>/dev/null || {
        printf "[phase-status] Cannot create lock root %s.\n" "${LOCK_ROOT}" >&2
        return 1
    }
    LOCK_TOKEN="phase-status-$$-$(date +%s 2>/dev/null || printf 0)"
    started_at="$(date +%s 2>/dev/null || printf 0)"
    attempts=0
    while :; do
        # Directory creation is intentionally idempotent. The exclusive owner
        # file below, not this external utility's exit status, grants the lock.
        mkdir "${LOCK_DIR}" 2>/dev/null || true
        if [ -d "${LOCK_DIR}" ] && claim_lock_owner; then
            return 0
        fi
        attempts=$((attempts + 1))
        now="$(date +%s 2>/dev/null || printf 0)"
        if { [ "${started_at}" -gt 0 ] 2>/dev/null \
                && [ $((now - started_at)) -ge 5 ]; } \
            || [ "${attempts}" -ge 50 ]; then
            printf "[phase-status] Timed out waiting for lock %s. No plan changes were made.\n" "${LOCK_DIR}" >&2
            return 75
        fi
        sleep 0.1
    done
}

trap 'release_lock' EXIT
trap 'release_lock; exit 1' HUP INT TERM

acquire_lock
lock_rc=$?
if [ "${lock_rc}" -ne 0 ]; then
    exit "${lock_rc}"
fi

# Confirm the phase heading exists while holding the same lock as the rewrite.
if ! grep -q "### Phase ${PHASE_NUM}\b" "${PLAN_FILE}" 2>/dev/null; then
    # Fall back to a looser match for headings like "### Phase 1:" where \b may
    # not be honored by a minimal grep.
    if ! grep -Eq "^### Phase ${PHASE_NUM}([^0-9]|$)" "${PLAN_FILE}" 2>/dev/null; then
        printf "[phase-status] Phase %s not found in %s.\n" "${PHASE_NUM}" "${PLAN_FILE}" >&2
        exit 1
    fi
fi

# Rewrite only the FIRST "**Status:**" line that follows the "### Phase N"
# heading. awk tracks whether we are inside the target phase block; once we
# rewrite its status line we stop matching so later phases are untouched.
rewrite() {
    src="$1"
    dst="$2"
    awk -v target="${PHASE_NUM}" -v newstatus="${NEW_STATUS}" '
        BEGIN { in_block = 0; done = 0 }
        {
            line = $0
            if (line ~ /^### Phase /) {
                # Extract the phase number right after "### Phase ".
                rest = line
                sub(/^### Phase /, "", rest)
                num = rest
                sub(/[^0-9].*$/, "", num)
                if (num == target && done == 0) {
                    in_block = 1
                } else {
                    in_block = 0
                }
            } else if (in_block == 1 && done == 0 && line ~ /\*\*Status:\*\*/) {
                # Preserve leading whitespace/bullet before "**Status:**".
                prefix = line
                sub(/\*\*Status:\*\*.*$/, "", prefix)
                line = prefix "**Status:** " newstatus
                in_block = 0
                done = 1
            }
            print line
        }
        END { if (done == 0) exit 3 }
    ' "${src}" > "${dst}"
}

TMP_FILE="${PLAN_FILE}.tmp.$$"

do_write() {
    if ! rewrite "${PLAN_FILE}" "${TMP_FILE}"; then
        rm -f "${TMP_FILE}" 2>/dev/null
        printf "[phase-status] No **Status:** line found for Phase %s.\n" "${PHASE_NUM}" >&2
        return 1
    fi
    mv -f "${TMP_FILE}" "${PLAN_FILE}"
    return 0
}

rc=0
do_write || rc=$?

if [ "${rc}" -ne 0 ]; then
    rm -f "${TMP_FILE}" 2>/dev/null
    exit 1
fi

printf "[phase-status] Phase %s -> %s in %s\n" "${PHASE_NUM}" "${NEW_STATUS}" "${PLAN_FILE}"
exit 0
