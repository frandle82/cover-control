"""Shared parsing and persisted-status helpers."""

from __future__ import annotations

import logging
import re
from datetime import datetime, time

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

IDLE_REASON = "idle"
STORAGE_VERSION = 1
_LOGGER = logging.getLogger(__name__)

TRIGGER_BRIGHTNESS_CHANGED = "brightness_changed"
TRIGGER_BRIGHTNESS_CLOSE_TIMER = "brightness_close_duration_elapsed"
TRIGGER_BRIGHTNESS_OPEN_TIMER = "brightness_open_duration_elapsed"
TRIGGER_CALENDAR_CLOSE_END = "calendar_close_end"
TRIGGER_CALENDAR_CLOSE_START = "calendar_close_start"
TRIGGER_CALENDAR_OPEN_END = "calendar_open_end"
TRIGGER_CALENDAR_OPEN_START = "calendar_open_start"
TRIGGER_COVER_POSITION_CHANGED = "cover_position_changed"
TRIGGER_RESIDENT_OFF = "resident_off"
TRIGGER_RESIDENT_ON = "resident_on"
TRIGGER_SCHEDULED_CLOSE = "scheduled_close"
TRIGGER_SCHEDULED_FINAL_CLOSE = "scheduled_final_close"
TRIGGER_SCHEDULED_OPEN = "scheduled_open"
TRIGGER_SUNRISE_REACHED = "sunrise_reached"
TRIGGER_SUNSET_REACHED = "sunset_reached"
TRIGGER_GOLDEN_HOUR_OPEN_REACHED = "golden_hour_open_reached"
TRIGGER_GOLDEN_HOUR_CLOSE_REACHED = "golden_hour_close_reached"
TRIGGER_SHADING_END_CHANGED = "shading_end_condition_changed"
TRIGGER_SHADING_END_TIMER = "shading_end_timer"
TRIGGER_SHADING_START_CHANGED = "shading_start_condition_changed"
TRIGGER_SHADING_START_TIMER = "shading_start_timer"
TRIGGER_SUN_CHANGED = "sun_elevation_changed"
TRIGGER_SUN_CLOSE_TIMER = "sun_close_duration_elapsed"
TRIGGER_SUN_OPEN_TIMER = "sun_open_duration_elapsed"
TRIGGER_WINDOW_CLOSED = "window_closed"
TRIGGER_WINDOW_DOWN_SEQUENCE_TARGET_REACHED = (
    "window_down_sequence_target_reached"
)
TRIGGER_WINDOW_OPEN = "window_open"
TRIGGER_WINDOW_TILTED = "window_tilted"
TRIGGER_WORKDAY_CHANGED = "workday_changed"
TRIGGER_WORKDAY_TOMORROW_CHANGED = "workday_tomorrow_changed"
TRIGGER_FIRE_ALARM_ON = "fire_alarm_on"
TRIGGER_FIRE_ALARM_OFF = "fire_alarm_off"
TRIGGER_RAIN_ALARM_ON = "rain_alarm_on"
TRIGGER_RAIN_ALARM_OFF = "rain_alarm_off"
TRIGGER_WIND_ALARM_2_ON = "wind_alarm_2_on"
TRIGGER_WIND_ALARM_2_OFF = "wind_alarm_2_off"
TRIGGER_WIND_ALARM_1_ON = "wind_alarm_1_on"
TRIGGER_WIND_ALARM_1_OFF = "wind_alarm_1_off"
TRIGGER_FROST_ALARM_ON = "frost_alarm_on"
TRIGGER_FROST_ALARM_OFF = "frost_alarm_off"
TRIGGER_FIRE_LATCH_RESET = "fire_latch_reset"

WINDOW_DOWN_SEQUENCE_REASONS = frozenset(
    {"scheduled_close", "scheduled_final_close", "sun_close", "brightness_close"}
)


def scheduled_trigger(kind: str, mode: str) -> str:
    """Return a stable trigger identity for one scheduled mode event."""

    return {
        ("open", "sunrise"): TRIGGER_SUNRISE_REACHED,
        ("close", "sunset"): TRIGGER_SUNSET_REACHED,
        ("open", "golden_hour"): TRIGGER_GOLDEN_HOUR_OPEN_REACHED,
        ("close", "golden_hour"): TRIGGER_GOLDEN_HOUR_CLOSE_REACHED,
    }.get(
        (kind, mode),
        TRIGGER_SCHEDULED_OPEN if kind == "open" else TRIGGER_SCHEDULED_CLOSE,
    )

