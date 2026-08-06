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

from ..const import (
    BRIGHTNESS_SUN_OPERATOR_AND,
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
    CONF_BRIGHTNESS_SUN_OPERATOR,
    CONF_BRIGHTNESS_TIME_DURATION,
    CONF_CLOSE_POSITION,
    CONF_COVER_TYPE,
    CONF_COVER_TYPE_AWNING,
    CONF_LOCKOUT_POSITION,
    CONF_LOCKOUT_TILT_CLOSE,
    CONF_LOCKOUT_TILT_SHADING_END,
    CONF_LOCKOUT_TILT_SHADING_START,
    CONF_OPEN_POSITION,
    CONF_OPEN_TILT_POSITION,
    CONF_PREVENT_CLOSING_MULTIPLE_TIMES,
    CONF_PREVENT_HIGHER_POSITION_CLOSING,
    CONF_PREVENT_LOWERING_WHEN_CLOSING_IF_SHADED,
    CONF_PREVENT_OPENING_AFTER_SHADING_END,
    CONF_PREVENT_OPENING_AFTER_VENTILATION_END,
    CONF_PREVENT_OPENING_MULTIPLE_TIMES,
    CONF_PREVENT_SHADING_END_IF_CLOSED,
    CONF_PREVENT_SHADING_MULTIPLE_TIMES,
    CONF_RESIDENT_ALLOW_OPEN,
    CONF_RESIDENT_ALLOW_SHADING,
    CONF_RESIDENT_ALLOW_VENTILATION,
    CONF_RESIDENT_CLOSE_ENABLED,
    CONF_RESIDENT_OPEN_ENABLED,
    CONF_RESIDENT_STATUS,
    CONF_SHADING_END_IMMEDIATE_BY_SUN_POSITION,
    CONF_SHADING_END_MAX_DURATION,
    CONF_SHADING_OVER_VENTILATION,
    CONF_SHADING_START_MAX_DURATION,
    CONF_SHADING_WAITINGTIME_END,
    CONF_SHADING_WAITINGTIME_START,
    CONF_SUN_AZIMUTH_END,
    CONF_SUN_AZIMUTH_START,
    CONF_SUN_ELEVATION_CLOSE,
    CONF_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR,
    CONF_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR,
    CONF_SUN_ELEVATION_MAX,
    CONF_SUN_ELEVATION_MIN,
    CONF_SUN_ELEVATION_MODE,
    CONF_SUN_ELEVATION_OPEN,
    CONF_SUN_TIME_DURATION,
    CONF_VENTILATE_POSITION,
    CONF_VENTILATION_ALLOW_HIGHER_POSITION,
    CONF_VENTILATION_KEEP_OPEN_ON_FULL_TO_TILT,
    CONF_VENTILATION_USE_AFTER_SHADING,
    DEFAULT_AUTOMATION_FLAGS,
    DEFAULT_BEHAVIOR_SETTINGS,
    DEFAULT_BRIGHTNESS_CLOSE,
    DEFAULT_BRIGHTNESS_HYSTERESIS,
    DEFAULT_BRIGHTNESS_OPEN,
    DEFAULT_BRIGHTNESS_SUN_OPERATOR,
    DEFAULT_BRIGHTNESS_TIME_DURATION,
    DEFAULT_CLOSE_POSITION,
    DEFAULT_OPEN_POSITION,
    DEFAULT_OPEN_TILT_POSITION,
    DEFAULT_SHADING_TIMING_SETTINGS,
    DEFAULT_SUN_ELEVATION_CLOSE,
    DEFAULT_SUN_ELEVATION_MODE,
    DEFAULT_SUN_ELEVATION_OPEN,
    DEFAULT_SUN_TIME_DURATION,
    DEFAULT_VENTILATE_POSITION,
)
from .common import (
    _LOGGER,
    _coerce_float,
    _float_state,
)


