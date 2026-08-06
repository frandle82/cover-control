"""Cover controller behavior split from the public controller facade."""

from __future__ import annotations

import asyncio
from datetime import (
    datetime,
    timedelta,
)
from importlib import import_module
from inspect import isawaitable

from homeassistant.const import (
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    Context,
    State,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from ..const import (
    CONF_ADDITIONAL_CONDITION_CLOSE,
    CONF_ADDITIONAL_CONDITION_GLOBAL,
    CONF_ADDITIONAL_CONDITION_OPEN,
    CONF_ADDITIONAL_CONDITION_SHADING,
    CONF_ADDITIONAL_CONDITION_SHADING_END,
    CONF_ADDITIONAL_CONDITION_SHADING_TILT,
    CONF_ADDITIONAL_CONDITION_VENTILATE,
    CONF_ADDITIONAL_CONDITION_VENTILATE_END,
    CONF_ADDITIONAL_CONDITIONS_ENABLED,
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_SHADING,
    CONF_AUTO_SUN,
    CONF_AUTO_TIME,
    CONF_AUTO_VENTILATE,
    CONF_BRIGHTNESS_SENSOR,
    CONF_CALENDAR_ENTITY,
    CONF_CLOSE_TILT_POSITION,
    CONF_COVER_TILT_WAIT_MODE,
    CONF_COVER_TILT_WAIT_TIMEOUT,
    CONF_CUSTOM_POSITION_SENSOR,
    CONF_DRIVE_TIME,
    CONF_LOCKOUT_POSITION,
    CONF_MASTER_ENABLED,
    CONF_OPEN_POSITION,
    CONF_OPEN_TILT_POSITION,
    CONF_POSITION_SOURCE,
    CONF_POSITION_SOURCE_CURRENT_POSITION_ATTR,
    CONF_POSITION_SOURCE_CUSTOM_SENSOR,
    CONF_POSITION_SOURCE_POSITION_ATTR,
    CONF_POSITION_TOLERANCE,
    CONF_PREVENT_DEFAULT_COVER_ACTIONS,
    CONF_RESIDENT_SENSOR,
    CONF_RESIDENT_STATUS,
    CONF_SHADING_BRIGHTNESS_SENSOR,
    CONF_SHADING_FORECAST_SENSOR,
    CONF_SHADING_FORECAST_TEMP_SENSOR,
    CONF_SHADING_POSITION,
    CONF_SHADING_POSITION_ALT,
    CONF_SHADING_POSITION_ALT_ENTITY,
    CONF_SHADING_TEMPERATURE_SENSOR_1,
    CONF_SHADING_TEMPERATURE_SENSOR_2,
    CONF_SHADING_TILT_ELEVATION_1,
    CONF_SHADING_TILT_ELEVATION_2,
    CONF_SHADING_TILT_ELEVATION_3,
    CONF_SHADING_TILT_POSITION,
    CONF_SHADING_TILT_POSITION_0,
    CONF_SHADING_TILT_POSITION_1,
    CONF_SHADING_TILT_POSITION_2,
    CONF_SHADING_TILT_POSITION_3,
    CONF_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR,
    CONF_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR,
    CONF_VENTILATE_POSITION,
    CONF_VENTILATE_TILT_POSITION,
    CONF_WINDOW_SENSOR_FULL,
    CONF_WINDOW_SENSOR_TILT,
    CONF_WORKDAY_SENSOR,
    CONF_WORKDAY_TOMORROW_SENSOR,
    COVER_TILT_WAIT_BEFORE_POSITION,
    COVER_TILT_WAIT_IDLE,
    DEFAULT_AUTOMATION_FLAGS,
    DEFAULT_CLOSE_TILT_POSITION,
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
    DEFAULT_VENTILATE_POSITION,
    DEFAULT_VENTILATE_TILT_POSITION,
    DOMAIN,
    EVENT_COVER_CONTROL,
    SIGNAL_STATE_UPDATED,
)
from .common import (
    _LOGGER,
    IDLE_REASON,
    _coerce_float,
    _float_state,
)

_COVER_ENTITY_FEATURE = None
_CONDITION_API = None
_CONDITION_ERROR = None


async def _async_cover_entity_feature(hass):
    """Load the heavy cover component off the event loop on first use."""

    global _COVER_ENTITY_FEATURE
    if _COVER_ENTITY_FEATURE is None:
        cover_module = await hass.async_add_executor_job(
            import_module, "homeassistant.components.cover"
        )
        _COVER_ENTITY_FEATURE = cover_module.CoverEntityFeature
    return _COVER_ENTITY_FEATURE


async def _async_condition_api(hass):
    """Load optional condition support off the event loop on first use."""

    global _CONDITION_API, _CONDITION_ERROR
    if _CONDITION_API is None:

        def _load_condition_api():
            condition_api = import_module("homeassistant.helpers.condition")
            exceptions = import_module("homeassistant.exceptions")
            return condition_api, exceptions.ConditionError

        async_add_executor_job = getattr(hass, "async_add_executor_job", None)
        if async_add_executor_job is None:
            _CONDITION_API, _CONDITION_ERROR = _load_condition_api()
        else:
            _CONDITION_API, _CONDITION_ERROR = await async_add_executor_job(
                _load_condition_api
            )
    return _CONDITION_API, _CONDITION_ERROR


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
        manager = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id)
        get_runtime_toggle = getattr(manager, "get_runtime_toggle", None)
        if get_runtime_toggle is not None:
            runtime_override = get_runtime_toggle(config_key)
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

        condition, condition_error = await _async_condition_api(self.hass)

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
            checker = await condition.async_from_config(self.hass, validated_config)
            async_check = getattr(checker, "async_check", None)
            if async_check is None:
                # Home Assistant before the condition checker API returned a
                # callable instead. Keep supporting the HACS minimum version.
                result = checker(self.hass)
                if isawaitable(result):
                    result = await result
                return bool(result)
            try:
                return bool(async_check())
            finally:
                checker.async_unload()
        except (
            condition_error
        ) as err:  # pragma: no cover - defensive for invalid config
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
        if self._group_position_callback is not None:
            await self._group_position_callback(self, float(position), reason)
            return
        await self._set_position_local(float(position), reason)

    async def _set_position_local(self, position: float, reason: str) -> None:
        """Move only this cover after room-level coordination is resolved."""

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
                await self._command_tilt_position(float(tilt_position), reason=reason)
            if self._reason is None:
                self._reason = reason
            self._target = target
            self._record_action_status(reason, target)
            self._publish_state()
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
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

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
            if not self._config_bool(CONF_PREVENT_DEFAULT_COVER_ACTIONS):
                await self.hass.services.async_call(
                    "cover",
                    "close_cover",
                    {"entity_id": self.cover},
                    blocking=True,
                    context=ctx,
                )
            await asyncio.sleep(1)
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
            end = dt_util.utcnow() + timedelta(seconds=timeout)
            while dt_util.utcnow() < end:
                state = self.hass.states.get(self.cover)
                if state is not None and state.state in ("open", "closed"):
                    break
                await asyncio.sleep(0.5)
        await self._command_tilt_position(tilt_position, reason=reason)

    def _tilt_position_value(self, reason: str | None) -> float | None:
        if not reason:
            return None
        if reason == "ventilation_full" or "open" in reason:
            return self._position_value(
                CONF_OPEN_TILT_POSITION, DEFAULT_OPEN_TILT_POSITION
            )
        if "close" in reason or reason == "resident_asleep":
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
        sun_state = self.hass.states.get("sun.sun")
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
        if auto_sun:
            keys.extend(
                [
                    CONF_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR,
                    CONF_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR,
                ]
            )
        if auto_shading:
            keys.extend(
                [
                    CONF_SHADING_BRIGHTNESS_SENSOR,
                    CONF_SHADING_TEMPERATURE_SENSOR_1,
                    CONF_SHADING_TEMPERATURE_SENSOR_2,
                    CONF_SHADING_FORECAST_SENSOR,
                    CONF_SHADING_FORECAST_TEMP_SENSOR,
                    CONF_SHADING_POSITION_ALT_ENTITY,
                ]
            )
        if self._auto_enabled(CONF_RESIDENT_STATUS):
            keys.append(CONF_RESIDENT_SENSOR)
        if self.config.get(CONF_POSITION_SOURCE) == CONF_POSITION_SOURCE_CUSTOM_SENSOR:
            keys.append(CONF_CUSTOM_POSITION_SENSOR)

        for key in keys:
            entity_id = self.config.get(key)
            if isinstance(entity_id, str) and entity_id:
                entities.add(entity_id)
        if auto_sun or auto_shading:
            entities.add("sun.sun")
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
        if self.config.get(
            CONF_ADDITIONAL_CONDITIONS_ENABLED,
            DEFAULT_AUTOMATION_FLAGS.get(CONF_ADDITIONAL_CONDITIONS_ENABLED, False),
        ):
            for key in (
                CONF_ADDITIONAL_CONDITION_GLOBAL,
                CONF_ADDITIONAL_CONDITION_OPEN,
                CONF_ADDITIONAL_CONDITION_CLOSE,
                CONF_ADDITIONAL_CONDITION_VENTILATE,
                CONF_ADDITIONAL_CONDITION_VENTILATE_END,
                CONF_ADDITIONAL_CONDITION_SHADING,
                CONF_ADDITIONAL_CONDITION_SHADING_TILT,
                CONF_ADDITIONAL_CONDITION_SHADING_END,
            ):
                entity_id = self.config.get(key)
                if isinstance(entity_id, str) and entity_id:
                    entities.add(entity_id)
        return entities

    def _unavailable_decision_entities(self) -> set[str]:
        """Return required decision inputs which do not have a usable state."""

        return {
            entity_id
            for entity_id in self._decision_entities()
            if (
                (state := self.hass.states.get(entity_id)) is None
                or state.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}
            )
        }

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
        tolerance = float(
            self._position_value(CONF_POSITION_TOLERANCE, DEFAULT_TOLERANCE)
        )
        return abs(current - float(target)) <= tolerance

    def _shading_is_active(
        self, current_position: float | None, shading_enabled: bool
    ) -> bool:
        if not shading_enabled:
            return False
        if self._reason not in {"shading", "manual_shading"}:
            return False
        shading_target = self._effective_shading_position()
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
        if not self._config_bool(CONF_PREVENT_DEFAULT_COVER_ACTIONS):
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
        if not self._config_bool(CONF_PREVENT_DEFAULT_COVER_ACTIONS):
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
        end = dt_util.utcnow() + timedelta(seconds=timeout)
        while dt_util.utcnow() < end:
            current = self._current_position()
            if current is not None and abs(current - target) <= tolerance:
                return
            await asyncio.sleep(1)
