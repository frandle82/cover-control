# AGENTS.md – Cover Control (Lokale Instruktionen)

Verbindliche lokale Arbeitsanweisungen für KI-Coding-Agenten im Projekt `cover-control`.

Diese Datei enthält projektweite Arbeitsanweisungen für KI-Coding-Agenten und wird versioniert.

---

## 1. Regelungen & Verbindliche Anweisungen

* **Verbindliche Regeln:** Befolge strikt die Regeln unter `.agents/rules/`:
  * `project.md`: Projekt- und Architekturregeln, Mixin-Verantwortlichkeiten, Konfigurationsmodell.
  * `git-safety.md`: Git-Sicherheitsregeln, Release-Verfahren, Merge- und PR-Standards.
  * `quality.md`: Teststrategie, Code-Reviews, Home Assistant Standards.
  * `task-completion.md`: Verbindliche Kriterien zur vollständigen Aufgabenerledigung.
* **Internes Wissenssystem (Obsidian-Vault):** Das Verzeichnis `.agents/knowledge/` dient als lokales Second Brain. Vor jeder Aufgabe Wissen abrufen, nach jeder neuen Erkenntnis oder Architekturentscheidung strukturiert aufnehmen (Skill [`knowledge`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/knowledge/SKILL.md)). Keine externen Obsidian-MCP-Server nötig.
* **Git-Sicherheit:** Keine eigenständigen Commits, Pushes, Tags, Pull Requests oder Releases ohne ausdrücklichen Auftrag von Andreas.
* **Änderungsschutz:** Vorhandene Änderungen des Benutzers müssen zwingend erhalten bleiben.
* **Berichterstattung:** Nach Änderungen immer die ausgeführten Tests und den aktuellen `git status` auf Deutsch berichten.

---

## 2. Skill-Einsatzmatrix nach Entwicklungsphasen

Verwende bei der Bearbeitung von Aufgaben die spezialisierten Skills unter `.agents/skills/`:

| Phase | Skill | Zweck / Einsatzgebiet |
|---|---|---|
| **1. Wissensabruf & Anforderungsanalyse** | [`knowledge`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/knowledge/SKILL.md) | Relevantes Vorwissen, ADRs und Troubleshooting-Notizen aus `.agents/knowledge/` abrufen. |
| | [`grill-me`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/grill-me/SKILL.md) | Intensives Entwickler-Interview vor Codeerstellung; deckt unklare Anforderungen und Edge Cases auf. |
| | [`cca-parity`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/cca-parity/SKILL.md) | Blueprint-Parität; Kriterien für vollständige funktionale Integration (FULL-Kette). |
| **2. Architektur & Runtime-Entwicklung** | [`cover-control`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/cover-control/SKILL.md) | Domänenübersicht und Mixin-Aufteilung (`runtime/`). |
| | [`profile-model`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/profile-model/SKILL.md) | Zentrale Profile im Controller, Raum-Referenzen, Resolver und Live-Propagation. |
| | [`schedule-runtime`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/schedule-runtime/SKILL.md) | Zeitpläne, Early/Late, Workday, Fixed/Dynamic/Hybrid Sun, `_TimeProfileProbe`. |
| | [`runtime-lifecycle`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/runtime-lifecycle/SKILL.md) | Datenfluss Controller → Hub → Room Manager → Controller → Snapshot → Entity. |
| | [`home-assistant`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/home-assistant/SKILL.md) | Async-Richtlinien, Non-blocking Callbacks, Event-Loop und Lifecycle-Management. |
| | [`config-flow`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/config-flow/SKILL.md) | Reconfigure Flows, Standalone Room Entries (`ENTRY_TYPE_ROOM`), UI-Schemas. |
| | [`migrations`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/migrations/SKILL.md) | Schema-Migrationen zwischen Versionen und Upgradepfade. |
| | [`entity-registry`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/entity-registry/SKILL.md) | Entity-Registry-Lifecycle, Cleanup verwaister Entitäten bei Raum-/Profiländerungen. |
| | [`translations`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/translations/SKILL.md) | Synchronisation von `strings.json`, `en.json` und `de.json`. |
| | [`token-budget`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/token-budget/SKILL.md) | Schonung des Kontextfensters und Vermeidung von Tool-Overhead. |
| **3. Testen & E2E-Verifikation** | [`testing`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/testing/SKILL.md) | Pytest-Ausführung, isolierte Umgebung, Modul- und Integrationstests. |
| | [`cca-parity`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/cca-parity/SKILL.md) | Blueprint-Paritätstests ohne externe Netzwerkabhängigkeit. |
| | [`playwright-interactive`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/playwright-interactive/SKILL.md) | End-to-End-Tests und Web-App-Testing; interaktives Durchklicken von UI-Flows im Browser. |
| **4. Fehlersuche & CI-Debugging** | [`systematic-debugging`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/systematic-debugging/SKILL.md) | Hypothesenbasierte 4-Schritte-Fehlerdiagnose ohne Trial-and-Error. |
| | [`gh-fix-ci`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/gh-fix-ci/SKILL.md) | Automatisierte Analyse fehlgeschlagener GitHub-Actions-Workflows via `gh`-CLI und gezielte Fixes. |
| **5. Qualitätssicherung & Review** | [`code-reviewer`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/code-reviewer/SKILL.md) | Automatisierte Reviews von Diffs und PRs auf Sicherheit, Async-Konformität und Performance. |
| | [`diff-audit`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/diff-audit/SKILL.md) | Pre-Completion-Checkliste vor Aufgabenabschluss (Scope, Whitespace, Artefakte). |
| **6. Commit, PR & Release** | [`release`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/release/SKILL.md) | Verbindliche Release-Kette (PR → Merge → Draft-Review → Workflow-Dispatch → Assets). |
| | [`pr-description`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/pr-description/SKILL.md) | Strukturierte, changelog-taugliche PR-Bodies für Release Drafter. |
| | [`changelog-review`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/changelog-review/SKILL.md) | Prüfung des generierten Release-Drafts vor Workflow-Dispatch. |
| | [`caveman-commit`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/caveman-commit/SKILL.md) | Normgerechte Conventional Commits ohne Fülltext (`<type>(<scope>): <kurze beschreibung>`). |
| | [`caveman`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/caveman/SKILL.md) | Ultra-kompakte, token-sparende Kommunikation. |
| **7. Wissensaufnahme & Standardisierung** | [`knowledge`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/knowledge/SKILL.md) | Neue Erkenntnisse, Entwurfsentscheidungen und Bug-Lösungen als Notizen in `.agents/knowledge/` aufnehmen. |
| | [`skill-creator`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/skill-creator/SKILL.md) | Überführen bewährter Sitzungen und wiederkehrender Muster in neue `SKILL.md`-Dateien. |

