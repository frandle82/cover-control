---
title: Entity Registry Lifecycle & Cleanup
type: troubleshooting
status: active
tags:
  - troubleshooting
  - entity-registry
  - cleanup
  - lifecycle
---

# Entity Registry Lifecycle & Cleanup

## Symptom
Wenn der Benutzer im Options-Flow eine Profilfunktion (z. B. `shading`) abwählt oder ein Profil aus einem Raum entfernt, bleiben die zuvor erzeugten Entitäten (z. B. `switch.<raum>_shading`) als "verwaist" oder "nicht verfügbar" in der Home Assistant Entity Registry stehen.

## Ursache
Home Assistant löscht Entitäten nicht automatisch, wenn sie beim Reload eines Config Entries nicht mehr registriert werden. Sie verbleiben als verwaiste Registry-Einträge, es sei denn, die Integration bereinigt sie explizit über `er.async_get(hass).async_remove(entity_id)`.

## Lösung
In `custom_components/cover_control/entity.py` bzw. `__init__.py`:
1. Beim Setup und bei jedem Reconfigure/Reload wird die Menge der aktuell konfigurierten Funktionen (`current_configured_functions`) mit den in der Entity Registry registrierten Entitäten der Domain verglichen.
2. Alle Entitäten, die nicht mehr in `profile_functions` des Raumes enthalten sind oder deren Raum gelöscht wurde, werden explizit mit `registry.async_remove(entity_entry.entity_id)` entfernt.
3. Dieser Cleanup-Vorgang wird durch Unit-Tests in `tests/test_entity_registry.py` bzw. `tests/test_config_flow.py` abgesichert.

---
Verwandte Notizen:
* [`../architecture/adr-002-config-entry-vs-subentry.md`](../architecture/adr-002-config-entry-vs-subentry.md)
* [`../architecture/adr-003-state-hierarchy-configured-enabled-eligible.md`](../architecture/adr-003-state-hierarchy-configured-enabled-eligible.md)
