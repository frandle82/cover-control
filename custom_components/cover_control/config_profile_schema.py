"""Reusable native Home Assistant schemas for profiles and room overrides."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Mapping
from datetime import date, datetime, time, timedelta
from dataclasses import dataclass
from typing import Any

import voluptuous as vol
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from . import const as c
from .config_resolver import PROFILE_KEYS

CONF_PROFILE_FIELDS = "configured_profile_fields"
CONF_OVERRIDE_FIELDS = "configured_override_fields"
CONF_GLOBAL_DEFAULT_FIELDS = "configured_global_default_fields"
CONF_PROFILE_CAPABILITIES_FIELD = "profile_capabilities"

_SHADING_CONDITIONS = [
    c.SHADING_CONDITION_AZIMUTH,
    c.SHADING_CONDITION_ELEVATION,
    c.SHADING_CONDITION_BRIGHTNESS,
    c.SHADING_CONDITION_TEMP_1,
    c.SHADING_CONDITION_TEMP_2,
    c.SHADING_CONDITION_FORECAST_TEMP,
    c.SHADING_CONDITION_FORECAST_WEATHER,
]
_SHADING_CONFIGS = [
    c.SHADING_CONFIG_TEMP_INDEPENDENT,
    c.SHADING_CONFIG_COMPARE_FORECAST_SENSOR2,
]
_WEATHER_CONDITIONS = [
    "clear-night",
    "clear",
    "cloudy",
    "fog",
    "hail",
    "lightning",
    "lightning-rainy",
    "partlycloudy",
    "pouring",
    "rainy",
    "snowy",
    "snowy-rainy",
    "sunny",
    "windy",
    "windy-variant",
    "exceptional",
]

_BOOLEAN_KEYS = frozenset(
    {
        c.CONF_AUTO_UP,
        c.CONF_AUTO_DOWN,
        c.CONF_AUTO_TIME,
        c.CONF_AUTO_BRIGHTNESS,
        c.CONF_AUTO_SUN,
        c.CONF_USE_WORKDAY_SENSOR,
        c.CONF_USE_BRIGHTNESS_SENSOR,
        c.CONF_USE_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR,
        c.CONF_USE_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR,
        c.CONF_AUTO_SHADING,
        c.CONF_USE_SHADING_FORECAST_SENSOR,
        c.CONF_USE_COLD_PROTECTION_FORECAST_SENSOR,
        c.CONF_SHADING_END_IMMEDIATE_BY_SUN_POSITION,
        c.CONF_SHADING_INDEPENDENT_HOLDS_END,
        c.CONF_AUTO_VENTILATE,
        c.CONF_RESIDENT_STATUS,
        c.CONF_RESIDENT_OPEN_ENABLED,
        c.CONF_RESIDENT_CLOSE_ENABLED,
        c.CONF_RESIDENT_ALLOW_SHADING,
        c.CONF_RESIDENT_ALLOW_OPEN,
        c.CONF_RESIDENT_ALLOW_VENTILATION,
        c.CONF_MANUAL_OVERRIDE_BLOCK_OPEN,
        c.CONF_MANUAL_OVERRIDE_BLOCK_CLOSE,
        c.CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE,
        c.CONF_MANUAL_OVERRIDE_BLOCK_SHADING,
        c.CONF_MANUAL_SCHEDULE_ADOPTION,
        c.CONF_ENABLE_LOGBOOK_COVER,
        c.CONF_PREVENT_HIGHER_POSITION_CLOSING,
        c.CONF_PREVENT_LOWERING_WHEN_CLOSING_IF_SHADED,
        c.CONF_PREVENT_SHADING_END_IF_CLOSED,
        c.CONF_PREVENT_OPENING_AFTER_SHADING_END,
        c.CONF_PREVENT_OPENING_AFTER_VENTILATION_END,
        c.CONF_PREVENT_OPENING_MULTIPLE_TIMES,
        c.CONF_PREVENT_CLOSING_MULTIPLE_TIMES,
        c.CONF_PREVENT_SHADING_MULTIPLE_TIMES,
        c.CONF_PREVENT_DEFAULT_COVER_ACTIONS,
        c.CONF_VENTILATION_ALLOW_HIGHER_POSITION,
        c.CONF_VENTILATION_USE_AFTER_SHADING,
        c.CONF_VENTILATION_START_NO_DELAY,
        c.CONF_VENTILATION_KEEP_OPEN_ON_FULL_TO_TILT,
        c.CONF_SHADING_OVER_VENTILATION,
        c.CONF_LOCKOUT_TILT_CLOSE,
        c.CONF_LOCKOUT_TILT_SHADING_START,
        c.CONF_LOCKOUT_TILT_SHADING_END,
    }
)

_TIME_KEYS = frozenset(
    {
        c.CONF_TIME_UP_EARLY_WORKDAY,
        c.CONF_TIME_UP_LATE_WORKDAY,
        c.CONF_TIME_UP_EARLY_NON_WORKDAY,
        c.CONF_TIME_UP_LATE_NON_WORKDAY,
        c.CONF_TIME_DOWN_EARLY_WORKDAY,
        c.CONF_TIME_DOWN_LATE_WORKDAY,
        c.CONF_TIME_DOWN_EARLY_NON_WORKDAY,
        c.CONF_TIME_DOWN_LATE_NON_WORKDAY,
        c.CONF_MANUAL_OVERRIDE_RESET_TIME,
    }
)

_POSITION_KEYS = frozenset(
    {
        c.CONF_OPEN_POSITION,
        c.CONF_CLOSE_POSITION,
        c.CONF_VENTILATE_POSITION,
        c.CONF_LOCKOUT_POSITION,
        c.CONF_SHADING_POSITION,
        c.CONF_SHADING_POSITION_ALT,
        c.CONF_OPEN_TILT_POSITION,
        c.CONF_CLOSE_TILT_POSITION,
        c.CONF_VENTILATE_TILT_POSITION,
        c.CONF_SHADING_TILT_POSITION,
        c.CONF_SHADING_TILT_POSITION_0,
        c.CONF_SHADING_TILT_POSITION_1,
        c.CONF_SHADING_TILT_POSITION_2,
        c.CONF_SHADING_TILT_POSITION_3,
    }
)

_DURATION_KEYS = frozenset(
    {
        c.CONF_BRIGHTNESS_TIME_DURATION,
        c.CONF_SUN_TIME_DURATION,
        c.CONF_SHADING_WAITINGTIME_START,
        c.CONF_SHADING_WAITINGTIME_END,
        c.CONF_SHADING_START_MAX_DURATION,
        c.CONF_SHADING_END_MAX_DURATION,
        c.CONF_COVER_TILT_WAIT_TIMEOUT,
        c.CONF_CONTACT_TRIGGER_DELAY,
        c.CONF_CONTACT_STATUS_DELAY,
        c.CONF_VENTILATION_DELAY_AFTER_CLOSE,
    }
)

_TEMPERATURE_KEYS = frozenset(
    {
        c.CONF_COLD_PROTECTION_THRESHOLD,
        c.CONF_SHADING_MIN_TEMPERATURE_1,
        c.CONF_SHADING_MIN_TEMPERATURE_2,
        c.CONF_SHADING_FORECAST_TEMP,
        c.CONF_SHADING_INDEPENDENT_TEMP,
        c.CONF_TEMPERATURE_THRESHOLD,
        c.CONF_TEMPERATURE_FORECAST_THRESHOLD,
    }
)

_TEMPERATURE_HYSTERESIS_KEYS = frozenset(
    {
        c.CONF_SHADING_TEMPERATURE_HYSTERESIS_1,
        c.CONF_SHADING_TEMPERATURE_HYSTERESIS_2,
        c.CONF_SHADING_FORECAST_TEMP_HYSTERESIS,
    }
)

_ELEVATION_KEYS = frozenset(
    {
        c.CONF_SUN_ELEVATION_OPEN,
        c.CONF_SUN_ELEVATION_CLOSE,
        c.CONF_SUN_ELEVATION_OPEN_OFFSET,
        c.CONF_SUN_ELEVATION_CLOSE_OFFSET,
        c.CONF_SHADING_TILT_ELEVATION_1,
        c.CONF_SHADING_TILT_ELEVATION_2,
        c.CONF_SHADING_TILT_ELEVATION_3,
    }
)

_BRIGHTNESS_KEYS = frozenset(
    {
        c.CONF_BRIGHTNESS_OPEN_ABOVE,
        c.CONF_BRIGHTNESS_CLOSE_BELOW,
        c.CONF_BRIGHTNESS_HYSTERESIS,
        c.CONF_SHADING_BRIGHTNESS_START,
        c.CONF_SHADING_BRIGHTNESS_END,
        c.CONF_SHADING_BRIGHTNESS_HYSTERESIS,
    }
)

_MULTI_SELECTS = {
    c.CONF_SHADING_CONDITIONS_START_AND: (_SHADING_CONDITIONS, "shading_condition"),
    c.CONF_SHADING_CONDITIONS_START_OR: (_SHADING_CONDITIONS, "shading_condition"),
    c.CONF_SHADING_CONDITIONS_END_AND: (_SHADING_CONDITIONS, "shading_condition"),
    c.CONF_SHADING_CONDITIONS_END_OR: (_SHADING_CONDITIONS, "shading_condition"),
    c.CONF_SHADING_CONFIG: (_SHADING_CONFIGS, "shading_config"),
    c.CONF_SHADING_WEATHER_CONDITIONS: (_WEATHER_CONDITIONS, "weather_condition"),
}

_SELECTS = {
    c.CONF_SUN_ELEVATION_MODE: (["fixed", "dynamic"], "sun_elevation_mode"),
    c.CONF_BRIGHTNESS_SUN_OPERATOR: (
        [c.BRIGHTNESS_SUN_OPERATOR_OR, c.BRIGHTNESS_SUN_OPERATOR_AND],
        "brightness_sun_operator",
    ),
    c.CONF_SHADING_FORECAST_TYPE: (
        ["daily", "hourly", c.DEFAULT_SHADING_FORECAST_TYPE],
        "forecast_type",
    ),
    c.CONF_MANUAL_OVERRIDE_RESET_MODE: (
        [
            c.MANUAL_OVERRIDE_RESET_NONE,
            c.MANUAL_OVERRIDE_RESET_TIME,
            c.MANUAL_OVERRIDE_RESET_TIMEOUT,
        ],
        "manual_override_reset_mode",
    ),
    c.CONF_COVER_TILT_WAIT_MODE: (
        [
            c.COVER_TILT_WAIT_FIXED_DELAY,
            c.COVER_TILT_WAIT_IDLE,
            c.COVER_TILT_WAIT_BEFORE_POSITION,
        ],
        "cover_tilt_wait_mode",
    ),
    c.CONF_COVER_TYPE: (
        [c.CONF_COVER_TYPE_BLIND, c.CONF_COVER_TYPE_AWNING],
        "cover_type",
    ),
}

_TEXT_KEYS = frozenset({c.CONF_CALENDAR_OPEN_TITLE, c.CONF_CALENDAR_CLOSE_TITLE})

_PROFILE_GROUPS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    c.PROFILE_TYPE_TIME: (
        (
            "time_features",
            (
                c.CONF_AUTO_TIME,
                c.CONF_AUTO_UP,
                c.CONF_AUTO_DOWN,
                c.CONF_AUTO_SUN,
                c.CONF_AUTO_BRIGHTNESS,
                c.CONF_USE_WORKDAY_SENSOR,
                c.CONF_USE_BRIGHTNESS_SENSOR,
                c.CONF_USE_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR,
                c.CONF_USE_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR,
            ),
        ),
        (
            "workday_times",
            (
                c.CONF_TIME_UP_EARLY_WORKDAY,
                c.CONF_TIME_UP_LATE_WORKDAY,
                c.CONF_TIME_DOWN_EARLY_WORKDAY,
                c.CONF_TIME_DOWN_LATE_WORKDAY,
            ),
        ),
        (
            "non_workday_times",
            (
                c.CONF_TIME_UP_EARLY_NON_WORKDAY,
                c.CONF_TIME_UP_LATE_NON_WORKDAY,
                c.CONF_TIME_DOWN_EARLY_NON_WORKDAY,
                c.CONF_TIME_DOWN_LATE_NON_WORKDAY,
            ),
        ),
        (
            "sun_settings",
            (
                c.CONF_SUN_ELEVATION_MODE,
                c.CONF_SUN_ELEVATION_OPEN,
                c.CONF_SUN_ELEVATION_CLOSE,
                c.CONF_SUN_ELEVATION_OPEN_OFFSET,
                c.CONF_SUN_ELEVATION_CLOSE_OFFSET,
                c.CONF_SUN_TIME_DURATION,
            ),
        ),
        (
            "brightness_settings",
            (
                c.CONF_BRIGHTNESS_OPEN_ABOVE,
                c.CONF_BRIGHTNESS_CLOSE_BELOW,
                c.CONF_BRIGHTNESS_HYSTERESIS,
                c.CONF_BRIGHTNESS_TIME_DURATION,
                c.CONF_BRIGHTNESS_SUN_OPERATOR,
            ),
        ),
        (
            "calendar_behavior",
            (c.CONF_CALENDAR_OPEN_TITLE, c.CONF_CALENDAR_CLOSE_TITLE),
        ),
    ),
    c.PROFILE_TYPE_SHADING: (
        (
            "shading_targets",
            (
                c.CONF_AUTO_SHADING,
                c.CONF_SHADING_POSITION,
                c.CONF_SHADING_POSITION_ALT,
                c.CONF_SHADING_TILT_POSITION,
                c.CONF_SHADING_TILT_POSITION_0,
                c.CONF_SHADING_TILT_POSITION_1,
                c.CONF_SHADING_TILT_POSITION_2,
                c.CONF_SHADING_TILT_POSITION_3,
                c.CONF_SHADING_TILT_ELEVATION_1,
                c.CONF_SHADING_TILT_ELEVATION_2,
                c.CONF_SHADING_TILT_ELEVATION_3,
            ),
        ),
        (
            "shading_brightness",
            (
                c.CONF_SHADING_BRIGHTNESS_START,
                c.CONF_SHADING_BRIGHTNESS_END,
                c.CONF_SHADING_BRIGHTNESS_HYSTERESIS,
            ),
        ),
        (
            "shading_temperature",
            (
                c.CONF_SHADING_MIN_TEMPERATURE_1,
                c.CONF_SHADING_TEMPERATURE_HYSTERESIS_1,
                c.CONF_SHADING_MIN_TEMPERATURE_2,
                c.CONF_SHADING_TEMPERATURE_HYSTERESIS_2,
                c.CONF_TEMPERATURE_THRESHOLD,
                c.CONF_TEMPERATURE_FORECAST_THRESHOLD,
                c.CONF_COLD_PROTECTION_THRESHOLD,
                c.CONF_SHADING_INDEPENDENT_TEMP,
                c.CONF_SHADING_INDEPENDENT_HOLDS_END,
            ),
        ),
        (
            "shading_forecast",
            (
                c.CONF_USE_SHADING_FORECAST_SENSOR,
                c.CONF_USE_COLD_PROTECTION_FORECAST_SENSOR,
                c.CONF_SHADING_FORECAST_TYPE,
                c.CONF_SHADING_FORECAST_TEMP,
                c.CONF_SHADING_FORECAST_TEMP_HYSTERESIS,
                c.CONF_SHADING_WEATHER_CONDITIONS,
                c.CONF_SHADING_CONFIG,
            ),
        ),
        (
            "shading_conditions",
            (
                c.CONF_SHADING_CONDITIONS_START_AND,
                c.CONF_SHADING_CONDITIONS_START_OR,
                c.CONF_SHADING_CONDITIONS_END_AND,
                c.CONF_SHADING_CONDITIONS_END_OR,
            ),
        ),
        (
            "shading_waits",
            (
                c.CONF_SHADING_WAITINGTIME_START,
                c.CONF_SHADING_WAITINGTIME_END,
                c.CONF_SHADING_START_MAX_DURATION,
                c.CONF_SHADING_END_MAX_DURATION,
                c.CONF_SHADING_END_IMMEDIATE_BY_SUN_POSITION,
            ),
        ),
    ),
    c.PROFILE_TYPE_BEHAVIOR: (
        (
            "positions",
            (
                c.CONF_COVER_TYPE,
                c.CONF_OPEN_POSITION,
                c.CONF_CLOSE_POSITION,
                c.CONF_VENTILATE_POSITION,
                c.CONF_LOCKOUT_POSITION,
                c.CONF_OPEN_TILT_POSITION,
                c.CONF_CLOSE_TILT_POSITION,
                c.CONF_VENTILATE_TILT_POSITION,
                c.CONF_POSITION_TOLERANCE,
            ),
        ),
        (
            "manual_override",
            (
                c.CONF_MANUAL_OVERRIDE_MINUTES,
                c.CONF_MANUAL_OVERRIDE_RESET_MODE,
                c.CONF_MANUAL_OVERRIDE_RESET_TIME,
                c.CONF_MANUAL_OVERRIDE_BLOCK_OPEN,
                c.CONF_MANUAL_OVERRIDE_BLOCK_CLOSE,
                c.CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE,
                c.CONF_MANUAL_OVERRIDE_BLOCK_SHADING,
                c.CONF_MANUAL_SCHEDULE_ADOPTION,
            ),
        ),
        (
            "ventilation",
            (
                c.CONF_AUTO_VENTILATE,
                c.CONF_CONTACT_TRIGGER_DELAY,
                c.CONF_CONTACT_STATUS_DELAY,
                c.CONF_VENTILATION_DELAY_AFTER_CLOSE,
                c.CONF_VENTILATION_ALLOW_HIGHER_POSITION,
                c.CONF_VENTILATION_USE_AFTER_SHADING,
                c.CONF_VENTILATION_START_NO_DELAY,
                c.CONF_VENTILATION_KEEP_OPEN_ON_FULL_TO_TILT,
                c.CONF_SHADING_OVER_VENTILATION,
                c.CONF_LOCKOUT_TILT_CLOSE,
                c.CONF_LOCKOUT_TILT_SHADING_START,
                c.CONF_LOCKOUT_TILT_SHADING_END,
            ),
        ),
        (
            "resident_behavior",
            (
                c.CONF_RESIDENT_STATUS,
                c.CONF_RESIDENT_OPEN_ENABLED,
                c.CONF_RESIDENT_CLOSE_ENABLED,
                c.CONF_RESIDENT_ALLOW_SHADING,
                c.CONF_RESIDENT_ALLOW_OPEN,
                c.CONF_RESIDENT_ALLOW_VENTILATION,
            ),
        ),
        (
            "prevention",
            (
                c.CONF_PREVENT_HIGHER_POSITION_CLOSING,
                c.CONF_PREVENT_LOWERING_WHEN_CLOSING_IF_SHADED,
                c.CONF_PREVENT_SHADING_END_IF_CLOSED,
                c.CONF_PREVENT_OPENING_AFTER_SHADING_END,
                c.CONF_PREVENT_OPENING_AFTER_VENTILATION_END,
                c.CONF_PREVENT_OPENING_MULTIPLE_TIMES,
                c.CONF_PREVENT_CLOSING_MULTIPLE_TIMES,
                c.CONF_PREVENT_SHADING_MULTIPLE_TIMES,
                c.CONF_PREVENT_DEFAULT_COVER_ACTIONS,
            ),
        ),
        (
            "tilt_wait",
            (
                c.CONF_COVER_TILT_WAIT_MODE,
                c.CONF_COVER_TILT_WAIT_TIMEOUT,
                c.CONF_ENABLE_LOGBOOK_COVER,
            ),
        ),
    ),
}

# A capability is the user-facing ownership boundary for a coherent group of
# canonical runtime keys. Runtime code continues to consume only those keys.
PROFILE_CAPABILITY_KEYS: dict[str, dict[str, frozenset[str]]] = {
    c.PROFILE_TYPE_TIME: {
        "opening": frozenset(
            {
                c.CONF_AUTO_TIME,
                c.CONF_AUTO_UP,
                c.CONF_TIME_UP_EARLY_WORKDAY,
                c.CONF_TIME_UP_LATE_WORKDAY,
                c.CONF_TIME_UP_EARLY_NON_WORKDAY,
                c.CONF_TIME_UP_LATE_NON_WORKDAY,
            }
        ),
        "closing": frozenset(
            {
                c.CONF_AUTO_DOWN,
                c.CONF_TIME_DOWN_EARLY_WORKDAY,
                c.CONF_TIME_DOWN_LATE_WORKDAY,
                c.CONF_TIME_DOWN_EARLY_NON_WORKDAY,
                c.CONF_TIME_DOWN_LATE_NON_WORKDAY,
            }
        ),
        "workday": frozenset({c.CONF_USE_WORKDAY_SENSOR}),
        "calendar": frozenset(
            {c.CONF_CALENDAR_OPEN_TITLE, c.CONF_CALENDAR_CLOSE_TITLE}
        ),
        "sun": frozenset(
            {
                c.CONF_AUTO_SUN,
                c.CONF_USE_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR,
                c.CONF_USE_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR,
                c.CONF_SUN_ELEVATION_OPEN,
                c.CONF_SUN_ELEVATION_CLOSE,
                c.CONF_SUN_ELEVATION_MODE,
                c.CONF_SUN_TIME_DURATION,
                c.CONF_SUN_ELEVATION_OPEN_OFFSET,
                c.CONF_SUN_ELEVATION_CLOSE_OFFSET,
            }
        ),
        "brightness": frozenset(
            {
                c.CONF_AUTO_BRIGHTNESS,
                c.CONF_USE_BRIGHTNESS_SENSOR,
                c.CONF_BRIGHTNESS_OPEN_ABOVE,
                c.CONF_BRIGHTNESS_CLOSE_BELOW,
                c.CONF_BRIGHTNESS_HYSTERESIS,
                c.CONF_BRIGHTNESS_TIME_DURATION,
                c.CONF_BRIGHTNESS_SUN_OPERATOR,
            }
        ),
    },
    c.PROFILE_TYPE_SHADING: {
        "positioning": frozenset(
            {
                c.CONF_AUTO_SHADING,
                c.CONF_SHADING_POSITION,
                c.CONF_SHADING_POSITION_ALT,
            }
        ),
        "brightness": frozenset(
            {
                c.CONF_SHADING_BRIGHTNESS_START,
                c.CONF_SHADING_BRIGHTNESS_END,
                c.CONF_SHADING_BRIGHTNESS_HYSTERESIS,
            }
        ),
        "temperature": frozenset(
            {
                c.CONF_SHADING_MIN_TEMPERATURE_1,
                c.CONF_SHADING_TEMPERATURE_HYSTERESIS_1,
                c.CONF_SHADING_MIN_TEMPERATURE_2,
                c.CONF_SHADING_TEMPERATURE_HYSTERESIS_2,
                c.CONF_COLD_PROTECTION_THRESHOLD,
                c.CONF_TEMPERATURE_THRESHOLD,
                c.CONF_TEMPERATURE_FORECAST_THRESHOLD,
                c.CONF_USE_COLD_PROTECTION_FORECAST_SENSOR,
            }
        ),
        "forecast": frozenset(
            {
                c.CONF_USE_SHADING_FORECAST_SENSOR,
                c.CONF_SHADING_FORECAST_TYPE,
                c.CONF_SHADING_FORECAST_TEMP,
                c.CONF_SHADING_FORECAST_TEMP_HYSTERESIS,
            }
        ),
        "weather": frozenset(
            {c.CONF_SHADING_WEATHER_CONDITIONS, c.CONF_SHADING_CONFIG}
        ),
        "conditions": frozenset(
            {
                c.CONF_SHADING_CONDITIONS_START_AND,
                c.CONF_SHADING_CONDITIONS_START_OR,
                c.CONF_SHADING_CONDITIONS_END_AND,
                c.CONF_SHADING_CONDITIONS_END_OR,
            }
        ),
        "waiting": frozenset(
            {
                c.CONF_SHADING_WAITINGTIME_START,
                c.CONF_SHADING_WAITINGTIME_END,
                c.CONF_SHADING_START_MAX_DURATION,
                c.CONF_SHADING_END_MAX_DURATION,
                c.CONF_SHADING_END_IMMEDIATE_BY_SUN_POSITION,
            }
        ),
        "tilt": frozenset(
            {
                c.CONF_SHADING_TILT_POSITION,
                c.CONF_SHADING_TILT_POSITION_0,
                c.CONF_SHADING_TILT_POSITION_1,
                c.CONF_SHADING_TILT_POSITION_2,
                c.CONF_SHADING_TILT_POSITION_3,
                c.CONF_SHADING_TILT_ELEVATION_1,
                c.CONF_SHADING_TILT_ELEVATION_2,
                c.CONF_SHADING_TILT_ELEVATION_3,
            }
        ),
        "independent_temperature": frozenset(
            {
                c.CONF_SHADING_INDEPENDENT_TEMP,
                c.CONF_SHADING_INDEPENDENT_HOLDS_END,
            }
        ),
    },
    c.PROFILE_TYPE_BEHAVIOR: {
        "cover_positions": frozenset(
            {
                c.CONF_COVER_TYPE,
                c.CONF_OPEN_POSITION,
                c.CONF_CLOSE_POSITION,
                c.CONF_VENTILATE_POSITION,
                c.CONF_LOCKOUT_POSITION,
                c.CONF_POSITION_TOLERANCE,
            }
        ),
        "manual_override": frozenset(
            {
                c.CONF_MANUAL_OVERRIDE_MINUTES,
                c.CONF_MANUAL_OVERRIDE_RESET_MODE,
                c.CONF_MANUAL_OVERRIDE_RESET_TIME,
                c.CONF_MANUAL_OVERRIDE_BLOCK_OPEN,
                c.CONF_MANUAL_OVERRIDE_BLOCK_CLOSE,
                c.CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE,
                c.CONF_MANUAL_OVERRIDE_BLOCK_SHADING,
                c.CONF_MANUAL_SCHEDULE_ADOPTION,
            }
        ),
        "ventilation": frozenset(
            {
                c.CONF_AUTO_VENTILATE,
                c.CONF_CONTACT_TRIGGER_DELAY,
                c.CONF_CONTACT_STATUS_DELAY,
                c.CONF_VENTILATION_DELAY_AFTER_CLOSE,
                c.CONF_VENTILATION_ALLOW_HIGHER_POSITION,
                c.CONF_VENTILATION_USE_AFTER_SHADING,
                c.CONF_VENTILATION_START_NO_DELAY,
                c.CONF_VENTILATION_KEEP_OPEN_ON_FULL_TO_TILT,
                c.CONF_SHADING_OVER_VENTILATION,
                c.CONF_LOCKOUT_TILT_CLOSE,
                c.CONF_LOCKOUT_TILT_SHADING_START,
                c.CONF_LOCKOUT_TILT_SHADING_END,
            }
        ),
        "resident": frozenset(
            {
                c.CONF_RESIDENT_STATUS,
                c.CONF_RESIDENT_OPEN_ENABLED,
                c.CONF_RESIDENT_CLOSE_ENABLED,
                c.CONF_RESIDENT_ALLOW_SHADING,
                c.CONF_RESIDENT_ALLOW_OPEN,
                c.CONF_RESIDENT_ALLOW_VENTILATION,
            }
        ),
        "movement_protection": frozenset(
            {
                c.CONF_PREVENT_HIGHER_POSITION_CLOSING,
                c.CONF_PREVENT_LOWERING_WHEN_CLOSING_IF_SHADED,
                c.CONF_PREVENT_SHADING_END_IF_CLOSED,
                c.CONF_PREVENT_OPENING_AFTER_SHADING_END,
                c.CONF_PREVENT_OPENING_AFTER_VENTILATION_END,
                c.CONF_PREVENT_OPENING_MULTIPLE_TIMES,
                c.CONF_PREVENT_CLOSING_MULTIPLE_TIMES,
                c.CONF_PREVENT_SHADING_MULTIPLE_TIMES,
                c.CONF_PREVENT_DEFAULT_COVER_ACTIONS,
            }
        ),
        "tilt_behavior": frozenset(
            {
                c.CONF_OPEN_TILT_POSITION,
                c.CONF_CLOSE_TILT_POSITION,
                c.CONF_VENTILATE_TILT_POSITION,
                c.CONF_COVER_TILT_WAIT_MODE,
                c.CONF_COVER_TILT_WAIT_TIMEOUT,
                c.CONF_ENABLE_LOGBOOK_COVER,
            }
        ),
    },
}


@dataclass(frozen=True)
class ProfileFieldMetadata:
    """Canonical ownership metadata shared by profile and override forms."""

    key: str
    profile_type: str
    capability: str
    group: str
    value_type: str
    unit: str | None
    override_allowed: bool = True
    owner: str = "PROFILE"
    feature: str | None = None
    ui_level: str = "advanced"
    selector: str | None = None
    default: Any = None
    source_scope: str = "profile"


def _build_profile_field_metadata() -> dict[str, ProfileFieldMetadata]:
    basic_fields = {
        c.CONF_AUTO_TIME,
        c.CONF_TIME_UP_EARLY_WORKDAY,
        c.CONF_TIME_UP_LATE_WORKDAY,
        c.CONF_TIME_UP_EARLY_NON_WORKDAY,
        c.CONF_TIME_UP_LATE_NON_WORKDAY,
        c.CONF_TIME_DOWN_EARLY_WORKDAY,
        c.CONF_TIME_DOWN_LATE_WORKDAY,
        c.CONF_TIME_DOWN_EARLY_NON_WORKDAY,
        c.CONF_TIME_DOWN_LATE_NON_WORKDAY,
        c.CONF_AUTO_BRIGHTNESS,
        c.CONF_BRIGHTNESS_OPEN_ABOVE,
        c.CONF_BRIGHTNESS_CLOSE_BELOW,
        c.CONF_AUTO_SUN,
        c.CONF_SUN_ELEVATION_OPEN,
        c.CONF_SUN_ELEVATION_CLOSE,
        c.CONF_AUTO_SHADING,
        c.CONF_SHADING_POSITION,
        c.CONF_AUTO_VENTILATE,
        c.CONF_VENTILATE_POSITION,
        c.CONF_VENTILATE_TILT_POSITION,
        c.CONF_RESIDENT_STATUS,
        c.CONF_RESIDENT_OPEN_ENABLED,
        c.CONF_RESIDENT_CLOSE_ENABLED,
        c.CONF_RESIDENT_ALLOW_OPEN,
        c.CONF_RESIDENT_ALLOW_SHADING,
        c.CONF_RESIDENT_ALLOW_VENTILATION,
    }
    groups = {
        profile_type: {
            key: group
            for group, keys in profile_groups
            for key in keys
        }
        for profile_type, profile_groups in _PROFILE_GROUPS.items()
    }
    metadata: dict[str, ProfileFieldMetadata] = {}

    def value_type(key: str) -> str:
        if key in _BOOLEAN_KEYS:
            return "boolean"
        if key in _TIME_KEYS:
            return "time"
        if key in _MULTI_SELECTS:
            return "multi_select"
        if key in _SELECTS:
            return "select"
        if key in _TEXT_KEYS:
            return "text"
        return "number"

    def unit(key: str) -> str | None:
        if key in _POSITION_KEYS or key == c.CONF_POSITION_TOLERANCE:
            return "%"
        if key in _DURATION_KEYS:
            return "s"
        if key == c.CONF_MANUAL_OVERRIDE_MINUTES:
            return "min"
        if key in _TEMPERATURE_KEYS or key in _TEMPERATURE_HYSTERESIS_KEYS:
            return "°C"
        if key in _ELEVATION_KEYS:
            return "°"
        if key in _BRIGHTNESS_KEYS:
            return "lx"
        return None

    for profile_type, capabilities in PROFILE_CAPABILITY_KEYS.items():
        for capability, keys in capabilities.items():
            for key in keys:
                selector_type = value_type(key)
                metadata[key] = ProfileFieldMetadata(
                    key=key,
                    profile_type=profile_type,
                    capability=capability,
                    group=groups[profile_type][key],
                    value_type=selector_type,
                    unit=unit(key),
                    feature=profile_type,
                    ui_level="basic" if key in basic_fields else "advanced",
                    selector=selector_type,
                )
    return metadata


PROFILE_FIELD_METADATA = _build_profile_field_metadata()


def capability_keys(profile_type: str, capabilities: Iterable[str]) -> frozenset[str]:
    """Return canonical keys owned by the selected capabilities."""

    selected = set(capabilities)
    return frozenset(
        key
        for key, metadata in PROFILE_FIELD_METADATA.items()
        if metadata.profile_type == profile_type
        and metadata.capability in selected
    )


def infer_capabilities(profile_type: str, settings: Mapping[str, Any]) -> list[str]:
    """Infer legacy profile metadata without changing effective values."""

    configured = set(settings)
    return [
        capability
        for capability, keys in PROFILE_CAPABILITY_KEYS[profile_type].items()
        if configured & keys
    ]


def _number_selector(
    minimum: float,
    maximum: float,
    step: float,
    unit: str | None = None,
) -> selector.NumberSelector:
    config: selector.NumberSelectorConfig = {
        "min": minimum,
        "max": maximum,
        "step": step,
        "mode": selector.NumberSelectorMode.BOX,
    }
    if unit:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(config)


def _time_default(value: Any) -> Any:
    if isinstance(value, time):
        return value
    parsed = dt_util.parse_time(str(value)) if value not in (None, "") else None
    return parsed or time(0, 0)


def _field_validator(key: str, value: Any, *, stored: bool) -> tuple[Any, Any]:
    """Return voluptuous marker and native selector for one canonical key."""

    def marker(default: Any) -> vol.Optional:
        if stored:
            return vol.Optional(key, default=default)
        if value is not None:
            return vol.Optional(key, description={"suggested_value": default})
        return vol.Optional(key)

    if key in _BOOLEAN_KEYS:
        return marker(bool(value)), bool
    if key in _TIME_KEYS:
        return marker(_time_default(value)), selector.TimeSelector()
    if key in _POSITION_KEYS:
        return marker(int(value or 0)), _number_selector(0, 100, 1, "%")
    if key == c.CONF_POSITION_TOLERANCE:
        return marker(int(value or 0)), _number_selector(0, 20, 1, "%")
    if key == c.CONF_MANUAL_OVERRIDE_MINUTES:
        return marker(int(value or 0)), _number_selector(0, 10080, 1, "min")
    if key in _DURATION_KEYS:
        return marker(float(value or 0)), _number_selector(0, 86400, 1, "s")
    if key in _TEMPERATURE_KEYS:
        return marker(float(value or 0)), _number_selector(-50, 100, 0.1, "°C")
    if key in _TEMPERATURE_HYSTERESIS_KEYS:
        return marker(float(value or 0)), _number_selector(0, 20, 0.1, "°C")
    if key in _ELEVATION_KEYS:
        return marker(float(value or 0)), _number_selector(-90, 90, 0.1, "°")
    if key in _BRIGHTNESS_KEYS:
        return marker(float(value or 0)), _number_selector(0, 200000, 1, "lx")
    if key in _MULTI_SELECTS:
        options, translation_key = _MULTI_SELECTS[key]
        return marker(list(value or [])), selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=options,
                multiple=True,
                translation_key=translation_key,
            )
        )
    if key in _SELECTS:
        options, translation_key = _SELECTS[key]
        default = value if value in options else options[0]
        return marker(default), selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=options,
                translation_key=translation_key,
            )
        )
    if key in _TEXT_KEYS:
        return marker(str(value or "")), selector.TextSelector()
    raise ValueError(f"No native profile selector for {key}")


def profile_groups(profile_type: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return canonical UI groups, ensuring every supported key is reachable."""

    groups = _PROFILE_GROUPS[profile_type]
    grouped = {key for _name, keys in groups for key in keys}
    missing = PROFILE_KEYS[profile_type] - grouped
    extra = grouped - PROFILE_KEYS[profile_type]
    if missing or extra:
        raise ValueError(
            f"Profile schema mismatch for {profile_type}: missing={missing}, extra={extra}"
        )
    return groups