---

## 3. Verbindliche Teststrategie

* Jede Verhaltensänderung (behavioral change) muss durch Regressionstests abgedeckt werden.
* Vor dem Abschluss einer Änderung immer die vollständige Integrationstestsuite ausführen.
* Tests niemals nur auf das aktuell bearbeitete Modul beschränken.
* Änderungen an Config Flows, Migrationen, Entitäten, Attributen, Discovery, Events, Services, Diagnosen, Umgebungsbewertungen oder Release-Verhalten erfordern spezifische Regressionstests.
* Authoritative Release Gate: Die stabile Home Assistant Testsuite (`pytest-homeassistant-custom-component`) ist das verbindliche Freigabekriterium.

---

## 4. Projektübersicht & Laufzeitarchitektur

Home Assistant Custom Integration zur automatisierten Rollladen- und Jalousiensteuerung.
* Laufzeit-Code: `custom_components/cover_control/`
* Regressionstests: `tests/`
* Wartungs- und Release-Skripte: `scripts/`
* Wissensspeicher: `.agents/knowledge/`

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

## 5. Arbeitsweise, Single Source of Truth & Wissensnetz

* Vor Änderungen immer relevante Implementierung, Tests, Konstanten, Übersetzungen und Notizen in `.agents/knowledge/` prüfen.
* Bestehende Muster wiederverwenden und Pfade konsolidieren, statt Parallelstrukturen aufzubauen.
* Änderungen strikt auf die Anforderung beschränken (keine unaufgeforderten Refactorings oder Formatierungsänderungen).
* **Source of Truth:**
  * Gemeinsame Konstanten und Defaults gehören in `const.py`.
  * Persistente Konfiguration gehört ausschließlich in den Home Assistant Config Entry.
  * Laufzeit-Zustände bleiben im Speicher, sofern keine Persistenz über Neustarts/Reloads hinweg nötig ist.
  * Keine redundanten Konfigurationsschlüssel für denselben logischen Parameter anlegen.
  * Shared Normalisierung und Validierung für Config Flow und Options Flow verwenden.

---

## 6. Cover Control Konfigurationsarchitektur

