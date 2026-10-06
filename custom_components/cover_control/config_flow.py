"""Config and reconfigure flow for Cover Control."""
from __future__ import annotations

import logging
from types import MappingProxyType
from datetime import date, datetime, time, timedelta
from collections import OrderedDict
from copy import deepcopy
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigSubentry, ConfigSubentryFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult, section
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .config_profiles import ConfigProfileModel
from .config_profile_schema import (
    PROFILE_CAPABILITY_KEYS,
    build_profile_schema,
    capability_keys,
    extract_sparse_settings,
    flatten_section_input,
)
from .config_resolver import (
    GLOBAL_SOURCE_KEYS,
    PROFILE_KEYS,
    ROOM_SOURCE_OVERRIDE_KEYS,
    configured_functions_from_profile,
    effective_profile,
    resolve_config_model,
    system_defaults,
)
from .config_subentries import model_to_native_payloads
from .const import (
    BRIGHTNESS_SUN_OPERATOR_AND,
    BRIGHTNESS_SUN_OPERATOR_OR,
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_DOWN,
    CONF_AUTO_SHADING,
    CONF_AUTO_SUN,
    CONF_AUTO_TIME,
    CONF_AUTO_UP,
    CONF_AUTO_VENTILATE,
    CONF_ADDITIONAL_CONDITION_CLOSE,
    CONF_ADDITIONAL_CONDITION_GLOBAL,
    CONF_ADDITIONAL_CONDITION_OPEN,
    CONF_ADDITIONAL_CONDITION_SHADING,
    CONF_ADDITIONAL_CONDITION_SHADING_END,
    CONF_ADDITIONAL_CONDITION_SHADING_TILT,
    CONF_ADDITIONAL_CONDITION_VENTILATE,
    CONF_ADDITIONAL_CONDITION_VENTILATE_END,
    CONF_ADDITIONAL_CONDITIONS_ENABLED,
    CONF_BRIGHTNESS_SUN_OPERATOR,
    CONF_COLD_PROTECTION_FORECAST_SENSOR,
    CONF_COLD_PROTECTION_THRESHOLD,
    CONF_GLOBAL,
    CONF_GLOBAL_DEFAULTS,
    CONF_GLOBAL_SOURCES,
    CONF_CALENDAR_CLOSE_TITLE,
    CONF_CALENDAR_ENTITY,
    CONF_CALENDAR_OPEN_TITLE,
    CONF_BRIGHTNESS_CLOSE_BELOW,
    CONF_BRIGHTNESS_HYSTERESIS,
    CONF_BRIGHTNESS_OPEN_ABOVE,
    CONF_BRIGHTNESS_SENSOR,
    CONF_BRIGHTNESS_TIME_DURATION,
    CONF_CONTACT_STATUS_DELAY,
    CONF_CONTACT_TRIGGER_DELAY,
    CONF_CLOSE_POSITION,
    CONF_CLOSE_TILT_POSITION,
    CONF_COVER_TILT_WAIT_MODE,
    CONF_COVER_TILT_WAIT_TIMEOUT,
    CONF_CUSTOM_POSITION_SENSOR,
    CONF_COVERS,
    CONF_COVER_TYPE,
    CONF_COVER_TYPE_AWNING,
    CONF_COVER_TYPE_BLIND,
    CONF_DRIVE_TIME,
    CONF_ENABLE_CLEAR_MANUAL_OVERRIDE_BUTTON,
    CONF_ENABLE_LOGBOOK_COVER,
    CONF_ENABLE_RECALIBRATE_BUTTON,
    CONF_MANUAL_CONTROL,
    CONF_MANUAL_SCHEDULE_ADOPTION,
    CONF_LOCKOUT_POSITION,
    CONF_LOCKOUT_TILT_CLOSE,
    CONF_LOCKOUT_TILT_SHADING_END,
    CONF_LOCKOUT_TILT_SHADING_START,
    CONF_MANUAL_OVERRIDE_MINUTES,
    CONF_MANUAL_OVERRIDE_BLOCK_CLOSE,
    CONF_MANUAL_OVERRIDE_BLOCK_OPEN,
    CONF_MANUAL_OVERRIDE_BLOCK_SHADING,
    CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE,
    CONF_MANUAL_OVERRIDE_RESET_MODE,
    CONF_MANUAL_OVERRIDE_RESET_TIME,
    CONF_NAME,
    CONF_PROFILE_FUNCTIONS,
    CONF_PROFILE_ID,
    CONF_PROFILE_NAME,
    CONF_PROFILES,
    CONF_PROFILE_SETTINGS,
    CONF_OPEN_POSITION,
    CONF_ROOM_PROFILE_ID,
    CONF_OPEN_TILT_POSITION,
    CONF_ROOM,
    CONF_ROOMS,
    CONF_ROOM_OVERRIDES,
    CONF_ROOM_SETTINGS,
    CONF_SOURCE_OVERRIDES,
    CONF_PROFILE_SELECTIONS,
    CONF_ROOM_ID,
    CONF_POSITION_TOLERANCE,
    CONF_POSITION_SOURCE,
    CONF_POSITION_SOURCE_CURRENT_POSITION_ATTR,
    CONF_POSITION_SOURCE_CUSTOM_SENSOR,
    CONF_POSITION_SOURCE_POSITION_ATTR,
    CONF_PREVENT_CLOSING_MULTIPLE_TIMES,
    CONF_PREVENT_DEFAULT_COVER_ACTIONS,
    CONF_PREVENT_HIGHER_POSITION_CLOSING,
    CONF_PREVENT_LOWERING_WHEN_CLOSING_IF_SHADED,
    CONF_PREVENT_OPENING_AFTER_SHADING_END,
    CONF_PREVENT_OPENING_AFTER_VENTILATION_END,
    CONF_PREVENT_OPENING_MULTIPLE_TIMES,
    CONF_PREVENT_SHADING_END_IF_CLOSED,
    CONF_PREVENT_SHADING_MULTIPLE_TIMES,
    CONF_RESIDENT_SENSOR,
    CONF_RESIDENT_STATUS,
    CONF_RESIDENT_OPEN_ENABLED,
    CONF_RESIDENT_CLOSE_ENABLED,
    CONF_RESIDENT_ALLOW_SHADING,
    CONF_RESIDENT_ALLOW_OPEN,
    CONF_RESIDENT_ALLOW_VENTILATION,
    CONF_SHADING_FORECAST_SENSOR,
    CONF_SHADING_FORECAST_TEMP,
    CONF_SHADING_FORECAST_TEMP_HYSTERESIS,
    CONF_SHADING_FORECAST_TEMP_SENSOR,
    CONF_SHADING_FORECAST_TYPE,
    CONF_SHADING_INDEPENDENT_TEMP,
    CONF_SHADING_INDEPENDENT_HOLDS_END,
    CONF_SHADING_WEATHER_CONDITIONS,
    CONF_SHADING_BRIGHTNESS_HYSTERESIS,
    CONF_SHADING_BRIGHTNESS_END,
    CONF_SHADING_BRIGHTNESS_SENSOR,
    CONF_SHADING_BRIGHTNESS_START,
    CONF_SHADING_CONDITIONS_END_AND,
    CONF_SHADING_CONDITIONS_END_OR,
    CONF_SHADING_CONDITIONS_START_AND,
    CONF_SHADING_CONDITIONS_START_OR,
    CONF_SHADING_CONFIG,
    CONF_SHADING_END_IMMEDIATE_BY_SUN_POSITION,
    CONF_SHADING_END_MAX_DURATION,
    CONF_SHADING_MIN_TEMPERATURE_1,
    CONF_SHADING_MIN_TEMPERATURE_2,
    CONF_SHADING_POSITION,
    CONF_SHADING_POSITION_ALT,
    CONF_SHADING_POSITION_ALT_ENTITY,
    CONF_SHADING_TEMPERATURE_HYSTERESIS_1,
    CONF_SHADING_TEMPERATURE_HYSTERESIS_2,
    CONF_SHADING_TEMPERATURE_SENSOR_1,
    CONF_SHADING_TEMPERATURE_SENSOR_2,
    CONF_SHADING_TILT_ELEVATION_1,
    CONF_SHADING_TILT_ELEVATION_2,
    CONF_SHADING_TILT_ELEVATION_3,
    CONF_SHADING_TILT_POSITION,
    CONF_SHADING_TILT_POSITION_0,
    CONF_SHADING_TILT_POSITION_1,
    CONF_SHADING_TILT_POSITION_2,
    CONF_SHADING_TILT_POSITION_3,
    CONF_SHADING_START_MAX_DURATION,
    CONF_SHADING_WAITINGTIME_END,
    CONF_SHADING_WAITINGTIME_START,
    CONF_SUN_AZIMUTH_END,
    CONF_SUN_AZIMUTH_START,
    CONF_SUN_ELEVATION_CLOSE,
    CONF_SUN_ELEVATION_MODE,
    CONF_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR,
    CONF_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR,
    CONF_SUN_TIME_DURATION,
    CONF_SUN_ELEVATION_OPEN_OFFSET,
    CONF_SUN_ELEVATION_CLOSE_OFFSET,
    CONF_SUN_ELEVATION_MAX,
    CONF_SUN_ELEVATION_MIN,
    CONF_SUN_ELEVATION_OPEN,
    CONF_TEMPERATURE_FORECAST_THRESHOLD,
    CONF_TEMPERATURE_SENSOR_INDOOR,
    CONF_TEMPERATURE_SENSOR_OUTDOOR,
    CONF_TEMPERATURE_THRESHOLD,
    CONF_TIME_DOWN_EARLY_NON_WORKDAY,
    CONF_TIME_DOWN_EARLY_WORKDAY,
    CONF_TIME_DOWN_LATE_NON_WORKDAY,
    CONF_TIME_DOWN_LATE_WORKDAY,
    CONF_TIME_UP_EARLY_NON_WORKDAY,
    CONF_TIME_UP_EARLY_WORKDAY,
    CONF_TIME_UP_LATE_NON_WORKDAY,
    CONF_TIME_UP_LATE_WORKDAY,
    CONF_VENTILATION_ALLOW_HIGHER_POSITION,
    CONF_VENTILATION_DELAY_AFTER_CLOSE,
    CONF_VENTILATION_KEEP_OPEN_ON_FULL_TO_TILT,
    CONF_SHADING_OVER_VENTILATION,
    CONF_VENTILATION_START_NO_DELAY,
    CONF_VENTILATION_USE_AFTER_SHADING,
    CONF_VENTILATE_POSITION,
    CONF_VENTILATE_TILT_POSITION,
    CONF_WINDOW_SENSOR_FULL,
    CONF_WINDOW_SENSOR_TILT,
    CONF_WORKDAY_SENSOR,
    CONF_WORKDAY_TOMORROW_SENSOR,
    CONF_USE_WORKDAY_SENSOR,
    CONF_USE_RESIDENT_SENSOR,
    CONF_USE_BRIGHTNESS_SENSOR,
    CONF_USE_TEMPERATURE_SENSOR_INDOOR,
    CONF_USE_TEMPERATURE_SENSOR_OUTDOOR,
    CONF_USE_COLD_PROTECTION_FORECAST_SENSOR,
    CONF_USE_SHADING_FORECAST_SENSOR,
    CONF_USE_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR,
    CONF_USE_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR,
    COVER_TILT_WAIT_BEFORE_POSITION,
    COVER_TILT_WAIT_FIXED_DELAY,
    COVER_TILT_WAIT_IDLE,
    DEFAULT_BRIGHTNESS_SUN_OPERATOR,
    DEFAULT_CONTACT_SETTINGS,
    DEFAULT_AUTOMATION_FLAGS,
    DEFAULT_BEHAVIOR_SETTINGS,
    DEFAULT_BUTTON_SETTINGS,
    DEFAULT_BRIGHTNESS_CLOSE,
    DEFAULT_BRIGHTNESS_HYSTERESIS,
    DEFAULT_BRIGHTNESS_OPEN,
    DEFAULT_BRIGHTNESS_TIME_DURATION,
    DEFAULT_COLD_PROTECTION_THRESHOLD,
    DEFAULT_COVER_TILT_WAIT_MODE,
    DEFAULT_COVER_TILT_WAIT_TIMEOUT,
    DEFAULT_DRIVE_TIME,
    DEFAULT_MANUAL_OVERRIDE_MINUTES,
    DEFAULT_MANUAL_OVERRIDE_FLAGS,
    DEFAULT_MANUAL_OVERRIDE_RESET_TIME,
    DEFAULT_MASTER_FLAGS,
    DEFAULT_NAME,
    DEFAULT_POSITION_SETTINGS,
    DEFAULT_SHADING_AZIMUTH_END,
    DEFAULT_SHADING_AZIMUTH_START,
    DEFAULT_SHADING_BRIGHTNESS_END,
    DEFAULT_SHADING_BRIGHTNESS_HYSTERESIS,
    DEFAULT_SHADING_BRIGHTNESS_START,
    DEFAULT_SHADING_CONDITION_SETTINGS,
    DEFAULT_SHADING_CONDITIONS_END_AND,
    DEFAULT_SHADING_CONDITIONS_END_OR,
    DEFAULT_SHADING_CONDITIONS_START_AND,
    DEFAULT_SHADING_CONDITIONS_START_OR,
    DEFAULT_SHADING_END_MAX_DURATION,
    DEFAULT_SHADING_FORECAST_TYPE,
    DEFAULT_SHADING_FORECAST_TEMP_HYSTERESIS,
    DEFAULT_SHADING_INDEPENDENT_TEMP,
    DEFAULT_SHADING_ELEVATION_MAX,
    DEFAULT_SHADING_ELEVATION_MIN,
    DEFAULT_SHADING_MIN_TEMPERATURE_1,
    DEFAULT_SHADING_MIN_TEMPERATURE_2,
    DEFAULT_SHADING_START_MAX_DURATION,
    DEFAULT_SHADING_TEMPERATURE_HYSTERESIS_1,
    DEFAULT_SHADING_TEMPERATURE_HYSTERESIS_2,
    DEFAULT_SHADING_TILT_ELEVATION_1,
    DEFAULT_SHADING_TILT_ELEVATION_2,
    DEFAULT_SHADING_TILT_ELEVATION_3,
    DEFAULT_SHADING_TILT_POSITION_0,
    DEFAULT_SHADING_TILT_POSITION_1,
    DEFAULT_SHADING_TILT_POSITION_2,
    DEFAULT_SHADING_TILT_POSITION_3,
    DEFAULT_SHADING_TIMING_SETTINGS,
    DEFAULT_SHADING_WAITINGTIME_END,
    DEFAULT_SHADING_WAITINGTIME_START,
    DEFAULT_SUN_ELEVATION_CLOSE,
    DEFAULT_SUN_ELEVATION_OPEN,
    DEFAULT_SUN_ELEVATION_MODE,
    DEFAULT_SUN_ELEVATION_OPEN_OFFSET,
    DEFAULT_SUN_ELEVATION_CLOSE_OFFSET,
    DEFAULT_SUN_TIME_DURATION,
    DEFAULT_TIME_SETTINGS,
    DEFAULT_TEMPERATURE_FORECAST_THRESHOLD,
    DEFAULT_TEMPERATURE_THRESHOLD,
    DEFAULT_CONTACT_TRIGGER_DELAY,
    DEFAULT_CONTACT_STATUS_DELAY,
    DEFAULT_VENTILATION_DELAY_AFTER_CLOSE,
    DOMAIN,
    PROFILE_TYPE_BEHAVIOR,
    PROFILE_TYPE_SHADING,
    PROFILE_TYPE_TIME,
    PROFILE_FUNCTIONS,
    PROFILE_TYPES,
    MANUAL_OVERRIDE_RESET_NONE,
    MANUAL_OVERRIDE_RESET_TIME,
    MANUAL_OVERRIDE_RESET_TIMEOUT,
    SHADING_CONDITION_AZIMUTH,
    SHADING_CONDITION_BRIGHTNESS,
    SHADING_CONDITION_ELEVATION,
    SHADING_CONDITION_FORECAST_TEMP,
    SHADING_CONDITION_FORECAST_WEATHER,
    SHADING_CONDITION_TEMP_1,
    SHADING_CONDITION_TEMP_2,
    SHADING_CONFIG_COMPARE_FORECAST_SENSOR2,
    SHADING_CONFIG_TEMP_INDEPENDENT,
)


