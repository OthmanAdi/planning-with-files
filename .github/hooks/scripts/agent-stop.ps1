# planning-with-files: Agent stop hook for GitHub Copilot (PowerShell)
# Checks if all phases in task_plan.md are complete.
# Injects continuation context if phases are incomplete.
# Always exits 0 — outputs JSON to stdout.

# Read stdin (required — Copilot pipes JSON to stdin)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$InputData = [Console]::In.ReadToEnd()

$PlanFile = "task_plan.md"

if (-not (Test-Path $PlanFile)) {
    Write-Output '{}'
    exit 0
}

$content = Get-Content $PlanFile -Raw -Encoding UTF8

# Count total phases
$TOTAL = ([regex]::Matches($content, "### Phase")).Count

# Check for **Status:** format first
$COMPLETE = ([regex]::Matches($content, "\*\*Status:\*\* complete")).Count
$IN_PROGRESS = ([regex]::Matches($content, "\*\*Status:\*\* in_progress")).Count
$PENDING = ([regex]::Matches($content, "\*\*Status:\*\* pending")).Count

# Fallback: check for [complete] inline format
if ($COMPLETE -eq 0 -and $IN_PROGRESS -eq 0 -and $PENDING -eq 0) {
    $COMPLETE = ([regex]::Matches($content, "\[complete\]")).Count
    $IN_PROGRESS = ([regex]::Matches($content, "\[in_progress\]")).Count
    $PENDING = ([regex]::Matches($content, "\[pending\]")).Count
}

if ($TOTAL -eq 0) {
    Write-Output '{}'
    exit 0
}

if ($COMPLETE -eq $TOTAL -and $TOTAL -gt 0) {
    $msg = "[planning-with-files] ALL PHASES COMPLETE ($COMPLETE/$TOTAL). If the user has additional work, add new phases to task_plan.md before starting."
    $output = @{
        hookSpecificOutput = @{
            hookEventName = "AgentStop"
            additionalContext = $msg
        }
    }
    $output | ConvertTo-Json -Depth 3 -Compress
    exit 0
}

$msg = "[planning-with-files] Task incomplete ($COMPLETE/$TOTAL phases done). Update progress.md, then read task_plan.md and continue working on the remaining phases."
$output = @{
    hookSpecificOutput = @{
        hookEventName = "AgentStop"
        additionalContext = $msg
    }
}
$output | ConvertTo-Json -Depth 3 -Compress
exit 0
