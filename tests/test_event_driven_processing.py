"""Regression tests for event-driven controller processing."""

from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta, timezone
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.util import dt as dt_util
from homeassistant.components.sensor import SensorDeviceClass

from custom_components.cover_control.const import (
    CONF_AUTO_DOWN,
    CONF_AUTO_SUN,
    CONF_AUTO_TIME,
    CONF_AUTO_UP,
    CONF_FINAL_CLOSE_TIME,
    CONF_FINAL_CLOSE_ELEVATION,
    CONF_FINAL_CLOSE_ELEVATION_ENABLED,
    CONF_FINAL_CLOSE_TIME_ENABLED,
    CONF_INTERMEDIATE_CLOSE_ENABLED,
    CONF_INTERMEDIATE_CLOSE_POSITION,
    CONF_NO_GO_TIME_MINUTES,
    CONF_BRIGHTNESS_SENSOR,
    CONF_CLOSE_MODE,
    CONF_OPEN_MODE,
    CONF_SHADING_BRIGHTNESS_SENSOR,
    CONF_SUN_ELEVATION_CLOSE,
    CONF_SUN_ELEVATION_OPEN,
    CONF_TIME_DOWN_EARLY_WORKDAY,
    CONF_TIME_DOWN_LATE_WORKDAY,
    CONF_TIME_UP_EARLY_WORKDAY,
    CONF_TIME_UP_LATE_WORKDAY,
    CONF_NAME,
    CONF_GROUP,
    CONF_GROUPS,
    CONF_ROOM_OVERRIDES,
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
    CONF_SOURCE_OVERRIDES,
    CONF_TIME_DOWN_EARLY_WORKDAY,
    CONF_TIME_DOWN_LATE_WORKDAY,
    CONF_TIME_UP_EARLY_WORKDAY,
    CONF_TIME_UP_LATE_WORKDAY,
    GROUP_LIVING,
    MODE_ELEVATION,
    MODE_TIME,
    SIGNAL_ENTRY_STATE_UPDATED,
)
from custom_components.cover_control.runtime.group_evaluation import (
    evaluate_time_group,
)
from custom_components.cover_control.config_resolver import resolve_config_model
from custom_components.cover_control.controller import ControllerManager, CoverController
from custom_components.cover_control.runtime.events import EventsMixin
from custom_components.cover_control.runtime.common import (
    TRIGGER_SCHEDULED_FINAL_CLOSE_ELEVATION,
)
from custom_components.cover_control.sensor import (
    CONTROL_STATE_OPTIONS,
    ControlStateSensor,
    NextOpenSensor,
)


CONTROL_STATE_OPTION_SET = set(CONTROL_STATE_OPTIONS)

def test_setup_has_no_generic_interval_evaluation() -> None:
    """Controller setup must not restore the removed minute polling loop."""

    source = inspect.getsource(EventsMixin.async_setup)
    assert "async_track_time_interval" not in source
    assert "_handle_interval" not in source


def test_runtime_control_states_are_valid_sensor_options() -> None:
    """The diagnostic sensor exposes every stable runtime control state."""

    sensor = object.__new__(ControlStateSensor)
    assert sensor.device_class is SensorDeviceClass.ENUM
    assert set(sensor.options or ()) == CONTROL_STATE_OPTION_SET
    assert {
        "idle", "time", "sun", "brightness", "calendar", "resident",
        "ventilation", "shading", "heat_protection", "manual_override",
        "window_lockout", "recovery", "multiple",
    } <= CONTROL_STATE_OPTION_SET


def test_control_state_translation_contains_all_sensor_states() -> None:
    """All enum options have English and German entity-state translations."""

    for path in (
        "custom_components/cover_control/strings.json",
        "custom_components/cover_control/translations/en.json",
        "custom_components/cover_control/translations/de.json",
    ):
        import json

        document = json.loads(Path(path).read_text(encoding="utf-8"))
        translations = document["entity"]["sensor"]["control_state"]["state"]
        assert CONTROL_STATE_OPTION_SET <= translations.keys()


def test_state_snapshot_is_read_only() -> None:
    """Reading a snapshot must not recalculate schedule state or publish."""

    controller = object.__new__(CoverController)
    controller._target = 42
    controller._reason = None
    controller._manual_until = None
    controller._manual_active = False
    controller._next_open = dt_util.utcnow() + timedelta(hours=1)
    controller._next_close = dt_util.utcnow() + timedelta(hours=2)
    controller._next_final_close = controller._next_close - timedelta(minutes=30)
    controller._current_position = Mock(return_value=40)
    controller._auto_enabled = Mock(return_value=True)
    controller._shading_is_active = Mock(return_value=False)
    controller._ventilation_is_active = Mock(return_value=False)
    controller._refresh_next_events = Mock()
    controller._publish_state = Mock()

    first = controller.state_snapshot()
    second = controller.state_snapshot()

    assert first == second
    assert first[5] == controller._next_final_close
    controller._refresh_next_events.assert_not_called()
    controller._publish_state.assert_not_called()


