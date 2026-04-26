"""Core controller logic derived from the Cover Control Automation blueprint."""
from __future__ import annotations

import asyncio
import logging
import re
from inspect import isawaitable
from datetime import datetime, timedelta, time
from typing import Callable

from astral import LocationInfo
from astral.sun import SunDirection, time_at_elevation

from homeassistant.components.cover import CoverEntityFeature
from homeassistant import config_entries
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Context, CALLBACK_TYPE, HomeAssistant, State, callback
from homeassistant.helpers import condition, entity_registry as er
from homeassistant.exceptions import ConditionError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_BRIGHTNESS_ENTITY,
    CONF_AUTO_DOWN,
    CONF_AUTO_DOWN_ENTITY,
    CONF_AUTO_SHADING,
    CONF_AUTO_SHADING_ENTITY,
    CONF_AUTO_SUN,
    CONF_AUTO_SUN_ENTITY,
    CONF_AUTO_TIME,
    CONF_AUTO_UP,
    CONF_AUTO_UP_ENTITY,
    CONF_AUTO_VENTILATE,
    CONF_AUTO_VENTILATE_ENTITY,
    CONF_ADDITIONAL_CONDITION_CLOSE,
    CONF_ADDITIONAL_CONDITION_GLOBAL,
    CONF_ADDITIONAL_CONDITION_OPEN,
    CONF_ADDITIONAL_CONDITION_SHADING,
    CONF_ADDITIONAL_CONDITION_SHADING_END,
    CONF_ADDITIONAL_CONDITION_SHADING_TILT,
    CONF_ADDITIONAL_CONDITION_VENTILATE,
    CONF_ADDITIONAL_CONDITION_VENTILATE_END,
    CONF_ADDITIONAL_CONDITIONS_ENABLED,
    CONF_BRIGHTNESS_CLOSE_BELOW,
    CONF_BRIGHTNESS_HYSTERESIS,
    CONF_BRIGHTNESS_OPEN_ABOVE,
    CONF_BRIGHTNESS_SENSOR,
    CONF_BRIGHTNESS_TIME_DURATION,
    CONF_CALENDAR_CLOSE_TITLE,
    CONF_CALENDAR_ENTITY,
    CONF_CALENDAR_OPEN_TITLE,
    CONF_CLOSE_POSITION,
    CONF_COVERS,
    CONF_CONTACT_STATUS_DELAY,
    CONF_CONTACT_TRIGGER_DELAY,
    CONF_COVER_TYPE,
    CONF_COVER_TYPE_AWNING,
    CONF_LOCKOUT_TILT_CLOSE,
    CONF_LOCKOUT_TILT_SHADING_END,
    CONF_LOCKOUT_TILT_SHADING_START,
    CONF_MANUAL_OVERRIDE_MINUTES,
    CONF_MANUAL_OVERRIDE_BLOCK_CLOSE,
    CONF_MANUAL_OVERRIDE_BLOCK_OPEN,
    CONF_MANUAL_OVERRIDE_BLOCK_SHADING,
    CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE,
    CONF_MANUAL_OVERRIDE_RESET_MODE,
    CONF_MANUAL_OVERRIDE_RESET_TIME,
    CONF_MASTER_ENABLED,
    CONF_OPEN_POSITION,
    CONF_POSITION_TOLERANCE,
    CONF_PREVENT_CLOSING_MULTIPLE_TIMES,
    CONF_PREVENT_HIGHER_POSITION_CLOSING,
    CONF_PREVENT_LOWERING_WHEN_CLOSING_IF_SHADED,
    CONF_PREVENT_OPENING_AFTER_SHADING_END,
    CONF_PREVENT_OPENING_AFTER_VENTILATION_END,
    CONF_PREVENT_OPENING_MULTIPLE_TIMES,
    CONF_PREVENT_SHADING_END_IF_CLOSED,
    CONF_PREVENT_SHADING_MULTIPLE_TIMES,
    CONF_RESIDENT_STATUS,
    CONF_RESIDENT_SENSOR,
    CONF_RESIDENT_OPEN_ENABLED,
    CONF_RESIDENT_CLOSE_ENABLED,
    CONF_RESIDENT_ALLOW_SHADING,
    CONF_RESIDENT_ALLOW_OPEN,
    CONF_RESIDENT_ALLOW_VENTILATION,
    CONF_SHADING_FORECAST_SENSOR,
    CONF_SHADING_FORECAST_TYPE,
    CONF_SHADING_WEATHER_CONDITIONS,
    CONF_SHADING_BRIGHTNESS_END,
    CONF_SHADING_BRIGHTNESS_START,
    CONF_SHADING_END_IMMEDIATE_BY_SUN_POSITION,
    CONF_SHADING_POSITION,
    CONF_SHADING_START_MAX_DURATION,
    CONF_SHADING_WAITINGTIME_END,
    CONF_SHADING_WAITINGTIME_START,
    CONF_SUN_AZIMUTH_END,
    CONF_SUN_AZIMUTH_START,
    CONF_SUN_ELEVATION_CLOSE,
    CONF_SUN_ELEVATION_MAX,
    CONF_SUN_ELEVATION_MIN,
    CONF_SUN_ELEVATION_OPEN,
    CONF_SUN_ELEVATION_MODE,
    CONF_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR,
    CONF_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR,
    CONF_SUN_TIME_DURATION,
    CONF_TEMPERATURE_FORECAST_THRESHOLD,
    CONF_TEMPERATURE_SENSOR_INDOOR,
    CONF_TEMPERATURE_SENSOR_OUTDOOR,
    CONF_TEMPERATURE_THRESHOLD,
    CONF_TIME_DOWN_EARLY_NON_WORKDAY,
    CONF_TIME_DOWN_EARLY_WORKDAY,
    CONF_TIME_DOWN_LATE_NON_WORKDAY,
    CONF_TIME_DOWN_LATE_WORKDAY,
    CONF_TIME_UP_EARLY_NON_WORKDAY,
    CONF_TIME_UP_EARLY_WORKDAY,
    CONF_TIME_UP_LATE_NON_WORKDAY,
    CONF_TIME_UP_LATE_WORKDAY,
    CONF_VENTILATION_ALLOW_HIGHER_POSITION,
    CONF_VENTILATION_DELAY_AFTER_CLOSE,
    CONF_VENTILATION_USE_AFTER_SHADING,
    CONF_VENTILATE_POSITION,
    CONF_WINDOW_SENSOR_FULL,
    CONF_WINDOW_SENSOR_TILT,
    CONF_WORKDAY_SENSOR,
    CONF_WORKDAY_TOMORROW_SENSOR,
    DEFAULT_AUTOMATION_FLAGS,
    DEFAULT_BEHAVIOR_SETTINGS,
    DEFAULT_BRIGHTNESS_CLOSE,
    DEFAULT_BRIGHTNESS_HYSTERESIS,
    DEFAULT_BRIGHTNESS_OPEN,
    DEFAULT_BRIGHTNESS_TIME_DURATION,
    DEFAULT_MANUAL_OVERRIDE_MINUTES,
    DEFAULT_MANUAL_OVERRIDE_FLAGS,
    DEFAULT_MANUAL_OVERRIDE_RESET_TIME,
    DEFAULT_MASTER_FLAGS,
    DEFAULT_POSITION_SETTINGS,
    DEFAULT_TIME_SETTINGS,
    DEFAULT_OPEN_POSITION,
    DEFAULT_TOLERANCE,
    DEFAULT_VENTILATE_POSITION,
    DEFAULT_SHADING_POSITION,
    DEFAULT_CLOSE_POSITION,
    DEFAULT_SHADING_BRIGHTNESS_END,
    DEFAULT_SHADING_BRIGHTNESS_START,
    DEFAULT_SHADING_FORECAST_TYPE,
    DEFAULT_SHADING_TIMING_SETTINGS,
    DEFAULT_SUN_ELEVATION_MODE,
    DEFAULT_SUN_ELEVATION_OPEN,
    DEFAULT_SUN_ELEVATION_CLOSE,
    DEFAULT_SUN_TIME_DURATION,
    DOMAIN,
    SIGNAL_STATE_UPDATED,
    MANUAL_OVERRIDE_RESET_NONE,
    MANUAL_OVERRIDE_RESET_TIME,
    MANUAL_OVERRIDE_RESET_TIMEOUT,
    EVENT_COVER_CONTROL,
)

IDLE_REASON = "idle"
STORAGE_VERSION = 1
_LOGGER = logging.getLogger(__name__)

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
        status["ventilation"]["ts"] = int(ventilation.get("ts") or 0)

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


