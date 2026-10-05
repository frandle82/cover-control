"""Tests for config-entry migration to reusable profiles."""

from custom_components.cover_control.config_migration import (
    migrate_entry_collection,
    migrate_entry_payload,
)
from custom_components.cover_control.config_resolver import resolve_config_model
from custom_components.cover_control.const import (
    CONF_BRIGHTNESS_SENSOR,
    CONF_CONFIG_MODEL,
    CONF_COVERS,
    CONF_NAME,
    CONF_ROOM_ID,
    CONF_SHADING_POSITION,
    CONF_SHADING_WAITINGTIME_END,
    CONF_PROFILES,
    CONF_ROOMS,
)


def _resolve_migrated(data: dict, room_id: str):
    return resolve_config_model(data[CONF_CONFIG_MODEL], room_id)


def test_flat_data_and_options_migrate_with_options_precedence() -> None:
    old_data = {
        CONF_NAME: "Living",
        CONF_COVERS: ["cover.left", "cover.right"],
        CONF_SHADING_POSITION: 30,
        CONF_BRIGHTNESS_SENSOR: "sensor.outdoor",
    }
    old_options = {
        CONF_SHADING_POSITION: 25,
        CONF_SHADING_WAITINGTIME_END: 600,
    }

    data, options = migrate_entry_payload(
        old_data, old_options, entry_id="entry-1"
    )
    resolved = _resolve_migrated(data, "entry-1")

    assert options == {}
    assert resolved[CONF_COVERS] == ["cover.left", "cover.right"]
    assert resolved[CONF_SHADING_POSITION] == 25
    assert resolved[CONF_SHADING_WAITINGTIME_END] == 600
    assert resolved[CONF_BRIGHTNESS_SENSOR] == "sensor.outdoor"


def test_migration_is_idempotent() -> None:
    data, options = migrate_entry_payload(
        {CONF_NAME: "Living", CONF_COVERS: ["cover.living"]},
        {},
        entry_id="entry-1",
    )

    migrated_again, options_again = migrate_entry_payload(
        data, options, entry_id="entry-1"
    )

    assert migrated_again == data
    assert options_again == options
    assert migrated_again[CONF_ROOM_ID] == "entry-1"
    assert CONF_CONFIG_MODEL in migrated_again


def test_different_entries_keep_different_profile_values() -> None:
    first, _ = migrate_entry_payload(
        {CONF_SHADING_POSITION: 24}, {}, entry_id="living"
    )
    second, _ = migrate_entry_payload(
        {CONF_SHADING_POSITION: 26}, {}, entry_id="office"
    )

    assert _resolve_migrated(first, "living")[CONF_SHADING_POSITION] == 24
    assert _resolve_migrated(second, "office")[CONF_SHADING_POSITION] == 26


def test_missing_optional_setting_is_not_persisted() -> None:
    data, _ = migrate_entry_payload(
        {CONF_NAME: "Living", CONF_COVERS: ["cover.living"]},
        {},
        entry_id="entry-1",
    )

    serialized = repr(data[CONF_CONFIG_MODEL])
    assert CONF_BRIGHTNESS_SENSOR not in serialized


def test_multiple_legacy_rooms_are_consolidated_without_name_deduplication() -> None:
    model = migrate_entry_collection(
        {
            "living": (
                {CONF_NAME: "Living", CONF_SHADING_POSITION: 24},
                {},
            ),
            "office": (
                {CONF_NAME: "Office", CONF_SHADING_POSITION: 26},
                {},
            ),
        }
    )

    assert set(model[CONF_ROOMS]) == {"living", "office"}
    profiles = model[CONF_PROFILES]
    assert len(profiles) == 2
    assert {
        room["settings"][CONF_SHADING_POSITION]
        for room in model[CONF_ROOMS].values()
    } == {24, 26}


def test_collection_migration_is_idempotent_for_canonical_hub_model() -> None:
    model = migrate_entry_collection(
        {"living": ({CONF_NAME: "Living", CONF_SHADING_POSITION: 24}, {})}
    )
    migrated = migrate_entry_collection(
        {"living": ({CONF_NAME: "Living", CONF_CONFIG_MODEL: model}, {})}
    )

    assert migrated == model
