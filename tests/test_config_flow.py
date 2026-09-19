"""Config flow tests for Cover Control."""

from __future__ import annotations

import json

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
from custom_components.cover_control.const import (
    CONF_AUTO_SHADING,
    CONF_AUTO_VENTILATE,
    CONF_COVERS,
    CONF_ROOM,
    DEFAULT_NAME,
    DOMAIN,
)

REQUIRES_NEW_HA = (
    not hasattr(selector, "ConditionSelector")
    or not hasattr(ServiceRegistry, "async_services_for_domain")
)


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
    assert result["data"][CONF_COVERS] == ["cover.test_cover"]


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
    assert schedule_data["positions"]["open_position"] == "100"
    assert schedule_data["tilt_positions"]["open_tilt_position"] == "50"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], schedule_data
    )
    assert result["step_id"] == "shading"
    shading_data = _frontend_initial_data(result["data_schema"])
    assert shading_data["brightness_controls"]
    assert shading_data["sun_controls"]
    assert shading_data["shading_controls"]
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
