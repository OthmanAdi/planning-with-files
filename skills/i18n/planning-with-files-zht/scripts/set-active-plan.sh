#!/bin/sh
# List saved named plans, show the shared pointer, or change that pointer.
# Usage: set-active-plan.sh [--list|-l|--verify-root|PLAN_ID]
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
    awk -v output="${2:-text}" '
        function finish() {
            if (phase) {
                status = primary != "" ? primary : inline_status
                if (primary_count > 1) malformed = 1
                if (status == "complete") complete++
                else if (status == "in_progress") in_progress++
                else if (status == "pending") pending++
            }
            phase = 0; primary = ""; inline_status = ""; primary_count = 0
        }
        {
            line = $0
            if (NR == 1 && output == "json") sub(/^\357\273\277/, "", line)
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
            } else if (phase && line ~ /^ ? ? ?(-[ \t]+)?\*\*(Status:|Estado:|الحالة:|状态：|狀態：)\*\*[ \t]+(complete|in_progress|pending)([ \t]|$)/) {
                primary_count++
                sub(/^ ? ? ?(-[ \t]+)?\*\*(Status:|Estado:|الحالة:|状态：|狀態：)\*\*[ \t]+/, "", line)
                sub(/[ \t].*$/, "", line)
                if (primary == "") primary = line
            } else if (phase && line ~ /^ ? ? ?(-[ \t]+)?\*\*(Status:|Estado:|الحالة:|状态：|狀態：)\*\*/) {
                malformed = 1
            }
        }
        END {
            finish()
            if (output == "json") {
                state = total == 0 ? "empty" : ((malformed || total != complete + in_progress + pending) ? "malformed" : "parsed")
                printf "{\"status\":\"%s\",\"total\":%d,\"complete\":%d,\"in_progress\":%d,\"pending\":%d}", state, total, complete, in_progress, pending
            } else printf "%d/%d complete, %d in_progress, %d pending", complete, total, in_progress, pending
        }
    ' < "$1"
}

# A pre-existing pointer must be a contained regular file before it is
# replaced: a link would be followed or its shared inode overwritten.
pointer_is_unsafe() {
    { [ -e "${ACTIVE_FILE}" ] || [ -L "${ACTIVE_FILE}" ]; } &&
        { [ -L "${ACTIVE_FILE}" ] || [ ! -f "${ACTIVE_FILE}" ] || ! is_within_root "${ACTIVE_FILE}"; }
}

# Constant-time check for callers that are about to create a plan: the
# planning root, when present, must be inside the project, and an existing
# pointer must be replaceable. Nothing is read, listed, or written.
verify_root() {
    if [ -d "${PLAN_ROOT}" ] && ! is_within_root "${PLAN_ROOT}"; then
        printf '%s\n' 'Error: planning directory is outside the project or cannot be verified.' >&2
        return 1
    fi
    if pointer_is_unsafe; then
        printf '%s\n' 'Error: active plan pointer is not a safe file inside the project.' >&2
        return 1
    fi
    return 0
}

current_active() {
    # An unreadable pointer is treated as unset; under set -e the read
    # would otherwise abort listing.
    if [ -f "${ACTIVE_FILE}" ] && [ -r "${ACTIVE_FILE}" ] && is_within_root "${ACTIVE_FILE}"; then
        _current="$(tr '\r' '\n' < "${ACTIVE_FILE}")"
        # Windows editors and older PowerShell defaults can leave a UTF-8 BOM.
        # Treat it as an encoding marker, not part of the shared plan slug.
        _utf8_bom="$(printf '\357\273\277')"
        case "${_current}" in
            "${_utf8_bom}"*) _current="${_current#"${_utf8_bom}"}" ;;
        esac
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
        # A linked plan directory is never a plan (#270): no resolver selects
        # it, so listing it would advertise a PLAN_ID every route refuses.
        [ -L "${_dir}" ] && continue
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

