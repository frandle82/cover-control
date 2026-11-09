"""Cover controller behavior split from the public controller facade."""

from __future__ import annotations

import asyncio
import random
from datetime import (
    datetime,
    timedelta,
)
from importlib import import_module

from homeassistant.const import (
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    Context,
    State,
    callback,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from ..const import (
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_SHADING,
    CONF_AUTO_SUN,
    CONF_AUTO_TIME,
    CONF_AUTO_VENTILATE,
    CONF_BRIGHTNESS_SENSOR,
    CONF_CALENDAR_ENTITY,
    CONF_CLOSE_POSITION,
    CONF_CLOSE_TILT_POSITION,
    CONF_COVER_TILT_WAIT_MODE,
    CONF_COVER_TILT_WAIT_TIMEOUT,
    CONF_CUSTOM_POSITION_SENSOR,
    CONF_DRIVE_TIME,
    CONF_ENABLE_LOGBOOK_COVER,
    CONF_LOCKOUT_POSITION,
    CONF_MASTER_ENABLED,
    CONF_OPEN_POSITION,
    CONF_OPEN_TILT_POSITION,
    CONF_POSITION_SOURCE,
    CONF_POSITION_SOURCE_CURRENT_POSITION_ATTR,
    CONF_POSITION_SOURCE_CUSTOM_SENSOR,
    CONF_POSITION_SOURCE_POSITION_ATTR,
    CONF_POSITION_TOLERANCE,
    CONF_TILT_POSITION_TOLERANCE,
    CONF_TEMPERATURE_SENSOR_INDOOR,
    CONF_TEMPERATURE_SENSOR_OUTDOOR,
    CONF_DRIVE_DELAY_FIXED,
    CONF_DRIVE_DELAY_RANDOM,
    CONF_FORCE_PAUSE_ENTITY,
    CONF_RESIDENT_SENSOR,
    CONF_RESIDENT_STATUS,
    CONF_SHADING_BRIGHTNESS_SENSOR,
    CONF_SHADING_POSITION,
    CONF_SHADING_POSITION_ALT,
    CONF_SHADING_POSITION_ALT_ENTITY,
    CONF_SHADING_TILT_ELEVATION_1,
    CONF_SHADING_TILT_ELEVATION_2,
    CONF_SHADING_TILT_ELEVATION_3,
    CONF_SHADING_TILT_POSITION,
    CONF_SHADING_TILT_POSITION_0,
    CONF_SHADING_TILT_POSITION_1,
    CONF_SHADING_TILT_POSITION_2,
    CONF_SHADING_TILT_POSITION_3,
    CONF_VENTILATE_POSITION,
    CONF_VENTILATE_TILT_POSITION,
    CONF_WINDOW_SENSOR_FULL,
    CONF_WINDOW_SENSOR_TILT,
    CONF_WORKDAY_SENSOR,
    CONF_WORKDAY_TOMORROW_SENSOR,
    FUNCTION_SAFETY,
    SAFETY_ALARMS,
    COVER_TILT_WAIT_BEFORE_POSITION,
    COVER_TILT_WAIT_IDLE,
    DEFAULT_AUTOMATION_FLAGS,
    DEFAULT_CLOSE_TILT_POSITION,
    DEFAULT_CLOSE_POSITION,
    DEFAULT_COVER_TILT_WAIT_MODE,
    DEFAULT_COVER_TILT_WAIT_TIMEOUT,
    DEFAULT_DRIVE_TIME,
    DEFAULT_MASTER_FLAGS,
    DEFAULT_OPEN_POSITION,
    DEFAULT_OPEN_TILT_POSITION,
    DEFAULT_SHADING_POSITION,
    DEFAULT_SHADING_TILT_ELEVATION_1,
    DEFAULT_SHADING_TILT_ELEVATION_2,
    DEFAULT_SHADING_TILT_ELEVATION_3,
    DEFAULT_SHADING_TILT_POSITION,
    DEFAULT_SHADING_TILT_POSITION_0,
    DEFAULT_SHADING_TILT_POSITION_1,
    DEFAULT_SHADING_TILT_POSITION_2,
    DEFAULT_SHADING_TILT_POSITION_3,
    DEFAULT_TOLERANCE,
    DEFAULT_DRIVE_DELAY_FIXED,
    DEFAULT_DRIVE_DELAY_RANDOM,
    DEFAULT_VENTILATE_POSITION,
    DEFAULT_VENTILATE_TILT_POSITION,
    DOMAIN,
    EVENT_COVER_CONTROL,
    SIGNAL_STATE_UPDATED,
)
from .common import (
    _LOGGER,
    IDLE_REASON,
    TRIGGER_BRIGHTNESS_CHANGED,
    TRIGGER_RESIDENT_OFF,
    TRIGGER_RESIDENT_ON,
    TRIGGER_SHADING_END_CHANGED,
    TRIGGER_SHADING_START_CHANGED,
    TRIGGER_SUN_CHANGED,
    TRIGGER_WORKDAY_CHANGED,
    TRIGGER_WORKDAY_TOMORROW_CHANGED,
    TRIGGER_FIRE_ALARM_ON,
    TRIGGER_FIRE_ALARM_OFF,
    TRIGGER_RAIN_ALARM_ON,
    TRIGGER_RAIN_ALARM_OFF,
    TRIGGER_WIND_ALARM_2_ON,
    TRIGGER_WIND_ALARM_2_OFF,
    TRIGGER_WIND_ALARM_1_ON,
    TRIGGER_WIND_ALARM_1_OFF,
    TRIGGER_FROST_ALARM_ON,
    TRIGGER_FROST_ALARM_OFF,
    TRIGGER_WINDOW_DOWN_SEQUENCE_TARGET_REACHED,
    WINDOW_DOWN_SEQUENCE_REASONS,
    _coerce_float,
    _float_state,
)
from .safety import SAFETY_REASONS

_COVER_ENTITY_FEATURE = None


async def _async_cover_entity_feature(hass):
    """Load the heavy cover component off the event loop on first use."""

    global _COVER_ENTITY_FEATURE
    if _COVER_ENTITY_FEATURE is None:
        cover_module = await hass.async_add_executor_job(
            import_module, "homeassistant.components.cover"
        )
        _COVER_ENTITY_FEATURE = cover_module.CoverEntityFeature
    return _COVER_ENTITY_FEATURE


class ActuatorMixin:
    def _effective_shading_position(self) -> float | None:
        """Return the alternate shading target while its gating entity is active."""

        default = self._position_value(CONF_SHADING_POSITION, DEFAULT_SHADING_POSITION)
        entity_id = self.config.get(CONF_SHADING_POSITION_ALT_ENTITY)
        entity_state = self.hass.states.get(entity_id) if entity_id else None
        if entity_state is not None and entity_state.state in {STATE_ON, "true", "1"}:
            return self._position_value(CONF_SHADING_POSITION_ALT, default)
        return default

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
        context = getattr(self, "_evaluation_context", None)
        runtime_toggles = (
            context.get("runtime_toggles", {}) if isinstance(context, dict) else {}
        )
        if isinstance(runtime_toggles, dict) and config_key in runtime_toggles:
            return bool(runtime_toggles[config_key])
        entity_key = self._auto_entity_map.get(config_key)
        if entity_key:
            entity_id = self.config.get(entity_key)
            if entity_id and self.hass.states.get(entity_id) is not None:
                return self.hass.states.is_state(entity_id, STATE_ON)
        return bool(self.config.get(config_key))

    def _master_enabled(self) -> bool:
        return bool(
            self.config.get(
                CONF_MASTER_ENABLED, DEFAULT_MASTER_FLAGS[CONF_MASTER_ENABLED]
            )
        )

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
                {
                    k: v.isoformat() if isinstance(v, datetime) else v
                    for k, v in data.items()
                }
            )

        self.hass.bus.async_fire(EVENT_COVER_CONTROL, payload)

    def _logbook_entry(
        self, message: str, *, dedupe_key: str | None = None
    ) -> None:
        """Write an optional cover-scoped logbook entry without affecting control."""

        if not self.config.get(CONF_ENABLE_LOGBOOK_COVER, False):
            return
        dedupe = getattr(self, "_logbook_dedupe", None)
        if dedupe is None:
            dedupe = self._logbook_dedupe = set()
        if dedupe_key is not None and dedupe_key in dedupe:
            return
        try:
            logbook = import_module("homeassistant.components.logbook")
            logbook.async_log_entry(
                self.hass,
                "Cover Control",
                message,
                DOMAIN,
                self.cover,
            )
        except (ImportError, AttributeError):
            _LOGGER.debug("Home Assistant logbook is unavailable", exc_info=True)
            return
        except Exception:  # pragma: no cover - optional diagnostics must be harmless
            _LOGGER.debug("Failed to write Cover Control logbook entry", exc_info=True)
            return
        if dedupe_key is None:
            dedupe.clear()
        else:
            dedupe.add(dedupe_key)

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
        frost_target = self._frost_target_if_active()
        if (
            reason not in SAFETY_REASONS
            and frost_target is not None
            and float(position) < frost_target
        ):
            position = frost_target
            reason = "frost_alarm"
        if (
            self._group_position_callback is not None
            and reason != "scheduled_intermediate_close"
        ):
            await self._group_position_callback(self, float(position), reason)
            return
        await self._set_position_local(float(position), reason)

    async def _set_position_local(self, position: float, reason: str) -> None:
        """Move only this cover after room-level coordination is resolved."""

        sequence_needed = self._window_down_sequence_target(reason) is not None
        if self._window_down_sequence is not None and not sequence_needed:
            self._cancel_window_down_sequence()
        tilt_position = self._tilt_position_value(reason)
        tolerance = float(
            self._position_value(CONF_POSITION_TOLERANCE, DEFAULT_TOLERANCE)
        )
        current = self._current_position()
        target = position
        command_in_flight = (
            self._last_command_at is not None
            and self._target is not None
            and abs(self._target - target) <= tolerance
            and dt_util.utcnow() - self._last_command_at
            <= timedelta(
                seconds=self._duration_value(CONF_DRIVE_TIME, DEFAULT_DRIVE_TIME)
            )
        )
        if (
            command_in_flight
            and current is not None
            and abs(current - target) > tolerance
        ):
            self._reason = reason
            self._publish_state()
            return
        if current is not None and abs(current - target) <= tolerance:
            if tilt_position is not None:
                state = self.hass.states.get(self.cover)
                current_tilt = _coerce_float(
                    state and state.attributes.get("current_tilt_position")
                )
                tilt_tolerance = self._position_value(
                    CONF_TILT_POSITION_TOLERANCE, DEFAULT_TOLERANCE
                )
                if current_tilt is None or abs(current_tilt - tilt_position) > tilt_tolerance:
                    await self._command_tilt_position(float(tilt_position), reason=reason)
            if self._reason is None:
                self._reason = reason
            self._target = target
            self._record_action_status(reason, target)
            if sequence_needed:
                self._start_window_down_sequence(target, reason)
            self._publish_state()
            return
        delay = self._drive_delay_seconds()
        if delay > 0:
            await asyncio.sleep(delay)
            safety_move = reason in SAFETY_REASONS
            if not safety_move and self._entity_active(CONF_FORCE_PAUSE_ENTITY):
                self.async_request_evaluate("force_pause_during_delay")
                return
            if not safety_move and (self._manual_active or not self._master_enabled()):
                self.async_request_evaluate("movement_gate_changed_during_delay")
                return
            force_reasons = {
                "force_open": "force_open_entity",
                "force_close": "force_close_entity",
                "force_ventilate": "force_ventilate_entity",
                "force_shading": "force_shading_entity",
            }
            if not safety_move and any(
                self._entity_active(key)
                for key in force_reasons.values()
                if key != force_reasons.get(reason)
            ):
                self.async_request_evaluate("force_changed_during_delay")
                return
            if (
                not safety_move
                and not sequence_needed
                and "close" in reason
                and self._contacts_active(
                    self._full_open_sensors(), dt_util.utcnow()
                )
            ):
                self.async_request_evaluate("window_lockout_during_delay")
                return
            current_after_delay = self._current_position()
            if current_after_delay is not None and abs(current_after_delay - target) <= tolerance:
                self.async_request_evaluate("target_reached_during_delay")
                return
        if (
            tilt_position is not None
            and str(
                self.config.get(CONF_COVER_TILT_WAIT_MODE, DEFAULT_COVER_TILT_WAIT_MODE)
                or DEFAULT_COVER_TILT_WAIT_MODE
            ).lower()
            == COVER_TILT_WAIT_BEFORE_POSITION
            and current is not None
        ):
            await self._align_tilt_before_position(current, target, reason)
        await self._command_position(target, reason=reason)
        if tilt_position is not None:
            await self._send_tilt_after_position(float(tilt_position), reason=reason)
        self._target = target
        self._reason = reason
        self._record_action_status(reason, target)
        if sequence_needed:
            self._start_window_down_sequence(target, reason)
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

    def _window_down_sequence_target(
        self, reason: str
    ) -> tuple[str, float] | None:
        if (
            reason not in WINDOW_DOWN_SEQUENCE_REASONS
            or self._is_awning()
            or not self._auto_enabled(CONF_AUTO_VENTILATE)
        ):
            return None
        for entity_id in self._full_open_sensors():
            state = self._state_for(entity_id)
            if state is not None and state.state in {STATE_ON, "true", "1"}:
                open_position = self._position_value(
                    CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION
                )
                return (
                    "open",
                    self._position_value(CONF_LOCKOUT_POSITION, open_position),
                )
        for entity_id in self._tilt_sensors():
            state = self._state_for(entity_id)
            if state is not None and state.state in {STATE_ON, "true", "1"}:
                return (
                    "tilted",
                    self._position_value(
                        CONF_VENTILATE_POSITION, DEFAULT_VENTILATE_POSITION
                    ),
                )
        return None

    def _start_window_down_sequence(self, close_target: float, reason: str) -> None:
        window = self._window_down_sequence_target(reason)
        if window is None:
            return
        window_state, final_target = window
        self._pre_ventilation_position = close_target
        section = self._status.setdefault("ventilation", {})
        section["background"] = {"open": False, "close": True, "shading": False}
        section["restore_position"] = close_target
        self._window_down_sequence = {
            "phase": "closing",
            "initial_target": close_target,
            "window_state": window_state,
            "final_target": final_target,
            "reason": reason,
        }
        self.persist_status()
        self._schedule_delayed_evaluate(
            TRIGGER_WINDOW_DOWN_SEQUENCE_TARGET_REACHED,
            self._duration_value(CONF_DRIVE_TIME, DEFAULT_DRIVE_TIME),
            timer_key="window_down_sequence",
        )

    def _cancel_window_down_sequence(self) -> None:
        timers = getattr(self, "_delayed_evaluation_unsubs", {})
        unsubscribe = timers.pop("window_down_sequence", None)
        if unsubscribe is not None:
            unsubscribe()
        self._window_down_sequence = None

    async def _evaluate_window_down_sequence(self, trigger: str) -> bool:
        sequence = self._window_down_sequence
        if sequence is None:
            return False
        reason = str(sequence.get("reason") or "")
        latest = self._window_down_sequence_target(reason)
        if latest is not None:
            sequence["window_state"], sequence["final_target"] = latest
        if trigger != TRIGGER_WINDOW_DOWN_SEQUENCE_TARGET_REACHED:
            self._decision_controls.add("ventilation")
            self._publish_state()
            return True

        initial_target = _coerce_float(sequence.get("initial_target"))
        self._cancel_window_down_sequence()
        if latest is None or initial_target is None:
            self._reason = reason or self._reason
            self._publish_state()
            return True

        window_state, final_target = latest
        self._pre_ventilation_position = initial_target
        section = self._status.setdefault("ventilation", {})
        section["background"] = {"open": False, "close": True, "shading": False}
        section["restore_position"] = initial_target
        await self._set_position_local(
            final_target,
            "ventilation_full" if window_state == "open" else "ventilation",
        )
        return True

    def window_down_sequence_snapshot(self) -> dict[str, object]:
        return dict(self._window_down_sequence or {})

    def _drive_delay_seconds(self) -> float:
        """Return the combined pre-drive delay for a real movement."""

        fixed = max(0.0, float(self.config.get(CONF_DRIVE_DELAY_FIXED, DEFAULT_DRIVE_DELAY_FIXED) or 0))
        random_max = max(0.0, float(self.config.get(CONF_DRIVE_DELAY_RANDOM, DEFAULT_DRIVE_DELAY_RANDOM) or 0))
        return fixed + random.uniform(0.0, random_max)

    def _current_position(self) -> float | None:
        state = self.hass.states.get(self.cover)
        if not state:
            return None

        source = str(
            self.config.get(
                CONF_POSITION_SOURCE, CONF_POSITION_SOURCE_CURRENT_POSITION_ATTR
            )
            or CONF_POSITION_SOURCE_CURRENT_POSITION_ATTR
        )
        if source == CONF_POSITION_SOURCE_CUSTOM_SENSOR:
            return _float_state(self.hass, self.config.get(CONF_CUSTOM_POSITION_SENSOR))

        try:
            if (
                source == CONF_POSITION_SOURCE_CURRENT_POSITION_ATTR
                and "current_position" in state.attributes
            ):
                return float(state.attributes["current_position"])
            if (
                source == CONF_POSITION_SOURCE_POSITION_ATTR
                and "position" in state.attributes
            ):
                return float(state.attributes["position"])
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

    async def _align_tilt_before_position(
        self, current: float, target: float, reason: str
    ) -> None:
        """Align slats with the travel direction for tilt-restoring motors."""

        state = self.hass.states.get(self.cover)
        if state is None or state.attributes.get("current_tilt_position") is None:
            return
        if current >= 99.5:
            ctx = Context()
            self._last_command_context_id = ctx.id
            self._last_command_at = dt_util.utcnow()
            await self.hass.services.async_call(
                "cover",
                "close_cover",
                {"entity_id": self.cover},
                blocking=True,
                context=ctx,
            )
            await self._async_wait_for_state_change(
                lambda: (
                    (state := self.hass.states.get(self.cover)) is not None
                    and state.state != "open"
                ),
                1,
            )
            return
        preliminary_tilt = 0.0 if target < current else 100.0
        await self._command_tilt_position(
            preliminary_tilt, reason=f"{reason}_tilt_alignment"
        )

    async def _send_tilt_after_position(
        self, tilt_position: float, *, reason: str | None = None
    ) -> None:
        wait_mode = str(
            self.config.get(CONF_COVER_TILT_WAIT_MODE, DEFAULT_COVER_TILT_WAIT_MODE)
            or DEFAULT_COVER_TILT_WAIT_MODE
        ).lower()
        if wait_mode in {
            COVER_TILT_WAIT_IDLE,
            COVER_TILT_WAIT_BEFORE_POSITION,
        }:
            timeout = self._duration_value(
                CONF_COVER_TILT_WAIT_TIMEOUT, DEFAULT_COVER_TILT_WAIT_TIMEOUT
            )
            await self._async_wait_for_state_change(
                lambda: (
                    (state := self.hass.states.get(self.cover)) is not None
                    and state.state in ("open", "closed")
                ),
                timeout,
            )
        await self._command_tilt_position(tilt_position, reason=reason)

    def _tilt_position_value(self, reason: str | None) -> float | None:
        if not reason:
            return None
        if reason == "ventilation_full" or "open" in reason:
            return self._position_value(
                CONF_OPEN_TILT_POSITION, DEFAULT_OPEN_TILT_POSITION
            )
        if "close" in reason or reason in {"resident_asleep", "heat_protection"}:
            return self._position_value(
                CONF_CLOSE_TILT_POSITION, DEFAULT_CLOSE_TILT_POSITION
            )
        if reason == "ventilation_end_shading":
            return self._position_value(
                CONF_SHADING_TILT_POSITION, DEFAULT_SHADING_TILT_POSITION
            )
        if "ventilation" in reason or reason.startswith("ventilate"):
            return self._position_value(
                CONF_VENTILATE_TILT_POSITION, DEFAULT_VENTILATE_TILT_POSITION
            )
        if (
            "shading" in reason
            and reason != "manual_shading_end"
            and "end_open" not in reason
            and "end_close" not in reason
        ):
            return self._shading_tilt_for_elevation()
        return None

    def _shading_tilt_for_elevation(self) -> float | None:
        sun_state = self.hass.states.get(self._sun_entity())
        elevation = _coerce_float(sun_state and sun_state.attributes.get("elevation"))
        el1 = self._number_value(
            CONF_SHADING_TILT_ELEVATION_1, DEFAULT_SHADING_TILT_ELEVATION_1
        )
        el2 = self._number_value(
            CONF_SHADING_TILT_ELEVATION_2, DEFAULT_SHADING_TILT_ELEVATION_2
        )
        el3 = self._number_value(
            CONF_SHADING_TILT_ELEVATION_3, DEFAULT_SHADING_TILT_ELEVATION_3
        )
        pos0 = self._number_value(
            CONF_SHADING_TILT_POSITION_0, DEFAULT_SHADING_TILT_POSITION_0
        )
        pos1 = self._number_value(
            CONF_SHADING_TILT_POSITION_1, DEFAULT_SHADING_TILT_POSITION_1
        )
        pos2 = self._number_value(
            CONF_SHADING_TILT_POSITION_2, DEFAULT_SHADING_TILT_POSITION_2
        )
        pos3 = self._number_value(
            CONF_SHADING_TILT_POSITION_3, DEFAULT_SHADING_TILT_POSITION_3
        )
        if elevation is None:
            return pos0
        if elevation >= el3:
            return pos3
        if elevation >= el2:
            return pos2
        if elevation >= el1:
            return pos1
        return pos0

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

    def _decision_entities(self) -> set[str]:
        """Return configured entities whose state can change a movement decision."""

        entities: set[str] = set()
        auto_time = self._auto_enabled(CONF_AUTO_TIME)
        auto_brightness = self._auto_enabled(CONF_AUTO_BRIGHTNESS)
        auto_sun = self._auto_enabled(CONF_AUTO_SUN)
        auto_shading = self._auto_enabled(CONF_AUTO_SHADING)
        auto_ventilate = self._auto_enabled(CONF_AUTO_VENTILATE)

        keys: list[str] = []
        if auto_time:
            keys.extend(
                [
                    CONF_WORKDAY_SENSOR,
                    CONF_WORKDAY_TOMORROW_SENSOR,
                    CONF_CALENDAR_ENTITY,
                ]
            )
        if auto_brightness:
            keys.append(CONF_BRIGHTNESS_SENSOR)
        if auto_shading:
            keys.extend(
                [
                    CONF_SHADING_BRIGHTNESS_SENSOR,
                    CONF_TEMPERATURE_SENSOR_INDOOR,
                    CONF_TEMPERATURE_SENSOR_OUTDOOR,
                    CONF_SHADING_POSITION_ALT_ENTITY,
                ]
            )
        if self._auto_enabled(CONF_RESIDENT_STATUS):
            keys.append(CONF_RESIDENT_SENSOR)
        if FUNCTION_SAFETY in getattr(
            self.config, "configured_functions", frozenset()
        ):
            for _alarm, entity_key, enabled_key, _target, room_key, _default in SAFETY_ALARMS:
                if self.config.get(enabled_key) and self.config.get(room_key):
                    keys.append(entity_key)
        if self.config.get(CONF_POSITION_SOURCE) == CONF_POSITION_SOURCE_CUSTOM_SENSOR:
            keys.append(CONF_CUSTOM_POSITION_SENSOR)

        for key in keys:
            entity_id = self.config.get(key)
            if isinstance(entity_id, str) and entity_id:
                entities.add(entity_id)
        if auto_sun or auto_shading:
            entities.add(self._sun_entity())
        if auto_ventilate:
            entities.update(self._contact_entities())

        entities.update(
            entity_id
            for entity_id in (
                self.config.get(entity_key)
                for entity_key in self._auto_entity_map.values()
            )
            if isinstance(entity_id, str) and entity_id
        )
        entities.update(
            entity_id
            for entity_id in (
                self.config.get(key)
                for key in (
                    "force_open_entity",
                    "force_close_entity",
                    "force_ventilate_entity",
                    "force_shading_entity",
                    "force_pause_entity",
                )
            )
            if isinstance(entity_id, str) and entity_id
        )
        return entities

    def _local_decision_entities(self) -> set[str]:
        """Return inputs whose state is specific to this cover."""

        entities = set(self._contact_entities())
        if self.config.get(CONF_POSITION_SOURCE) == CONF_POSITION_SOURCE_CUSTOM_SENSOR:
            custom_sensor = self.config.get(CONF_CUSTOM_POSITION_SENSOR)
            if isinstance(custom_sensor, str) and custom_sensor:
                entities.add(custom_sensor)
        return entities

    def _shared_decision_entities(self) -> set[str]:
        """Return entry-wide decision inputs owned by the manager."""

        return self._decision_entities() - self._local_decision_entities()

    def _shared_state_triggers(
        self, entity_id: str, old_value: str | None, new_value: str | None
    ) -> set[str]:
        """Identify every configured role affected by one shared entity update."""

        triggers: set[str] = set()
        role_triggers = {
            CONF_BRIGHTNESS_SENSOR: (TRIGGER_BRIGHTNESS_CHANGED,),
            CONF_WORKDAY_SENSOR: (TRIGGER_WORKDAY_CHANGED,),
            CONF_WORKDAY_TOMORROW_SENSOR: (TRIGGER_WORKDAY_TOMORROW_CHANGED,),
            CONF_CALENDAR_ENTITY: ("calendar_changed",),
            CONF_SHADING_POSITION_ALT_ENTITY: ("shading_position_changed",),
        }
        for key in (
            CONF_SHADING_BRIGHTNESS_SENSOR,
            CONF_TEMPERATURE_SENSOR_INDOOR,
            CONF_TEMPERATURE_SENSOR_OUTDOOR,
        ):
            role_triggers[key] = (
                TRIGGER_SHADING_START_CHANGED,
                TRIGGER_SHADING_END_CHANGED,
            )
        for key, values in role_triggers.items():
            if self.config.get(key) == entity_id:
                triggers.update(values)

        if entity_id == self._sun_entity():
            triggers.add(TRIGGER_SUN_CHANGED)
            if self._auto_enabled(CONF_AUTO_SHADING):
                triggers.update(
                    (TRIGGER_SHADING_START_CHANGED, TRIGGER_SHADING_END_CHANGED)
                )
        if self.config.get(CONF_RESIDENT_SENSOR) == entity_id:
            if self._resident_state_is_off(old_value) and self._resident_state_is_on(
                new_value
            ):
                triggers.add(TRIGGER_RESIDENT_ON)
            elif self._resident_state_is_on(old_value) and self._resident_state_is_off(
                new_value
            ):
                triggers.add(TRIGGER_RESIDENT_OFF)
            else:
                triggers.add("resident_changed")

        alarm_triggers = {
            "fire": (TRIGGER_FIRE_ALARM_ON, TRIGGER_FIRE_ALARM_OFF),
            "rain": (TRIGGER_RAIN_ALARM_ON, TRIGGER_RAIN_ALARM_OFF),
            "wind_alarm_2": (TRIGGER_WIND_ALARM_2_ON, TRIGGER_WIND_ALARM_2_OFF),
            "wind_alarm_1": (TRIGGER_WIND_ALARM_1_ON, TRIGGER_WIND_ALARM_1_OFF),
            "frost": (TRIGGER_FROST_ALARM_ON, TRIGGER_FROST_ALARM_OFF),
        }
        active_values = {"on", "true", "1", "open", "active"}
        inactive_values = {"off", "false", "0", "closed", "inactive"}
        old_active = str(old_value).strip().lower() in active_values
        new_active = str(new_value).strip().lower() in active_values
        new_inactive = str(new_value).strip().lower() in inactive_values
        for alarm, entity_key, enabled_key, _target, room_key, _default in SAFETY_ALARMS:
            if (
                self.config.get(entity_key) == entity_id
                and self.config.get(enabled_key)
                and self.config.get(room_key)
            ):
                on_trigger, off_trigger = alarm_triggers[alarm]
                if new_active and not old_active:
                    triggers.add(on_trigger)
                elif old_active and new_inactive:
                    triggers.add(off_trigger)

        for key in (
            *self._auto_entity_map.values(),
            "force_open_entity",
            "force_close_entity",
            "force_ventilate_entity",
            "force_shading_entity",
            "force_pause_entity",
        ):
            if self.config.get(key) == entity_id:
                triggers.add(f"{key}_changed")
        return triggers

    def _unavailable_decision_entities(self) -> set[str]:
        """Return required decision inputs which do not have a usable state."""

        return {
            entity_id
            for entity_id in self._decision_entities()
            if (
                (state := self._state_for(entity_id)) is None
                or state.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}
            )
        }

    def _publish_state(self) -> None:
        if getattr(self, "_publish_callback", None) is not None:
            self._publish_callback(self)
            return
        self._dispatch_state()

    def _dispatch_state(self) -> None:
        """Send the stable legacy per-cover runtime signal."""

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
        tolerance = float(
            self._position_value(CONF_POSITION_TOLERANCE, DEFAULT_TOLERANCE)
        )
        return abs(current - float(target)) <= tolerance

    def _shading_is_active(
        self, current_position: float | None, shading_enabled: bool
    ) -> bool:
        if not shading_enabled:
            return False
        if self._reason not in {"shading", "manual_shading", "heat_protection"}:
            return False
        shading_target = (
            self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION)
            if self._reason == "heat_protection"
            else self._effective_shading_position()
        )
        return self._position_matches(shading_target, current_position)

    def _ventilation_is_active(self, current_position: float | None) -> bool:
        if self._reason not in {"ventilation", "ventilation_full"}:
            return False
        if self._reason == "ventilation_full":
            open_position = self._position_value(
                CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION
            )
            vent_target = self._position_value(CONF_LOCKOUT_POSITION, open_position)
        else:
            vent_target = self._position_value(
                CONF_VENTILATE_POSITION, DEFAULT_VENTILATE_POSITION
            )
        return self._position_matches(vent_target, current_position)

    async def _open_cover(
        self, target: float | None = None, reason: str | None = None
    ) -> None:
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
        self._ignore_service_call_until = self._last_command_at + timedelta(
            seconds=self._duration_value(CONF_DRIVE_TIME, DEFAULT_DRIVE_TIME)
        )
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
        self._target = float(position)
        self._status["target"] = self._target
        state = self._cover_state_or_warn(
            "set_cover_position",
            reason=reason,
            trigger=trigger,
            target_position=self._target,
        )
        if not state:
            return
        cover_entity_feature = await _async_cover_entity_feature(self.hass)
        supported = (state.attributes.get("supported_features")) or 0
        supports_position = bool(int(supported) & cover_entity_feature.SET_POSITION)

        ctx = Context()
        self._last_command_context_id = ctx.id
        self._last_command_at = dt_util.utcnow()
        self._ignore_service_call_until = self._last_command_at + timedelta(
            seconds=self._duration_value(CONF_DRIVE_TIME, DEFAULT_DRIVE_TIME)
        )
        message_reason = reason or self._reason
        service: str = "set_cover_position"
        service_data = {"entity_id": self.cover, "position": self._target}
        if supports_position:
            pass
        else:
            if self._target >= 99.5:
                service = "open_cover"
                service_data = {"entity_id": self.cover}
            elif self._target <= 0.5:
                service = "close_cover"
                service_data = {"entity_id": self.cover}

        _LOGGER.info(
            "Cover Control moving %s via %s to %.1f%% (reason=%s, trigger=%s)",
            self.cover,
            service,
            self._target,
            message_reason,
            trigger,
        )
        self._fire_event(
            "command",
            {
                "service": service,
                "reason": message_reason,
                "trigger": trigger,
                "target_position": self._target,
            },
        )
        await self.hass.services.async_call(
            "cover", service, service_data, blocking=True, context=ctx
        )

    async def _command_tilt_position(
        self, tilt_position: float, *, reason: str | None = None
    ) -> None:
        state = self._cover_state_or_warn(
            "set_cover_tilt_position",
            reason=reason,
            target_position=tilt_position,
        )
        if not state:
            return
        cover_entity_feature = await _async_cover_entity_feature(self.hass)
        supported = (state.attributes.get("supported_features")) or 0
        if not bool(int(supported) & cover_entity_feature.SET_TILT_POSITION):
            return

        ctx = Context()
        self._last_command_context_id = ctx.id
        self._last_command_at = dt_util.utcnow()
        self._ignore_service_call_until = self._last_command_at + timedelta(
            seconds=self._duration_value(CONF_DRIVE_TIME, DEFAULT_DRIVE_TIME)
        )
        self._fire_event(
            "command",
            {
                "service": "set_cover_tilt_position",
                "reason": reason or self._reason,
                "target_tilt_position": float(tilt_position),
            },
        )
        await self.hass.services.async_call(
            "cover",
            "set_cover_tilt_position",
            {"entity_id": self.cover, "tilt_position": float(tilt_position)},
            blocking=True,
            context=ctx,
        )

    async def _wait_for_position(
        self, target: float, tolerance: float, timeout: int = 30
    ) -> None:
        if self._current_position() is None:
            return

        def _target_reached() -> bool:
            current = self._current_position()
            return current is not None and abs(current - target) <= tolerance

        entities = [self.cover]
        if self.config.get(CONF_POSITION_SOURCE) == CONF_POSITION_SOURCE_CUSTOM_SENSOR:
            custom_sensor = self.config.get(CONF_CUSTOM_POSITION_SENSOR)
            if isinstance(custom_sensor, str) and custom_sensor:
                entities.append(custom_sensor)
        await self._async_wait_for_state_change(_target_reached, timeout, entities)

    async def _async_wait_for_state_change(
        self,
        predicate,
        timeout: float,
        entity_ids: list[str] | None = None,
    ) -> bool:
        """Wait for a relevant HA state event, with a non-polling timeout."""

        if predicate():
            return True
        loop = asyncio.get_running_loop()
        reached = loop.create_future()

        @callback
        def _handle_state_event(_event) -> None:
            if not reached.done() and predicate():
                reached.set_result(True)

        unsubscribe = async_track_state_change_event(
            self.hass, entity_ids or [self.cover], _handle_state_event
        )
        try:
            async with asyncio.timeout(max(0, timeout)):
                await reached
            return True
        except TimeoutError:
            return predicate()
        finally:
            unsubscribe()
