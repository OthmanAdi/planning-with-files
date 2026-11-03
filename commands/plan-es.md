---
description: "Iniciar planificación de archivos estilo Manus. Crear task_plan.md, findings.md, progress.md para tareas complejas."
---

Lee el texto de la habilidad en español desde la primera de estas rutas que exista y síguelo estrictamente:

- `$HOME/.claude/skills/planning-with-files-es/SKILL.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/i18n/planning-with-files-es/SKILL.md`

Si ninguna de las dos rutas existe, invoca la habilidad planning-with-files:planning-with-files y continúa trabajando en español.

Restaura antes de crear. Si `PWF_PLAN_ROOT` está definido, valida que sea una raíz de proyecto absoluta y existente; rechaza un pin de raíz no válido antes de leer o crear archivos. Si no, la raíz del proyecto es el directorio actual. Resuelve la tarea seleccionada con `sh ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-plan-dir.sh` (PowerShell: `& "$env:CLAUDE_PLUGIN_ROOT\scripts\resolve-plan-dir.ps1"`):
- Un directorio impreso es la tarea seleccionada. Reanúdala: lee sus `task_plan.md`, `findings.md` y `progress.md` y consérvalos; nunca sobrescribas archivos de planificación existentes.
- Una salida vacía con `PLAN_ID` no vacío significa que el selector de plan fue rechazado. Detente y pide al usuario que corrija el pin. No recurras a la raíz ni a otro plan.
- Una salida vacía en la que `resolve-plan-dir.sh --check-ambiguity` (PowerShell: `-CheckAmbiguity`) imprime `PWF_PLAN_AMBIGUOUS_V1` significa que existen varios planes sin selector. Detente y pide al usuario que defina `PLAN_ID=<slug>`.
- En cualquier otro caso, la salida vacía corresponde a la convención antigua (legacy) del plan en la raíz del proyecto: reanuda `task_plan.md` desde la raíz de proyecto validada (`PWF_PLAN_ROOT` si está definido), si existe. Un pin de raíz válido por sí solo no rechaza un plan antiguo en la raíz.

Solo para una tarea nueva, ejecuta el inicializador desde la raíz de proyecto validada, incluso cuando `PWF_PLAN_ROOT` apunte fuera del cwd del host: `sh ${CLAUDE_PLUGIN_ROOT}/scripts/init-session.sh` (PowerShell: `init-session.ps1`). Pasa un nombre de tarea para obtener un plan aislado en `.planning/<id>/` y fija el host con el `PLAN_ID` impreso. `.planning/.active_plan` es solo un valor predeterminado compartido; no vincula una sesión paralela.
- task_plan.md — para fases, progreso y decisiones
- findings.md — para investigación y descubrimientos
- progress.md — para registro de sesión

Conserva cada encabezado `### Phase N: Name` con exactamente una línea `**Status:**` y luego valida la ruta explícita del plan seleccionado con `sh ${CLAUDE_PLUGIN_ROOT}/scripts/check-complete.sh --validate path/to/task_plan.md` (PowerShell: `check-complete.ps1 -Validate -PlanFile path/to/task_plan.md`). Si un plan existente no pasa la validación, infórmalo en lugar de reescribirlo.

Luego guía al usuario a través del flujo de trabajo de planificación. Todos los archivos de planificación deben estar en español.

Los marcadores de estado se mantienen literalmente en inglés (`**Status:** in_progress`, `**Status:** complete`) porque `check-complete.sh` los busca con `grep -F`. Traducirlos desactivaría la verificación de finalización.
