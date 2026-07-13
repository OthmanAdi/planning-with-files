#!/bin/sh
# planning-with-files: global Codex hook resolver entry point.
#
# The resolver implementation is owned by the installed skill. Keep this file
# as a thin forwarding shim so Hook and helper callers cannot silently drift
# onto different slug/containment rules again.

set -u

HOOK_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd)" || exit 0
CANONICAL_RESOLVER="${HOOK_DIR}/../skills/planning-with-files/scripts/resolve-plan-dir.sh"

[ -f "${CANONICAL_RESOLVER}" ] || exit 0
exec sh "${CANONICAL_RESOLVER}" "$@"
