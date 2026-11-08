---
name: reverse-engineering-anything
description: Analysiert fremde Referenzimplementierungen quellcodebasiert und reproduzierbar, bevor Funktionen in Cover Control zugeordnet oder implementiert werden.
---

# Reverse Engineering Anything – Referenzimplementierungen untersuchen

## Zweck

Dieser Skill verhindert Implementierungen auf Basis von README, UI-Feldnamen oder Vermutungen. Maßgeblich sind ein fixierter Referenz-Commit und die tatsächlich ausgeführte Runtime-Logik. Das Ergebnis ist eine belegte Funktionsinventur und eine Paritätsmatrix, aus der erst danach kleine Implementierungsblöcke abgeleitet werden.

## Wann anwenden?

- Vor jeder Übernahme oder Zuordnung von Verhalten aus einem Fremdprojekt.
- Bei Paritätsprüfungen gegen Blueprints, Adapter, Integrationen oder andere Referenzimplementierungen.
- Erneut, wenn der untersuchte Referenz-Commit aktualisiert wird.

## Kern-Workflow

1. **Scope und Revision fixieren**
   - Aktuellen Zielbranch und vollständigen Commit-SHA aus der autoritativen Remote-Quelle ermitteln.
   - Repository an genau diesem SHA in ein temporäres Verzeichnis auschecken.
   - Remote-URL, Branch, SHA und Prüfdatum im Analyseartefakt festhalten.
2. **Repository inventarisieren**
   - Struktur, Paketmetadaten, Konfigurationsschema, Defaults, UI-Felder, Dokumentation, Tests und Changelog erfassen.
   - Alle Runtime-Einstiegspunkte und Dateien mit Steuerungsverhalten über Importe und Aufrufer verfolgen; vorgegebene Dateilisten sind nur die Mindestmenge.
3. **Konfiguration bis zur Wirkung verfolgen**
   - Für jedes Feld belegen: Definition und Default, Persistenz, Leser/Aufrufer, Aktivierungsbedingung, Aktion, Priorität und Reset.
   - Ungelesene, nur migrierte oder historische Felder als solche kennzeichnen; ein vorhandenes Feld ist kein Funktionsbeleg.
4. **Laufzeit als Zustandsmaschine analysieren**
   - Trigger, eindeutige Trigger-Identitäten, Listener, Timer, Delays, Hysteresen, Prioritäten, Zustände und Restart-/Reload-Verhalten erfassen.
   - Sensor- und Aktordaten, manuelle Eingriffe, Schutzfunktionen, Rückkehrlogik sowie normale und konkurrierende Zustandswechsel nachvollziehen.
5. **Aktuellen Stand gegen Historie prüfen**
   - Tests und aktuellen Changelog lesen und die zugehörigen Fixes im Quellcode lokalisieren.
   - Dokumentationsaussagen bei Abweichungen hinter dem Code zurückstellen.
6. **Zielprojekt zuordnen**
   - Bestehende Architektur und vorhandene Implementierung einschließlich UI, Persistenz, Resolver, Listener, Runtime, Fahrentscheidung, Diagnose und Tests prüfen.
   - Pro Referenzfunktion genau einen Status vergeben: `FULL`, `MAPPED`, `PARTIAL`, `MISSING` oder `NOT_APPLICABLE`.
   - `FULL` nur vergeben, wenn die vollständige Kette nachweislich vorhanden und regressionsgetestet ist.
7. **Artefakte und nächste Schritte erstellen**
   - Analyse mit belegten Dateipfaden und Symbolen im Knowledge-System dokumentieren.
   - Paritätsmatrix mit Referenzverhalten, Zielzuordnung, Status, Evidenz und konkreter Lücke pflegen.
   - Fehlende Funktionen nach Sicherheitsrelevanz, Abhängigkeiten und Nutzerwirkung priorisieren; noch keine Implementierung während der Analyse beginnen.

## Checkliste / Kriterien

- [ ] Referenz-URL, Branch, vollständiger SHA und Prüfdatum dokumentiert.
- [ ] Repository-Struktur, Konfigurationsmodell, Defaults und UI-Felder untersucht.
- [ ] Runtime-Logik, Trigger, Timer, Prioritäten und Zustände quellcodebasiert verfolgt.
- [ ] Sensor-/Aktordaten, Schutzfunktionen und manuelle Eingriffe erfasst.
- [ ] Restart-/Reload-Verhalten und relevante Edge Cases geprüft.
- [ ] Tests, Changelog und aktuelle Bugfixes mit der Implementierung abgeglichen.
- [ ] Historische oder unbenutzte Optionen gesondert ausgewiesen.
- [ ] Jede Statuszuordnung nennt überprüfbare Evidenz und die verbleibende Lücke.
- [ ] Analyseartefakt, Paritätsmatrix und Knowledge-Index sind konsistent.
- [ ] Erst nach abgeschlossener Analyse wird Implementierung geplant.

## Anti-Patterns / Häufige Fehler

- Gegen einen beweglichen Branch ohne dokumentierten SHA analysieren.
- README, Dokumentation oder Feldnamen als Beleg für Runtime-Verhalten behandeln.
- Nur die vorab genannten Dateien lesen und importierte Steuerungslogik übersehen.
- `FULL` wegen ähnlicher Einzelmethoden vergeben, obwohl UI, Trigger, Diagnose oder Tests fehlen.
- Referenzarchitektur technisch kopieren, statt Verhalten in die Cover-Control-Architektur einzuordnen.
- Historische Optionen oder auskommentierten Code als aktive Funktion übernehmen.
- Analyse und umfangreiche Neuimplementierung in denselben Arbeitsblock vermischen.

Verwandte Skills:
* [`../knowledge/SKILL.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/knowledge/SKILL.md)
* [`../cca-parity/SKILL.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/cca-parity/SKILL.md)
* [`../diff-audit/SKILL.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/diff-audit/SKILL.md)
