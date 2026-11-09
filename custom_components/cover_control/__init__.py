"""Set up the Cover Control integration."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

from homeassistant.config_entries import (
    ConfigEntryError,
    ConfigEntryNotReady,
    ConfigEntryState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CONTROLLER_ENTRY_ID,
    CONF_ENTRY_TYPE,
    CONF_GLOBAL,
    CONF_GROUP,
    CONF_GROUPS,
    CONF_NAME,
    CONF_ROOM_ID,
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
    DOMAIN,
    ENTRY_TYPE_CONTROLLER,
    ENTRY_TYPE_ROOM,
    GROUPS,
    PLATFORMS,
)
from .config_migration import (
    classify_legacy_profile,
    cleanup_cca_settings,
    is_native_parent_entry,
    migrate_profile_model,
)
from .config_subentries import (
    model_from_entries,
    model_from_subentries,
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
    """Build the transient model from one controller and its room entries."""

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
        CONF_GROUPS: deepcopy(controller_model.get(CONF_GROUPS, {})),
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


async def _async_load_room_entry(hass: HomeAssistant, room_entry: ConfigEntry) -> None:
    """Ask Home Assistant to load a dependent room entry."""

    if room_entry.state is ConfigEntryState.NOT_LOADED:
        await hass.config_entries.async_setup(room_entry.entry_id)
        return
    if room_entry.state is ConfigEntryState.SETUP_RETRY:
        await hass.config_entries.async_reload(room_entry.entry_id)


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
        await recovery.async_mark_good(model)
        for room_entry in _room_entries_for_controller(hass, entry.entry_id):
            if room_entry.state in {
                ConfigEntryState.NOT_LOADED,
                ConfigEntryState.SETUP_RETRY,
            }:
                hass.async_create_task(
                    _async_load_room_entry(hass, room_entry),
                    "load Cover Control room entry",
                )
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
    """Migrate controller-owned profiles and standalone rooms to fixed groups."""

    if entry.version >= 16:
        return True
    if _is_room_entry(entry):
        controller = _controller_entry(hass, entry.data.get(CONF_CONTROLLER_ENTRY_ID))
        data = deepcopy(dict(entry.data))
        if data.get(CONF_GROUP) not in GROUPS:
            profiles = controller.data.get("profiles", {}) if controller else {}
            profile = profiles.get(data.get("profile_id"), {}) if isinstance(profiles, dict) else {}
            data[CONF_GROUP] = classify_legacy_profile(
                str(profile.get("name", data.get("profile_id", ""))),
                (str(data.get(CONF_NAME, entry.title)),),
            )
        if controller is not None and CONF_GROUPS in controller.data:
            data.pop("profile_id", None)
            data.pop("profile_functions", None)
            data.pop("profiles", None)
        settings, cca_changed = cleanup_cca_settings(data.get(CONF_ROOM_SETTINGS, {}))
        data[CONF_ROOM_SETTINGS] = settings
        hass.config_entries.async_update_entry(entry, data=data, options={}, version=16)
        if cca_changed:
            ir.async_create_issue(
                hass,
                DOMAIN,
                "cca_cleanup_migration",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="cca_cleanup_migration",
            )
        return True
    if not _is_controller_entry(entry):
        return False

    rooms = _room_entries_for_controller(hass, entry.entry_id)
    legacy_model = {
        CONF_GLOBAL: deepcopy(entry.data.get(CONF_GLOBAL, {})),
        CONF_ROOMS: {
            str(room.data.get(CONF_ROOM_ID) or room.entry_id): deepcopy(dict(room.data))
            for room in rooms
        },
    }
    if CONF_GROUPS in entry.data:
        legacy_model[CONF_GROUPS] = deepcopy(entry.data[CONF_GROUPS])
    else:
        legacy_model["profiles"] = deepcopy(entry.data.get("profiles", {}))
    migrated, warnings = migrate_profile_model(legacy_model)
    controller_data = deepcopy(dict(entry.data))
    controller_data.pop("profiles", None)
    controller_data[CONF_GROUPS] = deepcopy(migrated[CONF_GROUPS])
    controller_data[CONF_ENTRY_TYPE] = ENTRY_TYPE_CONTROLLER
    hass.config_entries.async_update_entry(
        entry, data=controller_data, options={}, version=16
    )
    for room in rooms:
        room_id = str(room.data.get(CONF_ROOM_ID) or room.entry_id)
        migrated_room = migrated[CONF_ROOMS][room_id]
        room_data = deepcopy(dict(room.data))
        room_data[CONF_GROUP] = migrated_room[CONF_GROUP]
        room_data[CONF_ROOM_SETTINGS] = deepcopy(
            migrated_room.get(CONF_ROOM_SETTINGS, room_data.get(CONF_ROOM_SETTINGS, {}))
        )
        room_data.pop("profile_id", None)
        room_data.pop("profile_functions", None)
        room_data.pop("profiles", None)
        hass.config_entries.async_update_entry(
            room, data=room_data, options={}, version=16
        )
    sun_warnings = [warning for warning in warnings if "dynamic sun" in warning]
    shading_warnings = [warning for warning in warnings if "shading rules" in warning]
    cca_warnings = [warning for warning in warnings if "CCA behavior" in warning]
    profile_warnings = [
        warning
        for warning in warnings
        if warning not in sun_warnings
        and warning not in shading_warnings
        and warning not in cca_warnings
    ]
    if profile_warnings:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "fixed_group_migration_conflict",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="fixed_group_migration_conflict",
            translation_placeholders={"details": "; ".join(profile_warnings)},
        )
    if sun_warnings:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "sun_mode_migration",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="sun_mode_migration",
            translation_placeholders={"details": "; ".join(sun_warnings)},
        )
    if shading_warnings:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "shading_mode_migration",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="shading_mode_migration",
            translation_placeholders={"details": "; ".join(shading_warnings)},
        )
    if cca_warnings:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "cca_cleanup_migration",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="cca_cleanup_migration",
        )
    for subentry_id in tuple(entry.subentries):
        hass.config_entries.async_remove_subentry(entry, subentry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    runtime = getattr(entry, "runtime_data", None)
    if isinstance(runtime, CoverControlRuntime):
        if _is_room_entry(entry):
            room_id = str(entry.data.get(CONF_ROOM_ID) or entry.entry_id)
            room_manager = runtime.room_managers.pop(room_id, None)
            if room_manager is not None:
                await room_manager.async_unload()
            await runtime.hub.async_unregister_room(room_id)
            if not runtime.hub.managers:
                await runtime.hub.async_unload_parent()
            return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        for room_manager in list(runtime.hub.managers.values()):
            await room_manager.async_unload()
        await runtime.hub.async_unload_parent()
        return True
    return True


async def _handle_options_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply updated options through one clean entry reload."""

    runtime = getattr(entry, "runtime_data", None)
    if isinstance(runtime, CoverControlRuntime):
        await hass.config_entries.async_reload(entry.entry_id)
        return
    await hass.config_entries.async_reload(entry.entry_id)
