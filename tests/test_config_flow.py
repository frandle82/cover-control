"""Config flow tests for Cover Control."""

from __future__ import annotations

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import ServiceRegistry
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import selector
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cover_control.const import CONF_COVERS, DEFAULT_NAME, DOMAIN

REQUIRES_NEW_HA = (
    not hasattr(selector, "ConditionSelector")
    or not hasattr(ServiceRegistry, "async_services_for_domain")
)


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
        {CONF_NAME: "Test", CONF_COVERS: ["cover.test_cover"]},
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
async def test_options_flow_loads_for_existing_entry(hass):
    """Ensure options flow schema can be built successfully."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={CONF_NAME: DEFAULT_NAME, CONF_COVERS: ["cover.test_cover"]},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
