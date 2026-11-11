"""Config-flow tests for the three fixed groups."""
import json
from pathlib import Path
import pytest
from homeassistant import config_entries
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import selector
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.cover_control.config_flow import CoverControlFlow
from custom_components.cover_control.const import (
    CONF_CONTROLLER_ENTRY_ID, CONF_COVERS, CONF_ENTRY_TYPE, CONF_GLOBAL, CONF_GROUP,
    CONF_GROUPS, CONF_NAME, CONF_ROOM, CONF_ROOM_ID, CONF_ROOM_SETTINGS,
    CONF_CLOSE_MODE, CONF_OPEN_MODE, CONF_SUN_ELEVATION_OPEN,
    CONF_FINAL_CLOSE_ELEVATION, CONF_FINAL_CLOSE_ELEVATION_ENABLED,
    CONF_FINAL_CLOSE_TIME, CONF_FINAL_CLOSE_TIME_ENABLED,
    CONF_INTERMEDIATE_CLOSE_ENABLED,
    CONF_SHADING_DIRECTION, CONF_SHADING_INSIDE_TEMPERATURE_THRESHOLD,
    CONF_KEEP_SUN_PROTECTION,
    CONF_OPEN_TILT_POSITION,
    CONF_MANUAL_CONTROL, CONF_MANUAL_OVERRIDE_MINUTES,
    CONF_SHADING_MODE, CONF_SHADING_OUTSIDE_TEMPERATURE_THRESHOLD,
    CONF_ASTRO_CLOSE_OFFSET, DOMAIN, ENTRY_TYPE_CONTROLLER, ENTRY_TYPE_ROOM,
    GROUPS, GROUP_LIVING, MODE_ELEVATION, MODE_GOLDEN_HOUR,
    SHADING_MODE_DIRECTION, SHADING_MODE_INSIDE,
    SHADING_MODE_INSIDE_OUTSIDE, SHADING_MODE_INSIDE_OUTSIDE_DIRECTION,
    SHADING_MODE_OUTSIDE, SHADING_MODE_OUTSIDE_DIRECTION,
)