@pytest.mark.parametrize("own_context", [True, False])
def test_tilt_service_manual_override_depends_on_command_context(own_context) -> None:
    controller = object.__new__(CoverController)
    controller.cover = "cover.test"
    controller._ignore_service_call_until = None
    controller._last_command_context_id = "own-command"
    controller._current_position = Mock(return_value=50)
    controller._status = {}
    controller._manual_detection_enabled = Mock(return_value=True)
    controller._clear_shading_for_manual_override = Mock()
    controller._activate_manual_override = Mock()
    controller.async_request_evaluate = Mock()
    event = SimpleNamespace(
        context=SimpleNamespace(id="own-command" if own_context else "external"),
        data={
            "domain": "cover",
            "service": "set_cover_tilt_position",
            "service_data": {"entity_id": "cover.test", "tilt_position": 40},
        },
    )

    controller._handle_service_call(event)

    if own_context:
        controller._activate_manual_override.assert_not_called()
    else:
        controller._activate_manual_override.assert_called_once_with(
            reason="manual_override"
        )


def test_scheduled_event_timer_is_single_and_rescheduled() -> None:
    """A changed event replaces its predecessor and fires one evaluation."""

    controller = object.__new__(CoverController)
    controller.hass = object()
    controller._scheduled_open_unsub = None
    controller._scheduled_close_unsub = None
    controller._scheduled_open_at = None
    controller._scheduled_close_at = None
    controller._next_close = None
    controller.async_request_evaluate = Mock()
    now = dt_util.utcnow()
    first_due = now + timedelta(hours=1)
    second_due = now + timedelta(hours=2)
    controller._next_open = first_due
    callbacks = []
    unsubs = []

    def _track(_hass, callback, due):
        callbacks.append((callback, due))
        unsubscribe = Mock()
        unsubs.append(unsubscribe)
        return unsubscribe

    with patch(
        "custom_components.cover_control.runtime.events.async_track_point_in_time",
        side_effect=_track,
    ):
        controller._reschedule_next_event_timers(now)
        controller._reschedule_next_event_timers(now)
        assert len(callbacks) == 1
        assert callbacks[0][1] == first_due

        controller._next_open = second_due
        controller._reschedule_next_event_timers(now)
        unsubs[0].assert_called_once_with()
        assert len(callbacks) == 2
        assert callbacks[1][1] == second_due

        callbacks[1][0](second_due)

    controller.async_request_evaluate.assert_called_once_with("scheduled_open")
    assert controller._scheduled_open_unsub is None


def test_completed_daily_action_advances_to_tomorrow() -> None:
    """A completed opening exposes the next day's stable schedule window."""

    controller = object.__new__(CoverController)
    now = datetime(2026, 1, 15, 22, tzinfo=timezone.utc)
    controller.hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda _entity_id: None),
        config=SimpleNamespace(latitude=None, longitude=None, time_zone=None),
    )
    controller.config = {}
    controller._auto_enabled = lambda key: key in {CONF_AUTO_TIME, CONF_AUTO_UP}
    controller._is_workday = Mock(return_value=True)
    controller._is_workday_tomorrow = Mock(return_value=False)
    controller._time_bounds = Mock(return_value=(time(7), time(8)))
    controller._last_action_dates = {"open": dt_util.as_local(now).date()}
    controller._reschedule_next_event_timers = Mock()

    controller._refresh_next_events(now)

    local_now = dt_util.as_local(now)
    expected_local = datetime.combine(
        local_now.date() + timedelta(days=1), time(7), local_now.tzinfo
    )
    assert controller._next_open == dt_util.as_utc(expected_local)
    assert controller._next_open.date() > now.date()


def _schedule_probe(config: dict, *, states: dict | None = None):
    """Create a schedule probe with deterministic astronomical observations."""

    controller = object.__new__(CoverController)
    controller.config = config
    controller.hass = SimpleNamespace(
        states=SimpleNamespace(
            get=lambda entity_id: (states or {}).get(entity_id)
        ),
        config=SimpleNamespace(latitude=50.0, longitude=8.0, time_zone="UTC"),
    )
    controller._last_action_dates = {}
    controller._auto_enabled = lambda key: bool(config.get(key, False))
    controller._reschedule_next_event_timers = Mock()
    controller._is_workday = Mock(return_value=True)
    controller._is_workday_tomorrow = Mock(return_value=True)
    controller._time_bounds = Mock(return_value=(None, None))
    return controller


def test_next_open_fixed_sun_only() -> None:
    controller = _schedule_probe({
        CONF_AUTO_SUN: True,
        CONF_AUTO_UP: True,
        CONF_OPEN_MODE: MODE_ELEVATION,
        CONF_CLOSE_MODE: MODE_ELEVATION,
        CONF_SUN_ELEVATION_OPEN: 6,
        CONF_SUN_ELEVATION_CLOSE: -4,
    })
    calls = []
    controller._next_sun_time_for_elevation = lambda elevation, direction, now: (
        calls.append((elevation, direction)) or now + timedelta(hours=2)
    )
    now = dt_util.utcnow()
    controller._refresh_next_events(now)
    assert calls[0][0] == 6
    assert controller._next_open == (now + timedelta(hours=2)).replace(microsecond=0)


