# AGENTS.md – Cover Control (Lokale Instruktionen)

Verbindliche lokale Arbeitsanweisungen für KI-Coding-Agenten im Projekt `cover-control`.

Diese Datei ist ausschließlich lokal und wird nicht über Git getrackt.

## Regelungen & Anweisungen

* **Verbindliche Regeln:** Befolge strikt die Regeln unter `.agents/rules/` (`project.md`, `git-safety.md`, `quality.md`).
* **Skills verwenden:** Verwende bei Bedarf die passenden Skills unter `.agents/skills/` (`caveman`, `token-budget`, `systematic-debugging`, `diff-audit`, `home-assistant`, `config-flow`, `migrations`, `translations`, `testing`, `cover-control`).
* **Git-Sicherheit:** Keine eigenständigen Commits, Pushes, Tags, Pull Requests oder Releases ohne ausdrücklichen Auftrag von Andreas.
* **Änderungsschutz:** Vorhandene Änderungen des Benutzers müssen zwingend erhalten bleiben.
* **Berichterstattung:** Nach Änderungen immer die ausgeführten Tests und den aktuellen `git status` auf Deutsch berichten.

## Verbindliche Teststrategie

* Every behavioral change must be covered by tests.
* Run the full integration test suite before completing a change.
* Do not limit testing to the module being edited.
* Changes to config flows, migrations, entities, attributes, discovery, events, services, diagnostics, environment evaluation or release behavior require corresponding regression tests.
* The stable Home Assistant test suite is the authoritative release gate.

---

## Projektübersicht & Laufzeitarchitektur

Home Assistant Custom Integration zur automatisierten Rollladen- und Jalousiensteuerung.
* Laufzeit-Code: `custom_components/cover_control/`
* Regressionstests: `tests/`
* Wartungs- und Release-Skripte: `scripts/`

### Mixin-Zuständigkeiten (`custom_components/cover_control/runtime/`)
Logik gehört in das jeweilige Mixin, nicht in die Controller-Fassade:
* `actuator.py`: Fahrbefehle, Positionstoleranz, Lamellenkippung (Tilt) und Verzögerungslogik.
* `evaluation.py`: Berechnung der Zielposition und Auswertung der Bedingungen.
* `events.py`: Home Assistant State-Listener und Event-Subscriptions.
* `schedule.py`: Zeitpläne, Arbeitstag-Sensoren und Kalender-Ereignisse.
* `shading.py`: Sonnengeometrie (Azimut/Elevation), Wetterbedingungen und Beschattungsregeln.
* `status.py`: Zustände der Steuerungsentitäten, Diagnosesensoren und Statusgründe.

Controller-Imports bleiben stabil über `controller.py`. Keine Logik ohne klaren Grund zwischen Mixins verschieben.

---

## Arbeitsweise & Single Source of Truth

* Vor Änderungen immer relevante Implementierung, Tests, Konstanten, Übersetzungen und bestehende Helper prüfen.
* Bestehende Muster wiederverwenden und Pfade konsolidieren, statt Parallelstrukturen aufzubauen.
* Änderungen strikt auf die Anforderung beschränken (keine unaufgeforderten Refactorings oder Formatierungsänderungen).
* **Source of Truth:**
  * Gemeinsame Konstanten und Defaults gehören in `const.py`.
  * Persistente Konfiguration gehört ausschließlich in den Home Assistant Config Entry.
  * Laufzeit-Zustände bleiben im Speicher, sofern keine Persistenz über Neustarts/Reloads hinweg nötig ist.
  * Keine redundanten Konfigurationsschlüssel für denselben logischen Parameter anlegen.
  * Shared Normalisierung und Validierung für Config Flow und Options Flow verwenden.

---

## Cover Control Konfigurationsarchitektur (Native v6 / v7)

