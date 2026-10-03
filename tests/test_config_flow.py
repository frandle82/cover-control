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
from custom_components.cover_control.config_resolver import (
    config_entry_room_id,
    resolve_entry_config,
)
from custom_components.cover_control.const import (
    CONF_AUTO_SHADING,
    CONF_AUTO_TIME,
    CONF_AUTO_VENTILATE,
    CONF_BRIGHTNESS_SENSOR,
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

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
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
        "general",
        "global_sources",
        "profiles",
        "room_profiles",
        "advanced",
        "diagnostics",
        "finish",
    ]


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
        result["flow_id"], {"next_step_id": "room_profiles"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "time_profile": f"legacy-{entry.entry_id}-time",
            "shading_profile": f"legacy-{entry.entry_id}-shading",
            "behavior_profile": f"legacy-{entry.entry_id}-behavior",
            "room_overrides_json": '{"shading":{"shading_position":27}}',
            CONF_BRIGHTNESS_SENSOR: "sensor.room_brightness",
        },
    )
    assert result["step_id"] == "menu"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
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
        result["flow_id"], {"next_step_id": "advanced"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "positions"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "positions"
    position_data = _frontend_initial_data(result["data_schema"])
    assert position_data[CONF_LOCKOUT_POSITION] == 85

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], position_data
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
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
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "advanced"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "behavior"}
    )
    behavior_data = _frontend_initial_data(result["data_schema"])
    assert behavior_data[CONF_MANUAL_SCHEDULE_ADOPTION] is False
    assert behavior_data[CONF_ENABLE_LOGBOOK_COVER] is False

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], behavior_data
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "advanced"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "shading"}
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
