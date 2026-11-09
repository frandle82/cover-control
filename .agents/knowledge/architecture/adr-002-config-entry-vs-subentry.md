---
title: ADR-002: Controller- und Room-ConfigEntries mit festen Gruppen
type: adr
status: accepted
date: 2026-11-08
tags: [architecture, config-flow, config-entry, migration]
---

# ADR-002: Controller, Standalone Rooms und feste Gruppen

## Entscheidung

- Ein Controller-ConfigEntry besitzt globale Quellen und exakt drei feste Gruppen unter `CONF_GROUPS`: `living`, `sleep`, `children`.
- Jeder Raum ist ein eigenständiger `ENTRY_TYPE_ROOM`-ConfigEntry und speichert genau `CONF_GROUP`.
- Gruppen sind weder ConfigEntries noch ConfigSubentries und können nicht erstellt, umbenannt oder gelöscht werden.
- Rooms besitzen Hardware, physische Positionen, Kontakte, lokale Quellen, Safety-Teilnahme und Controls.
- `async_get_supported_subentry_types() == {}`.
- ConfigEntry-Version 13 und Modellversion 8 migrieren frühere freie Profile deterministisch in Gruppen.

## Konsequenzen

Klare Eigentümerschaft, generischer Resolver `Room -> Group -> Controller group config`, gezielte Live-Propagation pro Gruppe und kein paralleles Profilmodell.

Verwandt: [`../ioBroker-shuttercontrol.md`](../ioBroker-shuttercontrol.md)
