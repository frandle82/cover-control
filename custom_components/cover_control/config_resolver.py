"""Resolve controller groups and room-owned configuration for one room."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from .const import *  # noqa: F403


GLOBAL_SOURCE_KEYS = frozenset(
    {
        CONF_WORKDAY_SENSOR,
        CONF_WORKDAY_TOMORROW_SENSOR,
        CONF_CALENDAR_ENTITY,
        CONF_BRIGHTNESS_SENSOR,
        CONF_SHADING_BRIGHTNESS_SENSOR,
        CONF_TEMPERATURE_SENSOR_OUTDOOR,
        CONF_COLD_PROTECTION_FORECAST_SENSOR,
        CONF_FIRE_ALARM_ENTITY,
        CONF_RAIN_ALARM_ENTITY,
        CONF_WIND_ALARM_2_ENTITY,
        CONF_WIND_ALARM_1_ENTITY,
        CONF_FROST_ALARM_ENTITY,
    }
)

ROOM_SOURCE_OVERRIDE_KEYS = frozenset(
    {
        CONF_BRIGHTNESS_SENSOR,
        CONF_SHADING_BRIGHTNESS_SENSOR,
        CONF_TEMPERATURE_SENSOR_OUTDOOR,
        CONF_COLD_PROTECTION_FORECAST_SENSOR,
    }
)

GLOBAL_DEFAULT_KEYS = frozenset()

ROOM_HARDWARE_KEYS = frozenset(
    {
        CONF_COVERS,
        CONF_COVER_TYPE,
        CONF_DRIVE_TIME,
        CONF_POSITION_TOLERANCE,
        CONF_TILT_POSITION_TOLERANCE,
        CONF_COVER_TILT_WAIT_MODE,
        CONF_COVER_TILT_WAIT_TIMEOUT,
    }
)

ROOM_POSITION_KEYS = frozenset(
    {
        CONF_OPEN_POSITION,
        CONF_CLOSE_POSITION,
        CONF_INTERMEDIATE_CLOSE_POSITION,
        CONF_CHRISTMAS_POSITION,
        CONF_SUMMER_SKIP_CLOSE_ENABLED,
        CONF_CHRISTMAS_POSITION_ENABLED,
        CONF_SHADING_POSITION,
        CONF_SHADING_POSITION_ALT,
        CONF_SHADING_POSITION_ALT_ENTITY,
        CONF_VENTILATE_POSITION,
        CONF_LOCKOUT_POSITION,
        CONF_OPEN_TILT_POSITION,
        CONF_CLOSE_TILT_POSITION,
        CONF_SHADING_TILT_POSITION,
        CONF_VENTILATE_TILT_POSITION,
        CONF_SHADING_TILT_POSITION_0,
        CONF_SHADING_TILT_POSITION_1,
        CONF_SHADING_TILT_POSITION_2,
        CONF_SHADING_TILT_POSITION_3,
    }
)

ROOM_SENSOR_KEYS = frozenset(
    {
        CONF_TEMPERATURE_SENSOR_INDOOR,
        CONF_RESIDENT_SENSOR,
        CONF_WINDOW_SENSORS,
        CONF_WINDOW_SENSOR_FULL,
        CONF_WINDOW_SENSOR_TILT,
    }
)

ROOM_GEOMETRY_KEYS = frozenset()

ROOM_CONTROL_KEYS = frozenset(
    {
        CONF_ENABLE_RECALIBRATE_BUTTON,
        CONF_ENABLE_CLEAR_MANUAL_OVERRIDE_BUTTON,
        CONF_ENABLE_LOGBOOK_COVER,
    }
)

ROOM_SAFETY_KEYS = frozenset(DEFAULT_SAFETY_PARTICIPATION)

TIME_GROUP_KEYS = frozenset(
    {
        CONF_AUTO_UP,
        CONF_AUTO_DOWN,
        CONF_AUTO_TIME,
        CONF_AUTO_BRIGHTNESS,
        CONF_AUTO_SUN,
        CONF_USE_WORKDAY_SENSOR,
        CONF_USE_BRIGHTNESS_SENSOR,
        CONF_OPEN_MODE,
        CONF_CLOSE_MODE,
        CONF_TIME_UP_EARLY_WORKDAY,
        CONF_TIME_UP_LATE_WORKDAY,
        CONF_TIME_UP_EARLY_NON_WORKDAY,
        CONF_TIME_UP_LATE_NON_WORKDAY,
        CONF_TIME_DOWN_EARLY_WORKDAY,
        CONF_TIME_DOWN_LATE_WORKDAY,
        CONF_TIME_DOWN_EARLY_NON_WORKDAY,
        CONF_TIME_DOWN_LATE_NON_WORKDAY,
        CONF_INTERMEDIATE_CLOSE_ENABLED,
        CONF_FINAL_CLOSE_TIME,
        CONF_SUMMER_START,
        CONF_SUMMER_END,
        CONF_CHRISTMAS_START,
        CONF_CHRISTMAS_END,
        CONF_CALENDAR_OPEN_TITLE,
        CONF_CALENDAR_CLOSE_TITLE,
        CONF_BRIGHTNESS_OPEN_ABOVE,
        CONF_BRIGHTNESS_CLOSE_BELOW,
        CONF_BRIGHTNESS_HYSTERESIS,
        CONF_BRIGHTNESS_TIME_DURATION,
        CONF_ASTRO_OPEN_OFFSET,
        CONF_ASTRO_CLOSE_OFFSET,
        CONF_SUN_ELEVATION_OPEN,
        CONF_SUN_ELEVATION_CLOSE,
    }
)

BRIGHTNESS_GROUP_KEYS = frozenset(
    {
        CONF_AUTO_BRIGHTNESS,
        CONF_USE_BRIGHTNESS_SENSOR,
        CONF_BRIGHTNESS_OPEN_ABOVE,
        CONF_BRIGHTNESS_CLOSE_BELOW,
        CONF_BRIGHTNESS_HYSTERESIS,
        CONF_BRIGHTNESS_TIME_DURATION,
    }
)

SUN_GROUP_KEYS = frozenset(
    {
        CONF_AUTO_SUN,
        CONF_OPEN_MODE,
        CONF_CLOSE_MODE,
        CONF_ASTRO_OPEN_OFFSET,
        CONF_ASTRO_CLOSE_OFFSET,
        CONF_SUN_ELEVATION_OPEN,
        CONF_SUN_ELEVATION_CLOSE,
    }
)

SHADING_GROUP_KEYS = frozenset(
    {
        CONF_AUTO_SHADING,
        CONF_KEEP_SUN_PROTECTION,
        CONF_SHADING_MODE,
        CONF_SHADING_DIRECTION,
        CONF_SHADING_DIRECTION_RANGE,
        CONF_SUN_ELEVATION_MIN,
        CONF_SUN_ELEVATION_MAX,
        CONF_SHADING_BRIGHTNESS_THRESHOLD,
        CONF_SHADING_BRIGHTNESS_HYSTERESIS,
        CONF_SHADING_INSIDE_TEMPERATURE_THRESHOLD,
        CONF_SHADING_INSIDE_TEMPERATURE_HYSTERESIS,
        CONF_SHADING_OUTSIDE_TEMPERATURE_THRESHOLD,
        CONF_SHADING_OUTSIDE_TEMPERATURE_HYSTERESIS,
        CONF_HEAT_PROTECTION_ENABLED,
        CONF_HEAT_PROTECTION_THRESHOLD,
        CONF_SHADING_WAITINGTIME_END,
        CONF_USE_COLD_PROTECTION_FORECAST_SENSOR,
        CONF_COLD_PROTECTION_THRESHOLD,
        CONF_TEMPERATURE_THRESHOLD,
        CONF_TEMPERATURE_FORECAST_THRESHOLD,
        CONF_SHADING_TILT_ELEVATION_1,
        CONF_SHADING_TILT_ELEVATION_2,
        CONF_SHADING_TILT_ELEVATION_3,
    }
)

BEHAVIOR_GROUP_KEYS = frozenset(
    {
        *DEFAULT_BEHAVIOR_SETTINGS,
        *DEFAULT_SAFETY_SETTINGS,
        *DEFAULT_MANUAL_OVERRIDE_FLAGS,
        *DEFAULT_CONTACT_SETTINGS,
        CONF_MANUAL_OVERRIDE_MINUTES,
        CONF_MANUAL_OVERRIDE_RESET_MODE,
        CONF_MANUAL_OVERRIDE_RESET_TIME,
        CONF_NO_GO_TIME_MINUTES,
        CONF_AUTO_VENTILATE,
        CONF_RESIDENT_STATUS,
        CONF_RESIDENT_OPEN_ENABLED,
        CONF_RESIDENT_CLOSE_ENABLED,
        CONF_RESIDENT_ALLOW_SHADING,
        CONF_RESIDENT_ALLOW_OPEN,
        CONF_RESIDENT_ALLOW_VENTILATION,
    }
) - ROOM_HARDWARE_KEYS - ROOM_POSITION_KEYS - ROOM_SENSOR_KEYS - ROOM_GEOMETRY_KEYS
BEHAVIOR_GROUP_KEYS = BEHAVIOR_GROUP_KEYS - ROOM_CONTROL_KEYS

VENTILATION_GROUP_KEYS = frozenset({CONF_AUTO_VENTILATE, *DEFAULT_CONTACT_SETTINGS})

RESIDENT_GROUP_KEYS = frozenset(
    {
        CONF_RESIDENT_STATUS,
        CONF_RESIDENT_OPEN_ENABLED,
        CONF_RESIDENT_CLOSE_ENABLED,
        CONF_RESIDENT_ALLOW_SHADING,
        CONF_RESIDENT_ALLOW_OPEN,
        CONF_RESIDENT_ALLOW_VENTILATION,
    }
)

SAFETY_GROUP_KEYS = frozenset(DEFAULT_SAFETY_SETTINGS)

GROUP_SECTION_KEYS = {
    FUNCTION_TIME: TIME_GROUP_KEYS - BRIGHTNESS_GROUP_KEYS - SUN_GROUP_KEYS,
    FUNCTION_BRIGHTNESS: BRIGHTNESS_GROUP_KEYS,
    FUNCTION_SUN: SUN_GROUP_KEYS,
    FUNCTION_SHADING: SHADING_GROUP_KEYS,
    FUNCTION_VENTILATION: VENTILATION_GROUP_KEYS,
    FUNCTION_RESIDENT: RESIDENT_GROUP_KEYS,
    FUNCTION_BEHAVIOR: BEHAVIOR_GROUP_KEYS
    - VENTILATION_GROUP_KEYS
    - RESIDENT_GROUP_KEYS
    - ROOM_HARDWARE_KEYS
    - ROOM_POSITION_KEYS
    - ROOM_SENSOR_KEYS
    - ROOM_GEOMETRY_KEYS
    - ROOM_CONTROL_KEYS
    - SAFETY_GROUP_KEYS,
    FUNCTION_SAFETY: SAFETY_GROUP_KEYS,
}

FUNCTION_TOGGLE_KEYS = {
    FUNCTION_TIME: CONF_AUTO_TIME,
    FUNCTION_BRIGHTNESS: CONF_AUTO_BRIGHTNESS,
    FUNCTION_SUN: CONF_AUTO_SUN,
    FUNCTION_SHADING: CONF_AUTO_SHADING,
    FUNCTION_VENTILATION: CONF_AUTO_VENTILATE,
    FUNCTION_RESIDENT: CONF_RESIDENT_STATUS,
}

TOGGLE_FUNCTION_KEYS = {
    toggle_key: function
    for function, toggle_key in FUNCTION_TOGGLE_KEYS.items()
}


GROUP_BLOCKED_KEYS = (
    ROOM_HARDWARE_KEYS
    | ROOM_POSITION_KEYS
    | ROOM_SENSOR_KEYS
    | ROOM_GEOMETRY_KEYS
    | ROOM_CONTROL_KEYS
    | ROOM_SAFETY_KEYS
)


@dataclass(frozen=True, slots=True)
class ResolvedRoomConfig(Mapping[str, Any]):
    """Complete runtime configuration and non-persistent origin metadata."""

    room_id: str
    room_name: str
    values: Mapping[str, Any]
    sources: Mapping[str, str] = field(default_factory=dict)
    group: str = DEFAULT_GROUP
    configured_functions: frozenset[str] = frozenset()

    def __getitem__(self, key: str) -> Any:
        return self.values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)


def system_defaults() -> dict[str, Any]:
    """Return the single runtime default layer used by every room."""

    return {
        **DEFAULT_POSITION_SETTINGS,
        **DEFAULT_TIME_SETTINGS,
        **DEFAULT_AUTOMATION_FLAGS,
        **DEFAULT_MASTER_FLAGS,
        **DEFAULT_MANUAL_OVERRIDE_FLAGS,
        **DEFAULT_CONTACT_SETTINGS,
        **DEFAULT_BEHAVIOR_SETTINGS,
        **DEFAULT_BUTTON_SETTINGS,
        **DEFAULT_SAFETY_SETTINGS,
        **DEFAULT_SAFETY_PARTICIPATION,
        **DEFAULT_SHADING_TIMING_SETTINGS,
        **{
            key: list(value) if isinstance(value, list) else value
            for key, value in DEFAULT_SHADING_SETTINGS.items()
        },
        CONF_OPEN_MODE: DEFAULT_OPEN_MODE,
        CONF_CLOSE_MODE: DEFAULT_CLOSE_MODE,
        CONF_ASTRO_OPEN_OFFSET: DEFAULT_ASTRO_OPEN_OFFSET,
        CONF_ASTRO_CLOSE_OFFSET: DEFAULT_ASTRO_CLOSE_OFFSET,
        CONF_TEMPERATURE_THRESHOLD: DEFAULT_TEMPERATURE_THRESHOLD,
        CONF_TEMPERATURE_FORECAST_THRESHOLD: DEFAULT_TEMPERATURE_FORECAST_THRESHOLD,
    }


def resolve_room_config(
    system_values: Mapping[str, Any],
    global_sources: Mapping[str, Any],
    global_defaults: Mapping[str, Any],
    group: str,
    group_settings: Mapping[str, Any],
    room_settings: Mapping[str, Any],
    room_overrides: Mapping[str, Mapping[str, Any]],
    *,
    room_id: str = "room",
    room_name: str = "Room",
    source_overrides: Mapping[str, Any] | None = None,
) -> ResolvedRoomConfig:
    """Resolve all layers once, before runtime modules consume configuration."""

    values: dict[str, Any] = {}
    sources: dict[str, str] = {}

    def merge(layer: Mapping[str, Any], origin: str) -> None:
        for key, value in layer.items():
            values[key] = value
            sources[key] = origin

    merge(system_values, "system_default")
    merge(global_defaults, "global_default")
    settings = {
        key: value for key, value in group_settings.items() if key not in GROUP_BLOCKED_KEYS
    }
    if CONF_AUTO_TIME in settings:
        time_enabled = bool(settings[CONF_AUTO_TIME])
        settings.setdefault(CONF_AUTO_UP, time_enabled)
        settings.setdefault(CONF_AUTO_DOWN, time_enabled)
    merge(settings, f"group:{group}")
    merge(room_settings, "room_setting")
    for overrides in room_overrides.values():
        if isinstance(overrides, Mapping):
            merge(overrides, "room_override")
    merge(global_sources, "global_source")
    merge(source_overrides or {}, "room_source_override")
    values[CONF_ROOM_ID] = room_id
    values[CONF_ROOM] = room_name
    return ResolvedRoomConfig(
        room_id,
        room_name,
        values,
        sources,
        group,
        frozenset(GROUP_FUNCTIONS),
    )


def resolve_config_model(
    model: Mapping[str, Any], room_id: str
) -> ResolvedRoomConfig:
    """Resolve one room from the native parent/subentry configuration model."""

    global_config = model.get(CONF_GLOBAL, {})
    groups = model.get(CONF_GROUPS, {})
    rooms = model.get(CONF_ROOMS, {})
    room = rooms.get(room_id, {}) if isinstance(rooms, Mapping) else {}
    group = str(room.get(CONF_GROUP, DEFAULT_GROUP))
    if group not in GROUPS:
        group = DEFAULT_GROUP
    group_settings = groups.get(group, {}) if isinstance(groups, Mapping) else {}
    return resolve_room_config(
        system_defaults(),
        global_config.get(CONF_GLOBAL_SOURCES, {}),
        global_config.get(CONF_GLOBAL_DEFAULTS, {}),
        group,
        group_settings,
        room.get(CONF_ROOM_SETTINGS, {}),
        room.get(CONF_ROOM_OVERRIDES, {}),
        room_id=room_id,
        room_name=str(room.get(CONF_NAME, room_id)),
        source_overrides=room.get(CONF_SOURCE_OVERRIDES, {}),
    )