class EvaluationMixin:
    async def _evaluate(self, trigger: str) -> None:
        now = dt_util.utcnow()
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
                "manual_active": self._manual_active,
                "manual_scope_all": self._manual_scope_all,
                "next_open": self._next_open,
                "next_close": self._next_close,
                "master_enabled": self._master_enabled(),
                "cover_available": cover_available,
            },
        )
        if not cover_available:
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

        unavailable_dependencies = self._unavailable_decision_entities()
        if unavailable_dependencies:
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
        if self._unavailable_dependencies:
            _LOGGER.info(
                "Cover Control dependencies available again for %s: %s",
                self.cover,
                ", ".join(sorted(self._unavailable_dependencies)),
            )
            self._unavailable_dependencies = set()

        brightness = _float_state(self.hass, self.config.get(CONF_BRIGHTNESS_SENSOR))
        sun_state = self.hass.states.get("sun.sun")
        sun_elevation = _coerce_float(
            sun_state and sun_state.attributes.get("elevation")
        )
        sun_azimuth = _coerce_float(sun_state and sun_state.attributes.get("azimuth"))

        global_condition = await self._condition_allows(
            CONF_ADDITIONAL_CONDITION_GLOBAL
        )
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
            self.config.get(
                CONF_RESIDENT_STATUS,
                DEFAULT_AUTOMATION_FLAGS.get(CONF_RESIDENT_STATUS, False),
            )
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

        resident_blocks_open = resident_sleeping and not resident_allow_open
        resident_blocks_ventilation = (
            resident_sleeping and not resident_allow_ventilation
        )
        resident_blocks_shading = resident_sleeping and not resident_allow_shading

        auto_ventilate = (not self._is_awning()) and self._auto_enabled(
            CONF_AUTO_VENTILATE
        )
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
        calendar_open_window, calendar_close_window = (
            await self._calendar_windows(now) if auto_time_enabled else (None, None)
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
        is_shading_allowed_window = (
            (not auto_time_enabled)
            or self._within_shading_window(now)
            or (
                calendar_open_window is not None
                and calendar_close_window is not None
                and calendar_open_window[0] <= now <= calendar_close_window[1]
            )
        )
        has_environment_control = self._auto_enabled(
            CONF_AUTO_BRIGHTNESS
        ) or self._auto_enabled(CONF_AUTO_SUN)

        environment_allows_opening = self._environment_allows_opening(
            sun_elevation, brightness
        )
        environment_allows_closing = self._environment_allows_closing(
            sun_elevation, brightness
        )

        if auto_ventilate and full_contact_active:
            if (
                ventilation_condition
                and not resident_blocks_ventilation
                and not self._manual_blocks_action("ventilation")
            ):
                self._remember_pre_ventilation_position()
                open_position = self._position_value(
                    CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION
                )
                await self._set_position(
                    self._position_value(CONF_LOCKOUT_POSITION, open_position),
                    "ventilation_full",
                )
            else:
                self._reason = "ventilation_full"
                self._set_ventilation_status(False, True)
                self.persist_status()
                self._publish_state()
            return

        current_position = self._current_position()

        shading_over_ventilation_active = False
        if (
            auto_ventilate
            and tilt_contact_active
            and self._config_bool(CONF_SHADING_OVER_VENTILATION)
            and self._auto_enabled(CONF_AUTO_SHADING)
            and not self._manual_blocks_action("shading")
            and not resident_blocks_shading
            and not tilt_lock_shading_start
        ):
            await self._async_update_shading_forecast()
            shading_conditions_met, shading_temp_independent = (
                self._shading_start_conditions(sun_azimuth, sun_elevation, brightness)
            )
            shading_over_ventilation_active = (
                (shading_conditions_met or shading_temp_independent)
                and shading_condition
                and shading_tilt_condition
                and is_shading_allowed_window
            )

        if (
            auto_ventilate
            and tilt_contact_active
            and ventilation_condition
            and not resident_blocks_ventilation
            and not shading_over_ventilation_active
        ):
            if not self._manual_blocks_action("ventilation"):
                keep_open = bool(
                    self.config.get(CONF_VENTILATION_KEEP_OPEN_ON_FULL_TO_TILT, False)
                ) and self._reason in {"ventilation_full"}
                if keep_open:
                    self._reason = "ventilation_full"
                    self._set_ventilation_status(False, True)
                    self.persist_status()
                    self._publish_state()
                else:
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
            if self._manual_blocks_action("close") or tilt_lock_close:
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

        if post_ventilation and not ventilation_end_condition:
            self._refresh_next_events(now)
            self._publish_state()
            return

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
            await self._async_update_shading_forecast()
            shading_conditions_met, shading_temp_independent = (
                self._shading_start_conditions(sun_azimuth, sun_elevation, brightness)
            )
            shading_end_conditions_met = self._shading_end_conditions(
                sun_azimuth, sun_elevation, brightness
            )
            shading_allowed = (
                (shading_conditions_met or shading_temp_independent)
                and shading_condition
                and is_shading_allowed_window
            )
            if tilt_contact_active:
                shading_allowed = shading_allowed and shading_tilt_condition
            if tilt_lock_shading_start and not shading_active:
                shading_allowed = False
            if shading_allowed:
                if self._shading_pending_active("end"):
                    self._clear_shading_pending("end")
            elif self._shading_pending_active("start") and self._shading_pending_due(
                "start", now
            ):
                max_duration = self._duration_value(
                    CONF_SHADING_START_MAX_DURATION,
                    DEFAULT_SHADING_TIMING_SETTINGS[CONF_SHADING_START_MAX_DURATION],
                )
                if max_duration <= 0:
                    self._clear_shading_pending("start")
                else:
                    pending_ts = (
                        _coerce_float(self._shading_status().get("start_pending")) or 0
                    )
                    waiting = self._duration_value(
                        CONF_SHADING_WAITINGTIME_START,
                        DEFAULT_SHADING_TIMING_SETTINGS[CONF_SHADING_WAITINGTIME_START],
                    )
                    started_ts = max(0, pending_ts - waiting)
                    if started_ts and now.timestamp() - started_ts > max_duration:
                        self._clear_shading_pending("start")
            if shading_active and shading_allowed:
                shading_target = self._effective_shading_position()
                if not self._position_matches(shading_target, current_position):
                    await self._set_position(shading_target, "shading")
                    return
                shading_end_conditions_met = False
            shading_end_warranted = (
                shading_end_conditions_met and is_shading_allowed_window
            )
            if (
                shading_active
                and not shading_end_warranted
                and self._shading_pending_active("end")
            ):
                self._clear_shading_pending("end")
            if shading_active and shading_end_warranted:
                if not shading_end_condition:
                    self._publish_state()
                    return
                if self._config_bool(
                    CONF_PREVENT_SHADING_END_IF_CLOSED
                ) and self._position_matches(
                    self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION),
                    current_position,
                ):
                    self._publish_state()
                    return
                waiting_end = self._duration_value(
                    CONF_SHADING_WAITINGTIME_END,
                    DEFAULT_SHADING_TIMING_SETTINGS[CONF_SHADING_WAITINGTIME_END],
                )
                max_end_duration = self._duration_value(
                    CONF_SHADING_END_MAX_DURATION,
                    DEFAULT_SHADING_TIMING_SETTINGS[CONF_SHADING_END_MAX_DURATION],
                )
                if self._shading_pending_active("end") and max_end_duration > 0:
                    pending_ts = (
                        _coerce_float(self._shading_status().get("end_pending")) or 0
                    )
                    started_ts = max(0, pending_ts - waiting_end)
                    if started_ts and now.timestamp() - started_ts > max_end_duration:
                        self._clear_shading_pending("end")
                        if self._reason in {"shading", "manual_shading"}:
                            self._reason = None
                        self._set_status_bucket("shading", False)
                        self.persist_status()
                        self._publish_state()
                        return
                if bool(
                    self.config.get(CONF_SHADING_END_IMMEDIATE_BY_SUN_POSITION, False)
                ):
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
                        waiting_end = 20
                if waiting_end > 0 and not self._shading_pending_due("end", now):
                    if not self._shading_pending_active("end"):
                        self._set_shading_pending(
                            "end", now + timedelta(seconds=waiting_end), True
                        )
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
                        or (tilt_contact_active and tilt_lock_shading_end)
                    )
                ):
                    if self._reason in {"shading", "manual_shading"}:
                        self._reason = None
                    self._set_status_bucket("shading", False)
                    self._clear_shading_pending(persist=False)
                    self.persist_status()
                    self._publish_state()
                    return
                if (
                    auto_ventilate
                    and ventilation_condition
                    and tilt_contact_active
                    and not full_contact_active
                    and (
                        tilt_lock_shading_end
                        or self.config.get(CONF_VENTILATION_USE_AFTER_SHADING)
                    )
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
                if not self._config_bool(CONF_PREVENT_OPENING_AFTER_SHADING_END):
                    await self._set_position(
                        self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION),
                        "shading_end_open",
                    )
                    return
                if self._config_bool(CONF_PREVENT_OPENING_AFTER_SHADING_END):
                    open_tilt = self._position_value(
                        CONF_OPEN_TILT_POSITION, DEFAULT_OPEN_TILT_POSITION
                    )
                    if open_tilt is not None:
                        await self._command_tilt_position(
                            float(open_tilt), reason="shading_end_tilt"
                        )
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
                shading_target = self._effective_shading_position()
                if (
                    current_position is None
                    or self._position_is_above(current_position, shading_target)
                    or self._position_matches(shading_target, current_position)
                    or self._status_active("open")
                ):
                    await self._set_position(shading_target, "shading")
                else:
                    self._reason = "shading"
                    self._set_status_bucket("shading", True)
                    self.persist_status()
                    self._publish_state()
                return

        close_events: list[tuple[datetime, str, float | None]] = []
        open_events: list[tuple[datetime, str, float | None]] = []

        if post_ventilation and ventilation_end_condition:
            restore_position = self._pre_ventilation_position
            target, reason = self._background_return_target(
                self._background_for("ventilation"),
                fallback=restore_position,
                allow_open=not self._config_bool(
                    CONF_PREVENT_OPENING_AFTER_VENTILATION_END
                ),
                allow_shading=not resident_blocks_shading,
            )
            if not (
                self._config_bool(CONF_PREVENT_OPENING_AFTER_VENTILATION_END)
                and self._target_is_opening_move(target)
            ):
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

        close_target = self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION)
        open_target = self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION)
        close_status_satisfied = self._status_active(
            "close"
        ) and self._position_matches(close_target, current_position)
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
                    and ((not has_environment_control) or environment_allows_closing)
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
            and not shading_holds_cover
            and not open_status_satisfied
            and not self._action_already_done_today(
                "open", CONF_PREVENT_OPENING_MULTIPLE_TIMES
            )
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

    def _brightness_sun_operator_is_and(self) -> bool:
        return (
            str(
                self.config.get(
                    CONF_BRIGHTNESS_SUN_OPERATOR, DEFAULT_BRIGHTNESS_SUN_OPERATOR
                )
                or DEFAULT_BRIGHTNESS_SUN_OPERATOR
            ).lower()
            == BRIGHTNESS_SUN_OPERATOR_AND
        )

    def _environment_allows_opening(
        self, sun_elevation: float | None, brightness: float | None
    ) -> bool:
        use_brightness = self._auto_enabled(CONF_AUTO_BRIGHTNESS)
        use_sun = self._auto_enabled(CONF_AUTO_SUN)
        if not use_brightness and not use_sun:
            return True
        brightness_ok = not use_brightness or self._brightness_allows_open(brightness)
        sun_ok = not use_sun or self._sun_allows_open(sun_elevation)
        if use_brightness and use_sun and self._brightness_sun_operator_is_and():
            return brightness_ok and sun_ok
        return brightness_ok or sun_ok

    def _environment_allows_closing(
        self, sun_elevation: float | None, brightness: float | None
    ) -> bool:
        use_brightness = self._auto_enabled(CONF_AUTO_BRIGHTNESS)
        use_sun = self._auto_enabled(CONF_AUTO_SUN)
        if not use_brightness and not use_sun:
            return False
        brightness_ok = use_brightness and self._brightness_allows_close(brightness)
        sun_ok = use_sun and self._sun_allows_close(sun_elevation)
        if use_brightness and use_sun and self._brightness_sun_operator_is_and():
            return brightness_ok and sun_ok
        return brightness_ok or sun_ok

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
        return bool(self.config.get(key, DEFAULT_BEHAVIOR_SETTINGS.get(key, False)))

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
        close_position = self._position_value(
            CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION
        )
        shading_position = self._effective_shading_position()
        if self._config_bool(
            CONF_PREVENT_HIGHER_POSITION_CLOSING
        ) and self._position_is_below(current, close_position):
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
