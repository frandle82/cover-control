"""Tests for parent profiles and native room subentry persistence."""

from types import MappingProxyType
from types import SimpleNamespace

from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.cover_control.config_subentries import (
    legacy_model_to_subentry_data,
    model_from_subentries,
)
from custom_components.cover_control.config_flow import CoverControlFlow
from custom_components.cover_control import async_migrate_entry
from custom_components.cover_control.const import DOMAIN
from custom_components.cover_control.sensor import async_setup_entry as async_setup_sensors
from custom_components.cover_control.switch import async_setup_entry as async_setup_switches
from custom_components.cover_control.runtime_data import CoverControlRuntime
from custom_components.cover_control.const import (
    CONF_AUTO_TIME,
    CONF_CLOSE_POSITION,
    CONF_CONTROLLER_ENTRY_ID,
    CONF_COVERS,
    CONF_ENTRY_TYPE,
    CONF_GLOBAL,
    CONF_GLOBAL_SOURCES,
    CONF_OPEN_POSITION,
    CONF_NAME,
    CONF_PROFILE_FUNCTIONS,
    CONF_PROFILE_ID,
    CONF_PROFILE_NAME,
    CONF_PROFILE_SELECTIONS,
    CONF_PROFILE_SETTINGS,
    CONF_PROFILES,
    CONF_RESIDENT_SENSOR,
    CONF_RESIDENT_STATUS,
    CONF_ROOM_ID,
    CONF_ROOM_PROFILE_ID,
    CONF_ROOM_SETTINGS,
    CONF_ROOMS,
    CONF_SOURCE_OVERRIDES,
    CONF_SHADING_POSITION,
    CONF_VENTILATE_POSITION,
    CONF_TIME_UP_EARLY_WORKDAY,
    ENTRY_TYPE_CONTROLLER,
    ENTRY_TYPE_ROOM,
    FUNCTION_RESIDENT,
    FUNCTION_TIME,
    PROFILE_TYPE_SHADING,
    PROFILE_TYPES,
)


def _room_entries(hass, controller_entry):
    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_ROOM
        and entry.data.get(CONF_CONTROLLER_ENTRY_ID) == controller_entry.entry_id
    ]


