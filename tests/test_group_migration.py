"""Migration coverage from free profiles to fixed groups."""
import pytest
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.cover_control import async_migrate_entry
from custom_components.cover_control.config_migration import cleanup_runtime_options, migrate_profile_model
from custom_components.cover_control.config_resolver import resolve_config_model
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


@pytest.mark.parametrize(
    ("stored", "expected"),
    [(-6, -6.0), ("-6.5", -6.5), ("-6,5", -6.5), ("00:00:00", -6.0), (None, -6.0)],
)
def test_legacy_time_elevation_value_is_normalized(stored, expected) -> None:
    source = {
        CONF_GROUPS: {
            group: (
                {CONF_FINAL_CLOSE_ELEVATION: stored}
                if group == GROUP_LIVING
                else {}
            )
            for group in GROUPS
        },
        CONF_ROOMS: {
            "room": {CONF_GROUP: GROUP_LIVING, CONF_ROOM_SETTINGS: {}}
        },
    }

    model, _warnings = migrate_profile_model(source)
    resolved = resolve_config_model(model, "room")

    assert model[CONF_GROUPS][GROUP_LIVING][CONF_FINAL_CLOSE_ELEVATION] == expected
    assert resolved[CONF_FINAL_CLOSE_ELEVATION] == expected
    assert isinstance(resolved[CONF_FINAL_CLOSE_ELEVATION], float)


async def test_v19_upgrade_repairs_legacy_time_elevation_value(hass) -> None:
    controller = MockConfigEntry(
        domain=DOMAIN,
        version=19,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER,
            CONF_GLOBAL: {CONF_GLOBAL_SOURCES: {}, CONF_GLOBAL_DEFAULTS: {}},
            CONF_GROUPS: {
                group: (
                    {CONF_FINAL_CLOSE_ELEVATION: "00:00:00"}
                    if group == GROUP_LIVING
                    else {}
                )
                for group in GROUPS
            },
        },
    )
    controller.add_to_hass(hass)

    assert await async_migrate_entry(hass, controller)

    repaired = controller.data[CONF_GROUPS][GROUP_LIVING][
        CONF_FINAL_CLOSE_ELEVATION
    ]
    assert repaired == DEFAULT_FINAL_CLOSE_ELEVATION
    assert isinstance(repaired, float)
    assert controller.version == 20

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


def test_recalibrate_remains_available_after_cca_cleanup() -> None:
    local = {
        CONF_ENABLE_RECALIBRATE_BUTTON: True,
        "lockout_tilt_close": True,
    }
    model, _ = migrate_profile_model(
        _legacy("Living", {"room": ("Room", "selected", local)})
    )
    settings = model[CONF_ROOMS]["room"][CONF_ROOM_SETTINGS]
    assert settings[CONF_ENABLE_RECALIBRATE_BUTTON] is True
    assert "lockout_tilt_close" not in settings


def test_keep_sun_protection_migrates_from_legacy_setting() -> None:
    source = _fixed_groups_with_sun("fixed")
    source[CONF_GROUPS][GROUP_LIVING]["prevent_opening_after_shading_end"] = True

    model, _ = migrate_profile_model(source)

    living = model[CONF_GROUPS][GROUP_LIVING]
    assert living[CONF_KEEP_SUN_PROTECTION] is True
    assert "prevent_opening_after_shading_end" not in living


def test_removed_cca_settings_are_deleted_from_all_layers() -> None:
    source = _fixed_groups_with_sun("fixed")
    source[CONF_GLOBAL] = {
        CONF_GLOBAL_SOURCES: {"additional_condition_global": {"condition": "state"}},
        CONF_GLOBAL_DEFAULTS: {},
    }
    source[CONF_GROUPS][GROUP_LIVING]["ventilation_use_after_shading"] = True
    source[CONF_ROOMS] = {
        "room": {
            CONF_GROUP: GROUP_LIVING,
            CONF_ROOM_SETTINGS: {"lockout_tilt_close": True},
            CONF_ROOM_OVERRIDES: {
                "cover.test": {"ventilation_start_no_delay": True}
            },
        }
    }

    model, warnings = migrate_profile_model(source)

    assert "additional_condition_global" not in model[CONF_GLOBAL][CONF_GLOBAL_SOURCES]
    assert "ventilation_use_after_shading" not in model[CONF_GROUPS][GROUP_LIVING]
    assert "lockout_tilt_close" not in model[CONF_ROOMS]["room"][CONF_ROOM_SETTINGS]
    assert "ventilation_start_no_delay" not in (
        model[CONF_ROOMS]["room"][CONF_ROOM_OVERRIDES]["cover.test"]
    )
    assert warnings == ["CCA behavior overrides were removed"]


