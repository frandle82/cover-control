"""Regression tests for the fixed shuttercontrol-style shading modes."""

from types import SimpleNamespace

import pytest

from custom_components.cover_control.const import (
    CONF_KEEP_SUN_PROTECTION,
    CONF_OPEN_POSITION,
    CONF_SHADING_BRIGHTNESS_HYSTERESIS,
    CONF_SHADING_BRIGHTNESS_SENSOR,
    CONF_SHADING_BRIGHTNESS_THRESHOLD,
    CONF_SHADING_DIRECTION,
    CONF_SHADING_DIRECTION_RANGE,
    CONF_SHADING_INSIDE_TEMPERATURE_HYSTERESIS,
    CONF_SHADING_INSIDE_TEMPERATURE_THRESHOLD,
    CONF_SHADING_MODE,
    CONF_SHADING_OUTSIDE_TEMPERATURE_HYSTERESIS,
    CONF_SHADING_OUTSIDE_TEMPERATURE_THRESHOLD,
    CONF_SUN_ELEVATION_MAX,
    CONF_SUN_ELEVATION_MIN,
    CONF_TEMPERATURE_SENSOR_INDOOR,
    CONF_TEMPERATURE_SENSOR_OUTDOOR,
    SHADING_MODE_DIRECTION,
    SHADING_MODE_INSIDE,
    SHADING_MODE_INSIDE_OUTSIDE,
    SHADING_MODE_INSIDE_OUTSIDE_DIRECTION,
    SHADING_MODE_OFF,
    SHADING_MODE_OUTSIDE,
    SHADING_MODE_OUTSIDE_DIRECTION,
)
from custom_components.cover_control.runtime.common import _normalize_cover_status
from custom_components.cover_control.runtime.controller import CoverController


class _States:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    def get(self, entity_id: str | None):
        value = self.values.get(entity_id or "")
        return SimpleNamespace(state=value, attributes={}) if value is not None else None


def _controller(mode: str, *, brightness_sensor: bool = False) -> CoverController:
    controller = object.__new__(CoverController)
    controller.config = {
        CONF_SHADING_MODE: mode,
        CONF_TEMPERATURE_SENSOR_INDOOR: "sensor.inside",
        CONF_TEMPERATURE_SENSOR_OUTDOOR: "sensor.outside",
        CONF_SHADING_INSIDE_TEMPERATURE_THRESHOLD: 23,
        CONF_SHADING_INSIDE_TEMPERATURE_HYSTERESIS: 10,
        CONF_SHADING_OUTSIDE_TEMPERATURE_THRESHOLD: 25,
        CONF_SHADING_OUTSIDE_TEMPERATURE_HYSTERESIS: 10,
        CONF_SHADING_DIRECTION: 180,
        CONF_SHADING_DIRECTION_RANGE: 45,
        CONF_SUN_ELEVATION_MIN: 10,
        CONF_SUN_ELEVATION_MAX: 70,
        CONF_SHADING_BRIGHTNESS_THRESHOLD: 20000,
        CONF_SHADING_BRIGHTNESS_HYSTERESIS: 10,
    }
    if brightness_sensor:
        controller.config[CONF_SHADING_BRIGHTNESS_SENSOR] = "sensor.brightness"
    controller.hass = SimpleNamespace(
        states=_States(
            {
                "sensor.inside": "24",
                "sensor.outside": "26",
                "sensor.brightness": "21000",
            }
        )
    )
    controller._status = _normalize_cover_status(None)
    return controller


@pytest.mark.parametrize(
    "mode",
    [
        SHADING_MODE_INSIDE_OUTSIDE,
        SHADING_MODE_DIRECTION,
        SHADING_MODE_INSIDE_OUTSIDE_DIRECTION,
        SHADING_MODE_OUTSIDE_DIRECTION,
        SHADING_MODE_OUTSIDE,
        SHADING_MODE_INSIDE,
    ],
)
def test_shading_modes_start_when_required_conditions_match(mode: str) -> None:
    assert _controller(mode)._shading_start_conditions(180, 40, None)[0]


def test_shading_mode_off() -> None:
    assert not _controller(SHADING_MODE_OFF)._shading_start_conditions(180, 40, None)[0]


