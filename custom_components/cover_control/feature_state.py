"""Configured, enabled, and eligible state for room functions."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from .config_resolver import configured_functions_for_layers, TOGGLE_FUNCTION_KEYS
from .const import CONF_GROUP, CONF_GROUPS, CONF_ROOM_OVERRIDES, CONF_ROOM_SETTINGS, CONF_ROOMS, DEFAULT_GROUP

@dataclass(frozen=True, slots=True)
class FeatureState:
    configured: bool
    enabled: bool
    eligible: bool

def feature_configured(model: Mapping[str, Any], room_id: str, key: str) -> bool:
    """Return whether a runtime key belongs to the room's group model."""
    room = model.get(CONF_ROOMS, {}).get(room_id, {})
    group = model.get(CONF_GROUPS, {}).get(room.get(CONF_GROUP, DEFAULT_GROUP), {})
    room_settings = room.get(CONF_ROOM_SETTINGS, {})
    room_overrides = room.get(CONF_ROOM_OVERRIDES, {})
    function = TOGGLE_FUNCTION_KEYS.get(key)
    if function is not None:
        return function in configured_functions_for_layers(
            group, room_settings, room_overrides
        )
    return key in group or key in room_settings or any(
        isinstance(values, Mapping) and key in values
        for values in room_overrides.values()
    )
