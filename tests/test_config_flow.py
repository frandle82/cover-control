"""Config flow tests for Cover Control."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from probatio import to_field_list

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import ServiceRegistry
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.json import json_dumps
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cover_control.config_flow import INITIAL_FEATURE_KEYS
from custom_components.cover_control.config_profile_schema import (
    CONF_GLOBAL_DEFAULT_FIELDS,
    CONF_OVERRIDE_FIELDS,
    CONF_PROFILE_CAPABILITIES_FIELD,
    CONF_PROFILE_FIELDS,
    PROFILE_CAPABILITY_KEYS,
)
from custom_components.cover_control.config_resolver import (
    GLOBAL_SOURCE_KEYS,
    ROOM_SOURCE_OVERRIDE_KEYS,
    config_entry_room_id,
    entry_config_model,
    resolve_entry_config,
)
from custom_components.cover_control import const as c
from custom_components.cover_control.switch import (
    AUTOMATION_TOGGLES,
    async_setup_entry as async_setup_switch_entry,
)
from custom_components.cover_control.const import (
    CONF_AUTO_SHADING,
    CONF_AUTO_TIME,
    CONF_AUTO_VENTILATE,
    CONF_BRIGHTNESS_SENSOR,
    CONF_CONFIG_MODEL,
    CONF_COVERS,
    CONF_ENABLE_LOGBOOK_COVER,
    CONF_LOCKOUT_POSITION,
    CONF_MANUAL_SCHEDULE_ADOPTION,
    CONF_ROOM,
    CONF_SHADING_INDEPENDENT_HOLDS_END,
    CONF_SHADING_POSITION,
    DEFAULT_NAME,
    DOMAIN,
)

REQUIRES_NEW_HA = (
    not hasattr(selector, "ConditionSelector")
    or not hasattr(ServiceRegistry, "async_services_for_domain")
)


def test_translation_files_have_matching_structure() -> None:
    """Keep source strings and English/German translations structurally aligned."""

    translation_dir = Path("custom_components/cover_control")
    paths = [
        translation_dir / "strings.json",
        translation_dir / "translations/en.json",
        translation_dir / "translations/de.json",
    ]

    def _shape(value):
        if isinstance(value, dict):
            return {key: _shape(child) for key, child in value.items()}
        return None

    structures = [_shape(json.loads(path.read_text())) for path in paths]
    assert structures[0] == structures[1] == structures[2]


def _frontend_initial_data(data_schema) -> dict:
    """Mirror the frontend's relevant default handling for expandable sections."""

    fields = to_field_list(data_schema, custom_serializer=cv.custom_serializer)

    def _defaults(serialized_fields: list[dict]) -> dict:
        data = {}
        for field in serialized_fields:
            if "default" in field:
                data[field["name"]] = field["default"]
            elif field.get("type") == "expandable":
                nested = _defaults(field["schema"])
                if field.get("required") or nested:
                    data[field["name"]] = nested
        return data

    return json.loads(json_dumps(_defaults(fields)))


def _entry(hass, *, data: dict | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living",
        data=data
        or {CONF_NAME: "Living", CONF_COVERS: ["cover.living"]},
    )
    entry.add_to_hass(hass)
    return entry


async def _open_options_step(hass, entry, *steps: str):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    if steps and steps[0] in {"global_settings", "profiles"}:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "hub_settings"}
        )
    elif steps and steps[0] in {
        "general",
        "room_profiles",
        "advanced",
        "diagnostics",
    }:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "room_settings"}
        )
    for step in steps:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": step}
        )
    return result


async def _finish_options_flow(hass, result):
    """Finish a flow after asserting a nested step's parent destination."""

    flow = hass.config_entries.options._progress[result["flow_id"]]
    return await hass.config_entries.options._async_handle_step(flow, "finish", None)


