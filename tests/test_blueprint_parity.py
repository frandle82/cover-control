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
    CONF_AUTO_DOWN,
    CONF_AUTO_SHADING,
    CONF_AUTO_TIME,
    CONF_AUTO_UP,
    CONF_AUTO_VENTILATE,
    CONF_DRIVE_TIME,
    CONF_DRIVE_DELAY_FIXED,
    CONF_ENABLE_LOGBOOK_COVER,
    CONF_LOCKOUT_POSITION,
    CONF_MANUAL_OVERRIDE_MINUTES,
    CONF_OPEN_POSITION,
    CONF_MANUAL_CONTROL,
    CONF_POSITION_TOLERANCE,
    CONF_SHADING_POSITION,
    CONF_SHADING_POSITION_ALT,
    CONF_SHADING_POSITION_ALT_ENTITY,
    CONF_MASTER_ENABLED,
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


def _manual_shading_controller(
    position: float = 100,
) -> tuple[CoverController, SimpleNamespace]:
    cover_state = SimpleNamespace(
        state="open",
        attributes={"current_position": position},
    )
    controller = _controller(
        {
            CONF_MASTER_ENABLED: True,
            CONF_AUTO_SHADING: True,
            CONF_MANUAL_CONTROL: True,
            CONF_SHADING_POSITION: 30,
            CONF_POSITION_TOLERANCE: 2,
        },
        {"cover.test": cover_state},
    )
    controller.cover = "cover.test"
    controller._status = {}
    controller._manual_until = None
    controller._manual_active = False
    controller._manual_expire_unsub = None
    controller._manual_movement_pending = False
    controller._last_position = position
    controller._target = position
    controller._last_command_at = None
    controller._last_command_context_id = None
    controller._ignore_service_call_until = None
    controller._next_open = None
    controller._next_close = None
    controller._next_final_close = None
    controller._shading_pending = {}
    controller._shading_timer_unsubs = {}
    controller._last_action_dates = {}
    controller._decision_controls = set()
    controller._reason = None
    controller.persist_status = Mock()
    controller._logbook_entry = Mock()
    controller._fire_event = Mock()
    controller._publish_state = Mock()
    controller._cancel_shading_timer = Mock()
    controller._activate_manual_override = Mock()
    controller.async_request_evaluate = Mock()
    controller._active_safety_alarm = Mock(return_value=None)
    controller.fire_latched = Mock(return_value=False)
    return controller, cover_state


def _manual_position_event(controller: CoverController, cover_state: SimpleNamespace) -> None:
    controller._handle_state_event(
        SimpleNamespace(
            data={
                "entity_id": controller.cover,
                "old_state": None,
                "new_state": cover_state,
            }
        )
    )


def test_manual_move_to_shading_position_is_adopted() -> None:
    controller, cover_state = _manual_shading_controller()
    controller._set_position = AsyncMock()
    cover_state.attributes["current_position"] = 31

    _manual_position_event(controller, cover_state)

    assert controller._reason == "shading"
    assert controller._status_active("shading")
    assert not controller._manual_active
    controller._activate_manual_override.assert_not_called()
    controller._set_position.assert_not_awaited()
    assert controller.state_snapshot()[8] is True
    controller._fire_event.assert_called_once_with(
        "manual_shading_adopted",
        {"trigger": "cover_position_changed", "reason": "shading"},
    )


def test_manual_move_outside_shading_tolerance_sets_override() -> None:
    controller, cover_state = _manual_shading_controller()
    cover_state.attributes["current_position"] = 33

    _manual_position_event(controller, cover_state)

    controller._activate_manual_override.assert_called_once_with(
        reason="manual_override"
    )
    assert not controller._status_active("shading")


def test_manual_shading_adoption_uses_position_tolerance() -> None:
    controller, _cover_state = _manual_shading_controller()

    assert controller._manual_shading_position_matches(28)
    assert controller._manual_shading_position_matches(32)
    assert not controller._manual_shading_position_matches(27)


def test_manual_service_to_shading_waits_for_position_adoption() -> None:
    controller, cover_state = _manual_shading_controller()
    event = SimpleNamespace(
        data={
            "domain": "cover",
            "service": "set_cover_position",
            "service_data": {"entity_id": "cover.test", "position": 30},
        },
        context=None,
    )

    controller._handle_service_call(event)

    controller._activate_manual_override.assert_not_called()
    assert controller._manual_movement_pending

    cover_state.attributes["current_position"] = 30
    _manual_position_event(controller, cover_state)

    assert controller._status_active("shading")
    assert not controller._manual_movement_pending


def test_second_manual_move_after_adoption_sets_override() -> None:
    controller, cover_state = _manual_shading_controller()
    cover_state.attributes["current_position"] = 30
    _manual_position_event(controller, cover_state)
    controller._activate_manual_override.reset_mock()

    cover_state.attributes["current_position"] = 50
    _manual_position_event(controller, cover_state)

    controller._activate_manual_override.assert_called_once_with(
        reason="manual_override"
    )
    assert not controller._status_active("shading")


def test_reality_manual_override_blocks_then_expires() -> None:
    controller, cover_state = _manual_shading_controller()
    controller.config[CONF_MANUAL_OVERRIDE_MINUTES] = 1
    controller._activate_manual_override = (
        CoverController._activate_manual_override.__get__(controller)
    )
    controller._schedule_manual_expiry = Mock()
    controller._refresh_next_events = Mock()

    cover_state.attributes["current_position"] = 60
    _manual_position_event(controller, cover_state)

    assert controller._manual_active
    assert controller._reason == "manual_override"
    assert controller._manual_blocks_action("close")

    controller._handle_manual_expiry(None)

    assert not controller._manual_active
    controller.async_request_evaluate.assert_called_with("manual_expired")


