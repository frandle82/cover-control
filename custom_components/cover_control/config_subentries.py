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
from .const import (
    CONF_GLOBAL,
    CONF_GLOBAL_DEFAULTS,
    CONF_GLOBAL_SOURCES,
    CONF_NAME,
    CONF_PROFILE_CAPABILITIES,
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
        CONF_PROFILES: {
            profile_type: deepcopy(parent_profiles.get(profile_type, {}))
            for profile_type in PROFILE_TYPES
        },
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
            room.setdefault(CONF_PROFILE_SELECTIONS, {})
            room.setdefault(CONF_ROOM_SETTINGS, {})
            room.setdefault(CONF_SOURCE_OVERRIDES, {})
            room.setdefault(CONF_ROOM_OVERRIDES, {})
            model[CONF_ROOMS][subentry_id] = room
            continue
    _migrate_legacy_global_resident_source(model)
    return ConfigProfileModel(model).data


def legacy_model_to_subentry_data(
    model: Mapping[str, Any],
    subentry_id: Callable[[], str],
) -> tuple[dict[str, Any], list[tuple[str, str, str, dict[str, Any]]]]:
    """Convert legacy catalog model to parent data and room subentry payloads."""

    canonical = ConfigProfileModel(model).data
    _migrate_legacy_global_resident_source(canonical)
    parent_data = {
        CONF_GLOBAL: deepcopy(canonical[CONF_GLOBAL]),
        CONF_PROFILES: {profile_type: {} for profile_type in PROFILE_TYPES},
    }
    profile_ids: dict[tuple[str, str], str] = {}
    for profile_type in PROFILE_TYPES:
        for legacy_id, profile in canonical[CONF_PROFILES][profile_type].items():
            new_id = subentry_id()
            profile_ids[(profile_type, legacy_id)] = new_id
            parent_data[CONF_PROFILES][profile_type][new_id] = {
                CONF_PROFILE_ID: new_id,
                CONF_PROFILE_NAME: str(profile.get(CONF_PROFILE_NAME, legacy_id)),
                CONF_PROFILE_CAPABILITIES: deepcopy(
                    profile.get(CONF_PROFILE_CAPABILITIES, [])
                ),
                CONF_PROFILE_SETTINGS: deepcopy(
                    profile.get(CONF_PROFILE_SETTINGS, {})
                ),
            }

    rooms: list[tuple[str, str, str, dict[str, Any]]] = []
    for _legacy_id, room in canonical[CONF_ROOMS].items():
        room_id = subentry_id()
        room_data = deepcopy(room)
        selections = room_data.setdefault(CONF_PROFILE_SELECTIONS, {})
        for profile_type, legacy_profile_id in tuple(selections.items()):
            selections[profile_type] = profile_ids[(profile_type, legacy_profile_id)]
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

    canonical = ConfigProfileModel(model).data
    parent_data = {
        CONF_GLOBAL: deepcopy(canonical[CONF_GLOBAL]),
        CONF_PROFILES: deepcopy(canonical[CONF_PROFILES]),
    }
    payloads: list[tuple[str, str, str, dict[str, Any]]] = []
    for room_id, room in canonical[CONF_ROOMS].items():
        room_data = deepcopy(room)
        room_data.pop(CONF_ROOM_ID, None)
        payloads.append(
            (
                room_id,
                SUBENTRY_TYPE_ROOM,
                str(room_data.get(CONF_NAME, room_id)),
                room_data,
            )
        )
    return parent_data, payloads


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
