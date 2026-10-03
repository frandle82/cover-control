"""Set up the Cover Control integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import CONF_CONFIG_MODEL, DOMAIN, PLATFORMS
from .config_migration import migrate_entry_payload
from .config_resolver import config_entry_room_id, entry_config_model
from .hub import CoverControlHub

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


def _load_controller_manager():
    """Import the runtime outside Home Assistant's event loop."""

    from .controller import ControllerManager

    return ControllerManager


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize integration-level storage."""

    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load a config entry."""

    controller_manager = await hass.async_add_import_executor_job(
        _load_controller_manager
    )

    registry = er.async_get(hass)
    for entity_entry in list(registry.entities.values()):
        if entity_entry.config_entry_id != entry.entry_id:
            continue
        if entity_entry.domain in {"number", "text", "time"}:
            registry.async_remove(entity_entry.entity_id)

    hub = hass.data[DOMAIN].get("hub")
    if not isinstance(hub, CoverControlHub):
        hub = CoverControlHub(hass)
        hass.data[DOMAIN]["hub"] = hub
    hub.prepare_entry(entry)
    manager = controller_manager(hass, entry, hub)
    await manager.async_setup()
    hass.data[DOMAIN][entry.entry_id] = manager
    await hub.async_register(entry, manager)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_handle_options_update))
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate flat version-1 entries to the hierarchical version-2 model."""

    if entry.version >= 3:
        return True
    data, options = migrate_entry_payload(
        entry.data, entry.options, entry_id=entry.entry_id
    )
    hass.config_entries.async_update_entry(
        entry, data=data, options=options, version=3
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    manager = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if manager:
        await manager.async_unload()
    hub = hass.data.get(DOMAIN, {}).get("hub")
    if isinstance(hub, CoverControlHub):
        await hub.async_unregister(entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _handle_options_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply updated options through one clean entry reload."""

    manager = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    hub = hass.data.get(DOMAIN, {}).get("hub")
    if (
        manager is not None
        and isinstance(hub, CoverControlHub)
        and CONF_CONFIG_MODEL in entry.data
    ):
        room_id = config_entry_room_id(entry.data, entry.entry_id)
        model = entry_config_model(entry.data, entry.options, room_id=room_id)
        hub.apply_model(model, set(model.get("rooms", {})))
    await hass.config_entries.async_reload(entry.entry_id)
