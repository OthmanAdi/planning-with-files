# التحقق من اكتمال جميع المراحل في task_plan.md
# ينهي دائمًا برمز خروج 0 — يستخدم stdout للإبلاغ عن الحالة
# يُستدعى بواسطة خطاف Stop للإبلاغ عن حالة اكتمال المهمة

param(
    [string]$PlanFile = "task_plan.md"
)

# issue #195: per-invocation opt-out (PLANNING_DISABLED=1) for one-shot/CI
# sessions that share a cwd with a plan but never opted into it.
if ($env:PLANNING_DISABLED -eq '1') { exit 0 }

if (-not (Test-Path $PlanFile)) {
    Write-Host '[planning-with-files-ar] لم يتم العثور على task_plan.md — لا توجد جلسة تخطيط نشطة.'
    exit 0
}

# قراءة محتوى الملف
$content = Get-Content $PlanFile -Raw

# حساب إجمالي عدد المراحل
$TOTAL = ([regex]::Matches($content, "### المرحلة")).Count

# التحقق أولاً من تنسيق **الحالة:**
$COMPLETE = ([regex]::Matches($content, "\*\*الحالة:\*\* complete")).Count
$IN_PROGRESS = ([regex]::Matches($content, "\*\*الحالة:\*\* in_progress")).Count
$PENDING = ([regex]::Matches($content, "\*\*الحالة:\*\* pending")).Count

# بديل: إذا لم يتم العثور على **الحالة:** فتحقق من تنسيق [complete] المضمن
if ($COMPLETE -eq 0 -and $IN_PROGRESS -eq 0 -and $PENDING -eq 0) {
    $COMPLETE = ([regex]::Matches($content, "\[complete\]")).Count
    $IN_PROGRESS = ([regex]::Matches($content, "\[in_progress\]")).Count
    $PENDING = ([regex]::Matches($content, "\[pending\]")).Count
}

# الإبلاغ عن الحالة — ينهي دائمًا برمز خروج 0، المهام غير المكتملة حالة طبيعية
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
