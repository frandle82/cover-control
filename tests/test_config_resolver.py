"""Tests for hierarchical room configuration resolution."""

from custom_components.cover_control.config_resolver import (
    PROFILE_FUNCTION_KEYS,
    ROOM_HARDWARE_KEYS,
    ROOM_POSITION_KEYS,
    ROOM_SENSOR_KEYS,
    ROOM_GEOMETRY_KEYS,
    ROOM_CONTROL_KEYS,
    configured_functions_from_profile,
    resolve_config_model,
    resolve_room_config,
)
from custom_components.cover_control.config_migration import normalize_legacy_config
from custom_components.cover_control.const import (
    CONF_BRIGHTNESS_SENSOR,
    CONF_CONFIG_VERSION,
    CONF_COVERS,
    CONF_COVER_TYPE,
    CONF_DRIVE_TIME,
    CONF_ENABLE_LOGBOOK_COVER,
    CONF_ENABLE_RECALIBRATE_BUTTON,
    CONF_GLOBAL,
    CONF_GLOBAL_DEFAULTS,
    CONF_GLOBAL_SOURCES,
    CONF_NAME,
    CONF_PROFILE_ID,
    CONF_PROFILE_NAME,
    CONF_PROFILE_FUNCTIONS,
    CONF_PROFILE_SELECTIONS,
    CONF_PROFILE_SETTINGS,
    CONF_PROFILES,
    CONF_ROOM_OVERRIDES,
    CONF_ROOM_PROFILE_ID,
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
    CONF_RESIDENT_ALLOW_OPEN,
    CONF_RESIDENT_OPEN_ENABLED,
    CONF_RESIDENT_SENSOR,
    CONF_RESIDENT_STATUS,
    CONF_SHADING_POSITION,
    CONF_SUN_AZIMUTH_END,
    CONF_SUN_AZIMUTH_START,
    CONF_TEMPERATURE_SENSOR_INDOOR,
    CONF_SHADING_WAITINGTIME_END,
    CONF_SOURCE_OVERRIDES,
    CONFIG_MODEL_VERSION,
    FUNCTION_BRIGHTNESS,
    FUNCTION_RESIDENT,
    FUNCTION_SHADING,
    FUNCTION_TIME,
    PROFILE_TYPE_SHADING,
)


def _profile(profile_id: str, **settings):
    return {
        CONF_PROFILE_ID: profile_id,
        CONF_PROFILE_NAME: "South",
        CONF_PROFILE_SETTINGS: settings,
    }


def test_profile_wins_over_global_default() -> None:
    resolved = resolve_room_config(
        {CONF_SHADING_POSITION: 20},
        {},
        {CONF_SHADING_POSITION: 25},
        {PROFILE_TYPE_SHADING: _profile("south", shading_position=30)},
        {},
        {},
    )

    assert resolved[CONF_SHADING_POSITION] == 30
    assert resolved.sources[CONF_SHADING_POSITION] == "profile:south"


def test_room_override_wins_over_profile() -> None:
    resolved = resolve_room_config(
        {},
        {},
        {},
        {PROFILE_TYPE_SHADING: _profile("south", shading_position=30)},
        {},
        {PROFILE_TYPE_SHADING: {CONF_SHADING_POSITION: 25}},
    )

    assert resolved[CONF_SHADING_POSITION] == 25
    assert resolved.sources[CONF_SHADING_POSITION] == "room_override"


def test_global_default_fills_missing_profile_value() -> None:
    resolved = resolve_room_config(
        {CONF_SHADING_WAITINGTIME_END: 0},
        {},
        {CONF_SHADING_WAITINGTIME_END: 600},
        {PROFILE_TYPE_SHADING: _profile("south")},
        {},
        {},
    )

    assert resolved[CONF_SHADING_WAITINGTIME_END] == 600
    assert resolved.sources[CONF_SHADING_WAITINGTIME_END] == "global_default"


