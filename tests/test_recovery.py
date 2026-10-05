"""Regression tests for structural recovery behavior."""

import pytest

from custom_components.cover_control.recovery import (
    ConfigValidationError,
    RecoveryManager,
)


def _model(profile_id: str = "profile") -> dict:
    return {
        "global": {"sources": {}, "defaults": {}},
        "profiles": {
            "time": {profile_id: {"settings": {}}},
            "shading": {},
            "behavior": {},
        },
        "rooms": {
            "room": {
                "profiles": {"time": profile_id},
                "settings": {},
                "source_overrides": {},
                "overrides": {},
            }
        },
    }


async def test_recovery_uses_last_known_good_for_dangling_reference(hass) -> None:
    manager = RecoveryManager(hass, "entry")
    await manager.async_initialize()
    await manager.async_mark_good(_model())
    broken = _model("missing")
    broken["profiles"]["time"] = {}

    recovered = await manager.async_resolve(broken)

    assert recovered == _model()
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
        await manager.async_resolve(
            {
                "profiles": {},
                "rooms": {
                    "room": {
                        "profile_id": "missing",
                        "settings": {},
                        "source_overrides": {},
                        "overrides": {},
                    }
                },
            }
        )
