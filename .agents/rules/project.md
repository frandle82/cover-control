---
trigger: always_on
---

# Projekt- & Architekturregeln – Cover Control

Verbindliche Architektur- und Implementierungsrichtlinien für die Home Assistant Custom Integration `cover-control`.

## 1. Projektstruktur & Runtime-Architektur

* **Laufzeit-Code:** `custom_components/cover_control/`
* **Regressionstests:** `tests/`
* **Skripte & Werkzeuge:** `scripts/`
* **Internes Wissenssystem (Obsidian-Vault):** `.agents/knowledge/`

### Mixin-Zuständigkeiten (`custom_components/cover_control/runtime/`)
Logik gehört in das zuständige Mixin, nicht in die Controller-Fassade:
* `actuator.py`: Fahrbefehle, Positionstoleranz, Lamellenkippung (Tilt) und Verzögerungslogik.
* `evaluation.py`: Berechnung der Zielposition und Auswertung der Bedingungen.
* `events.py`: Home Assistant State-Listener und Event-Subscriptions.
* `schedule.py`: Zeitpläne, Arbeitstag-Sensoren und Kalender-Ereignisse.
* `shading.py`: Feste Sonnenschutzmodi, Sonnengeometrie, Temperatur- und optionale Helligkeitsbedingungen.
* `status.py`: Zustände der Steuerungsentitäten, Diagnosesensoren und Statusgründe.

Controller-Imports bleiben stabil über `controller.py`. Logik nicht ohne klaren architektonischen Grund zwischen Mixins verschieben.

---

## 2. Source of Truth & Konfigurationsarchitektur

* **Konstanten & Defaults:** Gehören zentral nach `const.py`.
* **Persistente Konfiguration:** Gehört ausschließlich in den Home Assistant Config Entry.
* **Laufzeit-Status:** Bleibt im Arbeitsspeicher (in-memory), sofern keine Persistenz über Neustarts/Reloads hinweg erforderlich ist.
* **Shared Logic:** Gemeinsame Normalisierung und Validierung für Config Flow und Options Flow verwenden. Keine redundanten Konfigurationsschlüssel für denselben logischen Parameter.
* **Multi-Entry-Modell:**
  * Rooms sind eigenständige ConfigEntries (`ENTRY_TYPE_ROOM`), keine Subentries (`async_get_supported_subentry_types() == {}`).
  * Genau drei Gruppen liegen zentral in `controller.data[CONF_GROUPS]`: `living`, `sleep`, `children`.
  * Ein Raum speichert genau eine Gruppenzuordnung (`CONF_GROUP`). Details siehe Skill [`profile-model`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/profile-model/SKILL.md).

### Strikte Grenzen der Verantwortlichkeit:
* **GLOBAL:** Besitzt geteilte HA-Datenquellen (Arbeitstage, Kalender, Helligkeit, Außentemperatur, Wetter/Vorhersage, globale Bedingungen).
* **GROUP:** Besitzt Automationsverhalten und Schwellenwerte. Gruppen besitzen niemals raumeigene Entitäten oder Positionen.
  * Öffnen verwendet genau einen Modus aus `time`, `sunrise`, `golden_hour`, `elevation`, `brightness`; Schließen genau einen aus `time`, `sunset`, `golden_hour`, `elevation`, `brightness`.
  * Dynamic-/Hybrid-Elevation ist kein aktives Feature und wird nur als Legacy-Migrationsinput erkannt.
* **ROOM:** Besitzt Hardware, Cover-Entitäten, physische Positionen, Fenstersensoren, Geometrie, Raumschalter und eine Gruppenzuordnung.
* **SWITCH:** Steuert, ob eine konfigurierte Raumfunktion zur Laufzeit aktiv (enabled) ist.
* **RUNTIME:** Entscheidet, ob eine aktive Funktion unter den aktuellen Bedingungen ausführungsberechtigt (eligible) ist.
* Generische Zusatzbedingungen und CCA-spezifische Override-Schalter gehören nicht zum Zielmodell. Window-, Ventilation- und Shading-Konflikte folgen festen Shuttercontrol-Prioritäten.

