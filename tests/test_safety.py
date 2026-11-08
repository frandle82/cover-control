"""Regression tests for alarm priority and persistent fire safety."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cover_control import button
from custom_components.cover_control.const import (
    CONF_COVERS,
    CONF_ENTRY_TYPE,
    CONF_FIRE_ALARM_ENTITY,
    CONF_GLOBAL,
    CONF_GLOBAL_DEFAULTS,
    CONF_GLOBAL_SOURCES,
    CONF_HEAT_PROTECTION_ENABLED,
    CONF_HEAT_PROTECTION_THRESHOLD,
    CONF_NAME,
    CONF_PROFILE_FUNCTIONS,
    CONF_PROFILE_ID,
    CONF_PROFILE_NAME,
    CONF_PROFILE_SETTINGS,
    CONF_PROFILES,
    CONF_ROOM_PROFILE_ID,
    CONF_ROOM_SETTINGS,
    CONF_SHADING_TEMPERATURE_SENSOR_2,
    CONF_ROOMS,
    DOMAIN,
    ENTRY_TYPE_CONTROLLER,
    FUNCTION_SAFETY,
    SAFETY_ALARMS,
)
from custom_components.cover_control.config_resolver import resolve_config_model
from custom_components.cover_control.runtime.common import _normalize_cover_status
from custom_components.cover_control.runtime.controller import CoverController
from custom_components.cover_control.runtime.manager import (
    ControllerManager,
    _controls_for_reason,
)
from custom_components.cover_control.runtime_data import CoverControlRuntime


class SafetyConfig(dict):
    configured_functions = frozenset({FUNCTION_SAFETY})


def _safety_values() -> SafetyConfig:
    values = SafetyConfig()
    for alarm, entity_key, enabled_key, target_key, room_key, default in SAFETY_ALARMS:
        values.update(
            {
                entity_key: f"binary_sensor.{alarm}",
                enabled_key: True,
                target_key: default,
                room_key: True,
            }
        )
    return values


def _controller(states: dict[str, str], persisted: object = None) -> CoverController:
    controller = object.__new__(CoverController)
    controller.config = _safety_values()
    controller.hass = SimpleNamespace(
        states=SimpleNamespace(
            get=lambda entity_id: SimpleNamespace(
                state=states.get(entity_id, "off"), attributes={}
            )
        )
    )
    controller._evaluation_context = None
    controller._auto_entity_map = {}
    controller._status = _normalize_cover_status(persisted)
    controller._decision_controls = set()
    controller._active_safety = None
    controller._safety_target = None
    controller._reason = None
    controller._set_position = AsyncMock()
    controller._publish_state = Mock()
    controller.persist_status = Mock()
    controller._position_value = Mock(return_value=0)
    controller._position_matches = Mock(return_value=False)
    controller._current_position = Mock(return_value=100)
    return controller


def test_fire_alarm_has_highest_priority() -> None:
    controller = _controller(
        {
            "binary_sensor.fire": "on",
            "binary_sensor.rain": "on",
            "binary_sensor.wind_alarm_2": "on",
        }
    )
    assert controller._active_safety_alarm() == ("fire", 100)


def test_rain_beats_wind_and_frost() -> None:
    controller = _controller(
        {
            "binary_sensor.rain": "on",
            "binary_sensor.wind_alarm_2": "on",
            "binary_sensor.wind_alarm_1": "on",
            "binary_sensor.frost": "on",
        }
    )
    assert controller._active_safety_alarm() == ("rain", 100)


def test_wind2_beats_wind1_and_frost() -> None:
    controller = _controller(
        {
            "binary_sensor.wind_alarm_2": "on",
            "binary_sensor.wind_alarm_1": "on",
            "binary_sensor.frost": "on",
        }
    )
    assert controller._active_safety_alarm() == ("wind_alarm_2", 100)


def test_wind1_beats_frost() -> None:
    controller = _controller(
        {"binary_sensor.wind_alarm_1": "on", "binary_sensor.frost": "on"}
    )
    assert controller._active_safety_alarm() == ("wind_alarm_1", 100)


def test_alarm_falls_back_to_next_active_priority() -> None:
    states = {
        "binary_sensor.rain": "on",
        "binary_sensor.wind_alarm_1": "on",
    }
    controller = _controller(states)
    assert controller._active_safety_alarm()[0] == "rain"
    states["binary_sensor.rain"] = "off"
    assert controller._active_safety_alarm()[0] == "wind_alarm_1"


@pytest.mark.parametrize(
    ("entity_id", "trigger"),
    [
        ("binary_sensor.fire", "fire_alarm"),
        ("binary_sensor.rain", "rain_alarm"),
        ("binary_sensor.wind_alarm_2", "wind_alarm_2"),
        ("binary_sensor.wind_alarm_1", "wind_alarm_1"),
        ("binary_sensor.frost", "frost_alarm"),
    ],
)
def test_safety_sources_use_unique_on_off_triggers(
    entity_id: str, trigger: str
) -> None:
    controller = _controller({})
    assert controller._shared_state_triggers(entity_id, "off", "on") == {
        f"{trigger}_on"
    }
    assert controller._shared_state_triggers(entity_id, "on", "off") == {
        f"{trigger}_off"
    }


@pytest.mark.asyncio
async def test_fire_alarm_sets_latch() -> None:
    controller = _controller({"binary_sensor.fire": "on"})
    assert await controller._evaluate_safety()
    assert controller.fire_latched()
    controller._set_position.assert_awaited_once_with(100, "fire_alarm")


@pytest.mark.asyncio
async def test_fire_active_at_startup_preempts_normal_runtime() -> None:
    controller = _controller({"binary_sensor.fire": "on"})
    assert await controller._evaluate_safety()
    assert controller._active_safety == "fire"


@pytest.mark.asyncio
async def test_rain_active_at_startup_preempts_normal_runtime() -> None:
    controller = _controller({"binary_sensor.rain": "on"})
    assert await controller._evaluate_safety()
    assert controller._active_safety == "rain"


@pytest.mark.asyncio
async def test_multiple_alarms_at_startup_use_highest_priority() -> None:
    controller = _controller(
        {"binary_sensor.rain": "on", "binary_sensor.wind_alarm_2": "on"}
    )
    assert await controller._evaluate_safety()
    assert controller._active_safety == "rain"


@pytest.mark.asyncio
async def test_lower_unavailable_alarm_does_not_block_active_higher_alarm() -> None:
    controller = _controller(
        {"binary_sensor.rain": "on", "binary_sensor.frost": "unavailable"}
    )
    assert await controller._evaluate_safety()
    assert controller._active_safety == "rain"


@pytest.mark.asyncio
async def test_fire_latch_survives_sensor_off() -> None:
    states = {"binary_sensor.fire": "on"}
    controller = _controller(states)
    await controller._evaluate_safety()
    states["binary_sensor.fire"] = "off"
    controller._set_position.reset_mock()
    assert await controller._evaluate_safety()
    assert controller._reason == "fire_latched"
    controller._set_position.assert_not_awaited()


def test_fire_latch_survives_restart() -> None:
    controller = _controller(
        {"binary_sensor.fire": "off"},
        {"safety": {"fire_latched": True, "ts": 1}},
    )
    assert controller.fire_latched()


def test_fire_latch_reset_requires_inactive_fire_sensor() -> None:
    controller = _controller(
        {"binary_sensor.fire": "on"},
        {"safety": {"fire_latched": True, "ts": 1}},
    )
    assert not controller.reset_fire_latch()
    assert controller.fire_latched()


def test_fire_latch_reset_reenables_normal_evaluation() -> None:
    controller = _controller(
        {"binary_sensor.fire": "off"},
        {"safety": {"fire_latched": True, "ts": 1}},
    )
    assert controller.reset_fire_latch()
    assert not controller.fire_latched()


async def _assert_alarm_moves(alarm: str, reason: str) -> None:
    controller = _controller({f"binary_sensor.{alarm}": "on"})
    assert await controller._evaluate_safety()
    controller._set_position.assert_awaited_once_with(100, reason)


@pytest.mark.asyncio
async def test_rain_alarm_moves_to_configured_position() -> None:
    await _assert_alarm_moves("rain", "rain_alarm")


@pytest.mark.asyncio
async def test_wind1_alarm_moves_to_configured_position() -> None:
    await _assert_alarm_moves("wind_alarm_1", "wind_alarm_1")


@pytest.mark.asyncio
async def test_wind2_alarm_moves_to_configured_position() -> None:
    await _assert_alarm_moves("wind_alarm_2", "wind_alarm_2")


@pytest.mark.parametrize("close_reason", ["scheduled_close", "final_close"])
@pytest.mark.asyncio
async def test_frost_wins_over_christmas_close_targets(close_reason: str) -> None:
    """Frost clamps both Christmas schedule paths to the safer target."""

    controller = _controller({"binary_sensor.frost": "on"})
    assert not await controller._evaluate_safety()
    controller._set_position.assert_not_awaited()

    controller._position_matches.return_value = True
    assert await controller._evaluate_safety()
    controller._set_position.assert_awaited_once_with(80, "frost_alarm")

    controller._position_matches.return_value = False
    controller._set_position = CoverController._set_position.__get__(controller)
    controller._group_position_callback = None
    controller._set_position_local = AsyncMock()
    await controller._set_position(25, close_reason)
    controller._set_position_local.assert_awaited_once_with(80, "frost_alarm")


async def _assert_safety_blocks_normal_action(test_name: str) -> None:
    controller = _controller({"binary_sensor.rain": "on"})
    assert await controller._evaluate_safety(), test_name


@pytest.mark.asyncio
async def test_safety_blocks_normal_time_action() -> None:
    await _assert_safety_blocks_normal_action("time")


@pytest.mark.asyncio
async def test_safety_blocks_sun_action() -> None:
    await _assert_safety_blocks_normal_action("sun")


@pytest.mark.asyncio
async def test_safety_blocks_shading_action() -> None:
    await _assert_safety_blocks_normal_action("shading")


def _safety_model(target: int = 100) -> dict:
    settings = {}
    for _alarm, _entity, enabled, target_key, _room, default in SAFETY_ALARMS:
        settings[enabled] = True
        settings[target_key] = (
            target if target_key.endswith("fire_alarm_target") else default
        )
    return {
        CONF_GLOBAL: {
            CONF_GLOBAL_SOURCES: {
                entity_key: f"binary_sensor.{alarm}"
                for alarm, entity_key, *_rest in SAFETY_ALARMS
            },
            CONF_GLOBAL_DEFAULTS: {},
        },
        CONF_PROFILES: {
            "profile": {
                CONF_PROFILE_ID: "profile",
                CONF_PROFILE_NAME: "Safety",
                CONF_PROFILE_SETTINGS: settings,
                CONF_PROFILE_FUNCTIONS: [FUNCTION_SAFETY],
            }
        },
        CONF_ROOMS: {
            "living": {
                CONF_NAME: "Living",
                CONF_ROOM_PROFILE_ID: "profile",
                CONF_PROFILE_FUNCTIONS: [FUNCTION_SAFETY],
                CONF_ROOM_SETTINGS: {
                    CONF_COVERS: ["cover.living"],
                    **{room_key: True for *_head, room_key, _default in SAFETY_ALARMS},
                },
            }
        },
    }


def test_safety_profile_updates_loaded_rooms() -> None:
    manager = object.__new__(ControllerManager)
    manager.room_id = "living"
    manager.entry = SimpleNamespace(entry_id="entry", runtime_data=None)
    manager.controllers = {"cover.living": Mock()}
    manager._setup_shared_listener = Mock()
    manager.refresh_schedule_snapshot = Mock()
    manager._config_model = {}

    manager.apply_config_model(_safety_model(90))

    resolved = manager.controllers["cover.living"].update_config.call_args.args[0]
    assert resolved["fire_alarm_target"] == 90


def test_active_control_reports_safety_reason() -> None:
    assert _controls_for_reason("rain_alarm") == {"rain_alarm"}
    assert _controls_for_reason("fire_latched") == {"fire_latched"}


@pytest.mark.asyncio
async def test_safety_reality_sequence() -> None:
    states = {
        "binary_sensor.wind_alarm_1": "on",
        "binary_sensor.rain": "off",
        "binary_sensor.fire": "off",
    }
    controller = _controller(states)

    await controller._evaluate_safety()
    assert controller._active_safety == "wind_alarm_1"
    states["binary_sensor.rain"] = "on"
    await controller._evaluate_safety()
    assert controller._active_safety == "rain"
    states["binary_sensor.fire"] = "on"
    await controller._evaluate_safety()
    assert controller.fire_latched()
    states["binary_sensor.fire"] = "off"
    await controller._evaluate_safety()
    assert controller._active_safety == "fire_latched"
    assert controller.reset_fire_latch()
    await controller._evaluate_safety()
    assert controller._active_safety == "rain"
    states["binary_sensor.rain"] = "off"
    await controller._evaluate_safety()
    assert controller._active_safety == "wind_alarm_1"
    states["binary_sensor.wind_alarm_1"] = "off"
    assert not await controller._evaluate_safety()
    assert controller._active_safety is None


@pytest.mark.asyncio
async def test_safety_interrupts_window_down_sequence() -> None:
    controller = _controller({"binary_sensor.rain": "on"})
    controller._window_down_sequence = {"phase": "closing"}
    controller._delayed_evaluation_unsubs = {"window_down_sequence": Mock()}

    assert await controller._evaluate_safety()

    assert controller._window_down_sequence is None
    assert "window_down_sequence" not in controller._delayed_evaluation_unsubs


@pytest.mark.asyncio
async def test_heat_protection_does_not_override_safety() -> None:
    controller = _controller(
        {"binary_sensor.wind_alarm_1": "on", "sensor.outdoor": "35"}
    )
    controller.config.update(
        {
            CONF_HEAT_PROTECTION_ENABLED: True,
            CONF_HEAT_PROTECTION_THRESHOLD: 30,
            CONF_SHADING_TEMPERATURE_SENSOR_2: "sensor.outdoor",
        }
    )

    assert await controller._evaluate_safety()
    assert controller._active_safety == "wind_alarm_1"
    controller._set_position.assert_awaited_once_with(100, "wind_alarm_1")


@pytest.mark.asyncio
async def test_heat_protection_resumes_after_safety_when_still_valid() -> None:
    states = {"binary_sensor.wind_alarm_1": "on", "sensor.outdoor": "35"}
    controller = _controller(states)
    controller.config.update(
        {
            CONF_HEAT_PROTECTION_ENABLED: True,
            CONF_HEAT_PROTECTION_THRESHOLD: 30,
            CONF_SHADING_TEMPERATURE_SENSOR_2: "sensor.outdoor",
        }
    )
    await controller._evaluate_safety()

    states["binary_sensor.wind_alarm_1"] = "off"

    assert not await controller._evaluate_safety()
    assert controller._heat_protection_state()[0]


@pytest.mark.asyncio
async def test_config_entry_exposes_fire_latch_reset_button(hass) -> None:
    manager = Mock()
    manager._resolved_config = resolve_config_model(_safety_model(), "living")
    controller = Mock()
    controller.fire_latched.return_value = False
    manager.controllers = {"cover.living": controller}
    runtime = CoverControlRuntime(
        hub=Mock(), model=_safety_model(), room_managers={"living": manager}
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="controller",
        data={CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER},
    )
    entry.runtime_data = runtime
    entry.add_to_hass(hass)
    entities = []

    await button.async_setup_entry(hass, entry, entities.extend)

    reset = next(
        entity for entity in entities if entity.translation_key == "reset_fire_latch"
    )
    await reset.async_press()
    manager.reset_fire_latch.assert_called_once_with()
