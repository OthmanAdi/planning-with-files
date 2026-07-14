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
ACTIVE_FILE="${PLAN_ROOT}/.active_plan"

# Plan-id safe-identifier check. Rejects whitespace, path separators, leading
# dots, and empty strings; accepts the YYYY-MM-DD-<slug> shape from
# init-session.sh as well as legacy hand-created names like "alpha" or
# "feature-foo". The intent is to filter garbage content (e.g. a corrupt
# .active_plan file containing only whitespace or random text) without
# enforcing a date prefix that would break backward compatibility.
SLUG_RE='^[A-Za-z0-9_][A-Za-z0-9._-]*$'

slug_is_valid() {
    case "$1" in
        '') return 1 ;;
    esac
    printf "%s" "$1" | grep -Eq "${SLUG_RE}"
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
# the caller treats the candidate as unresolved and falls back safely. If
# canonicalization is unavailable for BOTH paths we fail open (return 0) to keep
# legacy behavior byte-equivalent on minimal shells that lack realpath/readlink
# and python; the SLUG_RE check already blocks traversal in the slug name.
is_within_root() {
    candidate="$1"
    root_real="$(canonicalize "${PWD}")" || root_real=""
    cand_real="$(canonicalize "${candidate}")" || cand_real=""
    if [ -z "${root_real}" ] || [ -z "${cand_real}" ]; then
        return 0
    fi
    case "${cand_real}" in
        "${root_real}"|"${root_real}"/*) return 0 ;;
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
        name="$(basename "${clean}")"
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
