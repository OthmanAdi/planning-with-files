#!/bin/sh
# Standalone Claude Code skill-hook entrypoint.
#
# Skill frontmatter command hooks receive their host identity as JSON on stdin;
# Claude Code does not export session_id for child processes.  Keep stdin
# parsing here rather than teaching inject-plan.sh to consume input, because
# that script is also a public direct-call surface.  UserPromptSubmit may emit
# plain context, while PreToolUse and PostToolUse require structured JSON for
# model-visible additionalContext.
#
# Events:
#   userprompt  re-arm this session's nudge, then preserve injector stdout.
#   pretool     serialize injector output as PreToolUse additionalContext.
#   posttool    validate the effective plan, then nudge once per turn.
#   precompact  forward the reminder with the resolved session identity.
#   stop        validate selection, then preserve stdin for the completion gate.
#
# The helper always exits 0.  Missing identity or an unusable cache fails toward
# a repeated reminder, never toward a shared empty-id marker that could silence
# another session.

set -u

EVENT=""
for _arg in "$@"; do
    case "$_arg" in
        --event=*) EVENT="${_arg#--event=}" ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd 2>/dev/null)" || SCRIPT_DIR="."
INJECT_PLAN="${SCRIPT_DIR}/inject-plan.sh"
GATE_STOP="${SCRIPT_DIR}/gate-stop.sh"
CHECK_COMPLETE="${SCRIPT_DIR}/check-complete.sh"

FAST_PATH="${SCRIPT_DIR}/inject-plan.py"

[ "${PLANNING_DISABLED:-}" = "1" ] && exit 0
[ -f "$INJECT_PLAN" ] || exit 0

_pretool_recovery=0
case "$EVENT" in
    userprompt|precompact)
        if [ -n "${XDG_CACHE_HOME:-}" ]; then
            [ ! -d "${XDG_CACHE_HOME}/pwf-pretool" ] || _pretool_recovery=1
        elif [ -n "${HOME:-}" ]; then
            [ ! -d "${HOME}/.cache/pwf-pretool" ] || _pretool_recovery=1
        fi
        ;;
esac

# No planning state where the resolver will look and no selector to validate:
# every event below answers with nothing (and Stop is not consumed until a
# plan is accepted), so answer with nothing now, before any fork. A set
# PLAN_ID or PWF_PLAN_ROOT still gets its refusal notice from the injector.
if [ -z "${PLAN_ID:-}" ] && [ -z "${PWF_PLAN_ROOT:-}" ] \
    && [ ! -f task_plan.md ] && [ ! -d .planning ] && [ "$_pretool_recovery" = 0 ]; then
    exit 0
fi

# Locate a CPython 3 without forking (v3.17.0). Every $(...) and every
# pipeline is a fork, and under Git Bash on Windows a fork costs about 90 ms;
# the old `$(command -v ...)` plus a `-c` version probe cost three of them on
# every event. This walk is stat calls only. Explicit PWF_TRUSTED_PYTHON or
# PYTHON_BIN wins; otherwise python3 is preferred over python across the whole
# PATH so an old distro's Python 2 `python` is never picked while a python3
# exists further down. Only absolute PATH entries are searched (a relative or
# empty entry would let the current repository plant the interpreter) and the
# Microsoft Store aliases are skipped by path: they are discoverable yet refuse
# to run a script. Python stays optional: without it the payload is still
# consumed to EOF, the session id is treated as absent, and the PostToolUse
# throttle deliberately degrades to repeat output.
select_python() {
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
            printf '%s\n' "$_fp_explicit"
            return 0
        fi
    done
    _fp_found=""
    # set -u is active: an unset IFS or PATH must not kill the hook.
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
                _fp_found="${_fp_dir}/${_fp_name}"
                break
            fi
        done
        set +f
        if [ "$_fp_ifs_was_set" = 1 ]; then IFS="$_fp_saved_ifs"; else unset IFS; fi
        if [ -n "$_fp_found" ]; then
            printf '%s\n' "$_fp_found"
            return 0
        fi
    done
    return 1
}

PWF_PYTHON=""
select_python_into_var() {
    # Assign without a subshell: the walk above is the only work this costs.
    _spv_out="$(select_python 2>/dev/null)" || _spv_out=""
    PWF_PYTHON="$_spv_out"
}
select_python_into_var