def _with_config_defaults(config: dict) -> dict:
    """Ensure automation, time, and position defaults are present."""

    return {
        **DEFAULT_POSITION_SETTINGS,
        **DEFAULT_TIME_SETTINGS,
        **DEFAULT_AUTOMATION_FLAGS,
        **DEFAULT_MASTER_FLAGS,
        **DEFAULT_MANUAL_OVERRIDE_FLAGS,
        **DEFAULT_CONTACT_SETTINGS,
        **DEFAULT_BEHAVIOR_SETTINGS,
        **DEFAULT_BUTTON_SETTINGS,
        **DEFAULT_SHADING_TIMING_SETTINGS,
        **{key: list(value) if isinstance(value, list) else value for key, value in DEFAULT_SHADING_CONDITION_SETTINGS.items()},
        CONF_SUN_ELEVATION_MODE: DEFAULT_SUN_ELEVATION_MODE,
        CONF_SUN_ELEVATION_OPEN_OFFSET: DEFAULT_SUN_ELEVATION_OPEN_OFFSET,
        CONF_SUN_ELEVATION_CLOSE_OFFSET: DEFAULT_SUN_ELEVATION_CLOSE_OFFSET,
        CONF_TEMPERATURE_THRESHOLD: DEFAULT_TEMPERATURE_THRESHOLD,
        CONF_TEMPERATURE_FORECAST_THRESHOLD: DEFAULT_TEMPERATURE_FORECAST_THRESHOLD,
        **config,
    }


