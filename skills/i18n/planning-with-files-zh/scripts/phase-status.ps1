#requires -Version 5.0
<#
.SYNOPSIS
    Set the status of one phase in task_plan.md (PowerShell mirror, v3).

.DESCRIPTION
    The ONLY sanctioned concurrent-safe writer of task_plan.md status lines. The
    orchestrator owns task_plan.md; workers NEVER edit it directly. The edit is
    a read-modify-write under an exclusive lock on the <plan-dir>\.write_lock
    sentinel, with an atomic temp-file + move swap so a torn write can never
    leave a half-rewritten plan on disk (architecture C4).

    Editing task_plan.md changes its SHA, so the orchestrator must re-attest at
    phase boundaries (see attest-plan.ps1).

    Plan-dir resolution matches resolve-plan-dir.ps1:
      1. $env:PLAN_ID -> .\.planning\$PLAN_ID\
      2. .\.planning\.active_plan
      3. Newest .\.planning\<dir>\ by LastWriteTime
      4. Legacy: project root .\task_plan.md

    Exits 1 with a message if the phase does not exist or the status is invalid.

.PARAMETER Phase
    Phase number (positive integer).

.PARAMETER Status
    New status: pending, in_progress, or complete.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string] $Phase,

    [Parameter(Mandatory = $true, Position = 1)]
    [string] $Status
)

$ErrorActionPreference = "Stop"

function Resolve-PlanFile {
    $planRoot = Join-Path (Get-Location) ".planning"

    if ($env:PLAN_ID) {
        $candidate = Join-Path $planRoot $env:PLAN_ID
        $planFile  = Join-Path $candidate "task_plan.md"
        if (Test-Path -LiteralPath $planFile) { return (Resolve-Path -LiteralPath $planFile).Path }
    }

    $activePointer = Join-Path $planRoot ".active_plan"
    if (Test-Path -LiteralPath $activePointer) {
        $planId = (Get-Content -LiteralPath $activePointer -Raw).Trim()
        if ($planId) {
            $candidate = Join-Path $planRoot $planId
            $planFile  = Join-Path $candidate "task_plan.md"
            if (Test-Path -LiteralPath $planFile) { return (Resolve-Path -LiteralPath $planFile).Path }
        }
    }

    if (Test-Path -LiteralPath $planRoot -PathType Container) {
        $newest = Get-ChildItem -LiteralPath $planRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { -not $_.Name.StartsWith(".") } |
            Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "task_plan.md") } |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($newest) {
            return (Resolve-Path -LiteralPath (Join-Path $newest.FullName "task_plan.md")).Path
        }
    }

    $legacy = Join-Path (Get-Location) "task_plan.md"
    if (Test-Path -LiteralPath $legacy) {
        return (Resolve-Path -LiteralPath $legacy).Path
    }

    return $null
}

# Validate phase number is a positive integer.
if ($Phase -notmatch '^[0-9]+$') {
    Write-Error ("[phase-status] phase number must be a positive integer, got '" + $Phase + "'.")
    exit 1
}

# Validate status value against the allowlist.
$validStatus = @("pending", "in_progress", "complete")
if ($validStatus -notcontains $Status) {
    Write-Error ("[phase-status] invalid status '" + $Status + "' (allowed: pending, in_progress, complete).")
    exit 1
}

$planFile = Resolve-PlanFile
if (-not $planFile) {
    Write-Error "[phase-status] No task_plan.md found. Create a plan first."
    exit 1
}

$planDir  = Split-Path -Parent $planFile
$lockFile = Join-Path $planDir ".write_lock"

# Acquire an exclusive lock on the sentinel so concurrent writers serialize.
$fs = $null
$acquired = $false
for ($i = 0; $i -lt 50 -and -not $acquired; $i++) {
    try {
        $fs = [System.IO.File]::Open($lockFile, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
        $acquired = $true
    } catch {
        Start-Sleep -Milliseconds 100
    }
}

$tmpFile = $planFile + ".tmp." + $PID
$rc = 0
try {
    $lines = Get-Content -LiteralPath $planFile

    # Confirm the phase heading exists.
    $headingRe = '^### Phase ' + $Phase + '([^0-9]|$)'
    if (-not ($lines | Where-Object { $_ -match $headingRe })) {
        Write-Error ("[phase-status] Phase " + $Phase + " not found in " + $planFile + ".")
        $rc = 1
    } else {
        $inBlock = $false
        $done = $false
        $out = New-Object System.Collections.Generic.List[string]
        foreach ($line in $lines) {
            $emit = $line
            if ($line -match '^### Phase ') {
                $rest = $line -replace '^### Phase ', ''
                $num = $rest -replace '[^0-9].*$', ''
                if (($num -eq $Phase) -and (-not $done)) {
                    $inBlock = $true
                } else {
                    $inBlock = $false
                }
            } elseif ($inBlock -and (-not $done) -and ($line -match '\*\*Status:\*\*')) {
                $prefix = $line -replace '\*\*Status:\*\*.*$', ''
                $emit = $prefix + '**Status:** ' + $Status
                $inBlock = $false
                $done = $true
            }
            $out.Add($emit)
        }

        if (-not $done) {
            Write-Error ("[phase-status] No **Status:** line found for Phase " + $Phase + ".")
            $rc = 1
        } else {
            # Atomic-enough swap: write temp, then move over the target.
            # Write BOM-less UTF-8 (platform-major): Set-Content -Encoding utf8 on
            # Windows PowerShell 5.1 prepends a UTF-8 BOM (EF BB BF). The temp file
            # then replaces task_plan.md, so every phase-status call from PS 5.1
            # changes the file's leading bytes. If the plan was created on Linux or
            # macOS (no BOM), the stored attestation SHA-256 no longer matches and
            # inject-plan.sh blocks all further injection as [PLAN TAMPERED]. A
            # UTF8Encoding constructed with $false emits no BOM on every PS version.
            $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
            [System.IO.File]::WriteAllLines($tmpFile, $out, $utf8NoBom)
            Move-Item -LiteralPath $tmpFile -Destination $planFile -Force
        }
    }
} catch {
    Write-Error ("[phase-status] " + $_.Exception.Message)
    $rc = 1
} finally {
    if ($fs) { $fs.Close(); $fs.Dispose() }
    if (Test-Path -LiteralPath $lockFile) { Remove-Item -LiteralPath $lockFile -Force -ErrorAction SilentlyContinue }
    if (Test-Path -LiteralPath $tmpFile) { Remove-Item -LiteralPath $tmpFile -Force -ErrorAction SilentlyContinue }
}

if ($rc -ne 0) { exit 1 }

Write-Output ("[phase-status] Phase " + $Phase + " -> " + $Status + " in " + $planFile)
exit 0
