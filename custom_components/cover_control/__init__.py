"""Set up the Cover Control integration."""

from __future__ import annotations

from copy import deepcopy
from types import MappingProxyType
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntryError, ConfigEntryNotReady, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .config_profiles import ConfigProfileModel
from .const import (
    CONF_GLOBAL,
    CONF_CONTROLLER_ENTRY_ID,
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_PROFILE_CAPABILITIES,
    CONF_PROFILE_ID,
    CONF_PROFILE_NAME,
    CONF_PROFILE_SETTINGS,
    CONF_PROFILES,
    CONF_ROOM_ID,
    CONF_ROOMS,
    DOMAIN,
    ENTRY_TYPE_CONTROLLER,
    ENTRY_TYPE_ROOM,
    PLATFORMS,
    PROFILE_TYPES,
)
from .config_migration import (
    is_native_parent_entry,
    migrate_entry_collection,
    unify_profile_model,
)
from .config_subentries import (
    legacy_model_to_subentry_data,
    model_from_entries,
    model_from_subentries,
    room_entry_data_from_subentry,
)
from .hub import CoverControlHub
from .runtime_data import CoverControlRuntime
from .recovery import ConfigValidationError, RecoveryManager

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


def _is_controller_entry(entry: ConfigEntry) -> bool:
    """Return whether entry is the central controller entry."""

    entry_type = entry.data.get(CONF_ENTRY_TYPE)
    return entry_type == ENTRY_TYPE_CONTROLLER or (
        entry_type is None and is_native_parent_entry(entry.data)
    )


def _is_room_entry(entry: ConfigEntry) -> bool:
    """Return whether entry is a room ConfigEntry."""

    return entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_ROOM


def _controller_entry(
    hass: HomeAssistant, controller_entry_id: str | None
) -> ConfigEntry | None:
    """Return the referenced controller entry when it exists."""

    if not controller_entry_id:
        return None
    return next(
        (
            candidate
            for candidate in hass.config_entries.async_entries(DOMAIN)
            if candidate.entry_id == controller_entry_id
            and _is_controller_entry(candidate)
        ),
        None,
    )


def _room_entries_for_controller(
    hass: HomeAssistant, controller_entry_id: str
) -> list[ConfigEntry]:
    """Return all room entries belonging to one controller entry."""

    return [
        candidate
        for candidate in hass.config_entries.async_entries(DOMAIN)
        if candidate.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_ROOM
        and candidate.data.get(CONF_CONTROLLER_ENTRY_ID) == controller_entry_id
    ]


def _room_entry_for_controller_room(
    hass: HomeAssistant, controller_entry_id: str, room_id: str
) -> ConfigEntry | None:
    """Return one existing room entry by controller and stable room id."""

    return next(
        (
            candidate
            for candidate in _room_entries_for_controller(hass, controller_entry_id)
            if candidate.data.get(CONF_ROOM_ID) == room_id
        ),
        None,
    )


def _controller_model_from_entries(
    hass: HomeAssistant, controller_entry: ConfigEntry
) -> dict:
    """Build the v7 transient model from one controller and its room entries."""

    if controller_entry.version < 7 and controller_entry.subentries:
        return model_from_subentries(
            controller_entry.data, controller_entry.subentries.values()
        )
    return model_from_entries(
        controller_entry.entry_id,
        controller_entry.data,
        _room_entries_for_controller(hass, controller_entry.entry_id),
    )


def _single_room_model(controller_model: dict, room_entry: ConfigEntry) -> dict:
    """Return the controller model narrowed to one room entry."""

    room_id = str(room_entry.data.get(CONF_ROOM_ID) or room_entry.entry_id)
    room = deepcopy(dict(room_entry.data))
    room.pop(CONF_ENTRY_TYPE, None)
    room.pop(CONF_CONTROLLER_ENTRY_ID, None)
    room[CONF_ROOM_ID] = room_id
    return {
        CONF_GLOBAL: deepcopy(controller_model.get(CONF_GLOBAL, {})),
        CONF_PROFILES: deepcopy(controller_model.get(CONF_PROFILES, {})),
        CONF_ROOMS: {room_id: room},
    }


