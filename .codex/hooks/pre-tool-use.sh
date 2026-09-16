#!/bin/bash
# planning-with-files: Pre-tool-use hook for Codex

# issue #195: per-invocation opt-out for one-shot/CI sessions. Still emit the
# allow decision so the tool call proceeds; only the plan context is skipped.
if [ "${PLANNING_DISABLED:-}" = "1" ]; then
    echo '{"decision": "allow"}'
    exit 0
fi

HOOK_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
PLAN_DIR="$(sh "${HOOK_DIR}/resolve-plan-dir.sh" 2>/dev/null)"
if [ -z "$PLAN_DIR" ] && [ "$(sh "${HOOK_DIR}/resolve-plan-dir.sh" --check-ambiguity 2>/dev/null)" = "PWF_PLAN_AMBIGUOUS_V1" ]; then
    exit 0
fi
# An explicit PLAN_ID is a binding, not a hint (issue #237). When the shared
# resolver rejected one it emits nothing, and the legacy-root fallback below
# would recite a plan the operator never named on every tool call. Stay silent
# instead; the once-per-turn user-prompt-submit hook carries the notice.
[ -z "$PLAN_DIR" ] && [ -n "${PLAN_ID:-}" ] && exit 0
PLAN_FILE="${PLAN_DIR:+${PLAN_DIR}/}task_plan.md"

if [ -f "$PLAN_FILE" ]; then
    PWF_PYTHON="${PWF_TRUSTED_PYTHON:-${PYTHON_BIN:-}}"
    case "$PWF_PYTHON" in
        //*) PWF_PYTHON="" ;;
        [A-Za-z]:[\\/]*)
            if command -v cygpath >/dev/null 2>&1; then
                PWF_PYTHON=$(cygpath -u -- "$PWF_PYTHON" 2>/dev/null) || PWF_PYTHON=""
            else
                PWF_PYTHON=""
            fi
            ;;
        /*) ;;
        *) PWF_PYTHON="" ;;
    esac
    if [ -n "$PWF_PYTHON" ] && [ -f "$PWF_PYTHON" ] && [ -f "${HOOK_DIR}/context_frame.py" ]; then
        if [ -n "$PLAN_DIR" ]; then ATTEST_FILE="${PLAN_DIR}/.attestation"; else ATTEST_FILE=".plan-attestation"; fi
        if [ -n "$PLAN_DIR" ]; then MODE_FILE="${PLAN_DIR}/.mode"; else MODE_FILE=".mode"; fi
        PWF_MODE=$("$PWF_PYTHON" -I -X utf8 -c 'import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); import context_frame as c; raw=c.read_optional_regular_bytes(Path(sys.argv[2]), max_source_bytes=256); tokens=[] if raw is None else raw.decode("ascii", errors="strict").split(); allowed={"autonomous", "gate", "inject-smart"}; print("unsafe" if any(t not in allowed for t in tokens) else ("gated" if "gate" in tokens else ("autonomous" if "autonomous" in tokens else "legacy")))' "$HOOK_DIR" "$MODE_FILE" 2>/dev/null) || PWF_MODE="unsafe"
        case "$PWF_MODE" in
            autonomous|gated) echo '{"decision": "allow"}'; exit 0 ;;
            legacy) "$PWF_PYTHON" -I -X utf8 "${HOOK_DIR}/context_frame.py" plan "$PLAN_FILE" --head 30 --attestation "$ATTEST_FILE" --mode "$MODE_FILE" >&2 ;;
            *) : ;;
        esac
    fi
fi

echo '{"decision": "allow"}'
exit 0
