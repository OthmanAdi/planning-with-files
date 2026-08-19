# planning-with-files: resolve active plan directory (PowerShell mirror).
#
# Resolution order matches scripts/resolve-plan-dir.sh:
#   1. $env:PLAN_ID -> .\.planning\$PLAN_ID\
#   2. .\.planning\.active_plan content
#   3. Newest .\.planning\<dir>\ by LastWriteTime
#   4. Empty (legacy fallback to .\task_plan.md handled by caller)
#
# v3.8.0 parity with the sh resolver: slug validation on every branch, the
# newest-dir scan requires task_plan.md inside the candidate (a sessions/ or
# artifacts/ dir must never win), and containment fails CLOSED when
# canonicalization fails. Only successful canonicalization can rule out a
# junction/symlink escape; slug validation alone blocks textual traversal.

param(
    [string]$PlanRoot = (Join-Path (Get-Location) ".planning")
)

$projectRoot = (Get-Location).Path

# PWF_PLAN_ROOT: absolute plan-root binding (issue #212), mirroring
# resolve-plan-dir.sh. A thread whose cwd is a shared PARENT of the real
# project resolves the parent's plan and never sees the nested one;
# PWF_PLAN_ROOT names the project root whose .planning must be used. Highest
# precedence: it overrides both the cwd default and the -PlanRoot argument
# (an adapter passing ".planning" is spelling out the cwd default, not
# overriding a user's deliberate pin). A pin that is not a directory fails
# CLOSED: the resolver emits nothing, so no caller can be handed the
# ambiguous cwd plan the pin was escaping (injection routes own the
# user-facing notice; stdout here is the data channel). Containment is then
# checked against the pinned root. Unset keeps legacy behavior unchanged.
if ($env:PWF_PLAN_ROOT) {
    if (Test-Path -LiteralPath $env:PWF_PLAN_ROOT -PathType Container) {
        $projectRoot = $env:PWF_PLAN_ROOT
        $PlanRoot = Join-Path $env:PWF_PLAN_ROOT ".planning"
    } else {
        exit 0
    }
}

# Same shape as the sh resolver's slug_is_valid: first char [A-Za-z0-9_],
# rest [A-Za-z0-9._-]. Blocks traversal tokens before any path is built.
function Test-ValidSlug {
    param([string]$Name)
    if (-not $Name) { return $false }
    return $Name -match '^[A-Za-z0-9_][A-Za-z0-9._-]*$'
}

# Containment guard (security A1.3): a resolved plan dir must canonicalize to
# a path under the project root. A directory symlink/junction inside a valid
# slug pointing outside the workspace would otherwise let the hooks hash and
# inject an arbitrary file. Resolve-Path follows reparse points; we compare
# the real paths. Fails CLOSED on canonicalization failure, matching
# resolve-plan-dir.sh.
function Test-WithinRoot {
    param([string]$Candidate)
    try {
        $rootReal = (Resolve-Path -LiteralPath $projectRoot -ErrorAction Stop).Path
        $candReal = (Resolve-Path -LiteralPath $Candidate -ErrorAction Stop).Path
    } catch {
        return $false
    }
    if (-not $rootReal -or -not $candReal) { return $false }
    $rootNorm = $rootReal.TrimEnd('\', '/')
    $candNorm = $candReal.TrimEnd('\', '/')
    if ($candNorm -eq $rootNorm) { return $true }
    return $candNorm.StartsWith($rootNorm + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
}

$activeFile = Join-Path $PlanRoot ".active_plan"

if ($env:PLAN_ID) {
    if (Test-ValidSlug $env:PLAN_ID) {
        $candidate = Join-Path $PlanRoot $env:PLAN_ID
        if ((Test-Path $candidate -PathType Container) -and (Test-WithinRoot $candidate)) {
            Write-Output $candidate
            exit 0
        }
    }
}

if (Test-Path $activeFile) {
    $planId = (Get-Content $activeFile -Raw).Trim()
    if ($planId -and (Test-ValidSlug $planId)) {
        $candidate = Join-Path $PlanRoot $planId
        if ((Test-Path $candidate -PathType Container) -and (Test-WithinRoot $candidate)) {
            Write-Output $candidate
            exit 0
        }
    }
}

if (Test-Path $PlanRoot -PathType Container) {
    $latest = Get-ChildItem -Path $PlanRoot -Directory |
        Where-Object { -not $_.Name.StartsWith('.') } |
        Where-Object { Test-ValidSlug $_.Name } |
        Where-Object { Test-Path (Join-Path $_.FullName "task_plan.md") -PathType Leaf } |
        Where-Object { Test-WithinRoot $_.FullName } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($latest) {
        Write-Output $latest.FullName
    }
}

exit 0