def test_next_close_fixed_sun_only() -> None:
    controller = _schedule_probe({
        CONF_AUTO_SUN: True,
        CONF_AUTO_DOWN: True,
        CONF_OPEN_MODE: MODE_ELEVATION,
        CONF_CLOSE_MODE: MODE_ELEVATION,
        CONF_SUN_ELEVATION_OPEN: 6,
        CONF_SUN_ELEVATION_CLOSE: -4,
    })
    calls = []
    controller._next_sun_time_for_elevation = lambda elevation, direction, now: (
        calls.append((elevation, direction)) or now + timedelta(hours=3)
    )
    now = dt_util.utcnow()
    controller._refresh_next_events(now)
    assert calls[1][0] == -4
    assert controller._next_close == (now + timedelta(hours=3)).replace(microsecond=0)


def test_next_events_are_none_when_time_and_sun_are_disabled() -> None:
    controller = _schedule_probe({})
    controller._refresh_next_events(dt_util.utcnow())
    assert controller._next_open is None
    assert controller._next_close is None


def test_time_only_ignores_sun_and_live_gates() -> None:
    controller = _schedule_probe(
        {
            CONF_AUTO_TIME: True,
            CONF_AUTO_UP: True,
            CONF_AUTO_DOWN: True,
            CONF_AUTO_SUN: False,
            CONF_TIME_UP_EARLY_WORKDAY: time(6),
            CONF_TIME_UP_LATE_WORKDAY: time(8),
            CONF_TIME_DOWN_EARLY_WORKDAY: time(20),
            CONF_TIME_DOWN_LATE_WORKDAY: time(22),
            "brightness_sensor": "sensor.brightness",
            "resident_sensor": "binary_sensor.resident",
        },
        states={
            "sensor.brightness": SimpleNamespace(state="0"),
            "binary_sensor.resident": SimpleNamespace(state="on"),
        },
    )
    controller._time_bounds = Mock(
        side_effect=lambda _workday, opening: (
            (time(6), time(8)) if opening else (time(20), time(22))
        )
    )
    now = datetime(2026, 1, 15, 5, tzinfo=timezone.utc)
    controller._refresh_next_events(now)
    baseline = (controller._next_open, controller._next_close)
    controller._state_for = lambda _entity_id: SimpleNamespace(state="on")
    controller._refresh_next_events(now)
    assert dt_util.as_local(controller._next_open).time() == time(6)
    assert (controller._next_open, controller._next_close) == baseline


def test_missing_location_and_unreachable_sun_are_safe() -> None:
    controller = _schedule_probe({CONF_AUTO_SUN: True})
    controller.hass.config = SimpleNamespace(
        latitude=None, longitude=None, time_zone=None
    )
    controller._refresh_next_events(dt_util.utcnow())
    assert controller._next_open is None
    assert controller._next_close is None


def test_active_group_provides_next_open_and_close() -> None:
    """A fixed group using the existing master toggle schedules both events."""

    model = {
        CONF_GROUPS: {
            GROUP_LIVING: {
                CONF_AUTO_TIME: True,
                CONF_TIME_UP_EARLY_WORKDAY: "06:30:00",
                CONF_TIME_UP_LATE_WORKDAY: "07:30:00",
                CONF_TIME_DOWN_EARLY_WORKDAY: "20:00:00",
                CONF_TIME_DOWN_LATE_WORKDAY: "21:00:00",
            }
        },
        CONF_ROOMS: {
            "living": {
                CONF_NAME: "Living",
                CONF_GROUP: GROUP_LIVING,
                CONF_ROOM_SETTINGS: {},
                CONF_SOURCE_OVERRIDES: {},
                CONF_ROOM_OVERRIDES: {},
            }
        },
    }
    resolved = resolve_config_model(model, "living")
    assert resolved[CONF_AUTO_UP] is True
    assert resolved[CONF_AUTO_DOWN] is True

    controller = object.__new__(CoverController)
    controller.config = resolved
    controller.hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda _entity_id: None),
        config=SimpleNamespace(latitude=None, longitude=None, time_zone=None),
    )
    controller._auto_enabled = lambda key: bool(resolved.get(key))
    controller._is_workday = Mock(return_value=True)
    controller._is_workday_tomorrow = Mock(return_value=True)
    controller._last_action_dates = {}
    controller._reschedule_next_event_timers = Mock()
    now = datetime(2026, 1, 15, 12, tzinfo=dt_util.UTC)

    controller._refresh_next_events(now)

    assert controller._next_open is not None
    assert controller._next_close is not None


def test_point_timer_triggers_have_deterministic_priority() -> None:
    """Precise timer causes outrank generic state changes in a coalesced batch."""

    assert ControllerManager._trigger_priority("scheduled_open") > (
        ControllerManager._trigger_priority("sun_elevation_changed")
    )
    assert ControllerManager._trigger_priority("sun_open_duration_elapsed") > (
        ControllerManager._trigger_priority("brightness_changed")
    )


def test_open_and_close_schedule_use_distinct_triggers() -> None:
    controller = object.__new__(CoverController)
    controller.hass = object()
    controller.async_request_evaluate = Mock()
    callbacks = {}

    def _track(_hass, callback, due):
        callbacks[due] = callback
        return Mock()

    now = dt_util.utcnow()
    with patch(
        "custom_components.cover_control.runtime.events.async_track_point_in_time",
        side_effect=_track,
    ):
        controller._reschedule_event_timer(None, None, now + timedelta(minutes=1), now, "open")
        controller._reschedule_event_timer(None, None, now + timedelta(minutes=2), now, "close")
        for due, callback in callbacks.items():
            callback(due)

    assert [call.args[0] for call in controller.async_request_evaluate.call_args_list] == [
        "scheduled_open",
        "scheduled_close",
    ]


