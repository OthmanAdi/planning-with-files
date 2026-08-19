---
description: "啟動 Manus 風格的檔案規劃。為複雜任務建立 task_plan.md、findings.md、progress.md。"
---

從以下路徑中第一個存在的檔案讀取繁體中文技能正文，並嚴格按照其指示執行：

- `$HOME/.claude/skills/planning-with-files-zht/SKILL.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/i18n/planning-with-files-zht/SKILL.md`

如果兩個路徑都不存在，請調用 planning-with-files:planning-with-files 技能，並繼續以繁體中文工作。

如果當前專案目錄中不存在以下三個規劃檔案，請建立它們：
- task_plan.md — 用於階段、進度和決策
- findings.md — 用於研究和發現
- progress.md — 用於工作階段日誌

然後引導使用者完成規劃工作流程。所有規劃檔案內容使用繁體中文。

狀態標記保持英文原樣（`**Status:** in_progress`、`**Status:** complete`），因為 `check-complete.sh` 使用 `grep -F` 比對，翻譯這些標記會使完成檢查失效。
