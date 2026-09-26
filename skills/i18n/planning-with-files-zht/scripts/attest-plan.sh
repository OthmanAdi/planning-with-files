#!/bin/sh
# planning-with-files: lock the current task_plan.md content with a SHA-256 attestation.
#
# Use after you finalise (or intentionally edit) a plan. The hooks then refuse
# to inject plan content into the model context if the file diverges from the
# attested hash, surfacing a "[PLAN TAMPERED]" warning instead.
#
# Resolution:
#   1. --target root → legacy ./task_plan.md, or --target <plan-id> → ./.planning/<plan-id>/
#   2. $PLAN_ID env var → ./.planning/$PLAN_ID/
#   3. ./.planning/.active_plan
#   4. Newest ./.planning/<dir>/ by mtime
#   5. Current directory when it is .planning/<valid-slug>/
#   6. Legacy ./task_plan.md at project root
#
# Usage:
#   sh scripts/attest-plan.sh         # attest the active plan
#   sh scripts/attest-plan.sh --show  # print the stored hash
#   sh scripts/attest-plan.sh --clear # remove the attestation (re-open the plan)
#   sh scripts/attest-plan.sh --target root      # attest the legacy root plan
#   sh scripts/attest-plan.sh --target <plan-id> # attest one named plan

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESOLVER="${SCRIPT_DIR}/resolve-plan-dir.sh"

slug_is_valid() {
    case "$1" in
        '') return 1 ;;
        *[!A-Za-z0-9._-]*) return 1 ;;
        [A-Za-z0-9_]*) return 0 ;;
    esac
    return 1
}

resolve_from_slug_cwd() {
    slug_cwd="$(pwd -P 2>/dev/null)" || return 1
    planning_dir="${slug_cwd%/*}"
    [ "${planning_dir##*/}" = ".planning" ] || return 1
    plan_id="${slug_cwd##*/}"
    slug_is_valid "${plan_id}" || return 1
    [ -f "${slug_cwd}/task_plan.md" ] || return 1
    printf "%s\n" "${slug_cwd}/task_plan.md"
}

resolve_plan_file() {
    if [ -n "${target:-}" ]; then
        if [ "${target}" = "root" ]; then
            [ -f "./task_plan.md" ] || return 1
            printf "%s\n" "./task_plan.md"
            return 0
        fi
        slug_is_valid "${target}" || return 1
        target_dir="./.planning/${target}"
        [ -f "${target_dir}/task_plan.md" ] || return 1
        printf "%s\n" "${target_dir}/task_plan.md"
        return 0
    fi

    plan_dir=""
    if [ -f "${RESOLVER}" ]; then
        plan_dir="$(sh "${RESOLVER}" 2>/dev/null)"
        if [ -z "$plan_dir" ] && [ "$(sh "${RESOLVER}" --check-ambiguity 2>/dev/null)" = "PWF_PLAN_AMBIGUOUS_V1" ]; then
            printf "[plan-attest] Multiple plans are available. Set PLAN_ID=<slug>; nothing was attested.\n" >&2
            return 1
        fi
    fi
    if [ -n "${plan_dir}" ] && [ -f "${plan_dir}/task_plan.md" ]; then
        printf "%s\n" "${plan_dir}/task_plan.md"
        return 0
    fi

    # Explicit selectors are bindings, not hints. If the shared resolver
    # rejected one, do not attest a different plan through a cwd fallback.
    if [ -n "${PWF_PLAN_ROOT:-}" ] || [ -n "${PLAN_ID:-}" ]; then
        return 1
    fi

    # An absolute script path does not change the invoking shell's cwd. When
    # that cwd is a slug plan directory, keep slug-mode storage semantics
    # instead of misclassifying its task_plan.md as a legacy root plan.
    slug_plan_file="$(resolve_from_slug_cwd)" || slug_plan_file=""
    if [ -n "${slug_plan_file}" ]; then
        printf "%s\n" "${slug_plan_file}"
        return 0
    fi

    if [ -f "./task_plan.md" ]; then
        printf "%s\n" "./task_plan.md"
        return 0
    fi
    return 1
}

attestation_path_for() {
    plan_file="$1"
    plan_dir="$(dirname "${plan_file}")"
    if [ "${plan_dir}" = "." ]; then
        # Legacy mode: store at project root.
        printf "%s\n" "./.plan-attestation"
    else
        printf "%s\n" "${plan_dir}/.attestation"
    fi
}

