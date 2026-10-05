"""Tests for integration-wide hub routing and migration merging."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from custom_components.cover_control.config_profiles import ConfigProfileModel
from custom_components.cover_control.const import (
    CONF_BRIGHTNESS_SENSOR,
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
    CONF_ROOM_OVERRIDES,
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
    CONF_SHADING_WAITINGTIME_END,
    CONF_SOURCE_OVERRIDES,
    CONF_AUTO_TIME,
    CONF_AUTO_UP,
    CONF_TIME_UP_EARLY_WORKDAY,
    FUNCTION_RESIDENT,
    FUNCTION_SHADING,
    FUNCTION_TIME,
)
from custom_components.cover_control.hub import CoverControlHub


def test_hub_uses_one_listener_and_removes_it_on_last_route() -> None:
    hub = CoverControlHub(Mock())
    first = Mock()
    first.shared_entity_routes.return_value = {"sensor.outdoor"}
    second = Mock()
    second.shared_entity_routes.return_value = {"sensor.outdoor"}
    hub.managers = {"first": first, "second": second}
    unsubscribe = Mock()

    with patch(
        "custom_components.cover_control.shared_input.async_track_state_change_event",
        return_value=unsubscribe,
    ) as track:
        hub.refresh_shared_listener()
        hub.refresh_shared_listener()
        first.shared_entity_routes.return_value = set()
        second.shared_entity_routes.return_value = set()
        hub.refresh_shared_listener()

    track.assert_called_once()
    unsubscribe.assert_called_once_with()


def test_profile_evaluation_keeps_shared_and_room_schedule_levels() -> None:
    hub = CoverControlHub(Mock())
    now = datetime.now(UTC)
    hub.profile_users = {("profile", "weekday"): {"living", "office"}}
    living = SimpleNamespace(
        room_id="living",
        entry_snapshot=lambda: {
            "next_open": (now + timedelta(hours=2), "cover.living"),
            "next_close": None,
        },
    )
    office = SimpleNamespace(
        room_id="office",
        entry_snapshot=lambda: {
            "next_open": (now + timedelta(hours=1), "cover.office"),
            "next_close": None,
        },
    )
    hub.managers = {"living": living, "office": office}

    profile_due = now + timedelta(minutes=30)
    with (
        patch("custom_components.cover_control.hub.async_dispatcher_send"),
        patch(
            "custom_components.cover_control.hub.evaluate_time_profile",
            return_value=(profile_due, None),
        ),
        patch(
            "custom_components.cover_control.hub.async_track_point_in_time",
            return_value=Mock(),
        ) as track,
    ):
        hub.refresh_profile_evaluations()

    evaluation = hub.profile_evaluations[("profile", "weekday")]
    assert evaluation.next_open == profile_due
    assert living.entry_snapshot()["next_open"][0] == now + timedelta(hours=2)
    track.assert_called_once()


def test_room_override_keeps_its_time_timer_local() -> None:
    hub = CoverControlHub(Mock())
    hub.model = ConfigProfileModel(
        {
            CONF_PROFILES: {
                "weekday": {
                    "id": "weekday",
                    "name": "Weekday",
                    "settings": {
                        CONF_AUTO_TIME: True,
                        CONF_AUTO_UP: True,
                        CONF_TIME_UP_EARLY_WORKDAY: "07:00:00",
                    },
                    "functions": [FUNCTION_TIME],
                }
            },
            CONF_ROOMS: {
                "living": {
                    CONF_ROOM_PROFILE_ID: "weekday",
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_TIME],
                    CONF_ROOM_OVERRIDES: {},
                },
                "office": {
                    CONF_ROOM_PROFILE_ID: "weekday",
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_TIME],
                    CONF_ROOM_OVERRIDES: {
                        "time": {"time_up_early_workday": "07:00:00"}
                    },
                },
            },
        }
    ).data

    assert hub.room_uses_shared_time_timer("living")
    assert not hub.room_uses_shared_time_timer("office")


def test_hub_diagnostics_reports_unified_profiles_without_typed_catalogs() -> None:
    hub = CoverControlHub(Mock())
    hub.set_parent_model(
        {
            CONF_GLOBAL: {CONF_GLOBAL_SOURCES: {}, CONF_GLOBAL_DEFAULTS: {}},
            CONF_PROFILES: {
                "profile-living": {
                    CONF_PROFILE_ID: "profile-living",
                    CONF_PROFILE_NAME: "Wohnen",
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_TIME, FUNCTION_SHADING],
                    CONF_PROFILE_SETTINGS: {"auto_time_enabled": True},
                },
                "profile-sleep": {
                    CONF_PROFILE_ID: "profile-sleep",
                    CONF_PROFILE_NAME: "Schlafen",
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_RESIDENT],
                    CONF_PROFILE_SETTINGS: {"resident_status_enabled": True},
                },
            },
            CONF_ROOMS: {
                "living": {
                    CONF_NAME: "Living",
                    CONF_ROOM_PROFILE_ID: "profile-living",
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_TIME],
                    CONF_ROOM_SETTINGS: {},
                    CONF_SOURCE_OVERRIDES: {},
                },
                "bedroom": {
                    CONF_NAME: "Bedroom",
                    CONF_ROOM_PROFILE_ID: "profile-sleep",
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_RESIDENT],
                    CONF_ROOM_SETTINGS: {},
                    CONF_SOURCE_OVERRIDES: {},
                },
            },
        }
    )

    diagnostics = hub.diagnostics()

    assert set(diagnostics["profiles"]) == {"profile-living", "profile-sleep"}
    assert "time" not in diagnostics["profiles"]
    assert diagnostics["profiles"]["profile-living"]["name"] == "Wohnen"
    assert diagnostics["profiles"]["profile-living"]["users"] == ["living"]
    assert diagnostics["profiles"]["profile-living"]["functions"] == [
        FUNCTION_TIME
    ]
    assert diagnostics["profiles"]["profile-sleep"]["name"] == "Schlafen"
    assert diagnostics["profiles"]["profile-sleep"]["users"] == ["bedroom"]
    assert diagnostics["profiles"]["profile-sleep"]["functions"] == [
        FUNCTION_RESIDENT
    ]
