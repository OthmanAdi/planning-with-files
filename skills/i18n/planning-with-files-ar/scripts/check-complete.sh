#!/usr/bin/env bash
# التحقق من اكتمال جميع المراحل في task_plan.md
# ينهي دائمًا برمز خروج 0 — يستخدم stdout للإبلاغ عن الحالة
# يُستدعى بواسطة خطاف Stop للإبلاغ عن حالة اكتمال المهمة

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

PLAN_FILE="${1:-task_plan.md}"
[ "$VALIDATE" -eq 0 ] || PLAN_FILE="${VALIDATION_PLAN:-task_plan.md}"

if [ ! -f "$PLAN_FILE" ]; then
    # Automatic gate checks have nothing to report without a plan (header:
    # "plans stay silent in --gate mode"); the explicit report keeps its notice.
    [ "$GATE" -eq 1 ] && exit 0
    echo "[planning-with-files-ar] لم يتم العثور على task_plan.md — لا توجد جلسة تخطيط نشطة."
    exit 0
fi

# Count native statuses inside real phases, excluding fenced examples (#377).
PLAN_COUNTS=$(awk '
        function finish_phase() {
            if (in_phase) {
                if (status_count != 1) invalid = 1
                else {
                    counts[phase_status]++
                    if (phase_status == "in_progress" && active_heading == "") active_heading = heading
                }
            }
            in_phase = 0; status_count = 0; phase_status = ""
        }
        function fenced(line,    trimmed, marker, run) {
            trimmed = line; sub(/^ ? ? ?/, "", trimmed)
            if (line ~ /^ ? ? ?```/ || line ~ /^ ? ? ?~~~/) {
                marker = substr(trimmed, 1, 1); run = 0
                while (substr(trimmed, run + 1, 1) == marker) run++
                if (fence == "") { fence = marker; fence_length = run }
                else if (marker == fence && run >= fence_length && substr(trimmed, run + 1) ~ /^[ \t]*$/) fence = ""
                return 1
            }
            return fence != ""
        }
        function read_status(line,    token, boundary) {
            while (match(line, /\*\*الحالة:\*\*[ \t]+(pending|in_progress|complete)([^[:alnum:]_]|$)|\[(pending|in_progress|complete)\]/)) {
                token = substr(line, RSTART, RLENGTH)
                boundary = substr(token, 1, 2) == "**" && token ~ /[^[:alnum:]_]$/
                sub(/^\*\*الحالة:\*\*[ \t]+|^\[/, "", token)
                sub(/[^a-z_].*$/, "", token)
                status_count++; phase_status = token
                line = substr(line, RSTART + RLENGTH - boundary)
            }
        }
        { sub(/\r$/, "") }
        fenced($0) { next }
        /^### المرحلة([ \t]|$)/ {
            finish_phase(); total++; in_phase = 1; heading = $0
        }
        !/^### المرحلة([ \t]|$)/ && /^#{1,3}([ \t]|$)/ { finish_phase() }
        in_phase { read_status($0) }
        END {
            finish_phase()
            printf "%d %d %d %d %d\n%s\n", total, counts["complete"], counts["in_progress"], counts["pending"], invalid, active_heading
        }
    ' "$PLAN_FILE")
read -r TOTAL COMPLETE IN_PROGRESS PENDING INVALID <<EOF
$PLAN_COUNTS
EOF

if [ "$VALIDATE" -eq 1 ]; then
    if [ "$TOTAL" -eq 0 ] || [ "$INVALID" -ne 0 ]; then
        echo "[planning-with-files] Plan format invalid: use ### المرحلة headings with exactly one native status per phase."
        exit 1
    fi
    printf '[planning-with-files] Plan format valid (%d phases).\n' "$TOTAL"
    exit 0
fi

# issue #191: TOTAL=0 -> not phase-structured, stay silent
if [ "$TOTAL" -eq 0 ]; then
    exit 0
fi

if [ "$COMPLETE" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
    echo "[planning-with-files-ar] اكتملت جميع المراحل ($COMPLETE/$TOTAL). إذا كان لدى المستخدم عمل إضافي، أضف مراحل في task_plan.md قبل البدء."
else
    echo "[planning-with-files-ar] المهمة قيد التنفيذ ($COMPLETE/$TOTAL مرحلة مكتملة). حدّث progress.md قبل التوقف."
    if [ "$IN_PROGRESS" -gt 0 ]; then
        echo "[planning-with-files-ar] $IN_PROGRESS مرحلة/مراحل لا تزال قيد التنفيذ."
    fi
    if [ "$PENDING" -gt 0 ]; then
        echo "[planning-with-files-ar] $PENDING مرحلة/مراحل معلقة."
    fi
fi
exit 0
