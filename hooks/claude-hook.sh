#!/bin/sh
# Claude Code plugin lifecycle dispatcher.
#
# Plugin execution is deliberately rooted only at CLAUDE_PLUGIN_ROOT. The
# standalone skill keeps its own activation-scoped frontmatter hooks, while
# this launcher is the single plugin-level lifecycle route.

set -u

[ "${PLANNING_DISABLED:-}" = "1" ] && exit 0

EVENT="${1:-}"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-}"
[ -n "$PLUGIN_ROOT" ] || exit 0

SCRIPTS_DIR="${PLUGIN_ROOT}/scripts"
INJECT_PLAN="${SCRIPTS_DIR}/inject-plan.sh"
GATE_STOP="${SCRIPTS_DIR}/gate-stop.sh"
RESOLVE_PLAN_DIR="${SCRIPTS_DIR}/resolve-plan-dir.sh"
SESSION_CATCHUP="${SCRIPTS_DIR}/session-catchup.py"
FAST_PATH="${SCRIPTS_DIR}/inject-plan.py"

# --- One interpreter instead of one fork per tool (v3.17.0). ---
# Everything below this block answers an event by running resolve-plan-dir.sh
# and inject-plan.sh, and those answer by forking: realpath, stat, sha256sum,
# awk, tr, mktemp, head, tail, sed, wc, four Python starts, and a $(...)
# around most of them. A UserPromptSubmit fire forks about 130 times. On Linux
# and macOS a fork costs one to three milliseconds. Under Git Bash on Windows
# it costs about 90 ms, so the same fire took seven to twelve seconds against
# the 10 s hook timeout: Claude Code discarded the output, the plan never
# reached the model, and every Bash, Read, Grep and Edit call waited five
# more seconds in PreToolUse first.
#
# scripts/inject-plan.py is a byte-identical twin of the chain below
# (tests/test_inject_plan_python_parity.py proves it against this file and
# inject-plan.sh on every CI leg). When a CPython 3 is on PATH the event runs
# there in one process. The twin exits 0 only when its stdout is the complete
# answer; any other status, including an interpreter that cannot run it, falls
# through to the reference chain below unchanged. PWF_FAST_PATH=0 forces the
# reference chain. The Stop event never takes the fast path because it must
# forward Claude's stdin payload to gate-stop.sh.
#
# The PATH walk below is pure shell on purpose: `$(command -v python3)` is
# itself a fork, and the whole point of this block is to spend none. The
# Microsoft Store python.exe/python3.exe aliases are skipped by path: they are
# discoverable on PATH yet refuse to run a script. python3 is preferred over
# python across the whole PATH so an old distro's Python 2 `python` is never
# tried while a python3 exists further down.
find_python() {
    FOUND_PYTHON=""
    for _fp_explicit in "${PWF_TRUSTED_PYTHON:-}" "${PYTHON_BIN:-}"; do
        [ -n "$_fp_explicit" ] || continue
        case "$_fp_explicit" in
            /*|[A-Za-z]:[\\/]*) ;;
            *) continue ;;
        esac
        case "$_fp_explicit" in
            *[Ww][Ii][Nn][Dd][Oo][Ww][Ss][Aa][Pp][Pp][Ss]*) continue ;;
        esac
        if [ -f "$_fp_explicit" ] && [ -x "$_fp_explicit" ]; then
            FOUND_PYTHON="$_fp_explicit"
            return 0
        fi
    done
    # set -u is active: an unset IFS or PATH must not kill the dispatcher
    # before the reference chain gets its turn.
    if [ "${IFS+set}" = set ]; then
        _fp_saved_ifs="$IFS"
        _fp_ifs_was_set=1
    else
        _fp_saved_ifs=""
        _fp_ifs_was_set=0
    fi
    for _fp_name in python3 python; do
        IFS=:
        set -f
        for _fp_dir in ${PATH-}; do
            case "$_fp_dir" in
                /*) ;;
                *) continue ;;
            esac
            case "$_fp_dir" in
                *[Ww][Ii][Nn][Dd][Oo][Ww][Ss][Aa][Pp][Pp][Ss]*) continue ;;
            esac
            if [ -f "${_fp_dir}/${_fp_name}" ] && [ -x "${_fp_dir}/${_fp_name}" ]; then
                FOUND_PYTHON="${_fp_dir}/${_fp_name}"
                break
            fi
        done
        set +f
        if [ "$_fp_ifs_was_set" = 1 ]; then IFS="$_fp_saved_ifs"; else unset IFS; fi
        [ -n "$FOUND_PYTHON" ] && return 0
    done
    return 1
}

case "$EVENT" in
    session-start|user-prompt-submit|pre-tool-use|post-tool-use|pre-compact)
        # A recovery with a temporarily missing plan must invalidate a view
        # delivered to the old context. With no cache, keep the zero-probe exit.
        _pretool_recovery=0
        case "$EVENT" in
            session-start|user-prompt-submit|pre-compact)
                if [ -n "${XDG_CACHE_HOME:-}" ]; then
                    [ ! -d "${XDG_CACHE_HOME}/pwf-pretool" ] || _pretool_recovery=1
                elif [ -n "${HOME:-}" ]; then
                    [ ! -d "${HOME}/.cache/pwf-pretool" ] || _pretool_recovery=1
                fi
                ;;
        esac
        # No planning state where the resolver will look and no selector to
        # validate: every route below answers with nothing, so answer with
        # nothing now, before any interpreter or fork. Byte-identical to the
        # reference chain, which reaches the same silence about ten forks
        # later. A set PLAN_ID or PWF_PLAN_ROOT still gets its refusal notice.
        if [ -z "${PLAN_ID:-}" ] && [ -z "${PWF_PLAN_ROOT:-}" ] \
            && [ ! -f task_plan.md ] && [ ! -d .planning ] && [ "$_pretool_recovery" = 0 ]; then
            exit 0
        fi
        # Own one native payload for these events. Keep Stop's stdin untouched.
        # Preserve it for the shell fallback if the Python twin cannot run.
        HOOK_PAYLOAD="$(cat 2>/dev/null)" || HOOK_PAYLOAD=""
        if [ "${PWF_FAST_PATH:-}" != "0" ] && [ -f "$FAST_PATH" ] && find_python; then
            # -I: isolated mode, so the project directory is never on
            # sys.path and a repository's own secrets.py or hashlib.py cannot
            # be imported by a hook. -B: never write bytecode into the
            # plugin cache. PWF_SHELL_PWD hands the twin this shell's own
            # $PWD spelling so both routes derive the same turn-marker and
            # progress-guard slots; MSYS2_ENV_CONV_EXCL keeps Git Bash from
            # rewriting it into a Windows path on the way.
            #
            # The twin's stdout is deliberately not captured: $(...) costs
            # another fork, the very thing this block exists to remove. The
            # contract that makes this safe is the twin's: it writes nothing
            # until its answer is complete, and exits non-zero otherwise.
            if printf '%s' "$HOOK_PAYLOAD" | PWF_SHELL_PWD="$PWD" \
                MSYS2_ENV_CONV_EXCL="${MSYS2_ENV_CONV_EXCL:+${MSYS2_ENV_CONV_EXCL};}PWF_SHELL_PWD" \
                "$FOUND_PYTHON" -I -B "$FAST_PATH" "--claude-event=${EVENT}" 2>/dev/null; then
                exit 0
            fi
        fi
        # Native session identity is needed on the reference route too. Only
        # use the same trusted interpreter selection as the existing fast path.
        if [ -f "$FAST_PATH" ] && find_python; then
            _identity=$(printf '%s' "$HOOK_PAYLOAD" | "$FOUND_PYTHON" -I -B "$FAST_PATH" --hook-identity 2>/dev/null) || _identity=""
            case "$_identity" in
                *"|"*"|"*)
                    PWF_SESSION_ID="${_identity%%|*}"
                    _identity_tail="${_identity#*|}"
                    PWF_PRETOOL_AGENT="${_identity_tail%%|*}"
                    PWF_PRETOOL_PROMPT="${_identity_tail#*|}"
                    export PWF_SESSION_ID PWF_PRETOOL_AGENT PWF_PRETOOL_PROMPT
                    ;;
                *) unset PWF_SESSION_ID PWF_PRETOOL_AGENT PWF_PRETOOL_PROMPT ;;
            esac
            case "$EVENT" in
                session-start|user-prompt-submit|pre-compact)
                    "$FOUND_PYTHON" -I -B "$FAST_PATH" --pretool-cache clear >/dev/null 2>&1 || :
                    ;;
            esac
        else
            unset PWF_SESSION_ID PWF_PRETOOL_AGENT PWF_PRETOOL_PROMPT
        fi
        ;;
esac

# JSON-string encode bounded, trusted hook output without requiring Python or
# Node. The planning scripts already bound injected project data; this removes
# remaining JSON-forbidden control bytes and preserves line boundaries. Walk
# characters directly because awk gsub replacement escaping varies by runtime.
# LC_ALL=C makes that walk byte-wise: in a UTF-8 locale gawk on Windows walks
# UTF-16 units and re-emits a character outside the BMP as a lone surrogate,
# which is not UTF-8 and reaches the model as garbage.
json_string() {
    tr '\001-\011\013-\037' ' ' \
        | LC_ALL=C awk 'BEGIN { first = 1 }
            {
                if (!first) printf "\\n"
                for (i = 1; i <= length($0); i++) {
                    c = substr($0, i, 1)
                    if (c == "\\") printf "%s", "\\\\"
                    else if (c == "\"") printf "%s", "\\\""
                    else printf "%s", c
                }
                first = 0
            }'
}

emit_context() {
    _event_name="$1"
    _context="$2"
    [ -f "$INJECT_PLAN" ] || exit 0
    _output=$(sh "$INJECT_PLAN" "--context=${_context}" 2>/dev/null) || exit 0
    [ -n "$_output" ] || exit 0
    _encoded=$(printf '%s' "$_output" | json_string)
    printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"%s"}}\n' \
        "$_event_name" "$_encoded"
}

active_plan_dir() {
    _resolved=""
    if [ -f "$RESOLVE_PLAN_DIR" ]; then
        _resolved=$(sh "$RESOLVE_PLAN_DIR" 2>/dev/null) || _resolved=""
        if [ -z "$_resolved" ] && [ "$(sh "$RESOLVE_PLAN_DIR" --check-ambiguity 2>/dev/null)" = "PWF_PLAN_AMBIGUOUS_V1" ]; then
            return 0
        fi
    fi
    if [ -n "$_resolved" ] && [ -f "${_resolved}/task_plan.md" ]; then
        printf '%s\n' "$_resolved"
        return 0
    fi
    # Explicit selectors are bindings, not hints (issue #237). The shared
    # resolver emits nothing when it rejected one, and the legacy-root fallback
    # below would answer for a plan the operator never named. v3.15.0 closed
    # this on the script and Codex routes; the plugin dispatcher reads the same
    # resolver and needed the same guard.
    if [ -n "${PLAN_ID:-}" ] || [ -n "${PWF_PLAN_ROOT:-}" ]; then
        return 0
    fi
    if [ -f task_plan.md ]; then
        printf '%s\n' "."
    fi
}

# --- Once-per-turn throttle for the PostToolUse nudge (issue #239). ---
# The progress reminder is worth one appearance after the first write in a turn
# and is pure noise on every tool call after that: the string is constant, so
# repeats carry no information beyond the first. UserPromptSubmit and
# SessionStart fire exactly once per turn, so they clear the marker and the
# first PostToolUse of the turn sets it.
#
# The marker lives in the user's private cache, never in the plan directory:
# that directory is shared project state and a per-session throttle file does
# not belong in a repo. Cache root and key derivation are deliberately the same
# shape inject-plan.sh already uses for its SHA and progress-guard slots, so
# the marker inherits the same cwd-invariance (#212). If no cache root can be
# created the throttle is skipped rather than the nudge suppressed, which keeps
# a broken cache from silently removing the reminder.
turn_marker_path() {
    _tm_plan="$1"
    if [ -n "${XDG_CACHE_HOME:-}" ]; then
        _tm_root="${XDG_CACHE_HOME}/pwf-turn"
    elif [ -n "${HOME:-}" ]; then
        _tm_root="${HOME}/.cache/pwf-turn"
    else
        _tm_root="${TMPDIR:-/tmp}/pwf-turn"
    fi
    mkdir -p "$_tm_root" 2>/dev/null || return 1
    case "$_tm_plan" in
        /*|[A-Za-z]:*|\\\\*) _tm_key_src="$_tm_plan" ;;
        *) _tm_key_src="${PWD}/${_tm_plan}" ;;
    esac
    # Two sessions sharing one plan must not silence each other's first nudge,
    # so the host's session id joins the key whenever it names one.
    _tm_key_src="${_tm_key_src}|${PWF_SESSION_ID:-}"
    _tm_key=$(printf '%s' "$_tm_key_src" \
        | { sha256sum 2>/dev/null || shasum -a 256 2>/dev/null; } \
        | awk '{print $1}' | cut -c1-16)
    [ -n "$_tm_key" ] || return 1
    printf '%s/%s\n' "$_tm_root" "$_tm_key"
}

clear_turn_marker() {
    _ct_plan=$(active_plan_dir) || return 0
    [ -n "$_ct_plan" ] || return 0
    _ct_marker=$(turn_marker_path "$_ct_plan") || return 0
    rm -f -- "$_ct_marker" 2>/dev/null || :
}

# The nudge is addressed to Claude, so it goes into the model's context as
# additionalContext, not to the user as systemMessage (issue #239).
# systemMessage is documented as a warning shown to the USER, so the model
# never received this instruction and the person received it after every
# matching tool call. emit_session_start above already used the correct shape
# for its event; this path had simply never been moved over.
emit_post_tool_nudge() {
    [ -f "$RESOLVE_PLAN_DIR" ] || exit 0
    _plan_dir=$(active_plan_dir) || exit 0
    [ -n "$_plan_dir" ] && [ -f "${_plan_dir}/task_plan.md" ] || exit 0

    _marker=$(turn_marker_path "$_plan_dir") || _marker=""
    if [ -n "$_marker" ]; then
        [ -e "$_marker" ] && exit 0
        : > "$_marker" 2>/dev/null || :
    fi

    _nudge="[planning-with-files] Update progress.md with what you just did. If a phase is now complete, update task_plan.md status."
    _encoded=$(printf '%s' "$_nudge" | json_string)
    printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"%s"}}\n' \
        "$_encoded"
}

emit_session_start() {
    [ -f "$INJECT_PLAN" ] && [ -f "$RESOLVE_PLAN_DIR" ] || exit 0
    _plan_dir=$(active_plan_dir) || exit 0
    [ -n "$_plan_dir" ] && [ -f "${_plan_dir}/task_plan.md" ] || exit 0

    _catchup=""
    # Prefer `python` on Windows because the WindowsApps `python3` alias can be
    # discoverable yet non-functional. Unix hosts fall through to python3.
    _python=$(command -v python 2>/dev/null || command -v python3 2>/dev/null || true)
    if [ -n "$_python" ] && [ -f "$SESSION_CATCHUP" ]; then
        _catchup=$("$_python" "$SESSION_CATCHUP" --no-history "$PWD" 2>/dev/null) || _catchup=""
    fi
    _context=$(sh "$INJECT_PLAN" --context=userprompt 2>/dev/null) || exit 0
    if [ -n "$_catchup" ] && [ -n "$_context" ]; then
        _output="${_catchup}
${_context}"
    elif [ -n "$_catchup" ]; then
        _output="$_catchup"
    else
        _output="$_context"
    fi
    [ -n "$_output" ] || exit 0
    _encoded=$(printf '%s' "$_output" | json_string)
    printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$_encoded"
}

emit_system_message() {
    _message="$1"
    [ -n "$_message" ] || exit 0
    _encoded=$(printf '%s' "$_message" | json_string)
    printf '{"systemMessage":"%s"}\n' "$_encoded"
}

case "$EVENT" in
    session-start)
        # Startup, resume, clear, and post-compact restoration share the same
        # bounded planning context. Catch-up runs first when Python is present.
        # With no active plan, both operations remain silent.
        # A new session starts a new turn, so any stale throttle marker from a
        # previous run of this session id is cleared here as well (#239).
        clear_turn_marker
        emit_session_start
        ;;
    user-prompt-submit)
        # One user message is one turn. Clearing here re-arms the PostToolUse
        # nudge exactly once per turn (#239). It runs before emit_context
        # because that function exits early on several paths.
        clear_turn_marker
        emit_context "UserPromptSubmit" "userprompt"
        ;;
    pre-tool-use)
        emit_context "PreToolUse" "pretool"
        ;;
    post-tool-use)
        emit_post_tool_nudge
        ;;
    pre-compact)
        [ -f "$INJECT_PLAN" ] || exit 0
        _output=$(sh "$INJECT_PLAN" --context=precompact 2>/dev/null) || exit 0
        emit_system_message "$_output"
        ;;
    stop)
        # Do not read stdin here. gate-stop must receive Claude's original Stop
        # payload so stop_hook_active can prevent recursive continuation.
        [ -f "$GATE_STOP" ] || exit 0
        _output=$(sh "$GATE_STOP" 2>/dev/null) || exit 0
        [ -n "$_output" ] || exit 0
        case "$_output" in
            '{"decision":"block"'*) printf '%s\n' "$_output" ;;
            *) emit_system_message "$_output" ;;
        esac
        ;;
    *)
        exit 0
        ;;
esac

exit 0