compute_hash() {
    target="$1"
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "${target}" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "${target}" | awk '{print $1}'
    else
        printf "ERROR: no sha256 utility available\n" >&2
        return 1
    fi
}

mode="attest"
target=""
case "${1:-}" in
    --show)  mode="show"  ;;
    --clear) mode="clear" ;;
    --target)
        [ "$#" -eq 2 ] || {
            printf "Usage: %s [--show|--clear|--target root|<plan-id>]\n" "$0" >&2
            exit 2
        }
        target="$2"
        ;;
    "")      mode="attest" ;;
    *)
        printf "Usage: %s [--show|--clear|--target root|<plan-id>]\n" "$0" >&2
        exit 2
        ;;
esac

plan_file="$(resolve_plan_file)" || {
    # Name the actual cause. "No task_plan.md found" is true but misleading
    # when the plan exists and an explicit selector was rejected: before #237
    # a mistyped PLAN_ID attested a DIFFERENT plan at rc=0, and an operator
    # who now sees a generic not-found is likely to go looking for the wrong
    # problem. The selectors are bindings, so say which one refused.
    if [ -n "${target:-}" ]; then
        printf "[plan-attest] --target %s did not resolve to a plan. An explicit target is a binding: nothing was attested and no other plan was substituted.\n" "${target}" >&2
    elif [ -n "${PLAN_ID:-}" ]; then
        printf "[plan-attest] PLAN_ID=%s names no plan directory under .planning. An explicit selector is a binding: nothing was attested and no other plan was substituted.\n" "${PLAN_ID}" >&2
    elif [ -n "${PWF_PLAN_ROOT:-}" ]; then
        printf "[plan-attest] PWF_PLAN_ROOT=%s did not resolve to a project root holding a plan. An explicit pin is a binding: nothing was attested and no other plan was substituted.\n" "${PWF_PLAN_ROOT}" >&2
    else
        printf "[plan-attest] No task_plan.md found. Create a plan first.\n" >&2
    fi
    exit 1
}

attestation_file="$(attestation_path_for "${plan_file}")"

