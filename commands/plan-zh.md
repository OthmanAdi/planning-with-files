---
description: "启动 Manus 风格的文件规划。为复杂任务创建 task_plan.md、findings.md、progress.md。"
---

从以下路径中第一个存在的文件读取中文技能正文，并严格按照其指示执行：

- `$HOME/.claude/skills/planning-with-files-zh/SKILL.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/i18n/planning-with-files-zh/SKILL.md`

如果两个路径都不存在，请调用 planning-with-files:planning-with-files 技能，并继续用中文工作。

先恢复，再创建。如果设置了 `PWF_PLAN_ROOT`，先验证它是一个存在的绝对项目根目录；在读取或创建任何文件之前，拒绝无效的根目录固定值。否则，项目根目录就是当前目录。用 `sh ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-plan-dir.sh`（PowerShell：`& "$env:CLAUDE_PLUGIN_ROOT\scripts\resolve-plan-dir.ps1"`）解析选定的任务：
- 输出一个目录，表示这就是选定的任务。继续该任务：读取并保留它的 `task_plan.md`、`findings.md` 和 `progress.md`；绝不覆盖已有的规划文件。
- 输出为空且 `PLAN_ID` 非空，表示计划选择器被拒绝。停下来，请用户更正固定值。不要退回到根目录或其他计划。
- 输出为空，且 `resolve-plan-dir.sh --check-ambiguity`（PowerShell：`-CheckAmbiguity`）输出 `PWF_PLAN_AMBIGUOUS_V1`，表示存在多个计划但没有选择器。停下来，请用户设置 `PLAN_ID=<slug>`。
- 其他情况下，空输出对应旧版（legacy）的项目根目录约定：如果已验证的项目根目录（设置了 `PWF_PLAN_ROOT` 时即为它）中存在 `task_plan.md`，就从那里继续。仅有一个有效的根目录固定值，并不会拒绝根目录中的旧版计划。

只有在开始新任务时，才从已验证的项目根目录运行初始化脚本，即使 `PWF_PLAN_ROOT` 指向主机 cwd 以外的位置也是如此：`sh ${CLAUDE_PLUGIN_ROOT}/scripts/init-session.sh`（PowerShell：`init-session.ps1`）。传入任务名称以在 `.planning/<id>/` 下创建独立计划，并用输出的 `PLAN_ID` 固定主机。`.planning/.active_plan` 只是共享的默认值，不会绑定并行会话。
- task_plan.md — 用于阶段、进度和决策
- findings.md — 用于研究和发现
- progress.md — 用于会话日志

每个 `### Phase N: Name` 标题下保留且仅保留一行 `**Status:**`，然后用 `sh ${CLAUDE_PLUGIN_ROOT}/scripts/check-complete.sh --validate path/to/task_plan.md`（PowerShell：`check-complete.ps1 -Validate -PlanFile path/to/task_plan.md`）验证选定计划的明确路径。如果已有计划未通过验证，请报告问题，不要重写它。

然后引导用户完成规划工作流。所有规划文件内容使用中文。

状态标记保持英文原样（`**Status:** in_progress`、`**Status:** complete`），因为 `check-complete.sh` 使用 `grep -F` 匹配它们，翻译这些标记会使完成检查失效。
