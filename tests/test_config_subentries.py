"""Tests for parent profiles and native room subentry persistence."""

from types import SimpleNamespace

from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers import entity_registry as er

from custom_components.cover_control.config_subentries import (
    legacy_model_to_subentry_data,
    model_from_subentries,
)
from custom_components.cover_control.config_flow import CoverControlFlow
from custom_components.cover_control.const import DOMAIN
from custom_components.cover_control.sensor import ProfileScheduleSensor
from custom_components.cover_control.sensor import async_setup_entry as async_setup_sensors
from custom_components.cover_control.switch import async_setup_entry as async_setup_switches
from custom_components.cover_control.runtime_data import CoverControlRuntime
from custom_components.cover_control.const import (
    CONF_AUTO_TIME,
    CONF_COVERS,
    CONF_GLOBAL,
    CONF_GLOBAL_SOURCES,
    CONF_NAME,
    CONF_PROFILE_FUNCTIONS,
    CONF_PROFILE_ID,
    CONF_PROFILE_NAME,
    CONF_PROFILE_SELECTIONS,
    CONF_PROFILE_SETTINGS,
    CONF_PROFILES,
    CONF_RESIDENT_SENSOR,
    CONF_ROOM_PROFILE_ID,
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
    CONF_TIME_UP_EARLY_WORKDAY,
    FUNCTION_TIME,
    PROFILE_TYPE_SHADING,
    PROFILE_TYPES,
)


def _subentry(subentry_id: str, subentry_type: str, title: str, data: dict):
    return SimpleNamespace(
        subentry_id=subentry_id,
        subentry_type=subentry_type,
        title=title,
        data=data,
    )


def test_parent_profiles_and_room_subentries_build_one_transient_runtime_model() -> None:
    model = model_from_subentries(
        {
            CONF_GLOBAL: {CONF_GLOBAL_SOURCES: {"brightness_sensor": "sensor.lux"}},
            CONF_PROFILES: {
                "time": {},
                "shading": {
                    "profile-south": {
                        "id": "profile-south",
                        "name": "South",
                        "capabilities": ["positioning"],
                        "settings": {"shading_position": 25},
                    }
                },
                "behavior": {},
            },
        },
        [
            _subentry(
                "room-living",
                "room",
                "Living",
                {CONF_PROFILE_SELECTIONS: {PROFILE_TYPE_SHADING: "profile-south"}},
            ),
        ],
    )

    profile_id = model[CONF_ROOMS]["room-living"]["profile_id"]
    assert profile_id in model[CONF_PROFILES]
    assert model[CONF_ROOMS]["room-living"][CONF_NAME] == "Living"
    assert model[CONF_ROOMS]["room-living"]["profile_functions"]


def test_legacy_conversion_rewrites_profile_references_to_parent_profile_ids() -> None:
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
    assert len(parent[CONF_PROFILES]) == 1
    room = next(data for subentry_id, kind, _title, data in subentries if kind == "room")
    assert room["profile_id"] in parent[CONF_PROFILES]
    assert CONF_PROFILE_SELECTIONS not in room


def test_legacy_global_resident_sensor_moves_to_room_settings() -> None:
    parent, subentries = legacy_model_to_subentry_data(
        {
            CONF_GLOBAL: {
                CONF_GLOBAL_SOURCES: {
                    CONF_RESIDENT_SENSOR: "binary_sensor.sleeping",
                    "brightness_sensor": "sensor.lux",
                }
            },
            CONF_PROFILES: {"time": {}, "shading": {}, "behavior": {}},
            CONF_ROOMS: {
                "legacy-living": {
                    "name": "Living",
                    CONF_ROOM_SETTINGS: {"covers": ["cover.living"]},
                },
                "legacy-bedroom": {
                    "name": "Bedroom",
                    CONF_ROOM_SETTINGS: {
                        "covers": ["cover.bedroom"],
                        CONF_RESIDENT_SENSOR: "input_boolean.bedroom_sleep",
                    },
                },
            },
        },
        iter(["room-living", "room-bedroom"]).__next__,
    )

    assert parent[CONF_GLOBAL][CONF_GLOBAL_SOURCES] == {
        "brightness_sensor": "sensor.lux"
    }
    rooms = {
        title: data
        for _subentry_id, kind, title, data in subentries
        if kind == "room"
    }
    assert rooms["Living"][CONF_ROOM_SETTINGS][CONF_RESIDENT_SENSOR] == (
        "binary_sensor.sleeping"
    )
    assert rooms["Bedroom"][CONF_ROOM_SETTINGS][CONF_RESIDENT_SENSOR] == (
        "input_boolean.bedroom_sleep"
    )


def test_config_flow_exposes_only_native_room_subentry_type() -> None:
    supported = CoverControlFlow.async_get_supported_subentry_types(None)

    assert set(supported) == {"room"}


