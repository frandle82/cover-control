"""Fixed group and room operations for Cover Control configuration."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .config_resolver import GLOBAL_SOURCE_KEYS, ROOM_SOURCE_OVERRIDE_KEYS
from .const import (
    CONF_GLOBAL,
    CONF_GLOBAL_DEFAULTS,
    CONF_GLOBAL_SOURCES,
    CONF_GROUP,
    CONF_GROUPS,
    CONF_NAME,
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
    CONF_SOURCE_OVERRIDES,
    DEFAULT_GROUP,
    GROUPS,
)


class GroupError(ValueError):
    """Raised for invalid fixed-group model changes."""


class ConfigGroupModel:
    """Normalize the fixed-group configuration model."""

    def __init__(self, model: Mapping[str, Any]) -> None:
        self.data: dict[str, Any] = deepcopy(dict(model))
        self.data.setdefault(CONF_GLOBAL, {}).setdefault(CONF_GLOBAL_SOURCES, {})
        self.data[CONF_GLOBAL].setdefault(CONF_GLOBAL_DEFAULTS, {})
        groups = self.data.setdefault(CONF_GROUPS, {})
        for group in GROUPS:
            if not isinstance(groups.get(group), dict):
                groups[group] = {}
        for group in tuple(groups):
            if group not in GROUPS:
                groups.pop(group)
        rooms = self.data.setdefault(CONF_ROOMS, {})
        for room in rooms.values():
            if isinstance(room, dict) and room.get(CONF_GROUP) not in GROUPS:
                room[CONF_GROUP] = DEFAULT_GROUP

    @property
    def group_users(self) -> dict[str, set[str]]:
        """Return rooms assigned to each fixed group."""

        users = {group: set() for group in GROUPS}
        for room_id, room in self.data[CONF_ROOMS].items():
            users[str(room.get(CONF_GROUP, DEFAULT_GROUP))].add(room_id)
        return users

    def set_global_source(self, key: str, value: Any) -> set[str]:
        """Update one shared source and return rooms without an override."""

        if key not in GLOBAL_SOURCE_KEYS:
            raise GroupError(f"Unsupported global source: {key}")
        self.data[CONF_GLOBAL][CONF_GLOBAL_SOURCES][key] = value
        return {
            room_id
            for room_id, room in self.data[CONF_ROOMS].items()
            if key not in room.get(CONF_SOURCE_OVERRIDES, {})
        }

    def set_source_override(self, room_id: str, key: str, value: Any) -> None:
        """Set a room-local source override."""

        if key not in ROOM_SOURCE_OVERRIDE_KEYS:
            raise GroupError(f"Unsupported room source override: {key}")
        self._room(room_id).setdefault(CONF_SOURCE_OVERRIDES, {})[key] = value

    def apply_flat_settings(self, room_id: str, values: Mapping[str, Any]) -> None:
        """Route existing room pages into their canonical model layers."""

        room = self._room(room_id)
        room_settings = room.setdefault(CONF_ROOM_SETTINGS, {})
        for key, value in values.items():
            if key in GLOBAL_SOURCE_KEYS:
                self.data[CONF_GLOBAL][CONF_GLOBAL_SOURCES][key] = value
            elif key in ROOM_SOURCE_OVERRIDE_KEYS:
                room.setdefault(CONF_SOURCE_OVERRIDES, {})[key] = value
            else:
                room_settings[key] = value
        if CONF_NAME in values:
            room[CONF_NAME] = str(values[CONF_NAME])

    def _room(self, room_id: str) -> dict[str, Any]:
        try:
            return self.data[CONF_ROOMS][room_id]
        except KeyError as err:
            raise GroupError(f"Unknown room: {room_id}") from err
