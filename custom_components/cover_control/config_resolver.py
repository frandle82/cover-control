"""Resolve hierarchical Cover Control configuration for one room.

Profiles own automation behavior. Rooms own the physical installation and the
per-room selection of which configured profile functions are used.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

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
        CONF_SHADING_FORECAST_SENSOR,
        CONF_SHADING_FORECAST_TEMP_SENSOR,
        CONF_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR,
        CONF_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR,
        CONF_ADDITIONAL_CONDITION_GLOBAL,
    }
)

ROOM_SOURCE_OVERRIDE_KEYS = frozenset(
    {
        CONF_BRIGHTNESS_SENSOR,
        CONF_SHADING_BRIGHTNESS_SENSOR,
        CONF_TEMPERATURE_SENSOR_OUTDOOR,
        CONF_COLD_PROTECTION_FORECAST_SENSOR,
        CONF_SHADING_FORECAST_SENSOR,
        CONF_SHADING_FORECAST_TEMP_SENSOR,
    }
)

GLOBAL_DEFAULT_KEYS = frozenset(
    {
        CONF_MANUAL_OVERRIDE_MINUTES,
        CONF_MANUAL_SCHEDULE_ADOPTION,
        CONF_ENABLE_LOGBOOK_COVER,
    }
)

ROOM_HARDWARE_KEYS = frozenset(
    {
        CONF_COVERS,
        CONF_COVER_TYPE,
        CONF_POSITION_SOURCE,
        CONF_CUSTOM_POSITION_SENSOR,
        CONF_DRIVE_TIME,
        CONF_POSITION_TOLERANCE,
        CONF_COVER_TILT_WAIT_MODE,
        CONF_COVER_TILT_WAIT_TIMEOUT,
    }
)

ROOM_POSITION_KEYS = frozenset(
    {
        CONF_OPEN_POSITION,
        CONF_CLOSE_POSITION,
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

ROOM_GEOMETRY_KEYS = frozenset(
    {
        CONF_SUN_AZIMUTH_START,
        CONF_SUN_AZIMUTH_END,
    }
)

ROOM_CONTROL_KEYS = frozenset(
    {
        CONF_ENABLE_RECALIBRATE_BUTTON,
        CONF_ENABLE_CLEAR_MANUAL_OVERRIDE_BUTTON,
        CONF_ENABLE_LOGBOOK_COVER,
    }
)

TIME_PROFILE_KEYS = frozenset(
    {
        CONF_AUTO_UP,
        CONF_AUTO_DOWN,
        CONF_AUTO_TIME,
        CONF_AUTO_BRIGHTNESS,
        CONF_AUTO_SUN,
        CONF_USE_WORKDAY_SENSOR,
        CONF_USE_BRIGHTNESS_SENSOR,
        CONF_USE_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR,
        CONF_USE_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR,
        CONF_TIME_UP_EARLY_WORKDAY,
        CONF_TIME_UP_LATE_WORKDAY,
        CONF_TIME_UP_EARLY_NON_WORKDAY,
        CONF_TIME_UP_LATE_NON_WORKDAY,
        CONF_TIME_DOWN_EARLY_WORKDAY,
        CONF_TIME_DOWN_LATE_WORKDAY,
        CONF_TIME_DOWN_EARLY_NON_WORKDAY,
        CONF_TIME_DOWN_LATE_NON_WORKDAY,
        CONF_CALENDAR_OPEN_TITLE,
        CONF_CALENDAR_CLOSE_TITLE,
        CONF_BRIGHTNESS_OPEN_ABOVE,
        CONF_BRIGHTNESS_CLOSE_BELOW,
        CONF_BRIGHTNESS_HYSTERESIS,
        CONF_BRIGHTNESS_TIME_DURATION,
        CONF_BRIGHTNESS_SUN_OPERATOR,
        CONF_SUN_ELEVATION_OPEN,
        CONF_SUN_ELEVATION_CLOSE,
        CONF_SUN_ELEVATION_MODE,
        CONF_SUN_TIME_DURATION,
        CONF_SUN_ELEVATION_OPEN_OFFSET,
        CONF_SUN_ELEVATION_CLOSE_OFFSET,
    }
)

BRIGHTNESS_PROFILE_KEYS = frozenset(
    {
        CONF_AUTO_BRIGHTNESS,
        CONF_USE_BRIGHTNESS_SENSOR,
        CONF_BRIGHTNESS_OPEN_ABOVE,
        CONF_BRIGHTNESS_CLOSE_BELOW,
        CONF_BRIGHTNESS_HYSTERESIS,
        CONF_BRIGHTNESS_TIME_DURATION,
        CONF_BRIGHTNESS_SUN_OPERATOR,
    }
)

SUN_PROFILE_KEYS = frozenset(
    {
        CONF_AUTO_SUN,
        CONF_USE_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR,
        CONF_USE_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR,
        CONF_SUN_ELEVATION_OPEN,
        CONF_SUN_ELEVATION_CLOSE,
        CONF_SUN_ELEVATION_MODE,
        CONF_SUN_TIME_DURATION,
        CONF_SUN_ELEVATION_OPEN_OFFSET,
        CONF_SUN_ELEVATION_CLOSE_OFFSET,
    }
)

SHADING_PROFILE_KEYS = frozenset(
    {
        CONF_AUTO_SHADING,
        CONF_SHADING_BRIGHTNESS_START,
        CONF_SHADING_BRIGHTNESS_END,
        CONF_SHADING_BRIGHTNESS_HYSTERESIS,
        CONF_SHADING_MIN_TEMPERATURE_1,
        CONF_SHADING_TEMPERATURE_HYSTERESIS_1,
        CONF_SHADING_MIN_TEMPERATURE_2,
        CONF_SHADING_TEMPERATURE_HYSTERESIS_2,
        CONF_SHADING_FORECAST_TYPE,
        CONF_SHADING_FORECAST_TEMP,
        CONF_SHADING_FORECAST_TEMP_HYSTERESIS,
        CONF_SHADING_WEATHER_CONDITIONS,
        CONF_SHADING_CONFIG,
        CONF_SHADING_CONDITIONS_START_AND,
        CONF_SHADING_CONDITIONS_START_OR,
        CONF_SHADING_CONDITIONS_END_AND,
        CONF_SHADING_CONDITIONS_END_OR,
        CONF_SHADING_WAITINGTIME_START,
        CONF_SHADING_WAITINGTIME_END,
        CONF_SHADING_START_MAX_DURATION,
        CONF_SHADING_END_MAX_DURATION,
        CONF_SHADING_END_IMMEDIATE_BY_SUN_POSITION,
        CONF_SHADING_INDEPENDENT_HOLDS_END,
        CONF_SHADING_INDEPENDENT_TEMP,
        CONF_USE_SHADING_FORECAST_SENSOR,
        CONF_USE_COLD_PROTECTION_FORECAST_SENSOR,
        CONF_COLD_PROTECTION_THRESHOLD,
        CONF_TEMPERATURE_THRESHOLD,
        CONF_TEMPERATURE_FORECAST_THRESHOLD,
        CONF_SHADING_TILT_ELEVATION_1,
        CONF_SHADING_TILT_ELEVATION_2,
        CONF_SHADING_TILT_ELEVATION_3,
    }
)

BEHAVIOR_PROFILE_KEYS = frozenset(
    {
        *DEFAULT_BEHAVIOR_SETTINGS,
        *DEFAULT_MANUAL_OVERRIDE_FLAGS,
        *DEFAULT_CONTACT_SETTINGS,
        CONF_MANUAL_OVERRIDE_MINUTES,
        CONF_MANUAL_OVERRIDE_RESET_MODE,
        CONF_MANUAL_OVERRIDE_RESET_TIME,
        CONF_AUTO_VENTILATE,
        CONF_RESIDENT_STATUS,
        CONF_RESIDENT_OPEN_ENABLED,
        CONF_RESIDENT_CLOSE_ENABLED,
        CONF_RESIDENT_ALLOW_SHADING,
        CONF_RESIDENT_ALLOW_OPEN,
        CONF_RESIDENT_ALLOW_VENTILATION,
    }
) - ROOM_HARDWARE_KEYS - ROOM_POSITION_KEYS - ROOM_SENSOR_KEYS - ROOM_GEOMETRY_KEYS

VENTILATION_PROFILE_KEYS = frozenset({CONF_AUTO_VENTILATE, *DEFAULT_CONTACT_SETTINGS})

RESIDENT_PROFILE_KEYS = frozenset(
    {
        CONF_RESIDENT_STATUS,
        CONF_RESIDENT_OPEN_ENABLED,
        CONF_RESIDENT_CLOSE_ENABLED,
        CONF_RESIDENT_ALLOW_SHADING,
        CONF_RESIDENT_ALLOW_OPEN,
        CONF_RESIDENT_ALLOW_VENTILATION,
    }
)

PROFILE_KEYS = {
    PROFILE_TYPE_TIME: TIME_PROFILE_KEYS,
    PROFILE_TYPE_SHADING: SHADING_PROFILE_KEYS,
    PROFILE_TYPE_BEHAVIOR: BEHAVIOR_PROFILE_KEYS,
}

PROFILE_FUNCTION_KEYS = {
    FUNCTION_TIME: TIME_PROFILE_KEYS - BRIGHTNESS_PROFILE_KEYS - SUN_PROFILE_KEYS,
    FUNCTION_BRIGHTNESS: BRIGHTNESS_PROFILE_KEYS,
    FUNCTION_SUN: SUN_PROFILE_KEYS,
    FUNCTION_SHADING: SHADING_PROFILE_KEYS,
    FUNCTION_VENTILATION: VENTILATION_PROFILE_KEYS,
    FUNCTION_RESIDENT: RESIDENT_PROFILE_KEYS,
    FUNCTION_BEHAVIOR: BEHAVIOR_PROFILE_KEYS
    - VENTILATION_PROFILE_KEYS
    - RESIDENT_PROFILE_KEYS
    - ROOM_HARDWARE_KEYS
    - ROOM_POSITION_KEYS
    - ROOM_SENSOR_KEYS
    - ROOM_GEOMETRY_KEYS
    - ROOM_CONTROL_KEYS,
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


def configured_functions_from_profile(profile: Mapping[str, Any]) -> frozenset[str]:
    """Return behavior functions that are explicitly configured in a profile."""

    functions = profile.get(CONF_PROFILE_FUNCTIONS)
    if isinstance(functions, Mapping):
        configured = frozenset(
            function
            for function, enabled in functions.items()
            if enabled and function in PROFILE_FUNCTIONS
        )
        if configured:
            return configured
    if isinstance(functions, (list, tuple, set, frozenset)):
        configured = frozenset(
            function for function in functions if function in PROFILE_FUNCTIONS
        )
        if configured:
            return configured
    capabilities = profile.get(CONF_PROFILE_CAPABILITIES)
    if isinstance(capabilities, (list, tuple, set, frozenset)):
        configured: set[str] = set()
        if set(capabilities) & {"opening", "closing", "workday", "calendar"}:
            configured.add(FUNCTION_TIME)
        if "brightness" in capabilities:
            configured.add(FUNCTION_BRIGHTNESS)
        if "sun" in capabilities:
            configured.add(FUNCTION_SUN)
        if set(capabilities) & {
            "positioning",
            "temperature",
            "forecast",
            "weather",
            "conditions",
            "waiting",
            "tilt",
            "independent_temperature",
        }:
            configured.add(FUNCTION_SHADING)
        if "ventilation" in capabilities:
            configured.add(FUNCTION_VENTILATION)
        if "resident" in capabilities:
            configured.add(FUNCTION_RESIDENT)
        if set(capabilities) & {
            "manual_override",
            "movement_protection",
            "tilt_behavior",
        }:
            configured.add(FUNCTION_BEHAVIOR)
        if configured:
            return frozenset(configured)

    settings = profile.get(CONF_PROFILE_SETTINGS, {})
    if not isinstance(settings, Mapping):
        settings = profile
    configured: set[str] = set()
    for function, keys in PROFILE_FUNCTION_KEYS.items():
        block = profile.get(function)
        if (
            isinstance(block, Mapping)
            and block
            or any(key in settings for key in keys)
        ):
            configured.add(function)
    return frozenset(configured)


def profile_settings(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Return flattened runtime settings from legacy or unified profile data."""

    settings: dict[str, Any] = {}
    legacy_settings = profile.get(CONF_PROFILE_SETTINGS, {})
    if isinstance(legacy_settings, Mapping):
        settings.update(legacy_settings)
    for function in PROFILE_FUNCTIONS:
        block = profile.get(function)
        if isinstance(block, Mapping):
            settings.update(block)
    return settings