def test_system_default_fills_unconfigured_value() -> None:
    resolved = resolve_room_config(
        {CONF_SHADING_POSITION: 25}, {}, {}, {}, {}, {}
    )

    assert resolved[CONF_SHADING_POSITION] == 25
    assert resolved.sources[CONF_SHADING_POSITION] == "system_default"


def test_room_source_override_wins_over_global_source() -> None:
    resolved = resolve_room_config(
        {},
        {CONF_BRIGHTNESS_SENSOR: "sensor.outdoor"},
        {},
        {},
        {},
        {},
        source_overrides={CONF_BRIGHTNESS_SENSOR: "sensor.wintergarden"},
    )

    assert resolved[CONF_BRIGHTNESS_SENSOR] == "sensor.wintergarden"
    assert resolved.sources[CONF_BRIGHTNESS_SENSOR] == "room_source_override"


def test_legacy_flat_config_resolves_without_behavior_change() -> None:
    data = {
        CONF_NAME: "Living room",
        CONF_COVERS: ["cover.left", "cover.right"],
        CONF_SHADING_POSITION: 31,
        CONF_BRIGHTNESS_SENSOR: "sensor.outdoor",
    }
    options = {CONF_SHADING_WAITINGTIME_END: 90}
    model = normalize_legacy_config(data, options, room_id="entry-1")

    assert model[CONF_CONFIG_VERSION] == CONFIG_MODEL_VERSION
    resolved = resolve_config_model(model, "entry-1")
    assert resolved[CONF_COVERS] == ["cover.left", "cover.right"]
    assert resolved[CONF_SHADING_POSITION] == 31
    assert resolved[CONF_SHADING_WAITINGTIME_END] == 90
    assert resolved[CONF_BRIGHTNESS_SENSOR] == "sensor.outdoor"
    assert resolved.selected_profiles["profile"].startswith("legacy:")


def test_persisted_model_resolves_profile_reference_without_copying() -> None:
    model = {
        CONF_CONFIG_VERSION: CONFIG_MODEL_VERSION,
        CONF_GLOBAL: {
            CONF_GLOBAL_SOURCES: {},
            CONF_GLOBAL_DEFAULTS: {},
        },
        CONF_PROFILES: {
            PROFILE_TYPE_SHADING: {
                "south": _profile("south", shading_position=30)
            }
        },
        CONF_ROOMS: {
            "living": {
                CONF_NAME: "Living",
                CONF_PROFILE_SELECTIONS: {PROFILE_TYPE_SHADING: "south"},
                CONF_ROOM_SETTINGS: {CONF_COVERS: ["cover.living"]},
                CONF_SOURCE_OVERRIDES: {},
                CONF_ROOM_OVERRIDES: {},
            }
        },
    }

    resolved = resolve_config_model(model, "living")

    assert resolved[CONF_SHADING_POSITION] == 30
    assert CONF_SHADING_POSITION not in model[CONF_ROOMS]["living"]


def test_room_profile_functions_limit_configured_functions() -> None:
    model = {
        CONF_CONFIG_VERSION: CONFIG_MODEL_VERSION,
        CONF_GLOBAL: {
            CONF_GLOBAL_SOURCES: {},
            CONF_GLOBAL_DEFAULTS: {},
        },
        CONF_PROFILES: {
            PROFILE_TYPE_SHADING: {
                "south": {
                    CONF_PROFILE_ID: "south",
                    CONF_PROFILE_NAME: "South",
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_BRIGHTNESS, FUNCTION_SHADING],
                    CONF_PROFILE_SETTINGS: {
                        "auto_brightness_enabled": True,
                        "auto_shading_enabled": True,
                    },
                }
            }
        },
        CONF_ROOMS: {
            "living": {
                CONF_NAME: "Living",
                CONF_PROFILE_SELECTIONS: {PROFILE_TYPE_SHADING: "south"},
                CONF_PROFILE_FUNCTIONS: [FUNCTION_SHADING],
                CONF_ROOM_SETTINGS: {CONF_COVERS: ["cover.living"]},
                CONF_SOURCE_OVERRIDES: {},
                CONF_ROOM_OVERRIDES: {},
            }
        },
    }

    resolved = resolve_config_model(model, "living")

    assert resolved.configured_functions == frozenset({FUNCTION_SHADING})


