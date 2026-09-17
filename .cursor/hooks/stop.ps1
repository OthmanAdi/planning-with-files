# planning-with-files: Stop hook for Cursor (PowerShell)
# Checks if all phases in task_plan.md are complete.
# Returns followup_message to auto-continue if phases are incomplete.
# Always exits 0 — uses JSON stdout for control.

# Issue #195 opt-out. The disabled branch reproduces this hook's own
# no-plan-file behaviour, so the Cursor protocol shape never changes.
if ($env:PLANNING_DISABLED -eq '1') { exit 0 }

# The OEM code page turns the em-dash into "-" and non-ASCII plan text into "?"
# on both Windows PowerShell 5.1 and pwsh; the plan reaches Cursor as UTF-8.
# ConstrainedLanguage may refuse the assignment, which only keeps the old bytes.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

. (Join-Path $PSScriptRoot "resolve-plan-context.ps1")
$PlanContext = Resolve-CursorPlanContext
$PlanFile = if ($PlanContext.Directory) {
    Join-Path $PlanContext.Directory "task_plan.md"
} else {
    $null
}

if (-not $PlanFile -or -not (Test-Path -LiteralPath $PlanFile -PathType Leaf)) {
    exit 0
}

$content = Get-Content -LiteralPath $PlanFile -Raw

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

# issue #191: no "### Phase" headings -> not phase-structured. Avoid the false
# "0/0 phases done ... continue working" auto-continue message. The sh twin has
# carried this since v3.2.0; this file was the one copy the fix never reached.
if ($TOTAL -eq 0) {
    exit 0
}

if ($COMPLETE -eq $TOTAL -and $TOTAL -gt 0) {
    Write-Host "{`"followup_message`": `"[planning-with-files] ALL PHASES COMPLETE ($COMPLETE/$TOTAL). If the user has additional work, add new phases to task_plan.md before starting.`"}"
    exit 0
} else {
    Write-Host "{`"followup_message`": `"[planning-with-files] Task incomplete ($COMPLETE/$TOTAL phases done). Update progress.md, then read task_plan.md and continue working on the remaining phases.`"}"
    exit 0
}
