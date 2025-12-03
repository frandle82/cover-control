"""Time entities to configure open/close windows."""
from __future__ import annotations

import inspect
from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_TIME_UP_EARLY_WORKDAY,
    CONF_TIME_UP_EARLY_NON_WORKDAY,
    CONF_TIME_UP_LATE_WORKDAY,
    CONF_TIME_UP_LATE_NON_WORKDAY,
    CONF_TIME_DOWN_EARLY_WORKDAY,
    CONF_TIME_DOWN_EARLY_NON_WORKDAY,
    CONF_TIME_DOWN_LATE_WORKDAY,
    CONF_TIME_DOWN_LATE_NON_WORKDAY,
    CONF_NAME,
    DEFAULT_NAME,
    DOMAIN,
)
from .controller import ControllerManager

def _instance_name(entry: ConfigEntry) -> str:
    return entry.options.get(CONF_NAME, entry.data.get(CONF_NAME, entry.title or DEFAULT_NAME))

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Register time entities for scheduling."""

    entities: list[TimeEntity] = [
        ShutterTimeEntity(entry, CONF_TIME_UP_EARLY_WORKDAY, "time_up_early_workday","mdi:sort-clock-descending-outline"),
        ShutterTimeEntity(entry, CONF_TIME_UP_LATE_WORKDAY, "time_up_late_workday","mdi:sort-clock-ascending-outline"),
        ShutterTimeEntity(entry, CONF_TIME_DOWN_EARLY_WORKDAY, "time_down_early_workday","mdi:sort-clock-descending-outline"),
        ShutterTimeEntity(entry, CONF_TIME_DOWN_LATE_WORKDAY, "time_down_late_workday","mdi:sort-clock-ascending-outline"),
        ShutterTimeEntity(entry, CONF_TIME_UP_EARLY_NON_WORKDAY, "time_up_early_non_workday","mdi:sort-clock-descending-outline"),
        ShutterTimeEntity(entry, CONF_TIME_UP_LATE_NON_WORKDAY, "time_up_late_non_workday","mdi:sort-clock-ascending-outline"),
        ShutterTimeEntity(entry, CONF_TIME_DOWN_EARLY_NON_WORKDAY, "time_down_early_non_workday","mdi:sort-clock-descending-outline"),
        ShutterTimeEntity(entry, CONF_TIME_DOWN_LATE_NON_WORKDAY, "time_down_late_non_workday","mdi:sort-clock-ascending-outline"),
    ]

    async_add_entities(entities)

    manager: ControllerManager = hass.data[DOMAIN][entry.entry_id]
    manager.async_update_options()


class ShutterTimeEntity(TimeEntity):
    """Time entity that stores schedule windows in config entry options."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, key: str, translation_key: str, icon: str) -> None:
        self.entry = entry
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}-{key}"
        self._attr_translation_key = translation_key
        self._attr_translation_placeholders = {}
        self._attr_friendly_name = f"{translation_key}"  # replaced via translations
        self._attr_icon = icon

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=_instance_name(self.entry),
        )

    @property
    def native_value(self) -> time | None:
        value = self.entry.options.get(self._key, self.entry.data.get(self._key))
        if not value:
            return None
        try:
            return dt_util.parse_time(value)
        except (TypeError, ValueError):
            return None

    async def async_set_value(self, value: time) -> None:
        options = {**self.entry.options, self._key: value.isoformat()}
        update_result = self.hass.config_entries.async_update_entry(
            self.entry, options=options
        )
        if inspect.isawaitable(update_result):
            await update_result