def test_native_profile_settings_are_filtered_to_selected_functions() -> None:
    model = {
        CONF_CONFIG_VERSION: CONFIG_MODEL_VERSION,
        CONF_GLOBAL: {
            CONF_GLOBAL_SOURCES: {},
            CONF_GLOBAL_DEFAULTS: {},
        },
        CONF_PROFILES: {
            "profile-living": {
                CONF_PROFILE_ID: "profile-living",
                CONF_PROFILE_NAME: "Living",
                CONF_PROFILE_FUNCTIONS: [FUNCTION_TIME, FUNCTION_RESIDENT],
                CONF_PROFILE_SETTINGS: {
                    "auto_time_enabled": True,
                    CONF_RESIDENT_STATUS: True,
                    CONF_RESIDENT_OPEN_ENABLED: True,
                    CONF_RESIDENT_ALLOW_OPEN: True,
                },
            }
        },
        CONF_ROOMS: {
            "living": {
                CONF_NAME: "Living",
                CONF_ROOM_PROFILE_ID: "profile-living",
                CONF_PROFILE_FUNCTIONS: [FUNCTION_TIME],
                CONF_ROOM_SETTINGS: {CONF_COVERS: ["cover.living"]},
                CONF_SOURCE_OVERRIDES: {},
            }
        },
    }

    resolved = resolve_config_model(model, "living")

    assert resolved.configured_functions == frozenset({FUNCTION_TIME})
    assert resolved["auto_time_enabled"] is True
    assert resolved.sources["auto_time_enabled"] == "profile:profile-living"
    assert resolved[CONF_RESIDENT_STATUS] is False
    assert resolved.sources[CONF_RESIDENT_STATUS] == "system_default"
    assert resolved.sources[CONF_RESIDENT_OPEN_ENABLED] == "system_default"


def test_native_profile_settings_block_room_owned_values() -> None:
    model = {
        CONF_CONFIG_VERSION: CONFIG_MODEL_VERSION,
        CONF_GLOBAL: {
            CONF_GLOBAL_SOURCES: {},
            CONF_GLOBAL_DEFAULTS: {},
        },
        CONF_PROFILES: {
            "profile-shading": {
                CONF_PROFILE_ID: "profile-shading",
                CONF_PROFILE_NAME: "Shading",
                CONF_PROFILE_FUNCTIONS: [FUNCTION_SHADING],
                CONF_PROFILE_SETTINGS: {
                    "auto_shading_enabled": True,
                    CONF_SHADING_POSITION: 10,
                    CONF_RESIDENT_SENSOR: "binary_sensor.profile_resident",
                    CONF_TEMPERATURE_SENSOR_INDOOR: "sensor.profile_temp",
                    CONF_SUN_AZIMUTH_START: 111,
                    CONF_SUN_AZIMUTH_END: 222,
                    CONF_COVER_TYPE: "awning",
                    CONF_DRIVE_TIME: 99,
                    CONF_ENABLE_LOGBOOK_COVER: True,
                    CONF_ENABLE_RECALIBRATE_BUTTON: True,
                },
            }
        },
        CONF_ROOMS: {
            "living": {
                CONF_NAME: "Living",
                CONF_ROOM_PROFILE_ID: "profile-shading",
                CONF_PROFILE_FUNCTIONS: [FUNCTION_SHADING],
                CONF_ROOM_SETTINGS: {
                    CONF_COVERS: ["cover.living"],
                    CONF_SHADING_POSITION: 42,
                    CONF_RESIDENT_SENSOR: "binary_sensor.room_resident",
                    CONF_TEMPERATURE_SENSOR_INDOOR: "sensor.room_temp",
                    CONF_SUN_AZIMUTH_START: 120,
                    CONF_SUN_AZIMUTH_END: 240,
                },
                CONF_SOURCE_OVERRIDES: {},
            }
        },
    }

    resolved = resolve_config_model(model, "living")

    assert resolved[CONF_SHADING_POSITION] == 42
    assert resolved.sources[CONF_SHADING_POSITION] == "room_setting"
    assert resolved[CONF_RESIDENT_SENSOR] == "binary_sensor.room_resident"
    assert resolved.sources[CONF_RESIDENT_SENSOR] == "room_setting"
    assert resolved[CONF_TEMPERATURE_SENSOR_INDOOR] == "sensor.room_temp"
    assert resolved.sources[CONF_TEMPERATURE_SENSOR_INDOOR] == "room_setting"
    assert resolved[CONF_SUN_AZIMUTH_START] == 120
    assert resolved.sources[CONF_SUN_AZIMUTH_START] == "room_setting"
    assert resolved[CONF_COVER_TYPE] != "awning"
    assert resolved.sources[CONF_COVER_TYPE] == "system_default"
    assert CONF_DRIVE_TIME not in resolved
    assert CONF_DRIVE_TIME not in resolved.sources
    assert resolved[CONF_ENABLE_LOGBOOK_COVER] is False
    assert resolved.sources[CONF_ENABLE_LOGBOOK_COVER] == "system_default"
    assert resolved[CONF_ENABLE_RECALIBRATE_BUTTON] is False
    assert resolved.sources[CONF_ENABLE_RECALIBRATE_BUTTON] == "system_default"


