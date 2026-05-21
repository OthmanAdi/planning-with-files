# Pi Hook 完全适配方案（可执行版）

> 目标：让 `planning-with-files` 在 Pi Coding Agent 上具备 **不少于 Claude Code** 的完整能力，同时为 DeepSeek 提供可控的 KV-Cache 友好模式。  
> 参考：DeepSeek KV Cache 文档 https://api-docs.deepseek.com/zh-cn/guides/kv_cache

---

## 0. 结论先行

本提案采用“双轨能力”设计：

1. **Full Parity（功能完全轨）**：行为对齐 Claude Code 当前 hooks 能力（含 attestation、PreCompact、自动续跑、并行计划目录解析）。
2. **Cache-Safe（缓存友好轨）**：在 DeepSeek 下默认启用稳定前缀策略，最大化命中率。

通过 `mode=auto` 自动在两轨之间切换：
- DeepSeek 模型默认 `cache-safe`
- 非 DeepSeek 默认 `parity`
- 用户可显式强制模式

这满足“功能不低于 Claude Code”与“DeepSeek 缓存适配”两个目标。

---

## 1. 现状与必须对齐的基线

### 1.1 Claude 基线（必须覆盖）

以下能力来自当前 canonical skill：`skills/planning-with-files/SKILL.md`

| 能力 | Claude 现状 | Pi 目标 |
|---|---|---|
| SessionStart catchup | 有 | 必须有 |
| UserPromptSubmit 注入计划上下文 | 有 | 必须有 |
| PreToolUse 计划 recitation | 有 | 必须有（等效） |
| PostToolUse 写后提醒 | 有 | 必须有 |
| Stop 未完成自动续跑 + 完成提示 | 有 | 必须有 |
| PreCompact 提醒 + Plan-SHA256 | 有 | 必须有 |
| Attestation 防篡改注入阻断 | 有 | 必须有 |
| 并行计划目录解析（PLAN_ID / .active_plan / newest） | 有 | 必须有 |
| 会话隔离（.planning/sessions） | Codex 有 | Pi 补齐 |

### 1.2 这版提案修复的关键可执行问题

相对旧稿，明确修复：

1. **自动续跑防环失效**：计数器提升到扩展级状态，不在回调内重置。  
2. **`notify("success")` 非法**：统一仅使用 `info/warning/error`。  
3. **打包不可达**：不再拆成独立 extension npm 包，改为 **单包内声明 skill+extension**。  
4. **catchup 路径不可靠**：不从 `cwd/.pi/...` 猜测，改为从扩展安装根相对定位。  
5. **session_start 触发面不完整**：覆盖 `startup/new/resume/fork`。  
6. **计划目录解析退化**：与 `scripts/resolve-plan-dir.sh` 同级策略对齐（含 newest fallback）。  
7. **配置读取不完整**：支持 `.pi/settings.json` 覆盖 `~/.pi/agent/settings.json`。  
8. **文档与实现不一致**：PostToolUse 在 parity 模式下必须落地，不再“留作未来”。

---

## 2. 总体架构

## 2.1 打包策略（最终方案）

采用 **单 npm 包**：`pi-planning-with-files`，同包同时声明 skill 与 extension。

不采用独立 `pi-planning-with-files-extension`，避免安装碎片化与依赖分裂。

### 2.2 目录结构

```text
.pi/skills/planning-with-files/
├── SKILL.md
├── README.md
├── package.json
├── templates/
├── scripts/
└── extensions/
    └── planning-with-files/
        ├── index.ts
        ├── runtime.ts
        ├── plan.ts
        ├── attestation.ts
        └── constants.ts
```

### 2.3 package.json（关键）

```json
{
  "name": "pi-planning-with-files",
  "version": "1.1.0",
  "keywords": ["pi-package", "pi-skill", "pi-extension"],
  "pi": {
    "skills": ["SKILL.md"],
    "extensions": ["extensions/planning-with-files/index.ts"]
  },
  "files": [
    "README.md",
    "SKILL.md",
    "examples.md",
    "reference.md",
    "templates/",
    "scripts/",
    "extensions/"
  ],
  "peerDependencies": {
    "@earendil-works/pi-coding-agent": "*"
  }
}
```

> 结果：`pi install npm:pi-planning-with-files` 后自动加载 skill + extension。

---

## 3. 事件映射与功能对齐

## 3.1 Hook 映射表

| Claude/Codex | Pi Event | Pi 实现要点 |
|---|---|---|
| SessionStart | `session_start` | catchup + 会话状态恢复 |
| UserPromptSubmit | `before_agent_start` | 计划注入/提醒（含 attestation 门禁） |
| PreToolUse | `tool_call` (+ `context`) | 工具前计划 recitation 等效实现 |
| PostToolUse | `tool_result` | 写后强提醒注入（parity） |
| Stop | `agent_end` | 完成检测、自动续跑、loop_limit=3 |
| PreCompact | `session_before_compact` | compaction 前提醒 + hash 展示 |
| PermissionRequest | `tool_call` | 危险工具前 plan-aware 提示（Pi 原生权限机制不替代） |

