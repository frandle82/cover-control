"""Configured, enabled, and eligible state for room functions."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from .config_resolver import GROUP_SECTION_KEYS, TOGGLE_FUNCTION_KEYS
from .const import CONF_GROUP, CONF_GROUPS, CONF_RESIDENT_SENSOR, CONF_ROOM_OVERRIDES, CONF_ROOM_SETTINGS, CONF_ROOMS, DEFAULT_GROUP

@dataclass(frozen=True, slots=True)
class FeatureState:
    configured: bool
    enabled: bool
    eligible: bool

def feature_configured(model: Mapping[str, Any], room_id: str, key: str) -> bool:
    """Return whether a runtime key belongs to the room's group model."""
    room = model.get(CONF_ROOMS, {}).get(room_id, {})
    group = model.get(CONF_GROUPS, {}).get(room.get(CONF_GROUP, DEFAULT_GROUP), {})
    layers = [group, room.get(CONF_ROOM_SETTINGS, {})]
    layers.extend(room.get(CONF_ROOM_OVERRIDES, {}).values())
    configured_keys = {key for layer in layers if isinstance(layer, Mapping) for key in layer}
    function = TOGGLE_FUNCTION_KEYS.get(key)
    if function == "resident" and CONF_RESIDENT_SENSOR in room.get(CONF_ROOM_SETTINGS, {}):
        return True
    if function is not None:
        return bool(configured_keys & GROUP_SECTION_KEYS[function])
    return key in configured_keys
