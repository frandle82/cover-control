"""Button platform for Cover Control."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ENABLE_CLEAR_MANUAL_OVERRIDE_BUTTON,
    CONF_ENABLE_RECALIBRATE_BUTTON,
    CONF_FULL_OPEN_POSITION,
    CONF_MANUAL_CONTROL,
    CONF_NAME,
    DEFAULT_BUTTON_SETTINGS,
    DEFAULT_NAME,
    DEFAULT_OPEN_POSITION,
    DOMAIN,
)
from .controller import ControllerManager


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up optional Cover Control button entities."""

    merged = {**DEFAULT_BUTTON_SETTINGS, **entry.data, **entry.options}
    desired: dict[str, type[_BaseCoverControlButton]] = {}
    manual_control_enabled = bool(
        merged.get(CONF_MANUAL_CONTROL)
        or merged.get(CONF_ENABLE_RECALIBRATE_BUTTON)
        or merged.get(CONF_ENABLE_CLEAR_MANUAL_OVERRIDE_BUTTON)
    )
    if manual_control_enabled:
        desired["recalibrate"] = RecalibrateButton
        desired["clear_manual_override"] = ClearManualOverrideButton

    desired_unique_ids = {f"{entry.entry_id}-{key}" for key in desired}
    registry = er.async_get(hass)
    for entity_entry in list(registry.entities.values()):
        if entity_entry.config_entry_id != entry.entry_id or entity_entry.domain != "button":
            continue
        if entity_entry.unique_id not in desired_unique_ids:
            registry.async_remove(entity_entry.entity_id)
            continue
        if entity_entry.entity_category is not None:
            registry.async_update_entity(
                entity_entry.entity_id,
                entity_category=None,
            )

    async_add_entities([entity_cls(hass, entry, key) for key, entity_cls in desired.items()])


class _BaseCoverControlButton(ButtonEntity):
    """Base class for room-level Cover Control buttons."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, key: str) -> None:
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}-{key}"
        self._attr_translation_key = key

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

    def _manager(self) -> ControllerManager | None:
        manager = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id)
        return manager if isinstance(manager, ControllerManager) else None


class RecalibrateButton(_BaseCoverControlButton):
    """Recalibrate all covers controlled by this room entry."""

    _attr_icon = "mdi:restore"

    async def async_press(self) -> None:
        manager = self._manager()
        if manager:
            full_open = self.entry.options.get(
                CONF_FULL_OPEN_POSITION,
                self.entry.data.get(CONF_FULL_OPEN_POSITION, DEFAULT_OPEN_POSITION),
            )
            await manager.recalibrate_all(full_open)


class ClearManualOverrideButton(_BaseCoverControlButton):
    """Clear manual override for all covers controlled by this room entry."""

    _attr_icon = "mdi:cancel"

    async def async_press(self) -> None:
        manager = self._manager()
        if manager:
            manager.clear_all_manual_overrides()