def effective_profile_id(room: Mapping[str, Any]) -> str | None:
    """Return the room's single active profile reference."""

    profile_id = room.get(CONF_ROOM_PROFILE_ID)
    if profile_id:
        return str(profile_id)
    profile_id = room.get(CONF_PROFILE_ID)
    if profile_id:
        return str(profile_id)
    selections = room.get(CONF_PROFILE_SELECTIONS, {})
    if isinstance(selections, Mapping) and selections:
        return "legacy:" + "|".join(
            f"{profile_type}={selections.get(profile_type, '')}"
            for profile_type in PROFILE_TYPES
        )
    return None


def effective_profile(model: Mapping[str, Any], room: Mapping[str, Any]) -> dict[str, Any]:
    """Return the single active profile, composing legacy typed profiles if needed."""

    profiles = model.get(CONF_PROFILES, {})
    profile_id = (
        room.get(CONF_ROOM_PROFILE_ID)
        or room.get("profile_id")
        or room.get(CONF_PROFILE_ID)
    )
    if profile_id and isinstance(profiles, Mapping):
        profile = profiles.get(profile_id)
        if isinstance(profile, Mapping):
            return dict(profile)

    selections = room.get(CONF_PROFILE_SELECTIONS, {})
    if not isinstance(selections, Mapping):
        return {}
    merged: dict[str, Any] = {
        CONF_PROFILE_ID: effective_profile_id(room) or "",
        CONF_PROFILE_NAME: "Legacy profile",
        CONF_PROFILE_SETTINGS: {},
        CONF_PROFILE_FUNCTIONS: [],
    }
    functions: set[str] = set()
    settings = merged[CONF_PROFILE_SETTINGS]
    for profile_type in PROFILE_TYPES:
        selected_id = selections.get(profile_type)
        catalog = profiles.get(profile_type, {}) if isinstance(profiles, Mapping) else {}
        profile = catalog.get(selected_id, {}) if isinstance(catalog, Mapping) else {}
        if not isinstance(profile, Mapping):
            continue
        settings.update(profile_settings(profile))
        functions.update(configured_functions_from_profile(profile))
        if merged[CONF_PROFILE_NAME] == "Legacy profile":
            merged[CONF_PROFILE_NAME] = str(
                profile.get(CONF_PROFILE_NAME, selected_id or "Legacy profile")
            )
    merged[CONF_PROFILE_FUNCTIONS] = sorted(functions)
    return merged


