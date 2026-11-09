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
LEGACY_SHADING_KEYS = {
    "shading_conditions_start_and", "shading_conditions_start_or",
    "shading_conditions_end_and", "shading_conditions_end_or",
    "shading_forecast_sensor", "use_shading_forecast_sensor",
    "shading_forecast_type", "shading_forecast_temp_sensor",
    "shading_forecast_temp", "shading_forecast_temp_hysteresis",
    "shading_weather_conditions", "shading_config",
    "shading_independent_temp", "shading_independent_holds_end",
    "shading_waitingtime_start",
    "shading_start_max_duration", "shading_end_max_duration",
    "shading_end_immediate_by_sun_position", "shading_temperatur_sensor1",
    "shading_temperatur_sensor2", "shading_min_temperatur1",
    "shading_min_temperatur2", "shading_temperature_hysteresis1",
    "shading_temperature_hysteresis2", "shading_brightness_start",
    "shading_brightness_end",
}
LEGACY_CCA_KEYS = {
    "additional_conditions_enabled",
    "additional_condition_global",
    "additional_condition_open",
    "additional_condition_close",
    "additional_condition_ventilate",
    "additional_condition_ventilate_end",
    "additional_condition_shading",
    "additional_condition_shading_tilt",
    "additional_condition_shading_end",
    "prevent_higher_position_closing",
    "prevent_lowering_when_closing_if_shaded",
    "prevent_shading_end_if_closed",
    "prevent_opening_after_ventilation_end",
    "prevent_opening_multiple_times",
    "prevent_closing_multiple_times",
    "prevent_shading_multiple_times",
    "prevent_default_cover_actions",
    "ventilation_allow_higher_position",
    "ventilation_use_after_shading",
    "ventilation_start_no_delay",
    "ventilation_keep_open_on_full_to_tilt",
    "shading_over_ventilation",
    "lockout_tilt_close",
    "lockout_tilt_shading_start",
    "lockout_tilt_shading_end",
}
LEGACY_KEEP_SUN_PROTECTION = "prevent_opening_after_shading_end"
LEGACY_RUNTIME_OPTION_KEYS = {
    "force_open_entity",
    "force_close_entity",
    "force_ventilate_entity",
    "force_shading_entity",
    "force_pause_entity",
    "position_source",
    "custom_position_sensor",
    "recovery_mode",
    "drive_delay_random",
}


def cleanup_runtime_options(settings: Mapping[str, Any]) -> tuple[dict[str, Any], set[str]]:
    """Remove runtime options that no longer belong to the fixed model."""

    result = deepcopy(dict(settings))
    warnings: set[str] = set()
    if result.get("position_source") == "custom_sensor" or result.get(
        "custom_position_sensor"
    ):
        warnings.add("custom position source was removed")
    if result.get("recovery_mode") in {"never", "always"}:
        warnings.add("configurable recovery mode was removed")
    for key in LEGACY_RUNTIME_OPTION_KEYS:
        result.pop(key, None)
    return result, warnings


def cleanup_runtime_model(model: dict[str, Any], warnings: list[str]) -> None:
    """Remove retired runtime options from every persistent model layer."""

    found: set[str] = set()
    global_config = model.get(CONF_GLOBAL, {})  # noqa: F405
    if isinstance(global_config, dict):
        for section in (CONF_GLOBAL_SOURCES, CONF_GLOBAL_DEFAULTS):  # noqa: F405
            values = global_config.get(section)
            if isinstance(values, Mapping):
                global_config[section], section_warnings = cleanup_runtime_options(values)
                found.update(section_warnings)
    for settings in model.get(CONF_GROUPS, {}).values():  # noqa: F405
        if isinstance(settings, dict):
            cleaned, section_warnings = cleanup_runtime_options(settings)
            settings.clear()
            settings.update(cleaned)
            found.update(section_warnings)
    for room in model.get(CONF_ROOMS, {}).values():  # noqa: F405
        if not isinstance(room, dict):
            continue
        for section in (CONF_ROOM_SETTINGS, CONF_SOURCE_OVERRIDES):  # noqa: F405
            values = room.get(section)
            if isinstance(values, Mapping):
                room[section], section_warnings = cleanup_runtime_options(values)
                found.update(section_warnings)
        overrides = room.get(CONF_ROOM_OVERRIDES)  # noqa: F405
        if isinstance(overrides, Mapping):
            for override_id, values in tuple(overrides.items()):
                if isinstance(values, Mapping):
                    overrides[override_id], section_warnings = cleanup_runtime_options(values)
                    found.update(section_warnings)
    warnings.extend(sorted(found))