def _room_entry(hass, controller_entry, room_id="room-living"):
    return next(
        entry
        for entry in _room_entries(hass, controller_entry)
        if entry.data.get(CONF_ROOM_ID) == room_id
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

    assert supported == {}


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

    room_entry = _room_entry(hass, entry)
    assert await hass.config_entries.async_unload(room_entry.entry_id)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    runtime = entry.runtime_data
    assert isinstance(runtime, CoverControlRuntime)
    assert not (set(runtime.model[CONF_PROFILES]) & set(PROFILE_TYPES))
    room_entry = _room_entry(hass, entry)
    assert room_entry.data[CONF_ROOM_PROFILE_ID] == "profile-time"
    assert CONF_PROFILE_SELECTIONS not in room_entry.data
    assert await hass.config_entries.async_unload(room_entry.entry_id)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_v6_room_subentry_migration_preserves_registry_links(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cover Control",
        version=6,
        data={
            CONF_NAME: "Cover Control",
            CONF_GLOBAL: {"sources": {}, "defaults": {}},
            CONF_PROFILES: {},
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
                    CONF_PROFILE_FUNCTIONS: [],
                    CONF_SOURCE_OVERRIDES: {},
                },
            }
        ],
    )
    entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id="room-living",
        identifiers={(DOMAIN, entry.entry_id, "room-living")},
        name="Living",
    )
    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "room-living-control_state",
        suggested_object_id="living_active_control",
        config_entry=entry,
        config_subentry_id="room-living",
        device_id=device.id,
    )

    assert await async_migrate_entry(hass, entry)
    await hass.async_block_till_done()

    room_entry = _room_entry(hass, entry)
    migrated_device = device_registry.async_get(device.id)
    migrated_entity = entity_registry.async_get(entity.entity_id)
    assert migrated_device is not None
    assert migrated_device.id == device.id
    assert migrated_device.config_entry_id == room_entry.entry_id
    assert migrated_device.config_subentry_id is None
    assert migrated_entity is not None
    assert migrated_entity.entity_id == entity.entity_id
    assert migrated_entity.unique_id == entity.unique_id
    assert migrated_entity.config_entry_id == room_entry.entry_id
    assert migrated_entity.config_subentry_id is None

    # Simulate a restart after the room entry was created but before the legacy
    # subentry disappeared. Migration must reuse the existing room entry.
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(
                {
                    CONF_NAME: "Living",
                    CONF_ROOM_SETTINGS: {CONF_COVERS: ["cover.living"]},
                    CONF_PROFILE_FUNCTIONS: [],
                    CONF_SOURCE_OVERRIDES: {},
                }
            ),
            subentry_id="room-living",
            subentry_type="room",
            title="Living",
            unique_id="room-living",
        ),
    )
    hass.config_entries.async_update_entry(entry, version=6)
    assert await async_migrate_entry(hass, entry)
    await hass.async_block_till_done()

    assert len(_room_entries(hass, entry)) == 1
    assert not entry.subentries


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
    room_entry = _room_entry(hass, entry)
    if room_entry.state is not ConfigEntryState.LOADED:
        assert await hass.config_entries.async_setup(room_entry.entry_id)
        await hass.async_block_till_done()
    added = []
    await async_setup_switches(hass, room_entry, added.extend)
    await async_setup_sensors(hass, room_entry, added.extend)

    added_unique_ids = {entity.unique_id for entity in added}
    room_entities = [
        entity for entity in added if entity.unique_id.startswith("room-living-")
    ]
    assert room_entities
    assert {
        getattr(entity, "_attr_config_subentry_id", None) for entity in room_entities
    } == {None}
    assert all(
        entity.device_info["identifiers"] == {(DOMAIN, entry.entry_id, "room-living")}
        for entity in room_entities
    )
    registry_unique_ids = {
        entity.unique_id
        for entity in er.async_entries_for_config_entry(registry, room_entry.entry_id)
    }
    assert "room-living-auto_time_enabled" in added_unique_ids
    assert "room-living-auto_brightness_enabled" not in registry_unique_ids
    assert "profile-stale-next_open" not in registry_unique_ids
    assert await hass.config_entries.async_unload(room_entry.entry_id)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_resident_entities_follow_selected_profile_function(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cover Control",
        version=6,
        data={
            CONF_NAME: "Cover Control",
            CONF_GLOBAL: {"sources": {}, "defaults": {}},
            CONF_PROFILES: {
                "profile-resident": {
                    CONF_PROFILE_ID: "profile-resident",
                    CONF_PROFILE_NAME: "Resident",
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_TIME, FUNCTION_RESIDENT],
                    CONF_PROFILE_SETTINGS: {
                        CONF_AUTO_TIME: True,
                        CONF_RESIDENT_STATUS: True,
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
                    CONF_ROOM_PROFILE_ID: "profile-resident",
                    CONF_PROFILE_FUNCTIONS: [FUNCTION_TIME],
                    CONF_SOURCE_OVERRIDES: {},
                },
            }
        ],
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "switch",
        DOMAIN,
        "room-living-resident_status_enabled",
        config_entry=entry,
    )
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "room-living-resident_status",
        config_entry=entry,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    room_entry = _room_entry(hass, entry)
    if room_entry.state is not ConfigEntryState.LOADED:
        assert await hass.config_entries.async_setup(room_entry.entry_id)
        await hass.async_block_till_done()
    added = []
    await async_setup_switches(hass, room_entry, added.extend)
    await async_setup_sensors(hass, room_entry, added.extend)

    added_unique_ids = {entity.unique_id for entity in added}
    registry_unique_ids = {
        entity.unique_id
        for entity in er.async_entries_for_config_entry(registry, room_entry.entry_id)
    }
    assert "room-living-auto_time_enabled" in added_unique_ids
    assert "room-living-resident_status_enabled" not in added_unique_ids
    assert "room-living-resident_status" not in added_unique_ids
    assert "room-living-resident_status_enabled" not in registry_unique_ids
    assert "room-living-resident_status" not in registry_unique_ids

    hass.config_entries.async_update_entry(
        room_entry,
        data={
            **room_entry.data,
            CONF_PROFILE_FUNCTIONS: [FUNCTION_TIME, FUNCTION_RESIDENT],
        },
    )
    await hass.config_entries.async_reload(room_entry.entry_id)
    await hass.async_block_till_done()
    added = []
    await async_setup_switches(hass, room_entry, added.extend)
    await async_setup_sensors(hass, room_entry, added.extend)

    added_unique_ids = {entity.unique_id for entity in added}
    assert "room-living-resident_status_enabled" in added_unique_ids
    assert "room-living-resident_status" in added_unique_ids
    assert await hass.config_entries.async_unload(room_entry.entry_id)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_room_entries_own_room_managers_and_entities(hass) -> None:
    hass.states.async_set("cover.living", "open", {"current_position": 100})
    hass.states.async_set("cover.office", "open", {"current_position": 100})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cover Control",
        version=7,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER,
            CONF_GLOBAL: {"sources": {}, "defaults": {}},
            CONF_PROFILES: {},
        },
    )
    entry.add_to_hass(hass)
    room_living = MockConfigEntry(
        domain=DOMAIN,
        title="Living",
        version=7,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_ROOM,
            CONF_CONTROLLER_ENTRY_ID: entry.entry_id,
            CONF_ROOM_ID: "room-living",
            "name": "Living",
            "settings": {
                "covers": ["cover.living"],
                "auto_time_enabled": False,
            },
            "source_overrides": {},
            "overrides": {},
        },
    )
    room_living.add_to_hass(hass)
    room_office = MockConfigEntry(
        domain=DOMAIN,
        title="Office",
        version=7,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_ROOM,
            CONF_CONTROLLER_ENTRY_ID: entry.entry_id,
            CONF_ROOM_ID: "room-office",
            "name": "Office",
            "settings": {
                "covers": ["cover.office"],
                "auto_time_enabled": True,
            },
            "source_overrides": {},
            "overrides": {},
        },
    )
    room_office.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    if room_living.state is not ConfigEntryState.LOADED:
        assert await hass.config_entries.async_setup(room_living.entry_id)
    if room_office.state is not ConfigEntryState.LOADED:
        assert await hass.config_entries.async_setup(room_office.entry_id)
    await hass.async_block_till_done()

    assert isinstance(entry.runtime_data, CoverControlRuntime)
    assert entry.runtime_data.room_managers == {}
    assert set(entry.runtime_data.hub.managers) == {"room-living", "room-office"}
    assert set(room_living.runtime_data.room_managers) == {"room-living"}
    assert set(room_living.runtime_data.room_managers["room-living"].controllers) == {
        "cover.living"
    }
    assert set(room_office.runtime_data.room_managers) == {"room-office"}
    switches = [
        entity
        for entity in er.async_entries_for_config_entry(
            er.async_get(hass), room_living.entry_id
        )
        if entity.domain == "switch"
    ]
    assert [entity.unique_id for entity in switches] == [
        "room-living-auto_time_enabled"
    ]
    assert hass.states.get(switches[0].entity_id).state == "off"
    assert not er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)

    assert await hass.config_entries.async_unload(room_living.entry_id)
    await hass.async_block_till_done()

    assert "room-living" not in entry.runtime_data.hub.managers
    assert "room-office" in entry.runtime_data.hub.managers
    assert await hass.config_entries.async_unload(room_office.entry_id)
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

    assert entry.version == 7
    assert entry.title == "Cover Control"
    assert entry.unique_id == DOMAIN
    assert "config_model" not in entry.data
    assert entry.data[CONF_ENTRY_TYPE] == ENTRY_TYPE_CONTROLLER
    assert not entry.subentries
    assert len(_room_entries(hass, entry)) == 1
    assert entry.data[CONF_PROFILES]
    assert isinstance(entry.runtime_data, CoverControlRuntime)
    assert entry.runtime_data.room_managers == {}
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
                    "settings": {
                        CONF_OPEN_POSITION: 100,
                        CONF_CLOSE_POSITION: 0,
                        CONF_SHADING_POSITION: 25,
                        CONF_VENTILATE_POSITION: 35,
                    },
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

    assert entry.version == 7
    assert entry.data[CONF_ENTRY_TYPE] == ENTRY_TYPE_CONTROLLER
    room = _room_entry(hass, entry).data
    profile = entry.data[CONF_PROFILES][room[CONF_ROOM_PROFILE_ID]]
    assert CONF_SHADING_POSITION not in profile[CONF_PROFILE_SETTINGS]
    assert room[CONF_ROOM_SETTINGS][CONF_SHADING_POSITION] == 25
    assert room[CONF_ROOM_SETTINGS][CONF_OPEN_POSITION] == 100
    assert room[CONF_ROOM_SETTINGS][CONF_CLOSE_POSITION] == 0
    assert room[CONF_ROOM_SETTINGS][CONF_VENTILATE_POSITION] == 35
    assert len(entry.data[CONF_PROFILES]) == 1
    profile = next(iter(entry.data[CONF_PROFILES].values()))
    assert profile["name"] == "South"
    assert not entry.subentries
    assert room["profile_id"] in entry.data[CONF_PROFILES]


