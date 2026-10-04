"""Set up the Cover Control integration."""

from __future__ import annotations

from copy import deepcopy
from types import MappingProxyType
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntryError, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .config_profiles import ConfigProfileModel
from .const import (
    CONF_CONFIG_MODEL,
    CONF_GLOBAL,
    CONF_NAME,
    CONF_PROFILE_CAPABILITIES,
    CONF_PROFILE_ID,
    CONF_PROFILE_NAME,
    CONF_PROFILE_SETTINGS,
    CONF_PROFILES,
    CONF_ROOMS,
    DOMAIN,
    PLATFORMS,
    PROFILE_TYPES,
)
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

    if entry.version >= 5:
        return True
    if entry.version == 4:
        return await _async_migrate_parent_profiles_to_data(hass, entry)
    from homeassistant.util.ulid import ulid_now
    from .hub import merge_config_models

    entries = hass.config_entries.async_entries(DOMAIN)
    native_parent = next(
        (
            candidate
            for candidate in entries
            if CONF_GLOBAL in candidate.data
            and CONF_CONFIG_MODEL not in candidate.data
            and not candidate.data.get("hub_entry_id")
        ),
        None,
    )
    legacy_parents = [
        candidate
        for candidate in entries
        if candidate is not native_parent
        and candidate.version < 4
        and not candidate.data.get("hub_entry_id")
    ]

    if native_parent is not None and not legacy_parents:
        return await _async_migrate_parent_profiles_to_data(hass, native_parent)

    if native_parent is not None:
        parent = native_parent
        merged = model_from_subentries(
            native_parent.data, native_parent.subentries.values()
        )
    elif legacy_parents:
        parent = legacy_parents.pop(0)
        merged = _legacy_entry_model(parent)
    else:
        parent = next(
            (
                candidate
                for candidate in entries
                if candidate.entry_id == entry.data.get("hub_entry_id")
            ),
            None,
        )
        if parent is None:
            raise ConfigEntryError("Cover Control parent entry migration is incomplete")
        hass.config_entries.async_update_entry(
            entry,
            data={"hub_entry_id": parent.entry_id},
            options={},
            version=5,
        )
        return True

    for legacy_entry in legacy_parents:
        merged = merge_config_models(
            merged,
            _legacy_entry_model(legacy_entry),
            namespace=legacy_entry.entry_id,
        )

    parent_data, payloads = legacy_model_to_subentry_data(merged, ulid_now)
    parent_data["name"] = "Cover Control"
    for subentry_id in tuple(parent.subentries):
        hass.config_entries.async_remove_subentry(parent, subentry_id)
    _add_subentries(hass, parent, payloads)
    hass.config_entries.async_update_entry(
        parent,
        data=parent_data,
        options={},
        title="Cover Control",
        unique_id=DOMAIN,
        version=4,
    )
    for legacy_entry in entries:
        if legacy_entry.entry_id == parent.entry_id:
            continue
        if legacy_entry.version >= 4 and not legacy_entry.data.get("hub_entry_id"):
            continue
        hass.config_entries.async_update_entry(
            legacy_entry,
            data={"hub_entry_id": parent.entry_id},
            options={},
            version=5,
        )
    return await _async_migrate_parent_profiles_to_data(hass, parent)


async def _async_migrate_parent_profiles_to_data(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Move legacy profile subentries into the parent profile catalog."""

    from .config_subentries import PROFILE_SUBENTRY_TYPES, is_profile_subentry

    if CONF_GLOBAL not in entry.data or CONF_CONFIG_MODEL in entry.data:
        hass.config_entries.async_update_entry(entry, version=5)
        return True

    parent_data = deepcopy(dict(entry.data))
    profiles = parent_data.setdefault(
        CONF_PROFILES, {profile_type: {} for profile_type in PROFILE_TYPES}
    )
    for profile_type in PROFILE_TYPES:
        profiles.setdefault(profile_type, {})

    legacy_profile_ids: list[str] = []
    for subentry in entry.subentries.values():
        if not is_profile_subentry(subentry):
            continue
        profile_type = PROFILE_SUBENTRY_TYPES[subentry.subentry_type]
        profile_id = subentry.subentry_id
        migrated = {
            CONF_PROFILE_ID: profile_id,
            CONF_PROFILE_NAME: subentry.title,
            CONF_PROFILE_CAPABILITIES: deepcopy(
                subentry.data.get(CONF_PROFILE_CAPABILITIES, [])
            ),
            CONF_PROFILE_SETTINGS: deepcopy(
                subentry.data.get(CONF_PROFILE_SETTINGS, {})
            ),
        }
        existing = profiles[profile_type].get(profile_id)
        if existing is not None and existing != migrated:
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"profile_migration_conflict_{profile_id}",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="profile_migration_conflict",
                translation_placeholders={
                    "profile": str(existing.get(CONF_PROFILE_NAME, profile_id))
                },
            )
            return False
        profiles[profile_type][profile_id] = migrated
        legacy_profile_ids.append(profile_id)

    candidate = model_from_subentries(parent_data, entry.subentries.values())
    ConfigProfileModel(candidate)
    hass.config_entries.async_update_entry(
        entry,
        data=parent_data,
        options={},
        title=entry.title or "Cover Control",
        unique_id=entry.unique_id or DOMAIN,
        version=5,
    )
    for subentry_id in legacy_profile_ids:
        hass.config_entries.async_remove_subentry(entry, subentry_id)
    return True


def _legacy_entry_model(entry: ConfigEntry) -> dict:
    """Normalize one legacy parent or standalone room entry."""

    if CONF_CONFIG_MODEL in entry.data:
        return dict(entry.data[CONF_CONFIG_MODEL])
    data, _options = migrate_entry_payload(
        entry.data, entry.options, entry_id=entry.entry_id
    )
    return data[CONF_CONFIG_MODEL]


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

    runtime = getattr(entry, "runtime_data", None)
    if isinstance(runtime, CoverControlRuntime):
        for room_manager in runtime.room_managers.values():
            await room_manager.async_unload()
        await runtime.hub.async_unload_parent()
        return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return True


async def _handle_options_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply updated options through one clean entry reload."""

    runtime = getattr(entry, "runtime_data", None)
    if isinstance(runtime, CoverControlRuntime):
        await hass.config_entries.async_reload(entry.entry_id)
        return
    await hass.config_entries.async_reload(entry.entry_id)