def _controller(hass):
    entry = MockConfigEntry(domain=DOMAIN, version=16, unique_id=DOMAIN, data={
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
    room = MockConfigEntry(domain=DOMAIN, version=16, data={
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


@pytest.mark.parametrize("supports_tilt", [False, True])
async def test_room_positions_follow_cover_tilt_capability(hass, supports_tilt) -> None:
    controller = _controller(hass)
    features = int(CoverEntityFeature.SET_TILT_POSITION) if supports_tilt else 0
    hass.states.async_set("cover.room", "open", {"supported_features": features})
    room = MockConfigEntry(
        domain=DOMAIN,
        version=19,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_ROOM,
            CONF_CONTROLLER_ENTRY_ID: controller.entry_id,
            CONF_ROOM_ID: "room",
            CONF_NAME: "Room",
            CONF_GROUP: GROUP_LIVING,
            CONF_ROOM_SETTINGS: {CONF_COVERS: ["cover.room"]},
        },
    )
    room.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": room.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "positions"}
    )

    sections = {
        field.schema: schema for field, schema in result["data_schema"].schema.items()
    }
    assert ("tilt_positions" in sections) is supports_tilt
    if supports_tilt:
        tilt_fields = {
            field.schema for field in sections["tilt_positions"].schema.schema
        }
        assert CONF_OPEN_TILT_POSITION in tilt_fields
        assert not any(field.startswith("shading_tilt_position_") for field in tilt_fields)

def test_supported_subentry_types_remains_empty() -> None:
    assert CoverControlFlow.async_get_supported_subentry_types(None) == {}

def test_translation_structures_match() -> None:
    paths = [
        Path("custom_components/cover_control/strings.json"),
        Path("custom_components/cover_control/translations/en.json"),
        Path("custom_components/cover_control/translations/de.json"),
    ]
    documents = [json.loads(path.read_text()) for path in paths]
    def paths(value, prefix=()):
        if isinstance(value, dict):
            return {
                item
                for key, child in value.items()
                for item in paths(child, prefix + (key,))
            }
        return {prefix}

    assert all(paths(doc) == paths(documents[0]) for doc in documents)
    assert "profile_action" not in documents[0]["selector"]


def test_menu_option_descriptions_differ_from_menu_labels() -> None:
    for path in (
        Path("custom_components/cover_control/strings.json"),
        Path("custom_components/cover_control/translations/en.json"),
        Path("custom_components/cover_control/translations/de.json"),
    ):
        document = json.loads(path.read_text())

        def check(value) -> None:
            if not isinstance(value, dict):
                return
            labels = value.get("menu_options", {})
            descriptions = value.get("menu_option_descriptions", {})
            for key, label in labels.items():
                if key in descriptions:
                    description = descriptions[key]
                    assert description != label, f"{path}: {key}"
                    assert len(description.split()) > len(label.split()), (
                        f"{path}: {key} description adds no useful context"
                    )
            for child in value.values():
                check(child)

        check(document)


def test_required_translation_keys_exist() -> None:
    paths = (
        Path("custom_components/cover_control/strings.json"),
        Path("custom_components/cover_control/translations/en.json"),
        Path("custom_components/cover_control/translations/de.json"),
    )
    required_final_close = {
        "final_close_time",
        "final_close_elevation",
    }
    required_switches = {
        "auto_time",
        "auto_brightness",
        "auto_sun",
        "auto_ventilate",
        "auto_shading",
        "resident_status",
    }
    for path in paths:
        document = json.loads(path.read_text())
        for namespace in ("config", "options"):
            section = document[namespace]["step"]["group_final_close"][
                "sections"
            ]["non_workday_times"]
            assert required_final_close <= section["data"].keys()
            assert required_final_close <= section["data_description"].keys()
        assert required_switches <= document["entity"]["switch"].keys()


def test_no_internal_keys_are_exposed_as_ui_labels() -> None:
    paths = (
        Path("custom_components/cover_control/strings.json"),
        Path("custom_components/cover_control/translations/en.json"),
        Path("custom_components/cover_control/translations/de.json"),
    )
    internal_keys = {
        "final_close_elevation",
        "final_close_time_enabled",
        "auto_sun",
        "auto_brightness",
        "resident_status",
        "intermediate_close_enabled",
    }

    def visible_texts(value):
        if isinstance(value, dict):
            return [
                text
                for child in value.values()
                for text in visible_texts(child)
            ]
        return [value] if isinstance(value, str) else []

    for path in paths:
        document = json.loads(path.read_text())
        for text in visible_texts(document):
            assert not any(key in text for key in internal_keys), f"{path}: {text}"

    german = Path(
        "custom_components/cover_control/translations/de.json"
    ).read_text()
    for anglicism in (
        "Final Close",
        "Manual Override",
        "Runtime Toggle",
        "Room-Entries",
        "Workday",
    ):
        assert anglicism not in german


def test_final_close_translations_are_complete_and_user_facing() -> None:
    internal_keys = {
        "final_close_elevation",
        "final_close_elevation_enabled",
        "final_close_time_enabled",
        "intermediate_close_enabled",
    }
    for path in (
        Path("custom_components/cover_control/strings.json"),
        Path("custom_components/cover_control/translations/en.json"),
        Path("custom_components/cover_control/translations/de.json"),
    ):
        document = json.loads(path.read_text())
        for namespace in ("config", "options"):
            fields = document[namespace]["step"]["group_time"]["sections"][
                "time_features"
            ]
            assert internal_keys <= fields["data"].keys()
            assert internal_keys <= fields["data_description"].keys()
            assert not internal_keys & set(fields["data"].values())


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
    ("time_enabled", "elevation_enabled", "expected_fields"),
    [
        (True, False, {CONF_FINAL_CLOSE_TIME}),
        (False, True, {CONF_FINAL_CLOSE_ELEVATION}),
        (
            True,
            True,
            {CONF_FINAL_CLOSE_TIME, CONF_FINAL_CLOSE_ELEVATION},
        ),
        (False, False, None),
    ],
)
async def test_final_close_only_shows_values_for_enabled_triggers(
    hass, time_enabled, elevation_enabled, expected_fields
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
        result["flow_id"], {"next_step_id": "group_time"}
    )
    main_fields = {
        field.schema
        for section_field, schema in result["data_schema"].schema.items()
        for field in schema.schema.schema
    }
    assert CONF_FINAL_CLOSE_TIME not in main_fields
    assert CONF_FINAL_CLOSE_ELEVATION not in main_fields

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "time_features": {
                CONF_INTERMEDIATE_CLOSE_ENABLED: True,
            },
            "non_workday_times": {
                CONF_FINAL_CLOSE_TIME_ENABLED: time_enabled,
                CONF_FINAL_CLOSE_ELEVATION_ENABLED: elevation_enabled,
            }
        },
    )
    if expected_fields is None:
        assert result["step_id"] == "group_sections"
        return
    assert result["step_id"] == "group_final_close"
    detail_fields = {
        field.schema: validator
        for section_field, schema in result["data_schema"].schema.items()
        for field, validator in schema.schema.schema.items()
    }
    assert set(detail_fields) == expected_fields
    if CONF_FINAL_CLOSE_TIME in detail_fields:
        assert isinstance(detail_fields[CONF_FINAL_CLOSE_TIME], selector.TimeSelector)
    if CONF_FINAL_CLOSE_ELEVATION in detail_fields:
        assert isinstance(
            detail_fields[CONF_FINAL_CLOSE_ELEVATION], selector.NumberSelector
        )


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
    assert CONF_KEEP_SUN_PROTECTION in fields


async def test_group_ventilation_hides_removed_cca_options(hass) -> None:
    entry = _controller(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "group_living"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "group_ventilation"}
    )
    fields = {
        field.schema
        for section_field, schema in result["data_schema"].schema.items()
        for field in schema.schema.schema
    }
    assert fields == {
        "auto_ventilate_enabled",
        "contact_status_delay",
        "contact_trigger_delay",
        "ventilation_delay_after_close",
    }


async def test_group_behavior_exposes_simple_manual_override(hass) -> None:
    entry = _controller(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "group_living"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "group_behavior"}
    )
    fields = {
        field.schema
        for _section_field, schema in result["data_schema"].schema.items()
        for field in schema.schema.schema
    }

    assert {CONF_MANUAL_CONTROL, CONF_MANUAL_OVERRIDE_MINUTES} <= fields
    assert not fields & {
        "manual_override_block_open",
        "manual_override_block_close",
        "manual_override_block_ventilate",
        "manual_override_block_shading",
        "manual_override_reset_mode",
        "manual_override_reset_time",
        "manual_schedule_adoption",
    }