def test_final_close_timer_uses_distinct_trigger() -> None:
    controller = object.__new__(CoverController)
    controller.hass = object()
    controller.async_request_evaluate = Mock()
    now = dt_util.utcnow()
    callback = None

    def _track(_hass, scheduled_callback, _due):
        nonlocal callback
        callback = scheduled_callback
        return Mock()

    with patch(
        "custom_components.cover_control.runtime.events.async_track_point_in_time",
        side_effect=_track,
    ):
        controller._reschedule_event_timer(
            None, None, now + timedelta(minutes=1), now, "final_close"
        )

    assert callback is not None
    callback(now + timedelta(minutes=1))
    controller.async_request_evaluate.assert_called_once_with("scheduled_final_close")


def test_opening_no_go_uses_cover_last_changed(hass) -> None:
    controller = object.__new__(CoverController)
    controller.hass = hass
    controller.cover = "cover.office"
    controller.config = {CONF_NO_GO_TIME_MINUTES: 10}
    hass.states.async_set(controller.cover, "closed", {"current_position": 0})
    changed_at = hass.states.get(controller.cover).last_changed

    assert controller._opening_no_go_remaining(changed_at + timedelta(minutes=4)) == 360
    assert controller._opening_no_go_remaining(changed_at + timedelta(minutes=10)) == 0


def test_final_close_forecast_uses_existing_schedule_timer() -> None:
    controller = object.__new__(CoverController)
    controller.config = {
        CONF_INTERMEDIATE_CLOSE_ENABLED: True,
        CONF_FINAL_CLOSE_TIME: "22:00:00",
    }
    controller._auto_enabled = Mock(return_value=True)
    controller._state_for = Mock(return_value=None)
    controller._sun_entity = Mock(return_value="sun.sun")
    controller._is_workday = Mock(return_value=True)
    controller._is_workday_tomorrow = Mock(return_value=True)
    controller._last_action_dates = {}
    controller._condition_since = {}
    controller._reschedule_next_event_timers = Mock()
    controller._next_sun_time_for_elevation = Mock(return_value=None)
    now = datetime(2026, 11, 8, 20, 0, tzinfo=timezone.utc)

    controller._refresh_next_events(now)

    assert controller._next_final_close.date().isoformat() == "2026-11-08"
    assert controller._next_final_close.timetz().replace(tzinfo=None) == time(22, 0)


def test_legacy_final_close_keeps_time_behavior_and_disables_elevation() -> None:
    resolved = resolve_config_model(
        {
            CONF_GROUPS: {
                GROUP_LIVING: {
                    CONF_INTERMEDIATE_CLOSE_ENABLED: True,
                    CONF_FINAL_CLOSE_TIME: "21:30:00",
                }
            },
            CONF_ROOMS: {
                "room": {
                    CONF_GROUP: GROUP_LIVING,
                    CONF_ROOM_SETTINGS: {},
                }
            },
        },
        "room",
    )

    assert resolved[CONF_FINAL_CLOSE_TIME_ENABLED] is True
    assert resolved[CONF_FINAL_CLOSE_ELEVATION_ENABLED] is False
    assert resolved[CONF_FINAL_CLOSE_TIME] == "21:30:00"


def test_next_close_uses_earliest_final_close_candidate() -> None:
    controller = object.__new__(CoverController)
    controller.config = {
        CONF_INTERMEDIATE_CLOSE_ENABLED: True,
        CONF_FINAL_CLOSE_TIME_ENABLED: True,
        CONF_FINAL_CLOSE_TIME: "22:00:00",
        CONF_FINAL_CLOSE_ELEVATION_ENABLED: True,
        CONF_FINAL_CLOSE_ELEVATION: -6,
    }
    controller._auto_enabled = Mock(return_value=True)
    controller._state_for = Mock(return_value=None)
    controller._sun_entity = Mock(return_value="sun.sun")
    controller._is_workday = Mock(return_value=True)
    controller._is_workday_tomorrow = Mock(return_value=True)
    controller._last_action_dates = {}
    controller._condition_since = {}
    controller._reschedule_next_event_timers = Mock()
    elevation_close = datetime(2026, 11, 8, 18, 15, tzinfo=timezone.utc)
    controller._next_sun_time_for_elevation = Mock(return_value=elevation_close)

    controller._refresh_next_events(
        datetime(2026, 11, 8, 17, 0, tzinfo=timezone.utc)
    )

    assert controller._next_final_close == elevation_close
    assert (
        controller._next_final_close_trigger
        == TRIGGER_SCHEDULED_FINAL_CLOSE_ELEVATION
    )


