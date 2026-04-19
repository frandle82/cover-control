"""Pytest fixtures for Cover Control tests."""

from collections.abc import AsyncGenerator
from pathlib import Path
import sys

import pytest

# Ensure repository root is importable so `custom_components` can be resolved.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
async def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> AsyncGenerator[None, None]:
    """Enable loading the integration from custom_components during tests."""
    _ = enable_custom_integrations
    yield
