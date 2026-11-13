"""Pytest configuration for Cover Control tests."""

import sys

import pytest

try:
    import pytest_homeassistant.common
except ModuleNotFoundError:
    import pytest_homeassistant_custom_component as pytest_homeassistant
    from pytest_homeassistant_custom_component import common

    sys.modules["pytest_homeassistant"] = pytest_homeassistant
    sys.modules["pytest_homeassistant.common"] = common


@pytest.fixture(autouse=True)
def enable_custom_component_loading(enable_custom_integrations):
    """Enable local custom integrations with both supported test plugins."""


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """Keep Home Assistant test storage outside the repository."""
    return hass_tmp_config_dir
