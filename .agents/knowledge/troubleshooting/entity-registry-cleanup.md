---
title: Entity-Registry-Cleanup bei Room-Änderungen
type: troubleshooting
status: active
tags: [entity-registry, lifecycle, rooms]
---

# Entity-Registry-Cleanup

Rooms sind eigenständige ConfigEntries. Beim Entfernen eines Rooms oder einer room-eigenen optionalen Entity müssen nicht mehr gewünschte Registry-Einträge explizit über `registry.async_remove()` entfernt werden. Ein Gruppenwechsel entfernt keine Entity-Konfiguration; er ersetzt nur die aufgelösten Gruppenwerte und baut Listener/Timer neu auf.
