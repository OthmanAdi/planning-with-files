---
description: "بدء تخطيط الملفات بنمط Manus. إنشاء task_plan.md و findings.md و progress.md للمهام المعقدة."
---

اقرأ نص المهارة العربية من أول مسار موجود من هذين المسارين ونفّذ تعليماته بدقة:

- `$HOME/.claude/skills/planning-with-files-ar/SKILL.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/i18n/planning-with-files-ar/SKILL.md`

إذا لم يكن أي من المسارين موجودًا، استدعِ مهارة planning-with-files:planning-with-files وتابع العمل باللغة العربية.

إذا لم تكن ملفات التخطيط الثلاثة موجودة في مجلد المشروع الحالي، قم بإنشائها:
- task_plan.md — للمراحل والتقدم والقرارات
- findings.md — للبحث والاكتشافات
- progress.md — لسجل الجلسة

ثم ارشد المستخدم خلال سير عمل التخطيط. جميع ملفات التخطيط يجب أن تكون باللغة العربية.

تبقى علامات الحالة بالإنجليزية حرفيًا (`**Status:** in_progress` و `**Status:** complete`) لأن `check-complete.sh` يبحث عنها باستخدام `grep -F`، وترجمتها تُعطّل بوابة الإكمال.
