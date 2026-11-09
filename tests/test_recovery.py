"""Regression tests for structural recovery behavior."""
import json
from pathlib import Path
import pytest
from custom_components.cover_control.const import GROUPS, GROUP_LIVING
from custom_components.cover_control.recovery import ConfigValidationError, RecoveryManager

def _model() -> dict:
    return {
        "global": {"sources": {}, "defaults": {}},
        "groups": {group: {} for group in GROUPS},
        "rooms": {"room": {"group": GROUP_LIVING, "settings": {}, "source_overrides": {}, "overrides": {}}},
    }

async def test_recovery_uses_last_known_good_for_invalid_group(hass) -> None:
    manager = RecoveryManager(hass, "entry")
    await manager.async_mark_good(_model())
    broken = _model()
    broken["rooms"]["room"]["group"] = "missing"
    assert await manager.async_resolve(broken) == _model()
    assert manager.recovered

async def test_recovery_does_not_treat_runtime_unavailability_as_invalid(hass) -> None:
    manager = RecoveryManager(hass, "entry-unavailable")
    await manager.async_initialize()
    model = _model()
    model["global"]["sources"]["brightness_sensor"] = "sensor.unavailable"
    assert await manager.async_resolve(model) == model

async def test_recovery_rejects_invalid_config_without_fallback(hass) -> None:
    manager = RecoveryManager(hass, "entry-empty")
    await manager.async_initialize()
    with pytest.raises(ConfigValidationError):
        await manager.async_resolve({"groups": {}, "rooms": {}})


async def test_recovery_store_loads_current_version(hass) -> None:
    manager = RecoveryManager(hass, "current")
    await manager.async_mark_good(_model())
    restored = RecoveryManager(hass, "current")

    await restored.async_initialize()

    assert restored.last_known_good == _model()


async def test_recovery_store_migrates_version_1(hass) -> None:
    manager = RecoveryManager(hass, "legacy")
    legacy = {
        "profiles": {
            "living": {"name": "Living", "settings": {}},
        },
        "rooms": {
            "room": {
                "name": "Room",
                "profile_id": "living",
                "profile_functions": ["time"],
                "settings": {},
            }
        },
    }
    path = Path(manager._store.path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "minor_version": 1,
                "key": manager._store.key,
                "data": legacy,
            }
        ),
        encoding="utf-8",
    )
    manager._store._manager.async_invalidate(manager._store.key)
    manager._store._manager._files = None
    assert path.exists()
    migrated = await manager._store._async_migrate_func(1, 1, legacy)
    assert set(migrated["groups"]) == set(GROUPS)

    await manager._store.async_save(migrated)
    restored = RecoveryManager(hass, "legacy")
    await restored.async_initialize()

    assert restored.last_known_good is not None
    assert set(restored.last_known_good["groups"]) == set(GROUPS)
    assert restored._store.version == 2


async def test_invalid_legacy_recovery_does_not_block_valid_current_config(hass) -> None:
    manager = RecoveryManager(hass, "invalid-legacy")
    path = Path(manager._store.path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "minor_version": 1,
                "key": manager._store.key,
                "data": {"profiles": None, "rooms": {}},
            }
        ),
        encoding="utf-8",
    )
    manager._store._manager.async_invalidate(manager._store.key)
    manager._store._manager._files = None

    await manager.async_initialize()

    assert manager.last_known_good is None
    assert await manager.async_resolve(_model()) == _model()
