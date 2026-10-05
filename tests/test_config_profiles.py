"""Native v6 profile model invariants."""

from custom_components.cover_control.config_profiles import ConfigProfileModel
from custom_components.cover_control.config_resolver import resolve_config_model
from custom_components.cover_control.const import (
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
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
    CONF_SHADING_POSITION,
    CONF_SHADING_WAITINGTIME_END,
    CONF_SOURCE_OVERRIDES,
    FUNCTION_SHADING,
)


def _native_v6_model() -> dict:
    return {
        CONF_GLOBAL: {
            CONF_GLOBAL_SOURCES: {},
            CONF_GLOBAL_DEFAULTS: {},
        },
        CONF_PROFILES: {
            "profile-south": {
                CONF_PROFILE_ID: "profile-south",
                CONF_PROFILE_NAME: "South",
                CONF_PROFILE_SETTINGS: {
                    CONF_SHADING_WAITINGTIME_END: 600,
                },
                CONF_PROFILE_FUNCTIONS: [FUNCTION_SHADING],
            }
        },
        CONF_ROOMS: {
            "living": {
                CONF_NAME: "Living",
                CONF_ROOM_PROFILE_ID: "profile-south",
                CONF_PROFILE_FUNCTIONS: [FUNCTION_SHADING],
                CONF_ROOM_SETTINGS: {
                    CONF_SHADING_POSITION: 25,
                },
                CONF_SOURCE_OVERRIDES: {},
            },
        },
    }


def test_native_v6_model_keeps_profile_and_room_ownership_separate() -> None:
    model = ConfigProfileModel(_native_v6_model())

    resolved = resolve_config_model(model.data, "living")

    assert model.profile_users == {("profile", "profile-south"): {"living"}}
    assert resolved[CONF_SHADING_WAITINGTIME_END] == 600
    assert resolved[CONF_SHADING_POSITION] == 25
    room = model.data[CONF_ROOMS]["living"]
    assert "profile_selections" not in room
    assert "room_overrides" not in room


def test_native_v6_flat_room_updates_do_not_create_typed_profiles() -> None:
    model = ConfigProfileModel(_native_v6_model())

    model.apply_flat_settings(
        "living",
        {
            CONF_NAME: "Wohnzimmer",
            CONF_SHADING_WAITINGTIME_END: 900,
        },
    )

    assert set(model.data[CONF_PROFILES]) == {"profile-south"}
    room = model.data[CONF_ROOMS]["living"]
    assert room[CONF_NAME] == "Wohnzimmer"
    assert room[CONF_ROOM_SETTINGS][CONF_SHADING_WAITINGTIME_END] == 900
    assert "profile_selections" not in room
    assert "room_overrides" not in room
