"""Regression tests for event-driven actuator waits."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.cover_control.controller import CoverController
from custom_components.cover_control.const import (
    CONF_CLOSE_TILT_POSITION,
    CONF_OPEN_TILT_POSITION,
    CONF_SHADING_TILT_POSITION,
    CONF_VENTILATE_TILT_POSITION,
)


@pytest.mark.asyncio
async def test_position_wait_completes_from_state_event() -> None:
    """Position waits react to HA events without periodic sleeps."""

    controller = object.__new__(CoverController)
    controller.hass = object()
    controller.cover = "cover.test"
    controller.config = {}
    position = {"value": 0}
    controller._current_position = lambda: position["value"]
    unsubscribe = Mock()

    def _track(_hass, entity_ids, callback):
        assert entity_ids == ["cover.test"]

        def _finish():
            position["value"] = 50
            callback(object())

        asyncio.get_running_loop().call_soon(_finish)
        return unsubscribe

    with patch(
        "custom_components.cover_control.runtime.actuator.async_track_state_change_event",
        side_effect=_track,
    ):
        await controller._wait_for_position(50, 0, timeout=5)

    unsubscribe.assert_called_once_with()


@pytest.mark.asyncio
async def test_state_wait_timeout_is_non_polling() -> None:
    """Integrations without events exit via timeout and clean their listener."""

    controller = object.__new__(CoverController)
    controller.hass = object()
    controller.cover = "cover.test"
    unsubscribe = Mock()

    with patch(
        "custom_components.cover_control.runtime.actuator.async_track_state_change_event",
        return_value=unsubscribe,
    ):
        reached = await controller._async_wait_for_state_change(
            lambda: False, 0, ["cover.test"]
        )

    assert not reached
    unsubscribe.assert_called_once_with()


@pytest.mark.parametrize(
    ("reason", "key"),
    [
        ("scheduled_open", CONF_OPEN_TILT_POSITION),
        ("scheduled_close", CONF_CLOSE_TILT_POSITION),
        ("shading_start", CONF_SHADING_TILT_POSITION),
        ("ventilation", CONF_VENTILATE_TILT_POSITION),
    ],
)
def test_tilt_reasons_use_single_physical_targets(reason: str, key: str) -> None:
    controller = object.__new__(CoverController)
    controller.config = {key: 42}

    assert controller._tilt_position_value(reason) == 42


@pytest.mark.asyncio
async def test_tilt_waits_for_idle_before_command() -> None:
    controller = object.__new__(CoverController)
    state = SimpleNamespace(attributes={"supported_features": 128})
    controller.hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda _entity_id: state)
    )
    controller.cover = "cover.test"
    controller._async_wait_for_state_change = AsyncMock(return_value=True)
    controller._command_tilt_position = AsyncMock()

    with patch(
        "custom_components.cover_control.runtime.actuator._async_cover_entity_feature",
        AsyncMock(return_value=SimpleNamespace(SET_TILT_POSITION=128)),
    ):
        await controller._send_tilt_after_position(35, reason="shading_start")

    controller._async_wait_for_state_change.assert_awaited_once()
    controller._command_tilt_position.assert_awaited_once_with(
        35, reason="shading_start"
    )


@pytest.mark.asyncio
async def test_duplicate_tilt_command_is_suppressed() -> None:
    state = SimpleNamespace(
        state="open",
        attributes={"supported_features": 128, "current_tilt_position": 35},
    )
    controller = object.__new__(CoverController)
    controller.hass = SimpleNamespace(
        states=SimpleNamespace(get=lambda _entity_id: state),
        services=SimpleNamespace(async_call=AsyncMock()),
    )
    controller.cover = "cover.test"
    controller.config = {}
    controller._cover_state_or_warn = Mock(return_value=state)

    with patch(
        "custom_components.cover_control.runtime.actuator._async_cover_entity_feature",
        AsyncMock(return_value=SimpleNamespace(SET_TILT_POSITION=128)),
    ):
        await controller._command_tilt_position(35.5, reason="shading_start")

    controller.hass.services.async_call.assert_not_awaited()
