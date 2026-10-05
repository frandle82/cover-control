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
    CONF_PROFILES,
    CONF_NAME,
    CONF_RESIDENT_STATUS,
    DEFAULT_NAME,
    DOMAIN,
    SIGNAL_ENTRY_STATE_UPDATED,
    SIGNAL_HUB_STATE_UPDATED,
    FUNCTION_TIME,
)
from .config_resolver import (
    configured_functions_from_profile,
    effective_profile,
    effective_profile_id,
)
from .controller import ControllerManager
from .hub import CoverControlHub
from .runtime_data import CoverControlRuntime


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Cover Control sensor entities."""
    runtime = getattr(entry, "runtime_data", None)
    if isinstance(runtime, CoverControlRuntime):
        entities: list[SensorEntity] = []
        for room_id, manager in runtime.room_managers.items():
            entities.extend(
                [
                    NextOpenSensor(hass, entry, room_id),
                    NextCloseSensor(hass, entry, room_id),
                    ControlStateSensor(hass, entry, room_id),
                ]
            )
            resolved = manager._resolved_config or {}
            if CONF_RESIDENT_STATUS in resolved and bool(
                resolved.get(CONF_RESIDENT_STATUS)
            ):
                entities.append(ResidentStatusSensor(hass, entry, room_id))
        profile_ids: set[str] = set()
        for room in runtime.model.get("rooms", {}).values():
            profile_id = effective_profile_id(room)
            if profile_id:
                profile_ids.add(profile_id)
        for profile_id in sorted(profile_ids):
            profile = effective_profile(runtime.model, {"profile_id": profile_id})
            if not profile:
                room = next(
                    room
                    for room in runtime.model.get("rooms", {}).values()
                    if effective_profile_id(room) == profile_id
                )
                profile = effective_profile(runtime.model, room)
            if FUNCTION_TIME in configured_functions_from_profile(profile):
                entities.append(ProfileScheduleSensor(hass, entry, profile_id, "next_open"))
                entities.append(ProfileScheduleSensor(hass, entry, profile_id, "next_close"))
        desired = {entity.unique_id for entity in entities}
        registry = er.async_get(hass)
        for entity_entry in list(registry.entities.values()):
            if (
                entity_entry.config_entry_id == entry.entry_id
                and entity_entry.domain == "sensor"
                and entity_entry.unique_id not in desired
            ):
                registry.async_remove(entity_entry.entity_id)
        async_add_entities(entities)
        return


class _BaseCoverControlSensor(SensorEntity):
    """Base sensor for shared metadata and update wiring."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, room_id: str | None = None
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.room_id = room_id
        self._attr_config_subentry_id = room_id

    @property
    def device_info(self) -> DeviceInfo:
        if self.room_id:
            runtime = getattr(self.entry, "runtime_data", None)
            room = runtime.model.get("rooms", {}).get(self.room_id, {}) if isinstance(runtime, CoverControlRuntime) else {}
            return DeviceInfo(
                identifiers={(DOMAIN, self.entry.entry_id, self.room_id)},
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


class _BaseEntryRuntimeSensor(_BaseCoverControlSensor):
    """Base class for entry-level runtime sensors."""

    _key: str

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, room_id: str | None = None
    ) -> None:
        super().__init__(hass, entry, room_id)
        self._attr_unique_id = f"{room_id or entry.entry_id}-{self._key}"
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

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, room_id: str | None = None
    ) -> None:
        super().__init__(hass, entry, room_id)
        self._attr_unique_id = f"{room_id or entry.entry_id}-control_state"
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

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, room_id: str | None = None
    ) -> None:
        super().__init__(hass, entry, room_id)
        self._attr_unique_id = f"{room_id or entry.entry_id}-resident_status"
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


class ProfileScheduleSensor(_BaseCoverControlSensor):
    """Expose a shared time-profile opportunity independently of room plans."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        profile_id: str,
        key: str,
    ) -> None:
        super().__init__(hass, entry)
        self.profile_id = profile_id
        self.key = key
        self._attr_unique_id = f"profile-{profile_id}-{key}"
        self._attr_translation_key = f"profile_{key}"
        hub = self._hub()
        profile_name = (
            hub.profile_name("profile", profile_id)
            if hub is not None
            else profile_id
        )
        self._attr_translation_placeholders = {"profile": profile_name}
        self._value: datetime | None = None

    def _hub(self) -> CoverControlHub | None:
        runtime = getattr(self.entry, "runtime_data", None)
        if isinstance(runtime, CoverControlRuntime):
            return runtime.hub
        return None

    async def async_added_to_hass(self) -> None:
        self._refresh()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_HUB_STATE_UPDATED, self._handle_hub_update
            )
        )

    @callback
    def _handle_hub_update(self) -> None:
        if self._refresh():
            self.async_write_ha_state()

    @callback
    def _refresh(self) -> bool:
        previous = self._value
        hub = self._hub()
        evaluation = (
            hub.profile_evaluations.get(("profile", self.profile_id))
            if hub is not None
            else None
        )
        self._value = getattr(evaluation, self.key, None)
        return previous != self._value

    @property
    def native_value(self) -> datetime | None:
        return self._value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        hub = self._hub()
        return {
            "profile_id": self.profile_id,
            "rooms": sorted(
                hub.profile_users.get(("profile", self.profile_id), ())
            )
            if hub is not None
            else [],
        }
