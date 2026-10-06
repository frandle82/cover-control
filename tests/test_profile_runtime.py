"""Tests for profile dependency updates, event routes, and timer refreshes."""

from types import SimpleNamespace
from unittest.mock import Mock
from datetime import datetime, timedelta, UTC

from custom_components.cover_control.config_profiles import ConfigProfileModel
from custom_components.cover_control.const import (
    CONF_AUTO_BRIGHTNESS,
    CONF_BRIGHTNESS_SENSOR,
    CONF_CONFIG_VERSION,
    CONF_GLOBAL,
    CONF_GLOBAL_DEFAULTS,
    CONF_GLOBAL_SOURCES,
    CONF_NAME,
    CONF_PROFILE_FUNCTIONS,
    CONF_PROFILE_ID,
    CONF_PROFILE_NAME,
    CONF_PROFILE_SETTINGS,
    CONF_PROFILES,
    CONF_ROOM_PROFILE_ID,
    CONF_ROOM_OVERRIDES,
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
    CONF_SHADING_WAITINGTIME_END,
    CONF_SOURCE_OVERRIDES,
    CONFIG_MODEL_VERSION,
    FUNCTION_SHADING,
    FUNCTION_TIME,
    PROFILE_TYPE_SHADING,
)
from custom_components.cover_control.runtime.controller import CoverController
from custom_components.cover_control.runtime.manager import ControllerManager
from custom_components.cover_control.config_resolver import resolve_config_model
from custom_components.cover_control.sensor import _profile_time_selected_by_any_room


def _model() -> ConfigProfileModel:
    return ConfigProfileModel(
        {
            CONF_CONFIG_VERSION: CONFIG_MODEL_VERSION,
            CONF_GLOBAL: {
                CONF_GLOBAL_SOURCES: {
                    CONF_BRIGHTNESS_SENSOR: "sensor.global_brightness"
                },
                CONF_GLOBAL_DEFAULTS: {},
            },
            CONF_PROFILES: {
                "south": {
                    CONF_PROFILE_ID: "south",
                    CONF_PROFILE_NAME: "South",
                    CONF_PROFILE_SETTINGS: {
                        CONF_SHADING_WAITINGTIME_END: 60,
                    },
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_SHADING],
                },
            },
            CONF_ROOMS: {
                "living": {
                    CONF_NAME: "Living",
                    CONF_ROOM_PROFILE_ID: "south",
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_SHADING],
                    CONF_ROOM_SETTINGS: {},
                    CONF_SOURCE_OVERRIDES: {},
                },
                "office": {
                    CONF_NAME: "Office",
                    CONF_ROOM_PROFILE_ID: "south",
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_SHADING],
                    CONF_ROOM_SETTINGS: {},
                    CONF_SOURCE_OVERRIDES: {},
                },
            },
        }
    )


def _manager() -> ControllerManager:
    manager = object.__new__(ControllerManager)
    manager.entry = SimpleNamespace(entry_id="living", data={})
    manager.controllers = {"cover.living": Mock()}
    manager._config_model = {}
    manager._resolved_config = None
    manager.profile_users = {}
    manager._setup_shared_listener = Mock()
    return manager


def test_profile_change_updates_only_affected_runtime_room() -> None:
    model = _model()
    model.data[CONF_ROOMS]["living"].pop(CONF_ROOM_PROFILE_ID)
    model.data[CONF_ROOMS]["living"][CONF_PROFILE_FUNCTIONS] = []
    manager = _manager()

    model.data[CONF_PROFILES]["south"][CONF_PROFILE_SETTINGS][
        CONF_SHADING_WAITINGTIME_END
    ] = 90
    affected = set(model.profile_users.get(("profile", "south"), set()))
    applied = manager.apply_config_model(model.data, affected)

    assert applied == set()
    manager.controllers["cover.living"].update_config.assert_not_called()
    assert manager.profile_users[("profile", "south")] == {"office"}


def test_profile_change_refreshes_config_listeners_and_timers() -> None:
    model = _model()
    manager = _manager()

    model.data[CONF_PROFILES]["south"][CONF_PROFILE_SETTINGS][
        CONF_SHADING_WAITINGTIME_END
    ] = 90
    affected = set(model.profile_users.get(("profile", "south"), set()))
    applied = manager.apply_config_model(model.data, affected)

    assert applied == {"living"}
    resolved = manager.controllers["cover.living"].update_config.call_args.args[0]
    assert resolved[CONF_SHADING_WAITINGTIME_END] == 90
    manager._setup_shared_listener.assert_called_once_with()