async def _setup_room_manager(
    controller_manager,
    hass: HomeAssistant,
    entry: ConfigEntry,
    hub: CoverControlHub,
    runtime: CoverControlRuntime,
    room_entry: ConfigEntry,
) -> None:
    """Create one runtime manager for a room entry."""

    room_id = str(room_entry.data.get(CONF_ROOM_ID) or room_entry.entry_id)
    manager = controller_manager(hass, entry, hub, room_id=room_id)
    runtime.room_managers[room_id] = manager
    await manager.async_setup()
    await hub.async_register_room(manager)


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

    if _is_controller_entry(entry):
        model = _controller_model_from_entries(hass, entry)
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
        hass.data.setdefault(DOMAIN, {}).setdefault("controllers", {})[
            entry.entry_id
        ] = entry
        for room_entry in _room_entries_for_controller(hass, entry.entry_id):
            await _setup_room_manager(controller_manager, hass, entry, hub, runtime, room_entry)
        await recovery.async_mark_good(model)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(_handle_options_update))
        return True

    if _is_room_entry(entry):
        controller_entry_id = entry.data.get(CONF_CONTROLLER_ENTRY_ID)
        controller_entry = _controller_entry(hass, controller_entry_id)
        if controller_entry is None or not getattr(controller_entry, "runtime_data", None):
            raise ConfigEntryNotReady("Cover Control controller entry is not ready")
        controller_runtime = controller_entry.runtime_data
        hub = controller_runtime.hub
        runtime = CoverControlRuntime(
            hub=hub,
            model=_single_room_model(controller_runtime.model, entry),
            recovery_manager=None,
        )
        entry.runtime_data = runtime
        await _setup_room_manager(controller_manager, hass, entry, hub, runtime, entry)
        controller_runtime.model = _controller_model_from_entries(hass, controller_entry)
        hub.apply_model(controller_runtime.model, {str(entry.data.get(CONF_ROOM_ID))})
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(_handle_options_update))
        return True

    raise ConfigEntryError("Cover Control parent entry migration is incomplete")


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate legacy room entries to one parent with native subentries."""

    if entry.version >= 7:
        return True
    if entry.version == 6:
        return await _async_migrate_subentries_to_room_entries(hass, entry)
    if entry.version == 5:
        if not await _async_migrate_parent_to_unified_profiles(hass, entry):
            return False
        return await _async_migrate_subentries_to_room_entries(hass, entry)
    if entry.version == 4:
        if not await _async_migrate_parent_profiles_to_data(hass, entry):
            return False
        if not await _async_migrate_parent_to_unified_profiles(hass, entry):
            return False
        return await _async_migrate_subentries_to_room_entries(hass, entry)
    from homeassistant.util.ulid import ulid_now

    entries = hass.config_entries.async_entries(DOMAIN)
    native_parent = next(
        (
            candidate
            for candidate in entries
            if is_native_parent_entry(candidate.data)
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
        migrated_entries = {
            parent.entry_id: (parent.data, parent.options),
            **{
                legacy_entry.entry_id: (legacy_entry.data, legacy_entry.options)
                for legacy_entry in legacy_parents
            },
        }
        merged = migrate_entry_collection(migrated_entries)
        legacy_parents = []
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
            version=7,
        )
        return True

    for legacy_entry in legacy_parents:
        merged = migrate_entry_collection(
            {
                "parent": ({CONF_GLOBAL: merged.get(CONF_GLOBAL, {}), CONF_PROFILES: merged.get(CONF_PROFILES, {}), CONF_ROOMS: merged.get(CONF_ROOMS, {})}, {}),
                legacy_entry.entry_id: (legacy_entry.data, legacy_entry.options),
            }
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
            version=7,
        )
    if not await _async_migrate_parent_profiles_to_data(hass, parent):
        return False
    if not await _async_migrate_parent_to_unified_profiles(hass, parent):
        return False
    return await _async_migrate_subentries_to_room_entries(hass, parent)


async def _async_migrate_subentries_to_room_entries(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Move v6 room subentries to standalone v7 room ConfigEntries."""

    if not _is_controller_entry(entry):
        hass.config_entries.async_update_entry(entry, version=7)
        return True

    parent_data = deepcopy(dict(entry.data))
    parent_data[CONF_ENTRY_TYPE] = ENTRY_TYPE_CONTROLLER
    room_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if getattr(subentry, "subentry_type", None) == "room"
    ]
    for subentry in room_subentries:
        room_id = str(subentry.subentry_id)
        room_entry = _room_entry_for_controller_room(hass, entry.entry_id, room_id)
        if room_entry is None:
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "import"},
                data=room_entry_data_from_subentry(
                    entry.entry_id, room_id, subentry.data, subentry.title
                ),
            )
            room_entry = _room_entry_for_controller_room(hass, entry.entry_id, room_id)
            if result.get("type") == "abort" and room_entry is None:
                return False
        if room_entry is None:
            return False
        _migrate_room_registries(hass, entry.entry_id, room_entry.entry_id, room_id)
        if room_id in entry.subentries:
            hass.config_entries.async_remove_subentry(entry, room_id)

    hass.config_entries.async_update_entry(
        entry,
        data=parent_data,
        options={},
        title=entry.title or DEFAULT_NAME,
        unique_id=entry.unique_id or DOMAIN,
        version=7,
    )
    return True


