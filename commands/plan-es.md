---
description: "Iniciar planificación de archivos estilo Manus. Crear task_plan.md, findings.md, progress.md para tareas complejas."
---

Lee el texto de la habilidad en español desde la primera de estas rutas que exista y síguelo estrictamente:

- `$HOME/.claude/skills/planning-with-files-es/SKILL.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/i18n/planning-with-files-es/SKILL.md`

Si ninguna de las dos rutas existe, invoca la habilidad planning-with-files:planning-with-files y continúa trabajando en español.

Si los tres archivos de planificación no existen en el directorio del proyecto actual, créalos:
- task_plan.md — para fases, progreso y decisiones
- findings.md — para investigación y descubrimientos
- progress.md — para registro de sesión

Luego guía al usuario a través del flujo de trabajo de planificación. Todos los archivos de planificación deben estar en español.

Los marcadores de estado se mantienen literalmente en inglés (`**Status:** in_progress`, `**Status:** complete`) porque `check-complete.sh` los busca con `grep -F`. Traducirlos desactivaría la verificación de finalización.
