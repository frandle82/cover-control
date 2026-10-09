"""Computed profile summary placeholders for config flow descriptions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from . import const as c


SUMMARY_SECTIONS = (
    "time",
    "brightness",
    "sun",
    "shading",
    "ventilation",
    "resident",
    "behavior",
)


def profile_summary(profile: Mapping[str, Any], defaults: Mapping[str, Any]) -> dict[str, str]:
    """Return compact dynamic summary placeholders for one sparse profile."""

    settings = profile.get(c.CONF_PROFILE_SETTINGS, {})
    if not isinstance(settings, Mapping):
        settings = {}
    functions = profile.get(c.CONF_PROFILE_FUNCTIONS, [])
    summaries = {
        "profile_time_summary": profile_time_summary(settings, defaults),
        "profile_brightness_summary": profile_brightness_summary(settings, defaults),
        "profile_sun_summary": profile_sun_summary(settings, defaults),
        "profile_shading_summary": profile_shading_summary(settings, defaults),
        "profile_ventilation_summary": profile_ventilation_summary(settings, defaults),
        "profile_resident_summary": profile_resident_summary(settings, defaults),
        "profile_behavior_summary": profile_behavior_summary(settings, defaults),
    }
    return {
        "profile_configured_functions": ", ".join(map(str, functions)) or "-",
        "profile_summary": " | ".join(summaries.values()) or "-",
        **summaries,
    }


def profile_time_summary(settings: Mapping[str, Any], defaults: Mapping[str, Any]) -> str:
    return _lines(
        "time",
        settings,
        defaults,
        (
            ("workday_open", c.CONF_TIME_UP_EARLY_WORKDAY, c.CONF_TIME_UP_LATE_WORKDAY),
            ("workday_close", c.CONF_TIME_DOWN_EARLY_WORKDAY, c.CONF_TIME_DOWN_LATE_WORKDAY),
            ("free_open", c.CONF_TIME_UP_EARLY_NON_WORKDAY, c.CONF_TIME_UP_LATE_NON_WORKDAY),
            ("free_close", c.CONF_TIME_DOWN_EARLY_NON_WORKDAY, c.CONF_TIME_DOWN_LATE_NON_WORKDAY),
        ),
    )


def profile_brightness_summary(settings: Mapping[str, Any], defaults: Mapping[str, Any]) -> str:
    return _lines(
        "brightness",
        settings,
        defaults,
        (
            ("open_above", c.CONF_BRIGHTNESS_OPEN_ABOVE),
            ("close_below", c.CONF_BRIGHTNESS_CLOSE_BELOW),
            ("hysteresis", c.CONF_BRIGHTNESS_HYSTERESIS),
        ),
    )


def profile_sun_summary(settings: Mapping[str, Any], defaults: Mapping[str, Any]) -> str:
    return _lines(
        "sun",
        settings,
        defaults,
        (
            ("open_elevation", c.CONF_SUN_ELEVATION_OPEN),
            ("close_elevation", c.CONF_SUN_ELEVATION_CLOSE),
            ("mode", c.CONF_SUN_ELEVATION_MODE),
        ),
    )


def profile_shading_summary(settings: Mapping[str, Any], defaults: Mapping[str, Any]) -> str:
    return _lines(
        "shading",
        settings,
        defaults,
        (
            ("position", c.CONF_SHADING_POSITION),
            ("brightness_start", c.CONF_SHADING_BRIGHTNESS_START),
            ("min_temperature", c.CONF_SHADING_MIN_TEMPERATURE_1),
            ("waiting_end", c.CONF_SHADING_WAITINGTIME_END),
        ),
    )


def profile_ventilation_summary(settings: Mapping[str, Any], defaults: Mapping[str, Any]) -> str:
    return _lines(
        "ventilation",
        settings,
        defaults,
        (
            ("delay_after_close", c.CONF_VENTILATION_DELAY_AFTER_CLOSE),
            ("allow_higher_position", c.CONF_VENTILATION_ALLOW_HIGHER_POSITION),
            ("use_after_shading", c.CONF_VENTILATION_USE_AFTER_SHADING),
        ),
    )


def profile_resident_summary(settings: Mapping[str, Any], defaults: Mapping[str, Any]) -> str:
    return _lines(
        "resident",
        settings,
        defaults,
        (
            ("open_enabled", c.CONF_RESIDENT_OPEN_ENABLED),
            ("close_enabled", c.CONF_RESIDENT_CLOSE_ENABLED),
            ("allow_shading", c.CONF_RESIDENT_ALLOW_SHADING),
        ),
    )


def profile_behavior_summary(settings: Mapping[str, Any], defaults: Mapping[str, Any]) -> str:
    return _lines(
        "behavior",
        settings,
        defaults,
        (
            ("override_minutes", c.CONF_MANUAL_OVERRIDE_MINUTES),
            ("block_open", c.CONF_MANUAL_OVERRIDE_BLOCK_OPEN),
            ("block_close", c.CONF_MANUAL_OVERRIDE_BLOCK_CLOSE),
        ),
    )


def _lines(
    section: str,
    settings: Mapping[str, Any],
    defaults: Mapping[str, Any],
    items: tuple[tuple[str, str] | tuple[str, str, str], ...],
) -> str:
    rows = []
    for item in items:
        label = item[0]
        if len(item) == 3:
            first, second = item[1], item[2]
            value = f"{_value(settings, defaults, first)}-{_value(settings, defaults, second)}"
            source = _source(settings, first, second)
        else:
            key = item[1]
            value = _value(settings, defaults, key)
            source = _source(settings, key)
        rows.append(f"{label}={value} ({source})")
    return "; ".join(rows)


def _value(settings: Mapping[str, Any], defaults: Mapping[str, Any], key: str) -> Any:
    return settings[key] if key in settings else defaults.get(key, "-")


def _source(settings: Mapping[str, Any], *keys: str) -> str:
    return "profile" if any(key in settings for key in keys) else "default"