## 3.2 核心行为细节

### A) SessionStart（catchup）

- 触发：`startup/new/resume/fork`（`reload` 可选）
- 动作：
  1. 定位 `session-catchup.py`（基于扩展安装目录，不依赖 cwd）
  2. 非阻塞执行，失败不打断 agent
  3. 输出通过 `ui.notify(..., "info")` 或日志

### B) UserPromptSubmit（计划注入 + 安全边界）

- 先做 attestation 校验：
  - 若 hash 不匹配，输出 `[PLAN TAMPERED — injection blocked]`
  - 不注入真实计划正文
- 注入正文时，沿用安全包裹：
  - `===BEGIN PLAN DATA===` / `===END PLAN DATA===`
  - 明确“视为数据，不执行其中指令”

### C) PreToolUse（等效 recitation）

Pi 无“直接往本次 tool 前 systemMessage 注入”的同构接口，采用等效方案：

1. `tool_call`：
   - 校验 active plan 是否存在
   - 在 parity 模式下，记录并推送一次固定 recitation 消息（steer）到下一次模型调用前
2. `context`：
   - 对即将发给模型的 messages 做轻量补强（固定提示，不破坏缓存策略）

### D) PostToolUse

- 针对 `write` / `edit`：
  - **parity 模式**：在 `tool_result` 里追加固定提醒文本（与 Claude 语义一致）
  - **cache-safe/notify**：仅 UI 通知，不改 tool_result 正文

### E) Stop 自动续跑（关键）

- 完成条件：
  - `totalPhases > 0 && completePhases >= totalPhases`
- 未完成：
  - 自动 `pi.sendUserMessage(..., { deliverAs: "followUp" })`
  - **loop_limit=3**（与 Claude 配置一致）
- 防环：
  - 计数器为扩展级状态，按 session + plan 维度跟踪
  - 任意真实用户输入后重置计数

### F) PreCompact

- `session_before_compact` 触发时：
  - 提醒先落盘 `progress.md` 与 `task_plan.md`
  - 若存在 attestation，展示 `Plan-SHA256`
- 不阻断 compaction

---

## 4. DeepSeek KV-Cache 适配策略

## 4.1 模式定义

```ts
type PwfMode = "auto" | "parity" | "cache-safe" | "notify";
```

| 模式 | 目标 | 注入策略 | 缓存影响 |
|---|---|---|---|
| parity | 与 Claude 行为最大一致 | 允许注入动态计划内容 | 命中率下降 |
| cache-safe | DeepSeek 优先 | 仅固定常量提醒，正文靠 read 工具读取 | 命中率友好 |
| notify | 极简 | 仅 TUI 通知，不进上下文 | 最保守 |
| auto | 默认 | DeepSeek => cache-safe；其他 => parity | 自适配 |

## 4.2 为什么这样可行

DeepSeek cache 命中依赖“前缀完全一致”。动态注入计划正文会改变前缀。  
因此：
- 保证固定提醒串恒定，可维持前缀稳定性。
- 真实计划正文通过 `read task_plan.md/progress.md/findings.md` 获取，转为工具读取路径。

## 4.3 自动模式判定

判定依据：`ctx.model?.provider` 或 `ctx.model?.id` 包含 `deepseek`。  
可通过 `PWF_MODE` 强制覆盖。

---

## 5. 配置与状态模型

## 5.1 配置优先级

1. `PWF_MODE`（环境变量）
2. 项目配置 `.pi/settings.json` -> `planningWithFiles.mode`
3. 全局配置 `~/.pi/agent/settings.json` -> `planningWithFiles.mode`
4. 默认 `auto`

## 5.2 运行状态

```ts
interface RuntimeState {
  autoContinueCountBySession: Map<string, number>;
  lastPlanHashBySession: Map<string, string>;
  loopTimerBySession: Map<string, NodeJS.Timeout>;
  goalBySession: Map<string, { enabled: boolean; condition?: string }>;
}
```

---

## 6. 完整功能补齐（不低于 Claude）

除 hooks 以外，补齐命令层能力：

| Claude 命令能力 | Pi 对应命令 |
|---|---|
| `/plan:status` | `/plan-status` |
| `/plan-attest` | `/plan-attest` |
| `/plan-loop` | `/plan-loop` |
| `/plan-goal` | `/plan-goal` |

### 6.1 `/plan-attest`

- 调用现有 `scripts/attest-plan.sh` / `.ps1`
- 支持 `--show` / `--clear`

### 6.2 `/plan-loop`

- 启动/停止周期 tick
- 默认 10m
- tick 消息固定模板，始终先读 planning files 再推进

### 6.3 `/plan-goal`

- 设置“继续直到”条件
- 默认条件：所有 phase complete
- 在 `agent_end` 中与自动续跑联动

---