def test_completed_final_close_advances_both_candidates_to_tomorrow() -> None:
    controller = object.__new__(CoverController)
    controller.config = {
        CONF_INTERMEDIATE_CLOSE_ENABLED: True,
        CONF_FINAL_CLOSE_TIME_ENABLED: True,
        CONF_FINAL_CLOSE_TIME: "22:00:00",
        CONF_FINAL_CLOSE_ELEVATION_ENABLED: True,
        CONF_FINAL_CLOSE_ELEVATION: -6,
    }
    controller._auto_enabled = Mock(return_value=True)
    controller._state_for = Mock(return_value=None)
    controller._sun_entity = Mock(return_value="sun.sun")
    controller._is_workday = Mock(return_value=True)
    controller._is_workday_tomorrow = Mock(return_value=True)
    now = datetime(2026, 11, 8, 19, 0, tzinfo=timezone.utc)
    controller._last_action_dates = {"final_close": dt_util.as_local(now).date()}
    controller._condition_since = {}
    controller._reschedule_next_event_timers = Mock()
    controller._next_sun_time_for_elevation = Mock(
        return_value=datetime(2026, 11, 9, 18, 15, tzinfo=timezone.utc)
    )

    controller._refresh_next_events(now)

    assert controller._next_final_close.date().isoformat() == "2026-11-09"
    search_from = controller._next_sun_time_for_elevation.call_args.args[2]
    assert dt_util.as_local(search_from).date().isoformat() == "2026-11-08"
    assert dt_util.as_local(search_from).time() == time(23, 59, 59, 999999)


def test_intermediate_close_never_raises_cover_below_target() -> None:
    controller = object.__new__(CoverController)
    controller.config = {
        CONF_INTERMEDIATE_CLOSE_ENABLED: True,
        CONF_INTERMEDIATE_CLOSE_POSITION: 50,
        CONF_FINAL_CLOSE_TIME: "22:00:00",
    }
    controller._position_value = lambda key, default: controller.config.get(key, default)
    now = datetime(2026, 11, 8, 20, 0, tzinfo=timezone.utc)

    assert controller._intermediate_close_target(now, 40, False) == (True, None)
    assert controller._intermediate_close_target(now, 80, False) == (True, 50)


def test_shading_end_timer_cancels_and_restarts() -> None:
    """A broken shading condition cancels its timer before a fresh wait."""

    controller = object.__new__(CoverController)
    controller.hass = object()
    controller._status = {"shading": {"active": False}}
    controller._shading_pending = {}
    controller._shading_timer_unsubs = {}
    controller.async_request_evaluate = Mock()
    now = dt_util.utcnow()
    first_due = now + timedelta(minutes=5)
    second_due = now + timedelta(minutes=10)
    third_due = now + timedelta(minutes=15)
    callbacks = []
    unsubs = []

    def _track(_hass, callback, due):
        callbacks.append((callback, due))
        unsubscribe = Mock()
        unsubs.append(unsubscribe)
        return unsubscribe

    with patch(
        "custom_components.cover_control.runtime.events.async_track_point_in_time",
        side_effect=_track,
    ):
        controller._set_shading_pending("end", first_due, False)
        assert controller._shading_pending_active("end")
        controller._set_shading_pending("end", second_due, False)
        unsubs[0].assert_called_once_with()
        controller._clear_shading_pending("end")
        unsubs[1].assert_called_once_with()
        assert not controller._shading_pending_active("end")

        controller._set_shading_pending("end", third_due, False)
        callbacks[2][0](third_due)

    controller.async_request_evaluate.assert_called_once_with("shading_end_timer")


def test_duration_condition_uses_timer_and_cancels_on_fall() -> None:
    """A duration condition is reevaluated at its deadline without polling."""

    controller = object.__new__(CoverController)
    controller.hass = object()
    controller._condition_since = {}
    controller._condition_timer_unsubs = {}
    controller.async_request_evaluate = Mock()
    now = dt_util.utcnow()
    callbacks = []
    unsubscribe = Mock()

    def _track(_hass, callback, due):
        callbacks.append((callback, due))
        return unsubscribe

    with (
        patch(
            "custom_components.cover_control.runtime.events.async_track_point_in_time",
            side_effect=_track,
        ),
        patch(
            "custom_components.cover_control.runtime.evaluation.dt_util.utcnow",
            return_value=now,
        ),
    ):
        assert not controller._condition_held("sun_open", True, 60)
        assert len(callbacks) == 1
        assert callbacks[0][1] == now + timedelta(seconds=60)
        assert not controller._condition_held("sun_open", False, 60)

    unsubscribe.assert_called_once_with()
    assert "sun_open" not in controller._condition_since


def _condition_timer_triggers(*keys: str) -> list[str]:
    controller = object.__new__(CoverController)
    controller.hass = object()
    controller._condition_timer_unsubs = {}
    controller.async_request_evaluate = Mock()
    callbacks = []

    def _track(_hass, tracked_callback, _due):
        callbacks.append(tracked_callback)
        return Mock()

    with patch(
        "custom_components.cover_control.runtime.events.async_track_point_in_time",
        side_effect=_track,
    ):
        for index, key in enumerate(keys, 1):
            controller._schedule_condition_timer(
                key, dt_util.utcnow() + timedelta(seconds=index)
            )
        for callback in callbacks:
            callback(dt_util.utcnow())
    return [call.args[0] for call in controller.async_request_evaluate.call_args_list]


