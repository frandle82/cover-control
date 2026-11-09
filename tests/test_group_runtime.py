"""Runtime propagation and lifecycle tests for fixed groups."""
from types import SimpleNamespace
from unittest.mock import Mock
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service
from custom_components.cover_control.config_groups import ConfigGroupModel
from custom_components.cover_control.const import (
    CONF_GROUP, CONF_GROUPS, CONF_ROOMS, CONF_ROOM_SETTINGS,
    CONF_TIME_UP_EARLY_WORKDAY, GROUP_LIVING, GROUP_SLEEP,
    CONF_ENTRY_TYPE, CONF_GLOBAL, CONF_CONTROLLER_ENTRY_ID, CONF_ROOM_ID,
    CONF_NAME, CONF_COVERS, CONF_OPEN_POSITION, CONF_CLOSE_POSITION,
    CONF_SOURCE_OVERRIDES, DOMAIN, ENTRY_TYPE_CONTROLLER, ENTRY_TYPE_ROOM, GROUPS,
    CONF_SHADING_MODE, CONF_RESIDENT_SENSOR,
)
from custom_components.cover_control.runtime.manager import ControllerManager
from custom_components.cover_control.hub import CoverControlHub, GroupEvaluation
from datetime import datetime, timezone

def _model():
    return ConfigGroupModel({
        CONF_GROUPS: {
            GROUP_LIVING: {CONF_TIME_UP_EARLY_WORKDAY: "06:00:00"},
            GROUP_SLEEP: {CONF_TIME_UP_EARLY_WORKDAY: "08:00:00"},
        },
        CONF_ROOMS: {
            "living": {CONF_GROUP: GROUP_LIVING, CONF_ROOM_SETTINGS: {}},
            "sleep": {CONF_GROUP: GROUP_SLEEP, CONF_ROOM_SETTINGS: {}},
        },
    })

def _manager(room_id):
    manager = object.__new__(ControllerManager)
    manager.room_id = room_id
    manager.entry = SimpleNamespace(entry_id=room_id, runtime_data=None)
    manager.controllers = {f"cover.{room_id}": Mock()}
    manager._setup_shared_listener = Mock()
    manager.refresh_schedule_snapshot = Mock()
    manager._config_model = {}
    manager.group_users = {}
    return manager

def test_group_update_propagates_only_to_assigned_rooms() -> None:
    model = _model()
    living, sleep = _manager("living"), _manager("sleep")
    assert living.apply_config_model(model.data, {"living"}) == {"living"}
    assert sleep.apply_config_model(model.data, {"living"}) == set()
    sleep.controllers["cover.sleep"].update_config.assert_not_called()

def test_room_group_switch_rebuilds_runtime_without_stale_values() -> None:
    model = _model()
    manager = _manager("living")
    manager.apply_config_model(model.data, {"living"})
    first = manager.controllers["cover.living"].update_config.call_args.args[0]
    model.data[CONF_ROOMS]["living"][CONF_GROUP] = GROUP_SLEEP
    manager.apply_config_model(model.data, {"living"})
    second = manager.controllers["cover.living"].update_config.call_args.args[0]
    assert first[CONF_TIME_UP_EARLY_WORKDAY] == "06:00:00"
    assert second[CONF_TIME_UP_EARLY_WORKDAY] == "08:00:00"
    assert manager._setup_shared_listener.call_count == 2
    assert manager.refresh_schedule_snapshot.call_count == 2

def test_group_switch_rebuilds_listener_routes() -> None:
    manager = _manager("living")
    model = _model().data
    manager.apply_config_model(model, {"living"})
    model[CONF_ROOMS]["living"][CONF_GROUP] = GROUP_SLEEP
    manager.apply_config_model(model, {"living"})
    assert manager._setup_shared_listener.call_count == 2

def test_group_switch_clears_old_group_timer() -> None:
    hub = object.__new__(CoverControlHub)
    unsubscribe = Mock()
    due = datetime.now(timezone.utc)
    hub.group_evaluations = {GROUP_SLEEP: GroupEvaluation()}
    hub._group_timer_unsubs = {(GROUP_LIVING, "open"): unsubscribe}
    hub._group_timer_at = {(GROUP_LIVING, "open"): due}
    hub._reschedule_group_timers()
    unsubscribe.assert_called_once_with()
    assert hub._group_timer_unsubs == {}


def test_room_manager_snapshot_without_controllers() -> None:
    manager = object.__new__(ControllerManager)
    manager.controllers = {}
    manager.hass = SimpleNamespace(states=SimpleNamespace(get=Mock(return_value=None)))
    manager._resolved_config = SimpleNamespace(
        configured_functions=(),
        get=lambda key, default=None: {
            CONF_RESIDENT_SENSOR: "binary_sensor.resident",
            CONF_SHADING_MODE: "inside",
        }.get(key, default),
    )

    manager._rebuild_entry_snapshot()

    snapshot = manager.entry_snapshot()
    assert snapshot["covers"] == {}
    assert snapshot["shading_mode"] == "inside"
    assert snapshot["resident_status"] == "off"
    assert snapshot["next_open"] is None
    assert snapshot["next_close"] is None

async def test_controller_and_room_load_with_fixed_groups(hass) -> None:
    async_mock_service(hass, "cover", "set_cover_position")
    hass.states.async_set("cover.living", "open", {"current_position": 100})
    controller = MockConfigEntry(domain=DOMAIN, version=15, unique_id=DOMAIN, data={
        CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER,
        CONF_GLOBAL: {"sources": {}, "defaults": {}},
        CONF_GROUPS: {group: {} for group in GROUPS},
    })
    room = MockConfigEntry(domain=DOMAIN, version=15, data={
        CONF_ENTRY_TYPE: ENTRY_TYPE_ROOM,
        CONF_CONTROLLER_ENTRY_ID: controller.entry_id,
        CONF_ROOM_ID: "living",
        CONF_NAME: "Living",
        CONF_GROUP: GROUP_LIVING,
        CONF_ROOM_SETTINGS: {
            CONF_COVERS: ["cover.living"],
            CONF_OPEN_POSITION: 100,
            CONF_CLOSE_POSITION: 0,
        },
        CONF_SOURCE_OVERRIDES: {},
    })
    controller.add_to_hass(hass)
    room.add_to_hass(hass)
    assert await hass.config_entries.async_setup(controller.entry_id)
    await hass.async_block_till_done()
    if room.state is ConfigEntryState.NOT_LOADED:
        assert await hass.config_entries.async_setup(room.entry_id)
        await hass.async_block_till_done()
    assert "living" in room.runtime_data.room_managers
    assert room.runtime_data.room_managers["living"]._resolved_config.group == GROUP_LIVING