# JSON is an explicit read-only listing mode. Keep all of its work outside the
# existing text/selection paths, including interpreter and resolver discovery.
json_string() {
    printf '%s' "$1" | LC_ALL=C awk '
        BEGIN { printf "\""; for (i=1; i<32; i++) escape[sprintf("%c",i)] = sprintf("\\u%04x",i) }
        { if (NR>1) printf "\\n"; for (i=1; i<=length($0); i++) {
            c=substr($0,i,1)
            if (c=="\\") printf "\\\\"
            else if (c=="\"") printf "\\\""
            else if (c in escape) printf "%s",escape[c]
            else printf "%s",c
        }} END { printf "\"" }
    '
}

file_metadata() {
    _jf_path="$1"; _jf_display="$2"; _jf_state=missing; _jf_mtime=null
    if [ -L "$_jf_path" ]; then _jf_state=excluded
    elif [ -e "$_jf_path" ]; then
        if [ ! -f "$_jf_path" ] || ! is_within_root "$_jf_path"; then _jf_state=excluded
        elif [ ! -r "$_jf_path" ]; then _jf_state=unreadable
        else
            _jf_state=readable
            _jf_mtime=$(stat -c %Y "$_jf_path" 2>/dev/null || stat -f %m "$_jf_path" 2>/dev/null) || _jf_mtime=null
            case "$_jf_mtime" in ''|*[!0-9]*) _jf_mtime=null ;; esac
        fi
    fi
    printf '{"path":%s,"status":"%s","modified_at":%s}' "$(json_string "$_jf_display")" "$_jf_state" "$_jf_mtime"
}

json_phases() {
    _jp_file="$1"
    if [ -L "$_jp_file" ] || [ ! -f "$_jp_file" ] || [ ! -r "$_jp_file" ] || ! is_within_root "$_jp_file"; then
        printf '{"status":"unavailable","total":0,"complete":0,"in_progress":0,"pending":0}'; return
    fi
    _jp_bytes=$(stat -c %s "$_jp_file" 2>/dev/null || stat -f %z "$_jp_file" 2>/dev/null) || _jp_bytes=''
    case "$_jp_bytes" in ''|*[!0-9]*) _jp_bytes=262145 ;; esac
    if [ "$_jp_bytes" -gt 262144 ]; then
        printf '{"status":"too_large","total":0,"complete":0,"in_progress":0,"pending":0}'; return
    fi
    phase_status "$_jp_file" json
}