def test_room_source_override_changes_only_its_effective_route() -> None:
    model = _model()
    model.set_source_override(
        "living", CONF_BRIGHTNESS_SENSOR, "sensor.living_brightness"
    )

    living = resolve_config_model(model.data, "living")
    office = resolve_config_model(model.data, "office")
    assert living[CONF_BRIGHTNESS_SENSOR] == "sensor.living_brightness"
    assert office[CONF_BRIGHTNESS_SENSOR] == "sensor.global_brightness"


def test_config_update_clears_pending_timers_before_rescheduling() -> None:
    controller = object.__new__(CoverController)
    controller.config = {}
    controller._resubscribe_local_decision_entities = Mock()
    controller._clear_runtime_condition_timers = Mock()
    controller._clear_manual_expiry = Mock()
    controller._hydrate_persistent_status = Mock()
    controller._target = 1
    controller._last_position = 1
    controller._refresh_next_events = Mock()
    controller._schedule_manual_expiry = Mock()
    controller.persist_status = Mock()
    controller.async_request_evaluate = Mock()
    controller._publish_state = Mock()

    controller.update_config({CONF_AUTO_BRIGHTNESS: True})

    controller._clear_runtime_condition_timers.assert_called_once_with()
    controller._refresh_next_events.assert_called_once()
    controller.async_request_evaluate.assert_called_once_with("config")


def test_profile_waiting_time_reschedules_existing_pending_timer() -> None:
    controller = object.__new__(CoverController)
    now = datetime.now(UTC)
    original_due = now + timedelta(seconds=300)
    controller.config = {CONF_SHADING_WAITINGTIME_END: 600}
    controller._shading_pending = {"end": original_due}
    controller._resubscribe_local_decision_entities = Mock()
    controller._clear_runtime_condition_timers = Mock(
        side_effect=lambda: controller._shading_pending.clear()
    )
    controller._clear_manual_expiry = Mock()
    controller._hydrate_persistent_status = Mock()
    controller._target = 1
    controller._last_position = 1
    controller._set_shading_pending = Mock()
    controller._refresh_next_events = Mock()
    controller._schedule_manual_expiry = Mock()
    controller.persist_status = Mock()
    controller.async_request_evaluate = Mock()
    controller._publish_state = Mock()

    controller.update_config({CONF_SHADING_WAITINGTIME_END: 900})

    rescheduled = controller._set_shading_pending.call_args.args[1]
    assert rescheduled == original_due + timedelta(seconds=300)


def test_configuration_diagnostics_expose_profile_and_value_origin() -> None:
    model = _model()
    model.data[CONF_PROFILES]["south"][CONF_PROFILE_NAME] = "South standard"
    model.data[CONF_PROFILES]["south"][CONF_PROFILE_FUNCTIONS] = [
        FUNCTION_TIME,
        FUNCTION_SHADING,
    ]
    model.data[CONF_ROOMS]["living"][CONF_PROFILE_FUNCTIONS] = [FUNCTION_SHADING]
    model.data[CONF_PROFILES]["south"][CONF_PROFILE_SETTINGS][
        CONF_SHADING_WAITINGTIME_END
    ] = 600
    model.data[CONF_ROOMS]["living"][CONF_ROOM_SETTINGS][
        CONF_SHADING_WAITINGTIME_END
    ] = 300
    manager = object.__new__(ControllerManager)
    manager._config_model = model.data
    manager._resolved_config = resolve_config_model(model.data, "living")
    manager._runtime_toggles = {}

    diagnostics = manager.configuration_diagnostics()

    assert diagnostics["room_name"] == "Living"
    assert diagnostics["profile_id"] == "south"
    assert diagnostics["profiles"]["profile"] == "South standard"
    assert diagnostics["selected_profile_functions"] == [FUNCTION_SHADING]
    assert diagnostics["configured_functions"] == [FUNCTION_SHADING]
    assert diagnostics["resolved"][CONF_SHADING_WAITINGTIME_END] == {
        "value": 300,
        "source": "room_setting",
        "source_name": "Room setting",
    }


def test_profile_time_sensor_requires_room_selected_time_function() -> None:
    model = _model()
    model.data[CONF_PROFILES]["south"][CONF_PROFILE_FUNCTIONS] = [
        FUNCTION_TIME,
        FUNCTION_SHADING,
    ]
    model.data[CONF_PROFILES]["south"][CONF_PROFILE_SETTINGS]["auto_time_enabled"] = True
    model.data[CONF_ROOMS]["living"][CONF_PROFILE_FUNCTIONS] = [FUNCTION_SHADING]
    model.data[CONF_ROOMS]["office"][CONF_PROFILE_FUNCTIONS] = [FUNCTION_SHADING]

    assert not _profile_time_selected_by_any_room(model.data, "south")

    model.data[CONF_ROOMS]["office"][CONF_PROFILE_FUNCTIONS] = [FUNCTION_TIME]

    assert _profile_time_selected_by_any_room(model.data, "south")
