"""Cover controller behavior split from the public controller facade."""

from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
)

from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.util import dt as dt_util

from ..config_resolver import normalize_final_close_elevation
from ..const import (
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_DOWN,
    CONF_AUTO_SHADING,
    CONF_AUTO_SUN,
    CONF_AUTO_TIME,
    CONF_AUTO_UP,
    CONF_AUTO_VENTILATE,
    CONF_BRIGHTNESS_CLOSE_BELOW,
    CONF_BRIGHTNESS_HYSTERESIS,
    CONF_BRIGHTNESS_OPEN_ABOVE,
    CONF_BRIGHTNESS_SENSOR,
    CONF_BRIGHTNESS_TIME_DURATION,
    CONF_CLOSE_POSITION,
    CONF_CLOSE_MODE,
    CONF_FINAL_CLOSE_TIME,
    CONF_FINAL_CLOSE_TIME_ENABLED,
    CONF_FINAL_CLOSE_ELEVATION_ENABLED,
    CONF_FINAL_CLOSE_ELEVATION,
    CONF_INTERMEDIATE_CLOSE_ENABLED,
    CONF_INTERMEDIATE_CLOSE_POSITION,
    CONF_COVER_TYPE,
    CONF_COVER_TYPE_AWNING,
    CONF_LOCKOUT_POSITION,
    CONF_OPEN_POSITION,
    CONF_OPEN_MODE,
    CONF_NO_GO_TIME_MINUTES,
    CONF_KEEP_SUN_PROTECTION,
    CONF_RESIDENT_ALLOW_OPEN,
    CONF_RESIDENT_ALLOW_SHADING,
    CONF_RESIDENT_ALLOW_VENTILATION,
    CONF_RESIDENT_CLOSE_ENABLED,
    CONF_RESIDENT_OPEN_ENABLED,
    CONF_RESIDENT_STATUS,
    CONF_SHADING_WAITINGTIME_END,
    CONF_SUN_ELEVATION_CLOSE,
    CONF_SUN_ELEVATION_OPEN,
    CONF_VENTILATE_POSITION,
    DEFAULT_AUTOMATION_FLAGS,
    DEFAULT_BEHAVIOR_SETTINGS,
    DEFAULT_BRIGHTNESS_CLOSE,
    DEFAULT_BRIGHTNESS_HYSTERESIS,
    DEFAULT_BRIGHTNESS_OPEN,
    DEFAULT_BRIGHTNESS_TIME_DURATION,
    DEFAULT_CLOSE_MODE,
    DEFAULT_CLOSE_POSITION,
    DEFAULT_FINAL_CLOSE_TIME,
    DEFAULT_INTERMEDIATE_CLOSE_POSITION,
    DEFAULT_OPEN_MODE,
    DEFAULT_OPEN_POSITION,
    DEFAULT_SHADING_TIMING_SETTINGS,
    DEFAULT_SUN_ELEVATION_CLOSE,
    DEFAULT_SUN_ELEVATION_OPEN,
    DEFAULT_VENTILATE_POSITION,
    MODE_BRIGHTNESS,
    MODE_ELEVATION,
    MODE_TIME,
)
from .common import (
    _LOGGER,
    _coerce_float,
    _parse_time,
    TRIGGER_RESIDENT_OFF,
    TRIGGER_GOLDEN_HOUR_CLOSE_REACHED,
    TRIGGER_GOLDEN_HOUR_OPEN_REACHED,
    TRIGGER_SCHEDULED_CLOSE,
    TRIGGER_SCHEDULED_FINAL_CLOSE,
    TRIGGER_SCHEDULED_FINAL_CLOSE_ELEVATION,
    TRIGGER_SCHEDULED_OPEN,
    TRIGGER_SUNRISE_REACHED,
    TRIGGER_SUNSET_REACHED,
)


