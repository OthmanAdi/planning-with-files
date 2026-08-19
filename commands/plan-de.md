---
description: "Starte Manus-artige Dateiplanung. Erstelle task_plan.md, findings.md, progress.md für komplexe Aufgaben."
---

Lies den deutschen Skill-Text aus dem ersten dieser Pfade, der existiert, und folge ihm genau:

- `$HOME/.claude/skills/planning-with-files-de/SKILL.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/i18n/planning-with-files-de/SKILL.md`

Existiert keiner der beiden Pfade, rufe die planning-with-files:planning-with-files Skill auf und arbeite auf Deutsch weiter.

Wenn die drei Planungsdateien nicht im aktuellen Projektverzeichnis existieren, erstelle sie:
- task_plan.md — für Phasen, Fortschritt und Entscheidungen
- findings.md — für Forschung und Erkenntnisse
- progress.md — für Sitzungsprotokolle

Dann führe den Benutzer durch den Planungs-Workflow. Alle Planungsdateien müssen auf Deutsch sein.

Die Statuskennzeichen bleiben wörtlich englisch (`**Status:** in_progress`, `**Status:** complete`), weil `check-complete.sh` sie mit `grep -F` sucht. Eine Übersetzung würde das Abschluss-Gate abschalten.
