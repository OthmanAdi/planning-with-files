#!/bin/bash
# planning-with-files: User prompt submit hook for Codex

# issue #195: per-invocation opt-out for one-shot/CI sessions (e.g. codex exec)
# that share a cwd with a plan but never opted into it.
[ "${PLANNING_DISABLED:-}" = "1" ] && exit 0

HOOK_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"

validate_python_candidate() {
    _tp_candidate="$1"
    case "$_tp_candidate" in
        //*) return 1 ;;
        [A-Za-z]:[\\/]*)
            command -v cygpath >/dev/null 2>&1 || return 1
            _tp_candidate=$(cygpath -u -- "$_tp_candidate" 2>/dev/null) || return 1
            ;;
        /*) ;;
        *) return 1 ;;
    esac
    [ -f "$_tp_candidate" ] || return 1
    _tp_lower=$(printf '%s' "$_tp_candidate" | tr '[:upper:]' '[:lower:]')
    case "$_tp_lower" in
        */microsoft/windowsapps/*) return 1 ;;
    esac
    "$_tp_candidate" -I -X utf8 -c 'import sys' >/dev/null 2>&1 || return 1
    printf '%s\n' "$_tp_candidate"
}

trusted_python() {
    _tp_explicit="${PWF_TRUSTED_PYTHON:-${PYTHON_BIN:-}}"
    if [ -n "$_tp_explicit" ]; then
        validate_python_candidate "$_tp_explicit"
        return $?
    fi
    [ "${1:-}" = "explicit" ] && return 1
    for _tp_name in python3 python; do
        _tp_found=$(command -v "$_tp_name" 2>/dev/null) || _tp_found=""
        [ -n "$_tp_found" ] || continue
        validate_python_candidate "$_tp_found" && return 0
    done
    return 1
}

# --- PWF_PLAN_ROOT: absolute plan-root binding (issue #212). ---
# A thread whose cwd is a shared PARENT of the real project (e.g. /workspace
# holding /workspace/project with its own .planning/.active_plan) used to
# resolve the parent's plan on every hook fire and never see the nested one.
# PWF_PLAN_ROOT names the project root whose .planning must be used; every
# planning-state path read below goes through ${PLAN_PREFIX}, and the shared
# resolver honors the same variable. With the var unset the prefix is EMPTY so
# every path string stays byte-identical to the legacy shape. An explicit but
# broken pin fails CLOSED: pointing PWF_PLAN_ROOT at a non-directory emits one
# notice and injects nothing, never silently falls back to the ambiguous cwd
# plan the caller was escaping. Wording matches scripts/inject-plan.sh.
PLAN_PREFIX=""
if [ -n "${PWF_PLAN_ROOT:-}" ]; then
    case "${PWF_PLAN_ROOT}" in
        /*|[A-Za-z]:[\\/]*) ;;
        *) echo "[planning-with-files] PWF_PLAN_ROOT must be an absolute local path; nothing injected."; exit 0 ;;
    esac
    PIN_PYTHON="$(trusted_python explicit 2>/dev/null)" || PIN_PYTHON=""
    [ -n "$PIN_PYTHON" ] || { echo "[planning-with-files] PWF_PLAN_ROOT could not be validated; nothing injected."; exit 0; }
    PIN_REAL=$("$PIN_PYTHON" -I -X utf8 -c 'import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); import codex_hook_adapter as a; root=a.effective_plan_root(Path.cwd()); print(root or "")' "$HOOK_DIR" 2>/dev/null) || PIN_REAL=""
    [ -n "$PIN_REAL" ] || { echo "[planning-with-files] PWF_PLAN_ROOT must stay within the current workspace; nothing injected."; exit 0; }
    if [ -n "$PIN_REAL" ] && [ -d "$PIN_REAL" ]; then
        PWF_PLAN_ROOT="$PIN_REAL"
        export PWF_PLAN_ROOT
        PLAN_PREFIX="${PIN_REAL}/"
    else
        echo "[planning-with-files] PWF_PLAN_ROOT is not a directory; nothing injected."
        exit 0
    fi
fi

# Resolve and confirm a contained plan before probing or executing any Python
# candidate. No-plan hook fires remain shell-only and silent.
PLAN_DIR="$(sh "${HOOK_DIR}/resolve-plan-dir.sh" 2>/dev/null)"
PLAN_AMBIGUOUS=0
if [ -z "$PLAN_DIR" ] && [ "$(sh "${HOOK_DIR}/resolve-plan-dir.sh" --check-ambiguity 2>/dev/null)" = "PWF_PLAN_AMBIGUOUS_V1" ]; then
    PLAN_AMBIGUOUS=1
fi
if [ -n "$PLAN_DIR" ]; then
    PLAN_FILE="${PLAN_DIR}/task_plan.md"
    PROGRESS_FILE="${PLAN_DIR}/progress.md"
elif [ -n "${PLAN_ID:-}" ]; then
    # An explicit PLAN_ID is a binding, not a hint (issue #237). The shared
    # resolver rejected it, so the legacy-root fallback below would inject a
    # plan the operator never named. This hook fires once per turn, so one
    # diagnosable line is not spam and the alternative is a dark session with
    # no stated cause. Wording matches scripts/inject-plan.sh so all routes say
    # the same thing.
    echo "[planning-with-files] PLAN_ID does not name a plan directory under .planning: ${PLAN_ID} — nothing injected. Fix or unset the pin; a broken pin fails closed rather than selecting another plan."
    exit 0
else
    PLAN_FILE="${PLAN_PREFIX}task_plan.md"
    PROGRESS_FILE="${PLAN_PREFIX}progress.md"
fi
[ -f "$PLAN_FILE" ] || [ "$PLAN_AMBIGUOUS" = "1" ] || exit 0

# --- Re-arm the once-per-turn PostToolUse nudge (issue #239). ---
# One user message is one turn, and this hook fires once per turn, so clearing
# the marker here is what makes the nudge appear once after the first write
# instead of after every matching tool call.
#
# The key is computed from post-tool-use.sh's OWN plan-file expression, not
# from $PLAN_FILE above. This hook resolves a PWF_PLAN_ROOT pin and that one
# does not, so the two spellings diverge under a pin; keying off the shared
# expression keeps both sides on one marker. A mismatch here would not be
# loud: the marker would never be cleared and the nudge would fire once per
# session instead of once per turn.
TURN_PLAN_FILE="${PLAN_DIR:+${PLAN_DIR}/}task_plan.md"
if [ -n "${XDG_CACHE_HOME:-}" ]; then
    TURN_ROOT="${XDG_CACHE_HOME}/pwf-turn"
elif [ -n "${HOME:-}" ]; then
    TURN_ROOT="${HOME}/.cache/pwf-turn"
else
    TURN_ROOT="${TMPDIR:-/tmp}/pwf-turn"
fi
if [ "$PLAN_AMBIGUOUS" = "0" ] && [ -d "$TURN_ROOT" ]; then
    case "$TURN_PLAN_FILE" in
        /*|[A-Za-z]:*|\\\\*) TURN_KEY_SRC="$TURN_PLAN_FILE" ;;
        *) TURN_KEY_SRC="${PWD}/${TURN_PLAN_FILE}" ;;
    esac
    TURN_KEY_SRC="${TURN_KEY_SRC}|${PWF_SESSION_ID:-}"
    TURN_KEY=$(printf '%s' "$TURN_KEY_SRC" \
        | { sha256sum 2>/dev/null || shasum -a 256 2>/dev/null; } \
        | awk '{print $1}' | cut -c1-16)
    [ -n "$TURN_KEY" ] && rm -f -- "${TURN_ROOT}/${TURN_KEY}" 2>/dev/null || :
fi

# Session isolation: if .planning/sessions/ exists, only attached sessions see
# plan context. Absence of the sessions dir means legacy single-session mode —
# all sessions in the cwd receive context to preserve backward compatibility.
# issue #212: the refusal is no longer silent. This hook fires once per turn,
# so one diagnosable line is not spam; the per-tool-call hooks (the Python
# adapter's guard) stay silent. Wording matches scripts/inject-plan.sh so all
# three routes say the same thing.
SESSION_ATTACHED=0
SESSION_ID="${PWF_SESSION_ID:-}"
if [ ! -e "${PLAN_PREFIX}.planning/sessions" ] && [ ! -L "${PLAN_PREFIX}.planning/sessions" ]; then
    PWF_SESSION_ADMISSION="legacy"
else
    PWF_PYTHON="$(trusted_python 2>/dev/null)" || PWF_PYTHON=""
    if [ -z "$PWF_PYTHON" ]; then
        PWF_SESSION_ADMISSION="refused"
    else
        PWF_SESSION_ADMISSION=$("$PWF_PYTHON" -I -X utf8 -c 'import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); import codex_hook_adapter as a; root=a.effective_plan_root(Path.cwd());
if root is None: print("refused")
else:
    try: (root / ".planning" / "sessions").lstat(); armed=True
    except FileNotFoundError: armed=False
    except OSError: armed=True
    admitted=a.is_session_attached(root, sys.argv[2] or None)
    print("attached" if admitted and armed else ("legacy" if admitted else "refused"))' "$HOOK_DIR" "$SESSION_ID" 2>/dev/null) || PWF_SESSION_ADMISSION="refused"
    fi
fi
case "$PWF_SESSION_ADMISSION" in
    attached) SESSION_ATTACHED=1 ;;
    legacy) ;;
    *)
        echo "[planning-with-files] Session isolation is armed (${PLAN_PREFIX}.planning/sessions/ exists) and this session is not attached, so no plan was injected. Attachment sentinels use a fixed-width digest of host, canonical project, and PWF_SESSION_ID; delete the sessions directory to return to legacy single-session mode."
        exit 0
        ;;
esac

if [ "$PLAN_AMBIGUOUS" = "1" ]; then
    echo "[planning-with-files] Multiple plans are available. Set PLAN_ID=<slug> for this session; nothing injected."
    exit 0
fi

# Plan-id safe-identifier check. Pure-sh case patterns; shared shape with
# resolve-plan-dir.sh, needed below to decide whether PLAN_ID named the plan.
slug_is_valid() {
    case "$1" in
        '') return 1 ;;
        *[!A-Za-z0-9._-]*) return 1 ;;
        [A-Za-z0-9_]*) return 0 ;;
    esac
    return 1
}

# An attachment admits a session but does not select one of several plans.
# When isolation is armed, require PLAN_ID if more than one live same-root
# candidate exists. PWF_PLAN_ROOT selects the project root, not a plan within
# that root.
if [ "$SESSION_ATTACHED" = "1" ] && [ -z "${PLAN_ID:-}" ]; then
    SESSION_PLAN_N=0
    [ -f "${PLAN_PREFIX}task_plan.md" ] && SESSION_PLAN_N=1
    for candidate in "${PLAN_PREFIX}".planning/*/task_plan.md; do
        [ -f "$candidate" ] || continue
        candidate_dir="${candidate%/task_plan.md}"
        candidate_slug="${candidate_dir##*/}"
        slug_is_valid "$candidate_slug" || continue
        SESSION_PLAN_N=$((SESSION_PLAN_N + 1))
        [ "$SESSION_PLAN_N" -gt 1 ] && break
    done
    if [ "$SESSION_PLAN_N" -gt 1 ]; then
        echo "[planning-with-files] Multiple plans are available while session isolation is armed. Set PLAN_ID=<slug> for this session; nothing injected."
        exit 0
    fi
