"""Fixed shuttercontrol-style shading modes."""

from __future__ import annotations

from datetime import datetime, timedelta

from ..const import (
    CONF_CLOSE_POSITION, CONF_HEAT_PROTECTION_ENABLED,
    CONF_HEAT_PROTECTION_THRESHOLD, CONF_SHADING_BRIGHTNESS_HYSTERESIS,
    CONF_SHADING_BRIGHTNESS_SENSOR, CONF_SHADING_BRIGHTNESS_THRESHOLD,
    CONF_SHADING_DIRECTION, CONF_SHADING_DIRECTION_RANGE,
    CONF_SHADING_INSIDE_TEMPERATURE_HYSTERESIS,
    CONF_SHADING_INSIDE_TEMPERATURE_THRESHOLD, CONF_SHADING_MODE,
    CONF_SHADING_OUTSIDE_TEMPERATURE_HYSTERESIS,
    CONF_SHADING_OUTSIDE_TEMPERATURE_THRESHOLD, CONF_SUN_ELEVATION_MAX,
    CONF_SUN_ELEVATION_MIN, CONF_TEMPERATURE_SENSOR_INDOOR,
    CONF_TEMPERATURE_SENSOR_OUTDOOR, DEFAULT_CLOSE_POSITION,
    DEFAULT_HEAT_PROTECTION_THRESHOLD, DEFAULT_SHADING_BRIGHTNESS_HYSTERESIS,
    DEFAULT_SHADING_BRIGHTNESS_THRESHOLD, DEFAULT_SHADING_DIRECTION,
    DEFAULT_SHADING_DIRECTION_RANGE, DEFAULT_SHADING_ELEVATION_MAX,
    DEFAULT_SHADING_ELEVATION_MIN, DEFAULT_SHADING_INSIDE_TEMPERATURE_HYSTERESIS,
    DEFAULT_SHADING_INSIDE_TEMPERATURE_THRESHOLD, DEFAULT_SHADING_MODE,
    DEFAULT_SHADING_OUTSIDE_TEMPERATURE_HYSTERESIS,
    DEFAULT_SHADING_OUTSIDE_TEMPERATURE_THRESHOLD, SHADING_MODE_DIRECTION,
    SHADING_MODE_INSIDE, SHADING_MODE_INSIDE_OUTSIDE,
    SHADING_MODE_INSIDE_OUTSIDE_DIRECTION, SHADING_MODE_OFF,
    SHADING_MODE_OUTSIDE, SHADING_MODE_OUTSIDE_DIRECTION,
)
from .common import _coerce_float