def _selector_default(value: Any) -> Any:
    """Return a safe selector default, skipping None/empty placeholders."""

    if value in (None, "", vol.UNDEFINED):
        return vol.UNDEFINED
    return value


LOGGER = logging.getLogger(__name__)


CLEARABLE_ENTITY_SELECTOR_KEYS = {
    CONF_WORKDAY_SENSOR,
    CONF_WORKDAY_TOMORROW_SENSOR,
    CONF_CALENDAR_ENTITY,
    CONF_RESIDENT_SENSOR,
    CONF_BRIGHTNESS_SENSOR,
    CONF_SHADING_BRIGHTNESS_SENSOR,
    CONF_TEMPERATURE_SENSOR_INDOOR,
    CONF_TEMPERATURE_SENSOR_OUTDOOR,
    CONF_SHADING_TEMPERATURE_SENSOR_1,
    CONF_SHADING_TEMPERATURE_SENSOR_2,
    CONF_COLD_PROTECTION_FORECAST_SENSOR,
    CONF_SHADING_FORECAST_SENSOR,
    CONF_SHADING_FORECAST_TEMP_SENSOR,
    CONF_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR,
    CONF_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR,
    CONF_CUSTOM_POSITION_SENSOR,
}

ENTITY_TOGGLE_MAP: dict[str, str] = {
    CONF_USE_WORKDAY_SENSOR: CONF_WORKDAY_SENSOR,
    CONF_USE_RESIDENT_SENSOR: CONF_RESIDENT_SENSOR,
    CONF_USE_BRIGHTNESS_SENSOR: CONF_BRIGHTNESS_SENSOR,
    CONF_USE_TEMPERATURE_SENSOR_INDOOR: CONF_TEMPERATURE_SENSOR_INDOOR,
    CONF_USE_TEMPERATURE_SENSOR_OUTDOOR: CONF_TEMPERATURE_SENSOR_OUTDOOR,
    CONF_USE_COLD_PROTECTION_FORECAST_SENSOR: CONF_COLD_PROTECTION_FORECAST_SENSOR,
    CONF_USE_SHADING_FORECAST_SENSOR: CONF_SHADING_FORECAST_SENSOR,
    CONF_USE_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR: CONF_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR,
    CONF_USE_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR: CONF_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR,
}


INITIAL_FEATURE_KEYS = (
    CONF_AUTO_TIME,
    CONF_AUTO_VENTILATE,
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_SUN,
    CONF_AUTO_SHADING,
    CONF_RESIDENT_STATUS,
    CONF_ADDITIONAL_CONDITIONS_ENABLED,
)


def _is_enabled(options: dict, key: str) -> bool:
    """Return whether an optional entity key currently stores an active value."""

    return options.get(key) not in (None, "", vol.UNDEFINED)

def _time_default(value, fallback: str | None = None):
    """Return a time object for selectors, falling back safely."""

    for candidate in (value, fallback):
        if candidate in (None, "", vol.UNDEFINED):
            continue
        parsed = dt_util.parse_time(str(candidate))
        if parsed:
            return parsed
    return vol.UNDEFINED


SHADING_CONDITION_OPTIONS = [
    {"value": SHADING_CONDITION_AZIMUTH, "label": "cond_azimuth"},
    {"value": SHADING_CONDITION_ELEVATION, "label": "cond_elevation"},
    {"value": SHADING_CONDITION_BRIGHTNESS, "label": "cond_brightness"},
    {"value": SHADING_CONDITION_TEMP_1, "label": "cond_temp1"},
    {"value": SHADING_CONDITION_TEMP_2, "label": "cond_temp2"},
    {"value": SHADING_CONDITION_FORECAST_TEMP, "label": "cond_forecast_temp"},
    {"value": SHADING_CONDITION_FORECAST_WEATHER, "label": "cond_forecast_weather"},
]

SHADING_CONFIG_OPTIONS = [
    {
        "value": SHADING_CONFIG_TEMP_INDEPENDENT,
        "label": "shading_temp_comparison_independent",
    },
    {
        "value": SHADING_CONFIG_COMPARE_FORECAST_SENSOR2,
        "label": "shading_compare_forecast_with_sensor2",
    },
]


POSITION_FIELD_LIMITS = {
    CONF_OPEN_POSITION: 100,
    CONF_CLOSE_POSITION: 100,
    CONF_VENTILATE_POSITION: 100,
    CONF_LOCKOUT_POSITION: 100,
    CONF_SHADING_POSITION: 100,
    CONF_SHADING_POSITION_ALT: 100,
    CONF_POSITION_TOLERANCE: 20,
    CONF_OPEN_TILT_POSITION: 100,
    CONF_CLOSE_TILT_POSITION: 100,
    CONF_VENTILATE_TILT_POSITION: 100,
    CONF_SHADING_TILT_POSITION: 100,
    CONF_SHADING_TILT_POSITION_0: 100,
    CONF_SHADING_TILT_POSITION_1: 100,
    CONF_SHADING_TILT_POSITION_2: 100,
    CONF_SHADING_TILT_POSITION_3: 100,
}

_EXTRA_POSITION_DEFAULTS: dict[str, int] = {
    CONF_SHADING_TILT_POSITION_0: DEFAULT_SHADING_TILT_POSITION_0,
    CONF_SHADING_TILT_POSITION_1: DEFAULT_SHADING_TILT_POSITION_1,
    CONF_SHADING_TILT_POSITION_2: DEFAULT_SHADING_TILT_POSITION_2,
    CONF_SHADING_TILT_POSITION_3: DEFAULT_SHADING_TILT_POSITION_3,
}


def _position_number_selector(
    key: str = CONF_OPEN_POSITION,
) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=POSITION_FIELD_LIMITS[key],
            step=1,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _normalize_position_value(key: str, value: Any) -> int | None:
    max_value = POSITION_FIELD_LIMITS[key]
    optional_positions = {CONF_LOCKOUT_POSITION, CONF_SHADING_POSITION_ALT}
    if key in optional_positions and value in (None, "", vol.UNDEFINED):
        return None
    try:
        parsed = int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        fallback = DEFAULT_POSITION_SETTINGS.get(key, _EXTRA_POSITION_DEFAULTS.get(key, 0))
        if key in optional_positions and fallback is None:
            return None
        parsed = int(fallback)
    return max(0, min(max_value, parsed))


def _position_default(config: dict[str, Any], key: str) -> int | None:
    fallback = DEFAULT_POSITION_SETTINGS.get(key, _EXTRA_POSITION_DEFAULTS.get(key, 0))
    return _normalize_position_value(key, config.get(key, fallback))


