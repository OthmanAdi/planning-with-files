#!/bin/sh
# planning-with-files: lock the current task_plan.md content with a SHA-256 attestation.
#
# Use after you finalise (or intentionally edit) a plan. The hooks then refuse
# to inject plan content into the model context if the file diverges from the
# attested hash, surfacing a "[PLAN TAMPERED]" warning instead.
#
# Resolution:
#   1. --target root or <plan-id> → root or named plan under $PWF_PLAN_ROOT (default: cwd)
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

# An echoed selector must not forge output: a newline or an escape sequence
# in PLAN_ID could otherwise print a fake status line.
printable() {
    # The sed step covers C1 controls, which are two bytes in UTF-8.
    c1_lead="$(printf '\302')"
    c1_low="$(printf '\200')"
    c1_high="$(printf '\237')"
    printf '%s' "$1" | LC_ALL=C tr '\000-\037\177' '?' \
        | LC_ALL=C sed "s/${c1_lead}[${c1_low}-${c1_high}]/?/g"
}

pwf_plan_root_is_accepted() {
    case "${PWF_PLAN_ROOT:-}" in
        \\\\*|//*|[A-Za-z]:[!\\/]*) return 1 ;;
        /*|[A-Za-z]:[\\/]*) ;;
        *) return 1 ;;
    esac
    [ -d "${PWF_PLAN_ROOT}" ]
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
            target_root="."
            if [ -n "${PWF_PLAN_ROOT:-}" ]; then
                # Match the shared resolver's supported absolute local pins.
                # A valid project-root junction is intentional, so resolve it.
                pwf_plan_root_is_accepted || return 1
                target_root="$(cd "${PWF_PLAN_ROOT}" 2>/dev/null && pwd -P)" || return 1
            fi
            [ ! -L "${target_root}/task_plan.md" ] || return 1
            [ -f "${target_root}/task_plan.md" ] || return 1
            printf "%s\n" "${target_root}/task_plan.md"
            return 0
        fi
        slug_is_valid "${target}" || return 1
        # Reuse the binding, project-pin and containment rules. A flag replaces
        # PLAN_ID for this call only; it does not change the shared pointer.
        [ -f "${RESOLVER}" ] || return 1
        target_dir="$(PLAN_ID="${target}" sh "${RESOLVER}" 2>/dev/null)" || return 1
        [ -n "${target_dir}" ] || return 1
        # Use the shell's physical path spelling: native Windows backslashes
        # make sha256sum prefix its output with an escaped-filename marker.
        target_dir="$(cd "${target_dir}" 2>/dev/null && pwd -P)" || return 1
        [ ! -L "${target_dir}/task_plan.md" ] || return 1
        [ -f "${target_dir}/task_plan.md" ] || return 1
        printf "%s\n" "${target_dir}/task_plan.md"
        return 0
    fi

    plan_dir=""
    if [ -f "${RESOLVER}" ]; then
        plan_dir="$(sh "${RESOLVER}" 2>/dev/null)"
        if [ -z "$plan_dir" ] && [ "$(sh "${RESOLVER}" --check-ambiguity 2>/dev/null)" = "PWF_PLAN_AMBIGUOUS_V1" ]; then
            return 2
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
    if [ "${target:-}" = "root" ]; then
        printf "%s\n" "${plan_dir}/.plan-attestation"
    elif [ "${plan_dir}" = "." ]; then
        # Legacy mode: store at project root.
        printf "%s\n" "./.plan-attestation"
    else
        printf "%s\n" "${plan_dir}/.attestation"
    fi
}

compute_hash() {
    target="$1"
    if command -v sha256sum >/dev/null 2>&1; then
        # GNU sha256sum prefixes the hash with a backslash when the path holds
        # one, which a native Windows PWF_PLAN_ROOT does.
        sha256sum "${target}" | awk '{ sub(/^\\/, "", $1); print $1 }'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "${target}" | awk '{print $1}'
    else
        printf "ERROR: no sha256 utility available\n" >&2
        return 1
    fi
}

mode="attest"
target=""
usage_error() {
    printf "Usage: %s [--show|--clear|--enable-checkbox-only|--checkbox-only] [--target root|<plan-id>]\n" "$0" >&2
    exit 2
}
case "${1:-}" in
    --clear|--show)
        [ "$#" -eq 1 ] || usage_error
        mode="${1#--}"
        shift ;;
    --enable-checkbox-only|--checkbox-only)
        mode="${1#--}"
        shift ;;
esac
if [ "${1:-}" = "--target" ]; then
    [ "$#" -eq 2 ] && [ -n "$2" ] || usage_error
    target="$2"
    shift 2
fi
[ "$#" -eq 0 ] || usage_error

plan_file="$(resolve_plan_file)"
resolve_status=$?
if [ "${resolve_status}" -ne 0 ]; then
    # Name the actual cause. "No task_plan.md found" is true but misleading
    # when the plan exists and an explicit selector was rejected: before #237
    # a mistyped PLAN_ID attested a DIFFERENT plan at rc=0, and an operator
    # who now sees a generic not-found is likely to go looking for the wrong
    # problem. The selectors are bindings, so say which one refused.
    if [ "${resolve_status}" -eq 2 ]; then
        printf "[plan-attest] Multiple plans are available. Set PLAN_ID=<slug>; nothing was attested.\n" >&2
    elif [ -n "${target:-}" ]; then
        printf "[plan-attest] --target %s did not resolve to a plan. An explicit target is a binding: nothing was attested and no other plan was substituted.\n" "$(printable "${target}")" >&2
    elif [ -n "${PWF_PLAN_ROOT:-}" ] && ! pwf_plan_root_is_accepted; then
        printf "[plan-attest] PWF_PLAN_ROOT=%s did not resolve to a project root holding a plan. An explicit pin is a binding: nothing was attested and no other plan was substituted.\n" "$(printable "${PWF_PLAN_ROOT}")" >&2
    elif [ -n "${PLAN_ID:-}" ]; then
        printf "[plan-attest] PLAN_ID=%s names no plan directory under .planning. An explicit selector is a binding: nothing was attested and no other plan was substituted.\n" "$(printable "${PLAN_ID}")" >&2
    elif [ -n "${PWF_PLAN_ROOT:-}" ]; then
        printf "[plan-attest] PWF_PLAN_ROOT=%s did not resolve to a project root holding a plan. An explicit pin is a binding: nothing was attested and no other plan was substituted.\n" "$(printable "${PWF_PLAN_ROOT}")" >&2
    else
        printf "[plan-attest] No task_plan.md found. Create a plan first.\n" >&2
    fi
    exit 1
fi

attestation_file="$(attestation_path_for "${plan_file}")"

checkbox_state() {
    command -v python3 >/dev/null 2>&1 || {
        printf '[plan-attest] Checkbox enrollment requires POSIX Python 3.\n' >&2
        return 1
    }
    python3 -I - "$1" "${plan_file}" "${attestation_file##*/}" <<'PWF_CHECKBOX_PY'