def test_removed_runtime_options_are_deleted_from_all_layers() -> None:
    source = _fixed_groups_with_sun("fixed")
    source[CONF_GLOBAL] = {
        CONF_GLOBAL_SOURCES: {"force_open_entity": "input_boolean.force"},
        CONF_GLOBAL_DEFAULTS: {"recovery_mode": "outage"},
    }
    source[CONF_GROUPS][GROUP_LIVING].update(
        {
            "drive_delay_fixed": 4,
            "drive_delay_random": 8,
            "manual_override_block_open": False,
            "manual_override_reset_mode": "time",
            "manual_override_reset_time": "06:30:00",
            "manual_schedule_adoption": True,
        }
    )
    source[CONF_ROOMS] = {
        "room": {
            CONF_GROUP: GROUP_LIVING,
            CONF_ROOM_SETTINGS: {
                "position_source": "custom_sensor",
                "custom_position_sensor": "sensor.position",
                "recovery_mode": "always",
            },
            CONF_SOURCE_OVERRIDES: {"force_pause_entity": "input_boolean.pause"},
            CONF_ROOM_OVERRIDES: {
                "cover.test": {"force_close_entity": "input_boolean.close"}
            },
        }
    }

    model, warnings = migrate_profile_model(source)
    serialized = str(model)

    assert model[CONF_CONFIG_VERSION] == 14
    assert "force_" not in serialized
    assert "position_source" not in serialized
    assert "custom_position_sensor" not in serialized
    assert "recovery_mode" not in serialized
    assert "drive_delay_random" not in serialized
    assert "manual_override_block_open" not in serialized
    assert "manual_override_reset_mode" not in serialized
    assert "manual_override_reset_time" not in serialized
    assert "manual_schedule_adoption" not in serialized
    assert model[CONF_GROUPS][GROUP_LIVING]["drive_delay_fixed"] == 4
    assert model[CONF_GROUPS][GROUP_LIVING][CONF_MANUAL_OVERRIDE_MINUTES] == 0
    assert warnings == [
        "configurable recovery mode was removed",
        "custom position source was removed",
        "manual override reset time was removed",
    ]


@pytest.mark.parametrize(
    ("mode", "expected_minutes", "expected_warning"),
    [
        ("timeout", 120, False),
        ("none", 0, False),
        ("time", 0, True),
    ],
)
def test_manual_override_reset_modes_migrate(
    mode: str, expected_minutes: int, expected_warning: bool
) -> None:
    source = _fixed_groups_with_sun("fixed")
    source[CONF_GROUPS][GROUP_LIVING].update(
        {
            "manual_override_minutes": 120,
            "manual_override_reset_mode": mode,
            "manual_override_reset_time": "06:30:00",
        }
    )

    model, warnings = migrate_profile_model(source)
    settings = model[CONF_GROUPS][GROUP_LIVING]

    assert settings[CONF_MANUAL_OVERRIDE_MINUTES] == expected_minutes
    assert "manual_override_reset_mode" not in settings
    assert "manual_override_reset_time" not in settings
    assert ("manual override reset time was removed" in warnings) is expected_warning


async def test_removed_runtime_options_create_repair_warnings(hass) -> None:
    data = _fixed_groups_with_sun("fixed")
    data[CONF_GROUPS][GROUP_LIVING]["recovery_mode"] = "never"
    data[CONF_GROUPS][GROUP_LIVING]["manual_override_reset_mode"] = "time"
    data[CONF_GROUPS][GROUP_LIVING]["manual_override_reset_time"] = "06:30:00"
    controller = MockConfigEntry(
        domain=DOMAIN,
        version=16,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER,
            CONF_GLOBAL: {CONF_GLOBAL_SOURCES: {}, CONF_GLOBAL_DEFAULTS: {}},
            **data,
        },
    )
    room = MockConfigEntry(
        domain=DOMAIN,
        version=16,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_ROOM,
            CONF_CONTROLLER_ENTRY_ID: controller.entry_id,
            CONF_ROOM_ID: "living",
            CONF_GROUP: GROUP_LIVING,
            CONF_ROOM_SETTINGS: {
                "position_source": "custom_sensor",
                "custom_position_sensor": "sensor.position",
            },
        },
    )
    controller.add_to_hass(hass)
    room.add_to_hass(hass)

    assert await async_migrate_entry(hass, controller)

    issues = ir.async_get(hass).issues
    assert (DOMAIN, "custom_position_migration") in issues
    assert (DOMAIN, "recovery_mode_migration") in issues
    assert (DOMAIN, "manual_override_reset_time_migration") in issues
    assert "custom_position_sensor" not in str(room.data)

