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
        # Explicit selectors are bindings, not hints (issue #237). A rejected
        # PLAN_ID or PWF_PLAN_ROOT must not fall back to the cwd: this summary
        # is injected into autonomous turns, so reporting the ROOT plan's
        # phase counts under a mistyped pin feeds the loop another plan's
        # termination signal. Degrade loudly, the same way a missing resolver
        # already does.
        if [ -n "${PLAN_ID:-}" ] || [ -n "${PWF_PLAN_ROOT:-}" ]; then
            emit_unavailable "explicit PLAN_ID or PWF_PLAN_ROOT did not resolve"
        fi
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

TOTAL=0
COMPLETE=0
IN_PROGRESS=0
IN_PROGRESS_HEADING="none"
if [ -f "$PLAN_FILE" ]; then
# Count native statuses inside real phases, excluding fenced examples (#377).
PLAN_COUNTS=$(awk '
        function finish_phase() {
            if (in_phase) {
                if (status_count != 1) invalid = 1
                else {
                    counts[phase_status]++
                    if (phase_status == "in_progress" && active_heading == "") active_heading = heading
                }
            }
            in_phase = 0; status_count = 0; phase_status = ""
        }
        function fenced(line,    trimmed, marker, run) {
            trimmed = line; sub(/^ ? ? ?/, "", trimmed)
            if (line ~ /^ ? ? ?```/ || line ~ /^ ? ? ?~~~/) {
                marker = substr(trimmed, 1, 1); run = 0
                while (substr(trimmed, run + 1, 1) == marker) run++
                if (fence == "") { fence = marker; fence_length = run }
                else if (marker == fence && run >= fence_length && substr(trimmed, run + 1) ~ /^[ \t]*$/) fence = ""
                return 1
            }
            return fence != ""
        }
        function read_status(line,    token, boundary) {
            while (match(line, /\*\*Status:\*\*[ \t]+(pending|in_progress|complete)([^[:alnum:]_]|$)|\[(pending|in_progress|complete)\]/)) {
                token = substr(line, RSTART, RLENGTH)
                boundary = substr(token, 1, 2) == "**" && token ~ /[^[:alnum:]_]$/
                sub(/^\*\*Status:\*\*[ \t]+|^\[/, "", token)
                sub(/[^a-z_].*$/, "", token)
                status_count++; phase_status = token
                line = substr(line, RSTART + RLENGTH - boundary)
            }
        }
        { sub(/\r$/, "") }
        fenced($0) { next }
        /^### Phase([ \t]|$)/ {
            finish_phase(); total++; in_phase = 1; heading = $0
        }
        !/^### Phase([ \t]|$)/ && /^#{1,3}([ \t]|$)/ { finish_phase() }
        in_phase { read_status($0) }
        END {
            finish_phase()
            printf "%d %d %d %d %d\n%s\n", total, counts["complete"], counts["in_progress"], counts["pending"], invalid, active_heading
        }
    ' "$PLAN_FILE")
read -r TOTAL COMPLETE IN_PROGRESS PENDING INVALID <<EOF
$PLAN_COUNTS
EOF
    _active_heading=$(printf '%s\n' "$PLAN_COUNTS" | sed -n '2p')
    [ -z "$_active_heading" ] || IN_PROGRESS_HEADING="$_active_heading"
fi

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
