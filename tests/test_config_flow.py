"""Config flow tests for Cover Control."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

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
    PROFILE_CAPABILITY_KEYS,
)
from custom_components.cover_control.config_resolver import (
    GLOBAL_DEFAULT_KEYS,
    GLOBAL_SOURCE_KEYS,
    PROFILE_KEYS,
    ROOM_SOURCE_OVERRIDE_KEYS,
    resolve_config_model,
)
from custom_components.cover_control.config_migration import normalize_legacy_config
from custom_components.cover_control.config_subentries import (
    model_from_subentries,
    model_to_native_payloads,
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
    CONF_COVERS,
    CONF_RESIDENT_SENSOR,
    CONF_ENABLE_LOGBOOK_COVER,
    CONF_GLOBAL,
    CONF_LOCKOUT_POSITION,
    CONF_MANUAL_SCHEDULE_ADOPTION,
    CONF_PROFILES,
    CONF_ROOM,
    CONF_ROOMS,
    CONF_SHADING_INDEPENDENT_HOLDS_END,
    CONF_SHADING_POSITION,
    DEFAULT_NAME,
    DOMAIN,
)

LEGACY_PROFILE_FIELDS = "configured_profile_fields"


def test_resident_sensor_is_room_only_source() -> None:
    assert CONF_RESIDENT_SENSOR not in GLOBAL_SOURCE_KEYS
    assert CONF_RESIDENT_SENSOR not in ROOM_SOURCE_OVERRIDE_KEYS

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


def test_parent_reconfigure_steps_have_runtime_translations() -> None:
    """Parent reconfigure forms must not render empty or technical-only text."""

    expected_steps = {
        "user",
        "reconfigure",
        "global_sources",
        "profiles",
        "profile_setup",
        "profile_sections",
        "profile_time",
        "profile_brightness",
        "profile_sun",
        "profile_shading",
        "profile_ventilation",
        "profile_resident",
        "profile_behavior",
        "diagnostics",
        "recovery",
    }
    translation_dir = Path("custom_components/cover_control")
    for path in (
        translation_dir / "strings.json",
        translation_dir / "translations/en.json",
        translation_dir / "translations/de.json",
    ):
        document = json.loads(path.read_text())
        steps = document["config"]["step"]
        assert expected_steps <= set(steps)
        assert set(steps["user"]["data"]) == {CONF_NAME}
        assert set(steps["user"]["data_description"]) == {CONF_NAME}

        assert set(steps["reconfigure"]["menu_options"]) == {
            "global_sources",
            "profiles",
            "diagnostics",
            "recovery",
        }
        assert set(steps["reconfigure"]["menu_option_descriptions"]) == set(
            steps["reconfigure"]["menu_options"]
        )
        assert set(steps["global_sources"]["data"]) == GLOBAL_SOURCE_KEYS
        assert set(steps["global_sources"]["data_description"]) == GLOBAL_SOURCE_KEYS
        assert GLOBAL_DEFAULT_KEYS == frozenset()
        assert "global_defaults" not in steps
        assert "configured_global_default_fields" not in json.dumps(document)
        assert {"profile_action", "profile_id"} <= set(steps["profiles"]["data"])
        assert {"profile_name"} <= set(steps["profile_setup"]["data"])
        assert set(steps["profile_sections"]["menu_options"]) == {
            "profile_setup",
            "profile_time",
            "profile_brightness",
            "profile_sun",
            "profile_shading",
            "profile_ventilation",
            "profile_resident",
            "profile_behavior",
        }
        assert "{profile_usage}" in steps["profile_setup"]["description"]
        assert "{profiles}" in steps["diagnostics"]["description"]
        assert "{available}" in steps["recovery"]["description"]
        assert "reconfigure_successful" in document["config"]["abort"]
        assert "single_instance_allowed" in document["config"]["abort"]
        assert {
            "profile_required_for_functions",
            "profile_has_no_functions",
        } <= set(document["config_subentries"]["room"]["abort"])


def test_active_room_steps_have_runtime_translations() -> None:
    """Every active room subentry step needs visible runtime text."""

    active_room_steps = {
        "user",
        "reconfigure",
        "general",
        "hardware",
        "positions",
        "contacts",
        "room_sensors",
        "geometry",
        "profile_references",
        "profile_functions",
        "source_overrides",
        "controls",
        "diagnostics",
    }
    legacy_room_steps = {
        "time",
        "brightness",
        "sun",
        "shading",
        "ventilation",
        "resident",
        "behavior",
        "functions",
        "overrides",
        "override_time",
        "override_shading",
        "override_behavior",
    }
    menu_steps = {
        "reconfigure",
    }
    translation_dir = Path("custom_components/cover_control")
    for path in (
        translation_dir / "strings.json",
        translation_dir / "translations/en.json",
        translation_dir / "translations/de.json",
    ):
        document = json.loads(path.read_text())
        steps = document["config_subentries"]["room"]["step"]
        assert active_room_steps <= set(steps)
        assert legacy_room_steps.isdisjoint(steps)
        for step in active_room_steps:
            assert "title" in steps[step]
            assert "description" in steps[step]
        for step in menu_steps:
            assert set(steps[step]["menu_options"]) == set(
                steps[step]["menu_option_descriptions"]
            )
        room_abort = document["config_subentries"]["room"]["abort"]
        assert {
            "reconfigure_successful",
            "profile_required_for_functions",
            "profile_has_no_functions",
        } <= set(room_abort)


def _translation_leaf_strings(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from _translation_leaf_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _translation_leaf_strings(child)
    else:
        yield value


def test_active_v6_translation_details_are_covered() -> None:
    """Active v6 menus, profile sections, selectors, and German copy are covered."""

    expected_profile_sections = {
        "profile_time": {
            "time_features",
            "workday_times",
            "non_workday_times",
            "calendar_behavior",
        },
        "profile_brightness": {"time_features", "brightness_settings"},
        "profile_sun": {"time_features", "sun_settings"},
        "profile_shading": {
            "shading_targets",
            "shading_brightness",
            "shading_temperature",
            "shading_forecast",
            "shading_conditions",
            "shading_waits",
        },
        "profile_ventilation": {"ventilation"},
        "profile_resident": {"resident_behavior"},
        "profile_behavior": {"manual_override", "prevention", "tilt_wait"},
    }
    required_selectors = {
        "profile_action",
        "profile_functions",
        "profile_reference",
        "position_source",
        "cover_type",
        "cover_tilt_wait_mode",
        "sun_elevation_mode",
        "brightness_sun_operator",
        "forecast_type",
        "manual_override_reset_mode",
        "shading_condition",
        "shading_config",
        "weather_condition",
    }
    for path in (
        Path("custom_components/cover_control/strings.json"),
        Path("custom_components/cover_control/translations/en.json"),
        Path("custom_components/cover_control/translations/de.json"),
    ):
        document = json.loads(path.read_text())
        steps = document["config"]["step"]
        selectors = document["selector"]
        assert required_selectors <= set(selectors)
        for selector_key in required_selectors:
            assert selectors[selector_key]["options"]
        for step, sections in expected_profile_sections.items():
            assert set(steps[step]["sections"]) == sections
            for section in steps[step]["sections"].values():
                assert section["data"]
                assert set(section["data"]) <= set(section["data_description"])
        room_positions = document["config_subentries"]["room"]["step"]["positions"]
        assert set(room_positions["sections"]) == {"positions", "tilt_positions"}
        for section in room_positions["sections"].values():
            assert section["data"]
            assert set(section["data"]) <= set(section["data_description"])

    de_document = json.loads(
        Path("custom_components/cover_control/translations/de.json").read_text()
    )
    de_text = "\n".join(
        value
        for value in _translation_leaf_strings(de_document)
        if isinstance(value, str)
    )
    for forbidden in (
        "Profile sections",
        "Setup",
        "Sun position",
        "No profile",
        "Zeitprofil",
        "Beschattungsprofil",
        "Verhaltensprofil",
        "time_features",
        "shading_waits",
        "resident_behavior",
        "fuer",
    ):
        assert forbidden not in de_text
    assert "Azimut" not in de_document["config"]["step"]["profile_sun"]["description"]


def test_legacy_config_flow_methods_are_not_active() -> None:
    """Removed legacy UI steps must not remain directly addressable."""

    from custom_components.cover_control.config_flow import (
        CoverControlFlow,
        RoomSubentryFlow,
    )

    assert not hasattr(CoverControlFlow, "async_step_global_defaults")
    parent_steps = {
        name.removeprefix("async_step_")
        for name in CoverControlFlow.__dict__
        if name.startswith("async_step_")
    }
    assert parent_steps == {
        "user",
        "global_sources",
        "reconfigure",
        "profiles",
        "profile_setup",
        "profile_sections",
        "profile_time",
        "profile_brightness",
        "profile_sun",
        "profile_shading",
        "profile_ventilation",
        "profile_resident",
        "profile_behavior",
        "diagnostics",
        "recovery",
    }
    room_steps = {
        name.removeprefix("async_step_")
        for name in RoomSubentryFlow.__dict__
        if name.startswith("async_step_")
    }
    assert room_steps == {
        "user",
        "reconfigure",
        "general",
        "hardware",
        "positions",
        "contacts",
        "room_sensors",
        "geometry",
        "profile_references",
        "profile_functions",
        "source_overrides",
        "controls",
        "diagnostics",
    }
    for method in (
        "async_step_time",
        "async_step_brightness",
        "async_step_sun",
        "async_step_shading",
        "async_step_ventilation",
        "async_step_resident",
        "async_step_behavior",
        "async_step_overrides",
        "async_step_override_time",
        "async_step_override_shading",
        "async_step_override_behavior",
        "_async_function_step",
        "_async_override_step",
    ):
        assert not hasattr(RoomSubentryFlow, method)


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
    flat_data = data or {CONF_NAME: "Living", CONF_COVERS: ["cover.living"]}
    model = normalize_legacy_config(flat_data, {}, room_id="room-test")
    parent_data, subentries = model_to_native_payloads(model)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living",
        version=5,
        data=parent_data,
        subentries_data=[
            {
                "subentry_id": subentry_id,
                "subentry_type": subentry_type,
                "title": title,
                "unique_id": subentry_id,
                "data": subentry_data,
            }
            for subentry_id, subentry_type, title, subentry_data in subentries
        ],
    )
    entry.add_to_hass(hass)
    return entry


async def _open_options_step(hass, entry, *steps: str):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    for step in steps:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": step}
        )
    return result


def _room_subentry(entry):
    return next(
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "room"
    )


def _room_id(entry) -> str:
    return _room_subentry(entry).subentry_id


def _native_model(entry) -> dict:
    return model_from_subentries(entry.data, entry.subentries.values())


def _update_native_model(hass, entry, model: dict) -> None:
    parent_data, subentries = model_to_native_payloads(model)
    hass.config_entries.async_update_entry(entry, data=parent_data, options={})
    for subentry_id, _subentry_type, title, subentry_data in subentries:
        hass.config_entries.async_update_subentry(
            entry=entry,
            subentry=entry.subentries[subentry_id],
            title=title,
            data=subentry_data,
        )


def _resolve_native(entry):
    return resolve_config_model(_native_model(entry), _room_id(entry))


async def _open_room_step(hass, entry, *steps: str):
    subentry = _room_subentry(entry)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "room"),
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "subentry_id": subentry.subentry_id,
        },
    )
    for step in steps:
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": step}
        )
    return result


async def _finish_options_flow(hass, result):
    """Return a synthetic successful finish for reconfigure helper compatibility."""

    return {"type": FlowResultType.CREATE_ENTRY}


async def _create_profile(hass, entry, profile_type: str, data: dict):
    result = await _open_options_step(hass, entry, "profiles")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"profile_action": "create"}
    )
    assert result["step_id"] == "profile_setup"
    data.pop(LEGACY_PROFILE_FIELDS, None)
    profile_name = data.pop("profile_name")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"profile_name": profile_name}
    )
    assert result["step_id"] == "profile_sections"
    section = {
        c.PROFILE_TYPE_TIME: "profile_time",
        c.PROFILE_TYPE_SHADING: "profile_shading",
        c.PROFILE_TYPE_BEHAVIOR: "profile_behavior",
    }[profile_type]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": section}
    )
    assert result["step_id"] == section
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["step_id"] == "profile_sections"
    result = await _finish_options_flow(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    catalog = {
        profile_id: profile
        for profile_id, profile in entry.data[CONF_PROFILES].items()
        if profile_id not in c.PROFILE_TYPES
    }
    return next(reversed(catalog.values()))


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_user_flow_can_be_completed_without_errors(hass):
    """Create one room-free parent entry through global setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "Cover Control"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "global_sources"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cover Control"
    assert result["data"]["global"] == {"sources": {}, "defaults": {}}
    assert CONF_COVERS not in result["data"]


