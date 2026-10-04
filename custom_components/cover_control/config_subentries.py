"""Canonical parent-entry and config-subentry representation.

The persisted model deliberately has one source of truth per layer: global data
lives on the parent entry, while rooms and profiles live on ConfigSubentries.
``ConfigProfileModel`` remains an in-memory compatibility model for resolver
and runtime code during the migration only; it is never persisted as a second
catalog on a parent entry.
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
    CONF_ROOM_ID,
    CONF_ROOM_OVERRIDES,
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
    CONF_SOURCE_OVERRIDES,
    PROFILE_TYPES,
    SUBENTRY_TYPE_PROFILE_BEHAVIOR,
    SUBENTRY_TYPE_PROFILE_SHADING,
    SUBENTRY_TYPE_PROFILE_TIME,
    SUBENTRY_TYPE_ROOM,
)

PROFILE_SUBENTRY_TYPES = {
    "time_profile": "time",
    "shading_profile": "shading",
    "behavior_profile": "behavior",
}


def profile_subentry_type(profile_type: str) -> str:
    """Return native subentry type for one supported profile type."""

    types = {
        "time": SUBENTRY_TYPE_PROFILE_TIME,
        "shading": SUBENTRY_TYPE_PROFILE_SHADING,
        "behavior": SUBENTRY_TYPE_PROFILE_BEHAVIOR,
    }
    try:
        return types[profile_type]
    except KeyError as err:
        raise ValueError(f"Unsupported profile type: {profile_type}") from err


def is_room_subentry(subentry: Any) -> bool:
    """Return whether a Home Assistant subentry represents one room."""

    return getattr(subentry, "subentry_type", None) == SUBENTRY_TYPE_ROOM


def is_profile_subentry(subentry: Any) -> bool:
    """Return whether a Home Assistant subentry represents one profile."""

    return getattr(subentry, "subentry_type", None) in PROFILE_SUBENTRY_TYPES


def model_from_subentries(
    parent_data: Mapping[str, Any], subentries: Iterable[Any]
) -> dict[str, Any]:
    """Build transient resolver model from parent data and native subentries."""

    global_data = parent_data.get(CONF_GLOBAL, {})
    model: dict[str, Any] = {
        CONF_GLOBAL: {
            CONF_GLOBAL_SOURCES: deepcopy(global_data.get(CONF_GLOBAL_SOURCES, {})),
            CONF_GLOBAL_DEFAULTS: deepcopy(global_data.get(CONF_GLOBAL_DEFAULTS, {})),
        },
        CONF_PROFILES: {profile_type: {} for profile_type in PROFILE_TYPES},
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
        profile_type = PROFILE_SUBENTRY_TYPES.get(
            getattr(subentry, "subentry_type", None)
        )
        if profile_type is None:
            continue
        model[CONF_PROFILES][profile_type][subentry_id] = {
            CONF_PROFILE_ID: subentry_id,
            CONF_PROFILE_NAME: str(getattr(subentry, "title", subentry_id)),
            CONF_PROFILE_CAPABILITIES: list(
                data.get(CONF_PROFILE_CAPABILITIES, ())
            ),
            CONF_PROFILE_SETTINGS: deepcopy(data.get(CONF_PROFILE_SETTINGS, {})),
        }
    return ConfigProfileModel(model).data


def legacy_model_to_subentry_data(
    model: Mapping[str, Any],
    subentry_id: Callable[[], str],
) -> tuple[dict[str, Any], list[tuple[str, str, str, dict[str, Any]]]]:
    """Convert legacy catalog model to parent data and native subentry payloads.

    Returned tuple items are ``(id, type, title, data)``. Callers create native
    ``ConfigSubentry`` objects, preserving profile references through generated
    subentry IDs rather than carrying legacy profile IDs forward as active data.
    """

    canonical = ConfigProfileModel(model).data
    parent_data = {
        CONF_GLOBAL: deepcopy(canonical[CONF_GLOBAL]),
    }
    profiles: list[tuple[str, str, str, dict[str, Any]]] = []
    profile_ids: dict[tuple[str, str], str] = {}
    for profile_type in PROFILE_TYPES:
        for legacy_id, profile in canonical[CONF_PROFILES][profile_type].items():
            new_id = subentry_id()
            profile_ids[(profile_type, legacy_id)] = new_id
            profiles.append(
                (
                    new_id,
                    profile_subentry_type(profile_type),
                    str(profile.get(CONF_PROFILE_NAME, legacy_id)),
                    {
                        CONF_PROFILE_CAPABILITIES: deepcopy(
                            profile.get(CONF_PROFILE_CAPABILITIES, [])
                        ),
                        CONF_PROFILE_SETTINGS: deepcopy(
                            profile.get(CONF_PROFILE_SETTINGS, {})
                        ),
                    },
                )
            )

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
    return parent_data, [*profiles, *rooms]


def model_to_native_payloads(
    model: Mapping[str, Any],
) -> tuple[dict[str, Any], list[tuple[str, str, str, dict[str, Any]]]]:
    """Serialize runtime model while preserving native subentry IDs."""

    canonical = ConfigProfileModel(model).data
    parent_data = {CONF_GLOBAL: deepcopy(canonical[CONF_GLOBAL])}
    payloads: list[tuple[str, str, str, dict[str, Any]]] = []
    for profile_type in PROFILE_TYPES:
        for profile_id, profile in canonical[CONF_PROFILES][profile_type].items():
            payloads.append(
                (
                    profile_id,
                    profile_subentry_type(profile_type),
                    str(profile.get(CONF_PROFILE_NAME, profile_id)),
                    {
                        CONF_PROFILE_CAPABILITIES: deepcopy(
                            profile.get(CONF_PROFILE_CAPABILITIES, [])
                        ),
                        CONF_PROFILE_SETTINGS: deepcopy(
                            profile.get(CONF_PROFILE_SETTINGS, {})
                        ),
                    },
                )
            )
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
