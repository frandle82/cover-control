---
name: release
description: Verbindlicher Release- und Veröffentlichungsprozess für cover-control über GitHub Actions, Release Drafter und SemVer.
---

# Release Skill – Veröffentlichungs- & Release-Prozess

## Zweck

Definiert die verbindliche Release-Kette für `cover-control`. Releases werden ausschließlich automatisiert über den GitHub Actions Workflow `Create Release` (`release.yml`) auf `main` erstellt.

---

## 1. Die 6 Schritte der Release-Kette

```
[1. Lokale Gates] ──> [2. PR & Checks] ──> [3. Merge] ──> [4. Draft-Prüfung] ──> [5. Workflow-Dispatch] ──> [6. Verifikation]
```

### Schritt 1: Lokale Release-Gates
Vor dem Erstellen oder Mergen des PRs müssen alle lokalen Prüfungen erfolgreich sein:
```sh
# 1. Vollständige Testsuite:
.venv/bin/pytest -q --asyncio-mode=auto

# 2. Syntax- und Bytecode-Kompilierung:
.venv/bin/python -m compileall -q custom_components tests scripts

# 3. Git-Whitespace-Prüfung:
git diff --check
```

### Schritt 2: Pull Request & Checks
* Jede Änderung gelangt über einen PR nach `main`.
* Ausführliche, benutzerorientierte PR-Beschreibung gemäß Skill [`pr-description`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/pr-description/SKILL.md) verfassen (Summary, New Features, Bug Fixes, Breaking Changes, Test Status).
* Required Checks auf GitHub abwarten. Bei Fehlern mit Skill [`gh-fix-ci`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/gh-fix-ci/SKILL.md) reparieren.

### Schritt 3: Merge nach `main`
* Wenn alle Checks grün und der PR konfliktfrei ist, PR mergen.

### Schritt 4: Release-Drafter & Changelog-Prüfung
* Release Drafter generiert den Changelog automatisch aus den PR-Beschreibungen.
* Gemäß Skill [`changelog-review`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/changelog-review/SKILL.md) den Draft prüfen:
  ```sh
  gh release list --limit 5
  gh api repos/frandle82/cover-control/releases --jq '.[] | select(.draft==true) | .body'
  ```
* Keine leeren PR-Bodies oder reinen Commit-Listen im Changelog!

### Schritt 5: SemVer-Bestimmung & Workflow-Dispatch
* **SemVer-Stufe bestimmen:**
  * Breaking Changes / Schema-Bruch → **Major** (`X.0.0`)
  * Neue Features / Konfigurationsoptionen → **Minor** (`x.Y.0`)
  * Bugfixes / Wartung / Abhängigkeiten → **Patch** (`x.y.Z`)
* **Workflow starten:**
  ```sh
  gh workflow run release.yml \
    --field version=<NEUE_VERSION> \
    --field release_type=release
  ```

### Schritt 6: Release verifizieren
Nach Abschluss des GitHub Actions Workflows das Release-Ergebnis prüfen:
```sh
gh release view <TAG> --json name,tagName,isDraft,isPrerelease,assets \
  --jq '{name,tag: .tagName, draft: .isDraft, prerelease: .isPrerelease, assets: [.assets[].name]}'
```
* **Kriterien für Erfolg:**
  * `draft: false`
  * Release-Tag stimmt exakt mit der Version überein.
  * `cover_control.zip` ist als Asset vorhanden und intakt.

---

## 2. Strikte Verbote

* ❌ **Keine manuellen Releases:** Niemals lokal ein Git-Tag erstellen, pushen oder ein GitHub-Release von Hand erzeugen.
* ❌ **Keine manuellen Versionsänderungen:** `manifest.json` wird ausschließlich vom Release-Workflow im CI aktualisiert und committed.
* ❌ **Kein Release bei roten Tests:** Scheitert auch nur ein Test, ist der Release blockiert.
