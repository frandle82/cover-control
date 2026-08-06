"""Cover controller behavior split from the public controller facade."""

from __future__ import annotations

from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)

from ..const import (
    CONF_BRIGHTNESS_SENSOR,
    CONF_SHADING_BRIGHTNESS_END,
    CONF_SHADING_BRIGHTNESS_HYSTERESIS,
    CONF_SHADING_BRIGHTNESS_SENSOR,
    CONF_SHADING_BRIGHTNESS_START,
    CONF_SHADING_CONDITIONS_END_AND,
    CONF_SHADING_CONDITIONS_END_OR,
    CONF_SHADING_CONDITIONS_START_AND,
    CONF_SHADING_CONDITIONS_START_OR,
    CONF_SHADING_CONFIG,
    CONF_SHADING_FORECAST_SENSOR,
    CONF_SHADING_FORECAST_TEMP,
    CONF_SHADING_FORECAST_TEMP_HYSTERESIS,
    CONF_SHADING_FORECAST_TEMP_SENSOR,
    CONF_SHADING_FORECAST_TYPE,
    CONF_SHADING_INDEPENDENT_TEMP,
    CONF_SHADING_MIN_TEMPERATURE_1,
    CONF_SHADING_MIN_TEMPERATURE_2,
    CONF_SHADING_TEMPERATURE_HYSTERESIS_1,
    CONF_SHADING_TEMPERATURE_HYSTERESIS_2,
    CONF_SHADING_TEMPERATURE_SENSOR_1,
    CONF_SHADING_TEMPERATURE_SENSOR_2,
    CONF_SHADING_WEATHER_CONDITIONS,
    CONF_SUN_AZIMUTH_END,
    CONF_SUN_AZIMUTH_START,
    CONF_SUN_ELEVATION_MAX,
    CONF_SUN_ELEVATION_MIN,
    CONF_TEMPERATURE_FORECAST_THRESHOLD,
    CONF_TEMPERATURE_SENSOR_INDOOR,
    CONF_TEMPERATURE_SENSOR_OUTDOOR,
    CONF_TEMPERATURE_THRESHOLD,
    DEFAULT_SHADING_BRIGHTNESS_END,
    DEFAULT_SHADING_BRIGHTNESS_HYSTERESIS,
    DEFAULT_SHADING_BRIGHTNESS_START,
    DEFAULT_SHADING_CONDITIONS_END_AND,
    DEFAULT_SHADING_CONDITIONS_END_OR,
    DEFAULT_SHADING_CONDITIONS_START_AND,
    DEFAULT_SHADING_CONDITIONS_START_OR,
    DEFAULT_SHADING_FORECAST_TEMP_HYSTERESIS,
    DEFAULT_SHADING_FORECAST_TYPE,
    DEFAULT_SHADING_INDEPENDENT_TEMP,
    DEFAULT_SHADING_MIN_TEMPERATURE_1,
    DEFAULT_SHADING_MIN_TEMPERATURE_2,
    DEFAULT_SHADING_TEMPERATURE_HYSTERESIS_1,
    DEFAULT_SHADING_TEMPERATURE_HYSTERESIS_2,
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
from .common import (
    _LOGGER,
    _coerce_float,
    _float_state,
)


class ShadingMixin:
    def _shading_config_list(self, key: str, default: list[str]) -> list[str]:
        value = self.config.get(key, default)
        if isinstance(value, str):
            return [value]
        if isinstance(value, list | tuple | set):
            return [str(item) for item in value if item]
        return list(default)

    def _shading_brightness_value(self, fallback: float | None) -> float | None:
        sensor = self.config.get(CONF_SHADING_BRIGHTNESS_SENSOR) or self.config.get(
            CONF_BRIGHTNESS_SENSOR
        )
        if not sensor:
            return fallback
        return _float_state(self.hass, sensor)

    async def _async_update_shading_forecast(self) -> None:
        forecast_entity = self.config.get(CONF_SHADING_FORECAST_SENSOR)
        forecast_type = self.config.get(
            CONF_SHADING_FORECAST_TYPE, DEFAULT_SHADING_FORECAST_TYPE
        )
        self._shading_forecast_cache = None
        if not forecast_entity or forecast_type in (None, "weather_attributes"):
            return

        state = self.hass.states.get(forecast_entity)
        if state is None or not state.entity_id.startswith("weather."):
            return

        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": forecast_entity, "type": forecast_type},
                blocking=True,
                return_response=True,
            )
        except Exception as err:  # noqa: BLE001 - HA service availability varies by version.
            _LOGGER.debug(
                "Cover Control could not fetch %s forecast for %s: %s",
                forecast_type,
                forecast_entity,
                err,
            )
            return

        payload = response.get(forecast_entity) if isinstance(response, dict) else None
        forecast = payload.get("forecast") if isinstance(payload, dict) else None
        if isinstance(forecast, list):
            self._shading_forecast_cache = {
                "entity_id": forecast_entity,
                "forecast": forecast,
            }

    def _cached_shading_forecast(self, forecast_entity: str) -> list | None:
        cache = self._shading_forecast_cache
        if not isinstance(cache, dict) or cache.get("entity_id") != forecast_entity:
            return None
        forecast = cache.get("forecast")
        return forecast if isinstance(forecast, list) else None

    def _shading_forecast_temperature(self) -> float | None:
        temp_sensor = self.config.get(CONF_SHADING_FORECAST_TEMP_SENSOR)
        if temp_sensor:
            value = _float_state(self.hass, temp_sensor)
            if value is not None:
                return value

        forecast_entity = self.config.get(CONF_SHADING_FORECAST_SENSOR)
        if not forecast_entity:
            return None
        state = self.hass.states.get(forecast_entity)
        if state is None:
            return None

        if state.entity_id.startswith("sensor."):
            return _coerce_float(state.state)

        if not state.entity_id.startswith("weather."):
            return None

        forecast_type = self.config.get(
            CONF_SHADING_FORECAST_TYPE, DEFAULT_SHADING_FORECAST_TYPE
        )
        if forecast_type in (None, "weather_attributes"):
            for key in ("temperature", "templow"):
                value = _coerce_float(state.attributes.get(key))
                if value is not None:
                    return value

        forecast = self._cached_shading_forecast(forecast_entity)
        if forecast is None:
            forecast = state.attributes.get("forecast")
        if not isinstance(forecast, list) or not forecast:
            return None
        first = forecast[0] or {}
        for key in ("temperature", "templow"):
            value = _coerce_float(first.get(key))
            if value is not None:
                return value
        return None

    def _shading_forecast_weather_condition(self) -> str | None:
        forecast_entity = self.config.get(CONF_SHADING_FORECAST_SENSOR)
        if not forecast_entity:
            return None
        state = self.hass.states.get(forecast_entity)
        if state is None or not state.entity_id.startswith("weather."):
            return None

        forecast_type = self.config.get(
            CONF_SHADING_FORECAST_TYPE, DEFAULT_SHADING_FORECAST_TYPE
        )
        if forecast_type in (None, "weather_attributes"):
            return (
                state.state
                if state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
                else None
            )

        forecast = self._cached_shading_forecast(forecast_entity)
        if forecast is None:
            forecast = state.attributes.get("forecast")
        if isinstance(forecast, list) and forecast:
            value = (forecast[0] or {}).get("condition")
            if isinstance(value, str) and value:
                return value
        return None

    def _shading_condition_state(
        self,
        sun_azimuth: float | None,
        sun_elevation: float | None,
        brightness: float | None,
    ) -> dict[str, object]:
        az_start = self._number_value(CONF_SUN_AZIMUTH_START, 95)
        az_end = self._number_value(CONF_SUN_AZIMUTH_END, 265)
        el_min = self._number_value(CONF_SUN_ELEVATION_MIN, 25)
        el_max = self._number_value(CONF_SUN_ELEVATION_MAX, 90)
        shading_brightness = self._shading_brightness_value(brightness)
        brightness_sensor = self.config.get(
            CONF_SHADING_BRIGHTNESS_SENSOR
        ) or self.config.get(CONF_BRIGHTNESS_SENSOR)
        bright_start = self._number_value(
            CONF_SHADING_BRIGHTNESS_START, DEFAULT_SHADING_BRIGHTNESS_START
        )
        bright_end = self._number_value(
            CONF_SHADING_BRIGHTNESS_END, DEFAULT_SHADING_BRIGHTNESS_END
        )
        bright_hysteresis = self._number_value(
            CONF_SHADING_BRIGHTNESS_HYSTERESIS, DEFAULT_SHADING_BRIGHTNESS_HYSTERESIS
        )

        temp1_sensor = self.config.get(
            CONF_SHADING_TEMPERATURE_SENSOR_1
        ) or self.config.get(CONF_TEMPERATURE_SENSOR_INDOOR)
        temp2_sensor = self.config.get(
            CONF_SHADING_TEMPERATURE_SENSOR_2
        ) or self.config.get(CONF_TEMPERATURE_SENSOR_OUTDOOR)
        temp1 = _float_state(self.hass, temp1_sensor)
        temp2 = _float_state(self.hass, temp2_sensor)
        temp1_min = _coerce_float(
            self.config.get(
                CONF_SHADING_MIN_TEMPERATURE_1,
                self.config.get(
                    CONF_TEMPERATURE_THRESHOLD, DEFAULT_SHADING_MIN_TEMPERATURE_1
                ),
            )
        )
        temp2_min = _coerce_float(
            self.config.get(
                CONF_SHADING_MIN_TEMPERATURE_2,
                self.config.get(
                    CONF_TEMPERATURE_THRESHOLD, DEFAULT_SHADING_MIN_TEMPERATURE_2
                ),
            )
        )
        if temp1_min is None:
            temp1_min = DEFAULT_SHADING_MIN_TEMPERATURE_1
        if temp2_min is None:
            temp2_min = DEFAULT_SHADING_MIN_TEMPERATURE_2
        temp1_hysteresis = self._number_value(
            CONF_SHADING_TEMPERATURE_HYSTERESIS_1,
            DEFAULT_SHADING_TEMPERATURE_HYSTERESIS_1,
        )
        temp2_hysteresis = self._number_value(
            CONF_SHADING_TEMPERATURE_HYSTERESIS_2,
            DEFAULT_SHADING_TEMPERATURE_HYSTERESIS_2,
        )

        forecast_temp_limit = _coerce_float(
            self.config.get(
                CONF_SHADING_FORECAST_TEMP,
                self.config.get(CONF_TEMPERATURE_FORECAST_THRESHOLD),
            )
        )
        forecast_temp_hysteresis = self._number_value(
            CONF_SHADING_FORECAST_TEMP_HYSTERESIS,
            DEFAULT_SHADING_FORECAST_TEMP_HYSTERESIS,
        )
        forecast_temp = self._shading_forecast_temperature()
        config_flags = self._shading_config_list(CONF_SHADING_CONFIG, [])
        compare_forecast_with_sensor2 = (
            SHADING_CONFIG_COMPARE_FORECAST_SENSOR2 in config_flags
        )
        forecast_temp_start_valid = forecast_temp_limit is not None and (
            (
                forecast_temp is not None
                and forecast_temp > forecast_temp_limit + forecast_temp_hysteresis
            )
            or (
                compare_forecast_with_sensor2
                and temp2 is not None
                and temp2 > forecast_temp_limit + forecast_temp_hysteresis
            )
        )

        weather_conditions = self._shading_config_list(
            CONF_SHADING_WEATHER_CONDITIONS, []
        )
        direct_forecast_temp_sensor = bool(
            self.config.get(CONF_SHADING_FORECAST_TEMP_SENSOR)
        )
        forecast_weather = self._shading_forecast_weather_condition()

        configured = {
            SHADING_CONDITION_AZIMUTH: sun_azimuth is not None,
            SHADING_CONDITION_ELEVATION: sun_elevation is not None,
            SHADING_CONDITION_BRIGHTNESS: bool(brightness_sensor),
            SHADING_CONDITION_TEMP_1: bool(temp1_sensor),
            SHADING_CONDITION_TEMP_2: bool(temp2_sensor),
            SHADING_CONDITION_FORECAST_TEMP: forecast_temp_limit is not None,
            SHADING_CONDITION_FORECAST_WEATHER: bool(weather_conditions),
        }
        start_valid = {
            SHADING_CONDITION_AZIMUTH: (
                sun_azimuth is not None and az_start < sun_azimuth < az_end
            ),
            SHADING_CONDITION_ELEVATION: (
                sun_elevation is not None and el_min < sun_elevation < el_max
            ),
            SHADING_CONDITION_BRIGHTNESS: (
                shading_brightness is not None
                and shading_brightness > bright_start + bright_hysteresis
            ),
            SHADING_CONDITION_TEMP_1: (
                temp1 is not None and temp1 > temp1_min + temp1_hysteresis
            ),
            SHADING_CONDITION_TEMP_2: (
                temp2 is not None and temp2 > temp2_min + temp2_hysteresis
            ),
            SHADING_CONDITION_FORECAST_TEMP: forecast_temp_start_valid,
            SHADING_CONDITION_FORECAST_WEATHER: (
                direct_forecast_temp_sensor
                or not weather_conditions
                or forecast_weather in weather_conditions
            ),
        }
        end_invalid = {
            SHADING_CONDITION_AZIMUTH: (
                sun_azimuth is not None
                and (sun_azimuth <= az_start or sun_azimuth >= az_end)
            ),
            SHADING_CONDITION_ELEVATION: (
                sun_elevation is not None
                and (sun_elevation <= el_min or sun_elevation >= el_max)
            ),
            SHADING_CONDITION_BRIGHTNESS: (
                shading_brightness is not None
                and shading_brightness < bright_end - bright_hysteresis
            ),
            SHADING_CONDITION_TEMP_1: (
                temp1 is not None and temp1 < temp1_min - temp1_hysteresis
            ),
            SHADING_CONDITION_TEMP_2: (
                temp2 is not None and temp2 < temp2_min - temp2_hysteresis
            ),
            SHADING_CONDITION_FORECAST_TEMP: (
                forecast_temp_limit is not None
                and forecast_temp is not None
                and forecast_temp < forecast_temp_limit - forecast_temp_hysteresis
            ),
            SHADING_CONDITION_FORECAST_WEATHER: (
                bool(weather_conditions)
                and not direct_forecast_temp_sensor
                and forecast_weather not in weather_conditions
            ),
        }
        return {
            "configured": configured,
            "start_valid": start_valid,
            "end_invalid": end_invalid,
            "forecast_temp_valid": start_valid[SHADING_CONDITION_FORECAST_TEMP],
            "forecast_temp": forecast_temp,
            "temperature_2": temp2,
            "compare_forecast_with_sensor2": compare_forecast_with_sensor2,
            "forecast_temp_hysteresis": forecast_temp_hysteresis,
        }

    def _shading_start_conditions(
        self,
        sun_azimuth: float | None,
        sun_elevation: float | None,
        brightness: float | None,
    ) -> tuple[bool, bool]:
        state = self._shading_condition_state(sun_azimuth, sun_elevation, brightness)
        configured = state["configured"]
        start_valid = state["start_valid"]
        assert isinstance(configured, dict)
        assert isinstance(start_valid, dict)

        start_and = self._shading_config_list(
            CONF_SHADING_CONDITIONS_START_AND, DEFAULT_SHADING_CONDITIONS_START_AND
        )
        start_or = self._shading_config_list(
            CONF_SHADING_CONDITIONS_START_OR, DEFAULT_SHADING_CONDITIONS_START_OR
        )
        and_result = all(
            start_valid.get(condition, False)
            for condition in start_and
            if configured.get(condition, False)
        )
        or_result = not start_or or any(
            configured.get(condition, False) and start_valid.get(condition, False)
            for condition in start_or
        )
        config_flags = self._shading_config_list(CONF_SHADING_CONFIG, [])
        temp_independent = False
        if SHADING_CONFIG_TEMP_INDEPENDENT in config_flags:
            independent_limit = _coerce_float(
                self.config.get(
                    CONF_SHADING_INDEPENDENT_TEMP, DEFAULT_SHADING_INDEPENDENT_TEMP
                )
            )
            if independent_limit is None:
                independent_limit = DEFAULT_SHADING_INDEPENDENT_TEMP
            forecast_temp = _coerce_float(state["forecast_temp"])
            temperature_2 = _coerce_float(state["temperature_2"])
            forecast_temp_hysteresis = _coerce_float(state["forecast_temp_hysteresis"])
            if forecast_temp_hysteresis is None:
                forecast_temp_hysteresis = DEFAULT_SHADING_FORECAST_TEMP_HYSTERESIS
            temp_independent = (
                forecast_temp is not None
                and forecast_temp > independent_limit + forecast_temp_hysteresis
            ) or (
                bool(state["compare_forecast_with_sensor2"])
                and temperature_2 is not None
                and temperature_2 > independent_limit + forecast_temp_hysteresis
            )
        return and_result and or_result, temp_independent

    def _shading_end_conditions(
        self,
        sun_azimuth: float | None,
        sun_elevation: float | None,
        brightness: float | None,
    ) -> bool:
        state = self._shading_condition_state(sun_azimuth, sun_elevation, brightness)
        configured = state["configured"]
        end_invalid = state["end_invalid"]
        assert isinstance(configured, dict)
        assert isinstance(end_invalid, dict)

        end_and = self._shading_config_list(
            CONF_SHADING_CONDITIONS_END_AND, DEFAULT_SHADING_CONDITIONS_END_AND
        )
        end_or = self._shading_config_list(
            CONF_SHADING_CONDITIONS_END_OR, DEFAULT_SHADING_CONDITIONS_END_OR
        )
        configured_end_and = [
            condition for condition in end_and if configured.get(condition, False)
        ]
        and_result = bool(configured_end_and) and all(
            end_invalid.get(condition, False) for condition in configured_end_and
        )
        or_result = any(
            configured.get(condition, False) and end_invalid.get(condition, False)
            for condition in end_or
        )
        return and_result or or_result
