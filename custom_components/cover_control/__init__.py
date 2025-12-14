"""Set up the Cover Control integration."""
from __future__ import annotations

from datetime import datetime, time
from typing import Mapping

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import service as service_helper
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_DOWN,
    CONF_AUTO_SHADING,
    CONF_AUTO_SUN,
    CONF_AUTO_UP,
    CONF_AUTO_VENTILATE,
    CONF_BRIGHTNESS_CLOSE_BELOW,
    CONF_BRIGHTNESS_OPEN_ABOVE,
    CONF_BRIGHTNESS_SENSOR,
    CONF_COVERS,
    CONF_CLOSE_POSITION,
    CONF_FULL_OPEN_POSITION,
    CONF_OPEN_POSITION,
    CONF_POSITION_TOLERANCE,
    CONF_MANUAL_OVERRIDE_MINUTES,
    DEFAULT_MANUAL_OVERRIDE_MINUTES,
    DEFAULT_OPEN_POSITION,
    CONF_SHADING_BRIGHTNESS_END,
    CONF_SHADING_BRIGHTNESS_START,
    CONF_SHADING_POSITION,
    CONF_SUN_AZIMUTH_END,
    CONF_SUN_AZIMUTH_START,
    CONF_SUN_ELEVATION_CLOSE,
    CONF_SUN_ELEVATION_MAX,
    CONF_SUN_ELEVATION_MIN,
    CONF_SUN_ELEVATION_OPEN,
    CONF_TIME_DOWN_EARLY_NON_WORKDAY,
    CONF_TIME_DOWN_EARLY_WORKDAY,
    CONF_TIME_DOWN_LATE_NON_WORKDAY,
    CONF_TIME_DOWN_LATE_WORKDAY,
    CONF_TIME_UP_EARLY_NON_WORKDAY,
    CONF_TIME_UP_EARLY_WORKDAY,
    CONF_TIME_UP_LATE_NON_WORKDAY,
    CONF_TIME_UP_LATE_WORKDAY,
    CONF_VENTILATE_POSITION,
    DOMAIN,
    PLATFORMS,
)
from .controller import ControllerManager

SERVICE_MANUAL_OVERRIDE = "set_manual_override"
SERVICE_ACTIVATE_SHADING = "activate_shading"
SERVICE_CLEAR_MANUAL_OVERRIDE = "clear_manual_override"
SERVICE_RECALIBRATE = "recalibrate_cover"
SERVICE_CHANGE_SWITCH_SETTINGS = "change_switch_settings"
SERVICE_FORCE_ACTION = "force_action"


