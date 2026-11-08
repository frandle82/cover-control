---
name: config-flow
description: Config-, Reconfigure- und Options-Flow-Regeln für feste Gruppen und Standalone Rooms.
---

# Config Flow

- Controller: globale Quellen, exakt drei feste Gruppen (`living`, `sleep`, `children`), Diagnose und Recovery.
- Gruppen werden weder erstellt, umbenannt, dupliziert noch gelöscht. Jede Gruppe bietet dieselben Bereiche.
- Rooms sind eigenständige `ENTRY_TYPE_ROOM`-ConfigEntries; `async_get_supported_subentry_types() == {}`.
- Ein Room speichert `CONF_GROUP` (Default `living`) sowie Hardware, Positionen, Kontakte, lokale Quellen, Safety-Teilnahme und Controls.
- Gruppenwerte liegen ausschließlich in `controller.data[CONF_GROUPS]`.
- Shared Schemas liegen in `config_group_schema.py`, Modellnormalisierung in `config_groups.py`, Auflösung in `config_resolver.py`.
- `strings.json`, `translations/en.json` und `translations/de.json` strukturell synchron halten.

Tests: `.venv/bin/pytest -q tests/test_group_config_flow.py --asyncio-mode=auto`.
