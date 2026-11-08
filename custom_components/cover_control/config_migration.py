"""Configuration migration to the fixed-group model."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from .config_groups import ConfigGroupModel
from .config_resolver import GLOBAL_SOURCE_KEYS, GROUP_BLOCKED_KEYS, GROUP_SECTION_KEYS
from .const import *  # noqa: F403

LEGACY_PROFILES = "profiles"
LEGACY_PROFILE_ID = "profile_id"
LEGACY_PROFILE_FUNCTIONS = "profile_functions"
LEGACY_PROFILE_SETTINGS = "settings"
LEGACY_PROFILE_NAME = "name"
LEGACY_PROFILE_TYPES = ("time", "shading", "behavior")
LEGACY_SUN_MODE = "sun_elevation_mode"
LEGACY_DYNAMIC_SUN_KEYS = {
    "sun_elevation_dynamic_open_sensor",
    "sun_elevation_dynamic_close_sensor",
    "use_sun_elevation_dynamic_open_sensor",
    "use_sun_elevation_dynamic_close_sensor",
    "sun_elevation_open_offset",
    "sun_elevation_close_offset",
    "sun_time_duration",
    "brightness_sun_operator",
}


def migrate_sun_settings(settings: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    """Convert legacy sun coupling to explicit shuttercontrol-style modes."""

    result = deepcopy(dict(settings))
    legacy_mode = str(result.pop(LEGACY_SUN_MODE, "") or "").lower()
    warned = legacy_mode in {"dynamic", "hybrid"}
    if legacy_mode:
        result[CONF_OPEN_MODE] = MODE_ELEVATION  # noqa: F405
        result[CONF_CLOSE_MODE] = MODE_ELEVATION  # noqa: F405
    for key in LEGACY_DYNAMIC_SUN_KEYS:
        result.pop(key, None)
    return result, warned


def is_native_parent_entry(data: Mapping[str, Any]) -> bool:
    return CONF_GLOBAL in data and CONF_CONFIG_MODEL not in data  # noqa: F405


def has_legacy_config_model(data: Mapping[str, Any]) -> bool:
    return CONF_CONFIG_MODEL in data  # noqa: F405


def classify_legacy_profile(name: str, room_names: Iterable[str] = ()) -> str:
    """Classify legacy profile and room names into one fixed group."""

    text = " ".join((name, *room_names)).casefold()
    if any(word in text for word in ("kind", "children", "kids")):
        return GROUP_CHILDREN  # noqa: F405
    if any(word in text for word in ("schlaf", "sleep", "bedroom")):
        return GROUP_SLEEP  # noqa: F405
    return GROUP_LIVING  # noqa: F405


def _legacy_settings(profile: Mapping[str, Any]) -> dict[str, Any]:
    settings = profile.get(LEGACY_PROFILE_SETTINGS, profile)
    result = (
        {key: deepcopy(value) for key, value in settings.items() if key not in GROUP_BLOCKED_KEYS}
        if isinstance(settings, Mapping)
        else {}
    )
    for section in GROUP_SECTION_KEYS:
        block = profile.get(section)
        if isinstance(block, Mapping):
            result.update(
                (key, deepcopy(value))
                for key, value in block.items()
                if key not in GROUP_BLOCKED_KEYS
            )
    return result


def migrate_profile_model(model: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Convert arbitrary legacy profiles and rooms to three fixed groups."""

    if CONF_GROUPS in model:  # noqa: F405
        canonical = ConfigGroupModel(model).data
        warnings: list[str] = []
        for group in GROUPS:  # noqa: F405
            canonical[CONF_GROUPS][group], warned = migrate_sun_settings(  # noqa: F405
                canonical[CONF_GROUPS][group]
            )
            if warned:
                warnings.append(
                    f"{group}: dynamic sun elevation was replaced by fixed elevation"
                )
        canonical[CONF_CONFIG_VERSION] = CONFIG_MODEL_VERSION  # noqa: F405
        return canonical, warnings
    result = deepcopy(dict(model))
    profiles = result.pop(LEGACY_PROFILES, {})
    rooms = result.setdefault(CONF_ROOMS, {})  # noqa: F405
    flat_profiles: dict[str, Mapping[str, Any]] = {}
    if isinstance(profiles, Mapping):
        for profile_id, profile in profiles.items():
            if profile_id in LEGACY_PROFILE_TYPES and isinstance(profile, Mapping):
                flat_profiles.update(
                    (str(nested_id), nested)
                    for nested_id, nested in profile.items()
                    if isinstance(nested, Mapping)
                )
            elif isinstance(profile, Mapping):
                flat_profiles[str(profile_id)] = profile

    usage: Counter[tuple[str, str]] = Counter()
    for room_id, room in rooms.items():
        if not isinstance(room, dict):
            continue
        profile_id = str(room.get(LEGACY_PROFILE_ID, ""))
        profile = flat_profiles.get(profile_id, {})
        group = classify_legacy_profile(
            str(profile.get(LEGACY_PROFILE_NAME, profile_id)),
            (str(room.get(CONF_NAME, room_id)),),  # noqa: F405
        )
        if profile_id:
            usage[(group, profile_id)] += 1
        legacy_settings = profile.get(LEGACY_PROFILE_SETTINGS, {})
        if isinstance(legacy_settings, Mapping):
            room_settings = room.setdefault(CONF_ROOM_SETTINGS, {})  # noqa: F405
            for key, value in legacy_settings.items():
                if key in GROUP_BLOCKED_KEYS and isinstance(room_settings, dict):
                    room_settings.setdefault(key, deepcopy(value))
        room[CONF_GROUP] = group  # noqa: F405
        room.pop(LEGACY_PROFILE_ID, None)
        room.pop(LEGACY_PROFILE_FUNCTIONS, None)
        room.pop(LEGACY_PROFILES, None)

    groups: dict[str, dict[str, Any]] = {group: {} for group in GROUPS}  # noqa: F405
    warnings: list[str] = []
    for group in GROUPS:  # noqa: F405
        candidates = sorted(
            ((count, profile_id) for (target, profile_id), count in usage.items() if target == group),
            key=lambda item: (-item[0], item[1]),
        )
        if not candidates:
            candidates = sorted(
                (0, profile_id)
                for profile_id, profile in flat_profiles.items()
                if classify_legacy_profile(str(profile.get(LEGACY_PROFILE_NAME, profile_id))) == group
            )
        if candidates:
            selected_id = candidates[0][1]
            groups[group], warned = migrate_sun_settings(
                _legacy_settings(flat_profiles[selected_id])
            )
            if warned:
                warnings.append(
                    f"{group}: dynamic sun elevation was replaced by fixed elevation"
                )
            if len(candidates) > 1:
                warnings.append(
                    f"{group}: selected legacy profile {selected_id}; ignored "
                    + ", ".join(profile_id for _, profile_id in candidates[1:])
                )
    result[CONF_GROUPS] = groups  # noqa: F405
    result[CONF_CONFIG_VERSION] = CONFIG_MODEL_VERSION  # noqa: F405
    return ConfigGroupModel(result).data, warnings


