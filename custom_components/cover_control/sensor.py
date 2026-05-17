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
from .const import (
    CONF_NAME,
    CONF_RESIDENT_SENSOR,
    CONF_RESIDENT_STATUS,
    DEFAULT_AUTOMATION_FLAGS,
    DEFAULT_NAME,
    DOMAIN,
    SIGNAL_STATE_UPDATED,
)
from .controller import ControllerManager


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Cover Control sensor entities."""
    merged = {**entry.data, **entry.options}
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
                self.hass, SIGNAL_STATE_UPDATED, self._async_handle_state_update
            )
        )

    @callback
    def _refresh_from_manager(self) -> None:
        manager = self._manager()
        if not manager or not manager.controllers:
            self._target_time = None
            self._target_cover = None
            self._controlled_covers = []
            return

        self._controlled_covers = list(manager.controllers.keys())
        candidates: list[tuple[datetime, str]] = []
        now = dt_util.utcnow()
        for cover, controller in manager.controllers.items():
            candidate = self._event_time_for_controller(controller)
            if isinstance(candidate, datetime) and candidate >= now:
                candidates.append((candidate, cover))

        if not candidates:
            self._target_time = None
            self._target_cover = None
            return

        self._target_time, self._target_cover = min(candidates, key=lambda item: item[0])

    def _event_time_for_controller(self, controller) -> datetime | None:
        snapshot = controller.state_snapshot()
        idx = 4 if self._key == "next_open" else 5
        scheduled = snapshot[idx]
        return scheduled if isinstance(scheduled, datetime) else None

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
        self._refresh_from_manager()
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
        if not manager or not manager.controllers:
            self._state = "idle"
            self._cover_states = {}
            return

        cover_states: dict[str, dict[str, Any]] = {}
        active_reasons: list[str] = []
        for cover, controller in manager.controllers.items():
            (
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
            ) = controller.state_snapshot()

            reason_value = reason or "idle"
            cover_states[cover] = {
                "reason": reason_value,
                "current_position": current_position,
                "target_position": target,
                "manual_active": manual_active,
                "manual_until": manual_until.isoformat() if manual_until else None,
                "next_open": next_open.isoformat() if next_open else None,
                "next_close": next_close.isoformat() if next_close else None,
                "shading_enabled": shading_enabled,
                "shading_active": shading_active,
                "ventilation_active": ventilation_active,
            }
            if reason_value != "idle" and reason_value not in active_reasons:
                active_reasons.append(reason_value)

        self._cover_states = cover_states
        if not active_reasons:
            self._state = "idle"
        elif len(active_reasons) == 1:
            self._state = active_reasons[0]
        else:
            self._state = "multiple"

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
