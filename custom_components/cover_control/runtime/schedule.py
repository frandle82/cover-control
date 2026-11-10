"""Cover controller behavior split from the public controller facade."""

from __future__ import annotations

from datetime import (
    datetime,
    time,
    timedelta,
)

from astral import LocationInfo
from astral.sun import SunDirection, golden_hour, sunrise, sunset, time_at_elevation
from homeassistant.const import (
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.util import dt as dt_util

from ..const import (
    CONF_AUTO_DOWN,
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_SUN,
    CONF_AUTO_TIME,
    CONF_AUTO_UP,
    CONF_AUTO_VENTILATE,
    CONF_CALENDAR_CLOSE_TITLE,
    CONF_CALENDAR_ENTITY,
    CONF_CALENDAR_OPEN_TITLE,
    CONF_CONTACT_STATUS_DELAY,
    CONF_CONTACT_TRIGGER_DELAY,
    CONF_CLOSE_POSITION,
    CONF_CHRISTMAS_END,
    CONF_CHRISTMAS_POSITION,
    CONF_CHRISTMAS_POSITION_ENABLED,
    CONF_CHRISTMAS_START,
    CONF_ASTRO_CLOSE_OFFSET,
    CONF_ASTRO_OPEN_OFFSET,
    CONF_CLOSE_MODE,
    CONF_FINAL_CLOSE_TIME,
    CONF_FINAL_CLOSE_TIME_ENABLED,
    CONF_FINAL_CLOSE_ELEVATION_ENABLED,
    CONF_FINAL_CLOSE_ELEVATION,
    CONF_INTERMEDIATE_CLOSE_ENABLED,
    CONF_OPEN_POSITION,
    CONF_OPEN_MODE,
    CONF_RESIDENT_SENSOR,
    CONF_SUMMER_END,
    CONF_SUMMER_SKIP_CLOSE_ENABLED,
    CONF_SUMMER_START,
    CONF_SUN_ELEVATION_CLOSE,
    CONF_SUN_ELEVATION_OPEN,
    CONF_TIME_DOWN_EARLY_NON_WORKDAY,
    CONF_TIME_DOWN_EARLY_WORKDAY,
    CONF_TIME_DOWN_LATE_NON_WORKDAY,
    CONF_TIME_DOWN_LATE_WORKDAY,
    CONF_TIME_UP_EARLY_NON_WORKDAY,
    CONF_TIME_UP_EARLY_WORKDAY,
    CONF_TIME_UP_LATE_NON_WORKDAY,
    CONF_TIME_UP_LATE_WORKDAY,
    CONF_VENTILATION_DELAY_AFTER_CLOSE,
    CONF_WORKDAY_SENSOR,
    CONF_WORKDAY_TOMORROW_SENSOR,
    DEFAULT_ASTRO_CLOSE_OFFSET,
    DEFAULT_ASTRO_OPEN_OFFSET,
    DEFAULT_CLOSE_MODE,
    DEFAULT_CONTACT_SETTINGS,
    DEFAULT_CLOSE_POSITION,
    DEFAULT_CHRISTMAS_END,
    DEFAULT_CHRISTMAS_POSITION,
    DEFAULT_CHRISTMAS_START,
    DEFAULT_FINAL_CLOSE_TIME,
    DEFAULT_FINAL_CLOSE_TIME_ENABLED,
    DEFAULT_FINAL_CLOSE_ELEVATION_ENABLED,
    DEFAULT_FINAL_CLOSE_ELEVATION,
    DEFAULT_OPEN_MODE,
    DEFAULT_OPEN_POSITION,
    DEFAULT_SUN_ELEVATION_CLOSE,
    DEFAULT_SUN_ELEVATION_OPEN,
    DEFAULT_SUMMER_END,
    DEFAULT_SUMMER_START,
    DEFAULT_TIME_SETTINGS,
    MODE_BRIGHTNESS,
    MODE_ELEVATION,
    MODE_GOLDEN_HOUR,
    MODE_SUNRISE,
    MODE_SUNSET,
    MODE_TIME,
)
from .common import (
    _LOGGER,
    _coerce_float,
    _parse_time,
)


class ScheduleMixin:
    @staticmethod
    def _is_date_in_recurring_range(
        now: datetime, start_value: object, end_value: object
    ) -> bool:
        """Return whether local month/day is inside an inclusive annual range."""

        def _month_day(value: object) -> tuple[int, int] | None:
            parts = str(value or "").strip().split(".")
            if len(parts) < 2:
                return None
            try:
                day, month = int(parts[0]), int(parts[1])
                datetime(2000, month, day)
            except (TypeError, ValueError):
                return None
            return month, day

        start = _month_day(start_value)
        end = _month_day(end_value)
        if start is None or end is None:
            return False
        current = (dt_util.as_local(now).month, dt_util.as_local(now).day)
        return (
            start <= current <= end
            if start <= end
            else current >= start or current <= end
        )

    def _summer_close_suppressed(self, now: datetime) -> bool:
        return bool(self.config.get(CONF_SUMMER_SKIP_CLOSE_ENABLED, False)) and (
            self._is_date_in_recurring_range(
                now,
                self.config.get(CONF_SUMMER_START, DEFAULT_SUMMER_START),
                self.config.get(CONF_SUMMER_END, DEFAULT_SUMMER_END),
            )
        )

    def _christmas_close_position(self, now: datetime) -> float | None:
        if not self.config.get(CONF_CHRISTMAS_POSITION_ENABLED, False):
            return None
        if not self._is_date_in_recurring_range(
            now,
            self.config.get(CONF_CHRISTMAS_START, DEFAULT_CHRISTMAS_START),
            self.config.get(CONF_CHRISTMAS_END, DEFAULT_CHRISTMAS_END),
        ):
            return None
        return self._position_value(
            CONF_CHRISTMAS_POSITION, DEFAULT_CHRISTMAS_POSITION
        )

    def _is_workday(self) -> bool:
        workday_entity = self.config.get(CONF_WORKDAY_SENSOR)
        if not workday_entity:
            return True
        state = self._state_for(workday_entity)
        return bool(state and state.state == STATE_ON)

    def _is_workday_tomorrow(self) -> bool:
        tomorrow_entity = self.config.get(CONF_WORKDAY_TOMORROW_SENSOR)
        if not tomorrow_entity:
            return self._is_workday()
        state = self._state_for(tomorrow_entity)
        return bool(state and state.state == STATE_ON)

    def _single_contact_active(self, entity_id: str, now: datetime) -> bool:
        state = self._state_for(entity_id)
        if state is None or state.state != STATE_ON:
            return False

        last_changed = getattr(state, "last_changed", None)
        if last_changed:
            last_changed = dt_util.as_utc(last_changed)
        else:
            last_changed = now

        required_seconds = self._contact_trigger_delay()
        if required_seconds and (now - last_changed) < timedelta(
            seconds=required_seconds
        ):
            return False
        return True

    def _contact_trigger_delay(self) -> int:
        return self._duration_value(
            CONF_CONTACT_TRIGGER_DELAY,
            int(DEFAULT_CONTACT_SETTINGS[CONF_CONTACT_TRIGGER_DELAY]),
        )

    def _contact_status_delay(self) -> int:
        return self._duration_value(
            CONF_CONTACT_STATUS_DELAY,
            int(DEFAULT_CONTACT_SETTINGS[CONF_CONTACT_STATUS_DELAY]),
        )

    def _contacts_active(self, entity_ids: list[str], now: datetime) -> bool:
        return any(
            self._single_contact_active(entity_id, now) for entity_id in entity_ids
        )

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
            state = self._state_for(sensor)
            if state is None:
                continue
            if state.state == STATE_ON:
                continue
            last_changed = getattr(state, "last_changed", None)
            last_changed = dt_util.as_utc(last_changed) if last_changed else now
            if (now - last_changed) < timedelta(seconds=delay_after_close):
                return True
        return False

    def _ventilation_requires_independent_control(self, now: datetime) -> bool:
        """Return whether this cover must stay outside coordinated room movement."""

        if self._is_awning() or not self._auto_enabled(CONF_AUTO_VENTILATE):
            return False
        if self._ventilation_status_active() or self._reason in {
            "ventilation",
            "ventilation_full",
            "shading_end_ventilation",
        }:
            return True
        if any(
            (state := self._state_for(entity_id)) is not None
            and state.state in {STATE_ON, "true", "1"}
            for entity_id in self._contact_entities()
        ):
            return True
        return self._contacts_active(
            self._full_open_sensors(), now
        ) or self._tilt_contact_active(now)

    def _is_resident_sleeping(self) -> bool:
        resident_entity = self.config.get(CONF_RESIDENT_SENSOR)
        if not resident_entity:
            return False
        state = self._state_for(resident_entity)
        return self._resident_state_is_on(state.state if state else None)

    @staticmethod
    def _resident_state_is_on(value: str | None) -> bool:
        return value in {STATE_ON, "true"}

    @staticmethod
    def _resident_state_is_off(value: str | None) -> bool:
        return value in {"off", "false"}

    def _time_from_config(self, key: str) -> time | None:
        configured = self.config.get(key)
        parsed = _parse_time(configured)
        if parsed:
            return parsed
        fallback = DEFAULT_TIME_SETTINGS.get(key)
        return _parse_time(fallback) if fallback is not None else None

    def _calendar_window_from_state(
        self, title_key: str, now: datetime
    ) -> tuple[datetime, datetime] | None:
        calendar_entity = self.config.get(CONF_CALENDAR_ENTITY)
        title = str(self.config.get(title_key) or "").strip().lower()
        if not calendar_entity or not title:
            return None

        state = self._state_for(calendar_entity)
        if state is None or state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
            return None

        message = str(state.attributes.get("message") or "").strip().lower()
        if title not in message:
            return None

        start_raw = state.attributes.get("start_time") or state.attributes.get("start")
        end_raw = state.attributes.get("end_time") or state.attributes.get("end")
        start_dt = dt_util.parse_datetime(str(start_raw)) if start_raw else None
        end_dt = dt_util.parse_datetime(str(end_raw)) if end_raw else None
        if not start_dt or not end_dt:
            return None
        start_dt = dt_util.as_utc(start_dt)
        end_dt = dt_util.as_utc(end_dt)
        if end_dt <= start_dt:
            return None
        return (start_dt, end_dt) if start_dt <= now < end_dt else None

    async def _calendar_windows(
        self, now: datetime
    ) -> tuple[tuple[datetime, datetime] | None, tuple[datetime, datetime] | None]:
        calendar_entity = self.config.get(CONF_CALENDAR_ENTITY)
        if not calendar_entity:
            return None, None

        state = self._state_for(calendar_entity)
        if state is None or state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
            return None, None

        local_now = dt_util.as_local(now)
        start = datetime.combine(
            local_now.date(), time.min, local_now.tzinfo
        ) - timedelta(hours=1)
        end = start + timedelta(days=2, hours=1)
        response = None
        try:
            response = await self.hass.services.async_call(
                "calendar",
                "get_events",
                {
                    "entity_id": calendar_entity,
                    "start_date_time": start.isoformat(),
                    "end_date_time": end.isoformat(),
                },
                blocking=True,
                return_response=True,
            )
        except Exception:
            _LOGGER.debug(
                "Calendar event lookup failed for %s", calendar_entity, exc_info=True
            )

        if isinstance(response, dict):
            events = response.get(calendar_entity, {}).get("events", [])
            open_window = self._calendar_window_from_events(
                events, CONF_CALENDAR_OPEN_TITLE, now
            )
            close_window = self._calendar_window_from_events(
                events, CONF_CALENDAR_CLOSE_TITLE, now
            )
            if open_window or close_window:
                return open_window, close_window

        return (
            self._calendar_window_from_state(CONF_CALENDAR_OPEN_TITLE, now),
            self._calendar_window_from_state(CONF_CALENDAR_CLOSE_TITLE, now),
        )

    def _calendar_window_from_events(
        self, events: object, title_key: str, now: datetime
    ) -> tuple[datetime, datetime] | None:
        title = str(self.config.get(title_key) or "").strip().lower()
        if not title or not isinstance(events, list):
            return None

        candidates: list[tuple[datetime, datetime]] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            summary = str(event.get("summary") or event.get("message") or "").lower()
            if title not in summary:
                continue
            start_dt = self._parse_calendar_event_datetime(event.get("start"))
            end_dt = self._parse_calendar_event_datetime(event.get("end"))
            if not start_dt or not end_dt or end_dt <= start_dt:
                continue
            if end_dt >= now:
                candidates.append((start_dt, end_dt))

        if not candidates:
            return None
        return sorted(candidates, key=lambda item: item[0])[0]

    def _parse_calendar_event_datetime(self, value: object) -> datetime | None:
        raw = value
        if isinstance(raw, dict):
            raw = raw.get("dateTime") or raw.get("date")
        if isinstance(raw, datetime):
            return dt_util.as_utc(raw)
        if not raw:
            return None
        parsed = dt_util.parse_datetime(str(raw))
        if parsed:
            return dt_util.as_utc(parsed)
        try:
            parsed_date = datetime.fromisoformat(str(raw)).date()
        except (TypeError, ValueError):
            parsed_date = None
        if parsed_date:
            local_start = datetime.combine(
                parsed_date, time.min, dt_util.get_default_time_zone()
            )
            return dt_util.as_utc(local_start)
        return None

    @staticmethod
    def _calendar_window_active(
        window: tuple[datetime, datetime] | None, now: datetime
    ) -> bool:
        return bool(window and window[0] <= now < window[1])

    @staticmethod
    def _calendar_after_start(
        window: tuple[datetime, datetime] | None, now: datetime
    ) -> bool:
        return bool(window and now >= window[0])

    @staticmethod
    def _calendar_after_end(
        window: tuple[datetime, datetime] | None, now: datetime
    ) -> bool:
        return bool(window and now >= window[1])

    @staticmethod
    def _calendar_between(
        open_window: tuple[datetime, datetime] | None,
        close_window: tuple[datetime, datetime] | None,
        now: datetime,
    ) -> bool:
        return bool(
            open_window and close_window and open_window[1] <= now < close_window[0]
        )

    @staticmethod
    def _calendar_daytime_phase(
        open_window: tuple[datetime, datetime] | None,
        close_window: tuple[datetime, datetime] | None,
        now: datetime,
    ) -> bool:
        return bool(
            open_window and close_window and open_window[0] <= now < close_window[0]
        )

    def _time_bounds(
        self, workday: bool, is_up: bool
    ) -> tuple[time | None, time | None]:
        if workday:
            early_key = (
                CONF_TIME_UP_EARLY_WORKDAY if is_up else CONF_TIME_DOWN_EARLY_WORKDAY
            )
            late_key = (
                CONF_TIME_UP_LATE_WORKDAY if is_up else CONF_TIME_DOWN_LATE_WORKDAY
            )
        else:
            early_key = (
                CONF_TIME_UP_EARLY_NON_WORKDAY
                if is_up
                else CONF_TIME_DOWN_EARLY_NON_WORKDAY
            )
            late_key = (
                CONF_TIME_UP_LATE_NON_WORKDAY
                if is_up
                else CONF_TIME_DOWN_LATE_NON_WORKDAY
            )

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

    def _today_at(self, now: datetime, point: time | None) -> datetime | None:
        if not point:
            return None
        local_now = dt_util.as_local(now)
        return datetime.combine(local_now.date(), point, local_now.tzinfo)

    def _within_opening_phase(self, now: datetime) -> bool:
        workday = self._is_workday()
        early, late = self._time_bounds(workday, True)
        return self._within_time_window(now, early, late)

    def _within_daytime_phase(self, now: datetime) -> bool:
        workday = self._is_workday()
        workday_tomorrow = self._is_workday_tomorrow()
        open_early, _open_late = self._time_bounds(workday, True)
        close_early, _close_late = self._time_bounds(workday_tomorrow, False)
        return self._within_time_window(now, open_early, close_early)

    def _within_closing_phase(self, now: datetime) -> bool:
        workday_tomorrow = self._is_workday_tomorrow()
        early, late = self._time_bounds(workday_tomorrow, False)
        return self._within_time_window(now, early, late)

    def _within_evening_phase(self, now: datetime) -> bool:
        workday_tomorrow = self._is_workday_tomorrow()
        early, _late = self._time_bounds(workday_tomorrow, False)
        start = self._today_at(now, early)
        return bool(start and dt_util.as_local(now) >= start)

    def _is_time_up_late(self, now: datetime) -> bool:
        workday = self._is_workday()
        workday_tomorrow = self._is_workday_tomorrow()
        _open_early, open_late = self._time_bounds(workday, True)
        close_early, _close_late = self._time_bounds(workday_tomorrow, False)
        local_now = dt_util.as_local(now)
        late_dt = self._today_at(now, open_late)
        close_early_dt = self._today_at(now, close_early)
        return bool(
            late_dt
            and close_early_dt
            and local_now >= late_dt
            and local_now < close_early_dt
        )

    def _is_time_down_late(self, now: datetime) -> bool:
        workday_tomorrow = self._is_workday_tomorrow()
        _early, late = self._time_bounds(workday_tomorrow, False)
        late_dt = self._today_at(now, late)
        return bool(late_dt and dt_util.as_local(now) >= late_dt)

    def _within_shading_window(self, now: datetime) -> bool:
        workday = self._is_workday()
        workday_tomorrow = self._is_workday_tomorrow()
        open_early, _open_late = self._time_bounds(workday, True)
        _close_early, close_late = self._time_bounds(workday_tomorrow, False)
        open_dt = self._today_at(now, open_early)
        close_dt = self._today_at(now, close_late)
        local_now = dt_util.as_local(now)
        return bool(open_dt and close_dt and open_dt <= local_now <= close_dt)

    def _refresh_next_events(self, now: datetime) -> None:
        workday = self._is_workday()
        workday_tomorrow = self._is_workday_tomorrow()
        up_early_time, up_late_time = self._time_bounds(workday, True)
        down_early_time, down_late_time = self._time_bounds(workday_tomorrow, False)

        next_up_early, next_up_late = self._window_points(
            up_early_time, up_late_time, now
        )
        next_down_early, next_down_late = self._window_points(
            down_early_time, down_late_time, now
        )
        action_dates = getattr(self, "_last_action_dates", {})
        today = dt_util.as_local(now).date()
        if action_dates.get("open") == today:
            tomorrow_workday = self._is_workday_tomorrow()
            up_early_time, up_late_time = self._time_bounds(tomorrow_workday, True)
            next_up_early, next_up_late = self._window_points_for_date(
                up_early_time, up_late_time, now, 1
            )
        if action_dates.get("close") == today:
            next_down_early, next_down_late = self._window_points_for_date(
                down_early_time, down_late_time, now, 1
            )

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

            future_fallbacks = sorted(
                point
                for point in fallback_candidates
                if point is not None and point >= now
            )
            return future_fallbacks[0] if future_fallbacks else None

        open_mode = self._control_mode("open")
        close_mode = self._control_mode("close")
        open_base = self._next_mode_event("open", open_mode, now)
        close_base = self._next_mode_event("close", close_mode, now)

        if self._auto_enabled(CONF_AUTO_UP) and self._mode_enabled(open_mode):
            self._next_open = _clamp_candidate(
                open_base, next_up_early, next_up_late, (next_up_early, next_up_late)
            )
        else:
            self._next_open = None

        if self._auto_enabled(CONF_AUTO_DOWN) and self._mode_enabled(close_mode):
            self._next_close = _clamp_candidate(
                close_base,
                next_down_early,
                next_down_late,
                (next_down_early, next_down_late),
            )
        else:
            self._next_close = None

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

        if self._next_open is not None:
            self._next_open = self._next_open.replace(microsecond=0)
        if self._next_close is not None:
            self._next_close = self._next_close.replace(microsecond=0)

        self._next_final_close = None
        self._next_final_close_trigger = "scheduled_final_close"
        if self.config.get(CONF_INTERMEDIATE_CLOSE_ENABLED, False) and self._auto_enabled(CONF_AUTO_DOWN):
            candidates = []
            if self.config.get(CONF_FINAL_CLOSE_TIME_ENABLED, DEFAULT_FINAL_CLOSE_TIME_ENABLED):
                final_time = _parse_time(str(self.config.get(CONF_FINAL_CLOSE_TIME, DEFAULT_FINAL_CLOSE_TIME)))
                final_today = self._today_at(now, final_time)
                if final_today is not None:
                    if final_today <= dt_util.as_local(now):
                        final_today += timedelta(days=1)
                    candidates.append(final_today)
            if self.config.get(CONF_FINAL_CLOSE_ELEVATION_ENABLED, DEFAULT_FINAL_CLOSE_ELEVATION_ENABLED):
                elevation_time = self._next_sun_time_for_elevation(
                    self.config.get(CONF_FINAL_CLOSE_ELEVATION, DEFAULT_FINAL_CLOSE_ELEVATION),
                    SunDirection.SETTING,
                    now,
                )
                if elevation_time is not None:
                    candidates.append(elevation_time)
            if candidates:
                self._next_final_close = min(candidates).replace(microsecond=0)
                elevation_time = self._next_sun_time_for_elevation(
                    self.config.get(CONF_FINAL_CLOSE_ELEVATION, DEFAULT_FINAL_CLOSE_ELEVATION),
                    SunDirection.SETTING,
                    now,
                )
                if elevation_time is not None and elevation_time == min(candidates):
                    self._next_final_close_trigger = "scheduled_final_close_elevation"

        self._reschedule_next_event_timers(now)

    def _control_mode(self, kind: str) -> str:
        key, default = (
            (CONF_OPEN_MODE, DEFAULT_OPEN_MODE)
            if kind == "open"
            else (CONF_CLOSE_MODE, DEFAULT_CLOSE_MODE)
        )
        config = getattr(self, "config", {})
        return str(config.get(key, default) or default).lower()

    def _mode_enabled(self, mode: str) -> bool:
        if mode == MODE_TIME:
            return self._auto_enabled(CONF_AUTO_TIME)
        if mode == MODE_BRIGHTNESS:
            return self._auto_enabled(CONF_AUTO_BRIGHTNESS)
        return self._auto_enabled(CONF_AUTO_SUN)

    def _next_mode_event(
        self, kind: str, mode: str, now: datetime
    ) -> datetime | None:
        if mode == MODE_TIME:
            return None
        if mode == MODE_BRIGHTNESS:
            return None
        if mode == MODE_ELEVATION:
            key = CONF_SUN_ELEVATION_OPEN if kind == "open" else CONF_SUN_ELEVATION_CLOSE
            default = (
                DEFAULT_SUN_ELEVATION_OPEN
                if kind == "open"
                else DEFAULT_SUN_ELEVATION_CLOSE
            )
            direction = SunDirection.RISING if kind == "open" else SunDirection.SETTING
            return self._next_sun_time_for_elevation(
                self.config.get(key, default), direction, now
            )
        return self._next_astro_event(kind, mode, now)

    def _next_astro_event(
        self, kind: str, mode: str, now: datetime
    ) -> datetime | None:
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
        offset_key, offset_default = (
            (CONF_ASTRO_OPEN_OFFSET, DEFAULT_ASTRO_OPEN_OFFSET)
            if kind == "open"
            else (CONF_ASTRO_CLOSE_OFFSET, DEFAULT_ASTRO_CLOSE_OFFSET)
        )
        try:
            offset = float(self.config.get(offset_key, offset_default))
        except (TypeError, ValueError):
            offset = float(offset_default)
        for day_offset in range(370):
            target_date = local_now.date() + timedelta(days=day_offset)
            try:
                if mode == MODE_SUNRISE:
                    event_local = sunrise(location.observer, target_date, tzinfo=tzinfo)
                elif mode == MODE_SUNSET:
                    event_local = sunset(location.observer, target_date, tzinfo=tzinfo)
                elif mode == MODE_GOLDEN_HOUR:
                    direction = (
                        SunDirection.RISING if kind == "open" else SunDirection.SETTING
                    )
                    interval = golden_hour(
                        location.observer,
                        target_date,
                        direction=direction,
                        tzinfo=tzinfo,
                    )
                    event_local = interval[1] if kind == "open" else interval[0]
                else:
                    return None
            except (ValueError, TypeError):
                continue
            event_utc = dt_util.as_utc(event_local + timedelta(minutes=offset))
            if event_utc > now:
                return event_utc
        return None

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
        self,
        elevation: float | int | str | None,
        direction: SunDirection,
        now: datetime,
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

    def _next_time_for_point(
        self, scheduled: time | None, now: datetime
    ) -> datetime | None:
        if not scheduled:
            return None
        local_now = dt_util.as_local(now)
        candidate_local = datetime.combine(
            local_now.date(), scheduled, local_now.tzinfo
        )
        if candidate_local <= local_now:
            candidate_local = candidate_local + timedelta(days=1)
        return dt_util.as_utc(candidate_local)

    def _window_points(
        self, early: time | None, late: time | None, now: datetime
    ) -> tuple[datetime | None, datetime | None]:
        """Return early/late bounds for the current actionable window.

        A plain "next time" calculation moves a passed early bound to tomorrow.
        During today's still-open window this would make room sensors report
        tomorrow's close/open instead of today's remaining late fallback.
        """

        local_now = dt_util.as_local(now)
        today = local_now.date()
        tzinfo = local_now.tzinfo

        early_local = datetime.combine(today, early, tzinfo) if early else None
        late_local = datetime.combine(today, late, tzinfo) if late else None

        if late_local and local_now > late_local:
            early_local = (
                datetime.combine(today + timedelta(days=1), early, tzinfo)
                if early
                else None
            )
            late_local = datetime.combine(today + timedelta(days=1), late, tzinfo)
        elif not late_local and early_local and local_now > early_local:
            early_local = datetime.combine(today + timedelta(days=1), early, tzinfo)

        return (
            dt_util.as_utc(early_local) if early_local else None,
            dt_util.as_utc(late_local) if late_local else None,
        )

    def _window_points_for_date(
        self,
        early: time | None,
        late: time | None,
        now: datetime,
        day_offset: int,
    ) -> tuple[datetime | None, datetime | None]:
        """Return fixed bounds for a future local calendar date."""

        local_now = dt_util.as_local(now)
        target_date = local_now.date() + timedelta(days=day_offset)
        tzinfo = local_now.tzinfo
        early_local = (
            datetime.combine(target_date, early, tzinfo) if early is not None else None
        )
        late_local = (
            datetime.combine(target_date, late, tzinfo) if late is not None else None
        )
        return (
            dt_util.as_utc(early_local) if early_local else None,
            dt_util.as_utc(late_local) if late_local else None,
        )
