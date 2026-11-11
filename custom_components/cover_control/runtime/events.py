"""Cover controller behavior split from the public controller facade."""

from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
)

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from ..const import (
    CONF_AUTO_SHADING,
    CONF_CLOSE_POSITION,
    CONF_DRIVE_TIME,
    CONF_MANUAL_CONTROL,
    CONF_MANUAL_OVERRIDE_MINUTES,
    CONF_OPEN_POSITION,
    CONF_POSITION_TOLERANCE,
    CONF_RESIDENT_SENSOR,
    CONF_SHADING_WAITINGTIME_END,
    CONF_VENTILATION_DELAY_AFTER_CLOSE,
    CONF_VENTILATE_POSITION,
    DEFAULT_CLOSE_POSITION,
    DEFAULT_DRIVE_TIME,
    DEFAULT_MANUAL_CONTROL,
    DEFAULT_MANUAL_OVERRIDE_MINUTES,
    DEFAULT_OPEN_POSITION,
    DEFAULT_TOLERANCE,
    DEFAULT_VENTILATE_POSITION,
    DOMAIN,
)
from .common import (
    CALENDAR_BOUNDARY_TRIGGERS,
    CONDITION_TIMER_TRIGGERS,
    IDLE_REASON,
    TRIGGER_COVER_POSITION_CHANGED,
    TRIGGER_RESIDENT_OFF,
    TRIGGER_RESIDENT_ON,
    TRIGGER_SCHEDULED_CLOSE,
    TRIGGER_SCHEDULED_FINAL_CLOSE,
    TRIGGER_SCHEDULED_OPEN,
    TRIGGER_SHADING_END_TIMER,
    TRIGGER_WINDOW_CLOSED,
    TRIGGER_WINDOW_OPEN,
    TRIGGER_WINDOW_TILTED,
    _coerce_float,
    scheduled_trigger,
    _ts_now,
)


