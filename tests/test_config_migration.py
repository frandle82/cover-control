"""Tests for config-entry migration to reusable profiles."""

from custom_components.cover_control.config_migration import migrate_entry_payload
from custom_components.cover_control.config_resolver import (
    config_entry_room_id,
    resolve_entry_config,
)
from custom_components.cover_control.const import (
    CONF_BRIGHTNESS_SENSOR,
    CONF_CONFIG_MODEL,
    CONF_COVERS,
    CONF_NAME,
    CONF_ROOM_ID,
    CONF_SHADING_POSITION,
    CONF_SHADING_WAITINGTIME_END,
)


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
    resolved = resolve_entry_config(
        data, options, room_id=config_entry_room_id(data, "entry-1")
    )

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

    assert resolve_entry_config(first, {}, room_id="living")[CONF_SHADING_POSITION] == 24
    assert resolve_entry_config(second, {}, room_id="office")[CONF_SHADING_POSITION] == 26


def test_missing_optional_setting_is_not_persisted() -> None:
    data, _ = migrate_entry_payload(
        {CONF_NAME: "Living", CONF_COVERS: ["cover.living"]},
        {},
        entry_id="entry-1",
    )

    serialized = repr(data[CONF_CONFIG_MODEL])
    assert CONF_BRIGHTNESS_SENSOR not in serialized
