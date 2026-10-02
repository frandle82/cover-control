"""Regression tests for behavior synchronized from the CCA blueprint."""

from __future__ import annotations

from types import SimpleNamespace
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
import voluptuous as vol
from homeassistant.util import dt as dt_util

from custom_components.cover_control.config_flow import _normalize_position_value
from custom_components.cover_control.const import (
    CONF_ADDITIONAL_CONDITION_OPEN,
    CONF_AUTO_DOWN,
    CONF_AUTO_TIME,
    CONF_AUTO_UP,
    CONF_AUTO_VENTILATE,
    CONF_DRIVE_TIME,
    CONF_ENABLE_LOGBOOK_COVER,
    CONF_LOCKOUT_POSITION,
    CONF_OPEN_POSITION,
    CONF_MANUAL_SCHEDULE_ADOPTION,
    CONF_POSITION_TOLERANCE,
    CONF_SHADING_POSITION,
    CONF_SHADING_POSITION_ALT,
    CONF_SHADING_POSITION_ALT_ENTITY,
    CONF_SHADING_CONDITIONS_END_AND,
    CONF_SHADING_CONDITIONS_END_OR,
    CONF_SHADING_INDEPENDENT_HOLDS_END,
    CONF_MASTER_ENABLED,
    SHADING_CONDITION_AZIMUTH,
    SHADING_CONDITION_BRIGHTNESS,
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
@pytest.mark.parametrize(
    ("current", "target", "expected_tilt"), [(50, 20, 0), (50, 80, 100)]
)
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

    assert controller._unavailable_decision_entities() == {"binary_sensor.window"}

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
    assert not getattr(controller, "_manual_movement_pending", False)


def test_clearing_manual_override_requests_immediate_evaluation() -> None:
    """Clearing an override immediately resumes automatic cover control."""

    controller = _controller({}, {})
    controller._manual_until = dt_util.utcnow()
    controller._manual_active = True
    controller._manual_scope_all = True
    controller._manual_expire_unsub = None
    controller._reason = "manual_override"
    controller._status = {
        "manual": {"active": True, "scope_all": True, "until": "later"}
    }
    controller.persist_status = Mock()
    controller._refresh_next_events = Mock()
    controller._publish_state = Mock()
    controller.async_request_evaluate = Mock()

    controller.clear_manual_override()

    assert not controller._manual_active
    assert not controller._manual_scope_all
    assert controller._manual_until is None
    controller.async_request_evaluate.assert_called_once_with("manual_cleared")


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
            "homeassistant.helpers.condition.async_validate_condition_config",
            new=AsyncMock(return_value=condition_config),
        ) as validate,
        patch(
            "homeassistant.helpers.condition.async_from_config",
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
            "homeassistant.helpers.condition.async_validate_condition_config",
            new=AsyncMock(return_value=condition_config),
        ),
        patch(
            "homeassistant.helpers.condition.async_from_config",
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


def _shading_wait_controller() -> CoverController:
    controller = _controller({}, {})
    controller._status = {
        "shading": {
            "active": True,
            "start_pending": 0,
            "end_pending": 0,
            "ts": 0,
        }
    }
    controller.persist_status = Mock()
    return controller


def test_continuous_shading_end_wait_completes_without_interruption() -> None:
    """CCA parity: a continuously valid end condition completes its wait."""

    controller = _shading_wait_controller()
    start = dt_util.utcnow()

    assert not controller._shading_end_wait_complete(start, True, 300)
    assert not controller._shading_end_wait_complete(
        start + timedelta(seconds=299), True, 300
    )
    assert controller._shading_end_wait_complete(
        start + timedelta(seconds=300), True, 300
    )


def test_continuous_shading_end_wait_resets_and_restarts() -> None:
    """CCA parity: an interruption discards the complete pending period."""

    controller = _shading_wait_controller()
    start = dt_util.utcnow()

    assert not controller._shading_end_wait_complete(start, True, 300)
    assert not controller._shading_end_wait_complete(
        start + timedelta(seconds=120), False, 300
    )
    assert not controller._shading_pending_active("end")
    assert not controller._shading_end_wait_complete(
        start + timedelta(seconds=200), True, 300
    )
    assert not controller._shading_end_wait_complete(
        start + timedelta(seconds=499), True, 300
    )
    assert controller._shading_end_wait_complete(
        start + timedelta(seconds=500), True, 300
    )


@pytest.mark.parametrize(
    ("end_and", "end_or", "end_invalid", "expected"),
    [
        (
            [SHADING_CONDITION_AZIMUTH, SHADING_CONDITION_BRIGHTNESS],
            [],
            {SHADING_CONDITION_AZIMUTH: True, SHADING_CONDITION_BRIGHTNESS: False},
            False,
        ),
        (
            [],
            [SHADING_CONDITION_AZIMUTH, SHADING_CONDITION_BRIGHTNESS],
            {SHADING_CONDITION_AZIMUTH: False, SHADING_CONDITION_BRIGHTNESS: True},
            True,
        ),
    ],
)
def test_continuous_shading_end_preserves_and_or_semantics(
    end_and, end_or, end_invalid, expected
) -> None:
    """CCA parity: the combined end result, not one sensor, drives continuity."""

    controller = _controller(
        {
            CONF_SHADING_CONDITIONS_END_AND: end_and,
            CONF_SHADING_CONDITIONS_END_OR: end_or,
        },
        {},
    )
    controller._shading_condition_state = Mock(
        return_value={
            "configured": {
                SHADING_CONDITION_AZIMUTH: True,
                SHADING_CONDITION_BRIGHTNESS: True,
            },
            "end_invalid": end_invalid,
        }
    )

    assert controller._shading_end_conditions(180, 30, 1000) is expected


@pytest.mark.parametrize(
    ("enabled", "temperature_met", "immediate_end", "expected"),
    [
        (False, True, False, False),
        (True, True, False, True),
        (True, False, False, False),
        (True, True, True, False),
    ],
)
def test_independent_temperature_hold_is_optional_and_yields_to_immediate_end(
    enabled: bool, temperature_met: bool, immediate_end: bool, expected: bool
) -> None:
    """CCA parity: independent heat starts shading but only optionally holds it."""

    controller = _controller(
        {CONF_SHADING_INDEPENDENT_HOLDS_END: enabled},
        {},
    )

    assert (
        controller._shading_conditions_allow_active_state(
            False, temperature_met, True, immediate_end
        )
        is expected
    )


def _adoption_controller(position: float, **overrides) -> CoverController:
    cover_state = SimpleNamespace(
        state="open" if position else "closed",
        attributes={"current_position": position},
    )
    config = {
        CONF_MASTER_ENABLED: True,
        CONF_AUTO_TIME: True,
        CONF_AUTO_UP: True,
        CONF_AUTO_DOWN: True,
        CONF_MANUAL_SCHEDULE_ADOPTION: True,
        CONF_OPEN_POSITION: 100,
        "close_position": 0,
        CONF_POSITION_TOLERANCE: 2,
        **overrides,
    }
    controller = _controller(config, {"cover.test": cover_state})
    controller.cover = "cover.test"
    controller._last_action_dates = {}
    controller.persist_status = Mock()
    controller._logbook_entry = Mock()
    controller._calendar_windows = AsyncMock(return_value=(None, None))
    return controller


@pytest.mark.asyncio
async def test_manual_schedule_adoption_open_and_close_inside_windows() -> None:
    """CCA parity: final manual targets adopt their per-cover daily actions."""

    now = dt_util.utcnow()
    opening = _adoption_controller(99)
    opening._within_opening_phase = Mock(return_value=True)
    opening._within_closing_phase = Mock(return_value=False)
    assert await opening._async_adopt_manual_schedule("open", now)
    assert opening._last_action_dates["open"] == dt_util.as_local(now).date()
    opening._logbook_entry.assert_called_once_with(
        "Manual movement adopted as today's scheduled opening"
    )

    closing = _adoption_controller(1)
    closing._within_opening_phase = Mock(return_value=False)
    closing._within_closing_phase = Mock(return_value=True)
    assert await closing._async_adopt_manual_schedule("close", now)
    assert closing._last_action_dates["close"] == dt_util.as_local(now).date()


@pytest.mark.asyncio
async def test_manual_schedule_adoption_rejects_window_and_position_mismatches() -> None:
    """CCA parity: outside-window and intermediate manual positions are ignored."""

    now = dt_util.utcnow()
    outside = _adoption_controller(100)
    outside._within_opening_phase = Mock(return_value=False)
    outside._within_closing_phase = Mock(return_value=False)
    assert not await outside._async_adopt_manual_schedule("open", now)
    assert outside._last_action_dates == {}

    intermediate = _adoption_controller(50)
    assert intermediate._manual_schedule_action_for_position(50) is None


def test_manual_schedule_adoption_waits_for_final_position_feedback() -> None:
    """CCA parity: opening/closing feedback never causes premature adoption."""

    controller = _adoption_controller(50)
    cover_state = controller.hass.states.get("cover.test")
    cover_state.state = "opening"
    controller._manual_until = None
    controller._manual_active = False
    controller._manual_expire_unsub = None
    controller._last_position = 0
    controller._target = 0
    controller._last_command_at = None
    controller._manual_movement_pending = False
    controller._activate_manual_override = Mock()
    controller.async_request_evaluate = Mock()
    scheduled = []

    def _capture_task(coro):
        scheduled.append(coro)
        coro.close()

    controller.hass.async_create_task = _capture_task
    event = SimpleNamespace(
        data={
            "entity_id": "cover.test",
            "old_state": None,
            "new_state": cover_state,
        }
    )
    controller._handle_state_event(event)
    assert scheduled == []

    cover_state.state = "open"
    cover_state.attributes["current_position"] = 100
    controller._handle_state_event(event)
    assert len(scheduled) == 1


@pytest.mark.asyncio
async def test_manual_schedule_adoption_is_per_cover_and_keeps_override() -> None:
    """CCA parity: adoption changes one history and never clears manual override."""

    now = dt_util.utcnow()
    left = _adoption_controller(100)
    right = _adoption_controller(0)
    left._within_opening_phase = Mock(return_value=True)
    left._within_closing_phase = Mock(return_value=False)
    left._manual_active = True
    left._manual_scope_all = True

    assert await left._async_adopt_manual_schedule("open", now)
    assert left._manual_active
    assert left._last_action_dates.get("open") == dt_util.as_local(now).date()
    assert right._last_action_dates == {}


def test_logbook_is_optional_and_deduplicates_blocked_decisions() -> None:
    """CCA parity: cover logbook diagnostics are opt-in and avoid repeated noise."""

    controller = _controller({CONF_ENABLE_LOGBOOK_COVER: False}, {})
    controller.cover = "cover.test"
    controller._logbook_dedupe = set()
    logbook = SimpleNamespace(async_log_entry=Mock())
    with patch(
        "custom_components.cover_control.runtime.actuator.import_module",
        return_value=logbook,
    ):
        controller._logbook_entry("disabled")
        logbook.async_log_entry.assert_not_called()

        controller.config[CONF_ENABLE_LOGBOOK_COVER] = True
        controller._logbook_entry("No movement · manual override active", dedupe_key="manual")
        controller._logbook_entry("No movement · manual override active", dedupe_key="manual")
        logbook.async_log_entry.assert_called_once()


def test_logbook_records_actions_and_tolerates_unavailable_component() -> None:
    """CCA parity: scheduled/shading events are cover-scoped and non-critical."""

    controller = _controller({CONF_ENABLE_LOGBOOK_COVER: True}, {})
    controller.cover = "cover.test"
    controller._logbook_dedupe = set()
    controller._target = 100
    logbook = SimpleNamespace(async_log_entry=Mock())
    with patch(
        "custom_components.cover_control.runtime.actuator.import_module",
        return_value=logbook,
    ):
        controller._logbook_action("scheduled_open", 100)
        controller._logbook_action("shading", 25)
        controller._logbook_action("shading_end_open", 100)
    messages = [call.args[2] for call in logbook.async_log_entry.call_args_list]
    assert messages == [
        "Moved to 100% · scheduled opening",
        "Moved to 25% · sun shading started",
        "Sun shading ended",
    ]

    with patch(
        "custom_components.cover_control.runtime.actuator.import_module",
        side_effect=ImportError,
    ):
        controller._logbook_entry("still safe")