async def test_user_flow_blocks_second_parent_entry(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cover Control",
        version=4,
        data={"global": {"sources": {}, "defaults": {}}},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_user_flow_exposes_nested_defaults_to_frontend(hass):
    """Parent setup requires no room hardware or function settings."""

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
    assert initial_data == {CONF_NAME: DEFAULT_NAME}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: DEFAULT_NAME},
    )
    assert result["step_id"] == "global_sources"
    source_fields = {str(key.schema) for key in result["data_schema"].schema}
    assert CONF_BRIGHTNESS_SENSOR in source_fields
    assert CONF_COVERS not in source_fields

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_parent_reconfigure_loads_for_existing_entry(hass):
    """Ensure parent reconfigure schema can be built successfully."""
    entry = _entry(
        hass,
        data={CONF_NAME: DEFAULT_NAME, CONF_COVERS: ["cover.test_cover"]},
    )

    result = await _open_options_step(hass, entry)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_parent_reconfigure_menu_exposes_hierarchical_sections(hass):
    entry = _entry(hass)

    result = await _open_options_step(hass, entry)

    assert result["menu_options"] == [
        "global_sources",
        "profiles",
        "diagnostics",
        "recovery",
    ]

    result = await _open_room_step(hass, entry)
    assert result["menu_options"] == [
        "general",
        "hardware",
        "positions",
        "contacts",
        "room_sensors",
        "geometry",
        "profile_references",
        "profile_functions",
        "source_overrides",
        "controls",
        "diagnostics",
    ]


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_parent_reconfigure_submenus_open_without_errors(hass):
    entry = _entry(hass)

    for step in (
        "global_sources",
        "profiles",
        "diagnostics",
        "recovery",
    ):
        result = await _open_options_step(hass, entry, step)
        assert result["type"] in {
            FlowResultType.FORM,
            FlowResultType.MENU,
            FlowResultType.ABORT,
        }
        if result["type"] is FlowResultType.FORM:
            to_field_list(result["data_schema"], custom_serializer=cv.custom_serializer)


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_room_reconfigure_submenus_open_without_errors(hass):
    entry = _entry(hass)

    for step in (
        "general",
        "hardware",
        "positions",
        "contacts",
        "room_sensors",
        "geometry",
        "profile_references",
        "profile_functions",
        "source_overrides",
        "diagnostics",
    ):
        result = await _open_room_step(hass, entry, step)
        assert result["type"] in {
            FlowResultType.FORM,
            FlowResultType.MENU,
            FlowResultType.ABORT,
        }
        if result["type"] is FlowResultType.FORM:
            to_field_list(result["data_schema"], custom_serializer=cv.custom_serializer)


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_room_profile_functions_step_serializes_without_errors(hass):
    entry = _entry(hass)
    model = _native_model(entry)
    room_id = _room_id(entry)
    profile_id = model["rooms"][room_id]["profile_id"]
    model["profiles"][profile_id][c.CONF_PROFILE_FUNCTIONS] = [c.FUNCTION_TIME]
    model["rooms"][room_id][c.CONF_PROFILE_FUNCTIONS] = [c.FUNCTION_TIME]
    _update_native_model(hass, entry, model)

    result = await _open_room_step(hass, entry, "profile_functions")

    assert result["type"] is FlowResultType.FORM
    to_field_list(result["data_schema"], custom_serializer=cv.custom_serializer)


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_room_subentry_menu_has_no_parallel_profile_editors(hass):
    entry = _entry(hass)
    result = await _open_room_step(hass, entry)

    assert result["menu_options"] == [
        "general",
        "hardware",
        "positions",
        "contacts",
        "room_sensors",
        "geometry",
        "profile_references",
        "profile_functions",
        "source_overrides",
        "controls",
        "diagnostics",
    ]
    assert "functions" not in result["menu_options"]
    assert "overrides" not in result["menu_options"]
    assert not {
        "global_sources",
        "global_defaults",
        "profiles",
        "time_profiles",
        "shading_profiles",
        "behavior_profiles",
        "time",
        "brightness",
        "sun",
        "shading",
        "ventilation",
        "resident",
        "behavior",
        "override_time",
        "override_shading",
        "override_behavior",
    } & set(result["menu_options"])


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_selected_function_switches_exist_even_when_initial_state_is_off(hass):
    """Selected profile functions expose switches, even when disabled."""

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
    model = _native_model(entry)
    room_id = _room_id(entry)
    profile_id = model["rooms"][room_id]["profile_id"]
    model["profiles"][profile_id][c.CONF_PROFILE_FUNCTIONS] = [
        c.FUNCTION_TIME,
        c.FUNCTION_BRIGHTNESS,
        c.FUNCTION_SHADING,
    ]
    model["rooms"][room_id][c.CONF_PROFILE_FUNCTIONS] = [
        c.FUNCTION_TIME,
        c.FUNCTION_BRIGHTNESS,
    ]
    _update_native_model(hass, entry, model)
    entities = []

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await async_setup_switch_entry(hass, entry, entities.extend)

    assert {entity._key for entity in entities} == {
        c.CONF_AUTO_TIME,
        c.CONF_AUTO_BRIGHTNESS,
    }
    assert len(entities) == 2
    for entity in entities:
        entity.hass = hass
    states = {entity._key: entity.is_on for entity in entities}
    assert states[c.CONF_AUTO_BRIGHTNESS] is True
    assert states[c.CONF_AUTO_TIME] is False
    assert await hass.config_entries.async_unload(entry.entry_id)


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
            LEGACY_PROFILE_FIELDS: [c.CONF_AUTO_TIME, c.CONF_TIME_UP_EARLY_WORKDAY],
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
            LEGACY_PROFILE_FIELDS: selected,
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
            LEGACY_PROFILE_FIELDS: [
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
    """U4-U7: Load old values, preserve unknown data, and keep a stable ID."""

    entry = _entry(hass)
    room_id = _room_id(entry)
    model = _native_model(entry)
    profile_id = model["rooms"][room_id]["profile_id"]
    model["rooms"][room_id][c.CONF_PROFILE_FUNCTIONS] = [
        c.FUNCTION_TIME,
        c.FUNCTION_SHADING,
    ]
    settings = model["profiles"][profile_id]["settings"]
    settings.clear()
    settings.update(
        {
            c.CONF_SHADING_WAITINGTIME_START: 300,
            "future_profile_key": "keep-me",
        }
    )
    _update_native_model(hass, entry, model)

    result = await _open_options_step(hass, entry, "profiles")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"profile_action": "edit", "profile_id": profile_id},
    )
    assert result["step_id"] == "profile_sections"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "profile_setup"}
    )
    setup = _frontend_initial_data(result["data_schema"])
    setup["profile_name"] = "South renamed"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], setup
    )
    assert result["step_id"] == "profile_sections"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "profile_shading"}
    )
    initial = _frontend_initial_data(result["data_schema"])
    initial["shading_waits"] = {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], initial
    )
    assert result["step_id"] == "profile_sections"
    result = await _finish_options_flow(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY

    catalog = entry.data[CONF_PROFILES]
    assert profile_id in catalog
    assert catalog[profile_id]["name"] == "South renamed"
    assert catalog[profile_id]["settings"] == {
        "future_profile_key": "keep-me",
        c.CONF_SHADING_WAITINGTIME_START: 300.0,
    }
    resolved = _resolve_native(entry)
    assert resolved[c.CONF_SHADING_WAITINGTIME_START] == 300.0


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_existing_profile_values_round_trip_unchanged(hass):
    """Stored values are current form values and survive an unchanged save."""

    entry = _entry(hass)
    room_id = _room_id(entry)
    model = _native_model(entry)
    profile_id = model["rooms"][room_id]["profile_id"]
    stored = {
        c.CONF_AUTO_TIME: True,
        c.CONF_AUTO_UP: True,
        c.CONF_AUTO_DOWN: True,
        c.CONF_TIME_UP_EARLY_WORKDAY: "06:15:00",
        c.CONF_TIME_DOWN_EARLY_WORKDAY: "20:45:00",
    }
    model["profiles"][profile_id]["settings"] = stored.copy()
    _update_native_model(hass, entry, model)

    result = await _open_options_step(hass, entry, "profiles")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"profile_action": "edit", "profile_id": profile_id},
    )
    assert result["step_id"] == "profile_sections"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "profile_time"}
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

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], initial
    )
    assert result["step_id"] == "profile_sections"
    result = await _finish_options_flow(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_PROFILES][profile_id]["settings"] == stored


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_profile_function_detection_recomputes_from_current_content(hass):
    """Adding and removing profile sections updates available room functions."""

    entry = _entry(hass)
    result = await _open_options_step(hass, entry, "profiles")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"profile_action": "create"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"profile_name": "Wohnen"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "profile_time"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"time_features": {c.CONF_AUTO_TIME: True}}
    )
    assert result["step_id"] == "profile_sections"
    profile_id = next(
        profile_id
        for profile_id, profile in entry.data[CONF_PROFILES].items()
        if profile.get(c.CONF_PROFILE_NAME) == "Wohnen"
    )
    assert entry.data[CONF_PROFILES][profile_id][c.CONF_PROFILE_FUNCTIONS] == [
        c.FUNCTION_TIME
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "profile_shading"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"shading_targets": {c.CONF_AUTO_SHADING: True}}
    )
    assert set(entry.data[CONF_PROFILES][profile_id][c.CONF_PROFILE_FUNCTIONS]) == {
        c.FUNCTION_TIME,
        c.FUNCTION_SHADING,
    }

    result = await _open_room_step(hass, entry, "profile_references")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {c.CONF_ROOM_PROFILE_ID: profile_id}
    )
    assert result["type"] is FlowResultType.ABORT

    result = await _open_room_step(hass, entry, "profile_functions")
    fields = to_field_list(result["data_schema"], custom_serializer=cv.custom_serializer)
    options = fields[0]["selector"]["select"]["options"]
    assert set(options) == {c.FUNCTION_TIME, c.FUNCTION_SHADING}

    model = _native_model(entry)
    settings = model["profiles"][profile_id][c.CONF_PROFILE_SETTINGS]
    settings.pop(c.CONF_AUTO_SHADING)
    model["profiles"][profile_id][c.CONF_PROFILE_FUNCTIONS] = [c.FUNCTION_TIME]
    model["rooms"][_room_id(entry)][c.CONF_PROFILE_FUNCTIONS] = [
        c.FUNCTION_TIME,
        c.FUNCTION_SHADING,
    ]
    _update_native_model(hass, entry, model)
    resolved = _resolve_native(entry)
    assert resolved.configured_functions == frozenset({c.FUNCTION_TIME})


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_profile_delete_is_blocked_while_room_uses_it(hass):
    entry = _entry(hass)
    profile_id = _native_model(entry)["rooms"][_room_id(entry)]["profile_id"]

    result = await _open_options_step(hass, entry, "profiles")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"profile_action": "delete", "profile_id": profile_id},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "profile_in_use"}


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_room_positions_and_source_override_are_persisted(hass):
    entry = _entry(
        hass,
        data={
            CONF_NAME: "Living",
            CONF_COVERS: ["cover.living"],
            CONF_BRIGHTNESS_SENSOR: "sensor.global_brightness",
        },
    )

    result = await _open_room_step(hass, entry, "profile_references")
    profile_id = _native_model(entry)["rooms"][_room_id(entry)]["profile_id"]
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"profile_id": profile_id},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    result = await _open_room_step(hass, entry, "positions")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"positions": {CONF_SHADING_POSITION: 27}},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    result = await _open_room_step(hass, entry, "source_overrides")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_BRIGHTNESS_SENSOR: "sensor.room_brightness"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    resolved = _resolve_native(entry)
    assert resolved[CONF_SHADING_POSITION] == 27
    assert resolved[CONF_BRIGHTNESS_SENSOR] == "sensor.room_brightness"
    assert resolved.sources[CONF_SHADING_POSITION] == "room_setting"
    assert resolved.sources[CONF_BRIGHTNESS_SENSOR] == "room_source_override"


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_room_contacts_use_stable_form_keys_and_preserve_cover_mapping(hass):
    entry = _entry(
        hass,
        data={
            CONF_NAME: "Living",
            CONF_COVERS: ["cover.living_left", "cover.living_right"],
        },
    )

    result = await _open_room_step(hass, entry, "contacts")
    fields = {
        field["name"]
        for field in to_field_list(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
    }

    assert fields == {
        "cover_0_full",
        "cover_0_tilt",
        "cover_1_full",
        "cover_1_tilt",
    }
    assert not any("living" in field for field in fields)

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "cover_0_full": ["binary_sensor.left_open"],
            "cover_0_tilt": ["binary_sensor.left_tilt"],
            "cover_1_full": ["binary_sensor.right_open"],
            "cover_1_tilt": ["binary_sensor.right_tilt"],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    room = _native_model(entry)["rooms"][_room_id(entry)]["settings"]
    assert room[c.CONF_WINDOW_SENSOR_FULL] == {
        "cover.living_left": ["binary_sensor.left_open"],
        "cover.living_right": ["binary_sensor.right_open"],
    }
    assert room[c.CONF_WINDOW_SENSOR_TILT] == {
        "cover.living_left": ["binary_sensor.left_tilt"],
        "cover.living_right": ["binary_sensor.right_tilt"],
    }


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_room_profile_without_override_resolves_profile_values(hass):
    """O1: Assignment alone resolves the selected sparse profile."""

    entry = _entry(hass, data={
        CONF_NAME: "Living",
        CONF_COVERS: ["cover.living"],
        CONF_SHADING_POSITION: 34,
        c.CONF_SHADING_WAITINGTIME_END: 420,
    })
    room_id = _room_id(entry)
    resolved = _resolve_native(entry)

    assert resolved[CONF_SHADING_POSITION] == 34
    assert resolved[c.CONF_SHADING_WAITINGTIME_END] == 420
    room = _native_model(entry)["rooms"][room_id]
    assert room.get("overrides", {}) == {}


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_room_profile_functions_persist_selected_subset(hass):
    entry = _entry(hass)
    model = _native_model(entry)
    room_id = _room_id(entry)
    profile_id = model["rooms"][room_id]["profile_id"]
    model["profiles"][profile_id][c.CONF_PROFILE_FUNCTIONS] = [
        c.FUNCTION_TIME,
        c.FUNCTION_RESIDENT,
    ]
    model["rooms"][room_id][c.CONF_PROFILE_FUNCTIONS] = [c.FUNCTION_TIME]
    _update_native_model(hass, entry, model)

    result = await _open_room_step(hass, entry, "profile_functions")
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {c.CONF_PROFILE_FUNCTIONS: [c.FUNCTION_RESIDENT, c.FUNCTION_TIME]},
    )

    assert result["type"] is FlowResultType.ABORT
    room = _native_model(entry)["rooms"][room_id]
    assert room[c.CONF_PROFILE_FUNCTIONS] == [
        c.FUNCTION_RESIDENT,
        c.FUNCTION_TIME,
    ]


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_room_profile_change_intersects_existing_function_selection(hass):
    entry = _entry(hass)
    model = _native_model(entry)
    room_id = _room_id(entry)
    first_profile_id = model["rooms"][room_id]["profile_id"]
    second_profile_id = "profile-second"
    model["profiles"][first_profile_id][c.CONF_PROFILE_FUNCTIONS] = [
        c.FUNCTION_TIME,
        c.FUNCTION_BRIGHTNESS,
        c.FUNCTION_SHADING,
    ]
    model["profiles"][second_profile_id] = {
        c.CONF_PROFILE_ID: second_profile_id,
        c.CONF_PROFILE_NAME: "Second",
        c.CONF_PROFILE_FUNCTIONS: [
            c.FUNCTION_TIME,
            c.FUNCTION_SUN,
            c.FUNCTION_SHADING,
            c.FUNCTION_RESIDENT,
        ],
        c.CONF_PROFILE_SETTINGS: {},
    }
    model["rooms"][room_id][c.CONF_PROFILE_FUNCTIONS] = [
        c.FUNCTION_TIME,
        c.FUNCTION_SHADING,
    ]
    _update_native_model(hass, entry, model)

    result = await _open_room_step(hass, entry, "profile_references")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {c.CONF_ROOM_PROFILE_ID: second_profile_id}
    )

    assert result["type"] is FlowResultType.ABORT
    room = _native_model(entry)["rooms"][room_id]
    assert room[c.CONF_ROOM_PROFILE_ID] == second_profile_id
    assert room[c.CONF_PROFILE_FUNCTIONS] == [
        c.FUNCTION_SHADING,
        c.FUNCTION_TIME,
    ]


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_room_profile_clear_removes_reference_and_function_selection(hass):
    entry = _entry(hass)
    room_id = _room_id(entry)

    result = await _open_room_step(hass, entry, "profile_references")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {}
    )

    assert result["type"] is FlowResultType.ABORT
    room = _native_model(entry)["rooms"][room_id]
    assert c.CONF_ROOM_PROFILE_ID not in room
    assert room[c.CONF_PROFILE_FUNCTIONS] == []


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_room_position_can_be_removed_without_copying_profile_values(hass):
    """Clearing a room position returns to inherited defaults without overrides."""

    entry = _entry(hass)
    room_id = _room_id(entry)
    model = _native_model(entry)
    profile_id = model["rooms"][room_id]["profile_id"]
    model["rooms"][room_id][c.CONF_PROFILE_FUNCTIONS] = [
        c.FUNCTION_TIME,
        c.FUNCTION_SHADING,
    ]
    model["profiles"][profile_id]["settings"] = {
        c.CONF_SHADING_WAITINGTIME_END: 500,
    }
    model["rooms"][room_id]["settings"][CONF_LOCKOUT_POSITION] = 27
    _update_native_model(hass, entry, model)

    result = await _open_room_step(hass, entry, "positions")
    initial = _frontend_initial_data(result["data_schema"])
    assert initial["positions"][CONF_LOCKOUT_POSITION] == 27
    initial["positions"][CONF_LOCKOUT_POSITION] = None
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], initial
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    room = _native_model(entry)["rooms"][room_id]
    assert CONF_LOCKOUT_POSITION not in room["settings"]
    resolved = _resolve_native(entry)
    assert resolved[CONF_LOCKOUT_POSITION] is None
    assert resolved[c.CONF_SHADING_WAITINGTIME_END] == 500


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_global_sources_and_defaults_are_complete_native_forms(hass):
    """G1/G4: All sources are reachable and global defaults resolve."""

    entry = _entry(hass)
    result = await _open_options_step(hass, entry, "global_sources")
    source_fields = {
        field["name"]
        for field in to_field_list(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
    }
    assert source_fields == GLOBAL_SOURCE_KEYS
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_BRIGHTNESS_SENSOR: "sensor.global_brightness"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    model = _native_model(entry)
    model["global"]["defaults"] = {c.CONF_MANUAL_OVERRIDE_MINUTES: 45}
    _update_native_model(hass, entry, model)
    model = _native_model(entry)
    assert model["global"]["sources"] == {
        CONF_BRIGHTNESS_SENSOR: "sensor.global_brightness"
    }
    assert model["global"]["defaults"] == {c.CONF_MANUAL_OVERRIDE_MINUTES: 45}
    resolved = _resolve_native(entry)
    assert resolved[CONF_BRIGHTNESS_SENSOR] == "sensor.global_brightness"
    assert resolved[c.CONF_MANUAL_OVERRIDE_MINUTES] == 45


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_diagnostics_use_profile_names_and_readable_values(hass):
    """Normal diagnostics avoid opaque IDs and internal configuration keys."""

    entry = _entry(hass)
    room_id = _room_id(entry)
    model = _native_model(entry)
    opaque_id = "9b59b74c-846d-45b8-9257-opaque"
    model["profiles"][opaque_id] = {
        c.CONF_PROFILE_ID: opaque_id,
        c.CONF_PROFILE_NAME: "South windows",
        c.CONF_PROFILE_SETTINGS: {c.CONF_SHADING_POSITION: 32},
        c.CONF_PROFILE_FUNCTIONS: ["shading"],
    }
    model["rooms"][room_id]["profile_id"] = opaque_id
    _update_native_model(hass, entry, model)

    result = await _open_options_step(hass, entry, "diagnostics")
    text = " ".join(result["description_placeholders"].values())

    assert "South windows" in text
    assert opaque_id not in text
    assert c.CONF_SHADING_POSITION not in text


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_room_diagnostics_use_runtime_schedule_snapshot(hass):
    entry = _entry(
        hass,
        data={CONF_NAME: "Living", CONF_COVERS: ["cover.living"]},
    )
    room_id = _room_id(entry)
    hass.states.async_set("cover.living", "open", {"friendly_name": "Living cover"})
    entry.runtime_data = SimpleNamespace(
        room_managers={
            room_id: SimpleNamespace(
                entry_snapshot=lambda: {
                    "next_open": (
                        datetime(2026, 10, 4, 7, 30, tzinfo=timezone.utc),
                        "cover.living",
                    ),
                    "next_close": (
                        datetime(2026, 10, 4, 19, 45, tzinfo=timezone.utc),
                        "cover.living",
                    ),
                }
            )
        }
    )

    result = await _open_room_step(hass, entry, "diagnostics")

    assert result["description_placeholders"]["next_open"].startswith("2026-10-04")
    assert "Living cover" in result["description_placeholders"]["next_open"]
    assert result["description_placeholders"]["next_close"].startswith("2026-10-04")
    assert "07:30:00" not in result["description_placeholders"]["next_open"]
    assert "(" in result["description_placeholders"]["next_open"]


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_global_and_room_sources_can_be_removed_with_empty_forms(hass):
    """G2/G3: Empty native selectors remove stored source values."""

    entry = _entry(hass, data={
        CONF_NAME: "Living",
        CONF_COVERS: ["cover.living"],
        CONF_BRIGHTNESS_SENSOR: "sensor.global_brightness",
    })
    room_id = _room_id(entry)
    model = _native_model(entry)
    model["rooms"][room_id]["source_overrides"] = {
        CONF_BRIGHTNESS_SENSOR: "sensor.room_brightness"
    }
    _update_native_model(hass, entry, model)
    assert _resolve_native(entry)[CONF_BRIGHTNESS_SENSOR] == "sensor.room_brightness"

    result = await _open_room_step(hass, entry, "source_overrides")
    fields = {
        field["name"]
        for field in to_field_list(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
    }
    assert fields == ROOM_SOURCE_OVERRIDE_KEYS
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    result = await _open_options_step(hass, entry, "global_sources")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    model = _native_model(entry)
    assert model["global"]["sources"] == {}
    assert model["rooms"][room_id]["source_overrides"] == {}


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_options_flow_accepts_numeric_full_open_position(hass):
    """Allow an integer full-open position to be displayed and submitted."""
    entry = _entry(
        hass,
        data={
            CONF_NAME: DEFAULT_NAME,
            CONF_COVERS: ["cover.test_cover"],
            CONF_LOCKOUT_POSITION: 85,
        },
    )

    result = await _open_room_step(hass, entry, "positions")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "positions"
    position_data = {
        "positions": {CONF_LOCKOUT_POSITION: 85},
    }
    assert position_data["positions"][CONF_LOCKOUT_POSITION] == 85

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], position_data
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    resolved = _resolve_native(entry)
    assert resolved[CONF_LOCKOUT_POSITION] == 85


@pytest.mark.skipif(REQUIRES_NEW_HA, reason="requires Home Assistant >= 2023.9")
async def test_options_flow_exposes_new_behavior_defaults(hass):
    """New parity switches remain disabled for existing config entries."""

    entry = _entry(
        hass,
        data={
            CONF_NAME: DEFAULT_NAME,
            CONF_COVERS: ["cover.test_cover"],
            CONF_AUTO_TIME: True,
            CONF_AUTO_SHADING: True,
        },
    )

    result = await _open_room_step(hass, entry)

    assert "functions" not in result["menu_options"]
    assert "behavior" not in result["menu_options"]
    assert "shading" not in result["menu_options"]


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
    runtime = entry.runtime_data
    manager = next(iter(runtime.room_managers.values()))
    assert manager._evaluation_task in entry._background_tasks
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
