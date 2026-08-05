"""Regression tests for behavior synchronized from the CCA blueprint."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import voluptuous as vol

from custom_components.cover_control.config_flow import _normalize_position_value
from custom_components.cover_control.const import (
    CONF_LOCKOUT_POSITION,
    CONF_OPEN_POSITION,
    CONF_POSITION_TOLERANCE,
    CONF_SHADING_POSITION,
    CONF_SHADING_POSITION_ALT,
    CONF_SHADING_POSITION_ALT_ENTITY,
)
from custom_components.cover_control.controller import CoverController


class _States:
    def __init__(self, states: dict[str, SimpleNamespace]) -> None:
        self._states = states

    def get(self, entity_id: str | None):
        return self._states.get(entity_id)


def _controller(config: dict, states: dict[str, SimpleNamespace]) -> CoverController:
    controller = object.__new__(CoverController)
    controller.config = config
    controller.hass = SimpleNamespace(states=_States(states))
    return controller


@pytest.mark.parametrize("value", [None, "", vol.UNDEFINED])
def test_optional_blueprint_positions_remain_empty(value) -> None:
    """Empty optional targets must not be normalized to zero."""

    assert _normalize_position_value(CONF_LOCKOUT_POSITION, value) is None
    assert _normalize_position_value(CONF_SHADING_POSITION_ALT, value) is None


def test_alternate_shading_position_follows_gate() -> None:
    """The alternate target is selected only while its gate is active."""

    config = {
        CONF_SHADING_POSITION: 25,
        CONF_SHADING_POSITION_ALT: 45,
        CONF_SHADING_POSITION_ALT_ENTITY: "input_boolean.alt_shading",
    }
    gate = SimpleNamespace(state="on", attributes={})
    controller = _controller(config, {"input_boolean.alt_shading": gate})

    assert controller._effective_shading_position() == 45

    gate.state = "off"
    assert controller._effective_shading_position() == 25


def test_full_ventilation_status_uses_lockout_position() -> None:
    """A configured full-window target is used for ventilation status."""

    controller = _controller(
        {
            CONF_OPEN_POSITION: 100,
            CONF_LOCKOUT_POSITION: 82,
            CONF_POSITION_TOLERANCE: 0,
        },
        {},
    )
    controller._reason = "ventilation_full"

    assert controller._ventilation_is_active(82)
    assert not controller._ventilation_is_active(100)


@pytest.mark.asyncio
@pytest.mark.parametrize(("current", "target", "expected_tilt"), [(50, 20, 0), (50, 80, 100)])
async def test_tilt_before_position_aligns_with_travel(
    current: float, target: float, expected_tilt: float
) -> None:
    """Slats align in the cover's travel direction before positioning."""

    cover_state = SimpleNamespace(
        state="open",
        attributes={"current_tilt_position": 50},
    )
    controller = _controller({}, {"cover.test": cover_state})
    controller.cover = "cover.test"
    controller._command_tilt_position = AsyncMock()

    await controller._align_tilt_before_position(current, target, "shading")

    controller._command_tilt_position.assert_awaited_once_with(
        float(expected_tilt), reason="shading_tilt_alignment"
    )
