#!/usr/bin/env bash
# 初始化新會話的規劃檔案
# 用法：./init-session.sh [專案名稱]

set -e

PROJECT_NAME="${1:-project}"
DATE=$(date +%Y-%m-%d)

echo "正在初始化規劃檔案：$PROJECT_NAME"

# 如果 task_plan.md 不存在則建立
if [ ! -f "task_plan.md" ]; then
    cat > task_plan.md << 'EOF'
# 任務計畫：[簡要描述]

## 目標
[用一句話描述最終狀態]

## 目前階段
階段 1

## 各階段

### 階段 1：需求與發現
- [ ] 理解使用者意圖
- [ ] 確定約束條件和需求
- [ ] 將發現記錄到 findings.md
- **狀態：** in_progress

### 階段 2：規劃與結構
- [ ] 確定技術方案
- [ ] 如有需要建立專案結構
- **狀態：** pending

### 階段 3：實作
- [ ] 按計畫逐步執行
- [ ] 先將程式碼寫入檔案再執行
- **狀態：** pending

### 階段 4：測試與驗證
- [ ] 驗證所有需求已滿足
- [ ] 將測試結果記錄到 progress.md
- **狀態：** pending

### 階段 5：交付
- [ ] 檢查所有輸出檔案
- [ ] 交付給使用者
- **狀態：** pending

## 已做決策
| 決策 | 理由 |
|------|------|

## 遇到的錯誤
| 錯誤 | 解決方案 |
|------|---------|
EOF
    echo "已建立 task_plan.md"
else
    echo "task_plan.md 已存在，跳過"
fi

# 如果 findings.md 不存在則建立
if [ ! -f "findings.md" ]; then
    cat > findings.md << 'EOF'
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
EOF
    echo "已建立 findings.md"
else
    echo "findings.md 已存在，跳過"
fi

# 如果 progress.md 不存在則建立
if [ ! -f "progress.md" ]; then
    cat > progress.md << EOF
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
EOF
    echo "已建立 progress.md"
else
    echo "progress.md 已存在，跳過"
fi

echo ""
echo "規劃檔案初始化完成！"
echo "檔案：task_plan.md、findings.md、progress.md"