def _migrate_room_registries(
    hass: HomeAssistant,
    controller_entry_id: str,
    room_entry_id: str,
    room_id: str,
) -> None:
    """Move room devices and entities from controller subentry to room entry."""

    device_registry = dr.async_get(hass)
    migrated_device_ids: set[str] = set()
    for device in dr.async_entries_for_config_entry(
        device_registry, controller_entry_id
    ):
        if (
            device.config_entry_id == controller_entry_id
            and device.config_subentry_id == room_id
        ):
            device_registry.async_update_device(
                device.id,
                new_config_entry_id=room_entry_id,
                new_config_subentry_id=None,
            )
            migrated_device_ids.add(device.id)
            continue
        if (
            controller_entry_id in device.config_entries
            and room_id in device.config_entries_subentries.get(controller_entry_id, set())
        ):
            device_registry.async_update_device(
                device.id,
                add_config_entry_id=room_entry_id,
                remove_config_subentry_id=room_id,
            )
            migrated_device_ids.add(device.id)

    entity_registry = er.async_get(hass)
    for entity_entry in list(entity_registry.entities.values()):
        if (
            entity_entry.config_entry_id == controller_entry_id
            and (
                entity_entry.config_subentry_id == room_id
                or entity_entry.device_id in migrated_device_ids
                or str(entity_entry.unique_id or "").startswith(f"{room_id}-")
            )
        ):
            kwargs = {
                "config_entry_id": room_entry_id,
                "config_subentry_id": None,
            }
            if entity_entry.device_id in migrated_device_ids:
                kwargs["device_id"] = entity_entry.device_id
            entity_registry.async_update_entity(entity_entry.entity_id, **kwargs)


async def _async_migrate_parent_to_unified_profiles(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Persist the v6 unified profile catalog and single room profile references."""

    if not is_native_parent_entry(entry.data):
        hass.config_entries.async_update_entry(entry, version=6)
        return True

    model = unify_profile_model(
        model_from_subentries(entry.data, entry.subentries.values())
    )
    parent_data = deepcopy(dict(entry.data))
    parent_data[CONF_PROFILES] = deepcopy(model.get(CONF_PROFILES, {}))
    for subentry in entry.subentries.values():
        if subentry.subentry_type != "room":
            continue
        room = model.get(CONF_ROOMS, {}).get(subentry.subentry_id)
        if not isinstance(room, dict):
            continue
        room_data = deepcopy(room)
        room_data.pop("room_id", None)
        hass.config_entries.async_update_subentry(
            entry,
            subentry,
            data=room_data,
            title=str(room_data.get(CONF_NAME, subentry.title)),
        )
    hass.config_entries.async_update_entry(
        entry,
        data={**parent_data, CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER},
        options={},
        title=entry.title or "Cover Control",
        unique_id=entry.unique_id or DOMAIN,
        version=6,
    )
    return True


async def _async_migrate_parent_profiles_to_data(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Move legacy profile subentries into the parent profile catalog."""

    from .config_subentries import PROFILE_SUBENTRY_TYPES, is_profile_subentry

    if not is_native_parent_entry(entry.data):
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
