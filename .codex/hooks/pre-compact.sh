#!/bin/sh
# planning-with-files: PreCompact hook for Codex
# Reminds the agent to flush progress before context compaction.

HOOK_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
PLAN_DIR="$(sh "${HOOK_DIR}/resolve-plan-dir.sh" 2>/dev/null)"
PLAN_FILE="${PLAN_DIR:+${PLAN_DIR}/}task_plan.md"

if [ ! -f "$PLAN_FILE" ]; then
    exit 0
fi

if [ -n "$PLAN_DIR" ]; then
    ATTESTATION_FILE="${PLAN_DIR}/.attestation"
else
    ATTESTATION_FILE=".plan-attestation"
fi

echo "[planning-with-files] PreCompact: context compaction is about to occur."
echo "Before compaction completes: ensure progress.md captures recent actions and task_plan.md status reflects current phase."
echo "task_plan.md, findings.md, progress.md remain on disk and will be re-read after compaction."

if [ -f "$ATTESTATION_FILE" ]; then
    ATTEST="$(tr -d '\r\n[:space:]' < "$ATTESTATION_FILE" 2>/dev/null)"
    if [ -n "$ATTEST" ]; then
        echo "Plan-SHA256 at compaction: $ATTEST"
    fi
fi

exit 0
