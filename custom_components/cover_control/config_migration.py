"""Config-entry schema migration for hierarchical room configuration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .config_profiles import ConfigProfileModel
from .config_resolver import normalize_legacy_config
from .const import (
    CONFIG_MODEL_VERSION,
    CONF_CONFIG_MODEL,
    CONF_CONFIG_VERSION,
    CONF_NAME,
    CONF_ROOM_ID,
    DEFAULT_NAME,
)


def migrate_entry_payload(
    data: Mapping[str, Any], options: Mapping[str, Any], *, entry_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return canonical entry data and empty options without changing behavior."""

    existing = data.get(CONF_CONFIG_MODEL)
    if isinstance(existing, Mapping):
        room_id = str(data.get(CONF_ROOM_ID) or entry_id)
        canonical = dict(data)
        canonical[CONF_ROOM_ID] = room_id
        model = ConfigProfileModel(existing).data
        model[CONF_CONFIG_VERSION] = CONFIG_MODEL_VERSION
        canonical[CONF_CONFIG_MODEL] = model
        return canonical, dict(options)

    flat = {**data, **options}
    room_id = str(flat.get(CONF_ROOM_ID) or entry_id)
    name = str(flat.get(CONF_NAME) or DEFAULT_NAME)
    model = ConfigProfileModel(
        normalize_legacy_config(data, options, room_id=room_id)
    ).data
    model[CONF_CONFIG_VERSION] = CONFIG_MODEL_VERSION
    return (
        {
            CONF_ROOM_ID: room_id,
            CONF_NAME: name,
            CONF_CONFIG_MODEL: model,
        },
        {},
    )


def migrate_entry_collection(
    entries: Mapping[str, tuple[Mapping[str, Any], Mapping[str, Any]]]
) -> dict[str, Any]:
    """Consolidate 0.10.x room entries into one idempotent hub model."""

    from .hub import merge_config_models

    hub_model: dict[str, Any] | None = None
    for entry_id, (data, options) in entries.items():
        migrated, _ = migrate_entry_payload(data, options, entry_id=entry_id)
        incoming = migrated[CONF_CONFIG_MODEL]
        hub_model = (
            ConfigProfileModel(incoming).data
            if hub_model is None
            else merge_config_models(hub_model, incoming, namespace=entry_id)
        )
    if hub_model is None:
        hub_model = ConfigProfileModel({}).data
    hub_model[CONF_CONFIG_VERSION] = CONFIG_MODEL_VERSION
    return hub_model
