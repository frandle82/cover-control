"""Validation and last-known-good recovery for parent configuration."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    CONF_ROOM_PROFILE_ID,
    CONF_PROFILE_SELECTIONS,
    CONF_PROFILES,
    CONF_ROOMS,
    DOMAIN,
    PROFILE_TYPES,
)

RECOVERY_STORAGE_VERSION = 1


class ConfigValidationError(ValueError):
    """Raised when structural configuration cannot be resolved safely."""


class RecoveryManager:
    """Keep and restore validated parent configuration snapshots."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass,
            RECOVERY_STORAGE_VERSION,
            f"{DOMAIN}.{entry_id}.last_known_good",
        )
        self.last_known_good: dict[str, Any] | None = None
        self.recovered = False
    async def async_initialize(self) -> None:
        stored = await self._store.async_load()
        if isinstance(stored, Mapping):
            candidate = deepcopy(dict(stored))
            try:
                self.validate(candidate)
            except ConfigValidationError:
                return
            self.last_known_good = candidate

    @staticmethod
    def validate(model: Mapping[str, Any]) -> None:
        """Reject corrupt catalogs and dangling room profile references."""

        profiles = model.get(CONF_PROFILES)
        rooms = model.get(CONF_ROOMS)
        if not isinstance(profiles, Mapping) or not isinstance(rooms, Mapping):
            raise ConfigValidationError("missing profiles or rooms catalog")
        legacy_catalog = any(profile_type in profiles for profile_type in PROFILE_TYPES)
        if not legacy_catalog:
            for profile_id, profile in profiles.items():
                if not isinstance(profile, Mapping):
                    raise ConfigValidationError(f"invalid profile: {profile_id}")
            for room_id, room in rooms.items():
                if not isinstance(room, Mapping):
                    raise ConfigValidationError(f"invalid room: {room_id}")
                profile_id = room.get(CONF_ROOM_PROFILE_ID)
                if profile_id and profile_id not in profiles:
                    raise ConfigValidationError(
                        f"missing profile reference: {room_id}:profile:{profile_id}"
                    )
            return
        for profile_type in PROFILE_TYPES:
            if not isinstance(profiles.get(profile_type), Mapping):
                raise ConfigValidationError(f"invalid {profile_type} profile catalog")
        for room_id, room in rooms.items():
            if not isinstance(room, Mapping):
                raise ConfigValidationError(f"invalid room: {room_id}")
            selections = room.get(CONF_PROFILE_SELECTIONS, {})
            if not isinstance(selections, Mapping):
                raise ConfigValidationError(f"invalid profile references: {room_id}")
            for profile_type, profile_id in selections.items():
                if profile_type not in PROFILE_TYPES or profile_id not in profiles.get(
                    profile_type, {}
                ):
                    raise ConfigValidationError(
                        f"missing profile reference: {room_id}:{profile_type}:{profile_id}"
                    )

    async def async_resolve(self, current: Mapping[str, Any]) -> dict[str, Any]:
        """Return valid current model or validated last-known-good snapshot."""

        try:
            self.validate(current)
        except ConfigValidationError:
            if self.last_known_good is None:
                raise
            self.validate(self.last_known_good)
            self.recovered = True
            return deepcopy(self.last_known_good)
        return deepcopy(dict(current))

    async def async_mark_good(self, model: Mapping[str, Any]) -> None:
        """Persist model only after successful runtime setup."""

        self.validate(model)
        snapshot = deepcopy(dict(model))
        await self._store.async_save(snapshot)
        self.last_known_good = snapshot
        self.recovered = False
