"""Switch entities to control automation toggles."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_MANUAL_OVERRIDE_MINUTES,
    CONF_MANUAL_OVERRIDE_RESET_TIME,
    CONF_EXPOSE_SWITCH_SETTINGS,
    CONF_CLOSE_POSITION,
    CONF_OPEN_POSITION,
    CONF_POSITION_TOLERANCE,
    CONF_SHADING_BRIGHTNESS_END,
    CONF_SHADING_BRIGHTNESS_START,
    CONF_SHADING_POSITION,
    CONF_SHADING_FORECAST_TYPE,
    CONF_TEMPERATURE_THRESHOLD,
    CONF_TEMPERATURE_FORECAST_THRESHOLD,
    CONF_COLD_PROTECTION_THRESHOLD,
    CONF_SUN_AZIMUTH_END,
    CONF_SUN_AZIMUTH_START,
    CONF_SUN_ELEVATION_CLOSE,
    CONF_SUN_ELEVATION_MODE,
    CONF_SUN_ELEVATION_OPEN_OFFSET,
    CONF_SUN_ELEVATION_CLOSE_OFFSET,
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
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_DOWN,
    CONF_AUTO_SHADING,
    CONF_AUTO_SUN,
    CONF_AUTO_TIME,
    CONF_AUTO_UP,
    CONF_AUTO_VENTILATE,
    CONF_MASTER_ENABLED,
    CONF_VENTILATE_POSITION,
    CONF_BRIGHTNESS_SENSOR,
    CONF_BRIGHTNESS_OPEN_ABOVE,
    CONF_BRIGHTNESS_CLOSE_BELOW,
    CONF_NAME,
    DEFAULT_AUTOMATION_FLAGS,
    DEFAULT_BRIGHTNESS_CLOSE,
    DEFAULT_BRIGHTNESS_OPEN,
    DEFAULT_NAME,
    DEFAULT_SHADING_AZIMUTH_END,
    DEFAULT_SHADING_AZIMUTH_START,
    DEFAULT_SHADING_BRIGHTNESS_END,
    DEFAULT_SHADING_BRIGHTNESS_START,
    DEFAULT_SHADING_ELEVATION_MAX,
    DEFAULT_SHADING_ELEVATION_MIN,
    DEFAULT_SHADING_POSITION,
    DEFAULT_SUN_ELEVATION_CLOSE,
    DEFAULT_SUN_ELEVATION_OPEN,
    DEFAULT_SUN_ELEVATION_MODE,
    DEFAULT_SUN_ELEVATION_OPEN_OFFSET,
    DEFAULT_SUN_ELEVATION_CLOSE_OFFSET,
    DEFAULT_OPEN_POSITION,
    DEFAULT_CLOSE_POSITION,
    DEFAULT_MASTER_FLAGS,
    DEFAULT_POSITION_SETTINGS,
    DEFAULT_TIME_SETTINGS,
    DEFAULT_TIME_DOWN_EARLY_NON_WORKDAY,
    DEFAULT_TIME_DOWN_EARLY_WORKDAY,
    DEFAULT_TIME_DOWN_LATE_NON_WORKDAY,
    DEFAULT_TIME_DOWN_LATE_WORKDAY,
    DEFAULT_TIME_UP_EARLY_NON_WORKDAY,
    DEFAULT_TIME_UP_EARLY_WORKDAY,
    DEFAULT_TIME_UP_LATE_NON_WORKDAY,
    DEFAULT_TIME_UP_LATE_WORKDAY,
    DEFAULT_VENTILATE_POSITION,
    DEFAULT_TOLERANCE,
    DEFAULT_CONTACT_SETTINGS,
    DEFAULT_MANUAL_OVERRIDE_MINUTES,
    DEFAULT_MANUAL_OVERRIDE_RESET_TIME,
    DEFAULT_MANUAL_OVERRIDE_FLAGS,
    DEFAULT_SHADING_FORECAST_TYPE,
    DEFAULT_TEMPERATURE_THRESHOLD,
    DEFAULT_TEMPERATURE_FORECAST_THRESHOLD,
    DEFAULT_COLD_PROTECTION_THRESHOLD,
    REASON_LABELS,
    DOMAIN,
    SIGNAL_STATE_UPDATED,
)
from .controller import ControllerManager


AUTOMATION_TOGGLES: tuple[tuple[str, str], ...] = (
    (CONF_AUTO_TIME, "auto_time"),
    (CONF_AUTO_VENTILATE, "auto_ventilate"),
    (CONF_AUTO_BRIGHTNESS, "auto_brightness"),
    (CONF_AUTO_SHADING, "auto_shading"),
)

TOGGLE_ICONS: dict[str, str] = {
    CONF_AUTO_TIME: "mdi:clock-time-eight-auto",
    CONF_AUTO_VENTILATE: "mdi:door-open",
    CONF_AUTO_BRIGHTNESS: "mdi:brightness-auto",
    CONF_AUTO_SHADING: "mdi:theme-light-dark",
}

DEFAULT_LOOKUP = {
    CONF_BRIGHTNESS_OPEN_ABOVE: DEFAULT_BRIGHTNESS_OPEN,
    CONF_BRIGHTNESS_CLOSE_BELOW: DEFAULT_BRIGHTNESS_CLOSE,
    CONF_VENTILATE_POSITION: DEFAULT_VENTILATE_POSITION,
    CONF_POSITION_TOLERANCE: DEFAULT_TOLERANCE,
    CONF_SHADING_POSITION: DEFAULT_SHADING_POSITION,
    CONF_SHADING_BRIGHTNESS_START: DEFAULT_SHADING_BRIGHTNESS_START,
    CONF_SHADING_BRIGHTNESS_END: DEFAULT_SHADING_BRIGHTNESS_END,
    CONF_SUN_AZIMUTH_START: DEFAULT_SHADING_AZIMUTH_START,
    CONF_SUN_AZIMUTH_END: DEFAULT_SHADING_AZIMUTH_END,
    CONF_SUN_ELEVATION_MIN: DEFAULT_SHADING_ELEVATION_MIN,
    CONF_SUN_ELEVATION_MAX: DEFAULT_SHADING_ELEVATION_MAX,
    CONF_SUN_ELEVATION_OPEN: DEFAULT_SUN_ELEVATION_OPEN,
    CONF_SUN_ELEVATION_CLOSE: DEFAULT_SUN_ELEVATION_CLOSE,
    CONF_SUN_ELEVATION_MODE: DEFAULT_SUN_ELEVATION_MODE,
    CONF_SUN_ELEVATION_OPEN_OFFSET: DEFAULT_SUN_ELEVATION_OPEN_OFFSET,
    CONF_SUN_ELEVATION_CLOSE_OFFSET: DEFAULT_SUN_ELEVATION_CLOSE_OFFSET,
    CONF_TIME_UP_EARLY_WORKDAY: DEFAULT_TIME_UP_EARLY_WORKDAY,
    CONF_TIME_UP_LATE_WORKDAY: DEFAULT_TIME_UP_LATE_WORKDAY,
    CONF_TIME_DOWN_EARLY_WORKDAY: DEFAULT_TIME_DOWN_EARLY_WORKDAY,
    CONF_TIME_DOWN_LATE_WORKDAY: DEFAULT_TIME_DOWN_LATE_WORKDAY,
    CONF_TIME_UP_EARLY_NON_WORKDAY: DEFAULT_TIME_UP_EARLY_NON_WORKDAY,
    CONF_TIME_UP_LATE_NON_WORKDAY: DEFAULT_TIME_UP_LATE_NON_WORKDAY,
    CONF_TIME_DOWN_EARLY_NON_WORKDAY: DEFAULT_TIME_DOWN_EARLY_NON_WORKDAY,
    CONF_TIME_DOWN_LATE_NON_WORKDAY: DEFAULT_TIME_DOWN_LATE_NON_WORKDAY,
    CONF_OPEN_POSITION: DEFAULT_OPEN_POSITION,
    CONF_CLOSE_POSITION: DEFAULT_CLOSE_POSITION,
}

MASTER_DEFAULT_LOOKUP = {
    **DEFAULT_LOOKUP,
    **DEFAULT_POSITION_SETTINGS,
    **DEFAULT_TIME_SETTINGS,
    **DEFAULT_AUTOMATION_FLAGS,
    **DEFAULT_MASTER_FLAGS,
    **DEFAULT_MANUAL_OVERRIDE_FLAGS,
    **DEFAULT_CONTACT_SETTINGS,
    CONF_MANUAL_OVERRIDE_MINUTES: DEFAULT_MANUAL_OVERRIDE_MINUTES,
    CONF_MANUAL_OVERRIDE_RESET_TIME: DEFAULT_MANUAL_OVERRIDE_RESET_TIME,
    CONF_SHADING_FORECAST_TYPE: DEFAULT_SHADING_FORECAST_TYPE,
    CONF_TEMPERATURE_THRESHOLD: DEFAULT_TEMPERATURE_THRESHOLD,
    CONF_TEMPERATURE_FORECAST_THRESHOLD: DEFAULT_TEMPERATURE_FORECAST_THRESHOLD,
    CONF_COLD_PROTECTION_THRESHOLD: DEFAULT_COLD_PROTECTION_THRESHOLD,
}

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Register automation toggle switches."""

    options_and_data = {**entry.data, **entry.options}

    def _is_enabled_in_flow(key: str) -> bool:
        if key in options_and_data:
            return bool(options_and_data.get(key))
        return bool(DEFAULT_AUTOMATION_FLAGS.get(key, True))

    enabled_keys = {
        key for key, _translation_key in AUTOMATION_TOGGLES if _is_enabled_in_flow(key)
    }
    registry = er.async_get(hass)
    for entity_entry in list(registry.entities.values()):
        if entity_entry.config_entry_id != entry.entry_id or entity_entry.domain != "switch":
            continue
        unique_id = entity_entry.unique_id or ""
        if unique_id == f"{entry.entry_id}-master":
            registry.async_remove(entity_entry.entity_id)
            continue
        key = unique_id.removeprefix(f"{entry.entry_id}-")
        if key in {CONF_AUTO_UP, CONF_AUTO_DOWN} or key not in enabled_keys:
            registry.async_remove(entity_entry.entity_id)

    entities: list[SwitchEntity] = [
        AutomationToggleSwitch(entry, key, translation_key)
        for key, translation_key in AUTOMATION_TOGGLES
        if key in enabled_keys
    ]

    async_add_entities(entities)


