"""Switch entities to control automation toggles."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_MANUAL_OVERRIDE_MINUTES,
    CONF_MANUAL_OVERRIDE_RESET_TIME,
    CONF_CONTROLLER_ENTRY_ID,
    CONF_ENTRY_TYPE,
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
    CONF_RESIDENT_STATUS,
    CONF_VENTILATE_POSITION,
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
    DOMAIN,
    ENTRY_TYPE_ROOM,
)
from .feature_state import feature_configured
from .runtime_data import CoverControlRuntime


AUTOMATION_TOGGLES: tuple[tuple[str, str], ...] = (
    (CONF_AUTO_TIME, "auto_time"),
    (CONF_AUTO_VENTILATE, "auto_ventilate"),
    (CONF_AUTO_BRIGHTNESS, "auto_brightness"),
    (CONF_AUTO_SUN, "auto_sun"),
    (CONF_AUTO_SHADING, "auto_shading"),
    (CONF_RESIDENT_STATUS, "resident_status"),
)

TOGGLE_ICONS: dict[str, str] = {
    CONF_AUTO_TIME: "mdi:clock-time-eight-auto",
    CONF_AUTO_VENTILATE: "mdi:door-open",
    CONF_AUTO_BRIGHTNESS: "mdi:brightness-auto",
    CONF_AUTO_SUN: "mdi:weather-sunset",
    CONF_AUTO_SHADING: "mdi:theme-light-dark",
    CONF_RESIDENT_STATUS: "mdi:bed",
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

    runtime = getattr(entry, "runtime_data", None)
    if isinstance(runtime, CoverControlRuntime):
        entities: list[SwitchEntity] = []
        for room_id, manager in runtime.room_managers.items():
            for key, translation_key in AUTOMATION_TOGGLES:
                if feature_configured(runtime.model, room_id, key):
                    entities.append(
                        AutomationToggleSwitch(
                            entry, key, translation_key, room_id=room_id
                        )
                    )
        desired = {entity.unique_id for entity in entities}
        registry = er.async_get(hass)
        for entity_entry in list(registry.entities.values()):
            if (
                entity_entry.config_entry_id == entry.entry_id
                and entity_entry.domain == "switch"
                and entity_entry.unique_id not in desired
            ):
                registry.async_remove(entity_entry.entity_id)
        async_add_entities(entities)
        return

    toggle_keys = {key for key, _translation_key in AUTOMATION_TOGGLES}
    registry = er.async_get(hass)
    for entity_entry in list(registry.entities.values()):
        if entity_entry.config_entry_id != entry.entry_id or entity_entry.domain != "switch":
            continue
        unique_id = entity_entry.unique_id or ""
        if unique_id == f"{entry.entry_id}-master":
            registry.async_remove(entity_entry.entity_id)
            continue
        key = unique_id.removeprefix(f"{entry.entry_id}-")
        if key in {CONF_AUTO_UP, CONF_AUTO_DOWN} or key not in toggle_keys:
            registry.async_remove(entity_entry.entity_id)
            continue
        if entity_entry.entity_category != EntityCategory.CONFIG:
            registry.async_update_entity(
                entity_entry.entity_id,
                entity_category=EntityCategory.CONFIG,
            )

    entities: list[SwitchEntity] = [
        AutomationToggleSwitch(entry, key, translation_key)
        for key, translation_key in AUTOMATION_TOGGLES
    ]

    async_add_entities(entities)


class AutomationToggleSwitch(SwitchEntity):
    """Switch to enable or disable automation features."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        entry: ConfigEntry,
        key: str,
        translation_key: str,
        *,
        room_id: str | None = None,
    ) -> None:
        self.entry = entry
        self.room_id = room_id
        self._key = key
        owner_id = room_id or entry.entry_id
        self._attr_unique_id = f"{owner_id}-{key}"
        self._attr_config_subentry_id = (
            None if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_ROOM else room_id
        )
        self._attr_translation_key = translation_key
        self._attr_icon = TOGGLE_ICONS.get(key)
        self._attr_friendly_name = translation_key

    async def async_added_to_hass(self) -> None:
        """Handle entity addition and keep state in sync with options."""

        self.async_on_remove(
            self.entry.add_update_listener(self._handle_entry_update)
        )

    @property
    def icon(self) -> str | None:
        """Return the configured icon for the automation toggle."""

        return TOGGLE_ICONS.get(self._key)

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

    @property
    def is_on(self) -> bool:
        if self.room_id:
            runtime = getattr(self.entry, "runtime_data", None)
            manager = runtime.manager(self.room_id) if isinstance(runtime, CoverControlRuntime) else None
            if manager is None:
                return False
            runtime_value = manager.get_runtime_toggle(self._key)
            if runtime_value is not None:
                return bool(runtime_value)
            return bool(manager._resolved_config.get(self._key, False))
        return bool(DEFAULT_AUTOMATION_FLAGS.get(self._key))

    @property
    def extra_state_attributes(self):
        return None

    async def async_turn_on(self, **kwargs) -> None:  # type: ignore[override]
        if self.room_id:
            runtime = getattr(self.entry, "runtime_data", None)
            manager = runtime.manager(self.room_id) if isinstance(runtime, CoverControlRuntime) else None
            if manager:
                manager.set_runtime_toggle(self._key, True)
                if self._key == CONF_AUTO_TIME:
                    manager.set_runtime_toggle(CONF_AUTO_UP, True)
                    manager.set_runtime_toggle(CONF_AUTO_DOWN, True)
                self.async_write_ha_state()
            return
        options = {**self.entry.options, self._key: True}
        if self._key == CONF_AUTO_TIME:
            options[CONF_AUTO_UP] = True
            options[CONF_AUTO_DOWN] = True
        self.hass.config_entries.async_update_entry(self.entry, options=options)

    async def async_turn_off(self, **kwargs) -> None:  # type: ignore[override]
        if self.room_id:
            runtime = getattr(self.entry, "runtime_data", None)
            manager = runtime.manager(self.room_id) if isinstance(runtime, CoverControlRuntime) else None
            if manager:
                manager.set_runtime_toggle(self._key, False)
                if self._key == CONF_AUTO_TIME:
                    manager.set_runtime_toggle(CONF_AUTO_UP, False)
                    manager.set_runtime_toggle(CONF_AUTO_DOWN, False)
                self.async_write_ha_state()
            return
        options = {**self.entry.options, self._key: False}
        if self._key == CONF_AUTO_TIME:
            options[CONF_AUTO_UP] = False
            options[CONF_AUTO_DOWN] = False
        self.hass.config_entries.async_update_entry(self.entry, options=options)

    async def _handle_entry_update(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Refresh state when config entry is updated."""

        self.async_write_ha_state()
