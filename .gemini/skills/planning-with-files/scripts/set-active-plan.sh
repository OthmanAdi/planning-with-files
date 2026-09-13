#!/bin/sh
# List saved named plans, show the shared pointer, or change that pointer.
# Usage: set-active-plan.sh [--list|-l|PLAN_ID]
# Operates on the current project; listing never binds a host or injects data.
set -eu
PLAN_ROOT="${PWD}/.planning"
ACTIVE_FILE="${PLAN_ROOT}/.active_plan"
PWF_ROOT_PIN=""

# Use the resolver canonicalization policy without running plan selection.
slug_is_valid() {
    case "$1" in
        '') return 1 ;;
        *[!A-Za-z0-9._-]*) return 1 ;;
        [A-Za-z0-9_]*) return 0 ;;
    esac
    return 1
}

# Pure-sh backslash-to-forward-slash normalizer; result lands in $NORM_OUT.
# Windows-native coreutils builds (e.g. C:\Program Files\coreutils on PATH
# ahead of Git's usr/bin) canonicalize MSYS-style /c/... input to C:\-style
# backslash output. The containment prefix match below is written with forward
# slashes, so without this normalization every canonical pair mismatches and
# resolution silently fails. On POSIX systems paths contain no backslash and
# this is the identity. A literal backslash in a Unix filename normalizes to
# "/" and at worst fails containment — the safe direction. No subshell, no
# fork: plain parameter expansion in a loop.
norm_slashes() {
    NORM_OUT=""
    _ns_rest="$1"
    while :; do
        case "${_ns_rest}" in
            *\\*)
                NORM_OUT="${NORM_OUT}${_ns_rest%%\\*}/"
                _ns_rest="${_ns_rest#*\\}"
                ;;
            *)
                NORM_OUT="${NORM_OUT}${_ns_rest}"
                break
                ;;
        esac
    done
}