def effective_room_profile_functions(
    model: Mapping[str, Any], room: Mapping[str, Any]
) -> frozenset[str]:
    """Return configured functions selected by the room for its active profile."""

    profile = effective_profile(model, room)
    available = configured_functions_from_profile(profile)
    selected = room_selected_functions(room)
    if selected is None:
        return available
    return frozenset(function for function in selected if function in available)


def room_selected_functions(room: Mapping[str, Any]) -> frozenset[str] | None:
    """Return the room's selected profile functions, or None for legacy rooms."""

    selected = room.get(CONF_PROFILE_FUNCTIONS)
    if selected is None:
        selections = room.get(CONF_PROFILE_SELECTIONS)
        if (
            isinstance(selections, Mapping)
            and selections
            and not (room.get(CONF_ROOM_PROFILE_ID) or room.get(CONF_PROFILE_ID))
        ):
            return None
        return frozenset()
    if isinstance(selected, Mapping):
        return frozenset(
            function
            for function, enabled in selected.items()
            if enabled and function in PROFILE_FUNCTIONS
        )
    if isinstance(selected, (list, tuple, set, frozenset)):
        return frozenset(
            function for function in selected if function in PROFILE_FUNCTIONS
        )
    return frozenset()


@dataclass(frozen=True, slots=True)
class ResolvedRoomConfig(Mapping[str, Any]):
    """Complete runtime configuration and non-persistent origin metadata."""

    room_id: str
    room_name: str
    values: Mapping[str, Any]
    sources: Mapping[str, str] = field(default_factory=dict)
    selected_profiles: Mapping[str, str] = field(default_factory=dict)
    profile_names: Mapping[str, str] = field(default_factory=dict)
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
        **DEFAULT_SHADING_TIMING_SETTINGS,
        **{
            key: list(value) if isinstance(value, list) else value
            for key, value in DEFAULT_SHADING_CONDITION_SETTINGS.items()
        },
        CONF_SUN_ELEVATION_MODE: DEFAULT_SUN_ELEVATION_MODE,
        CONF_SUN_ELEVATION_OPEN_OFFSET: DEFAULT_SUN_ELEVATION_OPEN_OFFSET,
        CONF_SUN_ELEVATION_CLOSE_OFFSET: DEFAULT_SUN_ELEVATION_CLOSE_OFFSET,
        CONF_TEMPERATURE_THRESHOLD: DEFAULT_TEMPERATURE_THRESHOLD,
        CONF_TEMPERATURE_FORECAST_THRESHOLD: DEFAULT_TEMPERATURE_FORECAST_THRESHOLD,
    }


