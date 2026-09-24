# planning-with-files: Post-tool-use hook for Cursor (PowerShell)
# Injects a reminder after file modifications using postToolUse's context field.

# Issue #195 opt-out. The disabled branch reproduces this hook's own
# no-plan-file behaviour, so the Cursor protocol shape never changes.
if ($env:PLANNING_DISABLED -eq '1') {
    Write-Output '{}'
    exit 0
}

# The OEM code page turns the em-dash into "-" and non-ASCII plan text into "?"
# on both Windows PowerShell 5.1 and pwsh; the plan reaches Cursor as UTF-8.
# ConstrainedLanguage may refuse the assignment, which only keeps the old bytes.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

try {
    . (Join-Path $PSScriptRoot "resolve-plan-context.ps1")
    $PlanContext = Resolve-CursorPlanContext
    $PlanFile = if ($PlanContext.Directory) {
        Join-Path $PlanContext.Directory "task_plan.md"
    } else {
        $null
    }

    if ($PlanFile -and (Test-Path -LiteralPath $PlanFile -PathType Leaf)) {
        $response = @{
            additional_context = "[planning-with-files] Update progress.md with what you just did. If a phase is now complete, update task_plan.md status."
        }
        Write-Output ($response | ConvertTo-Json -Compress)
    } else {
        Write-Output '{}'
    }
} catch {
    Write-Output '{}'
}
exit 0
