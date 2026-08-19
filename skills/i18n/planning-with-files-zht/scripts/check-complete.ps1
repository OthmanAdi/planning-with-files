# 檢查 task_plan.md 中所有階段是否完成
# 始終以退出碼 0 結束 — 使用標準輸出回報狀態
# 由 Stop 鉤子呼叫以回報任務完成狀態

param(
    [string]$PlanFile = "task_plan.md"
)

# issue #195: per-invocation opt-out (PLANNING_DISABLED=1) for one-shot/CI
# sessions that share a cwd with a plan but never opted into it.
if ($env:PLANNING_DISABLED -eq '1') { exit 0 }

if (-not (Test-Path $PlanFile)) {
    Write-Host '[planning-with-files] 未找到 task_plan.md — 沒有進行中的規劃會話。'
    exit 0
}

# 讀取檔案內容
$content = Get-Content $PlanFile -Raw

# 計算階段總數
$TOTAL = ([regex]::Matches($content, "### 階段")).Count

# 先檢查 **狀態：** 格式
$COMPLETE = ([regex]::Matches($content, "\*\*狀態：\*\* complete")).Count
$IN_PROGRESS = ([regex]::Matches($content, "\*\*狀態：\*\* in_progress")).Count
$PENDING = ([regex]::Matches($content, "\*\*狀態：\*\* pending")).Count

# 備用：如果未找到 **狀態：** 則檢查 [complete] 行內格式
if ($COMPLETE -eq 0 -and $IN_PROGRESS -eq 0 -and $PENDING -eq 0) {
    $COMPLETE = ([regex]::Matches($content, "\[complete\]")).Count
    $IN_PROGRESS = ([regex]::Matches($content, "\[in_progress\]")).Count
    $PENDING = ([regex]::Matches($content, "\[pending\]")).Count
}

# 回報狀態 — 始終以退出碼 0 結束，未完成的任務是正常狀態
if ($COMPLETE -eq $TOTAL -and $TOTAL -gt 0) {
    Write-Host ('[planning-with-files] 所有階段已完成（' + $COMPLETE + '/' + $TOTAL + '）。如果使用者有額外工作，請在開始前於 task_plan.md 中新增階段。')
} else {
    Write-Host ('[planning-with-files] 任務進行中（' + $COMPLETE + '/' + $TOTAL + ' 個階段已完成）。停止前請更新 progress.md。')
    if ($IN_PROGRESS -gt 0) {
        Write-Host ('[planning-with-files] ' + $IN_PROGRESS + ' 個階段仍在進行中。')
    }
    if ($PENDING -gt 0) {
        Write-Host ('[planning-with-files] ' + $PENDING + ' 個階段待處理。')
    }
}
exit 0
