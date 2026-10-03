"""Regression tests for event-driven controller processing."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from homeassistant.util import dt as dt_util

from custom_components.cover_control.const import (
    CONF_AUTO_DOWN,
    CONF_AUTO_SUN,
    CONF_AUTO_TIME,
    CONF_AUTO_UP,
)
from custom_components.cover_control.controller import CoverController


def test_state_snapshot_is_read_only() -> None:
    """Reading a snapshot must not recalculate schedule state or publish."""

    controller = object.__new__(CoverController)
    controller._target = 42
    controller._reason = None
    controller._manual_until = None
    controller._manual_active = False
    controller._next_open = dt_util.utcnow() + timedelta(hours=1)
    controller._next_close = dt_util.utcnow() + timedelta(hours=2)
    controller._current_position = Mock(return_value=40)
    controller._auto_enabled = Mock(return_value=True)
    controller._shading_is_active = Mock(return_value=False)
    controller._ventilation_is_active = Mock(return_value=False)
    controller._refresh_next_events = Mock()
    controller._publish_state = Mock()

    first = controller.state_snapshot()
    second = controller.state_snapshot()

    assert first == second
    controller._refresh_next_events.assert_not_called()
    controller._publish_state.assert_not_called()


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


def test_next_sun_event_does_not_follow_now() -> None:
    """An already-met sun threshold still exposes the next scheduled event."""

    controller = object.__new__(CoverController)
    now = dt_util.utcnow()
    next_rising = now + timedelta(hours=20)
    sun = SimpleNamespace(
        attributes={
            "elevation": 30,
            "next_rising": next_rising.isoformat(),
            "next_setting": (now + timedelta(hours=8)).isoformat(),
        }
    )
    controller.hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda entity_id: sun if entity_id == "sun.sun" else None),
        config=SimpleNamespace(latitude=None, longitude=None, time_zone=None),
    )
    controller.config = {}
    controller._auto_enabled = lambda key: key == CONF_AUTO_SUN and key not in {
        CONF_AUTO_TIME,
        CONF_AUTO_UP,
        CONF_AUTO_DOWN,
    }
    controller._dynamic_sun_threshold = lambda kind: 5 if kind == "open" else -5
    controller._is_workday = Mock(return_value=True)
    controller._is_workday_tomorrow = Mock(return_value=True)
    controller._time_bounds = Mock(return_value=(None, None))
    controller._reschedule_next_event_timers = Mock()

    controller._refresh_next_events(now)

    assert controller._next_open == next_rising
    assert controller._next_open != now
    controller._reschedule_next_event_timers.assert_called_once_with(now)
