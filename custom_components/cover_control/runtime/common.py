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

_TRIGGER_PRIORITY = {
    "state": 0,
    "time": 1,
    "startup": 2,
    "config": 3,
    "runtime_toggle": 3,
    "contact": 4,
    "manual_expired": 5,
    "manual_cleared": 6,
    "manual_service": 6,
    "resident_asleep": 7,
    "resident_woke": 7,
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