### Zustandsmodell
* **`configured`**: Funktion gehört zum festen Gruppenmodell.
* **`enabled`**: Der zugehörige Laufzeitschalter steht auf **ON**.
* **`eligible`**: Die aktuellen Bedingungen erlauben der Funktion eine Aktion.

Ein Schalterzustand ändert niemals die Konfiguration oder Gruppenzuordnung.

### Gruppenfunktionen & Schalter
* Autonom schaltbare Gruppenfunktionen mit Laufzeitschalter: `time`, `brightness`, `sun`, `shading`, `ventilation`, `resident`.
* Automationsverhalten ohne eigenständigen Laufzeitschalter: `behavior`.

---

## 3. UI-Struktur & Lokalisierung

* **Raum-UI:** General, Group, Cover & Hardware, Positions, Window contacts, Room sensors, Local data sources, Controls, Diagnostics.
* **Gruppen-UI:** Time, Brightness, Sun, Shading, Ventilation, Resident, Safety, Manual behavior.
* Shading-Direction und -Schwellen gehören zur Gruppe; die physische `shading_position` bleibt Room-Eigentum.
* Ein Raum wählt genau eine feste Gruppe; einzelne Gruppenfunktionen werden nicht selektiert.
* Klare Trennung im UI: `Room name` (Konfigurationsobjekt) vs. `Home Assistant area` (zugeordnete physische HA-Area).
* Übersetzungen immer synchron halten: `strings.json`, `translations/en.json`, `translations/de.json`.

---

## 4. Fahrbefehle, Beschattung & Manuelle Steuerung

* **Fahrbefehle (`actuator.py`):** Sämtliche automatischen Fahrbefehle laufen über den Controller und `actuator.py`.
* **Prioritätenhierarchie:** Safety > Manual Override > Window / Ventilation / Lockout > Shading / Heat Protection > Resident > Time / Astro / Brightness.
* **Toleranz:** Keine doppelten Fahrbefehle senden, wenn sich die Position bereits innerhalb der konfigurierten Toleranz befindet.
* **Fensterpriorität:** Offen fährt auf die Lockout-Position, gekippt auf die Lüftungsposition; beide Zustände gehen Komfort-Beschattung vor. Nach dem Schließen wird der gespeicherte Hintergrund wieder ausgewertet.
* **Manuelle Steuerung:** Strikt trennen zwischen:
  1. Manueller Bewegungserkennung (`manual movement detection`)
  2. Manuellem Override-Zustand (`manual override state`)
  3. Geplanter Aktionshistorie (`scheduled action history`)
* Durch Cover Control initiierte Fahrten (auch Zwischenzustände wie `opening`/`closing`) dürfen niemals als manuelle Bedienung gewertet werden.
* **Beschattungsregeln:** Ausschließlich feste Shuttercontrol-Modi; keine frei kombinierbaren AND-/OR- oder Forecast-Bedingungen. Direction ist Mittelpunkt ± Bereich, Endgrenzen nutzen prozentuale Hysterese. Zielposition/Aktorpfad bleiben in `evaluation.py`/`actuator.py`.

---

## 5. Internes Wissenssystem (Obsidian-Vault in `.agents/knowledge/`)