class ControllerManager:
    """Create and coordinate per-cover controllers."""

    def __init__(self, hass: HomeAssistant, entry: config_entries.ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.controllers: dict[str, CoverController] = {}
        # Runtime-only feature overrides controlled by integration switch entities.
        # None/absent => follow persisted config flow options.
        self._runtime_toggles: dict[str, bool] = {}
        self._store: Store | None = None
        self._stored_state: dict = {"covers": {}}

    async def async_setup(self) -> None:
        self._store = Store(
            self.hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{self.entry.entry_id}.cover_status",
        )
        loaded = await self._store.async_load()
        if isinstance(loaded, dict):
            self._stored_state = loaded
        self._stored_state.setdefault("covers", {})

        data = {
            **DEFAULT_POSITION_SETTINGS,
            **DEFAULT_TIME_SETTINGS,
            **DEFAULT_AUTOMATION_FLAGS,
            **DEFAULT_MANUAL_OVERRIDE_FLAGS,
            **DEFAULT_BEHAVIOR_SETTINGS,
            **self.entry.data,
            **self.entry.options,
        }
        for cover in data.get(CONF_COVERS, []):
            controller = CoverController(
                self.hass,
                self.entry,
                cover,
                data,
                self._stored_state["covers"].get(cover),
                self._store_cover_status,
            )
            await controller.async_setup()
            self.controllers[cover] = controller

    async def async_unload(self) -> None:
        for controller in self.controllers.values():
            controller.persist_status()
            await controller.async_unload()
        if self._store:
            await self._store.async_save(self._stored_state)
        self.controllers.clear()

    @callback
    def _store_cover_status(self, cover: str, status: dict) -> None:
        self._stored_state.setdefault("covers", {})[cover] = status
        if self._store:
            self._store.async_delay_save(lambda: self._stored_state, 1)

    @callback
    def async_update_options(self) -> None:
        new_data = {
            **DEFAULT_POSITION_SETTINGS,
            **DEFAULT_TIME_SETTINGS,
            **DEFAULT_AUTOMATION_FLAGS,
            **DEFAULT_MANUAL_OVERRIDE_FLAGS,
            **DEFAULT_BEHAVIOR_SETTINGS,
            **self.entry.data,
            **self.entry.options,
        }
        for controller in self.controllers.values():
            controller.update_config(new_data)

    def set_manual_override(self, cover: str, minutes: int) -> bool:
        controller = self.controllers.get(cover)
        if not controller:
            return False
        controller.set_manual_override(minutes)
        return True

    @callback
    def get_runtime_toggle(self, key: str) -> bool | None:
        """Return runtime override for a feature toggle, if present."""

        return self._runtime_toggles.get(key)

    @callback
    def set_runtime_toggle(self, key: str, enabled: bool) -> None:
        """Set runtime-only feature toggle and re-evaluate all controllers."""

        self._runtime_toggles[key] = bool(enabled)
        for controller in self.controllers.values():
            controller.async_request_evaluate("runtime_toggle")

    @callback
    def clear_runtime_toggle(self, key: str) -> None:
        """Clear runtime override so persisted config controls the feature again."""

        if key in self._runtime_toggles:
            self._runtime_toggles.pop(key, None)
            for controller in self.controllers.values():
                controller.async_request_evaluate("runtime_toggle")

    def activate_shading(self, cover: str, minutes: int | None) -> bool:
        controller = self.controllers.get(cover)
        if not controller:
            return False
        controller.activate_shading(minutes)
        return True

    def clear_manual_override(self, cover: str) -> bool:
        controller = self.controllers.get(cover)
        if not controller:
            return False
        controller.clear_manual_override()
        return True

    def clear_all_manual_overrides(self) -> None:
        """Clear manual override state for every cover in this entry."""

        for controller in self.controllers.values():
            controller.clear_manual_override()

    async def recalibrate_cover(self, cover: str, full_open: float | None) -> bool:
        controller = self.controllers.get(cover)
        if not controller:
            return False
        await controller.recalibrate(full_open)
        return True

    async def recalibrate_all(self, full_open: float | None = None) -> None:
        """Recalibrate every cover in this entry sequentially."""

        for controller in self.controllers.values():
            await controller.recalibrate(full_open)

    async def force_action(self, cover: str, action: str) -> bool:
        controller = self.controllers.get(cover)
        if not controller:
            return False

        if action in {"open", "close"}:
            await controller.force_move(action)
            return True
        if action in {"ventilate_start", "ventilate_stop"}:
            await controller.force_ventilation(
                "start" if action == "ventilate_start" else "stop"
            )
            return True
        if action in {"shading_activate", "shading_deactivate"}:
            await controller.force_shading(
                "activate" if action == "shading_activate" else "deactivate"
            )
            return True

        return False

    def state_snapshot(
        self, cover: str
        ) -> tuple[
            float | None,
            str | None,
            datetime | None,
            bool,
            datetime | None,
            datetime | None,
            float | None,
            bool,
            bool,
            bool,
        ] | None:
            controller = self.controllers.get(cover)
            if not controller:
                return (
                    False,
                    IDLE_REASON,
                    None,
                    None,
                    False,
                    None,
                    None,
                    False,
                    False,
                    False,
                )
            return controller.state_snapshot()

class CoverController:
    """Translate blueprint-style parameters into runtime cover control."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: config_entries.ConfigEntry,
        cover: str,
        config: ConfigType,
        persisted_status: object = None,
        persist_callback: Callable[[str, dict], None] | None = None,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.cover = cover
        self.config = config
        self._persist_callback = persist_callback
        self._status = _normalize_cover_status(persisted_status)
        self._unsubs: list[CALLBACK_TYPE] = []
        self._manual_until: datetime | None = None
        self._manual_active: bool = False
        self._manual_scope_all: bool = False
        self._target: float | None = None
        self._last_position: float | None = None
        self._pre_ventilation_position: float | None = None
        self._last_command_at: datetime | None = None
        self._manual_expire_unsub: CALLBACK_TYPE | None = None
        self._last_command_context_id: str | None = None
        self._reason: str | None = None
        self._next_open: datetime | None = None
        self._next_close: datetime | None = None
        self._master_entity_id: str | None = None
        self._condition_since: dict[str, datetime] = {}
        self._last_action_dates: dict[str, datetime.date] = {}
        self._hydrate_persistent_status()
        self._auto_entity_map = {
            CONF_AUTO_UP: CONF_AUTO_UP_ENTITY,
            CONF_AUTO_DOWN: CONF_AUTO_DOWN_ENTITY,
            CONF_AUTO_BRIGHTNESS: CONF_AUTO_BRIGHTNESS_ENTITY,
            CONF_AUTO_SUN: CONF_AUTO_SUN_ENTITY,
            CONF_AUTO_VENTILATE: CONF_AUTO_VENTILATE_ENTITY,
            CONF_AUTO_SHADING: CONF_AUTO_SHADING_ENTITY,
        }

    def _hydrate_persistent_status(self) -> None:
        target = _coerce_float(self._status.get("target"))
        self._target = target
        reason = self._status.get("reason")
        self._reason = reason if isinstance(reason, str) and reason else None

        ventilation = self._status.get("ventilation", {})
        if isinstance(ventilation, dict):
            self._pre_ventilation_position = _coerce_float(
                ventilation.get("restore_position")
            )

        manual = self._status.get("manual", {})
        if isinstance(manual, dict):
            until_raw = manual.get("until")
            until = dt_util.parse_datetime(until_raw) if until_raw else None
            if until:
                until = dt_util.as_utc(until)
            self._manual_until = until
            self._manual_active = bool(manual.get("active") and (until is None or until > dt_util.utcnow()))
            self._manual_scope_all = bool(manual.get("scope_all"))
            if not self._manual_active:
                self._manual_until = None
                self._manual_scope_all = False

        dates = self._status.get("last_action_dates", {})
        if isinstance(dates, dict):
            for action, date_value in dates.items():
                try:
                    self._last_action_dates[str(action)] = datetime.fromisoformat(
                        str(date_value)
                    ).date()
                except (TypeError, ValueError):
                    continue

    def persist_status(self) -> None:
        self._sync_runtime_status()
        if self._persist_callback:
            self._persist_callback(self.cover, self._status)

    def _sync_runtime_status(self) -> None:
        self._status["reason"] = self._reason
        self._status["target"] = self._target
        self._status["last_action_dates"] = {
            action: date_value.isoformat()
            for action, date_value in self._last_action_dates.items()
        }
        manual = self._status.setdefault("manual", {})
        manual["active"] = self._manual_active
        manual["scope_all"] = self._manual_scope_all
        manual["until"] = self._manual_until.isoformat() if self._manual_until else None
        if self._manual_active and not manual.get("ts"):
            manual["ts"] = _ts_now()

        ventilation = self._status.setdefault("ventilation", {})
        ventilation["restore_position"] = self._pre_ventilation_position

    def _set_status_bucket(self, bucket: str, active: bool, ts: int | None = None) -> None:
        section = self._status.setdefault(bucket, {})
        section["active"] = active
        section["ts"] = ts if ts is not None else _ts_now()

    def _status_active(self, bucket: str) -> bool:
        section = self._status.get(bucket, {})
        return isinstance(section, dict) and bool(section.get("active"))

    def _ventilation_status_active(self) -> bool:
        section = self._status.get("ventilation", {})
        return isinstance(section, dict) and bool(
            section.get("partial") or section.get("full")
        )

    def _shading_status(self) -> dict:
        section = self._status.setdefault("shading", {})
        if not isinstance(section, dict):
            section = {}
            self._status["shading"] = section
        section.setdefault("active", False)
        section.setdefault("start_pending", 0)
        section.setdefault("end_pending", 0)
        section.setdefault("ts", 0)
        return section

    def _set_shading_pending(
        self, kind: str, due_at: datetime | None, active: bool | None = None
    ) -> None:
        section = self._shading_status()
        key = "start_pending" if kind == "start" else "end_pending"
        section[key] = int(due_at.timestamp()) if due_at else 0
        section["ts"] = _ts_now()
        if active is not None:
            section["active"] = active
        self.persist_status()

    def _shading_pending_due(self, kind: str, now: datetime) -> bool:
        section = self._shading_status()
        key = "start_pending" if kind == "start" else "end_pending"
        due_ts = _coerce_float(section.get(key)) or 0
        return bool(due_ts and now.timestamp() >= due_ts)

    def _shading_pending_active(self, kind: str) -> bool:
        section = self._shading_status()
        key = "start_pending" if kind == "start" else "end_pending"
        return bool((_coerce_float(section.get(key)) or 0) > 0)

    def _clear_shading_pending(self, kind: str | None = None, persist: bool = True) -> None:
        section = self._shading_status()
        if kind in (None, "start"):
            section["start_pending"] = 0
        if kind in (None, "end"):
            section["end_pending"] = 0
        section["ts"] = _ts_now()
        if persist:
            self.persist_status()

    def _set_ventilation_status(
        self, partial: bool = False, full: bool = False, ts: int | None = None
    ) -> None:
        section = self._status.setdefault("ventilation", {})
        section["partial"] = partial
        section["full"] = full
        section["restore_position"] = self._pre_ventilation_position
        section["ts"] = ts if ts is not None else _ts_now()

    def _record_action_status(self, reason: str, position: float | None = None) -> None:
        ts = _ts_now()
        today = dt_util.as_local(dt_util.utcnow()).date()
        if reason == "ventilation_full":
            self._set_status_bucket("open", True, ts)
            self._set_status_bucket("close", False, ts)
            self._set_ventilation_status(False, True, ts)
        elif "open" in reason or reason == "shading_end_open":
            self._last_action_dates["open"] = today
            self._set_status_bucket("open", True, ts)
            self._set_status_bucket("close", False, ts)
            self._set_status_bucket("shading", False, ts)
            self._clear_shading_pending(persist=False)
            self._set_ventilation_status(False, False, ts)
        elif "close" in reason or reason == "resident_asleep":
            self._last_action_dates["close"] = today
            self._set_status_bucket("open", False, ts)
            self._set_status_bucket("close", True, ts)
            self._set_status_bucket("shading", False, ts)
            self._clear_shading_pending(persist=False)
            self._set_ventilation_status(False, False, ts)
        elif reason in {"ventilation", "shading_end_ventilation"}:
            self._set_status_bucket("open", False, ts)
            self._set_status_bucket("close", False, ts)
            self._set_ventilation_status(True, False, ts)
        elif "shading" in reason:
            self._last_action_dates["shading"] = today
            self._set_status_bucket("open", True, ts)
            self._set_status_bucket("close", False, ts)
            self._set_status_bucket("shading", reason != "manual_shading_end", ts)
            self._clear_shading_pending(persist=False)
            self._set_ventilation_status(False, False, ts)

        self._status["target"] = position if position is not None else self._target
        self._status["reason"] = self._reason
        self.persist_status()

    async def async_setup(self) -> None:
        registry = er.async_get(self.hass)
        self._master_entity_id = registry.async_get_entity_id(
            "switch", DOMAIN, f"{self.entry.entry_id}-master"
        )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._handle_interval, timedelta(minutes=1))
        )
        self._unsubs.append(self.hass.bus.async_listen("call_service", self._handle_service_call))
        if self._target is None:
            self._target = self._current_position()
        self._last_position = self._target
        sensor_entities = {
            self.config.get(CONF_BRIGHTNESS_SENSOR),
            self.config.get(CONF_WORKDAY_SENSOR),
            self.config.get(CONF_WORKDAY_TOMORROW_SENSOR),
            self.config.get(CONF_TEMPERATURE_SENSOR_INDOOR),
            self.config.get(CONF_TEMPERATURE_SENSOR_OUTDOOR),
            self.config.get(CONF_RESIDENT_SENSOR),
            self.config.get(CONF_SHADING_FORECAST_SENSOR),
            self.config.get(CONF_CALENDAR_ENTITY),
            self.cover,
        }
        sensor_entities.update(self._contact_entities())
        sensor_entities.update(
            entity
            for entity in (self.config.get(entity_key) for entity_key in self._auto_entity_map.values())
            if entity
        )
        for entity_id in sensor_entities:
            if not entity_id:
                continue
            self._unsubs.append(
                async_track_state_change_event(self.hass, [entity_id], self._handle_state_event)
            )
        self._refresh_next_events(dt_util.utcnow())
        self._schedule_manual_expiry()
        self.persist_status()
        self._publish_state()


    async def async_unload(self) -> None:
        while self._unsubs:
            unsub = self._unsubs.pop()
            unsub()

    @callback
    def update_config(self, new_config: ConfigType) -> None:
        self.config = new_config
        self._clear_manual_expiry()
        self._hydrate_persistent_status()
        if self._target is None:
            self._target = self._current_position()
        self._last_position = self._target
        now = dt_util.utcnow()
        self._refresh_next_events(now)
        self._schedule_manual_expiry()
        self.persist_status()
        self.hass.async_create_task(self._evaluate("config"))
        self._publish_state()

    @callback
    def async_request_evaluate(self, trigger: str = "runtime_toggle") -> None:
        """Request re-evaluation after runtime-only toggle changes."""

        self.hass.async_create_task(self._evaluate(trigger))

    @callback
    def _handle_state_event(self, event) -> None:
        now = dt_util.utcnow()
        self._expire_manual_override(now)
        self._ensure_manual_expiry_timer(now)
        previous_position = self._last_position
        entity_id = event.data.get("entity_id")
        trigger = "state"
        if entity_id == self.config.get(CONF_RESIDENT_SENSOR):
            old_state = event.data.get("old_state")
            new_state = event.data.get("new_state")
            old_value = old_state.state if old_state else None
            new_value = new_state.state if new_state else None
            if self._resident_state_is_on(old_value) and self._resident_state_is_off(
                new_value
            ):
                trigger = "resident_woke"
            elif self._resident_state_is_off(old_value) and self._resident_state_is_on(
                new_value
            ):
                trigger = "resident_asleep"

        if entity_id == self.cover:
            tolerance = float(
                self._position_value(CONF_POSITION_TOLERANCE, DEFAULT_TOLERANCE)
            )
            current = self._current_position()
            if self._target is None and current is not None:
                self._target = current
            command_recent = False
            moving_toward_target = False
            if self._last_command_at:
                command_recent = (now - self._last_command_at) < timedelta(seconds=90)
            if (
                command_recent
                and previous_position is not None
                and current is not None
                and self._target is not None
            ):
                prev_delta = abs(previous_position - self._target)
                curr_delta = abs(current - self._target)
                moving_toward_target = curr_delta <= prev_delta + tolerance
            if current is not None and self._manual_detection_enabled():
                deviation_from_target = (
                    self._target is not None
                    and abs(current - self._target) > tolerance
                    and not moving_toward_target
                )
                unexplained_move = (
                    self._target is None
                    and previous_position is not None
                    and abs(current - previous_position) > tolerance
                )
                if (deviation_from_target or unexplained_move) and (
                    not command_recent or not moving_toward_target
                ):
                    self._target = current
                    self._activate_manual_override(
                        scope_all=True, reason="manual_override"
                    )
            self._last_position = current if current is not None else previous_position
        self.hass.async_create_task(self._evaluate(trigger))

    @callback
    def _handle_service_call(self, event) -> None:
        if event.data.get("domain") != "cover":
            return

        service = event.data.get("service")
        if service not in {"set_cover_position", "open_cover", "close_cover"}:
            return

        service_data = event.data.get("service_data") or {}
        entity_ids = service_data.get("entity_id")
        if not entity_ids:
            return
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
        if self.cover not in entity_ids:
            return

        if event.context and event.context.id == self._last_command_context_id:
            return

        position: float | None = None
        if service == "set_cover_position":
            try:
                position_value = service_data.get("position")
                position = float(position_value) if position_value is not None else None
            except (TypeError, ValueError):
                position = None
        elif service == "open_cover":
            position = 100.0
        elif service == "close_cover":
            position = 0.0

        if position is not None:
            self._target = position
            self._status["target"] = position

        self._activate_manual_override(scope_all=True, reason="manual_override")
        self.hass.async_create_task(self._evaluate("manual_service"))

    @callback
    def _handle_interval(self, now: datetime) -> None:
        self.hass.async_create_task(self._evaluate("time"))

    def _manual_detection_enabled(self) -> bool:
        if self._manual_active:
            return False
        return any(
            bool(self.config.get(flag, DEFAULT_MANUAL_OVERRIDE_FLAGS.get(flag, False)))
            for flag in (
                CONF_MANUAL_OVERRIDE_BLOCK_OPEN,
                CONF_MANUAL_OVERRIDE_BLOCK_CLOSE,
                CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE,
                CONF_MANUAL_OVERRIDE_BLOCK_SHADING,
            )
        )

    def _activate_manual_override(
        self, minutes: int | None = None, scope_all: bool = False, reason: str | None = None
    ) -> None:
        now = dt_util.utcnow()
        self._manual_active = True
        self._manual_scope_all = self._manual_scope_all or scope_all
        self._manual_until = self._manual_reset_at(now, minutes)
        if reason:
            self._reason = reason
        elif self._manual_scope_all:
            self._reason = "manual_override"
        manual = self._status.setdefault("manual", {})
        manual["active"] = True
        manual["scope_all"] = self._manual_scope_all
        manual["until"] = self._manual_until.isoformat() if self._manual_until else None
        manual["ts"] = _ts_now()
        self.persist_status()
        self._schedule_manual_expiry()
        self._refresh_next_events(now)
        self._publish_state()

    def _manual_reset_at(self, now: datetime, minutes: int | None = None) -> datetime | None:
        if minutes is not None:
            return now + timedelta(minutes=minutes)
        mode = self.config.get(CONF_MANUAL_OVERRIDE_RESET_MODE, MANUAL_OVERRIDE_RESET_TIMEOUT)
        if mode == MANUAL_OVERRIDE_RESET_NONE:
            return None
        if mode == MANUAL_OVERRIDE_RESET_TIME:
            reset_time = _parse_time(self.config.get(CONF_MANUAL_OVERRIDE_RESET_TIME)) or _parse_time(
                DEFAULT_MANUAL_OVERRIDE_RESET_TIME
            )
            return self._next_time_for_point(reset_time, now)
        duration = self.config.get(CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES)
        try:
            minutes_value = int(duration)
        except (TypeError, ValueError):
            minutes_value = DEFAULT_MANUAL_OVERRIDE_MINUTES
        return now + timedelta(minutes=minutes_value)

    def _manual_blocks_action(self, action: str) -> bool:
        if not self._manual_active:
            return False
        if self._manual_scope_all:
            return True
        flag_map = {
            "open": CONF_MANUAL_OVERRIDE_BLOCK_OPEN,
            "close": CONF_MANUAL_OVERRIDE_BLOCK_CLOSE,
            "ventilation": CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE,
            "shading": CONF_MANUAL_OVERRIDE_BLOCK_SHADING,
        }
        flag = flag_map.get(action)
        if not flag:
            return False
        return bool(self.config.get(flag, DEFAULT_MANUAL_OVERRIDE_FLAGS.get(flag, False)))

    def set_manual_override(self, minutes: int) -> None:
        duration = minutes or self.config.get(
            CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES
        )
        self._activate_manual_override(
            minutes=duration, scope_all=True, reason="manual_override"
        )

    def clear_manual_override(self) -> None:
        self._manual_until = None
        self._manual_active = False
        self._manual_scope_all = False
        self._clear_manual_expiry()
        if self._reason in {"manual_override", "manual_shading"}:
            self._reason = None
        manual = self._status.setdefault("manual", {})
        manual["active"] = False
        manual["scope_all"] = False
        manual["until"] = None
        self.persist_status()
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

    def _remember_pre_ventilation_position(self) -> None:
        """Remember current position before switching into ventilation mode."""
        if self._reason in {"ventilation", "ventilation_full"}:
            return
        current = self._current_position()
        if current is not None:
            self._pre_ventilation_position = float(current)
            self._status.setdefault("ventilation", {})[
                "restore_position"
            ] = self._pre_ventilation_position
            self.persist_status()

    def publish_state(self) -> None:
        """Expose the current state via dispatcher for newly added entities."""
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

    def state_snapshot(
        self,
    ) -> tuple[
        float | None,
        str | None,
        datetime | None,
        bool,
        datetime | None,
        datetime | None,
        float | None,
        bool,
        bool,
        bool,
    ]:
        """Provide the current state values without dispatching updates."""

        self._refresh_next_events(dt_util.utcnow())
        current_position = self._current_position()
        shading_enabled = self._auto_enabled(CONF_AUTO_SHADING)
        shading_active = self._shading_is_active(current_position, shading_enabled)
        ventilation_active = self._ventilation_is_active(current_position)
        return (
            self._target,
            self._reason or IDLE_REASON,
            self._manual_until,
            self._manual_active,
            self._next_open,
            self._next_close,
            current_position,
            shading_enabled,
            shading_active,
            ventilation_active,
        )

    def activate_shading(self, minutes: int | None = None) -> None:
        duration = minutes or self.config.get(CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES)
        self._manual_until = dt_util.utcnow() + timedelta(minutes=duration)
        self._manual_active = True
        self._manual_scope_all = True
        manual = self._status.setdefault("manual", {})
        manual["active"] = True
        manual["scope_all"] = True
        manual["until"] = self._manual_until.isoformat()
        manual["ts"] = _ts_now()
        self.persist_status()
        self._schedule_manual_expiry()
        self.hass.async_create_task(
            self._set_position(self.config.get(CONF_SHADING_POSITION), "manual_shading")
        )

    async def recalibrate(self, full_open: float | None) -> None:
        tolerance = float(self._position_value(CONF_POSITION_TOLERANCE, DEFAULT_TOLERANCE))
        target_open = self._normalize_position(full_open, DEFAULT_OPEN_POSITION)
        current_position = self._current_position()

        manual_state = (
            self._manual_until,
            self._manual_active,
            self._manual_scope_all,
            self._reason,
        )

        self._activate_manual_override(
            minutes=self.config.get(
                CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES
            ),
            scope_all=True,
            reason="manual_override",
        )

        try:
            await self._open_cover(target_open, reason="recalibrate_open")
            await self._wait_for_position(target_open, tolerance)

            if current_position is not None:
                await self._command_position(
                    current_position, reason="recalibrate_restore"
                )
                await self._wait_for_position(current_position, tolerance)
        finally:
            (
                self._manual_until,
                self._manual_active,
                self._manual_scope_all,
                self._reason,
            ) = manual_state
            self._refresh_next_events(dt_util.utcnow())
            self._publish_state()

    async def force_move(self, action: str) -> None:
        if action == "open":
            target = self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION)
            reason = "force_open"
        elif action == "close":
            target = self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION)
            reason = "force_close"
        else:
            return
        if target is None:
            return
        self._activate_manual_override(scope_all=True, reason=reason)
        await self._command_position(float(target), reason=reason)
        self._target = float(target)
        self._reason = reason
        self._record_action_status(reason, float(target))
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

    async def force_ventilation(self, action: str) -> None:
        self._activate_manual_override(scope_all=True, reason="ventilation")
        if action == "start":
            self._remember_pre_ventilation_position()
            target = self._position_value(CONF_VENTILATE_POSITION, DEFAULT_VENTILATE_POSITION)
            if target is None:
                return
            await self._command_position(float(target), reason="ventilation_start")
            self._target = float(target)
            self._reason = "ventilation"
            self._set_ventilation_status(True, False)
            self.persist_status()
        elif action == "stop":
            target = self._pre_ventilation_position
            if target is None:
                target = self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION)
            if target is None:
                return
            await self._command_position(float(target), reason="ventilation_stop")
            self._target = float(target)
            self._pre_ventilation_position = None
            if self._reason == "ventilation":
                self._reason = None
            self._set_ventilation_status(False, False)
            self.persist_status()
        else:
            return
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

    async def force_shading(self, action: str) -> None:
        self._activate_manual_override(scope_all=True, reason="manual_shading")
        if action == "activate":
            target = self._position_value(CONF_SHADING_POSITION, DEFAULT_SHADING_POSITION)
            if target is None:
                return
            await self._command_position(float(target), reason="manual_shading")
            self._target = float(target)
            self._reason = "manual_shading"
            self._record_action_status("manual_shading", float(target))
        elif action == "deactivate":
            target = self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION)
            if target is None:
                return
            await self._command_position(float(target), reason="manual_shading_end")
            self._target = float(target)
            if self._reason in {"shading", "manual_shading"}:
                self._reason = None
            self._record_action_status("manual_shading_end", float(target))
        else:
            return
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

    def _expire_manual_override(self, now: datetime) -> None:
        if self._manual_until and now >= self._manual_until:
            self._manual_until = None
            self._manual_active = False
            self._manual_scope_all = False
            self._clear_manual_expiry()
            if self._reason in {"manual_override", "manual_shading"}:
                self._reason = None
            manual = self._status.setdefault("manual", {})
            manual["active"] = False
            manual["scope_all"] = False
            manual["until"] = None
            self.persist_status()

    def _ensure_manual_expiry_timer(self, now: datetime) -> None:
        if not self._manual_active or not self._manual_until:
            return
        if self._manual_expire_unsub:
            return
        if self._manual_until <= now:
            self._handle_manual_expiry(None)
            return
        self._manual_expire_unsub = async_track_point_in_time(
            self.hass, self._handle_manual_expiry, self._manual_until
        )

    def _clear_manual_expiry(self) -> None:
        if self._manual_expire_unsub:
            self._manual_expire_unsub()
            self._manual_expire_unsub = None

    def _schedule_manual_expiry(self) -> None:
        self._clear_manual_expiry()
        if not self._manual_until:
            return
        now = dt_util.utcnow()
        if self._manual_until <= now:
            self._handle_manual_expiry(None)
            return
        self._manual_expire_unsub = async_track_point_in_time(
            self.hass, self._handle_manual_expiry, self._manual_until
        )

    @callback
    def _handle_manual_expiry(self, _) -> None:
        self._manual_until = None
        self._manual_active = False
        self._manual_scope_all = False
        self._manual_expire_unsub = None
        if self._reason in {"manual_override", "manual_shading"}:
            self._reason = None
        manual = self._status.setdefault("manual", {})
        manual["active"] = False
        manual["scope_all"] = False
        manual["until"] = None
        self.persist_status()
        now = dt_util.utcnow()
        self._refresh_next_events(now)
        self._publish_state()
        self.hass.async_create_task(self._evaluate("manual_expired"))
    async def _evaluate(self, trigger: str) -> None:
        now = dt_util.utcnow()
        self._expire_manual_override(now)
        self._ensure_manual_expiry_timer(now)
        self._fire_event(
            "evaluate",
            {
                "trigger": trigger,
                "manual_active": self._manual_active,
                "manual_scope_all": self._manual_scope_all,
                "next_open": self._next_open,
                "next_close": self._next_close,
                "master_enabled": self._master_enabled(),
            },
        )
        if self._manual_active:
            if self._manual_scope_all or all(
                self._manual_blocks_action(action)
                for action in ("open", "close", "ventilation", "shading")
            ):
                self._refresh_next_events(now)
                self._publish_state()
                return

        if not self._master_enabled():
            self._refresh_next_events(now)
            self._publish_state()
            return

        brightness = _float_state(self.hass, self.config.get(CONF_BRIGHTNESS_SENSOR))
        sun_state = self.hass.states.get("sun.sun")
        sun_elevation = sun_state and sun_state.attributes.get("elevation")
        sun_azimuth = sun_state and sun_state.attributes.get("azimuth")

        global_condition = await self._condition_allows(CONF_ADDITIONAL_CONDITION_GLOBAL)
        if not global_condition:
            self._refresh_next_events(now)
            self._publish_state()
            return

        if bool(
            self.config.get(
                CONF_ADDITIONAL_CONDITIONS_ENABLED,
                DEFAULT_AUTOMATION_FLAGS.get(CONF_ADDITIONAL_CONDITIONS_ENABLED, False),
            )
        ):
            conditions = {
                CONF_ADDITIONAL_CONDITION_CLOSE: await self._condition_allows(
                    CONF_ADDITIONAL_CONDITION_CLOSE
                ),
                CONF_ADDITIONAL_CONDITION_OPEN: await self._condition_allows(
                    CONF_ADDITIONAL_CONDITION_OPEN
                ),
                CONF_ADDITIONAL_CONDITION_VENTILATE: await self._condition_allows(
                    CONF_ADDITIONAL_CONDITION_VENTILATE
                ),
                CONF_ADDITIONAL_CONDITION_VENTILATE_END: await self._condition_allows(
                    CONF_ADDITIONAL_CONDITION_VENTILATE_END
                ),
                CONF_ADDITIONAL_CONDITION_SHADING: await self._condition_allows(
                    CONF_ADDITIONAL_CONDITION_SHADING
                ),
                CONF_ADDITIONAL_CONDITION_SHADING_TILT: await self._condition_allows(
                    CONF_ADDITIONAL_CONDITION_SHADING_TILT
                ),
                CONF_ADDITIONAL_CONDITION_SHADING_END: await self._condition_allows(
                    CONF_ADDITIONAL_CONDITION_SHADING_END
                ),
            }
        else:
            conditions = {
                CONF_ADDITIONAL_CONDITION_CLOSE: True,
                CONF_ADDITIONAL_CONDITION_OPEN: True,
                CONF_ADDITIONAL_CONDITION_VENTILATE: True,
                CONF_ADDITIONAL_CONDITION_VENTILATE_END: True,
                CONF_ADDITIONAL_CONDITION_SHADING: True,
                CONF_ADDITIONAL_CONDITION_SHADING_TILT: True,
                CONF_ADDITIONAL_CONDITION_SHADING_END: True,
            }

        close_condition = conditions[CONF_ADDITIONAL_CONDITION_CLOSE]
        open_condition = conditions[CONF_ADDITIONAL_CONDITION_OPEN]
        ventilation_condition = conditions[CONF_ADDITIONAL_CONDITION_VENTILATE]
        ventilation_end_condition = conditions[CONF_ADDITIONAL_CONDITION_VENTILATE_END]
        shading_condition = conditions[CONF_ADDITIONAL_CONDITION_SHADING]
        shading_tilt_condition = conditions[CONF_ADDITIONAL_CONDITION_SHADING_TILT]
        shading_end_condition = conditions[CONF_ADDITIONAL_CONDITION_SHADING_END]

        resident_mode_enabled = bool(
            self.config.get(CONF_RESIDENT_STATUS, DEFAULT_AUTOMATION_FLAGS.get(CONF_RESIDENT_STATUS, False))
        )
        resident_sleeping = resident_mode_enabled and self._is_resident_sleeping()
        resident_woke = trigger == "resident_woke"

        resident_allow_open = bool(
            self.config.get(
                CONF_RESIDENT_ALLOW_OPEN,
                DEFAULT_AUTOMATION_FLAGS.get(CONF_RESIDENT_ALLOW_OPEN, False),
            )
        )
        resident_allow_ventilation = bool(
            self.config.get(
                CONF_RESIDENT_ALLOW_VENTILATION,
                DEFAULT_AUTOMATION_FLAGS.get(CONF_RESIDENT_ALLOW_VENTILATION, False),
            )
        )
        resident_allow_shading = bool(
            self.config.get(
                CONF_RESIDENT_ALLOW_SHADING,
                DEFAULT_AUTOMATION_FLAGS.get(CONF_RESIDENT_ALLOW_SHADING, False),
            )
        )
        resident_close_enabled = bool(
            self.config.get(
                CONF_RESIDENT_CLOSE_ENABLED,
                DEFAULT_AUTOMATION_FLAGS.get(CONF_RESIDENT_CLOSE_ENABLED, True),
            )
        )
        resident_open_enabled = bool(
            self.config.get(
                CONF_RESIDENT_OPEN_ENABLED,
                DEFAULT_AUTOMATION_FLAGS.get(CONF_RESIDENT_OPEN_ENABLED, True),
            )
        )

        if resident_sleeping and resident_close_enabled:
            if self._manual_blocks_action("close"):
                self._refresh_next_events(now)
                self._publish_state()
                return
            close_target = self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION)
            current_position = self._current_position()
            if not self._position_matches(close_target, current_position):
                await self._set_position(close_target, "resident_asleep")
                return
            if not (resident_allow_open or resident_allow_shading or resident_allow_ventilation):
                self._refresh_next_events(now)
                self._publish_state()
                return

        resident_blocks_open = resident_sleeping and not resident_allow_open
        resident_blocks_ventilation = resident_sleeping and not resident_allow_ventilation
        resident_blocks_shading = resident_sleeping and not resident_allow_shading

        auto_ventilate = (not self._is_awning()) and self._auto_enabled(CONF_AUTO_VENTILATE)
        full_contact_active = auto_ventilate and self._contacts_active(
            self._full_open_sensors(), now
        )
        tilt_contact_active = auto_ventilate and self._tilt_contact_active(now)
        ventilation_contact_active = full_contact_active or tilt_contact_active
        tilt_lock_close = tilt_contact_active and bool(
            self.config.get(CONF_LOCKOUT_TILT_CLOSE, False)
        )
        tilt_lock_shading_start = tilt_contact_active and bool(
            self.config.get(CONF_LOCKOUT_TILT_SHADING_START, False)
        )
        tilt_lock_shading_end = tilt_contact_active and bool(
            self.config.get(CONF_LOCKOUT_TILT_SHADING_END, False)
        )

        auto_time_enabled = self._auto_enabled(CONF_AUTO_TIME)
        calendar_open_active = auto_time_enabled and self._calendar_open_active(now)
        calendar_close_active = auto_time_enabled and self._calendar_close_active(now)
        is_opening_phase = self._within_opening_phase(now) or calendar_open_active
        is_daytime_phase = (
            (not auto_time_enabled)
            or self._within_daytime_phase(now)
            or (calendar_open_active and not calendar_close_active)
        )
        is_closing_phase = self._within_closing_phase(now) or calendar_close_active
        is_evening_phase = (auto_time_enabled and self._within_evening_phase(now)) or calendar_close_active
        is_time_up_late = self._is_time_up_late(now)
        is_time_down_late = self._is_time_down_late(now)
        has_environment_control = self._auto_enabled(CONF_AUTO_BRIGHTNESS) or self._auto_enabled(
            CONF_AUTO_SUN
        )

        environment_allows_opening = self._environment_allows_opening(
            sun_elevation, brightness
        )
        environment_allows_closing = self._environment_allows_closing(
            sun_elevation, brightness
        )

        if auto_ventilate and full_contact_active and ventilation_condition and not resident_blocks_ventilation:
            if not self._manual_blocks_action("ventilation"):
                self._remember_pre_ventilation_position()
                await self._set_position(
                    self._position_value(
                        CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION
                    ),
                    "ventilation_full",
                )
            return

        current_position = self._current_position()

        if auto_ventilate and tilt_contact_active and ventilation_condition and not resident_blocks_ventilation:
            if not self._manual_blocks_action("ventilation"):
                self._remember_pre_ventilation_position()
                target = self._position_value(
                    CONF_VENTILATE_POSITION, DEFAULT_VENTILATE_POSITION
                )
                allow_higher = bool(
                    self.config.get(CONF_VENTILATION_ALLOW_HIGHER_POSITION, False)
                )
                close_position = self._position_value(
                    CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION
                )
                ready = (
                    allow_higher
                    or current_position is None
                    or self._position_is_below(current_position, target)
                    or self._position_matches(target, current_position)
                    or self._position_matches(close_position, current_position)
                )
                if ready:
                    if (
                        current_position is None
                        or not self._position_matches(target, current_position)
                    ):
                        await self._set_position(target, "ventilation")
                    else:
                        self._reason = "ventilation"
                        self._set_ventilation_status(True, False)
                        self.persist_status()
                        self._publish_state()
            return


        post_ventilation = (
            auto_ventilate
            and not ventilation_contact_active
            and (
                self._reason in {"ventilation", "ventilation_full", "shading_end_ventilation"}
                or self._ventilation_status_active()
            )
        )

        if post_ventilation and not ventilation_end_condition:
            self._refresh_next_events(now)
            self._publish_state()
            return

        if (
            self._auto_enabled(CONF_AUTO_SHADING)
            and not self._manual_blocks_action("shading")
            and not resident_blocks_shading
        ):
            shading_active = self._status_active("shading") or self._reason in {
                "shading",
                "manual_shading",
            }
            shading_allowed = self._shading_conditions(
                sun_azimuth, sun_elevation, brightness
            )
            shading_allowed = shading_allowed and shading_condition
            if tilt_contact_active:
                shading_allowed = shading_allowed and shading_tilt_condition
            if tilt_lock_shading_start and not shading_active:
                shading_allowed = False
            if shading_allowed:
                if self._shading_pending_active("end"):
                    self._clear_shading_pending("end")
            elif self._shading_pending_active("start"):
                max_duration = self._duration_value(
                    CONF_SHADING_START_MAX_DURATION,
                    DEFAULT_SHADING_TIMING_SETTINGS[CONF_SHADING_START_MAX_DURATION],
                )
                if max_duration <= 0:
                    self._clear_shading_pending("start")
                else:
                    pending_ts = _coerce_float(
                        self._shading_status().get("start_pending")
                    ) or 0
                    waiting = self._duration_value(
                        CONF_SHADING_WAITINGTIME_START,
                        DEFAULT_SHADING_TIMING_SETTINGS[CONF_SHADING_WAITINGTIME_START],
                    )
                    started_ts = max(0, pending_ts - waiting)
                    if started_ts and now.timestamp() - started_ts > max_duration:
                        self._clear_shading_pending("start")
            if shading_active and not shading_allowed:
                if not shading_end_condition:
                    self._publish_state()
                    return
                if (
                    self._config_bool(CONF_PREVENT_SHADING_END_IF_CLOSED)
                    and self._position_matches(
                        self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION),
                        current_position,
                    )
                ):
                    self._publish_state()
                    return
                waiting_end = self._duration_value(
                    CONF_SHADING_WAITINGTIME_END,
                    DEFAULT_SHADING_TIMING_SETTINGS[CONF_SHADING_WAITINGTIME_END],
                )
                if bool(self.config.get(CONF_SHADING_END_IMMEDIATE_BY_SUN_POSITION, False)):
                    sun_out_of_range = False
                    if sun_azimuth is not None and sun_elevation is not None:
                        az_start = self._number_value(CONF_SUN_AZIMUTH_START, 0)
                        az_end = self._number_value(CONF_SUN_AZIMUTH_END, 360)
                        el_min = self._number_value(CONF_SUN_ELEVATION_MIN, 0)
                        el_max = self._number_value(CONF_SUN_ELEVATION_MAX, 90)
                        sun_out_of_range = not (
                            az_start <= sun_azimuth <= az_end
                            and el_min <= sun_elevation <= el_max
                        )
                    if sun_out_of_range:
                        waiting_end = min(waiting_end, 5)
                if waiting_end > 0 and not self._shading_pending_due("end", now):
                    if not self._shading_pending_active("end"):
                        self._set_shading_pending(
                            "end", now + timedelta(seconds=waiting_end), True
                        )
                    self._publish_state()
                    return
                if self._shading_pending_active("end"):
                    self._clear_shading_pending("end")
                if (
                    auto_ventilate
                    and ventilation_condition
                    and (
                        tilt_lock_shading_end
                        or self.config.get(CONF_VENTILATION_USE_AFTER_SHADING)
                    )
                    and not self._manual_blocks_action("ventilation")
                ):
                    self._remember_pre_ventilation_position()
                    await self._set_position(
                        self._position_value(CONF_VENTILATE_POSITION, DEFAULT_VENTILATE_POSITION),
                        "shading_end_ventilation",
                    )
                    return
                if (
                    self._auto_enabled(CONF_AUTO_DOWN)
                    and self._sun_allows_close(sun_elevation)
                    and self._brightness_allows_close(brightness)
                ):
                    if (
                        close_condition
                        and not self._manual_blocks_action("close")
                        and not tilt_lock_close
                    ):
                        await self._set_position(
                            self._position_value(
                                CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION
                            ),
                            "shading_end_close",
                        )
                        return
                if (
                    not self._config_bool(CONF_PREVENT_OPENING_AFTER_SHADING_END)
                    and self._auto_enabled(CONF_AUTO_UP)
                    and self._sun_allows_open(sun_elevation)
                    and self._brightness_allows_open(brightness)
                ):
                    if open_condition and not self._manual_blocks_action("open"):
                        await self._set_position(
                            self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION),
                            "shading_end_open",
                        )
                        return
                if self._reason in {"shading", "manual_shading"}:
                    self._reason = None
                self._set_status_bucket("shading", False)
                self._clear_shading_pending("end", persist=False)
                self.persist_status()
                self._publish_state()
                return
            if (
                shading_allowed
                and not shading_active
                and not self._action_already_done_today(
                    "shading", CONF_PREVENT_SHADING_MULTIPLE_TIMES
                )
            ):
                waiting_start = self._duration_value(
                    CONF_SHADING_WAITINGTIME_START,
                    DEFAULT_SHADING_TIMING_SETTINGS[CONF_SHADING_WAITINGTIME_START],
                )
                if waiting_start > 0 and not self._shading_pending_due("start", now):
                    if not self._shading_pending_active("start"):
                        self._set_shading_pending(
                            "start", now + timedelta(seconds=waiting_start), False
                        )
                    self._publish_state()
                    return
                if self._shading_pending_active("start"):
                    self._clear_shading_pending("start")
                await self._set_position(
                    self._position_value(CONF_SHADING_POSITION, DEFAULT_SHADING_POSITION),
                    "shading",
                )
                return

        close_events: list[tuple[datetime, str, float | None]] = []
        open_events: list[tuple[datetime, str, float | None]] = []

        if post_ventilation and ventilation_end_condition:
            restore_position = self._pre_ventilation_position
            if restore_position is None:
                restore_position = self._position_value(
                    CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION
                )
            if not (
                self._config_bool(CONF_PREVENT_OPENING_AFTER_VENTILATION_END)
                and self._target_is_opening_move(restore_position)
            ):
                close_events.append(
                    (
                        now + timedelta(seconds=1),
                        "ventilation_end_restore",
                        restore_position,
                    )
                )
            self._pre_ventilation_position = None
            self._set_ventilation_status(False, False)
            self.persist_status()

        close_target = self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION)
        open_target = self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION)
        close_status_satisfied = self._status_active("close") and self._position_matches(
            close_target, current_position
        )
        open_status_satisfied = self._status_active("open") and self._position_matches(
            open_target, current_position
        )

        if (
            close_condition
            and not self._manual_blocks_action("close")
            and not close_status_satisfied
            and not self._action_already_done_today(
                "close", CONF_PREVENT_CLOSING_MULTIPLE_TIMES
            )
        ):
            close_due = (
                (not auto_time_enabled and environment_allows_closing)
                or is_time_down_late
                or (
                    (is_closing_phase or is_evening_phase)
                    and (
                        (not has_environment_control)
                        or environment_allows_closing
                    )
                )
            )
            if (
                close_due
                and self._auto_enabled(CONF_AUTO_SUN)
                and self._sun_allows_close(sun_elevation)
                and not self._close_position_protected(current_position)
            ):
                close_events.append(
                    (
                        now,
                        "sun_close",
                        close_target,
                    )
                )
            if (
                close_due
                and self._auto_enabled(CONF_AUTO_BRIGHTNESS)
                and brightness is not None
                and self._brightness_allows_close(brightness)
                and not self._close_position_protected(current_position)
            ):
                close_events.append(
                    (
                        now,
                        "brightness_close",
                        close_target,
                    )
                )

            if (
                self._auto_enabled(CONF_AUTO_TIME)
                and self._auto_enabled(CONF_AUTO_DOWN)
                and close_due
                and not close_events
                and not self._close_position_protected(current_position)
            ):
                close_events.append(
                    (
                        self._next_close or now,
                        "scheduled_close",
                        close_target,
                    )
                )

        if tilt_lock_close:
            close_events = []

        if (
            open_condition
            and not resident_blocks_open
            and not self._manual_blocks_action("open")
            and not open_status_satisfied
            and not self._action_already_done_today(
                "open", CONF_PREVENT_OPENING_MULTIPLE_TIMES
            )
        ):
            should_be_open_now = is_daytime_phase and not is_evening_phase and (
                (not has_environment_control) or environment_allows_opening
            )
            open_due = (
                resident_open_enabled and should_be_open_now
                if resident_woke
                else (
                    (not auto_time_enabled and environment_allows_opening)
                    or is_time_up_late
                    or (
                        (is_opening_phase or is_daytime_phase)
                        and not is_evening_phase
                        and environment_allows_opening
                    )
                )
            )
            if (
                open_due
                and self._auto_enabled(CONF_AUTO_SUN)
                and self._sun_allows_open(sun_elevation)
            ):
                open_events.append(
                    (
                        now,
                        "sun_open",
                        open_target,
                    )
                )


            if (
                open_due
                and self._auto_enabled(CONF_AUTO_BRIGHTNESS)
                and brightness is not None
                and self._brightness_allows_open(brightness)
            ):
                open_events.append(
                    (
                        now,
                        "brightness_open",
                        open_target,
                    )
                )

            if (
                self._auto_enabled(CONF_AUTO_TIME)
                and self._auto_enabled(CONF_AUTO_UP)
                and open_due
                and not open_events
            ):
                open_events.append(
                    (
                        self._next_open or now,
                        "scheduled_open",
                        open_target,
                    )
                )

        def _pick_event(
            candidates: list[tuple[datetime, str, float | None]]
        ) -> tuple[datetime, str, float | None] | None:
            if not candidates:
                return None
            return sorted(candidates, key=lambda item: item[0])[0]

        next_close = _pick_event(close_events)
        next_open = _pick_event(open_events)

        selected: tuple[datetime, str, float | None] | None = None
        if next_close and next_open:
            selected = next_close if next_close[0] <= next_open[0] else next_open
        else:
            selected = next_close or next_open

        if selected:
            _, reason, position = selected
            if "close" in reason:
                if close_condition and not self._manual_blocks_action("close"):
                    await self._set_position(position, reason)
                    return
            elif open_condition and not self._manual_blocks_action("open"):
                await self._set_position(position, reason)
                return

        self._refresh_next_events(now)
        self._publish_state()

    def _dynamic_sun_threshold(self, kind: str) -> float | None:
        mode = str(
            self.config.get(CONF_SUN_ELEVATION_MODE, DEFAULT_SUN_ELEVATION_MODE)
            or DEFAULT_SUN_ELEVATION_MODE
        ).lower()
        if mode == "hybid":
            mode = "hybrid"

        if kind == "open":
            fixed_key = CONF_SUN_ELEVATION_OPEN
            sensor_key = CONF_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR
            fixed_default = DEFAULT_SUN_ELEVATION_OPEN
        else:
            fixed_key = CONF_SUN_ELEVATION_CLOSE
            sensor_key = CONF_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR
            fixed_default = DEFAULT_SUN_ELEVATION_CLOSE

        try:
            fixed_threshold = float(self.config.get(fixed_key, fixed_default))
        except (TypeError, ValueError):
            return None

        if mode == "fixed":
            return fixed_threshold

        sensor_value = _float_state(self.hass, self.config.get(sensor_key))
        if mode == "dynamic":
            # Dynamic sensor is optional in config flow. If unavailable or invalid,
            # fall back to the configured fixed threshold so sun timing still works.
            return sensor_value if sensor_value is not None else fixed_threshold

        if mode == "hybrid":
            if sensor_value is None:
                return fixed_threshold
            # Hybrid mode uses the fixed value as manual offset.
            return sensor_value + fixed_threshold

        return fixed_threshold

    def _sun_allows_open(self, sun_elevation: float | None) -> bool:
        if not self._auto_enabled(CONF_AUTO_SUN):
            return True
        if sun_elevation is None:
            return False
        threshold = self._dynamic_sun_threshold("open")
        if threshold is None:
            return False
        passed = sun_elevation > threshold
        return self._condition_held(
            "sun_open",
            passed,
            self._duration_value(CONF_SUN_TIME_DURATION, DEFAULT_SUN_TIME_DURATION),
        )

    def _sun_allows_close(self, sun_elevation: float | None) -> bool:
        if not self._auto_enabled(CONF_AUTO_SUN):
            return True
        if sun_elevation is None:
            return False
        threshold = self._dynamic_sun_threshold("close")
        if threshold is None:
            return False
        passed = sun_elevation < threshold
        return self._condition_held(
            "sun_close",
            passed,
            self._duration_value(CONF_SUN_TIME_DURATION, DEFAULT_SUN_TIME_DURATION),
        )

    def _brightness_allows_open(self, brightness: float | None) -> bool:
        if not self._auto_enabled(CONF_AUTO_BRIGHTNESS) or brightness is None:
            return True
        threshold = _coerce_float(self.config.get(CONF_BRIGHTNESS_OPEN_ABOVE))
        if threshold is None:
            threshold = float(DEFAULT_BRIGHTNESS_OPEN)
        hysteresis = self._number_value(
            CONF_BRIGHTNESS_HYSTERESIS, DEFAULT_BRIGHTNESS_HYSTERESIS
        )
        passed = brightness > threshold + hysteresis
        return self._condition_held(
            "brightness_open",
            passed,
            self._duration_value(
                CONF_BRIGHTNESS_TIME_DURATION, DEFAULT_BRIGHTNESS_TIME_DURATION
            ),
        )

    def _brightness_allows_close(self, brightness: float | None) -> bool:
        if not self._auto_enabled(CONF_AUTO_BRIGHTNESS) or brightness is None:
            return True
        threshold = _coerce_float(self.config.get(CONF_BRIGHTNESS_CLOSE_BELOW))
        if threshold is None:
            threshold = float(DEFAULT_BRIGHTNESS_CLOSE)
        hysteresis = self._number_value(
            CONF_BRIGHTNESS_HYSTERESIS, DEFAULT_BRIGHTNESS_HYSTERESIS
        )
        passed = brightness < threshold - hysteresis
        return self._condition_held(
            "brightness_close",
            passed,
            self._duration_value(
                CONF_BRIGHTNESS_TIME_DURATION, DEFAULT_BRIGHTNESS_TIME_DURATION
            ),
        )

    def _environment_allows_opening(
        self, sun_elevation: float | None, brightness: float | None
    ) -> bool:
        return self._brightness_allows_open(brightness) and self._sun_allows_open(
            sun_elevation
        )

    def _environment_allows_closing(
        self, sun_elevation: float | None, brightness: float | None
    ) -> bool:
        return (
            self._auto_enabled(CONF_AUTO_BRIGHTNESS)
            and self._brightness_allows_close(brightness)
        ) or (
            self._auto_enabled(CONF_AUTO_SUN)
            and self._sun_allows_close(sun_elevation)
        )

    def _number_value(self, key: str, default: float) -> float:
        value = _coerce_float(self.config.get(key, default))
        return default if value is None else value

    def _duration_value(self, key: str, default: int) -> int:
        value = _coerce_float(self.config.get(key, default))
        if value is None:
            return default
        return max(0, int(value))

    def _condition_held(self, key: str, passed: bool, seconds: int) -> bool:
        if not passed:
            self._condition_since.pop(key, None)
            return False
        if seconds <= 0:
            return True
        now = dt_util.utcnow()
        start = self._condition_since.setdefault(key, now)
        return now - start >= timedelta(seconds=seconds)

    def _config_bool(self, key: str) -> bool:
        return bool(
            self.config.get(key, DEFAULT_BEHAVIOR_SETTINGS.get(key, False))
        )

    def _is_awning(self) -> bool:
        return (
            str(
                self.config.get(
                    CONF_COVER_TYPE,
                    DEFAULT_BEHAVIOR_SETTINGS.get(CONF_COVER_TYPE, "blind"),
                )
            )
            == CONF_COVER_TYPE_AWNING
        )

    def _position_is_above(self, current: float | None, target: float | None) -> bool:
        if current is None or target is None:
            return False
        return current < target if self._is_awning() else current > target

    def _position_is_below(self, current: float | None, target: float | None) -> bool:
        if current is None or target is None:
            return False
        return current > target if self._is_awning() else current < target

    def _target_is_opening_move(self, target: float | None) -> bool:
        current = self._current_position()
        return self._position_is_above(target, current)

    def _close_position_protected(self, current: float | None) -> bool:
        close_position = self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION)
        shading_position = self._position_value(
            CONF_SHADING_POSITION, DEFAULT_SHADING_POSITION
        )
        if (
            self._config_bool(CONF_PREVENT_HIGHER_POSITION_CLOSING)
            and self._position_is_below(current, close_position)
        ):
            return True
        if (
            self._config_bool(CONF_PREVENT_LOWERING_WHEN_CLOSING_IF_SHADED)
            and self._reason in {"shading", "manual_shading"}
            and not self._position_is_above(shading_position, close_position)
        ):
            return True
        return False

    def _action_already_done_today(self, action: str, flag_key: str) -> bool:
        if not self._config_bool(flag_key):
            return False
        last_date = self._last_action_dates.get(action)
        return last_date == dt_util.as_local(dt_util.utcnow()).date()

    def _shading_conditions(
        self, sun_azimuth: float | None, sun_elevation: float | None, brightness: float | None
    ) -> bool:
        if sun_azimuth is None or sun_elevation is None:
            return False
        if brightness is None:
            return False
        if not self._weather_allows_shading():
            return False
        az_start = self._number_value(CONF_SUN_AZIMUTH_START, 90)
        az_end = self._number_value(CONF_SUN_AZIMUTH_END, 270)
        el_min = self._number_value(CONF_SUN_ELEVATION_MIN, 10)
        el_max = self._number_value(CONF_SUN_ELEVATION_MAX, 70)
        bright_start = self._number_value(
            CONF_SHADING_BRIGHTNESS_START, DEFAULT_SHADING_BRIGHTNESS_START
        )
        bright_end = self._number_value(
            CONF_SHADING_BRIGHTNESS_END, DEFAULT_SHADING_BRIGHTNESS_END
        )
        if not (az_start <= sun_azimuth <= az_end and el_min <= sun_elevation <= el_max):
            return False
        shading_active = self._status_active("shading") or self._reason in {
            "shading",
            "manual_shading",
        }
        brightness_limit = bright_end if shading_active else bright_start
        if brightness < brightness_limit:
            return False
        temp_ok = self._temperature_allows_shading()
        return temp_ok or (shading_active and brightness >= bright_end) or brightness >= bright_start

    def _temperature_allows_shading(self) -> bool:
        indoor = _float_state(self.hass, self.config.get(CONF_TEMPERATURE_SENSOR_INDOOR))
        outdoor = _float_state(self.hass, self.config.get(CONF_TEMPERATURE_SENSOR_OUTDOOR))
        threshold = float(self.config.get(CONF_TEMPERATURE_THRESHOLD))
        forecast_threshold = self.config.get(CONF_TEMPERATURE_FORECAST_THRESHOLD)
        forecast_hot = False
        try:
            forecast_limit = float(forecast_threshold)
        except (TypeError, ValueError):
            forecast_limit = None

        forecast_sensor = self.config.get(CONF_SHADING_FORECAST_SENSOR)
        forecast_temp: float | None = None
        if forecast_sensor:
            state = self.hass.states.get(forecast_sensor)
            if state is not None:
                # Sensor case: state value contains temperature
                if state.entity_id.startswith("sensor."):
                    try:
                        forecast_temp = float(state.state)
                    except (TypeError, ValueError):
                        forecast_temp = None
                # Weather case: use first forecast item temperature/templow
                if state.entity_id.startswith("weather."):
                    forecast = state.attributes.get("forecast")
                    if isinstance(forecast, list) and forecast:
                        first = forecast[0] or {}
                        for key in ("temperature", "templow"):
                            value = first.get(key)
                            if value is None:
                                continue
                            try:
                                forecast_temp = float(value)
                            except (TypeError, ValueError):
                                forecast_temp = None
                            else:
                                break

        if forecast_limit is not None and forecast_temp is not None:
            forecast_hot = forecast_temp >= forecast_limit
        elif forecast_limit is not None:
            forecast_hot = forecast_limit > 0
        if indoor is not None and indoor >= threshold:
            return True
        if outdoor is not None and outdoor >= threshold:
            return True
        return forecast_hot

    def _weather_allows_shading(self) -> bool:
        weather_entity = self.config.get(CONF_SHADING_FORECAST_SENSOR)
        conditions: list[str] = self.config.get(CONF_SHADING_WEATHER_CONDITIONS) or []
        if not weather_entity or not conditions:
            return True

        state = self.hass.states.get(weather_entity)
        if state is None:
            return False

        if state.entity_id.split(".")[0] != "weather":
            return False

        forecast_type = self.config.get(
            CONF_SHADING_FORECAST_TYPE, DEFAULT_SHADING_FORECAST_TYPE
        )
        condition_value: str | None = None

        if forecast_type == "weather_attributes" or forecast_type is None:
            condition_value = state.state
        else:
            forecast = state.attributes.get("forecast")
            if isinstance(forecast, list) and forecast:
                entry = forecast[0] or {}
                value = entry.get("condition")
                if isinstance(value, str):
                    condition_value = value

        return condition_value in conditions

    def _is_workday(self) -> bool:
        workday_entity = self.config.get(CONF_WORKDAY_SENSOR)
        if not workday_entity:
            return True
        return self.hass.states.is_state(workday_entity, STATE_ON)

    def _is_workday_tomorrow(self) -> bool:
        tomorrow_entity = self.config.get(CONF_WORKDAY_TOMORROW_SENSOR)
        if not tomorrow_entity:
            return self._is_workday()
        return self.hass.states.is_state(tomorrow_entity, STATE_ON)

    def _single_contact_active(self, entity_id: str, now: datetime) -> bool:
        state = self.hass.states.get(entity_id)
        if state is None or state.state != STATE_ON:
            return False

        last_changed = getattr(state, "last_changed", None)
        if last_changed:
            last_changed = dt_util.as_utc(last_changed)
        else:
            last_changed = now

        trigger_delay = max(0, int(self.config.get(CONF_CONTACT_TRIGGER_DELAY, 0) or 0))
        status_delay = max(0, int(self.config.get(CONF_CONTACT_STATUS_DELAY, 0) or 0))
        required_seconds = max(trigger_delay, status_delay)
        if required_seconds and (now - last_changed) < timedelta(seconds=required_seconds):
            return False
        return True

    def _contacts_active(self, entity_ids: list[str], now: datetime) -> bool:
        return any(self._single_contact_active(entity_id, now) for entity_id in entity_ids)

    def _tilt_contact_active(self, now: datetime) -> bool:
        sensors = self._tilt_sensors()
        if not sensors:
            return False

        delay_after_close = max(
            0, int(self.config.get(CONF_VENTILATION_DELAY_AFTER_CLOSE, 0) or 0)
        )

        if self._contacts_active(sensors, now):
            return True

        if not delay_after_close:
            return False

        for sensor in sensors:
            state = self.hass.states.get(sensor)
            if state is None:
                continue
            if state.state == STATE_ON:
                continue
            last_changed = getattr(state, "last_changed", None)
            last_changed = dt_util.as_utc(last_changed) if last_changed else now
            if (now - last_changed) < timedelta(seconds=delay_after_close):
                return True
        return False


    def _is_resident_sleeping(self) -> bool:
        resident_entity = self.config.get(CONF_RESIDENT_SENSOR)
        if not resident_entity:
            return False
        state = self.hass.states.get(resident_entity)
        return self._resident_state_is_on(state.state if state else None)

    @staticmethod
    def _resident_state_is_on(value: str | None) -> bool:
        return value in {STATE_ON, "true"}

    @staticmethod
    def _resident_state_is_off(value: str | None) -> bool:
        return value in {"off", "false"}

    def _time_from_config(self, key: str) -> time | None:
        configured = self.config.get(key)
        parsed = _parse_time(configured)
        if parsed:
            return parsed
        fallback = DEFAULT_TIME_SETTINGS.get(key)
        return _parse_time(fallback) if fallback is not None else None

    def _calendar_window(self, title_key: str, now: datetime) -> tuple[datetime, datetime] | None:
        calendar_entity = self.config.get(CONF_CALENDAR_ENTITY)
        title = str(self.config.get(title_key) or "").strip().lower()
        if not calendar_entity or not title:
            return None

        state = self.hass.states.get(calendar_entity)
        if state is None or state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
            return None

        message = str(state.attributes.get("message") or "").strip().lower()
        if title not in message:
            return None

        start_raw = state.attributes.get("start_time") or state.attributes.get("start")
        end_raw = state.attributes.get("end_time") or state.attributes.get("end")
        start_dt = dt_util.parse_datetime(str(start_raw)) if start_raw else None
        end_dt = dt_util.parse_datetime(str(end_raw)) if end_raw else None
        if not start_dt or not end_dt:
            return None
        start_dt = dt_util.as_utc(start_dt)
        end_dt = dt_util.as_utc(end_dt)
        if end_dt <= start_dt:
            return None
        return (start_dt, end_dt) if start_dt <= now < end_dt else None

    def _calendar_open_active(self, now: datetime) -> bool:
        return self._calendar_window(CONF_CALENDAR_OPEN_TITLE, now) is not None

    def _calendar_close_active(self, now: datetime) -> bool:
        return self._calendar_window(CONF_CALENDAR_CLOSE_TITLE, now) is not None

    def _time_bounds(self, workday: bool, is_up: bool) -> tuple[time | None, time | None]:
        if workday:
            early_key = (CONF_TIME_UP_EARLY_WORKDAY if is_up else CONF_TIME_DOWN_EARLY_WORKDAY)
            late_key = (CONF_TIME_UP_LATE_WORKDAY if is_up else CONF_TIME_DOWN_LATE_WORKDAY)
        else:
            early_key = (CONF_TIME_UP_EARLY_NON_WORKDAY if is_up else CONF_TIME_DOWN_EARLY_NON_WORKDAY)
            late_key = (CONF_TIME_UP_LATE_NON_WORKDAY if is_up else CONF_TIME_DOWN_LATE_NON_WORKDAY)

        return self._time_from_config(early_key), self._time_from_config(late_key)

    def _within_time_window(
        self, now: datetime, start: time | None, end: time | None
    ) -> bool:
        if not start or not end:
            return False

        local_now = dt_util.as_local(now)

        start_dt = datetime.combine(local_now.date(), start, local_now.tzinfo)
        end_dt = datetime.combine(local_now.date(), end, local_now.tzinfo)
        if end_dt <= start_dt:
            end_dt = end_dt + timedelta(days=1)

        for offset in (0, -1):
            window_start = start_dt + timedelta(days=offset)
            window_end = end_dt + timedelta(days=offset)
            if window_start <= local_now < window_end:
                return True
        return False

    def _today_at(self, now: datetime, point: time | None) -> datetime | None:
        if not point:
            return None
        local_now = dt_util.as_local(now)
        return datetime.combine(local_now.date(), point, local_now.tzinfo)

    def _within_opening_phase(self, now: datetime) -> bool:
        workday = self._is_workday()
        early, late = self._time_bounds(workday, True)
        return self._within_time_window(now, early, late)

    def _within_daytime_phase(self, now: datetime) -> bool:
        workday = self._is_workday()
        workday_tomorrow = self._is_workday_tomorrow()
        open_early, _open_late = self._time_bounds(workday, True)
        close_early, _close_late = self._time_bounds(workday_tomorrow, False)
        return self._within_time_window(now, open_early, close_early)

    def _within_closing_phase(self, now: datetime) -> bool:
        workday_tomorrow = self._is_workday_tomorrow()
        early, late = self._time_bounds(workday_tomorrow, False)
        return self._within_time_window(now, early, late)

    def _within_evening_phase(self, now: datetime) -> bool:
        workday_tomorrow = self._is_workday_tomorrow()
        early, _late = self._time_bounds(workday_tomorrow, False)
        start = self._today_at(now, early)
        return bool(start and dt_util.as_local(now) >= start)

    def _is_time_up_late(self, now: datetime) -> bool:
        workday = self._is_workday()
        workday_tomorrow = self._is_workday_tomorrow()
        _open_early, open_late = self._time_bounds(workday, True)
        close_early, _close_late = self._time_bounds(workday_tomorrow, False)
        local_now = dt_util.as_local(now)
        late_dt = self._today_at(now, open_late)
        close_early_dt = self._today_at(now, close_early)
        return bool(
            late_dt
            and close_early_dt
            and local_now >= late_dt
            and local_now < close_early_dt
        )

    def _is_time_down_late(self, now: datetime) -> bool:
        workday_tomorrow = self._is_workday_tomorrow()
        _early, late = self._time_bounds(workday_tomorrow, False)
        late_dt = self._today_at(now, late)
        return bool(late_dt and dt_util.as_local(now) >= late_dt)

    def _position_value(self, key: str, default: float) -> float | None:
        raw_value = self.config.get(key, default)
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return default

    def _normalize_position(self, value: float | int | None, default: float) -> float:
        try:
            position = float(value)
        except (TypeError, ValueError):
            position = default
        return max(0.0, min(100.0, position))

    def _auto_enabled(self, config_key: str) -> bool:
        if not self._master_enabled():
            return False
        manager = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id)
        if isinstance(manager, ControllerManager):
            runtime_override = manager.get_runtime_toggle(config_key)
            if runtime_override is not None:
                return runtime_override
        entity_key = self._auto_entity_map.get(config_key)
        if entity_key:
            entity_id = self.config.get(entity_key)
            if entity_id and self.hass.states.get(entity_id) is not None:
                return self.hass.states.is_state(entity_id, STATE_ON)
        return bool(self.config.get(config_key))

    async def _condition_allows(self, config_key: str) -> bool:
        condition_config = self.config.get(config_key)
        if condition_config in (None, "", []):
            return True

        if isinstance(condition_config, bool):
            return condition_config

        if isinstance(condition_config, str):
            state = self.hass.states.get(condition_config)
            if state is None:
                return False
            return self.hass.states.is_state(condition_config, STATE_ON)

        if not isinstance(condition_config, (list, dict)):
            _LOGGER.error(
                "Invalid additional condition '%s': unsupported type %s",
                config_key,
                type(condition_config).__name__,
            )
            return False

        try:
            config: dict = (
                {"condition": "and", "conditions": condition_config}
                if isinstance(condition_config, list)
                else condition_config
            )
            normalized_config = self._normalize_condition_config(config)
            validated_config = await condition.async_validate_condition_config(
                self.hass, normalized_config
            )
            check = await condition.async_from_config(self.hass, validated_config)
            result = check(self.hass)
            if isawaitable(result):
                result = await result
            return bool(result)
        except ConditionError as err:  # pragma: no cover - defensive for invalid config
            _LOGGER.error(
                "Invalid additional condition '%s': %s (config=%s)",
                config_key,
                err,
                condition_config,
            )
            return False
        except Exception:  # pragma: no cover - defensive for runtime errors
            _LOGGER.exception("Failed to evaluate additional condition: %s", config_key)
            return False

    def _normalize_condition_config(self, config: dict | list) -> dict | list:
        """Normalize condition configuration to match Home Assistant expectations.

        Converts string-based time values into ``datetime.time`` objects so they are
        not misinterpreted as entity IDs during validation. Nested condition blocks
        are processed recursively.
        """

        if isinstance(config, list):
            return [self._normalize_condition_config(item) for item in config]

        normalized = dict(config)
        condition_type = normalized.get("condition")

        if condition_type == "time":
            for key in ("after", "before"):
                value = normalized.get(key)
                if isinstance(value, str):
                    parsed = dt_util.parse_time(value)
                    if parsed is not None:
                        normalized[key] = parsed

        if condition_type in {"and", "or", "not"}:
            normalized["conditions"] = [
                self._normalize_condition_config(item)
                for item in normalized.get("conditions", [])
            ]

        return normalized

    def _master_enabled(self) -> bool:
        return bool(self.config.get(CONF_MASTER_ENABLED, DEFAULT_MASTER_FLAGS[CONF_MASTER_ENABLED]))

    def _fire_event(self, kind: str, data: dict | None = None) -> None:
        payload: dict[str, object] = {
            "kind": kind,
            "entry_id": self.entry.entry_id,
            "cover": self.cover,
            "master_entity_id": self._master_entity_id,
            "timestamp": dt_util.utcnow().isoformat(),
        }

        if self._reason:
            payload["reason"] = self._reason

        if data:
            payload.update(
                {k: v.isoformat() if isinstance(v, datetime) else v for k, v in data.items()}
            )

        self.hass.bus.async_fire(EVENT_COVER_CONTROL, payload)

    def _cover_state_or_warn(
        self,
        service: str,
        *,
        reason: str | None = None,
        trigger: str | None = None,
        target_position: float | None = None,
    ) -> State | None:
        state = self.hass.states.get(self.cover)
        if state is None or state.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
            _LOGGER.warning(
                "Cover Control skipping %s for %s: entity is missing or unavailable",
                service,
                self.cover,
            )
            self._fire_event(
                "command",
                {
                    "service": service,
                    "reason": reason or self._reason,
                    "trigger": trigger,
                    "target_position": target_position,
                    "skipped": "unavailable",
                },
            )
            return None
        return state

    async def _set_position(self, position: float | None, reason: str) -> None:
        if position is None:
            return
        tolerance = float(
            self._position_value(CONF_POSITION_TOLERANCE, DEFAULT_TOLERANCE)
        )
        current = self._current_position()
        if current is not None and abs(current - float(position)) <= tolerance:
            if self._reason is None:
                self._reason = reason
            self._target = float(position)
            self._record_action_status(reason, float(position))
            self._publish_state()
            return
        await self._command_position(float(position), reason=reason)
        self._target = float(position)
        self._reason = reason
        self._record_action_status(reason, float(position))
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

    def _current_position(self) -> float | None:
        state = self.hass.states.get(self.cover)
        if not state:
            return None
        try:
            if "current_position" in state.attributes:
                return float(state.attributes["current_position"])
            if "position" in state.attributes:
                return float(state.attributes["position"])
            if state.state == "open" or state.state == "opening":
                return 100.0
            if state.state == "closed" or state.state == "closing":
                return 0.0
            return float(state.state)
        except (TypeError, ValueError):
            return None

    def _full_open_sensors(self) -> list[str]:
        mapping = self.config.get(CONF_WINDOW_SENSOR_FULL) or {}
        sensors = mapping.get(self.cover, [])
        if isinstance(sensors, str):
            return [sensors]
        if isinstance(sensors, list):
            return [sensor for sensor in sensors if isinstance(sensor, str)]
        return []

    def _tilt_sensors(self) -> list[str]:
        mapping = self.config.get(CONF_WINDOW_SENSOR_TILT) or {}
        sensors = mapping.get(self.cover, [])
        if isinstance(sensors, str):
            return [sensors]
        if isinstance(sensors, list):
            return [sensor for sensor in sensors if isinstance(sensor, str)]
        return []

    def _contact_entities(self) -> list[str]:
        sensors: list[str] = []
        for sensor in self._full_open_sensors() + self._tilt_sensors():
            if sensor not in sensors:
                sensors.append(sensor)
        return sensors

    def _refresh_next_events(self, now: datetime) -> None:

        sun_enabled = self._auto_enabled(CONF_AUTO_SUN)
        time_up_enabled = self._auto_enabled(CONF_AUTO_TIME) and self._auto_enabled(CONF_AUTO_UP)
        time_down_enabled = self._auto_enabled(CONF_AUTO_TIME) and self._auto_enabled(CONF_AUTO_DOWN)
        sun_state = self.hass.states.get("sun.sun") if sun_enabled else None
        sun_next_rising = self._parse_datetime_attr(
            sun_state and sun_state.attributes.get("next_rising")
        )
        sun_next_setting = self._parse_datetime_attr(
            sun_state and sun_state.attributes.get("next_setting")
        )
        open_threshold = self._dynamic_sun_threshold("open")
        close_threshold = self._dynamic_sun_threshold("close")
        mode = str(
            self.config.get(CONF_SUN_ELEVATION_MODE, DEFAULT_SUN_ELEVATION_MODE)
            or DEFAULT_SUN_ELEVATION_MODE
        ).lower()
        if mode == "hybid":
            mode = "hybrid"

        sun_open_target = (
            self._next_sun_time_for_elevation(
                open_threshold, SunDirection.RISING, now
            )
            if sun_enabled
            else None
        )
        sun_close_target = (
            self._next_sun_time_for_elevation(
                close_threshold, SunDirection.SETTING, now
            )
            if sun_enabled
            else None
        )

        workday = self._is_workday()
        workday_tomorrow = self._is_workday_tomorrow()
        up_early_time, up_late_time = self._time_bounds(workday, True)
        down_early_time, down_late_time = self._time_bounds(workday_tomorrow, False)

        next_up_early, next_up_late = self._window_points(up_early_time, up_late_time, now)
        next_down_early, next_down_late = self._window_points(
            down_early_time, down_late_time, now
        )

        def _clamp_candidate(
            candidate: datetime | None,
            earliest: datetime | None,
            latest: datetime | None,
            fallback_candidates: tuple[datetime | None, datetime | None],
        ) -> datetime | None:
            base = candidate
            if earliest and base and base < earliest:
                base = earliest
            if latest and base and base > latest:
                base = latest
            if base:
                return base

            future_fallbacks = sorted(
                point for point in fallback_candidates if point is not None and point >= now
            )
            return future_fallbacks[0] if future_fallbacks else None

        if sun_enabled and mode in {"dynamic", "hybrid"}:
            # Dynamic/Hybrid use the elevation-based calculation first.
            # If unavailable, fall back to the native sun integration times
            # so next_open/next_close still remain sun-based.
            open_base = sun_open_target or sun_next_rising
            close_base = sun_close_target or sun_next_setting
        else:
            open_base = (sun_open_target or sun_next_rising) if sun_enabled else None
            close_base = (sun_close_target or sun_next_setting) if sun_enabled else None

        if time_up_enabled:
            self._next_open = _clamp_candidate(
                open_base, next_up_early, next_up_late, (next_up_early, next_up_late)
            )
        else:
            self._next_open = open_base

        if time_down_enabled:
            self._next_close = _clamp_candidate(
                close_base,
                next_down_early,
                next_down_late,
                (next_down_early, next_down_late),
            )
        else:
            self._next_close = close_base

        # Avoid reporting identical timestamps when the clamped opening and closing
        # targets converge. Prefer the next distinct closing point that still
        # respects the configured window.
        if self._next_open and self._next_close and self._next_open == self._next_close:

            later_close = sorted(
                [
                point
                for point in (next_down_early, next_down_late)
                if point and point > self._next_open
                ]
            )
            if later_close:
                self._next_close = later_close[0]


    def _parse_datetime_attr(self, value: datetime | str | None) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if not value:
            return None
        parsed = dt_util.parse_datetime(str(value))
        if parsed:
            return dt_util.as_utc(parsed)
        return None

    def _next_sun_time_for_elevation(
        self, elevation: float | int | str | None, direction: SunDirection, now: datetime
    ) -> datetime | None:
        try:
            elevation_value = float(elevation)
        except (TypeError, ValueError):
            return None

        if (
            self.hass.config.latitude is None
            or self.hass.config.longitude is None
            or self.hass.config.time_zone is None
        ):
            return None

        location = LocationInfo(
            latitude=self.hass.config.latitude,
            longitude=self.hass.config.longitude,
            timezone=self.hass.config.time_zone,
        )

        tzinfo = dt_util.get_time_zone(location.timezone)
        if tzinfo is None:
            return None

        local_now = dt_util.as_local(now)
        for day_offset in range(3):
            target_date = local_now.date() + timedelta(days=day_offset)
            try:
                event_local = time_at_elevation(
                    location.observer,
                    elevation_value,
                    date=target_date,
                    direction=direction,
                    tzinfo=tzinfo,
                )
            except (ValueError, TypeError):
                continue

            if not isinstance(event_local, datetime):
                continue

            event_utc = dt_util.as_utc(event_local)
            if event_utc > now:
                return event_utc

        return None

    def _next_time_for_point(self, scheduled: time | None, now: datetime) -> datetime | None:
        if not scheduled:
            return None
        local_now = dt_util.as_local(now)
        candidate_local = datetime.combine(local_now.date(), scheduled, local_now.tzinfo)
        if candidate_local <= local_now:
            candidate_local = candidate_local + timedelta(days=1)
        return dt_util.as_utc(candidate_local)

    def _window_points(
        self, early: time | None, late: time | None, now: datetime
    ) -> tuple[datetime | None, datetime | None]:
        """Return early/late bounds for the current actionable window.

        A plain "next time" calculation moves a passed early bound to tomorrow.
        During today's still-open window this would make room sensors report
        tomorrow's close/open instead of today's remaining late fallback.
        """

        local_now = dt_util.as_local(now)
        today = local_now.date()
        tzinfo = local_now.tzinfo

        early_local = datetime.combine(today, early, tzinfo) if early else None
        late_local = datetime.combine(today, late, tzinfo) if late else None

        if late_local and local_now > late_local:
            early_local = (
                datetime.combine(today + timedelta(days=1), early, tzinfo)
                if early
                else None
            )
            late_local = datetime.combine(today + timedelta(days=1), late, tzinfo)
        elif not late_local and early_local and local_now > early_local:
            early_local = datetime.combine(today + timedelta(days=1), early, tzinfo)

        return (
            dt_util.as_utc(early_local) if early_local else None,
            dt_util.as_utc(late_local) if late_local else None,
        )

    def _publish_state(self) -> None:
        current_position = self._current_position()
        shading_enabled = self._auto_enabled(CONF_AUTO_SHADING)
        shading_active = self._shading_is_active(current_position, shading_enabled)
        ventilation_active = self._ventilation_is_active(current_position)
        async_dispatcher_send(
            self.hass,
            SIGNAL_STATE_UPDATED,
            self.entry.entry_id,
            self.cover,
            self._target,
            self._reason or IDLE_REASON,
            self._manual_until,
            self._manual_active,
            self._next_open,
            self._next_close,
            current_position,
            shading_enabled,
            shading_active,
            ventilation_active,
        )

    def _position_matches(self, target: float | None, current: float | None) -> bool:
        if target is None or current is None:
            return False
        tolerance = float(self._position_value(CONF_POSITION_TOLERANCE, DEFAULT_TOLERANCE))
        return abs(current - float(target)) <= tolerance

    def _shading_is_active(self, current_position: float | None, shading_enabled: bool) -> bool:
        if not shading_enabled:
            return False
        if self._reason not in {"shading", "manual_shading"}:
            return False
        shading_target = self._position_value(CONF_SHADING_POSITION, DEFAULT_SHADING_POSITION)
        return self._position_matches(shading_target, current_position)

    def _ventilation_is_active(self, current_position: float | None) -> bool:
        if self._reason not in {"ventilation", "ventilation_full"}:
            return False
        if self._reason == "ventilation_full":
            vent_target = self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION)
        else:
            vent_target = self._position_value(
                CONF_VENTILATE_POSITION, DEFAULT_VENTILATE_POSITION
            )
        return self._position_matches(vent_target, current_position)

    async def _open_cover(self, target: float | None = None, reason: str | None = None) -> None:
        """Open the cover using the native service call.

        The optional ``target`` argument is accepted for backward compatibility with
        earlier recalibration flows that passed a desired open position even though
        the service call itself does not use it.
        """
        ctx = Context()
        message_reason = reason or self._reason
        if not self._cover_state_or_warn(
            "open_cover", reason=message_reason, target_position=target
        ):
            return
        self._last_command_context_id = ctx.id
        self._last_command_at = dt_util.utcnow()
        _LOGGER.info(
            "Cover Control issuing open command for %s (reason=%s)",
            self.cover,
            message_reason,
        )
        self._fire_event(
            "command",
            {
                "service": "open_cover",
                "reason": message_reason,
                "target_position": target,
            },
        )
        await self.hass.services.async_call(
            "cover",
            "open_cover",
            {"entity_id": self.cover},
            blocking=True,
            context=ctx,
        )

    async def _command_position(
        self, position: float, *, reason: str | None = None, trigger: str | None = None
    ) -> None:
        state = self._cover_state_or_warn(
            "set_cover_position", reason=reason, trigger=trigger, target_position=position
        )
        if not state:
            return
        supported = (state.attributes.get("supported_features")) or 0
        supports_position = bool(int(supported) & CoverEntityFeature.SET_POSITION)

        ctx = Context()
        self._last_command_context_id = ctx.id
        self._last_command_at = dt_util.utcnow()
        message_reason = reason or self._reason
        service: str = "set_cover_position"
        service_data = {"entity_id": self.cover, "position": float(position)}
        if supports_position:
            pass
        else:
            if position >= 99.5:
                service = "open_cover"
                service_data = {"entity_id": self.cover}
            elif position <= 0.5:
                service = "close_cover"
                service_data = {"entity_id": self.cover}

        _LOGGER.info(
            "Cover Control moving %s via %s to %.1f%% (reason=%s, trigger=%s)",
            self.cover,
            service,
            float(position),
            message_reason,
            trigger,
        )
        self._fire_event(
            "command",
            {
                "service": service,
                "reason": message_reason,
                "trigger": trigger,
                "target_position": float(position),
            },
        )
        await self.hass.services.async_call(
            "cover", service, service_data, blocking=True, context=ctx
        )

    async def _wait_for_position(
        self, target: float, tolerance: float, timeout: int = 30
    ) -> None:
        if self._current_position() is None:
            return
        end = dt_util.utcnow() + timedelta(seconds=timeout)
        while dt_util.utcnow() < end:
            current = self._current_position()
            if current is not None and abs(current - target) <= tolerance:
                return
            await asyncio.sleep(1)
