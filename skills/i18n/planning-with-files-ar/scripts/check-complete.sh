#!/usr/bin/env bash
# التحقق من اكتمال جميع المراحل في task_plan.md
# ينهي دائمًا برمز خروج 0 — يستخدم stdout للإبلاغ عن الحالة
# يُستدعى بواسطة خطاف Stop للإبلاغ عن حالة اكتمال المهمة

# issue #195: per-invocation opt-out (PLANNING_DISABLED=1) for one-shot/CI
# sessions that share a cwd with a plan but never opted into it.
[ "${PLANNING_DISABLED:-}" = "1" ] && exit 0

PLAN_FILE="${1:-task_plan.md}"

if [ ! -f "$PLAN_FILE" ]; then
    echo "[planning-with-files-ar] لم يتم العثور على task_plan.md — لا توجد جلسة تخطيط نشطة."
    exit 0
fi

# حساب إجمالي عدد المراحل
TOTAL=$(grep -c "### المرحلة" "$PLAN_FILE" || true)

# التحقق أولاً من تنسيق **الحالة:**
COMPLETE=$(grep -cF "**الحالة:** complete" "$PLAN_FILE" || true)
IN_PROGRESS=$(grep -cF "**الحالة:** in_progress" "$PLAN_FILE" || true)
PENDING=$(grep -cF "**الحالة:** pending" "$PLAN_FILE" || true)

# بديل: إذا لم يتم العثور على **الحالة:** فتحقق من تنسيق [complete] المضمن
if [ "$COMPLETE" -eq 0 ] && [ "$IN_PROGRESS" -eq 0 ] && [ "$PENDING" -eq 0 ]; then
    COMPLETE=$(grep -c "\[complete\]" "$PLAN_FILE" || true)
    IN_PROGRESS=$(grep -c "\[in_progress\]" "$PLAN_FILE" || true)
    PENDING=$(grep -c "\[pending\]" "$PLAN_FILE" || true)
fi

# الافتراضي 0 (إذا كان فارغًا)
: "${TOTAL:=0}"
: "${COMPLETE:=0}"
: "${IN_PROGRESS:=0}"
: "${PENDING:=0}"

# الإبلاغ عن الحالة (ينهي دائمًا برمز خروج 0 — المهام غير المكتملة حالة طبيعية)
# issue #191: TOTAL=0 -> not phase-structured, stay silent
if [ "$TOTAL" -eq 0 ]; then
    exit 0
fi

if [ "$COMPLETE" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
    echo "[planning-with-files-ar] اكتملت جميع المراحل ($COMPLETE/$TOTAL). إذا كان لدى المستخدم عمل إضافي، أضف مراحل في task_plan.md قبل البدء."
else
    echo "[planning-with-files-ar] المهمة قيد التنفيذ ($COMPLETE/$TOTAL مرحلة مكتملة). حدّث progress.md قبل التوقف."
    if [ "$IN_PROGRESS" -gt 0 ]; then
        echo "[planning-with-files-ar] $IN_PROGRESS مرحلة/مراحل لا تزال قيد التنفيذ."
    fi
    if [ "$PENDING" -gt 0 ]; then
        echo "[planning-with-files-ar] $PENDING مرحلة/مراحل معلقة."
    fi
fi
exit 0