class EventsMixin:
    async def async_setup(self) -> None:
        registry = er.async_get(self.hass)
        self._master_entity_id = registry.async_get_entity_id(
            "switch", DOMAIN, f"{self.entry.entry_id}-master"
        )
        self._unsubs.append(
            self.hass.bus.async_listen("call_service", self._handle_service_call)
        )
        self._sync_position_reference_from_entity()
        if self._target is None:
            self._target = self._current_position()
        if self._last_position is None:
            self._last_position = self._current_position()
        self._resubscribe_local_decision_entities()
        self._refresh_next_events(dt_util.utcnow())
        self._schedule_manual_expiry()
        self.persist_status()
        self._publish_state()
        self.async_request_evaluate("startup")

    async def async_unload(self) -> None:
        self._cancel_window_down_sequence()
        self._clear_scheduled_event_timers()
        self._clear_runtime_condition_timers()
        self._clear_manual_expiry()
        self._clear_local_decision_listeners()
        while self._unsubs:
            unsub = self._unsubs.pop()
            unsub()

    @callback
    def update_config(self, new_config: ConfigType) -> None:
        self._cancel_window_down_sequence()
        old_config = self.config
        due_at = getattr(self, "_shading_pending", {}).get("end")
        old_wait = max(
            0.0, float(old_config.get(CONF_SHADING_WAITINGTIME_END, 0) or 0)
        )
        pending_started = due_at - timedelta(seconds=old_wait) if due_at else None
        self.config = new_config
        self._resubscribe_local_decision_entities()
        self._clear_runtime_condition_timers()
        self._clear_manual_expiry()
        self._hydrate_persistent_status()
        if self._target is None:
            self._target = self._current_position()
        if self._last_position is None:
            self._last_position = self._current_position()
        now = dt_util.utcnow()
        if pending_started is not None:
            new_wait = max(
                0.0,
                float(new_config.get(CONF_SHADING_WAITINGTIME_END, 0) or 0),
            )
            due_at = pending_started + timedelta(seconds=new_wait)
            if new_wait > 0 and due_at > now:
                self._set_shading_pending("end", due_at, False)
        self._refresh_next_events(now)
        self._schedule_manual_expiry()
        self.persist_status()
        self.async_request_evaluate("config_updated")
        self._publish_state()

    @callback
    def _resubscribe_local_decision_entities(self) -> None:
        """Diff and update cover-specific state listeners."""

        desired = {self.cover, *self._local_decision_entities()}
        desired.discard("")
        for entity_id in self._local_listener_entities - desired:
            unsubscribe = self._local_listener_unsubs.pop(entity_id, None)
            if unsubscribe is not None:
                unsubscribe()
        for entity_id in desired - self._local_listener_entities:
            self._local_listener_unsubs[entity_id] = async_track_state_change_event(
                self.hass, [entity_id], self._handle_state_event
            )
        self._local_listener_entities = desired

    @callback
    def _clear_local_decision_listeners(self) -> None:
        for unsubscribe in self._local_listener_unsubs.values():
            unsubscribe()
        self._local_listener_unsubs.clear()
        self._local_listener_entities.clear()

    @callback
    def async_request_evaluate(self, trigger: str) -> None:
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
        trigger = TRIGGER_COVER_POSITION_CHANGED
        if entity_id == self.config.get(CONF_RESIDENT_SENSOR):
            old_state = event.data.get("old_state")
            new_state = event.data.get("new_state")
            old_value = old_state.state if old_state else None
            new_value = new_state.state if new_state else None
            if self._resident_state_is_on(old_value) and self._resident_state_is_off(
                new_value
            ):
                trigger = TRIGGER_RESIDENT_OFF
            elif self._resident_state_is_off(old_value) and self._resident_state_is_on(
                new_value
            ):
                trigger = TRIGGER_RESIDENT_ON

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
                    self._manual_movement_pending = True
            if getattr(self, "_manual_movement_pending", False) and current is not None:
                cover_state = self.hass.states.get(self.cover)
                movement_finished = cover_state is not None and cover_state.state not in {
                    "opening",
                    "closing",
                }
                if movement_finished:
                    self._manual_movement_pending = False
                    adopted_shading = self._adopt_manual_shading_position(current)
                    if (
                        not adopted_shading
                        and not self._manual_active
                        and self._manual_detection_enabled()
                    ):
                        self._clear_shading_for_manual_override()
                        self._activate_manual_override(reason="manual_override")
            self._last_position = current if current is not None else previous_position
        if entity_id in self._contact_entities():
            new_state = event.data.get("new_state")
            contact_now_active = new_state is not None and new_state.state in (
                "on",
                "true",
                "1",
            )
            delay = self._contact_trigger_delay() + self._contact_status_delay()
            trigger = self._window_trigger(entity_id, contact_now_active)
            if (
                not contact_now_active
                and entity_id in self._tilt_sensors()
            ):
                delay += self._duration_value(CONF_VENTILATION_DELAY_AFTER_CLOSE, 0)
            if delay > 0:
                self._schedule_delayed_evaluate(
                    trigger, delay, timer_key=f"contact:{entity_id}"
                )
                return
        self.async_request_evaluate(trigger)

    def _window_trigger(self, entity_id: str, active: bool) -> str:
        if active and entity_id in self._full_open_sensors():
            return TRIGGER_WINDOW_OPEN
        if active and entity_id in self._tilt_sensors():
            return TRIGGER_WINDOW_TILTED
        return TRIGGER_WINDOW_CLOSED

    def _is_position_state_event(self, entity_id: str | None) -> bool:
        return entity_id == self.cover

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
        if service != "set_cover_tilt_position":
            self._manual_movement_pending = True

        shading_adoption_pending = (
            service != "set_cover_tilt_position"
            and self._manual_shading_position_matches(position)
        )
        if not shading_adoption_pending:
            if self._manual_detection_enabled():
                self._clear_shading_for_manual_override()
                self._activate_manual_override(reason="manual_override")
        self.async_request_evaluate("manual_service")

    @callback
    def _schedule_delayed_evaluate(
        self, trigger: str, delay: int, *, timer_key: str | None = None
    ) -> None:
        key = timer_key or trigger
        unsubscribe = self._delayed_evaluation_unsubs.pop(key, None)
        if unsubscribe is not None:
            unsubscribe()
        due_at = dt_util.utcnow() + timedelta(seconds=delay)

        @callback
        def _handle_delayed_evaluation(_now: datetime) -> None:
            self._delayed_evaluation_unsubs.pop(key, None)
            self.async_request_evaluate(trigger)

        self._delayed_evaluation_unsubs[key] = async_track_point_in_time(
            self.hass, _handle_delayed_evaluation, due_at
        )

    def _manual_detection_enabled(self) -> bool:
        return not self._manual_active and bool(
            self.config.get(CONF_MANUAL_CONTROL, DEFAULT_MANUAL_CONTROL)
        )

    def _manual_shading_position_matches(self, position: float | None) -> bool:
        """Return whether a manual target is the enabled effective shading target."""

        return self._auto_enabled(CONF_AUTO_SHADING) and self._position_matches(
            self._effective_shading_position(), position
        )

    def _adopt_manual_shading_position(self, position: float) -> bool:
        """Adopt a completed manual move to the effective shading position."""

        if (
            not self._manual_shading_position_matches(position)
            or self._active_safety_alarm() is not None
            or self.fire_latched()
        ):
            return False
        target = self._effective_shading_position()
        self._target = target
        self._status["target"] = target
        self._reason = "shading"
        self._set_status_bucket("shading", True)
        self._clear_shading_pending(persist=False)
        self.persist_status()
        self._logbook_entry("Manual movement adopted as sun shading")
        self._fire_event(
            "manual_shading_adopted",
            {"trigger": TRIGGER_COVER_POSITION_CHANGED, "reason": "shading"},
        )
        self._publish_state()
        return True

    def _clear_shading_for_manual_override(self) -> None:
        """End an active shading state before applying a manual override."""

        if self._status_active("shading") or self._reason in {
            "shading",
            "manual_shading",
            "heat_protection",
        }:
            self._set_status_bucket("shading", False)
            self._set_heat_protection_status(False, False)
            self._clear_shading_pending(persist=False)

    def _activate_manual_override(
        self,
        minutes: int | None = None,
        reason: str | None = None,
    ) -> None:
        now = dt_util.utcnow()
        was_active = self._manual_active
        self._manual_active = True
        self._manual_until = self._manual_reset_at(now, minutes)
        self._reason = reason or "manual_override"
        manual = self._status.setdefault("manual", {})
        manual["active"] = True
        manual["until"] = self._manual_until.isoformat() if self._manual_until else None
        manual["ts"] = _ts_now()
        self.persist_status()
        if not was_active:
            self._logbook_entry("Manual override activated")
        self._schedule_manual_expiry()
        self._refresh_next_events(now)
        self._publish_state()

    def _manual_reset_at(
        self, now: datetime, minutes: int | None = None
    ) -> datetime | None:
        duration = (
            minutes
            if minutes is not None
            else self.config.get(
                CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES
            )
        )
        try:
            minutes_value = int(duration)
        except (TypeError, ValueError):
            minutes_value = DEFAULT_MANUAL_OVERRIDE_MINUTES
        return now + timedelta(minutes=minutes_value) if minutes_value > 0 else None

    def _manual_blocks_action(self, _action: str) -> bool:
        return self._manual_active

    def set_manual_override(self, minutes: int) -> None:
        self._activate_manual_override(minutes=minutes, reason="manual_override")

    def clear_manual_override(self) -> None:
        was_active = self._manual_active
        self._manual_until = None
        self._manual_active = False
        self._clear_manual_expiry()
        if self._reason in {"manual_override", "manual_shading"}:
            self._reason = None
        manual = self._status.setdefault("manual", {})
        manual["active"] = False
        manual["until"] = None
        self.persist_status()
        if was_active:
            self._logbook_entry("Manual override cleared")
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

    def publish_state(self) -> None:
        """Expose the current state via dispatcher for newly added entities."""
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
            min(
                point
                for point in (self._next_close, getattr(self, "_next_final_close", None))
                if point is not None
            )
            if self._next_close is not None
            or getattr(self, "_next_final_close", None) is not None
            else None,
            current_position,
            shading_enabled,
            shading_active,
            ventilation_active,
        )

    def active_decision_controls(self) -> frozenset[str]:
        """Return controls involved in the latest evaluation decision."""

        return frozenset(getattr(self, "_decision_controls", set()))

    @callback
    def _reschedule_next_event_timers(self, now: datetime) -> None:
        """Keep one point-in-time callback for each calculated schedule event."""

        hub = getattr(self, "hub", None)
        room_id = getattr(self, "room_id", None)
        if (
            hub is not None
            and room_id is not None
            and hub.room_uses_shared_time_timer(room_id)
        ):
            self._clear_scheduled_event_timers()
            self._reschedule_final_close_timer(now)
            return

        self._scheduled_open_unsub, self._scheduled_open_at = (
            self._reschedule_event_timer(
                self._scheduled_open_unsub,
                self._scheduled_open_at,
                self._next_open,
                now,
                "open",
            )
        )
        self._scheduled_close_unsub, self._scheduled_close_at = (
            self._reschedule_event_timer(
                self._scheduled_close_unsub,
                self._scheduled_close_at,
                self._next_close,
                now,
                "close",
            )
        )
        self._reschedule_final_close_timer(now)

    def _reschedule_final_close_timer(self, now: datetime) -> None:
        self._scheduled_final_close_unsub, self._scheduled_final_close_at = (
            self._reschedule_event_timer(
                getattr(self, "_scheduled_final_close_unsub", None),
                getattr(self, "_scheduled_final_close_at", None),
                getattr(self, "_next_final_close", None),
                now,
                "final_close",
            )
        )

    def _reschedule_event_timer(
        self,
        unsubscribe,
        scheduled_at: datetime | None,
        next_event: datetime | None,
        now: datetime,
        kind: str,
    ):
        if scheduled_at == next_event and unsubscribe is not None:
            return unsubscribe, scheduled_at
        if unsubscribe is not None:
            unsubscribe()
        if next_event is None or next_event <= now:
            return None, None

        @callback
        def _handle_scheduled_event(_now: datetime) -> None:
            if kind == "open":
                self._scheduled_open_unsub = None
                self._scheduled_open_at = None
            elif kind == "final_close":
                self._scheduled_final_close_unsub = None
                self._scheduled_final_close_at = None
            else:
                self._scheduled_close_unsub = None
                self._scheduled_close_at = None
            trigger = scheduled_trigger(kind, self._control_mode(kind))
            if kind == "final_close":
                trigger = getattr(
                    self, "_next_final_close_trigger", TRIGGER_SCHEDULED_FINAL_CLOSE
                )
            self.async_request_evaluate(trigger)

        return (
            async_track_point_in_time(self.hass, _handle_scheduled_event, next_event),
            next_event,
        )

    @callback
    def _clear_scheduled_event_timers(self) -> None:
        for attribute in (
            "_scheduled_open_unsub",
            "_scheduled_close_unsub",
            "_scheduled_final_close_unsub",
        ):
            unsubscribe = getattr(self, attribute, None)
            if unsubscribe is not None:
                unsubscribe()
                setattr(self, attribute, None)
        self._scheduled_open_at = None
        self._scheduled_close_at = None
        self._scheduled_final_close_at = None

    @callback
    def _schedule_shading_timer(self, kind: str, due_at: datetime) -> None:
        self._cancel_shading_timer(kind)

        @callback
        def _handle_shading_timer(_now: datetime) -> None:
            self._shading_timer_unsubs.pop(kind, None)
            self.async_request_evaluate(TRIGGER_SHADING_END_TIMER)

        self._shading_timer_unsubs[kind] = async_track_point_in_time(
            self.hass, _handle_shading_timer, due_at
        )

    @callback
    def _cancel_shading_timer(self, kind: str) -> None:
        unsubscribe = self._shading_timer_unsubs.pop(kind, None)
        if unsubscribe is not None:
            unsubscribe()

    @callback
    def _schedule_condition_timer(self, key: str, due_at: datetime) -> None:
        if key in self._condition_timer_unsubs:
            return

        @callback
        def _handle_condition_timer(_now: datetime) -> None:
            self._condition_timer_unsubs.pop(key, None)
            self.async_request_evaluate(CONDITION_TIMER_TRIGGERS[key])

        self._condition_timer_unsubs[key] = async_track_point_in_time(
            self.hass, _handle_condition_timer, due_at
        )

    @callback
    def _cancel_condition_timer(self, key: str) -> None:
        unsubscribe = self._condition_timer_unsubs.pop(key, None)
        if unsubscribe is not None:
            unsubscribe()

    @callback
    def _clear_runtime_condition_timers(self) -> None:
        for kind in tuple(self._shading_timer_unsubs):
            self._cancel_shading_timer(kind)
        self._shading_pending.clear()
        for key in tuple(self._condition_timer_unsubs):
            self._cancel_condition_timer(key)
        self._condition_since.clear()
        for trigger, unsubscribe in tuple(self._delayed_evaluation_unsubs.items()):
            unsubscribe()
            self._delayed_evaluation_unsubs.pop(trigger, None)
        for key, unsubscribe in tuple(self._calendar_timer_unsubs.items()):
            unsubscribe()
            self._calendar_timer_unsubs.pop(key, None)
        self._calendar_timer_times.clear()

    @callback
    def _reschedule_calendar_boundaries(
        self,
        open_window: tuple[datetime, datetime] | None,
        close_window: tuple[datetime, datetime] | None,
        now: datetime,
    ) -> None:
        desired = {
            key: due_at
            for key, due_at in (
                ("open_start", open_window[0] if open_window else None),
                ("open_end", open_window[1] if open_window else None),
                ("close_start", close_window[0] if close_window else None),
                ("close_end", close_window[1] if close_window else None),
            )
            if due_at is not None and due_at > now
        }
        for key in tuple(self._calendar_timer_unsubs):
            if self._calendar_timer_times.get(key) != desired.get(key):
                self._calendar_timer_unsubs.pop(key)()
                self._calendar_timer_times.pop(key, None)
        for key, due_at in desired.items():
            if key in self._calendar_timer_unsubs:
                continue

            @callback
            def _handle_calendar_boundary(_now: datetime, boundary: str = key) -> None:
                self._calendar_timer_unsubs.pop(boundary, None)
                self._calendar_timer_times.pop(boundary, None)
                self.async_request_evaluate(CALENDAR_BOUNDARY_TRIGGERS[boundary])

            self._calendar_timer_times[key] = due_at
            self._calendar_timer_unsubs[key] = async_track_point_in_time(
                self.hass, _handle_calendar_boundary, due_at
            )

    def activate_shading(self, minutes: int | None = None) -> None:
        self._activate_manual_override(minutes=minutes, reason="manual_shading")
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
            self._reason,
        )

        self._activate_manual_override(
            minutes=self.config.get(
                CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES
            ),
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
                self._reason,
            ) = manual_state
            self._refresh_next_events(dt_util.utcnow())
            self._publish_state()

    def _expire_manual_override(self, now: datetime) -> None:
        if self._manual_until and now >= self._manual_until:
            self._manual_until = None
            self._manual_active = False
            self._clear_manual_expiry()
            if self._reason in {"manual_override", "manual_shading"}:
                self._reason = None
            manual = self._status.setdefault("manual", {})
            manual["active"] = False
            manual["until"] = None
            self.persist_status()
            self._logbook_entry("Manual override ended")

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
        self._manual_expire_unsub = None
        if self._reason in {"manual_override", "manual_shading"}:
            self._reason = None
        manual = self._status.setdefault("manual", {})
        manual["active"] = False
        manual["until"] = None
        self.persist_status()
        self._logbook_entry("Manual override ended")
        now = dt_util.utcnow()
        self._refresh_next_events(now)
        self._publish_state()
        self.async_request_evaluate("manual_expired")
