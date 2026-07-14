# planning-with-files: set or display the active plan pointer (PowerShell).
#
# Usage:
#   .\set-active-plan.ps1 <plan_id>   — pin .planning\.active_plan to plan_id
#   .\set-active-plan.ps1             — print the current active plan (if any)

param(
    [string]$PlanId = ""
)

$PlanRoot  = Join-Path (Get-Location) ".planning"
$ActiveFile = Join-Path $PlanRoot ".active_plan"

if ($PlanId -eq "") {
    if (Test-Path $ActiveFile) {
        $current = (Get-Content $ActiveFile -Raw -Encoding UTF8).Trim()
        $planDir = Join-Path $PlanRoot $current
        if ($current -ne "" -and (Test-Path $planDir)) {
            Write-Output "Active plan: $current"
            Write-Output "Path: $planDir"
        } elseif ($current -ne "") {
            Write-Output "Active plan pointer: $current (directory not found — stale pointer)"
        } else {
            Write-Output "No active plan set."
        }
    } else {
        Write-Output "No active plan set."
    }
    exit 0
}

$PlanDir = Join-Path $PlanRoot $PlanId

if (-not (Test-Path $PlanDir)) {
    Write-Error "Error: plan directory not found: $PlanDir"
    Write-Error "Run: init-session.sh `"$PlanId`" to create it, or check .planning\ for available plans."
    exit 1
}

if (-not (Test-Path $PlanRoot)) {
    New-Item -ItemType Directory -Path $PlanRoot -Force | Out-Null
}

Set-Content -Path $ActiveFile -Value $PlanId -Encoding UTF8 -NoNewline

Write-Output "Active plan set to: $PlanId"
Write-Output "Path: $PlanDir"
Write-Output ""
Write-Output "To pin this terminal session only:"
Write-Output "`$env:PLAN_ID = '$PlanId'"
