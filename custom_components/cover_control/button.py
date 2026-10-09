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
    CONF_CONTROLLER_ENTRY_ID,
    CONF_ENTRY_TYPE,
    CONF_FULL_OPEN_POSITION,
    CONF_MANUAL_CONTROL,
    CONF_NAME,
    DEFAULT_BUTTON_SETTINGS,
    DEFAULT_NAME,
    DEFAULT_OPEN_POSITION,
    DOMAIN,
    ENTRY_TYPE_ROOM,
)
from .controller import ControllerManager
from .runtime_data import CoverControlRuntime


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up optional Cover Control button entities."""

    runtime = getattr(entry, "runtime_data", None)
    if isinstance(runtime, CoverControlRuntime):
        entities: list[ButtonEntity] = []
        for room_id, manager in runtime.room_managers.items():
            merged = {**DEFAULT_BUTTON_SETTINGS, **(manager._resolved_config or {})}
            manual_enabled = bool(merged.get(CONF_MANUAL_CONTROL))
            if manual_enabled or bool(merged.get(CONF_ENABLE_RECALIBRATE_BUTTON)):
                entities.append(RecalibrateButton(hass, entry, "recalibrate", room_id=room_id))
            if manual_enabled or bool(
                merged.get(CONF_ENABLE_CLEAR_MANUAL_OVERRIDE_BUTTON)
            ):
                entities.append(
                    ClearManualOverrideButton(
                        hass, entry, "clear_manual_override", room_id=room_id
                    )
                )
        desired = {entity.unique_id for entity in entities}
        registry = er.async_get(hass)
        for entity_entry in list(registry.entities.values()):
            if (
                entity_entry.config_entry_id == entry.entry_id
                and entity_entry.domain == "button"
                and entity_entry.unique_id not in desired
            ):
                registry.async_remove(entity_entry.entity_id)
        async_add_entities(entities)
        return



class _BaseCoverControlButton(ButtonEntity):
    """Base class for room-level Cover Control buttons."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        key: str,
        *,
        room_id: str | None = None,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.room_id = room_id
        self._attr_unique_id = f"{room_id or entry.entry_id}-{key}"
        self._attr_config_subentry_id = (
            None if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_ROOM else room_id
        )
        self._attr_translation_key = key

    @property
    def device_info(self) -> DeviceInfo:
        if self.room_id:
            runtime = getattr(self.entry, "runtime_data", None)
            room = runtime.model.get("rooms", {}).get(self.room_id, {}) if isinstance(runtime, CoverControlRuntime) else {}
            return DeviceInfo(
                identifiers={
                    (
                        DOMAIN,
                        self.entry.data.get(CONF_CONTROLLER_ENTRY_ID, self.entry.entry_id),
                        self.room_id,
                    )
                },
                name=str(room.get(CONF_NAME, self.room_id)),
                manufacturer="CCA-derived",
            )
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=self.entry.options.get(
                CONF_NAME,
                self.entry.data.get(CONF_NAME, self.entry.title or DEFAULT_NAME),
            ),
            manufacturer="CCA-derived",
        )

    def _manager(self) -> ControllerManager | None:
        runtime = getattr(self.entry, "runtime_data", None)
        if self.room_id and isinstance(runtime, CoverControlRuntime):
            return runtime.manager(self.room_id)
        return None


class RecalibrateButton(_BaseCoverControlButton):
    """Recalibrate all covers controlled by this room entry."""

    _attr_icon = "mdi:restore"

    async def async_press(self) -> None:
        manager = self._manager()
        if manager:
            resolved = manager._resolved_config or manager._resolve_entry_config()
            full_open = resolved.get(CONF_FULL_OPEN_POSITION, DEFAULT_OPEN_POSITION)
            await manager.recalibrate_all(full_open)


class ClearManualOverrideButton(_BaseCoverControlButton):
    """Clear manual override for all covers controlled by this room entry."""

    _attr_icon = "mdi:cancel"

    async def async_press(self) -> None:
        manager = self._manager()
        if manager:
            manager.clear_all_manual_overrides()
