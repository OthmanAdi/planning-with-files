#requires -Version 5.0
<#
.SYNOPSIS
    Append one structured entry to the run-ledger (PowerShell mirror, v3).

.DESCRIPTION
    The run-ledger is the machine layer of progress tracking: an append-only
    JSON-lines file per agent under the active plan dir. Workers append here;
    the orchestrator owns progress.md and task_plan.md. See architecture C3.

    Plan-dir resolution (matches resolve-plan-dir.ps1):
      1. $env:PLAN_ID -> .\.planning\$PLAN_ID\
      2. .\.planning\.active_plan
      3. Newest .\.planning\<dir>\ by LastWriteTime
      4. Legacy: project root (ledger lands beside .\task_plan.md)

    Writes ONE JSON line to <plan-dir>\ledger-<agent>.jsonl. tick = 1 + max tick
    across ALL ledger-*.jsonl in the plan dir so concurrent agents share a
    monotonic counter.

.PARAMETER Event
    One of: progress phase_complete error gate_block attest note.

.PARAMETER Summary
    Free text, truncated to 200 chars, newlines stripped.

.PARAMETER Agent
    Ledger owner (default "main"); sanitized to [A-Za-z0-9_-].

.PARAMETER Phase
    Phase number/name this entry concerns.

.PARAMETER Files
    Comma-separated file list recorded as a JSON array.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string] $Event,

    [Parameter(Mandatory = $true, Position = 1)]
    [string] $Summary,

    [string] $Agent = "main",

    [string] $Phase = "",

    [string] $Files = ""
)

$ErrorActionPreference = "Stop"

$validEvents = @("progress", "phase_complete", "error", "gate_block", "attest", "note")

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

    # Legacy single-file mode: ledger lives beside .\task_plan.md at root.
    return (Get-Location).Path
}

function ConvertTo-JsonString {
    param([string] $Value)
    $sb = New-Object System.Text.StringBuilder
    foreach ($ch in $Value.ToCharArray()) {
        switch ($ch) {
            '"'  { [void]$sb.Append('\"') }
            '\'  { [void]$sb.Append('\\') }
            "`n" { [void]$sb.Append(' ') }
            "`r" { [void]$sb.Append(' ') }
            "`t" { [void]$sb.Append(' ') }
            default {
                if ([int]$ch -lt 32) {
                    [void]$sb.Append(' ')
                } else {
                    [void]$sb.Append($ch)
                }
            }
        }
    }
    return $sb.ToString()
}

function Get-MaxTick {
    param([string] $Dir)
    $max = 0
    $pattern = '"tick"\s*:\s*(\d+)'
    Get-ChildItem -LiteralPath $Dir -Filter "ledger-*.jsonl" -File -ErrorAction SilentlyContinue | ForEach-Object {
        foreach ($line in (Get-Content -LiteralPath $_.FullName -ErrorAction SilentlyContinue)) {
            $m = [regex]::Match($line, $pattern)
            if ($m.Success) {
                $t = [int]$m.Groups[1].Value
                if ($t -gt $max) { $max = $t }
            }
        }
    }
    return $max
}

# Validate event against the allowlist.
if ($validEvents -notcontains $Event) {
    Write-Error ("[ledger] invalid event '" + $Event + "' (allowed: " + ($validEvents -join ' ') + ")")
    exit 2
}

# Sanitize agent name to [A-Za-z0-9_-]; empty result falls back to "main".
$agentClean = ($Agent -replace '[^A-Za-z0-9_-]', '')
if (-not $agentClean) { $agentClean = "main" }

# Truncate summary to the 200-character budget before escaping, matching the
# sh twin. .NET Substring counts characters, never bytes, so multibyte input
# cannot be clipped mid-codepoint here and no UTF-8 tail repair is needed.
if ($Summary.Length -gt 200) { $Summary = $Summary.Substring(0, 200) }

$planDir    = Resolve-PlanDir
$ledgerFile = Join-Path $planDir ("ledger-" + $agentClean + ".jsonl")
$lockFile   = Join-Path $planDir ".ledger_lock"

$ts = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")

# Build the files JSON array from the comma-separated list.
$filesJson = "[]"
if ($Files) {
    $parts = $Files.Split(",") | Where-Object { $_ -ne "" }
    $escaped = $parts | ForEach-Object { '"' + (ConvertTo-JsonString $_) + '"' }
    $filesJson = "[" + ($escaped -join ",") + "]"
}

$summaryEsc = ConvertTo-JsonString $Summary
$phaseEsc   = ConvertTo-JsonString $Phase

# Acquire an exclusive lock on a sidecar so concurrent appenders do not pick
# the same tick number, then compute tick and append inside the locked window.
# Atomic append of a single <4KB line is the real guarantee; the lock just
# serializes the read-tick / write-line pair.
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

try {
    $tick = (Get-MaxTick $planDir) + 1
    $line = '{"tick":' + $tick + ',"ts":"' + $ts + '","agent":"' + $agentClean + '","phase":"' + $phaseEsc + '","event":"' + $Event + '","summary":"' + $summaryEsc + '","files":' + $filesJson + '}'
    Add-Content -LiteralPath $ledgerFile -Value $line -Encoding utf8
} finally {
    if ($fs) { $fs.Close(); $fs.Dispose() }
    if (Test-Path -LiteralPath $lockFile) { Remove-Item -LiteralPath $lockFile -Force -ErrorAction SilentlyContinue }
}

Write-Output ("[ledger] tick " + $tick + " -> " + $ledgerFile + " (event=" + $Event + " agent=" + $agentClean + ")")
exit 0
