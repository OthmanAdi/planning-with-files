#requires -Version 5.0
<#
.SYNOPSIS
    Emit a fixed-shape, cache-stable run-ledger summary (PowerShell mirror, v3).

.DESCRIPTION
    Replaces raw progress.md tail injection in autonomous mode. Output is
    synthesized from the machine ledger and task_plan.md status counts only:
    NO free text from disk reaches model context, and NO timestamps, so the
    injected block is KV-cache stable by construction (architecture C3).

    Plan-dir resolution matches resolve-plan-dir.ps1:
      1. $env:PLAN_ID -> .\.planning\$PLAN_ID\
      2. .\.planning\.active_plan
      3. Newest .\.planning\<dir>\ by LastWriteTime
      4. Legacy: project root

    Output block (stable shape):
      === RUN LEDGER ===
      entries: <N>
      phases: <complete>/<total> complete
      in_progress: <phase heading or none>
      agent <name>: <last event type>
      ==================
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Resolve-PlanDir {
    $planRoot = Join-Path (Get-Location) ".planning"

    # A set PLAN_ID is a BINDING, not a hint (issue #237). A selector that
    # names no plan directory stops resolution instead of falling through to
    # .active_plan, newest-by-mtime and finally the cwd: summarizing another
    # plan's ledger under a mistyped pin is the same wrong-plan harm that let
    # a typo attest the wrong file.
    if ($env:PLAN_ID) {
        $candidate = Join-Path $planRoot $env:PLAN_ID
        if (Test-Path -LiteralPath $candidate -PathType Container) { return $candidate }
        return $null
    }

    $activePointer = Join-Path $planRoot ".active_plan"
    if (Test-Path -LiteralPath $activePointer) {
        $planId = "$(Get-Content -LiteralPath $activePointer -Raw -ErrorAction SilentlyContinue)".Trim()
        if ($planId) {
            $candidate = Join-Path $planRoot $planId
            if (Test-Path -LiteralPath $candidate -PathType Container) { return $candidate }
        }
    }

    if (Test-Path -LiteralPath $planRoot -PathType Container) {
        $newest = Get-ChildItem -LiteralPath $planRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { -not $_.Name.StartsWith(".") } |
            Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "task_plan.md") } |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($newest) { return $newest.FullName }
    }

    return (Get-Location).Path
}

$planDir  = Resolve-PlanDir
if (-not $planDir) {
    # Loud degradation, same contract as ledger-summary.sh's emit_unavailable:
    # a rejected PLAN_ID binding must not report the ROOT plan's phase counts,
    # because an autonomous loop reads those counts as its termination signal.
    Write-Output "=== RUN LEDGER ==="
    Write-Output "ledger: unavailable (explicit PLAN_ID did not resolve)"
    Write-Output "=================="
    exit 0
}
$planFile = Join-Path $planDir "task_plan.md"

$TOTAL = 0
$COMPLETE = 0
$IN_PROGRESS = 0
$inProgressHeading = "none"
$phaseReadError = $false
$fence = ""
if (Test-Path -LiteralPath $planFile) {
    try {
        $content = Get-Content -LiteralPath $planFile -Raw -Encoding UTF8 -ErrorAction Stop
    } catch { $phaseReadError = $true }
# Count native statuses inside real phases, excluding fenced examples (#377).
$counts = @{ total = 0; complete = 0; in_progress = 0; pending = 0 }
$phase = $null
$invalid = $false
$activeHeading = ""
$fence = ""
$fenceLength = 0
$malformedHeading = $false
function Complete-Phase {
    if ($null -ne $script:phase) {
        if ($script:phase.Statuses.Count -ne 1) { $script:invalid = $true }
        else {
            $state = $script:phase.Statuses[0]
            if ($state -ne 'in_progress') { $script:counts[$state]++ }
        }
        if ($script:phase.Statuses -contains 'in_progress') {
            $script:counts.in_progress++
            if (-not $script:activeHeading) { $script:activeHeading = $script:phase.Heading }
        }
    }
    $script:phase = $null
}
foreach ($line in (($content -creplace '^\uFEFF', '') -split '\r?\n')) {
    if ($fence) {
        if ($line -match ('^ {0,3}' + [regex]::Escape($fence) + '{' + $fenceLength + ',}[ \t]*$')) { $fence = "" }
        continue
    }
    if ($line -match '^ {0,3}(`{3,}|~{3,})' -and
        ($Matches[1][0] -eq '~' -or -not $line.Substring($Matches[0].Length).Contains('`'))) {
        $fence = $Matches[1].Substring(0, 1); $fenceLength = $Matches[1].Length
        continue
    }
    if ($line -match '^ {0,3}>') { continue }
    if ($line -cmatch '^ {0,3}### Phase(?:[0-9:]|-[0-9])') {
        Complete-Phase
        $malformedHeading = $true
        continue
    }
    if ($line -cmatch '^ {0,3}### Phase(?:[ \t]|$)') {
        Complete-Phase
        $counts.total++
        $phase = @{ Heading = $line; Statuses = @() }
    } elseif ($line -match '^ {0,3}#{1,3}(?:[ \t]|$)') {
        Complete-Phase
    }
    if ($null -ne $phase) {
        foreach ($match in [regex]::Matches($line, '\*\*Status:\*\*[ \t]+(pending|in_progress|complete)(?![A-Za-z0-9_])|\[(pending|in_progress|complete)\]')) {
            $state = $match.Groups[1].Value
            if (-not $state) { $state = $match.Groups[2].Value }
            $phase.Statuses += $state
        }
    }
}
Complete-Phase
$TOTAL = $counts.total
$COMPLETE = $counts.complete
$IN_PROGRESS = $counts.in_progress
$PENDING = $counts.pending
    if ($activeHeading) { $inProgressHeading = $activeHeading }
}

# --- Ledger stats ---
$totalEntries = 0
$ledgerFiles = Get-ChildItem -LiteralPath $planDir -Filter "ledger-*.jsonl" -File -ErrorAction SilentlyContinue
foreach ($f in $ledgerFiles) {
    $lines = Get-Content -LiteralPath $f.FullName -ErrorAction SilentlyContinue
    foreach ($line in $lines) {
        if ($line -match '"tick"') { $totalEntries++ }
    }
}

Write-Output "=== RUN LEDGER ==="
Write-Output ("entries: " + $totalEntries)
if ($phaseReadError -or $fence -or $malformedHeading) {
    Write-Output "phases: unavailable (plan format or read error)"
} else {
    Write-Output ("phases: " + $COMPLETE + "/" + $TOTAL + " complete")
}
Write-Output ("in_progress: " + $inProgressHeading)

foreach ($f in $ledgerFiles) {
    $agent = $f.Name -replace '^ledger-', '' -replace '\.jsonl$', ''
    # @(...) forces array semantics: a single-line file returns a string from
    # Get-Content and $lines[-1] would otherwise index the last character.
    $lines = @(Get-Content -LiteralPath $f.FullName -ErrorAction SilentlyContinue)
    $lastEvent = "none"
    if ($lines.Count -gt 0) {
        $lastLine = $lines[$lines.Count - 1]
        $m = [regex]::Match($lastLine, '"event"\s*:\s*"([A-Za-z_]+)"')
        if ($m.Success) { $lastEvent = $m.Groups[1].Value }
    }
    Write-Output ("agent " + $agent + ": " + $lastEvent)
}

Write-Output "=================="
exit 0