class ShadingMixin:
    """Evaluate one of the fixed shading modes."""

    def _shading_brightness_value(self, fallback: float | None) -> float | None:
        sensor = self.config.get(CONF_SHADING_BRIGHTNESS_SENSOR)
        if not sensor:
            return fallback
        state = self._state_for(sensor)
        return _coerce_float(state.state if state else None)

    def _temperature_value(self, key: str) -> float | None:
        state = self._state_for(self.config.get(key))
        return _coerce_float(state.state if state else None)

    @staticmethod
    def _above_threshold(
        value: float | None, threshold: float, hysteresis: float, active: bool
    ) -> bool:
        if value is None:
            return False
        limit = threshold * (1 - max(0.0, hysteresis) / 100) if active else threshold
        return value >= limit if active else value > limit

    @staticmethod
    def _direction_matches(azimuth: float | None, direction: float, span: float) -> bool:
        if azimuth is None:
            return False
        distance = abs((azimuth - direction + 180) % 360 - 180)
        return distance <= min(max(span, 0.0), 180.0)

    def _shading_condition_state(
        self, sun_azimuth: float | None, sun_elevation: float | None,
        brightness: float | None, *, active: bool,
    ) -> dict[str, bool]:
        mode = str(self.config.get(CONF_SHADING_MODE, DEFAULT_SHADING_MODE))
        inside_ok = self._above_threshold(
            self._temperature_value(CONF_TEMPERATURE_SENSOR_INDOOR),
            self._number_value(CONF_SHADING_INSIDE_TEMPERATURE_THRESHOLD, DEFAULT_SHADING_INSIDE_TEMPERATURE_THRESHOLD),
            self._number_value(CONF_SHADING_INSIDE_TEMPERATURE_HYSTERESIS, DEFAULT_SHADING_INSIDE_TEMPERATURE_HYSTERESIS),
            active,
        )
        outside_ok = self._above_threshold(
            self._temperature_value(CONF_TEMPERATURE_SENSOR_OUTDOOR),
            self._number_value(CONF_SHADING_OUTSIDE_TEMPERATURE_THRESHOLD, DEFAULT_SHADING_OUTSIDE_TEMPERATURE_THRESHOLD),
            self._number_value(CONF_SHADING_OUTSIDE_TEMPERATURE_HYSTERESIS, DEFAULT_SHADING_OUTSIDE_TEMPERATURE_HYSTERESIS),
            active,
        )
        direction_ok = self._direction_matches(
            sun_azimuth,
            self._number_value(CONF_SHADING_DIRECTION, DEFAULT_SHADING_DIRECTION),
            self._number_value(CONF_SHADING_DIRECTION_RANGE, DEFAULT_SHADING_DIRECTION_RANGE),
        )
        elevation_ok = (
            sun_elevation is not None
            and self._number_value(CONF_SUN_ELEVATION_MIN, DEFAULT_SHADING_ELEVATION_MIN)
            <= sun_elevation
            <= self._number_value(CONF_SUN_ELEVATION_MAX, DEFAULT_SHADING_ELEVATION_MAX)
        )
        brightness_sensor = self.config.get(CONF_SHADING_BRIGHTNESS_SENSOR)
        brightness_ok = True
        if brightness_sensor and mode in {
            SHADING_MODE_INSIDE_OUTSIDE, SHADING_MODE_INSIDE_OUTSIDE_DIRECTION,
            SHADING_MODE_OUTSIDE_DIRECTION, SHADING_MODE_OUTSIDE,
        }:
            brightness_ok = self._above_threshold(
                self._shading_brightness_value(brightness),
                self._number_value(CONF_SHADING_BRIGHTNESS_THRESHOLD, DEFAULT_SHADING_BRIGHTNESS_THRESHOLD),
                self._number_value(CONF_SHADING_BRIGHTNESS_HYSTERESIS, DEFAULT_SHADING_BRIGHTNESS_HYSTERESIS),
                active,
            )
        return {
            "inside_temperature": inside_ok, "outside_temperature": outside_ok,
            "brightness": brightness_ok, "direction": direction_ok,
            "elevation": elevation_ok,
        }

    def _shading_mode_allows(
        self, sun_azimuth: float | None, sun_elevation: float | None,
        brightness: float | None, *, active: bool,
    ) -> bool:
        mode = str(self.config.get(CONF_SHADING_MODE, DEFAULT_SHADING_MODE))
        conditions = self._shading_condition_state(
            sun_azimuth, sun_elevation, brightness, active=active
        )
        self._status["shading_conditions"] = conditions
        required = {
            SHADING_MODE_INSIDE_OUTSIDE: ("inside_temperature", "outside_temperature", "brightness"),
            SHADING_MODE_DIRECTION: ("direction", "elevation"),
            SHADING_MODE_INSIDE_OUTSIDE_DIRECTION: ("inside_temperature", "outside_temperature", "brightness", "direction", "elevation"),
            SHADING_MODE_OUTSIDE_DIRECTION: ("outside_temperature", "brightness", "direction", "elevation"),
            SHADING_MODE_OUTSIDE: ("outside_temperature", "brightness"),
            SHADING_MODE_INSIDE: ("inside_temperature",),
        }.get(mode, ())
        return mode != SHADING_MODE_OFF and bool(required) and all(conditions[key] for key in required)

    def _shading_start_conditions(self, sun_azimuth: float | None, sun_elevation: float | None, brightness: float | None) -> tuple[bool, bool]:
        return self._shading_mode_allows(sun_azimuth, sun_elevation, brightness, active=False), False

    def _shading_end_conditions(self, sun_azimuth: float | None, sun_elevation: float | None, brightness: float | None) -> bool:
        return not self._shading_mode_allows(sun_azimuth, sun_elevation, brightness, active=True)

    def _shading_end_wait_complete(self, now: datetime, condition_valid: bool, waiting_seconds: int) -> bool:
        if not condition_valid:
            if self._shading_pending_active("end"):
                self._clear_shading_pending("end")
            return False
        if waiting_seconds <= 0:
            return True
        if self._shading_pending_due("end", now):
            return True
        if not self._shading_pending_active("end"):
            self._set_shading_pending("end", now + timedelta(seconds=waiting_seconds), True)
        return False

    def _heat_protection_state(self) -> tuple[bool, float | None]:
        temperature = self._temperature_value(CONF_TEMPERATURE_SENSOR_OUTDOOR)
        threshold = _coerce_float(self.config.get(CONF_HEAT_PROTECTION_THRESHOLD, DEFAULT_HEAT_PROTECTION_THRESHOLD))
        active = bool(self.config.get(CONF_HEAT_PROTECTION_ENABLED, False) and temperature is not None and threshold is not None and temperature > threshold)
        return active, temperature

    def _heat_protection_hold(self) -> bool:
        section = self._status.get("heat_protection", {})
        return bool(section.get("hold")) if isinstance(section, dict) else False

    def _shading_target_reason(self) -> tuple[float, str]:
        active, _temperature = self._heat_protection_state()
        if active:
            return self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION), "heat_protection"
        return self._effective_shading_position(), "shading"

    def _active_shading_target_reason(self, current_position: float | None) -> tuple[float | None, str, bool]:
        active, _temperature = self._heat_protection_state()
        if active:
            target, reason = self._shading_target_reason()
            return target, reason, True
        close_target = self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION)
        if self._heat_protection_hold() and self._position_matches(close_target, current_position):
            return None, "shading", True
        return self._effective_shading_position(), "shading", False

    def _set_heat_protection_status(self, active: bool, hold: bool) -> bool:
        section = self._status.setdefault("heat_protection", {})
        changed = section.get("active") is not active or section.get("hold") is not hold
        section["active"] = active
        section["hold"] = hold
        return changed

    def heat_protection_snapshot(self) -> dict[str, object]:
        active, temperature = self._heat_protection_state()
        return {"active": active and self._reason == "heat_protection", "threshold": self._number_value(CONF_HEAT_PROTECTION_THRESHOLD, DEFAULT_HEAT_PROTECTION_THRESHOLD), "temperature": temperature}
