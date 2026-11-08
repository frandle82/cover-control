---
name: code-reviewer
description: Automatisierte Code-Reviews von Git-Diffs und PRs auf Sicherheitslücken, Performance-Engpässe, Home Assistant Standards und Codestyling.
---

# Code-Reviewer Skill – Qualitätssicherung & Review

## Zweck

Führt strukturierte, automatisierte Code-Reviews durch und prüft Diff-Dateien auf Sicherheitslücken, Performance-Engpässe, Architekturkonformität und die Einhaltung von Home Assistant Richtlinien.

**Vorteil:** Hält den Code auf Production-Niveau, verhindert Regressionen und entlastet das Team vor dem Merge und Pull Request.

---

## Wann anwenden?

* Vor dem Committen größerer Änderungen.
* Vor dem Erstellen oder Aktualisieren eines Pull Requests.
* Nach Refactorings oder Anpassungen an Kernkomponenten.
* Zur Überprüfung von Fremd- oder KI-generiertem Code auf versteckte Mängel.

---

## Review-Workflow

```sh
# 1. Diff zum Hauptbranch bzw. uncommitted changes inspizieren
git diff origin/main..HEAD
# oder für lokale Änderungen:
git diff
```

Strukturiert die folgenden 6 Prüfkategorien durchgehen:

---

## Die 6 Prüfkategorien

### 1. Home Assistant Async & Event-Loop
* [ ] **Keine blockierenden I/O-Operationen:** Keine synchronen File-Zugriffe, `time.sleep()`, HTTP-Requests oder rechenintensive Loops im Event-Loop. Synchrone Aufrufe müssen über `await hass.async_add_executor_job(...)` laufen.
* [ ] **Lifecycle & Unload:** Werden alle State-Listener (`async_track_*`) und Timer beim Unload deregistriert? Werden Hintergrund-Tasks an den Config Entry gebunden?
* [ ] **Callbacks:** Callbacks (`@callback`) müssen zwingend synchron und non-blocking sein.

### 2. Cover Control Architektur & Mixin-Grenzen
* [ ] **Mixin-Zuständigkeit eingehalten:**
  * Fahrbefehle/Toleranz → `actuator.py`
  * Bedingungen/Zielposition → `evaluation.py`
  * Events/Listener → `events.py`
  * Zeitpläne/Kalender → `schedule.py`
  * Sonnengeometrie/Sensorik → `shading.py`
  * Status/Diagnose → `status.py`
* [ ] **Keine Logik in Fassade:** `controller.py` bleibt reine Fassade/Delegator.
* [ ] **Schichten-Trennung:** Global vs. Profil vs. Raum sauber getrennt (Profile dürfen keine Raum-Entitäten/Positionen kennen).

### 3. Sicherheit, Robustheit & Resilienz
* [ ] **Defensive Entity-Zugriffe:** Kein blindes Vertrauen auf existierende States (`hass.states.get(...) is not None`). Fehlende oder unbekannte Entitäten (`STATE_UNAVAILABLE`, `STATE_UNKNOWN`) werden sauber abgefangen.
* [ ] **Sichere Typkonvertierung:** Keine ungeprüften `float(state.state)` ohne Try-Except oder Validierung.
* [ ] **Keine Secrets/Tokens:** Keine sensiblen Daten, Passwörter oder private Pfade im Code oder in Logs.

### 4. Performance & Logging-Hygiene
* [ ] **Deduplizierung von Logs:** Repetitive Log-Einträge bei zyklischer Evaluierung (z. B. jede Sekunde oder Minute) müssen dedupliziert werden.
* [ ] **Keine unnötigen Fahrbefehle:** Prüfung auf Positionstoleranz vor dem Absenden von `cover.set_cover_position`.
* [ ] **Effiziente Datenstrukturen:** Vermeidung redundanter Iterationen über State-Listen.

### 5. Code-Qualität & Wartbarkeit
* [ ] **Typannotationen:** Sinnvolle Typ-Hints für Funktionsparameter und Rückgabewerte.
* [ ] **Source of Truth:** Konstanten und Defaults in `const.py`, keine redundanten Keys.
* [ ] **Kein toter Code:** Keine auskommentierten Codeblöcke oder ungenutzten Imports.
* [ ] **Compiler & Whitespace:**
  ```sh
  .venv/bin/python -m compileall -q custom_components tests scripts
  git diff --check
  ```

### 6. Lokalisierung & Testabdeckung
* [ ] **Übersetzungen synchron:** `strings.json`, `translations/en.json` und `translations/de.json` sind identisch strukturiert.
* [ ] **Regressionstests vorhanden:** Jede Verhaltensänderung ist durch Tests in `tests/` abgedeckt.
* [ ] **Tests grün:**
  ```sh
  .venv/bin/pytest -q --asyncio-mode=auto
  ```

---

## Review-Befund ausgeben

Der Review-Bericht wird kompakt nach folgendem Schema formuliert:
* **🟢 Freigabe:** Keine Blocker, alle Standards eingehalten.
* **🟡 Hinweise (Optional):** Kleinere Optimierungsvorschläge ohne Blockadewirkung.
* **🔴 Blocker (Muss behoben werden):** Verletzung von Async-Regeln, fehlende Tests, Architekturbrüche oder Syntaxfehler.
