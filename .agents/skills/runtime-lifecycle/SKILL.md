---
name: runtime-lifecycle
description: Lebenszyklus und Datenfluss von festen Gruppen über Hub und Room Manager bis zur Entity.
---

# Runtime-Lifecycle

```text
Controller (global + groups)
  -> CoverControlHub (shared inputs + group timers)
  -> ControllerManager (one standalone room)
  -> CoverController (covers + mixins)
  -> Snapshot / Entities
```

- `CoverControlHub.group_users` indiziert Rooms nach `CONF_GROUP`.
- Eine Gruppenänderung wird nur auf Rooms dieser Gruppe angewendet.
- Ein Room-Gruppenwechsel ersetzt den `ResolvedRoomConfig`, aktualisiert Controller, Listener und Schedule-Snapshot und entfernt dadurch alte Gruppenwerte.
- Gemeinsame Gruppentimer werden per Cancel/Recreate dedupliziert; Unload entfernt Listener und Timer.
- Shared Inputs bleiben global oder room-lokal, physische Positionen bleiben Room-Eigentum.
- Keine blockierenden Callbacks; Tasks und Listener an ConfigEntry-Lifecycle binden.

Tests: `tests/test_group_runtime.py`, `tests/test_event_driven_processing.py`.