Strikte Grenzen der Verantwortlichkeit:
* **GLOBAL:** Besitzt geteilte Home Assistant Datenquellen (Arbeitstage, Kalender, Helligkeit, Außentemperatur, Wetter/Vorhersage, globale Bedingungen).
* **PROFILE:** Besitzt Automationsverhalten und Schwellenwerte (Zeitpläne, Helligkeitsschwellen, Hysterese, Wartezeiten, Beschattungs- und Lüftungsregeln). Profile besitzen niemals raumeigene Entitäten oder Positionen.
* **ROOM:** Besitzt Hardware, Cover-Entitäten, physische Positionen (Offen, Geschlossen, Beschattung, Kippung, Lüftung, Lockout), Fenstersensoren, Geometrie, Raumschalter und die Profilzuweisung.
* **SWITCH:** Steuert, ob eine konfigurierte Raumfunktion zur Laufzeit aktiv (enabled) ist.
* **RUNTIME:** Entscheidet, ob eine aktive Funktion unter den aktuellen Bedingungen ausführungsberechtigt (eligible) ist.

### Zustandsmodell
* **`configured`**: Funktion ist im gewählten Profil vorhanden **UND** vom Raum explizit ausgewählt (`profile_functions`).
* **`enabled`**: Der zugehörige Laufzeitschalter steht auf **ON**.
* **`eligible`**: Die aktuellen Bedingungen erlauben der Funktion eine Aktion.

Ein Schalterzustand ändert niemals die Konfiguration. Das Ausschalten eines Schalters löscht keine Raum-/Profilkonfiguration. Erst das Entfernen aus `profile_functions` hebt die Konfiguration auf.

### Native Profilfunktionen & Schalter
* Autonom schaltbare Profilfunktionen mit Laufzeitschalter: `time`, `brightness`, `sun`, `shading`, `ventilation`, `resident`.
* Automationsverhalten ohne eigenständigen Laufzeitschalter: `behavior`.

### UI-Struktur für Räume & Profile
* **Raum-UI:** General, Cover & Hardware, Positions, Window contacts, Room sensors, Geometry, Profile & Automation, Local data sources, Controls, Diagnostics.
* **Profil-UI:** General, Time, Brightness, Sun, Shading, Ventilation, Resident, Manual behavior.
* Im Raum-Schritt `Profile & Automation` zuerst das Profil wählen und danach die gewünschten Profilfunktionen explizit selektieren (niemals automatisch alle Funktionen aktivieren).
* Klare Trennung im UI: `Room name` (Konfigurationsobjekt) vs. `Home Assistant area` (zugeordnete physische HA-Area).

---

## Home Assistant Integration & Laufzeitregeln

* Callbacks dürfen nicht blockieren. `async_`-APIs verwenden; I/O über Home Assistant Helfer schedulen/awaiten (`async_add_executor_job`).
* State-Listener beim Unload sauber entfernen. Hintergrund-Tasks müssen an den Config Entry gebunden und beim Unload beendet werden.
* Nicht davon ausgehen, dass Entitäten existieren; fehlende oder nicht verfügbare Entitäten sicher abfangen.
* Lokale Home Assistant Zeit für sichtbare Zeitpläne verwenden; UTC für gespeicherte Timestamps.
* Konventionen der Entity Registry und Device Registry einhalten.

---

## Fahrbefehle, Beschattung & Manuelle Steuerung

### Fahrbefehle (`actuator.py`)
* Sämtliche automatischen Fahrbefehle laufen über den Controller und `actuator.py`.
* Prioritätenhierarchie wahren: Lockout > Force > Manual Override > Ventilation > Shading > Resident.
* Keine doppelten Fahrbefehle senden, wenn sich die Position bereits innerhalb der konfigurierten Toleranz befindet.
* Zwischenzustände (`opening`, `closing`) nicht als manuelle Bewegung werten, wenn Cover Control die Fahrt ausgelöst hat.

### Beschattungsregeln (`shading.py` & `evaluation.py`)
* Sonnengeometrie und beschattungsspezifische Sensorik gehören nach `shading.py`.
* Zielpositionsberechnung und Endauswertung gehören nach `evaluation.py`.
* Hysterese und Wartezeiten zustandsbehaftet führen und zurücksetzen, sobald die Bedingung ungültig wird.
* Sofort-Ende- und Sicherheitslogik bei Beschattung strikt wahren.