class AutomationToggleSwitch(SwitchEntity):
    """Switch to enable or disable automation features."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: ConfigEntry, key: str, translation_key: str) -> None:
        self.entry = entry
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}-{key}"
        self._attr_translation_key = translation_key
        self._attr_icon = TOGGLE_ICONS.get(key)
        self._attr_friendly_name = translation_key

    async def async_added_to_hass(self) -> None:
        """Handle entity addition and keep state in sync with options."""

        self.async_on_remove(
            self.entry.add_update_listener(self._handle_entry_update)
        )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=self.entry.options.get(
                CONF_NAME,
                self.entry.data.get(CONF_NAME, self.entry.title or DEFAULT_NAME),
            ),
            manufacturer="CCA-derived",
        )

    @property
    def is_on(self) -> bool:
        value = self.entry.options.get(self._key)
        if value is None:
            value = self.entry.data.get(self._key, DEFAULT_AUTOMATION_FLAGS.get(self._key))
        return bool(value)

    @property
    def extra_state_attributes(self):
        return None

    async def async_turn_on(self, **kwargs) -> None:  # type: ignore[override]
        options = {**self.entry.options, self._key: True}
        if self._key == CONF_AUTO_TIME:
            options[CONF_AUTO_UP] = True
            options[CONF_AUTO_DOWN] = True
        self.hass.config_entries.async_update_entry(self.entry, options=options)

    async def async_turn_off(self, **kwargs) -> None:  # type: ignore[override]
        options = {**self.entry.options, self._key: False}
        if self._key == CONF_AUTO_TIME:
            options[CONF_AUTO_UP] = False
            options[CONF_AUTO_DOWN] = False
        self.hass.config_entries.async_update_entry(self.entry, options=options)

    async def _handle_entry_update(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Refresh state when config entry is updated."""

        self.async_write_ha_state()
