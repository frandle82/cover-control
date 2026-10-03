"""Sensor platform for Cover Control."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import (
    CONF_NAME,
    CONF_RESIDENT_STATUS,
    DEFAULT_AUTOMATION_FLAGS,
    DEFAULT_NAME,
    DOMAIN,
    SIGNAL_ENTRY_STATE_UPDATED,
)
from .controller import ControllerManager
from .config_resolver import config_entry_room_id, resolve_entry_config


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Cover Control sensor entities."""
    merged = resolve_entry_config(
        entry.data,
        entry.options,
        room_id=config_entry_room_id(entry.data, entry.entry_id),
    )
    resident_enabled = bool(
        merged.get(
            CONF_RESIDENT_STATUS,
            DEFAULT_AUTOMATION_FLAGS.get(CONF_RESIDENT_STATUS, False),
        )
    )

    desired_unique_ids = {
        f"{entry.entry_id}-next_open",
        f"{entry.entry_id}-next_close",
        f"{entry.entry_id}-control_state",
    }
    if resident_enabled:
        desired_unique_ids.add(f"{entry.entry_id}-resident_status")

    registry = er.async_get(hass)
    for entity_entry in list(registry.entities.values()):
        if entity_entry.config_entry_id != entry.entry_id or entity_entry.domain != "sensor":
            continue
        unique_id = entity_entry.unique_id or ""
        if unique_id not in desired_unique_ids:
            registry.async_remove(entity_entry.entity_id)

    entities: list[SensorEntity] = [
        NextOpenSensor(hass, entry),
        NextCloseSensor(hass, entry),
        ControlStateSensor(hass, entry),
    ]

    if resident_enabled:
        entities.append(ResidentStatusSensor(hass, entry))

    async_add_entities(entities)


class _BaseCoverControlSensor(SensorEntity):
    """Base sensor for shared metadata and update wiring."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

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


class _BaseEntryRuntimeSensor(_BaseCoverControlSensor):
    """Base class for entry-level runtime sensors."""

    _key: str

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry)
        self._attr_unique_id = f"{entry.entry_id}-{self._key}"
        self._attr_translation_key = self._key
        self._target_time: datetime | None = None
        self._target_cover: str | None = None
        self._controlled_covers: list[str] = []

    async def async_added_to_hass(self) -> None:
        self._refresh_from_manager()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_ENTRY_STATE_UPDATED, self._async_handle_state_update
            )
        )

    @callback
    def _refresh_from_manager(self) -> bool:
        previous = (self._target_time, self._target_cover, self._controlled_covers)
        manager = self._manager()
        if not manager or not manager.controllers:
            self._target_time = None
            self._target_cover = None
            self._controlled_covers = []
            return previous != (
                self._target_time,
                self._target_cover,
                self._controlled_covers,
            )

        snapshot = manager.entry_snapshot()
        covers = snapshot.get("covers")
        self._controlled_covers = list(covers) if isinstance(covers, dict) else []
        event = snapshot.get(self._key)
        if not (
            isinstance(event, tuple)
            and len(event) == 2
            and isinstance(event[0], datetime)
        ):
            self._target_time = None
            self._target_cover = None
        else:
            self._target_time, self._target_cover = event
        return previous != (
            self._target_time,
            self._target_cover,
            self._controlled_covers,
        )

    @callback
    def _async_handle_state_update(
        self,
        entry_id: str,
    ) -> None:
        if entry_id != self.entry.entry_id:
            return
        if self._refresh_from_manager():
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "cover": self._target_cover,
            "covers": self._controlled_covers,
        }


class NextOpenSensor(_BaseEntryRuntimeSensor):
    """Next calculated opening timestamp across controlled covers."""

    _key = "next_open"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-start"

    @property
    def native_value(self) -> datetime | None:
        return self._target_time


class NextCloseSensor(_BaseEntryRuntimeSensor):
    """Next calculated closing timestamp across controlled covers."""

    _key = "next_close"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-end"

    @property
    def native_value(self) -> datetime | None:
        return self._target_time


class ControlStateSensor(_BaseCoverControlSensor):
    """Expose the currently active control situation for troubleshooting."""

    _attr_translation_key = "control_state"
    _attr_icon = "mdi:state-machine"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry)
        self._attr_unique_id = f"{entry.entry_id}-control_state"
        self._state: str = "idle"
        self._cover_states: dict[str, dict[str, Any]] = {}
        self._config_diagnostics: dict[str, Any] = {}

    async def async_added_to_hass(self) -> None:
        self._refresh_state()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_ENTRY_STATE_UPDATED, self._async_handle_state_update
            )
        )

    @callback
    def _async_handle_state_update(
        self,
        entry_id: str,
    ) -> None:
        if entry_id != self.entry.entry_id:
            return
        if self._refresh_state():
            self.async_write_ha_state()

    @callback
    def _refresh_state(self) -> bool:
        previous = (self._state, self._cover_states, self._config_diagnostics)
        manager = self._manager()
        if not manager or not manager.controllers:
            self._state = "idle"
            self._cover_states = {}
            self._config_diagnostics = {}
        else:
            snapshot = manager.entry_snapshot()
            covers = snapshot.get("covers")
            self._cover_states = covers if isinstance(covers, dict) else {}
            state = snapshot.get("control_state")
            self._state = state if isinstance(state, str) else "idle"
            self._config_diagnostics = manager.configuration_diagnostics()
        return previous != (
            self._state,
            self._cover_states,
            self._config_diagnostics,
        )

    @property
    def native_value(self) -> str:
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "covers": self._cover_states,
            "active_covers": [
                cover
                for cover, state in self._cover_states.items()
                if state.get("reason") != "idle"
            ],
            "configuration": self._config_diagnostics,
        }


class ResidentStatusSensor(_BaseCoverControlSensor):
    """Expose resident sensor status when resident mode is enabled."""

    _attr_translation_key = "resident_status"
    _attr_icon = "mdi:bed"
    _attr_unique_id: str

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry)
        self._attr_unique_id = f"{entry.entry_id}-resident_status"
        self._state: str = "off"
        self._resident_entity: str | None = None

    async def async_added_to_hass(self) -> None:
        self._refresh_state()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_ENTRY_STATE_UPDATED, self._async_handle_state_update
            )
        )

    @callback
    def _async_handle_state_update(
        self,
        entry_id: str,
    ) -> None:
        if entry_id != self.entry.entry_id:
            return
        if self._refresh_state():
            self.async_write_ha_state()

    @callback
    def _refresh_state(self) -> bool:
        previous = (self._state, self._resident_entity)
        manager = self._manager()
        snapshot = manager.entry_snapshot() if manager else {}
        resident_entity = snapshot.get("resident_entity")
        self._resident_entity = (
            resident_entity if isinstance(resident_entity, str) else None
        )
        resident_status = snapshot.get("resident_status")
        self._state = resident_status if isinstance(resident_status, str) else "off"
        return previous != (self._state, self._resident_entity)

    @property
    def native_value(self) -> str:
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"resident_entity": self._resident_entity}
