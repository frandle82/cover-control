"""Regression tests for two-stage automatic closing with open windows."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.util import dt as dt_util

from custom_components.cover_control.const import (
    CONF_AUTO_VENTILATE,
    CONF_CLOSE_POSITION,
    CONF_DRIVE_TIME,
    CONF_LOCKOUT_POSITION,
    CONF_POSITION_TOLERANCE,
    CONF_SHADING_POSITION,
    CONF_VENTILATE_POSITION,
    CONF_WINDOW_SENSOR_FULL,
    CONF_WINDOW_SENSOR_TILT,
)
from custom_components.cover_control.runtime.common import (
    TRIGGER_WINDOW_DOWN_SEQUENCE_TARGET_REACHED,
    _normalize_cover_status,
)
from custom_components.cover_control.runtime.controller import CoverController
from custom_components.cover_control.runtime.manager import ControllerManager


class _States:
    def __init__(self, states: dict[str, SimpleNamespace]) -> None:
        self.states = states

    def get(self, entity_id: str | None):
        return self.states.get(entity_id)

    def is_state(self, entity_id: str, state: str) -> bool:
        value = self.get(entity_id)
        return value is not None and value.state == state


def _state(state: str, position: float | None = None) -> SimpleNamespace:
    attributes = {} if position is None else {"current_position": position}
    return SimpleNamespace(state=state, attributes=attributes)


def _controller(
    cover: str = "cover.test", *, full_open: bool = False, tilted: bool = False
) -> CoverController:
    controller = object.__new__(CoverController)
    full_sensor = f"binary_sensor.{cover.split('.')[-1]}_open"
    tilt_sensor = f"binary_sensor.{cover.split('.')[-1]}_tilt"
    controller.cover = cover
    controller.config = {
        CONF_AUTO_VENTILATE: True,
        CONF_CLOSE_POSITION: 0,
        CONF_VENTILATE_POSITION: 25,
        CONF_LOCKOUT_POSITION: 80,
        CONF_DRIVE_TIME: 30,
        CONF_POSITION_TOLERANCE: 1,
        CONF_WINDOW_SENSOR_FULL: {cover: [full_sensor]},
        CONF_WINDOW_SENSOR_TILT: {cover: [tilt_sensor]},
    }
    controller.hass = SimpleNamespace(
        states=_States(
            {
                cover: _state("open", 100),
                full_sensor: _state("on" if full_open else "off"),
                tilt_sensor: _state("on" if tilted else "off"),
            }
        )
    )
    controller._evaluation_context = None
    controller._auto_enabled = Mock(
        side_effect=lambda key: key == CONF_AUTO_VENTILATE
    )
    controller._is_awning = Mock(return_value=False)
    controller._frost_target_if_active = Mock(return_value=None)
    controller._window_down_sequence = None
    controller._delayed_evaluation_unsubs = {}
    controller._status = _normalize_cover_status(None)
    controller._pre_ventilation_position = None
    controller._target = None
    controller._reason = None
    controller._manual_active = False
    controller._last_command_at = None
    controller._group_position_callback = None
    controller._decision_controls = set()
    controller._last_action_dates = {}
    controller._tilt_position_value = Mock(return_value=None)
    controller._drive_delay_seconds = Mock(return_value=0)
    controller._command_position = AsyncMock()
    controller._record_action_status = Mock()
    controller._refresh_next_events = Mock()
    controller._publish_state = Mock()
    controller.persist_status = Mock()
    controller._schedule_delayed_evaluate = Mock()
    return controller


def _set_window_state(
    controller: CoverController, *, full_open: bool, tilted: bool
) -> None:
    states = controller.hass.states.states
    states[controller._full_open_sensors()[0]].state = "on" if full_open else "off"
    states[controller._tilt_sensors()[0]].state = "on" if tilted else "off"


async def _finish_first_drive(controller: CoverController) -> None:
    controller.hass.states.states[controller.cover] = _state("closed", 0)
    await controller._evaluate_window_down_sequence(
        TRIGGER_WINDOW_DOWN_SEQUENCE_TARGET_REACHED
    )


@pytest.mark.asyncio
async def test_auto_close_with_open_window_closes_then_ventilates() -> None:
    controller = _controller(full_open=True)

    await controller._set_position_local(0, "scheduled_close")
    controller._schedule_delayed_evaluate.assert_called_once_with(
        TRIGGER_WINDOW_DOWN_SEQUENCE_TARGET_REACHED,
        30,
        timer_key="window_down_sequence",
    )
    assert controller.window_down_sequence_snapshot() == {
        "phase": "closing",
        "initial_target": 0.0,
        "window_state": "open",
        "final_target": 80.0,
        "reason": "scheduled_close",
    }
    await _finish_first_drive(controller)

    assert [call.args[0] for call in controller._command_position.await_args_list] == [
        0,
        80,
    ]
    assert controller._reason == "ventilation_full"


def test_open_window_uses_lockout_position() -> None:
    controller = _controller(full_open=True)

    assert controller._window_down_sequence_target("scheduled_close") == (
        "open",
        80,
    )


def test_tilted_window_uses_ventilation_position() -> None:
    controller = _controller(tilted=True)

    assert controller._window_down_sequence_target("scheduled_close") == (
        "tilted",
        25,
    )


@pytest.mark.asyncio
async def test_final_close_respects_window_sequence() -> None:
    controller = _controller(full_open=True)

    await controller._set_position_local(0, "scheduled_final_close")

    controller._command_position.assert_awaited_once_with(
        0.0, reason="scheduled_final_close"
    )
    assert controller.window_down_sequence_snapshot()["reason"] == (
        "scheduled_final_close"
    )


@pytest.mark.asyncio
async def test_christmas_window_close_uses_existing_window_runtime() -> None:
    controller = _controller(full_open=True)

    await controller._set_position_local(25, "scheduled_close")

    controller._command_position.assert_awaited_once_with(
        25.0, reason="scheduled_close"
    )
    assert controller.window_down_sequence_snapshot()["initial_target"] == 25.0


@pytest.mark.asyncio
async def test_auto_close_with_tilted_window_closes_then_ventilates() -> None:
    controller = _controller(tilted=True)

    await controller._set_position_local(0, "scheduled_close")
    await _finish_first_drive(controller)

    assert [call.args[0] for call in controller._command_position.await_args_list] == [
        0,
        25,
    ]
    assert controller._reason == "ventilation"


@pytest.mark.asyncio
async def test_window_closed_during_first_drive_skips_second_drive() -> None:
    controller = _controller(full_open=True)
    await controller._set_position_local(0, "scheduled_close")

    _set_window_state(controller, full_open=False, tilted=False)
    await _finish_first_drive(controller)

    controller._command_position.assert_awaited_once()
    assert controller._reason == "scheduled_close"


@pytest.mark.asyncio
async def test_window_open_changes_to_tilted_uses_latest_target() -> None:
    controller = _controller(full_open=True)
    await controller._set_position_local(0, "sun_close")

    _set_window_state(controller, full_open=False, tilted=True)
    await _finish_first_drive(controller)

    assert controller._command_position.await_args_list[-1].args[0] == 25


@pytest.mark.asyncio
async def test_window_tilted_changes_to_open_uses_latest_target() -> None:
    controller = _controller(tilted=True)
    await controller._set_position_local(0, "brightness_close")

    _set_window_state(controller, full_open=True, tilted=False)
    await _finish_first_drive(controller)

    assert controller._command_position.await_args_list[-1].args[0] == 80


@pytest.mark.asyncio
async def test_second_drive_is_not_detected_as_manual_override() -> None:
    controller = _controller(tilted=True)

    await controller._set_position_local(0, "scheduled_close")
    await _finish_first_drive(controller)

    assert not controller._manual_active
    assert controller._target == 25
    assert controller._window_down_sequence is None


@pytest.mark.asyncio
async def test_window_close_restores_original_close_target() -> None:
    controller = _controller(tilted=True)
    await controller._set_position_local(0, "scheduled_close")
    await _finish_first_drive(controller)
    _set_window_state(controller, full_open=False, tilted=False)
    controller.hass.states.states[controller.cover] = _state("open", 25)

    target, reason = controller._background_return_target(
        controller._background_for("ventilation"),
        fallback=controller._pre_ventilation_position,
    )
    await controller._set_position_local(target, reason)

    assert (target, reason) == (0, "ventilation_end_close")
    assert [call.args[0] for call in controller._command_position.await_args_list] == [
        0,
        25,
        0,
    ]


@pytest.mark.asyncio
async def test_reality_auto_close_window_ventilate_restore() -> None:
    controller = _controller(full_open=True)

    await controller._set_position_local(0, "scheduled_close")
    await _finish_first_drive(controller)
    _set_window_state(controller, full_open=False, tilted=False)
    controller.hass.states.states[controller.cover] = _state("open", 80)
    target, reason = controller._background_return_target(
        controller._background_for("ventilation"),
        fallback=controller._pre_ventilation_position,
    )
    await controller._set_position_local(target, reason)

    assert [call.args[0] for call in controller._command_position.await_args_list] == [
        0,
        80,
        0,
    ]


@pytest.mark.asyncio
async def test_reality_window_priority_replaces_shading_then_restores() -> None:
    controller = _controller()
    controller.config[CONF_SHADING_POSITION] = 25
    controller.hass.states.states[controller.cover] = _state("open", 25)
    controller._reason = "shading"
    controller._set_status_bucket("shading", True)
    controller._remember_pre_ventilation_position()

    await controller._set_position_local(80, "ventilation_full")
    target, reason = controller._background_return_target(
        controller._background_for("ventilation"),
        fallback=controller._pre_ventilation_position,
    )
    controller.hass.states.states[controller.cover] = _state("open", 80)
    await controller._set_position_local(target, reason)

    assert (target, reason) == (25, "ventilation_end_shading")
    assert [call.args[0] for call in controller._command_position.await_args_list] == [
        80,
        25,
    ]


def test_frost_does_not_use_window_ventilation_sequence() -> None:
    controller = _controller(tilted=True)

    assert controller._window_down_sequence_target("frost_alarm") is None


@pytest.mark.asyncio
async def test_frost_overrides_window_sequence() -> None:
    controller = _controller(full_open=True)
    controller._frost_target_if_active.return_value = 80

    await controller._set_position(0, "scheduled_close")

    controller._command_position.assert_awaited_once_with(80, reason="frost_alarm")
    assert controller._window_down_sequence is None


async def _assert_duplicate_target_is_suppressed(target: float, reason: str) -> None:
    controller = _controller()
    controller.hass.states.states[controller.cover] = _state("open", target)
    controller._target = target
    controller._last_command_at = dt_util.utcnow()

    await controller._set_position_local(target, reason)

    controller._command_position.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_open_command_is_suppressed_internally() -> None:
    await _assert_duplicate_target_is_suppressed(100, "scheduled_open")


@pytest.mark.asyncio
async def test_duplicate_close_command_is_suppressed_internally() -> None:
    await _assert_duplicate_target_is_suppressed(0, "scheduled_close")


@pytest.mark.asyncio
async def test_duplicate_shading_command_is_suppressed_internally() -> None:
    await _assert_duplicate_target_is_suppressed(25, "shading")


@pytest.mark.asyncio
async def test_room_covers_handle_window_sequence_independently() -> None:
    closed = _controller("cover.closed")
    opened = _controller("cover.opened", full_open=True)
    manager = object.__new__(ControllerManager)
    manager.controllers = {closed.cover: closed, opened.cover: opened}
    manager._batch_active = True
    manager._batch_group_actions = set()
    manager._group_command_lock = asyncio.Lock()
    for controller in manager.controllers.values():
        controller._manual_blocks_action = Mock(return_value=False)
        controller._ventilation_requires_independent_control = Mock(return_value=True)

    await manager._async_set_group_position(closed, 0, "scheduled_close")

    closed._command_position.assert_awaited_once_with(0, reason="scheduled_close")
    opened._command_position.assert_awaited_once_with(0, reason="scheduled_close")
    assert closed._window_down_sequence is None
    assert opened._window_down_sequence is not None