def test_legacy_tilt_options_collapse_to_single_shading_target() -> None:
    settings, warnings = cleanup_runtime_options(
        {
            "cover_tilt_wait_mode": "tilt_before_position",
            "cover_tilt_wait_timeout": 12,
            "tilt_position_tolerance": 7,
            "shading_tilt_position_0": 15,
            "shading_tilt_position_1": 25,
            "shading_tilt_position_2": 35,
            "shading_tilt_position_3": 45,
            "shading_tilt_elevation_1": 10,
            "shading_tilt_elevation_2": 20,
            "shading_tilt_elevation_3": 30,
        }
    )

    assert settings == {CONF_SHADING_TILT_POSITION: 35}
    assert warnings == {"custom multistage tilt shading was collapsed"}


def test_default_legacy_tilt_options_are_removed_without_warning() -> None:
    settings, warnings = cleanup_runtime_options(
        {
            "shading_tilt_position_0": 0,
            "shading_tilt_position_1": 20,
            "shading_tilt_position_2": 37,
            "shading_tilt_position_3": 50,
        }
    )

    assert settings == {}
    assert not warnings


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
    assert controller.version == room.version == 20
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


@pytest.mark.parametrize(
    ("conditions", "expected"),
    [
        (["cond_temp1", "cond_temp2"], SHADING_MODE_INSIDE_OUTSIDE),
        (["cond_azimuth", "cond_elevation"], SHADING_MODE_DIRECTION),
        (["cond_temp1", "cond_temp2", "cond_azimuth"], SHADING_MODE_INSIDE_OUTSIDE_DIRECTION),
        (["cond_temp2", "cond_azimuth"], SHADING_MODE_OUTSIDE_DIRECTION),
        (["cond_temp2"], SHADING_MODE_OUTSIDE),
        (["cond_temp1"], SHADING_MODE_INSIDE),
    ],
)
def test_migrate_fixed_shading_modes(conditions: list[str], expected: str) -> None:
    source = _fixed_groups_with_sun("fixed")
    source[CONF_GROUPS][GROUP_LIVING].update(
        {
            CONF_AUTO_SHADING: True,
            "shading_conditions_start_and": conditions,
            "shading_azimuth_start": 135,
            "shading_azimuth_end": 225,
        }
    )
    model, _ = migrate_profile_model(source)
    living = model[CONF_GROUPS][GROUP_LIVING]
    assert living[CONF_SHADING_MODE] == expected
    assert living[CONF_SHADING_DIRECTION] == 180
    assert living[CONF_SHADING_DIRECTION_RANGE] == 45


def test_complex_or_rules_create_repair_warning_and_remove_forecast() -> None:
    source = _fixed_groups_with_sun("fixed")
    source[CONF_GROUPS][GROUP_SLEEP].update(
        {
            "shading_conditions_start_and": ["cond_temp1", "cond_temp2"],
            "shading_conditions_start_or": ["cond_azimuth"],
            "shading_forecast_sensor": "weather.home",
            "shading_weather_conditions": ["sunny"],
        }
    )
    model, warnings = migrate_profile_model(source)
    sleep = model[CONF_GROUPS][GROUP_SLEEP]
    assert sleep[CONF_SHADING_MODE] == SHADING_MODE_INSIDE_OUTSIDE
    assert any("sleep: complex shading rules" in warning for warning in warnings)
    assert not any("forecast" in key or "conditions_" in key for key in sleep)


def test_group_specific_shading_migration() -> None:
    source = _fixed_groups_with_sun("fixed")
    source[CONF_GROUPS][GROUP_LIVING]["shading_conditions_start_and"] = ["cond_temp2"]
    source[CONF_GROUPS][GROUP_SLEEP]["shading_conditions_start_and"] = ["cond_temp1"]
    source[CONF_GROUPS][GROUP_CHILDREN]["shading_conditions_start_and"] = ["cond_azimuth"]
    model, _ = migrate_profile_model(source)
    assert model[CONF_GROUPS][GROUP_LIVING][CONF_SHADING_MODE] == SHADING_MODE_OUTSIDE
    assert model[CONF_GROUPS][GROUP_SLEEP][CONF_SHADING_MODE] == SHADING_MODE_INSIDE
    assert model[CONF_GROUPS][GROUP_CHILDREN][CONF_SHADING_MODE] == SHADING_MODE_DIRECTION