def migrate_legacy_model(model: Mapping[str, Any]) -> dict[str, Any]:
    """Compatibility entry point used only while migrating old entries."""

    return migrate_profile_model(model)[0]


def normalize_legacy_config(
    data: Mapping[str, Any], options: Mapping[str, Any], *, room_id: str
) -> dict[str, Any]:
    """Convert one flat legacy room into the fixed-group model."""

    flat = {**data, **options}
    room_name = str(flat.get(CONF_ROOM) or flat.get(CONF_NAME) or room_id)  # noqa: F405
    global_sources = {key: flat[key] for key in GLOBAL_SOURCE_KEYS if key in flat}
    group_keys = set().union(*GROUP_SECTION_KEYS.values())
    group_settings = {
        key: deepcopy(value)
        for key, value in flat.items()
        if key in group_keys and key not in GROUP_BLOCKED_KEYS
    }
    group_settings, _warned = migrate_sun_settings(group_settings)
    room_settings = {
        key: deepcopy(value)
        for key, value in flat.items()
        if key not in global_sources and key not in group_settings
    }
    group = classify_legacy_profile(room_name)
    groups = {item: {} for item in GROUPS}  # noqa: F405
    groups[group] = group_settings
    return {
        CONF_CONFIG_VERSION: CONFIG_MODEL_VERSION,  # noqa: F405
        CONF_GLOBAL: {CONF_GLOBAL_SOURCES: global_sources, CONF_GLOBAL_DEFAULTS: {}},  # noqa: F405
        CONF_GROUPS: groups,  # noqa: F405
        CONF_ROOMS: {  # noqa: F405
            room_id: {
                CONF_ROOM_ID: room_id,  # noqa: F405
                CONF_NAME: room_name,  # noqa: F405
                CONF_GROUP: group,  # noqa: F405
                CONF_ROOM_SETTINGS: room_settings,  # noqa: F405
                CONF_SOURCE_OVERRIDES: {},  # noqa: F405
                CONF_ROOM_OVERRIDES: {},  # noqa: F405
            }
        },
    }


def migrate_entry_payload(
    data: Mapping[str, Any], options: Mapping[str, Any], *, entry_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    existing = data.get(CONF_CONFIG_MODEL)  # noqa: F405
    model = (
        migrate_profile_model(existing)[0]
        if isinstance(existing, Mapping)
        else normalize_legacy_config(data, options, room_id=str(data.get(CONF_ROOM_ID) or entry_id))  # noqa: F405
    )
    return {
        CONF_ROOM_ID: str(data.get(CONF_ROOM_ID) or entry_id),  # noqa: F405
        CONF_NAME: str(data.get(CONF_NAME) or DEFAULT_NAME),  # noqa: F405
        CONF_CONFIG_MODEL: model,  # noqa: F405
    }, {}


def legacy_entry_model(
    data: Mapping[str, Any], options: Mapping[str, Any], *, entry_id: str
) -> dict[str, Any]:
    return migrate_entry_payload(data, options, entry_id=entry_id)[0][CONF_CONFIG_MODEL]  # noqa: F405


def migrate_entry_collection(
    entries: Mapping[str, tuple[Mapping[str, Any], Mapping[str, Any]]]
) -> dict[str, Any]:
    """Consolidate legacy room entries into one fixed-group model."""

    combined = ConfigGroupModel({}).data
    for entry_id, (data, options) in entries.items():
        incoming = legacy_entry_model(data, options, entry_id=entry_id)
        combined[CONF_GLOBAL][CONF_GLOBAL_SOURCES].update(  # noqa: F405
            incoming.get(CONF_GLOBAL, {}).get(CONF_GLOBAL_SOURCES, {})  # noqa: F405
        )
        for group in GROUPS:  # noqa: F405
            combined[CONF_GROUPS][group].update(incoming.get(CONF_GROUPS, {}).get(group, {}))  # noqa: F405
        combined[CONF_ROOMS].update(incoming.get(CONF_ROOMS, {}))  # noqa: F405
    combined[CONF_CONFIG_VERSION] = CONFIG_MODEL_VERSION  # noqa: F405
    return combined
