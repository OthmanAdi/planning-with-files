# Shared selected-plan resolver for Cursor's native PowerShell hooks.
# Returns one object with Directory set for a safe named or legacy plan root.
# Empty Directory means the hook must fail closed instead of reading a
# different plan than the selector or active pointer named.

$script:CursorPlanResolver = Join-Path (
    Split-Path -Parent $PSScriptRoot
) "skills/planning-with-files/scripts/resolve-plan-dir.ps1"

function New-CursorPlanContext {
    param([string]$Directory, [string]$Status, [string]$Detail = '')
    return [pscustomobject]@{
        Directory = $Directory
        Status = $Status
        Detail = $Detail
    }
}

function Test-CursorAbsoluteLocalPath {
    param([string]$Path)
    if (-not $Path -or $Path.StartsWith('\\') -or $Path.StartsWith('//')) {
        return $false
    }
    if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
        return $Path -match '^[A-Za-z]:[\\/]'
    }
    return [IO.Path]::IsPathRooted($Path)
}

function Resolve-CursorPlanContext {
    $legacyRoot = (Get-Location).Path
    if ($env:PWF_PLAN_ROOT) {
        if (-not (Test-CursorAbsoluteLocalPath $env:PWF_PLAN_ROOT) -or
            -not (Test-Path -LiteralPath $env:PWF_PLAN_ROOT -PathType Container)) {
            return (New-CursorPlanContext $null 'invalid' $env:PWF_PLAN_ROOT)
        }
        $legacyRoot = $env:PWF_PLAN_ROOT
    }

    $planRoot = Join-Path $legacyRoot '.planning'
    $planRootExists = Test-Path -LiteralPath $planRoot -PathType Container
    if (-not $env:PLAN_ID -and -not $planRootExists) {
        return (New-CursorPlanContext $legacyRoot 'legacy')
    }
    if (-not (Test-Path -LiteralPath $script:CursorPlanResolver -PathType Leaf)) {
        return (New-CursorPlanContext $null 'invalid' 'resolver-missing')
    }

    try {
        $resolvedOutput = @(& $script:CursorPlanResolver 2>$null)
        if (-not $?) { throw 'resolver failed' }
        $resolved = @($resolvedOutput | Where-Object { $_ } |
            Select-Object -First 1)
        if ($resolved.Count -gt 0) {
            return (New-CursorPlanContext ([string]$resolved[0]) 'selected')
        }
        $ambiguity = @(& $script:CursorPlanResolver -CheckAmbiguity 2>$null)
        if (-not $?) { throw 'ambiguity probe failed' }
        if ($ambiguity -contains 'PWF_PLAN_AMBIGUOUS_V1') {
            return (New-CursorPlanContext $null 'ambiguous')
        }
    } catch {
        return (New-CursorPlanContext $null 'invalid' 'resolver-error')
    }

    # Explicit or persisted selection state must never fall through to a
    # different root plan when the shared resolver refused it.
    $activeFile = Join-Path $planRoot '.active_plan'
    $selectionExists = [bool]$env:PLAN_ID -or
        [bool](Get-Item -LiteralPath $activeFile -Force -ErrorAction SilentlyContinue)
    if (-not $selectionExists -and $planRootExists) {
        $selectionExists = [bool](Get-ChildItem -LiteralPath $planRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object {
                Test-Path -LiteralPath (Join-Path $_.FullName 'task_plan.md') -PathType Leaf
            } | Select-Object -First 1)
    }
    if ($selectionExists) {
        return (New-CursorPlanContext $null 'invalid' 'selection-unresolved')
    }

    return (New-CursorPlanContext $legacyRoot 'legacy')
}
