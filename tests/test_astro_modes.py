"""Regression coverage for explicit shuttercontrol-style control modes."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from astral import LocationInfo
from astral.sun import SunDirection, golden_hour, sunrise, sunset, time_at_elevation
from homeassistant.util import dt as dt_util

from custom_components.cover_control.const import (
    CONF_ASTRO_CLOSE_OFFSET,
    CONF_ASTRO_OPEN_OFFSET,
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_DOWN,
    CONF_AUTO_SUN,
    CONF_AUTO_TIME,
    CONF_AUTO_UP,
    CONF_BRIGHTNESS_CLOSE_BELOW,
    CONF_BRIGHTNESS_OPEN_ABOVE,
    CONF_CLOSE_MODE,
    CONF_FINAL_CLOSE_ELEVATION,
    CONF_FINAL_CLOSE_ELEVATION_ENABLED,
    CONF_GROUP,
    CONF_GROUPS,
    CONF_INTERMEDIATE_CLOSE_ENABLED,
    CONF_OPEN_MODE,
    CONF_RESIDENT_ALLOW_OPEN,
    CONF_RESIDENT_STATUS,
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
    CONF_SUN_ELEVATION_CLOSE,
    CONF_SUN_ELEVATION_OPEN,
    CONF_TIME_DOWN_EARLY_WORKDAY,
    CONF_TIME_DOWN_LATE_WORKDAY,
    CONF_TIME_UP_EARLY_WORKDAY,
    CONF_TIME_UP_LATE_WORKDAY,
    MODE_BRIGHTNESS,
    MODE_ELEVATION,
    MODE_GOLDEN_HOUR,
    MODE_SUNRISE,
    MODE_SUNSET,
    MODE_TIME,
    GROUP_LIVING,
)
from custom_components.cover_control.config_resolver import resolve_config_model
from custom_components.cover_control.runtime.controller import CoverController
from custom_components.cover_control.runtime.common import scheduled_trigger
from custom_components.cover_control.runtime.group_evaluation import evaluate_time_group


LOCATION = LocationInfo("Frankfurt", "Germany", "Europe/Berlin", 50.11, 8.68)
LOCAL_TZ = dt_util.get_time_zone(LOCATION.timezone)


@pytest.fixture(autouse=True)
def _local_timezone():
    dt_util.set_default_time_zone(LOCAL_TZ)
    yield
    dt_util.set_default_time_zone(timezone.utc)


def _hass():
    return SimpleNamespace(
        states=SimpleNamespace(get=lambda _entity_id: None),
        config=SimpleNamespace(
            latitude=LOCATION.latitude,
            longitude=LOCATION.longitude,
            time_zone=LOCATION.timezone,
        ),
    )


def _config(open_mode: str, close_mode: str) -> dict:
    return {
        CONF_OPEN_MODE: open_mode,
        CONF_CLOSE_MODE: close_mode,
        CONF_AUTO_UP: True,
        CONF_AUTO_DOWN: True,
        CONF_AUTO_TIME: True,
        CONF_AUTO_SUN: True,
        CONF_AUTO_BRIGHTNESS: True,
        CONF_TIME_UP_EARLY_WORKDAY: "04:00:00",
        CONF_TIME_UP_LATE_WORKDAY: "12:00:00",
        CONF_TIME_DOWN_EARLY_WORKDAY: "14:00:00",
        CONF_TIME_DOWN_LATE_WORKDAY: "23:00:00",
        CONF_SUN_ELEVATION_OPEN: 4,
        CONF_SUN_ELEVATION_CLOSE: -4,
        CONF_BRIGHTNESS_OPEN_ABOVE: 100,
        CONF_BRIGHTNESS_CLOSE_BELOW: 20,
    }


def _events(config: dict, now: datetime) -> tuple[datetime | None, datetime | None]:
    return evaluate_time_group(
        _hass(), config, now, capabilities=("opening", "closing", "time", "sun", "brightness")
    )


def test_open_mode_time() -> None:
    now = datetime(2026, 1, 15, 1, tzinfo=timezone.utc)
    next_open, _ = _events(_config(MODE_TIME, MODE_TIME), now)
    assert next_open.astimezone(LOCAL_TZ).time() == time(4)


def test_open_mode_sunrise() -> None:
    now = datetime(2026, 1, 15, 1, tzinfo=timezone.utc)
    next_open, _ = _events(_config(MODE_SUNRISE, MODE_TIME), now)
    expected = sunrise(LOCATION.observer, now.date(), tzinfo=dt_util.get_time_zone(LOCATION.timezone))
    assert next_open == dt_util.as_utc(expected).replace(microsecond=0)


def test_open_mode_golden_hour() -> None:
    now = datetime(2026, 1, 15, 1, tzinfo=timezone.utc)
    next_open, _ = _events(_config(MODE_GOLDEN_HOUR, MODE_TIME), now)
    expected = golden_hour(
        LOCATION.observer,
        now.date(),
        direction=SunDirection.RISING,
        tzinfo=dt_util.get_time_zone(LOCATION.timezone),
    )[1]
    assert next_open == dt_util.as_utc(expected).replace(microsecond=0)


def test_open_mode_elevation() -> None:
    now = datetime(2026, 1, 15, 1, tzinfo=timezone.utc)
    next_open, _ = _events(_config(MODE_ELEVATION, MODE_TIME), now)
    expected = time_at_elevation(
        LOCATION.observer,
        4,
        date=now.date(),
        direction=SunDirection.RISING,
        tzinfo=dt_util.get_time_zone(LOCATION.timezone),
    )
    assert next_open == dt_util.as_utc(expected).replace(microsecond=0)


def test_open_mode_brightness() -> None:
    now = datetime(2026, 1, 15, 1, tzinfo=timezone.utc)
    next_open, _ = _events(_config(MODE_BRIGHTNESS, MODE_TIME), now)
    assert next_open.astimezone(LOCAL_TZ).time() == time(4)


def test_close_mode_time() -> None:
    now = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
    _, next_close = _events(_config(MODE_TIME, MODE_TIME), now)
    assert next_close.astimezone(LOCAL_TZ).time() == time(14)


def test_close_mode_sunset() -> None:
    now = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
    _, next_close = _events(_config(MODE_TIME, MODE_SUNSET), now)
    expected = sunset(LOCATION.observer, now.date(), tzinfo=dt_util.get_time_zone(LOCATION.timezone))
    assert next_close == dt_util.as_utc(expected).replace(microsecond=0)


def test_close_mode_golden_hour() -> None:
    now = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
    _, next_close = _events(_config(MODE_TIME, MODE_GOLDEN_HOUR), now)
    expected = golden_hour(
        LOCATION.observer,
        now.date(),
        direction=SunDirection.SETTING,
        tzinfo=dt_util.get_time_zone(LOCATION.timezone),
    )[0]
    assert next_close == dt_util.as_utc(expected).replace(microsecond=0)


def test_close_mode_elevation() -> None:
    now = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
    _, next_close = _events(_config(MODE_TIME, MODE_ELEVATION), now)
    expected = time_at_elevation(
        LOCATION.observer,
        -4,
        date=now.date(),
        direction=SunDirection.SETTING,
        tzinfo=dt_util.get_time_zone(LOCATION.timezone),
    )
    assert next_close == dt_util.as_utc(expected).replace(microsecond=0)


def test_close_mode_brightness() -> None:
    now = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
    _, next_close = _events(_config(MODE_TIME, MODE_BRIGHTNESS), now)
    assert next_close.astimezone(LOCAL_TZ).time() == time(14)


@pytest.mark.parametrize(
    ("direction", "trigger", "offset", "expected"),
    [
        (SunDirection.RISING, "sun_elevation_changed", timedelta(), False),
        (SunDirection.SETTING, "sun_elevation_changed", timedelta(), True),
        (SunDirection.RISING, "startup", -timedelta(minutes=30), False),
        (SunDirection.SETTING, "startup", timedelta(minutes=30), True),
    ],
)
def test_final_close_elevation_requires_falling_sun(
    direction: SunDirection,
    trigger: str,
    offset: timedelta,
    expected: bool,
) -> None:
    controller = object.__new__(CoverController)
    controller.hass = _hass()
    controller.config = {
        CONF_INTERMEDIATE_CLOSE_ENABLED: True,
        CONF_FINAL_CLOSE_ELEVATION_ENABLED: True,
        CONF_FINAL_CLOSE_ELEVATION: -6,
    }
    controller._last_action_dates = {}
    crossing = time_at_elevation(
        LOCATION.observer,
        -6,
        date=datetime(2026, 1, 15).date(),
        direction=direction,
        tzinfo=LOCAL_TZ,
    )
    now = dt_util.as_utc(crossing + offset)

    assert controller._elevation_final_close_due(
        now, -6 if not offset else -9, frozenset({trigger})
    ) is expected


def test_final_close_elevation_only_fires_once_per_day() -> None:
    controller = object.__new__(CoverController)
    controller.hass = _hass()
    controller.config = {
        CONF_INTERMEDIATE_CLOSE_ENABLED: True,
        CONF_FINAL_CLOSE_ELEVATION_ENABLED: True,
        CONF_FINAL_CLOSE_ELEVATION: -6,
    }
    crossing = time_at_elevation(
        LOCATION.observer,
        -6,
        date=datetime(2026, 1, 15).date(),
        direction=SunDirection.SETTING,
        tzinfo=LOCAL_TZ,
    )
    now = dt_util.as_utc(crossing)
    controller._last_action_dates = {"final_close": dt_util.as_local(now).date()}

    assert not controller._elevation_final_close_due(
        now, -6, frozenset({"sun_elevation_changed"})
    )


@pytest.mark.parametrize(
    ("mode", "early", "late", "expected"),
    [
        (MODE_SUNRISE, time(9), time(10), time(9)),
        (MODE_SUNRISE, time(5), time(6), time(6)),
        (MODE_GOLDEN_HOUR, time(8), time(9), time(9)),
        (MODE_ELEVATION, time(9), time(10), time(9)),
    ],
)
def test_open_astro_modes_are_clamped_by_window(
    mode: str, early: time, late: time, expected: time
) -> None:
    config = _config(mode, MODE_TIME)
    config[CONF_TIME_UP_EARLY_WORKDAY] = early.isoformat()
    config[CONF_TIME_UP_LATE_WORKDAY] = late.isoformat()
    next_open, _ = _events(config, datetime(2026, 1, 15, 1, tzinfo=timezone.utc))
    assert next_open.astimezone(LOCAL_TZ).time() == expected


def test_sunset_is_clamped_by_close_window() -> None:
    config = _config(MODE_TIME, MODE_SUNSET)
    config[CONF_TIME_DOWN_EARLY_WORKDAY] = "20:00:00"
    config[CONF_TIME_DOWN_LATE_WORKDAY] = "21:00:00"
    _, next_close = _events(config, datetime(2026, 1, 15, 12, tzinfo=timezone.utc))
    assert next_close.astimezone(LOCAL_TZ).time() == time(20)


def test_golden_hour_open_uses_reference_event() -> None:
    test_open_mode_golden_hour()


def test_golden_hour_close_uses_reference_event() -> None:
    test_close_mode_golden_hour()


def test_golden_hour_changes_across_seasons() -> None:
    winter, _ = _events(
        _config(MODE_GOLDEN_HOUR, MODE_TIME),
        datetime(2026, 1, 15, 1, tzinfo=timezone.utc),
    )
    summer, _ = _events(
        _config(MODE_GOLDEN_HOUR, MODE_TIME),
        datetime(2026, 6, 15, 1, tzinfo=timezone.utc),
    )
    assert winter.astimezone(LOCAL_TZ).time() != summer.astimezone(LOCAL_TZ).time()


def test_golden_hour_next_event_is_deterministic() -> None:
    now = datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc)
    first = _events(_config(MODE_GOLDEN_HOUR, MODE_GOLDEN_HOUR), now)
    second = _events(_config(MODE_GOLDEN_HOUR, MODE_GOLDEN_HOUR), now)
    assert first == second
    assert all(value is None or value.microsecond == 0 for value in first)


def test_astro_offsets_apply_to_sunrise_sunset_and_golden_hour() -> None:
    now = datetime(2026, 1, 15, 1, tzinfo=timezone.utc)
    base = _config(MODE_SUNRISE, MODE_SUNSET)
    shifted = {**base, CONF_ASTRO_OPEN_OFFSET: 15, CONF_ASTRO_CLOSE_OFFSET: -10}
    base_events = _events(base, now)
    shifted_events = _events(shifted, now)
    assert (shifted_events[0] - base_events[0]).total_seconds() == 900
    assert (shifted_events[1] - base_events[1]).total_seconds() == -600


@pytest.mark.parametrize(
    "now",
    [
        datetime(2026, 3, 29, 0, 30, tzinfo=timezone.utc),
        datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc),
        datetime(2026, 12, 31, 23, 30, tzinfo=timezone.utc),
    ],
)
def test_astro_modes_use_ha_timezone_across_dst_and_year(now: datetime) -> None:
    events = _events(_config(MODE_SUNRISE, MODE_GOLDEN_HOUR), now)
    assert all(value is not None and value.tzinfo is not None for value in events)


def test_astro_modes_use_unambiguous_trigger_ids() -> None:
    assert scheduled_trigger("open", MODE_SUNRISE) == "sunrise_reached"
    assert scheduled_trigger("close", MODE_SUNSET) == "sunset_reached"
    assert scheduled_trigger("open", MODE_GOLDEN_HOUR) == "golden_hour_open_reached"
    assert scheduled_trigger("close", MODE_GOLDEN_HOUR) == "golden_hour_close_reached"


def test_runtime_reality_sunrise_open_and_golden_hour_close() -> None:
    group = _config(MODE_SUNRISE, MODE_GOLDEN_HOUR)
    model = {
        CONF_GROUPS: {GROUP_LIVING: group},
        CONF_ROOMS: {
            "living": {CONF_GROUP: GROUP_LIVING, CONF_ROOM_SETTINGS: {}}
        },
    }
    resolved = resolve_config_model(model, "living")
    next_open, next_close = _events(
        dict(resolved), datetime(2026, 1, 15, 1, tzinfo=timezone.utc)
    )
    assert resolved[CONF_OPEN_MODE] == MODE_SUNRISE
    assert resolved[CONF_CLOSE_MODE] == MODE_GOLDEN_HOUR
    assert next_open is not None and next_close is not None


def test_runtime_reality_elevation_open_and_brightness_close() -> None:
    group = _config(MODE_ELEVATION, MODE_BRIGHTNESS)
    model = {
        CONF_GROUPS: {GROUP_LIVING: group},
        CONF_ROOMS: {
            "living": {CONF_GROUP: GROUP_LIVING, CONF_ROOM_SETTINGS: {}}
        },
    }
    resolved = resolve_config_model(model, "living")
    next_open, next_close = _events(
        dict(resolved), datetime(2026, 1, 15, 1, tzinfo=timezone.utc)
    )
    assert resolved[CONF_OPEN_MODE] == MODE_ELEVATION
    assert resolved[CONF_CLOSE_MODE] == MODE_BRIGHTNESS
    assert next_open is not None
    assert next_close.astimezone(LOCAL_TZ).time() == time(14)


def test_resident_blocks_and_later_allows_sunrise_action() -> None:
    controller = object.__new__(CoverController)
    controller.hass = _hass()
    controller.config = {
        **_config(MODE_SUNRISE, MODE_TIME),
        CONF_RESIDENT_STATUS: True,
        CONF_RESIDENT_ALLOW_OPEN: False,
    }
    controller._current_evaluation_triggers = set()
    after_sunrise = datetime(2026, 1, 15, 10, tzinfo=timezone.utc)
    with patch(
        "custom_components.cover_control.runtime.evaluation.dt_util.utcnow",
        return_value=after_sunrise,
    ):
        assert controller._environment_allows_opening(None, None)
    assert controller.config[CONF_RESIDENT_STATUS]
    assert not controller.config[CONF_RESIDENT_ALLOW_OPEN]
