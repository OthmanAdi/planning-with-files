# 检查 task_plan.md 中所有阶段是否完成
# 始终以退出码 0 结束 — 使用标准输出报告状态
# 由 Stop 钩子调用以报告任务完成状态

param(
    [string]$PlanFile = "task_plan.md"
)

# issue #195: per-invocation opt-out (PLANNING_DISABLED=1) for one-shot/CI
# sessions that share a cwd with a plan but never opted into it.
if ($env:PLANNING_DISABLED -eq '1') { exit 0 }

if (-not (Test-Path $PlanFile)) {
    Write-Host '[planning-with-files] 未找到 task_plan.md — 没有进行中的规划会话。'
    exit 0
}

# 读取文件内容
$content = Get-Content $PlanFile -Raw

# 计算阶段总数
$TOTAL = ([regex]::Matches($content, "### 阶段")).Count

# 先检查 **状态：** 格式
$COMPLETE = ([regex]::Matches($content, "\*\*状态：\*\* complete")).Count
$IN_PROGRESS = ([regex]::Matches($content, "\*\*状态：\*\* in_progress")).Count
$PENDING = ([regex]::Matches($content, "\*\*状态：\*\* pending")).Count

# 备用：如果未找到 **状态：** 则检查 [complete] 行内格式
if ($COMPLETE -eq 0 -and $IN_PROGRESS -eq 0 -and $PENDING -eq 0) {
    $COMPLETE = ([regex]::Matches($content, "\[complete\]")).Count
    $IN_PROGRESS = ([regex]::Matches($content, "\[in_progress\]")).Count
    $PENDING = ([regex]::Matches($content, "\[pending\]")).Count
}

# 报告状态 — 始终以退出码 0 结束，未完成的任务是正常状态
if ($COMPLETE -eq $TOTAL -and $TOTAL -gt 0) {
    Write-Host ('[planning-with-files] 所有阶段已完成（' + $COMPLETE + '/' + $TOTAL + '）。如果用户有额外工作，请在开始前于 task_plan.md 中新增阶段。')
} else {
    Write-Host ('[planning-with-files] 任务进行中（' + $COMPLETE + '/' + $TOTAL + ' 个阶段已完成）。停止前请更新 progress.md。')
    if ($IN_PROGRESS -gt 0) {
        Write-Host ('[planning-with-files] ' + $IN_PROGRESS + ' 个阶段仍在进行中。')
    }
    if ($PENDING -gt 0) {
        Write-Host ('[planning-with-files] ' + $PENDING + ' 个阶段待处理。')
    }
}
exit 0
