# Initialize planning files for a new session in .\.planning\{plan_id}
# Usage: .\init-session.ps1 [project-name]

param(
    [string]$ProjectName = "project"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillRoot = Split-Path -Parent $ScriptDir
$TemplateDir = Join-Path $SkillRoot "templates"
$PlanRoot = Join-Path (Get-Location) ".planning"
$ActivePlanFile = Join-Path $PlanRoot ".active_plan"

$taskTemplate = Join-Path $TemplateDir "task_plan.md"
$findingsTemplate = Join-Path $TemplateDir "findings.md"
$progressTemplate = Join-Path $TemplateDir "progress.md"

if (-not (Test-Path $taskTemplate) -or -not (Test-Path $findingsTemplate) -or -not (Test-Path $progressTemplate)) {
    Write-Error "Missing templates under $TemplateDir"
    exit 1
}

$planId = ([guid]::NewGuid().ToString().ToLowerInvariant())
$planDir = Join-Path $PlanRoot $planId

New-Item -ItemType Directory -Path $planDir -Force | Out-Null

Copy-Item $taskTemplate (Join-Path $planDir "task_plan.md") -Force
Copy-Item $findingsTemplate (Join-Path $planDir "findings.md") -Force
Copy-Item $progressTemplate (Join-Path $planDir "progress.md") -Force
Set-Content -Path $ActivePlanFile -Value $planId -Encoding UTF8

Write-Host "Initialized planning files for: $ProjectName"
Write-Host "PLAN_ID=$planId"
Write-Host "PLAN_DIR=$planDir"
Write-Host "Files:"
Write-Host "  - $(Join-Path $planDir 'task_plan.md')"
Write-Host "  - $(Join-Path $planDir 'findings.md')"
Write-Host "  - $(Join-Path $planDir 'progress.md')"
Write-Host ""
Write-Host "Active plan updated: $ActivePlanFile"
Write-Host "For parallel sessions, pin this terminal to the plan:"
Write-Host "  `$env:PLAN_ID = '$planId'"