def test_brightness_open_and_close_duration_use_distinct_timer_keys() -> None:
    assert _condition_timer_triggers("brightness_open", "brightness_close") == [
        "brightness_open_duration_elapsed",
        "brightness_close_duration_elapsed",
    ]


def test_shading_end_uses_distinct_trigger() -> None:
    controller = object.__new__(CoverController)
    controller.hass = object()
    controller._shading_timer_unsubs = {}
    controller.async_request_evaluate = Mock()
    callbacks = []

    with patch(
        "custom_components.cover_control.runtime.events.async_track_point_in_time",
        side_effect=lambda _hass, callback, _due: callbacks.append(callback) or Mock(),
    ):
        due = dt_util.utcnow() + timedelta(seconds=1)
        controller._schedule_shading_timer("end", due)
        for callback in callbacks:
            callback(due)

    controller.async_request_evaluate.assert_called_once_with("shading_end_timer")

    source = object.__new__(CoverController)
    source.config = {CONF_SHADING_BRIGHTNESS_SENSOR: "sensor.shading"}
    source._auto_entity_map = {}
    source._sun_entity = Mock(return_value="sun.sun")
    source._auto_enabled = Mock(return_value=False)
    assert source._shared_state_triggers("sensor.shading", None, "100") == {
        "shading_start_condition_changed",
        "shading_end_condition_changed",
    }


def test_shared_input_roles_use_specific_triggers() -> None:
    controller = object.__new__(CoverController)
    controller.config = {
        CONF_BRIGHTNESS_SENSOR: "sensor.brightness",
    }
    controller._auto_entity_map = {}
    controller._sun_entity = Mock(return_value="sun.sun")
    controller._auto_enabled = Mock(return_value=False)

    assert controller._shared_state_triggers(
        "sensor.brightness", None, "100"
    ) == {"brightness_changed"}


def test_window_state_triggers_are_unambiguous() -> None:
    controller = object.__new__(CoverController)
    controller._full_open_sensors = Mock(return_value=["binary_sensor.window"])
    controller._tilt_sensors = Mock(return_value=["binary_sensor.tilt"])

    assert controller._window_trigger("binary_sensor.window", True) == "window_open"
    assert controller._window_trigger("binary_sensor.tilt", True) == "window_tilted"
    assert controller._window_trigger("binary_sensor.window", False) == "window_closed"


def test_window_delay_timer_keys_are_per_sensor() -> None:
    controller = object.__new__(CoverController)
    controller.hass = object()
    controller._delayed_evaluation_unsubs = {}
    controller.async_request_evaluate = Mock()

    with patch(
        "custom_components.cover_control.runtime.events.async_track_point_in_time",
        return_value=Mock(),
    ):
        controller._schedule_delayed_evaluate(
            "window_open", 10, timer_key="contact:binary_sensor.left"
        )
        controller._schedule_delayed_evaluate(
            "window_tilted", 10, timer_key="contact:binary_sensor.right"
        )

    assert set(controller._delayed_evaluation_unsubs) == {
        "contact:binary_sensor.left",
        "contact:binary_sensor.right",
    }


def test_event_payload_exposes_specific_trigger() -> None:
    controller = object.__new__(CoverController)
    controller.entry = SimpleNamespace(entry_id="entry")
    controller.cover = "cover.living"
    controller._master_entity_id = "switch.master"
    controller._reason = "sun_open"
    controller.hass = SimpleNamespace(bus=SimpleNamespace(async_fire=Mock()))

    controller._fire_event("evaluate", {"trigger": "sun_elevation_changed"})

    payload = controller.hass.bus.async_fire.call_args.args[1]
    assert payload["trigger"] == "sun_elevation_changed"
    assert payload["reason"] == "sun_open"


def test_shared_entities_use_one_manager_listener() -> None:
    """Identical global entities are subscribed once for the whole entry."""

    manager = object.__new__(ControllerManager)
    manager.hass = object()
    manager._shared_listener_unsub = None
    manager._shared_entities = set()
    first = Mock()
    first._shared_decision_entities.return_value = {"sun.sun", "sensor.outdoor"}
    second = Mock()
    second._shared_decision_entities.return_value = {"sun.sun", "sensor.outdoor"}
    manager.controllers = {"cover.first": first, "cover.second": second}
    unsubscribe = Mock()

    with patch(
        "custom_components.cover_control.runtime.manager.async_track_state_change_event",
        return_value=unsubscribe,
    ) as track:
        manager._setup_shared_listener()

    track.assert_called_once_with(
        manager.hass,
        ["sensor.outdoor", "sun.sun"],
        manager._handle_shared_state_event,
    )


def test_shared_sun_event_queues_all_controllers_together() -> None:
    """One manager callback fans a shared sun change into the common queue."""

    manager = object.__new__(ControllerManager)
    manager.controllers = {"cover.first": Mock(), "cover.second": Mock()}
    for controller in manager.controllers.values():
        controller._shared_state_triggers.return_value = {"sun_elevation_changed"}
    manager._entity_routes = {"sun.sun": {"cover.first", "cover.second"}}
    manager._request_evaluate = Mock()
    event = SimpleNamespace(data={"entity_id": "sun.sun"})

    manager._handle_shared_state_event(event)

    assert manager._request_evaluate.call_count == 2
    assert {call.args[1] for call in manager._request_evaluate.call_args_list} == {
        "sun_elevation_changed"
    }


