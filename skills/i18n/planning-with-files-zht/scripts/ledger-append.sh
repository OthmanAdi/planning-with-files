#!/bin/sh
# planning-with-files: append one structured entry to the run-ledger (v3).
#
# The run-ledger is the machine layer of progress tracking: an append-only
# JSON-lines file per agent under the active plan dir. Workers append here;
# the orchestrator owns progress.md and task_plan.md. See architecture C3.
#
# Plan-dir resolution (via resolve-plan-dir.sh):
#   1. $PLAN_ID env var -> ./.planning/$PLAN_ID/
#   2. ./.planning/.active_plan
#   3. Newest ./.planning/<dir>/ by mtime
#   4. Legacy: project root (ledger lands beside ./task_plan.md)
#
# Usage:
#   sh scripts/ledger-append.sh <event> <summary> [options]
#
# Arguments:
#   <event>    one of: progress phase_complete error gate_block attest note
#   <summary>  free text, truncated to 200 chars, kept valid UTF-8,
#              newlines stripped
#
# Options:
#   --agent NAME      ledger owner (default "main"); sanitized to [A-Za-z0-9_-]
#   --phase N         phase number/name this entry concerns (default "")
#   --files f1,f2     comma-separated file list recorded as a JSON array
#
# Writes ONE JSON line to <plan-dir>/ledger-<agent>.jsonl:
#   {"tick":N,"ts":"ISO8601Z","agent":"...","phase":"...",
#    "event":"...","summary":"...","files":["..."]}
#
# tick = 1 + max tick across ALL ledger-*.jsonl in the plan dir, so concurrent
# agents share a monotonic counter and the stall detector (gate C2) sees one
# ordered stream.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESOLVER="${SCRIPT_DIR}/resolve-plan-dir.sh"

VALID_EVENTS="progress phase_complete error gate_block attest note"

usage() {
    printf "Usage: %s <event> <summary> [--agent NAME] [--phase N] [--files f1,f2]\n" "$0" >&2
    printf "  event one of: %s\n" "${VALID_EVENTS}" >&2
}

resolve_plan_dir() {
    plan_dir=""
    if [ -f "${RESOLVER}" ]; then
        plan_dir="$(sh "${RESOLVER}" 2>/dev/null)"
    fi
    if [ -n "${plan_dir}" ] && [ -d "${plan_dir}" ]; then
        printf "%s\n" "${plan_dir}"
        return 0
    fi
    # Legacy single-file mode: ledger lives beside ./task_plan.md at root.
    printf "%s\n" "."
    return 0
}

# Sanitize agent name to [A-Za-z0-9_-]; empty result falls back to "main".
sanitize_agent() {
    raw="$1"
    clean="$(printf '%s' "${raw}" | tr -cd 'A-Za-z0-9_-')"
    if [ -z "${clean}" ]; then
        clean="main"
    fi
    printf '%s' "${clean}"
}

# Escape a string for embedding inside a JSON string literal: backslash, double
# quote, and every bare control character JSON forbids. The single tr range
# 0x01-0x1F maps newline, CR, tab, vertical-tab (0x0B), form-feed (0x0C) and the
# rest of 0x01-0x08/0x0E-0x1F to spaces in one pass, matching the PS1
# ConvertTo-JsonString behavior so JSONL stays cross-platform parseable.
json_escape() {
    printf '%s' "$1" \
        | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' \
        | tr '\001-\037' ' '
}