# Run the injector for one context. scripts/inject-plan.py is a byte-identical
# twin of inject-plan.sh in one interpreter process (about 130 forks fewer per
# event; see the header of hooks/claude-hook.sh). It exits 0 only when its
# stdout is the complete answer, so any other status falls back to the
# reference chain. PWF_FAST_PATH=0 forces the reference chain. -I keeps the
# project directory off sys.path; -B never writes bytecode into the skill dir.
# PWF_SHELL_PWD hands the twin this shell's $PWD spelling so both routes
# derive the same cache slots; MSYS2_ENV_CONV_EXCL keeps Git Bash from
# rewriting it on the way.
run_inject() {
    if [ "${PWF_FAST_PATH:-}" != "0" ] && [ -n "$PWF_PYTHON" ] && [ -f "$FAST_PATH" ]; then
        if PWF_SHELL_PWD="$PWD" \
            MSYS2_ENV_CONV_EXCL="${MSYS2_ENV_CONV_EXCL:+${MSYS2_ENV_CONV_EXCL};}PWF_SHELL_PWD" \
            "$PWF_PYTHON" -I -B "$FAST_PATH" "--context=$1" 2>/dev/null; then
            return 0
        fi
    fi
    sh "$INJECT_PLAN" "--context=$1" 2>/dev/null
}

# Keep the injector's established no-probe boundary.  The preflight token is
# emitted only after a plan exists as a regular contained file, but before
# session admission needs stdin identity.  Rejected paths must not make this
# wrapper execute any interpreter, so the preflight and the refusal notices
# stay on the shell chain; the twin runs only once the plan is accepted.
_preflight="$(sh "$INJECT_PLAN" --context=preflight 2>/dev/null)" || exit 0
if [ "$_preflight" != "PWF_PLAN_ELIGIBLE_V1" ]; then
    # No project data is read by this recovery-only operation. A pre-existing
    # cache may describe context lost while the plan was temporarily absent.
    # Missing helper/interpreter preserves the dependency-free refusal path.
    if [ "$_pretool_recovery" = 1 ] && [ -n "$PWF_PYTHON" ] && [ -f "$FAST_PATH" ]; then
        _recovery_identity=$("$PWF_PYTHON" -I -B "$FAST_PATH" --hook-identity 2>/dev/null) || _recovery_identity=""
        case "$_recovery_identity" in
            *"|"*"|"*)
                _recovery_tail="${_recovery_identity#*|}"
                PWF_SESSION_ID="${_recovery_identity%%|*}" \
                    PWF_PRETOOL_AGENT="${_recovery_tail%%|*}" \
                    PWF_PRETOOL_PROMPT="${_recovery_tail#*|}" \
                    "$PWF_PYTHON" -I -B "$FAST_PATH" --pretool-cache clear >/dev/null 2>&1 || :
                ;;
        esac
    fi
    case "$EVENT" in
        userprompt) sh "$INJECT_PLAN" --context=userprompt 2>/dev/null || : ;;
        precompact) sh "$INJECT_PLAN" --context=precompact 2>/dev/null || : ;;
    esac
    exit 0
fi
PARSED_IDENTITY=""
HOOK_PAYLOAD=""
if [ "$EVENT" = "stop" ]; then
    # Stop's consumer must receive Claude's original JSON so stop_hook_active
    # can prevent recursive continuation.  Stop payloads are bounded host
    # metadata; command substitution preserves the JSON while trimming only
    # insignificant trailing newlines.
    HOOK_PAYLOAD="$(cat 2>/dev/null)" || HOOK_PAYLOAD=""
fi
parse_identity() {
    "$PWF_PYTHON" -I -c '
import hashlib
import json
import re
import sys

SAFE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")

try:
    payload = json.load(sys.stdin)
except (json.JSONDecodeError, OSError, UnicodeError, ValueError):
    raise SystemExit(0)

if not isinstance(payload, dict):
    raise SystemExit(0)
session_id = payload.get("session_id")
if not isinstance(session_id, str) or SAFE.fullmatch(session_id) is None:
    raise SystemExit(0)

agent_id = payload.get("agent_id")
prompt_id = payload.get("prompt_id")
agent_valid = agent_id is None or (
    isinstance(agent_id, str) and SAFE.fullmatch(agent_id) is not None
)
prompt_valid = isinstance(prompt_id, str) and SAFE.fullmatch(prompt_id) is not None

marker_key = ""
if agent_valid and (agent_id is None or prompt_valid):
    digest = hashlib.sha256(b"planning-with-files-skill-turn-v1\0")
    for value in (session_id, agent_id or "main"):
        encoded = value.encode("utf-8", "surrogatepass")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    marker_key = digest.hexdigest()

print("|".join((session_id, marker_key, prompt_id if prompt_valid else "")))
' 2>/dev/null
}

if [ -n "$PWF_PYTHON" ]; then
    # Output is delimiter-safe because every source field is allowlisted.  The
    # marker key includes agent_id when present, so sibling agents in one Claude
    # session cannot suppress one another.  Old hosts without prompt_id still
    # use UserPromptSubmit re-arming for the main agent; subagents without a
    # turn id skip throttling rather than risk a permanent marker.
    if [ "$EVENT" = "stop" ]; then
        PARSED_IDENTITY="$(printf '%s' "$HOOK_PAYLOAD" | parse_identity)" \
            || PARSED_IDENTITY=""
    else
        PARSED_IDENTITY="$(parse_identity)" || PARSED_IDENTITY=""
    fi