def test_native_profile_position_without_room_value_uses_system_default() -> None:
    model = {
        CONF_CONFIG_VERSION: CONFIG_MODEL_VERSION,
        CONF_GLOBAL: {CONF_GLOBAL_SOURCES: {}, CONF_GLOBAL_DEFAULTS: {}},
        CONF_PROFILES: {
            "profile-shading": {
                CONF_PROFILE_ID: "profile-shading",
                CONF_PROFILE_NAME: "Shading",
                CONF_PROFILE_FUNCTIONS: [FUNCTION_SHADING],
                CONF_PROFILE_SETTINGS: {
                    "auto_shading_enabled": True,
                    CONF_SHADING_POSITION: 10,
                },
            }
        },
        CONF_ROOMS: {
            "living": {
                CONF_NAME: "Living",
                CONF_ROOM_PROFILE_ID: "profile-shading",
                CONF_PROFILE_FUNCTIONS: [FUNCTION_SHADING],
                CONF_ROOM_SETTINGS: {CONF_COVERS: ["cover.living"]},
                CONF_SOURCE_OVERRIDES: {},
            }
        },
    }

    resolved = resolve_config_model(model, "living")

    assert resolved[CONF_SHADING_POSITION] != 10
    assert resolved.sources[CONF_SHADING_POSITION] == "system_default"


def test_native_profile_functions_are_derived_from_current_content() -> None:
    profile = {
        CONF_PROFILE_NAME: "Wohnen",
        CONF_PROFILE_FUNCTIONS: [FUNCTION_TIME],
        CONF_PROFILE_SETTINGS: {
            "auto_time_enabled": True,
            "auto_shading_enabled": True,
        },
    }

    assert configured_functions_from_profile(profile) == frozenset(
        {FUNCTION_TIME, FUNCTION_SHADING}
    )

    profile[CONF_PROFILE_SETTINGS].pop("auto_shading_enabled")
    profile[FUNCTION_RESIDENT] = {}

    assert configured_functions_from_profile(profile) == frozenset({FUNCTION_TIME})


