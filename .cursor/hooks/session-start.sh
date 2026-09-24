#!/usr/bin/env bash
# Inject the selected plan as initial session context using Cursor's sessionStart schema.

if [ "${PLANNING_DISABLED:-}" = "1" ]; then
    echo '{}'
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTEXT="$(sh "${SCRIPT_DIR}/user-prompt-submit.sh")"
if [ -z "${CONTEXT}" ]; then
    echo '{}'
    exit 0
fi

if command -v python3 >/dev/null 2>&1; then
    RESPONSE="$(printf '%s' "${CONTEXT}" | python3 -c 'import json,sys; print(json.dumps({"additional_context": sys.stdin.buffer.read().decode("utf-8", "replace")}))' 2>/dev/null)" || RESPONSE=""
    if [ -n "${RESPONSE}" ]; then
        printf '%s\n' "${RESPONSE}"
    else
        echo '{}'
    fi
else
    # Keep the response valid when Python is unavailable; planning scripts
    # require Python for their normal context-injection path as well.
    echo '{}'
fi
exit 0
