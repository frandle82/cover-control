"""Migration coverage from free profiles to fixed groups."""
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.cover_control import async_migrate_entry
from custom_components.cover_control.config_migration import migrate_profile_model
from custom_components.cover_control.const import *  # noqa: F403

def _legacy(name: str, rooms: dict, settings: dict | None = None, extra_profiles: dict | None = None):
    profiles = {"selected": {"name": name, "settings": settings or {}}}
    profiles.update(extra_profiles or {})
    return {
        "profiles": profiles,
        CONF_ROOMS: {
            room_id: {CONF_NAME: room_name, "profile_id": profile_id, "profile_functions": ["time"], CONF_ROOM_SETTINGS: room_settings}
            for room_id, (room_name, profile_id, room_settings) in rooms.items()
        },
    }

@pytest.mark.parametrize(("name", "expected"), [("Living", GROUP_LIVING), ("Schlafzimmer", GROUP_SLEEP), ("Kinder", GROUP_CHILDREN)])
def test_migrate_named_profile(name, expected) -> None:
    model, _ = migrate_profile_model(_legacy(name, {"room": (name, "selected", {})}, {CONF_AUTO_TIME: True}))
    assert model[CONF_ROOMS]["room"][CONF_GROUP] == expected
    assert model[CONF_GROUPS][expected][CONF_AUTO_TIME] is True

def test_migrate_multiple_rooms_using_same_profile() -> None:
    model, _ = migrate_profile_model(_legacy("Sleep", {"a": ("A", "selected", {}), "b": ("B", "selected", {})}))
    assert {model[CONF_ROOMS][room][CONF_GROUP] for room in ("a", "b")} == {GROUP_SLEEP}

def test_migrate_multiple_profiles_deterministically() -> None:
    legacy = _legacy("Living A", {
        "a": ("Living A", "selected", {}), "b": ("Living B", "selected", {}), "c": ("Living C", "other", {})
    }, {CONF_AUTO_TIME: True}, {"other": {"name": "Living B", "settings": {CONF_AUTO_TIME: False}}})
    model, warnings = migrate_profile_model(legacy)
    assert model[CONF_GROUPS][GROUP_LIVING][CONF_AUTO_TIME] is True
    assert warnings

def test_migration_preserves_room_positions_safety_and_recalibrate() -> None:
    local = {CONF_OPEN_POSITION: 88, CONF_FIRE_ALARM_PARTICIPATE: False, CONF_ENABLE_RECALIBRATE_BUTTON: True}
    model, _ = migrate_profile_model(_legacy("Living", {"room": ("Room", "selected", local)}))
    assert model[CONF_ROOMS]["room"][CONF_ROOM_SETTINGS] == local

def test_migration_moves_historical_physical_profile_values_to_room() -> None:
    model, _ = migrate_profile_model(_legacy(
        "Living", {"room": ("Room", "selected", {})}, {CONF_OPEN_POSITION: 42}
    ))
    assert model[CONF_ROOMS]["room"][CONF_ROOM_SETTINGS][CONF_OPEN_POSITION] == 42
    assert CONF_OPEN_POSITION not in model[CONF_GROUPS][GROUP_LIVING]

def test_migration_preserves_resident_settings() -> None:
    model, _ = migrate_profile_model(_legacy("Children", {"room": ("Room", "selected", {})}, {CONF_RESIDENT_STATUS: True}))
    assert model[CONF_GROUPS][GROUP_CHILDREN][CONF_RESIDENT_STATUS] is True

def test_migration_removes_legacy_assignment_fields() -> None:
    model, _ = migrate_profile_model(_legacy("Living", {"room": ("Room", "selected", {})}))
    room = model[CONF_ROOMS]["room"]
    assert "profile_id" not in room and "profile_functions" not in room
    assert "profiles" not in model

async def test_entry_migration_updates_controller_and_rooms(hass) -> None:
    controller = MockConfigEntry(domain=DOMAIN, version=12, data={
        CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER,
        CONF_GLOBAL: {CONF_GLOBAL_SOURCES: {}, CONF_GLOBAL_DEFAULTS: {}},
        "profiles": {"sleep": {"name": "Sleep", "settings": {CONF_RESIDENT_STATUS: True}}},
    })
    room = MockConfigEntry(domain=DOMAIN, version=12, data={
        CONF_ENTRY_TYPE: ENTRY_TYPE_ROOM,
        CONF_CONTROLLER_ENTRY_ID: controller.entry_id,
        CONF_ROOM_ID: "bedroom",
        CONF_NAME: "Bedroom",
        "profile_id": "sleep",
        "profile_functions": ["resident"],
        CONF_ROOM_SETTINGS: {CONF_ENABLE_RECALIBRATE_BUTTON: True},
    })
    controller.add_to_hass(hass)
    room.add_to_hass(hass)
    assert await async_migrate_entry(hass, controller)
    assert controller.version == room.version == 13
    assert set(controller.data[CONF_GROUPS]) == set(GROUPS)
    assert room.data[CONF_GROUP] == GROUP_SLEEP
    assert "profile_id" not in room.data
    assert room.data[CONF_ROOM_SETTINGS][CONF_ENABLE_RECALIBRATE_BUTTON] is True
