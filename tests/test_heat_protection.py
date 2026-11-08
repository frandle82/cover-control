"""Regression tests for ioBroker-compatible heat protection."""

from types import SimpleNamespace
from unittest.mock import Mock

from custom_components.cover_control.const import (
    CONF_CLOSE_POSITION,
    CONF_HEAT_PROTECTION_ENABLED,
    CONF_HEAT_PROTECTION_THRESHOLD,
    CONF_SHADING_BRIGHTNESS_SENSOR,
    CONF_SHADING_BRIGHTNESS_START,
    CONF_SHADING_CONDITIONS_START_AND,
    CONF_SHADING_POSITION,
    CONF_SHADING_TEMPERATURE_SENSOR_2,
    CONF_SUN_AZIMUTH_END,
    CONF_SUN_AZIMUTH_START,
    CONF_SUN_ELEVATION_MAX,
    CONF_SUN_ELEVATION_MIN,
    SHADING_CONDITION_AZIMUTH,
    SHADING_CONDITION_BRIGHTNESS,
    SHADING_CONDITION_ELEVATION,
)
from custom_components.cover_control.runtime.common import _normalize_cover_status
from custom_components.cover_control.runtime.controller import CoverController
from custom_components.cover_control.runtime.manager import _controls_for_reason


class _States:
    def __init__(self, states: dict[str, SimpleNamespace]) -> None:
        self.states = states

    def get(self, entity_id: str | None):
        return self.states.get(entity_id)


def _state(value: str) -> SimpleNamespace:
    return SimpleNamespace(state=value, attributes={})


def _controller(temperature: str = "31") -> CoverController:
    controller = object.__new__(CoverController)
    controller.config = {
        CONF_HEAT_PROTECTION_ENABLED: True,
        CONF_HEAT_PROTECTION_THRESHOLD: 30,
        CONF_SHADING_TEMPERATURE_SENSOR_2: "sensor.outdoor",
        CONF_SHADING_BRIGHTNESS_SENSOR: "sensor.brightness",
        CONF_SHADING_BRIGHTNESS_START: 20000,
        CONF_SHADING_CONDITIONS_START_AND: [
            SHADING_CONDITION_AZIMUTH,
            SHADING_CONDITION_ELEVATION,
            SHADING_CONDITION_BRIGHTNESS,
        ],
        CONF_SUN_AZIMUTH_START: 100,
        CONF_SUN_AZIMUTH_END: 260,
        CONF_SUN_ELEVATION_MIN: 10,
        CONF_SUN_ELEVATION_MAX: 70,
        CONF_CLOSE_POSITION: 0,
        CONF_SHADING_POSITION: 25,
    }
    controller.hass = SimpleNamespace(
        states=_States(
            {
                "sensor.outdoor": _state(temperature),
                "sensor.brightness": _state("30000"),
            }
        )
    )
    controller._status = _normalize_cover_status(None)
    controller._reason = None
    return controller


def test_heat_protection_activates_with_reference_conditions() -> None:
    controller = _controller()

    assert controller._shading_start_conditions(180, 40, 30000)[0]
    assert controller._heat_protection_state() == (True, 31.0)


def test_heat_protection_does_not_activate_below_threshold() -> None:
    assert _controller("30")._heat_protection_state() == (False, 30.0)


def test_heat_protection_uses_existing_shading_position() -> None:
    controller = _controller()
    assert controller._shading_target_reason() == (0.0, "heat_protection")

    controller.config[CONF_HEAT_PROTECTION_ENABLED] = False
    assert controller._shading_target_reason() == (25.0, "shading")


def test_heat_protection_respects_azimuth() -> None:
    controller = _controller()
    assert controller._heat_protection_state()[0]
    assert not controller._shading_start_conditions(90, 40, 30000)[0]


def test_heat_protection_respects_elevation() -> None:
    controller = _controller()
    assert controller._heat_protection_state()[0]
    assert not controller._shading_start_conditions(180, 5, 30000)[0]


def test_heat_protection_handles_temperature_sensor_unavailable() -> None:
    assert _controller("unavailable")._heat_protection_state() == (False, None)


def test_heat_protection_and_normal_shading_do_not_churn_position() -> None:
    controller = _controller("29")
    controller._status["heat_protection"] = {"active": False, "hold": True}
    controller._position_matches = Mock(return_value=True)

    assert controller._active_shading_target_reason(0) == (None, "shading", True)


def test_heat_protection_hold_survives_status_hydration() -> None:
    status = _normalize_cover_status(
        {"heat_protection": {"active": False, "hold": True}}
    )

    assert status["heat_protection"] == {"active": False, "hold": True}


def test_active_control_reports_heat_protection_reason() -> None:
    assert _controls_for_reason("heat_protection") == {"heat_protection"}

    controller = _controller()
    controller._reason = "heat_protection"
    assert controller._shading_is_active(0, True)
    assert controller.heat_protection_snapshot() == {
        "active": True,
        "threshold": 30.0,
        "temperature": 31.0,
    }
