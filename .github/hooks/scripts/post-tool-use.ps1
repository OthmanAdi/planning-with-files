# planning-with-files: Post-tool-use hook for GitHub Copilot (PowerShell)
# Reminds the agent to update task_plan.md after tool use.
# Always exits 0 — outputs JSON to stdout.

# Read stdin (required — Copilot pipes JSON to stdin)
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$InputData = [Console]::In.ReadToEnd()

if ($env:PLANNING_DISABLED -eq '1') {
    Write-Output '{}'
    exit 0
}

$output = @{
    hookSpecificOutput = @{
        hookEventName = "PostToolUse"
        additionalContext = "[planning-with-files] Update progress.md with what you just did. If a phase is now complete, update task_plan.md status."
    }
}
$output | ConvertTo-Json -Depth 3 -Compress
exit 0
