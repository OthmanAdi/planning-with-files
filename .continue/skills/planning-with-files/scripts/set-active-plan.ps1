# planning-with-files: set, display, or list the active plan pointer (PowerShell).
#
# Usage:
#   .\set-active-plan.ps1 <plan_id>   - pin .planning\.active_plan to plan_id
#   .\set-active-plan.ps1             - print the current active plan (if any)
#   .\set-active-plan.ps1 --list      - list available named plans and phase counts

param(
    [string]$PlanId = ""
)

$PlanRoot  = Join-Path (Get-Location) ".planning"
$ActiveFile = Join-Path $PlanRoot ".active_plan"

function Get-CurrentActivePlan {
    if (Test-Path $ActiveFile) {
        return (Get-Content $ActiveFile -Raw -Encoding UTF8).Trim()
    }
    return ""
}

function Get-Count($Path, $Pattern, [switch]$Simple) {
    if ($Simple) {
        return ([regex]::Matches((Get-Content $Path -Raw -Encoding UTF8), [regex]::Escape($Pattern))).Count
    }
    return ([regex]::Matches((Get-Content $Path -Raw -Encoding UTF8), $Pattern)).Count
}

function Get-PhaseStatus($PlanFile) {
    $total = Get-Count $PlanFile "### Phase"
    $completePrimary = Get-Count $PlanFile "**Status:** complete" -Simple
    $inProgressPrimary = Get-Count $PlanFile "**Status:** in_progress" -Simple
    $pendingPrimary = Get-Count $PlanFile "**Status:** pending" -Simple
    $completeInline = Get-Count $PlanFile "\[complete\]"
    $inProgressInline = Get-Count $PlanFile "\[in_progress\]"
    $pendingInline = Get-Count $PlanFile "\[pending\]"

    $complete = [Math]::Max($completePrimary, $completeInline)
    $inProgress = [Math]::Max($inProgressPrimary, $inProgressInline)
    $pending = [Math]::Max($pendingPrimary, $pendingInline)
    return "$complete/$total complete, $inProgress in_progress, $pending pending"
}

function Show-PlanList {
    if (-not (Test-Path $PlanRoot)) {
        Write-Output "No planning directory found."
        return
    }

    $active = Get-CurrentActivePlan
    $plans = Get-ChildItem -Path $PlanRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { -not $_.Name.StartsWith(".") -and (Test-Path (Join-Path $_.FullName "task_plan.md")) }

    Write-Output "Available plans:"
    if (-not $plans) {
        Write-Output "No named plans found."
        return
    }

    foreach ($plan in $plans) {
        $marker = ""
        if ($plan.Name -eq $active) { $marker = " [active]" }
        $status = Get-PhaseStatus (Join-Path $plan.FullName "task_plan.md")
        Write-Output "- $($plan.Name)$marker - $status"
    }
}

if ($PlanId -eq "--list" -or $PlanId -eq "-l") {
    Show-PlanList
    exit 0
}

if ($PlanId -eq "--help" -or $PlanId -eq "-h") {
    Write-Output "Usage: set-active-plan.ps1 [--list|PLAN_ID]"
    exit 0
}

if ($PlanId -eq "") {
    $current = Get-CurrentActivePlan
    $planDir = Join-Path $PlanRoot $current
    if ($current -ne "" -and (Test-Path $planDir)) {
        Write-Output "Active plan: $current"
        Write-Output "Path: $planDir"
    } elseif ($current -ne "") {
        Write-Output "Active plan pointer: $current (directory not found - stale pointer)"
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

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($ActiveFile, $PlanId, $utf8NoBom)

Write-Output "Active plan set to: $PlanId"
Write-Output "Path: $PlanDir"
Write-Output ""
Write-Output "To pin this terminal session only:"
Write-Output "`$env:PLAN_ID = '$PlanId'"
