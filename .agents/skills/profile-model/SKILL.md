---
name: profile-model
description: Feste Gruppenarchitektur für Controller, Rooms, Resolver und Live-Propagation.
---

# Fixed Group Model

Cover Control besitzt exakt drei feste, nicht umbenennbare und nicht löschbare Konfigurationsgruppen: `living`, `sleep`, `children`.

- Der Controller-ConfigEntry besitzt globale Quellen und `CONF_GROUPS`.
- Jede Gruppe besitzt dieselben Automationsbereiche: Time, Brightness, Sun, Shading, Ventilation, Resident, Behavior und Safety.
- Jeder Room ist ein eigenständiger `ENTRY_TYPE_ROOM`-ConfigEntry und speichert genau `CONF_GROUP`; Default ist `living`.
- Rooms besitzen Hardware, Kontakte, Geometrie, physische Positionen, Safety-Teilnahme und Recalibrate.
- Es gibt keine benutzerdefinierten Profile und keine Funktionsauswahl pro Raum.

Resolver-Reihenfolge:

```text
system defaults -> global defaults -> selected group -> room settings -> room overrides -> global sources -> local source overrides
```

Gruppenänderungen propagieren nur zu Rooms derselben Gruppe. Ein Gruppenwechsel eines Rooms ersetzt dessen komplette aufgelöste Gruppenwerte und baut Listener, Zeitplan-Snapshot und Timer neu auf.

Tests: `tests/test_fixed_groups.py`, `tests/test_group_migration.py`, `tests/test_group_runtime.py`, `tests/test_group_config_flow.py`.
