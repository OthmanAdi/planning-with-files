# Prüft, ob alle Phasen in task_plan.md abgeschlossen sind
# Immer mit Exit-Code 0 beenden — Status über stdout melden
# Wird vom Stop-Hook aufgerufen, um Aufgabenabschlussstatus zu melden

param(
    [string]$PlanFile = "task_plan.md"
)

# issue #195: per-invocation opt-out (PLANNING_DISABLED=1) for one-shot/CI
# sessions that share a cwd with a plan but never opted into it.
if ($env:PLANNING_DISABLED -eq '1') { exit 0 }

if (-not (Test-Path $PlanFile)) {
    Write-Host '[planning-with-files-de] task_plan.md nicht gefunden — keine aktive Planungssitzung.'
    exit 0
}

# Dateiinhalt lesen
$content = Get-Content $PlanFile -Raw

# Gesamtzahl der Phasen zählen
$TOTAL = ([regex]::Matches($content, "### Phase")).Count

# Zuerst **Status:** Format prüfen
$COMPLETE = ([regex]::Matches($content, "\*\*Status:\*\* complete")).Count
$IN_PROGRESS = ([regex]::Matches($content, "\*\*Status:\*\* in_progress")).Count
$PENDING = ([regex]::Matches($content, "\*\*Status:\*\* pending")).Count

# Fallback: Wenn **Status:** nicht gefunden, [complete] Inline-Format prüfen
if ($COMPLETE -eq 0 -and $IN_PROGRESS -eq 0 -and $PENDING -eq 0) {
    $COMPLETE = ([regex]::Matches($content, "\[complete\]")).Count
    $IN_PROGRESS = ([regex]::Matches($content, "\[in_progress\]")).Count
    $PENDING = ([regex]::Matches($content, "\[pending\]")).Count
}

# Status melden — immer mit Exit-Code 0 beenden, unvollständige Aufgaben sind normaler Zustand
if ($COMPLETE -eq $TOTAL -and $TOTAL -gt 0) {
    Write-Host ('[planning-with-files-de] Alle Phasen abgeschlossen (' + $COMPLETE + '/' + $TOTAL + '). Wenn der Benutzer zusätzliche Arbeit hat, neue Phasen in task_plan.md hinzufügen, bevor du beginnst.')
} else {
    Write-Host ('[planning-with-files-de] Aufgabe läuft (' + $COMPLETE + '/' + $TOTAL + ' Phasen abgeschlossen). progress.md vor dem Stoppen aktualisieren.')
    if ($IN_PROGRESS -gt 0) {
        Write-Host ('[planning-with-files-de] ' + $IN_PROGRESS + ' Phasen noch in Bearbeitung.')
    }
    if ($PENDING -gt 0) {
        Write-Host ('[planning-with-files-de] ' + $PENDING + ' Phasen ausstehend.')
    }
}
exit 0