fi

# EXPLICIT tracks who selected the effective project root or plan for the
# nested-root conflict check. A valid PLAN_ID names a plan deliberately and a
# valid PWF_PLAN_ROOT chooses the project root deliberately.
# The .active_plan pointer, the newest-by-mtime fallback, and the legacy root
# task_plan.md are cwd GUESSES — only guesses are subject to the nested-root
# conflict check below. Mirrors scripts/inject-plan.sh.
EXPLICIT=0
[ -n "$PLAN_PREFIX" ] && EXPLICIT=1
if [ -n "${PLAN_ID:-}" ] && slug_is_valid "$PLAN_ID" && [ -d "${PLAN_PREFIX}.planning/${PLAN_ID}" ]; then
    EXPLICIT=1
fi

if [ -f "$PLAN_FILE" ]; then
    # --- Nested-root conflict detection (issue #212): fail CLOSED on ambiguity.
    # Only a cwd guess gets here with EXPLICIT=0. If a direct child of the
    # effective root carries its own competing .planning (an .active_plan
    # pointer, or at least one <slug>/task_plan.md), this cwd is a shared
    # parent and "the plan under $PWD" is the wrong answer for at least one
    # thread — so inject NOTHING and say why. Depth 1 only: one shell glob per
    # hook fire is the whole perf budget; the effective root's own .planning is
    # never a hit because `*` does not match dotted names. Wording matches
    # scripts/inject-plan.sh.
    if [ "$EXPLICIT" = "0" ]; then
        NESTED_LIST=""
        NESTED_N=0
        for nd in "${PLAN_PREFIX}"*/.planning; do
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
            NR="${NR#"${PLAN_PREFIX}"}"
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

    PWF_PYTHON="$(trusted_python 2>/dev/null)" || PWF_PYTHON=""
    if [ -z "$PWF_PYTHON" ] || [ ! -f "${HOOK_DIR}/context_frame.py" ]; then exit 0; fi
    if [ -n "$PLAN_DIR" ]; then ATTEST_FILE="${PLAN_DIR}/.attestation"; else ATTEST_FILE="${PLAN_PREFIX}.plan-attestation"; fi
    if [ -n "$PLAN_DIR" ]; then MODE_FILE="${PLAN_DIR}/.mode"; else MODE_FILE="${PLAN_PREFIX}.mode"; fi
    PLAN_CONTEXT=$("$PWF_PYTHON" -I -X utf8 "${HOOK_DIR}/context_frame.py" plan "$PLAN_FILE" --head 50 --attestation "$ATTEST_FILE" --mode "$MODE_FILE" 2>&1)
    if [ $? -ne 0 ]; then printf '%s\n' "$PLAN_CONTEXT"; exit 0; fi
    echo "[planning-with-files] ACTIVE PLAN — current state:"
    printf '%s\n' "$PLAN_CONTEXT"
    echo ""
    if [ -f "$PROGRESS_FILE" ]; then
        PROGRESS_CONTEXT=$("$PWF_PYTHON" -I -X utf8 "${HOOK_DIR}/context_frame.py" progress "$PROGRESS_FILE" --tail 20 2>&1)
        [ $? -eq 0 ] && printf '%s\n' "$PROGRESS_CONTEXT"
    fi
    echo ""
    echo "[planning-with-files] Read findings.md for research context. Continue from the current phase."
fi
exit 0
