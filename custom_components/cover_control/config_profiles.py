"""Profile and room operations for hierarchical Cover Control configuration."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any
from uuid import uuid4

from .config_resolver import (
    effective_profile_id,
    effective_room_profile_functions,
    GLOBAL_SOURCE_KEYS,
    PROFILE_KEYS,
    ROOM_SOURCE_OVERRIDE_KEYS,
    resolve_config_model,
)
from .const import (
    CONF_GLOBAL,
    CONF_GLOBAL_DEFAULTS,
    CONF_GLOBAL_SOURCES,
    CONF_NAME,
    CONF_PROFILE_ID,
    CONF_PROFILE_CAPABILITIES,
    CONF_PROFILE_NAME,
    CONF_PROFILE_SELECTIONS,
    CONF_PROFILE_SETTINGS,
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
    """Apply validated profile changes without duplicating values into rooms."""

    def __init__(self, model: Mapping[str, Any]) -> None:
        self.data: dict[str, Any] = deepcopy(dict(model))
        self.data.setdefault(CONF_GLOBAL, {}).setdefault(CONF_GLOBAL_SOURCES, {})
        self.data[CONF_GLOBAL].setdefault(CONF_GLOBAL_DEFAULTS, {})
        profiles = self.data.setdefault(CONF_PROFILES, {})
        typed_catalogs = any(profile_type in profiles for profile_type in PROFILE_TYPES)
        for profile_type in PROFILE_TYPES if typed_catalogs else ():
            catalog = profiles.setdefault(profile_type, {})
            from .config_profile_schema import infer_capabilities

            for profile in catalog.values():
                profile.setdefault(
                    CONF_PROFILE_CAPABILITIES,
                    infer_capabilities(
                        profile_type, profile.get(CONF_PROFILE_SETTINGS, {})
                    ),
                )
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

    def create_profile(
        self,
        profile_type: str,
        name: str,
        settings: Mapping[str, Any],
        *,
        profile_id: str | None = None,
        capabilities: list[str] | tuple[str, ...] | None = None,
    ) -> str:
        """Create a profile with a stable opaque identifier."""

        self._validate_profile_type(profile_type)
        self._validate_settings(profile_type, settings)
        new_id = profile_id or f"{profile_type}-{uuid4().hex[:12]}"
        catalog = self.data[CONF_PROFILES][profile_type]
        if new_id in catalog:
            raise ProfileError(f"Profile already exists: {profile_type}:{new_id}")
        catalog[new_id] = {
            CONF_PROFILE_ID: new_id,
            CONF_PROFILE_NAME: name,
            CONF_PROFILE_SETTINGS: dict(settings),
            CONF_PROFILE_CAPABILITIES: list(capabilities or ()),
        }
        return new_id

    def update_profile(
        self,
        profile_type: str,
        profile_id: str,
        settings: Mapping[str, Any],
    ) -> set[str]:
        """Replace profile settings and return only affected rooms."""

        profile = self._profile(profile_type, profile_id)
        existing = profile.get(CONF_PROFILE_SETTINGS, {})
        unknown = set(settings) - PROFILE_KEYS[profile_type]
        new_unknown = unknown - set(existing)
        if new_unknown:
            raise ProfileError(
                f"Unknown settings cannot be added to {profile_type}: "
                + ", ".join(sorted(new_unknown))
            )
        profile[CONF_PROFILE_SETTINGS] = dict(settings)
        return set(self.profile_users.get((profile_type, profile_id), set()))

    def rename_profile(
        self, profile_type: str, profile_id: str, name: str
    ) -> set[str]:
        """Rename a profile without changing its ID or references."""

        self._profile(profile_type, profile_id)[CONF_PROFILE_NAME] = name
        return set(self.profile_users.get((profile_type, profile_id), set()))

    def set_capabilities(
        self, profile_type: str, profile_id: str, capabilities: list[str]
    ) -> set[str]:
        """Replace profile capabilities and discard disabled known values."""

        from .config_profile_schema import PROFILE_CAPABILITY_KEYS, capability_keys

        definitions = PROFILE_CAPABILITY_KEYS[profile_type]
        invalid = set(capabilities) - set(definitions)
        if invalid:
            raise ProfileError("Unsupported capabilities: " + ", ".join(sorted(invalid)))
        profile = self._profile(profile_type, profile_id)
        allowed = capability_keys(profile_type, capabilities)
        settings = profile.setdefault(CONF_PROFILE_SETTINGS, {})
        profile[CONF_PROFILE_SETTINGS] = {
            key: value
            for key, value in settings.items()
            if key in allowed or key not in PROFILE_KEYS[profile_type]
        }
        profile[CONF_PROFILE_CAPABILITIES] = list(capabilities)
        return set(self.profile_users.get((profile_type, profile_id), set()))

    def duplicate_profile(
        self, profile_type: str, profile_id: str, name: str
    ) -> str:
        """Copy profile settings into a new independently identified profile."""

        profile = self._profile(profile_type, profile_id)
        settings = profile.get(CONF_PROFILE_SETTINGS, {})
        known = {
            key: value
            for key, value in settings.items()
            if key in PROFILE_KEYS[profile_type]
        }
        profile_id_new = self.create_profile(profile_type, name, known)
        duplicate = self.data[CONF_PROFILES][profile_type][profile_id_new]
        duplicate[CONF_PROFILE_SETTINGS] = deepcopy(settings)
        duplicate[CONF_PROFILE_CAPABILITIES] = list(
            profile.get(CONF_PROFILE_CAPABILITIES, ())
        )
        return profile_id_new

    def delete_profile(self, profile_type: str, profile_id: str) -> None:
        """Delete an unused profile, blocking dangling room references."""

        profile = self._profile(profile_type, profile_id)
        users = self.profile_users.get((profile_type, profile_id), set())
        if users:
            raise ProfileInUseError(profile_type, profile_id, users)
        del self.data[CONF_PROFILES][profile_type][profile[CONF_PROFILE_ID]]

    def assign_profile(
        self, room_id: str, profile_type: str, profile_id: str
    ) -> None:
        """Store only a profile reference on the room."""

        self._profile(profile_type, profile_id)
        room = self._room(room_id)
        room.setdefault(CONF_PROFILE_SELECTIONS, {})[profile_type] = profile_id

    def unassign_profile(self, room_id: str, profile_type: str) -> None:
        """Remove a profile reference and overrides tied to that profile type."""

        room = self._room(room_id)
        room.setdefault(CONF_PROFILE_SELECTIONS, {}).pop(profile_type, None)
        room.setdefault(CONF_ROOM_OVERRIDES, {}).pop(profile_type, None)

    def set_override(
        self, room_id: str, profile_type: str, key: str, value: Any
    ) -> None:
        """Store an override only when it differs from the inherited value."""

        self._validate_settings(profile_type, {key: value})
        room = self._room(room_id)
        overrides = room.setdefault(CONF_ROOM_OVERRIDES, {}).setdefault(
            profile_type, {}
        )
        overrides.pop(key, None)
        inherited = resolve_config_model(self.data, room_id).get(key)
        if value != inherited:
            overrides[key] = value
        if not overrides:
            room[CONF_ROOM_OVERRIDES].pop(profile_type, None)

    def remove_override(self, room_id: str, profile_type: str, key: str) -> None:
        """Return a room value immediately to its inherited profile value."""

        room = self._room(room_id)
        overrides = room.setdefault(CONF_ROOM_OVERRIDES, {}).get(profile_type, {})
        overrides.pop(key, None)
        if not overrides:
            room[CONF_ROOM_OVERRIDES].pop(profile_type, None)

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
        selections = room.setdefault(CONF_PROFILE_SELECTIONS, {})
        room_settings = room.setdefault(CONF_ROOM_SETTINGS, {})
        for key, value in values.items():
            if key in GLOBAL_SOURCE_KEYS:
                self.data[CONF_GLOBAL][CONF_GLOBAL_SOURCES][key] = value
                continue
            if key in ROOM_SOURCE_OVERRIDE_KEYS:
                room.setdefault(CONF_SOURCE_OVERRIDES, {})[key] = value
                continue
            profile_type = next(
                (kind for kind, keys in PROFILE_KEYS.items() if key in keys),
                None,
            )
            if profile_type is None:
                room_settings[key] = value
                continue
            profile_id = selections.get(profile_type)
            if not profile_id:
                profile_id = self.create_profile(
                    profile_type,
                    f"{room.get(CONF_NAME, room_id)} (room profile)",
                    {},
                )
                selections[profile_type] = profile_id
            self._profile(profile_type, profile_id).setdefault(
                CONF_PROFILE_SETTINGS, {}
            )[key] = value
        if CONF_NAME in values:
            room[CONF_NAME] = str(values[CONF_NAME])

    def _room(self, room_id: str) -> dict[str, Any]:
        try:
            return self.data[CONF_ROOMS][room_id]
        except KeyError as err:
            raise ProfileError(f"Unknown room: {room_id}") from err

    def _profile(self, profile_type: str, profile_id: str) -> dict[str, Any]:
        self._validate_profile_type(profile_type)
        try:
            return self.data[CONF_PROFILES][profile_type][profile_id]
        except KeyError as err:
            raise ProfileError(
                f"Unknown profile: {profile_type}:{profile_id}"
            ) from err

    @staticmethod
    def _validate_profile_type(profile_type: str) -> None:
        if profile_type not in PROFILE_TYPES:
            raise ProfileError(f"Unsupported profile type: {profile_type}")

    @classmethod
    def _validate_settings(
        cls, profile_type: str, settings: Mapping[str, Any]
    ) -> None:
        cls._validate_profile_type(profile_type)
        invalid = set(settings) - PROFILE_KEYS[profile_type]
        if invalid:
            raise ProfileError(
                f"Settings do not belong to {profile_type}: "
                + ", ".join(sorted(invalid))
            )
