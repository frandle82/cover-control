"""Config-entry schema migration for hierarchical room configuration."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha1
from typing import Any

from .config_profiles import ConfigProfileModel
from .config_resolver import (
    GLOBAL_SOURCE_KEYS,
    PROFILE_KEYS,
    configured_functions_from_profile,
)
from .const import (
    CONFIG_MODEL_VERSION,
    CONF_CONFIG_MODEL,
    CONF_GLOBAL,
    CONF_GLOBAL_DEFAULTS,
    CONF_GLOBAL_SOURCES,
    CONF_CONFIG_VERSION,
    CONF_NAME,
    CONF_PROFILE_ID,
    CONF_PROFILE_FUNCTIONS,
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


def unified_profile_id(selections: Mapping[str, Any]) -> str:
    """Return a deterministic unified profile ID for a legacy type combination."""

    material = "|".join(
        f"{profile_type}={selections.get(profile_type, '')}"
        for profile_type in PROFILE_TYPES
    )
    return f"profile-{sha1(material.encode('utf-8')).hexdigest()[:12]}"


def unify_profile_model(model: Mapping[str, Any]) -> dict[str, Any]:
    """Convert legacy typed profile catalogs into the v6 unified profile model."""

    raw_profiles = model.get(CONF_PROFILES, {})
    already_unified = isinstance(raw_profiles, Mapping) and not any(
        profile_type in raw_profiles for profile_type in PROFILE_TYPES
    )
    canonical = ConfigProfileModel(model).data
    profiles = canonical.get(CONF_PROFILES, {})
    if already_unified:
        canonical[CONF_PROFILES] = {
            profile_id: deepcopy(profile)
            for profile_id, profile in profiles.items()
            if profile_id not in PROFILE_TYPES and isinstance(profile, Mapping)
        }
        canonical[CONF_CONFIG_VERSION] = CONFIG_MODEL_VERSION
        return canonical

    unified_profiles: dict[str, dict[str, Any]] = {
        profile_id: deepcopy(profile)
        for profile_id, profile in profiles.items()
        if profile_id not in PROFILE_TYPES and isinstance(profile, Mapping)
    }
    for room in canonical.get(CONF_ROOMS, {}).values():
        selections = room.get(CONF_PROFILE_SELECTIONS, {})
        if not isinstance(selections, Mapping) or not selections:
            continue
        profile_id = unified_profile_id(selections)
        if profile_id not in unified_profiles:
            settings: dict[str, Any] = {}
            names: list[str] = []
            functions: set[str] = set()
            for profile_type in PROFILE_TYPES:
                legacy_id = selections.get(profile_type)
                if not legacy_id:
                    continue
                legacy_profile = profiles.get(profile_type, {}).get(legacy_id, {})
                if not isinstance(legacy_profile, Mapping):
                    continue
                names.append(str(legacy_profile.get(CONF_PROFILE_NAME, legacy_id)))
                legacy_settings = legacy_profile.get(CONF_PROFILE_SETTINGS, {})
                if isinstance(legacy_settings, Mapping):
                    settings.update(deepcopy(dict(legacy_settings)))
                legacy_functions = legacy_profile.get(CONF_PROFILE_FUNCTIONS)
                if isinstance(legacy_functions, (list, tuple, set, frozenset)):
                    functions.update(str(function) for function in legacy_functions)
                functions.update(configured_functions_from_profile(legacy_profile))
            name = " / ".join(dict.fromkeys(name for name in names if name))
            unified_profiles[profile_id] = {
                CONF_PROFILE_ID: profile_id,
                CONF_PROFILE_NAME: name or str(room.get(CONF_NAME, profile_id)),
                CONF_PROFILE_SETTINGS: settings,
                CONF_PROFILE_FUNCTIONS: sorted(functions),
            }
            if not unified_profiles[profile_id][CONF_PROFILE_FUNCTIONS]:
                unified_profiles[profile_id][CONF_PROFILE_FUNCTIONS] = sorted(
                    configured_functions_from_profile(unified_profiles[profile_id])
                )
        room["profile_id"] = profile_id
        room.setdefault(
            CONF_PROFILE_FUNCTIONS,
            unified_profiles[profile_id].get(CONF_PROFILE_FUNCTIONS, []),
        )
        room.pop(CONF_PROFILE_SELECTIONS, None)
    canonical[CONF_PROFILES] = unified_profiles
    canonical[CONF_CONFIG_VERSION] = CONFIG_MODEL_VERSION
    return canonical


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
        model = unify_profile_model(existing)
        canonical[CONF_CONFIG_MODEL] = model
        return canonical, dict(options)

    flat = {**data, **options}
    room_id = str(flat.get(CONF_ROOM_ID) or entry_id)
    name = str(flat.get(CONF_NAME) or DEFAULT_NAME)
    model = unify_profile_model(normalize_legacy_config(data, options, room_id=room_id))
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

    hub_model: dict[str, Any] | None = None
    for entry_id, (data, options) in entries.items():
        migrated, _ = migrate_entry_payload(data, options, entry_id=entry_id)
        incoming = migrated[CONF_CONFIG_MODEL]
        if hub_model is None:
            hub_model = deepcopy(incoming)
            continue
        for layer in (CONF_GLOBAL_SOURCES, CONF_GLOBAL_DEFAULTS):
            target = hub_model[CONF_GLOBAL][layer]
            for key, value in incoming.get(CONF_GLOBAL, {}).get(layer, {}).items():
                target.setdefault(key, deepcopy(value))
        for profile_id, profile in incoming.get(CONF_PROFILES, {}).items():
            new_id = profile_id
            if new_id in hub_model[CONF_PROFILES] and hub_model[CONF_PROFILES][new_id] != profile:
                suffix = entry_id.replace("-", "")[:8] or "imported"
                new_id = f"{profile_id}-{suffix}"
                counter = 2
                while new_id in hub_model[CONF_PROFILES]:
                    new_id = f"{profile_id}-{suffix}-{counter}"
                    counter += 1
            copied_profile = deepcopy(profile)
            copied_profile[CONF_PROFILE_ID] = new_id
            hub_model[CONF_PROFILES].setdefault(new_id, copied_profile)
            for room in incoming.get(CONF_ROOMS, {}).values():
                if room.get("profile_id") == profile_id:
                    room["profile_id"] = new_id
        for room_id, room in incoming.get(CONF_ROOMS, {}).items():
            new_room_id = room_id
            if new_room_id in hub_model[CONF_ROOMS]:
                suffix = entry_id.replace("-", "")[:8] or "imported"
                new_room_id = f"{room_id}-{suffix}"
            copied_room = deepcopy(room)
            copied_room[CONF_ROOM_ID] = new_room_id
            hub_model[CONF_ROOMS][new_room_id] = copied_room
    if hub_model is None:
        hub_model = ConfigProfileModel({}).data
    return unify_profile_model(hub_model)