def _parse_service_time(value: object) -> time:
    """Coerce service input into a time object or raise a validation error."""

    if isinstance(value, time):
        return value
    if isinstance(value, datetime):
        return value.timetz()

    parsed = dt_util.parse_time(str(value)) if value not in (None, "") else None
    if not parsed:
        raise vol.Invalid("Expect HH:MM formatted time")
    return parsed


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize integration-level storage and services."""
    hass.data.setdefault(DOMAIN, {})

    async def _async_get_single_cover(call) -> str:
        cover = call.data.get(CONF_COVERS)
        if isinstance(cover, list):
            if len(cover) != 1:
                raise ValueError("Provide a single cover entity")
            return cover[0]
        if cover:
            return cover

        entity_ids = await service_helper.async_extract_entity_ids(hass, call)
        if not entity_ids:
            raise ValueError("No cover entity provided")
        if len(entity_ids) != 1:
            raise ValueError("Provide a single cover entity")
        return next(iter(entity_ids))

    if SERVICE_MANUAL_OVERRIDE not in hass.services.async_services_for_domain(DOMAIN):
        async def handle_manual_override(call):
            cover = await _async_get_single_cover(call)
            minutes = call.data.get(CONF_MANUAL_OVERRIDE_MINUTES, DEFAULT_MANUAL_OVERRIDE_MINUTES)
            matched = False
            for manager in hass.data.get(DOMAIN, {}).values():
                if isinstance(manager, ControllerManager) and manager.set_manual_override(cover, minutes):
                    matched = True
                    break
            if not matched:
                raise ValueError(f"No controller registered for {cover}")

        hass.services.async_register(
            DOMAIN,
            SERVICE_MANUAL_OVERRIDE,
            handle_manual_override,
            schema=vol.Schema(
                {
                    vol.Optional(ATTR_ENTITY_ID): vol.Any(cv.entity_id, cv.entity_ids),
                    vol.Optional(CONF_MANUAL_OVERRIDE_MINUTES): cv.positive_int,
                }
            ),
        )

    if SERVICE_ACTIVATE_SHADING not in hass.services.async_services_for_domain(DOMAIN):
        async def handle_activate_shading(call):
            cover = await _async_get_single_cover(call)
            minutes = call.data.get(CONF_MANUAL_OVERRIDE_MINUTES)
            matched = False
            for manager in hass.data.get(DOMAIN, {}).values():
                if isinstance(manager, ControllerManager) and manager.activate_shading(cover, minutes):
                    matched = True
                    break
            if not matched:
                raise ValueError(f"No controller registered for {cover}")

        hass.services.async_register(
            DOMAIN,
            SERVICE_ACTIVATE_SHADING,
            handle_activate_shading,
            schema=vol.Schema(
                {
                    vol.Optional(ATTR_ENTITY_ID): vol.Any(cv.entity_id, cv.entity_ids),
                    vol.Optional(CONF_MANUAL_OVERRIDE_MINUTES): cv.positive_int,
                }
            ),
        )
    if SERVICE_CLEAR_MANUAL_OVERRIDE not in hass.services.async_services_for_domain(DOMAIN):
        async def handle_clear_manual_override(call):
            cover = await _async_get_single_cover(call)
            matched = False
            for manager in hass.data.get(DOMAIN, {}).values():
                if isinstance(manager, ControllerManager) and manager.clear_manual_override(cover):
                    matched = True
                    break
            if not matched:
                raise ValueError(f"No controller registered for {cover}")

        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEAR_MANUAL_OVERRIDE,
            handle_clear_manual_override,
            schema=vol.Schema(
                {vol.Optional(ATTR_ENTITY_ID): vol.Any(cv.entity_id, cv.entity_ids)}
            ),
        )
    if SERVICE_RECALIBRATE not in hass.services.async_services_for_domain(DOMAIN):
        async def handle_recalibrate(call):
            cover = await _async_get_single_cover(call)
            full_open = call.data.get(CONF_FULL_OPEN_POSITION, DEFAULT_OPEN_POSITION)
            matched = False
            for manager in hass.data.get(DOMAIN, {}).values():
                if isinstance(manager, ControllerManager):
                    if await manager.recalibrate_cover(cover, full_open):
                        matched = True
                        break
            if not matched:
                raise ValueError(f"No controller registered for {cover}")

        hass.services.async_register(
            DOMAIN,
            SERVICE_RECALIBRATE,
            handle_recalibrate,
            schema=vol.Schema(
                {
                    vol.Optional(ATTR_ENTITY_ID): vol.Any(cv.entity_id, cv.entity_ids),
                    vol.Optional(CONF_FULL_OPEN_POSITION, default=DEFAULT_OPEN_POSITION): vol.All(
                        vol.Coerce(float), vol.Range(min=0, max=100)
                    ),
                }
            ),
        )
    if SERVICE_CHANGE_SWITCH_SETTINGS not in hass.services.async_services_for_domain(DOMAIN):
        time_keys = {
            CONF_TIME_UP_EARLY_WORKDAY,
            CONF_TIME_UP_LATE_WORKDAY,
            CONF_TIME_DOWN_EARLY_WORKDAY,
            CONF_TIME_DOWN_LATE_WORKDAY,
            CONF_TIME_UP_EARLY_NON_WORKDAY,
            CONF_TIME_UP_LATE_NON_WORKDAY,
            CONF_TIME_DOWN_EARLY_NON_WORKDAY,
            CONF_TIME_DOWN_LATE_NON_WORKDAY,
        }

        switch_settings = {
            CONF_AUTO_UP: time_keys,
            CONF_AUTO_DOWN: time_keys,
            CONF_AUTO_VENTILATE: {
                CONF_VENTILATE_POSITION,
                CONF_POSITION_TOLERANCE,
            },
            CONF_AUTO_SHADING: {
                CONF_SHADING_POSITION,
                CONF_SHADING_BRIGHTNESS_START,
                CONF_SHADING_BRIGHTNESS_END,
                CONF_SUN_AZIMUTH_START,
                CONF_SUN_AZIMUTH_END,
                CONF_SUN_ELEVATION_MIN,
                CONF_SUN_ELEVATION_MAX,
            },
            CONF_AUTO_BRIGHTNESS: {
                CONF_BRIGHTNESS_SENSOR,
                CONF_BRIGHTNESS_OPEN_ABOVE,
                CONF_BRIGHTNESS_CLOSE_BELOW,
            },
            CONF_AUTO_SUN: {
                CONF_SUN_ELEVATION_OPEN,
                CONF_SUN_ELEVATION_CLOSE,
                CONF_SUN_AZIMUTH_START,
                CONF_SUN_AZIMUTH_END,
                CONF_OPEN_POSITION,
                CONF_CLOSE_POSITION,
            },
        }

        translation_key_lookup = {
            "auto_up": CONF_AUTO_UP,
            "auto_down": CONF_AUTO_DOWN,
            "auto_ventilate": CONF_AUTO_VENTILATE,
            "auto_shading": CONF_AUTO_SHADING,
            "auto_brightness": CONF_AUTO_BRIGHTNESS,
            "auto_sun": CONF_AUTO_SUN,
        }


        validators: dict[str, object] = {
            CONF_BRIGHTNESS_SENSOR: cv.entity_id,
            CONF_BRIGHTNESS_OPEN_ABOVE: vol.Coerce(float),
            CONF_BRIGHTNESS_CLOSE_BELOW: vol.Coerce(float),
            CONF_VENTILATE_POSITION: vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            CONF_SHADING_POSITION: vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            CONF_SHADING_BRIGHTNESS_START: vol.Coerce(float),
            CONF_SHADING_BRIGHTNESS_END: vol.Coerce(float),
            CONF_SUN_AZIMUTH_START: vol.Coerce(float),
            CONF_SUN_AZIMUTH_END: vol.Coerce(float),
            CONF_SUN_ELEVATION_MIN: vol.Coerce(float),
            CONF_SUN_ELEVATION_MAX: vol.Coerce(float),
            CONF_POSITION_TOLERANCE: vol.Coerce(float),
            CONF_TIME_UP_EARLY_WORKDAY: _parse_service_time,
            CONF_TIME_UP_LATE_WORKDAY: _parse_service_time,
            CONF_TIME_DOWN_EARLY_WORKDAY: _parse_service_time,
            CONF_TIME_DOWN_LATE_WORKDAY: _parse_service_time,
            CONF_TIME_UP_EARLY_NON_WORKDAY: _parse_service_time,
            CONF_TIME_UP_LATE_NON_WORKDAY: _parse_service_time,
            CONF_TIME_DOWN_EARLY_NON_WORKDAY: _parse_service_time,
            CONF_TIME_DOWN_LATE_NON_WORKDAY: _parse_service_time,
            CONF_SUN_ELEVATION_OPEN: vol.Coerce(float),
            CONF_SUN_ELEVATION_CLOSE: vol.Coerce(float),
            CONF_OPEN_POSITION: vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            CONF_CLOSE_POSITION: vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
        }

        optional_fields: dict = {vol.Optional("settings"): dict}
        for key in sorted({item for values in switch_settings.values() for item in values}):
            validator = validators.get(key, cv.string)
            optional_fields[vol.Optional(key)] = validator

        async def handle_change_switch_settings(call):
            entity_id = call.data.get(ATTR_ENTITY_ID)
            provided_settings = {}
            extra_fields = {k: v for k, v in call.data.items() if k in validators}
            raw_settings = call.data.get("settings")
            if raw_settings is None:
                raw_settings = {}
            elif not isinstance(raw_settings, dict):
                raise ValueError("settings must be a mapping when provided")
            provided_settings.update(raw_settings)
            provided_settings.update(extra_fields)

            validated_settings: dict[str, object] = {}
            for key, value in provided_settings.items():
                validator = validators.get(key)
                if not validator:
                    continue
                try:
                    validated_settings[key] = validator(value)
                except vol.Invalid as err:
                    raise ValueError(f"Invalid value for {key}: {err}") from err

            registry = er.async_get(hass)
            entity = registry.async_get(entity_id)
            if not entity or entity.platform != DOMAIN:
                raise ValueError(f"No covercontrol switch found for {entity_id}")

            entry = hass.config_entries.async_get_entry(entity.config_entry_id)
            if not entry:
                raise ValueError(f"No config entry found for {entity_id}")

            key: str | None = None
            if entity.unique_id and entry.entry_id in entity.unique_id:
                parts = entity.unique_id.split(f"{entry.entry_id}-", 1)
                if len(parts) == 2:
                    key = parts[1]
            
            if not key and entity.translation_key:
                key = translation_key_lookup.get(entity.translation_key)

            if not key:
                entity_slug = entity_id.split(".", maxsplit=1)[-1]
                for translation_key, mapped in translation_key_lookup.items():
                    if entity_slug.endswith(translation_key):
                        key = mapped
                        break

            allowed_raw = switch_settings.get(key)

            # If we cannot map to a specific automation toggle, treat the
            # provided switch as the master switch for the instance and allow
            # all editable settings to be updated in one call.
            allowed: set[str] = set(validators) if not allowed_raw else set(allowed_raw)

            filtered = {k: v for k, v in validated_settings.items() if k in allowed}
            if not filtered:
                raise ValueError("No valid settings provided for this switch")

            options = {**entry.options, **filtered}
            hass.config_entries.async_update_entry(entry, options=options)

        hass.services.async_register(
            DOMAIN,
            SERVICE_CHANGE_SWITCH_SETTINGS,
            handle_change_switch_settings,
            schema=vol.Schema(
                {
                    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
                    **optional_fields,
                }
            ),
        )

    if SERVICE_FORCE_ACTION not in hass.services.async_services_for_domain(DOMAIN):
        async def handle_force_action(call):
            cover = await _async_get_single_cover(call)
            action = call.data["action"]
            matched = False
            for manager in hass.data.get(DOMAIN, {}).values():
                if isinstance(manager, ControllerManager) and await manager.force_action(cover, action):
                    matched = True
                    break
            if not matched:
                raise ValueError(f"No controller registered for {cover}")

        hass.services.async_register(
            DOMAIN,
            SERVICE_FORCE_ACTION,
            handle_force_action,
            schema=vol.Schema(
                {
                    vol.Optional(ATTR_ENTITY_ID): vol.Any(cv.entity_id, cv.entity_ids),
                    vol.Required("action"): vol.In(
                        [
                            "open",
                            "close",
                            "ventilate_start",
                            "ventilate_stop",
                            "shading_activate",
                            "shading_deactivate",
                        ]
                    ),
                }
            ),
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load a config entry."""
    registry = er.async_get(hass)
    for entity_entry in list(registry.entities.values()):
        if entity_entry.config_entry_id != entry.entry_id:
            continue
        if entity_entry.domain in {"number", "text", "time", "sensor"}:
            registry.async_remove(entity_entry.entity_id)
    
    manager = ControllerManager(hass, entry)
    await manager.async_setup()
    hass.data[DOMAIN][entry.entry_id] = manager

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_handle_options_update))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    manager: ControllerManager | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if manager:
        await manager.async_unload()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _handle_options_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
    manager: ControllerManager | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if manager:
        manager.async_update_options()