json_candidate() {
    _jc_dir="$1"; _jc_display="$2"; _jc_id="$3"; _jc_kind="$4"
    if [ "$_jc_kind" = root ]; then _jc_id_json=null; else _jc_id_json=$(json_string "$_jc_id"); fi
    printf '{"kind":"%s","plan_id":%s,"ownership":"unknown","files":{' "$_jc_kind" "$_jc_id_json"
    _jc_comma=''
    for _jc_pair in task_plan:task_plan.md findings:findings.md progress:progress.md; do
        _jc_key=${_jc_pair%%:*}; _jc_name=${_jc_pair#*:}
        printf '%s"%s":%s' "$_jc_comma" "$_jc_key" "$(file_metadata "$_jc_dir/$_jc_name" "$_jc_display/$_jc_name")"
        _jc_comma=,
    done
    printf '},"phases":%s}' "$(json_phases "$_jc_dir/task_plan.md")"
}

json_selection() {
    _js_status=unknown; _js_id=null
    # Listing scope stays cwd. Do not inspect another pinned project's plans.
    if [ -n "${PWF_PLAN_ROOT:-}" ]; then
        case "$PWF_PLAN_ROOT" in
            \\\\*|//*|[A-Za-z]:[!\\/]*|[!/]*)
                case "$PWF_PLAN_ROOT" in [A-Za-z]:[\\/]*) : ;; *) printf '{"status":"rejected","plan_id":null}'; return ;; esac ;;
        esac
        if [ ! -d "$PWF_PLAN_ROOT" ]; then printf '{"status":"rejected","plan_id":null}'; return; fi
        _js_pin=$(canonicalize "$PWF_PLAN_ROOT") || _js_pin=''
        norm_slashes "$_js_pin"; _js_pin="$NORM_OUT"
        if [ "$_js_pin" != "$JSON_PHYSICAL_ROOT" ] && ! [ "$PWF_PLAN_ROOT" -ef . ] 2>/dev/null; then printf '{"status":"outside_scope","plan_id":null}'; return; fi
    fi
    if [ -L "$PLAN_ROOT" ] || { [ -d "$PLAN_ROOT" ] && ! is_within_root "$PLAN_ROOT"; }; then
        _js_status=unknown
        [ -z "${PLAN_ID:-}" ] || _js_status=rejected
        printf '{"status":"%s","plan_id":null}' "$_js_status"; return
    fi
    _js_resolver="$(dirname "$0")/resolve-plan-dir.sh"
    if [ -z "${PLAN_ID:-}" ] && [ -f "$ACTIVE_FILE" ]; then
        _js_pointer_bytes=$(stat -c %s "$ACTIVE_FILE" 2>/dev/null || stat -f %z "$ACTIVE_FILE" 2>/dev/null) || _js_pointer_bytes=9999
        if [ "$_js_pointer_bytes" -gt 256 ]; then printf '{"status":"unknown","plan_id":null}'; return; fi
    fi
    if [ -f "$_js_resolver" ]; then
        _js_dir=$(sh "$_js_resolver" 2>/dev/null) || _js_dir=''
        if [ -n "$_js_dir" ]; then
            norm_slashes "$_js_dir"; _js_dir="$NORM_OUT"
            _js_status=selected; _js_id=$(json_string "${_js_dir##*/}")
        elif [ "$(sh "$_js_resolver" --check-ambiguity 2>/dev/null)" = PWF_PLAN_AMBIGUOUS_V1 ]; then _js_status=ambiguous
        elif [ -n "${PLAN_ID:-}" ]; then _js_status=rejected
        elif [ -f task_plan.md ] && [ ! -L task_plan.md ] && is_within_root task_plan.md; then _js_status=legacy_root
        elif [ -n "${PWF_PLAN_ROOT:-}" ]; then _js_status=rejected
        else _js_status=none
        fi
    fi
    printf '{"status":"%s","plan_id":%s}' "$_js_status" "$_js_id"
}

json_add_candidate() {
    if [ "$JSON_INDEX" -lt "$JSON_OFFSET" ]; then JSON_INDEX=$((JSON_INDEX + 1)); return 0; fi
    if [ "$JSON_RETURNED" -ge "$JSON_LIMIT" ]; then JSON_TRUNCATED=true; JSON_NEXT=$JSON_INDEX; return 1; fi
    _ja_row=$(json_candidate "$1" "$2" "$3" "$4")
    _ja_size=$(printf '%s' "$_ja_row" | LC_ALL=C wc -c)
    if [ $((JSON_USED + _ja_size + 1)) -gt "$JSON_BUDGET" ]; then
        JSON_TRUNCATED=true; JSON_NEXT=$JSON_INDEX
        if [ "$JSON_RETURNED" -eq 0 ]; then
            JSON_SKIPPED=$((JSON_SKIPPED + 1)); JSON_NEXT=$((JSON_INDEX + 1))
        fi
        return 1
    fi
    JSON_ROWS="${JSON_ROWS}${JSON_COMMA}${_ja_row}"; JSON_COMMA=,
    JSON_USED=$((JSON_USED + _ja_size + 1)); JSON_RETURNED=$((JSON_RETURNED + 1)); JSON_INDEX=$((JSON_INDEX + 1))
}

