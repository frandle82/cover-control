"""Tests for reusable profiles, assignments, and sparse room overrides."""

import pytest

from custom_components.cover_control.config_profiles import (
    ConfigProfileModel,
    ProfileInUseError,
)
from custom_components.cover_control.config_resolver import resolve_config_model
from custom_components.cover_control.const import (
    CONF_CONFIG_VERSION,
    CONF_GLOBAL,
    CONF_GLOBAL_DEFAULTS,
    CONF_GLOBAL_SOURCES,
    CONF_NAME,
    CONF_PROFILE_SELECTIONS,
    CONF_PROFILES,
    CONF_ROOM_OVERRIDES,
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
    CONF_SHADING_POSITION,
    CONF_SHADING_WAITINGTIME_END,
    CONF_SOURCE_OVERRIDES,
    CONFIG_MODEL_VERSION,
    PROFILE_TYPE_BEHAVIOR,
    PROFILE_TYPE_SHADING,
    PROFILE_TYPE_TIME,
)


def _model() -> ConfigProfileModel:
    return ConfigProfileModel(
        {
            CONF_CONFIG_VERSION: CONFIG_MODEL_VERSION,
            CONF_GLOBAL: {
                CONF_GLOBAL_SOURCES: {},
                CONF_GLOBAL_DEFAULTS: {},
            },
            CONF_PROFILES: {
                PROFILE_TYPE_TIME: {},
                PROFILE_TYPE_SHADING: {},
                PROFILE_TYPE_BEHAVIOR: {},
            },
            CONF_ROOMS: {
                "living": {
                    CONF_NAME: "Living",
                    CONF_PROFILE_SELECTIONS: {},
                    CONF_ROOM_SETTINGS: {},
                    CONF_SOURCE_OVERRIDES: {},
                    CONF_ROOM_OVERRIDES: {},
                },
                "office": {
                    CONF_NAME: "Office",
                    CONF_PROFILE_SELECTIONS: {},
                    CONF_ROOM_SETTINGS: {},
                    CONF_SOURCE_OVERRIDES: {},
                    CONF_ROOM_OVERRIDES: {},
                },
            },
        }
    )


def test_create_and_assign_profile_resolves_values_without_copying() -> None:
    model = _model()
    profile_id = model.create_profile(
        PROFILE_TYPE_SHADING,
        "South",
        {CONF_SHADING_POSITION: 30},
        profile_id="south",
    )
    model.assign_profile("living", PROFILE_TYPE_SHADING, profile_id)

    assert resolve_config_model(model.data, "living")[CONF_SHADING_POSITION] == 30
    assert CONF_SHADING_POSITION not in model.data[CONF_ROOMS]["living"]


def test_profile_edit_returns_and_updates_only_affected_rooms() -> None:
    model = _model()
    model.create_profile(
        PROFILE_TYPE_SHADING,
        "South",
        {CONF_SHADING_POSITION: 30},
        profile_id="south",
    )
    model.assign_profile("living", PROFILE_TYPE_SHADING, "south")

    affected = model.update_profile(
        PROFILE_TYPE_SHADING, "south", {CONF_SHADING_POSITION: 35}
    )

    assert affected == {"living"}
    assert resolve_config_model(model.data, "living")[CONF_SHADING_POSITION] == 35


def test_rename_keeps_room_reference_stable() -> None:
    model = _model()
    model.create_profile(
        PROFILE_TYPE_SHADING, "South", {}, profile_id="stable-id"
    )
    model.assign_profile("living", PROFILE_TYPE_SHADING, "stable-id")

    model.rename_profile(PROFILE_TYPE_SHADING, "stable-id", "Renamed")

    assert (
        model.data[CONF_ROOMS]["living"][CONF_PROFILE_SELECTIONS][
            PROFILE_TYPE_SHADING
        ]
        == "stable-id"
    )


def test_delete_referenced_profile_is_blocked() -> None:
    model = _model()
    model.create_profile(PROFILE_TYPE_SHADING, "South", {}, profile_id="south")
    model.assign_profile("living", PROFILE_TYPE_SHADING, "south")

    with pytest.raises(ProfileInUseError) as error:
        model.delete_profile(PROFILE_TYPE_SHADING, "south")

    assert error.value.rooms == {"living"}


def test_delete_unused_profile_succeeds() -> None:
    model = _model()
    model.create_profile(PROFILE_TYPE_SHADING, "South", {}, profile_id="south")

    model.delete_profile(PROFILE_TYPE_SHADING, "south")

    assert "south" not in model.data[CONF_PROFILES][PROFILE_TYPE_SHADING]


def test_single_override_keeps_other_profile_values() -> None:
    model = _model()
    model.create_profile(
        PROFILE_TYPE_SHADING,
        "South",
        {CONF_SHADING_POSITION: 30, CONF_SHADING_WAITINGTIME_END: 600},
        profile_id="south",
    )
    model.assign_profile("living", PROFILE_TYPE_SHADING, "south")
    model.set_override("living", PROFILE_TYPE_SHADING, CONF_SHADING_POSITION, 25)

    resolved = resolve_config_model(model.data, "living")
    assert resolved[CONF_SHADING_POSITION] == 25
    assert resolved[CONF_SHADING_WAITINGTIME_END] == 600
    assert model.data[CONF_ROOMS]["living"][CONF_ROOM_OVERRIDES] == {
        PROFILE_TYPE_SHADING: {CONF_SHADING_POSITION: 25}
    }


def test_profile_change_respects_waiting_time_override() -> None:
    model = _model()
    model.create_profile(
        PROFILE_TYPE_SHADING,
        "South",
        {CONF_SHADING_WAITINGTIME_END: 600},
        profile_id="south",
    )
    for room_id in ("living", "office"):
        model.assign_profile(room_id, PROFILE_TYPE_SHADING, "south")
    model.set_override(
        "office", PROFILE_TYPE_SHADING, CONF_SHADING_WAITINGTIME_END, 300
    )

    model.update_profile(
        PROFILE_TYPE_SHADING, "south", {CONF_SHADING_WAITINGTIME_END: 900}
    )

    assert resolve_config_model(model.data, "living")[CONF_SHADING_WAITINGTIME_END] == 900
    assert resolve_config_model(model.data, "office")[CONF_SHADING_WAITINGTIME_END] == 300


def test_remove_override_falls_back_to_profile_immediately() -> None:
    model = _model()
    model.create_profile(
        PROFILE_TYPE_SHADING,
        "South",
        {CONF_SHADING_POSITION: 30},
        profile_id="south",
    )
    model.assign_profile("living", PROFILE_TYPE_SHADING, "south")
    model.set_override("living", PROFILE_TYPE_SHADING, CONF_SHADING_POSITION, 25)

    model.remove_override("living", PROFILE_TYPE_SHADING, CONF_SHADING_POSITION)

    assert resolve_config_model(model.data, "living")[CONF_SHADING_POSITION] == 30
