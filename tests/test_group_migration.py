"""Migration coverage from free profiles to fixed groups."""
import pytest
from homeassistant.helpers import issue_registry as ir
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
    assert controller.version == room.version == 14
    assert set(controller.data[CONF_GROUPS]) == set(GROUPS)
    assert room.data[CONF_GROUP] == GROUP_SLEEP
    assert "profile_id" not in room.data
    assert room.data[CONF_ROOM_SETTINGS][CONF_ENABLE_RECALIBRATE_BUTTON] is True


def _fixed_groups_with_sun(mode: str) -> dict:
    return {
        CONF_GROUPS: {
            GROUP_LIVING: {
                "sun_elevation_mode": mode,
                CONF_SUN_ELEVATION_OPEN: 5,
                CONF_SUN_ELEVATION_CLOSE: -3,
                "sun_elevation_dynamic_open_sensor": "sensor.open",
                "sun_elevation_dynamic_close_sensor": "sensor.close",
                "use_sun_elevation_dynamic_open_sensor": True,
                "use_sun_elevation_dynamic_close_sensor": True,
                "sun_time_duration": 30,
                "brightness_sun_operator": "and",
            },
            GROUP_SLEEP: {"sun_elevation_mode": "fixed"},
            GROUP_CHILDREN: {"sun_elevation_mode": "fixed"},
        }
    }


def test_migrate_fixed_sun_mode() -> None:
    model, warnings = migrate_profile_model(_fixed_groups_with_sun("fixed"))
    living = model[CONF_GROUPS][GROUP_LIVING]
    assert living[CONF_OPEN_MODE] == living[CONF_CLOSE_MODE] == MODE_ELEVATION
    assert living[CONF_SUN_ELEVATION_OPEN] == 5
    assert living[CONF_SUN_ELEVATION_CLOSE] == -3
    assert not warnings


@pytest.mark.parametrize("legacy_mode", ["dynamic", "hybrid"])
def test_migrate_removed_sun_mode_to_elevation(legacy_mode: str) -> None:
    model, warnings = migrate_profile_model(_fixed_groups_with_sun(legacy_mode))
    living = model[CONF_GROUPS][GROUP_LIVING]
    assert living[CONF_OPEN_MODE] == living[CONF_CLOSE_MODE] == MODE_ELEVATION
    assert living[CONF_SUN_ELEVATION_OPEN] == 5
    assert living[CONF_SUN_ELEVATION_CLOSE] == -3
    assert warnings == [
        "living: dynamic sun elevation was replaced by fixed elevation"
    ]
    assert not any("dynamic" in key or key in {"sun_time_duration", "brightness_sun_operator"} for key in living)


def test_migration_preserves_group_specific_thresholds() -> None:
    source = _fixed_groups_with_sun("dynamic")
    source[CONF_GROUPS][GROUP_SLEEP][CONF_SUN_ELEVATION_OPEN] = 8
    source[CONF_GROUPS][GROUP_CHILDREN][CONF_SUN_ELEVATION_CLOSE] = -7
    model, _ = migrate_profile_model(source)
    assert model[CONF_GROUPS][GROUP_LIVING][CONF_SUN_ELEVATION_OPEN] == 5
    assert model[CONF_GROUPS][GROUP_SLEEP][CONF_SUN_ELEVATION_OPEN] == 8
    assert model[CONF_GROUPS][GROUP_CHILDREN][CONF_SUN_ELEVATION_CLOSE] == -7


async def test_migration_warns_for_removed_dynamic_mode(hass) -> None:
    controller = MockConfigEntry(
        domain=DOMAIN,
        version=13,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER,
            CONF_GLOBAL: {CONF_GLOBAL_SOURCES: {}, CONF_GLOBAL_DEFAULTS: {}},
            **_fixed_groups_with_sun("dynamic"),
        },
    )
    controller.add_to_hass(hass)
    assert await async_migrate_entry(hass, controller)
    assert controller.version == 14
    assert (DOMAIN, "sun_mode_migration") in ir.async_get(hass).issues