### Manuelle Steuerung
* Strikt trennen zwischen:
  1. Manueller Bewegungserkennung (`manual movement detection`)
  2. Manuellem Override-Zustand (`manual override state`)
  3. Geplanter Aktionshistorie (`scheduled action history`)
  4. Erzwingungsaktionen (`force actions`)
* Durch Cover Control initiierte Fahrten dürfen niemals nachträglich als manuelle Bedienung gewertet werden.

---

## UI, Übersetzungen & Diagnostik

* `strings.json`, `translations/en.json` und `translations/de.json` immer strukturell synchron halten.
* Für Selektor-Optionen Übersetzungsschlüssel statt hartkodierter englischer Texte verwenden.
* Python-Logging für Entwicklerdiagnose; HA-Events/Logbook für Benutzerdiagnose.
* Repetitive Logeinträge bei wiederholter Evaluierung deduplizieren.

---

## Test- & Verifizierungsstrategie

* Tests in isolierter virtueller Umgebung ausführen (`pytest-homeassistant-custom-component==0.13.365`).
* Parität zum Blueprint (CCA) in `tests/test_blueprint_parity.py` ohne externe Netzwerkabhängigkeit lokal testen.
* Native v6/v7-Tests klar von Legacy-Migrationstests trennen.
* `configured`, `enabled` und `eligible` separat abtesten.
* Entity-Registry-Cleanup testen, wenn Profilfunktionen abgewählt oder Profile entfernt werden.
* **Testausführung:**
  ```sh
  # Fokussierter Testlauf während der Entwicklung:
  .venv/bin/pytest -q tests/test_config_flow.py --asyncio-mode=auto

  # Vollständige Verifizierung vor Abschluss:
  .venv/bin/pytest -q --asyncio-mode=auto
  .venv/bin/python -m compileall -q custom_components tests scripts
  git diff --check
  ```

---

## Git, Commits & Releases (Ausschließlich auf Anweisung)

* **Git-Sicherheit:** Keine eigenständigen Commits, Pushes, Tags, Pull Requests oder Releases ohne ausdrücklichen Auftrag von Andreas.
* **Wenn Andreas Commits beauftragt:**
  * Logisch unabhängige Änderungen in separate Conventional Commits aufteilen.
  * Typen: `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `build`, `chore`, `style`, `perf`, `revert`.
  * Scopes kleingeschrieben (`runtime`, `config`, `release`, etc.).
  * Kein Punkt am Ende des Betreffs.
  * Validierung: `.venv/bin/python scripts/validate_commit.py --message "<subject>"`.
* **Wenn Andreas ein Release beauftragt:**
  * Keine manuellen Versionserhöhungen oder Änderungen an `manifest.json`.
  * Release-Verifizierung ausführen:
    ```sh
    .venv/bin/python scripts/verify_release.py --skip-tag
    .venv/bin/python scripts/build_release.py
    .venv/bin/python scripts/verify_release.py --archive --skip-tag
    rm -f cover_control.zip
    ```

---

## Checkliste vor Abschluss & Berichterstattung

Vor dem Melden einer abgeschlossenen Aufgabe:
1. Vorhandene Änderungen des Benutzers im Arbeitsbaum erhalten (`git status`).
2. Vollständigen Diff prüfen (`git diff`).
3. Relevante Tests und Validierungen ausführen.
4. `.venv/bin/python -m compileall -q custom_components tests scripts` und `git diff --check` ausführen.
5. Übersetzungen synchronisieren, falls Texte geändert wurden.
6. Keine temporären Dateien, ZIP-Dateien oder Debug-Artefakte hinterlassen.
7. **Berichterstattung:** Nach Änderungen immer die ausgeführten Tests und den aktuellen `git status` auf Deutsch berichten.