@pytest.mark.parametrize(
    ("mode", "sensor", "value"),
    [
        (SHADING_MODE_INSIDE, "sensor.inside", "20"),
        (SHADING_MODE_OUTSIDE, "sensor.outside", "20"),
        (SHADING_MODE_INSIDE_OUTSIDE, "sensor.outside", "20"),
        (SHADING_MODE_INSIDE_OUTSIDE_DIRECTION, "sensor.inside", "20"),
        (SHADING_MODE_OUTSIDE_DIRECTION, "sensor.outside", "20"),
    ],
)
def test_required_temperature_failure_ends_shading(mode: str, sensor: str, value: str) -> None:
    controller = _controller(mode)
    controller.hass.states.values[sensor] = value
    assert controller._shading_end_conditions(180, 40, None)


def test_direction_outside_range_ends_shading() -> None:
    controller = _controller(SHADING_MODE_DIRECTION)
    assert not controller._shading_end_conditions(180, 40, None)
    assert controller._shading_end_conditions(270, 40, None)


@pytest.mark.parametrize(("azimuth", "expected"), [(350, True), (10, True), (40, False)])
def test_direction_wraps_zero_degrees(azimuth: float, expected: bool) -> None:
    controller = _controller(SHADING_MODE_DIRECTION)
    controller.config[CONF_SHADING_DIRECTION] = 350
    controller.config[CONF_SHADING_DIRECTION_RANGE] = 30
    assert controller._shading_start_conditions(azimuth, 40, None)[0] is expected


def test_shading_without_brightness_sensor() -> None:
    assert _controller(SHADING_MODE_OUTSIDE)._shading_start_conditions(180, 40, 0)[0]


def test_shading_with_brightness_sensor() -> None:
    assert _controller(SHADING_MODE_OUTSIDE, brightness_sensor=True)._shading_start_conditions(180, 40, None)[0]


def test_brightness_blocks_start() -> None:
    controller = _controller(SHADING_MODE_OUTSIDE, brightness_sensor=True)
    controller.hass.states.values["sensor.brightness"] = "19000"
    assert not controller._shading_start_conditions(180, 40, None)[0]


def test_brightness_hysteresis_delays_end() -> None:
    controller = _controller(SHADING_MODE_OUTSIDE, brightness_sensor=True)
    controller.hass.states.values["sensor.brightness"] = "19000"
    assert not controller._shading_end_conditions(180, 40, None)
    controller.hass.states.values["sensor.brightness"] = "17000"
    assert controller._shading_end_conditions(180, 40, None)


def test_temperature_hysteresis_delays_end() -> None:
    controller = _controller(SHADING_MODE_OUTSIDE)
    controller.hass.states.values["sensor.outside"] = "23"
    assert not controller._shading_end_conditions(180, 40, None)
    controller.hass.states.values["sensor.outside"] = "22"
    assert controller._shading_end_conditions(180, 40, None)


def test_reality_outside_direction_starts_and_ends_with_sun() -> None:
    controller = _controller(SHADING_MODE_OUTSIDE_DIRECTION)
    assert controller._shading_start_conditions(180, 40, None)[0]
    assert controller._shading_end_conditions(250, 40, None)


def test_reality_inside_outside_ends_below_hysteresis() -> None:
    controller = _controller(SHADING_MODE_INSIDE_OUTSIDE, brightness_sensor=True)
    assert controller._shading_start_conditions(180, 40, None)[0]
    controller.hass.states.values["sensor.outside"] = "20"
    assert controller._shading_end_conditions(180, 40, None)


@pytest.mark.parametrize(
    ("sleeping", "allow_shading", "blocked"),
    [(True, False, True), (True, True, False), (False, False, False)],
)
def test_resident_allows_or_blocks_shading(
    sleeping: bool, allow_shading: bool, blocked: bool
) -> None:
    assert CoverController._resident_blocks_shading(sleeping, allow_shading) is blocked


def test_keep_sun_protection_preserves_existing_behavior() -> None:
    controller = _controller(SHADING_MODE_DIRECTION)
    controller.config[CONF_OPEN_POSITION] = 100
    controller.config[CONF_KEEP_SUN_PROTECTION] = True

    assert controller._shading_end_open_target() is None
    controller.config[CONF_KEEP_SUN_PROTECTION] = False
    assert controller._shading_end_open_target() == 100


def test_resident_behavior_unchanged_after_cca_cleanup() -> None:
    assert CoverController._resident_blocks_shading(True, False)
    assert not CoverController._resident_blocks_shading(True, True)
