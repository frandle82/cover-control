"""Tests for native profile and override schemas."""

import json
from datetime import time
from pathlib import Path

from probatio import to_field_list

from homeassistant.helpers import config_validation as cv

from custom_components.cover_control import const as c
from custom_components.cover_control.config_profile_schema import (
    CONF_PROFILE_FIELDS,
    PROFILE_CAPABILITY_KEYS,
    PROFILE_FIELD_METADATA,
    build_profile_schema,
    capability_keys,
    extract_sparse_settings,
    flatten_section_input,
    profile_groups,
)
from custom_components.cover_control.config_resolver import PROFILE_KEYS, system_defaults


def test_every_supported_profile_key_has_one_native_schema_field() -> None:
    """Every resolver-supported profile key is reachable in the native UI."""

    defaults = system_defaults()
    for profile_type, supported in PROFILE_KEYS.items():
        grouped = {key for _group, keys in profile_groups(profile_type) for key in keys}
        assert grouped == supported

        schema = build_profile_schema(profile_type, {}, defaults)
        serialized = to_field_list(schema, custom_serializer=cv.custom_serializer)
        native_fields = {
            nested["name"]
            for field in serialized
            if field.get("type") == "expandable"
            for nested in field["schema"]
        }
        assert native_fields == supported


def test_capabilities_partition_every_profile_key_exactly_once() -> None:
    """Capabilities remain a UI grouping, never a parallel runtime model."""

    for profile_type, supported in PROFILE_KEYS.items():
        groups = PROFILE_CAPABILITY_KEYS[profile_type]
        flattened = [key for keys in groups.values() for key in keys]
        assert set(flattened) == supported
        assert len(flattened) == len(set(flattened))
    assert set(PROFILE_FIELD_METADATA) == set().union(*PROFILE_KEYS.values())


def test_metadata_drives_basic_and_advanced_ui_levels() -> None:
    brightness = PROFILE_FIELD_METADATA[c.CONF_AUTO_SHADING]
    waiting = PROFILE_FIELD_METADATA[c.CONF_SHADING_WAITINGTIME_START]

    assert brightness.owner == "PROFILE"
    assert brightness.feature == c.PROFILE_TYPE_SHADING
    assert brightness.ui_level == "basic"
    assert waiting.ui_level == "advanced"
    assert brightness.selector == brightness.value_type
    assert c.CONF_SHADING_POSITION not in PROFILE_FIELD_METADATA


def test_capability_removal_discards_disabled_known_values() -> None:
    existing = {
        c.CONF_SHADING_BRIGHTNESS_START: 40000,
        c.CONF_SHADING_FORECAST_TEMP: 25,
        "future_profile_key": "preserve",
    }
    allowed = capability_keys(c.PROFILE_TYPE_SHADING, ["brightness"])

    settings = extract_sparse_settings(
        {c.CONF_SHADING_BRIGHTNESS_START: 45000},
        c.PROFILE_TYPE_SHADING,
        existing,
        field_selection=None,
        allowed_keys=allowed,
    )

    assert settings == {
        c.CONF_SHADING_BRIGHTNESS_START: 45000,
        "future_profile_key": "preserve",
    }


def test_sparse_extraction_normalizes_selectors_and_preserves_unknown_keys() -> None:
    """Displayed fallbacks stay transient while legacy data survives round trips."""

    submitted = flatten_section_input(
        {
            CONF_PROFILE_FIELDS: [
                c.CONF_AUTO_TIME,
                c.CONF_TIME_UP_EARLY_WORKDAY,
            ],
            "time_features": {c.CONF_AUTO_TIME: True},
            "workday_times": {c.CONF_TIME_UP_EARLY_WORKDAY: time(6, 45)},
            "sun_settings": {c.CONF_SUN_ELEVATION_OPEN: -3.0},
        }
    )
    settings = extract_sparse_settings(
        submitted,
        c.PROFILE_TYPE_TIME,
        {"future_profile_key": {"nested": True}},
    )

    assert settings == {
        c.CONF_AUTO_TIME: True,
        c.CONF_TIME_UP_EARLY_WORKDAY: "06:45:00",
        "future_profile_key": {"nested": True},
    }


def test_normal_options_flow_contains_no_free_json_fields() -> None:
    """Profile and room configuration no longer exposes JSON text editors."""

    source = Path("custom_components/cover_control/config_flow.py").read_text()
    assert "profile_settings_json" not in source
    assert "room_overrides_json" not in source
    assert "json.loads" not in source
    assert "json.dumps" not in source


def test_every_profile_field_has_selector_translations() -> None:
    """Legacy sparse field labels remain available for every active profile key."""

    expected = set().union(*PROFILE_KEYS.values())
    for path in (
        "custom_components/cover_control/strings.json",
        "custom_components/cover_control/translations/en.json",
        "custom_components/cover_control/translations/de.json",
    ):
        document = json.loads(Path(path).read_text())
        assert expected <= set(document["selector"]["profile_field"]["options"])
