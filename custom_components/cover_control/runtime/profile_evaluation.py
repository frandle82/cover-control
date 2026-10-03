"""Shared profile-level calculations that deliberately exclude room state."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from homeassistant.util import dt as dt_util

from ..const import (
    CONF_SUN_ELEVATION_CLOSE,
    CONF_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR,
    CONF_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR,
    CONF_SUN_ELEVATION_MODE,
    CONF_SUN_ELEVATION_OPEN,
    DEFAULT_SUN_ELEVATION_CLOSE,
    DEFAULT_SUN_ELEVATION_MODE,
    DEFAULT_SUN_ELEVATION_OPEN,
)
from .schedule import ScheduleMixin


class _TimeProfileProbe(ScheduleMixin):
    """Reuse schedule logic without creating cover state or room timers."""

    def __init__(self, hass, config: Mapping[str, Any]) -> None:
        self.hass = hass
        self.config = config
        self._last_action_dates: dict[str, object] = {}
        self._next_open: datetime | None = None
        self._next_close: datetime | None = None

    def _auto_enabled(self, config_key: str) -> bool:
        return bool(self.config.get(config_key))

    def _state_for(self, entity_id: str | None):
        return self.hass.states.get(entity_id) if entity_id else None

    def _dynamic_sun_threshold(self, kind: str) -> float | None:
        mode = str(
            self.config.get(CONF_SUN_ELEVATION_MODE, DEFAULT_SUN_ELEVATION_MODE)
            or DEFAULT_SUN_ELEVATION_MODE
        ).lower()
        if kind == "open":
            fixed_key = CONF_SUN_ELEVATION_OPEN
            sensor_key = CONF_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR
            fixed_default = DEFAULT_SUN_ELEVATION_OPEN
        else:
            fixed_key = CONF_SUN_ELEVATION_CLOSE
            sensor_key = CONF_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR
            fixed_default = DEFAULT_SUN_ELEVATION_CLOSE
        try:
            fixed = float(self.config.get(fixed_key, fixed_default))
        except (TypeError, ValueError):
            return None
        if mode == "fixed":
            return fixed
        state = self._state_for(self.config.get(sensor_key))
        try:
            dynamic = float(state.state) if state is not None else None
        except (TypeError, ValueError):
            dynamic = None
        if mode == "dynamic":
            return dynamic if dynamic is not None else fixed
        if mode == "hybrid":
            return fixed if dynamic is None else dynamic + fixed
        return fixed

    def _reschedule_next_event_timers(self, now: datetime) -> None:
        return None


def evaluate_time_profile(
    hass, config: Mapping[str, Any], now: datetime | None = None
) -> tuple[datetime | None, datetime | None]:
    """Return the next pure profile opportunities using existing schedule logic."""

    probe = _TimeProfileProbe(hass, config)
    probe._refresh_next_events(now or dt_util.utcnow())
    return probe._next_open, probe._next_close
