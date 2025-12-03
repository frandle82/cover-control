"""Best-effort helpers to provision configuration entities.

This module previously relied on Home Assistant helper factory functions that are
not available in all installations (for example,
``input_number.async_create_input_number``). Attempting to call those functions
would block setup entirely. The implementation below intentionally avoids
calling missing helper APIs so the Cover Control integration can continue to
load even when the dynamic helper creation features are unavailable.
"""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_WARNED_KEY = "config_entities_unavailable"


async def ensure_config_entities(
    hass: HomeAssistant, entry_id: str, data: dict
) -> dict:
    """Ensure any optional helper entities exist.

    Older releases attempted to create input_number helpers via
    ``homeassistant.components.input_number.async_create_input_number``, which
    does not exist on the target Home Assistant version. Instead of failing
    setup, we log once and skip creation. The returned dictionary mirrors the
    previous signature but is intentionally empty to signal that nothing was
    created.
    """

    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get(_WARNED_KEY):
        _LOGGER.debug(
            "Skipping helper entity creation because Home Assistant does not "
            "expose dynamic input helper APIs."
        )
        domain_data[_WARNED_KEY] = True

    return {}