# Emit $1 with any trailing incomplete UTF-8 sequence removed. GNU cut -c
# counts BYTES, so the 200 truncation below can clip a multibyte character and
# leave a tail that strict UTF-8 readers reject, poisoning the whole JSONL
# line. Preferred path: iconv -c drops every malformed byte (glibc, BSD/macOS,
# Git for Windows all ship it); its output is used whenever non-empty because
# GNU libiconv exits nonzero even after -c repaired the tail. Fallback: read
# the last <=4 bytes with od, count trailing continuation bytes (128-191),
# compare against the lead byte's declared length, drop the trailing character
# only when it is incomplete. A complete multibyte character at the boundary
# survives both paths. The fallback repairs truncation damage only; input that
# was invalid UTF-8 before truncation passes through unchanged.
utf8_trim_incomplete() {
    str="$1"
    if [ -z "${str}" ]; then
        return 0
    fi
    if command -v iconv >/dev/null 2>&1; then
        cleaned="$(printf '%s' "${str}" | iconv -f UTF-8 -t UTF-8 -c 2>/dev/null || true)"
        if [ -n "${cleaned}" ]; then
            printf '%s' "${cleaned}"
            return 0
        fi
        # Empty output for non-empty input: iconv missing the -c flag
        # (busybox) or a hard failure. Fall through to the byte-level trim.
    fi
    # The byte-level trim needs od, dd, and wc. On a PATH without them the
    # string passes through unchanged, the pre-repair behavior: an append
    # must never fail or lose the whole summary because a repair tool is
    # missing.
    if ! command -v od >/dev/null 2>&1 || ! command -v dd >/dev/null 2>&1; then
        printf '%s' "${str}"
        return 0
    fi
    # tr -cd normalizes BSD wc padding and yields empty when wc is absent.
    nbytes="$(printf '%s' "${str}" | wc -c 2>/dev/null | tr -cd '0-9')"
    if [ -z "${nbytes}" ] || [ "${nbytes}" -le 0 ]; then
        printf '%s' "${str}"
        return 0
    fi
    win=4
    if [ "${nbytes}" -lt 4 ]; then
        win="${nbytes}"
    fi
    # Last <win> bytes as decimal values, oldest first; a UTF-8 character is
    # at most 4 bytes, so the window always covers the trailing character.
    # shellcheck disable=SC2046
    set -- $(printf '%s' "${str}" | tail -c "${win}" | od -An -tu1 | tr '\n' ' ')
    last=""; prev1=""; prev2=""; prev3=""
    case $# in
        1) last="$1" ;;
        2) last="$2"; prev1="$1" ;;
        3) last="$3"; prev1="$2"; prev2="$1" ;;
        4) last="$4"; prev1="$3"; prev2="$2"; prev3="$1" ;;
        *) printf '%s' "${str}"; return 0 ;;
    esac
    cont=0
    lead=""
    for b in "${last}" "${prev1}" "${prev2}" "${prev3}"; do
        if [ -z "${b}" ]; then
            break
        fi
        if [ "${b}" -ge 128 ] && [ "${b}" -le 191 ]; then
            cont=$((cont + 1))
        else
            lead="${b}"
            break
        fi
    done
    have=$((cont + 1))
    strip=0
    if [ -z "${lead}" ]; then
        # 4+ trailing continuation bytes: invalid before truncation, keep.
        strip=0
    elif [ "${lead}" -lt 128 ]; then
        # Stray continuations after ASCII: invalid before truncation.
        strip="${cont}"
    elif [ "${lead}" -ge 194 ] && [ "${lead}" -le 223 ]; then
        if [ "${have}" -lt 2 ]; then strip="${have}"; fi
    elif [ "${lead}" -ge 224 ] && [ "${lead}" -le 239 ]; then
        if [ "${have}" -lt 3 ]; then strip="${have}"; fi
    elif [ "${lead}" -ge 240 ] && [ "${lead}" -le 244 ]; then
        if [ "${have}" -lt 4 ]; then strip="${have}"; fi
    else
        # 0xC0, 0xC1, 0xF5-0xFF are never valid UTF-8 lead bytes.
        strip="${have}"
    fi
    if [ "${strip}" -le 0 ]; then
        printf '%s' "${str}"
        return 0
    fi
    keep=$((nbytes - strip))
    if [ "${keep}" -le 0 ]; then
        return 0
    fi
    printf '%s' "${str}" | dd bs=1 count="${keep}" 2>/dev/null
    return 0
}

# Largest numeric tick already present across every ledger-*.jsonl in the dir.
# Greps the "tick":N field with sed (no jq), sorts numerically, takes the max.
# Missing/garbage files contribute nothing.
max_tick_in_dir() {
    dir="$1"
    max=0
    for f in "${dir}"/ledger-*.jsonl; do
        [ -f "${f}" ] || continue
        # Extract every "tick":<digits> value, one per line.
        ticks="$(sed -n 's/.*"tick"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p' "${f}" 2>/dev/null)"
        for t in ${ticks}; do
            if [ "${t}" -gt "${max}" ] 2>/dev/null; then
                max="${t}"
            fi
        done
    done
    printf '%s' "${max}"
}

iso_utc() {
    # ISO8601 UTC, second precision. GNU/BSD date both honor -u; fall back to
    # python, then a fixed epoch-zero marker that still parses as ISO8601.
    out="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
    if [ -n "${out}" ]; then printf '%s' "${out}"; return 0; fi
    if command -v python3 >/dev/null 2>&1; then
        out="$(python3 -c "import datetime;print(datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))" 2>/dev/null)"
        if [ -n "${out}" ]; then printf '%s' "${out}"; return 0; fi
    fi
    if command -v python >/dev/null 2>&1; then
        out="$(python -c "import datetime;print(datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'))" 2>/dev/null)"
        if [ -n "${out}" ]; then printf '%s' "${out}"; return 0; fi
    fi
    printf '1970-01-01T00:00:00Z'
}