else
    # The host writes one complete JSON payload.  Consume it even on the
    # dependency-free fallback so the hook owns exactly one native stdin frame.
    [ "$EVENT" = "stop" ] || cat >/dev/null 2>&1 || :
fi

# Never trust a manually inherited PWF_SESSION_ID over the hook's own payload.
unset PWF_SESSION_ID PWF_PRETOOL_AGENT PWF_PRETOOL_PROMPT
SESSION_ID=""
TURN_KEY=""
PROMPT_ID=""
case "$PARSED_IDENTITY" in
    *"|"*"|"*)
        SESSION_ID="${PARSED_IDENTITY%%|*}"
        _identity_tail="${PARSED_IDENTITY#*|}"
        TURN_KEY="${_identity_tail%%|*}"
        PROMPT_ID="${_identity_tail#*|}"
        PWF_SESSION_ID="$SESSION_ID"
        export PWF_SESSION_ID
        # TURN_KEY already includes the native agent identity and is absent
        # for subagents whose host did not provide a usable prompt identity.
        # Use it as a bounded identity component for the shared view cache.
        PWF_PRETOOL_AGENT="${TURN_KEY:-!invalid}"
        PWF_PRETOOL_PROMPT="${PROMPT_ID:-legacy}"
        export PWF_PRETOOL_AGENT PWF_PRETOOL_PROMPT
        ;;
esac

turn_cache_root() {
    if [ -n "${XDG_CACHE_HOME:-}" ]; then
        printf '%s\n' "${XDG_CACHE_HOME}/pwf-turn"
    elif [ -n "${HOME:-}" ]; then
        printf '%s\n' "${HOME}/.cache/pwf-turn"
    else
        return 1
    fi
}

clear_turn_marker() {
    [ -n "$TURN_KEY" ] || return 0
    _root="$(turn_cache_root 2>/dev/null)" || return 0
    cache_action clear "$_root" >/dev/null 2>&1 || :
}

# Cache state is advisory, but it still must not follow a planted link or use a
# directory controlled by another account.  TURN_KEY exists only when the
# already-selected Python parsed an authentic bounded identity, so use that
# interpreter for lstat/ownership/mode checks before and after directory setup.
cache_action() {
    _cache_action="$1"
    _cache_root="$2"
    "$PWF_PYTHON" -I - "$_cache_action" "$_cache_root" "$TURN_KEY" "$PROMPT_ID" <<'PY'
import os
import secrets
import stat
import sys

action, root, key, prompt_id = sys.argv[1:]
reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
no_follow = getattr(os, "O_NOFOLLOW", 0)
binary = getattr(os, "O_BINARY", 0)


def identity(info):
    return info.st_dev, info.st_ino, info.st_mode


def same_object(left, right):
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def acceptable_directory(info):
    if not stat.S_ISDIR(info.st_mode):
        return False
    if getattr(info, "st_file_attributes", 0) & reparse:
        return False
    return os.name != "posix" or info.st_uid == os.getuid()


def acceptable_file(info):
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 256:
        return False
    if getattr(info, "st_file_attributes", 0) & reparse:
        return False
    return os.name != "posix" or info.st_uid == os.getuid()


temporary = ""
try:
    if not key or len(key) != 64 or any(char not in "0123456789abcdef" for char in key):
        raise OSError("invalid cache key")

    existed = os.path.lexists(root)
    if existed and not acceptable_directory(os.lstat(root)):
        raise OSError("unsafe cache root")
    os.makedirs(root, mode=0o700, exist_ok=True)
    before = os.lstat(root)
    if not acceptable_directory(before):
        raise OSError("unsafe cache root")
    if os.name == "posix":
        os.chmod(root, 0o700)
    after = os.lstat(root)
    # chmod intentionally changes st_mode.  Freeze the directory object across
    # that operation, then use the post-chmod identity for every later check.
    if not acceptable_directory(after) or not same_object(before, after):
        raise OSError("cache root changed")
    if os.name == "posix" and stat.S_IMODE(after.st_mode) & 0o077:
        raise OSError("cache root is not private")

    root_real = os.path.realpath(os.path.abspath(root))
    slot = os.path.join(root_real, key)
    if os.path.commonpath((root_real, slot)) != root_real:
        raise OSError("cache slot escaped")

    if action == "clear":
        if not os.path.lexists(slot):
            raise SystemExit(0)
        slot_info = os.lstat(slot)
        if not acceptable_file(slot_info):
            raise OSError("unsafe cache slot")
        os.unlink(slot)
        raise SystemExit(0)

    if action != "claim":
        raise OSError("unknown cache action")
    desired = ((prompt_id or "legacy") + "\n").encode("ascii", "strict")
    if os.path.lexists(slot):
        slot_before = os.lstat(slot)
        if not acceptable_file(slot_before):
            raise OSError("unsafe cache slot")
        descriptor = os.open(slot, os.O_RDONLY | binary | no_follow)
        try:
            opened = os.fstat(descriptor)
            slot_after = os.lstat(slot)
            if (
                not acceptable_file(opened)
                or identity(slot_before) != identity(opened)
                or identity(slot_after) != identity(opened)
            ):
                raise OSError("cache slot changed")
            previous = os.read(descriptor, 257)
        finally:
            os.close(descriptor)
        if previous == desired:
            print("seen")
            raise SystemExit(0)

    temporary = os.path.join(root_real, f".{key}.{os.getpid()}.{secrets.token_hex(8)}")
    descriptor = os.open(
        temporary,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY | binary | no_follow,
        0o600,
    )
    try:
        os.write(descriptor, desired)
    finally:
        os.close(descriptor)
    root_final = os.lstat(root)
    if not acceptable_directory(root_final) or identity(after) != identity(root_final):
        raise OSError("cache root changed")
    os.replace(temporary, slot)
    temporary = ""
    claimed = os.lstat(slot)
    if not acceptable_file(claimed) or claimed.st_size != len(desired):
        raise OSError("unsafe claimed slot")
    print("claimed")
except (OSError, UnicodeError, ValueError):
    pass
finally:
    if temporary:
        try:
            os.unlink(temporary)
        except OSError:
            pass
PY
}

