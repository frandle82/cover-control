---
name: runtime-lifecycle
description: Lebenszyklus-, Datenfluss- und Event-Architektur von cover-control. Von ConfigEntry über Hub und Controller bis zur Entity.
---

# Runtime-Lifecycle Skill – Datenfluss & Lebenszyklus

## Zweck

Dieser Skill dokumentiert den hierarchischen Aufbau, den Lebenszyklus (Setup, Reload, Unload) und das Zusammenspiel der Runtime-Komponenten in `cover-control`.

---

## 1. Die Runtime-Hierarchie (Kette des Datenflusses)

```
[Central Controller Entry] ──hält──> Globale Quellen & Profile
           │
           ▼
[CoverControlHub (`hub.py`)] ──koordiniert──> Shared Inputs, Profil-Evaluierung, Dispatcher
           │
           ▼
[ControllerManager (`runtime/manager.py`)] ──verwaltet──> Alle Room-Controller
           │
           ▼
[CoverController (`runtime/controller.py`)] ──berechnet──> Mixin-Logik & Fahrbefehle
           │
           ▼
[FeatureState & Snapshot (`feature_state.py`)] ──friert ein──> Unveränderlicher Status
           │
           ▼
[Entities (`sensor.py`, `switch.py`, `button.py`)] ──exponiert──> HA State Machine
```

### Komponenten im Detail:
1. **Central Controller Entry (`ENTRY_TYPE_CONTROLLER`):**
   * Persistiert globale Sensoren (`global_sources`) und die Profilsammlung (`profiles`).
2. **`CoverControlHub` (`hub.py`):**
   * Koordiniert übergeordnete Datenquellen (`SharedInputCoordinator`).
   * Führt zentrale Profilberechnungen durch (`evaluate_time_profile`).
   * Sendet Signale via `async_dispatcher_send(hass, SIGNAL_HUB_STATE_UPDATED)`.
3. **`ControllerManager` (`runtime/manager.py`):**
   * Hält die Instanzen aller aktiven `CoverController`.
   * Reagiert auf Raum- und Profil-Updates und triggert Neu-Evaluierungen.
4. **`CoverController` (`runtime/controller.py`):**
   * Setzt die Mixins zusammen (`actuator`, `evaluation`, `events`, `schedule`, `shading`, `status`).
   * Führt Raum-spezifische Fahrten und Schalterlogik aus.
5. **Snapshot & `FeatureState`:**
   * Kapselt den Berechnungsstand (Position, Reason, Flags) in unveränderlichen Datenstrukturen.
6. **Entitäten:**
   * Diagnosesensoren, Steuerschalter (`switch.<raum>_<funktion>`) und Aktions-Buttons lesen rein aus dem Snapshot.

---

## 2. Lebenszyklus-Ereignisse

### Integration Setup (`async_setup_entry`)
* Initialisiert den Hub und Runtime-Container in `hass.data[DOMAIN][entry.entry_id]`.
* Erzeugt und startet Entitätsplattformen (`PLATFORMS = ["cover", "sensor", "switch", "button"]`).
* Bindet Hintergrund-Tasks an den Lebenszyklus des Entries.

### Unload & Reload (`async_unload_entry`)
* **Sauberes Deregistrieren:** Alle State-Listener (`async_track_state_change_event`) und Timer (`async_track_point_in_time`) müssen über ihre Unlisten-Callbacks deregistriert werden.
* **Task Cancellation:** Laufende Tasks (`async_create_task`) werden abgebrochen (`task.cancel()`) und mit `asyncio.gather` abgewartet.
* **Plattformen entladen:** `await hass.config_entries.async_unload_platforms(entry, PLATFORMS)`.

### Profiländerung & Live-Propagation
* Wird ein zentrales Profil im Controller rekonfiguriert:
  1. `CoverControlHub` invalidiert den Profil-Cache.
  2. Neuberechnung via `evaluate_time_profile()`.
  3. `SIGNAL_HUB_STATE_UPDATED` signalisiert den Raum-Controllern die Änderung.
  4. Alle verknüpften Räume evaluieren sofort mit der neuen effektiven Konfiguration neu.

---

## 3. Dispatcher, Signale & Timer

* **`SIGNAL_HUB_STATE_UPDATED`:** Informiert über Updates globaler Sensoren (Wetter, Kalender, Arbeitstag, Profilzeiten).
* **`SIGNAL_ENTRY_STATE_UPDATED`:** Informiert Entitäten über Statusänderungen des Raum-Controllers.
* **Timer-Hygiene:** Niemals blockierende sleeps! Immer `async_call_later` oder `async_track_point_in_time` von Home Assistant verwenden.

---

## 4. Testen des Lifecycles

```sh
# Lifecycle und Setup/Unload testen:
.venv/bin/pytest -q tests/test_init.py --asyncio-mode=auto
.venv/bin/pytest -q tests/test_manager.py --asyncio-mode=auto
```
