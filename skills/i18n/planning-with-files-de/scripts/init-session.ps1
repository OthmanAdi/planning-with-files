# Initialisiert Planungsdateien für eine neue Sitzung
# Verwendung: .\init-session.ps1 [Projektname]

param(
    [string]$ProjectName = "projekt"
)

$DATE = Get-Date -Format "yyyy-MM-dd"

Write-Host "Initialisiere Planungsdateien: $ProjectName"

# task_plan.md erstellen, wenn nicht vorhanden
if (-not (Test-Path "task_plan.md")) {
    @"
# Aufgabenplan: [Kurze Beschreibung]

## Ziel
[Ein-Satz-Beschreibung des Endzustands]

## Aktuelle Phase
Phase 1

## Phasen

### Phase 1: Anforderungen & Entdeckung
- [ ] Benutzerabsicht verstehen
- [ ] Einschränkungen und Anforderungen klären
- [ ] Erkenntnisse in findings.md dokumentieren
- **Status:** in_progress

### Phase 2: Planung & Struktur
- [ ] Technischen Ansatz festlegen
- [ ] Projektstruktur bei Bedarf erstellen
- **Status:** pending

### Phase 3: Implementierung
- [ ] Schrittweise gemäß Plan ausführen
- [ ] Code zuerst in Dateien schreiben, dann ausführen
- **Status:** pending

### Phase 4: Test & Validierung
- [ ] Alle Anforderungen geprüft
- [ ] Testergebnisse in progress.md dokumentieren
- **Status:** pending

### Phase 5: Auslieferung
- [ ] Alle Ausgabedateien geprüft
- [ ] An Benutzer ausgeliefert
- **Status:** pending

## Getroffene Entscheidungen
| Entscheidung | Begründung |
|------|------|

## Aufgetretene Fehler
| Fehler | Lösung |
|------|---------|
"@ | Out-File -FilePath "task_plan.md" -Encoding UTF8
    Write-Host "task_plan.md erstellt"
} else {
    Write-Host "task_plan.md existiert bereits, überspringe"
}

# findings.md erstellen, wenn nicht vorhanden
if (-not (Test-Path "findings.md")) {
    @"
# Erkenntnisse & Entscheidungen

## Anforderungen
-

## Forschungsergebnisse
-

## Technische Entscheidungen
| Entscheidung | Begründung |
|------|------|

## Aufgetretene Probleme
| Problem | Lösung |
|------|---------|

## Ressourcen
-
"@ | Out-File -FilePath "findings.md" -Encoding UTF8
    Write-Host "findings.md erstellt"
} else {
    Write-Host "findings.md existiert bereits, überspringe"
}

# progress.md erstellen, wenn nicht vorhanden
if (-not (Test-Path "progress.md")) {
    @"
# Fortschrittsprotokoll

## Sitzung: $DATE

### Aktueller Status
- **Phase:** 1 - Anforderungen & Entdeckung
- **Startzeit:** $DATE

### Ausgeführte Aktionen
-

### Testergebnisse
| Test | Erwartet | Tatsächlich | Status |
|------|---------|---------|------|

### Fehler
| Fehler | Lösung |
|------|---------|
"@ | Out-File -FilePath "progress.md" -Encoding UTF8
    Write-Host "progress.md erstellt"
} else {
    Write-Host "progress.md existiert bereits, überspringe"
}

Write-Host ""
Write-Host "Planungsdateien initialisiert!"
Write-Host "Dateien: task_plan.md, findings.md, progress.md"
