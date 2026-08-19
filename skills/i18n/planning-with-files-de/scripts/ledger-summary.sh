#!/bin/sh
# planning-with-files: emit a fixed-shape, cache-stable run-ledger summary (v3).
#
# This replaces raw `tail -20 progress.md` injection in autonomous mode. The
# output is synthesized from the machine ledger and task_plan.md status counts
# only: NO free text from disk reaches the model context, and there are NO
# timestamps, so the injected block is KV-cache stable by construction
# (architecture C3 injection rule).
#
# Plan-dir resolution:
#   0. Explicit plan-dir argument (issue #212, see below)
#   1. $PLAN_ID env var -> ./.planning/$PLAN_ID/   (via resolve-plan-dir.sh)
#   2. ./.planning/.active_plan                    (via resolve-plan-dir.sh)
#   3. Newest ./.planning/<dir>/ by mtime          (via resolve-plan-dir.sh)
#   4. Legacy: project root
#
# Usage:
#   sh scripts/ledger-summary.sh [plan-dir]
#
# The optional argument is the caller's already-resolved plan directory and
# wins over self-resolution: inject-plan.sh passes the dir it resolved,
# because a cwd-based re-resolution here would pair a PWF_PLAN_ROOT-pinned
# plan's body with the PARENT project's phase counts and agent events — a
# false termination signal for an autonomous loop. No argument keeps the
# self-resolution above unchanged.
#
# Output block (stable shape):
#   === RUN LEDGER ===
#   entries: <N>
#   phases: <complete>/<total> complete
#   in_progress: <phase heading or none>
#   agent <name>: <last event type>
#   ...
#   ==================
#
# When no plan directory is determinable at all (argument names a missing dir,
# or no argument AND resolve-plan-dir.sh is not next to this script), the block
# is replaced by a clearly marked unavailable state instead of a confident
# "phases: 0/0 complete" — see emit_unavailable below.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESOLVER="${SCRIPT_DIR}/resolve-plan-dir.sh"
ARG_DIR="${1:-}"

# Loud degradation: when the counts below are NOT computable — the caller
# named a plan dir that is gone, or no dir was passed and the resolver is
# missing next to this script — emit a clearly marked unavailable block
# instead of a confident "phases: 0/0 complete" + "in_progress: none", which
# an autonomous loop would read as its termination signal. Fixed strings
# only, so the block stays byte-stable (no timestamps, no free text from
# disk). Exit 0: this feeds hook output and must never error the agent loop.
emit_unavailable() {
    printf '=== RUN LEDGER ===\n'
    printf 'ledger: unavailable (%s)\n' "$1"
    printf '==================\n'
    exit 0
}

PLAN_DIR=""
if [ -n "${ARG_DIR}" ]; then
    # The caller already resolved the plan dir; never second-guess it with a
    # cwd-based re-resolution (that is exactly the parent/child mismatch this
    # argument exists to prevent). If the named dir is gone, say so.
    [ -d "${ARG_DIR}" ] || emit_unavailable "plan dir argument does not exist"
    PLAN_DIR="${ARG_DIR}"
elif [ -f "${RESOLVER}" ]; then
    PLAN_DIR="$(sh "${RESOLVER}" 2>/dev/null)"
    if [ -z "${PLAN_DIR}" ] || [ ! -d "${PLAN_DIR}" ]; then
        PLAN_DIR="."
    fi
else
    emit_unavailable "resolve-plan-dir.sh missing and no plan dir argument"
fi

if [ "${PLAN_DIR}" = "." ]; then
    PLAN_FILE="./task_plan.md"
else
    PLAN_FILE="${PLAN_DIR}/task_plan.md"
fi

# --- Phase counts: identical grep patterns to check-complete.sh ---
TOTAL=0
COMPLETE=0
IN_PROGRESS=0
IN_PROGRESS_HEADING="none"
if [ -f "${PLAN_FILE}" ]; then
    TOTAL=$(grep -c "### Phase" "${PLAN_FILE}" 2>/dev/null || true)
    COMPLETE=$(grep -cF "**Status:** complete" "${PLAN_FILE}" 2>/dev/null || true)
    IN_PROGRESS=$(grep -cF "**Status:** in_progress" "${PLAN_FILE}" 2>/dev/null || true)

    # Fallback to inline [status] format when **Status:** is absent.
    if [ "${COMPLETE}" -eq 0 ] && [ "${IN_PROGRESS}" -eq 0 ]; then
        c2=$(grep -c "\[complete\]" "${PLAN_FILE}" 2>/dev/null || true)
        i2=$(grep -c "\[in_progress\]" "${PLAN_FILE}" 2>/dev/null || true)
        : "${c2:=0}"
        : "${i2:=0}"
        if [ "${c2}" -gt 0 ] || [ "${i2}" -gt 0 ]; then
            COMPLETE="${c2}"
            IN_PROGRESS="${i2}"
        fi
    fi

    # Heading of the FIRST phase whose status block is in_progress. We walk
    # phase headings and look ahead for the status line so the summary names
    # the active phase without leaking any plan body text beyond the heading.
    heading=""
    state=""
    # shellcheck disable=SC2162
    while IFS= read -r line; do
        case "${line}" in
            "### Phase"*)
                heading="${line}"
                ;;
            *"**Status:** in_progress"*)
                if [ -n "${heading}" ]; then
                    IN_PROGRESS_HEADING="${heading}"
                    break
                fi
                ;;
            *"[in_progress]"*)
                if [ -n "${heading}" ] && [ "${IN_PROGRESS_HEADING}" = "none" ]; then
                    IN_PROGRESS_HEADING="${heading}"
                fi
                ;;
        esac
    done < "${PLAN_FILE}"
fi
: "${TOTAL:=0}"
: "${COMPLETE:=0}"
: "${IN_PROGRESS:=0}"

# --- Ledger stats: total entries + last event type per agent ---
TOTAL_ENTRIES=0
for f in "${PLAN_DIR}"/ledger-*.jsonl; do
    [ -f "${f}" ] || continue
    n=$(grep -c '"tick"' "${f}" 2>/dev/null || true)
    : "${n:=0}"
    TOTAL_ENTRIES=$((TOTAL_ENTRIES + n))
done

printf '=== RUN LEDGER ===\n'
printf 'entries: %s\n' "${TOTAL_ENTRIES}"
printf 'phases: %s/%s complete\n' "${COMPLETE}" "${TOTAL}"
printf 'in_progress: %s\n' "${IN_PROGRESS_HEADING}"

# Per-agent last event type. Agent name comes from the filename
# (ledger-<agent>.jsonl); the last event is parsed from the final line.
for f in "${PLAN_DIR}"/ledger-*.jsonl; do
    [ -f "${f}" ] || continue
    base="$(basename "${f}")"
    agent="${base#ledger-}"
    agent="${agent%.jsonl}"
    last_line="$(tail -n 1 "${f}" 2>/dev/null)"
    last_event="$(printf '%s' "${last_line}" | sed -n 's/.*"event"[[:space:]]*:[[:space:]]*"\([A-Za-z_]*\)".*/\1/p')"
    [ -z "${last_event}" ] && last_event="none"
    printf 'agent %s: %s\n' "${agent}" "${last_event}"
done

printf '==================\n'
exit 0
