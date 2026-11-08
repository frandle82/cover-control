---
name: pr-description
description: Systematische Erstellung benutzerorientierter Pull-Request-Beschreibungen für Release Drafter in cover-control. Erzeugt vollständige, changelog-taugliche PR-Bodies ohne interne Debug-Notizen.
---

# PR Description Skill – Cover Control

## Zweck

Release Notes werden in cover-control automatisch durch Release Drafter aus
PR-Beschreibungen erzeugt. Jede PR-Beschreibung muss daher eigenständig,
benutzerorientiert und vollständig sein – ohne Kenntnis der Commit-Historie.

---

## Pflichtstruktur einer PR-Beschreibung

Jede PR-Beschreibung enthält exakt diese Abschnitte (sofern anwendbar):

```markdown
## Summary
<!-- Kompakte Zusammenfassung aus Anwendersicht: Was hat sich geändert und warum. -->

## New Features
<!-- Nur wenn neue Funktionen vorhanden. Entfernen wenn leer. -->

## Bug Fixes
<!-- Behobene Fehler mit Symptom + Ursache. Entfernen wenn leer. -->

## Behavior Changes
<!-- Verhaltensänderungen, die bestehende Setups betreffen. Entfernen wenn leer. -->

## Migration / Compatibility
<!-- Config-Migration, Breaking Changes, benötigte Nutzeraktionen. Entfernen wenn leer. -->

## Technical Notes
<!-- Nur internals, die für Betreiber (HACS-Nutzer) relevant sind. Kein Debug-Fülltext. -->

## Test Status
<!-- Welche Tests wurden ausgeführt, Ergebnis, Abdeckung. Immer vorhanden. -->
```

---

## Qualitätsregeln

### Was MUSS vorhanden sein
- Summary: immer, konkret, aus Anwendersicht
- Test Status: immer, mit Testergebnis
- Breaking Changes: explizit als `⚠️ BREAKING CHANGE:` markiert

### Was VERBOTEN ist
- Interne Notizen wie „TODO: prüfen", „debug", „WIP", „quick fix"
- Reine Commit-Liste als PR-Body
- Platzhalter wie „see commits"
- Technische Stacktraces oder Log-Dumps
- Wiederholung des PR-Titels als Summary

### Entfernen wenn leer
Leere Abschnitte (z. B. kein Migration-Inhalt) vollständig aus der Beschreibung
entfernen. Nicht als leere Überschriften stehen lassen.

---

## Prozess: PR-Beschreibung erzeugen

1. `git log origin/main..HEAD --oneline` – Commits sammeln
2. `git diff origin/main..HEAD -- custom_components/` – Änderungen sichten
3. Für jeden logischen Änderungsblock: Benutzer-Impact bestimmen
4. Abschnitte nach obiger Struktur befüllen
5. Prüffragen:
   - Kann ein HACS-Nutzer ohne Code-Kenntnisse verstehen, was sich ändert?
   - Sind alle Breaking Changes und Migrations erwähnt?
   - Ist der Teststatus vollständig?

---

## Vor Release-Dispatch: Draft prüfen

Vor dem Starten des `release.yml`-Workflows sicherstellen:

```sh
# GitHub CLI: aktuellen Release-Draft anzeigen
gh release list --limit 5
gh api repos/{owner}/{repo}/releases --jq '.[] | select(.draft==true) | .body'
```

Checkliste:
- [ ] Alle PRs im Draft haben vollständige Beschreibungen
- [ ] Keine leeren oder nichtssagenden PR-Bodies
- [ ] Breaking Changes klar hervorgehoben
- [ ] Migrationen und Upgrade-Hinweise genannt
- [ ] Keine internen Debug-/Arbeitsnotizen sichtbar

---

## Labels für Release Drafter

Release Drafter kategorisiert PRs nach Labels. Diese Labels müssen korrekt
gesetzt sein:

| Label | Kategorie im Changelog |
|---|---|
| `enhancement`, `feature` | 🚀 New Features |
| `bug`, `fix` | 🐛 Bug Fixes |
| `breaking-change` | ⚠️ Breaking Changes |
| `migration` | 🔄 Migrations |
| `documentation` | 📚 Documentation |
| `dependencies` | 📦 Dependencies |

Labels prüfen/setzen:
```sh
gh pr edit <PR-Nummer> --add-label "enhancement"
gh pr view <PR-Nummer> --json labels
```
