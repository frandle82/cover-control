"""Configured, enabled, and eligible state for room functions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .const import (
    CONF_PROFILE_FUNCTIONS,
    CONF_PROFILE_ID,
    CONF_PROFILE_SELECTIONS,
    CONF_PROFILE_SETTINGS,
    CONF_PROFILES,
    CONF_ROOM_OVERRIDES,
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
)
from .config_resolver import (
    TOGGLE_FUNCTION_KEYS,
    effective_profile,
    effective_room_profile_functions,
    profile_settings,
    room_selected_functions,
)


@dataclass(frozen=True, slots=True)
class FeatureState:
    configured: bool
    enabled: bool
    eligible: bool


def feature_configured(model: Mapping[str, Any], room_id: str, key: str) -> bool:
    """Return whether a runtime key is configured for a room.

    New-model automation toggles are configured only when the selected unified
    profile contains the function and the room selected that function. Legacy
    rooms without ``profile_functions`` keep the previous explicit-key fallback.
    """

    room = model.get(CONF_ROOMS, {}).get(room_id, {})
    function = TOGGLE_FUNCTION_KEYS.get(key)
    if function is not None and CONF_PROFILE_FUNCTIONS in room:
        return function in effective_room_profile_functions(model, room)

    if key in room.get(CONF_ROOM_SETTINGS, {}):
        return True
    for values in room.get(CONF_ROOM_OVERRIDES, {}).values():
        if key in values:
            return True
    if key in profile_settings(effective_profile(model, room)):
        return True
    for profile_type, profile_id in room.get(CONF_PROFILE_SELECTIONS, {}).items():
        profile = model.get(CONF_PROFILES, {}).get(profile_type, {}).get(profile_id, {})
        if key in profile.get(CONF_PROFILE_SETTINGS, {}):
            return True
    return False
