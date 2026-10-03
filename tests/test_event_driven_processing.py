"""Regression tests for event-driven controller processing."""

from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.cover_control.const import (
    CONF_AUTO_DOWN,
    CONF_AUTO_SUN,
    CONF_AUTO_TIME,
    CONF_AUTO_UP,
)
from custom_components.cover_control.controller import ControllerManager, CoverController
from custom_components.cover_control.runtime.events import EventsMixin
from custom_components.cover_control.sensor import NextOpenSensor


def test_setup_has_no_generic_interval_evaluation() -> None:
    """Controller setup must not restore the removed minute polling loop."""

    source = inspect.getsource(EventsMixin.async_setup)
    assert "async_track_time_interval" not in source
    assert "_handle_interval" not in source


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


def test_completed_daily_action_advances_to_tomorrow() -> None:
    """A completed opening exposes the next day's stable schedule window."""

    controller = object.__new__(CoverController)
    now = dt_util.utcnow()
    controller.hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda _entity_id: None),
        config=SimpleNamespace(latitude=None, longitude=None, time_zone=None),
    )
    controller.config = {}
    controller._auto_enabled = lambda key: key in {CONF_AUTO_TIME, CONF_AUTO_UP}
    controller._dynamic_sun_threshold = Mock(return_value=None)
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


def test_point_timer_triggers_have_deterministic_priority() -> None:
    """Precise timer causes outrank generic state changes in a coalesced batch."""

    assert ControllerManager._trigger_priority("scheduled_open") > (
        ControllerManager._trigger_priority("state")
    )
    assert ControllerManager._trigger_priority("condition_timer:sun_open") > (
        ControllerManager._trigger_priority("state")
    )


def test_shading_pending_timer_cancels_and_restarts() -> None:
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
        controller._set_shading_pending("start", first_due, False)
        assert controller._shading_pending_active("start")
        controller._set_shading_pending("start", second_due, False)
        unsubs[0].assert_called_once_with()
        controller._clear_shading_pending("start")
        unsubs[1].assert_called_once_with()
        assert not controller._shading_pending_active("start")

        controller._set_shading_pending("start", third_due, False)
        callbacks[2][0](third_due)

    controller.async_request_evaluate.assert_called_once_with("shading_start_timer")


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


def test_duration_condition_timer_requests_one_evaluation() -> None:
    """A duration callback contributes its precise condition trigger."""

    controller = object.__new__(CoverController)
    controller.hass = object()
    controller._condition_timer_unsubs = {}
    controller.async_request_evaluate = Mock()
    due = dt_util.utcnow() + timedelta(seconds=30)
    callback = None

    def _track(_hass, tracked_callback, _due):
        nonlocal callback
        callback = tracked_callback
        return Mock()

    with patch(
        "custom_components.cover_control.runtime.events.async_track_point_in_time",
        side_effect=_track,
    ):
        controller._schedule_condition_timer("brightness_close", due)
        assert callback is not None
        callback(due)

    controller.async_request_evaluate.assert_called_once_with(
        "condition_timer:brightness_close"
    )


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
    manager.request_evaluate_all = Mock()
    event = SimpleNamespace(data={"entity_id": "sun.sun"})

    manager._handle_shared_state_event(event)

    manager.request_evaluate_all.assert_called_once_with("sun")


@pytest.mark.asyncio
async def test_trigger_sets_and_context_are_shared_across_batch() -> None:
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
        "cover.first": {"state", "resident_woke"},
        "cover.second": {"sun"},
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
        "resident_woke",
        frozenset({"state", "resident_woke"}),
    )
    assert contexts[1][1:] == ("sun", frozenset({"sun"}))


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
        "calendar_boundary:open_start"
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
        controller._schedule_delayed_evaluate("contact", 10)
        controller._schedule_delayed_evaluate("contact", 20)
        unsubscribe.assert_called_once_with()
        assert callback is not None
        callback(dt_util.utcnow())

    controller.async_request_evaluate.assert_called_once_with("contact")
