#!/usr/bin/env bash
# Verificar si todas las fases en task_plan.md están completas
# Siempre salir con código 0 — usar stdout para informar el estado
# Llamado por el hook Stop para informar el estado de finalización de la tarea

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
    echo "[planning-with-files-es] No se encontró task_plan.md — no hay sesión de planificación activa."
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
            while (match(line, /\*\*Estado:\*\*[ \t]+(pending|in_progress|complete)([^[:alnum:]_]|$)|\[(pending|in_progress|complete)\]/)) {
                token = substr(line, RSTART, RLENGTH)
                boundary = substr(token, 1, 2) == "**" && token ~ /[^[:alnum:]_]$/
                sub(/^\*\*Estado:\*\*[ \t]+|^\[/, "", token)
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
    echo "[planning-with-files-es] Todas las fases completadas ($COMPLETE/$TOTAL). Si el usuario tiene trabajo adicional, añadir fases en task_plan.md antes de comenzar."
else
    echo "[planning-with-files-es] Tarea en progreso ($COMPLETE/$TOTAL fases completadas). Actualizar progress.md antes de detenerse."
    if [ "$IN_PROGRESS" -gt 0 ]; then
        echo "[planning-with-files-es] $IN_PROGRESS fases aún en progreso."
    fi
    if [ "$PENDING" -gt 0 ]; then
        echo "[planning-with-files-es] $PENDING fases pendientes."
    fi
fi
exit 0
