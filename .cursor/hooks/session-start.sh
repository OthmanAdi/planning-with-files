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

# JSON-escape the context with the first interpreter that actually runs:
# python3 can be a stub (the Windows Store alias), so python is tried next.
# -I keeps a json.py in the project directory from being imported.
RESPONSE=""
for PYTHON in "$(command -v python3 2>/dev/null)" "$(command -v python 2>/dev/null)"; do
    [ -n "${PYTHON}" ] || continue
    RESPONSE="$(printf '%s' "${CONTEXT}" | "$PYTHON" -I -X utf8 -c 'import json,sys; print(json.dumps({"additional_context": sys.stdin.buffer.read().decode("utf-8", "replace")}))' 2>/dev/null)" || RESPONSE=""
    [ -n "${RESPONSE}" ] && break
done

# Keep the response valid when no Python runs; planning scripts require
# Python for their normal context-injection path as well.
if [ -n "${RESPONSE}" ]; then
    printf '%s\n' "${RESPONSE}"
else
    echo '{}'
fi
exit 0
