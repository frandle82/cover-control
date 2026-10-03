"""Regression tests for dynamic decision-entity subscriptions."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from custom_components.cover_control.const import (
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_SHADING,
    CONF_AUTO_VENTILATE,
    CONF_BRIGHTNESS_SENSOR,
    CONF_CUSTOM_POSITION_SENSOR,
    CONF_POSITION_SOURCE,
    CONF_POSITION_SOURCE_CUSTOM_SENSOR,
    CONF_WINDOW_SENSOR_TILT,
)
from custom_components.cover_control.controller import ControllerManager, CoverController


def _local_controller(config: dict) -> CoverController:
    controller = object.__new__(CoverController)
    controller.hass = object()
    controller.cover = "cover.test"
    controller.config = config
    controller._auto_entity_map = {}
    controller._local_listener_unsubs = {}
    controller._local_listener_entities = set()
    controller._handle_state_event = Mock()
    controller._auto_enabled = lambda key: bool(controller.config.get(key, False))
    return controller


def test_window_listener_rebinds_after_config_change() -> None:
    controller = _local_controller(
        {
            CONF_AUTO_VENTILATE: True,
            CONF_WINDOW_SENSOR_TILT: {"cover.test": ["binary_sensor.old_window"]},
        }
    )
    unsubs: dict[str, Mock] = {}

    def _track(_hass, entity_ids, _callback):
        entity_id = entity_ids[0]
        unsubs[entity_id] = Mock()
        return unsubs[entity_id]

    with patch(
        "custom_components.cover_control.runtime.events.async_track_state_change_event",
        side_effect=_track,
    ):
        controller._resubscribe_local_decision_entities()
        controller.config = {
            CONF_AUTO_VENTILATE: True,
            CONF_WINDOW_SENSOR_TILT: {"cover.test": ["binary_sensor.new_window"]},
        }
        controller._resubscribe_local_decision_entities()

    unsubs["binary_sensor.old_window"].assert_called_once_with()
    assert "binary_sensor.old_window" not in controller._local_listener_entities
    assert "binary_sensor.new_window" in controller._local_listener_entities
    assert not unsubs["cover.test"].called


def test_custom_position_listener_rebinds_after_config_change() -> None:
    controller = _local_controller(
        {
            CONF_POSITION_SOURCE: CONF_POSITION_SOURCE_CUSTOM_SENSOR,
            CONF_CUSTOM_POSITION_SENSOR: "sensor.old_position",
        }
    )
    unsubs: dict[str, Mock] = {}

    def _track(_hass, entity_ids, _callback):
        entity_id = entity_ids[0]
        unsubs[entity_id] = Mock()
        return unsubs[entity_id]

    with patch(
        "custom_components.cover_control.runtime.events.async_track_state_change_event",
        side_effect=_track,
    ):
        controller._resubscribe_local_decision_entities()
        controller.config = {
            CONF_POSITION_SOURCE: CONF_POSITION_SOURCE_CUSTOM_SENSOR,
            CONF_CUSTOM_POSITION_SENSOR: "sensor.new_position",
        }
        controller._resubscribe_local_decision_entities()

    unsubs["sensor.old_position"].assert_called_once_with()
    assert controller._local_listener_entities == {
        "cover.test",
        "sensor.new_position",
    }


def _toggle_manager() -> tuple[ControllerManager, Mock]:
    manager = object.__new__(ControllerManager)
    manager.hass = SimpleNamespace(data={})
    manager._runtime_toggles = {}
    manager._shared_listener_unsub = None
    manager._shared_entities = set()
    manager._entity_routes = {}
    controller = Mock()
    controller.cover = "cover.test"
    controller.async_request_evaluate = Mock()

    def _entities():
        if manager._runtime_toggles.get(CONF_AUTO_BRIGHTNESS, False) or manager._runtime_toggles.get(
            CONF_AUTO_SHADING, False
        ):
            return {"sensor.brightness"}
        return set()

    controller._shared_decision_entities.side_effect = _entities
    manager.controllers = {controller.cover: controller}
    return manager, controller


def test_brightness_toggle_adds_and_removes_shared_listener() -> None:
    manager, controller = _toggle_manager()
    unsubs = []

    def _track(_hass, entities, _callback):
        assert entities == ["sensor.brightness"]
        unsubscribe = Mock()
        unsubs.append(unsubscribe)
        return unsubscribe

    with patch(
        "custom_components.cover_control.runtime.manager.async_track_state_change_event",
        side_effect=_track,
    ):
        manager.set_runtime_toggle(CONF_AUTO_BRIGHTNESS, True)
        assert manager._entity_routes == {"sensor.brightness": {"cover.test"}}
        manager.set_runtime_toggle(CONF_AUTO_BRIGHTNESS, False)

    unsubs[0].assert_called_once_with()
    assert manager._shared_entities == set()
    assert manager._entity_routes == {}
    assert controller.async_request_evaluate.call_count == 2


def test_shared_entity_remains_while_another_feature_needs_it() -> None:
    manager, _controller = _toggle_manager()
    unsubscribe = Mock()

    with patch(
        "custom_components.cover_control.runtime.manager.async_track_state_change_event",
        return_value=unsubscribe,
    ) as track:
        manager.set_runtime_toggle(CONF_AUTO_BRIGHTNESS, True)
        manager.set_runtime_toggle(CONF_AUTO_SHADING, True)
        manager.set_runtime_toggle(CONF_AUTO_BRIGHTNESS, False)

    track.assert_called_once()
    unsubscribe.assert_not_called()
    assert manager._shared_entities == {"sensor.brightness"}
