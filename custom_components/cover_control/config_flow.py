"""Config and options flow for Cover Control."""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from collections import OrderedDict
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult, section
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .const import (
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
    CONF_COLD_PROTECTION_FORECAST_SENSOR,
    CONF_COLD_PROTECTION_THRESHOLD,
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
    CONF_COVERS,
    CONF_COVER_TYPE,
    CONF_COVER_TYPE_AWNING,
    CONF_COVER_TYPE_BLIND,
    CONF_ENABLE_CLEAR_MANUAL_OVERRIDE_BUTTON,
    CONF_ENABLE_RECALIBRATE_BUTTON,
    CONF_MANUAL_CONTROL,
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
    CONF_OPEN_TILT_POSITION,
    CONF_ROOM,
    CONF_POSITION_TOLERANCE,
    CONF_PREVENT_CLOSING_MULTIPLE_TIMES,
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
    CONF_SHADING_FORECAST_TYPE,
    CONF_SHADING_WEATHER_CONDITIONS,
    CONF_SHADING_BRIGHTNESS_END,
    CONF_SHADING_BRIGHTNESS_START,
    CONF_SHADING_END_IMMEDIATE_BY_SUN_POSITION,
    CONF_SHADING_END_MAX_DURATION,
    CONF_SHADING_POSITION,
    CONF_SHADING_TILT_POSITION,
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
    DEFAULT_CONTACT_SETTINGS,
    DEFAULT_AUTOMATION_FLAGS,
    DEFAULT_BEHAVIOR_SETTINGS,
    DEFAULT_BUTTON_SETTINGS,
    DEFAULT_BRIGHTNESS_CLOSE,
    DEFAULT_BRIGHTNESS_HYSTERESIS,
    DEFAULT_BRIGHTNESS_OPEN,
    DEFAULT_BRIGHTNESS_TIME_DURATION,
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
    DEFAULT_SHADING_END_MAX_DURATION,
    DEFAULT_SHADING_FORECAST_TYPE,
    DEFAULT_SHADING_ELEVATION_MAX,
    DEFAULT_SHADING_ELEVATION_MIN,
    DEFAULT_SHADING_START_MAX_DURATION,
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
        **DEFAULT_BEHAVIOR_SETTINGS,
        **DEFAULT_BUTTON_SETTINGS,
        **DEFAULT_SHADING_TIMING_SETTINGS,
        CONF_SUN_ELEVATION_MODE: DEFAULT_SUN_ELEVATION_MODE,
        CONF_SUN_ELEVATION_OPEN_OFFSET: DEFAULT_SUN_ELEVATION_OPEN_OFFSET,
        CONF_SUN_ELEVATION_CLOSE_OFFSET: DEFAULT_SUN_ELEVATION_CLOSE_OFFSET,
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
    CONF_TEMPERATURE_SENSOR_INDOOR,
    CONF_TEMPERATURE_SENSOR_OUTDOOR,
    CONF_COLD_PROTECTION_FORECAST_SENSOR,
    CONF_SHADING_FORECAST_SENSOR,
    CONF_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR,
    CONF_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR,
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


POSITION_FIELD_LIMITS = {
    CONF_OPEN_POSITION: 100,
    CONF_CLOSE_POSITION: 100,
    CONF_VENTILATE_POSITION: 100,
    CONF_SHADING_POSITION: 100,
    CONF_POSITION_TOLERANCE: 20,
    CONF_OPEN_TILT_POSITION: 100,
    CONF_CLOSE_TILT_POSITION: 100,
    CONF_VENTILATE_TILT_POSITION: 100,
    CONF_SHADING_TILT_POSITION: 100,
}


def _position_number_selector() -> selector.TextSelector:
    return selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.NUMBER)
    )


def _normalize_position_value(key: str, value: Any) -> int:
    max_value = POSITION_FIELD_LIMITS[key]
    try:
        parsed = int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        parsed = int(DEFAULT_POSITION_SETTINGS[key])
    return max(0, min(max_value, parsed))


def _position_default(config: dict[str, Any], key: str) -> str:
    return str(_normalize_position_value(key, config.get(key, DEFAULT_POSITION_SETTINGS[key])))


def _normalize_position_fields(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)
    for key in POSITION_FIELD_LIMITS:
        if key not in normalized:
            continue
        normalized[key] = _normalize_position_value(key, normalized[key])
    return normalized


class CoverControlFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            data = self._flatten_section_input(user_input, ("automation_features",))
            if CONF_AUTO_TIME in data:
                time_enabled = bool(data[CONF_AUTO_TIME])
                data[CONF_AUTO_UP] = time_enabled
                data[CONF_AUTO_DOWN] = time_enabled
            self._data.update(data)
            if self._data.get(CONF_AUTO_VENTILATE):
                return await self.async_step_windows()
            return await self.async_step_schedule()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_ROOM): selector.AreaSelector(),
                    vol.Required(CONF_COVERS): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["cover"], multiple=True)
                    ),
                    vol.Required("automation_features", default={}): section(
                        vol.Schema(
                            {
                                vol.Required(
                                    key,
                                    default=DEFAULT_AUTOMATION_FLAGS.get(key, False),
                                ): bool
                                for key in INITIAL_FEATURE_KEYS
                            }
                        ),
                        {"collapsed": False},
                    ),
                }
            ),
        )

    async def async_step_windows(self, user_input=None) -> FlowResult:
        if not self._data.get(CONF_AUTO_VENTILATE, DEFAULT_AUTOMATION_FLAGS[CONF_AUTO_VENTILATE]):
            return await self.async_step_schedule()

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

    def _needs_shading_step(self) -> bool:
        return any(
            bool(self._data.get(key, DEFAULT_AUTOMATION_FLAGS.get(key, False)))
            for key in (CONF_AUTO_BRIGHTNESS, CONF_AUTO_SUN, CONF_AUTO_SHADING)
        )

    async def async_step_schedule(self, user_input=None) -> FlowResult:
        if user_input is not None:
            self._data.update(
                _normalize_position_fields(
                    self._flatten_section_input(
                        user_input,
                        ("presence", "timing", "positions", "tilt_positions", "contacts"),
                    )
                )
            )
            if self._needs_shading_step():
                return await self.async_step_shading()
            return await self.async_step_finalize()

        schema: OrderedDict[Any, Any] = OrderedDict()
        uses_time = bool(self._data.get(CONF_AUTO_TIME, False))
        uses_ventilation = bool(self._data.get(CONF_AUTO_VENTILATE, False))
        uses_brightness = bool(self._data.get(CONF_AUTO_BRIGHTNESS, False))
        uses_sun = bool(self._data.get(CONF_AUTO_SUN, False))
        uses_shading = bool(self._data.get(CONF_AUTO_SHADING, False))
        uses_resident = bool(self._data.get(CONF_RESIDENT_STATUS, False))

        if uses_time or uses_brightness or uses_sun or uses_shading or uses_resident:
            presence_schema: OrderedDict[Any, Any] = OrderedDict()
            if uses_time:
                presence_schema[
                    vol.Optional(CONF_WORKDAY_SENSOR)
                ] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["binary_sensor", "sensor"])
                )
                presence_schema[
                    vol.Optional(CONF_WORKDAY_TOMORROW_SENSOR)
                ] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["binary_sensor", "sensor"])
                )
            if uses_resident:
                presence_schema[
                    vol.Optional(CONF_RESIDENT_SENSOR)
                ] = selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["binary_sensor", "input_boolean", "switch"]
                    )
                )
            if uses_brightness or uses_shading:
                presence_schema[
                    vol.Optional(CONF_BRIGHTNESS_SENSOR)
                ] = selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["sensor"], device_class=["illuminance"]
                    )
                )
            if uses_shading:
                presence_schema[
                    vol.Optional(CONF_TEMPERATURE_SENSOR_INDOOR)
                ] = selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"]))
                presence_schema[
                    vol.Optional(CONF_TEMPERATURE_SENSOR_OUTDOOR)
                ] = selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"]))
                presence_schema[
                    vol.Optional(
                        CONF_TEMPERATURE_THRESHOLD,
                        default=DEFAULT_TEMPERATURE_THRESHOLD,
                    )
                ] = vol.Coerce(float)
                presence_schema[
                    vol.Optional(
                        CONF_TEMPERATURE_FORECAST_THRESHOLD,
                        default=DEFAULT_TEMPERATURE_FORECAST_THRESHOLD,
                    )
                ] = vol.Coerce(float)
                presence_schema[
                    vol.Optional(
                        CONF_COLD_PROTECTION_THRESHOLD,
                        default=DEFAULT_COLD_PROTECTION_THRESHOLD,
                    )
                ] = vol.Coerce(float)
                presence_schema[
                    vol.Optional(CONF_COLD_PROTECTION_FORECAST_SENSOR)
                ] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["sensor", "weather"])
                )
            schema[vol.Required("presence", default={})] = section(
                vol.Schema(presence_schema),
                {"collapsed": False},
            )

        if uses_time:
            schema[vol.Required("timing", default={})] = section(
                vol.Schema(
                    {
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
                        vol.Optional(CONF_CALENDAR_ENTITY): selector.EntitySelector(
                            selector.EntitySelectorConfig(domain=["calendar"])
                        ),
                        vol.Optional(CONF_CALENDAR_OPEN_TITLE, default=""): str,
                        vol.Optional(CONF_CALENDAR_CLOSE_TITLE, default=""): str,
                    }
                ),
                {"collapsed": False},
            )

        schema[vol.Required("positions", default={})] = section(
            vol.Schema(
                {
                    vol.Required(
                        CONF_COVER_TYPE,
                        default=self._data.get(
                            CONF_COVER_TYPE,
                            DEFAULT_BEHAVIOR_SETTINGS[CONF_COVER_TYPE],
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": CONF_COVER_TYPE_BLIND, "label": "Blind / roller shutter"},
                                {"value": CONF_COVER_TYPE_AWNING, "label": "Awning / sunshade"},
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        CONF_OPEN_POSITION,
                        default=_position_default(self._data, CONF_OPEN_POSITION),
                    ): _position_number_selector(),
                    vol.Required(
                        CONF_CLOSE_POSITION,
                        default=_position_default(self._data, CONF_CLOSE_POSITION),
                    ): _position_number_selector(),
                    vol.Required(
                        CONF_VENTILATE_POSITION,
                        default=_position_default(self._data, CONF_VENTILATE_POSITION),
                    ): _position_number_selector(),
                    vol.Required(
                        CONF_SHADING_POSITION,
                        default=_position_default(self._data, CONF_SHADING_POSITION),
                    ): _position_number_selector(),
                    vol.Required(
                        CONF_POSITION_TOLERANCE,
                        default=_position_default(self._data, CONF_POSITION_TOLERANCE),
                    ): _position_number_selector(),
                }
            ),
            {"collapsed": False},
        )
        schema[vol.Required("tilt_positions", default={})] = section(
            vol.Schema(
                {
                    vol.Required(
                        CONF_OPEN_TILT_POSITION,
                        default=_position_default(self._data, CONF_OPEN_TILT_POSITION),
                    ): _position_number_selector(),
                    vol.Required(
                        CONF_CLOSE_TILT_POSITION,
                        default=_position_default(self._data, CONF_CLOSE_TILT_POSITION),
                    ): _position_number_selector(),
                    vol.Required(
                        CONF_VENTILATE_TILT_POSITION,
                        default=_position_default(self._data, CONF_VENTILATE_TILT_POSITION),
                    ): _position_number_selector(),
                    vol.Required(
                        CONF_SHADING_TILT_POSITION,
                        default=_position_default(self._data, CONF_SHADING_TILT_POSITION),
                    ): _position_number_selector(),
                }
            ),
            {"collapsed": True},
        )

        if uses_ventilation:
            schema[vol.Required("contacts", default={})] = section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_CONTACT_TRIGGER_DELAY,
                            default=self._data.get(
                                CONF_CONTACT_TRIGGER_DELAY,
                                DEFAULT_CONTACT_TRIGGER_DELAY,
                            ),
                        ): vol.Coerce(int),
                        vol.Optional(
                            CONF_CONTACT_STATUS_DELAY,
                            default=self._data.get(
                                CONF_CONTACT_STATUS_DELAY,
                                DEFAULT_CONTACT_STATUS_DELAY,
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
                                    DEFAULT_CONTACT_SETTINGS[
                                        CONF_VENTILATION_ALLOW_HIGHER_POSITION
                                    ],
                                )
                            ),
                        ): bool,
                        vol.Optional(
                            CONF_VENTILATION_USE_AFTER_SHADING,
                            default=bool(
                                self._data.get(
                                    CONF_VENTILATION_USE_AFTER_SHADING,
                                    DEFAULT_CONTACT_SETTINGS[
                                        CONF_VENTILATION_USE_AFTER_SHADING
                                    ],
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
                                    DEFAULT_CONTACT_SETTINGS[
                                        CONF_LOCKOUT_TILT_SHADING_START
                                    ],
                                )
                            ),
                        ): bool,
                        vol.Optional(
                            CONF_LOCKOUT_TILT_SHADING_END,
                            default=bool(
                                self._data.get(
                                    CONF_LOCKOUT_TILT_SHADING_END,
                                    DEFAULT_CONTACT_SETTINGS[
                                        CONF_LOCKOUT_TILT_SHADING_END
                                    ],
                                )
                            ),
                        ): bool,
                    }
                ),
                {"collapsed": True},
            )

        return self.async_show_form(
            step_id="schedule",
            data_schema=vol.Schema(schema),
        )

    async def async_step_shading(self, user_input=None) -> FlowResult:
        if user_input is not None:
            self._data.update(
                self._flatten_section_input(
                    user_input,
                    ("brightness_controls", "sun_controls", "shading_controls", "manual_override"),
                )
            )
            return await self.async_step_finalize()

        schema: dict[Any, Any] = {}
        if self._data.get(CONF_AUTO_BRIGHTNESS, DEFAULT_AUTOMATION_FLAGS[CONF_AUTO_BRIGHTNESS]):
            schema[vol.Required("brightness_controls", default={})] = section(
                vol.Schema(
                    {
                        vol.Optional(CONF_BRIGHTNESS_OPEN_ABOVE, default=DEFAULT_BRIGHTNESS_OPEN): vol.Coerce(float),
                        vol.Optional(CONF_BRIGHTNESS_CLOSE_BELOW, default=DEFAULT_BRIGHTNESS_CLOSE): vol.Coerce(float),
                    }
                ),
                {"collapsed": False},
            )
        if self._data.get(CONF_AUTO_SUN, DEFAULT_AUTOMATION_FLAGS[CONF_AUTO_SUN]):
            schema[vol.Required("sun_controls", default={})] = section(
                vol.Schema(
                    {
                        vol.Optional(CONF_SUN_ELEVATION_OPEN, default=DEFAULT_SUN_ELEVATION_OPEN): vol.Coerce(float),
                        vol.Optional(CONF_SUN_ELEVATION_CLOSE, default=DEFAULT_SUN_ELEVATION_CLOSE): vol.Coerce(float),
                    }
                ),
                {"collapsed": False},
            )
        if self._data.get(CONF_AUTO_SHADING, DEFAULT_AUTOMATION_FLAGS[CONF_AUTO_SHADING]):
            schema[vol.Required("shading_controls", default={})] = section(
                vol.Schema(
                    {
                        vol.Optional(CONF_SUN_AZIMUTH_START, default=DEFAULT_SHADING_AZIMUTH_START): vol.Coerce(float),
                        vol.Optional(CONF_SUN_AZIMUTH_END, default=DEFAULT_SHADING_AZIMUTH_END): vol.Coerce(float),
                        vol.Optional(CONF_SUN_ELEVATION_MIN, default=DEFAULT_SHADING_ELEVATION_MIN): vol.Coerce(float),
                        vol.Optional(CONF_SUN_ELEVATION_MAX, default=DEFAULT_SHADING_ELEVATION_MAX): vol.Coerce(float),
                        vol.Optional(CONF_SHADING_BRIGHTNESS_START, default=DEFAULT_SHADING_BRIGHTNESS_START): vol.Coerce(float),
                        vol.Optional(CONF_SHADING_BRIGHTNESS_END, default=DEFAULT_SHADING_BRIGHTNESS_END): vol.Coerce(float),
                        vol.Optional(CONF_SHADING_WAITINGTIME_START, default=DEFAULT_SHADING_WAITINGTIME_START): vol.Coerce(int),
                        vol.Optional(CONF_SHADING_WAITINGTIME_END, default=DEFAULT_SHADING_WAITINGTIME_END): vol.Coerce(int),
                        vol.Optional(CONF_SHADING_START_MAX_DURATION, default=DEFAULT_SHADING_START_MAX_DURATION): vol.Coerce(int),
                        vol.Optional(CONF_SHADING_END_MAX_DURATION, default=DEFAULT_SHADING_END_MAX_DURATION): vol.Coerce(int),
                        vol.Optional(CONF_SHADING_END_IMMEDIATE_BY_SUN_POSITION, default=False): bool,
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
                    }
                ),
                {"collapsed": False},
            )
        schema[vol.Required("manual_override", default={})] = section(
            vol.Schema(
                {
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
            {"collapsed": False},
        )
        return self.async_show_form(step_id="shading", data_schema=vol.Schema(schema))

    async def async_step_finalize(self, user_input=None) -> FlowResult:
        if user_input:
            self._data.update(user_input)
        for key in CLEARABLE_ENTITY_SELECTOR_KEYS:
            if self._data.get(key) in (None, "", vol.UNDEFINED):
                self._data.pop(key, None)
        name = str(self._data.get(CONF_NAME, DEFAULT_NAME)).strip() or DEFAULT_NAME
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

    def _flatten_section_input(
        self, user_input: dict[str, Any], section_keys: tuple[str, ...]
    ) -> dict[str, Any]:
        flattened: dict[str, Any] = {}
        for key, value in user_input.items():
            if key in section_keys and isinstance(value, dict):
                flattened.update(value)
                continue
            flattened[key] = value
        return flattened

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return CoverOptionsFlow(config_entry)


class CoverOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow."""

    _CLEARABLE_OPTION_KEYS = {
        *CLEARABLE_ENTITY_SELECTOR_KEYS,
        CONF_ADDITIONAL_CONDITION_GLOBAL,
        CONF_ADDITIONAL_CONDITION_OPEN,
        CONF_ADDITIONAL_CONDITION_CLOSE,
        CONF_ADDITIONAL_CONDITION_VENTILATE,
        CONF_ADDITIONAL_CONDITION_VENTILATE_END,
        CONF_ADDITIONAL_CONDITION_SHADING,
        CONF_ADDITIONAL_CONDITION_SHADING_TILT,
        CONF_ADDITIONAL_CONDITION_SHADING_END,
        CONF_CALENDAR_ENTITY,
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

        cleaned: dict[str, Any] = {}
        for key, value in user_input.items():
            if key in self._CLEARABLE_OPTION_KEYS and value in ("", vol.UNDEFINED, None, [], {}):
                cleaned[key] = None
                continue
            if value in ("", vol.UNDEFINED):
                continue
            cleaned[key] = _json_safe(value)

        for toggle_key, entity_key in ENTITY_TOGGLE_MAP.items():
            if toggle_key in user_input:
                enabled = bool(user_input.get(toggle_key))
            else:
                # In options menus without explicit toggle fields, keep newly
                # selected entities active instead of clearing them.
                enabled = (
                    entity_key in user_input
                    or cleaned.get(entity_key) not in ("", vol.UNDEFINED, None)
                    or _is_enabled(self._options, entity_key)
                )

            if not enabled:
                cleaned[entity_key] = None
            elif cleaned.get(entity_key) in ("", vol.UNDEFINED):
                cleaned[entity_key] = None

            cleaned.pop(toggle_key, None)

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
            if value not in ("", vol.UNDEFINED)
            and (value is not None or key in self._CLEARABLE_OPTION_KEYS)
        }

    def _normalize_options(
        self,
        config_entry: config_entries.ConfigEntry | None,
        overrides: dict | None = None,
        base_options: dict | None = None,
    ) -> dict:
        """Merge stored data/options with defaults, overrides, and sanitize them."""


        merged: dict = {}
        if base_options:
            merged.update(dict(base_options))
        if config_entry:
            merged.update(dict(config_entry.data or {}))
            merged.update(dict(config_entry.options or {}))

        merged = _with_config_defaults(merged)
        if overrides:
            merged.update(overrides)
        sanitized = self._sanitize_options(merged)

        covers_raw = sanitized.get(CONF_COVERS, [])
        if isinstance(covers_raw, str):
            covers = [covers_raw]
        elif isinstance(covers_raw, list):
            covers = covers_raw
        else:
            covers = list(covers_raw) if covers_raw else []
        unique_covers: list[str] = []
        for cover in covers:
            if isinstance(cover, str) and cover and cover not in unique_covers:
                unique_covers.append(cover)
        sanitized[CONF_COVERS] = unique_covers

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
        return await self.async_step_menu()

    def _menu_options(self) -> list[str]:
        """Return dynamic options menu entries based on active features."""

        options = ["general", "positions", "functions", "behavior"]
        if bool(self._options.get(CONF_AUTO_TIME, DEFAULT_AUTOMATION_FLAGS[CONF_AUTO_TIME])):
            options.append("time_control")
        if bool(self._options.get(CONF_AUTO_VENTILATE, DEFAULT_AUTOMATION_FLAGS[CONF_AUTO_VENTILATE])):
            options.append("contact_sensors")
        if bool(self._options.get(CONF_AUTO_BRIGHTNESS, DEFAULT_AUTOMATION_FLAGS[CONF_AUTO_BRIGHTNESS])):
            options.append("brightness")
        if bool(self._options.get(CONF_AUTO_SUN, DEFAULT_AUTOMATION_FLAGS[CONF_AUTO_SUN])):
            options.append("sun_elevation")
        if bool(self._options.get(CONF_AUTO_SHADING, DEFAULT_AUTOMATION_FLAGS[CONF_AUTO_SHADING])):
            options.append("shading")
        if bool(
            self._options.get(
                CONF_ADDITIONAL_CONDITIONS_ENABLED,
                DEFAULT_AUTOMATION_FLAGS[CONF_ADDITIONAL_CONDITIONS_ENABLED],
            )
        ):
            options.append("additional_conditions")
        if bool(self._options.get(CONF_RESIDENT_STATUS, DEFAULT_AUTOMATION_FLAGS[CONF_RESIDENT_STATUS])):
            options.append("resident")
        options.append("finish")
        return options

    async def async_step_menu(self, user_input=None) -> FlowResult:
        return self.async_show_menu(
            step_id="menu",
            menu_options=self._menu_options(),
        )

    async def async_step_general(self, user_input=None) -> FlowResult:
        if user_input is not None:
            await self._save_options(user_input)
            return await self.async_step_menu()

        schema: dict = {
            vol.Optional(
                CONF_NAME,
                default=self._options.get(CONF_NAME, self._config_entry.title or DEFAULT_NAME),
            ): str,
            vol.Optional(CONF_ROOM, default=self._optional_default(CONF_ROOM)): selector.AreaSelector(),
            vol.Required(CONF_COVERS, default=self._options.get(CONF_COVERS, [])): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["cover"], multiple=True)
            ),
        }
        return self.async_show_form(step_id="general", data_schema=vol.Schema(schema))

    async def async_step_positions(self, user_input=None) -> FlowResult:
        if user_input is not None:
            await self._save_options(user_input)
            return await self.async_step_menu()

        schema: dict = {
            vol.Required(
                CONF_COVER_TYPE,
                default=self._options.get(
                    CONF_COVER_TYPE,
                    DEFAULT_BEHAVIOR_SETTINGS[CONF_COVER_TYPE],
                ),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": CONF_COVER_TYPE_BLIND, "label": "Blind / roller shutter"},
                        {"value": CONF_COVER_TYPE_AWNING, "label": "Awning / sunshade"},
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_OPEN_POSITION,
                default=_position_default(self._options, CONF_OPEN_POSITION),
            ): _position_number_selector(),
            vol.Required(
                CONF_CLOSE_POSITION,
                default=_position_default(self._options, CONF_CLOSE_POSITION),
            ): _position_number_selector(),
            vol.Required(
                CONF_VENTILATE_POSITION,
                default=_position_default(self._options, CONF_VENTILATE_POSITION),
            ): _position_number_selector(),
            vol.Required(
                CONF_SHADING_POSITION,
                default=_position_default(self._options, CONF_SHADING_POSITION),
            ): _position_number_selector(),
            vol.Required(
                CONF_POSITION_TOLERANCE,
                default=_position_default(self._options, CONF_POSITION_TOLERANCE),
            ): _position_number_selector(),
            vol.Required(
                CONF_OPEN_TILT_POSITION,
                default=_position_default(self._options, CONF_OPEN_TILT_POSITION),
            ): _position_number_selector(),
            vol.Required(
                CONF_CLOSE_TILT_POSITION,
                default=_position_default(self._options, CONF_CLOSE_TILT_POSITION),
            ): _position_number_selector(),
            vol.Required(
                CONF_VENTILATE_TILT_POSITION,
                default=_position_default(self._options, CONF_VENTILATE_TILT_POSITION),
            ): _position_number_selector(),
            vol.Required(
                CONF_SHADING_TILT_POSITION,
                default=_position_default(self._options, CONF_SHADING_TILT_POSITION),
            ): _position_number_selector(),
        }
        return self.async_show_form(step_id="positions", data_schema=vol.Schema(schema))

    async def async_step_functions(self, user_input=None) -> FlowResult:
        if user_input is not None:
            if CONF_AUTO_TIME in user_input:
                time_enabled = bool(user_input[CONF_AUTO_TIME])
                user_input[CONF_AUTO_UP] = time_enabled
                user_input[CONF_AUTO_DOWN] = time_enabled
            await self._save_options(user_input)
            return await self.async_step_menu()

        schema: dict = {
            vol.Optional(
                CONF_AUTO_TIME,
                default=bool(self._options.get(CONF_AUTO_TIME, DEFAULT_AUTOMATION_FLAGS[CONF_AUTO_TIME])),
            ): bool,
            vol.Optional(
                CONF_AUTO_VENTILATE,
                default=bool(self._options.get(CONF_AUTO_VENTILATE, DEFAULT_AUTOMATION_FLAGS[CONF_AUTO_VENTILATE])),
            ): bool,
            vol.Optional(
                CONF_AUTO_BRIGHTNESS,
                default=bool(self._options.get(CONF_AUTO_BRIGHTNESS, DEFAULT_AUTOMATION_FLAGS[CONF_AUTO_BRIGHTNESS])),
            ): bool,
            vol.Optional(
                CONF_AUTO_SUN,
                default=bool(self._options.get(CONF_AUTO_SUN, DEFAULT_AUTOMATION_FLAGS[CONF_AUTO_SUN])),
            ): bool,
            vol.Optional(
                CONF_AUTO_SHADING,
                default=bool(self._options.get(CONF_AUTO_SHADING, DEFAULT_AUTOMATION_FLAGS[CONF_AUTO_SHADING])),
            ): bool,
            vol.Optional(
                CONF_RESIDENT_STATUS,
                default=bool(self._options.get(CONF_RESIDENT_STATUS, DEFAULT_AUTOMATION_FLAGS[CONF_RESIDENT_STATUS])),
            ): bool,
            vol.Optional(
                CONF_ADDITIONAL_CONDITIONS_ENABLED,
                default=bool(
                    self._options.get(
                        CONF_ADDITIONAL_CONDITIONS_ENABLED,
                        DEFAULT_AUTOMATION_FLAGS[CONF_ADDITIONAL_CONDITIONS_ENABLED],
                    )
                ),
            ): bool,
            vol.Optional(
                CONF_MANUAL_CONTROL,
                default=bool(
                    self._options.get(
                        CONF_MANUAL_CONTROL,
                        self._options.get(
                            CONF_ENABLE_RECALIBRATE_BUTTON,
                            self._options.get(
                                CONF_ENABLE_CLEAR_MANUAL_OVERRIDE_BUTTON,
                                DEFAULT_BUTTON_SETTINGS[CONF_MANUAL_CONTROL],
                            ),
                        ),
                    )
                ),
            ): bool,
        }
        return self.async_show_form(step_id="functions", data_schema=vol.Schema(schema))

    async def async_step_behavior(self, user_input=None) -> FlowResult:
        if user_input is not None:
            await self._save_options(user_input)
            return await self.async_step_menu()

        schema: dict = {
            vol.Optional(
                CONF_PREVENT_HIGHER_POSITION_CLOSING,
                default=bool(self._options.get(CONF_PREVENT_HIGHER_POSITION_CLOSING, False)),
            ): bool,
            vol.Optional(
                CONF_PREVENT_LOWERING_WHEN_CLOSING_IF_SHADED,
                default=bool(self._options.get(CONF_PREVENT_LOWERING_WHEN_CLOSING_IF_SHADED, False)),
            ): bool,
            vol.Optional(
                CONF_PREVENT_SHADING_END_IF_CLOSED,
                default=bool(self._options.get(CONF_PREVENT_SHADING_END_IF_CLOSED, False)),
            ): bool,
            vol.Optional(
                CONF_PREVENT_OPENING_AFTER_SHADING_END,
                default=bool(self._options.get(CONF_PREVENT_OPENING_AFTER_SHADING_END, False)),
            ): bool,
            vol.Optional(
                CONF_PREVENT_OPENING_AFTER_VENTILATION_END,
                default=bool(self._options.get(CONF_PREVENT_OPENING_AFTER_VENTILATION_END, False)),
            ): bool,
            vol.Optional(
                CONF_PREVENT_OPENING_MULTIPLE_TIMES,
                default=bool(self._options.get(CONF_PREVENT_OPENING_MULTIPLE_TIMES, False)),
            ): bool,
            vol.Optional(
                CONF_PREVENT_CLOSING_MULTIPLE_TIMES,
                default=bool(self._options.get(CONF_PREVENT_CLOSING_MULTIPLE_TIMES, False)),
            ): bool,
            vol.Optional(
                CONF_PREVENT_SHADING_MULTIPLE_TIMES,
                default=bool(self._options.get(CONF_PREVENT_SHADING_MULTIPLE_TIMES, False)),
            ): bool,
        }
        return self.async_show_form(step_id="behavior", data_schema=vol.Schema(schema))

    async def async_step_additional_conditions(self, user_input=None) -> FlowResult:
        if user_input is not None:
            await self._save_options(user_input)
            return await self.async_step_menu()

        condition_selector = selector.ConditionSelector()
        schema: dict = {
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
        return self.async_show_form(step_id="additional_conditions", data_schema=vol.Schema(schema))

    async def async_step_resident(self, user_input=None) -> FlowResult:
        if user_input is not None:
            await self._save_options(user_input)
            return await self.async_step_menu()

        schema: dict = {
            vol.Optional(
                CONF_RESIDENT_SENSOR,
                default=self._optional_default(CONF_RESIDENT_SENSOR),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["binary_sensor", "input_boolean", "switch"])
            ),
            vol.Optional(
                CONF_RESIDENT_OPEN_ENABLED,
                default=bool(
                    self._options.get(
                        CONF_RESIDENT_OPEN_ENABLED,
                        DEFAULT_AUTOMATION_FLAGS[CONF_RESIDENT_OPEN_ENABLED],
                    )
                ),
            ): bool,
            vol.Optional(
                CONF_RESIDENT_CLOSE_ENABLED,
                default=bool(
                    self._options.get(
                        CONF_RESIDENT_CLOSE_ENABLED,
                        DEFAULT_AUTOMATION_FLAGS[CONF_RESIDENT_CLOSE_ENABLED],
                    )
                ),
            ): bool,
            vol.Optional(
                CONF_RESIDENT_ALLOW_SHADING,
                default=bool(
                    self._options.get(
                        CONF_RESIDENT_ALLOW_SHADING,
                        DEFAULT_AUTOMATION_FLAGS[CONF_RESIDENT_ALLOW_SHADING],
                    )
                ),
            ): bool,
            vol.Optional(
                CONF_RESIDENT_ALLOW_OPEN,
                default=bool(
                    self._options.get(
                        CONF_RESIDENT_ALLOW_OPEN,
                        DEFAULT_AUTOMATION_FLAGS[CONF_RESIDENT_ALLOW_OPEN],
                    )
                ),
            ): bool,
            vol.Optional(
                CONF_RESIDENT_ALLOW_VENTILATION,
                default=bool(
                    self._options.get(
                        CONF_RESIDENT_ALLOW_VENTILATION,
                        DEFAULT_AUTOMATION_FLAGS[CONF_RESIDENT_ALLOW_VENTILATION],
                    )
                ),
            ): bool,
        }
        return self.async_show_form(step_id="resident", data_schema=vol.Schema(schema))

    async def async_step_time_control(self, user_input=None) -> FlowResult:
        if user_input is not None:
            await self._save_options(user_input)
            return await self.async_step_menu()

        auto_up = bool(self._options.get(CONF_AUTO_UP, DEFAULT_AUTOMATION_FLAGS[CONF_AUTO_UP]))
        auto_down = bool(self._options.get(CONF_AUTO_DOWN, DEFAULT_AUTOMATION_FLAGS[CONF_AUTO_DOWN]))

        schema: dict = {}
        if auto_up or auto_down:
            schema.update(
                {
            vol.Optional(
                CONF_WORKDAY_SENSOR,
                default=self._optional_default(CONF_WORKDAY_SENSOR),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["binary_sensor", "sensor"])),
                }
            )
        if auto_down:
            schema.update(
                {
                    vol.Optional(
                        CONF_WORKDAY_TOMORROW_SENSOR,
                        default=self._optional_default(CONF_WORKDAY_TOMORROW_SENSOR),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["binary_sensor", "sensor"])
                    ),
                }
            )
        if auto_up:
            schema.update(
                {
                    vol.Optional(
                        CONF_TIME_UP_EARLY_WORKDAY,
                        default=_time_default(
                            self._options.get(CONF_TIME_UP_EARLY_WORKDAY, DEFAULT_TIME_SETTINGS[CONF_TIME_UP_EARLY_WORKDAY])
                        ),
                    ): selector.TimeSelector(),
                    vol.Optional(
                        CONF_TIME_UP_LATE_WORKDAY,
                        default=_time_default(
                            self._options.get(CONF_TIME_UP_LATE_WORKDAY, DEFAULT_TIME_SETTINGS[CONF_TIME_UP_LATE_WORKDAY])
                        ),
                    ): selector.TimeSelector(),
                    vol.Optional(
                        CONF_TIME_UP_EARLY_NON_WORKDAY,
                        default=_time_default(
                            self._options.get(
                                CONF_TIME_UP_EARLY_NON_WORKDAY, DEFAULT_TIME_SETTINGS[CONF_TIME_UP_EARLY_NON_WORKDAY]
                            )
                        ),
                    ): selector.TimeSelector(),
                    vol.Optional(
                        CONF_TIME_UP_LATE_NON_WORKDAY,
                        default=_time_default(
                            self._options.get(CONF_TIME_UP_LATE_NON_WORKDAY, DEFAULT_TIME_SETTINGS[CONF_TIME_UP_LATE_NON_WORKDAY])
                        ),
                    ): selector.TimeSelector(),
                }
            )
        if auto_down:
            schema.update(
                {
                    vol.Optional(
                        CONF_TIME_DOWN_EARLY_WORKDAY,
                        default=_time_default(
                            self._options.get(
                                CONF_TIME_DOWN_EARLY_WORKDAY, DEFAULT_TIME_SETTINGS[CONF_TIME_DOWN_EARLY_WORKDAY]
                            )
                        ),
                    ): selector.TimeSelector(),
                    vol.Optional(
                        CONF_TIME_DOWN_LATE_WORKDAY,
                        default=_time_default(
                            self._options.get(CONF_TIME_DOWN_LATE_WORKDAY, DEFAULT_TIME_SETTINGS[CONF_TIME_DOWN_LATE_WORKDAY])
                        ),
                    ): selector.TimeSelector(),
                    vol.Optional(
                        CONF_TIME_DOWN_EARLY_NON_WORKDAY,
                        default=_time_default(
                            self._options.get(
                                CONF_TIME_DOWN_EARLY_NON_WORKDAY, DEFAULT_TIME_SETTINGS[CONF_TIME_DOWN_EARLY_NON_WORKDAY]
                            )
                        ),
                    ): selector.TimeSelector(),
                    vol.Optional(
                        CONF_TIME_DOWN_LATE_NON_WORKDAY,
                        default=_time_default(
                            self._options.get(
                                CONF_TIME_DOWN_LATE_NON_WORKDAY, DEFAULT_TIME_SETTINGS[CONF_TIME_DOWN_LATE_NON_WORKDAY]
                            )
                        ),
                    ): selector.TimeSelector(),
                    vol.Optional(
                        CONF_CALENDAR_ENTITY,
                        default=self._optional_default(CONF_CALENDAR_ENTITY),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["calendar"])
                    ),
                    vol.Optional(
                        CONF_CALENDAR_OPEN_TITLE,
                        default=self._options.get(CONF_CALENDAR_OPEN_TITLE, ""),
                    ): str,
                    vol.Optional(
                        CONF_CALENDAR_CLOSE_TITLE,
                        default=self._options.get(CONF_CALENDAR_CLOSE_TITLE, ""),
                    ): str,
                }
            )
        return self.async_show_form(step_id="time_control", data_schema=vol.Schema(schema))

    async def async_step_finish(self, user_input=None) -> FlowResult:
        name = str(self._options.get(CONF_NAME, self._config_entry.title)).strip() or DEFAULT_NAME
        self.hass.config_entries.async_update_entry(self._config_entry, title=name)
        return self.async_create_entry(title="", data=self._options)

    async def async_step_contact_sensors(self, user_input=None) -> FlowResult:
        covers = self._options.get(CONF_COVERS, [])
        if user_input is not None:
            await self._save_options(user_input, include_contacts=True)
            return await self.async_step_menu()

        multi_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=["binary_sensor"],
                device_class=["window", "door", "opening"],
                multiple=True,
            )
        )
        schema: OrderedDict = OrderedDict()
        for cover in covers:
            schema[vol.Optional(self._cover_full_key(cover), default=_selector_default(self._existing_full_contacts_for_cover(cover)))] = multi_selector
            schema[vol.Optional(self._cover_tilt_key(cover), default=_selector_default(self._existing_tilt_contacts_for_cover(cover)))] = multi_selector
        schema.update(
            {
                vol.Optional(
                    CONF_CONTACT_TRIGGER_DELAY,
                    default=self._options.get(CONF_CONTACT_TRIGGER_DELAY, DEFAULT_CONTACT_TRIGGER_DELAY),
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_CONTACT_STATUS_DELAY,
                    default=self._options.get(CONF_CONTACT_STATUS_DELAY, DEFAULT_CONTACT_STATUS_DELAY),
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_VENTILATION_DELAY_AFTER_CLOSE,
                    default=self._options.get(CONF_VENTILATION_DELAY_AFTER_CLOSE, DEFAULT_VENTILATION_DELAY_AFTER_CLOSE),
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_VENTILATION_ALLOW_HIGHER_POSITION,
                    default=bool(self._options.get(CONF_VENTILATION_ALLOW_HIGHER_POSITION, DEFAULT_CONTACT_SETTINGS[CONF_VENTILATION_ALLOW_HIGHER_POSITION])),
                ): bool,
                vol.Optional(
                    CONF_VENTILATION_USE_AFTER_SHADING,
                    default=bool(self._options.get(CONF_VENTILATION_USE_AFTER_SHADING, DEFAULT_CONTACT_SETTINGS[CONF_VENTILATION_USE_AFTER_SHADING])),
                ): bool,
                vol.Optional(
                    CONF_LOCKOUT_TILT_CLOSE,
                    default=bool(self._options.get(CONF_LOCKOUT_TILT_CLOSE, DEFAULT_CONTACT_SETTINGS[CONF_LOCKOUT_TILT_CLOSE])),
                ): bool,
                vol.Optional(
                    CONF_LOCKOUT_TILT_SHADING_START,
                    default=bool(self._options.get(CONF_LOCKOUT_TILT_SHADING_START, DEFAULT_CONTACT_SETTINGS[CONF_LOCKOUT_TILT_SHADING_START])),
                ): bool,
                vol.Optional(
                    CONF_LOCKOUT_TILT_SHADING_END,
                    default=bool(self._options.get(CONF_LOCKOUT_TILT_SHADING_END, DEFAULT_CONTACT_SETTINGS[CONF_LOCKOUT_TILT_SHADING_END])),
                ): bool,
            }
        )
        return self.async_show_form(step_id="contact_sensors", data_schema=vol.Schema(schema))

    async def async_step_brightness(self, user_input=None) -> FlowResult:
        if user_input is not None:
            await self._save_options(user_input)
            return await self.async_step_menu()

        auto_brightness = bool(
            self._options.get(CONF_AUTO_BRIGHTNESS, DEFAULT_AUTOMATION_FLAGS[CONF_AUTO_BRIGHTNESS])
        )

        schema: dict = {}
        if auto_brightness:
            schema.update(
                {
                    vol.Optional(
                        CONF_BRIGHTNESS_SENSOR,
                        default=self._optional_default(CONF_BRIGHTNESS_SENSOR),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor"], device_class="illuminance")
                    ),
                    vol.Optional(
                        CONF_BRIGHTNESS_OPEN_ABOVE,
                        default=self._options.get(CONF_BRIGHTNESS_OPEN_ABOVE, DEFAULT_BRIGHTNESS_OPEN),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_BRIGHTNESS_CLOSE_BELOW,
                        default=self._options.get(CONF_BRIGHTNESS_CLOSE_BELOW, DEFAULT_BRIGHTNESS_CLOSE),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_BRIGHTNESS_HYSTERESIS,
                        default=self._options.get(CONF_BRIGHTNESS_HYSTERESIS, DEFAULT_BRIGHTNESS_HYSTERESIS),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_BRIGHTNESS_TIME_DURATION,
                        default=self._options.get(CONF_BRIGHTNESS_TIME_DURATION, DEFAULT_BRIGHTNESS_TIME_DURATION),
                    ): vol.Coerce(int),
                }
            )

        return self.async_show_form(
            step_id="brightness",
            data_schema=vol.Schema(schema),
        )

    async def async_step_sun_elevation(self, user_input=None) -> FlowResult:
        selected_mode = str(
            (user_input or {}).get(
                CONF_SUN_ELEVATION_MODE,
                self._options.get(CONF_SUN_ELEVATION_MODE, DEFAULT_SUN_ELEVATION_MODE),
            )
            or DEFAULT_SUN_ELEVATION_MODE
        ).lower()

        schema: dict = {
            vol.Optional(
                CONF_SUN_ELEVATION_MODE,
                default=selected_mode,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "fixed", "label": "Fixed - use only fixed values"},
                        {"value": "dynamic", "label": "Dynamic - use only sensor values"},
                        {"value": "hybrid", "label": "Hybrid - sensor + fixed value as offset"},
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_SUN_ELEVATION_OPEN,
                default=(user_input or {}).get(
                    CONF_SUN_ELEVATION_OPEN,
                    self._options.get(CONF_SUN_ELEVATION_OPEN, DEFAULT_SUN_ELEVATION_OPEN),
                ),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_SUN_ELEVATION_CLOSE,
                default=(user_input or {}).get(
                    CONF_SUN_ELEVATION_CLOSE,
                    self._options.get(CONF_SUN_ELEVATION_CLOSE, DEFAULT_SUN_ELEVATION_CLOSE),
                ),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_SUN_TIME_DURATION,
                default=(user_input or {}).get(
                    CONF_SUN_TIME_DURATION,
                    self._options.get(CONF_SUN_TIME_DURATION, DEFAULT_SUN_TIME_DURATION),
                ),
            ): vol.Coerce(int),
            vol.Optional(
                CONF_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR,
                default=(user_input or {}).get(
                    CONF_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR,
                    self._optional_default(CONF_SUN_ELEVATION_DYNAMIC_OPEN_SENSOR),
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "input_number", "number"])
            ),
            vol.Optional(
                CONF_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR,
                default=(user_input or {}).get(
                    CONF_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR,
                    self._optional_default(CONF_SUN_ELEVATION_DYNAMIC_CLOSE_SENSOR),
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "input_number", "number"])
            ),
        }

        if user_input is not None:
            await self._save_options(user_input)
            return await self.async_step_menu()

        return self.async_show_form(
            step_id="sun_elevation",
            data_schema=vol.Schema(schema),
        )

    async def async_step_shading(self, user_input=None) -> FlowResult:
        if user_input is not None:
            await self._save_options(user_input)
            return await self.async_step_menu()

        return self.async_show_form(
            step_id="shading",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SUN_AZIMUTH_START, default=self._options.get(CONF_SUN_AZIMUTH_START, DEFAULT_SHADING_AZIMUTH_START)): vol.Coerce(float),
                    vol.Optional(CONF_SUN_AZIMUTH_END, default=self._options.get(CONF_SUN_AZIMUTH_END, DEFAULT_SHADING_AZIMUTH_END)): vol.Coerce(float),
                    vol.Optional(CONF_SUN_ELEVATION_MIN, default=self._options.get(CONF_SUN_ELEVATION_MIN, DEFAULT_SHADING_ELEVATION_MIN)): vol.Coerce(float),
                    vol.Optional(CONF_SUN_ELEVATION_MAX, default=self._options.get(CONF_SUN_ELEVATION_MAX, DEFAULT_SHADING_ELEVATION_MAX)): vol.Coerce(float),
                    vol.Optional(CONF_SHADING_BRIGHTNESS_START, default=self._options.get(CONF_SHADING_BRIGHTNESS_START, DEFAULT_SHADING_BRIGHTNESS_START)): vol.Coerce(float),
                    vol.Optional(CONF_SHADING_BRIGHTNESS_END, default=self._options.get(CONF_SHADING_BRIGHTNESS_END, DEFAULT_SHADING_BRIGHTNESS_END)): vol.Coerce(float),
                    vol.Optional(
                        CONF_SHADING_WAITINGTIME_START,
                        default=self._options.get(CONF_SHADING_WAITINGTIME_START, DEFAULT_SHADING_WAITINGTIME_START),
                    ): vol.Coerce(int),
                    vol.Optional(
                        CONF_SHADING_WAITINGTIME_END,
                        default=self._options.get(CONF_SHADING_WAITINGTIME_END, DEFAULT_SHADING_WAITINGTIME_END),
                    ): vol.Coerce(int),
                    vol.Optional(
                        CONF_SHADING_START_MAX_DURATION,
                        default=self._options.get(CONF_SHADING_START_MAX_DURATION, DEFAULT_SHADING_START_MAX_DURATION),
                    ): vol.Coerce(int),
                    vol.Optional(
                        CONF_SHADING_END_MAX_DURATION,
                        default=self._options.get(CONF_SHADING_END_MAX_DURATION, DEFAULT_SHADING_END_MAX_DURATION),
                    ): vol.Coerce(int),
                    vol.Optional(
                        CONF_SHADING_END_IMMEDIATE_BY_SUN_POSITION,
                        default=bool(
                            self._options.get(
                                CONF_SHADING_END_IMMEDIATE_BY_SUN_POSITION,
                                DEFAULT_SHADING_TIMING_SETTINGS[CONF_SHADING_END_IMMEDIATE_BY_SUN_POSITION],
                            )
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_SHADING_FORECAST_SENSOR,
                        default=self._optional_default(CONF_SHADING_FORECAST_SENSOR),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["sensor", "weather"])
                    ),
                    vol.Optional(
                        CONF_SHADING_FORECAST_TYPE,
                        default=self._options.get(CONF_SHADING_FORECAST_TYPE, DEFAULT_SHADING_FORECAST_TYPE),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": "daily", "label": "Use the daily weather forecast service"},
                                {"value": "hourly", "label": "Use the hourly weather forecast service"},
                                {"value": "weather_attributes", "label": "Use current weather attributes"},
                            ]
                        )
                    ),
                    vol.Optional(
                        CONF_SHADING_WEATHER_CONDITIONS,
                        default=self._options.get(CONF_SHADING_WEATHER_CONDITIONS, []),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                "clear-night", "clear", "cloudy", "fog", "hail", "lightning", "lightning-rainy",
                                "partlycloudy", "pouring", "rainy", "snowy", "snowy-rainy", "sunny", "windy",
                                "windy-variant", "exceptional",
                            ],
                            multiple=True,
                        )
                    ),
                }
            ),
        )

    async def _save_options(self, user_input: dict, include_contacts: bool = False) -> None:
        clean_input = _normalize_position_fields(self._clean_user_input(user_input))
        name = str(clean_input.pop(CONF_NAME, self._config_entry.title)).strip() or DEFAULT_NAME

        if include_contacts:
            covers = self._options.get(CONF_COVERS, [])
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
        self._options = self._normalize_options(
            None,
            overrides,
            base_options=self._options,
        )

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
