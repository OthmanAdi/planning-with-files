#!/usr/bin/env bash
# Initialisiert Planungsdateien für eine neue Sitzung
# Verwendung: ./init-session.sh [Projektname]

set -e

PROJECT_NAME="${1:-projekt}"
DATE=$(date +%Y-%m-%d)

echo "Initialisiere Planungsdateien: $PROJECT_NAME"

# task_plan.md erstellen, wenn nicht vorhanden
if [ ! -f "task_plan.md" ]; then
    cat > task_plan.md << 'EOF'
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
EOF
    echo "task_plan.md erstellt"
else
    echo "task_plan.md existiert bereits, überspringe"
fi

# findings.md erstellen, wenn nicht vorhanden
if [ ! -f "findings.md" ]; then
    cat > findings.md << 'EOF'
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
EOF
    echo "findings.md erstellt"
else
    echo "findings.md existiert bereits, überspringe"
fi

# progress.md erstellen, wenn nicht vorhanden
if [ ! -f "progress.md" ]; then
    cat > progress.md << EOF
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
EOF
    echo "progress.md erstellt"
else
    echo "progress.md existiert bereits, überspringe"
fi

echo ""
echo "Planungsdateien initialisiert!"
echo "Dateien: task_plan.md, findings.md, progress.md"
