"""Profile and room operations for hierarchical Cover Control configuration."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any
from .config_resolver import (
    effective_profile_id,
    effective_room_profile_functions,
    GLOBAL_SOURCE_KEYS,
    ROOM_SOURCE_OVERRIDE_KEYS,
)
from .const import (
    CONF_GLOBAL,
    CONF_GLOBAL_DEFAULTS,
    CONF_GLOBAL_SOURCES,
    CONF_NAME,
    CONF_PROFILE_ID,
    CONF_PROFILE_NAME,
    CONF_PROFILE_SELECTIONS,
    CONF_PROFILES,
    CONF_ROOM_PROFILE_ID,
    CONF_ROOM_OVERRIDES,
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
    CONF_SOURCE_OVERRIDES,
    PROFILE_TYPES,
)


class ProfileError(ValueError):
    """Base error for invalid profile model changes."""


class ProfileInUseError(ProfileError):
    """Raised when a referenced profile cannot be deleted."""

    def __init__(self, profile_type: str, profile_id: str, rooms: set[str]) -> None:
        self.profile_type = profile_type
        self.profile_id = profile_id
        self.rooms = rooms
        super().__init__(
            f"Profile {profile_type}:{profile_id} is used by: "
            + ", ".join(sorted(rooms))
        )


class ConfigProfileModel:
    """Normalize the native v6 profile model without creating legacy UI shape."""

    def __init__(self, model: Mapping[str, Any]) -> None:
        self.data: dict[str, Any] = deepcopy(dict(model))
        self.data.setdefault(CONF_GLOBAL, {}).setdefault(CONF_GLOBAL_SOURCES, {})
        self.data[CONF_GLOBAL].setdefault(CONF_GLOBAL_DEFAULTS, {})
        profiles = self.data.setdefault(CONF_PROFILES, {})
        self.data.setdefault(CONF_ROOMS, {})
        for room in self.data[CONF_ROOMS].values():
            profile_id = effective_profile_id(room)
            if profile_id and not profile_id.startswith("legacy:"):
                room.setdefault("profile_id", profile_id)
                room.setdefault(
                    "profile_functions",
                    sorted(effective_room_profile_functions(self.data, room)),
                )

    @property
    def profile_users(self) -> dict[tuple[str, str], set[str]]:
        """Return the current reverse dependency index."""

        users: dict[tuple[str, str], set[str]] = {}
        for room_id, room in self.data[CONF_ROOMS].items():
            profile_id = room.get(CONF_ROOM_PROFILE_ID)
            if profile_id:
                users.setdefault(("profile", str(profile_id)), set()).add(room_id)
            for profile_type, profile_id in room.get(
                CONF_PROFILE_SELECTIONS, {}
            ).items():
                users.setdefault((profile_type, profile_id), set()).add(room_id)
        return users

    def set_global_source(self, key: str, value: Any) -> set[str]:
        """Update one shared source and return rooms without an override."""

        if key not in GLOBAL_SOURCE_KEYS:
            raise ProfileError(f"Unsupported global source: {key}")
        self.data[CONF_GLOBAL][CONF_GLOBAL_SOURCES][key] = value
        return {
            room_id
            for room_id, room in self.data[CONF_ROOMS].items()
            if key not in room.get(CONF_SOURCE_OVERRIDES, {})
        }

    def set_source_override(self, room_id: str, key: str, value: Any) -> None:
        """Set a room-local source override."""

        if key not in ROOM_SOURCE_OVERRIDE_KEYS:
            raise ProfileError(f"Unsupported room source override: {key}")
        self._room(room_id).setdefault(CONF_SOURCE_OVERRIDES, {})[key] = value

    def apply_flat_settings(self, room_id: str, values: Mapping[str, Any]) -> None:
        """Route existing options pages back into their canonical model layers."""

        room = self._room(room_id)
        room_settings = room.setdefault(CONF_ROOM_SETTINGS, {})
        for key, value in values.items():
            if key in GLOBAL_SOURCE_KEYS:
                self.data[CONF_GLOBAL][CONF_GLOBAL_SOURCES][key] = value
                continue
            if key in ROOM_SOURCE_OVERRIDE_KEYS:
                room.setdefault(CONF_SOURCE_OVERRIDES, {})[key] = value
                continue
            room_settings[key] = value
        if CONF_NAME in values:
            room[CONF_NAME] = str(values[CONF_NAME])

    def _room(self, room_id: str) -> dict[str, Any]:
        try:
            return self.data[CONF_ROOMS][room_id]
        except KeyError as err:
            raise ProfileError(f"Unknown room: {room_id}") from err
