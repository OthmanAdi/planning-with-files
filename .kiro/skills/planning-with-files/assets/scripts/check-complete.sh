#!/usr/bin/env sh
# Report phase completion status for task_plan.md (stdout only, always exit 0).
# Default plan path: .kiro/plan/task_plan.md (relative to current directory).

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
    PLAN_FILE="${VALIDATION_PLAN:-.kiro/plan/task_plan.md}"
    [ -f "$PLAN_FILE" ] || { echo "[planning-with-files] Plan format invalid: task_plan.md was not found." >&2; exit 1; }
fi

# issue #195: per-invocation opt-out (PLANNING_DISABLED=1) for one-shot/CI
# sessions that share a cwd with a plan but never opted into it.
[ "${PLANNING_DISABLED:-}" = "1" ] && [ "$VALIDATE" -eq 0 ] && exit 0

PLAN_FILE="${1:-.kiro/plan/task_plan.md}"
[ "$VALIDATE" -eq 0 ] || PLAN_FILE="${VALIDATION_PLAN:-.kiro/plan/task_plan.md}"

if [ ! -f "$PLAN_FILE" ]; then
  echo "[planning-with-files] No task plan at $PLAN_FILE — run bootstrap or specify path."
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
                if (fence == "" && marker == "`" && index(substr(trimmed, run + 1), "`")) return 0
                if (fence == "") { fence = marker; fence_length = run }
                else if (marker == fence && run >= fence_length && substr(trimmed, run + 1) ~ /^[ \t]*$/) fence = ""
                return 1
            }
            return fence != ""
        }
        function read_status(line,    token, boundary) {
            while (match(line, /\*\*Status:\*\*[ \t]+(pending|in_progress|complete)([^[:alnum:]_]|$)|\[(pending|in_progress|complete)\]/)) {
                token = substr(line, RSTART, RLENGTH)
                boundary = substr(token, 1, 2) == "**" && token ~ /[^[:alnum:]_]$/
                sub(/^\*\*Status:\*\*[ \t]+|^\[/, "", token)
                sub(/[^a-z_].*$/, "", token)
                status_count++; phase_status = token
                line = substr(line, RSTART + RLENGTH - boundary)
            }
        }
        { sub(/\r$/, "") }
        fenced($0) { next }
        /^### Phase([ \t]|$)/ {
            finish_phase(); total++; in_phase = 1; heading = $0
        }
        !/^### Phase([ \t]|$)/ && /^ ? ? ?(###|##|#)([ \t]|$)/ { finish_phase() }
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
        echo "[planning-with-files] Plan format invalid: use ### Phase headings with exactly one native status per phase."
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
  echo "[planning-with-files] ALL PHASES COMPLETE ($COMPLETE/$TOTAL)."
else
  echo "[planning-with-files] In progress ($COMPLETE/$TOTAL phases complete)."
  if [ "$IN_PROGRESS" -gt 0 ]; then
    echo "[planning-with-files] $IN_PROGRESS phase(s) in_progress."
  fi
  if [ "$PENDING" -gt 0 ]; then
    echo "[planning-with-files] $PENDING phase(s) pending."
  fi
fi
exit 0
