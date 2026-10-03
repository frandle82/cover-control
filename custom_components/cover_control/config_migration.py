"""Config-entry schema migration for hierarchical room configuration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .config_resolver import normalize_legacy_config
from .const import CONF_CONFIG_MODEL, CONF_NAME, CONF_ROOM_ID, DEFAULT_NAME


def migrate_entry_payload(
    data: Mapping[str, Any], options: Mapping[str, Any], *, entry_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return canonical entry data and empty options without changing behavior."""

    existing = data.get(CONF_CONFIG_MODEL)
    if isinstance(existing, Mapping):
        room_id = str(data.get(CONF_ROOM_ID) or entry_id)
        canonical = dict(data)
        canonical[CONF_ROOM_ID] = room_id
        return canonical, dict(options)

    flat = {**data, **options}
    room_id = str(flat.get(CONF_ROOM_ID) or entry_id)
    name = str(flat.get(CONF_NAME) or DEFAULT_NAME)
    return (
        {
            CONF_ROOM_ID: room_id,
            CONF_NAME: name,
            CONF_CONFIG_MODEL: normalize_legacy_config(
                data, options, room_id=room_id
            ),
        },
        {},
    )
