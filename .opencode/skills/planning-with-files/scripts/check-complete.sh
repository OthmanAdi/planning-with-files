#!/usr/bin/env bash
# Check if all phases in task_plan.md are complete
# Default invocation: advisory echo, always exits 0 (Stop hook status report).
# With --validate: read-only creation check; exits 1 for an untrackable plan.
# With --gate: deliberate completion gate, opt-in per plan via <plan-dir>/.mode.
# Used by Stop hook to report task completion status.
#
# Plan-file resolution (v2.40+):
#   1. $1 (explicit path) — first non-flag positional argument
#   2. resolve-plan-dir.sh: $PLAN_ID env → .planning/.active_plan → newest mtime
#   3. Legacy ./task_plan.md
#
# This restores slug-mode parity: the Stop hook and any caller invoking with
# zero args now respects the active plan dir instead of silently defaulting to
# the legacy root path.
#
# Gate mode (v3, --gate flag):
#   The gate is OFF unless ALL of these hold (design "Gate decision table"):
#     1. <plan-dir>/.mode exists and contains "gate" (explicit opt-in)
#     2. an in_progress phase exists (not merely complete<total)
#     3. the Stop hook input JSON on stdin does not set stop_hook_active=true
#     4. the block counter (<plan-dir>/.stop_blocks) is below cap (PWF_GATE_CAP, default 20)
#     5. the ledger advanced since the last block (stall → allow stop)
#   When all hold, it emits a single-line block-decision JSON on stdout and
#   exits 0. Otherwise it reports incomplete plans and exits 0; completed
#   plans stay silent in --gate mode, including legacy plans without .mode.
#   Without --gate, the explicit advisory report is unchanged.
#
# Stdin handling: the Claude Code Stop hook pipes a JSON payload on stdin. To
# avoid hanging when nothing is piped, stdin is read ONLY when fd 0 is not a
# TTY ([ -t 0 ]). Hook-piped input is EOF-terminated, so the read returns; an
# interactive terminal (TTY) is skipped entirely. No data on stdin is treated
# as stop_hook_active=false.

GATE=0
VALIDATE=0
PLAN_FILE=""
for _arg in "$@"; do
    case "$_arg" in
        --gate) GATE=1 ;;
        --validate) VALIDATE=1 ;;
        *)
            if [ -z "$PLAN_FILE" ]; then
                PLAN_FILE="$_arg"
            fi
            ;;
    esac
done

# Hook opt-out does not turn an explicitly requested format check into success.
[ "${PLANNING_DISABLED:-}" = "1" ] && [ "$VALIDATE" -eq 0 ] && exit 0

PLAN_DIR=""
if [ -n "${PLAN_FILE}" ]; then
    PLAN_DIR="$(dirname "${PLAN_FILE}")"
else
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd 2>/dev/null)" || SCRIPT_DIR="."
    RESOLVER="${SCRIPT_DIR}/resolve-plan-dir.sh"
    RESOLVED_DIR=""
    if [ -f "${RESOLVER}" ]; then
        RESOLVED_DIR="$(sh "${RESOLVER}" 2>/dev/null)"
        if [ -z "$RESOLVED_DIR" ] && [ "$(sh "${RESOLVER}" --check-ambiguity 2>/dev/null)" = "PWF_PLAN_AMBIGUOUS_V1" ]; then
            [ "$VALIDATE" -eq 1 ] && { echo "[planning-with-files] Plan format invalid: select one plan before validation." >&2; exit 1; }
            exit 0
        fi
    fi
    if [ -n "${RESOLVED_DIR}" ] && [ -f "${RESOLVED_DIR}/task_plan.md" ]; then
        PLAN_FILE="${RESOLVED_DIR}/task_plan.md"
        PLAN_DIR="${RESOLVED_DIR}"
    elif [ -n "${PLAN_ID:-}" ] || [ -n "${PWF_PLAN_ROOT:-}" ]; then
        # Explicit selectors are bindings, not hints (issue #237). The shared
        # resolver rejected one, so the legacy cwd fallback below must not run:
        # answering a mistyped pin with the ROOT plan's completion state is the
        # same wrong-plan harm the binding removes, and here it would decide
        # whether an autonomous run is allowed to stop.
        echo "[planning-with-files] An explicit PLAN_ID or PWF_PLAN_ROOT did not resolve to a plan; no completion state was read and no other plan was substituted."
        exit "$VALIDATE"
    else
        PLAN_FILE="task_plan.md"
        PLAN_DIR="."
    fi
