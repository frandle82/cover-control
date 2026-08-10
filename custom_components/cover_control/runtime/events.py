"""Cover controller behavior split from the public controller facade."""

from __future__ import annotations

import asyncio
from datetime import (
    datetime,
    timedelta,
)

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from ..const import (
    CONF_AUTO_SHADING,
    CONF_CLOSE_POSITION,
    CONF_CUSTOM_POSITION_SENSOR,
    CONF_DRIVE_TIME,
    CONF_MANUAL_OVERRIDE_BLOCK_CLOSE,
    CONF_MANUAL_OVERRIDE_BLOCK_OPEN,
    CONF_MANUAL_OVERRIDE_BLOCK_SHADING,
    CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE,
    CONF_MANUAL_OVERRIDE_MINUTES,
    CONF_MANUAL_OVERRIDE_RESET_MODE,
    CONF_MANUAL_OVERRIDE_RESET_TIME,
    CONF_OPEN_POSITION,
    CONF_POSITION_SOURCE,
    CONF_POSITION_SOURCE_CURRENT_POSITION_ATTR,
    CONF_POSITION_SOURCE_CUSTOM_SENSOR,
    CONF_POSITION_TOLERANCE,
    CONF_RESIDENT_SENSOR,
    CONF_VENTILATE_POSITION,
    CONF_VENTILATION_START_NO_DELAY,
    DEFAULT_CLOSE_POSITION,
    DEFAULT_DRIVE_TIME,
    DEFAULT_MANUAL_OVERRIDE_FLAGS,
    DEFAULT_MANUAL_OVERRIDE_MINUTES,
    DEFAULT_MANUAL_OVERRIDE_RESET_TIME,
    DEFAULT_OPEN_POSITION,
    DEFAULT_TOLERANCE,
    DEFAULT_VENTILATE_POSITION,
    DOMAIN,
    MANUAL_OVERRIDE_RESET_NONE,
    MANUAL_OVERRIDE_RESET_TIME,
    MANUAL_OVERRIDE_RESET_TIMEOUT,
)
from .common import (
    IDLE_REASON,
    _coerce_float,
    _parse_time,
    _ts_now,
)