def test_manual_shading_adoption_is_per_cover() -> None:
    left, left_state = _manual_shading_controller()
    right, _right_state = _manual_shading_controller()
    left_state.attributes["current_position"] = 30

    _manual_position_event(left, left_state)

    assert left._status_active("shading")
    assert not right._status_active("shading")
    assert right._reason is None


def test_safety_overrides_manual_shading_adoption() -> None:
    controller, cover_state = _manual_shading_controller()
    controller._active_safety_alarm.return_value = ("rain", 100)
    cover_state.attributes["current_position"] = 30

    _manual_position_event(controller, cover_state)

    controller._activate_manual_override.assert_called_once_with(
        reason="manual_override"
    )
    assert not controller._status_active("shading")


def test_clearing_manual_override_requests_immediate_evaluation() -> None:
    """Clearing an override immediately resumes automatic cover control."""

    controller = _controller({}, {})
    controller._manual_until = dt_util.utcnow()
    controller._manual_active = True
    controller._manual_expire_unsub = None
    controller._reason = "manual_override"
    controller._status = {
        "manual": {"active": True, "until": "later"}
    }
    controller.persist_status = Mock()
    controller._refresh_next_events = Mock()
    controller._publish_state = Mock()
    controller.async_request_evaluate = Mock()

    controller.clear_manual_override()
    assert not controller._manual_active
    assert controller._manual_until is None
    controller.async_request_evaluate.assert_called_once_with("manual_cleared")


@pytest.mark.parametrize(
    "action",
    ["open", "close", "ventilation", "shading", "heat_protection", "resident"],
)
def test_manual_override_blocks_all_automation_actions(action: str) -> None:
    controller = _controller({}, {})
    controller._manual_active = True

    assert controller._manual_blocks_action(action)


def test_manual_override_expires_after_configured_minutes() -> None:
    now = dt_util.utcnow()
    controller = _controller({CONF_MANUAL_OVERRIDE_MINUTES: 15}, {})

    assert controller._manual_reset_at(now) == now + timedelta(minutes=15)


def test_manual_override_zero_duration_persists() -> None:
    controller = _controller({CONF_MANUAL_OVERRIDE_MINUTES: 0}, {})

    assert controller._manual_reset_at(dt_util.utcnow()) is None


def test_disabled_manual_override_ignores_manual_detection() -> None:
    controller = _controller({CONF_MANUAL_CONTROL: False}, {})
    controller._manual_active = False

    assert not controller._manual_detection_enabled()


def test_runtime_reevaluates_after_override_expiry() -> None:
    controller = _controller({}, {})
    controller._manual_until = dt_util.utcnow()
    controller._manual_active = True
    controller._manual_expire_unsub = None
    controller._reason = "manual_override"
    controller._status = {"manual": {"active": True}}
    controller.persist_status = Mock()
    controller._logbook_entry = Mock()
    controller._refresh_next_events = Mock()
    controller._publish_state = Mock()
    controller.async_request_evaluate = Mock()

    controller._handle_manual_expiry(None)

    assert not controller._manual_active
    controller.async_request_evaluate.assert_called_once_with("manual_expired")


def test_manual_override_survives_restart_before_expiry() -> None:
    until = dt_util.utcnow() + timedelta(minutes=15)
    controller = _controller({}, {})
    controller._status = {
        "manual": {"active": True, "until": until.isoformat(), "ts": 1}
    }
    controller._last_action_dates = {}

    controller._hydrate_persistent_status()

    assert controller._manual_active
    assert controller._manual_until == until


def test_expired_manual_override_is_not_restored() -> None:
    until = dt_util.utcnow() - timedelta(minutes=1)
    controller = _controller({}, {})
    controller._status = {
        "manual": {"active": True, "until": until.isoformat(), "ts": 1}
    }
    controller._last_action_dates = {}

    controller._hydrate_persistent_status()

    assert not controller._manual_active
    assert controller._manual_until is None


def test_drive_delay_uses_fixed_setting() -> None:
    controller = _controller(
        {CONF_DRIVE_TIME: 90, CONF_DRIVE_DELAY_FIXED: 2},
        {},
    )
    assert controller._drive_delay_seconds() == 2
    assert controller.config[CONF_DRIVE_TIME] == 90


def test_current_position_uses_home_assistant_cover_attribute() -> None:
    controller = _controller(
        {},
        {
            "cover.test": SimpleNamespace(
                state="open", attributes={"current_position": 42}
            )
        },
    )
    controller.cover = "cover.test"

    assert controller._current_position() == 42


def test_current_position_is_unavailable_without_standard_attribute() -> None:
    controller = _controller(
        {}, {"cover.test": SimpleNamespace(state="closed", attributes={})}
    )
    controller.cover = "cover.test"

    assert controller._current_position() is None


def test_delayed_startup_does_not_trigger_recovery() -> None:
    controller = _controller({}, {})
    controller._startup_complete = False
    controller._runtime_outage_active = False
    assert not controller._recovery_should_catch_up(True)


def test_completed_startup_recovery_uses_runtime_outage_mode() -> None:
    controller = _controller({}, {})
    controller._startup_complete = True
    controller._runtime_outage_active = True
    assert controller._recovery_should_catch_up(True)
    controller._runtime_outage_active = False
    assert not controller._recovery_should_catch_up(True)

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
    controller._shading_pending = {}
    controller._schedule_shading_timer = Mock()
    controller._cancel_shading_timer = Mock()
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
