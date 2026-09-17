# Shared selected-plan resolver for Cursor's native PowerShell hooks.
# Returns one hashtable with Directory set for a safe named or legacy plan root.
# Empty Directory means the hook must fail closed instead of reading a
# different plan than the selector or active pointer named.
#
# A hashtable, not [pscustomobject]: ConstrainedLanguage mode (WDAC, AppLocker
# script rules) rejects the custom-object cast, which turned every hook fire,
# the legacy root included, into a silent "nothing injected".

$script:CursorPlanResolver = Join-Path (
    Split-Path -Parent $PSScriptRoot
) "skills/planning-with-files/scripts/resolve-plan-dir.ps1"

function New-CursorPlanContext {
    param([string]$Directory, [string]$Status, [string]$Detail = '')
    return @{
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

# Same shape as the resolver's Test-ValidSlug and the sh slug_is_valid.
function Test-CursorValidSlug {
    param([string]$Name)
    if (-not $Name) { return $false }
    return $Name -match '^[A-Za-z0-9_][A-Za-z0-9._-]*$'
}

function Resolve-CursorPlanContext {
    $legacyRoot = (Get-Location).Path
    if ($env:PWF_PLAN_ROOT) {
        if (-not (Test-CursorAbsoluteLocalPath $env:PWF_PLAN_ROOT) -or
            -not (Test-Path -LiteralPath $env:PWF_PLAN_ROOT -PathType Container)) {
            return (New-CursorPlanContext $null 'invalid-pin' $env:PWF_PLAN_ROOT)
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
        # Assign first, then read $?: wrapping the call in @() resets $? to
        # $true on Windows PowerShell 5.1, so the failure check would never fire.
        $resolvedOutput = & $script:CursorPlanResolver 2>$null
        if (-not $?) { throw 'resolver failed' }
        $resolved = @(@($resolvedOutput) | Where-Object { $_ } | Select-Object -First 1)
        if ($resolved.Count -gt 0) {
            return (New-CursorPlanContext ([string]$resolved[0]) 'selected')
        }
        $ambiguity = & $script:CursorPlanResolver -CheckAmbiguity 2>$null
        if (-not $?) { throw 'ambiguity probe failed' }
        if (@($ambiguity) -contains 'PWF_PLAN_AMBIGUOUS_V1') {
            return (New-CursorPlanContext $null 'ambiguous')
        }
    } catch {
        return (New-CursorPlanContext $null 'invalid' 'resolver-error')
    }

    # The resolver named nothing. An explicit PLAN_ID is a binding (issue #237)
    # and fails closed instead of selecting another plan.
    if ($env:PLAN_ID) {
        return (New-CursorPlanContext $null 'invalid-plan-id' $env:PLAN_ID)
    }

    # A pointer that is a directory or a reparse point is an unsafe selector the
    # resolver stopped on, and a valid slug plan the resolver still refused is a
    # containment failure (a junction escaping the project). Neither may fall
    # through to the root plan. A stale pointer text, a dot-named directory or an
    # invalid slug is ignored the way inject-plan.sh ignores it, so the legacy
    # root applies, as on every other route.
    $activeItem = Get-Item -LiteralPath (Join-Path $planRoot '.active_plan') -Force -ErrorAction SilentlyContinue
    if ($activeItem -and ($activeItem.PSIsContainer -or
            (($activeItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0))) {
        return (New-CursorPlanContext $null 'invalid' 'unsafe-pointer')
    }
    if ($planRootExists) {
        $refused = @(Get-ChildItem -LiteralPath $planRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { -not $_.Name.StartsWith('.') } |
            Where-Object { Test-CursorValidSlug $_.Name } |
            Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'task_plan.md') -PathType Leaf } |
            Select-Object -First 1)
        if ($refused.Count -gt 0) {
            return (New-CursorPlanContext $null 'invalid' 'selection-unresolved')
        }
    }
    return (New-CursorPlanContext $legacyRoot 'legacy')
}