def test_native_v6_room_without_profile_functions_selects_none() -> None:
    model = {
        CONF_CONFIG_VERSION: CONFIG_MODEL_VERSION,
        CONF_GLOBAL: {
            CONF_GLOBAL_SOURCES: {},
            CONF_GLOBAL_DEFAULTS: {},
        },
        CONF_PROFILES: {
            "profile-living": {
                CONF_PROFILE_ID: "profile-living",
                CONF_PROFILE_NAME: "Living",
                CONF_PROFILE_FUNCTIONS: [FUNCTION_TIME, FUNCTION_RESIDENT],
                CONF_PROFILE_SETTINGS: {
                    "auto_time_enabled": True,
                    "resident_status": True,
                },
            }
        },
        CONF_ROOMS: {
            "living": {
                CONF_NAME: "Living",
                CONF_ROOM_PROFILE_ID: "profile-living",
                CONF_ROOM_SETTINGS: {CONF_COVERS: ["cover.living"]},
                CONF_SOURCE_OVERRIDES: {},
                CONF_ROOM_OVERRIDES: {},
            }
        },
    }

    resolved = resolve_config_model(model, "living")

    assert resolved.configured_functions == frozenset()


def test_legacy_room_without_profile_functions_uses_compatibility_fallback() -> None:
    model = {
        CONF_CONFIG_VERSION: CONFIG_MODEL_VERSION,
        CONF_GLOBAL: {
            CONF_GLOBAL_SOURCES: {},
            CONF_GLOBAL_DEFAULTS: {},
        },
        CONF_PROFILES: {
            PROFILE_TYPE_SHADING: {
                "south": {
                    CONF_PROFILE_ID: "south",
                    CONF_PROFILE_NAME: "South",
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_SHADING],
                    CONF_PROFILE_SETTINGS: {"auto_shading_enabled": True},
                }
            }
        },
        CONF_ROOMS: {
            "living": {
                CONF_NAME: "Living",
                CONF_PROFILE_SELECTIONS: {PROFILE_TYPE_SHADING: "south"},
                CONF_ROOM_SETTINGS: {CONF_COVERS: ["cover.living"]},
                CONF_SOURCE_OVERRIDES: {},
                CONF_ROOM_OVERRIDES: {},
            }
        },
    }

    resolved = resolve_config_model(model, "living")

    assert resolved.configured_functions == frozenset({FUNCTION_SHADING})


def test_profile_function_keys_do_not_own_room_hardware_positions_or_sensors() -> None:
    profile_keys = set().union(*PROFILE_FUNCTION_KEYS.values())

    assert profile_keys.isdisjoint(ROOM_HARDWARE_KEYS)
    assert profile_keys.isdisjoint(ROOM_POSITION_KEYS)
    assert profile_keys.isdisjoint(ROOM_SENSOR_KEYS)
    assert profile_keys.isdisjoint(ROOM_GEOMETRY_KEYS)
    assert profile_keys.isdisjoint(ROOM_CONTROL_KEYS)


def test_unified_profile_reference_resolves_function_blocks() -> None:
    model = {
        CONF_CONFIG_VERSION: CONFIG_MODEL_VERSION,
        CONF_GLOBAL: {
            CONF_GLOBAL_SOURCES: {},
            CONF_GLOBAL_DEFAULTS: {},
        },
        CONF_PROFILES: {
            "profile-living": {
                CONF_ROOM_PROFILE_ID: "profile-living",
                CONF_PROFILE_NAME: "Living",
                FUNCTION_TIME: {"auto_time_enabled": True},
                FUNCTION_SHADING: {"auto_shading_enabled": True},
            }
        },
        CONF_ROOMS: {
            "living": {
                CONF_NAME: "Living",
                CONF_PROFILE_ID: "profile-living",
                CONF_PROFILE_FUNCTIONS: [FUNCTION_SHADING],
                CONF_ROOM_SETTINGS: {
                    CONF_COVERS: ["cover.living"],
                    CONF_SHADING_POSITION: 28,
                },
                CONF_SOURCE_OVERRIDES: {},
                CONF_ROOM_OVERRIDES: {},
            }
        },
    }

    resolved = resolve_config_model(model, "living")

    assert resolved["auto_shading_enabled"] is True
    assert resolved.configured_functions == frozenset({FUNCTION_SHADING})
    assert resolved[CONF_SHADING_POSITION] == 28
