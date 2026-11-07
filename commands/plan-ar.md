---
description: "بدء تخطيط الملفات بنمط Manus. إنشاء task_plan.md و findings.md و progress.md للمهام المعقدة."
---

اقرأ نص المهارة العربية من أول مسار موجود من هذين المسارين ونفّذ تعليماته بدقة:

- `$HOME/.claude/skills/planning-with-files-ar/SKILL.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/i18n/planning-with-files-ar/SKILL.md`

إذا لم يكن أي من المسارين موجودًا، استدعِ مهارة planning-with-files:planning-with-files وتابع العمل باللغة العربية.

استعِد قبل أن تُنشئ. إذا كان `PWF_PLAN_ROOT` مضبوطًا، فتحقّق من أنه جذر مشروع مطلق وموجود، وارفض أي تثبيت غير صالح للجذر قبل قراءة أي ملف أو إنشائه. وإلا فجذر المشروع هو المجلد الحالي. حدّد المهمة المختارة باستخدام `sh ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-plan-dir.sh` (وفي PowerShell: `& "$env:CLAUDE_PLUGIN_ROOT\scripts\resolve-plan-dir.ps1"`):
- إذا طُبع مجلد فهو المهمة المختارة. استأنفها: اقرأ ملفاتها `task_plan.md` و`findings.md` و`progress.md` وحافظ عليها، ولا تكتب أبدًا فوق ملفات تخطيط موجودة.
- الإخراج الفارغ مع `PLAN_ID` غير فارغ يعني أن محدِّد الخطة مرفوض. توقّف واطلب من المستخدم تصحيح التثبيت. لا ترجع إلى الجذر ولا إلى خطة أخرى.
- الإخراج الفارغ مع طباعة `resolve-plan-dir.sh --check-ambiguity` (وفي PowerShell: `-CheckAmbiguity`) للقيمة `PWF_PLAN_AMBIGUOUS_V1` يعني وجود عدة خطط دون محدِّد. توقّف واطلب من المستخدم ضبط `PLAN_ID=<slug>`.
- في غير ذلك، يعني الإخراج الفارغ الاصطلاح القديم (legacy) لخطة في جذر المشروع: استأنف `task_plan.md` من جذر المشروع الذي تم التحقق منه (`PWF_PLAN_ROOT` إذا كان مضبوطًا) إن كان موجودًا. تثبيت جذر صالح وحده لا يرفض خطة قديمة في الجذر.

لمهمة جديدة فقط، شغّل أداة التهيئة من جذر المشروع الذي تم التحقق منه، حتى عندما يشير `PWF_PLAN_ROOT` إلى مكان غير cwd المضيف: `sh ${CLAUDE_PLUGIN_ROOT}/scripts/init-session.sh` (وفي PowerShell: `init-session.ps1`). مرّر اسم مهمة للحصول على خطة معزولة في `.planning/<id>/` وثبّت المضيف بـ `PLAN_ID` المطبوع. الملف `.planning/.active_plan` مجرد قيمة افتراضية مشتركة، ولا يربط جلسة موازية.
- task_plan.md — للمراحل والتقدم والقرارات
- findings.md — للبحث والاكتشافات
- progress.md — لسجل الجلسة

احتفظ بكل عنوان `### Phase N: Name` مع سطر `**Status:**` واحد فقط، ثم تحقّق من المسار الصريح للخطة المختارة باستخدام `sh ${CLAUDE_PLUGIN_ROOT}/scripts/check-complete.sh --validate path/to/task_plan.md` (وفي PowerShell: `check-complete.ps1 -Validate -PlanFile path/to/task_plan.md`). إذا فشلت خطة موجودة في التحقق، فأبلغ عن ذلك بدلًا من إعادة كتابتها.

ثم ارشد المستخدم خلال سير عمل التخطيط. جميع ملفات التخطيط يجب أن تكون باللغة العربية.

تبقى علامات الحالة بالإنجليزية حرفيًا (`**Status:** in_progress` و `**Status:** complete`) لأن `check-complete.sh` يبحث عنها باستخدام `grep -F`، وترجمتها تُعطّل بوابة الإكمال.
