"""Safety alarm priority, fire latch, and frost protection."""

from __future__ import annotations

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

from ..const import (
    CONF_CLOSE_POSITION,
    CONF_FIRE_ALARM_ENTITY,
    DEFAULT_CLOSE_POSITION,
    FUNCTION_SAFETY,
    SAFETY_ALARMS,
)
from .common import _coerce_float, _ts_now


SAFETY_REASONS = {
    "fire_alarm",
    "rain_alarm",
    "wind_alarm_2",
    "wind_alarm_1",
    "frost_alarm",
    "fire_latched",
}


class SafetyMixin:
    """Evaluate alarms above every comfort and manual control."""

    def fire_latched(self) -> bool:
        return bool(self._status.get("safety", {}).get("fire_latched", False))

    def safety_snapshot(self) -> dict[str, object]:
        return {
            "active_safety": self._active_safety,
            "fire_latched": self.fire_latched(),
            "safety_target": self._safety_target,
        }

    def _set_fire_latched(self, latched: bool) -> None:
        safety = self._status.setdefault("safety", {})
        safety["fire_latched"] = latched
        safety["ts"] = _ts_now()
        self.persist_status()

    def _safety_selected(self) -> bool:
        return FUNCTION_SAFETY in getattr(
            self.config, "configured_functions", frozenset()
        )

    def _safety_alarm_config(self, alarm: str) -> tuple[str, float] | None:
        if not self._safety_selected():
            return None
        for item in SAFETY_ALARMS:
            name, entity_key, enabled_key, target_key, room_key, default = item
            if name != alarm:
                continue
            if not self.config.get(enabled_key, False) or not self.config.get(
                room_key, False
            ):
                return None
            entity_id = self.config.get(entity_key)
            if not isinstance(entity_id, str) or not entity_id:
                return None
            target = _coerce_float(self.config.get(target_key, default))
            return (
                entity_id,
                default if target is None else max(0.0, min(100.0, target)),
            )
        return None

    def _safety_alarm_active(self, alarm: str) -> bool | None:
        config = self._safety_alarm_config(alarm)
        if config is None:
            return False
        state = self._state_for(config[0])
        if state is None or state.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
            return None
        value = str(state.state).strip().lower()
        if value in {"on", "true", "1", "open", "active"}:
            return True
        if value in {"off", "false", "0", "closed", "inactive"}:
            return False
        return None

    def _configured_safety_target(self, alarm: str) -> float | None:
        config = self._safety_alarm_config(alarm)
        return config[1] if config else None

    def _active_safety_alarm(self) -> tuple[str, float] | None:
        for alarm, *_rest in SAFETY_ALARMS:
            if self._safety_alarm_active(alarm) is True:
                target = self._configured_safety_target(alarm)
                if target is not None:
                    return alarm, target
        return None

    async def _evaluate_safety(self) -> bool:
        fire_active = self._safety_alarm_active("fire")
        if fire_active is True and not self.fire_latched():
            self._set_fire_latched(True)

        if self.fire_latched():
            self._cancel_window_down_sequence()
            self._active_safety = "fire" if fire_active is True else "fire_latched"
            self._safety_target = self._configured_safety_target("fire")
            self._decision_controls.add(
                "fire_alarm" if fire_active is True else "fire_latched"
            )
            if fire_active is True and self._safety_target is not None:
                await self._set_position(self._safety_target, "fire_alarm")
            else:
                self._reason = "fire_latched"
                self._publish_state()
            return True

        active = None
        for alarm, *_rest in SAFETY_ALARMS:
            state = self._safety_alarm_active(alarm)
            if state is None:
                self._cancel_window_down_sequence()
                self._active_safety = "unavailable"
                self._safety_target = None
                self._decision_controls.add("safety")
                self._publish_state()
                return True
            if state:
                target = self._configured_safety_target(alarm)
                if target is not None:
                    active = (alarm, target)
                    break
        if active is None:
            self._active_safety = None
            self._safety_target = None
            if self._reason in SAFETY_REASONS:
                self._reason = None
            return False

        alarm, target = active
        reason = f"{alarm}_alarm" if alarm in {"fire", "rain", "frost"} else alarm
        self._active_safety = alarm
        self._safety_target = target
        self._decision_controls.add(reason)
        self._cancel_window_down_sequence()
        if alarm == "frost":
            close_target = self._position_value(
                CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION
            )
            if self._position_matches(close_target, self._current_position()):
                await self._set_position(target, reason)
                return True
            if self._reason in SAFETY_REASONS:
                self._reason = None
            return False
        await self._set_position(target, reason)
        return True

    def _frost_target_if_active(self) -> float | None:
        if self.fire_latched() or self._safety_alarm_active("frost") is not True:
            return None
        return self._configured_safety_target("frost")

    def can_reset_fire_latch(self) -> bool:
        entity_id = self.config.get(CONF_FIRE_ALARM_ENTITY)
        if isinstance(entity_id, str) and entity_id:
            state = self._state_for(entity_id)
            if state is None or str(state.state).strip().lower() not in {
                "off",
                "false",
                "0",
                "closed",
                "inactive",
            }:
                return False
        return True

    def reset_fire_latch(self) -> bool:
        if not self.can_reset_fire_latch():
            return False
        self._set_fire_latched(False)
        if self._reason == "fire_latched":
            self._reason = None
        self._active_safety = None
        self._safety_target = None
        return True
