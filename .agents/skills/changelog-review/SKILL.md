---
name: changelog-review
description: Systematische Prüfung des Release Drafter Drafts vor dem Release-Dispatch. Stellt sicher, dass Changelog vollständig, benutzerorientiert und ohne interne Notizen ist.
---

# Changelog Review Skill – Cover Control

## Zweck

Vor jedem Release-Dispatch (`workflow_dispatch` auf `release.yml`) muss der
automatisch generierte Release-Draft durch Release Drafter geprüft werden.
Dieser Skill definiert den Prüfprozess und die Qualitätskriterien.

---

## Schritt 1: Draft abrufen

```sh
# Aktuellen Release-Draft anzeigen
gh release list --limit 5

# Draft-Body ausgeben (JSON-Feld 'body')
gh api repos/{OWNER}/{REPO}/releases \
  --jq '.[] | select(.draft==true) | {name: .name, tag: .tag_name, body: .body}'
```

Für cover-control:
```sh
gh api repos/frandle82/cover-control/releases \
  --jq '.[] | select(.draft==true) | {name: .name, tag: .tag_name, body: .body}'
```

---

## Schritt 2: Pflichtprüfung

### 2.1 Vollständigkeit

- [ ] Alle PRs seit dem letzten Release sind im Draft enthalten
  ```sh
  # PRs seit letztem Tag prüfen
  gh pr list --state merged --base main --json number,title,mergedAt \
    --jq '.[] | select(.mergedAt > "DATUM_LETZTER_RELEASE")'
  ```
- [ ] Kein PR hat einen leeren Body
- [ ] Kein PR hat nur den Titel als Body

### 2.2 Qualität

- [ ] Summary jedes PRs erklärt Anwender-Impact, nicht Implementierungsdetails
- [ ] Bug Fixes nennen Symptom + was behoben wurde
- [ ] Neue Features haben nachvollziehbare Beschreibung

### 2.3 Verbotene Inhalte

- [ ] Keine internen Debug-Notizen (`TODO:`, `WIP`, `debug`, `quick fix`)
- [ ] Keine Stacktraces oder Log-Dumps im Changelog
- [ ] Keine reine Commit-Liste als PR-Body

### 2.4 Breaking Changes & Migrations

- [ ] Breaking Changes mit `⚠️ BREAKING CHANGE:` markiert
- [ ] Migrations mit notwendigen Nutzeraktionen beschrieben
- [ ] Upgrade-Hinweise vorhanden wenn Nutzeraktion erforderlich

### 2.5 Kategorisierung

- [ ] Labels sind korrekt gesetzt (enhancement, bug, breaking-change etc.)
- [ ] PRs sind den richtigen Release-Drafter-Kategorien zugeordnet

---

## Schritt 3: Blocker beheben

Wenn Probleme gefunden werden:

### PR-Beschreibung nachbessern
```sh
# PR-Body bearbeiten
gh pr edit <PR-Nummer> --body "$(cat pr_body.md)"
```

Release Drafter generiert den Draft automatisch neu aus den aktuellen PR-Bodies.
Nach Änderungen: erneut Draft abrufen und prüfen.

### Labels setzen
```sh
gh pr edit <PR-Nummer> --add-label "enhancement"
gh pr edit <PR-Nummer> --remove-label "bug"
```

### Draft manuell regenerieren (optional)
```sh
# Release Drafter via Workflow-Dispatch neu triggern (falls vorhanden)
gh workflow run release-drafter.yml
```

---

## Schritt 4: Versionsnummer bestimmen

Wenn keine explizite Versionsnummer vorgegeben:

| Änderungstyp | Versionsstufe |
|---|---|
| Breaking Change / API-Bruch | Major (`X.0.0`) |
| Neue Funktion / Feature | Minor (`x.Y.0`) |
| Bugfix / Hotfix / Deps / Wartung | Patch (`x.y.Z`) |
| Gemischt → höchste Stufe gewinnt | – |

Nur bei fachlich uneindeutigem Breaking Change nachfragen.

---

## Schritt 5: Release-Dispatch

Erst wenn alle Checklistenpunkte erfüllt:

```sh
gh workflow run release.yml \
  --field version=<VERSION> \
  --field release_type=release
```

---

## Schritt 6: Release verifizieren

```sh
# Release-Status prüfen
gh release view <TAG> --json name,tagName,isDraft,isPrerelease,assets \
  --jq '{name,tag: .tagName, draft: .isDraft, prerelease: .isPrerelease, assets: [.assets[].name]}'
```

Erwartetes Ergebnis:
- `draft: false`
- `prerelease: false` (bei normalem Release)
- Assets enthält `cover_control.zip`
- Version und Tag stimmen überein

---

## Checkliste Kurzform (vor Dispatch ausführen)

```
[ ] Draft vollständig: alle PRs seit letztem Release enthalten
[ ] Kein leerer/nichtssagender PR-Body
[ ] Breaking Changes hervorgehoben (falls vorhanden)
[ ] Migrationen + Nutzeraktionen genannt (falls vorhanden)
[ ] Keine internen Debug-Notizen
[ ] Labels korrekt gesetzt
[ ] Versionsnummer bestimmt
[ ] main aktuell und alle CI-Gates grün
```