def resolve_room_config(
    system_values: Mapping[str, Any],
    global_sources: Mapping[str, Any],
    global_defaults: Mapping[str, Any],
    selected_profiles: Mapping[str, Mapping[str, Any]],
    room_settings: Mapping[str, Any],
    room_overrides: Mapping[str, Mapping[str, Any]],
    *,
    room_id: str = "room",
    room_name: str = "Room",
    source_overrides: Mapping[str, Any] | None = None,
    selected_profile_functions: frozenset[str] | None = None,
) -> ResolvedRoomConfig:
    """Resolve all layers once, before runtime modules consume configuration."""

    values: dict[str, Any] = {}
    sources: dict[str, str] = {}
    profile_ids: dict[str, str] = {}
    profile_names: dict[str, str] = {}
    profile_functions: set[str] = set()

    def merge(layer: Mapping[str, Any], origin: str) -> None:
        for key, value in layer.items():
            values[key] = value
            sources[key] = origin

    merge(system_values, "system_default")
    merge(global_defaults, "global_default")
    for profile_type, profile in selected_profiles.items():
        profile = selected_profiles.get(profile_type)
        if not isinstance(profile, Mapping):
            continue
        profile_id = str(profile.get(CONF_PROFILE_ID, ""))
        settings = profile_settings(profile)
        if not isinstance(settings, Mapping):
            continue
        resolved_settings = dict(settings)
        if CONF_AUTO_TIME in settings:
            time_enabled = bool(settings[CONF_AUTO_TIME])
            resolved_settings.setdefault(CONF_AUTO_UP, time_enabled)
            resolved_settings.setdefault(CONF_AUTO_DOWN, time_enabled)
        merge(resolved_settings, f"profile:{profile_id}")
        profile_ids[profile_type] = profile_id
        profile_names[profile_type] = str(
            profile.get(CONF_PROFILE_NAME, profile_id)
        )
        profile_functions.update(configured_functions_from_profile(profile))
    if selected_profile_functions is not None:
        profile_functions &= set(selected_profile_functions)
    merge(room_settings, "room_setting")
    for profile_type in PROFILE_TYPES:
        overrides = room_overrides.get(profile_type, {})
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
        profile_ids,
        profile_names,
        frozenset(profile_functions),
    )


