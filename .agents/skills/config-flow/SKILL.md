---
name: config-flow
description: Best Practices und Entwicklungsrichtlinien für Config Flows, Reconfigure Flows und Options Flows in cover-control.
---

# Config Flow Skill – Cover Control

Leitfaden für die Konfigurationsflüsse und Datenstrukturen von `cover-control`.

---

## 1. Architektur der Config Entries

Cover Control verwendet ein entkoppeltes Multi-Entry-Modell:

### Central Controller Entry (`ENTRY_TYPE_CONTROLLER`)
* **Verantwortung:** Globale Datenquellen (`global_sources`), zentrale Profile (`profiles`), Diagnose und Wiederherstellung (`recovery`).
* **Profile-Storage:** Alle Profile liegen ausschließlich in `controller.data[CONF_PROFILES]`.
* **Flow-Schritte:**
  * Initial-Setup: `user` → `global_sources` → Erstellung des Controller-Entry.
  * Reconfigure: `controller_reconfigure` Menü mit Profilverwaltung, globalen Quellen und Recovery.

### Standalone Room Entries (`ENTRY_TYPE_ROOM`)
* **Eigenständige ConfigEntries:** Räume sind **keine** Subentries, sondern vollwertige, eigenständige `ConfigEntry`-Objekte (`ENTRY_TYPE_ROOM`).
* **Unique ID:** `f"room-{controller_entry_id}-{room_id}"`.
* **Subentry-API:** Native Subentries sind deaktiviert:
  ```python
  @classmethod
  @callback
  def async_get_supported_subentry_types(cls, config_entry: config_entries.ConfigEntry) -> dict:
      return {}
  ```
* **Was der Raum speichert:**
  1. Physische Raumdaten: Cover-Entitäten, Positionen (Open, Closed, Shading, Ventilation, Lockout), Fenstersensoren, Geometrie.
  2. Profil-Referenz: Ausschließlich die Profil-ID (`CONF_ROOM_PROFILE_ID`) und die explizit ausgewählten Profilfunktionen (`CONF_PROFILE_FUNCTIONS`).
  3. Der Raum speichert **niemals** Profildefinitionen oder Schwellenwerte.

---

## 2. Ablauf im Room Reconfigure Flow

Der Reconfigure-Flow für Räume führt durch folgende Schritte:

1. `room_reconfigure`: Hauptmenü des Raums.
2. `room_general`: Name, zugeordnete Home Assistant Area.
3. `room_hardware`: Cover-Entitäten und Aktor-Einstellungen.
4. `room_positions`: Physische Fahrpositionen (0–100%).
5. `room_window`: Fenster- und Türkontakte, Aussperrschutz (Lockout).
6. `room_sensors`: Lokale Raum-Temperatur- oder Lux-Sensoren.
7. `room_geometry`: Ausrichtung (Azimut- und Elevationswinkel des Fensters).
8. `room_profile` (**Profile & Automation**):
   * Zuerst Profil auswählen (`profile_id`).
   * Danach die gewünschten Profilfunktionen explizit selektieren (`profile_functions`: `time`, `brightness`, `sun`, `shading`, `ventilation`, `resident`).
   * Niemals automatisch alle Funktionen aktivieren.
9. `room_local_sources`: Raum-spezifische Overrides für Datenquellen.
10. `room_controls` & `room_diagnostics`: Schalter- und Sensor-Setup.

---

## 3. Shared Normalisierung & Validierung

* Config Flow und Reconfigure Flow dürfen keine redundanten Schemata implementieren.
* Gemeinsame Schemata und Helfer liegen in:
  * `config_resolver.py`: Normalisierung und Auflösung der effektiven Konfiguration (`resolve_config_model`, `effective_profile`).
  * `config_profile_schema.py`: Schemadefinitionen für Profilfähigkeiten (`build_profile_schema`).
  * `config_profiles.py`: Validierung von Profilmodellen (`ConfigProfileModel`).
* Werte und Schlüssel immer über Konstanten in `const.py` definieren.

---

## 4. UI-Lokalisierung

* Keine englischen Labels hartkodieren.
* Selektor-Optionen immer über `translation_key` verknüpfen.
* Übersetzungen in `strings.json`, `translations/en.json` und `translations/de.json` synchron halten.

---

## 5. Testen von Flow-Änderungen

```sh
# Config Flow & Reconfigure Flow:
.venv/bin/pytest -q tests/test_config_flow.py --asyncio-mode=auto

# Datenmodell & Resolver:
.venv/bin/pytest -q tests/test_config_subentries.py --asyncio-mode=auto
```
