"""Switch entities to control automation toggles."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
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
    (CONF_AUTO_UP, "auto_up"),
    (CONF_AUTO_DOWN, "auto_down"),
    (CONF_AUTO_BRIGHTNESS, "auto_brightness"),
    (CONF_AUTO_SUN, "auto_sun"),
    (CONF_AUTO_VENTILATE, "auto_ventilate"),
    (CONF_AUTO_SHADING, "auto_shading"),
)

TOGGLE_ICONS: dict[str, str] = {
    CONF_AUTO_UP: "mdi:arrow-up-bold-circle",
    CONF_AUTO_DOWN: "mdi:arrow-down-bold-circle",
    CONF_AUTO_BRIGHTNESS: "mdi:brightness-auto",
    CONF_AUTO_SUN: "mdi:weather-sunny",
    CONF_AUTO_VENTILATE: "mdi:fan-auto",
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

    def _has_sensor(key: str) -> bool:
        options_and_data = {**entry.data, **entry.options}
        if key == CONF_AUTO_BRIGHTNESS:
            return bool(options_and_data.get(CONF_BRIGHTNESS_SENSOR))
        return True

    entities: list[SwitchEntity] = [MasterControlSwitch(entry)] + [
        AutomationToggleSwitch(entry, key, translation_key)
        for key, translation_key in AUTOMATION_TOGGLES
        if _has_sensor(key)
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
        self.hass.config_entries.async_update_entry(self.entry, options=options)

    async def async_turn_off(self, **kwargs) -> None:  # type: ignore[override]
        options = {**self.entry.options, self._key: False}
        self.hass.config_entries.async_update_entry(self.entry, options=options)

    async def _handle_entry_update(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Refresh state when config entry is updated."""

        self.async_write_ha_state()