async def _create_profile(hass, entry, profile_type: str, data: dict):
    result = await _open_options_step(
        hass, entry, "profiles", f"{profile_type}_profiles"
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"profile_action": "create"}
    )
    assert result["step_id"] == "profile_setup"
    selected_fields = set(data.pop(CONF_PROFILE_FIELDS, ()))
    capabilities = [
        capability
        for capability, keys in PROFILE_CAPABILITY_KEYS[profile_type].items()
        if selected_fields & keys
    ]
    profile_name = data.pop("profile_name")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "profile_name": profile_name,
            CONF_PROFILE_CAPABILITIES_FIELD: capabilities,
        },
    )
    assert result["step_id"] == "profile_edit"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], data
    )
    assert result["step_id"] == f"{profile_type}_profiles"
    result = await _finish_options_flow(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    catalog = entry.data[CONF_CONFIG_MODEL]["profiles"][profile_type]
    return next(reversed(catalog.values()))


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_user_flow_can_be_completed_without_errors(hass):
    """Ensure config flow reaches entry creation without internal server errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test",
            CONF_ROOM: "living-room",
            CONF_COVERS: ["cover.test_cover"],
            "automation_features": {
                CONF_AUTO_VENTILATE: True,
                CONF_AUTO_SHADING: True,
            },
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "windows"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "schedule"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "shading"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test"
    resolved = resolve_entry_config(
        result["data"],
        {},
        room_id=config_entry_room_id(result["data"], "new-entry"),
    )
    assert resolved[CONF_COVERS] == ["cover.test_cover"]


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_user_flow_exposes_nested_defaults_to_frontend(hass):
    """Ensure collapsed sections do not hide required fields without values."""

    hass.states.async_set(
        "cover.test_cover",
        "open",
        {"current_position": 100},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    initial_data = _frontend_initial_data(result["data_schema"])
    assert initial_data["automation_features"] == {
        key: False for key in INITIAL_FEATURE_KEYS
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "All functions",
            CONF_ROOM: "living-room",
            CONF_COVERS: ["cover.test_cover"],
            "automation_features": {key: True for key in INITIAL_FEATURE_KEYS},
        },
    )
    assert result["step_id"] == "windows"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "schedule"
    schedule_data = _frontend_initial_data(result["data_schema"])
    assert schedule_data["positions"]["open_position"] == 100
    assert schedule_data["tilt_positions"]["open_tilt_position"] == 50
    assert schedule_data["timing"][CONF_MANUAL_SCHEDULE_ADOPTION] is False
    assert schedule_data["behavior"][CONF_ENABLE_LOGBOOK_COVER] is False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], schedule_data
    )
    assert result["step_id"] == "shading"
    shading_data = _frontend_initial_data(result["data_schema"])
    assert shading_data["brightness_controls"]
    assert shading_data["sun_controls"]
    assert shading_data["shading_controls"]
    assert (
        shading_data["shading_controls"][CONF_SHADING_INDEPENDENT_HOLDS_END]
        is False
    )
    assert shading_data["manual_override"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], shading_data
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_options_flow_loads_for_existing_entry(hass):
    """Ensure options flow schema can be built successfully."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={CONF_NAME: DEFAULT_NAME, CONF_COVERS: ["cover.test_cover"]},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "menu"

    result = await _finish_options_flow(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_options_menu_exposes_hierarchical_sections(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living",
        data={CONF_NAME: "Living", CONF_COVERS: ["cover.living"]},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["menu_options"] == [
        "hub_settings",
        "room_settings",
        "finish",
    ]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "hub_settings"}
    )
    assert result["menu_options"] == [
        "global_settings",
        "profiles",
        "profile_evaluation",
    ]


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_room_advanced_menu_has_no_parallel_profile_editors(hass):
    entry = _entry(hass)
    result = await _open_options_step(hass, entry, "advanced")

    assert result["menu_options"] == [
        "hardware",
        "contact_sensors",
        "geometry",
        "additional_conditions",
    ]
    assert not {
        "positions",
        "functions",
        "behavior",
        "time_control",
        "brightness",
        "sun_elevation",
        "shading",
        "resident",
    } & set(result["menu_options"])


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_all_function_switches_exist_independent_of_initial_state(hass):
    """Every room exposes the five existing function toggles."""

    entry = _entry(
        hass,
        data={
            CONF_NAME: "Living",
            CONF_COVERS: ["cover.living"],
            c.CONF_AUTO_TIME: False,
            c.CONF_AUTO_VENTILATE: False,
            c.CONF_AUTO_BRIGHTNESS: True,
            c.CONF_AUTO_SUN: False,
            c.CONF_AUTO_SHADING: True,
        },
    )
    entities = []

    await async_setup_switch_entry(hass, entry, entities.extend)

    expected_keys = {key for key, _translation_key in AUTOMATION_TOGGLES}
    assert {entity._key for entity in entities} == expected_keys
    assert len(entities) == 5
    for entity in entities:
        entity.hass = hass
    states = {entity._key: entity.is_on for entity in entities}
    assert states[c.CONF_AUTO_BRIGHTNESS] is True
    assert states[c.CONF_AUTO_SHADING] is True
    assert states[c.CONF_AUTO_TIME] is False
    assert states[c.CONF_AUTO_VENTILATE] is False
    assert states[c.CONF_AUTO_SUN] is False


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_time_profile_can_be_created_with_native_fields(hass):
    """U1: Persist selected time values without a JSON editor."""

    entry = _entry(hass)
    profile = await _create_profile(
        hass,
        entry,
        c.PROFILE_TYPE_TIME,
        {
            "profile_name": "Weekday",
            CONF_PROFILE_FIELDS: [c.CONF_AUTO_TIME, c.CONF_TIME_UP_EARLY_WORKDAY],
            "time_features": {c.CONF_AUTO_TIME: True},
            "workday_times": {c.CONF_TIME_UP_EARLY_WORKDAY: "06:30:00"},
        },
    )

    assert profile["name"] == "Weekday"
    assert profile["settings"] == {
        c.CONF_AUTO_TIME: True,
        c.CONF_TIME_UP_EARLY_WORKDAY: "06:30:00",
    }


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_shading_profile_can_be_created_with_native_fields(hass):
    """U2: Persist number, select, multi-select, and boolean shading values."""

    entry = _entry(hass)
    selected = [
        c.CONF_SHADING_POSITION,
        c.CONF_SHADING_FORECAST_TYPE,
        c.CONF_SHADING_CONDITIONS_START_AND,
        c.CONF_SHADING_END_IMMEDIATE_BY_SUN_POSITION,
    ]
    profile = await _create_profile(
        hass,
        entry,
        c.PROFILE_TYPE_SHADING,
        {
            "profile_name": "South",
            CONF_PROFILE_FIELDS: selected,
            "shading_targets": {c.CONF_SHADING_POSITION: 31},
            "shading_forecast": {c.CONF_SHADING_FORECAST_TYPE: "hourly"},
            "shading_conditions": {
                c.CONF_SHADING_CONDITIONS_START_AND: [
                    c.SHADING_CONDITION_AZIMUTH,
                    c.SHADING_CONDITION_ELEVATION,
                ]
            },
            "shading_waits": {
                c.CONF_SHADING_END_IMMEDIATE_BY_SUN_POSITION: True
            },
        },
    )

    assert profile["settings"] == {
        c.CONF_SHADING_POSITION: 31,
        c.CONF_SHADING_FORECAST_TYPE: "hourly",
        c.CONF_SHADING_CONDITIONS_START_AND: [
            c.SHADING_CONDITION_AZIMUTH,
            c.SHADING_CONDITION_ELEVATION,
        ],
        c.CONF_SHADING_END_IMMEDIATE_BY_SUN_POSITION: True,
    }


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_behavior_profile_can_be_created_with_native_fields(hass):
    """U3: Persist typed behavior values without materializing fallbacks."""

    entry = _entry(hass)
    profile = await _create_profile(
        hass,
        entry,
        c.PROFILE_TYPE_BEHAVIOR,
        {
            "profile_name": "Standard",
            CONF_PROFILE_FIELDS: [
                c.CONF_MANUAL_OVERRIDE_MINUTES,
                c.CONF_MANUAL_OVERRIDE_RESET_MODE,
                c.CONF_MANUAL_OVERRIDE_BLOCK_SHADING,
            ],
            "manual_override": {
                c.CONF_MANUAL_OVERRIDE_MINUTES: 45,
                c.CONF_MANUAL_OVERRIDE_RESET_MODE: c.MANUAL_OVERRIDE_RESET_TIMEOUT,
                c.CONF_MANUAL_OVERRIDE_BLOCK_SHADING: True,
            },
        },
    )

    assert profile["settings"] == {
        c.CONF_MANUAL_OVERRIDE_MINUTES: 45,
        c.CONF_MANUAL_OVERRIDE_RESET_MODE: c.MANUAL_OVERRIDE_RESET_TIMEOUT,
        c.CONF_MANUAL_OVERRIDE_BLOCK_SHADING: True,
    }


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_existing_profile_round_trip_is_sparse_and_keeps_stable_id(hass):
    """U4-U7: Load old values, preserve unknown data, and remove optional values."""

    entry = _entry(hass)
    room_id = config_entry_room_id(entry.data, entry.entry_id)
    model = entry_config_model(entry.data, {}, room_id=room_id)
    profile_id = f"legacy-{entry.entry_id}-shading"
    settings = model["profiles"][c.PROFILE_TYPE_SHADING][profile_id]["settings"]
    settings.clear()
    settings.update(
        {
            c.CONF_SHADING_POSITION: 30,
            c.CONF_SHADING_WAITINGTIME_START: 300,
            "future_profile_key": "keep-me",
        }
    )
    hass.config_entries.async_update_entry(
        entry,
        data={c.CONF_ROOM_ID: room_id, CONF_NAME: "Living", CONF_CONFIG_MODEL: model},
    )

    result = await _open_options_step(
        hass, entry, "profiles", "shading_profiles"
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"profile_action": "edit", "profile_id": profile_id},
    )
    assert result["step_id"] == "profile_setup"
    setup = _frontend_initial_data(result["data_schema"])
    assert setup[CONF_PROFILE_CAPABILITIES_FIELD] == ["positioning", "waiting"]
    setup["profile_name"] = "South renamed"
    setup[CONF_PROFILE_CAPABILITIES_FIELD] = ["positioning"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], setup
    )
    initial = _frontend_initial_data(result["data_schema"])
    assert initial["shading_targets"][c.CONF_SHADING_POSITION] == 30
    assert "shading_waits" not in initial
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], initial
    )
    assert result["step_id"] == "shading_profiles"
    result = await _finish_options_flow(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY

    catalog = entry.data[CONF_CONFIG_MODEL]["profiles"][c.PROFILE_TYPE_SHADING]
    assert profile_id in catalog
    assert catalog[profile_id]["name"] == "South renamed"
    assert catalog[profile_id]["settings"] == {
        c.CONF_SHADING_POSITION: 30,
        "future_profile_key": "keep-me",
    }
    resolved = resolve_entry_config(entry.data, {}, room_id=room_id)
    assert resolved[c.CONF_SHADING_WAITINGTIME_START] != 300


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_existing_profile_values_round_trip_unchanged(hass):
    """Stored values are current form values and survive an unchanged save."""

    entry = _entry(hass)
    room_id = config_entry_room_id(entry.data, entry.entry_id)
    model = entry_config_model(entry.data, {}, room_id=room_id)
    profile_id = f"legacy-{entry.entry_id}-time"
    stored = {
        c.CONF_AUTO_TIME: True,
        c.CONF_AUTO_UP: True,
        c.CONF_AUTO_DOWN: True,
        c.CONF_TIME_UP_EARLY_WORKDAY: "06:15:00",
        c.CONF_TIME_DOWN_EARLY_WORKDAY: "20:45:00",
    }
    model["profiles"][c.PROFILE_TYPE_TIME][profile_id]["settings"] = stored.copy()
    hass.config_entries.async_update_entry(
        entry,
        data={c.CONF_ROOM_ID: room_id, CONF_NAME: "Living", CONF_CONFIG_MODEL: model},
    )

    result = await _open_options_step(hass, entry, "profiles", "time_profiles")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"profile_action": "edit", "profile_id": profile_id},
    )
    assert result["step_id"] == "profile_setup"
    setup = _frontend_initial_data(result["data_schema"])
    assert setup[CONF_PROFILE_CAPABILITIES_FIELD] == ["opening", "closing"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], setup
    )
    initial = _frontend_initial_data(result["data_schema"])
    assert initial["time_features"] == {
        c.CONF_AUTO_TIME: True,
        c.CONF_AUTO_UP: True,
        c.CONF_AUTO_DOWN: True,
    }
    assert initial["workday_times"] == {
        c.CONF_TIME_UP_EARLY_WORKDAY: "06:15:00",
        c.CONF_TIME_DOWN_EARLY_WORKDAY: "20:45:00",
    }
    assert "non_workday_times" not in initial

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], initial
    )
    assert result["step_id"] == "time_profiles"
    result = await _finish_options_flow(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_CONFIG_MODEL]["profiles"][c.PROFILE_TYPE_TIME][
        profile_id
    ]["settings"] == stored


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_profile_delete_is_blocked_while_room_uses_it(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living",
        data={CONF_NAME: "Living", CONF_COVERS: ["cover.living"]},
    )
    entry.add_to_hass(hass)
    profile_id = f"legacy-{entry.entry_id}-shading"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "hub_settings"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "profiles"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "shading_profiles"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"profile_action": "delete", "profile_id": profile_id},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "profile_in_use"}


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_room_profile_overrides_and_source_override_are_persisted(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living",
        data={
            CONF_NAME: "Living",
            CONF_COVERS: ["cover.living"],
            CONF_BRIGHTNESS_SENSOR: "sensor.global_brightness",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "room_settings"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "room_profiles"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": "room_assignments"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "time_profile": f"legacy-{entry.entry_id}-time",
            "shading_profile": f"legacy-{entry.entry_id}-shading",
            "behavior_profile": f"legacy-{entry.entry_id}-behavior",
        },
    )
    assert result["step_id"] == "room_profiles"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "shading_overrides"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "configured_override_fields": [CONF_SHADING_POSITION],
            "shading_targets": {CONF_SHADING_POSITION: 27},
        },
    )
    assert result["step_id"] == "room_profiles"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "source_overrides"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_BRIGHTNESS_SENSOR: "sensor.room_brightness"},
    )
    assert result["step_id"] == "room_profiles"
    result = await _finish_options_flow(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY

    resolved = resolve_entry_config(
        entry.data,
        entry.options,
        room_id=config_entry_room_id(entry.data, entry.entry_id),
    )
    assert resolved[CONF_SHADING_POSITION] == 27
    assert resolved[CONF_BRIGHTNESS_SENSOR] == "sensor.room_brightness"
    assert resolved.sources[CONF_SHADING_POSITION] == "room_override"
    assert resolved.sources[CONF_BRIGHTNESS_SENSOR] == "room_source_override"


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_room_profile_without_override_resolves_profile_values(hass):
    """O1: Assignment alone resolves the selected sparse profile."""

    entry = _entry(hass, data={
        CONF_NAME: "Living",
        CONF_COVERS: ["cover.living"],
        CONF_SHADING_POSITION: 34,
        c.CONF_SHADING_WAITINGTIME_END: 420,
    })
    room_id = config_entry_room_id(entry.data, entry.entry_id)
    resolved = resolve_entry_config(entry.data, entry.options, room_id=room_id)

    assert resolved[CONF_SHADING_POSITION] == 34
    assert resolved[c.CONF_SHADING_WAITINGTIME_END] == 420
    room = entry_config_model(entry.data, {}, room_id=room_id)["rooms"][room_id]
    assert room.get("overrides", {}) == {}


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_room_override_can_be_removed_without_copying_inherited_values(hass):
    """O3-O4: Clearing selection removes only the delta."""

    entry = _entry(hass)
    room_id = config_entry_room_id(entry.data, entry.entry_id)
    model = entry_config_model(entry.data, {}, room_id=room_id)
    profile_id = f"legacy-{entry.entry_id}-shading"
    model["profiles"][c.PROFILE_TYPE_SHADING][profile_id]["settings"] = {
        CONF_SHADING_POSITION: 30,
        c.CONF_SHADING_WAITINGTIME_END: 500,
    }
    model["rooms"][room_id]["overrides"] = {
        c.PROFILE_TYPE_SHADING: {CONF_SHADING_POSITION: 27}
    }
    hass.config_entries.async_update_entry(
        entry,
        data={c.CONF_ROOM_ID: room_id, CONF_NAME: "Living", CONF_CONFIG_MODEL: model},
    )

    result = await _open_options_step(
        hass, entry, "room_profiles", "shading_overrides"
    )
    initial = _frontend_initial_data(result["data_schema"])
    assert initial[CONF_OVERRIDE_FIELDS] == [CONF_SHADING_POSITION]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**initial, CONF_OVERRIDE_FIELDS: []}
    )
    assert result["step_id"] == "room_profiles"
    result = await _finish_options_flow(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY

    room = entry.data[CONF_CONFIG_MODEL]["rooms"][room_id]
    assert room.get("overrides", {}).get(c.PROFILE_TYPE_SHADING) is None
    resolved = resolve_entry_config(entry.data, {}, room_id=room_id)
    assert resolved[CONF_SHADING_POSITION] == 30
    assert resolved[c.CONF_SHADING_WAITINGTIME_END] == 500


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_global_sources_and_defaults_are_complete_native_forms(hass):
    """G1/G4: All sources are reachable and global defaults resolve."""

    entry = _entry(hass)
    result = await _open_options_step(
        hass, entry, "global_settings", "global_sources"
    )
    source_fields = {
        field["name"]
        for field in to_field_list(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
    }
    assert source_fields == GLOBAL_SOURCE_KEYS
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_BRIGHTNESS_SENSOR: "sensor.global_brightness"}
    )
    assert result["step_id"] == "global_settings"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "global_defaults"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_GLOBAL_DEFAULT_FIELDS: [c.CONF_OPEN_POSITION],
            "positions": {c.CONF_OPEN_POSITION: 88},
        },
    )
    assert result["step_id"] == "global_settings"
    result = await _finish_options_flow(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY

    model = entry.data[CONF_CONFIG_MODEL]
    assert model["global"]["sources"] == {
        CONF_BRIGHTNESS_SENSOR: "sensor.global_brightness"
    }
    assert model["global"]["defaults"] == {c.CONF_OPEN_POSITION: 88}
    resolved = resolve_entry_config(
        entry.data,
        {},
        room_id=entry.data[c.CONF_ROOM_ID],
    )
    assert resolved[CONF_BRIGHTNESS_SENSOR] == "sensor.global_brightness"
    assert resolved[c.CONF_OPEN_POSITION] == 88


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_diagnostics_use_profile_names_and_readable_values(hass):
    """Normal diagnostics avoid opaque IDs and internal configuration keys."""

    entry = _entry(hass)
    room_id = config_entry_room_id(entry.data, entry.entry_id)
    model = entry_config_model(entry.data, {}, room_id=room_id)
    opaque_id = "9b59b74c-846d-45b8-9257-opaque"
    model["profiles"][c.PROFILE_TYPE_SHADING][opaque_id] = {
        c.CONF_PROFILE_ID: opaque_id,
        c.CONF_PROFILE_NAME: "South windows",
        c.CONF_PROFILE_SETTINGS: {c.CONF_SHADING_POSITION: 32},
    }
    model["rooms"][room_id][c.CONF_PROFILE_SELECTIONS][
        c.PROFILE_TYPE_SHADING
    ] = opaque_id
    hass.config_entries.async_update_entry(
        entry,
        data={c.CONF_ROOM_ID: room_id, CONF_NAME: "Living", CONF_CONFIG_MODEL: model},
    )

    result = await _open_options_step(hass, entry, "diagnostics")
    text = " ".join(result["description_placeholders"].values())

    assert "South windows" in text
    assert opaque_id not in text
    assert c.CONF_SHADING_POSITION not in text
    assert "Shading position: 32 %" in text


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_global_and_room_sources_can_be_removed_with_empty_forms(hass):
    """G2/G3: Empty native selectors remove stored source values."""

    entry = _entry(hass, data={
        CONF_NAME: "Living",
        CONF_COVERS: ["cover.living"],
        CONF_BRIGHTNESS_SENSOR: "sensor.global_brightness",
    })
    room_id = config_entry_room_id(entry.data, entry.entry_id)
    model = entry_config_model(entry.data, {}, room_id=room_id)
    model["rooms"][room_id]["source_overrides"] = {
        CONF_BRIGHTNESS_SENSOR: "sensor.room_brightness"
    }
    hass.config_entries.async_update_entry(
        entry,
        data={c.CONF_ROOM_ID: room_id, CONF_NAME: "Living", CONF_CONFIG_MODEL: model},
    )
    assert resolve_entry_config(entry.data, {}, room_id=room_id)[
        CONF_BRIGHTNESS_SENSOR
    ] == "sensor.room_brightness"

    result = await _open_options_step(
        hass, entry, "room_profiles", "source_overrides"
    )
    fields = {
        field["name"]
        for field in to_field_list(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
    }
    assert fields == ROOM_SOURCE_OVERRIDE_KEYS
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {}
    )
    assert result["step_id"] == "room_profiles"
    result = await _finish_options_flow(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY

    result = await _open_options_step(
        hass, entry, "global_settings", "global_sources"
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {}
    )
    assert result["step_id"] == "global_settings"
    result = await _finish_options_flow(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY

    model = entry.data[CONF_CONFIG_MODEL]
    assert model["global"]["sources"] == {}
    assert model["rooms"][room_id]["source_overrides"] == {}


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_options_flow_accepts_numeric_full_open_position(hass):
    """Allow an integer full-open position to be displayed and submitted."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={
            CONF_NAME: DEFAULT_NAME,
            CONF_COVERS: ["cover.test_cover"],
            CONF_LOCKOUT_POSITION: 85,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "room_settings"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "advanced"}
    )
    flow = hass.config_entries.options._progress[result["flow_id"]]
    result = await hass.config_entries.options._async_handle_step(
        flow, "positions", None
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "positions"
    position_data = _frontend_initial_data(result["data_schema"])
    assert position_data[CONF_LOCKOUT_POSITION] == 85

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], position_data
    )
    assert result["type"] is FlowResultType.MENU

    result = await _finish_options_flow(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    resolved = resolve_entry_config(
        entry.data,
        entry.options,
        room_id=config_entry_room_id(entry.data, entry.entry_id),
    )
    assert resolved[CONF_LOCKOUT_POSITION] == 85


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_options_flow_exposes_new_behavior_defaults(hass):
    """New parity switches remain disabled for existing config entries."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={
            CONF_NAME: DEFAULT_NAME,
            CONF_COVERS: ["cover.test_cover"],
            CONF_AUTO_TIME: True,
            CONF_AUTO_SHADING: True,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    flow = hass.config_entries.options._progress[result["flow_id"]]
    result = await hass.config_entries.options._async_handle_step(
        flow, "behavior", None
    )
    behavior_data = _frontend_initial_data(result["data_schema"])
    assert behavior_data[CONF_MANUAL_SCHEDULE_ADOPTION] is False
    assert behavior_data[CONF_ENABLE_LOGBOOK_COVER] is False

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], behavior_data
    )
    flow = hass.config_entries.options._progress[result["flow_id"]]
    result = await hass.config_entries.options._async_handle_step(
        flow, "shading", None
    )
    shading_data = _frontend_initial_data(result["data_schema"])
    assert shading_data[CONF_SHADING_INDEPENDENT_HOLDS_END] is False


async def test_entry_setup_and_unload_on_home_assistant_2026_9(hass):
    """The integration loads and unloads through the current config entry API."""

    hass.states.async_set(
        "cover.test_cover",
        "open",
        {"current_position": 100},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        data={
            CONF_NAME: "Test",
            CONF_ROOM: "living-room",
            CONF_COVERS: ["cover.test_cover"],
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    manager = hass.data[DOMAIN][entry.entry_id]
    assert manager._evaluation_task in entry._background_tasks
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
