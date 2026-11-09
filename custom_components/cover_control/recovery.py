"""Validation and last-known-good recovery for controller configuration."""
from __future__ import annotations
from collections.abc import Mapping
from copy import deepcopy
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from .config_migration import migrate_profile_model
from .const import CONF_GROUP, CONF_GROUPS, CONF_ROOMS, DOMAIN, GROUPS

RECOVERY_STORAGE_VERSION = 2

class ConfigValidationError(ValueError):
    """Raised when structural configuration cannot be resolved safely."""


class RecoveryStore(Store[dict[str, Any]]):
    """Store with an explicit migration from the profile-era snapshot format."""

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, Any],
    ) -> dict[str, Any]:
        if old_major_version != 1:
            raise ConfigValidationError(
                f"unsupported recovery snapshot version: {old_major_version}"
            )
        if CONF_GROUPS in old_data and CONF_ROOMS in old_data:
            return deepcopy(old_data)
        migrated, _warnings = migrate_profile_model(old_data)
        return deepcopy(migrated)

class RecoveryManager:
    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: RecoveryStore = RecoveryStore(
            hass, RECOVERY_STORAGE_VERSION, f"{DOMAIN}.{entry_id}.last_known_good"
        )
        self.last_known_good: dict[str, Any] | None = None
        self.recovered = False

    async def async_initialize(self) -> None:
        try:
            stored = await self._store.async_load()
        except (ConfigValidationError, KeyError, TypeError, ValueError):
            stored = None
        if isinstance(stored, Mapping):
            candidate = deepcopy(dict(stored))
            try:
                self.validate(candidate)
            except ConfigValidationError:
                return
            self.last_known_good = candidate

    @staticmethod
    def validate(model: Mapping[str, Any]) -> None:
        groups, rooms = model.get(CONF_GROUPS), model.get(CONF_ROOMS)
        if not isinstance(groups, Mapping) or set(groups) != set(GROUPS):
            raise ConfigValidationError("fixed group catalog is incomplete")
        if not all(isinstance(groups[group], Mapping) for group in GROUPS):
            raise ConfigValidationError("invalid group settings")
        if not isinstance(rooms, Mapping):
            raise ConfigValidationError("missing rooms catalog")
        for room_id, room in rooms.items():
            if not isinstance(room, Mapping) or room.get(CONF_GROUP) not in GROUPS:
                raise ConfigValidationError(f"invalid room group: {room_id}")

    async def async_resolve(self, current: Mapping[str, Any]) -> dict[str, Any]:
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
        self.validate(model)
        snapshot = deepcopy(dict(model))
        await self._store.async_save(snapshot)
        self.last_known_good = snapshot
        self.recovered = False
