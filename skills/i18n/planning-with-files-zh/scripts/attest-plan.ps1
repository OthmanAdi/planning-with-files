#requires -Version 5.0
<#
.SYNOPSIS
    Lock the current task_plan.md content with a SHA-256 attestation.

.DESCRIPTION
    Use after you finalise (or intentionally edit) a plan. The hooks then refuse
    to inject plan content into the model context if the file diverges from the
    attested hash, surfacing a "[PLAN TAMPERED]" warning instead.

    Plan resolution:
      1. $env:PLAN_ID  -> ./.planning/$PLAN_ID/
      2. ./.planning/.active_plan
      3. Newest ./.planning/<dir>/ by LastWriteTime
      4. Legacy ./task_plan.md at project root

.PARAMETER Show
    Print the stored hash for the active plan.

.PARAMETER Clear
    Remove the attestation (re-open the plan).
#>
[CmdletBinding(DefaultParameterSetName = "Attest")]
param(
    [Parameter(ParameterSetName = "Show")]
    [switch] $Show,

    [Parameter(ParameterSetName = "Clear")]
    [switch] $Clear
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

    if (Test-Path -LiteralPath $planRoot) {
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

function Get-AttestationPath {
    param([string] $PlanFile)
    $planDir = Split-Path -Parent $PlanFile
    $cwd     = (Get-Location).Path
    if ($planDir -eq $cwd) {
        return (Join-Path $cwd ".plan-attestation")
    }
    return (Join-Path $planDir ".attestation")
}

$planFile = Resolve-PlanFile
if (-not $planFile) {
    Write-Error "[plan-attest] No task_plan.md found. Create a plan first."
    exit 1
}

$attestationFile = Get-AttestationPath -PlanFile $planFile

if ($Show) {
    if (Test-Path -LiteralPath $attestationFile) {
        Write-Output "Plan: $planFile"
        Write-Output "Attestation: $attestationFile"
        Write-Output ("SHA-256: " + (Get-Content -LiteralPath $attestationFile -Raw).Trim())
        # Nonce (security A1.4): surface the per-plan nonce if init-session
        # generated one next to the attestation. Informational only here; the
        # hooks consume it to build collision-proof BEGIN/END delimiters.
        $nonceFile = Join-Path (Split-Path -Parent $attestationFile) ".nonce"
        if (Test-Path -LiteralPath $nonceFile) {
            $nonceVal = (Get-Content -LiteralPath $nonceFile -Raw).Trim()
            if ($nonceVal) { Write-Output "Nonce: $nonceVal" }
        }
    } else {
        Write-Output "[plan-attest] No attestation set for $planFile."
        exit 1
    }
    exit 0
}

if ($Clear) {
    if (Test-Path -LiteralPath $attestationFile) {
        Remove-Item -LiteralPath $attestationFile -Force
        Write-Output "[plan-attest] Cleared attestation for $planFile."
    } else {
        Write-Output "[plan-attest] No attestation to clear."
    }
    exit 0
}

$hashVal = (Get-FileHash -LiteralPath $planFile -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath $attestationFile -Value $hashVal -NoNewline -Encoding ascii

# Integrity verification (security A2.1): confirm the on-disk attestation
# matches the intended hash before reporting success. A silent write failure
# (permissions, full disk) must not leave a stale attestation and exit clean.
$storedHash = (Get-Content -LiteralPath $attestationFile -Raw -ErrorAction SilentlyContinue)
if ($null -ne $storedHash) { $storedHash = $storedHash.Trim() }
if ($storedHash -ne $hashVal) {
    Write-Error "[plan-attest] Attestation write verification FAILED for $attestationFile. Expected $hashVal, found $storedHash. The plan is NOT attested."
    exit 1
}

$short = $hashVal.Substring(0, 12)
Write-Output "[plan-attest] Locked $planFile"
Write-Output "[plan-attest] SHA-256: $short... (stored in $attestationFile)"
Write-Output "[plan-attest] Hooks will block injection if the file is modified without re-running this command."
exit 0
