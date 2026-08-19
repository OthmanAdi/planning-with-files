---
description: "启动 Manus 风格的文件规划。为复杂任务创建 task_plan.md、findings.md、progress.md。"
---

从以下路径中第一个存在的文件读取中文技能正文，并严格按照其指示执行：

- `$HOME/.claude/skills/planning-with-files-zh/SKILL.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/i18n/planning-with-files-zh/SKILL.md`

如果两个路径都不存在，请调用 planning-with-files:planning-with-files 技能，并继续用中文工作。

如果当前项目目录中不存在以下三个规划文件，请创建它们：
- task_plan.md — 用于阶段、进度和决策
- findings.md — 用于研究和发现
- progress.md — 用于会话日志

然后引导用户完成规划工作流。所有规划文件内容使用中文。

状态标记保持英文原样（`**Status:** in_progress`、`**Status:** complete`），因为 `check-complete.sh` 使用 `grep -F` 匹配它们，翻译这些标记会使完成检查失效。
