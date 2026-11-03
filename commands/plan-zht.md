---
description: "啟動 Manus 風格的檔案規劃。為複雜任務建立 task_plan.md、findings.md、progress.md。"
---

從以下路徑中第一個存在的檔案讀取繁體中文技能正文，並嚴格按照其指示執行：

- `$HOME/.claude/skills/planning-with-files-zht/SKILL.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/i18n/planning-with-files-zht/SKILL.md`

如果兩個路徑都不存在，請調用 planning-with-files:planning-with-files 技能，並繼續以繁體中文工作。

先還原，再建立。如果設定了 `PWF_PLAN_ROOT`，先驗證它是一個存在的絕對專案根目錄；在讀取或建立任何檔案之前，拒絕無效的根目錄釘選值。否則，專案根目錄就是目前的目錄。以 `sh ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-plan-dir.sh`（PowerShell：`& "$env:CLAUDE_PLUGIN_ROOT\scripts\resolve-plan-dir.ps1"`）解析選定的任務：
- 輸出一個目錄，表示這就是選定的任務。接續該任務：讀取並保留它的 `task_plan.md`、`findings.md` 和 `progress.md`；絕不覆寫既有的規劃檔案。
- 輸出為空且 `PLAN_ID` 非空，表示計畫選擇器被拒絕。停下來，請使用者更正釘選值。不要退回到根目錄或其他計畫。
- 輸出為空，且 `resolve-plan-dir.sh --check-ambiguity`（PowerShell：`-CheckAmbiguity`）輸出 `PWF_PLAN_AMBIGUOUS_V1`，表示存在多個計畫但沒有選擇器。停下來，請使用者設定 `PLAN_ID=<slug>`。
- 其他情況下，空輸出對應舊版（legacy）的專案根目錄慣例：如果已驗證的專案根目錄（設定了 `PWF_PLAN_ROOT` 時即為它）中存在 `task_plan.md`，就從那裡接續。僅有一個有效的根目錄釘選值，並不會拒絕根目錄中的舊版計畫。

只有在開始新任務時，才從已驗證的專案根目錄執行初始化腳本，即使 `PWF_PLAN_ROOT` 指向主機 cwd 以外的位置也是如此：`sh ${CLAUDE_PLUGIN_ROOT}/scripts/init-session.sh`（PowerShell：`init-session.ps1`）。傳入任務名稱以在 `.planning/<id>/` 下建立獨立計畫，並以輸出的 `PLAN_ID` 釘選主機。`.planning/.active_plan` 只是共用的預設值，不會綁定並行的工作階段。
- task_plan.md — 用於階段、進度和決策
- findings.md — 用於研究和發現
- progress.md — 用於工作階段日誌

每個 `### Phase N: Name` 標題下保留且僅保留一行 `**Status:**`，然後以 `sh ${CLAUDE_PLUGIN_ROOT}/scripts/check-complete.sh --validate path/to/task_plan.md`（PowerShell：`check-complete.ps1 -Validate -PlanFile path/to/task_plan.md`）驗證選定計畫的明確路徑。如果既有計畫未通過驗證，請回報問題，不要改寫它。

然後引導使用者完成規劃工作流程。所有規劃檔案內容使用繁體中文。

狀態標記保持英文原樣（`**Status:** in_progress`、`**Status:** complete`），因為 `check-complete.sh` 使用 `grep -F` 比對，翻譯這些標記會使完成檢查失效。