async def test_v5_parent_migrates_to_v7_room_entries_in_one_run(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cover Control",
        version=5,
        data={
            CONF_GLOBAL: {"sources": {}, "defaults": {}},
            CONF_PROFILES: {
                profile_type: {} for profile_type in PROFILE_TYPES
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
                    CONF_PROFILE_SELECTIONS: {},
                    CONF_SOURCE_OVERRIDES: {},
                },
            },
        ],
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 7
    assert entry.data[CONF_ENTRY_TYPE] == ENTRY_TYPE_CONTROLLER
    assert not entry.subentries
    room = _room_entry(hass, entry).data
    assert room[CONF_ENTRY_TYPE] == ENTRY_TYPE_ROOM
    assert room[CONF_CONTROLLER_ENTRY_ID] == entry.entry_id


async def test_v6_parent_migrates_to_v7_room_entries_in_one_run(hass) -> None:
    profile_id = "profile-main"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cover Control",
        version=6,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER,
            CONF_GLOBAL: {"sources": {}, "defaults": {}},
            CONF_PROFILES: {
                profile_id: {
                    CONF_PROFILE_ID: profile_id,
                    CONF_PROFILE_NAME: "Main",
                    CONF_PROFILE_SETTINGS: {},
                    CONF_PROFILE_FUNCTIONS: [],
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
                    CONF_ROOM_PROFILE_ID: profile_id,
                    CONF_PROFILE_FUNCTIONS: [],
                    CONF_SOURCE_OVERRIDES: {},
                },
            },
        ],
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 7
    assert entry.data[CONF_ENTRY_TYPE] == ENTRY_TYPE_CONTROLLER
    assert not entry.subentries
    room_entry = _room_entry(hass, entry)
    room = room_entry.data
    assert room[CONF_ENTRY_TYPE] == ENTRY_TYPE_ROOM
    assert room[CONF_CONTROLLER_ENTRY_ID] == entry.entry_id
    assert room[CONF_ROOM_PROFILE_ID] == profile_id
    assert await hass.config_entries.async_unload(room_entry.entry_id)
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
    assert first in entries
    assert second.version == 7
    assert second.data == {"hub_entry_id": first.entry_id}
    assert {entry.title for entry in _room_entries(hass, first)} == {"Living", "Office"}