EVENT="${1:-}"
case "${EVENT}" in
    -h|--help|"")
        usage
        [ -z "${EVENT}" ] && exit 2 || exit 0
        ;;
esac
shift

SUMMARY="${1:-}"
if [ -z "${SUMMARY}" ]; then
    printf "[ledger] missing <summary> argument.\n" >&2
    usage
    exit 2
fi
shift

AGENT="main"
PHASE=""
FILES_CSV=""

while [ $# -gt 0 ]; do
    case "$1" in
        --agent)
            AGENT="${2:-}"
            shift 2 || { printf "[ledger] --agent needs a value.\n" >&2; exit 2; }
            ;;
        --phase)
            PHASE="${2:-}"
            shift 2 || { printf "[ledger] --phase needs a value.\n" >&2; exit 2; }
            ;;
        --files)
            FILES_CSV="${2:-}"
            shift 2 || { printf "[ledger] --files needs a value.\n" >&2; exit 2; }
            ;;
        *)
            printf "[ledger] unknown option: %s\n" "$1" >&2
            usage
            exit 2
            ;;
    esac
done

# Validate event against the allowlist.
valid=0
for e in ${VALID_EVENTS}; do
    if [ "${EVENT}" = "${e}" ]; then valid=1; break; fi
done
if [ "${valid}" -ne 1 ]; then
    printf "[ledger] invalid event '%s' (allowed: %s)\n" "${EVENT}" "${VALID_EVENTS}" >&2
    exit 2
fi

AGENT="$(sanitize_agent "${AGENT}")"

# Truncate summary to 200 BEFORE escaping (200 is a source-text budget).
# GNU cut -c counts bytes and can land mid-codepoint on multibyte input;
# BSD cut -c counts characters and clips cleanly. The trim removes any
# incomplete trailing UTF-8 sequence so the JSONL line stays valid UTF-8.
SUMMARY="$(printf '%s' "${SUMMARY}" | cut -c1-200)"
SUMMARY="$(utf8_trim_incomplete "${SUMMARY}")"

PLAN_DIR="$(resolve_plan_dir)"
LEDGER_FILE="${PLAN_DIR}/ledger-${AGENT}.jsonl"
LOCK_FILE="${PLAN_DIR}/.ledger_lock"

TS="$(iso_utc)"

# Build the files JSON array from the comma-separated list.
FILES_JSON="[]"
if [ -n "${FILES_CSV}" ]; then
    FILES_JSON="["
    first=1
    # Word-split on commas only.
    OLD_IFS="$IFS"
    IFS=','
    for item in ${FILES_CSV}; do
        IFS="$OLD_IFS"
        [ -z "${item}" ] && { IFS=','; continue; }
        esc="$(json_escape "${item}")"
        if [ "${first}" -eq 1 ]; then
            FILES_JSON="${FILES_JSON}\"${esc}\""
            first=0
        else
            FILES_JSON="${FILES_JSON},\"${esc}\""
        fi
        IFS=','
    done
    IFS="$OLD_IFS"
    FILES_JSON="${FILES_JSON}]"
fi

SUMMARY_ESC="$(json_escape "${SUMMARY}")"
PHASE_ESC="$(json_escape "${PHASE}")"

# Append under an advisory flock when available. The single printf write keeps
# the line atomic-enough on platforms without flock (line-buffered, <4KB).
append_line() {
    tick="$(max_tick_in_dir "${PLAN_DIR}")"
    tick=$((tick + 1))
    printf '{"tick":%s,"ts":"%s","agent":"%s","phase":"%s","event":"%s","summary":"%s","files":%s}\n' \
        "${tick}" "${TS}" "${AGENT}" "${PHASE_ESC}" "${EVENT}" "${SUMMARY_ESC}" "${FILES_JSON}" \
        >> "${LEDGER_FILE}"
    printf '%s' "${tick}"
}

if command -v flock >/dev/null 2>&1; then
    # Compute tick AND write while holding the lock so concurrent appenders do
    # not pick the same tick number. The subshell scopes fd 9 to the lock.
    written_tick="$(
        (
            flock -w 5 9 || true
            append_line
        ) 9>"${LOCK_FILE}" 2>/dev/null
    )"
    rm -f "${LOCK_FILE}" 2>/dev/null || true
else
    written_tick="$(append_line)"
fi

printf "[ledger] tick %s -> %s (event=%s agent=%s)\n" \
    "${written_tick:-?}" "${LEDGER_FILE}" "${EVENT}" "${AGENT}"
exit 0
