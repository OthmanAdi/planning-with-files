# Initialisiert Planungsdateien für eine neue Sitzung
# Verwendung: .\init-session.ps1 [Projektname]

param(
    [string]$ProjectName = "projekt"
)

$ErrorActionPreference = "Stop"

$DATE = Get-Date -Format "yyyy-MM-dd"

Write-Host "Initialisiere Planungsdateien: $ProjectName"

# task_plan.md erstellen, wenn nicht vorhanden
if (-not (Test-Path "task_plan.md")) {
    @"
# Aufgabenplan: [Kurze Beschreibung]

Nutzen Sie diese Datei als dauerhafte Roadmap und halten Sie sie bei jedem Phasenwechsel aktuell.

## Ziel
[Ein-Satz-Beschreibung des Endzustands]

## Nächster Schritt
[Die nächste einzelne Aktion. Bei jedem Phasenwechsel aktualisieren.]

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
- [ ] Entscheidungen mit Begründung dokumentieren
- **Status:** pending

### Phase 3: Implementierung
- [ ] Schrittweise gemäß Plan ausführen
- [ ] Code zuerst in Dateien schreiben, dann ausführen
- [ ] Inkrementell testen
- **Status:** pending

### Phase 4: Test & Validierung
- [ ] Alle Anforderungen geprüft
- [ ] Testergebnisse in progress.md dokumentieren
- [ ] Gefundene Probleme beheben
- **Status:** pending

### Phase 5: Auslieferung
- [ ] Alle Ausgabedateien geprüft
- [ ] Vollständigkeit der Lieferobjekte sicherstellen
- [ ] An Benutzer ausgeliefert
- **Status:** pending

## Schlüsselfragen
1. [Zu beantwortende Frage]
2. [Zu beantwortende Frage]

## Getroffene Entscheidungen
| Entscheidung | Begründung |
|------|------|

## Aufgetretene Fehler
| Fehler | Versuch | Lösung |
|------|---------|---------|

## Hinweise
- Aktualisieren Sie den Phasenstatus von `pending` zu `in_progress` und danach zu `complete`.
- Prüfen Sie Ziel und nächsten Schritt vor wichtigen Entscheidungen erneut.
- Protokollieren Sie Fehler zeitnah und ändern Sie den Ansatz vor einem erneuten Versuch.
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
