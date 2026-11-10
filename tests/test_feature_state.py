from types import SimpleNamespace

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cover_control.feature_state import feature_configured
from custom_components.cover_control.const import (
    CONF_AUTO_TIME,
    CONF_GROUP,
    CONF_GROUPS,
    CONF_ROOMS,
    CONF_ROOM_SETTINGS,
    DOMAIN,
)
from custom_components.cover_control.runtime_data import CoverControlRuntime
from custom_components.cover_control.switch import async_setup_entry


def test_switch_is_not_configured_for_empty_group() -> None:
    model = {
        CONF_GROUPS: {"living": {}},
        CONF_ROOMS: {"room": {CONF_GROUP: "living", CONF_ROOM_SETTINGS: {}}},
    }
    assert not feature_configured(model, "room", CONF_AUTO_TIME)


def test_switch_remains_configured_when_disabled() -> None:
    model = {
        CONF_GROUPS: {"living": {CONF_AUTO_TIME: False}},
        CONF_ROOMS: {"room": {CONF_GROUP: "living", CONF_ROOM_SETTINGS: {}}},
    }
    assert feature_configured(model, "room", CONF_AUTO_TIME)


@pytest.mark.asyncio
async def test_setup_removes_switch_for_removed_function(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    entry.runtime_data = CoverControlRuntime(
        hub=SimpleNamespace(),
        model={
            CONF_GROUPS: {"living": {}},
            CONF_ROOMS: {
                "room": {CONF_GROUP: "living", CONF_ROOM_SETTINGS: {}}
            },
        },
        room_managers={"room": SimpleNamespace()},
    )
    registry = er.async_get(hass)
    stale = registry.async_get_or_create(
        "switch",
        DOMAIN,
        "room-auto_shading_enabled",
        config_entry=entry,
    )
    added = []

    await async_setup_entry(hass, entry, added.extend)

    assert not added
    assert registry.async_get(stale.entity_id) is None
