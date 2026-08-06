"""Cover controller behavior split from the public controller facade."""

from __future__ import annotations

from datetime import (
    datetime,
    time,
    timedelta,
)

from astral import LocationInfo
from astral.sun import SunDirection, time_at_elevation
from homeassistant.const import (
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.util import dt as dt_util

from ..const import (
    CONF_AUTO_DOWN,
    CONF_AUTO_SUN,
    CONF_AUTO_TIME,
    CONF_AUTO_UP,
    CONF_AUTO_VENTILATE,
    CONF_CALENDAR_CLOSE_TITLE,
    CONF_CALENDAR_ENTITY,
    CONF_CALENDAR_OPEN_TITLE,
    CONF_CONTACT_STATUS_DELAY,
    CONF_CONTACT_TRIGGER_DELAY,
    CONF_RESIDENT_SENSOR,
    CONF_SUN_ELEVATION_MODE,
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
    DEFAULT_CONTACT_SETTINGS,
    DEFAULT_SUN_ELEVATION_MODE,
    DEFAULT_TIME_SETTINGS,
)
from .common import (
    _LOGGER,
    _coerce_float,
    _parse_time,
)


class ScheduleMixin:
    def _is_workday(self) -> bool:
        workday_entity = self.config.get(CONF_WORKDAY_SENSOR)
        if not workday_entity:
            return True
        return self.hass.states.is_state(workday_entity, STATE_ON)

    def _is_workday_tomorrow(self) -> bool:
        tomorrow_entity = self.config.get(CONF_WORKDAY_TOMORROW_SENSOR)
        if not tomorrow_entity:
            return self._is_workday()
        return self.hass.states.is_state(tomorrow_entity, STATE_ON)

    def _single_contact_active(self, entity_id: str, now: datetime) -> bool:
        state = self.hass.states.get(entity_id)
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
            state = self.hass.states.get(sensor)
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
            (state := self.hass.states.get(entity_id)) is not None
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
        state = self.hass.states.get(resident_entity)
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

        state = self.hass.states.get(calendar_entity)
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

        state = self.hass.states.get(calendar_entity)
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
        sun_enabled = self._auto_enabled(CONF_AUTO_SUN)
        time_up_enabled = self._auto_enabled(CONF_AUTO_TIME) and self._auto_enabled(
            CONF_AUTO_UP
        )
        time_down_enabled = self._auto_enabled(CONF_AUTO_TIME) and self._auto_enabled(
            CONF_AUTO_DOWN
        )
        sun_state = self.hass.states.get("sun.sun") if sun_enabled else None
        sun_next_rising = self._parse_datetime_attr(
            sun_state and sun_state.attributes.get("next_rising")
        )
        sun_next_setting = self._parse_datetime_attr(
            sun_state and sun_state.attributes.get("next_setting")
        )
        current_sun_elevation = _coerce_float(
            sun_state and sun_state.attributes.get("elevation")
        )
        open_threshold = self._dynamic_sun_threshold("open")
        close_threshold = self._dynamic_sun_threshold("close")
        mode = str(
            self.config.get(CONF_SUN_ELEVATION_MODE, DEFAULT_SUN_ELEVATION_MODE)
            or DEFAULT_SUN_ELEVATION_MODE
        ).lower()

        sun_open_target = (
            self._next_sun_time_for_elevation(open_threshold, SunDirection.RISING, now)
            if sun_enabled
            else None
        )
        sun_close_target = (
            self._next_sun_time_for_elevation(
                close_threshold, SunDirection.SETTING, now
            )
            if sun_enabled
            else None
        )

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

        sun_open_already_passed = (
            current_sun_elevation is not None
            and open_threshold is not None
            and current_sun_elevation > open_threshold
        )
        sun_close_already_passed = (
            current_sun_elevation is not None
            and close_threshold is not None
            and current_sun_elevation < close_threshold
            and (
                self._within_closing_phase(now)
                or self._within_evening_phase(now)
                or self._is_time_down_late(now)
            )
        )

        if sun_enabled and sun_open_already_passed:
            open_base = now
        elif sun_enabled and mode in {"dynamic", "hybrid"}:
            # Dynamic/Hybrid use the elevation-based calculation first.
            # If unavailable, fall back to the native sun integration times
            # so next_open/next_close still remain sun-based.
            open_base = sun_open_target or sun_next_rising
        else:
            open_base = (sun_open_target or sun_next_rising) if sun_enabled else None

        if sun_enabled and sun_close_already_passed:
            close_base = now
        elif sun_enabled and mode in {"dynamic", "hybrid"}:
            close_base = sun_close_target or sun_next_setting
        else:
            close_base = (sun_close_target or sun_next_setting) if sun_enabled else None

        if time_up_enabled:
            self._next_open = _clamp_candidate(
                open_base, next_up_early, next_up_late, (next_up_early, next_up_late)
            )
        else:
            self._next_open = open_base

        if time_down_enabled:
            self._next_close = _clamp_candidate(
                close_base,
                next_down_early,
                next_down_late,
                (next_down_early, next_down_late),
            )
        else:
            self._next_close = close_base

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