# Return 0 when the reminder should be emitted, 1 when this turn already saw
# it.  Any unsafe or unusable cache result fails toward the reminder.
claim_turn_marker() {
    [ -n "$TURN_KEY" ] && [ -n "$PWF_PYTHON" ] || return 0
    _root="$(turn_cache_root 2>/dev/null)" || return 0
    _cache_result="$(cache_action claim "$_root" 2>/dev/null)" || _cache_result=""
    [ "$_cache_result" = "seen" ] && return 1
    return 0
}

# Encode the injector's bounded output without interpolating it into a command
# or format string.  Walk characters directly because awk implementations do
# not agree on how many escapes gsub replacement text consumes.  LC_ALL=C
# makes the walk byte-wise: in a UTF-8 locale gawk on Windows walks UTF-16
# units and re-emits a character outside the BMP as a lone surrogate.
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

emit_context_json() {
    _event_name="$1"
    _context="$2"
    [ -n "$_context" ] || return 0
    _encoded="$(printf '%s' "$_context" | json_string)"
    printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"%s"}}\n' \
        "$_event_name" "$_encoded"
}

case "$EVENT" in
    userprompt)
        clear_turn_marker
        [ -f "$INJECT_PLAN" ] || exit 0
        # Plain stdout is explicitly model context for UserPromptSubmit.  Do
        # not capture or reframe it: preserve injector output byte-for-byte.
        run_inject userprompt || :
        ;;
    pretool)
        _context="$(run_inject pretool)" || exit 0
        emit_context_json "PreToolUse" "$_context"
        ;;
    posttool)
        [ -f "$INJECT_PLAN" ] || exit 0
        _decision="$(run_inject validate)" || exit 0
        [ "$_decision" = "PWF_PLAN_ACCEPTED_V1" ] || exit 0
        claim_turn_marker || exit 0
        printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"[planning-with-files] Update progress.md with what you just did. If a phase is now complete, update task_plan.md status."}}'
        ;;
    precompact)
        # PreCompact does not support additionalContext.  Preserve the current
        # plain diagnostic output and pass only the real session identity into
        # resolution; do not invent an unsupported event-specific JSON field.
        run_inject precompact || :
        ;;
    stop)
        _decision="$(run_inject validate)" || exit 0
        [ "$_decision" = "PWF_PLAN_ACCEPTED_V1" ] || exit 0
        if [ -f "$GATE_STOP" ]; then
            printf '%s' "$HOOK_PAYLOAD" | sh "$GATE_STOP" 2>/dev/null || :
        elif [ -f "$CHECK_COMPLETE" ]; then
            # Some existing IDE mirrors ship check-complete.sh without the thin
            # gate-stop.sh dispatcher.  Keep their current Stop capability.
            printf '%s' "$HOOK_PAYLOAD" | sh "$CHECK_COMPLETE" --gate 2>/dev/null || :
        fi
        ;;
    *)
        exit 0
        ;;
esac

exit 0
