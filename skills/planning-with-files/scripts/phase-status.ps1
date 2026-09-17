#requires -Version 5.0
<#
.SYNOPSIS
    Set the status of one phase in task_plan.md (PowerShell mirror, v3).

.DESCRIPTION
    The ONLY sanctioned concurrent-safe writer of task_plan.md status lines. The
    orchestrator owns task_plan.md; workers NEVER edit it directly. The edit is
    a read-modify-write under the portable
    <plan-dir>\.pwf-locks\phase-status.lock directory lock, with an atomic
    temp-file + move swap so a torn write can never leave a half-rewritten plan
    on disk (architecture C4).

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

    # A set PLAN_ID is a BINDING, not a hint (issue #237). A selector that
    # names no plan directory stops resolution instead of falling through to
    # .active_plan and newest-by-mtime: this script reports phase state, and
    # answering a mistyped pin with a DIFFERENT plan's phases is the same
    # wrong-plan harm that let a typo attest the wrong file.
    if ($env:PLAN_ID) {
        $candidate = Join-Path $planRoot $env:PLAN_ID
        $planFile  = Join-Path $candidate "task_plan.md"
        if (Test-Path -LiteralPath $planFile) { return (Resolve-Path -LiteralPath $planFile).Path }
        return $null
    }

    $activePointer = Join-Path $planRoot ".active_plan"
    if (Test-Path -LiteralPath $activePointer) {
        $planId = "$(Get-Content -LiteralPath $activePointer -Raw -ErrorAction SilentlyContinue)".Trim()
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

function Enter-PwfDirectoryLock {
    param(
        [string] $LockRoot,
        [string] $LockDir
    )

    try {
        [void][System.IO.Directory]::CreateDirectory($LockRoot)
    } catch {
        Write-Error ("[phase-status] Cannot create lock root " + $LockRoot + ": " + $_.Exception.Message)
        return $null
    }

    $token = "phase-status-" + $PID + "-" + [Guid]::NewGuid().ToString("N")
    $ownerFile = Join-Path $LockDir ".owner"
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)

    $wait = [Diagnostics.Stopwatch]::StartNew()
    while ($wait.Elapsed.TotalSeconds -lt 5) {
        $createdByUs = $false
        try {
            New-Item -Path $LockDir -ItemType Directory -ErrorAction Stop | Out-Null
            $createdByUs = $true
            [System.IO.File]::WriteAllText($ownerFile, $token + "`n", $utf8NoBom)
            return [PSCustomObject]@{
                Directory = $LockDir
                OwnerFile = $ownerFile
                Token = $token
            }
        } catch {
            if ($createdByUs) {
                try {
                    if ([System.IO.File]::Exists($ownerFile)) {
                        $ownerValue = [System.IO.File]::ReadAllText($ownerFile).Trim()
                        if ([string]::Equals($ownerValue, $token, [StringComparison]::Ordinal)) {
                            [System.IO.File]::Delete($ownerFile)
                        }
                    }
                    [System.IO.Directory]::Delete($LockDir, $false)
                } catch {
                    # Leave any directory we cannot prove is still ours intact.
                }
            }
            Start-Sleep -Milliseconds 100
        }
    }

    return $null
}

function Exit-PwfDirectoryLock {
    param($Lock)
    if (-not $Lock) { return }
    try {
        if (-not [System.IO.File]::Exists($Lock.OwnerFile)) { return }
        $ownerValue = [System.IO.File]::ReadAllText($Lock.OwnerFile).Trim()
        if (-not [string]::Equals($ownerValue, $Lock.Token, [StringComparison]::Ordinal)) { return }
        [System.IO.File]::Delete($Lock.OwnerFile)
        [System.IO.Directory]::Delete($Lock.Directory, $false)
    } catch {
        # Cleanup is best-effort and never removes a lock with another owner.
    }
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
    if ($env:PLAN_ID) {
        Write-Error "[phase-status] PLAN_ID names no plan directory under .planning; nothing was written and no other plan was substituted."
    } else {
        Write-Error "[phase-status] No task_plan.md found. Create a plan first."
    }
    exit 1
}

$planDir  = Split-Path -Parent $planFile
$lockRoot = Join-Path $planDir ".pwf-locks"
$lockDir  = Join-Path $lockRoot "phase-status.lock"

# Atomic directory creation is the common lock primitive used by both the sh
# and PowerShell implementations. Failure to acquire within about five seconds
# is fail-closed: no plan read/rewrite is attempted.
$lock = Enter-PwfDirectoryLock -LockRoot $lockRoot -LockDir $lockDir
if (-not $lock) {
    Write-Error ("[phase-status] Timed out waiting for lock " + $lockDir + ". No plan changes were made.")
    exit 75
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
    Exit-PwfDirectoryLock -Lock $lock
    if (Test-Path -LiteralPath $tmpFile) { Remove-Item -LiteralPath $tmpFile -Force -ErrorAction SilentlyContinue }
}

if ($rc -ne 0) { exit 1 }

Write-Output ("[phase-status] Phase " + $Phase + " -> " + $Status + " in " + $planFile)
exit 0