Der Ordner `.agents/` fungiert als lokales Second Brain für das Projekt:
* **Struktur:** Reines Markdown mit Frontmatter (`type`, `tags`, `status`), Querverweisen und zentralem Index ([`INDEX.md`](file:///Users/andreasgrundke/Git/cover-control/.agents/knowledge/INDEX.md)).
* **Abruf vor Aufgaben (Retrieval):** Vor Anforderungsanalyse oder Implementierung immer relevante Notizen und ADRs aus `.agents/knowledge/` abrufen (Skill `knowledge`).
* **Wissensaufnahme (Capture):** Neue architektonische Entscheidungen, gelöste Edge Cases und Best Practices werden nach Abschluss sofort strukturiert als Notiz festgehalten und im `INDEX.md` verlinkt.
* **Pflicht bei fachlich relevanten Änderungen:** Änderungen an ConfigEntry-/Group-/Room-Architektur, Resolver, Runtime-Lifecycle, Schedule/Time/Sun/Workday/Calendar, CCA-Parität, Aktivitäts-/Diagnose-Entitäten, Migrationen, Release-Prozess oder wichtigen Bugfixes mit neuer Root Cause/Invariante erfordern die Prüfung und gegebenenfalls Aktualisierung des Knowledge-Bestands im selben Auftrag.
* **Widerspruchsfreiheit:** Veraltete Aussagen sind zu korrigieren oder zu entfernen. Es dürfen nur bestätigte technische Fakten aufgenommen werden. Knowledge muss mit Code, Tests, `AGENTS.md`, `.agents/rules/` und `.agents/skills/` übereinstimmen.
* **Keine externen Abhängigkeiten:** Reines lokales Markdown; keine MCP-Server oder proprietäre Cloud-Tools erforderlich.

---

## 6. Entwicklungszyklus & Skill-Einsatz

Jede Entwicklungsaufgabe in `cover-control` folgt verbindlich diesem Phasenmodell:

1. **Anforderungsanalyse & Wissensabruf:**
   * Vor Beginn vorhandenes Wissen abrufen (Skill [`knowledge`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/knowledge/SKILL.md)).
   * Fremde Referenzimplementierungen vor jeder Zuordnung oder Portierung an einem fixierten Commit untersuchen (Skill [`reverse-engineering-anything`](../skills/reverse-engineering-anything/SKILL.md)).
   * Bei neuen Features oder unklaren Anforderungen: Skill [`grill-me`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/grill-me/SKILL.md) einsetzen.
   * Blueprint-Parität bei portierten Features beachten (Skill [`cca-parity`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/cca-parity/SKILL.md)).
2. **Architekturkonforme Implementierung:**
   * Domänenregeln beachten:
     * Gesamtübersicht: [`cover-control`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/cover-control/SKILL.md)
     * Groups & Resolver: [`profile-model`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/profile-model/SKILL.md)
     * Zeit- & Sonnenlogik: [`schedule-runtime`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/schedule-runtime/SKILL.md)
     * Datenfluss & Lifecycle: [`runtime-lifecycle`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/runtime-lifecycle/SKILL.md)
     * HA Core & Async: [`home-assistant`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/home-assistant/SKILL.md)
     * Flows & UI-Setup: [`config-flow`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/config-flow/SKILL.md)
     * Schema-Migrationen: [`migrations`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/migrations/SKILL.md)
     * Entity Registry: [`entity-registry`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/entity-registry/SKILL.md)
     * Übersetzungen: [`translations`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/translations/SKILL.md)
   * Kontext- und Token-Budget schonen ([`token-budget`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/token-budget/SKILL.md)).
3. **Hypothesenbasiertes Debugging & CI-Analyse:**
   * Bei lokalen Fehlern: Skill [`systematic-debugging`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/systematic-debugging/SKILL.md).
   * Bei GitHub-Actions-Fehlern: Skill [`gh-fix-ci`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/gh-fix-ci/SKILL.md).
4. **Verifikation & E2E-Tests:**
   * Backend-Regressionstests ([`testing`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/testing/SKILL.md), [`cca-parity`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/cca-parity/SKILL.md)).
   * Frontend-/UI-Workflow-Tests im Browser ([`playwright-interactive`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/playwright-interactive/SKILL.md)).
5. **Qualitätssicherung & Review:**
   * Code-Review vor Merge/Commit ([`code-reviewer`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/code-reviewer/SKILL.md), [`diff-audit`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/diff-audit/SKILL.md)).
6. **PR, Changelog & Release:**
   * Verbindlicher Veröffentlichungsprozess: [`release`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/release/SKILL.md).
   * Strukturierte PR-Beschreibungen: [`pr-description`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/pr-description/SKILL.md).
   * Changelog- und Draft-Audit: [`changelog-review`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/changelog-review/SKILL.md).
   * Disziplinierte Conventional Commits: [`caveman-commit`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/caveman-commit/SKILL.md).
7. **Wissensaufnahme & Workflow-Standardisierung:**
   * Neue Erkenntnisse und Architekturentscheidungen in `.agents/knowledge/` aufnehmen ([`knowledge`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/knowledge/SKILL.md)).
   * Wiederkehrende Workflows als Skills festhalten ([`skill-creator`](file:///Users/andreasgrundke/Git/cover-control/.agents/skills/skill-creator/SKILL.md)).
