# Inicializar archivos de planificación para una nueva sesión
# Uso: .\init-session.ps1 [nombre_del_proyecto]

param(
    [string]$ProjectName = "project"
)

$DATE = Get-Date -Format "yyyy-MM-dd"

Write-Host "Inicializando archivos de planificación: $ProjectName"

# Crear task_plan.md si no existe
if (-not (Test-Path "task_plan.md")) {
    @"
# Plan de Tarea: [descripción breve]

## Objetivo
[describir el estado final en una frase]

## Fase Actual
Fase 1

## Fases

### Fase 1: Requisitos y Descubrimiento
- [ ] Comprender la intención del usuario
- [ ] Identificar restricciones y requisitos
- [ ] Documentar hallazgos en findings.md
- **Status:** in_progress

### Fase 2: Planificación y Estructura
- [ ] Definir enfoque técnico
- [ ] Crear estructura de proyecto si es necesario
- **Status:** pending

### Fase 3: Implementación
- [ ] Ejecutar paso a paso según el plan
- [ ] Escribir código en archivos antes de ejecutar
- **Status:** pending

### Fase 4: Pruebas y Validación
- [ ] Verificar que todos los requisitos están satisfechos
- [ ] Documentar resultados de pruebas en progress.md
- **Status:** pending

### Fase 5: Entrega
- [ ] Revisar todos los archivos de salida
- [ ] Entregar al usuario
- **Status:** pending

## Decisiones Tomadas
| Decisión | Justificación |
|------|------|

## Errores Encontrados
| Error | Solución |
|------|---------|
"@ | Out-File -FilePath "task_plan.md" -Encoding UTF8
    Write-Host "Creado task_plan.md"
} else {
    Write-Host "task_plan.md ya existe, omitiendo"
}

# Crear findings.md si no existe
if (-not (Test-Path "findings.md")) {
    @"
# Hallazgos y Decisiones

## Requisitos
-

## Hallazgos de Investigación
-

## Decisiones Técnicas
| Decisión | Justificación |
|------|------|

## Problemas Encontrados
| Problema | Solución |
|------|---------|

## Recursos
-
"@ | Out-File -FilePath "findings.md" -Encoding UTF8
    Write-Host "Creado findings.md"
} else {
    Write-Host "findings.md ya existe, omitiendo"
}

# Crear progress.md si no existe
if (-not (Test-Path "progress.md")) {
    @"
# Registro de Progreso

## Sesión: $DATE

### Estado Actual
- **Fase:** 1 - Requisitos y Descubrimiento
- **Inicio:** $DATE

### Acciones Realizadas
-

### Resultados de Pruebas
| Prueba | Resultado esperado | Resultado real | Estado |
|------|---------|---------|------|

### Errores
| Error | Solución |
|------|---------|
"@ | Out-File -FilePath "progress.md" -Encoding UTF8
    Write-Host "Creado progress.md"
} else {
    Write-Host "progress.md ya existe, omitiendo"
}

Write-Host ""
Write-Host "¡Archivos de planificación inicializados!"
Write-Host "Archivos: task_plan.md, findings.md, progress.md"