fi

if [ ! -f "$PLAN_FILE" ]; then
    [ "$VALIDATE" -eq 1 ] && { echo "[planning-with-files] Plan format invalid: task_plan.md was not found." >&2; exit 1; }
    # Automatic gate checks have nothing to report without a plan (header:
    # "plans stay silent in --gate mode"); the explicit report keeps its notice.
    [ "$GATE" -eq 1 ] && exit 0
    echo "[planning-with-files] No task_plan.md found — no active planning session."
    exit 0
fi

# Count native statuses inside real phases, excluding fenced examples (#377).
PLAN_COUNTS=$(LC_ALL=C awk '
        function finish_phase() {
            if (in_phase) {
                if (status_count != 1) invalid = 1
                else {
                    if (phase_status != "in_progress") counts[phase_status]++
                }
                if (has_active_status) {
                    counts["in_progress"]++
                    if (active_heading == "") active_heading = heading
                }
            }
            in_phase = 0; status_count = 0; phase_status = ""; has_active_status = 0
        }
        function fenced(line,    trimmed, marker, run) {
            trimmed = line; sub(/^ ? ? ?/, "", trimmed)
            if (line ~ /^ ? ? ?```/ || line ~ /^ ? ? ?~~~/) {
                marker = substr(trimmed, 1, 1); run = 0
                while (substr(trimmed, run + 1, 1) == marker) run++
                if (fence == "" && marker == "`" && index(substr(trimmed, run + 1), "`")) return 0
                if (fence == "") { fence = marker; fence_length = run }
                else if (marker == fence && run >= fence_length && substr(trimmed, run + 1) ~ /^[ \t]*$/) fence = ""
                return 1
            }
            return fence != ""
        }
        function read_status(line,    token, boundary) {
            while (match(line, /\*\*Status:\*\*[ \t]+(pending|in_progress|complete)([^A-Za-z0-9_]|$)|\[(pending|in_progress|complete)\]/)) {
                token = substr(line, RSTART, RLENGTH)
                boundary = substr(token, 1, 2) == "**" && token ~ /[^A-Za-z0-9_]$/
                sub(/^\*\*Status:\*\*[ \t]+|^\[/, "", token)
                sub(/[^a-z_].*$/, "", token)
                status_count++; phase_status = token
                if (token == "in_progress") has_active_status = 1
                line = substr(line, RSTART + RLENGTH - boundary)
            }
        }
        NR == 1 { sub(/^\357\273\277/, "") }
        { sub(/\r$/, "") }
        fenced($0) || /^ ? ? ?>/ { next }
        /^ ? ? ?### Phase([0-9:]|-[0-9])/ { finish_phase(); malformed_heading = 1; next }
        /^ ? ? ?### Phase([ \t]|$)/ {
            finish_phase(); total++; in_phase = 1; heading = $0
        }
        !/^ ? ? ?### Phase([ \t]|$)/ && /^ ? ? ?(###|##|#)([ \t]|$)/ { finish_phase() }
        in_phase { read_status($0) }
        END {
            finish_phase()
            printf "%d %d %d %d %d %d\n%s\n", total, counts["complete"], counts["in_progress"], counts["pending"], invalid, (fence != "" || malformed_heading), active_heading
        }
    ' 2>/dev/null < "$PLAN_FILE") || PLAN_COUNTS="0 0 0 0 0 1"
read -r TOTAL COMPLETE IN_PROGRESS PENDING INVALID UNKNOWN <<EOF
$PLAN_COUNTS
EOF

if [ "$VALIDATE" -eq 1 ]; then
    if [ "$TOTAL" -eq 0 ] || [ "$INVALID" -ne 0 ] || [ "$UNKNOWN" -ne 0 ]; then
        echo "[planning-with-files] Plan format invalid: use ### Phase headings with exactly one native status per phase."
        exit 1
    fi
    printf '[planning-with-files] Plan format valid (%d phases).\n' "$TOTAL"
    exit 0
fi

# issue #191: no "### Phase" headings -> not a phase-structured plan. Report
# nothing rather than a false "0/0 phases complete" status. With TOTAL=0 the
# gate can never legitimately block (IN_PROGRESS is also 0), so exit is safe.
if [ "$TOTAL" -eq 0 ] && [ "$UNKNOWN" -eq 0 ]; then
    exit 0
fi

# Explicit status reports retain completion text. Automatic gate checks have
# nothing to report on success; keep evaluating all gate guards before here.
advisory_report() {
    if [ "$UNKNOWN" -ne 0 ]; then
        echo "[planning-with-files] Plan format or read error: phase completion unavailable."
    elif [ "$COMPLETE" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
        [ "$GATE" -eq 1 ] && return 0
        echo "[planning-with-files] ALL PHASES COMPLETE ($COMPLETE/$TOTAL). If the user has additional work, add new phases to task_plan.md before starting."
    else
        echo "[planning-with-files] Task in progress ($COMPLETE/$TOTAL phases complete). Update progress.md before stopping."
        if [ "$IN_PROGRESS" -gt 0 ]; then
            echo "[planning-with-files] $IN_PROGRESS phase(s) still in progress."
        fi
        if [ "$PENDING" -gt 0 ]; then
            echo "[planning-with-files] $PENDING phase(s) pending."
        fi
    fi
}

# ---- Default (advisory) path: byte-equivalent to v2.43 ----
if [ "$GATE" -ne 1 ]; then
    advisory_report
    exit 0
fi

# ---- Gate path (--gate). Resolves to advisory unless every guard says block. ----

# Guard 1: gated mode. A .mode file must contain "gate". Absent or other
# content means advisory mode (legacy behavior preserved).
#
# The project's root .mode is a FLOOR, not a default that slug scope replaces
# (issue #238). Reading only <plan-dir>/.mode let a slug plan with no .mode
# drop a project-committed gate, the same way it dropped the attestation
# requirement in inject-plan.sh. "gate" from EITHER file arms the gate; a slug
# may raise strictness, never lower it. In root scope PLAN_DIR already IS the
# project root, so the second source stays empty and behavior is unchanged.
MODE_FILE="${PLAN_DIR}/.mode"
ROOT_MODE_FILE=""
_root_for_mode="${PWF_PLAN_ROOT:-.}"
if [ "${PLAN_DIR}" != "${_root_for_mode}" ] && [ "${PLAN_DIR}" != "." ]; then
    ROOT_MODE_FILE="${_root_for_mode}/.mode"
fi
GATED=0
if [ -f "${MODE_FILE}" ] && grep -q "gate" "${MODE_FILE}" 2>/dev/null; then
    GATED=1
fi
if [ "${GATED}" -eq 0 ] && [ -n "${ROOT_MODE_FILE}" ] && [ -f "${ROOT_MODE_FILE}" ] \
    && grep -q "gate" "${ROOT_MODE_FILE}" 2>/dev/null; then
    GATED=1
fi
if [ "${GATED}" -eq 0 ]; then
    advisory_report
    exit 0
fi

# Guard 3: stop_hook_active. Read the Stop hook JSON from stdin only when fd 0
# is not a TTY (see header). A true value means we are already inside a forced
# continuation; allow the stop to avoid runaway recursion.
STDIN_JSON=""
if [ ! -t 0 ]; then
    STDIN_JSON="$(cat 2>/dev/null)"
fi
# Anchor on the VALUE: "stop_hook_active" immediately followed (allowing
# whitespace and the colon) by true. A bare glob like *stop_hook_active*true*
# false-positives on '{"stop_hook_active": false, "other": true}', which would
# silently disable the gate. Newlines are collapsed so the match works whether
# the payload is pretty-printed or single-line.
STOP_HOOK_ACTIVE="$(
    printf '%s' "${STDIN_JSON}" \
        | tr '\n' ' ' \
        | sed -n 's/.*"stop_hook_active"[[:space:]]*:[[:space:]]*true.*/FOUND/p'
)"
if [ "${STOP_HOOK_ACTIVE}" = "FOUND" ]; then
    advisory_report
    exit 0
fi

# Guard 2: an in_progress phase must exist. Merely complete<total is a normal
# state and must NOT block (issue #178 lesson).
if [ "$IN_PROGRESS" -le 0 ]; then
    advisory_report
    exit 0
fi

# ledger_line_count: total lines across all <plan-dir>/ledger-*.jsonl files.
# Echoes a single integer (0 when no ledger files exist).
ledger_line_count() {
    _total=0
    for _lf in "${PLAN_DIR}"/ledger-*.jsonl; do
        [ -f "${_lf}" ] || continue
        _n="$(grep -c '' "${_lf}" 2>/dev/null || echo 0)"
        _total=$((_total + _n))
    done
    printf "%s" "${_total}"
}

CAP="${PWF_GATE_CAP:-20}"
case "${CAP}" in
    ''|*[!0-9]*) CAP=20 ;;
esac

BLOCKS_FILE="${PLAN_DIR}/.stop_blocks"
BLOCKS="$(cat "${BLOCKS_FILE}" 2>/dev/null || echo 0)"
case "${BLOCKS}" in
    ''|*[!0-9]*) BLOCKS=0 ;;
esac

LEDGER_FILE="${PLAN_DIR}/.gate_last_ledger"
LEDGER_PREV="$(cat "${LEDGER_FILE}" 2>/dev/null || echo 0)"
case "${LEDGER_PREV}" in
    ''|*[!0-9]*) LEDGER_PREV=0 ;;
esac
LEDGER_NOW="$(ledger_line_count)"

# Guard 4: block-count cap. At or over the cap, allow the stop.
if [ "${BLOCKS}" -ge "${CAP}" ]; then
    advisory_report
    echo "[planning-with-files] gate cap reached ($BLOCKS/$CAP) — allowing stop."
    exit 0
fi

# Guard 5: stall detection. If we have blocked before (BLOCKS > 0) and the
# ledger line count has not advanced since the last block, nothing progressed:
# allow the stop instead of looping.
if [ "${BLOCKS}" -gt 0 ] && [ "${LEDGER_NOW}" -eq "${LEDGER_PREV}" ]; then
    advisory_report
    echo "[planning-with-files] no progress since last gate block — allowing stop."
    exit 0
fi

# All guards passed: block the stop.
# json_escape: escape a string for safe inclusion in a JSON string literal.
# Escapes backslash and double-quote, then neutralizes every bare control
# character JSON forbids (0x01-0x1F) by mapping it to a space. A phase heading
# may carry a literal tab or other control byte; left raw it produces invalid
# JSON ("Bad control character in string literal") that the Stop hook rejects.
json_escape() {
    printf "%s" "$1" \
        | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' \
        | tr '\001-\037' ' '
}

# first_in_progress_phase: heading text of the first phase whose Status is
# in_progress. Reads the plan top-to-bottom, remembers the most recent
# "### " heading, and prints it (with the "### " prefix stripped) at the first
# in_progress status line. Plain text only — no plan body beyond the heading.
first_in_progress_phase() {
    printf '%s\n' "$PLAN_COUNTS" | sed -n '2s/^ *### //p'
}

PHASE_NAME="$(first_in_progress_phase)"
if [ -z "${PHASE_NAME}" ]; then
    PHASE_NAME="unknown phase"
fi
PHASE_ESCAPED="$(json_escape "${PHASE_NAME}")"

NEW_BLOCKS=$((BLOCKS + 1))
printf "%s\n" "${NEW_BLOCKS}" > "${BLOCKS_FILE}" 2>/dev/null || true
printf "%s\n" "${LEDGER_NOW}" > "${LEDGER_FILE}" 2>/dev/null || true

printf '{"decision":"block","reason":"[planning-with-files] Gated plan incomplete: phase '\''%s'\'' is in_progress (%s/%s complete, gate block %s/%s). Finish or update the plan, then stop."}\n' \
    "${PHASE_ESCAPED}" "${COMPLETE}" "${TOTAL}" "${NEW_BLOCKS}" "${CAP}"
exit 0
