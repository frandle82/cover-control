"""Sensor platform for Cover Control."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    CONF_COVERS,
    CONF_NAME,
    CONF_RESIDENT_SENSOR,
    CONF_RESIDENT_STATUS,
    DEFAULT_AUTOMATION_FLAGS,
    DEFAULT_NAME,
    DOMAIN,
    SIGNAL_STATE_UPDATED,
)
from .controller import ControllerManager


RUNTIME_SENSOR_KEYS: tuple[str, ...] = (
    "next_open",
    "next_close",
    "reason",
    "shading_active",
    "ventilation",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Cover Control sensor entities."""
    merged = {**entry.data, **entry.options}
    covers = [
        cover for cover in merged.get(CONF_COVERS, []) if isinstance(cover, str) and cover
    ]
    resident_enabled = bool(
        merged.get(
            CONF_RESIDENT_STATUS,
            DEFAULT_AUTOMATION_FLAGS.get(CONF_RESIDENT_STATUS, False),
        )
    )

    desired_unique_ids = {
        f"{entry.entry_id}-{slugify(cover)}-{key}"
        for cover in covers
        for key in RUNTIME_SENSOR_KEYS
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

    entities: list[SensorEntity] = []
    for cover in covers:
        entities.append(NextOpenSensor(hass, entry, cover))
        entities.append(NextCloseSensor(hass, entry, cover))
        entities.append(ReasonSensor(hass, entry, cover))
        entities.append(ShadingActiveSensor(hass, entry, cover))
        entities.append(VentilationSensor(hass, entry, cover))

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


class _BaseCoverRuntimeSensor(_BaseCoverControlSensor):
    """Base class for per-cover runtime sensors."""

    _key: str

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, cover: str) -> None:
        super().__init__(hass, entry)
        self._cover = cover
        self._snapshot: tuple[
            float | None,
            str | None,
            datetime | None,
            bool,
            datetime | None,
            datetime | None,
            float | None,
            bool,
            bool,
            bool,
        ] | None = None
        self._attr_unique_id = f"{entry.entry_id}-{slugify(cover)}-{self._key}"
        self._attr_translation_key = self._key

    async def async_added_to_hass(self) -> None:
        self._refresh_from_manager()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_STATE_UPDATED, self._async_handle_state_update
            )
        )

    @callback
    def _refresh_from_manager(self) -> None:
        manager = self._manager()
        self._snapshot = manager.state_snapshot(self._cover) if manager else None

    @callback
    def _async_handle_state_update(
        self,
        entry_id: str,
        cover: str,
        target: float | None,
        reason: str | None,
        manual_until: datetime | None,
        manual_active: bool,
        next_open: datetime | None,
        next_close: datetime | None,
        current_position: float | None,
        shading_enabled: bool,
        shading_active: bool,
        ventilation_active: bool,
    ) -> None:
        if entry_id != self.entry.entry_id or cover != self._cover:
            return
        self._snapshot = (
            target,
            reason,
            manual_until,
            manual_active,
            next_open,
            next_close,
            current_position,
            shading_enabled,
            shading_active,
            ventilation_active,
        )
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"cover": self._cover}


class NextOpenSensor(_BaseCoverRuntimeSensor):
    """Next calculated opening timestamp for a cover."""

    _key = "next_open"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-start"

    @property
    def native_value(self) -> datetime | None:
        if not self._snapshot:
            return None
        return self._snapshot[4]


class NextCloseSensor(_BaseCoverRuntimeSensor):
    """Next calculated closing timestamp for a cover."""

    _key = "next_close"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-end"

    @property
    def native_value(self) -> datetime | None:
        if not self._snapshot:
            return None
        return self._snapshot[5]


class ReasonSensor(_BaseCoverRuntimeSensor):
    """Current control reason."""

    _key = "reason"
    _attr_icon = "mdi:information-outline"

    @property
    def native_value(self) -> str | None:
        if not self._snapshot:
            return None
        return self._snapshot[1]


class ShadingActiveSensor(_BaseCoverRuntimeSensor):
    """Whether shading is currently active."""

    _key = "shading_active"
    _attr_icon = "mdi:weather-sunny-alert"

    @property
    def native_value(self) -> str:
        if not self._snapshot:
            return "off"
        return "on" if self._snapshot[8] else "off"


class VentilationSensor(_BaseCoverRuntimeSensor):
    """Whether ventilation mode is currently active."""

    _key = "ventilation"
    _attr_icon = "mdi:window-open"

    @property
    def native_value(self) -> str:
        if not self._snapshot:
            return "off"
        return "on" if self._snapshot[9] else "off"


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
                self.hass, SIGNAL_STATE_UPDATED, self._async_handle_state_update
            )
        )

    @callback
    def _async_handle_state_update(
        self,
        entry_id: str,
        cover: str,
        target: float | None,
        reason: str | None,
        manual_until: datetime | None,
        manual_active: bool,
        next_open: datetime | None,
        next_close: datetime | None,
        current_position: float | None,
        shading_enabled: bool,
        shading_active: bool,
        ventilation_active: bool,
    ) -> None:
        if entry_id != self.entry.entry_id:
            return
        self._refresh_state()
        self.async_write_ha_state()

    @callback
    def _refresh_state(self) -> None:
        manager = self._manager()
        controller = next(iter(manager.controllers.values()), None) if manager else None
        resident_entity = None
        if controller:
            configured = controller.config.get(CONF_RESIDENT_SENSOR)
            resident_entity = configured if isinstance(configured, str) else None

        self._resident_entity = resident_entity
        if resident_entity and self.hass.states.is_state(resident_entity, STATE_ON):
            self._state = "on"
        else:
            self._state = "off"

    @property
    def native_value(self) -> str:
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"resident_entity": self._resident_entity}
