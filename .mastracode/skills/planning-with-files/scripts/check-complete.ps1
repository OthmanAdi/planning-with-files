# Check if all phases in task_plan.md are complete
# Default invocation: advisory echo, always exits 0 (Stop hook status report).
# With -Validate: read-only creation check; exits 1 for an untrackable plan.
# With -Gate: deliberate completion gate, opt-in per plan via <plan-dir>/.mode.
# Used by Stop hook to report task completion status.
#
# Gate mode (v3, -Gate flag) blocks ONLY when ALL hold (design "Gate decision table"):
#   1. <plan-dir>/.mode exists and contains "gate" (explicit opt-in)
#   2. an in_progress phase exists (not merely complete<total)
#   3. the Stop hook input JSON on stdin does not set stop_hook_active=true
#   4. the block counter (<plan-dir>/.stop_blocks) is below cap (PWF_GATE_CAP, default 20)
#   5. the ledger advanced since the last block (stall -> allow stop)
# When all hold, emits a single-line block-decision JSON on stdout and exits 0.
# Otherwise reports incomplete plans and exits 0; completed plans stay silent
# with -Gate, including legacy plans without .mode. Explicit reports are unchanged.
#
# Stdin: read only when input is redirected ([Console]::IsInputRedirected), so an
# interactive console never blocks. Hook-piped JSON is EOF-terminated.

param(
    [string]$PlanFile = "",
    [switch]$Gate,
    [switch]$Validate
)

# issue #195: per-invocation opt-out (PLANNING_DISABLED=1) for one-shot/CI
# sessions that share a cwd with a plan but never opted into it.
if ($env:PLANNING_DISABLED -eq '1' -and -not $Validate) { exit 0 }

if ($PlanFile -ne "") {
    $PlanDir = Split-Path -Parent $PlanFile
    if ($PlanDir -eq "") { $PlanDir = "." }
} else {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $resolver = Join-Path $scriptDir "resolve-plan-dir.ps1"
    $resolvedDir = ""
    if (Test-Path $resolver) {
        try {
            $resolvedDir = (& $resolver 2>$null | Select-Object -First 1)
            if ($null -eq $resolvedDir) { $resolvedDir = "" }
            if (-not $resolvedDir -and ((& $resolver -CheckAmbiguity) -eq "PWF_PLAN_AMBIGUOUS_V1")) {
                if ($Validate) { Write-Output '[planning-with-files] Plan format invalid: select one plan before validation.'; exit 1 }
                exit 0
            }
        } catch {
            $resolvedDir = ""
        }
    }
    if ($resolvedDir -ne "" -and (Test-Path (Join-Path $resolvedDir "task_plan.md"))) {
        $PlanFile = Join-Path $resolvedDir "task_plan.md"
        $PlanDir = $resolvedDir
    } else {
        if ($Validate -and ($env:PLAN_ID -or $env:PWF_PLAN_ROOT)) {
            Write-Output '[planning-with-files] Plan format invalid: an explicit plan selector did not resolve.'
            exit 1
        }
        $PlanFile = "task_plan.md"
        $PlanDir = "."
    }
}

if (-not (Test-Path -LiteralPath $PlanFile)) {
    if ($Validate) { Write-Output '[planning-with-files] Plan format invalid: task_plan.md was not found.'; exit 1 }
    # Automatic gate checks have nothing to report without a plan; the explicit report keeps its notice.
    if ($Gate) { exit 0 }
    Write-Host '[planning-with-files] No task_plan.md found -- no active planning session.'
    exit 0
}

