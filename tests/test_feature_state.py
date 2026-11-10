from custom_components.cover_control.feature_state import feature_configured
from custom_components.cover_control.const import (
    CONF_AUTO_TIME,
    CONF_GROUP,
    CONF_GROUPS,
    CONF_ROOMS,
    CONF_ROOM_SETTINGS,
)


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
