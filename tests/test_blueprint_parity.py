"""Regression tests for behavior synchronized from the CCA blueprint."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
import voluptuous as vol

from homeassistant.util import dt as dt_util

from custom_components.cover_control.config_flow import _normalize_position_value
from custom_components.cover_control.const import (
    CONF_ADDITIONAL_CONDITION_OPEN,
    CONF_AUTO_VENTILATE,
    CONF_DRIVE_TIME,
    CONF_LOCKOUT_POSITION,
    CONF_OPEN_POSITION,
    CONF_POSITION_TOLERANCE,
    CONF_SHADING_POSITION,
    CONF_SHADING_POSITION_ALT,
    CONF_SHADING_POSITION_ALT_ENTITY,
    CONF_WINDOW_SENSOR_TILT,
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
    controller.hass = SimpleNamespace(states=_States(states), data={})
    controller.entry = SimpleNamespace(entry_id="test-entry")
    controller._auto_entity_map = {}
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


def test_startup_position_sync_preserves_persisted_target() -> None:
    """Entity startup state must not overwrite the target loaded from storage."""

    cover_state = SimpleNamespace(
        state="open",
        attributes={"current_position": 80},
    )
    controller = _controller({}, {"cover.test": cover_state})
    controller.cover = "cover.test"
    controller._target = 25
    controller._last_position = None
    controller._status = {"target": 25}

    controller._sync_position_reference_from_entity()

    assert controller._target == 25
    assert controller._status["target"] == 25
    assert controller._last_position == 80


def test_unavailable_contact_blocks_decisions() -> None:
    """Ventilation must not end while a configured contact is unavailable."""

    window = SimpleNamespace(state="unavailable", attributes={})
    controller = _controller(
        {
            CONF_AUTO_VENTILATE: True,
            CONF_WINDOW_SENSOR_TILT: {
                "cover.test": ["binary_sensor.window"],
            },
        },
        {"binary_sensor.window": window},
    )
    controller.cover = "cover.test"

    assert controller._unavailable_decision_entities() == {
        "binary_sensor.window"
    }

    window.state = "off"
    assert controller._unavailable_decision_entities() == set()


def test_internal_position_feedback_is_not_manual_override() -> None:
    """Noisy feedback during an integration drive remains an internal move."""

    cover_state = SimpleNamespace(
        state="closing",
        attributes={"current_position": 40},
    )
    controller = _controller(
        {
            CONF_DRIVE_TIME: 90,
            CONF_POSITION_TOLERANCE: 0,
        },
        {"cover.test": cover_state},
    )
    controller.cover = "cover.test"
    controller._manual_until = None
    controller._manual_active = False
    controller._manual_expire_unsub = None
    controller._last_position = 50
    controller._target = 80
    controller._last_command_at = dt_util.utcnow()
    controller._activate_manual_override = Mock()
    controller.async_request_evaluate = Mock()

    event = SimpleNamespace(
        data={
            "entity_id": "cover.test",
            "old_state": None,
            "new_state": cover_state,
        }
    )
    controller._handle_state_event(event)

    controller._activate_manual_override.assert_not_called()
    assert controller._last_position == 40


@pytest.mark.asyncio
async def test_additional_condition_uses_current_condition_api() -> None:
    """Condition checkers use async_check and are unloaded after evaluation."""

    condition_config = {
        "condition": "state",
        "entity_id": "binary_sensor.test",
        "state": "on",
    }
    controller = _controller(
        {CONF_ADDITIONAL_CONDITION_OPEN: condition_config},
        {},
    )
    checker = Mock()
    checker.async_check.return_value = True

    with (
        patch(
            "custom_components.cover_control.controller.condition.async_validate_condition_config",
            new=AsyncMock(return_value=condition_config),
        ) as validate,
        patch(
            "custom_components.cover_control.controller.condition.async_from_config",
            new=AsyncMock(return_value=checker),
        ) as create,
    ):
        assert await controller._condition_allows(CONF_ADDITIONAL_CONDITION_OPEN)

    validate.assert_awaited_once_with(controller.hass, condition_config)
    create.assert_awaited_once_with(controller.hass, condition_config)
    checker.async_check.assert_called_once_with()
    checker.async_unload.assert_called_once_with()
    checker.assert_not_called()


@pytest.mark.asyncio
async def test_additional_condition_keeps_legacy_condition_compatibility() -> None:
    """The HACS minimum version can still use callable condition checkers."""

    condition_config = {"condition": "state"}
    controller = _controller(
        {CONF_ADDITIONAL_CONDITION_OPEN: condition_config},
        {},
    )
    legacy_checker = Mock(spec=())
    legacy_checker.return_value = True

    with (
        patch(
            "custom_components.cover_control.controller.condition.async_validate_condition_config",
            new=AsyncMock(return_value=condition_config),
        ),
        patch(
            "custom_components.cover_control.controller.condition.async_from_config",
            new=AsyncMock(return_value=legacy_checker),
        ),
    ):
        assert await controller._condition_allows(CONF_ADDITIONAL_CONDITION_OPEN)

    legacy_checker.assert_called_once_with(controller.hass)


@pytest.mark.asyncio
async def test_additional_condition_runs_on_home_assistant_2026_8(hass) -> None:
    """An actual Home Assistant condition checker can be evaluated."""

    condition_config = {
        "condition": "state",
        "entity_id": "binary_sensor.test",
        "state": "on",
    }
    controller = object.__new__(CoverController)
    controller.hass = hass
    controller.config = {CONF_ADDITIONAL_CONDITION_OPEN: condition_config}
    hass.states.async_set("binary_sensor.test", "on")

    assert await controller._condition_allows(CONF_ADDITIONAL_CONDITION_OPEN)

    hass.states.async_set("binary_sensor.test", "off")
    assert not await controller._condition_allows(CONF_ADDITIONAL_CONDITION_OPEN)
