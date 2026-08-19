#!/bin/sh
# planning-with-files: resolve active plan directory.
#
# Resolution order:
#   1. $PLAN_ID env var → ./.planning/$PLAN_ID/ if exists
#   2. ./.planning/.active_plan content → matching dir if exists
#   3. Newest ./.planning/<dir>/ by mtime
#   4. Otherwise empty stdout (caller falls back to legacy ./task_plan.md)
#
# Always exits 0. Never errors out the agent loop.
#
# Usage:
#   PLAN_DIR="$(sh scripts/resolve-plan-dir.sh)"
#   PLAN_FILE="${PLAN_DIR:+$PLAN_DIR/}task_plan.md"

set -u

PLAN_ROOT="${1:-${PWD}/.planning}"

# --- PWF_PLAN_ROOT: absolute plan-root binding (issue #212). ---
# A thread whose cwd is a shared PARENT of the real project (e.g. /workspace
# holding /workspace/project with its own .planning) resolves the parent's
# plan on every call and never sees the nested one. PWF_PLAN_ROOT names the
# project root whose .planning must be used. It is the highest-precedence
# binding: it overrides both the ${PWD} default and the positional argument,
# because an adapter passing ".planning" is spelling out the cwd default, not
# overriding a user's deliberate pin. A pin that is not a directory fails
# CLOSED: the resolver emits nothing, so no caller can be handed the
# ambiguous cwd plan the pin was escaping (the injection routes own the
# user-facing notice; stdout here is the data channel and must stay clean).
# With the variable unset, behavior is byte-identical to the legacy shape.
PWF_ROOT_PIN=""
if [ -n "${PWF_PLAN_ROOT:-}" ]; then
    if [ -d "${PWF_PLAN_ROOT}" ]; then
        PWF_ROOT_PIN="${PWF_PLAN_ROOT}"
        PLAN_ROOT="${PWF_PLAN_ROOT}/.planning"
    else
        exit 0
    fi
fi

ACTIVE_FILE="${PLAN_ROOT}/.active_plan"

# Plan-id safe-identifier check. Rejects whitespace, path separators, leading
# dots, and empty strings; accepts the YYYY-MM-DD-<slug> shape from
# init-session.sh as well as legacy hand-created names like "alpha" or
# "feature-foo". The intent is to filter garbage content (e.g. a corrupt
# .active_plan file containing only whitespace or random text) without
# enforcing a date prefix that would break backward compatibility.
# Pure-sh case patterns; semantics match the previous
# grep -E '^[A-Za-z0-9_][A-Za-z0-9._-]*$' exactly, without a grep fork per
# candidate (the newest-mtime scan calls this once per plan dir).
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

# Portable path canonicalizer. realpath first (Linux, modern coreutils),
# then readlink -f (older GNU), then python3/python os.path.realpath. Prints
# the canonical absolute path on success; prints nothing and returns 1 on a
# full miss so the caller can decide what to do. No python spawn on the happy
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
    if command -v python3 >/dev/null 2>&1; then
        out="$(python3 -c "import os,sys;print(os.path.realpath(sys.argv[1]))" "${target}" 2>/dev/null)" \
            && [ -n "${out}" ] && { printf "%s\n" "${out}"; return 0; }
    fi
    if command -v python >/dev/null 2>&1; then
        out="$(python -c "import os,sys;print(os.path.realpath(sys.argv[1]))" "${target}" 2>/dev/null)" \
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

# Portable mtime resolver. Tries GNU stat, BSD stat, BSD/macOS date -r,
# python3, then perl. Returns "0" on full miss so callers can sort.
mtime_of() {
    target="$1"
    out="$(stat -c '%Y' "${target}" 2>/dev/null)"
    if [ -n "${out}" ]; then printf "%s\n" "${out}"; return 0; fi
    out="$(stat -f '%m' "${target}" 2>/dev/null)"
    if [ -n "${out}" ]; then printf "%s\n" "${out}"; return 0; fi
    out="$(date -r "${target}" +%s 2>/dev/null)"
    if [ -n "${out}" ]; then printf "%s\n" "${out}"; return 0; fi
    if command -v python3 >/dev/null 2>&1; then
        out="$(python3 -c "import os,sys;print(int(os.stat(sys.argv[1]).st_mtime))" "${target}" 2>/dev/null)"
        if [ -n "${out}" ]; then printf "%s\n" "${out}"; return 0; fi
    fi
    if command -v python >/dev/null 2>&1; then
        out="$(python -c "import os,sys;print(int(os.stat(sys.argv[1]).st_mtime))" "${target}" 2>/dev/null)"
        if [ -n "${out}" ]; then printf "%s\n" "${out}"; return 0; fi
    fi
    if command -v perl >/dev/null 2>&1; then
        out="$(perl -e 'print((stat shift)[9])' "${target}" 2>/dev/null)"
        if [ -n "${out}" ]; then printf "%s\n" "${out}"; return 0; fi
    fi
    printf "0\n"
}

resolve_from_env() {
    plan_id="${PLAN_ID:-}"
    slug_is_valid "${plan_id}" || return 1
    candidate="${PLAN_ROOT}/${plan_id}"
    if [ -d "${candidate}" ] && is_within_root "${candidate}"; then
        printf "%s\n" "${candidate}"
        return 0
    fi
    return 1
}

resolve_from_active_file() {
    [ -f "${ACTIVE_FILE}" ] || return 1
    plan_id="$(tr -d '\r\n[:space:]' < "${ACTIVE_FILE}")"
    # UTF-8 BOM is not part of the plan id. POSIX printf octal escapes keep
    # this portable across GNU/BSD sed variants and Git-for-Windows sh.
    utf8_bom="$(printf '\357\273\277')"
    case "${plan_id}" in
        "${utf8_bom}"*) plan_id="${plan_id#"${utf8_bom}"}" ;;
    esac
    slug_is_valid "${plan_id}" || return 1
    candidate="${PLAN_ROOT}/${plan_id}"
    if [ -d "${candidate}" ] && is_within_root "${candidate}"; then
        printf "%s\n" "${candidate}"
        return 0
    fi
    return 1
}

resolve_latest_dir() {
    [ -d "${PLAN_ROOT}" ] || return 1
    # Portable newest-mtime selector. Skips hidden dirs, slug-invalid names,
    # and dirs without task_plan.md (e.g. sessions/).
    latest=""
    latest_mtime=0
    for entry in "${PLAN_ROOT}"/*/; do
        [ -d "${entry}" ] || continue
        clean="${entry%/}"
        name="${clean##*/}"
        case "${name}" in
            .*) continue ;;
        esac
        slug_is_valid "${name}" || continue
        [ -f "${clean}/task_plan.md" ] || continue
        is_within_root "${clean}" || continue
        mtime="$(mtime_of "${clean}")"
        if [ "${mtime}" -gt "${latest_mtime}" ] 2>/dev/null; then
            latest_mtime="${mtime}"
            latest="${clean}"
        fi
    done
    if [ -n "${latest}" ]; then
        printf "%s\n" "${latest}"
        return 0
    fi
    return 1
}

if resolve_from_env; then exit 0; fi
if resolve_from_active_file; then exit 0; fi
if resolve_latest_dir; then exit 0; fi
exit 0
