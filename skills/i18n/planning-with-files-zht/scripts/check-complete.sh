#!/usr/bin/env bash
# 檢查 task_plan.md 中所有階段是否完成
# 始終以退出碼 0 結束 — 使用標準輸出回報狀態
# 由 Stop 鉤子呼叫以回報任務完成狀態

# Explicit creation validation; the existing localized advisory path stays unchanged.
VALIDATE=0
VALIDATION_PLAN=""
for _arg in "$@"; do
    case "$_arg" in
        --validate) VALIDATE=1 ;;
        *) [ -z "$VALIDATION_PLAN" ] && VALIDATION_PLAN="$_arg" ;;
    esac
done
if [ "$VALIDATE" -eq 1 ]; then
    PLAN_FILE="${VALIDATION_PLAN:-task_plan.md}"
    [ -f "$PLAN_FILE" ] || { echo "[planning-with-files] Plan format invalid: task_plan.md was not found." >&2; exit 1; }
fi

# issue #195: per-invocation opt-out (PLANNING_DISABLED=1) for one-shot/CI
# sessions that share a cwd with a plan but never opted into it.
[ "${PLANNING_DISABLED:-}" = "1" ] && [ "$VALIDATE" -eq 0 ] && exit 0

[ "$VALIDATE" -ne 0 ] || PLAN_FILE="${1:-task_plan.md}"

if [ "$VALIDATE" -eq 0 ] && [ ! -f "$PLAN_FILE" ]; then
    # Automatic gate checks have nothing to report without a plan (header:
    # "plans stay silent in --gate mode"); the explicit report keeps its notice.
    [ "$GATE" -eq 1 ] && exit 0
    echo "[planning-with-files] 未找到 task_plan.md — 沒有進行中的規劃會話。"
    exit 0
fi

# Count native statuses inside real phases, excluding fenced examples (#377).
PLAN_COUNTS=$(LC_ALL=C awk '
        function finish_phase() {
            if (in_phase) {
                if (status_count != 1) invalid = 1
                else {
                    if (phase_status != "in_progress") counts[phase_status]++
                }
                if (has_active_status) {
                    counts["in_progress"]++
                    if (active_heading == "") active_heading = heading
                }
            }
            in_phase = 0; status_count = 0; phase_status = ""; has_active_status = 0
        }
        function fenced(line,    trimmed, marker, run) {
            trimmed = line; sub(/^ ? ? ?/, "", trimmed)
            if (line ~ /^ ? ? ?```/ || line ~ /^ ? ? ?~~~/) {
                marker = substr(trimmed, 1, 1); run = 0
                while (substr(trimmed, run + 1, 1) == marker) run++
                if (fence == "" && marker == "`" && index(substr(trimmed, run + 1), "`")) return 0
                if (fence == "") { fence = marker; fence_length = run }
                else if (marker == fence && run >= fence_length && substr(trimmed, run + 1) ~ /^[ \t]*$/) fence = ""
                return 1
            }
            return fence != ""
        }
        function read_status(line,    token, boundary) {
            while (match(line, /\*\*狀態：\*\*[ \t]+(pending|in_progress|complete)([^A-Za-z0-9_]|$)|\[(pending|in_progress|complete)\]/)) {
                token = substr(line, RSTART, RLENGTH)
                boundary = substr(token, 1, 2) == "**" && token ~ /[^A-Za-z0-9_]$/
                sub(/^\*\*狀態：\*\*[ \t]+|^\[/, "", token)
                sub(/[^a-z_].*$/, "", token)
                status_count++; phase_status = token
                if (token == "in_progress") has_active_status = 1
                line = substr(line, RSTART + RLENGTH - boundary)
            }
        }
        NR == 1 { sub(/^\357\273\277/, "") }
        { sub(/\r$/, "") }
        fenced($0) || /^ ? ? ?>/ { next }
        /^ ? ? ?### 階段([0-9:]|-[0-9])/ { finish_phase(); malformed_heading = 1; next }
        /^ ? ? ?### 階段([ \t]|$)/ {
            finish_phase(); total++; in_phase = 1; heading = $0
        }
        !/^ ? ? ?### 階段([ \t]|$)/ && /^ ? ? ?(###|##|#)([ \t]|$)/ { finish_phase() }
        in_phase { read_status($0) }
        END {
            finish_phase()
            printf "%d %d %d %d %d %d\n%s\n", total, counts["complete"], counts["in_progress"], counts["pending"], invalid, (fence != "" || malformed_heading), active_heading
        }
    ' 2>/dev/null < "$PLAN_FILE") || PLAN_COUNTS="0 0 0 0 0 1"
read -r TOTAL COMPLETE IN_PROGRESS PENDING INVALID UNKNOWN <<EOF
$PLAN_COUNTS
EOF

if [ "$VALIDATE" -eq 1 ]; then
    if [ "$TOTAL" -eq 0 ] || [ "$INVALID" -ne 0 ] || [ "$UNKNOWN" -ne 0 ]; then
        echo "[planning-with-files] Plan format invalid: use ### 階段 headings with exactly one native status per phase."
        exit 1
    fi
    printf '[planning-with-files] Plan format valid (%d phases).\n' "$TOTAL"
    exit 0
fi

# issue #191: TOTAL=0 -> not phase-structured, stay silent
if [ "$TOTAL" -eq 0 ] && [ "$UNKNOWN" -eq 0 ]; then
    exit 0
fi

if [ "$UNKNOWN" -ne 0 ]; then
  echo "[planning-with-files] Plan format or read error: phase completion unavailable."
elif [ "$COMPLETE" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
    echo "[planning-with-files] 所有階段已完成（$COMPLETE/$TOTAL）。如果使用者有額外工作，請在開始前於 task_plan.md 中新增階段。"
else
    echo "[planning-with-files] 任務進行中（$COMPLETE/$TOTAL 個階段已完成）。停止前請更新 progress.md。"
    if [ "$IN_PROGRESS" -gt 0 ]; then
        echo "[planning-with-files] $IN_PROGRESS 個階段仍在進行中。"
    fi
    if [ "$PENDING" -gt 0 ]; then
        echo "[planning-with-files] $PENDING 個階段待處理。"
    fi
fi
exit 0
