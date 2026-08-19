# 初始化新会话的规划文件
# 用法：.\init-session.ps1 [项目名称]

param(
    [string]$ProjectName = "project"
)

$DATE = Get-Date -Format "yyyy-MM-dd"

Write-Host "正在初始化规划文件：$ProjectName"

# 如果 task_plan.md 不存在则创建
if (-not (Test-Path "task_plan.md")) {
    @"
# 任务计划：[简要描述]

## 目标
[用一句话描述最终状态]

## 当前阶段
阶段 1

## 各阶段

### 阶段 1：需求与发现
- [ ] 理解用户意图
- [ ] 确定约束条件和需求
- [ ] 将发现记录到 findings.md
- **状态：** in_progress

### 阶段 2：规划与结构
- [ ] 确定技术方案
- [ ] 如有需要创建项目结构
- [ ] 记录决策及理由
- **状态：** pending

### 阶段 3：实现
- [ ] 按计划逐步执行
- [ ] 先将代码写入文件再执行
- [ ] 增量测试
- **状态：** pending

### 阶段 4：测试与验证
- [ ] 验证所有需求已满足
- [ ] 将测试结果记录到 progress.md
- [ ] 修复发现的问题
- **状态：** pending

### 阶段 5：交付
- [ ] 检查所有输出文件
- [ ] 确保交付物完整
- [ ] 交付给用户
- **状态：** pending

## 已做决策
| 决策 | 理由 |
|------|------|

## 遇到的错误
| 错误 | 解决方案 |
|------|---------|
"@ | Out-File -FilePath "task_plan.md" -Encoding UTF8
    Write-Host "已创建 task_plan.md"
} else {
    Write-Host "task_plan.md 已存在，跳过"
}

# 如果 findings.md 不存在则创建
if (-not (Test-Path "findings.md")) {
    @"
# 发现与决策

## 需求
-

## 研究发现
-

## 技术决策
| 决策 | 理由 |
|------|------|

## 遇到的问题
| 问题 | 解决方案 |
|------|---------|

## 资源
-
"@ | Out-File -FilePath "findings.md" -Encoding UTF8
    Write-Host "已创建 findings.md"
} else {
    Write-Host "findings.md 已存在，跳过"
}

# 如果 progress.md 不存在则创建
if (-not (Test-Path "progress.md")) {
    @"
# 进度日志

## 会话：$DATE

### 当前状态
- **阶段：** 1 - 需求与发现
- **开始时间：** $DATE

### 已执行操作
-

### 测试结果
| 测试 | 预期 | 实际 | 状态 |
|------|------|------|------|

### 错误
| 错误 | 解决方案 |
|------|---------|
"@ | Out-File -FilePath "progress.md" -Encoding UTF8
    Write-Host "已创建 progress.md"
} else {
    Write-Host "progress.md 已存在，跳过"
}

Write-Host ""
Write-Host "规划文件已初始化！"
Write-Host "文件：task_plan.md, findings.md, progress.md"