def _normalize_position_fields(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)
    for key in POSITION_FIELD_LIMITS:
        if key not in normalized:
            continue
        normalized[key] = _normalize_position_value(key, normalized[key])
    return normalized


class CoverControlFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 6

    def __init__(self) -> None:
        self._data: dict = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Create exactly one global parent entry without requiring a room."""

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            self._data[CONF_NAME] = str(user_input.get(CONF_NAME, DEFAULT_NAME))
            return await self.async_step_global_sources()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                }
            ),
        )

    async def async_step_global_sources(self, user_input=None) -> FlowResult:
        """Collect optional shared sources for parent entry."""

        if user_input is not None:
            self._data[CONF_GLOBAL] = {
                CONF_GLOBAL_SOURCES: {
                    key: value
                    for key, value in user_input.items()
                    if value not in (None, "")
                },
                CONF_GLOBAL_DEFAULTS: {},
            }
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={
                    CONF_NAME: DEFAULT_NAME,
                    CONF_GLOBAL: self._data[CONF_GLOBAL],
                    CONF_PROFILES: {},
                },
            )
        fields = {}
        for key in sorted(GLOBAL_SOURCE_KEYS):
            fields[vol.Optional(key)] = (
                selector.ConditionSelector()
                if key == CONF_ADDITIONAL_CONDITION_GLOBAL
                else selector.EntitySelector(selector.EntitySelectorConfig())
            )
        return self.async_show_form(
            step_id="global_sources", data_schema=vol.Schema(fields)
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: config_entries.ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Expose only physical rooms as native ConfigSubentries."""

        return {"room": RoomSubentryFlow}

    def _entry(self) -> config_entries.ConfigEntry:
        """Return the parent entry attached to this reconfigure flow."""

        return self._get_reconfigure_entry()

    def _model(self) -> ConfigProfileModel:
        from .config_subentries import model_from_subentries

        entry = self._entry()
        return ConfigProfileModel(
            model_from_subentries(entry.data, entry.subentries.values())
        )

    def _save_parent_model(self, model: ConfigProfileModel) -> None:
        entry = self._entry()
        new_data = deepcopy(dict(entry.data))
        new_data[CONF_GLOBAL] = deepcopy(model.data[CONF_GLOBAL])
        new_data[CONF_PROFILES] = {
            profile_id: deepcopy(profile)
            for profile_id, profile in model.data[CONF_PROFILES].items()
            if profile_id not in PROFILE_TYPES
        }
        self.hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            options={},
        )

    async def async_step_reconfigure(self, user_input=None) -> FlowResult:
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=[
                "global_sources",
                "profiles",
                "diagnostics",
                "recovery",
            ],
        )

    async def async_step_global_sources(self, user_input=None) -> FlowResult:
        if self.source != config_entries.SOURCE_RECONFIGURE:
            if user_input is not None:
                self._data[CONF_GLOBAL] = {
                    CONF_GLOBAL_SOURCES: {
                        key: value
                        for key, value in user_input.items()
                        if value not in (None, "")
                    },
                    CONF_GLOBAL_DEFAULTS: {},
                }
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={
                        CONF_NAME: DEFAULT_NAME,
                        CONF_GLOBAL: self._data[CONF_GLOBAL],
                        CONF_PROFILES: {},
                    },
                )
            fields = {}
            for key in sorted(GLOBAL_SOURCE_KEYS):
                fields[vol.Optional(key)] = (
                    selector.ConditionSelector()
                    if key == CONF_ADDITIONAL_CONDITION_GLOBAL
                    else selector.EntitySelector(selector.EntitySelectorConfig())
                )
            return self.async_show_form(
                step_id="global_sources", data_schema=vol.Schema(fields)
            )

        entry = self._entry()
        global_data = deepcopy(dict(entry.data.get(CONF_GLOBAL, {})))
        sources = dict(global_data.get(CONF_GLOBAL_SOURCES, {}))
        if user_input is not None:
            sources = {
                key: value
                for key, value in user_input.items()
                if value not in (None, "")
            }
            global_data[CONF_GLOBAL_SOURCES] = sources
            new_data = deepcopy(dict(entry.data))
            new_data[CONF_GLOBAL] = global_data
            return self.async_update_reload_and_abort(
                entry,
                data=new_data,
                options={},
                reload_even_if_entry_is_unchanged=False,
            )
        schema = {}
        for key in sorted(GLOBAL_SOURCE_KEYS):
            current = sources.get(key)
            marker = vol.Optional(
                key,
                description={"suggested_value": current} if current else None,
            )
            schema[marker] = (
                selector.ConditionSelector()
                if key == CONF_ADDITIONAL_CONDITION_GLOBAL
                else selector.EntitySelector(selector.EntitySelectorConfig())
            )
        return self.async_show_form(
            step_id="global_sources", data_schema=vol.Schema(schema)
        )

    async def async_step_recovery(self, user_input=None) -> FlowResult:
        """Restore last-known-good parent and native subentries."""

        entry = self._entry()
        runtime = getattr(entry, "runtime_data", None)
        recovery = getattr(runtime, "recovery_manager", None)
        available = recovery is not None and recovery.last_known_good is not None
        if user_input is not None and user_input.get("confirm") and available:
            parent_data, payloads = model_to_native_payloads(
                recovery.last_known_good
            )
            parent_data[CONF_NAME] = DEFAULT_NAME
            for subentry_id in tuple(entry.subentries):
                self.hass.config_entries.async_remove_subentry(
                    entry, subentry_id
                )
            for subentry_id, subentry_type, title, data in payloads:
                self.hass.config_entries.async_add_subentry(
                    entry,
                    ConfigSubentry(
                        data=MappingProxyType(data),
                        subentry_id=subentry_id,
                        subentry_type=subentry_type,
                        title=title,
                        unique_id=subentry_id,
                    ),
                )
            return self.async_update_reload_and_abort(
                entry,
                data=parent_data,
                options={},
                reload_even_if_entry_is_unchanged=False,
            )
        return self.async_show_form(
            step_id="recovery",
            data_schema=vol.Schema(
                {vol.Required("confirm", default=False): bool}
            ),
            description_placeholders={"available": str(available).lower()},
        )

    async def async_step_diagnostics(self, user_input=None) -> FlowResult:
        model = self._model()
        usage = []
        for profile_id, profile in model.data[CONF_PROFILES].items():
            if profile_id in PROFILE_TYPES:
                continue
            rooms = sorted(model.profile_users.get(("profile", profile_id), ()))
            usage.append(
                f"{profile.get(CONF_PROFILE_NAME, profile_id)}: "
                f"{', '.join(self._room_names(model, rooms)) or '—'}"
            )
        return self.async_show_form(
            step_id="diagnostics",
            data_schema=vol.Schema({}),
            description_placeholders={"profiles": "; ".join(usage) or "—"},
        )

    async def async_step_profiles(self, user_input=None) -> FlowResult:
        model = self._model()
        catalog = {
            profile_id: profile
            for profile_id, profile in model.data[CONF_PROFILES].items()
            if profile_id not in PROFILE_TYPES
        }
        errors: dict[str, str] = {}
        if user_input is not None:
            action = user_input["profile_action"]
            profile_id = user_input.get("profile_id")
            if action == "create":
                self._editing_profile_id = None
                return await self.async_step_profile_setup()
            if not profile_id:
                errors["base"] = "profile_required"
            elif action == "edit":
                self._editing_profile_id = profile_id
                return await self.async_step_profile_sections()
            elif action == "duplicate":
                from homeassistant.util.ulid import ulid_now

                copied = deepcopy(catalog[profile_id])
                new_id = ulid_now()
                copied[CONF_PROFILE_ID] = new_id
                copied[CONF_PROFILE_NAME] = f"{copied.get(CONF_PROFILE_NAME, profile_id)} 2"
                model.data[CONF_PROFILES][new_id] = copied
                self._save_parent_model(model)
                return await self.async_step_profiles()
            elif action == "delete":
                users = [
                    room_id
                    for room_id, room in model.data[CONF_ROOMS].items()
                    if room.get("profile_id") == profile_id
                ]
                if users:
                    self._blocked_profile_rooms = self._room_names(model, users)
                    errors["base"] = "profile_in_use"
                else:
                    model.data[CONF_PROFILES].pop(profile_id, None)
                    self._save_parent_model(model)
                    return await self.async_step_profiles()

        profile_options = [
            {"value": profile_id, "label": profile.get(CONF_PROFILE_NAME, profile_id)}
            for profile_id, profile in catalog.items()
        ]
        schema: dict = {
            vol.Required("profile_action", default="edit"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["create", "edit", "duplicate", "delete"],
                    translation_key="profile_action",
                )
            )
        }
        if profile_options:
            schema[vol.Optional("profile_id")] = selector.SelectSelector(
                selector.SelectSelectorConfig(options=profile_options)
            )
        return self.async_show_form(
            step_id="profiles",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "profile_usage": "; ".join(
                    f"{profile.get(CONF_PROFILE_NAME, profile_id)}: "
                    f"{', '.join(self._room_names(model, sorted(model.profile_users.get(('profile', profile_id), ())))) or '—'}"
                    for profile_id, profile in catalog.items()
                )
                or "—",
                "blocked_rooms": ", ".join(getattr(self, "_blocked_profile_rooms", [])),
            },
        )

    async def async_step_profile_setup(self, user_input=None) -> FlowResult:
        model = self._model()
        profile_id = getattr(self, "_editing_profile_id", None)
        profile = model.data[CONF_PROFILES].get(profile_id, {})
        if user_input is not None:
            name = str(user_input["profile_name"]).strip()
            if profile_id:
                profile[CONF_PROFILE_NAME] = name
            else:
                from homeassistant.util.ulid import ulid_now

                profile_id = ulid_now()
                model.data[CONF_PROFILES][profile_id] = {
                    CONF_PROFILE_ID: profile_id,
                    CONF_PROFILE_NAME: name,
                    CONF_PROFILE_SETTINGS: {},
                    CONF_PROFILE_FUNCTIONS: [],
                }
                self._editing_profile_id = profile_id
            self._save_parent_model(model)
            return await self.async_step_profile_sections()
        return self.async_show_form(
            step_id="profile_setup",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "profile_name",
                        default=profile.get(CONF_PROFILE_NAME, ""),
                    ): selector.TextSelector(),
                }
            ),
            description_placeholders={
                "profile_usage": self._profile_usage_text(model, "profile", profile_id)
            },
        )

    async def async_step_profile_sections(self, user_input=None) -> FlowResult:
        model = self._model()
        profile_id = getattr(self, "_editing_profile_id", None)
        return self.async_show_menu(
            step_id="profile_sections",
            menu_options=[
                "profile_setup",
                "profile_time",
                "profile_brightness",
                "profile_sun",
                "profile_shading",
                "profile_ventilation",
                "profile_resident",
                "profile_behavior",
            ],
            description_placeholders=self._profile_context_placeholders(
                model, profile_id
            ),
        )

    async def _async_unified_profile_function_step(
        self,
        profile_type: str,
        step_id: str,
        user_input,
        *,
        capabilities: tuple[str, ...],
    ) -> FlowResult:
        model = self._model()
        profile_id = getattr(self, "_editing_profile_id", None)
        if not profile_id or profile_id not in model.data[CONF_PROFILES]:
            return await self.async_step_profiles()
        profile = model.data[CONF_PROFILES][profile_id]
        existing = dict(profile.get(CONF_PROFILE_SETTINGS, {}))
        allowed = capability_keys(profile_type, capabilities)
        if user_input is not None:
            selected = extract_sparse_settings(
                flatten_section_input(user_input),
                profile_type,
                {key: value for key, value in existing.items() if key in allowed},
                field_selection=None,
                allowed_keys=allowed,
            )
            profile[CONF_PROFILE_SETTINGS] = {
                **{key: value for key, value in existing.items() if key not in allowed},
                **selected,
            }
            from .config_resolver import configured_functions_from_profile

            profile[CONF_PROFILE_FUNCTIONS] = sorted(
                configured_functions_from_profile(profile)
            )
            self._save_parent_model(model)
            return await self.async_step_profile_sections()
        return self.async_show_form(
            step_id=step_id,
            data_schema=build_profile_schema(
                profile_type,
                existing,
                system_defaults(),
                field_selection=None,
                allowed_keys=allowed,
            ),
            description_placeholders=self._profile_context_placeholders(
                model, profile_id
            ),
        )

    def _profile_context_placeholders(
        self, model: ConfigProfileModel, profile_id: str | None
    ) -> dict[str, str]:
        name = self._profile_display_name(model, profile_id)
        return {
            "profile_name": name,
            "profile_context": f'Profile "{name}"',
            "profile_usage": self._profile_usage_text(model, "profile", profile_id),
        }

    @staticmethod
    def _profile_display_name(
        model: ConfigProfileModel, profile_id: str | None
    ) -> str:
        if not profile_id:
            return "—"
        profile = model.data[CONF_PROFILES].get(profile_id, {})
        return str(profile.get(CONF_PROFILE_NAME) or profile_id)

    async def async_step_profile_time(self, user_input=None) -> FlowResult:
        return await self._async_unified_profile_function_step(
            PROFILE_TYPE_TIME,
            "profile_time",
            user_input,
            capabilities=("opening", "closing", "workday", "calendar"),
        )

    async def async_step_profile_brightness(self, user_input=None) -> FlowResult:
        return await self._async_unified_profile_function_step(
            PROFILE_TYPE_TIME,
            "profile_brightness",
            user_input,
            capabilities=("brightness",),
        )

    async def async_step_profile_sun(self, user_input=None) -> FlowResult:
        return await self._async_unified_profile_function_step(
            PROFILE_TYPE_TIME, "profile_sun", user_input, capabilities=("sun",)
        )

    async def async_step_profile_shading(self, user_input=None) -> FlowResult:
        return await self._async_unified_profile_function_step(
            PROFILE_TYPE_SHADING,
            "profile_shading",
            user_input,
            capabilities=tuple(PROFILE_CAPABILITY_KEYS[PROFILE_TYPE_SHADING]),
        )

    async def async_step_profile_ventilation(self, user_input=None) -> FlowResult:
        return await self._async_unified_profile_function_step(
            PROFILE_TYPE_BEHAVIOR,
            "profile_ventilation",
            user_input,
            capabilities=("ventilation",),
        )

    async def async_step_profile_resident(self, user_input=None) -> FlowResult:
        return await self._async_unified_profile_function_step(
            PROFILE_TYPE_BEHAVIOR,
            "profile_resident",
            user_input,
            capabilities=("resident",),
        )

    async def async_step_profile_behavior(self, user_input=None) -> FlowResult:
        return await self._async_unified_profile_function_step(
            PROFILE_TYPE_BEHAVIOR,
            "profile_behavior",
            user_input,
            capabilities=("manual_override", "movement_protection", "tilt_behavior"),
        )

    def _profile_usage_text(
        self, model: ConfigProfileModel, profile_type: str, profile_id: str | None
    ) -> str:
        if not profile_id:
            return "This profile is currently not used by any room."
        rooms = self._room_names(
            model, sorted(model.profile_users.get((profile_type, profile_id), ()))
        )
        return ", ".join(rooms) or "—"

    @staticmethod
    def _room_names(model: ConfigProfileModel, room_ids: list[str]) -> list[str]:
        return [
            str(model.data[CONF_ROOMS].get(room_id, {}).get(CONF_NAME, room_id))
            for room_id in room_ids
        ]