class EventsMixin:
    async def async_setup(self) -> None:
        registry = er.async_get(self.hass)
        self._master_entity_id = registry.async_get_entity_id(
            "switch", DOMAIN, f"{self.entry.entry_id}-master"
        )
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._handle_interval, timedelta(minutes=1)
            )
        )
        self._unsubs.append(
            self.hass.bus.async_listen("call_service", self._handle_service_call)
        )
        self._sync_position_reference_from_entity()
        if self._target is None:
            self._target = self._current_position()
        if self._last_position is None:
            self._last_position = self._current_position()
        sensor_entities = self._decision_entities()
        sensor_entities.add(self.cover)
        for entity_id in sensor_entities:
            if not entity_id:
                continue
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, [entity_id], self._handle_state_event
                )
            )
        self._refresh_next_events(dt_util.utcnow())
        self._schedule_manual_expiry()
        self.persist_status()
        self._publish_state()
        self.async_request_evaluate("startup")

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
        if self._last_position is None:
            self._last_position = self._current_position()
        now = dt_util.utcnow()
        self._refresh_next_events(now)
        self._schedule_manual_expiry()
        self.persist_status()
        self.async_request_evaluate("config")
        self._publish_state()

    @callback
    def async_request_evaluate(self, trigger: str = "runtime_toggle") -> None:
        """Request re-evaluation after runtime-only toggle changes."""

        if self._evaluate_callback is not None:
            self._evaluate_callback(self, trigger)
            return
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

        if self._is_position_state_event(entity_id):
            tolerance = float(
                self._position_value(CONF_POSITION_TOLERANCE, DEFAULT_TOLERANCE)
            )
            current = self._current_position()
            if previous_position is None and current is not None:
                self._target = current
                self._status["target"] = current
                self._last_position = current
                self.persist_status()
                self.async_request_evaluate(trigger)
                return
            if self._target is None and current is not None:
                self._target = current
            drive_window = timedelta(
                seconds=(self._duration_value(CONF_DRIVE_TIME, DEFAULT_DRIVE_TIME) + 60)
            )
            command_still_active = (
                self._last_command_at is not None
                and dt_util.utcnow() - self._last_command_at <= drive_window
            )
            if current is not None and self._manual_detection_enabled():
                position_changed = (
                    previous_position is not None
                    and abs(current - previous_position) > tolerance
                )
                expected_command_move = command_still_active
                deviation_from_target = (
                    position_changed
                    and self._target is not None
                    and abs(current - self._target) > tolerance
                )
                unexplained_move = (
                    self._target is None
                    and previous_position is not None
                    and abs(current - previous_position) > tolerance
                )
                if (
                    deviation_from_target or unexplained_move
                ) and not expected_command_move:
                    self._target = current
                    self._activate_manual_override(
                        scope_all=True, reason="manual_override"
                    )
            self._last_position = current if current is not None else previous_position
        if entity_id in self._contact_entities():
            new_state = event.data.get("new_state")
            contact_now_active = new_state is not None and new_state.state in (
                "on",
                "true",
                "1",
            )
            no_delay_on_start = (
                bool(self.config.get(CONF_VENTILATION_START_NO_DELAY, False))
                and contact_now_active
            )
            delay = (
                0
                if no_delay_on_start
                else (self._contact_trigger_delay() + self._contact_status_delay())
            )
            if delay > 0:
                self.hass.async_create_task(self._delayed_evaluate("contact", delay))
                return
            trigger = "contact"
        self.async_request_evaluate(trigger)

    def _is_position_state_event(self, entity_id: str | None) -> bool:
        if entity_id == self.cover:
            return True
        source = str(
            self.config.get(
                CONF_POSITION_SOURCE, CONF_POSITION_SOURCE_CURRENT_POSITION_ATTR
            )
            or CONF_POSITION_SOURCE_CURRENT_POSITION_ATTR
        )
        return (
            source == CONF_POSITION_SOURCE_CUSTOM_SENSOR
            and entity_id == self.config.get(CONF_CUSTOM_POSITION_SENSOR)
        )

    @callback
    def _handle_service_call(self, event) -> None:
        if event.data.get("domain") != "cover":
            return

        service = event.data.get("service")
        if service not in {
            "set_cover_position",
            "set_cover_tilt_position",
            "open_cover",
            "close_cover",
        }:
            return

        service_data = event.data.get("service_data") or {}
        entity_ids = service_data.get("entity_id")
        if not entity_ids:
            return
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
        if self.cover not in entity_ids:
            return

        now = dt_util.utcnow()
        if (
            self._ignore_service_call_until is not None
            and now <= self._ignore_service_call_until
        ):
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
        elif service == "set_cover_tilt_position":
            position = self._current_position()
        elif service == "open_cover":
            position = 100.0
        elif service == "close_cover":
            position = 0.0

        if position is not None:
            self._target = position
            self._status["target"] = position

        self._activate_manual_override(scope_all=True, reason="manual_override")
        self.async_request_evaluate("manual_service")

    @callback
    def _handle_interval(self, now: datetime) -> None:
        self.async_request_evaluate("time")

    async def _delayed_evaluate(self, trigger: str, delay: int) -> None:
        await asyncio.sleep(delay)
        self.async_request_evaluate(trigger)

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
        self,
        minutes: int | None = None,
        scope_all: bool = False,
        reason: str | None = None,
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

    def _manual_reset_at(
        self, now: datetime, minutes: int | None = None
    ) -> datetime | None:
        if minutes is not None:
            return now + timedelta(minutes=minutes)
        mode = self.config.get(
            CONF_MANUAL_OVERRIDE_RESET_MODE, MANUAL_OVERRIDE_RESET_TIMEOUT
        )
        if mode == MANUAL_OVERRIDE_RESET_NONE:
            return None
        if mode == MANUAL_OVERRIDE_RESET_TIME:
            reset_time = _parse_time(
                self.config.get(CONF_MANUAL_OVERRIDE_RESET_TIME)
            ) or _parse_time(DEFAULT_MANUAL_OVERRIDE_RESET_TIME)
            return self._next_time_for_point(reset_time, now)
        duration = self.config.get(
            CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES
        )
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
        return bool(
            self.config.get(flag, DEFAULT_MANUAL_OVERRIDE_FLAGS.get(flag, False))
        )

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
        self.async_request_evaluate("manual_cleared")

    def _remember_pre_ventilation_position(self) -> None:
        """Remember current position before switching into ventilation mode."""
        if self._reason in {"ventilation", "ventilation_full"}:
            return
        self._remember_status_background("ventilation")
        current = self._current_position()
        if current is not None:
            self._pre_ventilation_position = float(current)
            self._status.setdefault("ventilation", {})["restore_position"] = (
                self._pre_ventilation_position
            )
            self.persist_status()

    def _remember_force_background(self) -> None:
        section = self._status.setdefault("force", {})
        if not section.get("active"):
            self._remember_status_background("force")
        section["active"] = True
        section["ts"] = _ts_now()
        self.persist_status()

    def _clear_force_background(self) -> None:
        section = self._status.setdefault("force", {})
        section["active"] = False
        section["restore_position"] = None
        section["background"] = {"open": False, "close": False, "shading": False}
        section["ts"] = _ts_now()

    def _force_return_target(
        self, *, allow_open: bool = True, allow_shading: bool = True
    ) -> tuple[float | None, str]:
        section = self._status.get("force", {})
        fallback = None
        if isinstance(section, dict):
            fallback = _coerce_float(section.get("restore_position"))
        return self._background_return_target(
            self._background_for("force"),
            fallback=fallback,
            allow_open=allow_open,
            allow_shading=allow_shading,
        )

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
        duration = minutes or self.config.get(
            CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES
        )
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
            self._set_position(self._effective_shading_position(), "manual_shading")
        )

    async def recalibrate(self, full_open: float | None) -> None:
        tolerance = float(
            self._position_value(CONF_POSITION_TOLERANCE, DEFAULT_TOLERANCE)
        )
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
        self._remember_force_background()
        self._activate_manual_override(scope_all=True, reason=reason)
        await self._command_position(float(target), reason=reason)
        tilt_position = self._tilt_position_value(reason)
        if tilt_position is not None:
            await self._send_tilt_after_position(float(tilt_position), reason=reason)
        self._target = float(target)
        self._reason = reason
        self._record_action_status(reason, float(target))
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

    async def force_ventilation(self, action: str) -> None:
        self._activate_manual_override(scope_all=True, reason="ventilation")
        if action == "start":
            self._remember_force_background()
            self._remember_pre_ventilation_position()
            target = self._position_value(
                CONF_VENTILATE_POSITION, DEFAULT_VENTILATE_POSITION
            )
            if target is None:
                return
            await self._command_position(float(target), reason="ventilation_start")
            tilt_position = self._tilt_position_value("ventilation_start")
            if tilt_position is not None:
                await self._send_tilt_after_position(
                    float(tilt_position), reason="ventilation_start"
                )
            self._target = float(target)
            self._reason = "ventilation"
            self._set_ventilation_status(True, False)
            self.persist_status()
        elif action == "stop":
            target, reason = self._force_return_target()
            if target is None:
                target = self._pre_ventilation_position
                reason = "ventilation_stop"
            if target is None:
                target = self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION)
            if target is None:
                return
            await self._command_position(float(target), reason=reason)
            tilt_position = self._tilt_position_value(reason)
            if tilt_position is not None:
                await self._send_tilt_after_position(
                    float(tilt_position), reason=reason
                )
            self._target = float(target)
            self._reason = reason
            self._pre_ventilation_position = None
            self._set_ventilation_status(False, False)
            self._record_action_status(reason, float(target))
            self._clear_force_background()
            self.persist_status()
        else:
            return
        self._refresh_next_events(dt_util.utcnow())
        self._publish_state()

    async def force_shading(self, action: str) -> None:
        self._activate_manual_override(scope_all=True, reason="manual_shading")
        if action == "activate":
            self._remember_force_background()
            target = self._effective_shading_position()
            if target is None:
                return
            await self._command_position(float(target), reason="manual_shading")
            tilt_position = self._tilt_position_value("manual_shading")
            if tilt_position is not None:
                await self._send_tilt_after_position(
                    float(tilt_position), reason="manual_shading"
                )
            self._target = float(target)
            self._reason = "manual_shading"
            self._record_action_status("manual_shading", float(target))
        elif action == "deactivate":
            target, reason = self._force_return_target()
            if target is None:
                target = self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION)
                reason = "manual_shading_end"
            if target is None:
                return
            await self._command_position(float(target), reason=reason)
            tilt_position = self._tilt_position_value(reason)
            if tilt_position is not None:
                await self._send_tilt_after_position(
                    float(tilt_position), reason=reason
                )
            self._target = float(target)
            self._reason = reason
            self._record_action_status(reason, float(target))
            self._clear_force_background()
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
        self.async_request_evaluate("manual_expired")
