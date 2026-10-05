"""Tests for configured/enabled/eligible separation."""

from custom_components.cover_control.feature_state import feature_configured
from custom_components.cover_control.const import (
    CONF_PROFILE_FUNCTIONS,
    CONF_PROFILE_ID,
    CONF_PROFILE_NAME,
    CONF_PROFILE_SELECTIONS,
    CONF_PROFILE_SETTINGS,
    CONF_PROFILES,
    CONF_ROOM_PROFILE_ID,
    CONF_ROOMS,
    FUNCTION_BRIGHTNESS,
    FUNCTION_RESIDENT,
    FUNCTION_SHADING,
    FUNCTION_TIME,
    PROFILE_TYPE_TIME,
)


def test_configured_false_when_default_only() -> None:
    model = {"profiles": {"time": {}}, "rooms": {"room": {"settings": {}}}}
    assert not feature_configured(model, "room", "auto_time_enabled")


def test_configured_true_even_when_persisted_value_is_false() -> None:
    model = {
        "profiles": {"time": {}},
        "rooms": {"room": {"settings": {"auto_time_enabled": False}}},
    }
    assert feature_configured(model, "room", "auto_time_enabled")


def test_unselected_profile_function_is_not_configured() -> None:
    model = {
        CONF_PROFILES: {
            PROFILE_TYPE_TIME: {
                "living": {
                    CONF_PROFILE_ID: "living",
                    CONF_PROFILE_NAME: "Living",
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_BRIGHTNESS, FUNCTION_SHADING],
                    CONF_PROFILE_SETTINGS: {
                        "auto_brightness_enabled": True,
                        "auto_shading_enabled": True,
                    },
                }
            }
        },
        CONF_ROOMS: {
            "room": {
                CONF_PROFILE_SELECTIONS: {PROFILE_TYPE_TIME: "living"},
                CONF_PROFILE_FUNCTIONS: [FUNCTION_SHADING],
            }
        },
    }

    assert not feature_configured(model, "room", "auto_brightness_enabled")
    assert feature_configured(model, "room", "auto_shading_enabled")


def test_profile_function_must_exist_on_selected_profile() -> None:
    model = {
        CONF_PROFILES: {
            PROFILE_TYPE_TIME: {
                "living": {
                    CONF_PROFILE_ID: "living",
                    CONF_PROFILE_NAME: "Living",
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_SHADING],
                    CONF_PROFILE_SETTINGS: {"auto_shading_enabled": True},
                }
            }
        },
        CONF_ROOMS: {
            "room": {
                CONF_PROFILE_SELECTIONS: {PROFILE_TYPE_TIME: "living"},
                CONF_PROFILE_FUNCTIONS: [FUNCTION_BRIGHTNESS],
            }
        },
    }

    assert not feature_configured(model, "room", "auto_brightness_enabled")


def test_flat_profile_setting_is_configured() -> None:
    model = {
        CONF_PROFILES: {
            "profile-south": {
                CONF_PROFILE_ID: "profile-south",
                CONF_PROFILE_NAME: "South",
                CONF_PROFILE_SETTINGS: {"shading_waitingtime_end": 600},
            }
        },
        CONF_ROOMS: {
            "room": {
                CONF_ROOM_PROFILE_ID: "profile-south",
                CONF_PROFILE_FUNCTIONS: [FUNCTION_SHADING],
            }
        },
    }

    assert feature_configured(model, "room", "shading_waitingtime_end")


def test_selected_room_functions_gate_profile_behavior() -> None:
    model = {
        CONF_PROFILES: {
            "profile-living": {
                CONF_PROFILE_ID: "profile-living",
                CONF_PROFILE_NAME: "Living",
                CONF_PROFILE_FUNCTIONS: [FUNCTION_TIME, FUNCTION_RESIDENT],
                CONF_PROFILE_SETTINGS: {
                    "auto_time_enabled": True,
                    "resident_status_enabled": True,
                },
            }
        },
        CONF_ROOMS: {
            "room": {
                CONF_ROOM_PROFILE_ID: "profile-living",
                CONF_PROFILE_FUNCTIONS: [FUNCTION_TIME],
            }
        },
    }

    assert feature_configured(model, "room", "auto_time_enabled")
    assert not feature_configured(model, "room", "resident_status_enabled")
