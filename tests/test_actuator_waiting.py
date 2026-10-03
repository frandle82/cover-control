"""Regression tests for event-driven actuator waits."""

from __future__ import annotations

import asyncio
from unittest.mock import Mock, patch

import pytest

from custom_components.cover_control.controller import CoverController


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