class MasterControlSwitch(SwitchEntity):
    """Global switch to enable or disable the integration for an instance."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "master"
    _attr_icon = "mdi:home-circle"

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}-master"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=self.entry.options.get(
                CONF_NAME, self.entry.data.get(CONF_NAME, self.entry.title or DEFAULT_NAME)
            ),
            manufacturer="CCA-derived",
        )

    @property
    def is_on(self) -> bool:
        value = self.entry.options.get(CONF_MASTER_ENABLED)
        if value is None:
            value = self.entry.data.get(CONF_MASTER_ENABLED, DEFAULT_MASTER_FLAGS[CONF_MASTER_ENABLED])
        return bool(value)

    @property
    def extra_state_attributes(self):
        attributes: dict[str, object] = {}

        if self.entry.options.get(CONF_EXPOSE_SWITCH_SETTINGS):
            settings = self._settings_attributes()
            if settings:
                attributes["settings"] = settings

        reasons = self._reason_attributes()
        if reasons:
            attributes["reason"] = reasons

        manual_control = self._manual_control_attributes()
        if manual_control:
            attributes["manual_control"] = manual_control

        next_events = self._next_events_attributes()
        if next_events:
            attributes["next_events"] = next_events

        sun_position = self._sun_position_attributes()
        if sun_position:
            attributes["sun_position"] = sun_position

        current_positions = self._current_position_attributes()
        if current_positions:
            attributes["current_position"] = current_positions

        return attributes or None

    def _settings_attributes(self) -> dict[str, object] | None:
        config = {**self.entry.data, **self.entry.options}
        settings: dict[str, object] = {}
        for key, default in MASTER_DEFAULT_LOOKUP.items():
            if key not in config:
                continue
            value = config.get(key)
            if default is not None and value == default:
                continue
            if default is None and value is None:
                continue
            settings[key] = value
        return settings or None

    def _reason_attributes(self) -> dict[str, str] | None:
        manager = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id)
        if not isinstance(manager, ControllerManager):
            return None

        reasons: dict[str, str] = {}
        for cover in manager.controllers:
            snapshot = manager.state_snapshot(cover)
            if not snapshot:
                continue
            reason = snapshot[1] if len(snapshot) > 1 else None
            if reason:
                reasons[cover] = REASON_LABELS.get(reason, reason)
        return reasons or None

    def _manual_control_attributes(self) -> dict[str, object] | None:
        manager = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id)
        if not isinstance(manager, ControllerManager):
            return None

        now = dt_util.utcnow()
        any_active = False
        earliest_until: dt_util.dt.datetime | None = None

        for cover in manager.controllers:
            snapshot = manager.state_snapshot(cover)
            if not snapshot:
                continue
            until = snapshot[2] if len(snapshot) > 2 else None
            active = snapshot[3] if len(snapshot) > 3 else None
            if not active:
                continue
            any_active = True
            if isinstance(until, dt_util.dt.datetime):
                if earliest_until is None or until < earliest_until:
                    earliest_until = until

        if not any_active and earliest_until is None:
            return None

        attributes: dict[str, object] = {"active": any_active}

        if earliest_until:
            remaining = (earliest_until - now).total_seconds()
            attributes["autoreset_time_remaining"] = max(0, int(remaining))

        return attributes

    def _sun_position_attributes(self) -> dict[str, float] | None:
        sun_state = self.hass.states.get("sun.sun")
        if not sun_state:
            return None

        azimuth = sun_state.attributes.get("azimuth")
        elevation = sun_state.attributes.get("elevation")
        position: dict[str, float] = {}

        if isinstance(azimuth, (int, float)):
            position["azimuth"] = float(azimuth)
        if isinstance(elevation, (int, float)):
            position["elevation"] = float(elevation)

        return position or None

    def _current_position_attributes(self) -> dict[str, float] | None:
        manager = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id)
        if not isinstance(manager, ControllerManager):
            return None

        positions: dict[str, float] = {}
        for cover in manager.controllers:
            snapshot = manager.state_snapshot(cover)
            if not snapshot:
                continue
            current_position = snapshot[6] if len(snapshot) > 6 else None
            if current_position is None:
                continue
            positions[cover] = float(current_position)

        return positions or None

    def _next_events_attributes(self) -> dict[str, object] | None:
        manager = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id)
        if not isinstance(manager, ControllerManager):
            return None

        schedule: dict[str, object] = {}
        for cover in manager.controllers:
            snapshot = manager.state_snapshot(cover)
            if not snapshot:
                continue
            next_open = snapshot[4] if len(snapshot) > 4 else None
            next_close = snapshot[5] if len(snapshot) > 5 else None

            cover_schedule: dict[str, object] = {}
            if next_open:
                cover_schedule["next_open"] = self._format_dt(next_open)
            if next_close:
                cover_schedule["next_close"] = self._format_dt(next_close)

            if cover_schedule:
                schedule[cover] = cover_schedule

        return schedule or None

    def _format_dt(self, value: object) -> object:
        if isinstance(value, str):
            parsed = dt_util.parse_datetime(value)
            if parsed:
                return dt_util.as_utc(parsed).isoformat()
            return value
        if isinstance(value, dt_util.dt.datetime):
            return value.isoformat()
        return value

    async def async_turn_on(self, **kwargs) -> None:  # type: ignore[override]
        options = {**self.entry.options, CONF_MASTER_ENABLED: True}
        self.hass.config_entries.async_update_entry(self.entry, options=options)

    async def async_turn_off(self, **kwargs) -> None:  # type: ignore[override]
        options = {**self.entry.options, CONF_MASTER_ENABLED: False}
        self.hass.config_entries.async_update_entry(self.entry, options=options)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_STATE_UPDATED, self._handle_state_update
            )
        )
        self.async_on_remove(self.entry.add_update_listener(self._handle_entry_update))

    async def _handle_entry_update(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.async_write_ha_state()

    @callback
    def _handle_state_update(self, entry_id: str, *payload: object) -> None:
        if entry_id != self.entry.entry_id:
            return
        self.async_write_ha_state()
