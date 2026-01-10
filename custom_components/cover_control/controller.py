"""Core controller logic derived from the Cover Control Automation blueprint."""
from __future__ import annotations

import asyncio
import logging
from inspect import isawaitable
from datetime import datetime, timedelta, time

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
    CONF_BRIGHTNESS_CLOSE_BELOW,
    CONF_BRIGHTNESS_OPEN_ABOVE,
    CONF_BRIGHTNESS_SENSOR,
    CONF_CLOSE_POSITION,
    CONF_COVERS,
    CONF_CONTACT_STATUS_DELAY,
    CONF_CONTACT_TRIGGER_DELAY,
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
    CONF_RESIDENT_SENSOR,
    CONF_SHADING_FORECAST_SENSOR,
    CONF_SHADING_FORECAST_TYPE,
    CONF_SHADING_WEATHER_CONDITIONS,
    CONF_SHADING_BRIGHTNESS_END,
    CONF_SHADING_BRIGHTNESS_START,
    CONF_SHADING_POSITION,
    CONF_SUN_AZIMUTH_END,
    CONF_SUN_AZIMUTH_START,
    CONF_SUN_ELEVATION_CLOSE,
    CONF_SUN_ELEVATION_MAX,
    CONF_SUN_ELEVATION_MIN,
    CONF_SUN_ELEVATION_OPEN,
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
    DEFAULT_AUTOMATION_FLAGS,
    DEFAULT_MANUAL_OVERRIDE_MINUTES,
    DEFAULT_MANUAL_OVERRIDE_FLAGS,
    DEFAULT_MANUAL_OVERRIDE_RESET_TIME,
    DEFAULT_MASTER_FLAGS,
    DEFAULT_POSITION_SETTINGS,
    DEFAULT_TIME_SETTINGS,
    DEFAULT_TIME_DOWN_LATE_NON_WORKDAY,
    DEFAULT_TIME_DOWN_EARLY_NON_WORKDAY,
    DEFAULT_TIME_DOWN_EARLY_WORKDAY,
    DEFAULT_TIME_DOWN_LATE_WORKDAY,
    DEFAULT_TIME_UP_EARLY_NON_WORKDAY,
    DEFAULT_TIME_UP_LATE_NON_WORKDAY,
    DEFAULT_TIME_UP_LATE_WORKDAY,
    DEFAULT_TIME_UP_EARLY_WORKDAY,
    DEFAULT_OPEN_POSITION,
    DEFAULT_TOLERANCE,
    DEFAULT_VENTILATE_POSITION,
    DEFAULT_SHADING_POSITION,
    DEFAULT_CLOSE_POSITION,
    DEFAULT_SHADING_FORECAST_TYPE,
    DOMAIN,
    SIGNAL_STATE_UPDATED,
    MANUAL_OVERRIDE_RESET_NONE,
    MANUAL_OVERRIDE_RESET_TIME,
    MANUAL_OVERRIDE_RESET_TIMEOUT,
    EVENT_COVER_CONTROL,
)

IDLE_REASON = "idle"
_LOGGER = logging.getLogger(__name__)

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
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


