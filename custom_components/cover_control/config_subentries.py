"""Canonical controller and standalone-room ConfigEntry representation."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from typing import Any

from .config_groups import ConfigGroupModel
from .config_migration import migrate_legacy_model
from .const import (
    CONF_CONTROLLER_ENTRY_ID,
    CONF_ENTRY_TYPE,
    CONF_GLOBAL,
    CONF_GLOBAL_DEFAULTS,
    CONF_GLOBAL_SOURCES,
    CONF_GROUP,
    CONF_GROUPS,
    CONF_NAME,
    CONF_RESIDENT_SENSOR,
    CONF_ROOM_ID,
    CONF_ROOM_OVERRIDES,
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
    CONF_SOURCE_OVERRIDES,
    DEFAULT_GROUP,
    ENTRY_TYPE_CONTROLLER,
    ENTRY_TYPE_ROOM,
    SUBENTRY_TYPE_ROOM,
)


def is_room_subentry(subentry: Any) -> bool:
    """Return whether a legacy Home Assistant subentry represents a room."""

    return getattr(subentry, "subentry_type", None) == SUBENTRY_TYPE_ROOM


def model_from_subentries(
    parent_data: Mapping[str, Any], subentries: Iterable[Any]
) -> dict[str, Any]:
    """Build a group model while upgrading legacy room subentries."""

    model = _base_model(parent_data)
    for subentry in subentries:
        data = getattr(subentry, "data", {})
        if not isinstance(data, Mapping) or not is_room_subentry(subentry):
            continue
        room_id = str(getattr(subentry, "subentry_id", ""))
        room = deepcopy(dict(data))
        room[CONF_ROOM_ID] = room_id
        room.setdefault(CONF_NAME, getattr(subentry, "title", room_id))
        _normalize_room(room)
        model[CONF_ROOMS][room_id] = room
    _migrate_legacy_global_resident_source(model)
    return ConfigGroupModel(migrate_legacy_model(model)).data


def legacy_model_to_subentry_data(
    model: Mapping[str, Any], subentry_id: Callable[[], str]
) -> tuple[dict[str, Any], list[tuple[str, str, str, dict[str, Any]]]]:
    """Convert the embedded legacy model for the historical v7 migration."""

    canonical = ConfigGroupModel(migrate_legacy_model(model)).data
    parent_data = _controller_payload(canonical)
    rooms = []
    for room in canonical[CONF_ROOMS].values():
        room_id = subentry_id()
        room_data = deepcopy(room)
        room_data.pop(CONF_ROOM_ID, None)
        rooms.append((room_id, SUBENTRY_TYPE_ROOM, str(room_data.get(CONF_NAME, room_id)), room_data))
    return parent_data, rooms


def model_to_native_payloads(
    model: Mapping[str, Any],
) -> tuple[dict[str, Any], list[tuple[str, str, str, dict[str, Any]]]]:
    """Serialize a transient model into controller and room payloads."""

    canonical = ConfigGroupModel(migrate_legacy_model(model)).data
    payloads = []
    for room_id, room in canonical[CONF_ROOMS].items():
        room_data = deepcopy(room)
        room_data.pop(CONF_ROOM_ID, None)
        if not room_data.get(CONF_ROOM_OVERRIDES):
            room_data.pop(CONF_ROOM_OVERRIDES, None)
        payloads.append((room_id, SUBENTRY_TYPE_ROOM, str(room_data.get(CONF_NAME, room_id)), room_data))
    return _controller_payload(canonical), payloads


def model_from_entries(
    controller_entry_id: str,
    controller_data: Mapping[str, Any],
    room_entries: Iterable[Any],
) -> dict[str, Any]:
    """Build the runtime model from a controller and standalone room entries."""

    model = _base_model(controller_data)
    for entry in room_entries:
        data = getattr(entry, "data", {})
        if not isinstance(data, Mapping) or data.get(CONF_ENTRY_TYPE) != ENTRY_TYPE_ROOM:
            continue
        if controller_entry_id and data.get(CONF_CONTROLLER_ENTRY_ID) != controller_entry_id:
            continue
        room_id = str(data.get(CONF_ROOM_ID) or getattr(entry, "entry_id", ""))
        room = deepcopy(dict(data))
        room.pop(CONF_ENTRY_TYPE, None)
        room.pop(CONF_CONTROLLER_ENTRY_ID, None)
        room[CONF_ROOM_ID] = room_id
        room.setdefault(CONF_NAME, getattr(entry, "title", room_id))
        _normalize_room(room)
        model[CONF_ROOMS][room_id] = room
    _migrate_legacy_global_resident_source(model)
    return ConfigGroupModel(migrate_legacy_model(model)).data


def room_entry_data_from_subentry(
    controller_entry_id: str, room_id: str, data: Mapping[str, Any], title: str
) -> dict[str, Any]:
    """Return canonical standalone room data for a legacy subentry."""

    room = deepcopy(dict(data))
    room.update({CONF_ENTRY_TYPE: ENTRY_TYPE_ROOM, CONF_CONTROLLER_ENTRY_ID: controller_entry_id, CONF_ROOM_ID: room_id})
    room.setdefault(CONF_NAME, title or room_id)
    _normalize_room(room)
    return room


def _base_model(data: Mapping[str, Any]) -> dict[str, Any]:
    global_data = data.get(CONF_GLOBAL, {})
    return {
        CONF_GLOBAL: {
            CONF_GLOBAL_SOURCES: deepcopy(global_data.get(CONF_GLOBAL_SOURCES, {})),
            CONF_GLOBAL_DEFAULTS: deepcopy(global_data.get(CONF_GLOBAL_DEFAULTS, {})),
        },
        CONF_GROUPS: deepcopy(data.get(CONF_GROUPS, {})),
        CONF_ROOMS: {},
    }


def _controller_payload(model: Mapping[str, Any]) -> dict[str, Any]:
    return {
        CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER,
        CONF_GLOBAL: deepcopy(model[CONF_GLOBAL]),
        CONF_GROUPS: deepcopy(model[CONF_GROUPS]),
    }


def _normalize_room(room: dict[str, Any]) -> None:
    room.setdefault(CONF_GROUP, DEFAULT_GROUP)
    room.setdefault(CONF_ROOM_SETTINGS, {})
    room.setdefault(CONF_SOURCE_OVERRIDES, {})


def _migrate_legacy_global_resident_source(model: dict[str, Any]) -> None:
    global_sources = model.get(CONF_GLOBAL, {}).get(CONF_GLOBAL_SOURCES, {})
    if not isinstance(global_sources, dict):
        return
    resident_sensor = global_sources.pop(CONF_RESIDENT_SENSOR, None)
    if resident_sensor in (None, ""):
        return
    for room in model.get(CONF_ROOMS, {}).values():
        settings = room.setdefault(CONF_ROOM_SETTINGS, {})
        if isinstance(settings, dict) and not settings.get(CONF_RESIDENT_SENSOR):
            settings[CONF_RESIDENT_SENSOR] = resident_sensor
