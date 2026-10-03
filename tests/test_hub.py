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
    CONF_CONFIG_MODEL,
    CONF_HUB_ENTRY_ID,
    CONF_NAME,
    CONF_PROFILE_SELECTIONS,
    CONF_PROFILES,
    CONF_ROOM_OVERRIDES,
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
    CONF_SOURCE_OVERRIDES,
    PROFILE_TYPE_BEHAVIOR,
    PROFILE_TYPE_SHADING,
    PROFILE_TYPE_TIME,
)
from custom_components.cover_control.hub import CoverControlHub, merge_config_models


def _model(room_id: str, profile_id: str, position: int) -> dict:
    model = ConfigProfileModel(
        {
            CONF_GLOBAL: {
                CONF_GLOBAL_SOURCES: {
                    CONF_BRIGHTNESS_SENSOR: "sensor.outdoor"
                },
                CONF_GLOBAL_DEFAULTS: {},
            },
            CONF_PROFILES: {
                PROFILE_TYPE_TIME: {},
                PROFILE_TYPE_SHADING: {},
                PROFILE_TYPE_BEHAVIOR: {},
            },
            CONF_ROOMS: {
                room_id: {
                    CONF_NAME: room_id.title(),
                    CONF_PROFILE_SELECTIONS: {},
                    CONF_ROOM_SETTINGS: {},
                    CONF_SOURCE_OVERRIDES: {},
                    CONF_ROOM_OVERRIDES: {},
                }
            },
        }
    )
    model.create_profile(
        PROFILE_TYPE_SHADING,
        "Same visible name",
        {"shading_position": position},
        profile_id=profile_id,
        capabilities=["positioning"],
    )
    model.assign_profile(room_id, PROFILE_TYPE_SHADING, profile_id)
    return model.data


def test_merge_keeps_same_name_profiles_separate_when_values_differ() -> None:
    merged = merge_config_models(
        _model("living", "south", 25),
        _model("office", "south", 35),
        namespace="entry-office",
    )

    catalog = merged[CONF_PROFILES][PROFILE_TYPE_SHADING]
    assert len(catalog) == 2
    office_id = merged[CONF_ROOMS]["office"][CONF_PROFILE_SELECTIONS][
        PROFILE_TYPE_SHADING
    ]
    assert office_id != "south"
    assert catalog[office_id]["settings"]["shading_position"] == 35


def test_merge_reuses_identical_stable_profile_id() -> None:
    merged = merge_config_models(
        _model("living", "south", 25),
        _model("office", "south", 25),
        namespace="entry-office",
    )

    assert set(merged[CONF_PROFILES][PROFILE_TYPE_SHADING]) == {"south"}
    assert merged[CONF_ROOMS]["office"][CONF_PROFILE_SELECTIONS][
        PROFILE_TYPE_SHADING
    ] == "south"


def test_hub_uses_one_listener_and_removes_it_on_last_route() -> None:
    hub = CoverControlHub(Mock())
    first = Mock()
    first.shared_entity_routes.return_value = {"sensor.outdoor"}
    second = Mock()
    second.shared_entity_routes.return_value = {"sensor.outdoor"}
    hub.managers = {"first": first, "second": second}
    unsubscribe = Mock()

    with patch(
        "custom_components.cover_control.hub.async_track_state_change_event",
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
    hub.profile_users = {(PROFILE_TYPE_TIME, "weekday"): {"living", "office"}}
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

    evaluation = hub.profile_evaluations[(PROFILE_TYPE_TIME, "weekday")]
    assert evaluation.next_open == profile_due
    assert living.entry_snapshot()["next_open"][0] == now + timedelta(hours=2)
    track.assert_called_once()


def test_room_override_keeps_its_time_timer_local() -> None:
    hub = CoverControlHub(Mock())
    hub.model = ConfigProfileModel(
        {
            CONF_PROFILES: {
                PROFILE_TYPE_TIME: {
                    "weekday": {
                        "id": "weekday",
                        "name": "Weekday",
                        "settings": {},
                        "capabilities": ["opening"],
                    }
                }
            },
            CONF_ROOMS: {
                "living": {
                    CONF_PROFILE_SELECTIONS: {PROFILE_TYPE_TIME: "weekday"},
                    CONF_ROOM_OVERRIDES: {},
                },
                "office": {
                    CONF_PROFILE_SELECTIONS: {PROFILE_TYPE_TIME: "weekday"},
                    CONF_ROOM_OVERRIDES: {
                        PROFILE_TYPE_TIME: {"time_up_early_workday": "07:00:00"}
                    },
                },
            },
        }
    ).data

    assert hub.room_uses_shared_time_timer("living")
    assert not hub.room_uses_shared_time_timer("office")


async def test_hub_persists_model_once_and_thins_room_entries() -> None:
    owner = SimpleNamespace(
        entry_id="owner",
        title="Living",
        data={CONF_NAME: "Living"},
        options={},
    )
    room = SimpleNamespace(
        entry_id="room",
        title="Office",
        data={CONF_NAME: "Office", CONF_CONFIG_MODEL: {"legacy": True}},
        options={},
    )
    entries = {"owner": owner, "room": room}

    def update_entry(entry, *, data, options):
        entry.data = data
        entry.options = options

    config_entries = SimpleNamespace(
        async_get_entry=lambda entry_id: entries.get(entry_id),
        async_update_entry=Mock(side_effect=update_entry),
    )
    hub = CoverControlHub(SimpleNamespace(config_entries=config_entries))
    hub.owner_entry_id = "owner"
    hub.model = _model("living", "south", 25)
    hub.model[CONF_ROOMS]["office"] = {
        CONF_NAME: "Office",
        CONF_PROFILE_SELECTIONS: {},
        CONF_ROOM_SETTINGS: {},
        CONF_SOURCE_OVERRIDES: {},
        CONF_ROOM_OVERRIDES: {},
    }
    hub.managers = {
        "owner": SimpleNamespace(room_id="living"),
        "room": SimpleNamespace(room_id="office"),
    }

    await hub.async_persist()

    assert owner.data[CONF_CONFIG_MODEL] == hub.model
    assert room.data == {
        CONF_HUB_ENTRY_ID: "owner",
        "room_id": "office",
        CONF_NAME: "Office",
    }
