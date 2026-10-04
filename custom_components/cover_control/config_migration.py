"""Config-entry schema migration for hierarchical room configuration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .config_profiles import ConfigProfileModel
from .config_resolver import GLOBAL_SOURCE_KEYS, PROFILE_KEYS
from .const import (
    CONFIG_MODEL_VERSION,
    CONF_CONFIG_MODEL,
    CONF_GLOBAL,
    CONF_GLOBAL_DEFAULTS,
    CONF_GLOBAL_SOURCES,
    CONF_CONFIG_VERSION,
    CONF_NAME,
    CONF_PROFILE_ID,
    CONF_PROFILE_NAME,
    CONF_PROFILE_SELECTIONS,
    CONF_PROFILE_SETTINGS,
    CONF_PROFILES,
    CONF_ROOMS,
    CONF_ROOM,
    CONF_ROOM_ID,
    CONF_ROOM_OVERRIDES,
    CONF_ROOM_SETTINGS,
    CONF_SOURCE_OVERRIDES,
    DEFAULT_NAME,
    PROFILE_TYPES,
)


def is_native_parent_entry(data: Mapping[str, Any]) -> bool:
    """Return whether data already uses the native parent/subentry shape."""

    return CONF_GLOBAL in data and CONF_CONFIG_MODEL not in data


def has_legacy_config_model(data: Mapping[str, Any]) -> bool:
    """Return whether a legacy embedded model is still present."""

    return CONF_CONFIG_MODEL in data


def legacy_entry_model(
    data: Mapping[str, Any], options: Mapping[str, Any], *, entry_id: str
) -> dict[str, Any]:
    """Normalize one legacy parent or standalone room entry."""

    if CONF_CONFIG_MODEL in data:
        return dict(data[CONF_CONFIG_MODEL])
    migrated, _options = migrate_entry_payload(data, options, entry_id=entry_id)
    return migrated[CONF_CONFIG_MODEL]


def normalize_legacy_config(
    data: Mapping[str, Any],
    options: Mapping[str, Any],
    *,
    room_id: str,
) -> dict[str, Any]:
    """Convert a flat legacy entry to an equivalent in-memory profile model."""

    flat = {**data, **options}
    room_name = str(flat.get(CONF_ROOM) or flat.get(CONF_NAME) or room_id)
    profiles: dict[str, dict[str, Any]] = {kind: {} for kind in PROFILE_TYPES}
    selections: dict[str, str] = {}
    classified: set[str] = set()
    for profile_type, keys in PROFILE_KEYS.items():
        settings = {key: flat[key] for key in keys if key in flat}
        profile_id = f"legacy-{room_id}-{profile_type}"
        profiles[profile_type][profile_id] = {
            CONF_PROFILE_ID: profile_id,
            CONF_PROFILE_NAME: f"{room_name} (legacy)",
            CONF_PROFILE_SETTINGS: settings,
        }
        selections[profile_type] = profile_id
        classified.update(settings)

    global_sources = {
        key: flat[key] for key in GLOBAL_SOURCE_KEYS if key in flat
    }
    classified.update(global_sources)
    model_keys = {
        CONF_CONFIG_MODEL,
        CONF_CONFIG_VERSION,
        CONF_GLOBAL,
        CONF_PROFILES,
        CONF_ROOMS,
    }
    room_settings = {
        key: value
        for key, value in flat.items()
        if key not in classified and key not in model_keys
    }
    return {
        CONF_CONFIG_VERSION: CONFIG_MODEL_VERSION,
        CONF_GLOBAL: {
            CONF_GLOBAL_SOURCES: global_sources,
            CONF_GLOBAL_DEFAULTS: {},
        },
        CONF_PROFILES: profiles,
        CONF_ROOMS: {
            room_id: {
                CONF_ROOM_ID: room_id,
                CONF_NAME: room_name,
                CONF_PROFILE_SELECTIONS: selections,
                CONF_ROOM_SETTINGS: room_settings,
                CONF_SOURCE_OVERRIDES: {},
                CONF_ROOM_OVERRIDES: {},
            }
        },
    }


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
