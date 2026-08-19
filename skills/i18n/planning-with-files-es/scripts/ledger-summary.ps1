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

    if ($env:PLAN_ID) {
        $candidate = Join-Path $planRoot $env:PLAN_ID
        if (Test-Path -LiteralPath $candidate -PathType Container) { return $candidate }
    }

    $activePointer = Join-Path $planRoot ".active_plan"
    if (Test-Path -LiteralPath $activePointer) {
        $planId = (Get-Content -LiteralPath $activePointer -Raw).Trim()
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
$planFile = Join-Path $planDir "task_plan.md"

# --- Phase counts: same patterns as check-complete.ps1 ---
$TOTAL = 0
$COMPLETE = 0
$IN_PROGRESS = 0
$inProgressHeading = "none"

if (Test-Path -LiteralPath $planFile) {
    $content = Get-Content -LiteralPath $planFile -Raw
    $TOTAL = ([regex]::Matches($content, "### Phase")).Count
    $COMPLETE = ([regex]::Matches($content, "\*\*Status:\*\* complete")).Count
    $IN_PROGRESS = ([regex]::Matches($content, "\*\*Status:\*\* in_progress")).Count

    if ($COMPLETE -eq 0 -and $IN_PROGRESS -eq 0) {
        $c2 = ([regex]::Matches($content, "\[complete\]")).Count
        $i2 = ([regex]::Matches($content, "\[in_progress\]")).Count
        if ($c2 -gt 0 -or $i2 -gt 0) {
            $COMPLETE = $c2
            $IN_PROGRESS = $i2
        }
    }

    # Heading of the first phase block whose status is in_progress.
    $heading = ""
    foreach ($line in (Get-Content -LiteralPath $planFile)) {
        if ($line -match "^### Phase") {
            $heading = $line
        } elseif ($line -match "\*\*Status:\*\* in_progress" -or $line -match "\[in_progress\]") {
            if ($heading) {
                $inProgressHeading = $heading
                break
            }
        }
    }
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
Write-Output ("phases: " + $COMPLETE + "/" + $TOTAL + " complete")
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