class EvaluationMixin:
    def _elevation_final_close_due(
        self,
        now: datetime,
        sun_elevation: float | None,
        triggers: frozenset[str],
    ) -> bool:
        """Return whether falling sun requires the final close now."""

        if not (
            self.config.get(CONF_INTERMEDIATE_CLOSE_ENABLED, False)
            and self.config.get(CONF_FINAL_CLOSE_ELEVATION_ENABLED, False)
            and sun_elevation is not None
            and sun_elevation
            <= normalize_final_close_elevation(
                self.config.get(CONF_FINAL_CLOSE_ELEVATION)
            )
            and triggers
            & frozenset({"startup", "config_updated", "sun_elevation_changed"})
        ):
            return False
        return self._last_action_dates.get("final_close") != dt_util.as_local(
            now
        ).date() and self._sun_is_falling(now)

    def _seasonal_close_target(
        self, now: datetime, current_position: float | None, final_close_due: bool
    ) -> tuple[bool, float | None, bool]:
        """Return summer suppression, effective target, and intermediate state."""

        intermediate_close, intermediate_target = self._intermediate_close_target(
            now, current_position, final_close_due
        )
        christmas_target = self._christmas_close_position(now)
        uses_intermediate = intermediate_close and christmas_target is None
        target = (
            christmas_target
            if christmas_target is not None
            else intermediate_target
            if uses_intermediate
            else self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION)
        )
        return self._summer_close_suppressed(now), target, uses_intermediate

    def _opening_no_go_remaining(self, now: datetime) -> float:
        """Return seconds until a scheduled opening may follow a cover change."""

        minutes = max(0, int(self.config.get(CONF_NO_GO_TIME_MINUTES, 0) or 0))
        state = self.hass.states.get(self.cover)
        if minutes == 0 or state is None:
            return 0
        return max(
            0,
            (state.last_changed + timedelta(minutes=minutes) - now).total_seconds(),
        )

    def _intermediate_close_target(
        self, now: datetime, current_position: float | None, final_close_due: bool
    ) -> tuple[bool, float | None]:
        final_time = _parse_time(
            str(self.config.get(CONF_FINAL_CLOSE_TIME, DEFAULT_FINAL_CLOSE_TIME))
        )
        if not self.config.get(CONF_FINAL_CLOSE_TIME_ENABLED, True):
            final_time = None
        active = bool(
            self.config.get(CONF_INTERMEDIATE_CLOSE_ENABLED, False)
            and (final_time or self.config.get(CONF_FINAL_CLOSE_ELEVATION_ENABLED, False))
            and (
                final_time is None
                or dt_util.as_local(now).timetz().replace(tzinfo=None) < final_time
            )
            and not final_close_due
        )
        if not active:
            return False, None
        target = self._position_value(
            CONF_INTERMEDIATE_CLOSE_POSITION, DEFAULT_INTERMEDIATE_CLOSE_POSITION
        )
        if current_position is not None and not self._position_is_above(
            current_position, target
        ):
            return True, None
        return True, target

    async def _evaluate(
        self, trigger: str, triggers: frozenset[str] | None = None
    ) -> None:
        context = self._evaluation_context
        context_now = context.get("now") if context is not None else None
        now = context_now if isinstance(context_now, datetime) else dt_util.utcnow()
        self._current_evaluation_triggers = triggers or frozenset({trigger})
        self._decision_controls.clear()
        self._expire_manual_override(now)
        self._ensure_manual_expiry_timer(now)
        cover_state = self.hass.states.get(self.cover)
        cover_available = cover_state is not None and cover_state.state not in {
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        }
        self._fire_event(
            "evaluate",
            {
                "trigger": trigger,
                "triggers": sorted(self._current_evaluation_triggers),
                "manual_active": self._manual_active,
                "next_open": self._next_open,
                "next_close": self._next_close,
                "master_enabled": self._master_enabled(),
                "cover_available": cover_available,
            },
        )
        if not cover_available:
            self._cancel_window_down_sequence()
            if self._startup_complete:
                self._runtime_outage_active = True
                self._outage_dependencies.add(self.cover)
            self._unavailable_dependencies.add(self.cover)
            if not self._cover_unavailable_logged:
                _LOGGER.info(
                    "Cover Control waiting for %s to become available before evaluating",
                    self.cover,
                )
                self._cover_unavailable_logged = True
            self._refresh_next_events(now)
            self._publish_state()
            return
        if self._cover_unavailable_logged:
            _LOGGER.info("Cover Control resumed evaluation for %s", self.cover)
            self._cover_unavailable_logged = False
        if await self._evaluate_safety():
            self._refresh_next_events(now)
            return
        if self._manual_active:
            self._cancel_window_down_sequence()
            self._logbook_entry(
                "No movement · manual override active",
                dedupe_key="blocked:manual_override",
            )
            self._refresh_next_events(now)
            self._publish_state()
            return

        if not self._master_enabled():
            self._cancel_window_down_sequence()
            self._refresh_next_events(now)
            self._publish_state()
            return

        unavailable_dependencies = self._unavailable_decision_entities()
        if unavailable_dependencies:
            self._cancel_window_down_sequence()
            if self._startup_complete:
                self._runtime_outage_active = True
                self._outage_dependencies.update(unavailable_dependencies)
            if unavailable_dependencies != self._unavailable_dependencies:
                _LOGGER.info(
                    "Cover Control waiting for dependencies before evaluating %s: %s",
                    self.cover,
                    ", ".join(sorted(unavailable_dependencies)),
                )
            self._unavailable_dependencies = unavailable_dependencies
            self._refresh_next_events(now)
            self._publish_state()
            return
        recovered_from_outage = bool(self._unavailable_dependencies)
        if self._unavailable_dependencies:
            _LOGGER.info(
                "Cover Control dependencies available again for %s: %s",
                self.cover,
                ", ".join(sorted(self._unavailable_dependencies)),
            )
            self._unavailable_dependencies = set()

        is_initial_startup_completion = not self._startup_complete
        recovered_from_runtime_outage = (
            self._startup_complete
            and self._runtime_outage_active
            and recovered_from_outage
        )
        should_catch_up = self._recovery_should_catch_up(recovered_from_outage)
        if is_initial_startup_completion and not should_catch_up:
            self._startup_complete = True
            self._runtime_outage_active = False
            self._outage_dependencies.clear()
            self._refresh_next_events(now)
            self._publish_state()
            return
        if recovered_from_runtime_outage:
            self._runtime_outage_active = False
            self._outage_dependencies.clear()
        self._startup_complete = True

        brightness_state = self._state_for(self.config.get(CONF_BRIGHTNESS_SENSOR))
        brightness = _coerce_float(brightness_state.state if brightness_state else None)
        sun_state = self._state_for(self._sun_entity())
        sun_elevation = _coerce_float(
            sun_state and sun_state.attributes.get("elevation")
        )
        sun_azimuth = _coerce_float(sun_state and sun_state.attributes.get("azimuth"))

        resident_mode_enabled = bool(
            self.config.get(
                CONF_RESIDENT_STATUS,
                DEFAULT_AUTOMATION_FLAGS.get(CONF_RESIDENT_STATUS, False),
            )
        )
        resident_sleeping = resident_mode_enabled and self._is_resident_sleeping()
        resident_woke = trigger == TRIGGER_RESIDENT_OFF

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

        resident_blocks_open = resident_sleeping and not resident_allow_open
        resident_blocks_ventilation = (
            resident_sleeping and not resident_allow_ventilation
        )
        resident_blocks_shading = self._resident_blocks_shading(
            resident_sleeping, resident_allow_shading
        )

        auto_ventilate = (not self._is_awning()) and self._auto_enabled(
            CONF_AUTO_VENTILATE
        )
        full_contact_active = auto_ventilate and self._contacts_active(
            self._full_open_sensors(), now
        )
        tilt_contact_active = auto_ventilate and self._tilt_contact_active(now)
        ventilation_contact_active = full_contact_active or tilt_contact_active
        if await self._evaluate_window_down_sequence(trigger):
            self._refresh_next_events(now)
            return

        auto_time_enabled = True
        calendar_open_window, calendar_close_window = (
            await self._calendar_windows(now) if auto_time_enabled else (None, None)
        )
        self._reschedule_calendar_boundaries(
            calendar_open_window, calendar_close_window, now
        )
        calendar_open_active = self._calendar_window_active(calendar_open_window, now)
        calendar_close_active = self._calendar_window_active(calendar_close_window, now)
        calendar_daytime_phase = self._calendar_daytime_phase(
            calendar_open_window, calendar_close_window, now
        )
        is_opening_phase = self._within_opening_phase(now) or calendar_open_active
        is_daytime_phase = (
            (not auto_time_enabled)
            or self._within_daytime_phase(now)
            or calendar_daytime_phase
        )
        is_closing_phase = self._within_closing_phase(now) or calendar_close_active
        is_evening_phase = (
            (auto_time_enabled and self._within_evening_phase(now))
            or calendar_close_active
            or self._calendar_after_start(calendar_close_window, now)
        )
        is_time_up_late = self._is_time_up_late(now) or self._calendar_between(
            calendar_open_window, calendar_close_window, now
        )
        is_time_down_late = self._is_time_down_late(now) or self._calendar_after_end(
            calendar_close_window, now
        )
        open_mode = self._control_mode("open")
        close_mode = self._control_mode("close")
        for mode in {open_mode, close_mode}:
            if self._mode_enabled(mode):
                self._decision_controls.add(
                    "brightness" if mode == MODE_BRIGHTNESS else "time" if mode == MODE_TIME else "sun"
                )
        if auto_ventilate and ventilation_contact_active:
            self._decision_controls.add("ventilation")
        if resident_sleeping:
            self._decision_controls.add("resident")
        is_shading_allowed_window = (
            (not auto_time_enabled)
            or self._within_shading_window(now)
            or (
                calendar_open_window is not None
                and calendar_close_window is not None
                and calendar_open_window[0] <= now <= calendar_close_window[1]
            )
        )
        if (
            self._auto_enabled(CONF_AUTO_SHADING)
            and is_shading_allowed_window
        ):
            self._decision_controls.add("shading")
        has_environment_control = open_mode != MODE_TIME or close_mode != MODE_TIME

        environment_allows_opening = self._environment_allows_opening(
            sun_elevation, brightness
        )
        environment_allows_closing = self._environment_allows_closing(
            sun_elevation, brightness
        )

        current_position = self._current_position()
        final_close_due = bool(
            {TRIGGER_SCHEDULED_FINAL_CLOSE, TRIGGER_SCHEDULED_FINAL_CLOSE_ELEVATION}
            & self._current_evaluation_triggers
        ) and self._last_action_dates.get("final_close") != dt_util.as_local(now).date()
        if not final_close_due:
            final_close_due = self._elevation_final_close_due(
                now, sun_elevation, self._current_evaluation_triggers
            )
        summer_close_suppressed, close_target, uses_intermediate = (
            self._seasonal_close_target(now, current_position, final_close_due)
        )
        intermediate_target = close_target if uses_intermediate else None
        close_status_satisfied = self._status_active(
            "close"
        ) and self._position_matches(close_target, current_position)
        regular_close_event: tuple[datetime, str, float | None] | None = None
        if (
            not summer_close_suppressed
            and not self._manual_blocks_action("close")
            and not close_status_satisfied
            and (
                not uses_intermediate
                or intermediate_target is not None
            )
        ):
            close_due = (
                final_close_due
                or
                (not auto_time_enabled and environment_allows_closing)
                or is_time_down_late
                or (
                    (is_closing_phase or is_evening_phase)
                    and ((not has_environment_control) or environment_allows_closing)
                )
            )
            if final_close_due:
                regular_close_event = (now, "scheduled_final_close", close_target)
            elif (
                close_due
                and self._mode_enabled(close_mode)
                and environment_allows_closing
            ):
                reason = (
                    "scheduled_close"
                    if close_mode == MODE_TIME
                    else "brightness_close"
                    if close_mode == MODE_BRIGHTNESS
                    else "sun_close"
                )
                regular_close_event = (
                    now,
                    "scheduled_intermediate_close" if uses_intermediate else reason,
                    close_target,
                )

        if summer_close_suppressed:
            self._reason = "summer_period"
            self._decision_controls.add("time")

        if (
            auto_ventilate
            and full_contact_active
            and self._active_safety != "frost"
        ):
            has_tilt_sensor = bool(self._tilt_sensors())
            open_position = self._position_value(
                CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION
            )
            target = self._position_value(
                CONF_LOCKOUT_POSITION if has_tilt_sensor else CONF_VENTILATE_POSITION,
                open_position if has_tilt_sensor else DEFAULT_VENTILATE_POSITION,
            )
            reason = "ventilation_full" if has_tilt_sensor else "ventilation"
            if (
                not resident_blocks_ventilation
                and not self._manual_blocks_action("ventilation")
            ):
                self._remember_pre_ventilation_position()
                await self._set_position(
                    target,
                    reason,
                )
            else:
                self._reason = reason
                self._set_ventilation_status(not has_tilt_sensor, has_tilt_sensor)
                self.persist_status()
                self._publish_state()
            return

        if (
            auto_ventilate
            and tilt_contact_active
            and self._active_safety != "frost"
            and not resident_blocks_ventilation
        ):
            if not self._manual_blocks_action("ventilation"):
                self._remember_pre_ventilation_position()
                target = self._position_value(
                    CONF_VENTILATE_POSITION, DEFAULT_VENTILATE_POSITION
                )
                if current_position is None or not self._position_matches(
                    target, current_position
                ):
                    await self._set_position(target, "ventilation")
                else:
                    self._reason = "ventilation"
                    self._set_ventilation_status(True, False)
                    self.persist_status()
                    self._publish_state()
            return

        if resident_sleeping and resident_close_enabled:
            if self._manual_blocks_action("close"):
                self._refresh_next_events(now)
                self._publish_state()
                return
            close_target = self._position_value(
                CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION
            )
            if not self._position_matches(close_target, current_position):
                await self._set_position(close_target, "resident_asleep")
                return
            if not (
                resident_allow_open
                or resident_allow_shading
                or resident_allow_ventilation
            ):
                self._refresh_next_events(now)
                self._publish_state()
                return

        post_ventilation = (
            auto_ventilate
            and not ventilation_contact_active
            and (
                self._reason
                in {"ventilation", "ventilation_full", "shading_end_ventilation"}
                or self._ventilation_status_active()
            )
        )

        shading_holds_cover = self._auto_enabled(CONF_AUTO_SHADING) and (
            self._status_active("shading")
            or self._reason in {"shading", "manual_shading"}
        )

        if (
            self._auto_enabled(CONF_AUTO_SHADING)
            and not self._manual_blocks_action("shading")
            and not resident_blocks_shading
        ):
            shading_active = self._status_active("shading") or self._reason in {
                "shading",
                "manual_shading",
            }
            shading_conditions_met, _unused = (
                self._shading_start_conditions(sun_azimuth, sun_elevation, brightness)
            )
            shading_end_conditions_met = self._shading_end_conditions(
                sun_azimuth, sun_elevation, brightness
            )
            shading_allowed = (
                shading_conditions_met
                and is_shading_allowed_window
            )
            heat_active_now, _temperature = self._heat_protection_state()
            if (
                shading_active
                and not heat_active_now
                and self._reason == "heat_protection"
            ):
                self._set_heat_protection_status(False, True)
                self._reason = "shading"
                self.persist_status()
            if shading_allowed:
                if self._shading_pending_active("end"):
                    self._clear_shading_pending("end")
            if shading_active and shading_allowed:
                shading_target, reason, heat_hold = (
                    self._active_shading_target_reason(current_position)
                )
                heat_active = reason == "heat_protection"
                changed = self._set_heat_protection_status(heat_active, heat_hold)
                if shading_target is None:
                    self._reason = "shading"
                if changed:
                    self.persist_status()
                if shading_target is not None and not self._position_matches(
                    shading_target, current_position
                ):
                    await self._set_position(shading_target, reason)
                    return
                if self._reason != reason:
                    self._reason = reason
                    self.persist_status()
                    self._publish_state()
                shading_end_conditions_met = False
            shading_end_warranted = (
                shading_end_conditions_met and is_shading_allowed_window
            )
            shading_end_condition_valid = shading_end_warranted
            if shading_active and not shading_end_condition_valid:
                self._shading_end_wait_complete(now, False, 0)
            if shading_active and shading_end_warranted:
                waiting_end = self._duration_value(
                    CONF_SHADING_WAITINGTIME_END,
                    DEFAULT_SHADING_TIMING_SETTINGS[CONF_SHADING_WAITINGTIME_END],
                )
                if not self._shading_end_wait_complete(
                    now, shading_end_condition_valid, waiting_end
                ):
                    self._publish_state()
                    return
                if self._shading_pending_active("end"):
                    self._clear_shading_pending("end")
                ventilate_position = self._position_value(
                    CONF_VENTILATE_POSITION, DEFAULT_VENTILATE_POSITION
                )
                current_below_ventilate = self._position_is_below(
                    current_position, ventilate_position
                )
                if (
                    auto_ventilate
                    and current_below_ventilate
                    and (
                        full_contact_active
                        or tilt_contact_active
                    )
                ):
                    if self._reason in {
                        "shading",
                        "manual_shading",
                        "heat_protection",
                    }:
                        self._reason = None
                    self._set_status_bucket("shading", False)
                    self._set_heat_protection_status(False, False)
                    self._clear_shading_pending(persist=False)
                    self.persist_status()
                    self._logbook_entry("Sun shading ended")
                    self._publish_state()
                    return
                if (
                    auto_ventilate
                    and tilt_contact_active
                    and not full_contact_active
                    and not self._manual_blocks_action("ventilation")
                ):
                    self._remember_pre_ventilation_position()
                    await self._set_position(
                        self._position_value(
                            CONF_VENTILATE_POSITION, DEFAULT_VENTILATE_POSITION
                        ),
                        "shading_end_ventilation",
                    )
                    return
                shading_end_target = self._shading_end_open_target()
                if shading_end_target is not None:
                    await self._set_position(
                        shading_end_target,
                        "shading_end_open",
                    )
                    return
                if self._reason in {
                    "shading",
                    "manual_shading",
                    "heat_protection",
                }:
                    self._reason = None
                self._set_status_bucket("shading", False)
                self._set_heat_protection_status(False, False)
                self._clear_shading_pending("end", persist=False)
                self.persist_status()
                self._logbook_entry("Sun shading ended")
                self._publish_state()
                return
            if shading_allowed and not shading_active:
                heat_active, _temperature = self._heat_protection_state()
                shading_target, reason = self._shading_target_reason()
                self._set_heat_protection_status(heat_active, heat_active)
                if (
                    current_position is None
                    or self._position_is_above(current_position, shading_target)
                    or self._position_matches(shading_target, current_position)
                    or self._status_active("open")
                ):
                    await self._set_position(shading_target, reason)
                else:
                    self._reason = reason
                    self._set_status_bucket("shading", True)
                    self.persist_status()
                    self._publish_state()
                return

        close_events: list[tuple[datetime, str, float | None]] = []
        open_events: list[tuple[datetime, str, float | None]] = []

        if post_ventilation:
            restore_position = self._pre_ventilation_position
            target, reason = self._background_return_target(
                self._background_for("ventilation"),
                fallback=restore_position,
                allow_open=True,
                allow_shading=not resident_blocks_shading,
            )
            close_events.append(
                (
                    now + timedelta(seconds=1),
                    reason,
                    target,
                )
            )
            self._pre_ventilation_position = None
            self._set_ventilation_status(False, False)
            self.persist_status()

        open_target = self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION)
        open_status_satisfied = self._status_active("open") and self._position_matches(
            open_target, current_position
        )

        if regular_close_event is not None:
            close_events.append(regular_close_event)
        if (
            not resident_blocks_open
            and not self._manual_blocks_action("open")
            and not shading_holds_cover
            and not open_status_satisfied
        ):
            should_be_open_now = (
                is_daytime_phase
                and not is_evening_phase
                and ((not has_environment_control) or environment_allows_opening)
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
            if open_due and self._mode_enabled(open_mode) and environment_allows_opening:
                no_go_remaining = self._opening_no_go_remaining(now)
                if open_mode != MODE_TIME or no_go_remaining <= 0:
                    reason = (
                        "scheduled_open"
                        if open_mode == MODE_TIME
                        else "brightness_open"
                        if open_mode == MODE_BRIGHTNESS
                        else "sun_open"
                    )
                    open_events.append(
                        (
                            now,
                            reason,
                            open_target,
                        )
                    )
                else:
                    self._reason = "no_go_time"
                    self._decision_controls.add("no_go_time")

        def _pick_event(
            candidates: list[tuple[datetime, str, float | None]],
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
                if not self._manual_blocks_action("close"):
                    await self._set_position(position, reason)
                    return
            elif not self._manual_blocks_action("open"):
                await self._set_position(position, reason)
                return

        self._refresh_next_events(now)
        self._publish_state()

    def _recovery_should_catch_up(self, dependencies_recovered: bool) -> bool:
        """Decide recovery from runtime state, never from the trigger name."""

        if not self._startup_complete:
            return False
        return bool(
            dependencies_recovered
            and self._runtime_outage_active
        )

    def _sun_allows_open(self, sun_elevation: float | None) -> bool:
        if sun_elevation is None:
            return False
        threshold = self._number_value(
            CONF_SUN_ELEVATION_OPEN, DEFAULT_SUN_ELEVATION_OPEN
        )
        return sun_elevation >= threshold

    def _sun_allows_close(self, sun_elevation: float | None) -> bool:
        if sun_elevation is None:
            return False
        threshold = self._number_value(
            CONF_SUN_ELEVATION_CLOSE, DEFAULT_SUN_ELEVATION_CLOSE
        )
        return sun_elevation <= threshold

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
        passed = brightness <= threshold - hysteresis
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
        mode = self._control_mode("open")
        if mode == MODE_TIME:
            return True
        if self._is_time_up_late(dt_util.utcnow()):
            return True
        if mode == MODE_BRIGHTNESS:
            return self._brightness_allows_open(brightness)
        if mode == MODE_ELEVATION:
            return self._sun_allows_open(sun_elevation)
        return self._scheduled_mode_reached("open")

    def _environment_allows_closing(
        self, sun_elevation: float | None, brightness: float | None
    ) -> bool:
        mode = self._control_mode("close")
        if mode == MODE_TIME:
            return True
        if self._is_time_down_late(dt_util.utcnow()):
            return True
        if mode == MODE_BRIGHTNESS:
            return self._brightness_allows_close(brightness)
        if mode == MODE_ELEVATION:
            return self._sun_allows_close(sun_elevation)
        return self._scheduled_mode_reached("close")

    def _scheduled_mode_reached(self, kind: str) -> bool:
        triggers = (
            {
                TRIGGER_SCHEDULED_OPEN,
                TRIGGER_SUNRISE_REACHED,
                TRIGGER_GOLDEN_HOUR_OPEN_REACHED,
            }
            if kind == "open"
            else {
                TRIGGER_SCHEDULED_CLOSE,
                TRIGGER_SUNSET_REACHED,
                TRIGGER_GOLDEN_HOUR_CLOSE_REACHED,
            }
        )
        if triggers & self._current_evaluation_triggers:
            return True
        now = dt_util.utcnow()
        if kind == "open" and self._is_time_up_late(now):
            return True
        if kind == "close" and self._is_time_down_late(now):
            return True
        local_now = dt_util.as_local(now)
        day_start = datetime.combine(
            local_now.date(), datetime.min.time(), local_now.tzinfo
        )
        event = self._next_astro_event(
            kind,
            self._control_mode(kind),
            dt_util.as_utc(day_start) - timedelta(seconds=1),
        )
        return bool(event and event <= now)

    def _number_value(self, key: str, default: float) -> float:
        value = _coerce_float(self.config.get(key, default))
        return default if value is None else value

    @staticmethod
    def _resident_blocks_shading(sleeping: bool, allow_shading: bool) -> bool:
        return sleeping and not allow_shading

    def _duration_value(self, key: str, default: int) -> int:
        value = _coerce_float(self.config.get(key, default))
        if value is None:
            return default
        return max(0, int(value))

    def _condition_held(self, key: str, passed: bool, seconds: int) -> bool:
        if not passed:
            self._condition_since.pop(key, None)
            self._cancel_condition_timer(key)
            return False
        if seconds <= 0:
            self._condition_since.pop(key, None)
            self._cancel_condition_timer(key)
            return True
        context = getattr(self, "_evaluation_context", None)
        context_now = context.get("now") if context is not None else None
        now = context_now if isinstance(context_now, datetime) else dt_util.utcnow()
        start = self._condition_since.get(key)
        if start is None:
            start = now
            self._condition_since[key] = start
            self._schedule_condition_timer(key, start + timedelta(seconds=seconds))
        return now - start >= timedelta(seconds=seconds)

    def _config_bool(self, key: str) -> bool:
        return bool(self.config.get(key, DEFAULT_BEHAVIOR_SETTINGS.get(key, False)))

    def _shading_end_open_target(self) -> float | None:
        """Return no target when shuttercontrol KeepSunProtect is active."""

        if self._config_bool(CONF_KEEP_SUN_PROTECTION):
            return None
        return self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION)

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

    def _action_done_today(self, action: str) -> bool:
        return self._last_action_dates.get(action) == dt_util.as_local(
            dt_util.utcnow()
        ).date()