list_plans_json() {
    JSON_PHYSICAL_ROOT=$(canonicalize .) || { printf '{"schema_version":1,"error":"unresolved_project_root"}\n'; return 1; }
    norm_slashes "$JSON_PHYSICAL_ROOT"; JSON_PHYSICAL_ROOT=$NORM_OUT
    JSON_PROJECT=$JSON_PHYSICAL_ROOT
    if [ -x /usr/bin/cygpath.exe ]; then JSON_PROJECT=$(/usr/bin/cygpath.exe -am "$JSON_PROJECT"); fi
    _jl_pointer=null; _jl_pointer_state=missing
    if [ -L "$ACTIVE_FILE" ]; then _jl_pointer_state=excluded
    elif [ -e "$ACTIVE_FILE" ]; then
        _jl_pointer_state=invalid
        if [ -f "$ACTIVE_FILE" ] && [ -r "$ACTIVE_FILE" ] && is_within_root "$ACTIVE_FILE"; then
            _jl_bytes=$(stat -c %s "$ACTIVE_FILE" 2>/dev/null || stat -f %z "$ACTIVE_FILE" 2>/dev/null) || _jl_bytes=9999
            if [ "$_jl_bytes" -le 256 ]; then
                _jl_active=$(current_active)
                if [ -n "$_jl_active" ]; then
                    _jl_pointer=$(json_string "$_jl_active"); _jl_pointer_state=dangling
                    if [ ! -L "$PLAN_ROOT/$_jl_active" ] && [ ! -L "$PLAN_ROOT/$_jl_active/task_plan.md" ] && [ -f "$PLAN_ROOT/$_jl_active/task_plan.md" ] && is_within_root "$PLAN_ROOT/$_jl_active/task_plan.md"; then _jl_pointer_state=present; fi
                fi
            fi
        fi
    fi
    _jl_header="{\"schema_version\":1,\"scope\":{\"project_root\":$(json_string "$JSON_PROJECT"),\"source\":\"cwd\"},\"shared_default\":{\"plan_id\":${_jl_pointer},\"status\":\"${_jl_pointer_state}\"},\"selection\":$(json_selection),\"host_session\":null,\"candidates\":["
    _jl_header_size=$(printf '%s' "$_jl_header" | LC_ALL=C wc -c)
    JSON_BUDGET=$((16383 - _jl_header_size - 512))
    JSON_ROWS=''; JSON_COMMA=''; JSON_INDEX=0; JSON_RETURNED=0; JSON_USED=0; JSON_SKIPPED=0; JSON_NEXT=null; JSON_TRUNCATED=false
    if [ "$JSON_BUDGET" -lt 0 ]; then printf '{"schema_version":1,"error":"project_path_exceeds_output_limit"}\n'; return 1; fi
    _jl_continue=1
    if [ -e task_plan.md ] || [ -L task_plan.md ] || [ -e findings.md ] || [ -e progress.md ]; then
        json_add_candidate . "$JSON_PROJECT" '' root || _jl_continue=0
    fi
    if [ "$_jl_continue" = 1 ] && [ -d "$PLAN_ROOT" ]; then
        if [ -L "$PLAN_ROOT" ] || ! is_within_root "$PLAN_ROOT"; then JSON_SKIPPED=$((JSON_SKIPPED + 1))
        else
            # Slugs are ASCII. C locale gives the same ordering as PS ordinal.
            LC_ALL=C; export LC_ALL
            for _jl_dir in "$PLAN_ROOT"/*; do
                [ -d "$_jl_dir" ] || [ -L "$_jl_dir" ] || continue
                _jl_id=${_jl_dir##*/}; slug_is_valid "$_jl_id" || continue
                if [ -L "$_jl_dir" ] || [ -L "$_jl_dir/task_plan.md" ] || ! is_within_root "$_jl_dir"; then JSON_SKIPPED=$((JSON_SKIPPED + 1)); continue; fi
                [ -f "$_jl_dir/task_plan.md" ] || continue
                json_add_candidate "$_jl_dir" "$JSON_PROJECT/.planning/$_jl_id" "$_jl_id" named || break
            done
        fi
    fi
    printf '%s%s],"limits":{"limit":%s,"offset":%s,"returned":%s,"truncated":%s,"next_offset":%s,"skipped":%s},"warnings":[' "$_jl_header" "$JSON_ROWS" "$JSON_LIMIT" "$JSON_OFFSET" "$JSON_RETURNED" "$JSON_TRUNCATED" "$JSON_NEXT" "$JSON_SKIPPED"
    [ "$JSON_SKIPPED" -eq 0 ] || printf '"linked_unsafe_or_oversized_entries_skipped"'
    printf ']}\n'
}

