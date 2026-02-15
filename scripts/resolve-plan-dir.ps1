# Resolve active plan directory under .\.planning\{plan_id}
# Prints resolved directory path to stdout, or nothing if unavailable.

param(
    [string]$PlanRoot = (Join-Path (Get-Location) ".planning")
)

$activeFile = Join-Path $PlanRoot ".active_plan"

if ($env:PLAN_ID) {
    $candidate = Join-Path $PlanRoot $env:PLAN_ID
    if (Test-Path $candidate -PathType Container) {
        Write-Output $candidate
        exit 0
    }
}

if (Test-Path $activeFile) {
    $planId = (Get-Content $activeFile -Raw).Trim()
    if ($planId) {
        $candidate = Join-Path $PlanRoot $planId
        if (Test-Path $candidate -PathType Container) {
            Write-Output $candidate
            exit 0
        }
    }
}

if (Test-Path $PlanRoot -PathType Container) {
    $latest = Get-ChildItem -Path $PlanRoot -Directory |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($latest) {
        Write-Output $latest.FullName
    }
}

exit 0
