"""Canonical background and effective target regressions."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.cover_control.const import (
    CONF_AUTO_VENTILATE,
    CONF_CONTACT_STATUS_DELAY,
    CONF_CONTACT_TRIGGER_DELAY,
    CONF_LOCKOUT_POSITION,
    CONF_MASTER_ENABLED,
    CONF_POSITION_TOLERANCE,
    CONF_SHADING_POSITION,
    CONF_VENTILATE_POSITION,
    CONF_WINDOW_SENSOR_FULL,
    CONF_WINDOW_SENSOR_TILT,
)
from custom_components.cover_control.runtime.controller import CoverController


class _States:
    def __init__(self, values: dict[str, SimpleNamespace]) -> None:
        self.values = values

    def get(self, entity_id: str | None):
        return self.values.get(entity_id)

    def is_state(self, entity_id: str, state: str) -> bool:
        value = self.get(entity_id)
        return value is not None and value.state == state


def _state(value: str, position: float | None = None) -> SimpleNamespace:
    attributes = {} if position is None else {"current_position": position}
    return SimpleNamespace(state=value, attributes=attributes)


def _controller(
    *, window_open: bool = True, position: float = 25, persisted: object = None
) -> CoverController:
    cover = "cover.test"
    contact = "binary_sensor.window"
    hass = SimpleNamespace(
        states=_States(
            {
                cover: _state("open", position),
                contact: _state("on" if window_open else "off"),
            }
        )
    )
    controller = CoverController(
        hass,
        SimpleNamespace(entry_id="entry"),
        cover,
        {
            CONF_MASTER_ENABLED: True,
            CONF_AUTO_VENTILATE: True,
            CONF_CONTACT_TRIGGER_DELAY: 0,
            CONF_CONTACT_STATUS_DELAY: 0,
            CONF_VENTILATE_POSITION: 25,
            CONF_LOCKOUT_POSITION: 80,
            CONF_SHADING_POSITION: 35,
            CONF_POSITION_TOLERANCE: 1,
            CONF_WINDOW_SENSOR_FULL: {cover: [contact]},
            CONF_WINDOW_SENSOR_TILT: {cover: []},
        },
        persisted_status=persisted,
        publish_callback=lambda _controller: None,
    )
    controller._command_position = AsyncMock()
    controller._startup_complete = True
    controller._tilt_position_value = Mock(return_value=None)
    controller._drive_delay_seconds = Mock(return_value=0)
    controller._refresh_next_events = Mock()
    return controller


@pytest.mark.asyncio
async def test_background_target_updates_while_window_open() -> None:
    controller = _controller()

    controller._set_background_target(100, "scheduled_open")
    await controller._apply_effective_target()
    controller._set_background_target(50, "scheduled_intermediate_close")
    await controller._apply_effective_target()

    assert (controller._background_target, controller._background_reason) == (
        50,
        "scheduled_intermediate_close",
    )
    assert (controller._effective_target, controller._effective_reason) == (
        25,
        "ventilation",
    )
    controller._command_position.assert_not_awaited()


@pytest.mark.asyncio
async def test_final_close_background_survives_window_override() -> None:
    controller = _controller()

    controller._set_background_target(0, "scheduled_final_close")
    await controller._apply_effective_target()

    assert controller._background_target == 0
    assert controller._background_reason == "scheduled_final_close"
    assert controller._effective_target == 25
    assert controller._effective_reason == "ventilation"


@pytest.mark.asyncio
async def test_window_close_uses_latest_background_target() -> None:
    controller = _controller()
    controller._set_background_target(0, "scheduled_final_close")
    await controller._apply_effective_target()
    controller.hass.states.values["binary_sensor.window"].state = "off"

    await controller._apply_effective_target()

    controller._command_position.assert_awaited_once_with(
        0.0, reason="scheduled_final_close"
    )
    assert controller._effective_target == 0


@pytest.mark.asyncio
async def test_intermediate_close_does_not_return_after_final_close() -> None:
    controller = _controller()
    controller._set_background_target(50, "scheduled_intermediate_close")
    controller._set_background_target(0, "scheduled_final_close")
    await controller._apply_effective_target()
    controller.hass.states.values["binary_sensor.window"].state = "off"

    await controller._apply_effective_target()

    assert [call.args[0] for call in controller._command_position.await_args_list] == [0]
    assert controller._background_target == 0


@pytest.mark.asyncio
async def test_background_open_updates_while_window_open() -> None:
    controller = _controller()

    controller._set_background_target(100, "scheduled_open")
    await controller._apply_effective_target()

    assert controller._background_target == 100
    assert controller._effective_target == 25
    controller.hass.states.values["binary_sensor.window"].state = "off"
    await controller._apply_effective_target()
    controller._command_position.assert_awaited_once_with(
        100.0, reason="scheduled_open"
    )


@pytest.mark.asyncio
async def test_shading_background_updates_while_window_open() -> None:
    controller = _controller()

    controller._set_background_target(35, "shading")
    await controller._apply_effective_target()

    assert (controller._background_target, controller._background_reason) == (
        35,
        "shading",
    )
    assert controller._effective_reason == "ventilation"
    controller.hass.states.values["binary_sensor.window"].state = "off"
    await controller._apply_effective_target()
    controller._command_position.assert_awaited_once_with(35.0, reason="shading")


@pytest.mark.asyncio
async def test_manual_override_does_not_stop_background_evaluation() -> None:
    controller = _controller(position=40)
    controller._manual_active = True
    controller._set_background_target(0, "scheduled_final_close")

    await controller._apply_effective_target()

    assert controller._background_target == 0
    assert (controller._effective_target, controller._effective_reason) == (
        40,
        "manual_override",
    )
    controller._command_position.assert_not_awaited()

    controller._manual_active = False
    await controller._apply_effective_target()
    assert controller._effective_reason == "ventilation"
    controller.hass.states.values["cover.test"] = _state("open", 25)
    controller.hass.states.values["binary_sensor.window"].state = "off"
    await controller._apply_effective_target()
    assert controller._command_position.await_args_list[-1].args == (0.0,)
    assert controller._command_position.await_args_list[-1].kwargs == {
        "reason": "scheduled_final_close"
    }


@pytest.mark.asyncio
async def test_safety_override_does_not_destroy_background_target() -> None:
    controller = _controller()
    controller._set_background_target(0, "scheduled_final_close")
    controller._safety_decision = Mock(return_value=(True, 100, "fire_alarm"))

    await controller._apply_effective_target()

    assert controller._background_target == 0
    assert (controller._effective_target, controller._effective_reason) == (
        100,
        "fire_alarm",
    )

    controller._safety_decision = Mock(return_value=(False, None, None))
    await controller._apply_effective_target()
    assert controller._effective_reason == "ventilation"
    controller.hass.states.values["binary_sensor.window"].state = "off"
    await controller._apply_effective_target()
    assert controller._effective_reason == "scheduled_final_close"
    assert controller._background_target == 0


@pytest.mark.asyncio
async def test_restart_restores_background_state_safely() -> None:
    controller = _controller(
        persisted={
            "target": 25,
            "reason": "ventilation",
            "background": {
                "target": 0,
                "reason": "scheduled_final_close",
                "updated_at": 123,
            },
            "effective": {
                "target": 25,
                "reason": "ventilation",
                "updated_at": 124,
            },
        }
    )

    assert controller._background_target == 0
    assert controller._effective_target == 25
    controller._command_position.assert_not_awaited()

    await controller._apply_effective_target()

    assert controller._background_target == 0
    assert controller._effective_reason == "ventilation"


def test_legacy_status_falls_back_to_target_and_reason() -> None:
    controller = _controller(
        window_open=False,
        persisted={"target": 42, "reason": "scheduled_close"},
    )

    assert (controller._background_target, controller._background_reason) == (
        42,
        "scheduled_close",
    )
    assert (controller._effective_target, controller._effective_reason) == (
        42,
        "scheduled_close",
    )


def test_legacy_override_uses_restore_position_only_as_fallback() -> None:
    controller = _controller(
        window_open=False,
        persisted={
            "target": 25,
            "reason": "ventilation",
            "ventilation": {"restore_position": 0},
        },
    )

    assert (controller._background_target, controller._background_reason) == (0, None)
    assert (controller._effective_target, controller._effective_reason) == (
        25,
        "ventilation",
    )


@pytest.mark.asyncio
async def test_target_state_snapshot_distinguishes_all_layers() -> None:
    controller = _controller()
    controller._set_background_target(0, "scheduled_final_close")
    await controller._apply_effective_target()

    snapshot = controller.target_state_snapshot()

    assert snapshot["background_target"] == 0
    assert snapshot["background_reason"] == "scheduled_final_close"
    assert snapshot["effective_target"] == 25
    assert snapshot["effective_reason"] == "ventilation"
    assert snapshot["actual_position"] == 25
    assert snapshot["background_updated_at"] is not None
    assert snapshot["effective_updated_at"] is not None
    assert controller._status["background"] == {
        "target": 0.0,
        "reason": "scheduled_final_close",
        "updated_at": snapshot["background_updated_at"],
    }