def test_profile_schedule_sensor_is_parent_entry_entity(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Cover Control", data={})
    sensor = ProfileScheduleSensor(hass, entry, "profile-time", "next_open")

    assert sensor.unique_id == "profile-profile-time-next_open"
    assert getattr(sensor, "config_subentry_id", None) is None


async def test_v6_setup_keeps_runtime_model_flat_and_restart_persistent(hass) -> None:
    hass.states.async_set("cover.living", "open", {"current_position": 100})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cover Control",
        version=6,
        data={
            CONF_NAME: "Cover Control",
            CONF_GLOBAL: {"sources": {}, "defaults": {}},
            CONF_PROFILES: {
                "profile-time": {
                    CONF_PROFILE_ID: "profile-time",
                    CONF_PROFILE_NAME: "Weekday",
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_TIME],
                    CONF_PROFILE_SETTINGS: {
                        CONF_AUTO_TIME: True,
                        CONF_TIME_UP_EARLY_WORKDAY: "07:00:00",
                    },
                }
            },
        },
        subentries_data=[
            {
                "subentry_id": "room-living",
                "subentry_type": "room",
                "title": "Living",
                "unique_id": "room-living",
                "data": {
                    CONF_NAME: "Living",
                    CONF_ROOM_SETTINGS: {CONF_COVERS: ["cover.living"]},
                    CONF_ROOM_PROFILE_ID: "profile-time",
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_TIME],
                    "source_overrides": {},
                    "overrides": {},
                },
            }
        ],
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    runtime = entry.runtime_data
    assert isinstance(runtime, CoverControlRuntime)
    assert not (set(runtime.model[CONF_PROFILES]) & set(PROFILE_TYPES))
    assert not (set(entry.data[CONF_PROFILES]) & set(PROFILE_TYPES))

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    runtime = entry.runtime_data
    assert isinstance(runtime, CoverControlRuntime)
    assert not (set(runtime.model[CONF_PROFILES]) & set(PROFILE_TYPES))
    assert entry.subentries["room-living"].data[CONF_ROOM_PROFILE_ID] == "profile-time"
    assert CONF_PROFILE_SELECTIONS not in entry.subentries["room-living"].data


async def test_entity_registry_cleanup_uses_v6_desired_entities(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cover Control",
        version=6,
        data={
            CONF_NAME: "Cover Control",
            CONF_GLOBAL: {"sources": {}, "defaults": {}},
            CONF_PROFILES: {
                "profile-time": {
                    CONF_PROFILE_ID: "profile-time",
                    CONF_PROFILE_NAME: "Weekday",
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_TIME],
                    CONF_PROFILE_SETTINGS: {CONF_AUTO_TIME: True},
                }
            },
        },
        subentries_data=[
            {
                "subentry_id": "room-living",
                "subentry_type": "room",
                "title": "Living",
                "unique_id": "room-living",
                "data": {
                    CONF_NAME: "Living",
                    CONF_ROOM_SETTINGS: {CONF_COVERS: ["cover.living"]},
                    CONF_ROOM_PROFILE_ID: "profile-time",
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_TIME],
                    "source_overrides": {},
                    "overrides": {},
                },
            }
        ],
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "switch",
        DOMAIN,
        "room-living-auto_brightness_enabled",
        config_entry=entry,
    )
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "profile-stale-next_open",
        config_entry=entry,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    added = []
    await async_setup_switches(hass, entry, added.extend)
    await async_setup_sensors(hass, entry, added.extend)

    added_unique_ids = {entity.unique_id for entity in added}
    registry_unique_ids = {
        entity.unique_id
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert "room-living-auto_time_enabled" in added_unique_ids
    assert "profile-profile-time-next_open" in added_unique_ids
    assert "room-living-auto_brightness_enabled" not in registry_unique_ids
    assert "profile-stale-next_open" not in registry_unique_ids


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

    assert entry.version == 6
    assert entry.title == "Cover Control"
    assert entry.unique_id == DOMAIN
    assert "config_model" not in entry.data
    assert {subentry.subentry_type for subentry in entry.subentries.values()} == {
        "room",
    }
    assert entry.data[CONF_PROFILES]
    assert isinstance(entry.runtime_data, CoverControlRuntime)
    assert len(entry.runtime_data.room_managers) == 1
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_v4_profile_subentries_migrate_to_parent_profiles(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cover Control",
        version=4,
        data={CONF_GLOBAL: {"sources": {}, "defaults": {}}},
        subentries_data=[
            {
                "subentry_id": "profile-south",
                "subentry_type": "shading_profile",
                "title": "South",
                "unique_id": "profile-south",
                "data": {
                    "capabilities": ["positioning"],
                    "settings": {"shading_position": 25},
                },
            },
            {
                "subentry_id": "room-living",
                "subentry_type": "room",
                "title": "Living",
                "unique_id": "room-living",
                "data": {
                    "name": "Living",
                    "settings": {"covers": ["cover.living"]},
                    "profiles": {"shading": "profile-south"},
                    "source_overrides": {},
                    "overrides": {},
                },
            },
        ],
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 6
    assert len(entry.data[CONF_PROFILES]) == 1
    profile = next(iter(entry.data[CONF_PROFILES].values()))
    assert profile["name"] == "South"
    assert {subentry.subentry_type for subentry in entry.subentries.values()} == {
        "room"
    }
    room = next(iter(entry.subentries.values()))
    assert room.data["profile_id"] in entry.data[CONF_PROFILES]


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
    assert second.version == 6
    assert second.data == {"hub_entry_id": first.entry_id}
    room_subentries = [
        subentry
        for subentry in first.subentries.values()
        if subentry.subentry_type == "room"
    ]
    assert {subentry.title for subentry in room_subentries} == {"Living", "Office"}