def cleanup_cca_settings(settings: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    """Remove legacy CCA overrides and preserve KeepSunProtect semantics."""

    result = deepcopy(dict(settings))
    changed_behavior = any(bool(result.get(key)) for key in LEGACY_CCA_KEYS)
    if LEGACY_KEEP_SUN_PROTECTION in result:
        result.setdefault(
            CONF_KEEP_SUN_PROTECTION,  # noqa: F405
            bool(result[LEGACY_KEEP_SUN_PROTECTION]),
        )
        result.pop(LEGACY_KEEP_SUN_PROTECTION, None)
    for key in LEGACY_CCA_KEYS:
        result.pop(key, None)
    return result, changed_behavior


def cleanup_cca_model(model: dict[str, Any], warnings: list[str]) -> None:
    """Remove CCA-only settings from every persistent model layer."""

    changed_behavior = False
    global_config = model.get(CONF_GLOBAL, {})  # noqa: F405
    if isinstance(global_config, dict):
        for section in (CONF_GLOBAL_SOURCES, CONF_GLOBAL_DEFAULTS):  # noqa: F405
            values = global_config.get(section)
            if isinstance(values, Mapping):
                global_config[section], changed = cleanup_cca_settings(values)
                changed_behavior |= changed
    for settings in model.get(CONF_GROUPS, {}).values():  # noqa: F405
        if isinstance(settings, dict):
            cleaned, changed = cleanup_cca_settings(settings)
            settings.clear()
            settings.update(cleaned)
            changed_behavior |= changed
    for room in model.get(CONF_ROOMS, {}).values():  # noqa: F405
        if not isinstance(room, dict):
            continue
        for section in (
            CONF_ROOM_SETTINGS,  # noqa: F405
            CONF_SOURCE_OVERRIDES,  # noqa: F405
        ):
            values = room.get(section)
            if isinstance(values, Mapping):
                room[section], changed = cleanup_cca_settings(values)
                changed_behavior |= changed
        overrides = room.get(CONF_ROOM_OVERRIDES)  # noqa: F405
        if isinstance(overrides, Mapping):
            cleaned_overrides: dict[str, Any] = {}
            for override_id, values in overrides.items():
                if isinstance(values, Mapping):
                    cleaned_overrides[str(override_id)], changed = (
                        cleanup_cca_settings(values)
                    )
                    changed_behavior |= changed
                else:
                    cleaned_overrides[str(override_id)] = deepcopy(values)
            room[CONF_ROOM_OVERRIDES] = cleaned_overrides  # noqa: F405
    if changed_behavior:
        warnings.append("CCA behavior overrides were removed")


def _percent_hysteresis(threshold: float, end_limit: float) -> float:
    if threshold <= 0:
        return 0.0
    return max(0.0, min(100.0, (1 - end_limit / threshold) * 100))


def _legacy_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def migrate_shading_settings(settings: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    """Map the legacy free shading rules to one fixed mode."""

    result = deepcopy(dict(settings))
    if CONF_SHADING_MODE in result:  # noqa: F405
        for key in LEGACY_SHADING_KEYS | {"shading_azimuth_start", "shading_azimuth_end"}:
            result.pop(key, None)
        return result, False
    start_and = set(result.get("shading_conditions_start_and") or [])
    start_or = set(result.get("shading_conditions_start_or") or [])
    direction_conditions = {"cond_azimuth", "cond_elevation"} & start_and
    direction = bool(direction_conditions)
    inside = "cond_temp1" in start_and
    outside = "cond_temp2" in start_and
    complex_rules = bool(
        start_or
        or len(direction_conditions) == 1
        or result.get("shading_conditions_end_and")
        or result.get("shading_conditions_end_or")
        or {"cond_forecast_temp", "cond_forecast_weather"} & start_and
        or result.get("shading_forecast_sensor")
        or result.get("shading_forecast_temp_sensor")
        or result.get("shading_weather_conditions")
        or result.get("shading_config")
        or result.get("shading_independent_temp") is not None
    )
    if direction and inside and outside:
        mode = SHADING_MODE_INSIDE_OUTSIDE_DIRECTION  # noqa: F405
    elif direction and outside:
        mode = SHADING_MODE_OUTSIDE_DIRECTION  # noqa: F405
    elif direction and not inside:
        mode = SHADING_MODE_DIRECTION  # noqa: F405
    elif inside and outside:
        mode = SHADING_MODE_INSIDE_OUTSIDE  # noqa: F405
    elif outside:
        mode = SHADING_MODE_OUTSIDE  # noqa: F405
    elif inside:
        mode = SHADING_MODE_INSIDE  # noqa: F405
    elif result.get(CONF_AUTO_SHADING, False):  # noqa: F405
        mode = SHADING_MODE_DIRECTION  # noqa: F405
        complex_rules = True
    else:
        mode = SHADING_MODE_OFF  # noqa: F405
    if direction and inside and not outside:
        mode = SHADING_MODE_INSIDE_OUTSIDE_DIRECTION  # noqa: F405
        complex_rules = True
    result[CONF_SHADING_MODE] = mode  # noqa: F405

    start = _legacy_float(result.get("shading_azimuth_start"), 95)
    end = _legacy_float(result.get("shading_azimuth_end"), 265)
    span = (end - start) % 360
    result[CONF_SHADING_DIRECTION] = (start + span / 2) % 360  # noqa: F405
    result[CONF_SHADING_DIRECTION_RANGE] = span / 2  # noqa: F405

    for old_threshold, old_hysteresis, new_threshold, new_hysteresis, default in (
        ("shading_min_temperatur1", "shading_temperature_hysteresis1", CONF_SHADING_INSIDE_TEMPERATURE_THRESHOLD, CONF_SHADING_INSIDE_TEMPERATURE_HYSTERESIS, DEFAULT_SHADING_INSIDE_TEMPERATURE_THRESHOLD),  # noqa: F405
        ("shading_min_temperatur2", "shading_temperature_hysteresis2", CONF_SHADING_OUTSIDE_TEMPERATURE_THRESHOLD, CONF_SHADING_OUTSIDE_TEMPERATURE_HYSTERESIS, DEFAULT_SHADING_OUTSIDE_TEMPERATURE_THRESHOLD),  # noqa: F405
    ):
        base = _legacy_float(result.get(old_threshold), default)
        absolute = _legacy_float(result.get(old_hysteresis), 0)
        threshold = base + absolute
        result[new_threshold] = threshold
        result[new_hysteresis] = _percent_hysteresis(threshold, base - absolute)

    bright_start = _legacy_float(result.get("shading_brightness_start"), DEFAULT_SHADING_BRIGHTNESS_THRESHOLD)  # noqa: F405
    bright_end = _legacy_float(result.get("shading_brightness_end"), bright_start)
    bright_absolute = _legacy_float(result.get("shading_sun_brightness_hysteresis"), 0)
    bright_threshold = bright_start + bright_absolute
    result[CONF_SHADING_BRIGHTNESS_THRESHOLD] = bright_threshold  # noqa: F405
    result[CONF_SHADING_BRIGHTNESS_HYSTERESIS] = _percent_hysteresis(  # noqa: F405
        bright_threshold, bright_end - bright_absolute
    )
    for key in LEGACY_SHADING_KEYS | {"shading_azimuth_start", "shading_azimuth_end"}:
        result.pop(key, None)
    return result, complex_rules


def migrate_room_shading_geometry(model: dict[str, Any], warnings: list[str]) -> None:
    """Move legacy room azimuth ranges into their assigned fixed group."""

    selected: dict[str, tuple[float, float]] = {}
    for room_id, room in model.get(CONF_ROOMS, {}).items():  # noqa: F405
        if not isinstance(room, dict):
            continue
        settings = room.get(CONF_ROOM_SETTINGS, {})  # noqa: F405
        if not isinstance(settings, dict):
            continue
        start = settings.pop("shading_azimuth_start", None)
        end = settings.pop("shading_azimuth_end", None)
        if start is None and end is None:
            continue
        start_value = _legacy_float(start, 95)
        end_value = _legacy_float(end, 265)
        span = (end_value - start_value) % 360
        geometry = ((start_value + span / 2) % 360, span / 2)
        group = str(room.get(CONF_GROUP, GROUP_LIVING))  # noqa: F405
        if group in selected and selected[group] != geometry:
            warnings.append(
                f"{group}: conflicting room directions were simplified using the first room; check {room_id}"
            )
            continue
        selected[group] = geometry
        group_settings = model[CONF_GROUPS][group]  # noqa: F405
        group_settings[CONF_SHADING_DIRECTION] = geometry[0]  # noqa: F405
        group_settings[CONF_SHADING_DIRECTION_RANGE] = geometry[1]  # noqa: F405


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

    source = deepcopy(dict(model))
    warnings: list[str] = []
    cleanup_runtime_model(source, warnings)
    if CONF_GROUPS in source:  # noqa: F405
        canonical = ConfigGroupModel(source).data
        for group in GROUPS:  # noqa: F405
            canonical[CONF_GROUPS][group], warned = migrate_sun_settings(  # noqa: F405
                canonical[CONF_GROUPS][group]
            )
            if warned:
                warnings.append(
                    f"{group}: dynamic sun elevation was replaced by fixed elevation"
                )
            canonical[CONF_GROUPS][group], shading_warned = migrate_shading_settings(  # noqa: F405
                canonical[CONF_GROUPS][group]
            )
            if shading_warned:
                warnings.append(
                    f"{group}: complex shading rules were simplified; forecast and OR conditions were removed"
                )
        migrate_room_shading_geometry(canonical, warnings)
        cleanup_cca_model(canonical, warnings)
        cleanup_runtime_model(canonical, warnings)
        canonical[CONF_CONFIG_VERSION] = CONFIG_MODEL_VERSION  # noqa: F405
        return canonical, warnings
    result = source
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
            groups[group], shading_warned = migrate_shading_settings(groups[group])
            if warned:
                warnings.append(
                    f"{group}: dynamic sun elevation was replaced by fixed elevation"
                )
            if shading_warned:
                warnings.append(
                    f"{group}: complex shading rules were simplified; forecast and OR conditions were removed"
                )
            if len(candidates) > 1:
                warnings.append(
                    f"{group}: selected legacy profile {selected_id}; ignored "
                    + ", ".join(profile_id for _, profile_id in candidates[1:])
                )
    result[CONF_GROUPS] = groups  # noqa: F405
    migrate_room_shading_geometry(result, warnings)
    cleanup_cca_model(result, warnings)
    cleanup_runtime_model(result, warnings)
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
    flat, _cca_changed = cleanup_cca_settings(flat)
    flat, _runtime_warnings = cleanup_runtime_options(flat)
    room_name = str(flat.get(CONF_ROOM) or flat.get(CONF_NAME) or room_id)  # noqa: F405
    global_sources = {key: flat[key] for key in GLOBAL_SOURCE_KEYS if key in flat}
    group_keys = set().union(*GROUP_SECTION_KEYS.values())
    group_settings = {
        key: deepcopy(value)
        for key, value in flat.items()
        if key in group_keys and key not in GROUP_BLOCKED_KEYS
    }
    group_settings, _warned = migrate_sun_settings(group_settings)
    group_settings, _shading_warned = migrate_shading_settings(group_settings)
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
