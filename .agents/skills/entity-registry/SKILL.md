---
name: entity-registry
description: Entity-Registry-Lifecycle, Cleanup-Muster und Debugging bei Konfigurationsänderungen in cover-control. Verhindert verwaiste Entitäten und Registry-Inkonsistenzen nach Gruppen-/Raumänderungen.
---

# Entity Registry Skill – Cover Control

## Zweck

In cover-control werden Sensoren, Schalter und andere Entitäten dynamisch bei
der Setup-Zeit erstellt und an Config Entries gebunden. Bei Konfigurationsänderungen
(z. B. Gruppenfunktionen abwählen, Räume entfernen) entstehen leicht verwaiste
Entitäten in der HA Entity Registry.

Dieser Skill beschreibt, wie Entitäten korrekt registriert, bereinigt und
getestet werden.

---

## Grundregeln

### Entitäten niemals manuell erstellen
- Keine direkten `entity_registry.async_get_or_create()` ohne den zugehörigen
  Platform-Setup-Mechanismus.
- Entitäten immer über `async_add_entities()` via Platform-Setup registrieren.

### Unique IDs sind Pflicht
- Jede Entität braucht eine stabile, eindeutige `unique_id`.
- Schema für cover-control: `{config_entry_id}_{room_id}_{function}_{suffix}`
- Beispiel: `a1b2c3_living_room_shading_active`
- Bei Umbenennung von Räumen darf sich die `unique_id` **nicht** ändern.

### Config Entry Ownership
- Entitäten gehören immer exakt einem Config Entry.
- Beim Entladen (Unload) des Config Entry werden alle verknüpften Entitäten
  automatisch aus der Registry entfernt – sofern sie korrekt registriert sind.

---

## Cleanup: Verwaiste Entitäten entfernen

Wenn Gruppenfunktionen abgewählt werden oder Räume entfernt werden, müssen
die zugehörigen Entitäten aktiv bereinigt werden.

### Muster: Cleanup bei Options-Änderung

```python
from homeassistant.helpers import entity_registry as er

async def async_cleanup_removed_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    active_unique_ids: set[str],
) -> None:
    """Remove entities no longer active after config update."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    for entity_entry in entries:
        if entity_entry.unique_id not in active_unique_ids:
            registry.async_remove(entity_entry.entity_id)
```

### Wann aufrufen
- In `async_setup_entry` nach Ermittlung der aktiven Entitäten.
- In `async_reload_entry` (via Options Flow Reload) nach jeder Konfigurationsänderung.
- Nach dem Entfernen von Räumen oder Gruppenfunktionen.

---

## Diagnose: Registry-Zustand prüfen

```python
from homeassistant.helpers import entity_registry as er

def get_all_cc_entities(hass, entry_id):
    """Get all cover_control entities for a config entry."""
    registry = er.async_get(hass)
    return er.async_entries_for_config_entry(registry, entry_id)
```

### Typische Fehlerquellen

| Symptom | Ursache | Lösung |
|---|---|---|
| Entität nach Room-Entfernung weiter sichtbar | Cleanup nicht aufgerufen | `async_cleanup_removed_entities` nach Options-Reload |
| Doppelung nach Neustart | `unique_id` nicht stabil | `unique_id` aus stabilen IDs ableiten, nie aus Namen |
| Entity nicht gefunden nach Umbenennung | `unique_id` enthielt Display-Name | Nur interne IDs verwenden |
| Platform fehlt nach Reload | `async_unload_platforms` vergessen | Immer alle Platforms im Unload bereinigen |

---

## Tests: Was getestet werden muss

Jede Änderung an Entity-Registrierung oder Cleanup erfordert Tests für:

### 1. Entity-Erstellung
```python
async def test_entities_created_for_active_functions(hass, config_entry):
    """Verify entities exist for all configured group functions."""
    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    unique_ids = {e.unique_id for e in entries}
    assert f"{config_entry.entry_id}_room1_shading_active" in unique_ids
```

### 2. Cleanup nach Deaktivierung
```python
async def test_entity_removed_when_function_deselected(hass, config_entry):
    """Verify entity is removed from registry when a room function is removed."""
    # Deselect function via options update
    # ...
    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    unique_ids = {e.unique_id for e in entries}
    assert f"{config_entry.entry_id}_room1_shading_active" not in unique_ids
```

### 3. Stabilität der unique_id
```python
async def test_unique_id_stable_after_rename(hass, config_entry):
    """Verify unique_id does not change when room display name changes."""
    # Rename room, reload
    # Assert same unique_ids still exist
```

---

## Unload-Reihenfolge (kritisch)

```python
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload cover_control config entry."""
    # 1. Stop background tasks first
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_stop()

    # 2. Unload platforms (removes entities from HA)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # 3. Clean up domain data
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
```

**Reihenfolge nicht ändern.** Tasks vor Platforms stoppen, sonst Race Conditions
beim Entity-Unload.

---

## Debugging in Tests

```python
# Alle Entitäten eines Entry ausgeben
entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
for e in entries:
    print(f"{e.unique_id} -> {e.entity_id} [{e.domain}]")
```
