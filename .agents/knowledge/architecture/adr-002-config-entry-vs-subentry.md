---
title: ADR-002: Controller- und Room-ConfigEntries statt Subentries
type: adr
status: accepted
date: 2026-10-18
tags:
  - architecture
  - config-flow
  - config-entry
  - migration
---

# ADR-002: Controller- und Room-ConfigEntries statt Subentries

## Kontext
Frühere Versionen experimentierten mit `ConfigSubentryFlow` und einem einzigen ConfigEntry für Räume und Profile. Die Subentry-API führte zu instabilem Lifecycle, Registry-Inkonsistenzen und komplexer Navigation. Ein einziger Entry erschwerte zusätzlich die klare Eigentümerschaft von Raumhardware und raumeigenen Entitäten.

## Entscheidung
Das aktuelle Schema v12 verwendet ausschließlich native ConfigEntries:
* Ein zentraler Controller-Entry besitzt globale Datenquellen und Profile unter `CONF_PROFILES`.
* Jeder Raum ist ein eigenständiger `ENTRY_TYPE_ROOM`-ConfigEntry und besitzt Hardware, physische Positionen, lokale Quellen, Profil-ID und ausgewählte Profilfunktionen.
* Profile sind weder ConfigEntries noch ConfigSubentries; sie bleiben zentrale Datenobjekte im Controller-Entry.
* `async_get_supported_subentry_types() == {}`; es gibt keine Laufzeitabhängigkeit von `ConfigSubentryFlow`.
* Migrationen überführen Altmodelle deterministisch in den Controller-/Room-Entry-Aufbau.

## Konsequenzen
* **Robuster Lifecycle:** Controller und Räume können über Standard-Home-Assistant-APIs sauber geladen, entladen und aktualisiert werden.
* **Klare Eigentümerschaft:** Profile bleiben zentral; Raumhardware und Raum-Entities gehören ausschließlich zum Room-Entry.
* **Saubere Translation-Namespaces:** Alle Übersetzungen liegen standardkonform unter `config.step` bzw. `options.step`.
* **Stabile Migrationen:** Ältere Setups werden automatisch konvertiert, ohne Datenverlust oder verwaiste Subentries.

---
Verwandte Notizen:
* [`../troubleshooting/entity-registry-cleanup.md`](../troubleshooting/entity-registry-cleanup.md)
