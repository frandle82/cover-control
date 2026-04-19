"""Sensor platform for Cover Control.

This integration currently exposes switches only. The module exists so
`Platform.SENSOR` can be forwarded safely without setup failures.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Cover Control sensor entities."""
    registry = er.async_get(hass)
    for entity_entry in list(registry.entities.values()):
        if entity_entry.config_entry_id == entry.entry_id and entity_entry.domain == "sensor":
            registry.async_remove(entity_entry.entity_id)

    async_add_entities([])