def test_fixed_shading_mode_migration_is_idempotent() -> None:
    source = _fixed_groups_with_sun("fixed")
    source[CONF_GROUPS][GROUP_LIVING].update(
        {
            CONF_SHADING_MODE: SHADING_MODE_OUTSIDE_DIRECTION,
            CONF_SHADING_DIRECTION: 210,
            CONF_SHADING_DIRECTION_RANGE: 35,
        }
    )
    first, _ = migrate_profile_model(source)
    second, _ = migrate_profile_model(first)
    assert second[CONF_GROUPS][GROUP_LIVING][CONF_SHADING_MODE] == SHADING_MODE_OUTSIDE_DIRECTION
    assert second[CONF_GROUPS][GROUP_LIVING][CONF_SHADING_DIRECTION] == 210


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
    assert controller.version == 20
    assert (DOMAIN, "sun_mode_migration") in ir.async_get(hass).issues


async def test_complex_shading_rules_create_repair_warning(hass) -> None:
    data = _fixed_groups_with_sun("fixed")
    data[CONF_GROUPS][GROUP_LIVING].update(
        {
            "shading_conditions_start_and": ["cond_temp1", "cond_temp2"],
            "shading_conditions_start_or": ["cond_azimuth"],
            "shading_forecast_sensor": "weather.home",
        }
    )
    controller = MockConfigEntry(
        domain=DOMAIN,
        version=14,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER,
            CONF_GLOBAL: {CONF_GLOBAL_SOURCES: {}, CONF_GLOBAL_DEFAULTS: {}},
            **data,
        },
    )
    controller.add_to_hass(hass)
    assert await async_migrate_entry(hass, controller)
    assert controller.version == 20
    assert (DOMAIN, "shading_mode_migration") in ir.async_get(hass).issues


async def test_room_direction_migrates_to_assigned_group(hass) -> None:
    controller = MockConfigEntry(
        domain=DOMAIN,
        version=14,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER,
            CONF_GLOBAL: {CONF_GLOBAL_SOURCES: {}, CONF_GLOBAL_DEFAULTS: {}},
            CONF_GROUPS: {group: {} for group in GROUPS},
        },
    )
    room = MockConfigEntry(
        domain=DOMAIN,
        version=14,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_ROOM,
            CONF_CONTROLLER_ENTRY_ID: controller.entry_id,
            CONF_ROOM_ID: "living",
            CONF_GROUP: GROUP_LIVING,
            CONF_ROOM_SETTINGS: {
                "shading_azimuth_start": 320,
                "shading_azimuth_end": 20,
            },
        },
    )
    controller.add_to_hass(hass)
    room.add_to_hass(hass)
    assert await async_migrate_entry(hass, controller)
    group = controller.data[CONF_GROUPS][GROUP_LIVING]
    assert group[CONF_SHADING_DIRECTION] == 350
    assert group[CONF_SHADING_DIRECTION_RANGE] == 30
    assert "shading_azimuth_start" not in room.data[CONF_ROOM_SETTINGS]


async def test_removed_cca_behavior_creates_single_repair_warning(hass) -> None:
    data = _fixed_groups_with_sun("fixed")
    data[CONF_GROUPS][GROUP_LIVING]["shading_over_ventilation"] = True
    data[CONF_GROUPS][GROUP_SLEEP]["prevent_opening_multiple_times"] = True
    controller = MockConfigEntry(
        domain=DOMAIN,
        version=15,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER,
            CONF_GLOBAL: {CONF_GLOBAL_SOURCES: {}, CONF_GLOBAL_DEFAULTS: {}},
            **data,
        },
    )
    controller.add_to_hass(hass)

    assert await async_migrate_entry(hass, controller)

    assert controller.version == 20
    assert (DOMAIN, "cca_cleanup_migration") in ir.async_get(hass).issues


async def test_room_cleanup_creates_same_single_repair_warning(hass) -> None:
    room = MockConfigEntry(
        domain=DOMAIN,
        version=15,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_ROOM,
            CONF_ROOM_ID: "room",
            CONF_GROUP: GROUP_LIVING,
            CONF_ROOM_SETTINGS: {"lockout_tilt_shading_start": True},
        },
    )
    room.add_to_hass(hass)

    assert await async_migrate_entry(hass, room)

    assert room.version == 20
    assert "lockout_tilt_shading_start" not in room.data[CONF_ROOM_SETTINGS]
    assert (DOMAIN, "cca_cleanup_migration") in ir.async_get(hass).issues
