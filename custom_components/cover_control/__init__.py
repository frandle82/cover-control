"""Set up the Cover Control integration."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntryError, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import CONF_CONFIG_MODEL, CONF_GLOBAL, CONF_ROOMS, DOMAIN, PLATFORMS
from .config_migration import migrate_entry_payload
from .config_subentries import legacy_model_to_subentry_data, model_from_subentries
from .hub import CoverControlHub
from .runtime_data import CoverControlRuntime
from .recovery import ConfigValidationError, RecoveryManager

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

    if entry.data.get("hub_entry_id") and CONF_GLOBAL not in entry.data:
        hass.async_create_task(
            hass.config_entries.async_remove(entry.entry_id),
            "remove migrated Cover Control room entry",
        )
        return True

    controller_manager = await hass.async_add_import_executor_job(
        _load_controller_manager
    )

    registry = er.async_get(hass)
    for entity_entry in list(registry.entities.values()):
        if entity_entry.config_entry_id != entry.entry_id:
            continue
        if entity_entry.domain in {"number", "text", "time"}:
            registry.async_remove(entity_entry.entity_id)

    if CONF_GLOBAL in entry.data and CONF_CONFIG_MODEL not in entry.data:
        model = model_from_subentries(entry.data, entry.subentries.values())
        recovery = RecoveryManager(hass, entry.entry_id)
        await recovery.async_initialize()
        try:
            model = await recovery.async_resolve(model)
        except ConfigValidationError as err:
            ir.async_create_issue(
                hass,
                DOMAIN,
                "invalid_parent_config",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="invalid_parent_config",
                translation_placeholders={"error": str(err)},
            )
            raise
        if recovery.recovered:
            ir.async_create_issue(
                hass,
                DOMAIN,
                "automatic_recovery",
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key="automatic_recovery",
            )
        else:
            ir.async_delete_issue(hass, DOMAIN, "invalid_parent_config")
            ir.async_delete_issue(hass, DOMAIN, "automatic_recovery")
        hub = CoverControlHub(hass)
        hub.set_parent_model(model)
        runtime = CoverControlRuntime(
            hub=hub, model=model, recovery_manager=recovery
        )
        entry.runtime_data = runtime
        hass.data[DOMAIN][entry.entry_id] = runtime
        for room_id in model.get(CONF_ROOMS, {}):
            manager = controller_manager(hass, entry, hub, room_id=room_id)
            runtime.room_managers[room_id] = manager
            await manager.async_setup()
            await hub.async_register_room(manager)
        await recovery.async_mark_good(model)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(_handle_options_update))
        return True

    raise ConfigEntryError("Cover Control parent entry migration is incomplete")


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate legacy room entries to one parent with native subentries."""

    if entry.version >= 4:
        return True
    if CONF_GLOBAL in entry.data and CONF_CONFIG_MODEL not in entry.data:
        hass.config_entries.async_update_entry(entry, version=4)
        return True
    data, _options = (
        migrate_entry_payload(entry.data, entry.options, entry_id=entry.entry_id)
        if CONF_CONFIG_MODEL not in entry.data
        else (dict(entry.data), dict(entry.options))
    )
    from homeassistant.util.ulid import ulid_now

    native_parent = next(
        (
            candidate
            for candidate in hass.config_entries.async_entries(DOMAIN)
            if candidate.entry_id != entry.entry_id
            and CONF_GLOBAL in candidate.data
            and CONF_CONFIG_MODEL not in candidate.data
            and not candidate.data.get("hub_entry_id")
        ),
        None,
    )
    if native_parent is not None:
        from .hub import merge_config_models

        parent_model = model_from_subentries(
            native_parent.data, native_parent.subentries.values()
        )
        merged = merge_config_models(
            parent_model, data[CONF_CONFIG_MODEL], namespace=entry.entry_id
        )
        parent_data, payloads = legacy_model_to_subentry_data(merged, ulid_now)
        parent_data["name"] = "Cover Control"
        for subentry_id in tuple(native_parent.subentries):
            hass.config_entries.async_remove_subentry(native_parent, subentry_id)
        _add_subentries(hass, native_parent, payloads)
        hass.config_entries.async_update_entry(
            native_parent, data=parent_data, options={}, version=4
        )
        hass.config_entries.async_update_entry(
            entry,
            data={"hub_entry_id": native_parent.entry_id},
            options={},
            version=4,
        )
        return True

    parent_data, payloads = legacy_model_to_subentry_data(
        data[CONF_CONFIG_MODEL], ulid_now
    )
    parent_data["name"] = "Cover Control"
    _add_subentries(hass, entry, payloads)
    hass.config_entries.async_update_entry(
        entry,
        data=parent_data,
        options={},
        title="Cover Control",
        unique_id=DOMAIN,
        version=4,
    )
    return True


def _add_subentries(hass, entry, payloads) -> None:
    """Add generated native subentries to one parent entry."""

    for subentry_id, subentry_type, title, subentry_data in payloads:
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType(subentry_data),
                subentry_id=subentry_id,
                subentry_type=subentry_type,
                title=title,
                unique_id=subentry_id,
            ),
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    manager = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if isinstance(manager, CoverControlRuntime):
        for room_manager in manager.room_managers.values():
            await room_manager.async_unload()
        await manager.hub.async_unload_parent()
        return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return True


async def _handle_options_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply updated options through one clean entry reload."""

    manager = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if isinstance(manager, CoverControlRuntime):
        await hass.config_entries.async_reload(entry.entry_id)
        return
    await hass.config_entries.async_reload(entry.entry_id)
