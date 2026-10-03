"""Resolve hierarchical Cover Control configuration for one room."""

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
        CONF_RESIDENT_SENSOR,
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
        CONF_RESIDENT_SENSOR,
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
        CONF_OPEN_POSITION,
        CONF_CLOSE_POSITION,
        CONF_VENTILATE_POSITION,
        CONF_OPEN_TILT_POSITION,
        CONF_CLOSE_TILT_POSITION,
        CONF_VENTILATE_TILT_POSITION,
        CONF_POSITION_TOLERANCE,
        CONF_COVER_TILT_WAIT_MODE,
        CONF_COVER_TILT_WAIT_TIMEOUT,
        CONF_MANUAL_SCHEDULE_ADOPTION,
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

SHADING_PROFILE_KEYS = frozenset(
    {
        CONF_AUTO_SHADING,
        CONF_SHADING_POSITION,
        CONF_SHADING_TILT_POSITION,
        CONF_SHADING_POSITION_ALT,
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
        CONF_SHADING_TILT_POSITION_0,
        CONF_SHADING_TILT_POSITION_1,
        CONF_SHADING_TILT_POSITION_2,
        CONF_SHADING_TILT_POSITION_3,
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
        CONF_OPEN_POSITION,
        CONF_CLOSE_POSITION,
        CONF_VENTILATE_POSITION,
        CONF_LOCKOUT_POSITION,
        CONF_OPEN_TILT_POSITION,
        CONF_CLOSE_TILT_POSITION,
        CONF_VENTILATE_TILT_POSITION,
        CONF_POSITION_TOLERANCE,
        CONF_COVER_TILT_WAIT_MODE,
        CONF_COVER_TILT_WAIT_TIMEOUT,
    }
)

PROFILE_KEYS = {
    PROFILE_TYPE_TIME: TIME_PROFILE_KEYS,
    PROFILE_TYPE_SHADING: SHADING_PROFILE_KEYS,
    PROFILE_TYPE_BEHAVIOR: BEHAVIOR_PROFILE_KEYS,
}


@dataclass(frozen=True)
class ResolvedRoomConfig(Mapping[str, Any]):
    """Complete runtime configuration and non-persistent origin metadata."""

    room_id: str
    room_name: str
    values: Mapping[str, Any]
    sources: Mapping[str, str] = field(default_factory=dict)
    selected_profiles: Mapping[str, str] = field(default_factory=dict)
    profile_names: Mapping[str, str] = field(default_factory=dict)

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
) -> ResolvedRoomConfig:
    """Resolve all layers once, before runtime modules consume configuration."""

    values: dict[str, Any] = {}
    sources: dict[str, str] = {}
    profile_ids: dict[str, str] = {}
    profile_names: dict[str, str] = {}

    def merge(layer: Mapping[str, Any], origin: str) -> None:
        for key, value in layer.items():
            values[key] = value
            sources[key] = origin

    merge(system_values, "system_default")
    merge(global_defaults, "global_default")
    for profile_type in PROFILE_TYPES:
        profile = selected_profiles.get(profile_type)
        if not isinstance(profile, Mapping):
            continue
        profile_id = str(profile.get(CONF_PROFILE_ID, ""))
        settings = profile.get(CONF_PROFILE_SETTINGS, {})
        if not isinstance(settings, Mapping):
            continue
        merge(settings, f"profile:{profile_id}")
        profile_ids[profile_type] = profile_id
        profile_names[profile_type] = str(
            profile.get(CONF_PROFILE_NAME, profile_id)
        )
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
    )


