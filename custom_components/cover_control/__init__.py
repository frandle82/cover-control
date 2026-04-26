"""Set up the Cover Control integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS
from .controller import ControllerManager


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize integration-level storage."""

    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load a config entry."""

    registry = er.async_get(hass)
    for entity_entry in list(registry.entities.values()):
        if entity_entry.config_entry_id != entry.entry_id:
            continue
        if entity_entry.domain in {"number", "text", "time"}:
            registry.async_remove(entity_entry.entity_id)

    manager = ControllerManager(hass, entry)
    await manager.async_setup()
    hass.data[DOMAIN][entry.entry_id] = manager

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_handle_options_update))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    manager: ControllerManager | None = hass.data.get(DOMAIN, {}).pop(
        entry.entry_id, None
    )
    if manager:
        await manager.async_unload()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _handle_options_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply updated options by reloading entry platforms."""

    manager: ControllerManager | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if manager:
        manager.async_update_options()
    await hass.config_entries.async_reload(entry.entry_id)
