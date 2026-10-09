"""Canonical parent-entry and config-subentry representation.

The persisted model deliberately has one source of truth per layer: global data
and reusable profiles live on the parent entry, while physical rooms live on
ConfigSubentries. ``ConfigProfileModel`` remains the validated in-memory shape
used by resolver and runtime code.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from typing import Any

from .config_profiles import ConfigProfileModel
from .config_migration import unify_profile_model
from .const import (
    CONF_CONTROLLER_ENTRY_ID,
    CONF_ENTRY_TYPE,
    CONF_GLOBAL,
    CONF_GLOBAL_DEFAULTS,
    CONF_GLOBAL_SOURCES,
    CONF_NAME,
    CONF_PROFILE_ID,
    CONF_PROFILE_NAME,
    CONF_PROFILE_SELECTIONS,
    CONF_PROFILE_SETTINGS,
    CONF_PROFILES,
    CONF_RESIDENT_SENSOR,
    CONF_ROOM_ID,
    CONF_ROOM_OVERRIDES,
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
    CONF_SOURCE_OVERRIDES,
    ENTRY_TYPE_CONTROLLER,
    ENTRY_TYPE_ROOM,
    PROFILE_TYPES,
    SUBENTRY_TYPE_ROOM,
)

PROFILE_SUBENTRY_TYPES = {
    "time_profile": "time",
    "shading_profile": "shading",
    "behavior_profile": "behavior",
}


def is_room_subentry(subentry: Any) -> bool:
    """Return whether a Home Assistant subentry represents one room."""

    return getattr(subentry, "subentry_type", None) == SUBENTRY_TYPE_ROOM


def is_profile_subentry(subentry: Any) -> bool:
    """Return whether a Home Assistant subentry represents one profile."""

    return getattr(subentry, "subentry_type", None) in PROFILE_SUBENTRY_TYPES


def model_from_subentries(
    parent_data: Mapping[str, Any], subentries: Iterable[Any]
) -> dict[str, Any]:
    """Build transient resolver model from parent data and room subentries."""

    global_data = parent_data.get(CONF_GLOBAL, {})
    parent_profiles = parent_data.get(CONF_PROFILES, {})
    model: dict[str, Any] = {
        CONF_GLOBAL: {
            CONF_GLOBAL_SOURCES: deepcopy(global_data.get(CONF_GLOBAL_SOURCES, {})),
            CONF_GLOBAL_DEFAULTS: deepcopy(global_data.get(CONF_GLOBAL_DEFAULTS, {})),
        },
        CONF_PROFILES: deepcopy(parent_profiles),
        CONF_ROOMS: {},
    }
    for subentry in subentries:
        data = getattr(subentry, "data", {})
        if not isinstance(data, Mapping):
            continue
        subentry_id = str(getattr(subentry, "subentry_id", ""))
        if is_room_subentry(subentry):
            room = deepcopy(dict(data))
            room[CONF_ROOM_ID] = subentry_id
            room.setdefault(CONF_NAME, getattr(subentry, "title", subentry_id))
            room.setdefault(CONF_ROOM_SETTINGS, {})
            room.setdefault(CONF_SOURCE_OVERRIDES, {})
            model[CONF_ROOMS][subentry_id] = room
            continue
    _migrate_legacy_global_resident_source(model)
    return ConfigProfileModel(unify_profile_model(model)).data


def legacy_model_to_subentry_data(
    model: Mapping[str, Any],
    subentry_id: Callable[[], str],
) -> tuple[dict[str, Any], list[tuple[str, str, str, dict[str, Any]]]]:
    """Convert legacy catalog model to parent data and room subentry payloads."""

    canonical = unify_profile_model(model)
    _migrate_legacy_global_resident_source(canonical)
    parent_data = {
        CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER,
        CONF_GLOBAL: deepcopy(canonical[CONF_GLOBAL]),
        CONF_PROFILES: {
            profile_id: deepcopy(profile)
            for profile_id, profile in canonical[CONF_PROFILES].items()
            if profile_id not in PROFILE_TYPES
        },
    }

    rooms: list[tuple[str, str, str, dict[str, Any]]] = []
    for _legacy_id, room in canonical[CONF_ROOMS].items():
        room_id = subentry_id()
        room_data = deepcopy(room)
        room_data.pop(CONF_ROOM_ID, None)
        rooms.append(
            (
                room_id,
                SUBENTRY_TYPE_ROOM,
                str(room_data.get(CONF_NAME, room_id)),
                room_data,
            )
        )
    return parent_data, rooms


def model_to_native_payloads(
    model: Mapping[str, Any],
) -> tuple[dict[str, Any], list[tuple[str, str, str, dict[str, Any]]]]:
    """Serialize runtime model while preserving native subentry IDs."""

    canonical = ConfigProfileModel(unify_profile_model(model)).data
    parent_data = {
        CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER,
        CONF_GLOBAL: deepcopy(canonical[CONF_GLOBAL]),
        CONF_PROFILES: {
            profile_id: deepcopy(profile)
            for profile_id, profile in canonical[CONF_PROFILES].items()
            if profile_id not in PROFILE_TYPES
        },
    }
    payloads: list[tuple[str, str, str, dict[str, Any]]] = []
    for room_id, room in canonical[CONF_ROOMS].items():
        room_data = deepcopy(room)
        room_data.pop(CONF_ROOM_ID, None)
        if not room_data.get(CONF_PROFILE_SELECTIONS):
            room_data.pop(CONF_PROFILE_SELECTIONS, None)
        if not room_data.get(CONF_ROOM_OVERRIDES):
            room_data.pop(CONF_ROOM_OVERRIDES, None)
        payloads.append(
            (
                room_id,
                SUBENTRY_TYPE_ROOM,
                str(room_data.get(CONF_NAME, room_id)),
                room_data,
            )
        )
    return parent_data, payloads


def model_from_entries(
    controller_entry_id: str,
    controller_data: Mapping[str, Any],
    room_entries: Iterable[Any],
) -> dict[str, Any]:
    """Build transient resolver model from a controller entry and room entries."""

    global_data = controller_data.get(CONF_GLOBAL, {})
    model: dict[str, Any] = {
        CONF_GLOBAL: {
            CONF_GLOBAL_SOURCES: deepcopy(global_data.get(CONF_GLOBAL_SOURCES, {})),
            CONF_GLOBAL_DEFAULTS: deepcopy(global_data.get(CONF_GLOBAL_DEFAULTS, {})),
        },
        CONF_PROFILES: deepcopy(controller_data.get(CONF_PROFILES, {})),
        CONF_ROOMS: {},
    }
    for entry in room_entries:
        data = getattr(entry, "data", {})
        if not isinstance(data, Mapping):
            continue
        if data.get(CONF_ENTRY_TYPE) != ENTRY_TYPE_ROOM:
            continue
        if controller_entry_id and data.get(CONF_CONTROLLER_ENTRY_ID) != controller_entry_id:
            continue
        room_id = str(data.get(CONF_ROOM_ID) or getattr(entry, "entry_id", ""))
        room = deepcopy(dict(data))
        room.pop(CONF_ENTRY_TYPE, None)
        room.pop(CONF_CONTROLLER_ENTRY_ID, None)
        room[CONF_ROOM_ID] = room_id
        room.setdefault(CONF_NAME, getattr(entry, "title", room_id))
        room.setdefault(CONF_ROOM_SETTINGS, {})
        room.setdefault(CONF_SOURCE_OVERRIDES, {})
        model[CONF_ROOMS][room_id] = room
    _migrate_legacy_global_resident_source(model)
    return ConfigProfileModel(unify_profile_model(model)).data


def room_entry_data_from_subentry(
    controller_entry_id: str, room_id: str, data: Mapping[str, Any], title: str
) -> dict[str, Any]:
    """Return canonical room ConfigEntry data for a legacy room subentry."""

    room = deepcopy(dict(data))
    room[CONF_ENTRY_TYPE] = ENTRY_TYPE_ROOM
    room[CONF_CONTROLLER_ENTRY_ID] = controller_entry_id
    room[CONF_ROOM_ID] = room_id
    room.setdefault(CONF_NAME, title or room_id)
    room.setdefault(CONF_ROOM_SETTINGS, {})
    room.setdefault(CONF_SOURCE_OVERRIDES, {})
    return room


def _migrate_legacy_global_resident_source(model: dict[str, Any]) -> None:
    """Move legacy global resident sensor values to rooms that lack one."""

    global_sources = model.get(CONF_GLOBAL, {}).get(CONF_GLOBAL_SOURCES, {})
    if not isinstance(global_sources, dict):
        return
    resident_sensor = global_sources.pop(CONF_RESIDENT_SENSOR, None)
    if resident_sensor in (None, ""):
        return
    for room in model.get(CONF_ROOMS, {}).values():
        if not isinstance(room, dict):
            continue
        settings = room.setdefault(CONF_ROOM_SETTINGS, {})
        if isinstance(settings, dict) and not settings.get(CONF_RESIDENT_SENSOR):
            settings[CONF_RESIDENT_SENSOR] = resident_sensor