def normalize_legacy_config(
    data: Mapping[str, Any],
    options: Mapping[str, Any],
    *,
    room_id: str,
) -> dict[str, Any]:
    """Convert a flat entry to an equivalent in-memory profile model."""

    flat = {**data, **options}
    room_name = str(flat.get(CONF_ROOM) or flat.get(CONF_NAME) or room_id)
    profiles: dict[str, dict[str, Any]] = {kind: {} for kind in PROFILE_TYPES}
    selections: dict[str, str] = {}
    classified: set[str] = set()
    for profile_type, keys in PROFILE_KEYS.items():
        settings = {key: flat[key] for key in keys if key in flat}
        profile_id = f"legacy-{room_id}-{profile_type}"
        profiles[profile_type][profile_id] = {
            CONF_PROFILE_ID: profile_id,
            CONF_PROFILE_NAME: f"{room_name} (legacy)",
            CONF_PROFILE_SETTINGS: settings,
        }
        selections[profile_type] = profile_id
        classified.update(settings)

    global_sources = {
        key: flat[key] for key in GLOBAL_SOURCE_KEYS if key in flat
    }
    classified.update(global_sources)
    model_keys = {
        CONF_CONFIG_MODEL,
        CONF_CONFIG_VERSION,
        CONF_GLOBAL,
        CONF_PROFILES,
        CONF_ROOMS,
    }
    room_settings = {
        key: value
        for key, value in flat.items()
        if key not in classified and key not in model_keys
    }
    return {
        CONF_CONFIG_VERSION: CONFIG_MODEL_VERSION,
        CONF_GLOBAL: {
            CONF_GLOBAL_SOURCES: global_sources,
            CONF_GLOBAL_DEFAULTS: {},
        },
        CONF_PROFILES: profiles,
        CONF_ROOMS: {
            room_id: {
                CONF_ROOM_ID: room_id,
                CONF_NAME: room_name,
                CONF_PROFILE_SELECTIONS: selections,
                CONF_ROOM_SETTINGS: room_settings,
                CONF_SOURCE_OVERRIDES: {},
                CONF_ROOM_OVERRIDES: {},
            }
        },
    }


def resolve_config_model(
    model: Mapping[str, Any], room_id: str
) -> ResolvedRoomConfig:
    """Resolve one room from a persisted or in-memory configuration model."""

    global_config = model.get(CONF_GLOBAL, {})
    profiles = model.get(CONF_PROFILES, {})
    rooms = model.get(CONF_ROOMS, {})
    room = rooms.get(room_id, {}) if isinstance(rooms, Mapping) else {}
    selections = room.get(CONF_PROFILE_SELECTIONS, {})
    selected: dict[str, Mapping[str, Any]] = {}
    for profile_type in PROFILE_TYPES:
        profile_id = selections.get(profile_type)
        catalog = profiles.get(profile_type, {})
        if profile_id and isinstance(catalog, Mapping) and profile_id in catalog:
            selected[profile_type] = catalog[profile_id]
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
    )


def entry_config_model(
    data: Mapping[str, Any], options: Mapping[str, Any], *, room_id: str
) -> dict[str, Any]:
    """Return the persisted model or a lossless legacy normalization."""

    combined = {**data, **options}
    model = combined.get(CONF_CONFIG_MODEL)
    if isinstance(model, Mapping):
        return dict(model)
    if all(key in combined for key in (CONF_GLOBAL, CONF_PROFILES, CONF_ROOMS)):
        return {key: combined[key] for key in combined if key != CONF_CONFIG_MODEL}
    return normalize_legacy_config(data, options, room_id=room_id)


def config_entry_room_id(data: Mapping[str, Any], fallback: str) -> str:
    """Return the stable persisted room ID for a config entry."""

    room_id = data.get(CONF_ROOM_ID)
    return str(room_id) if room_id else fallback


def persisted_entry_data(
    flat: Mapping[str, Any], *, room_id: str | None = None
) -> dict[str, Any]:
    """Wrap flat flow output in the canonical persisted configuration model."""

    stable_room_id = room_id or f"room-{uuid4().hex}"
    model = normalize_legacy_config(flat, {}, room_id=stable_room_id)
    return {
        CONF_ROOM_ID: stable_room_id,
        CONF_NAME: flat.get(CONF_NAME, DEFAULT_NAME),
        CONF_CONFIG_MODEL: model,
    }


def resolve_entry_config(
    data: Mapping[str, Any], options: Mapping[str, Any], *, room_id: str
) -> ResolvedRoomConfig:
    """Resolve current or legacy config-entry data for the runtime."""

    return resolve_config_model(
        entry_config_model(data, options, room_id=room_id), room_id
    )
