---
name: home-assistant
description: Richtlinien für Home Assistant Integration, asynchrones Verhalten und Lifecycle-Management in cover-control.
---

# Home Assistant Skill – Cover Control

Vorgaben für eine robuste und standardkonforme Integration in Home Assistant.

## 1. Asynchrones Verhalten

* **Non-blocking Callbacks:** Callbacks (`async_` Methoden) dürfen den Event-Loop niemals blockieren.
* **Blocking I/O:** Datei- oder Netzwerkzugriffe müssen über `hass.async_add_executor_job` ausgelagert werden.
* **Kein DB-Direktzugriff:** Niemals direkt auf SQLite / die HA-Recorder-Datenbank zugreifen.

## 2. Lifecycle & Cleanup

* **State-Listener:** Alle mit `async_track_state_change_event` oder `async_track_point_in_time` registrierten Listener müssen beim Unload abgemeldet werden (`remove_listener()`).
* **Background Tasks:** Hintergrund-Tasks müssen an den Entry gebunden und beim Unload abgebrochen (`cancel()`) und awaited werden.
* **Entity Registry:** Wenn Profilfunktionen abgewählt oder Profile gelöscht werden, müssen nicht mehr benötigte Entitäten über die Entity Registry bereinigt werden.

## 3. Entitäten & Plattformen

* Entitäten müssen resilient gegen fehlende oder ungültige Sensor-Zustände sein (`state in (STATE_UNAVAILABLE, STATE_UNKNOWN)`).
* Gerätetreue: Entitäten müssen ordnungsgemäß mit der passenden `device_info` verknüpft sein.