case "${mode}" in
    show)
        if [ -f "${attestation_file}" ]; then
            printf "Plan: %s\n" "${plan_file}"
            printf "Attestation: %s\n" "${attestation_file}"
            printf "SHA-256: %s\n" "$(cat "${attestation_file}")"
            # Nonce (security A1.4): if init-session generated a per-plan nonce
            # next to the attestation, surface it. Informational only here; the
            # hooks consume it to build collision-proof BEGIN/END delimiters.
            nonce_file="$(dirname "${attestation_file}")/.nonce"
            if [ -f "${nonce_file}" ]; then
                printf "Nonce: %s\n" "$(tr -d '\r\n[:space:]' < "${nonce_file}" 2>/dev/null)"
            fi
        else
            printf "[plan-attest] No attestation set for %s.\n" "${plan_file}"
            exit 1
        fi
        ;;
    clear)
        if [ -f "${attestation_file}" ]; then
            rm -f "${attestation_file}"
            printf "[plan-attest] Cleared attestation for %s.\n" "${plan_file}"
        else
            printf "[plan-attest] No attestation to clear.\n"
        fi
        ;;
    attest)
        printf "Plan: %s\n" "${plan_file}"
        printf "Attestation: %s\n" "${attestation_file}"
        hash_val="$(compute_hash "${plan_file}")" || exit 1

        # v2.40: protect the write with an advisory flock when available so
        # concurrent legacy-mode sessions (no PLAN_ID, both at the same project
        # root) cannot corrupt the .plan-attestation file mid-write. Atomic
        # rename of a temp file is the real guarantee on POSIX; flock is the
        # cooperative gate around the rename for slow-disk writes.
        #
        # Note: legacy single-file mode is inherently racey across concurrent
        # sessions because both can edit task_plan.md without coordination. The
        # canonical parallel-session pattern is slug-mode under
        # .planning/<slug>/, where each session pins PLAN_ID and gets its own
        # .attestation file. We surface a hint when concurrent activity is
        # detected.
        if [ -f "${attestation_file}" ]; then
            mtime_now="$(date +%s 2>/dev/null || echo 0)"
            mtime_prev="$(stat -c '%Y' "${attestation_file}" 2>/dev/null \
                || stat -f '%m' "${attestation_file}" 2>/dev/null \
                || echo 0)"
            age=$((mtime_now - mtime_prev))
            if [ "${age}" -ge 0 ] && [ "${age}" -lt 30 ] 2>/dev/null; then
                # If we're in legacy mode (root .plan-attestation) and another
                # session just wrote, warn. Slug-mode files in .planning/<slug>/
                # are per-session by construction; no need to warn there.
                case "${attestation_file}" in
                    *./.plan-attestation|*/.plan-attestation)
                        case "${attestation_file}" in
                            *./.planning/*) : ;;  # slug-mode, ignore
                            *)
                                printf "[plan-attest] Note: %s was modified %ss ago by another process.\n" \
                                    "${attestation_file}" "${age}" >&2
                                printf "[plan-attest] For parallel sessions, prefer slug-mode (init-session.sh <name>) so each session gets its own .attestation file.\n" >&2
                                ;;
                        esac
                        ;;
                esac
            fi
        fi

        tmp_file="${attestation_file}.tmp.$$"
        printf "%s\n" "${hash_val}" > "${tmp_file}" 2>/dev/null || {
            printf "[plan-attest] Failed to write %s\n" "${tmp_file}" >&2
            exit 1
        }
        mv_ok=1
        if command -v flock >/dev/null 2>&1; then
            # Advisory lock around the rename. lock_dir is the dir containing
            # the target file. The {} subshell pattern keeps the lock scoped to
            # the mv call.
            lock_dir="$(dirname "${attestation_file}")"
            (
                flock -w 5 9 || true
                mv -f "${tmp_file}" "${attestation_file}"
            ) 9>"${lock_dir}/.attestation.lock" 2>/dev/null || mv_ok=0
            rm -f "${lock_dir}/.attestation.lock" 2>/dev/null
        else
            mv -f "${tmp_file}" "${attestation_file}" 2>/dev/null || mv_ok=0
        fi

        # Integrity gap fix (security A2.1): a failed atomic rename must not be
        # allowed to silently leave a stale attestation when the target already
        # existed. The old fallback only wrote when the file was absent, so a
        # cross-device or permission-denied mv on an existing attestation left
        # the OLD hash in place with a success exit. On mv failure we re-write
        # the intended hash through a second atomic rename (never a bare
        # redirect onto the live file, which would expose torn reads to
        # concurrent verifiers), then verify the on-disk content.
        if [ "${mv_ok}" -eq 0 ] || [ ! -f "${attestation_file}" ]; then
            fb_tmp="${attestation_file}.fb.$$"
            printf "%s\n" "${hash_val}" > "${fb_tmp}" 2>/dev/null \
                && mv -f "${fb_tmp}" "${attestation_file}" 2>/dev/null || {
                rm -f "${fb_tmp}" "${tmp_file}" 2>/dev/null
                printf "[plan-attest] Failed to write attestation %s\n" "${attestation_file}" >&2
                exit 1
            }
        fi
        rm -f "${tmp_file}" 2>/dev/null

        # Read-back verification. Both write paths above are atomic renames, so
        # a concurrent verifier always reads a complete 64-hex hash — either our
        # own or an identical one from a peer attesting the same plan content.
        # A mismatch here therefore means our intended hash genuinely did not
        # land (stale content, failed write); fail loudly with a nonzero exit so
        # callers never trust a stale attestation.
        stored_hash="$(tr -d '\r\n[:space:]' < "${attestation_file}" 2>/dev/null)"
        if [ "${stored_hash}" != "${hash_val}" ]; then
            printf "[plan-attest] Attestation write verification FAILED for %s\n" "${attestation_file}" >&2
            printf "[plan-attest] Expected %s, found %s. The plan is NOT attested.\n" "${hash_val}" "${stored_hash}" >&2
            exit 1
        fi

        short_hash="$(printf "%s" "${hash_val}" | cut -c1-12)"
        printf "[plan-attest] Locked %s\n" "${plan_file}"
        printf "[plan-attest] SHA-256: %s... (stored in %s)\n" "${short_hash}" "${attestation_file}"
        printf "[plan-attest] Hooks will block injection if the file is modified without re-running this command.\n"
        ;;
esac

exit 0