@pytest.mark.asyncio
async def test_pending_evaluations_preserve_distinct_trigger_sources() -> None:
    """A batch retains every cause and snapshots global state only once."""

    state_reads = []
    manager = object.__new__(ControllerManager)
    manager.hass = SimpleNamespace(
        states=SimpleNamespace(
            get=lambda entity_id: state_reads.append(entity_id) or object()
        )
    )
    manager._shared_entities = {"sun.sun", "sensor.outdoor"}
    manager._pending_evaluations = {
        "cover.first": {"sun_elevation_changed", "brightness_changed"},
        "cover.second": {"resident_off"},
    }
    manager._evaluation_lock = asyncio.Lock()
    manager._evaluation_task = Mock()
    manager._start_evaluation_task = Mock()
    manager._batch_group_actions = set()
    manager._pending_state_controllers = set()
    contexts = []

    def _controller(cover):
        controller = Mock()
        controller.cover = cover
        controller._evaluation_context = None

        async def _evaluate(trigger, triggers):
            contexts.append((controller._evaluation_context, trigger, triggers))

        controller._evaluate = AsyncMock(side_effect=_evaluate)
        return controller

    manager.controllers = {
        cover: _controller(cover) for cover in manager._pending_evaluations
    }

    with patch(
        "custom_components.cover_control.runtime.manager.asyncio.sleep",
        new=AsyncMock(),
    ):
        await manager._async_flush_evaluations()

    assert state_reads == ["sensor.outdoor", "sun.sun"] or state_reads == [
        "sun.sun",
        "sensor.outdoor",
    ]
    assert contexts[0][0] is contexts[1][0]
    assert contexts[0][1:] == (
        "sun_elevation_changed",
        frozenset({"sun_elevation_changed", "brightness_changed"}),
    )
    assert contexts[1][1:] == ("resident_off", frozenset({"resident_off"}))


@pytest.mark.asyncio
async def test_group_action_is_deduplicated_within_batch() -> None:
    """Equivalent group decisions result in one room-wide command."""

    manager = object.__new__(ControllerManager)
    manager._batch_active = True
    manager._batch_group_actions = set()
    manager._group_command_lock = asyncio.Lock()
    controllers = []
    for cover in ("cover.first", "cover.second", "cover.third"):
        controller = Mock()
        controller.cover = cover
        controller._manual_blocks_action.return_value = False
        controller._ventilation_requires_independent_control.return_value = False
        controller._set_position_local = AsyncMock()
        controllers.append(controller)
    manager.controllers = {controller.cover: controller for controller in controllers}

    await manager._async_set_group_position(controllers[0], 30, "shading")
    await manager._async_set_group_position(controllers[1], 30, "shading")

    for controller in controllers:
        controller._set_position_local.assert_awaited_once_with(30, "shading")


def test_entry_snapshot_reads_each_controller_once() -> None:
    """Sensors reuse one prepared snapshot instead of walking controllers again."""

    now = dt_util.utcnow()
    first = Mock()
    first.config = {}
    first.state_snapshot.return_value = (
        30,
        "shading",
        None,
        False,
        now + timedelta(hours=1),
        now + timedelta(hours=8),
        30,
        True,
        True,
        False,
    )
    first._resident_state_is_on.return_value = False
    second = Mock()
    second.config = {}
    second.state_snapshot.return_value = (
        100,
        "idle",
        None,
        False,
        now + timedelta(hours=2),
        now + timedelta(hours=7),
        100,
        True,
        False,
        False,
    )
    manager = object.__new__(ControllerManager)
    manager.controllers = {"cover.first": first, "cover.second": second}
    manager.hass = SimpleNamespace(states=SimpleNamespace(get=Mock(return_value=None)))

    manager._rebuild_entry_snapshot()
    initial = manager.entry_snapshot()
    assert manager.entry_snapshot() is initial
    assert manager.entry_snapshot() is initial
    first.state_snapshot.assert_called_once_with()
    second.state_snapshot.assert_called_once_with()
    assert initial["next_open"] == (now + timedelta(hours=1), "cover.first")
    assert initial["control_state"] == "shading"


def test_entry_snapshot_exposes_control_diagnostics() -> None:
    """Active control state keeps configured, active, and blocking details separate."""

    controller = Mock()
    controller.config = {}
    controller.state_snapshot.return_value = (
        None, "manual_override", None, True, None, None, 50, False, False, False
    )
    manager = object.__new__(ControllerManager)
    manager.controllers = {"cover.living": controller}
    manager.hass = SimpleNamespace(states=SimpleNamespace(get=Mock(return_value=None)))
    manager._resolved_config = SimpleNamespace(
        configured_functions=frozenset({"time", "sun", "brightness"})
    )

    manager._rebuild_entry_snapshot()

    snapshot = manager.entry_snapshot()
    assert snapshot["active_controls"] == ["manual_override"]
    assert snapshot["configured_controls"] == ["brightness", "sun", "time"]
    assert snapshot["blocked_by"] == ["manual_override"]
    assert snapshot["reason"] == "manual_override"


