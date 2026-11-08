"""Fixed-group data model, resolver, and reality tests."""
import pytest
from custom_components.cover_control.config_groups import ConfigGroupModel
from custom_components.cover_control.config_resolver import resolve_config_model
from custom_components.cover_control.runtime.manager import ControllerManager
from custom_components.cover_control.const import (
    CONF_AUTO_TIME, CONF_CLOSE_MODE, CONF_ENABLE_RECALIBRATE_BUTTON, CONF_FIRE_ALARM_ENABLED,
    CONF_FIRE_ALARM_PARTICIPATE, CONF_GROUP, CONF_GROUPS, CONF_NAME, CONF_OPEN_POSITION,
    CONF_OPEN_MODE, CONF_RESIDENT_STATUS, CONF_ROOM_SETTINGS, CONF_ROOMS,
    CONF_TIME_UP_EARLY_WORKDAY, DEFAULT_GROUP, GROUP_CHILDREN, GROUP_LIVING,
    GROUP_SLEEP, GROUPS, MODE_GOLDEN_HOUR, MODE_SUNSET,
)

def _model() -> ConfigGroupModel:
    return ConfigGroupModel({
        CONF_GROUPS: {
            GROUP_LIVING: {CONF_TIME_UP_EARLY_WORKDAY: "06:00:00", CONF_AUTO_TIME: True},
            GROUP_SLEEP: {CONF_TIME_UP_EARLY_WORKDAY: "07:00:00", CONF_RESIDENT_STATUS: True},
            GROUP_CHILDREN: {CONF_TIME_UP_EARLY_WORKDAY: "08:00:00", CONF_FIRE_ALARM_ENABLED: True},
        },
        CONF_ROOMS: {
            "living": {CONF_NAME: "Wohnzimmer", CONF_GROUP: GROUP_LIVING, CONF_ROOM_SETTINGS: {}},
            "sleep": {CONF_NAME: "Schlafzimmer", CONF_GROUP: GROUP_SLEEP, CONF_ROOM_SETTINGS: {}},
            "children": {CONF_NAME: "Kinderzimmer", CONF_GROUP: GROUP_CHILDREN, CONF_ROOM_SETTINGS: {}},
        },
    })

def test_controller_has_three_fixed_groups() -> None:
    assert tuple(_model().data[CONF_GROUPS]) == GROUPS

def test_groups_cannot_be_created_or_deleted() -> None:
    model = ConfigGroupModel({CONF_GROUPS: {"custom": {}, GROUP_SLEEP: {}}, CONF_ROOMS: {}})
    assert set(model.data[CONF_GROUPS]) == set(GROUPS)

def test_room_has_exactly_one_group() -> None:
    room = _model().data[CONF_ROOMS]["living"]
    assert room[CONF_GROUP] == GROUP_LIVING
    assert "profile_id" not in room and "profile_functions" not in room

def test_room_defaults_to_living_group() -> None:
    model = ConfigGroupModel({CONF_ROOMS: {"room": {CONF_ROOM_SETTINGS: {}}}})
    assert model.data[CONF_ROOMS]["room"][CONF_GROUP] == DEFAULT_GROUP

def test_room_group_change_updates_effective_config() -> None:
    model = _model().data
    assert resolve_config_model(model, "living")[CONF_TIME_UP_EARLY_WORKDAY] == "06:00:00"
    model[CONF_ROOMS]["living"][CONF_GROUP] = GROUP_SLEEP
    resolved = resolve_config_model(model, "living")
    assert resolved[CONF_TIME_UP_EARLY_WORKDAY] == "07:00:00"
    assert resolved.group == GROUP_SLEEP

def test_reality_rooms_use_only_their_group() -> None:
    model = _model().data
    assert [resolve_config_model(model, room)[CONF_TIME_UP_EARLY_WORKDAY] for room in ("living", "sleep", "children")] == ["06:00:00", "07:00:00", "08:00:00"]

@pytest.mark.parametrize(("room", "expected"), [("living", "06:00:00"), ("sleep", "07:00:00"), ("children", "08:00:00")])
def test_group_settings_reach_room_runtime(room, expected) -> None:
    assert resolve_config_model(_model().data, room)[CONF_TIME_UP_EARLY_WORKDAY] == expected

def test_room_owned_values_override_group_and_remain_local() -> None:
    model = _model().data
    model[CONF_ROOMS]["living"][CONF_ROOM_SETTINGS].update({
        CONF_OPEN_POSITION: 77,
        CONF_ENABLE_RECALIBRATE_BUTTON: True,
        CONF_FIRE_ALARM_PARTICIPATE: False,
    })
    resolved = resolve_config_model(model, "living")
    assert resolved[CONF_OPEN_POSITION] == 77
    assert resolved[CONF_ENABLE_RECALIBRATE_BUTTON] is True
    assert resolved[CONF_FIRE_ALARM_PARTICIPATE] is False


def test_configuration_diagnostics_expose_control_modes() -> None:
    model = _model().data
    model[CONF_GROUPS][GROUP_LIVING].update(
        {CONF_OPEN_MODE: MODE_GOLDEN_HOUR, CONF_CLOSE_MODE: MODE_SUNSET}
    )
    manager = object.__new__(ControllerManager)
    manager._resolved_config = resolve_config_model(model, "living")
    manager._config_model = model
    manager._runtime_toggles = {}
    diagnostics = manager.configuration_diagnostics()
    assert diagnostics["resolved"][CONF_OPEN_MODE]["value"] == MODE_GOLDEN_HOUR
    assert diagnostics["resolved"][CONF_CLOSE_MODE]["value"] == MODE_SUNSET