case "${1:-}:${2:-}" in
    --list:--json|-l:--json)
        shift 2; JSON_LIMIT=20; JSON_OFFSET=0
        while [ "$#" -gt 0 ]; do
            [ "$#" -ge 2 ] || { printf '%s\n' 'Error: a listing option needs an integer value.' >&2; exit 1; }
            case "$2" in ''|*[!0-9]*|0[0-9]*) printf '%s\n' 'Error: listing bounds must be decimal integers.' >&2; exit 1 ;; esac
            [ "${#2}" -le 6 ] || { printf '%s\n' 'Error: listing bound is too large.' >&2; exit 1; }
            case "$1" in --limit) JSON_LIMIT=$2 ;; --offset) JSON_OFFSET=$2 ;; *) printf '%s\n' 'Error: unknown JSON listing option.' >&2; exit 1 ;; esac
            shift 2
        done
        [ "$JSON_LIMIT" -ge 1 ] && [ "$JSON_LIMIT" -le 100 ] || { printf '%s\n' 'Error: limit must be between 1 and 100.' >&2; exit 1; }
        list_plans_json; exit $? ;;
esac

if [ "$#" -gt 1 ]; then
    printf '%s\n' 'Error: list plans, verify the root, or set PLAN_ID in separate calls.' >&2
    exit 1
fi

case "${1:-}" in
    --list|-l) list_plans; exit $? ;;
    --verify-root) verify_root; exit $? ;;
    --help|-h)
        printf '%s\n' 'Usage: set-active-plan.sh [--list|--verify-root|PLAN_ID]' \
            'Lists saved named plans in the current project without selecting a plan.' \
            '--list --json [--limit 1..100] [--offset N] emits bounded metadata, including root files.' \
            '--verify-root checks the planning root and pointer without listing or selecting.'
        exit 0 ;;
esac

if [ "${1:-}" = '' ]; then
    if [ -d "${PLAN_ROOT}" ] && ! is_within_root "${PLAN_ROOT}"; then
        printf '%s\n' 'Error: planning directory is outside the project or cannot be verified.' >&2
        exit 1
    fi
    plan_id="$(current_active)"
    if [ -n "${plan_id}" ] && [ -d "${PLAN_ROOT}/${plan_id}" ] && [ ! -L "${PLAN_ROOT}/${plan_id}" ] && is_within_root "${PLAN_ROOT}/${plan_id}"; then
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
if [ -L "${PLAN_DIR}" ]; then
    printf '%s\n' "Error: plan directory is a symlink or junction and no route selects it: ${PLAN_DIR}" >&2
    exit 1
fi
if ! is_within_root "${PLAN_ROOT}" || ! is_within_root "${PLAN_DIR}"; then
    printf '%s\n' 'Error: plan directory is outside the project or cannot be verified.' >&2
    exit 1
fi
if pointer_is_unsafe; then
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
# mktemp creates the file 0600; the shared pointer must stay readable by
# every session, so apply the caller's umask instead (=rw without a who
# clause is umask-relative in POSIX chmod).
chmod =rw "${temp_file}" 2>/dev/null || true
if ! mv -f "${temp_file}" "${ACTIVE_FILE}"; then
    printf '%s\n' 'Error: could not replace the active plan pointer.' >&2
    exit 1
fi
trap - EXIT HUP INT TERM
printf '%s\n' "Active plan set to: ${PLAN_ID}" "Path: ${PLAN_DIR}" '' \
    'To pin this terminal session only:' "  export PLAN_ID=${PLAN_ID}"
