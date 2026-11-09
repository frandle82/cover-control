"""Config-flow tests for the three fixed groups."""
import json
from pathlib import Path
import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.cover_control.config_flow import CoverControlFlow
from custom_components.cover_control.const import (
    CONF_CONTROLLER_ENTRY_ID, CONF_ENTRY_TYPE, CONF_GLOBAL, CONF_GROUP,
    CONF_GROUPS, CONF_NAME, CONF_ROOM, CONF_ROOM_ID, CONF_ROOM_SETTINGS,
    CONF_CLOSE_MODE, CONF_OPEN_MODE, CONF_SUN_ELEVATION_OPEN,
    CONF_SHADING_DIRECTION, CONF_SHADING_INSIDE_TEMPERATURE_THRESHOLD,
    CONF_SHADING_MODE, CONF_SHADING_OUTSIDE_TEMPERATURE_THRESHOLD,
    CONF_ASTRO_CLOSE_OFFSET, DOMAIN, ENTRY_TYPE_CONTROLLER, ENTRY_TYPE_ROOM,
    GROUPS, GROUP_LIVING, MODE_ELEVATION, MODE_GOLDEN_HOUR,
    SHADING_MODE_DIRECTION, SHADING_MODE_INSIDE,
    SHADING_MODE_INSIDE_OUTSIDE, SHADING_MODE_INSIDE_OUTSIDE_DIRECTION,
    SHADING_MODE_OUTSIDE, SHADING_MODE_OUTSIDE_DIRECTION,
)

def _controller(hass):
    entry = MockConfigEntry(domain=DOMAIN, version=15, unique_id=DOMAIN, data={
        CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER,
        CONF_GLOBAL: {"sources": {}, "defaults": {}},
        CONF_GROUPS: {group: {} for group in GROUPS},
    })
    entry.add_to_hass(hass)
    return entry

async def test_controller_menu_shows_three_groups(hass) -> None:
    entry = _controller(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id})
    assert result["menu_options"][:4] == ["global_sources", "group_living", "group_sleep", "group_children"]

async def test_no_profile_creation_menu_exists(hass) -> None:
    entry = _controller(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id})
    assert all("profile" not in option for option in result["menu_options"])

async def test_edit_each_fixed_group_and_back(hass) -> None:
    entry = _controller(hass)
    for group in GROUPS:
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": f"group_{group}"})
        assert result["step_id"] == "group_sections"
        assert "group_back" in result["menu_options"]

async def test_room_group_selector(hass) -> None:
    controller = _controller(hass)
    room = MockConfigEntry(domain=DOMAIN, version=15, data={
        CONF_ENTRY_TYPE: ENTRY_TYPE_ROOM, CONF_CONTROLLER_ENTRY_ID: controller.entry_id,
        CONF_ROOM_ID: "room", CONF_NAME: "Room", CONF_GROUP: GROUP_LIVING,
        CONF_ROOM_SETTINGS: {CONF_ROOM: "living"},
    })
    room.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": room.entry_id})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "group_assignment"})
    assert result["step_id"] == "group_assignment"
    field = next(iter(result["data_schema"].schema))
    assert field.schema == CONF_GROUP

def test_supported_subentry_types_remains_empty() -> None:
    assert CoverControlFlow.async_get_supported_subentry_types(None) == {}

def test_translation_structure_is_synchronized() -> None:
    paths = [
        Path("custom_components/cover_control/strings.json"),
        Path("custom_components/cover_control/translations/en.json"),
        Path("custom_components/cover_control/translations/de.json"),
    ]
    documents = [json.loads(path.read_text()) for path in paths]
    for section in ("config", "options"):
        assert all(set(doc[section]["step"]) == set(documents[0][section]["step"]) for doc in documents)
    assert all(set(doc["selector"]) == set(documents[0]["selector"]) for doc in documents)
    assert "profile_action" not in documents[0]["selector"]


async def test_group_sun_only_shows_fields_for_selected_modes(hass) -> None:
    entry = _controller(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "group_living"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "group_sun"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "time_features": {
                CONF_OPEN_MODE: MODE_ELEVATION,
                CONF_CLOSE_MODE: MODE_GOLDEN_HOUR,
            }
        },
    )
    assert result["step_id"] == "group_sun_details"
    fields = {
        field.schema
        for section_field, schema in result["data_schema"].schema.items()
        for field in schema.schema.schema
    }
    assert fields == {CONF_SUN_ELEVATION_OPEN, CONF_ASTRO_CLOSE_OFFSET}


@pytest.mark.parametrize(
    ("mode", "present", "absent"),
    [
        (SHADING_MODE_INSIDE, CONF_SHADING_INSIDE_TEMPERATURE_THRESHOLD, CONF_SHADING_DIRECTION),
        (SHADING_MODE_OUTSIDE, CONF_SHADING_OUTSIDE_TEMPERATURE_THRESHOLD, CONF_SHADING_DIRECTION),
        (SHADING_MODE_DIRECTION, CONF_SHADING_DIRECTION, CONF_SHADING_OUTSIDE_TEMPERATURE_THRESHOLD),
        (SHADING_MODE_INSIDE_OUTSIDE, CONF_SHADING_INSIDE_TEMPERATURE_THRESHOLD, CONF_SHADING_DIRECTION),
        (SHADING_MODE_OUTSIDE_DIRECTION, CONF_SHADING_DIRECTION, CONF_SHADING_INSIDE_TEMPERATURE_THRESHOLD),
        (SHADING_MODE_INSIDE_OUTSIDE_DIRECTION, CONF_SHADING_DIRECTION, "unsupported"),
    ],
)
async def test_group_shading_only_shows_fields_for_selected_mode(
    hass, mode: str, present: str, absent: str
) -> None:
    entry = _controller(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "group_living"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "group_shading"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"shading_mode": {CONF_SHADING_MODE: mode}}
    )
    assert result["step_id"] == "group_shading_details"
    fields = {
        field.schema
        for section_field, schema in result["data_schema"].schema.items()
        for field in schema.schema.schema
    }
    assert present in fields
    assert absent not in fields