# Read file content
try {
    $content = Get-Content -LiteralPath $PlanFile -Raw -Encoding UTF8 -ErrorAction Stop
} catch {
    Write-Output '[planning-with-files] Plan read error: phase completion unavailable.'
    if ($Validate) { exit 1 }
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

if ($Validate) {
    if ($TOTAL -eq 0 -or $invalid -or $fence -or $malformedHeading) {
        Write-Output '[planning-with-files] Plan format invalid: use ### Phase headings with exactly one native status per phase.'
        exit 1
    }
    Write-Output ('[planning-with-files] Plan format valid (' + $TOTAL + ' phases).')
    exit 0
}

# issue #191: no "### Phase" headings -> not a phase-structured plan. Report
# nothing rather than a false "0/0 phases complete" status. With TOTAL=0 the
# gate can never legitimately block (IN_PROGRESS is also 0), so exit is safe.
if ($TOTAL -eq 0 -and -not $fence -and -not $malformedHeading) {
    exit 0
}

# Keep explicit reports, but omit routine success from automatic gate checks.
function Write-AdvisoryReport {
    if ($fence -or $malformedHeading) {
        Write-Output '[planning-with-files] Plan format error: phase completion unavailable.'
    } elseif ($COMPLETE -eq $TOTAL -and $TOTAL -gt 0) {
        if ($Gate) { return }
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
}

# ---- Default (advisory) path: byte-equivalent to v2.43 ----
if (-not $Gate) {
    Write-AdvisoryReport
    exit 0
}

# ---- Gate path (-Gate). Resolves to advisory unless every guard says block. ----

# Guard 1: gated mode. A .mode file must contain "gate".
#
# The project's root .mode is a FLOOR, not a default that slug scope replaces
# (issue #238). Reading only <plan-dir>\.mode let a slug plan with no .mode
# drop a project-committed gate. "gate" from EITHER file arms the gate; a slug
# may raise strictness, never lower it. In root scope $PlanDir already IS the
# project root, so the second source is skipped and behavior is unchanged.
$modeFile = Join-Path $PlanDir ".mode"
$rootForMode = if ($env:PWF_PLAN_ROOT) { $env:PWF_PLAN_ROOT } else { "." }
$rootModeFile = $null
if ($PlanDir -ne $rootForMode -and $PlanDir -ne ".") {
    $rootModeFile = Join-Path $rootForMode ".mode"
}
$gatedMode = $false
foreach ($candidateMode in @($modeFile, $rootModeFile)) {
    if (-not $candidateMode) { continue }
    if (-not (Test-Path $candidateMode)) { continue }
    $modeContent = Get-Content $candidateMode -Raw -ErrorAction SilentlyContinue
    if ($null -ne $modeContent -and $modeContent -match "gate") {
        $gatedMode = $true
        break
    }
}
if (-not $gatedMode) {
    Write-AdvisoryReport
    exit 0
}

# Guard 3: stop_hook_active. Read stdin only when input is redirected, so an
# interactive console never blocks. A true value means we are already inside a
# forced continuation; allow the stop.
$stdinJson = ""
try {
    if ([Console]::IsInputRedirected) {
        $stdinJson = [Console]::In.ReadToEnd()
    }
} catch {
    $stdinJson = ""
}
# Anchor on the literal value: "stop_hook_active" then colon then exactly true,
# with a JSON-structural boundary after it (whitespace, comma, closing brace, or
# end of input). Without the boundary 'true' could match a longer token; the
# boundary keeps a 'false' value (or any other key set to true) from tripping
# the guard and silently disabling the gate.
if ($stdinJson -match '"stop_hook_active"\s*:\s*true(\s|,|}|$)') {
    Write-AdvisoryReport
    exit 0
}

# Guard 2: an in_progress phase must exist.
if ($IN_PROGRESS -le 0) {
    Write-AdvisoryReport
    exit 0
}

# ledger_line_count: total lines across all <plan-dir>/ledger-*.jsonl files.
function Get-LedgerLineCount {
    $total = 0
    $files = Get-ChildItem -Path $PlanDir -Filter "ledger-*.jsonl" -File -ErrorAction SilentlyContinue
    foreach ($f in $files) {
        $lines = @(Get-Content $f.FullName -ErrorAction SilentlyContinue)
        $total += $lines.Count
    }
    return $total
}

$cap = 20
if ($env:PWF_GATE_CAP -match '^\d+$') {
    $cap = [int]$env:PWF_GATE_CAP
}

$blocksFile = Join-Path $PlanDir ".stop_blocks"
$blocks = 0
if (Test-Path $blocksFile) {
    $raw = (Get-Content $blocksFile -Raw -ErrorAction SilentlyContinue)
    if ($raw -match '^\s*(\d+)') { $blocks = [int]$Matches[1] }
}

$ledgerFile = Join-Path $PlanDir ".gate_last_ledger"
$ledgerPrev = 0
if (Test-Path $ledgerFile) {
    $raw = (Get-Content $ledgerFile -Raw -ErrorAction SilentlyContinue)
    if ($raw -match '^\s*(\d+)') { $ledgerPrev = [int]$Matches[1] }
}
$ledgerNow = Get-LedgerLineCount

# Guard 4: block-count cap.
if ($blocks -ge $cap) {
    Write-AdvisoryReport
    Write-Host ('[planning-with-files] gate cap reached (' + $blocks + '/' + $cap + ') -- allowing stop.')
    exit 0
}

# Guard 5: stall detection.
if ($blocks -gt 0 -and $ledgerNow -eq $ledgerPrev) {
    Write-AdvisoryReport
    Write-Host '[planning-with-files] no progress since last gate block -- allowing stop.'
    exit 0
}

# All guards passed: block the stop.
# Get-FirstInProgressPhase: heading text of the first phase whose Status is
# in_progress. Plain text only -- no plan body beyond the heading.
function Get-FirstInProgressPhase {
    return ($activeHeading -replace '^ {0,3}### ', '')
}

$phaseName = Get-FirstInProgressPhase
if ($phaseName -eq "") { $phaseName = "unknown phase" }

# JSON-escape: backslash and double-quote, plus every bare control character
# JSON forbids (below 0x20) mapped to a space. A phase heading may carry a
# literal tab; left raw it produces invalid JSON the Stop hook rejects. Same
# logic as ledger-append.ps1 ConvertTo-JsonString.
function ConvertTo-JsonEscaped {
    param([string] $Value)
    $sb = New-Object System.Text.StringBuilder
    foreach ($ch in $Value.ToCharArray()) {
        switch ($ch) {
            '"'  { [void]$sb.Append('\"') }
            '\'  { [void]$sb.Append('\\') }
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
$phaseEscaped = ConvertTo-JsonEscaped $phaseName

$newBlocks = $blocks + 1
# Write sidecars as ASCII (single-byte digits) with an explicit LF and no BOM.
# Set-Content on Windows emits CRLF; check-complete.sh then reads '5\r', whose
# trailing CR makes the numeric guard reset BLOCKS to 0 on every cross-platform
# read, so the cap and stall guards never fire. WriteAllText with ASCII gives
# byte-for-byte '5\n' that both shells parse identically.
try { [System.IO.File]::WriteAllText($blocksFile, [string]$newBlocks + "`n", [System.Text.Encoding]::ASCII) } catch {}
try { [System.IO.File]::WriteAllText($ledgerFile, [string]$ledgerNow + "`n", [System.Text.Encoding]::ASCII) } catch {}

# Reason built from the JSON-escaped phase name; the surrounding template text
# has no quotes or backslashes, so only the heading needs escaping.
$reason = "[planning-with-files] Gated plan incomplete: phase '" + $phaseEscaped + "' is in_progress (" + $COMPLETE + "/" + $TOTAL + " complete, gate block " + $newBlocks + "/" + $cap + "). Finish or update the plan, then stop."

[Console]::Out.Write('{"decision":"block","reason":"' + $reason + '"}' + "`n")
exit 0
