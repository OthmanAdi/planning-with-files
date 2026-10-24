#!/bin/bash
# planning-with-files: Pre-tool-use hook for GitHub Copilot
# Copilot's PreToolUse command-hook contract supports permissionDecision /
# permissionDecisionReason / modifiedArgs only. Planning context is delivered
# on the documented startup and post-tool routes, not here.
# Always exits 0 — outputs JSON to stdout.

# Read stdin (required — Copilot pipes JSON to stdin)
cat >/dev/null

echo '{}'
exit 0
