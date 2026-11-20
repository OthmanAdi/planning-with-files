# Check if all phases in task_plan.md are complete
# Always exits 0 -- uses stdout for status reporting
# Used by Stop hook to report task completion status

param(
    [string]$PlanFile = "task_plan.md"
)

# issue #195: per-invocation opt-out (PLANNING_DISABLED=1) for one-shot/CI
# sessions that share a cwd with a plan but never opted into it.
if ($env:PLANNING_DISABLED -eq '1') { exit 0 }

if (-not (Test-Path -LiteralPath $PlanFile)) {
    Write-Host '[planning-with-files] No task_plan.md found -- no active planning session.'
    exit 0
}

# Read file content
try {
    $content = Get-Content -LiteralPath $PlanFile -Raw -Encoding UTF8 -ErrorAction Stop
} catch {
    Write-Output '[planning-with-files] Plan read error: phase completion unavailable.'
    exit 0
}

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

# Report status -- always exit 0, incomplete task is a normal state
if ($fence -or $malformedHeading) {
    Write-Output '[planning-with-files] Plan format error: phase completion unavailable.'
} elseif ($COMPLETE -eq $TOTAL -and $TOTAL -gt 0) {
    Write-Host ('[planning-with-files] ALL PHASES COMPLETE (' + $COMPLETE + '/' + $TOTAL + '). If the user has additional work, add new phases to task_plan.md before starting.')
} else {
    Write-Host ('[planning-with-files] Task in progress (' + $COMPLETE + '/' + $TOTAL + ' phases complete). Update progress.md before stopping.')
    if ($IN_PROGRESS -gt 0) {
        Write-Host ('[planning-with-files] ' + $IN_PROGRESS + ' phase(s) still in progress.')
    }
    if ($PENDING -gt 0) {
        Write-Host ('[planning-with-files] ' + $PENDING + ' phase(s) pending.')
    }
}
exit 0
