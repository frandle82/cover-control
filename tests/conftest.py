"""Pytest configuration for Cover Control tests."""

import pytest


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """Keep Home Assistant test storage outside the repository."""
    return hass_tmp_config_dir
