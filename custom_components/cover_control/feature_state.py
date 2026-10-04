"""Configured, enabled, and eligible state for room functions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .const import (
    CONF_PROFILE_SELECTIONS,
    CONF_PROFILE_SETTINGS,
    CONF_PROFILES,
    CONF_ROOM_OVERRIDES,
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
)


@dataclass(frozen=True, slots=True)
class FeatureState:
    configured: bool
    enabled: bool
    eligible: bool


def feature_configured(model: Mapping[str, Any], room_id: str, key: str) -> bool:
    """Return whether key is explicitly configured in any room layer."""

    room = model.get(CONF_ROOMS, {}).get(room_id, {})
    if key in room.get(CONF_ROOM_SETTINGS, {}):
        return True
    for values in room.get(CONF_ROOM_OVERRIDES, {}).values():
        if key in values:
            return True
    for profile_type, profile_id in room.get(CONF_PROFILE_SELECTIONS, {}).items():
        profile = model.get(CONF_PROFILES, {}).get(profile_type, {}).get(profile_id, {})
        if key in profile.get(CONF_PROFILE_SETTINGS, {}):
            return True
    return False
