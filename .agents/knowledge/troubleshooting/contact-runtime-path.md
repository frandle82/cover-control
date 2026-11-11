---
title: Fensterkontakte im Room-Runtime-Pfad
type: troubleshooting
status: active
tags:
  - contacts
  - ventilation
  - listeners
  - config-entry
---

# Fensterkontakte im Room-Runtime-Pfad

## Bestätigte Invarianten

- Room Contact-Maps sind mit der Cover-`entity_id` indiziert und bleiben beim Aufbau des transienten Modells, beim Resolver und nach einem Entry-Reload unverändert.
- Jeder `CoverController` liest nur die Sensorlisten seines Covers; mehrere Sensoren verwenden ODER-Semantik und lokale Listener verhindern eine Vermischung zwischen Covers.
- Nichtleere Room-owned Contact-Maps konfigurieren die Ventilation-Funktion und damit deren Runtime-Switch. Sie schalten Ventilation nicht automatisch ein; `enabled` bleibt Gruppenwert beziehungsweise Runtime-Toggle.
- Config-Updates diffen die cover-lokalen Listener: entfernte Sensoren werden abgemeldet, neue Sensoren registriert.
- Nur der HA-Zustand `on` ist ein aktiver Kontakt. `off`, `unknown` und `unavailable` lösen keine Komfortfahrt aus.

## Fehlerursache

Die zentrale Feature-Erkennung wertete nur Gruppenschlüssel aus. Dadurch konnten gültige Room Contact-Maps existieren, ohne dass der Ventilation-Switch angelegt wurde. Der Runtime-Pfad blieb so für Nutzer nicht aktivierbar, obwohl Persistenz, Resolver und Listenerzuordnung korrekt waren.

---
Verwandte Notizen:
* [`../domain/priorities-and-lockout.md`](../domain/priorities-and-lockout.md)
* [`../architecture/adr-003-state-hierarchy-configured-enabled-eligible.md`](../architecture/adr-003-state-hierarchy-configured-enabled-eligible.md)
