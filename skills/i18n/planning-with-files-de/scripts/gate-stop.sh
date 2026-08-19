#!/bin/sh
# planning-with-files: Stop-hook dispatcher for the v3 completion gate.
#
# Thin wrapper: discover check-complete.sh (sibling first, then the known
# install paths) and run it with --gate, passing the Stop hook's stdin JSON
# through so check-complete can read stop_hook_active and apply the gate
# decision table. check-complete in --gate mode is the host-aware termination
# oracle (W1A); without --gate it keeps the legacy advisory echo behavior.
#
# Always exits with check-complete's exit code. In legacy mode (no .mode file)
# check-complete --gate never blocks, so the Stop event proceeds exactly as v2.

set -u

# issue #195: per-invocation opt-out (PLANNING_DISABLED=1) for one-shot/CI
# sessions that share a cwd with a plan but never opted into it.
[ "${PLANNING_DISABLED:-}" = "1" ] && exit 0

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd 2>/dev/null)" || SCRIPT_DIR="."

TARGET="${SCRIPT_DIR}/check-complete.sh"
if [ ! -f "$TARGET" ] && [ -n "${HOME:-}" ]; then
    # ${HOME:-} keeps set -u from aborting the substitution in CI/Docker images
    # where HOME is unset; without the guard the shell exits before the gate runs.
    TARGET=$(ls "${HOME}/.claude/skills/planning-with-files/scripts/check-complete.sh" \
                "${HOME}/.claude/plugins/marketplaces/planning-with-files/scripts/check-complete.sh" \
                2>/dev/null | head -1)
fi

[ -n "${TARGET:-}" ] && [ -f "$TARGET" ] || exit 0

sh "$TARGET" --gate