Strikte Grenzen der Verantwortlichkeit:
* **GLOBAL:** Besitzt geteilte Home Assistant Datenquellen (Arbeitstage, Kalender, Helligkeit, Außentemperatur, Wetter/Vorhersage, globale Bedingungen) im zentralen Controller-Entry.
* **PROFILE:** Besitzt Automationsverhalten und Schwellenwerte (Zeitpläne, Helligkeitsschwellen, Hysterese, Wartezeiten, Beschattungs- und Lüftungsregeln) ausschließlich im Controller-Entry unter `controller.data[CONF_PROFILES]`. Profile besitzen niemals raumeigene Entitäten oder Positionen.
* **ROOM:** Ist ein eigenständiger `ConfigEntry` (`ENTRY_TYPE_ROOM`), kein Subentry (`async_get_supported_subentry_types() == {}`). Besitzt Hardware, Cover-Entitäten, physische Positionen (Offen, Geschlossen, Beschattung, Kippung, Lüftung, Lockout), Fenstersensoren, Geometrie, Raumschalter sowie die Profil-ID (`CONF_ROOM_PROFILE_ID`) und ausgewählte Profilfunktionen (`CONF_PROFILE_FUNCTIONS`).
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

## 7. Home Assistant Integration & Laufzeitregeln

* Callbacks dürfen nicht blockieren. `async_`-APIs verwenden; I/O über Home Assistant Helfer schedulen/awaiten (`async_add_executor_job`).
* State-Listener beim Unload sauber entfernen. Hintergrund-Tasks müssen an den Config Entry gebunden und beim Unload beendet werden.
* Nicht davon ausgehen, dass Entitäten existieren; fehlende oder nicht verfügbare Entitäten sicher abfangen.
* Lokale Home Assistant Zeit für sichtbare Zeitpläne verwenden; UTC für gespeicherte Timestamps.
* Konventionen der Entity Registry und Device Registry einhalten.

---

## 8. Fahrbefehle, Beschattung & Manuelle Steuerung

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

## 9. UI, Übersetzungen & Diagnostik

* `strings.json`, `translations/en.json` und `translations/de.json` immer strukturell synchron halten.
* Für Selektor-Optionen Übersetzungsschlüssel statt hartkodierter englischer Texte verwenden.
* Python-Logging für Entwicklerdiagnose; HA-Events/Logbook für Benutzerdiagnose.
* Repetitive Logeinträge bei wiederholter Evaluierung deduplizieren.

---

## 10. Test- & Verifizierungsstrategie

* Tests in isolierter virtueller Umgebung ausführen (`pytest-homeassistant-custom-component==0.13.365`).
* Parität zum Blueprint (CCA) in `tests/test_blueprint_parity.py` ohne externe Netzwerkabhängigkeit lokal testen.
* Native Tests klar von Legacy-Migrationstests trennen.
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

## 11. Git & Commits (Ausschließlich auf Anweisung)

* **Git-Sicherheit:** Keine eigenständigen Commits, Pushes, Tags oder Pull Requests ohne ausdrücklichen Auftrag von Andreas.
* **Release-Erstellung auf GitHub:** Releases werden ausschließlich über den GitHub Actions Workflow ("Create Release") auf GitHub erstellt. Codex erstellt keine manuellen Releases, erhöht keine Versionsnummern und setzt keine Release-Tags.
* **Wenn Andreas Commits beauftragt (Caveman-Commit):**
  * Den Skill [`caveman-commit`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/caveman-commit/SKILL.md) verwenden: Ultra-prägnante, normgerechte Conventional Commits ohne Fülltext (`<type>(<scope>): <kurze beschreibung>`).
  * Typen: `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `build`, `chore`, `style`, `perf`, `revert`.
  * Scopes kleingeschrieben (`runtime`, `config`, `shading`, `events`, `docs`, etc.).
  * Imperativer Stil, kein Punkt am Ende des Betreffs, maximal 72 Zeichen.
  * Logisch unabhängige Änderungen in separate Commits aufteilen.
  * Validierung: `.venv/bin/python scripts/validate_commit.py --message "<subject>"`.

---

## 12. Checkliste vor Abschluss & Berichterstattung

Vor dem Melden einer abgeschlossenen Aufgabe:
1. Vorhandene Änderungen des Benutzers im Arbeitsbaum erhalten (`git status`).
2. Vollständigen Diff prüfen (`git diff`).
3. Relevante Tests und Validierungen ausführen.
4. `.venv/bin/python -m compileall -q custom_components tests scripts` und `git diff --check` ausführen.
5. Neues Wissen in `.agents/knowledge/` aufnehmen (ADR, Domäne oder Troubleshooting), falls neue Erkenntnisse gewonnen wurden.
6. Übersetzungen synchronisieren, falls Texte geändert wurden.
7. Keine temporären Dateien, ZIP-Dateien oder Debug-Artefakte hinterlassen.
8. **Berichterstattung:** Nach Änderungen immer die ausgeführten Tests und den aktuellen `git status` auf Deutsch berichten.
