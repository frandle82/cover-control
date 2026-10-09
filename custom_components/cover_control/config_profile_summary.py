"""Computed profile summary placeholders for config flow descriptions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from . import const as c


_FUNCTION_LABELS = {
    "en": {
        c.FUNCTION_TIME: "Time",
        c.FUNCTION_BRIGHTNESS: "Brightness",
        c.FUNCTION_SUN: "Sun position",
        c.FUNCTION_SHADING: "Shading",
        c.FUNCTION_VENTILATION: "Ventilation",
        c.FUNCTION_RESIDENT: "Resident",
        c.FUNCTION_BEHAVIOR: "Manual behavior",
    },
    "de": {
        c.FUNCTION_TIME: "Zeit",
        c.FUNCTION_BRIGHTNESS: "Helligkeit",
        c.FUNCTION_SUN: "Sonnenstand",
        c.FUNCTION_SHADING: "Beschattung",
        c.FUNCTION_VENTILATION: "Lüftung",
        c.FUNCTION_RESIDENT: "Bewohner",
        c.FUNCTION_BEHAVIOR: "Manuelles Verhalten",
    },
}

_TEXT = {
    "en": {
        "current": "Current setting",
        "profile": "profile value",
        "default": "default value",
        "yes": "Yes",
        "no": "No",
        "workday": "Workday",
        "free_day": "Day off",
        "open": "Open",
        "close": "Close",
        "open_above": "Open above",
        "close_below": "Close below",
        "hysteresis": "Hysteresis",
        "open_elevation": "Open above",
        "close_elevation": "Close below",
        "mode": "Mode",
        "position": "Position",
        "brightness_start": "Start brightness",
        "min_temperature": "Minimum temperature",
        "waiting_end": "End delay",
        "delay_after_close": "Delay after closing",
        "allow_higher_position": "Allow higher ventilation position",
        "use_after_shading": "Use after shading",
        "open_enabled": "Open when ending",
        "close_enabled": "Close when starting",
        "allow_shading": "Allow shading",
        "override_minutes": "Override duration",
        "block_open": "Block opening",
        "block_close": "Block closing",
    },
    "de": {
        "current": "Aktuelle Einstellung",
        "profile": "Profilwert",
        "default": "Standardwert",
        "yes": "Ja",
        "no": "Nein",
        "workday": "Arbeitstag",
        "free_day": "Freier Tag",
        "open": "Öffnen",
        "close": "Schließen",
        "open_above": "Öffnen ab",
        "close_below": "Schließen unter",
        "hysteresis": "Hysterese",
        "open_elevation": "Öffnen ab",
        "close_elevation": "Schließen unter",
        "mode": "Modus",
        "position": "Position",
        "brightness_start": "Start-Helligkeit",
        "min_temperature": "Mindesttemperatur",
        "waiting_end": "Endverzögerung",
        "delay_after_close": "Verzögerung nach Schließen",
        "allow_higher_position": "Höhere Lüftungsposition erlaubt",
        "use_after_shading": "Nach Beschattung verwenden",
        "open_enabled": "Öffnen bei Ende",
        "close_enabled": "Schließen bei Start",
        "allow_shading": "Beschattung erlaubt",
        "override_minutes": "Override-Dauer",
        "block_open": "Öffnen blockieren",
        "block_close": "Schließen blockieren",
    },
}


def profile_summary(
    profile: Mapping[str, Any],
    defaults: Mapping[str, Any],
    *,
    language: str | None = None,
) -> dict[str, str]:
    """Return dynamic, localized summary placeholders for one sparse profile."""

    lang = "de" if str(language or "").lower().startswith("de") else "en"
    settings = profile.get(c.CONF_PROFILE_SETTINGS, {})
    if not isinstance(settings, Mapping):
        settings = {}
    functions = [
        _FUNCTION_LABELS[lang].get(str(function), str(function))
        for function in profile.get(c.CONF_PROFILE_FUNCTIONS, [])
    ]
    summaries = {
        "profile_time_summary": profile_time_summary(settings, defaults, lang),
        "profile_brightness_summary": profile_brightness_summary(settings, defaults, lang),
        "profile_sun_summary": profile_sun_summary(settings, defaults, lang),
        "profile_shading_summary": profile_shading_summary(settings, defaults, lang),
        "profile_ventilation_summary": profile_ventilation_summary(settings, defaults, lang),
        "profile_resident_summary": profile_resident_summary(settings, defaults, lang),
        "profile_behavior_summary": profile_behavior_summary(settings, defaults, lang),
    }
    return {
        "profile_configured_functions": " · ".join(functions) or "-",
        "profile_summary": "\n\n".join(summaries.values()) or "-",
        **summaries,
    }


def profile_time_summary(
    settings: Mapping[str, Any], defaults: Mapping[str, Any], lang: str
) -> str:
    t = _TEXT[lang]
    return "\n".join(
        (
            t["current"],
            "",
            t["workday"],
            _range_line(t["open"], settings, defaults, c.CONF_TIME_UP_EARLY_WORKDAY, c.CONF_TIME_UP_LATE_WORKDAY, lang),
            _range_line(t["close"], settings, defaults, c.CONF_TIME_DOWN_EARLY_WORKDAY, c.CONF_TIME_DOWN_LATE_WORKDAY, lang),
            "",
            t["free_day"],
            _range_line(t["open"], settings, defaults, c.CONF_TIME_UP_EARLY_NON_WORKDAY, c.CONF_TIME_UP_LATE_NON_WORKDAY, lang),
            _range_line(t["close"], settings, defaults, c.CONF_TIME_DOWN_EARLY_NON_WORKDAY, c.CONF_TIME_DOWN_LATE_NON_WORKDAY, lang),
        )
    )


def profile_brightness_summary(
    settings: Mapping[str, Any], defaults: Mapping[str, Any], lang: str
) -> str:
    t = _TEXT[lang]
    return _summary_lines(
        lang,
        (
            (t["open_above"], _lux(_value(settings, defaults, c.CONF_BRIGHTNESS_OPEN_ABOVE)), _source(settings, lang, c.CONF_BRIGHTNESS_OPEN_ABOVE)),
            (t["close_below"], _lux(_value(settings, defaults, c.CONF_BRIGHTNESS_CLOSE_BELOW)), _source(settings, lang, c.CONF_BRIGHTNESS_CLOSE_BELOW)),
            (t["hysteresis"], _lux(_value(settings, defaults, c.CONF_BRIGHTNESS_HYSTERESIS)), _source(settings, lang, c.CONF_BRIGHTNESS_HYSTERESIS)),
        ),
    )


def profile_sun_summary(
    settings: Mapping[str, Any], defaults: Mapping[str, Any], lang: str
) -> str:
    t = _TEXT[lang]
    return _summary_lines(
        lang,
        (
            (t["open_elevation"], _degree(_value(settings, defaults, c.CONF_SUN_ELEVATION_OPEN)), _source(settings, lang, c.CONF_SUN_ELEVATION_OPEN)),
            (t["close_elevation"], _degree(_value(settings, defaults, c.CONF_SUN_ELEVATION_CLOSE)), _source(settings, lang, c.CONF_SUN_ELEVATION_CLOSE)),
            (t["mode"], str(_value(settings, defaults, c.CONF_SUN_ELEVATION_MODE)), _source(settings, lang, c.CONF_SUN_ELEVATION_MODE)),
        ),
    )


def profile_shading_summary(
    settings: Mapping[str, Any], defaults: Mapping[str, Any], lang: str
) -> str:
    t = _TEXT[lang]
    return _summary_lines(
        lang,
        (
            (t["position"], _percent(_value(settings, defaults, c.CONF_SHADING_POSITION)), _source(settings, lang, c.CONF_SHADING_POSITION)),
            (t["brightness_start"], _lux(_value(settings, defaults, c.CONF_SHADING_BRIGHTNESS_START)), _source(settings, lang, c.CONF_SHADING_BRIGHTNESS_START)),
            (t["min_temperature"], _degree_c(_value(settings, defaults, c.CONF_SHADING_MIN_TEMPERATURE_1)), _source(settings, lang, c.CONF_SHADING_MIN_TEMPERATURE_1)),
            (t["waiting_end"], _minutes(_value(settings, defaults, c.CONF_SHADING_WAITINGTIME_END)), _source(settings, lang, c.CONF_SHADING_WAITINGTIME_END)),
        ),
    )


def profile_ventilation_summary(
    settings: Mapping[str, Any], defaults: Mapping[str, Any], lang: str
) -> str:
    t = _TEXT[lang]
    return _summary_lines(
        lang,
        (
            (t["delay_after_close"], _seconds(_value(settings, defaults, c.CONF_VENTILATION_DELAY_AFTER_CLOSE)), _source(settings, lang, c.CONF_VENTILATION_DELAY_AFTER_CLOSE)),
            (t["allow_higher_position"], _yes_no(_value(settings, defaults, c.CONF_VENTILATION_ALLOW_HIGHER_POSITION), lang), _source(settings, lang, c.CONF_VENTILATION_ALLOW_HIGHER_POSITION)),
            (t["use_after_shading"], _yes_no(_value(settings, defaults, c.CONF_VENTILATION_USE_AFTER_SHADING), lang), _source(settings, lang, c.CONF_VENTILATION_USE_AFTER_SHADING)),
        ),
    )


def profile_resident_summary(
    settings: Mapping[str, Any], defaults: Mapping[str, Any], lang: str
) -> str:
    t = _TEXT[lang]
    return _summary_lines(
        lang,
        (
            (t["open_enabled"], _yes_no(_value(settings, defaults, c.CONF_RESIDENT_OPEN_ENABLED), lang), _source(settings, lang, c.CONF_RESIDENT_OPEN_ENABLED)),
            (t["close_enabled"], _yes_no(_value(settings, defaults, c.CONF_RESIDENT_CLOSE_ENABLED), lang), _source(settings, lang, c.CONF_RESIDENT_CLOSE_ENABLED)),
            (t["allow_shading"], _yes_no(_value(settings, defaults, c.CONF_RESIDENT_ALLOW_SHADING), lang), _source(settings, lang, c.CONF_RESIDENT_ALLOW_SHADING)),
        ),
    )


def profile_behavior_summary(
    settings: Mapping[str, Any], defaults: Mapping[str, Any], lang: str
) -> str:
    t = _TEXT[lang]
    return _summary_lines(
        lang,
        (
            (t["override_minutes"], _minutes(_value(settings, defaults, c.CONF_MANUAL_OVERRIDE_MINUTES)), _source(settings, lang, c.CONF_MANUAL_OVERRIDE_MINUTES)),
            (t["block_open"], _yes_no(_value(settings, defaults, c.CONF_MANUAL_OVERRIDE_BLOCK_OPEN), lang), _source(settings, lang, c.CONF_MANUAL_OVERRIDE_BLOCK_OPEN)),
            (t["block_close"], _yes_no(_value(settings, defaults, c.CONF_MANUAL_OVERRIDE_BLOCK_CLOSE), lang), _source(settings, lang, c.CONF_MANUAL_OVERRIDE_BLOCK_CLOSE)),
        ),
    )


def _summary_lines(lang: str, rows: tuple[tuple[str, str, str], ...]) -> str:
    return "\n".join(
        [_TEXT[lang]["current"], "", *(f"{label}: {value} · {source}" for label, value, source in rows)]
    )


def _range_line(
    label: str,
    settings: Mapping[str, Any],
    defaults: Mapping[str, Any],
    first: str,
    second: str,
    lang: str,
) -> str:
    return (
        f"{label}: {_format_time(_value(settings, defaults, first))}-"
        f"{_format_time(_value(settings, defaults, second))} · "
        f"{_source(settings, lang, first, second)}"
    )


def _value(settings: Mapping[str, Any], defaults: Mapping[str, Any], key: str) -> Any:
    return settings[key] if key in settings else defaults.get(key, "-")


def _source(settings: Mapping[str, Any], lang: str, *keys: str) -> str:
    return _TEXT[lang]["profile" if any(key in settings for key in keys) else "default"]


def _format_time(value: Any) -> str:
    text = str(value)
    return text.removesuffix(":00") if text.count(":") == 2 else text


def _format_number(value: Any) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}".replace(",", ".")
    if isinstance(value, float) and value.is_integer():
        return f"{int(value):,}".replace(",", ".")
    return str(value)


def _lux(value: Any) -> str:
    return f"{_format_number(value)} lx"


def _degree(value: Any) -> str:
    return f"{_format_number(value)}°"


def _degree_c(value: Any) -> str:
    return f"{_format_number(value)} °C"


def _percent(value: Any) -> str:
    return f"{_format_number(value)} %"


def _minutes(value: Any) -> str:
    return f"{_format_number(value)} min"


def _seconds(value: Any) -> str:
    return f"{_format_number(value)} s"


def _yes_no(value: Any, lang: str) -> str:
    return _TEXT[lang]["yes" if bool(value) else "no"]