CONDITION_TIMER_TRIGGERS = {
    "sun_open": TRIGGER_SUN_OPEN_TIMER,
    "sun_close": TRIGGER_SUN_CLOSE_TIMER,
    "brightness_open": TRIGGER_BRIGHTNESS_OPEN_TIMER,
    "brightness_close": TRIGGER_BRIGHTNESS_CLOSE_TIMER,
}

CALENDAR_BOUNDARY_TRIGGERS = {
    "open_start": TRIGGER_CALENDAR_OPEN_START,
    "open_end": TRIGGER_CALENDAR_OPEN_END,
    "close_start": TRIGGER_CALENDAR_CLOSE_START,
    "close_end": TRIGGER_CALENDAR_CLOSE_END,
}

_TRIGGER_PRIORITY = {
    TRIGGER_FIRE_ALARM_ON: 20,
    TRIGGER_FIRE_ALARM_OFF: 20,
    TRIGGER_FIRE_LATCH_RESET: 20,
    TRIGGER_RAIN_ALARM_ON: 19,
    TRIGGER_RAIN_ALARM_OFF: 19,
    TRIGGER_WIND_ALARM_2_ON: 18,
    TRIGGER_WIND_ALARM_2_OFF: 18,
    TRIGGER_WIND_ALARM_1_ON: 17,
    TRIGGER_WIND_ALARM_1_OFF: 17,
    TRIGGER_FROST_ALARM_ON: 16,
    TRIGGER_FROST_ALARM_OFF: 16,
    TRIGGER_WINDOW_DOWN_SEQUENCE_TARGET_REACHED: 15,
    TRIGGER_SUN_CHANGED: 1,
    TRIGGER_SUN_OPEN_TIMER: 1,
    TRIGGER_SUN_CLOSE_TIMER: 1,
    TRIGGER_BRIGHTNESS_OPEN_TIMER: 1,
    TRIGGER_BRIGHTNESS_CLOSE_TIMER: 1,
    TRIGGER_CALENDAR_OPEN_START: 1,
    TRIGGER_CALENDAR_OPEN_END: 1,
    TRIGGER_CALENDAR_CLOSE_START: 1,
    TRIGGER_CALENDAR_CLOSE_END: 1,
    TRIGGER_SCHEDULED_OPEN: 2,
    TRIGGER_SUNRISE_REACHED: 2,
    TRIGGER_SUNSET_REACHED: 2,
    TRIGGER_GOLDEN_HOUR_OPEN_REACHED: 2,
    TRIGGER_GOLDEN_HOUR_CLOSE_REACHED: 2,
    TRIGGER_SCHEDULED_CLOSE: 2,
    TRIGGER_SCHEDULED_FINAL_CLOSE: 2,
    TRIGGER_SHADING_START_TIMER: 4,
    TRIGGER_SHADING_END_TIMER: 4,
    "startup": 2,
    "config_updated": 3,
    "toggle_time": 3,
    "toggle_sun": 3,
    "toggle_brightness": 3,
    "toggle_shading": 3,
    "toggle_ventilation": 3,
    "toggle_resident": 3,
    TRIGGER_WINDOW_OPEN: 4,
    TRIGGER_WINDOW_TILTED: 4,
    TRIGGER_WINDOW_CLOSED: 4,
    "manual_expired": 5,
    "manual_cleared": 6,
    "manual_service": 6,
    TRIGGER_RESIDENT_ON: 7,
    TRIGGER_RESIDENT_OFF: 7,
}

_FIRST_NUMBER_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


def _coerce_float(value: object) -> float | None:
    """Best-effort numeric conversion for config and sensor state values."""

    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None

    # Fast path for plain numeric strings.
    try:
        return float(text)
    except (TypeError, ValueError):
        pass

    # Locale-friendly decimal comma.
    if "," in text and "." not in text:
        try:
            return float(text.replace(",", "."))
        except (TypeError, ValueError):
            pass

    # Last resort: extract first numeric token (e.g. "1234 lx").
    match = _FIRST_NUMBER_RE.search(text)
    if not match:
        return None
    token = match.group(0).replace(",", ".")
    try:
        return float(token)
    except (TypeError, ValueError):
        return None


def _parse_time(value: str | datetime | None) -> time | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.timetz()
    parsed_datetime = dt_util.parse_datetime(value)
    if parsed_datetime:
        return parsed_datetime.timetz()
    try:
        return dt_util.parse_time(str(value))
    except (TypeError, ValueError):
        return None


