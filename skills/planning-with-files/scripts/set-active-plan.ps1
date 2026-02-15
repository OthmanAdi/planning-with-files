# Set active plan pointer in .\.planning\.active_plan
# Usage: .\set-active-plan.ps1 <plan_id>

param(
    [Parameter(Mandatory = $true)]
    [string]$PlanId
)

$planRoot = Join-Path (Get-Location) ".planning"
$planDir = Join-Path $planRoot $PlanId
$activeFile = Join-Path $planRoot ".active_plan"

if (-not (Test-Path $planDir -PathType Container)) {
    Write-Error "Plan directory not found: $planDir"
    exit 1
}

New-Item -ItemType Directory -Path $planRoot -Force | Out-Null
Set-Content -Path $activeFile -Value $PlanId -Encoding UTF8

Write-Host "Active plan set to: $PlanId"
Write-Host "Active file: $activeFile"
