"""Configured, enabled, and eligible state for room functions."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from .config_resolver import TOGGLE_FUNCTION_KEYS
from .const import CONF_GROUP, CONF_GROUPS, CONF_ROOM_OVERRIDES, CONF_ROOM_SETTINGS, CONF_ROOMS, DEFAULT_GROUP

@dataclass(frozen=True, slots=True)
class FeatureState:
    configured: bool
    enabled: bool
    eligible: bool

def feature_configured(model: Mapping[str, Any], room_id: str, key: str) -> bool:
    """Return whether a runtime key belongs to the room's group model."""
    room = model.get(CONF_ROOMS, {}).get(room_id, {})
    if key in TOGGLE_FUNCTION_KEYS:
        return True
    if key in room.get(CONF_ROOM_SETTINGS, {}):
        return True
    if any(key in values for values in room.get(CONF_ROOM_OVERRIDES, {}).values()):
        return True
    return key in model.get(CONF_GROUPS, {}).get(room.get(CONF_GROUP, DEFAULT_GROUP), {})