# Private cache records contain byte offsets and filesystem identities, never plan text.
import hashlib
import json
import os
import re
import secrets
import stat
import sys
from contextlib import ExitStack

mode, plan_path, attest = sys.argv[1:]
def refuse(reason):
    raise ValueError(reason)

def run(stack):
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
        refuse("Checkbox enrollment requires POSIX Python 3 with no-follow file descriptors.")
    dirs = os.O_DIRECTORY | os.O_RDONLY | os.O_NOFOLLOW
    def directory(path):
        fd = os.open("/", dirs)
        stack.callback(os.close, fd)
        for part in os.path.abspath(path).split("/"):
            if part:
                fd = os.open(part, dirs, dir_fd=fd)
                stack.callback(os.close, fd)
        return fd
    parent_path = os.path.abspath(os.path.dirname(plan_path))
    parent = os.open(".", dirs) if os.path.dirname(plan_path) == "." else directory(parent_path)
    if os.path.dirname(plan_path) == ".":
        stack.callback(os.close, parent)
    # macOS exposes /var through /private/var. Canonicalize the home path
    # before opening each component; never follow links inside the cache.
    home = directory(os.path.realpath(os.path.expanduser("~")))
    cache_name = ".pwf-checkbox-v1"
    if mode == "enable-checkbox-only":
        try:
            os.mkdir(cache_name, 0o700, dir_fd=home)
        except FileExistsError:
            pass
    try:
        cache = os.open(cache_name, dirs, dir_fd=home)
    except FileNotFoundError:
        if mode == "forget":
            return
        refuse("No checkbox enrollment. Review the plan and use --enable-checkbox-only.")
    stack.callback(os.close, cache)
    attrs = os.fstat(cache)
    if attrs.st_uid != os.geteuid() or attrs.st_mode & 0o077:
        refuse("Checkbox cache must be an owner-only directory.")
    key = hashlib.sha256(os.fsencode(os.path.join(parent_path, attest))).hexdigest()
    def read_file(fd, name, private=False):
        flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
        with os.fdopen(os.open(name, flags, dir_fd=fd), "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                refuse("Expected a regular, singly linked file.")
            if private and (info.st_uid != os.geteuid() or info.st_mode & 0o077):
                refuse("Unsafe permissions on checkbox enrollment.")
            data = stream.read()
            after = os.fstat(stream.fileno())
            if (info.st_size, info.st_ctime_ns) != (after.st_size, after.st_ctime_ns):
                refuse("File changed during read. Retry.")
            return data, info
    def identity(info):
        return [info.st_dev, info.st_ino, info.st_ctime_ns]
    def generation(info, digest):
        # Rename may change ctime. These values survive publishing the staged
        # inode and distinguish a fresh strict attestation of identical bytes.
        return [info.st_dev, info.st_ino, info.st_mtime_ns, digest.decode("ascii").strip()]
    def stage(fd, data):
        tmp = ".pwf-" + secrets.token_hex(16)
        writer = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=fd)
        def cleanup():
            try:
                os.unlink(tmp, dir_fd=fd)
            except FileNotFoundError:
                pass
        stack.callback(cleanup)
        with os.fdopen(writer, "wb") as output:
            output.write(data)
            output.flush()
            info = os.fstat(output.fileno())
        return tmp, info
    record = None
    try:
        raw, _ = read_file(cache, key, private=True)
        record = json.loads(raw)
        if not isinstance(record, dict) or record.get("format") != "pwf-checkbox-1":
            refuse("Unrecognized checkbox metadata.")
    except FileNotFoundError:
        pass
    if mode == "forget":
        if record is not None:
            os.unlink(key, dir_fd=cache)
        return
    snapshot, plan_info = read_file(parent, "task_plan.md")
    try:
        stored, digest_info = read_file(parent, attest)
        if not re.fullmatch(rb"[0-9a-f]{64}(?:\r?\n)?", stored):
            refuse("Refusing to replace an unrecognized attestation file.")
    except FileNotFoundError:
        stored = digest_info = None
    digest = hashlib.sha256(snapshot).hexdigest().encode("ascii") + b"\n"
    boxes = {}
    # Only standalone, flush-left "- [ ]" and "* [ ]" with one ASCII space
    # after the bullet are eligible. Indented tasks stay under strict approval.
    # A list-shaped line inside a Markdown code fence is example text.
    fence = None
    comment = False
    offset = 0
    for line in snapshot.split(b"\n"):
        # A UTF-8 BOM is ignored by Markdown only at the document start.
        # Keep offsets into the original byte string for digest reconstruction.
        bom = 3 if offset == 0 and line.startswith(b"\xef\xbb\xbf") else 0
        content = line[bom:]
        marker = re.match(rb" {0,3}(?:[-*+][ ]{1,4}|[0-9]{1,9}[.)][ ]{1,4})?(`{3,}|~{3,})(.*)", content)
        if fence is not None:
            closing = re.fullmatch(rb" {0,3}(`{3,}|~{3,})[ \t]*\r?", content)
            if closing and closing[1].startswith(fence):
                fence = None
        elif comment:
            if b"-->" in content:
                comment = False
                if content.partition(b"-->")[2].strip():
                    refuse("Ambiguous HTML after comment. Review the plan manually.")
        elif marker and (marker[1].startswith(b"~") or b"`" not in marker[2]):
            fence = marker[1]
        elif b"<!--" in content:
            prefix, _, tail = content.partition(b"<!--")
            if prefix.strip():
                refuse("Ambiguous HTML comment. Review the plan manually.")
            comment = b"-->" not in tail
            if not comment and tail.partition(b"-->")[2].strip():
                refuse("Ambiguous HTML after comment. Review the plan manually.")
        else:
            if re.match(rb"^[ \t]*(?:[-*+]|[0-9]{1,9}[.)])?[ \t]*<(?:/?[a-zA-Z]|[!?])", content):
                refuse("Raw HTML blocks require manual re-attestation.")
            box = re.match(rb"[-*] \[([ x])\](?=[ \t]|\r?$)", content)
            if box:
                boxes[offset + bom + box.start(1)] = box[1]
        offset += len(line) + 1
    def check_plan_generation():
        current = os.stat("task_plan.md", dir_fd=parent, follow_symlinks=False)
        if identity(current) != identity(plan_info):
            refuse("Plan changed during attestation. Retry.")
    previous = None
    if record and digest_info:
        selected = generation(digest_info, stored)
        previous = next((entry for entry in record.get("generations", [])
                         if entry["id"] == selected), None)
    if mode == "checkbox-only":
        if previous is None:
            refuse("No current checkbox enrollment. Review the plan and use --enable-checkbox-only.")
        prior = bytearray(snapshot)
        for offset in previous["unchecked"]:
            if boxes.get(offset) == b"x":
                prior[offset] = ord(" ")
        if hashlib.sha256(prior).hexdigest().encode("ascii") != stored.rstrip(b"\r\n"):
            refuse("Changes exceed checkbox-only scope.")
        if digest.rstrip() == stored.rstrip():
            check_plan_generation()
            print("[plan-attest] Plan already matches attestation.")
            return
    check_plan_generation()
    digest_tmp, staged = stage(parent, digest)
    candidate = {"id": generation(staged, digest),
                 "unchecked": [pos for pos, value in boxes.items() if value == b" "]}
    entries = [previous, candidate] if previous else [candidate]
    intent = {"format": "pwf-checkbox-1", "generations": entries}
    cache_tmp, _ = stage(cache, json.dumps(intent).encode("ascii"))
    # Until the digest rename, its previous generation remains authoritative.
    # Afterwards the candidate record is already usable, even across a retry.
    os.replace(cache_tmp, key, src_dir_fd=cache, dst_dir_fd=cache)
    check_plan_generation()
    os.replace(digest_tmp, attest, src_dir_fd=parent, dst_dir_fd=parent)
    current, written = read_file(parent, attest)
    if generation(written, current) != candidate["id"]:
        refuse("Attestation changed before verification.")
    check_plan_generation()
    print("[plan-attest] Attested selected plan with checkbox enrollment.")
