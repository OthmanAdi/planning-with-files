# planning-with-files: Pre-tool-use hook for GitHub Copilot (PowerShell)
# Copilot's PreToolUse command-hook contract supports permissionDecision /
# permissionDecisionReason / modifiedArgs only. Planning context is delivered
# on the documented startup and post-tool routes, not here.
# Always exits 0 — outputs JSON to stdout.

$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
# Read stdin (required — Copilot pipes JSON to stdin)
[void][Console]::In.ReadToEnd()

Write-Output '{}'
exit 0