def resolve_config_model(
    model: Mapping[str, Any], room_id: str
) -> ResolvedRoomConfig:
    """Resolve one room from the native parent/subentry configuration model."""

    global_config = model.get(CONF_GLOBAL, {})
    profiles = model.get(CONF_PROFILES, {})
    rooms = model.get(CONF_ROOMS, {})
    room = rooms.get(room_id, {}) if isinstance(rooms, Mapping) else {}
    profile = effective_profile(model, room)
    selected = {"profile": profile} if profile else {}
    selected_functions = effective_room_profile_functions(model, room)
    return resolve_room_config(
        system_defaults(),
        global_config.get(CONF_GLOBAL_SOURCES, {}),
        global_config.get(CONF_GLOBAL_DEFAULTS, {}),
        selected,
        room.get(CONF_ROOM_SETTINGS, {}),
        room.get(CONF_ROOM_OVERRIDES, {}),
        room_id=room_id,
        room_name=str(room.get(CONF_NAME, room_id)),
        source_overrides=room.get(CONF_SOURCE_OVERRIDES, {}),
        selected_profile_functions=selected_functions,
    )


def resolve_profile_config(
    model: Mapping[str, Any], profile_type: str, profile_id: str
) -> Mapping[str, Any]:
    """Resolve a profile without room settings, overrides, or runtime toggles."""

    global_config = model.get(CONF_GLOBAL, {})
    profiles = model.get(CONF_PROFILES, {})
    profile = profiles.get(profile_id) if isinstance(profiles, Mapping) else None
    if not isinstance(profile, Mapping) and profile_id.startswith("legacy:"):
        selections = {}
        for part in profile_id.removeprefix("legacy:").split("|"):
            if "=" in part:
                key, value = part.split("=", 1)
                if value:
                    selections[key] = value
        profile = effective_profile(model, {CONF_PROFILE_SELECTIONS: selections})
    if not isinstance(profile, Mapping):
        profile = (
            profiles.get(profile_type, {}).get(profile_id)
            if isinstance(profiles, Mapping)
            else None
        )
    selected = {"profile": profile} if isinstance(profile, Mapping) else {}
    return resolve_room_config(
        system_defaults(),
        global_config.get(CONF_GLOBAL_SOURCES, {}),
        global_config.get(CONF_GLOBAL_DEFAULTS, {}),
        selected,
        {},
        {},
        room_id="profile",
        room_name=str(
            profile.get(CONF_PROFILE_NAME, profile_id)
            if isinstance(profile, Mapping)
            else profile_id
        ),
    )