def test_entry_snapshot_exposes_active_decision_controls_without_action_reason() -> None:
    controller = Mock()
    controller.config = {}
    controller.state_snapshot.return_value = (
        None, "idle", None, False, None, None, 100, False, False, False
    )
    controller.active_decision_controls.return_value = {"time", "sun"}
    manager = object.__new__(ControllerManager)
    manager.controllers = {"cover.living": controller}
    manager.hass = SimpleNamespace(states=SimpleNamespace(get=Mock(return_value=None)))
    manager._resolved_config = SimpleNamespace(
        configured_functions=frozenset({"time", "sun"})
    )

    manager._rebuild_entry_snapshot()

    snapshot = manager.entry_snapshot()
    assert snapshot["active_controls"] == ["sun", "time"]
    assert snapshot["control_state"] == "multiple"
    assert snapshot["reason"] == "idle"


def test_schedule_snapshot_refresh_dispatches_without_pending_cover_state() -> None:
    """Room next-event sensors update even when no cover state was queued."""

    now = dt_util.utcnow()
    controller = Mock()
    controller.config = {}
    controller.state_snapshot.return_value = (
        None,
        "idle",
        None,
        False,
        now + timedelta(hours=1),
        None,
        None,
        False,
        False,
        False,
    )
    controller._resident_state_is_on.return_value = False
    manager = object.__new__(ControllerManager)
    manager.controllers = {"cover.living": controller}
    manager.hass = SimpleNamespace(states=SimpleNamespace(get=Mock(return_value=None)))
    manager.entry = SimpleNamespace(entry_id="entry")
    manager._entry_snapshot = {
        "covers": {},
        "next_open": None,
        "next_close": None,
        "resident_status": "off",
        "resident_entity": None,
    }

    with patch("custom_components.cover_control.runtime.manager.async_dispatcher_send") as send:
        assert manager.refresh_schedule_snapshot()

    send.assert_called_once_with(manager.hass, SIGNAL_ENTRY_STATE_UPDATED, "entry")
    assert manager.entry_snapshot()["next_open"] == (
        now + timedelta(hours=1),
        "cover.living",
    )


def test_sensor_writes_only_when_visible_entry_state_changes() -> None:
    """An unchanged dispatcher signal must not create another HA state write."""

    due = dt_util.utcnow() + timedelta(hours=1)
    snapshot = {
        "covers": {"cover.first": {}},
        "next_open": (due, "cover.first"),
    }
    manager = Mock()
    manager.controllers = {"cover.first": Mock()}
    manager.entry_snapshot.side_effect = lambda: snapshot
    entry = SimpleNamespace(entry_id="entry", data={}, options={}, title="Entry")
    sensor = NextOpenSensor(SimpleNamespace(data={}), entry)
    sensor._manager = Mock(return_value=manager)
    sensor.async_write_ha_state = Mock()
    sensor._refresh_from_manager()

    sensor._async_handle_state_update("entry")
    sensor.async_write_ha_state.assert_not_called()

    snapshot = {
        "covers": {"cover.first": {}},
        "next_open": (due + timedelta(hours=1), "cover.first"),
    }
    sensor._async_handle_state_update("entry")
    sensor.async_write_ha_state.assert_called_once_with()


def test_calendar_boundaries_are_rescheduled_as_point_timers() -> None:
    """Changed calendar windows replace old boundary callbacks cleanly."""

    controller = object.__new__(CoverController)
    controller.hass = object()
    controller._calendar_timer_unsubs = {}
    controller._calendar_timer_times = {}
    controller.async_request_evaluate = Mock()
    now = dt_util.utcnow()
    first_window = (now + timedelta(hours=1), now + timedelta(hours=2))
    second_window = (now + timedelta(hours=3), now + timedelta(hours=4))
    callbacks = {}
    unsubs = {}

    def _track(_hass, callback, due):
        callbacks[due] = callback
        unsubscribe = Mock()
        unsubs[due] = unsubscribe
        return unsubscribe

    with patch(
        "custom_components.cover_control.runtime.events.async_track_point_in_time",
        side_effect=_track,
    ):
        controller._reschedule_calendar_boundaries(first_window, None, now)
        controller._reschedule_calendar_boundaries(second_window, None, now)
        unsubs[first_window[0]].assert_called_once_with()
        unsubs[first_window[1]].assert_called_once_with()
        callbacks[second_window[0]](second_window[0])

    controller.async_request_evaluate.assert_called_once_with(
        "calendar_open_start"
    )


def test_contact_delay_uses_managed_point_timer() -> None:
    """A repeated contact delay cancels its predecessor instead of spawning tasks."""

    controller = object.__new__(CoverController)
    controller.hass = object()
    controller._delayed_evaluation_unsubs = {}
    controller.async_request_evaluate = Mock()
    unsubscribe = Mock()
    callback = None

    def _track(_hass, tracked_callback, _due):
        nonlocal callback
        callback = tracked_callback
        return unsubscribe

    with patch(
        "custom_components.cover_control.runtime.events.async_track_point_in_time",
        side_effect=_track,
    ):
        controller._schedule_delayed_evaluate("window_open", 10)
        controller._schedule_delayed_evaluate("window_open", 20)
        unsubscribe.assert_called_once_with()
        assert callback is not None
        callback(dt_util.utcnow())

    controller.async_request_evaluate.assert_called_once_with("window_open")