class ControllerManager:
    """Create and coordinate per-cover controllers."""

    def __init__(self, hass: HomeAssistant, entry: config_entries.ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.controllers: dict[str, CoverController] = {}

    async def async_setup(self) -> None:
        data = {
            **DEFAULT_POSITION_SETTINGS,
            **DEFAULT_TIME_SETTINGS,
            **DEFAULT_AUTOMATION_FLAGS,
            **DEFAULT_MANUAL_OVERRIDE_FLAGS,
            **self.entry.data,
            **self.entry.options,
        }
        for cover in data.get(CONF_COVERS, []):
            controller = CoverController(self.hass, self.entry, cover, data)
            await controller.async_setup()
            self.controllers[cover] = controller

    async def async_unload(self) -> None:
        for controller in self.controllers.values():
            await controller.async_unload()
        self.controllers.clear()

    @callback
    def async_update_options(self) -> None:
        new_data = {
            **DEFAULT_POSITION_SETTINGS,
            **DEFAULT_TIME_SETTINGS,
            **DEFAULT_AUTOMATION_FLAGS,
            **DEFAULT_MANUAL_OVERRIDE_FLAGS,
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

    async def recalibrate_cover(self, cover: str, full_open: float | None) -> bool:
        controller = self.controllers.get(cover)
        if not controller:
            return False
        await controller.recalibrate(full_open)
        return True
    
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

    def __init__(self, hass: HomeAssistant, entry: config_entries.ConfigEntry, cover: str, config: ConfigType) -> None:
        self.hass = hass
        self.entry = entry
        self.cover = cover
        self.config = config
        self._unsubs: list[CALLBACK_TYPE] = []
        self._manual_until: datetime | None = None
        self._manual_active: bool = False
        self._manual_scope_all: bool = False
        self._target: float | None = None
        self._last_position: float | None = None
        self._last_command_at: datetime | None = None
        self._manual_expire_unsub: CALLBACK_TYPE | None = None
        self._last_command_context_id: str | None = None
        self._reason: str | None = None
        self._next_open: datetime | None = None
        self._next_close: datetime | None = None
        self._master_entity_id: str | None = None
        # Position helpers were removed, but keep the mapping available so
        # legacy config entries that still reference helper entities do not
        # cause attribute errors during lookups.
        self._position_entity_map: dict[str, str] = {}
        self._auto_entity_map = {
            CONF_AUTO_UP: CONF_AUTO_UP_ENTITY,
            CONF_AUTO_DOWN: CONF_AUTO_DOWN_ENTITY,
            CONF_AUTO_BRIGHTNESS: CONF_AUTO_BRIGHTNESS_ENTITY,
            CONF_AUTO_SUN: CONF_AUTO_SUN_ENTITY,
            CONF_AUTO_VENTILATE: CONF_AUTO_VENTILATE_ENTITY,
            CONF_AUTO_SHADING: CONF_AUTO_SHADING_ENTITY,
        }

    async def async_setup(self) -> None:
        registry = er.async_get(self.hass)
        self._master_entity_id = registry.async_get_entity_id(
            "switch", DOMAIN, f"{self.entry.entry_id}-master"
        )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._handle_interval, timedelta(minutes=1))
        )
        self._unsubs.append(self.hass.bus.async_listen("call_service", self._handle_service_call))
        self._target = self._current_position()
        self._last_position = self._target
        sensor_entities = {
            self.config.get(CONF_BRIGHTNESS_SENSOR),
            self.config.get(CONF_WORKDAY_SENSOR),
            self.config.get(CONF_TEMPERATURE_SENSOR_INDOOR),
            self.config.get(CONF_TEMPERATURE_SENSOR_OUTDOOR),
            self.config.get(CONF_RESIDENT_SENSOR),
            self.config.get(CONF_SHADING_FORECAST_SENSOR),
            self.cover,
        }
        sensor_entities.update(self._contact_sensors())
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
        self._publish_state()


    async def async_unload(self) -> None:
        while self._unsubs:
            unsub = self._unsubs.pop()
            unsub()

    @callback
    def update_config(self, new_config: ConfigType) -> None:
        self.config = new_config
        self._manual_until = None
        self._manual_active = False
        self._manual_scope_all = False
        self._clear_manual_expiry()
        self._target = self._current_position()
        self._last_position = self._target
        now = dt_util.utcnow()
        self._refresh_next_events(now)
        self.hass.async_create_task(self._evaluate("config"))
        self._publish_state()

    @callback
    def _handle_state_event(self, event) -> None:
        now = dt_util.utcnow()
        self._expire_manual_override(now)
        self._ensure_manual_expiry_timer(now)
        previous_position = self._last_position
        if event.data.get("entity_id") == self.cover:
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
        self.hass.async_create_task(self._evaluate("state"))

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
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

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
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

    async def force_ventilation(self, action: str) -> None:
        self._activate_manual_override(scope_all=True, reason="ventilation")
        if action == "start":
            target = self._position_value(CONF_VENTILATE_POSITION, DEFAULT_VENTILATE_POSITION)
            if target is None:
                return
            await self._command_position(float(target), reason="ventilation_start")
            self._target = float(target)
            self._reason = "ventilation"
        elif action == "stop":
            target = self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION)
            if target is None:
                return
            await self._command_position(float(target), reason="ventilation_stop")
            self._target = float(target)
            if self._reason == "ventilation":
                self._reason = None
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
        elif action == "deactivate":
            target = self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION)
            if target is None:
                return
            await self._command_position(float(target), reason="manual_shading_end")
            self._target = float(target)
            if self._reason in {"shading", "manual_shading"}:
                self._reason = None
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
        now = dt_util.utcnow()
        self._refresh_next_events(now)
        self._publish_state()
        self.hass.async_create_task(self._evaluate("manual_expired"))
    async def _evaluate(self, trigger: str) -> None:
        now = dt_util.utcnow()
        self._expire_manual_override(now)
        self._ensure_manual_expiry_timer(now)
        self._refresh_next_events(now)
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

        up_due = self._event_due(self._next_open, now)
        down_due = self._event_due(self._next_close, now)

        brightness = _float_state(self.hass, self.config.get(CONF_BRIGHTNESS_SENSOR))
        sun_state = self.hass.states.get("sun.sun")
        sun_elevation = sun_state and sun_state.attributes.get("elevation")
        sun_azimuth = sun_state and sun_state.attributes.get("azimuth")

        global_condition = await self._condition_allows(CONF_ADDITIONAL_CONDITION_GLOBAL)
        if not global_condition:
            self._refresh_next_events(now)
            self._publish_state()
            return
        
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

        close_condition = conditions[CONF_ADDITIONAL_CONDITION_CLOSE]
        open_condition = conditions[CONF_ADDITIONAL_CONDITION_OPEN]
        ventilation_condition = conditions[CONF_ADDITIONAL_CONDITION_VENTILATE]
        ventilation_end_condition = conditions[CONF_ADDITIONAL_CONDITION_VENTILATE_END]
        shading_condition = conditions[CONF_ADDITIONAL_CONDITION_SHADING]
        shading_tilt_condition = conditions[CONF_ADDITIONAL_CONDITION_SHADING_TILT]
        shading_end_condition = conditions[CONF_ADDITIONAL_CONDITION_SHADING_END]

        if self._is_resident_sleeping():
            if close_condition:
                await self._set_position(
                    self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION),
                    "resident_asleep",
                )
            else:
                self._refresh_next_events(now)
                self._publish_state()
            return

        auto_ventilate = self._auto_enabled(CONF_AUTO_VENTILATE)
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

        time_window_open = self._within_open_close_window(now)

        if auto_ventilate and full_contact_active and ventilation_condition:
            if not self._manual_blocks_action("ventilation"):
                await self._set_position(
                    self._position_value(
                        CONF_VENTILATE_POSITION, DEFAULT_VENTILATE_POSITION
                    ),
                    "ventilation_full",
                )
            return

        current_position = self._current_position()

        if auto_ventilate and tilt_contact_active and ventilation_condition:
            if not self._manual_blocks_action("ventilation"):
                target = self._position_value(
                    CONF_VENTILATE_POSITION, DEFAULT_VENTILATE_POSITION
                )
                allow_higher = bool(
                    self.config.get(CONF_VENTILATION_ALLOW_HIGHER_POSITION, False)
                )
                close_position = self._position_value(
                    CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION
                )
                tolerance = float(
                    self._position_value(CONF_POSITION_TOLERANCE, DEFAULT_TOLERANCE)
                )
                if allow_higher or current_position is None:
                    ready = True
                else:
                    ready = current_position <= (float(close_position) + tolerance)
                if ready:
                    if (
                        current_position is None
                        or current_position < target
                        or (allow_higher and current_position > target)
                    ):
                        await self._set_position(target, "ventilation")
                    else:
                        self._reason = "ventilation"
                        self._publish_state()
            return

        
        post_ventilation = (
            auto_ventilate
            and not ventilation_contact_active
            and self._reason in {"ventilation", "ventilation_full"}
        )

        pending_open_due = False
        if open_condition and not self._manual_blocks_action("open"):
            pending_open_due = (
                (self._auto_enabled(CONF_AUTO_UP) and (up_due or time_window_open))
                or (
                    self._auto_enabled(CONF_AUTO_SUN)
                    and self._sun_allows_open(sun_elevation)
                )
                or (
                    self._auto_enabled(CONF_AUTO_BRIGHTNESS)
                    and brightness is not None
                    and self._brightness_allows_open(brightness)
                )
            )

        if post_ventilation and not ventilation_end_condition and not pending_open_due:
            self._refresh_next_events(now)
            self._publish_state()
            return

        if self._auto_enabled(CONF_AUTO_SHADING) and not self._manual_blocks_action("shading"):
            shading_active = self._reason in {"shading", "manual_shading"}
            shading_allowed = self._shading_conditions(
                sun_azimuth, sun_elevation, brightness
            )
            shading_allowed = shading_allowed and shading_condition
            if tilt_contact_active:
                shading_allowed = shading_allowed and shading_tilt_condition
            if tilt_lock_shading_start and not shading_active:
                shading_allowed = False
            if shading_active and not shading_allowed:
                if not shading_end_condition:
                    self._publish_state()
                    return
                if (
                    auto_ventilate
                    and ventilation_condition
                    and (
                        tilt_lock_shading_end
                        or self.config.get(CONF_VENTILATION_USE_AFTER_SHADING)
                    )
                    and not self._manual_blocks_action("ventilation")
                ):
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
                    self._auto_enabled(CONF_AUTO_UP)
                    and self._sun_allows_open(sun_elevation)
                    and self._brightness_allows_open(brightness)
                ):
                    if open_condition and not self._manual_blocks_action("open"):
                        await self._set_position(
                            self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION),
                            "shading_end_open",
                        )
                        return
            if shading_allowed:
                await self._set_position(
                    self._position_value(CONF_SHADING_POSITION, DEFAULT_SHADING_POSITION),
                    "shading",
                )
                return
        
        close_events: list[tuple[datetime, str, float | None]] = []
        open_events: list[tuple[datetime, str, float | None]] = []

        if post_ventilation and ventilation_end_condition:
            close_events.append(
                (
                    now + timedelta(seconds=1),
                    "ventilation_end_close",
                    self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION),
                )
            )

        if close_condition and not self._manual_blocks_action("close"):
            if self._auto_enabled(CONF_AUTO_SUN) and self._sun_allows_close(sun_elevation):
                close_events.append(
                    (
                        now,
                        "sun_close",
                        self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION),
                    )
                )
            if (
                self._auto_enabled(CONF_AUTO_BRIGHTNESS)
                and brightness is not None
                and self._brightness_allows_close(brightness)
            ):
                close_events.append(
                    (
                        now,
                        "brightness_close",
                        self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION),
                    )
                )

            if self._auto_enabled(CONF_AUTO_DOWN) and down_due:
                close_events.append(
                    (
                        self._next_close or now,
                        "scheduled_close",
                        self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION),
                    )
                )

        if tilt_lock_close:
            close_events = []

        if open_condition and not self._manual_blocks_action("open"):
            if self._auto_enabled(CONF_AUTO_SUN) and self._sun_allows_open(sun_elevation):
                open_events.append(
                    (
                        now,
                        "sun_open",
                        self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION),
                    )
                )
            

            if (
                self._auto_enabled(CONF_AUTO_BRIGHTNESS)
                and brightness is not None
                and self._brightness_allows_open(brightness)
            ):
                open_events.append(
                    (
                        now,
                        "brightness_open",
                        self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION),
                    )
                )

            if self._auto_enabled(CONF_AUTO_UP) and (up_due or time_window_open):
                open_events.append(
                    (
                        self._next_open or now,
                        "scheduled_open",
                        self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION),
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

    def _sun_allows_open(self, sun_elevation: float | None) -> bool:
        if not self._auto_enabled(CONF_AUTO_SUN):
            return True
        if sun_elevation is None:
            return False
        return sun_elevation >= float(self.config.get(CONF_SUN_ELEVATION_OPEN))

    def _sun_allows_close(self, sun_elevation: float | None) -> bool:
        if not self._auto_enabled(CONF_AUTO_SUN):
            return True
        if sun_elevation is None:
            return False
        return sun_elevation <= float(self.config.get(CONF_SUN_ELEVATION_CLOSE))

    def _brightness_allows_open(self, brightness: float | None) -> bool:
        if not self._auto_enabled(CONF_AUTO_BRIGHTNESS) or brightness is None:
            return True
        return brightness >= float(self.config.get(CONF_BRIGHTNESS_OPEN_ABOVE))

    def _brightness_allows_close(self, brightness: float | None) -> bool:
        if not self._auto_enabled(CONF_AUTO_BRIGHTNESS) or brightness is None:
            return True
        return brightness <= float(self.config.get(CONF_BRIGHTNESS_CLOSE_BELOW))

    def _shading_conditions(
        self, sun_azimuth: float | None, sun_elevation: float | None, brightness: float | None
    ) -> bool:
        if sun_azimuth is None or sun_elevation is None:
            return False
        if brightness is None:
            return False
        if not self._weather_allows_shading():
            return False
        az_start = float(self.config.get(CONF_SUN_AZIMUTH_START))
        az_end = float(self.config.get(CONF_SUN_AZIMUTH_END))
        el_min = float(self.config.get(CONF_SUN_ELEVATION_MIN))
        el_max = float(self.config.get(CONF_SUN_ELEVATION_MAX))
        bright_start = float(self.config.get(CONF_SHADING_BRIGHTNESS_START))
        bright_end = float(self.config.get(CONF_SHADING_BRIGHTNESS_END))
        if not (az_start <= sun_azimuth <= az_end and el_min <= sun_elevation <= el_max):
            return False
        if brightness < bright_start:
            return False
        if self._reason == "shading" and brightness <= bright_end:
            return False
        temp_ok = self._temperature_allows_shading()
        return temp_ok or brightness >= bright_start

    def _temperature_allows_shading(self) -> bool:
        indoor = _float_state(self.hass, self.config.get(CONF_TEMPERATURE_SENSOR_INDOOR))
        outdoor = _float_state(self.hass, self.config.get(CONF_TEMPERATURE_SENSOR_OUTDOOR))
        forecast_threshold = self.config.get(CONF_TEMPERATURE_FORECAST_THRESHOLD)
        forecast_hot = False
        if forecast_threshold is not None:
            try:
                forecast_hot = float(forecast_threshold) > 0
            except (TypeError, ValueError):
                forecast_hot = False
        threshold = float(self.config.get(CONF_TEMPERATURE_THRESHOLD))
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
            last_changed = getattr(state, "last_changed", None)
            last_changed = dt_util.as_utc(last_changed) if last_changed else now
            if (now - last_changed) < timedelta(seconds=delay_after_close):
                return True
        return False


    def _is_resident_sleeping(self) -> bool:
        resident_entity = self.config.get(CONF_RESIDENT_SENSOR)
        if not resident_entity:
            return False
        return self.hass.states.is_state(resident_entity, STATE_ON)

    def _time_from_config(self, key: str) -> time | None:
        configured = self.config.get(key)
        parsed = _parse_time(configured)
        if parsed:
            return parsed
        fallback = DEFAULT_TIME_SETTINGS.get(key)
        return _parse_time(fallback) if fallback is not None else None
    
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

    def _within_open_close_window(self, now: datetime) -> bool:
        workday = self._is_workday()
        early, late = self._time_bounds(workday, True)
        return self._within_time_window(now, early, late)

    def _event_due(self, target: datetime | None, now: datetime) -> bool:
        if not target:
            return False
        return now >= target

    def _position_value(self, key: str, default: float) -> float | None:
        entity_key = self._position_entity_map.get(key)
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
                self._publish_state()
            return
        await self._command_position(float(position), reason=reason)
        self._target = float(position)
        self._reason = reason
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

    # Backwards compatibility: older setups referenced `_contact_sensors`.
    # Preserve the legacy name to avoid AttributeError during upgrades.
    def _contact_sensors(self) -> list[str]:
        return self._contact_entities()

    def _refresh_next_events(self, now: datetime) -> None:

        sun_enabled = self._auto_enabled(CONF_AUTO_SUN)
        sun_state = self.hass.states.get("sun.sun") if sun_enabled else None
        sun_next_rising = self._parse_datetime_attr(
            sun_state and sun_state.attributes.get("next_rising")
        )
        sun_next_setting = self._parse_datetime_attr(
            sun_state and sun_state.attributes.get("next_setting")
        )
        sun_open_target = (
            self._next_sun_time_for_elevation(
                self.config.get(CONF_SUN_ELEVATION_OPEN), SunDirection.RISING, now
            )
            if sun_enabled
            else None
        )
        sun_close_target = (
            self._next_sun_time_for_elevation(
                self.config.get(CONF_SUN_ELEVATION_CLOSE), SunDirection.SETTING, now
            )
            if sun_enabled
            else None
        )
        workday = self._is_workday()
        up_early_time, up_late_time = self._time_bounds(workday, True)
        down_early_time, down_late_time = self._time_bounds(workday, False)

        next_up_early = self._next_time_for_point(up_early_time, now)
        next_up_late = self._next_time_for_point(up_late_time, now)
        next_down_early = self._next_time_for_point(down_early_time, now)
        next_down_late = self._next_time_for_point(down_late_time, now)

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
            
            first, second = fallback_candidates
            return first or second
        
        open_base = (sun_open_target or sun_next_rising) if sun_enabled else None
        close_base = (sun_close_target or sun_next_setting) if sun_enabled else None

        self._next_open = _clamp_candidate(
            open_base, next_up_early, next_up_late, (next_up_early, next_up_late)
        )
        self._next_close = _clamp_candidate(
            close_base,
            next_down_early,
            next_down_late,
            (next_down_early, next_down_late),
        )

        if self._within_open_close_window(now):
            if self._next_open is None or self._next_open > now:
                self._next_open = now

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
        vent_target = self._position_value(CONF_VENTILATE_POSITION, DEFAULT_VENTILATE_POSITION)
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
