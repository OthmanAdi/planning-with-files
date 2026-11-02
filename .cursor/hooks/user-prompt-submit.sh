#!/bin/bash
# planning-with-files: User prompt submit hook for Cursor
# Injects plan context on every user message.
# Critical for session recovery after /clear — dumps actual content, not just advice.

# Issue #195 opt-out. The disabled branch reproduces this hook's own
# no-plan-file behaviour, so the Cursor protocol shape never changes.
[ "${PLANNING_DISABLED:-}" = "1" ] && exit 0

HOOK_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)" || exit 0
[ -f "${HOOK_DIR}/resolve-plan-context.sh" ] || exit 0
. "${HOOK_DIR}/resolve-plan-context.sh"
cursor_resolve_plan_context "${HOOK_DIR}"
if [ -z "${CURSOR_PLAN_DIR}" ]; then
    case "${CURSOR_PLAN_STATUS}" in
        ambiguous)
            echo "[planning-with-files] Multiple plans are available. Set PLAN_ID=<slug> for this session; nothing injected. Finished plans can be archived with set-active-plan --archive <slug>." ;;
        invalid-pin)
            echo "[planning-with-files] PWF_PLAN_ROOT is not a supported absolute local directory: ${CURSOR_PLAN_DETAIL} — nothing injected." ;;
        invalid-plan-id)
            echo "[planning-with-files] PLAN_ID does not name a plan directory under .planning: ${CURSOR_PLAN_DETAIL} — nothing injected. Fix or unset the pin; a broken pin fails closed rather than selecting another plan." ;;
        refused) ;;
        *)
            echo "[planning-with-files] The selected plan could not be resolved safely (${CURSOR_PLAN_DETAIL}). Check PLAN_ID, PWF_PLAN_ROOT, and .active_plan; nothing injected." ;;
    esac
    exit 0
fi
PLAN_FILE="${CURSOR_PLAN_DIR}/task_plan.md"
PROGRESS_FILE="${CURSOR_PLAN_DIR}/progress.md"

if [ ! -f "$PLAN_FILE" ]; then
    exit 0
fi

# --- Nested-root conflict detection (issue #212): fail CLOSED on ambiguity.
# A shared pointer or newest-plan / legacy-root fallback is still a cwd GUESS
# unless an explicit PWF_PLAN_ROOT or PLAN_ID selected it. If a direct child
# carries its own competing .planning, inject NOTHING and say why.
if [ -z "${PWF_PLAN_ROOT:-}" ] && [ -z "${PLAN_ID:-}" ]; then
    NESTED_LIST=""
    NESTED_N=0
    for nd in */.planning; do
        [ -d "$nd" ] || continue
        COMPETING=0
        [ -f "${nd}/.active_plan" ] && COMPETING=1
        if [ "$COMPETING" = "0" ]; then
            for np in "${nd}"/*/task_plan.md; do
                [ -f "$np" ] && { COMPETING=1; break; }
            done
        fi
        [ "$COMPETING" = "1" ] || continue
        NR="${nd%/.planning}"
        NESTED_N=$((NESTED_N + 1))
        if [ "$NESTED_N" -le 3 ]; then
            if [ -z "$NESTED_LIST" ]; then NESTED_LIST="$NR"; else NESTED_LIST="${NESTED_LIST}, ${NR}"; fi
        fi
    done
    if [ "$NESTED_N" -gt 0 ]; then
        echo "[planning-with-files] Ambiguous plan: this cwd has an active plan and a nested project below it has its own (${NESTED_LIST}). Nothing injected. Pin the thread with PWF_PLAN_ROOT=<absolute path> or PLAN_ID=<slug>."
        exit 0
    fi
fi

echo "[planning-with-files] ACTIVE PLAN — current state:"
head -50 "$PLAN_FILE"
echo ""
echo "=== recent progress ==="
# Timestamp normalization matches scripts/inject-plan.sh (KV-cache stability, v2.40).
tail -20 "$PROGRESS_FILE" 2>/dev/null | sed -E 's/T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z/T00:00:00Z/g; s/T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?([+-][0-9]{2}:[0-9]{2})/T00:00:00\2/g'
echo ""
echo "[planning-with-files] Read findings.md for research context. Continue from the current phase."
exit 0
