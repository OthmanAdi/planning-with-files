# التحقق من اكتمال جميع المراحل في task_plan.md
# ينهي دائمًا برمز خروج 0 — يستخدم stdout للإبلاغ عن الحالة
# يُستدعى بواسطة خطاف Stop للإبلاغ عن حالة اكتمال المهمة

param(
    [string]$PlanFile = "task_plan.md",
    [switch]$Validate
)

if ($Validate) {
    if (-not (Test-Path -LiteralPath $PlanFile -PathType Leaf)) { Write-Output '[planning-with-files] Plan format invalid: task_plan.md was not found.'; exit 1 }
    $content = Get-Content -LiteralPath $PlanFile -Raw
}

# issue #195: per-invocation opt-out (PLANNING_DISABLED=1) for one-shot/CI
# sessions that share a cwd with a plan but never opted into it.
if ($env:PLANNING_DISABLED -eq '1' -and -not $Validate) { exit 0 }

if (-not (Test-Path -LiteralPath $PlanFile)) {
    # Automatic gate checks have nothing to report without a plan; the explicit report keeps its notice.
    if ($Gate) { exit 0 }
    Write-Host '[planning-with-files-ar] لم يتم العثور على task_plan.md — لا توجد جلسة تخطيط نشطة.'
    exit 0
}

# قراءة محتوى الملف
$content = Get-Content -LiteralPath $PlanFile -Raw

# حساب إجمالي عدد المراحل
# Count native statuses inside real phases, excluding fenced examples (#377).
$counts = @{ total = 0; complete = 0; in_progress = 0; pending = 0 }
$phase = $null
$invalid = $false
$activeHeading = ""
$fence = ""
$fenceLength = 0
function Complete-المرحلة {
    if ($null -ne $script:phase) {
        if ($script:phase.Statuses.Count -ne 1) { $script:invalid = $true }
        else {
            $state = $script:phase.Statuses[0]
            $script:counts[$state]++
            if ($state -eq 'in_progress' -and -not $script:activeHeading) {
                $script:activeHeading = $script:phase.Heading
            }
        }
    }
    $script:phase = $null
}
foreach ($line in ($content -split '\r?\n')) {
    if ($fence) {
        if ($line -match ('^ {0,3}' + [regex]::Escape($fence) + '{' + $fenceLength + ',}[ \t]*$')) { $fence = "" }
        continue
    }
    if ($line -match '^ {0,3}(`{3,}|~{3,})' -and
        ($Matches[1][0] -eq '~' -or -not $line.Substring($Matches[0].Length).Contains('`'))) {
        $fence = $Matches[1].Substring(0, 1); $fenceLength = $Matches[1].Length
        continue
    }
    if ($line -cmatch '^### المرحلة(?:[ \t]|$)') {
        Complete-المرحلة
        $counts.total++
        $phase = @{ Heading = $line; Statuses = @() }
    } elseif ($line -match '^ {0,3}#{1,3}(?:[ \t]|$)') {
        Complete-المرحلة
    }
    if ($null -ne $phase) {
        foreach ($match in [regex]::Matches($line, '\*\*الحالة:\*\*[ \t]+(pending|in_progress|complete)(?![\p{L}\p{N}_])|\[(pending|in_progress|complete)\]')) {
            $state = $match.Groups[1].Value
            if (-not $state) { $state = $match.Groups[2].Value }
            $phase.Statuses += $state
        }
    }
}
Complete-المرحلة
$TOTAL = $counts.total
$COMPLETE = $counts.complete
$IN_PROGRESS = $counts.in_progress
$PENDING = $counts.pending

if ($Validate) {
    if ($TOTAL -eq 0 -or $invalid) {
        Write-Output '[planning-with-files] Plan format invalid: use ### المرحلة headings with exactly one native status per phase.'
        exit 1
    }
    Write-Output ('[planning-with-files] Plan format valid (' + $TOTAL + ' phases).')
    exit 0
}

if ($COMPLETE -eq $TOTAL -and $TOTAL -gt 0) {
    Write-Host ('[planning-with-files-ar] اكتملت جميع المراحل (' + $COMPLETE + '/' + $TOTAL + '). إذا كان لدى المستخدم عمل إضافي، أضف مراحل في task_plan.md قبل البدء.')
} else {
    Write-Host ('[planning-with-files-ar] المهمة قيد التنفيذ (' + $COMPLETE + '/' + $TOTAL + ' مرحلة مكتملة). حدّث progress.md قبل التوقف.')
    if ($IN_PROGRESS -gt 0) {
        Write-Host ('[planning-with-files-ar] ' + $IN_PROGRESS + ' مرحلة/مراحل لا تزال قيد التنفيذ.')
    }
    if ($PENDING -gt 0) {
        Write-Host ('[planning-with-files-ar] ' + $PENDING + ' مرحلة/مراحل معلقة.')
    }
}
exit 0
