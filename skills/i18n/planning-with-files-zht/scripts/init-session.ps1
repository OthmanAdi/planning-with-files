# 初始化新會話的規劃檔案
# 用法：.\init-session.ps1 [專案名稱]

param(
    [string]$ProjectName = "project"
)

$ErrorActionPreference = "Stop"

$DATE = Get-Date -Format "yyyy-MM-dd"

Write-Host "正在初始化規劃檔案：$ProjectName"

# 如果 task_plan.md 不存在則建立
if (-not (Test-Path "task_plan.md")) {
    @'
# 任務計畫：[簡要描述]

將此檔案作為任務的持久化路線圖。開始複雜工作前先建立它，並在階段變更時持續更新。

## 目標

用一句清楚的話描述預期的最終結果。

[用一句話描述最終狀態]

## 下一步

記錄接下來唯一要執行的動作。每當目前階段或立即行動變更時都要更新。

[接下來唯一要執行的動作；階段狀態變更時請更新。]

## 目前階段

寫下目前正在處理的階段。

階段 1

## 各階段

將任務拆成三到七個可驗證的階段。每個狀態只能使用 `pending`、`in_progress` 或 `complete`，並在工作推進時更新。

### 階段 1：需求與發現

- [ ] 理解使用者意圖
- [ ] 確定約束條件和需求
- [ ] 將發現記錄到 findings.md
- **狀態：** in_progress

### 階段 2：規劃與結構

- [ ] 確定技術方案
- [ ] 如有需要，建立專案結構
- [ ] 記錄決策及理由
- **狀態：** pending

### 階段 3：實作

- [ ] 按計畫逐步執行
- [ ] 先將程式碼寫入檔案再執行
- [ ] 進行增量測試
- **狀態：** pending

### 階段 4：測試與驗證

- [ ] 驗證所有需求已滿足
- [ ] 將測試結果記錄到 progress.md
- [ ] 修復發現的問題
- **狀態：** pending

### 階段 5：交付

- [ ] 檢查所有輸出檔案
- [ ] 確保交付物完整
- [ ] 交付給使用者
- **狀態：** pending

## 關鍵問題

記錄重要問題，並在問題解決後以答案取代它們。

1. [待回答的問題]
2. [待回答的問題]

## 已做決策

記錄重要選擇及其理由。

| 決策 | 理由 |
|------|------|
|      |      |

## 遇到的錯誤

記錄每個不同的錯誤、嘗試次數與解決方式。再次嘗試失敗的動作前，先改變處理方法。

| 錯誤 | 嘗試次數 | 解決方案 |
|------|---------|---------|
|      | 1       |         |

## 備註

- 隨著工作推進，將階段狀態從 `pending` 更新為 `in_progress`，再更新為 `complete`。
- 做重大決策前，重新閱讀目標與下一步。
- 立即記錄錯誤，避免重複失敗的處理方式。
'@ | Out-File -FilePath "task_plan.md" -Encoding UTF8
    Write-Host "已建立 task_plan.md"
} else {
    Write-Host "task_plan.md 已存在，跳過"
}

# 如果 findings.md 不存在則建立
if (-not (Test-Path "findings.md")) {
    @"
# 發現與決策

## 需求
-

## 研究發現
-

## 技術決策
| 決策 | 理由 |
|------|------|

## 遇到的問題
| 問題 | 解決方案 |
|------|---------|

## 資源
-
"@ | Out-File -FilePath "findings.md" -Encoding UTF8
    Write-Host "已建立 findings.md"
} else {
    Write-Host "findings.md 已存在，跳過"
}

# 如果 progress.md 不存在則建立
if (-not (Test-Path "progress.md")) {
    @"
# 進度日誌

## 會話：$DATE

### 目前狀態
- **階段：** 1 - 需求與發現
- **開始時間：** $DATE

### 執行的操作
-

### 測試結果
| 測試 | 預期結果 | 實際結果 | 狀態 |
|------|---------|---------|------|

### 錯誤
| 錯誤 | 解決方案 |
|------|---------|
"@ | Out-File -FilePath "progress.md" -Encoding UTF8
    Write-Host "已建立 progress.md"
} else {
    Write-Host "progress.md 已存在，跳過"
}

Write-Host ""
Write-Host "規劃檔案初始化完成！"
Write-Host "檔案：task_plan.md、findings.md、progress.md"