try:
    with ExitStack() as stack:
        run(stack)
except (OSError, ValueError, KeyError, TypeError) as error:
    sys.exit("[plan-attest] " + str(error))

PWF_CHECKBOX_PY
}

if [ "${mode}" != show ]; then
    # Create in a private directory, then atomically claim the shared name
    # with link(2). Never open an existing lock (which might be a link or FIFO).
    writer_dir="$(dirname "${attestation_file}")"
    case "${mode}" in
        checkbox-only|enable-checkbox-only)
            project_root="$(cd "${PWF_PLAN_ROOT:-.}" && pwd -P)" || exit 1
            expected_slug="${writer_dir##*/}"
            case "${target:-}" in
                root) expected_slug="" ;;
                "") expected_slug="${PLAN_ID:-${expected_slug}}" ;;
                *) expected_slug="${target}" ;;
            esac
            cd -P "${writer_dir}" || exit 1
            selected_dir="$(pwd -P)" || exit 1
            if [ "${selected_dir}" != "${project_root}" ]; then
                slug_is_valid "${expected_slug}" && [ "${selected_dir}" = "${project_root}/.planning/${expected_slug}" ] || exit 1
            elif [ -n "${target:-${PLAN_ID:-}}" ] && [ "${target:-}" != root ]; then
                exit 1
            fi
            writer_dir=.
            plan_file=./task_plan.md
            attestation_file="./${attestation_file##*/}"
            ;;
    esac
    writer_name="${attestation_file##*/}.writer-lock"
    staging="$(mktemp -d "${writer_dir}/.pwf-writer.XXXXXXXX")" || exit 1
    claim="${staging}/${writer_name}"
    : > "${claim}" || exit 1
    trap 'rm -f "${claim}"; rmdir "${staging}"' EXIT
    attempts=0
    lock_path="${writer_dir}/${writer_name}"
    owner="${staging##*/}"
    if ln "${claim}" "${staging}/probe" 2>/dev/null && [ "${claim}" -ef "${staging}/probe" ]; then
        lock_type=link
    else
        case "$(uname -s)" in
            MINGW*|MSYS*|CYGWIN*)
                lock_type=windows
                if command -v pwsh >/dev/null 2>&1; then windows_shell=pwsh
                elif command -v powershell.exe >/dev/null 2>&1; then windows_shell=powershell.exe
                else printf '[plan-attest] Native PowerShell is required for this volume.\n' >&2; exit 1
                fi
                native_lock="$(cygpath -aw "${lock_path}")" || exit 1 ;;
            *) lock_type=directory ;;
        esac
    fi
    rm -f "${staging}/probe"
    claim_writer() {
        case "${lock_type}" in
            link) ln "${claim}" "${writer_dir}/" 2>/dev/null ;;
            directory)
                # On POSIX mkdir is exclusive, including on volumes without hard links.
                (umask 077; mkdir "${lock_path}") 2>/dev/null || return 1
                mkdir "${lock_path}/${owner}" || return 1 ;;
            windows)
                PWF_CLAIM_PATH="${native_lock}" PWF_CLAIM_OWNER="${owner}" \
                "${windows_shell}" -NoProfile -NonInteractive -Command '
                    $ErrorActionPreference = "Stop"
                    try {
                        $s = [IO.File]::Open($env:PWF_CLAIM_PATH, "CreateNew", "Write", "None")
                        try {
                            $data = [Text.Encoding]::ASCII.GetBytes($env:PWF_CLAIM_OWNER)
                            $s.Write($data, 0, $data.Length)
                        } finally { $s.Dispose() }
                    } catch { exit 1 }' ;;
        esac
    }
    until claim_writer; do
        attempts=$((attempts + 1))
        if [ "${attempts}" -ge 50 ]; then
            printf '[plan-attest] Cannot acquire attestation writer lock.\n' >&2
            exit 1
        fi
        sleep 0.1
    done
    release_writer() {
        case "${lock_type}" in
            link) [ "${claim}" -ef "${lock_path}" ] && rm -f "${lock_path}" ;;
            directory) rmdir "${lock_path}/${owner}" && rmdir "${lock_path}" ;;
            windows)
                if [ -f "${lock_path}" ] && [ ! -L "${lock_path}" ] &&
                   [ "$(cat "${lock_path}")" = "${owner}" ]; then rm -f "${lock_path}"; fi ;;
        esac
        rm -f "${claim}"
        rmdir "${staging}"
    }
    trap release_writer EXIT
    trap 'exit 1' HUP INT TERM
    case "${mode}" in
        checkbox-only|enable-checkbox-only)
            checkbox_state "${mode}"
            exit "$?" ;;
    esac
fi

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
            rm -f "${attestation_file}" || exit 1
            printf "[plan-attest] Cleared attestation for %s.\n" "${plan_file}"
        else
            printf "[plan-attest] No attestation to clear.\n"
        fi
        if [ -d "${HOME:-}/.pwf-checkbox-v1" ]; then
            checkbox_state forget || printf '[plan-attest] Optional checkbox cache cleanup was unavailable.\n' >&2
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
