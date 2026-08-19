#!/usr/bin/env bash
# 检查 task_plan.md 中所有阶段是否完成
# 始终以退出码 0 结束 — 使用标准输出报告状态
# 由 Stop 钩子调用以报告任务完成状态

# issue #195: per-invocation opt-out (PLANNING_DISABLED=1) for one-shot/CI
# sessions that share a cwd with a plan but never opted into it.
[ "${PLANNING_DISABLED:-}" = "1" ] && exit 0

PLAN_FILE="${1:-task_plan.md}"

if [ ! -f "$PLAN_FILE" ]; then
    echo "[planning-with-files] 未找到 task_plan.md — 没有进行中的规划会话。"
    exit 0
fi

# 计算阶段总数
TOTAL=$(grep -c "### 阶段" "$PLAN_FILE" || true)

# 先检查 **状态：** 格式
COMPLETE=$(grep -cF "**状态：** complete" "$PLAN_FILE" || true)
IN_PROGRESS=$(grep -cF "**状态：** in_progress" "$PLAN_FILE" || true)
PENDING=$(grep -cF "**状态：** pending" "$PLAN_FILE" || true)

# 备用：如果未找到 **状态：** 则检查 [complete] 行内格式
if [ "$COMPLETE" -eq 0 ] && [ "$IN_PROGRESS" -eq 0 ] && [ "$PENDING" -eq 0 ]; then
    COMPLETE=$(grep -c "\[complete\]" "$PLAN_FILE" || true)
    IN_PROGRESS=$(grep -c "\[in_progress\]" "$PLAN_FILE" || true)
    PENDING=$(grep -c "\[pending\]" "$PLAN_FILE" || true)
fi

# 默认为 0（如果为空）
: "${TOTAL:=0}"
: "${COMPLETE:=0}"
: "${IN_PROGRESS:=0}"
: "${PENDING:=0}"

# 报告状态（始终以退出码 0 结束 — 未完成的任务是正常状态）
# issue #191: TOTAL=0 -> not phase-structured, stay silent
if [ "$TOTAL" -eq 0 ]; then
    exit 0
fi

if [ "$COMPLETE" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
    echo "[planning-with-files] 所有阶段已完成（$COMPLETE/$TOTAL）。如果用户有额外工作，请在开始前于 task_plan.md 中新增阶段。"
else
    echo "[planning-with-files] 任务进行中（$COMPLETE/$TOTAL 个阶段已完成）。停止前请更新 progress.md。"
    if [ "$IN_PROGRESS" -gt 0 ]; then
        echo "[planning-with-files] $IN_PROGRESS 个阶段仍在进行中。"
    fi
    if [ "$PENDING" -gt 0 ]; then
        echo "[planning-with-files] $PENDING 个阶段待处理。"
    fi
fi
exit 0