def build_profile_schema(
    profile_type: str,
    stored: Mapping[str, Any],
    fallbacks: Mapping[str, Any],
    *,
    profile_name: str | None = None,
    field_selection: str | None = CONF_PROFILE_FIELDS,
    allowed_keys: Iterable[str] | None = None,
) -> vol.Schema:
    """Build typed, grouped schema while keeping persistence sparse."""

    allowed = frozenset(allowed_keys or PROFILE_KEYS[profile_type])
    schema: OrderedDict[Any, Any] = OrderedDict()
    if profile_name is not None:
        schema[vol.Required("profile_name", default=profile_name)] = selector.TextSelector()
    if field_selection is not None:
        schema[
            vol.Optional(
                field_selection,
                default=sorted(
                    key
                    for key in set(stored) & allowed
                    if stored.get(key) is not None
                ),
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=sorted(allowed),
                multiple=True,
                translation_key="profile_field",
            )
        )
    for group_name, keys in profile_groups(profile_type):
        fields: OrderedDict[Any, Any] = OrderedDict()
        for key in keys:
            if key not in allowed:
                continue
            has_stored_value = key in stored and stored.get(key) is not None
            marker, validator = _field_validator(
                key,
                stored[key] if has_stored_value else fallbacks.get(key),
                stored=has_stored_value,
            )
            fields[marker] = validator
        if fields:
            schema[vol.Optional(group_name)] = section(
                vol.Schema(fields), {"collapsed": True}
            )
    return vol.Schema(schema)


def extract_sparse_settings(
    user_input: Mapping[str, Any],
    profile_type: str,
    existing: Mapping[str, Any],
    *,
    field_selection: str | None = CONF_PROFILE_FIELDS,
    allowed_keys: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Keep selected known keys plus unknown legacy keys, never display defaults."""

    allowed = frozenset(allowed_keys or PROFILE_KEYS[profile_type])
    selected = (
        set(user_input.get(field_selection, [])) & allowed
        if field_selection is not None
        else set(allowed)
    )
    values: dict[str, Any] = {
        key: value
        for key, value in existing.items()
        if key not in PROFILE_KEYS[profile_type]
    }
    for key in selected:
        if key in user_input:
            values[key] = _json_safe(user_input[key])
    return values


def flatten_section_input(user_input: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten grouped profile form output for sparse extraction."""

    flattened: dict[str, Any] = {}
    for key, value in user_input.items():
        if key in {name for name, _keys in sum(_PROFILE_GROUPS.values(), ())} and isinstance(value, dict):
            flattened.update(value)
        else:
            flattened[key] = value
    return flattened


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value
