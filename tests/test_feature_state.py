"""Tests for configured/enabled/eligible separation."""

from custom_components.cover_control.feature_state import feature_configured


def test_configured_false_when_default_only() -> None:
    model = {"profiles": {"time": {}}, "rooms": {"room": {"settings": {}}}}
    assert not feature_configured(model, "room", "auto_time_enabled")


def test_configured_true_even_when_persisted_value_is_false() -> None:
    model = {
        "profiles": {"time": {}},
        "rooms": {"room": {"settings": {"auto_time_enabled": False}}},
    }
    assert feature_configured(model, "room", "auto_time_enabled")
