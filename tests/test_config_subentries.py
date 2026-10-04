"""Tests for parent entry and native room/profile subentry persistence."""

from types import SimpleNamespace

from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers import entity_registry as er

from custom_components.cover_control.config_subentries import (
    legacy_model_to_subentry_data,
    model_from_subentries,
)
from custom_components.cover_control.config_flow import CoverControlFlow
from custom_components.cover_control.const import DOMAIN
from custom_components.cover_control.runtime_data import CoverControlRuntime
from custom_components.cover_control.const import (
    CONF_GLOBAL,
    CONF_GLOBAL_SOURCES,
    CONF_NAME,
    CONF_PROFILE_SELECTIONS,
    CONF_PROFILES,
    CONF_ROOMS,
    PROFILE_TYPE_SHADING,
)


def _subentry(subentry_id: str, subentry_type: str, title: str, data: dict):
    return SimpleNamespace(
        subentry_id=subentry_id,
        subentry_type=subentry_type,
        title=title,
        data=data,
    )


def test_native_subentries_build_one_transient_runtime_model() -> None:
    model = model_from_subentries(
        {CONF_GLOBAL: {CONF_GLOBAL_SOURCES: {"brightness_sensor": "sensor.lux"}}},
        [
            _subentry(
                "profile-south",
                "shading_profile",
                "South",
                {"capabilities": ["positioning"], "settings": {"shading_position": 25}},
            ),
            _subentry(
                "room-living",
                "room",
                "Living",
                {CONF_PROFILE_SELECTIONS: {PROFILE_TYPE_SHADING: "profile-south"}},
            ),
        ],
    )

    assert set(model[CONF_PROFILES][PROFILE_TYPE_SHADING]) == {"profile-south"}
    assert model[CONF_ROOMS]["room-living"][CONF_NAME] == "Living"
    assert model[CONF_ROOMS]["room-living"][CONF_PROFILE_SELECTIONS] == {
        PROFILE_TYPE_SHADING: "profile-south"
    }


def test_legacy_conversion_rewrites_profile_references_to_subentry_ids() -> None:
    ids = iter(["new-profile", "new-room"])
    parent, subentries = legacy_model_to_subentry_data(
        {
            CONF_GLOBAL: {CONF_GLOBAL_SOURCES: {"brightness_sensor": "sensor.lux"}},
            CONF_PROFILES: {
                "time": {},
                "shading": {
                    "legacy-south": {
                        "id": "legacy-south",
                        "name": "South",
                        "settings": {"shading_position": 25},
                        "capabilities": ["positioning"],
                    }
                },
                "behavior": {},
            },
            CONF_ROOMS: {
                "legacy-living": {
                    "name": "Living",
                    CONF_PROFILE_SELECTIONS: {"shading": "legacy-south"},
                }
            },
        },
        lambda: next(ids),
    )

    assert parent[CONF_GLOBAL][CONF_GLOBAL_SOURCES] == {"brightness_sensor": "sensor.lux"}
    room = next(data for subentry_id, kind, _title, data in subentries if kind == "room")
    assert room[CONF_PROFILE_SELECTIONS] == {"shading": "new-profile"}


def test_config_flow_exposes_only_native_room_and_profile_subentry_types() -> None:
    supported = CoverControlFlow.async_get_supported_subentry_types(None)

    assert set(supported) == {
        "room",
        "time_profile",
        "shading_profile",
        "behavior_profile",
    }


async def test_parent_runtime_owns_room_managers(hass) -> None:
    hass.states.async_set("cover.living", "open", {"current_position": 100})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cover Control",
        version=3,
        data={CONF_GLOBAL: {"sources": {}, "defaults": {}}},
        subentries_data=[
            {
                "subentry_id": "room-living",
                "subentry_type": "room",
                "title": "Living",
                "unique_id": "room-living",
                "data": {
                    "name": "Living",
                    "settings": {
                        "covers": ["cover.living"],
                        "auto_time_enabled": False,
                    },
                    "profiles": {},
                    "source_overrides": {},
                    "overrides": {},
                },
            }
        ],
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert isinstance(entry.runtime_data, CoverControlRuntime)
    assert set(entry.runtime_data.room_managers) == {"room-living"}
    assert set(entry.runtime_data.room_managers["room-living"].controllers) == {
        "cover.living"
    }
    switches = [
        entity
        for entity in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if entity.domain == "switch"
    ]
    assert [entity.unique_id for entity in switches] == [
        "room-living-auto_time_enabled"
    ]
    assert hass.states.get(switches[0].entity_id).state == "off"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_legacy_entry_migrates_to_parent_and_native_subentries(hass) -> None:
    hass.states.async_set("cover.legacy", "open", {"current_position": 100})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Legacy Room",
        version=1,
        data={"name": "Legacy Room", "covers": ["cover.legacy"]},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 4
    assert entry.title == "Cover Control"
    assert entry.unique_id == DOMAIN
    assert "config_model" not in entry.data
    assert {subentry.subentry_type for subentry in entry.subentries.values()} == {
        "room",
        "time_profile",
        "shading_profile",
        "behavior_profile",
    }
    assert isinstance(entry.runtime_data, CoverControlRuntime)
    assert len(entry.runtime_data.room_managers) == 1
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_multiple_legacy_entries_consolidate_into_one_parent(hass) -> None:
    first = MockConfigEntry(
        domain=DOMAIN,
        title="Living",
        version=1,
        data={"name": "Living", "covers": ["cover.living"]},
    )
    second = MockConfigEntry(
        domain=DOMAIN,
        title="Office",
        version=1,
        data={"name": "Office", "covers": ["cover.office"]},
    )
    first.add_to_hass(hass)
    second.add_to_hass(hass)

    assert await hass.config_entries.async_setup(first.entry_id)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert [entry.entry_id for entry in entries] == [first.entry_id]
    room_subentries = [
        subentry
        for subentry in first.subentries.values()
        if subentry.subentry_type == "room"
    ]
    assert {subentry.title for subentry in room_subentries} == {"Living", "Office"}
