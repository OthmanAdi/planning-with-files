---
description: "Starte Manus-artige Dateiplanung. Erstelle task_plan.md, findings.md, progress.md für komplexe Aufgaben."
---

Lies den deutschen Skill-Text aus dem ersten dieser Pfade, der existiert, und folge ihm genau:

- `$HOME/.claude/skills/planning-with-files-de/SKILL.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/i18n/planning-with-files-de/SKILL.md`

Existiert keiner der beiden Pfade, rufe die planning-with-files:planning-with-files Skill auf und arbeite auf Deutsch weiter.

Erst wiederherstellen, dann erstellen. Ist `PWF_PLAN_ROOT` gesetzt, prüfe, dass es ein absoluter, existierender Projektstamm ist; lehne einen ungültigen Stamm-Pin ab, bevor du Dateien liest oder erstellst. Andernfalls ist der Projektstamm das aktuelle Verzeichnis. Löse die ausgewählte Aufgabe mit `sh ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-plan-dir.sh` auf (PowerShell: `& "$env:CLAUDE_PLUGIN_ROOT\scripts\resolve-plan-dir.ps1"`):
- Ein ausgegebenes Verzeichnis ist die ausgewählte Aufgabe. Setze sie fort: Lies ihre `task_plan.md`, `findings.md` und `progress.md` und bewahre sie; überschreibe niemals vorhandene Planungsdateien.
- Leere Ausgabe bei nicht leerer `PLAN_ID` bedeutet, dass der Plan-Selektor abgelehnt wurde. Halte an und bitte den Benutzer, den Pin zu korrigieren. Weiche nicht auf den Stamm oder einen anderen Plan aus.
- Leere Ausgabe, bei der `resolve-plan-dir.sh --check-ambiguity` (PowerShell: `-CheckAmbiguity`) `PWF_PLAN_AMBIGUOUS_V1` ausgibt, bedeutet, dass mehrere Pläne ohne Selektor existieren. Halte an und bitte den Benutzer, `PLAN_ID=<slug>` zu setzen.
- Sonst ist leere Ausgabe die alte Konvention (legacy) mit Plan im Projektstamm: Setze `task_plan.md` aus dem geprüften Projektstamm fort (`PWF_PLAN_ROOT`, falls gesetzt), sofern sie existiert. Ein gültiger Stamm-Pin allein lehnt einen alten Stamm-Plan nicht ab.

Nur für eine neue Aufgabe führe den Initialisierer aus dem geprüften Projektstamm aus, auch wenn `PWF_PLAN_ROOT` auf ein anderes Verzeichnis als das cwd des Hosts zeigt: `sh ${CLAUDE_PLUGIN_ROOT}/scripts/init-session.sh` (PowerShell: `init-session.ps1`). Übergib einen Aufgabennamen für einen isolierten Plan unter `.planning/<id>/` und pinne den Host mit der ausgegebenen `PLAN_ID`. `.planning/.active_plan` ist nur ein gemeinsamer Standard; es bindet keine parallele Sitzung.
- task_plan.md — für Phasen, Fortschritt und Entscheidungen
- findings.md — für Forschung und Erkenntnisse
- progress.md — für Sitzungsprotokolle

Behalte jede Überschrift `### Phase N: Name` mit genau einer `**Status:**`-Zeile und prüfe dann den expliziten Pfad des ausgewählten Plans mit `sh ${CLAUDE_PLUGIN_ROOT}/scripts/check-complete.sh --validate path/to/task_plan.md` (PowerShell: `check-complete.ps1 -Validate -PlanFile path/to/task_plan.md`). Besteht ein vorhandener Plan die Prüfung nicht, melde das, statt ihn neu zu schreiben.

Dann führe den Benutzer durch den Planungs-Workflow. Alle Planungsdateien müssen auf Deutsch sein.

Die Statuskennzeichen bleiben wörtlich englisch (`**Status:** in_progress`, `**Status:** complete`), weil `check-complete.sh` sie mit `grep -F` sucht. Eine Übersetzung würde das Abschluss-Gate abschalten.