class RoomSubentryFlow(ConfigSubentryFlow):
    """Create or edit room-local hardware data on a native subentry."""

    def _room_context_placeholders(self) -> dict[str, str]:
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        data = dict(subentry.data)
        settings = dict(data.get(CONF_ROOM_SETTINGS, {}))
        profiles = entry.data.get(CONF_PROFILES, {})
        profile_id = data.get(CONF_ROOM_PROFILE_ID)
        profile = profiles.get(profile_id, {}) if profile_id else {}
        profile_name = str(profile.get(CONF_PROFILE_NAME) or "—")
        covers = settings.get(CONF_COVERS, [])
        selected = data.get(CONF_PROFILE_FUNCTIONS, [])
        if isinstance(selected, dict):
            selected = [
                function for function, enabled in selected.items() if enabled
            ]
        return {
            "room_name": str(
                data.get(CONF_NAME) or subentry.title or subentry.subentry_id
            ),
            "area": str(settings.get(CONF_ROOM) or "—"),
            "cover_count": str(len(covers) if isinstance(covers, list) else 0),
            "profile_name": profile_name,
            "profile_function_count": str(
                len(selected) if isinstance(selected, list) else 0
            ),
        }

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Create one room without duplicating parent global settings."""

        if user_input is not None:
            title = str(user_input[CONF_NAME]).strip()
            return self.async_create_entry(
                title=title,
                data={
                    CONF_NAME: title,
                    CONF_PROFILE_FUNCTIONS: [],
                    CONF_ROOM_SETTINGS: {
                        CONF_ROOM: user_input[CONF_ROOM],
                        CONF_COVERS: list(user_input[CONF_COVERS]),
                    },
                    CONF_SOURCE_OVERRIDES: {},
                },
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): selector.TextSelector(),
                    vol.Required(CONF_ROOM): selector.AreaSelector(),
                    vol.Required(CONF_COVERS): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["cover"], multiple=True)
                    ),
                }
            ),
        )

    async def async_step_reconfigure(self, user_input=None) -> FlowResult:
        """Expose room-only configuration pages."""

        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=[
                "general",
                "hardware",
                "positions",
                "contacts",
                "room_sensors",
                "geometry",
                "profile_assignment",
                "source_overrides",
                "controls",
                "diagnostics",
            ],
            description_placeholders=self._room_context_placeholders(),
        )

    async def async_step_controls(self, user_input=None) -> FlowResult:
        subentry = self._get_reconfigure_subentry()
        data = dict(subentry.data)
        settings = dict(data.get(CONF_ROOM_SETTINGS, {}))
        if user_input is not None:
            settings.pop(CONF_MANUAL_CONTROL, None)
            for key in (
                CONF_ENABLE_RECALIBRATE_BUTTON,
                CONF_ENABLE_CLEAR_MANUAL_OVERRIDE_BUTTON,
                CONF_ENABLE_LOGBOOK_COVER,
            ):
                settings[key] = bool(user_input.get(key, False))
            data[CONF_ROOM_SETTINGS] = settings
            return self.async_update_and_abort(self._get_entry(), subentry, data=data)
        merged = {**DEFAULT_BUTTON_SETTINGS, **settings}
        return self.async_show_form(
            step_id="controls",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ENABLE_RECALIBRATE_BUTTON,
                        default=bool(merged.get(CONF_ENABLE_RECALIBRATE_BUTTON)),
                    ): bool,
                    vol.Optional(
                        CONF_ENABLE_CLEAR_MANUAL_OVERRIDE_BUTTON,
                        default=bool(
                            merged.get(CONF_ENABLE_CLEAR_MANUAL_OVERRIDE_BUTTON)
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_ENABLE_LOGBOOK_COVER,
                        default=bool(settings.get(CONF_ENABLE_LOGBOOK_COVER, False)),
                    ): bool,
                }
            ),
            description_placeholders=self._room_context_placeholders(),
        )

    async def async_step_general(self, user_input=None) -> FlowResult:
        subentry = self._get_reconfigure_subentry()
        data = dict(subentry.data)
        settings = dict(data.get(CONF_ROOM_SETTINGS, {}))
        if user_input is not None:
            title = str(user_input[CONF_NAME]).strip()
            data[CONF_NAME] = title
            settings[CONF_ROOM] = user_input[CONF_ROOM]
            data[CONF_ROOM_SETTINGS] = settings
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                title=title,
                data=data,
            )
        return self.async_show_form(
            step_id="general",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=subentry.title): selector.TextSelector(),
                    vol.Required(
                        CONF_ROOM, default=settings.get(CONF_ROOM)
                    ): selector.AreaSelector(),
                }
            ),
            description_placeholders=self._room_context_placeholders(),
        )

    async def async_step_contacts(self, user_input=None) -> FlowResult:
        subentry = self._get_reconfigure_subentry()
        data = dict(subentry.data)
        settings = dict(data.get(CONF_ROOM_SETTINGS, {}))
        covers = settings.get(CONF_COVERS, [])
        key_map = self._contact_key_map(covers)
        if user_input is not None:
            full_map: dict[str, list[str]] = {}
            tilt_map: dict[str, list[str]] = {}
            for cover in covers:
                full_map[cover] = list(user_input.get(key_map[(cover, "full")], []))
                tilt_map[cover] = list(user_input.get(key_map[(cover, "tilt")], []))
            settings[CONF_WINDOW_SENSOR_FULL] = full_map
            settings[CONF_WINDOW_SENSOR_TILT] = tilt_map
            data[CONF_ROOM_SETTINGS] = settings
            return self.async_update_and_abort(self._get_entry(), subentry, data=data)
        multi_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["binary_sensor"], multiple=True)
        )
        schema = {}
        full = settings.get(CONF_WINDOW_SENSOR_FULL, {})
        tilt = settings.get(CONF_WINDOW_SENSOR_TILT, {})
        for cover in covers:
            schema[
                vol.Optional(key_map[(cover, "full")], default=full.get(cover, []))
            ] = multi_selector
            schema[
                vol.Optional(key_map[(cover, "tilt")], default=tilt.get(cover, []))
            ] = multi_selector
        return self.async_show_form(
            step_id="contacts",
            data_schema=vol.Schema(schema),
            description_placeholders=self._room_context_placeholders(),
        )

    @staticmethod
    def _contact_key(index: int, contact_type: str) -> str:
        return f"cover_{index}_{contact_type}"

    def _contact_key_map(self, covers: list[str]) -> dict[tuple[str, str], str]:
        return {
            (cover, contact_type): self._contact_key(index, contact_type)
            for index, cover in enumerate(covers)
            for contact_type in ("full", "tilt")
        }

    async def async_step_room_sensors(self, user_input=None) -> FlowResult:
        subentry = self._get_reconfigure_subentry()
        data = dict(subentry.data)
        settings = dict(data.get(CONF_ROOM_SETTINGS, {}))
        if user_input is not None:
            for key, value in user_input.items():
                if value in (None, ""):
                    settings.pop(key, None)
                else:
                    settings[key] = value
            data[CONF_ROOM_SETTINGS] = settings
            return self.async_update_and_abort(self._get_entry(), subentry, data=data)
        return self.async_show_form(
            step_id="room_sensors",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_TEMPERATURE_SENSOR_INDOOR,
                        default=_selector_default(settings.get(CONF_TEMPERATURE_SENSOR_INDOOR)),
                    ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
                    vol.Optional(
                        CONF_RESIDENT_SENSOR,
                        default=_selector_default(settings.get(CONF_RESIDENT_SENSOR)),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["binary_sensor", "input_boolean", "switch"]
                        )
                    ),
                }
            ),
            description_placeholders=self._room_context_placeholders(),
        )

    async def async_step_geometry(self, user_input=None) -> FlowResult:
        subentry = self._get_reconfigure_subentry()
        data = dict(subentry.data)
        settings = dict(data.get(CONF_ROOM_SETTINGS, {}))
        keys = (CONF_SUN_AZIMUTH_START, CONF_SUN_AZIMUTH_END)
        if user_input is not None:
            for key in keys:
                settings[key] = user_input[key]
            data[CONF_ROOM_SETTINGS] = settings
            return self.async_update_and_abort(self._get_entry(), subentry, data=data)
        return self.async_show_form(
            step_id="geometry",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SUN_AZIMUTH_START,
                        default=settings.get(
                            CONF_SUN_AZIMUTH_START, DEFAULT_SHADING_AZIMUTH_START
                        ),
                    ): vol.Coerce(float),
                    vol.Required(
                        CONF_SUN_AZIMUTH_END,
                        default=settings.get(
                            CONF_SUN_AZIMUTH_END, DEFAULT_SHADING_AZIMUTH_END
                        ),
                    ): vol.Coerce(float),
                }
            ),
            description_placeholders=self._room_context_placeholders(),
        )

    async def async_step_diagnostics(self, user_input=None) -> FlowResult:
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        data = dict(subentry.data)
        settings = dict(data.get(CONF_ROOM_SETTINGS, {}))
        selections = data.get(CONF_PROFILE_SELECTIONS, {})
        profiles = entry.data.get(CONF_PROFILES, {})
        profile_labels = []
        profile_id = data.get("profile_id")
        profile = profiles.get(profile_id) if profile_id else None
        profile_labels.append(
            str(profile.get(CONF_PROFILE_NAME)) if isinstance(profile, dict) else "—"
        )
        snapshot = self._room_entry_snapshot(entry, subentry.subentry_id)

        return self.async_show_form(
            step_id="diagnostics",
            data_schema=vol.Schema({}),
            description_placeholders={
                "room": str(data.get(CONF_NAME, subentry.title)),
                "area": str(settings.get(CONF_ROOM) or "—"),
                "cover_count": str(len(settings.get(CONF_COVERS, []))),
                "profiles": "; ".join(profile_labels),
                "profile_name": "; ".join(profile_labels),
                "profile_function_count": str(
                    len(data.get(CONF_PROFILE_FUNCTIONS, []))
                    if isinstance(data.get(CONF_PROFILE_FUNCTIONS, []), list)
                    else 0
                ),
                "resident_sensor": self._entity_name(settings.get(CONF_RESIDENT_SENSOR)),
                "temperature_sensor": self._entity_name(settings.get(CONF_TEMPERATURE_SENSOR_INDOOR)),
                "next_open": self._format_schedule_event(snapshot.get("next_open")),
                "next_close": self._format_schedule_event(snapshot.get("next_close")),
            },
        )

    def _room_entry_snapshot(
        self, entry: config_entries.ConfigEntry, subentry_id: str
    ) -> dict[str, Any]:
        runtime = getattr(entry, "runtime_data", None)
        managers = getattr(runtime, "room_managers", {})
        manager = managers.get(subentry_id) if isinstance(managers, dict) else None
        if manager is None:
            return {}
        snapshot = manager.entry_snapshot()
        return snapshot if isinstance(snapshot, dict) else {}

    def _format_schedule_event(self, event: Any) -> str:
        if not (
            isinstance(event, tuple)
            and len(event) == 2
            and isinstance(event[0], datetime)
        ):
            return "—"
        when = dt_util.as_local(event[0])
        cover_name = self._entity_name(event[1])
        value = when.strftime("%Y-%m-%d %H:%M")
        return value if cover_name == "—" else f"{value} ({cover_name})"

    def _entity_name(self, entity_id: Any) -> str:
        if not entity_id:
            return "—"
        state = self.hass.states.get(str(entity_id))
        return state.name if state else "—"

    async def async_step_hardware(self, user_input=None) -> FlowResult:
        """Edit room-local hardware while retaining function configuration."""

        subentry = self._get_reconfigure_subentry()
        settings = subentry.data.get(CONF_ROOM_SETTINGS, {})
        if user_input is not None:
            data = dict(subentry.data)
            settings = dict(data.get(CONF_ROOM_SETTINGS, {}))
            settings.update(_normalize_position_fields(dict(user_input)))
            settings[CONF_COVERS] = list(user_input[CONF_COVERS])
            if settings.get(CONF_POSITION_SOURCE) != CONF_POSITION_SOURCE_CUSTOM_SENSOR:
                settings.pop(CONF_CUSTOM_POSITION_SENSOR, None)
            data[CONF_ROOM_SETTINGS] = settings
            return self.async_update_and_abort(self._get_entry(), subentry, data=data)
        return self.async_show_form(
            step_id="hardware",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_COVERS, default=settings.get(CONF_COVERS, [])
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["cover"], multiple=True)
                    ),
                    vol.Required(
                        CONF_POSITION_SOURCE,
                        default=settings.get(
                            CONF_POSITION_SOURCE,
                            CONF_POSITION_SOURCE_CURRENT_POSITION_ATTR,
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                CONF_POSITION_SOURCE_CURRENT_POSITION_ATTR,
                                CONF_POSITION_SOURCE_POSITION_ATTR,
                                CONF_POSITION_SOURCE_CUSTOM_SENSOR,
                            ],
                            translation_key="position_source",
                        )
                    ),
                    vol.Optional(
                        CONF_CUSTOM_POSITION_SENSOR,
                        default=_selector_default(settings.get(CONF_CUSTOM_POSITION_SENSOR)),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"])
                    ),
                    vol.Required(
                        CONF_COVER_TYPE,
                        default=settings.get(
                            CONF_COVER_TYPE,
                            DEFAULT_BEHAVIOR_SETTINGS[CONF_COVER_TYPE],
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                CONF_COVER_TYPE_BLIND,
                                CONF_COVER_TYPE_AWNING,
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="cover_type",
                        )
                    ),
                    vol.Optional(
                        CONF_DRIVE_TIME,
                        default=settings.get(CONF_DRIVE_TIME, DEFAULT_DRIVE_TIME),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=600,
                            step=0.1,
                            unit_of_measurement="s",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_COVER_TILT_WAIT_MODE,
                        default=settings.get(
                            CONF_COVER_TILT_WAIT_MODE,
                            DEFAULT_COVER_TILT_WAIT_MODE,
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                COVER_TILT_WAIT_FIXED_DELAY,
                                COVER_TILT_WAIT_IDLE,
                                COVER_TILT_WAIT_BEFORE_POSITION,
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="cover_tilt_wait_mode",
                        )
                    ),
                    vol.Optional(
                        CONF_COVER_TILT_WAIT_TIMEOUT,
                        default=settings.get(
                            CONF_COVER_TILT_WAIT_TIMEOUT,
                            DEFAULT_COVER_TILT_WAIT_TIMEOUT,
                        ),
                    ): vol.Coerce(int),
                    vol.Required(
                        CONF_POSITION_TOLERANCE,
                        default=_position_default(dict(settings), CONF_POSITION_TOLERANCE),
                    ): _position_number_selector(CONF_POSITION_TOLERANCE),
                }
            ),
            description_placeholders=self._room_context_placeholders(),
        )

    async def async_step_positions(self, user_input=None) -> FlowResult:
        """Edit room-owned physical cover and tilt positions."""

        subentry = self._get_reconfigure_subentry()
        data = dict(subentry.data)
        settings = dict(data.get(CONF_ROOM_SETTINGS, {}))
        if user_input is not None:
            submitted: dict[str, Any] = {}
            for value in user_input.values():
                if isinstance(value, dict):
                    submitted.update(value)
            keys = {
                CONF_OPEN_POSITION,
                CONF_CLOSE_POSITION,
                CONF_SHADING_POSITION,
                CONF_SHADING_POSITION_ALT,
                CONF_SHADING_POSITION_ALT_ENTITY,
                CONF_VENTILATE_POSITION,
                CONF_LOCKOUT_POSITION,
                CONF_OPEN_TILT_POSITION,
                CONF_CLOSE_TILT_POSITION,
                CONF_SHADING_TILT_POSITION,
                CONF_VENTILATE_TILT_POSITION,
                CONF_SHADING_TILT_POSITION_0,
                CONF_SHADING_TILT_POSITION_1,
                CONF_SHADING_TILT_POSITION_2,
                CONF_SHADING_TILT_POSITION_3,
            }
            normalized = _normalize_position_fields(
                {key: value for key, value in submitted.items() if key in keys}
            )
            optional_keys = {CONF_LOCKOUT_POSITION, CONF_SHADING_POSITION_ALT}
            for key in keys:
                if key in normalized and normalized[key] not in (None, ""):
                    settings[key] = normalized[key]
                elif key in submitted or key in optional_keys:
                    settings.pop(key, None)
            data[CONF_ROOM_SETTINGS] = settings
            return self.async_update_and_abort(self._get_entry(), subentry, data=data)

        return self.async_show_form(
            step_id="positions",
            data_schema=vol.Schema(
                {
                    vol.Optional("positions"): section(
                        vol.Schema(
                            {
                                vol.Required(
                                    CONF_OPEN_POSITION,
                                    default=_position_default(settings, CONF_OPEN_POSITION),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_CLOSE_POSITION,
                                    default=_position_default(settings, CONF_CLOSE_POSITION),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_SHADING_POSITION,
                                    default=_position_default(settings, CONF_SHADING_POSITION),
                                ): _position_number_selector(),
                                vol.Optional(
                                    CONF_SHADING_POSITION_ALT,
                                    default=_selector_default(settings.get(CONF_SHADING_POSITION_ALT)),
                                ): vol.Any(_position_number_selector(), None),
                                vol.Optional(
                                    CONF_SHADING_POSITION_ALT_ENTITY,
                                    default=_selector_default(settings.get(CONF_SHADING_POSITION_ALT_ENTITY)),
                                ): selector.EntitySelector(
                                    selector.EntitySelectorConfig(
                                        domain=["binary_sensor", "input_boolean"]
                                    )
                                ),
                                vol.Required(
                                    CONF_VENTILATE_POSITION,
                                    default=_position_default(settings, CONF_VENTILATE_POSITION),
                                ): _position_number_selector(),
                                vol.Optional(
                                    CONF_LOCKOUT_POSITION,
                                    default=_selector_default(settings.get(CONF_LOCKOUT_POSITION)),
                                ): vol.Any(_position_number_selector(), None),
                            }
                        ),
                        {"collapsed": False},
                    ),
                    vol.Optional("tilt_positions"): section(
                        vol.Schema(
                            {
                                vol.Required(
                                    CONF_OPEN_TILT_POSITION,
                                    default=_position_default(settings, CONF_OPEN_TILT_POSITION),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_CLOSE_TILT_POSITION,
                                    default=_position_default(settings, CONF_CLOSE_TILT_POSITION),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_SHADING_TILT_POSITION,
                                    default=_position_default(settings, CONF_SHADING_TILT_POSITION),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_VENTILATE_TILT_POSITION,
                                    default=_position_default(settings, CONF_VENTILATE_TILT_POSITION),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_SHADING_TILT_POSITION_0,
                                    default=_position_default(settings, CONF_SHADING_TILT_POSITION_0),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_SHADING_TILT_POSITION_1,
                                    default=_position_default(settings, CONF_SHADING_TILT_POSITION_1),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_SHADING_TILT_POSITION_2,
                                    default=_position_default(settings, CONF_SHADING_TILT_POSITION_2),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_SHADING_TILT_POSITION_3,
                                    default=_position_default(settings, CONF_SHADING_TILT_POSITION_3),
                                ): _position_number_selector(),
                            }
                        ),
                    ),
                }
            ),
            description_placeholders=self._room_context_placeholders(),
        )

    async def async_step_source_overrides(self, user_input=None) -> FlowResult:
        subentry = self._get_reconfigure_subentry()
        data = dict(subentry.data)
        overrides = dict(data.get(CONF_SOURCE_OVERRIDES, {}))
        if user_input is not None:
            data[CONF_SOURCE_OVERRIDES] = {
                key: value
                for key, value in user_input.items()
                if value not in (None, "")
            }
            return self.async_update_and_abort(
                self._get_entry(), subentry, data=data
            )
        schema = {}
        for key in sorted(ROOM_SOURCE_OVERRIDE_KEYS):
            current = overrides.get(key)
            marker = vol.Optional(
                key,
                description={"suggested_value": current} if current else None,
            )
            schema[marker] = selector.EntitySelector(selector.EntitySelectorConfig())
        return self.async_show_form(
            step_id="source_overrides",
            data_schema=vol.Schema(schema),
            description_placeholders=self._room_context_placeholders(),
        )

    def _store_profile_assignment(
        self,
        data: dict[str, Any],
        profiles: dict[str, Any],
        user_input: dict[str, Any],
    ) -> None:
        profile_id = user_input.get(CONF_ROOM_PROFILE_ID)
        if profile_id in (None, ""):
            data.pop(CONF_ROOM_PROFILE_ID, None)
            data[CONF_PROFILE_FUNCTIONS] = []
            data.pop(CONF_PROFILE_SELECTIONS, None)
            return
        data[CONF_ROOM_PROFILE_ID] = profile_id
        profile = profiles.get(profile_id, {})
        available = configured_functions_from_profile(profile)
        submitted = user_input.get(
            CONF_PROFILE_FUNCTIONS, data.get(CONF_PROFILE_FUNCTIONS, [])
        )
        if isinstance(submitted, dict):
            submitted = [
                function for function, enabled in submitted.items() if enabled
            ]
        data[CONF_PROFILE_FUNCTIONS] = sorted(
            function for function in submitted if function in available
        )
        data.pop(CONF_PROFILE_SELECTIONS, None)

    async def async_step_profile_assignment(self, user_input=None) -> FlowResult:
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        data = dict(subentry.data)
        profiles = entry.data.get(CONF_PROFILES, {})
        if user_input is not None:
            self._store_profile_assignment(data, profiles, user_input)
            return self.async_update_and_abort(entry, subentry, data=data)

        profile_options = [{"value": "", "label": "—"}]
        profile_options.extend(
            {
                "value": profile_id,
                "label": profile.get(CONF_PROFILE_NAME, profile_id),
            }
            for profile_id, profile in profiles.items()
            if profile_id not in PROFILE_TYPES
        )
        profile_id = data.get(CONF_ROOM_PROFILE_ID)
        profile = profiles.get(profile_id, {}) if profile_id else {}
        available = configured_functions_from_profile(profile)
        selected = data.get(CONF_PROFILE_FUNCTIONS, [])
        if isinstance(selected, dict):
            selected = [
                function for function, enabled in selected.items() if enabled
            ]
        current = sorted(function for function in selected if function in available)
        schema: dict = {
            vol.Optional(
                CONF_ROOM_PROFILE_ID,
                default=profile_id or "",
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=profile_options)
            )
        }
        if available:
            schema[
                vol.Optional(
                    CONF_PROFILE_FUNCTIONS,
                    default=current,
                )
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        function for function in PROFILE_FUNCTIONS if function in available
                    ],
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="profile_functions",
                )
            )
        return self.async_show_form(
            step_id="profile_assignment",
            data_schema=vol.Schema(schema),
            description_placeholders=self._room_context_placeholders(),
        )

    async def async_step_profile_references(self, user_input=None) -> FlowResult:
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        data = dict(subentry.data)
        profiles = entry.data.get(CONF_PROFILES, {})
        if user_input is not None:
            self._store_profile_assignment(data, profiles, user_input)
            return self.async_update_and_abort(
                entry, subentry, data=data
            )
        options = [
            {
                "value": profile_id,
                "label": profile.get(CONF_PROFILE_NAME, profile_id),
            }
            for profile_id, profile in profiles.items()
            if profile_id not in PROFILE_TYPES
        ]
        current = data.get(CONF_ROOM_PROFILE_ID)
        schema = {
            vol.Optional(
                CONF_ROOM_PROFILE_ID,
                description={"suggested_value": current} if current else None,
            ): selector.SelectSelector(selector.SelectSelectorConfig(options=options))
        }
        return self.async_show_form(
            step_id="profile_references",
            data_schema=vol.Schema(schema),
            description_placeholders=self._room_context_placeholders(),
        )

    async def async_step_profile_functions(self, user_input=None) -> FlowResult:
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        data = dict(subentry.data)
        profile_id = data.get(CONF_ROOM_PROFILE_ID)
        if not profile_id:
            return self.async_abort(reason="profile_required_for_functions")
        profile = effective_profile(
            {CONF_PROFILES: entry.data.get(CONF_PROFILES, {})},
            {CONF_ROOM_PROFILE_ID: profile_id},
        )
        available = configured_functions_from_profile(profile)
        if not available:
            return self.async_abort(reason="profile_has_no_functions")
        selected = data.get(CONF_PROFILE_FUNCTIONS, [])
        if isinstance(selected, dict):
            selected = [
                function for function, enabled in selected.items() if enabled
            ]
        current = sorted(function for function in selected if function in available)
        if user_input is not None:
            submitted = user_input.get(CONF_PROFILE_FUNCTIONS, [])
            data[CONF_PROFILE_FUNCTIONS] = sorted(
                function for function in submitted if function in available
            )
            return self.async_update_and_abort(entry, subentry, data=data)
        options = [
            function for function in PROFILE_FUNCTIONS if function in available
        ]
        return self.async_show_form(
            step_id="profile_functions",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PROFILE_FUNCTIONS,
                        default=current,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="profile_functions",
                        )
                    )
                }
            ),
            description_placeholders=self._room_context_placeholders(),
        )
