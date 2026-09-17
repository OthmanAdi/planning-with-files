# planning-with-files: Pre-tool-use hook for Cursor (PowerShell)
# Reads the first 30 lines of task_plan.md to keep goals in context.
# Returns {"decision": "allow"} — this hook never blocks tools.

# Issue #195 opt-out. The disabled branch reproduces this hook's own
# no-plan-file behaviour, so the Cursor protocol shape never changes.
if ($env:PLANNING_DISABLED -eq '1') {
    Write-Output '{"decision": "allow"}'
    exit 0
}

# The OEM code page turns the em-dash into "-" and non-ASCII plan text into "?"
# on both Windows PowerShell 5.1 and pwsh; the plan reaches Cursor as UTF-8.
# ConstrainedLanguage may refuse the assignment, which only keeps the old bytes.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

# The protocol response is printed from finally: a missing helper or a
# profile that sets $ErrorActionPreference = 'Stop' must not end the hook
# without it. This hook never blocks a tool.
try {
    . (Join-Path $PSScriptRoot "resolve-plan-context.ps1")
    $PlanContext = Resolve-CursorPlanContext
    $PlanFile = if ($PlanContext.Directory) {
        Join-Path $PlanContext.Directory "task_plan.md"
    } else {
        $null
    }

    if ($PlanFile -and (Test-Path -LiteralPath $PlanFile -PathType Leaf)) {
        Get-Content -LiteralPath $PlanFile -TotalCount 30 | Write-Host
    }
} catch {
    # A planning error is never a reason to hold a tool.
} finally {
    Write-Output '{"decision": "allow"}'
}
exit 0
