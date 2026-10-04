"""Tests for hierarchical room configuration resolution."""

from custom_components.cover_control.config_resolver import (
    resolve_config_model,
    resolve_room_config,
)
from custom_components.cover_control.config_migration import normalize_legacy_config
from custom_components.cover_control.const import (
    CONF_BRIGHTNESS_SENSOR,
    CONF_CONFIG_VERSION,
    CONF_COVERS,
    CONF_GLOBAL,
    CONF_GLOBAL_DEFAULTS,
    CONF_GLOBAL_SOURCES,
    CONF_NAME,
    CONF_PROFILE_ID,
    CONF_PROFILE_NAME,
    CONF_PROFILE_SELECTIONS,
    CONF_PROFILE_SETTINGS,
    CONF_PROFILES,
    CONF_ROOM_OVERRIDES,
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
    CONF_SHADING_POSITION,
    CONF_SHADING_WAITINGTIME_END,
    CONF_SOURCE_OVERRIDES,
    CONFIG_MODEL_VERSION,
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
    assert resolved.selected_profiles[PROFILE_TYPE_SHADING].startswith("legacy-")


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