# Return true when a candidate path names the Microsoft Store WindowsApps
# directory. Store app aliases are not stable interpreter binaries and may
# present as executable while refusing script execution. Matching is
# case-insensitive and works before or after Windows slash normalization.
is_windowsapps_path() {
    norm_slashes "$1"
    case "${NORM_OUT}" in
        [Ww][Ii][Nn][Dd][Oo][Ww][Ss][Aa][Pp][Pp][Ss]|\
        [Ww][Ii][Nn][Dd][Oo][Ww][Ss][Aa][Pp][Pp][Ss]/*|\
        */[Ww][Ii][Nn][Dd][Oo][Ww][Ss][Aa][Pp][Pp][Ss]|\
        */[Ww][Ii][Nn][Dd][Oo][Ww][Ss][Aa][Pp][Pp][Ss]/*) return 0 ;;
    esac
    return 1
}

# Select only an interpreter path the caller explicitly trusted.
# PWF_TRUSTED_PYTHON is preferred; PYTHON_BIN remains a compatibility alias.
# PATH discovery is intentionally forbidden because resolver hooks can run in
# repositories that control PATH. Windows-native absolute paths are converted
# with Git Bash's fixed system cygpath, never a PATH-selected shim.
trusted_python() {
    for _tp_candidate in "${PWF_TRUSTED_PYTHON:-}" "${PYTHON_BIN:-}"; do
        [ -n "${_tp_candidate}" ] || continue
        case "${_tp_candidate}" in
            \\\\*|//*) continue ;;
            [A-Za-z]:[\\/]*)
                is_windowsapps_path "${_tp_candidate}" && continue
                _tp_cygpath="/usr/bin/cygpath.exe"
                [ -f "${_tp_cygpath}" ] && [ -x "${_tp_cygpath}" ] || continue
                _tp_candidate="$("${_tp_cygpath}" -u "${_tp_candidate}" 2>/dev/null)" \
                    || continue
                ;;
            /*) ;;
            *) continue ;;
        esac
        is_windowsapps_path "${_tp_candidate}" && continue
        [ -f "${_tp_candidate}" ] || continue
        [ -x "${_tp_candidate}" ] || continue
        printf "%s\n" "${_tp_candidate}"
        return 0
    done
    return 1
}

# Portable path canonicalizer. realpath first (Linux, modern coreutils),
# then readlink -f (older GNU), then an explicitly trusted Python interpreter.
# Prints the canonical absolute path on success; prints nothing and returns 1
# on a full miss so containment fails closed. No Python spawn on the happy
# path: realpath/readlink cover Linux, WSL, Git-Bash, and modern macOS.
canonicalize() {
    target="$1"
    if command -v realpath >/dev/null 2>&1; then
        out="$(realpath "${target}" 2>/dev/null)" && [ -n "${out}" ] && {
            printf "%s\n" "${out}"; return 0; }
    fi
    if command -v readlink >/dev/null 2>&1; then
        out="$(readlink -f "${target}" 2>/dev/null)" && [ -n "${out}" ] && {
            printf "%s\n" "${out}"; return 0; }
    fi
    _canonical_python="$(trusted_python)" || _canonical_python=""
    if [ -n "${_canonical_python}" ]; then
        out="$("${_canonical_python}" -I -c "import os,sys;print(os.path.realpath(sys.argv[1]))" "${target}" 2>/dev/null)" \
            && [ -n "${out}" ] && { printf "%s\n" "${out}"; return 0; }
    fi
    return 1
}

# Containment guard (security A1.3): a resolved plan dir must canonicalize to a
# path under the project root (the CWD the script runs from). A symlink inside
# a valid slug dir pointing at /etc or outside the workspace would otherwise let
# the hooks hash and inject an arbitrary file. On any violation we return 1 so
# the caller treats the candidate as unresolved and falls back safely.
#
# The root canonicalizes via the relative token "." rather than the $PWD
# string. On some Windows/MSYS setups (8.3 short names, the /tmp mount alias)
# realpath("$PWD") and realpath(relative-candidate) resolve through different
# code paths and land on differently-spelled-but-equal targets, so the prefix
# match below fails and resolution silently goes dark. "." resolves through
# the same physical-cwd path candidates already use (same fix inject-plan.sh
# received earlier; the resolver kept the $PWD form until now). Both sides are
# backslash-normalized before comparison for Windows-native canonicalizers.
# The root is computed once per run: the newest-mtime scan calls this guard
# per plan dir, and each canonicalize costs a process spawn on Windows.
#
# With a PWF_PLAN_ROOT pin (issue #212) containment is checked against THAT
# root instead of the cwd: candidates arrive ${PWF_PLAN_ROOT}/-prefixed, so
# both sides canonicalize through the same path spelling. Unpinned keeps the
# relative "." root — byte-identical to the legacy check.
ROOT_REAL=""
ROOT_REAL_SET=0
is_within_root() {
    candidate="$1"
    if [ "${ROOT_REAL_SET}" = "0" ]; then
        ROOT_REAL="$(canonicalize "${PWF_ROOT_PIN:-.}")" || ROOT_REAL=""
        norm_slashes "${ROOT_REAL}"
        ROOT_REAL="${NORM_OUT}"
        ROOT_REAL_SET=1
    fi
    # Canonicalize the candidate through its cwd-RELATIVE form whenever it
    # lives under ${PWD}. The candidate string is built from ${PWD} (an MSYS
    # long-form spelling), while the root canonicalizes from "." (the process
    # cwd, which a caller may have set with an 8.3 short-form string). A
    # Windows-native realpath does not unify those spellings, so canonicalizing
    # both sides from the same cwd base is the only spelling-stable comparison.
    # The emitted result keeps the original absolute candidate — only the
    # containment check uses the relative form.
    # Pinned resolution skips the rewrite: candidate and root then share the
    # ${PWF_PLAN_ROOT} spelling, so both canonicalize directly from it.
    if [ -n "${PWF_ROOT_PIN}" ]; then
        check_target="${candidate}"
    else
        case "${candidate}" in
            "${PWD}"/*) check_target=".${candidate#"${PWD}"}" ;;
            *) check_target="${candidate}" ;;
        esac
    fi
    cand_real="$(canonicalize "${check_target}")" || cand_real=""
    norm_slashes "${cand_real}"
    cand_real="${NORM_OUT}"
    if [ -z "${ROOT_REAL}" ] || [ -z "${cand_real}" ]; then
        # Slug validation blocks textual traversal, but only successful
        # canonicalization can rule out a symlink/junction escape.
        return 1
    fi
    case "${cand_real}" in
        "${ROOT_REAL}"|"${ROOT_REAL}"/*) return 0 ;;
        *) return 1 ;;
    esac
}

# Each phase contributes at most one status. An explicit Status line wins
# over an inline heading marker. Fenced examples and unrelated sections are
# not phases. Keep this parser aligned with the PowerShell helper.
phase_status() {
    awk '
        function finish() {
            if (phase) {
                status = primary != "" ? primary : inline_status
                if (status == "complete") complete++
                else if (status == "in_progress") in_progress++
                else if (status == "pending") pending++
            }
            phase = 0; primary = ""; inline_status = ""
        }
        {
            line = $0
            sub(/\r$/, "", line)
            trimmed = line
            sub(/^ */, "", trimmed)
            if (line ~ /^ ? ? ?```/ || line ~ /^ ? ? ?~~~/) {
                marker = substr(trimmed, 1, 1)
                run = 0
                while (substr(trimmed, run + 1, 1) == marker) run++
                if (fence == "") { fence = marker; fence_length = run }
                else if (marker == fence && run >= fence_length && substr(trimmed, run + 1) ~ /^[ \t]*$/) fence = ""
                next
            }
            if (fence != "") next
            if (line ~ /^ ? ? ?###[ \t]+(Phase|Fase|المرحلة|阶段|階段)[ \t]+[0-9]+([^0-9A-Za-z_]|$)/) {
                finish(); phase = 1; total++
                if (match(line, /\[(complete|in_progress|pending)\]/))
                    inline_status = substr(line, RSTART + 1, RLENGTH - 2)
            } else if (line ~ /^ ? ? ?(###|##|#)([ \t]|$)/) {
                finish()
            } else if (phase && primary == "" && line ~ /^ ? ? ?(-[ \t]+)?\*\*(Status:|Estado:|الحالة:|状态：|狀態：)\*\*[ \t]+(complete|in_progress|pending)([ \t]|$)/) {
                sub(/^ ? ? ?(-[ \t]+)?\*\*(Status:|Estado:|الحالة:|状态：|狀態：)\*\*[ \t]+/, "", line)
                sub(/[ \t].*$/, "", line)
                primary = line
            }
        }
        END {
            finish()
            printf "%d/%d complete, %d in_progress, %d pending", complete, total, in_progress, pending
        }
    ' < "$1"
}

current_active() {
    if [ -f "${ACTIVE_FILE}" ] && is_within_root "${ACTIVE_FILE}"; then
        _current="$(tr '\r' '\n' < "${ACTIVE_FILE}")"
        slug_is_valid "${_current}" && printf '%s\n' "${_current}"
    fi
    return 0
}

list_plans() {
    if [ ! -d "${PLAN_ROOT}" ]; then
        printf '%s\n' 'No planning directory found.'
        return 0
    fi
    if ! is_within_root "${PLAN_ROOT}"; then
        printf '%s\n' 'Error: planning directory is outside the project or cannot be verified.' >&2
        return 1
    fi
    _active="$(current_active)"
    _found=0
    printf '%s\n' 'Available plans:'
    for _dir in "${PLAN_ROOT}"/*; do
        [ -d "${_dir}" ] || continue
        _id="${_dir##*/}"
        slug_is_valid "${_id}" || continue
        is_within_root "${_dir}" || continue
        _plan_file="${_dir}/task_plan.md"
        [ -f "${_plan_file}" ] && [ -r "${_plan_file}" ] || continue
        is_within_root "${_plan_file}" || continue
        _status="$(phase_status "${_plan_file}")" || continue
        _marker=''
        if [ "${_id}" = "${_active}" ]; then _marker=' [active]'; fi
        printf '%s\n' "- ${_id}${_marker} - ${_status}"
        _found=1
    done
    if [ "${_found}" -eq 0 ]; then
        printf '%s\n' 'No named plans found.'
    else
        printf '%s\n' '[active] marks the shared default pointer. Set PLAN_ID to pin a session.'
    fi
}

if [ "$#" -gt 1 ]; then
    printf '%s\n' 'Error: list plans or set PLAN_ID in separate calls.' >&2
    exit 1
fi

case "${1:-}" in
    --list|-l) list_plans; exit $? ;;
    --help|-h)
        printf '%s\n' 'Usage: set-active-plan.sh [--list|PLAN_ID]' \
            'Lists saved named plans in the current project without selecting a plan.'
        exit 0 ;;
esac

if [ "${1:-}" = '' ]; then
    if [ -d "${PLAN_ROOT}" ] && ! is_within_root "${PLAN_ROOT}"; then
        printf '%s\n' 'Error: planning directory is outside the project or cannot be verified.' >&2
        exit 1
    fi
    plan_id="$(current_active)"
    if [ -n "${plan_id}" ] && [ -d "${PLAN_ROOT}/${plan_id}" ] && is_within_root "${PLAN_ROOT}/${plan_id}"; then
        printf '%s\n' "Active plan: ${plan_id}" "Path: ${PLAN_ROOT}/${plan_id}"
    elif [ -n "${plan_id}" ]; then
        printf '%s\n' "Active plan pointer: ${plan_id} (directory not found or outside project - stale pointer)"
    else
        printf '%s\n' 'No active plan set.'
    fi
    exit 0
fi

PLAN_ID="$1"
if ! slug_is_valid "${PLAN_ID}"; then
    printf '%s\n' 'Error: invalid plan ID. Use a named directory under .planning.' >&2
    exit 1
fi
PLAN_DIR="${PLAN_ROOT}/${PLAN_ID}"
if [ ! -d "${PLAN_DIR}" ]; then
    printf '%s\n' "Error: plan directory not found: ${PLAN_DIR}" \
        "Run: init-session.sh \"${PLAN_ID}\" to create it, or use --list to see available plans." >&2
    exit 1
fi
if ! is_within_root "${PLAN_ROOT}" || ! is_within_root "${PLAN_DIR}"; then
    printf '%s\n' 'Error: plan directory is outside the project or cannot be verified.' >&2
    exit 1
fi
# A pre-existing pointer must itself be a contained regular file before writing.
if { [ -e "${ACTIVE_FILE}" ] || [ -L "${ACTIVE_FILE}" ]; } &&
    { [ -L "${ACTIVE_FILE}" ] || [ ! -f "${ACTIVE_FILE}" ] || ! is_within_root "${ACTIVE_FILE}"; }; then
    printf '%s\n' 'Error: active plan pointer is not a safe file inside the project.' >&2
    exit 1
fi
# Replace the pointer atomically instead of truncating a possible hardlink.
# mktemp creates a private, exclusive file beside the destination.
temp_file="$(mktemp "${PLAN_ROOT}/.active_plan.XXXXXX")" || {
    printf '%s\n' 'Error: could not create the active plan pointer.' >&2
    exit 1
}
trap 'rm -f "${temp_file}"' EXIT
trap 'exit 1' HUP INT TERM
printf '%s\n' "${PLAN_ID}" > "${temp_file}"
if ! mv -f "${temp_file}" "${ACTIVE_FILE}"; then
    printf '%s\n' 'Error: could not replace the active plan pointer.' >&2
    exit 1
fi
trap - EXIT HUP INT TERM
printf '%s\n' "Active plan set to: ${PLAN_ID}" "Path: ${PLAN_DIR}" '' \
    'To pin this terminal session only:' "  export PLAN_ID=${PLAN_ID}"
