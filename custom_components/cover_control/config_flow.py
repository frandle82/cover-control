"""Config and options flow for Cover Control."""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from collections import OrderedDict
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_SHADING,
    CONF_AUTO_SUN,
    CONF_AUTO_VENTILATE,
    CONF_ADDITIONAL_CONDITION_CLOSE,
    CONF_ADDITIONAL_CONDITION_GLOBAL,
    CONF_ADDITIONAL_CONDITION_OPEN,
    CONF_ADDITIONAL_CONDITION_SHADING,
    CONF_ADDITIONAL_CONDITION_SHADING_END,
    CONF_ADDITIONAL_CONDITION_SHADING_TILT,
    CONF_ADDITIONAL_CONDITION_VENTILATE,
    CONF_ADDITIONAL_CONDITION_VENTILATE_END,
    CONF_COLD_PROTECTION_FORECAST_SENSOR,
    CONF_COLD_PROTECTION_THRESHOLD,
    CONF_BRIGHTNESS_CLOSE_BELOW,
    CONF_BRIGHTNESS_OPEN_ABOVE,
    CONF_BRIGHTNESS_SENSOR,
    CONF_CONTACT_STATUS_DELAY,
    CONF_CONTACT_TRIGGER_DELAY,
    CONF_CLOSE_POSITION,
    CONF_COVERS,
    CONF_EXPOSE_SWITCH_SETTINGS,
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
    CONF_OPEN_POSITION,
    CONF_POSITION_TOLERANCE,
    CONF_RESIDENT_SENSOR,
    CONF_SHADING_FORECAST_SENSOR,
    CONF_SHADING_FORECAST_TYPE,
    CONF_SHADING_WEATHER_CONDITIONS,
    CONF_SHADING_BRIGHTNESS_END,
    CONF_SHADING_BRIGHTNESS_START,
    CONF_SHADING_POSITION,
    CONF_SUN_AZIMUTH_END,
    CONF_SUN_AZIMUTH_START,
    CONF_SUN_ELEVATION_CLOSE,
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
    CONF_VENTILATION_USE_AFTER_SHADING,
    CONF_VENTILATE_POSITION,
    CONF_WINDOW_SENSOR_FULL,
    CONF_WINDOW_SENSOR_TILT,
    CONF_WORKDAY_SENSOR,
    DEFAULT_CONTACT_SETTINGS,
    DEFAULT_AUTOMATION_FLAGS,
    DEFAULT_BRIGHTNESS_CLOSE,
    DEFAULT_BRIGHTNESS_OPEN,
    DEFAULT_COLD_PROTECTION_THRESHOLD,
    DEFAULT_MANUAL_OVERRIDE_MINUTES,
    DEFAULT_MANUAL_OVERRIDE_FLAGS,
    DEFAULT_MANUAL_OVERRIDE_RESET_TIME,
    DEFAULT_MASTER_FLAGS,
    DEFAULT_NAME,
    DEFAULT_POSITION_SETTINGS,
    DEFAULT_SHADING_AZIMUTH_END,
    DEFAULT_SHADING_AZIMUTH_START,
    DEFAULT_SHADING_BRIGHTNESS_END,
    DEFAULT_SHADING_BRIGHTNESS_START,
    DEFAULT_SHADING_FORECAST_TYPE,
    DEFAULT_SHADING_ELEVATION_MAX,
    DEFAULT_SHADING_ELEVATION_MIN,
    DEFAULT_SUN_ELEVATION_CLOSE,
    DEFAULT_SUN_ELEVATION_OPEN,
    DEFAULT_TIME_SETTINGS,
    DEFAULT_TEMPERATURE_FORECAST_THRESHOLD,
    DEFAULT_TEMPERATURE_THRESHOLD,
    DEFAULT_TOLERANCE,
    DEFAULT_COLD_PROTECTION_THRESHOLD,
    DEFAULT_CONTACT_TRIGGER_DELAY,
    DEFAULT_CONTACT_STATUS_DELAY,
    DEFAULT_VENTILATION_DELAY_AFTER_CLOSE,
    DOMAIN,
    MANUAL_OVERRIDE_RESET_NONE,
    MANUAL_OVERRIDE_RESET_TIME,
    MANUAL_OVERRIDE_RESET_TIMEOUT,
    
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
        **config,
    }


def _selector_default(value: Any) -> Any:
    """Return a safe selector default, skipping None/empty placeholders."""

    if value in (None, "", vol.UNDEFINED):
        return vol.UNDEFINED
    return value


LOGGER = logging.getLogger(__name__)


def _time_default(value, fallback: str | None = None):
    """Return a time object for selectors, falling back safely."""

    for candidate in (value, fallback):
        if candidate in (None, "", vol.UNDEFINED):
            continue
        parsed = dt_util.parse_time(str(candidate))
        if parsed:
            return parsed
    return vol.UNDEFINED


class ShutterControlFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_windows()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_COVERS): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["cover"], multiple=True)
                    ),
                }
            ),
        )

    async def async_step_windows(self, user_input=None) -> FlowResult:
        covers: list[str] = self._data.get(CONF_COVERS, [])
        if user_input is not None:
            full_map: dict[str, list[str]] = {}
            tilt_map: dict[str, list[str]] = {}
            for cover in covers:
                full_sensors = user_input.get(self._cover_full_key(cover), [])
                full_map[cover] = [
                    sensor for sensor in full_sensors if isinstance(sensor, str) and sensor
                ]

                tilt_sensors = user_input.get(self._cover_tilt_key(cover), [])
                tilt_map[cover] = [
                    sensor for sensor in tilt_sensors if isinstance(sensor, str) and sensor
                ]
            self._data[CONF_WINDOW_SENSOR_FULL] = full_map
            self._data[CONF_WINDOW_SENSOR_TILT] = tilt_map
            return await self.async_step_schedule()

        return self.async_show_form(
            step_id="windows",
            data_schema=self._build_windows_schema(covers),
        )

    async def async_step_schedule(self, user_input=None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_shading()

        return self.async_show_form(
            step_id="schedule",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_WORKDAY_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["binary_sensor", "sensor"])
                    ),
                    vol.Optional(CONF_RESIDENT_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["binary_sensor", "switch"])
                    ),
                    vol.Optional(
                        CONF_CONTACT_TRIGGER_DELAY,
                        default=self._data.get(
                            CONF_CONTACT_TRIGGER_DELAY, DEFAULT_CONTACT_TRIGGER_DELAY
                        ),
                    ): vol.Coerce(int),
                    vol.Optional(
                        CONF_CONTACT_STATUS_DELAY,
                        default=self._data.get(
                            CONF_CONTACT_STATUS_DELAY, DEFAULT_CONTACT_STATUS_DELAY
                        ),
                    ): vol.Coerce(int),
                    vol.Optional(
                        CONF_VENTILATION_DELAY_AFTER_CLOSE,
                        default=self._data.get(
                            CONF_VENTILATION_DELAY_AFTER_CLOSE,
                            DEFAULT_VENTILATION_DELAY_AFTER_CLOSE,
                        ),
                    ): vol.Coerce(int),
                    vol.Optional(
                        CONF_VENTILATION_ALLOW_HIGHER_POSITION,
                        default=bool(
                            self._data.get(
                                CONF_VENTILATION_ALLOW_HIGHER_POSITION,
                                DEFAULT_CONTACT_SETTINGS[CONF_VENTILATION_ALLOW_HIGHER_POSITION],
                            )
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_VENTILATION_USE_AFTER_SHADING,
                        default=bool(
                            self._data.get(
                                CONF_VENTILATION_USE_AFTER_SHADING,
                                DEFAULT_CONTACT_SETTINGS[CONF_VENTILATION_USE_AFTER_SHADING],
                            )
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_LOCKOUT_TILT_CLOSE,
                        default=bool(
                            self._data.get(
                                CONF_LOCKOUT_TILT_CLOSE,
                                DEFAULT_CONTACT_SETTINGS[CONF_LOCKOUT_TILT_CLOSE],
                            )
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_LOCKOUT_TILT_SHADING_START,
                        default=bool(
                            self._data.get(
                                CONF_LOCKOUT_TILT_SHADING_START,
                                DEFAULT_CONTACT_SETTINGS[CONF_LOCKOUT_TILT_SHADING_START],
                            )
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_LOCKOUT_TILT_SHADING_END,
                        default=bool(
                            self._data.get(
                                CONF_LOCKOUT_TILT_SHADING_END,
                                DEFAULT_CONTACT_SETTINGS[CONF_LOCKOUT_TILT_SHADING_END],
                            )
                        ),
                    ): bool,
                    vol.Optional(CONF_BRIGHTNESS_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"],device_class=["illuminance"])
                    ),
                    vol.Optional(CONF_TEMPERATURE_SENSOR_INDOOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"])
                    ),
                    vol.Optional(CONF_TEMPERATURE_SENSOR_OUTDOOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"])
                    ),
                    vol.Optional(
                        CONF_TEMPERATURE_THRESHOLD, default=DEFAULT_TEMPERATURE_THRESHOLD
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_TEMPERATURE_FORECAST_THRESHOLD, default=DEFAULT_TEMPERATURE_FORECAST_THRESHOLD
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_COLD_PROTECTION_THRESHOLD, default=DEFAULT_COLD_PROTECTION_THRESHOLD
                    ): vol.Coerce(float),
                    vol.Optional(CONF_COLD_PROTECTION_FORECAST_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor", "weather"])
                    ),
                    vol.Optional(
                        CONF_TIME_UP_EARLY_WORKDAY,
                        default=_time_default(
                            self._data.get(CONF_TIME_UP_EARLY_WORKDAY),
                            DEFAULT_TIME_SETTINGS[CONF_TIME_UP_EARLY_WORKDAY],
                        ),
                    ): selector.TimeSelector(),
                    vol.Optional(
                        CONF_TIME_UP_EARLY_NON_WORKDAY,
                        default=_time_default(
                            self._data.get(CONF_TIME_UP_EARLY_NON_WORKDAY),
                            DEFAULT_TIME_SETTINGS[CONF_TIME_UP_EARLY_NON_WORKDAY],
                        ),
                    ): selector.TimeSelector(),
                    vol.Optional(
                        CONF_TIME_UP_LATE_WORKDAY,
                        default=_time_default(
                            self._data.get(CONF_TIME_UP_LATE_WORKDAY),
                            DEFAULT_TIME_SETTINGS[CONF_TIME_UP_LATE_WORKDAY],
                        ),
                    ): selector.TimeSelector(),
                    vol.Optional(
                        CONF_TIME_UP_LATE_NON_WORKDAY,
                        default=_time_default(
                            self._data.get(CONF_TIME_UP_LATE_NON_WORKDAY),
                            DEFAULT_TIME_SETTINGS[CONF_TIME_UP_LATE_NON_WORKDAY],
                        ),
                    ): selector.TimeSelector(),
                    vol.Optional(
                        CONF_TIME_DOWN_EARLY_WORKDAY,
                        default=_time_default(
                            self._data.get(CONF_TIME_DOWN_EARLY_WORKDAY),
                            DEFAULT_TIME_SETTINGS[CONF_TIME_DOWN_EARLY_WORKDAY],
                        ),
                    ): selector.TimeSelector(),
                    vol.Optional(
                        CONF_TIME_DOWN_EARLY_NON_WORKDAY,
                        default=_time_default(
                            self._data.get(CONF_TIME_DOWN_EARLY_NON_WORKDAY),
                            DEFAULT_TIME_SETTINGS[CONF_TIME_DOWN_EARLY_NON_WORKDAY],
                        ),
                    ): selector.TimeSelector(),
                    vol.Optional(
                        CONF_TIME_DOWN_LATE_WORKDAY,
                        default=_time_default(
                            self._data.get(CONF_TIME_DOWN_LATE_WORKDAY),
                            DEFAULT_TIME_SETTINGS[CONF_TIME_DOWN_LATE_WORKDAY],
                        ),
                    ): selector.TimeSelector(),   
                    vol.Optional(
                        CONF_TIME_DOWN_LATE_NON_WORKDAY,
                        default=_time_default(
                            self._data.get(CONF_TIME_DOWN_LATE_NON_WORKDAY),
                            DEFAULT_TIME_SETTINGS[CONF_TIME_DOWN_LATE_NON_WORKDAY],
                        ),
                    ): selector.TimeSelector(),
                    vol.Optional(
                        CONF_OPEN_POSITION,
                        default=self._data.get(
                            CONF_OPEN_POSITION, DEFAULT_POSITION_SETTINGS[CONF_OPEN_POSITION]
                        ),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_CLOSE_POSITION,
                        default=self._data.get(
                            CONF_CLOSE_POSITION, DEFAULT_POSITION_SETTINGS[CONF_CLOSE_POSITION]
                        ),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_VENTILATE_POSITION,
                        default=self._data.get(
                            CONF_VENTILATE_POSITION,
                            DEFAULT_POSITION_SETTINGS[CONF_VENTILATE_POSITION],
                        ),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_SHADING_POSITION,
                        default=self._data.get(
                            CONF_SHADING_POSITION, DEFAULT_POSITION_SETTINGS[CONF_SHADING_POSITION]
                        ),
                    ): vol.Coerce(float),
                }
            ),
        )

    async def async_step_shading(self, user_input=None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_finalize()

        return self.async_show_form(
            step_id="shading",
            data_schema=vol.Schema(
                {

                    vol.Optional(CONF_BRIGHTNESS_OPEN_ABOVE, default=DEFAULT_BRIGHTNESS_OPEN): vol.Coerce(float),
                    vol.Optional(CONF_BRIGHTNESS_CLOSE_BELOW, default=DEFAULT_BRIGHTNESS_CLOSE): vol.Coerce(float),
                    vol.Optional(CONF_SUN_ELEVATION_OPEN, default=DEFAULT_SUN_ELEVATION_OPEN): vol.Coerce(float),
                    vol.Optional(CONF_SUN_ELEVATION_CLOSE, default=DEFAULT_SUN_ELEVATION_CLOSE): vol.Coerce(float),
                    vol.Optional(CONF_SUN_AZIMUTH_START, default=DEFAULT_SHADING_AZIMUTH_START): vol.Coerce(float),
                    vol.Optional(CONF_SUN_AZIMUTH_END, default=DEFAULT_SHADING_AZIMUTH_END): vol.Coerce(float),
                    vol.Optional(CONF_SUN_ELEVATION_MIN, default=DEFAULT_SHADING_ELEVATION_MIN): vol.Coerce(float),
                    vol.Optional(CONF_SUN_ELEVATION_MAX, default=DEFAULT_SHADING_ELEVATION_MAX): vol.Coerce(float),
                    vol.Optional(CONF_SHADING_BRIGHTNESS_START, default=DEFAULT_SHADING_BRIGHTNESS_START): vol.Coerce(float),
                    vol.Optional(CONF_SHADING_BRIGHTNESS_END, default=DEFAULT_SHADING_BRIGHTNESS_END): vol.Coerce(float),
                    vol.Optional(CONF_SHADING_FORECAST_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor", "weather"])
                    ),
                    vol.Optional(
                        CONF_SHADING_FORECAST_TYPE,
                        default=DEFAULT_SHADING_FORECAST_TYPE,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": "daily", "label": "Use the daily weather forecast service"},
                                {"value": "hourly", "label": "Use the hourly weather forecast service"},
                                {
                                    "value": "weather_attributes",
                                    "label": "Do not use a weather forecast, but the current weather attributes",
                                },
                            ]
                        )
                    ),
                    vol.Optional(CONF_SHADING_WEATHER_CONDITIONS, default=[]): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                "clear-night",
                                "cloudy",
                                "exceptional",
                                "fog",
                                "hail",
                                "lightning",
                                "lightning-rainy",
                                "partlycloudy",
                                "pouring",
                                "rainy",
                                "snowy",
                                "snowy-rainy",
                                "sunny",
                                "windy",
                                "windy-variant",
                            ],
                            multiple=True,
                        )
                    ),
                    vol.Optional(CONF_MANUAL_OVERRIDE_RESET_MODE, default=self._data.get(CONF_MANUAL_OVERRIDE_RESET_MODE, MANUAL_OVERRIDE_RESET_TIMEOUT)): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": MANUAL_OVERRIDE_RESET_NONE, "label": "No timed reset"},
                                {"value": MANUAL_OVERRIDE_RESET_TIME, "label": "Reset at specific time"},
                                {"value": MANUAL_OVERRIDE_RESET_TIMEOUT, "label": "Reset after timeout (minutes)"},
                            ]
                        )
                    ),
                    vol.Optional(
                        CONF_MANUAL_OVERRIDE_RESET_TIME,
                        default=_time_default(
                            self._data.get(
                                CONF_MANUAL_OVERRIDE_RESET_TIME,
                                DEFAULT_MANUAL_OVERRIDE_RESET_TIME,
                            ),
                            DEFAULT_MANUAL_OVERRIDE_RESET_TIME,
                        ),
                    ): selector.TimeSelector(),
                    vol.Optional(CONF_MANUAL_OVERRIDE_MINUTES, default=self._data.get(CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES)): vol.Coerce(int),
                    vol.Optional(CONF_MANUAL_OVERRIDE_BLOCK_OPEN, default=self._data.get(CONF_MANUAL_OVERRIDE_BLOCK_OPEN, DEFAULT_MANUAL_OVERRIDE_FLAGS[CONF_MANUAL_OVERRIDE_BLOCK_OPEN])): bool,
                    vol.Optional(CONF_MANUAL_OVERRIDE_BLOCK_CLOSE, default=self._data.get(CONF_MANUAL_OVERRIDE_BLOCK_CLOSE, DEFAULT_MANUAL_OVERRIDE_FLAGS[CONF_MANUAL_OVERRIDE_BLOCK_CLOSE])): bool,
                    vol.Optional(CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE, default=self._data.get(CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE, DEFAULT_MANUAL_OVERRIDE_FLAGS[CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE])): bool,
                    vol.Optional(CONF_MANUAL_OVERRIDE_BLOCK_SHADING, default=self._data.get(CONF_MANUAL_OVERRIDE_BLOCK_SHADING, DEFAULT_MANUAL_OVERRIDE_FLAGS[CONF_MANUAL_OVERRIDE_BLOCK_SHADING])): bool,
                }
            ),
        )

    async def async_step_finalize(self, user_input=None) -> FlowResult:
        if user_input:
            self._data.update(user_input)
        name = self._data.get(CONF_NAME, DEFAULT_NAME).strip() or DEFAULT_NAME
        data = _with_config_defaults(self._data)
        return self.async_create_entry(title=name, data=data)

    def _cover_full_key(self, cover: str) -> str:
        state = self.hass.states.get(cover)
        friendly_name = state.name if state else cover.split(".")[-1]
        return f"Voll geöffnet Sensor(e) für {friendly_name}"

    def _cover_tilt_key(self, cover: str) -> str:
        state = self.hass.states.get(cover)
        friendly_name = state.name if state else cover.split(".")[-1]
        return f"Kipp-Sensor(e) für {friendly_name}"

    def _existing_full_contacts_for_cover(self, cover: str) -> list[str]:
        mapping = self._data.get(CONF_WINDOW_SENSOR_FULL) or {}
        sensors = mapping.get(cover, [])
        if isinstance(sensors, str):
            return [sensors]
        return sensors if isinstance(sensors, list) else []

    def _existing_tilt_contacts_for_cover(self, cover: str) -> list[str]:
        mapping = self._data.get(CONF_WINDOW_SENSOR_TILT) or {}
        sensors = mapping.get(cover, [])
        if isinstance(sensors, str):
            return [sensors]
        return sensors if isinstance(sensors, list) else []

    def _build_windows_schema(self, covers: list[str]) -> vol.Schema:
        """Build the windows step schema using ordered fields per cover."""
        
        multi_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=["binary_sensor"],
                device_class=["window", "door", "opening"],
                multiple=True,
            )
        )

        fields: dict[Any, Any] = OrderedDict()

        for cover in covers:
            fields[vol.Optional(
                self._cover_full_key(cover),
                default=_selector_default(
                    self._existing_full_contacts_for_cover(cover)
                ),
            )] = multi_selector
            fields[vol.Optional(
                self._cover_tilt_key(cover),
                default=_selector_default(
                    self._existing_tilt_contacts_for_cover(cover)
                ),
            )] = multi_selector

        return vol.Schema(fields)
    
    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return ShutterOptionsFlow(config_entry)


class ShutterOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow."""

    _CLEARABLE_OPTION_KEYS = {
        CONF_ADDITIONAL_CONDITION_GLOBAL,
        CONF_ADDITIONAL_CONDITION_OPEN,
        CONF_ADDITIONAL_CONDITION_CLOSE,
        CONF_ADDITIONAL_CONDITION_VENTILATE,
        CONF_ADDITIONAL_CONDITION_VENTILATE_END,
        CONF_ADDITIONAL_CONDITION_SHADING,
        CONF_ADDITIONAL_CONDITION_SHADING_TILT,
        CONF_ADDITIONAL_CONDITION_SHADING_END,
    }

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._options = self._normalize_options(config_entry)

    def _clean_user_input(self, user_input: dict) -> dict:
        """Drop empty selector values while keeping valid falsy values."""
        
        def _json_safe(value: Any) -> Any:
            """Convert selector results to JSON-serialisable primitives."""

            if isinstance(value, (datetime, date)):
                return value.isoformat()
            if isinstance(value, time):
                return value.isoformat()
            if isinstance(value, timedelta):
                return value.total_seconds()
            if isinstance(value, list | tuple):
                return [_json_safe(item) for item in value]
            if isinstance(value, dict):
                return {key: _json_safe(val) for key, val in value.items()}
            return value
        
        cleaned: dict = {}
        for key, value in user_input.items():
            if value in ("", vol.UNDEFINED, []):
                if key in self._CLEARABLE_OPTION_KEYS:
                    cleaned[key] = None
                continue
            if value is None:
                if key in self._CLEARABLE_OPTION_KEYS:
                    cleaned[key] = None
                continue
            cleaned[key] = _json_safe(value)
        
        for key in self._CLEARABLE_OPTION_KEYS:
            # If the UI omits a clearable selector entirely (e.g. after manual removal),
            # treat it as an explicit request to clear the stored value.
            if key not in cleaned:
                cleaned[key] = None
        return cleaned

    def _optional_default(self, key: str):
        """Return a safe default for optional selectors."""

        if key not in self._options:
            return vol.UNDEFINED
        
        value = self._options.get(key)
        if value in (None, "", vol.UNDEFINED):
            return vol.UNDEFINED
        return value


    def _sanitize_options(self, options: dict) -> dict:
        """Remove empty selector placeholders from stored options."""

        return {
            key: value
            for key, value in options.items()
            if value not in (None, "", vol.UNDEFINED)
        }

    def _normalize_options(
        self, config_entry: config_entries.ConfigEntry | None, overrides: dict | None = None
    ) -> dict:
        """Merge stored data/options with defaults, overrides, and sanitize them."""


        merged: dict = {}
        if config_entry:
            merged.update(dict(config_entry.data or {}))
            merged.update(dict(config_entry.options or {}))

        merged = _with_config_defaults(merged)
        if overrides:
            merged.update(overrides)
        sanitized = self._sanitize_options(merged)

        covers = sanitized.get(CONF_COVERS, [])
        if not isinstance(covers, list):
            covers = list(covers) if covers else []
        sanitized[CONF_COVERS] = covers

        full_contacts = sanitized.get(CONF_WINDOW_SENSOR_FULL, {})
        if not isinstance(full_contacts, dict):
            full_contacts = {}
        sanitized[CONF_WINDOW_SENSOR_FULL] = {
            cover: [sensors]
            if isinstance(sensors, str)
            else sensors
            if isinstance(sensors, list)
            else []
            for cover, sensors in full_contacts.items()
            if cover
        }

        tilt_contacts = sanitized.get(CONF_WINDOW_SENSOR_TILT, {})
        if not isinstance(tilt_contacts, dict):
            tilt_contacts = {}
        sanitized[CONF_WINDOW_SENSOR_TILT] = {
            cover: [sensors]
            if isinstance(sensors, str)
            else sensors
            if isinstance(sensors, list)
            else []
            for cover, sensors in tilt_contacts.items()
            if cover
        }

        return sanitized

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            clean_input = self._clean_user_input(user_input)

            name = clean_input.pop(CONF_NAME, self._config_entry.title).strip() or DEFAULT_NAME
            covers = clean_input.get(CONF_COVERS, self._options.get(CONF_COVERS, []))
            full_mapping: dict[str, list[str]] = {}
            tilt_mapping: dict[str, list[str]] = {}
            for cover in covers:
                full_mapping[cover] = [
                    sensor
                    for sensor in clean_input.get(
                        self._cover_full_key(cover),
                        self._existing_full_contacts_for_cover(cover),
                    ) 
                    if isinstance(sensor, str) and sensor
                ]

                tilt_mapping[cover] = [
                    sensor
                    for sensor in clean_input.get(
                        self._cover_tilt_key(cover),
                        self._existing_tilt_contacts_for_cover(cover),
                    )
                    if isinstance(sensor, str) and sensor
                ]
            clean_input[CONF_WINDOW_SENSOR_FULL] = full_mapping
            clean_input[CONF_WINDOW_SENSOR_TILT] = tilt_mapping
            overrides = {CONF_NAME: name} | clean_input
            try:
                self._options = self._normalize_options(self._config_entry, overrides)
            except Exception:  # pragma: no cover - defensive fallback for HA runtime
                _LOGGER.exception("Failed to normalize Cover Control options")
                merged = {
                    **(self._config_entry.data or {}),
                    **(self._config_entry.options or {}),
                    **overrides,
                }
                self._options = self._sanitize_options(
                    _with_config_defaults(merged)
                )
            self.hass.config_entries.async_update_entry(self._config_entry, title=name)
            return self.async_create_entry(title="", data=self._options)

        auto_brightness = bool(self._options.get(CONF_AUTO_BRIGHTNESS, True))
        auto_sun = bool(self._options.get(CONF_AUTO_SUN, True))
        auto_ventilate = bool(self._options.get(CONF_AUTO_VENTILATE, True))
        auto_shading = bool(self._options.get(CONF_AUTO_SHADING, True))

        condition_selector = selector.ConditionSelector()

        schema: dict = {
            vol.Optional(CONF_NAME, default=self._options.get(CONF_NAME, self._config_entry.title or DEFAULT_NAME)): str,
            vol.Required(CONF_COVERS, default=self._options.get(CONF_COVERS, [])): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["cover"], multiple=True)
            ),
            vol.Optional(
                CONF_TIME_UP_EARLY_WORKDAY,
                default=_time_default(
                    self._options.get(
                        CONF_TIME_UP_EARLY_WORKDAY,
                        DEFAULT_TIME_SETTINGS[CONF_TIME_UP_EARLY_WORKDAY],
                    )
                ),
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_TIME_UP_EARLY_NON_WORKDAY,
                default=_time_default(
                    self._options.get(
                        CONF_TIME_UP_EARLY_NON_WORKDAY,
                        DEFAULT_TIME_SETTINGS[CONF_TIME_UP_EARLY_NON_WORKDAY],
                    )
                ),
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_TIME_UP_LATE_WORKDAY,
                default=_time_default(
                    self._options.get(
                        CONF_TIME_UP_LATE_WORKDAY,
                        DEFAULT_TIME_SETTINGS[CONF_TIME_UP_LATE_WORKDAY],
                    )
                ),
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_TIME_UP_LATE_NON_WORKDAY,
                default=_time_default(
                    self._options.get(
                        CONF_TIME_UP_LATE_NON_WORKDAY,
                        DEFAULT_TIME_SETTINGS[CONF_TIME_UP_LATE_NON_WORKDAY],
                    )
                ),
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_TIME_DOWN_EARLY_WORKDAY,
                default=_time_default(
                    self._options.get(
                        CONF_TIME_DOWN_EARLY_WORKDAY,
                        DEFAULT_TIME_SETTINGS[CONF_TIME_DOWN_EARLY_WORKDAY],
                    )
                ),
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_TIME_DOWN_EARLY_NON_WORKDAY,
                default=_time_default(
                    self._options.get(
                        CONF_TIME_DOWN_EARLY_NON_WORKDAY,
                        DEFAULT_TIME_SETTINGS[CONF_TIME_DOWN_EARLY_NON_WORKDAY],
                    )
                ),
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_TIME_DOWN_LATE_WORKDAY,
                default=_time_default(
                    self._options.get(
                        CONF_TIME_DOWN_LATE_WORKDAY,
                        DEFAULT_TIME_SETTINGS[CONF_TIME_DOWN_LATE_WORKDAY],
                    )
                ),
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_TIME_DOWN_LATE_NON_WORKDAY,
                default=_time_default(
                    self._options.get(
                        CONF_TIME_DOWN_LATE_NON_WORKDAY,
                        DEFAULT_TIME_SETTINGS[CONF_TIME_DOWN_LATE_NON_WORKDAY],
                    )
                ),
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_POSITION_TOLERANCE,
                default=self._options.get(CONF_POSITION_TOLERANCE, DEFAULT_TOLERANCE),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_OPEN_POSITION,
                default=self._options.get(
                    CONF_OPEN_POSITION, DEFAULT_POSITION_SETTINGS[CONF_OPEN_POSITION]
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional(
                CONF_CLOSE_POSITION,
                default=self._options.get(
                    CONF_CLOSE_POSITION, DEFAULT_POSITION_SETTINGS[CONF_CLOSE_POSITION]
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional(
                CONF_VENTILATE_POSITION,
                default=self._options.get(
                    CONF_VENTILATE_POSITION,
                    DEFAULT_POSITION_SETTINGS[CONF_VENTILATE_POSITION],
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional(
                CONF_SHADING_POSITION,
                default=self._options.get(
                    CONF_SHADING_POSITION, DEFAULT_POSITION_SETTINGS[CONF_SHADING_POSITION]
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional(
                CONF_EXPOSE_SWITCH_SETTINGS,
                default=bool(self._options.get(CONF_EXPOSE_SWITCH_SETTINGS, False)),
            ): bool,
            vol.Optional(
                CONF_CONTACT_TRIGGER_DELAY,
                default=self._options.get(
                    CONF_CONTACT_TRIGGER_DELAY, DEFAULT_CONTACT_TRIGGER_DELAY
                ),
            ): vol.Coerce(int),
            vol.Optional(
                CONF_CONTACT_STATUS_DELAY,
                default=self._options.get(
                    CONF_CONTACT_STATUS_DELAY, DEFAULT_CONTACT_STATUS_DELAY
                ),
            ): vol.Coerce(int),
            vol.Optional(
                CONF_VENTILATION_DELAY_AFTER_CLOSE,
                default=self._options.get(
                    CONF_VENTILATION_DELAY_AFTER_CLOSE, DEFAULT_VENTILATION_DELAY_AFTER_CLOSE
                ),
            ): vol.Coerce(int),
            vol.Optional(
                CONF_VENTILATION_ALLOW_HIGHER_POSITION,
                default=bool(
                    self._options.get(
                        CONF_VENTILATION_ALLOW_HIGHER_POSITION,
                        DEFAULT_CONTACT_SETTINGS[CONF_VENTILATION_ALLOW_HIGHER_POSITION],
                    )
                ),
            ): bool,
            vol.Optional(
                CONF_VENTILATION_USE_AFTER_SHADING,
                default=bool(
                    self._options.get(
                        CONF_VENTILATION_USE_AFTER_SHADING,
                        DEFAULT_CONTACT_SETTINGS[CONF_VENTILATION_USE_AFTER_SHADING],
                    )
                ),
            ): bool,
            vol.Optional(
                CONF_LOCKOUT_TILT_CLOSE,
                default=bool(
                    self._options.get(
                        CONF_LOCKOUT_TILT_CLOSE, DEFAULT_CONTACT_SETTINGS[CONF_LOCKOUT_TILT_CLOSE]
                    )
                ),
            ): bool,
            vol.Optional(
                CONF_LOCKOUT_TILT_SHADING_START,
                default=bool(
                    self._options.get(
                        CONF_LOCKOUT_TILT_SHADING_START,
                        DEFAULT_CONTACT_SETTINGS[CONF_LOCKOUT_TILT_SHADING_START],
                    )
                ),
            ): bool,
            vol.Optional(
                CONF_LOCKOUT_TILT_SHADING_END,
                default=bool(
                    self._options.get(
                        CONF_LOCKOUT_TILT_SHADING_END,
                        DEFAULT_CONTACT_SETTINGS[CONF_LOCKOUT_TILT_SHADING_END],
                    )
                ),
            ): bool,
            vol.Optional(
                CONF_ADDITIONAL_CONDITION_GLOBAL,
                default=self._optional_default(CONF_ADDITIONAL_CONDITION_GLOBAL),
            ): condition_selector,
            vol.Optional(
                CONF_ADDITIONAL_CONDITION_OPEN,
                default=self._optional_default(CONF_ADDITIONAL_CONDITION_OPEN),
            ): condition_selector,
            vol.Optional(
                CONF_ADDITIONAL_CONDITION_CLOSE,
                default=self._optional_default(CONF_ADDITIONAL_CONDITION_CLOSE),
            ): condition_selector,
            vol.Optional(
                CONF_ADDITIONAL_CONDITION_VENTILATE,
                default=self._optional_default(CONF_ADDITIONAL_CONDITION_VENTILATE),
            ): condition_selector,
            vol.Optional(
                CONF_ADDITIONAL_CONDITION_VENTILATE_END,
                default=self._optional_default(CONF_ADDITIONAL_CONDITION_VENTILATE_END),
            ): condition_selector,
            vol.Optional(
                CONF_ADDITIONAL_CONDITION_SHADING,
                default=self._optional_default(CONF_ADDITIONAL_CONDITION_SHADING),
            ): condition_selector,
            vol.Optional(
                CONF_ADDITIONAL_CONDITION_SHADING_TILT,
                default=self._optional_default(CONF_ADDITIONAL_CONDITION_SHADING_TILT),
            ): condition_selector,
            vol.Optional(
                CONF_ADDITIONAL_CONDITION_SHADING_END,
                default=self._optional_default(CONF_ADDITIONAL_CONDITION_SHADING_END),
            ): condition_selector,
        }
        if auto_ventilate:  
            multi_selector = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["binary_sensor"],
                    device_class=["window", "door", "opening"],
                    multiple=True,
                )
            )
            schema.update(
                {
                    **{
                        vol.Optional(
                            self._cover_full_key(cover),
                            default=_selector_default(
                                self._existing_full_contacts_for_cover(cover)    
                            ),
                        ): multi_selector
                        for cover in self._options.get(CONF_COVERS, [])
                        },
                    **{
                        vol.Optional(
                            self._cover_tilt_key(cover),
                            default=_selector_default(
                                self._existing_tilt_contacts_for_cover(cover)
                            ),
                        ): multi_selector
                        for cover in self._options.get(CONF_COVERS, [])
                        },
                    }
                )
            schema.update(
                {
                vol.Optional(
                    CONF_RESIDENT_SENSOR, default=self._optional_default(CONF_RESIDENT_SENSOR)
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["binary_sensor", "switch"])
                ),
                vol.Optional(
                    CONF_WORKDAY_SENSOR, default=self._optional_default(CONF_WORKDAY_SENSOR)
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["binary_sensor", "sensor"])
                ),
                vol.Optional(
                    CONF_MANUAL_OVERRIDE_RESET_MODE,
                    default=self._options.get(CONF_MANUAL_OVERRIDE_RESET_MODE, MANUAL_OVERRIDE_RESET_TIMEOUT),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": MANUAL_OVERRIDE_RESET_NONE, "label": "No timed reset"},
                            {"value": MANUAL_OVERRIDE_RESET_TIME, "label": "Reset at specific time"},
                            {"value": MANUAL_OVERRIDE_RESET_TIMEOUT, "label": "Reset after timeout (minutes)"},
                        ]
                    )
                ),
                vol.Optional(
                    CONF_MANUAL_OVERRIDE_RESET_TIME,
                    default=_time_default(
                        self._options.get(
                            CONF_MANUAL_OVERRIDE_RESET_TIME,
                            DEFAULT_MANUAL_OVERRIDE_RESET_TIME,
                        ),
                        DEFAULT_MANUAL_OVERRIDE_RESET_TIME,
                    ),
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_MANUAL_OVERRIDE_MINUTES,
                    default=self._options.get(CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES),
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_MANUAL_OVERRIDE_BLOCK_OPEN,
                    default=self._options.get(
                        CONF_MANUAL_OVERRIDE_BLOCK_OPEN,
                        DEFAULT_MANUAL_OVERRIDE_FLAGS[CONF_MANUAL_OVERRIDE_BLOCK_OPEN],
                    ),
                ): bool,
                vol.Optional(
                    CONF_MANUAL_OVERRIDE_BLOCK_CLOSE,
                    default=self._options.get(
                        CONF_MANUAL_OVERRIDE_BLOCK_CLOSE,
                        DEFAULT_MANUAL_OVERRIDE_FLAGS[CONF_MANUAL_OVERRIDE_BLOCK_CLOSE],
                    ),
                ): bool,
                vol.Optional(
                    CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE,
                    default=self._options.get(
                        CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE,
                        DEFAULT_MANUAL_OVERRIDE_FLAGS[CONF_MANUAL_OVERRIDE_BLOCK_VENTILATE],
                    ),
                ): bool,
                vol.Optional(
                    CONF_MANUAL_OVERRIDE_BLOCK_SHADING,
                    default=self._options.get(
                        CONF_MANUAL_OVERRIDE_BLOCK_SHADING,
                        DEFAULT_MANUAL_OVERRIDE_FLAGS[CONF_MANUAL_OVERRIDE_BLOCK_SHADING],
                    ),
                ): bool,
            }
        )

        if auto_brightness:
            schema.update(
                {
                    vol.Optional(
                        CONF_BRIGHTNESS_SENSOR,
                        default=self._optional_default(CONF_BRIGHTNESS_SENSOR),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"],device_class=["illuminance"])
                    ),
                    vol.Optional(
                        CONF_BRIGHTNESS_OPEN_ABOVE,
                        default=self._options.get(CONF_BRIGHTNESS_OPEN_ABOVE, DEFAULT_BRIGHTNESS_OPEN),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_BRIGHTNESS_CLOSE_BELOW,
                        default=self._options.get(CONF_BRIGHTNESS_CLOSE_BELOW, DEFAULT_BRIGHTNESS_CLOSE),
                    ): vol.Coerce(float),
                }
            )

        if auto_sun:
            schema.update(
                {
                    vol.Optional(
                        CONF_SUN_ELEVATION_OPEN,
                        default=self._options.get(CONF_SUN_ELEVATION_OPEN, DEFAULT_SUN_ELEVATION_OPEN),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_SUN_ELEVATION_CLOSE,
                        default=self._options.get(CONF_SUN_ELEVATION_CLOSE, DEFAULT_SUN_ELEVATION_CLOSE),
                    ): vol.Coerce(float),
                }
            )

        if auto_shading:
            schema.update(
                {
                    vol.Optional(
                        CONF_SUN_AZIMUTH_START,
                        default=self._options.get(CONF_SUN_AZIMUTH_START, DEFAULT_SHADING_AZIMUTH_START),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_SUN_AZIMUTH_END,
                        default=self._options.get(CONF_SUN_AZIMUTH_END, DEFAULT_SHADING_AZIMUTH_END),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_SUN_ELEVATION_MIN,
                        default=self._options.get(CONF_SUN_ELEVATION_MIN, DEFAULT_SHADING_ELEVATION_MIN),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_SUN_ELEVATION_MAX,
                        default=self._options.get(CONF_SUN_ELEVATION_MAX, DEFAULT_SHADING_ELEVATION_MAX),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_SHADING_BRIGHTNESS_START,
                        default=self._options.get(CONF_SHADING_BRIGHTNESS_START, DEFAULT_SHADING_BRIGHTNESS_START),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_SHADING_BRIGHTNESS_END,
                        default=self._options.get(CONF_SHADING_BRIGHTNESS_END, DEFAULT_SHADING_BRIGHTNESS_END),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_SHADING_FORECAST_SENSOR,
                        default=self._optional_default(CONF_SHADING_FORECAST_SENSOR),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor", "weather"])
                    ),
                    vol.Optional(
                        CONF_SHADING_FORECAST_TYPE,
                        default=self._options.get(
                            CONF_SHADING_FORECAST_TYPE, DEFAULT_SHADING_FORECAST_TYPE
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": "daily", "label": "Use the daily weather forecast service"},
                                {"value": "hourly", "label": "Use the hourly weather forecast service"},
                                {
                                    "value": "weather_attributes",
                                    "label": "Do not use a weather forecast, but the current weather attributes",
                                },
                            ]
                        )
                    ),
                    vol.Optional(
                        CONF_SHADING_WEATHER_CONDITIONS,
                        default=self._options.get(CONF_SHADING_WEATHER_CONDITIONS, []),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                "clear-night",
                                "clear",
                                "cloudy",
                                "fog",
                                "hail",
                                "lightning",
                                "lightning-rainy",
                                "partlycloudy",
                                "pouring",
                                "rainy",
                                "snowy",
                                "snowy-rainy",
                                "sunny",
                                "windy",
                                "windy-variant",
                                "exceptional",
                            ],
                            multiple=True,
                        )
                    ),
                }
            )

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))
    
    def _cover_full_key(self, cover: str) -> str:
        state = self.hass.states.get(cover)
        friendly_name = state.name if state else cover.split(".")[-1]
        return f"Voll geöffnet Sensor(e) für {friendly_name}"

    def _cover_tilt_key(self, cover: str) -> str:
        state = self.hass.states.get(cover)
        friendly_name = state.name if state else cover.split(".")[-1]
        return f"Kipp-Sensor(e) für {friendly_name}"
    
    def _existing_full_contacts_for_cover(self, cover: str) -> list[str]:
        mapping = self._options.get(CONF_WINDOW_SENSOR_FULL) or {}
        sensors = mapping.get(cover, [])
        return sensors if isinstance(sensors, list) else []

    def _existing_tilt_contacts_for_cover(self, cover: str) -> list[str]:
        mapping = self._options.get(CONF_WINDOW_SENSOR_TILT) or {}
        sensors = mapping.get(cover, [])
        return sensors if isinstance(sensors, list) else []
