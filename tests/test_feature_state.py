from types import SimpleNamespace

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cover_control.const import (
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_SHADING,
    CONF_AUTO_SUN,
    CONF_AUTO_TIME,
    CONF_CLOSE_MODE,
    CONF_GROUP,
    CONF_GROUPS,
    CONF_OPEN_MODE,
    CONF_RESIDENT_STATUS,
    CONF_AUTO_VENTILATE,
    CONF_WINDOW_SENSOR_FULL,
    CONF_ROOMS,
    CONF_ROOM_OVERRIDES,
    CONF_ROOM_SETTINGS,
    DOMAIN,
    MODE_BRIGHTNESS,
    MODE_ELEVATION,
    MODE_SUNSET,
    MODE_TIME,
)
from custom_components.cover_control.feature_state import feature_configured
from custom_components.cover_control.runtime_data import CoverControlRuntime
from custom_components.cover_control.switch import AUTOMATION_TOGGLES, async_setup_entry


def test_unconfigured_features_do_not_create_switches() -> None:
    model = {
        CONF_GROUPS: {"living": {}},
        CONF_ROOMS: {"room": {CONF_GROUP: "living", CONF_ROOM_SETTINGS: {}}},
    }
    assert not any(
        feature_configured(model, "room", key) for key, _name in AUTOMATION_TOGGLES
    )


def test_configured_but_disabled_feature_keeps_switch() -> None:
    model = {
        CONF_GROUPS: {"living": {CONF_AUTO_TIME: False}},
        CONF_ROOMS: {"room": {CONF_GROUP: "living", CONF_ROOM_SETTINGS: {}}},
    }
    assert feature_configured(model, "room", CONF_AUTO_TIME)


def test_room_contacts_configure_ventilation_switch_without_enabling_it() -> None:
    model = {
        CONF_GROUPS: {"living": {}},
        CONF_ROOMS: {
            "room": {
                CONF_GROUP: "living",
                CONF_ROOM_SETTINGS: {
                    CONF_WINDOW_SENSOR_FULL: {
                        "cover.room": ["binary_sensor.window"]
                    }
                },
            }
        },
    }

    assert feature_configured(model, "room", CONF_AUTO_VENTILATE)


def test_empty_room_contact_maps_do_not_create_ventilation_switch() -> None:
    model = {
        CONF_GROUPS: {"living": {}},
        CONF_ROOMS: {
            "room": {
                CONF_GROUP: "living",
                CONF_ROOM_SETTINGS: {
                    CONF_WINDOW_SENSOR_FULL: {"cover.room": []}
                },
            }
        },
    }

    assert not feature_configured(model, "room", CONF_AUTO_VENTILATE)


@pytest.mark.asyncio
async def test_room_with_only_sun_control_does_not_get_resident_or_shading_switch(
    hass,
) -> None:
    model = {
        CONF_GROUPS: {
            "living": {
                CONF_OPEN_MODE: MODE_ELEVATION,
                CONF_CLOSE_MODE: MODE_SUNSET,
                CONF_AUTO_TIME: True,
                CONF_AUTO_SUN: False,
            }
        },
        CONF_ROOMS: {"room": {CONF_GROUP: "living", CONF_ROOM_SETTINGS: {}}},
    }

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    entry.runtime_data = CoverControlRuntime(
        hub=SimpleNamespace(),
        model=model,
        room_managers={"room": SimpleNamespace()},
    )
    added = []

    await async_setup_entry(hass, entry, added.extend)

    assert {entity._key for entity in added} == {CONF_AUTO_TIME, CONF_AUTO_SUN}


def test_non_brightness_modes_ignore_derived_disabled_flag() -> None:
    model = {
        CONF_GROUPS: {
            "living": {
                CONF_OPEN_MODE: MODE_ELEVATION,
                CONF_CLOSE_MODE: MODE_SUNSET,
                CONF_AUTO_BRIGHTNESS: False,
            }
        },
        CONF_ROOMS: {"room": {CONF_GROUP: "living", CONF_ROOM_SETTINGS: {}}},
    }

    assert not feature_configured(model, "room", CONF_AUTO_BRIGHTNESS)


def test_brightness_mode_keeps_disabled_runtime_switch() -> None:
    model = {
        CONF_GROUPS: {
            "living": {
                CONF_CLOSE_MODE: MODE_BRIGHTNESS,
                CONF_AUTO_BRIGHTNESS: False,
            }
        },
        CONF_ROOMS: {"room": {CONF_GROUP: "living", CONF_ROOM_SETTINGS: {}}},
    }

    assert feature_configured(model, "room", CONF_AUTO_BRIGHTNESS)


def test_cover_override_does_not_hide_group_sun_function() -> None:
    model = {
        CONF_GROUPS: {
            "living": {
                CONF_OPEN_MODE: MODE_ELEVATION,
                CONF_CLOSE_MODE: MODE_SUNSET,
            }
        },
        CONF_ROOMS: {
            "room": {
                CONF_GROUP: "living",
                CONF_ROOM_SETTINGS: {},
                CONF_ROOM_OVERRIDES: {
                    "cover.one": {
                        CONF_OPEN_MODE: MODE_TIME,
                        CONF_CLOSE_MODE: MODE_TIME,
                    }
                },
            }
        },
    }

    assert feature_configured(model, "room", CONF_AUTO_SUN)


@pytest.mark.asyncio
async def test_removed_feature_switch_is_removed_from_registry(hass) -> None:
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