def _float_state(hass: HomeAssistant, entity_id: str | None) -> float | None:
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None:
        return None
    return _coerce_float(state.state)


def _ts_now() -> int:
    return int(dt_util.utcnow().timestamp())


def _unique_covers(value: object) -> list[str]:
    if isinstance(value, str):
        covers = [value]
    elif isinstance(value, list):
        covers = value
    else:
        covers = list(value) if value else []

    unique: list[str] = []
    for cover in covers:
        if not isinstance(cover, str) or not cover:
            continue
        if cover not in unique:
            unique.append(cover)
    return unique


def _default_cover_status() -> dict:
    return {
        "v": 1,
        "open": {"active": False, "ts": 0},
        "close": {"active": False, "ts": 0},
        "shading": {"active": False, "start_pending": 0, "end_pending": 0, "ts": 0},
        "heat_protection": {"active": False, "hold": False},
        "ventilation": {
            "partial": False,
            "full": False,
            "restore_position": None,
            "background": {"open": False, "close": False, "shading": False},
            "ts": 0,
        },
        "force": {
            "active": False,
            "restore_position": None,
            "background": {"open": False, "close": False, "shading": False},
            "ts": 0,
        },
        "safety": {"fire_latched": False, "ts": 0},
        "manual": {"active": False, "scope_all": False, "until": None, "ts": 0},
        "reason": None,
        "target": None,
        "last_action_dates": {},
    }


def _normalize_cover_status(raw: object) -> dict:
    status = _default_cover_status()
    if not isinstance(raw, dict):
        return status

    for key in ("open", "close"):
        value = raw.get(key)
        if isinstance(value, dict):
            status[key]["active"] = bool(value.get("active", status[key]["active"]))
            status[key]["ts"] = int(value.get("ts") or 0)

    shading = raw.get("shading")
    if isinstance(shading, dict):
        status["shading"]["active"] = bool(shading.get("active", False))
        status["shading"]["start_pending"] = int(shading.get("start_pending") or 0)
        status["shading"]["end_pending"] = int(shading.get("end_pending") or 0)
        status["shading"]["ts"] = int(shading.get("ts") or 0)

    heat_protection = raw.get("heat_protection")
    if isinstance(heat_protection, dict):
        status["heat_protection"]["active"] = bool(
            heat_protection.get("active", False)
        )
        status["heat_protection"]["hold"] = bool(
            heat_protection.get("hold", False)
        )

    ventilation = raw.get("ventilation")
    if isinstance(ventilation, dict):
        status["ventilation"]["partial"] = bool(ventilation.get("partial", False))
        status["ventilation"]["full"] = bool(ventilation.get("full", False))
        status["ventilation"]["restore_position"] = _coerce_float(
            ventilation.get("restore_position")
        )
        background = ventilation.get("background")
        if isinstance(background, dict):
            for key in ("open", "close", "shading"):
                status["ventilation"]["background"][key] = bool(background.get(key))
        status["ventilation"]["ts"] = int(ventilation.get("ts") or 0)

    force = raw.get("force")
    if isinstance(force, dict):
        status["force"]["active"] = bool(force.get("active", False))
        status["force"]["restore_position"] = _coerce_float(
            force.get("restore_position")
        )
        background = force.get("background")
        if isinstance(background, dict):
            for key in ("open", "close", "shading"):
                status["force"]["background"][key] = bool(background.get(key))
        status["force"]["ts"] = int(force.get("ts") or 0)

    safety = raw.get("safety")
    if isinstance(safety, dict):
        status["safety"]["fire_latched"] = bool(safety.get("fire_latched", False))
        status["safety"]["ts"] = int(safety.get("ts") or 0)

    manual = raw.get("manual")
    if isinstance(manual, dict):
        status["manual"]["active"] = bool(manual.get("active", False))
        status["manual"]["scope_all"] = bool(manual.get("scope_all", False))
        until = manual.get("until")
        status["manual"]["until"] = until if isinstance(until, str) and until else None
        status["manual"]["ts"] = int(manual.get("ts") or 0)

    reason = raw.get("reason")
    status["reason"] = reason if isinstance(reason, str) and reason else None
    status["target"] = _coerce_float(raw.get("target"))

    dates = raw.get("last_action_dates")
    if isinstance(dates, dict):
        status["last_action_dates"] = {
            str(action): str(date_value)
            for action, date_value in dates.items()
            if action and date_value
        }
    return status