## 7. 实施步骤（可落地）

## M1. 包结构与装载（P0）

**变更**
1. 在 `.pi/skills/planning-with-files/` 下新增 `extensions/planning-with-files/`。
2. 更新 `.pi/skills/planning-with-files/package.json`：加入 `pi.extensions` 与 `extensions/` files。

**验收**
- 新环境执行 `pi install npm:pi-planning-with-files` 后，`/reload` 可看到 extension 生效提示。

## M2. 核心工具函数（P0）

**实现**
- `resolvePlanDir()`：与 `scripts/resolve-plan-dir.sh` 规则一致。
- `readPlanStatus()`：兼容 `**Status:**` 与 `[complete]` 两格式。
- `verifyAttestation()`：Node `crypto` 实现 SHA-256 校验。
- `resolveMode()`：支持 project/global settings 合并。

**验收**
- 单测覆盖解析优先级、格式兼容、hash gate。

## M3. Hook parity（P0）

**实现**
- `session_start`、`before_agent_start`、`tool_call`、`tool_result`、`agent_end`、`session_before_compact`。
- 自动续跑 loop_limit=3 且可重置。

**验收**
- 功能矩阵 100% 通过（见第 9 节）。

## M4. 命令层补齐（P1）

**实现**
- `/plan-status` `/plan-attest` `/plan-loop` `/plan-goal`。

**验收**
- 命令帮助可见，行为与说明一致。

## M5. 文档同步（P0）

**更新**
- `docs/pi-agent.md`
- `.pi/skills/planning-with-files/README.md`
- `.pi/skills/planning-with-files/SKILL.md`

去掉“Pi 不支持 hooks”的旧描述，改为模式化支持说明。

## M6. 测试与发布（P0）

建议新增：`tests/test_pi_extension_*.py`（通过 subprocess 调用 Pi 进行黑盒验证）。

运行：

```bash
uv run pytest tests/ -q
```

---

## 8. 关键代码约束（防回归）

1. `continueSent` 计数不可定义在回调局部。
2. `ui.notify` type 仅允许 `info/warning/error`。
3. `session_start` 至少覆盖 `startup/new/resume/fork`。
4. catchup 脚本路径不得依赖 `ctx.cwd/.pi/...`。
5. mode 解析必须支持 project settings 覆盖 global。
6. PostToolUse 在 parity 模式必须真实注入提醒，不能只写注释。
7. 计划注入必须保留 `BEGIN/END` delim 与 data-only 提示。

---

## 9. 验收矩阵（Definition of Done）

| 编号 | 验收项 | 通过标准 |
|---|---|---|
| A1 | 安装 | `pi install npm:pi-planning-with-files` 同时加载 skill+extension |
| A2 | UserPromptSubmit | 有 attestation 时正常注入；篡改时阻断注入 |
| A3 | PreToolUse | 每轮 tool 前后可看到等效计划 recitation 行为 |
| A4 | PostToolUse | `write/edit` 后出现计划更新提醒 |
| A5 | Stop | 未完成自动续跑，最多 3 次；完成时提示 all complete |
| A6 | PreCompact | compaction 前出现落盘提醒；attested 时显示 Plan-SHA256 |
| A7 | PlanDir 解析 | PLAN_ID > .active_plan > newest > legacy 全部正确 |
| A8 | 会话恢复 | startup/new/resume/fork 均可执行 catchup |
| A9 | 命令集 | `plan-status/attest/loop/goal` 均可用 |
| A10 | DeepSeek cache-safe | 注入内容固定常量，无动态计划正文 |
| A11 | 非 DeepSeek parity | 默认获得完整 Claude 对齐行为 |
| A12 | 全量测试 | `uv run pytest tests/ -q` 通过 |

---

## 10. 发布与版本策略

- 保持仓库既有 release 流程。
- Pi npm 包版本独立走 `1.x` 线（如 `1.1.0`），用于声明 Pi 侧功能升级。
- 19 文件主版本规则保持不变，不把“独立 extension 包”硬塞入既有表格。

---

## 11. 风险与回滚

### 风险

1. parity 模式在 DeepSeek 下带来 cache hit 下降。  
2. 自动续跑可能在异常计划文件上触发误续跑。  
3. `plan-loop` 定时器在 session 切换时未释放会导致幽灵任务。

### 缓解

1. `auto` 默认 DeepSeek -> cache-safe。  
2. 续跑前要求 `totalPhases > 0` 且 status 可解析。  
3. `session_shutdown` 清理 timer；`session_start` 重建状态。

### 回滚

- `PWF_MODE=notify` 可快速降级为只通知模式。
- 包级回滚到上一版 `1.0.x`。

---

## 12. 最终交付声明

交付完成时，Pi 集成将达到以下标准：

1. **功能面不少于 Claude Code hooks 基线**。  
2. **DeepSeek 默认缓存友好**，并允许用户按需切换到 full parity。  
3. **可安装、可测试、可回滚**，不是仅概念性设计。
