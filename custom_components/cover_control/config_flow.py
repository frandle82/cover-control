"""Config and reconfigure flow for Cover Control."""
from __future__ import annotations

import logging
from datetime import datetime
from copy import deepcopy
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult, section
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .config_groups import ConfigGroupModel
from .config_group_schema import (
    GROUP_CAPABILITY_KEYS,
    build_group_schema,
    capability_keys,
    extract_sparse_settings,
    flatten_section_input,
)
from .config_resolver import (
    GLOBAL_SOURCE_KEYS,
    GROUP_BLOCKED_KEYS,
    ROOM_SOURCE_OVERRIDE_KEYS,
    system_defaults,
)
from .const import (
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_DOWN,
    CONF_AUTO_SHADING,
    CONF_AUTO_SUN,
    CONF_AUTO_TIME,
    CONF_AUTO_UP,
    CONF_AUTO_VENTILATE,
    CONF_BRIGHTNESS_SENSOR,
    CONF_CALENDAR_ENTITY,
    CONF_CHRISTMAS_POSITION,
    CONF_CHRISTMAS_POSITION_ENABLED,
    CONF_CLOSE_POSITION,
    CONF_CLOSE_TILT_POSITION,
    CONF_COLD_PROTECTION_FORECAST_SENSOR,
    CONF_CONTROLLER_ENTRY_ID,
    CONF_COVERS,
    CONF_COVER_TILT_WAIT_MODE,
    CONF_COVER_TILT_WAIT_TIMEOUT,
    CONF_COVER_TYPE,
    CONF_COVER_TYPE_AWNING,
    CONF_COVER_TYPE_BLIND,
    CONF_DRIVE_TIME,
    CONF_ENABLE_CLEAR_MANUAL_OVERRIDE_BUTTON,
    CONF_ENABLE_LOGBOOK_COVER,
    CONF_ENABLE_RECALIBRATE_BUTTON,
    CONF_ENTRY_TYPE,
    CONF_HEAT_PROTECTION_ENABLED,
    CONF_HEAT_PROTECTION_THRESHOLD,
    CONF_KEEP_SUN_PROTECTION,
    CONF_GLOBAL,
    CONF_GLOBAL_DEFAULTS,
    CONF_GLOBAL_SOURCES,
    CONF_GROUP,
    CONF_GROUPS,
    CONF_INTERMEDIATE_CLOSE_POSITION,
    CONF_LOCKOUT_POSITION,
    CONF_MANUAL_CONTROL,
    CONF_NAME,
    CONF_OPEN_POSITION,
    CONF_OPEN_TILT_POSITION,
    CONF_POSITION_TOLERANCE,
    CONF_RESIDENT_SENSOR,
    CONF_RESIDENT_STATUS,
    CONF_ROOM,
    CONF_ROOMS,
    CONF_ROOM_ID,
    CONF_ROOM_SETTINGS,
    CONF_SHADING_BRIGHTNESS_SENSOR,
    CONF_SHADING_BRIGHTNESS_HYSTERESIS,
    CONF_SHADING_BRIGHTNESS_THRESHOLD,
    CONF_SHADING_DIRECTION,
    CONF_SHADING_DIRECTION_RANGE,
    CONF_SHADING_INSIDE_TEMPERATURE_HYSTERESIS,
    CONF_SHADING_INSIDE_TEMPERATURE_THRESHOLD,
    CONF_SHADING_MODE,
    CONF_SHADING_OUTSIDE_TEMPERATURE_HYSTERESIS,
    CONF_SHADING_OUTSIDE_TEMPERATURE_THRESHOLD,
    CONF_SHADING_POSITION,
    CONF_SHADING_POSITION_ALT,
    CONF_SHADING_POSITION_ALT_ENTITY,
    CONF_SHADING_TILT_ELEVATION_1,
    CONF_SHADING_TILT_ELEVATION_2,
    CONF_SHADING_TILT_ELEVATION_3,
    CONF_SHADING_TILT_POSITION,
    CONF_SHADING_TILT_POSITION_0,
    CONF_SHADING_TILT_POSITION_1,
    CONF_SHADING_TILT_POSITION_2,
    CONF_SHADING_TILT_POSITION_3,
    CONF_SHADING_WAITINGTIME_END,
    CONF_SOURCE_OVERRIDES,
    CONF_SUMMER_SKIP_CLOSE_ENABLED,
    CONF_SUN_ELEVATION_CLOSE,
    CONF_SUN_ELEVATION_MAX,
    CONF_SUN_ELEVATION_MIN,
    CONF_SUN_ELEVATION_OPEN,
    CONF_ASTRO_CLOSE_OFFSET,
    CONF_ASTRO_OPEN_OFFSET,
    CONF_CLOSE_MODE,
    CONF_OPEN_MODE,
    CONF_TEMPERATURE_FORECAST_THRESHOLD,
    CONF_TEMPERATURE_SENSOR_INDOOR,
    CONF_TEMPERATURE_SENSOR_OUTDOOR,
    CONF_TEMPERATURE_THRESHOLD,
    CONF_TILT_POSITION_TOLERANCE,
    CONF_USE_BRIGHTNESS_SENSOR,
    CONF_USE_COLD_PROTECTION_FORECAST_SENSOR,
    CONF_USE_RESIDENT_SENSOR,
    CONF_USE_TEMPERATURE_SENSOR_INDOOR,
    CONF_USE_TEMPERATURE_SENSOR_OUTDOOR,
    CONF_USE_WORKDAY_SENSOR,
    CONF_VENTILATE_POSITION,
    CONF_VENTILATE_TILT_POSITION,
    CONF_WINDOW_SENSOR_FULL,
    CONF_WINDOW_SENSOR_TILT,
    CONF_WORKDAY_SENSOR,
    CONF_WORKDAY_TOMORROW_SENSOR,
    COVER_TILT_WAIT_BEFORE_POSITION,
    COVER_TILT_WAIT_FIXED_DELAY,
    COVER_TILT_WAIT_IDLE,
    DEFAULT_AUTOMATION_FLAGS,
    DEFAULT_BEHAVIOR_SETTINGS,
    DEFAULT_BUTTON_SETTINGS,
    DEFAULT_CONTACT_SETTINGS,
    DEFAULT_COVER_TILT_WAIT_MODE,
    DEFAULT_COVER_TILT_WAIT_TIMEOUT,
    DEFAULT_DRIVE_TIME,
    DEFAULT_GROUP,
    DEFAULT_MASTER_FLAGS,
    DEFAULT_NAME,
    DEFAULT_POSITION_SETTINGS,
    DEFAULT_SAFETY_PARTICIPATION,
    DEFAULT_SAFETY_SETTINGS,
    DEFAULT_SHADING_SETTINGS,
    DEFAULT_SHADING_TILT_POSITION_0,
    DEFAULT_SHADING_TILT_POSITION_1,
    DEFAULT_SHADING_TILT_POSITION_2,
    DEFAULT_SHADING_TILT_POSITION_3,
    DEFAULT_SHADING_TIMING_SETTINGS,
    DEFAULT_ASTRO_CLOSE_OFFSET,
    DEFAULT_ASTRO_OPEN_OFFSET,
    DEFAULT_CLOSE_MODE,
    DEFAULT_OPEN_MODE,
    DEFAULT_TEMPERATURE_FORECAST_THRESHOLD,
    DEFAULT_TEMPERATURE_THRESHOLD,
    DEFAULT_TIME_SETTINGS,
    DOMAIN,
    ENTRY_TYPE_CONTROLLER,
    ENTRY_TYPE_ROOM,
    GROUPS,
    GROUP_CHILDREN,
    GROUP_LIVING,
    GROUP_SECTION_BEHAVIOR,
    GROUP_SECTION_SHADING,
    GROUP_SECTION_TIME,
    GROUP_SLEEP,
    MODE_ELEVATION,
    MODE_BRIGHTNESS,
    MODE_GOLDEN_HOUR,
    MODE_SUNRISE,
    MODE_SUNSET,
    MODE_TIME,
    SAFETY_ALARMS,
    SHADING_MODE_DIRECTION,
    SHADING_MODE_INSIDE,
    SHADING_MODE_INSIDE_OUTSIDE,
    SHADING_MODE_INSIDE_OUTSIDE_DIRECTION,
    SHADING_MODE_OFF,
    SHADING_MODE_OUTSIDE,
    SHADING_MODE_OUTSIDE_DIRECTION,
)


def _with_config_defaults(config: dict) -> dict:
    """Ensure automation, time, and position defaults are present."""

    return {
        **DEFAULT_POSITION_SETTINGS,
        **DEFAULT_TIME_SETTINGS,
        **DEFAULT_AUTOMATION_FLAGS,
        **DEFAULT_MASTER_FLAGS,
        **DEFAULT_CONTACT_SETTINGS,
        **DEFAULT_BEHAVIOR_SETTINGS,
        **DEFAULT_BUTTON_SETTINGS,
        **DEFAULT_SAFETY_SETTINGS,
        **DEFAULT_SAFETY_PARTICIPATION,
        **DEFAULT_SHADING_TIMING_SETTINGS,
        **{key: list(value) if isinstance(value, list) else value for key, value in DEFAULT_SHADING_SETTINGS.items()},
        CONF_OPEN_MODE: DEFAULT_OPEN_MODE,
        CONF_CLOSE_MODE: DEFAULT_CLOSE_MODE,
        CONF_ASTRO_OPEN_OFFSET: DEFAULT_ASTRO_OPEN_OFFSET,
        CONF_ASTRO_CLOSE_OFFSET: DEFAULT_ASTRO_CLOSE_OFFSET,
        CONF_TEMPERATURE_THRESHOLD: DEFAULT_TEMPERATURE_THRESHOLD,
        CONF_TEMPERATURE_FORECAST_THRESHOLD: DEFAULT_TEMPERATURE_FORECAST_THRESHOLD,
        **config,
    }


def _selector_default(value: Any) -> Any:
    """Return a safe selector default, skipping None/empty placeholders."""

    if value in (None, "", vol.UNDEFINED):
        return vol.UNDEFINED
    return value


LOGGER = logging.getLogger(__name__)


def controller_entry_for_room(
    hass, room_entry: config_entries.ConfigEntry
) -> config_entries.ConfigEntry | None:
    """Return the controller entry referenced by a room entry."""

    controller_entry_id = room_entry.data.get(CONF_CONTROLLER_ENTRY_ID)
    if not controller_entry_id:
        return None
    return next(
        (
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.entry_id == controller_entry_id
            and entry.domain == DOMAIN
            and entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_CONTROLLER
        ),
        None,
    )


CLEARABLE_ENTITY_SELECTOR_KEYS = {
    CONF_WORKDAY_SENSOR,
    CONF_WORKDAY_TOMORROW_SENSOR,
    CONF_CALENDAR_ENTITY,
    CONF_RESIDENT_SENSOR,
    CONF_BRIGHTNESS_SENSOR,
    CONF_SHADING_BRIGHTNESS_SENSOR,
    CONF_TEMPERATURE_SENSOR_INDOOR,
    CONF_TEMPERATURE_SENSOR_OUTDOOR,
    CONF_COLD_PROTECTION_FORECAST_SENSOR,
}

ENTITY_TOGGLE_MAP: dict[str, str] = {
    CONF_USE_WORKDAY_SENSOR: CONF_WORKDAY_SENSOR,
    CONF_USE_RESIDENT_SENSOR: CONF_RESIDENT_SENSOR,
    CONF_USE_BRIGHTNESS_SENSOR: CONF_BRIGHTNESS_SENSOR,
    CONF_USE_TEMPERATURE_SENSOR_INDOOR: CONF_TEMPERATURE_SENSOR_INDOOR,
    CONF_USE_TEMPERATURE_SENSOR_OUTDOOR: CONF_TEMPERATURE_SENSOR_OUTDOOR,
    CONF_USE_COLD_PROTECTION_FORECAST_SENSOR: CONF_COLD_PROTECTION_FORECAST_SENSOR,
}


INITIAL_FEATURE_KEYS = (
    CONF_AUTO_TIME,
    CONF_AUTO_VENTILATE,
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_SUN,
    CONF_AUTO_SHADING,
    CONF_RESIDENT_STATUS,
)


def _is_enabled(options: dict, key: str) -> bool:
    """Return whether an optional entity key currently stores an active value."""

    return options.get(key) not in (None, "", vol.UNDEFINED)

def _time_default(value, fallback: str | None = None):
    """Return a time object for selectors, falling back safely."""

    for candidate in (value, fallback):
        if candidate in (None, "", vol.UNDEFINED):
            continue
        parsed = dt_util.parse_time(str(candidate))
        if parsed:
            return parsed
    return vol.UNDEFINED


POSITION_FIELD_LIMITS = {
    CONF_OPEN_POSITION: 100,
    CONF_CLOSE_POSITION: 100,
    CONF_INTERMEDIATE_CLOSE_POSITION: 100,
    CONF_CHRISTMAS_POSITION: 100,
    CONF_VENTILATE_POSITION: 100,
    CONF_LOCKOUT_POSITION: 100,
    CONF_SHADING_POSITION: 100,
    CONF_SHADING_POSITION_ALT: 100,
    CONF_POSITION_TOLERANCE: 20,
    CONF_TILT_POSITION_TOLERANCE: 20,
    CONF_OPEN_TILT_POSITION: 100,
    CONF_CLOSE_TILT_POSITION: 100,
    CONF_VENTILATE_TILT_POSITION: 100,
    CONF_SHADING_TILT_POSITION: 100,
    CONF_SHADING_TILT_POSITION_0: 100,
    CONF_SHADING_TILT_POSITION_1: 100,
    CONF_SHADING_TILT_POSITION_2: 100,
    CONF_SHADING_TILT_POSITION_3: 100,
}

_EXTRA_POSITION_DEFAULTS: dict[str, int] = {
    CONF_SHADING_TILT_POSITION_0: DEFAULT_SHADING_TILT_POSITION_0,
    CONF_SHADING_TILT_POSITION_1: DEFAULT_SHADING_TILT_POSITION_1,
    CONF_SHADING_TILT_POSITION_2: DEFAULT_SHADING_TILT_POSITION_2,
    CONF_SHADING_TILT_POSITION_3: DEFAULT_SHADING_TILT_POSITION_3,
}


def _position_number_selector(
    key: str = CONF_OPEN_POSITION,
) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=POSITION_FIELD_LIMITS[key],
            step=1,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _normalize_position_value(key: str, value: Any) -> int | None:
    max_value = POSITION_FIELD_LIMITS[key]
    optional_positions = {CONF_LOCKOUT_POSITION, CONF_SHADING_POSITION_ALT}
    if key in optional_positions and value in (None, "", vol.UNDEFINED):
        return None
    try:
        parsed = int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        fallback = DEFAULT_POSITION_SETTINGS.get(key, _EXTRA_POSITION_DEFAULTS.get(key, 0))
        if key in optional_positions and fallback is None:
            return None
        parsed = int(fallback)
    return max(0, min(max_value, parsed))


def _position_default(config: dict[str, Any], key: str) -> int | None:
    fallback = DEFAULT_POSITION_SETTINGS.get(key, _EXTRA_POSITION_DEFAULTS.get(key, 0))
    return _normalize_position_value(key, config.get(key, fallback))


def _normalize_position_fields(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)
    for key in POSITION_FIELD_LIMITS:
        if key not in normalized:
            continue
        normalized[key] = _normalize_position_value(key, normalized[key])
    return normalized


class CoverOptionsFlow(config_entries.OptionsFlow):
    """Expose the same navigation entry point as reconfigure flows."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._cover_entry = config_entry
        self._delegate: CoverControlFlow | None = None

    def _config_flow_delegate(self) -> CoverControlFlow:
        if self._delegate is None:
            delegate = CoverControlFlow()
            delegate.hass = self.hass
            delegate.flow_id = self.flow_id
            delegate.context = {
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": self._cover_entry.entry_id,
            }
            self._delegate = delegate
        return self._delegate

    def __getattr__(self, name: str):
        if name.startswith("async_step_"):
            return getattr(self._config_flow_delegate(), name)
        raise AttributeError(name)

    async def async_step_init(self, user_input=None) -> FlowResult:
        return await self._config_flow_delegate().async_step_reconfigure(user_input)

    async def async_step_finish(self, user_input=None) -> FlowResult:
        return self.async_create_entry(title="", data={})

    async def _forward_step(self, step_id: str, user_input=None) -> FlowResult:
        return await getattr(self._config_flow_delegate(), f"async_step_{step_id}")(
            user_input
        )

    async def async_step_controller_reconfigure(self, user_input=None):
        return await self._forward_step("controller_reconfigure", user_input)

    async def async_step_room_reconfigure(self, user_input=None):
        return await self._forward_step("room_reconfigure", user_input)

    async def async_step_global_sources(self, user_input=None):
        return await self._forward_step("global_sources", user_input)

    async def async_step_diagnostics(self, user_input=None):
        return await self._forward_step("diagnostics", user_input)

    async def async_step_recovery(self, user_input=None):
        return await self._forward_step("recovery", user_input)

    async def async_step_general(self, user_input=None):
        return await self._forward_step("general", user_input)

    async def async_step_hardware(self, user_input=None):
        return await self._forward_step("hardware", user_input)

    async def async_step_positions(self, user_input=None):
        return await self._forward_step("positions", user_input)

    async def async_step_contacts(self, user_input=None):
        return await self._forward_step("contacts", user_input)

    async def async_step_room_sensors(self, user_input=None):
        return await self._forward_step("room_sensors", user_input)

    async def async_step_geometry(self, user_input=None):
        return await self._forward_step("geometry", user_input)

    async def async_step_group_assignment(self, user_input=None):
        return await self._forward_step("group_assignment", user_input)

    async def async_step_source_overrides(self, user_input=None):
        return await self._forward_step("source_overrides", user_input)

    async def async_step_safety(self, user_input=None):
        return await self._forward_step("safety", user_input)

    async def async_step_controls(self, user_input=None):
        return await self._forward_step("controls", user_input)

    async def async_step_room_diagnostics(self, user_input=None):
        result = await self._forward_step("room_diagnostics", user_input)
        if result.get("step_id") == "diagnostics":
            result["step_id"] = "room_diagnostics"
        return result


class CoverControlFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 18

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return CoverOptionsFlow(config_entry)

    def __init__(self) -> None:
        self._data: dict = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Create exactly one global parent entry without requiring a room."""

        controller_entry = self._controller_entry()
        if controller_entry is not None:
            self._data[CONF_CONTROLLER_ENTRY_ID] = controller_entry.entry_id
            return await self.async_step_room()
        if user_input is not None:
            self._data[CONF_NAME] = str(user_input.get(CONF_NAME, DEFAULT_NAME))
            return await self.async_step_global_sources()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                }
            ),
        )

    async def async_step_global_sources(self, user_input=None) -> FlowResult:
        """Collect optional shared sources for parent entry."""

        if user_input is not None:
            self._data[CONF_GLOBAL] = {
                CONF_GLOBAL_SOURCES: {
                    key: value
                    for key, value in user_input.items()
                    if value not in (None, "")
                },
                CONF_GLOBAL_DEFAULTS: {},
            }
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={
                    CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER,
                    CONF_NAME: DEFAULT_NAME,
                    CONF_GLOBAL: self._data[CONF_GLOBAL],
                    CONF_GROUPS: {group: {} for group in GROUPS},
                },
            )
        fields = {}
        for key in sorted(GLOBAL_SOURCE_KEYS):
            fields[vol.Optional(key)] = selector.EntitySelector(
                selector.EntitySelectorConfig()
            )
        return self.async_show_form(
            step_id="global_sources", data_schema=vol.Schema(fields)
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: config_entries.ConfigEntry
    ) -> dict:
        """Do not expose native ConfigSubentries for standalone rooms."""

        return {}

    def _entry(self) -> config_entries.ConfigEntry:
        """Return the parent entry attached to this reconfigure flow."""

        return self._get_reconfigure_entry()

    def _controller_entry(self) -> config_entries.ConfigEntry | None:
        """Return the existing central controller entry."""

        return next(
            (
                entry
                for entry in self._async_current_entries()
                if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_CONTROLLER
                or (
                    CONF_ENTRY_TYPE not in entry.data
                    and CONF_GLOBAL in entry.data
                    and CONF_GROUPS in entry.data
                )
            ),
            None,
        )

    async def async_step_import(self, user_input=None) -> FlowResult:
        """Create imported controller or room entries."""

        data = dict(user_input or {})
        entry_type = data.get(CONF_ENTRY_TYPE)
        if entry_type == ENTRY_TYPE_ROOM:
            room_id = str(data[CONF_ROOM_ID])
            await self.async_set_unique_id(
                f"room-{data[CONF_CONTROLLER_ENTRY_ID]}-{room_id}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=str(data.get(CONF_NAME) or room_id),
                data=data,
            )
        if entry_type == ENTRY_TYPE_CONTROLLER:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=DEFAULT_NAME, data=data)
        return self.async_abort(reason="invalid_import")

    async def async_step_room(self, user_input=None) -> FlowResult:
        """Create one standalone room ConfigEntry."""

        controller_entry_id = self._data.get(CONF_CONTROLLER_ENTRY_ID)
        if not controller_entry_id:
            controller = self._controller_entry()
            if controller is None:
                return await self.async_step_user()
            controller_entry_id = controller.entry_id
        if user_input is not None:
            from homeassistant.util.ulid import ulid_now

            title = str(user_input[CONF_NAME]).strip()
            room_id = ulid_now()
            await self.async_set_unique_id(f"room-{controller_entry_id}-{room_id}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=title,
                data={
                    CONF_ENTRY_TYPE: ENTRY_TYPE_ROOM,
                    CONF_CONTROLLER_ENTRY_ID: controller_entry_id,
                    CONF_ROOM_ID: room_id,
                    CONF_NAME: title,
                    CONF_GROUP: user_input.get(CONF_GROUP, DEFAULT_GROUP),
                    CONF_ROOM_SETTINGS: {
                        CONF_ROOM: user_input[CONF_ROOM],
                        CONF_COVERS: list(user_input[CONF_COVERS]),
                    },
                    CONF_SOURCE_OVERRIDES: {},
                },
            )
        return self.async_show_form(
            step_id="room",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): selector.TextSelector(),
                    vol.Required(CONF_GROUP, default=DEFAULT_GROUP): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(GROUPS), translation_key="group"
                        )
                    ),
                    vol.Required(CONF_ROOM): selector.AreaSelector(),
                    vol.Required(CONF_COVERS): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["cover"], multiple=True)
                    ),
                }
            ),
        )

    def _model(self) -> ConfigGroupModel:
        from .config_subentries import model_from_entries, model_from_subentries

        entry = self._entry()
        if entry.version >= 7:
            room_entries = [
                candidate
                for candidate in self.hass.config_entries.async_entries(DOMAIN)
                if candidate.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_ROOM
                and candidate.data.get(CONF_CONTROLLER_ENTRY_ID) == entry.entry_id
            ]
            return ConfigGroupModel(
                model_from_entries(entry.entry_id, entry.data, room_entries)
            )
        return ConfigGroupModel(
            model_from_subentries(entry.data, entry.subentries.values())
        )

    def _save_parent_model(self, model: ConfigGroupModel) -> None:
        entry = self._entry()
        new_data = deepcopy(dict(entry.data))
        new_data[CONF_GLOBAL] = deepcopy(model.data[CONF_GLOBAL])
        new_data[CONF_GROUPS] = deepcopy(model.data[CONF_GROUPS])
        self.hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            options={},
        )
        runtime = getattr(entry, "runtime_data", None)
        if runtime is not None and getattr(runtime, "hub", None) is not None:
            runtime.model = deepcopy(model.data)
            editing_group = getattr(self, "_editing_group", None)
            affected_rooms = (
                set(model.group_users.get(editing_group, set()))
                if editing_group
                else set(model.data[CONF_ROOMS])
            )
            if affected_rooms:
                runtime.hub.apply_model(runtime.model, affected_rooms)

    async def async_step_reconfigure(self, user_input=None) -> FlowResult:
        if self._entry().data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_ROOM:
            return await self.async_step_room_reconfigure(user_input)
        return await self.async_step_controller_reconfigure(user_input)

    async def async_step_finish(self, user_input=None) -> FlowResult:
        """Close a reconfigure flow without changing persisted data."""

        return self.async_abort(reason="reconfigure_successful")

    async def async_step_controller_reconfigure(self, user_input=None) -> FlowResult:
        """Expose controller-only configuration pages."""

        return self.async_show_menu(
            step_id="controller_reconfigure",
            menu_options=[
                "global_sources",
                "group_living",
                "group_sleep",
                "group_children",
                "diagnostics",
                "recovery",
                "finish",
            ],
        )

    async def async_step_global_sources(self, user_input=None) -> FlowResult:
        if self.source != config_entries.SOURCE_RECONFIGURE:
            if user_input is not None:
                self._data[CONF_GLOBAL] = {
                    CONF_GLOBAL_SOURCES: {
                        key: value
                        for key, value in user_input.items()
                        if value not in (None, "")
                    },
                    CONF_GLOBAL_DEFAULTS: {},
                }
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={
                        CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER,
                        CONF_NAME: DEFAULT_NAME,
                        CONF_GLOBAL: self._data[CONF_GLOBAL],
                        CONF_GROUPS: {group: {} for group in GROUPS},
                    },
                )
            fields = {}
            for key in sorted(GLOBAL_SOURCE_KEYS):
                fields[vol.Optional(key)] = selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["binary_sensor", "input_boolean", "switch"]
                    )
                    if key in {alarm[1] for alarm in SAFETY_ALARMS}
                    else selector.EntitySelectorConfig()
                )
            return self.async_show_form(
                step_id="global_sources", data_schema=vol.Schema(fields)
            )

        entry = self._entry()
        global_data = deepcopy(dict(entry.data.get(CONF_GLOBAL, {})))
        sources = dict(global_data.get(CONF_GLOBAL_SOURCES, {}))
        if user_input is not None:
            sources = {
                key: value
                for key, value in user_input.items()
                if value not in (None, "")
            }
            global_data[CONF_GLOBAL_SOURCES] = sources
            new_data = deepcopy(dict(entry.data))
            new_data[CONF_GLOBAL] = global_data
            self.hass.config_entries.async_update_entry(
                entry,
                data=new_data,
                options={},
            )
            await self.hass.config_entries.async_reload(entry.entry_id)
            return await self.async_step_controller_reconfigure()
        schema = {}
        for key in sorted(GLOBAL_SOURCE_KEYS):
            current = sources.get(key)
            marker = vol.Optional(
                key,
                description={"suggested_value": current} if current else None,
            )
            schema[marker] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["binary_sensor", "input_boolean", "switch"]
                )
                if key in {alarm[1] for alarm in SAFETY_ALARMS}
                else selector.EntitySelectorConfig()
            )
        return self.async_show_form(
            step_id="global_sources", data_schema=vol.Schema(schema)
        )

    async def async_step_recovery(self, user_input=None) -> FlowResult:
        """Restore the last-known-good controller and standalone rooms."""

        entry = self._entry()
        runtime = getattr(entry, "runtime_data", None)
        recovery = getattr(runtime, "recovery_manager", None)
        available = recovery is not None and recovery.last_known_good is not None
        if user_input is not None and user_input.get("confirm") and available:
            restored = ConfigGroupModel(recovery.last_known_good).data
            parent_data = deepcopy(dict(entry.data))
            parent_data[CONF_GLOBAL] = deepcopy(restored[CONF_GLOBAL])
            parent_data[CONF_GROUPS] = deepcopy(restored[CONF_GROUPS])
            for room_entry in self.hass.config_entries.async_entries(DOMAIN):
                if room_entry.data.get(CONF_CONTROLLER_ENTRY_ID) != entry.entry_id:
                    continue
                room_id = str(room_entry.data.get(CONF_ROOM_ID) or room_entry.entry_id)
                room = restored[CONF_ROOMS].get(room_id)
                if room is None:
                    continue
                room_data = deepcopy(dict(room))
                room_data.update({
                    CONF_ENTRY_TYPE: ENTRY_TYPE_ROOM,
                    CONF_CONTROLLER_ENTRY_ID: entry.entry_id,
                    CONF_ROOM_ID: room_id,
                })
                self.hass.config_entries.async_update_entry(room_entry, data=room_data)
            self.hass.config_entries.async_update_entry(
                entry,
                data=parent_data,
                options={},
            )
            await self.hass.config_entries.async_reload(entry.entry_id)
            return await self.async_step_controller_reconfigure()
        return self.async_show_form(
            step_id="recovery",
            data_schema=vol.Schema(
                {vol.Required("confirm", default=False): bool}
            ),
            description_placeholders={"available": str(available).lower()},
        )

    async def async_step_diagnostics(self, user_input=None) -> FlowResult:
        model = self._model()
        usage = [
            f"{group}: {', '.join(self._room_names(model, sorted(rooms))) or '—'}"
            for group, rooms in model.group_users.items()
        ]
        return self.async_show_form(
            step_id="diagnostics",
            data_schema=vol.Schema({}),
            description_placeholders={"groups": "; ".join(usage)},
        )

    async def async_step_group_living(self, user_input=None) -> FlowResult:
        return await self._start_group(GROUP_LIVING)

    async def async_step_group_sleep(self, user_input=None) -> FlowResult:
        return await self._start_group(GROUP_SLEEP)

    async def async_step_group_children(self, user_input=None) -> FlowResult:
        return await self._start_group(GROUP_CHILDREN)

    async def _start_group(self, group: str) -> FlowResult:
        self._editing_group = group
        return await self.async_step_group_sections()

    async def async_step_group_sections(self, user_input=None) -> FlowResult:
        return self.async_show_menu(
            step_id="group_sections",
            menu_options=[
                "group_time",
                "group_brightness",
                "group_sun",
                "group_shading",
                "group_ventilation",
                "group_resident",
                "group_behavior",
                "group_safety",
                "group_back",
            ],
            description_placeholders=self._group_context_placeholders(),
        )

    async def async_step_group_back(self, user_input=None) -> FlowResult:
        self._editing_group = None
        return await self.async_step_controller_reconfigure()

    async def _async_group_section_step(
        self,
        section_name: str,
        step_id: str,
        user_input,
        *,
        capabilities: tuple[str, ...],
    ) -> FlowResult:
        group = getattr(self, "_editing_group", None)
        if group not in GROUPS:
            return await self.async_step_controller_reconfigure()
        model = self._model()
        existing = dict(model.data[CONF_GROUPS][group])
        allowed = capability_keys(section_name, capabilities) - GROUP_BLOCKED_KEYS
        if user_input is not None:
            selected = extract_sparse_settings(
                flatten_section_input(user_input),
                section_name,
                {key: value for key, value in existing.items() if key in allowed},
                field_selection=None,
                allowed_keys=allowed,
            )
            model.data[CONF_GROUPS][group] = {
                **{key: value for key, value in existing.items() if key not in allowed},
                **selected,
            }
            self._save_parent_model(model)
            return await self.async_step_group_sections()
        return self.async_show_form(
            step_id=step_id,
            data_schema=build_group_schema(
                section_name,
                existing,
                system_defaults(),
                field_selection=None,
                allowed_keys=allowed,
            ),
            description_placeholders=self._group_context_placeholders(),
        )

    def _group_context_placeholders(self) -> dict[str, str]:
        group = getattr(self, "_editing_group", DEFAULT_GROUP)
        model = self._model()
        rooms = self._room_names(model, sorted(model.group_users.get(group, ())))
        return {
            "group": group,
            "group_name": group,
            "group_usage": ", ".join(rooms) or "—",
        }

    async def async_step_group_time(self, user_input=None) -> FlowResult:
        return await self._async_group_section_step(
            GROUP_SECTION_TIME, "group_time", user_input,
            capabilities=("opening", "closing", "workday", "calendar"),
        )

    async def async_step_group_brightness(self, user_input=None) -> FlowResult:
        return await self._async_group_section_step(
            GROUP_SECTION_TIME, "group_brightness", user_input,
            capabilities=("brightness",),
        )

    async def async_step_group_sun(self, user_input=None) -> FlowResult:
        group = getattr(self, "_editing_group", None)
        if group not in GROUPS:
            return await self.async_step_controller_reconfigure()
        model = self._model()
        existing = dict(model.data[CONF_GROUPS][group])
        mode_keys = {CONF_OPEN_MODE, CONF_CLOSE_MODE}
        if user_input is not None:
            selected = extract_sparse_settings(
                flatten_section_input(user_input),
                GROUP_SECTION_TIME,
                {key: value for key, value in existing.items() if key in mode_keys},
                allowed_keys=mode_keys,
            )
            model.data[CONF_GROUPS][group] = {
                **existing,
                **selected,
            }
            modes = {selected.get(CONF_OPEN_MODE), selected.get(CONF_CLOSE_MODE)}
            model.data[CONF_GROUPS][group].update(
                {
                    CONF_AUTO_UP: True,
                    CONF_AUTO_DOWN: True,
                    CONF_AUTO_TIME: True,
                    CONF_AUTO_SUN: bool(
                        modes - {None, MODE_TIME, MODE_BRIGHTNESS}
                    ),
                    CONF_AUTO_BRIGHTNESS: MODE_BRIGHTNESS in modes,
                }
            )
            self._save_parent_model(model)
            return await self.async_step_group_sun_details()
        return self.async_show_form(
            step_id="group_sun",
            data_schema=build_group_schema(
                GROUP_SECTION_TIME,
                existing,
                system_defaults(),
                allowed_keys=mode_keys,
            ),
            description_placeholders=self._group_context_placeholders(),
        )

    async def async_step_group_sun_details(self, user_input=None) -> FlowResult:
        group = getattr(self, "_editing_group", None)
        if group not in GROUPS:
            return await self.async_step_controller_reconfigure()
        model = self._model()
        existing = dict(model.data[CONF_GROUPS][group])
        open_mode = str(existing.get(CONF_OPEN_MODE, DEFAULT_OPEN_MODE))
        close_mode = str(existing.get(CONF_CLOSE_MODE, DEFAULT_CLOSE_MODE))
        allowed: set[str] = set()
        if open_mode == MODE_ELEVATION:
            allowed.add(CONF_SUN_ELEVATION_OPEN)
        if close_mode == MODE_ELEVATION:
            allowed.add(CONF_SUN_ELEVATION_CLOSE)
        if open_mode in {MODE_SUNRISE, MODE_GOLDEN_HOUR}:
            allowed.add(CONF_ASTRO_OPEN_OFFSET)
        if close_mode in {MODE_SUNSET, MODE_GOLDEN_HOUR}:
            allowed.add(CONF_ASTRO_CLOSE_OFFSET)
        if not allowed:
            return await self.async_step_group_sections()
        if user_input is not None:
            selected = extract_sparse_settings(
                flatten_section_input(user_input),
                GROUP_SECTION_TIME,
                {key: value for key, value in existing.items() if key in allowed},
                allowed_keys=allowed,
            )
            model.data[CONF_GROUPS][group] = {**existing, **selected}
            self._save_parent_model(model)
            return await self.async_step_group_sections()
        return self.async_show_form(
            step_id="group_sun_details",
            data_schema=build_group_schema(
                GROUP_SECTION_TIME,
                existing,
                system_defaults(),
                allowed_keys=allowed,
            ),
            description_placeholders=self._group_context_placeholders(),
        )

    async def async_step_group_shading(self, user_input=None) -> FlowResult:
        group = getattr(self, "_editing_group", None)
        if group not in GROUPS:
            return await self.async_step_controller_reconfigure()
        model = self._model()
        existing = dict(model.data[CONF_GROUPS][group])
        allowed = {CONF_SHADING_MODE}
        if user_input is not None:
            selected = extract_sparse_settings(
                flatten_section_input(user_input),
                GROUP_SECTION_SHADING,
                {key: value for key, value in existing.items() if key in allowed},
                allowed_keys=allowed,
            )
            mode = str(selected.get(CONF_SHADING_MODE, SHADING_MODE_OFF))
            self._selected_shading_mode = mode
            model.data[CONF_GROUPS][group] = {
                **existing,
                **selected,
                CONF_AUTO_SHADING: mode != SHADING_MODE_OFF,
            }
            if mode == SHADING_MODE_OFF:
                for key in (
                    CONF_SHADING_DIRECTION,
                    CONF_SHADING_DIRECTION_RANGE,
                    CONF_SUN_ELEVATION_MIN,
                    CONF_SUN_ELEVATION_MAX,
                    CONF_SHADING_INSIDE_TEMPERATURE_THRESHOLD,
                    CONF_SHADING_INSIDE_TEMPERATURE_HYSTERESIS,
                    CONF_SHADING_OUTSIDE_TEMPERATURE_THRESHOLD,
                    CONF_SHADING_OUTSIDE_TEMPERATURE_HYSTERESIS,
                    CONF_SHADING_BRIGHTNESS_THRESHOLD,
                    CONF_SHADING_BRIGHTNESS_HYSTERESIS,
                    CONF_HEAT_PROTECTION_ENABLED,
                    CONF_HEAT_PROTECTION_THRESHOLD,
                ):
                    model.data[CONF_GROUPS][group].pop(key, None)
            self._save_parent_model(model)
            return await self.async_step_group_shading_details()
        return self.async_show_form(
            step_id="group_shading",
            data_schema=build_group_schema(
                GROUP_SECTION_SHADING,
                existing,
                system_defaults(),
                allowed_keys=allowed,
            ),
            description_placeholders=self._group_context_placeholders(),
        )

    async def async_step_group_shading_details(self, user_input=None) -> FlowResult:
        group = getattr(self, "_editing_group", None)
        if group not in GROUPS:
            return await self.async_step_controller_reconfigure()
        model = self._model()
        existing = dict(model.data[CONF_GROUPS][group])
        mode = str(
            getattr(
                self,
                "_selected_shading_mode",
                existing.get(CONF_SHADING_MODE, SHADING_MODE_OFF),
            )
        )
        allowed = {
            CONF_SHADING_WAITINGTIME_END,
            CONF_KEEP_SUN_PROTECTION,
            CONF_SHADING_TILT_ELEVATION_1,
            CONF_SHADING_TILT_ELEVATION_2,
            CONF_SHADING_TILT_ELEVATION_3,
        }
        if mode in {
            SHADING_MODE_INSIDE_OUTSIDE,
            SHADING_MODE_INSIDE_OUTSIDE_DIRECTION,
            SHADING_MODE_INSIDE,
        }:
            allowed.update(
                {
                    CONF_SHADING_INSIDE_TEMPERATURE_THRESHOLD,
                    CONF_SHADING_INSIDE_TEMPERATURE_HYSTERESIS,
                }
            )
        if mode in {
            SHADING_MODE_INSIDE_OUTSIDE,
            SHADING_MODE_INSIDE_OUTSIDE_DIRECTION,
            SHADING_MODE_OUTSIDE_DIRECTION,
            SHADING_MODE_OUTSIDE,
        }:
            allowed.update(
                {
                    CONF_SHADING_OUTSIDE_TEMPERATURE_THRESHOLD,
                    CONF_SHADING_OUTSIDE_TEMPERATURE_HYSTERESIS,
                    CONF_SHADING_BRIGHTNESS_THRESHOLD,
                    CONF_SHADING_BRIGHTNESS_HYSTERESIS,
                    CONF_HEAT_PROTECTION_ENABLED,
                    CONF_HEAT_PROTECTION_THRESHOLD,
                }
            )
        if mode in {
            SHADING_MODE_DIRECTION,
            SHADING_MODE_INSIDE_OUTSIDE_DIRECTION,
            SHADING_MODE_OUTSIDE_DIRECTION,
        }:
            allowed.update(
                {
                    CONF_SHADING_DIRECTION,
                    CONF_SHADING_DIRECTION_RANGE,
                    CONF_SUN_ELEVATION_MIN,
                    CONF_SUN_ELEVATION_MAX,
                }
            )
        if mode == SHADING_MODE_OFF:
            return await self.async_step_group_sections()
        if user_input is not None:
            selected = extract_sparse_settings(
                flatten_section_input(user_input),
                GROUP_SECTION_SHADING,
                {key: value for key, value in existing.items() if key in allowed},
                allowed_keys=allowed,
            )
            mode_fields = {
                CONF_SHADING_DIRECTION,
                CONF_SHADING_DIRECTION_RANGE,
                CONF_SUN_ELEVATION_MIN,
                CONF_SUN_ELEVATION_MAX,
                CONF_SHADING_INSIDE_TEMPERATURE_THRESHOLD,
                CONF_SHADING_INSIDE_TEMPERATURE_HYSTERESIS,
                CONF_SHADING_OUTSIDE_TEMPERATURE_THRESHOLD,
                CONF_SHADING_OUTSIDE_TEMPERATURE_HYSTERESIS,
                CONF_SHADING_BRIGHTNESS_THRESHOLD,
                CONF_SHADING_BRIGHTNESS_HYSTERESIS,
                CONF_HEAT_PROTECTION_ENABLED,
                CONF_HEAT_PROTECTION_THRESHOLD,
            }
            retained = {
                key: value
                for key, value in existing.items()
                if key not in mode_fields or key in allowed
            }
            model.data[CONF_GROUPS][group] = {**retained, **selected}
            self._save_parent_model(model)
            return await self.async_step_group_sections()
        return self.async_show_form(
            step_id="group_shading_details",
            data_schema=build_group_schema(
                GROUP_SECTION_SHADING,
                existing,
                system_defaults(),
                allowed_keys=allowed,
            ),
            description_placeholders=self._group_context_placeholders(),
        )

    async def async_step_group_ventilation(self, user_input=None) -> FlowResult:
        return await self._async_group_section_step(
            GROUP_SECTION_BEHAVIOR, "group_ventilation", user_input,
            capabilities=("ventilation",),
        )

    async def async_step_group_resident(self, user_input=None) -> FlowResult:
        return await self._async_group_section_step(
            GROUP_SECTION_BEHAVIOR, "group_resident", user_input,
            capabilities=("resident",),
        )

    async def async_step_group_behavior(self, user_input=None) -> FlowResult:
        return await self._async_group_section_step(
            GROUP_SECTION_BEHAVIOR, "group_behavior", user_input,
            capabilities=("manual_override", "movement_protection", "tilt_behavior"),
        )

    async def async_step_group_safety(self, user_input=None) -> FlowResult:
        return await self._async_group_section_step(
            GROUP_SECTION_BEHAVIOR, "group_safety", user_input,
            capabilities=("safety",),
        )

    @staticmethod
    def _room_names(model: ConfigGroupModel, room_ids: list[str]) -> list[str]:
        return [
            str(model.data[CONF_ROOMS].get(room_id, {}).get(CONF_NAME, room_id))
            for room_id in room_ids
        ]


class RoomFlowMixin:
    """Provide room-local steps for standalone room ConfigEntries."""

    def _room_entry(self) -> config_entries.ConfigEntry:
        """Return the standalone room ConfigEntry being reconfigured."""

        return self._get_reconfigure_entry()

    def _room_id(self) -> str:
        """Return the stable room id for this flow."""

        entry = self._room_entry()
        return str(entry.data.get(CONF_ROOM_ID) or entry.entry_id)

    def _room_title(self) -> str:
        """Return the current room title."""

        entry = self._room_entry()
        return str(entry.data.get(CONF_NAME) or entry.title or self._room_id())

    def _room_data(self) -> dict[str, Any]:
        """Return a mutable copy of persisted room data."""

        return deepcopy(dict(self._room_entry().data))

    def _controller_entry_for_room(self) -> config_entries.ConfigEntry | None:
        """Return the controller entry that owns this room."""

        return controller_entry_for_room(self.hass, self._room_entry())

    def _controller_groups(self) -> dict[str, Any]:
        """Return the controller-owned fixed groups."""

        controller_entry = self._controller_entry_for_room()
        if controller_entry is None:
            return {}
        return dict(controller_entry.data.get(CONF_GROUPS, {}))

    async def _save_room(
        self, data: dict[str, Any], *, title: str | None = None
    ) -> FlowResult:
        """Persist room data through the owning Home Assistant API."""

        entry = self._room_entry()
        saved = deepcopy(dict(data))
        saved[CONF_ENTRY_TYPE] = ENTRY_TYPE_ROOM
        saved[CONF_CONTROLLER_ENTRY_ID] = entry.data[CONF_CONTROLLER_ENTRY_ID]
        saved[CONF_ROOM_ID] = entry.data.get(CONF_ROOM_ID, entry.entry_id)
        self.hass.config_entries.async_update_entry(
            entry,
            data=saved,
            title=title or str(saved.get(CONF_NAME, entry.title)),
        )
        await self.hass.config_entries.async_reload(entry.entry_id)
        return await self.async_step_room_reconfigure()

    def _room_context_placeholders(self) -> dict[str, str]:
        data = self._room_data()
        settings = dict(data.get(CONF_ROOM_SETTINGS, {}))
        covers = settings.get(CONF_COVERS, [])
        return {
            "room_name": str(data.get(CONF_NAME) or self._room_title()),
            "area": str(settings.get(CONF_ROOM) or "—"),
            "cover_count": str(len(covers) if isinstance(covers, list) else 0),
            "group": str(data.get(CONF_GROUP, DEFAULT_GROUP)),
            "group_name": str(data.get(CONF_GROUP, DEFAULT_GROUP)),
        }

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Create one room without duplicating parent global settings."""

        if user_input is not None:
            title = str(user_input[CONF_NAME]).strip()
            return self.async_create_entry(
                title=title,
                data={
                    CONF_NAME: title,
                    CONF_GROUP: user_input.get(CONF_GROUP, DEFAULT_GROUP),
                    CONF_ROOM_SETTINGS: {
                        CONF_ROOM: user_input[CONF_ROOM],
                        CONF_COVERS: list(user_input[CONF_COVERS]),
                    },
                    CONF_SOURCE_OVERRIDES: {},
                },
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): selector.TextSelector(),
                    vol.Required(CONF_GROUP, default=DEFAULT_GROUP): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(GROUPS), translation_key="group"
                        )
                    ),
                    vol.Required(CONF_ROOM): selector.AreaSelector(),
                    vol.Required(CONF_COVERS): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["cover"], multiple=True)
                    ),
                }
            ),
        )

    async def async_step_reconfigure(self, user_input=None) -> FlowResult:
        """Expose room-only configuration pages."""

        return await self.async_step_room_reconfigure(user_input)

    async def async_step_room_reconfigure(self, user_input=None) -> FlowResult:
        """Expose room-only configuration pages."""

        return self.async_show_menu(
            step_id="room_reconfigure",
            menu_options=[
                "general",
                "hardware",
                "positions",
                "contacts",
                "room_sensors",
                "group_assignment",
                "safety",
                "source_overrides",
                "controls",
                "room_diagnostics",
                "finish",
            ],
            description_placeholders=self._room_context_placeholders(),
        )

    async def async_step_controls(self, user_input=None) -> FlowResult:
        data = self._room_data()
        settings = dict(data.get(CONF_ROOM_SETTINGS, {}))
        if user_input is not None:
            settings.pop(CONF_MANUAL_CONTROL, None)
            for key in (
                CONF_ENABLE_RECALIBRATE_BUTTON,
                CONF_ENABLE_CLEAR_MANUAL_OVERRIDE_BUTTON,
                CONF_ENABLE_LOGBOOK_COVER,
            ):
                settings[key] = user_input.get(key) or None
            data[CONF_ROOM_SETTINGS] = settings
            return await self._save_room(data)
        merged = {**DEFAULT_BUTTON_SETTINGS, **settings}
        return self.async_show_form(
            step_id="controls",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ENABLE_RECALIBRATE_BUTTON,
                        default=bool(merged.get(CONF_ENABLE_RECALIBRATE_BUTTON)),
                    ): bool,
                    vol.Optional(
                        CONF_ENABLE_CLEAR_MANUAL_OVERRIDE_BUTTON,
                        default=bool(
                            merged.get(CONF_ENABLE_CLEAR_MANUAL_OVERRIDE_BUTTON)
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_ENABLE_LOGBOOK_COVER,
                        default=bool(settings.get(CONF_ENABLE_LOGBOOK_COVER, False)),
                    ): bool,
                }
            ),
            description_placeholders=self._room_context_placeholders(),
        )

    async def async_step_safety(self, user_input=None) -> FlowResult:
        data = self._room_data()
        settings = dict(data.get(CONF_ROOM_SETTINGS, {}))
        if user_input is not None:
            for _alarm, _entity, _enabled, _target, room_key, _default in SAFETY_ALARMS:
                settings[room_key] = bool(user_input.get(room_key, False))
            data[CONF_ROOM_SETTINGS] = settings
            return await self._save_room(data)
        return self.async_show_form(
            step_id="safety",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        room_key,
                        default=bool(
                            settings.get(
                                room_key, DEFAULT_SAFETY_PARTICIPATION[room_key]
                            )
                        ),
                    ): bool
                    for _alarm, _entity, _enabled, _target, room_key, _default in SAFETY_ALARMS
                }
            ),
            description_placeholders=self._room_context_placeholders(),
        )

    async def async_step_general(self, user_input=None) -> FlowResult:
        data = self._room_data()
        settings = dict(data.get(CONF_ROOM_SETTINGS, {}))
        if user_input is not None:
            title = str(user_input[CONF_NAME]).strip()
            data[CONF_NAME] = title
            settings[CONF_ROOM] = user_input[CONF_ROOM]
            data[CONF_ROOM_SETTINGS] = settings
            return await self._save_room(data, title=title)
        return self.async_show_form(
            step_id="general",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=self._room_title()): selector.TextSelector(),
                    vol.Required(
                        CONF_ROOM, default=settings.get(CONF_ROOM)
                    ): selector.AreaSelector(),
                }
            ),
            description_placeholders=self._room_context_placeholders(),
        )

    async def async_step_contacts(self, user_input=None) -> FlowResult:
        data = self._room_data()
        settings = dict(data.get(CONF_ROOM_SETTINGS, {}))
        covers = settings.get(CONF_COVERS, [])
        key_map = self._contact_key_map(covers)
        if user_input is not None:
            full_map: dict[str, list[str]] = {}
            tilt_map: dict[str, list[str]] = {}
            for cover in covers:
                full_map[cover] = list(user_input.get(key_map[(cover, "full")], []))
                tilt_map[cover] = list(user_input.get(key_map[(cover, "tilt")], []))
            settings[CONF_WINDOW_SENSOR_FULL] = full_map
            settings[CONF_WINDOW_SENSOR_TILT] = tilt_map
            data[CONF_ROOM_SETTINGS] = settings
            return await self._save_room(data)
        multi_selector = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["binary_sensor"], multiple=True)
        )
        schema = {}
        full = settings.get(CONF_WINDOW_SENSOR_FULL, {})
        tilt = settings.get(CONF_WINDOW_SENSOR_TILT, {})
        for cover in covers:
            schema[
                vol.Optional(key_map[(cover, "full")], default=full.get(cover, []))
            ] = multi_selector
            schema[
                vol.Optional(key_map[(cover, "tilt")], default=tilt.get(cover, []))
            ] = multi_selector
        return self.async_show_form(
            step_id="contacts",
            data_schema=vol.Schema(schema),
            description_placeholders=self._room_context_placeholders(),
        )

    @staticmethod
    def _contact_key(index: int, contact_type: str) -> str:
        return f"cover_{index}_{contact_type}"

    def _contact_key_map(self, covers: list[str]) -> dict[tuple[str, str], str]:
        return {
            (cover, contact_type): self._contact_key(index, contact_type)
            for index, cover in enumerate(covers)
            for contact_type in ("full", "tilt")
        }

    async def async_step_room_sensors(self, user_input=None) -> FlowResult:
        data = self._room_data()
        settings = dict(data.get(CONF_ROOM_SETTINGS, {}))
        if user_input is not None:
            for key, value in user_input.items():
                if value in (None, ""):
                    settings.pop(key, None)
                else:
                    settings[key] = value
            data[CONF_ROOM_SETTINGS] = settings
            return await self._save_room(data)
        return self.async_show_form(
            step_id="room_sensors",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_TEMPERATURE_SENSOR_INDOOR,
                        default=_selector_default(settings.get(CONF_TEMPERATURE_SENSOR_INDOOR)),
                    ): selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor"])),
                    vol.Optional(
                        CONF_RESIDENT_SENSOR,
                        default=_selector_default(settings.get(CONF_RESIDENT_SENSOR)),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["binary_sensor", "input_boolean", "switch"]
                        )
                    ),
                }
            ),
            description_placeholders=self._room_context_placeholders(),
        )

    async def async_step_geometry(self, user_input=None) -> FlowResult:
        return await self.async_step_room_reconfigure()

    async def async_step_diagnostics(self, user_input=None) -> FlowResult:
        entry = self._room_entry()
        data = self._room_data()
        settings = dict(data.get(CONF_ROOM_SETTINGS, {}))
        snapshot = self._room_entry_snapshot(entry, self._room_id())

        return self.async_show_form(
            step_id="diagnostics",
            data_schema=vol.Schema({}),
            description_placeholders={
                "room": str(data.get(CONF_NAME, self._room_title())),
                "area": str(settings.get(CONF_ROOM) or "—"),
                "cover_count": str(len(settings.get(CONF_COVERS, []))),
                "group": str(data.get(CONF_GROUP, DEFAULT_GROUP)),
                "group_name": str(data.get(CONF_GROUP, DEFAULT_GROUP)),
                "resident_sensor": self._entity_name(settings.get(CONF_RESIDENT_SENSOR)),
                "temperature_sensor": self._entity_name(settings.get(CONF_TEMPERATURE_SENSOR_INDOOR)),
                "next_open": self._format_schedule_event(snapshot.get("next_open")),
                "next_close": self._format_schedule_event(snapshot.get("next_close")),
            },
        )

    def _room_entry_snapshot(
        self, entry: config_entries.ConfigEntry, subentry_id: str
    ) -> dict[str, Any]:
        runtime = getattr(entry, "runtime_data", None)
        managers = getattr(runtime, "room_managers", {})
        manager = managers.get(subentry_id) if isinstance(managers, dict) else None
        if manager is None and entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_ROOM:
            controller_entry = controller_entry_for_room(self.hass, entry)
            runtime = getattr(controller_entry, "runtime_data", None)
            managers = getattr(runtime, "room_managers", {})
            manager = managers.get(subentry_id) if isinstance(managers, dict) else None
        if manager is None:
            return {}
        snapshot = manager.entry_snapshot()
        return snapshot if isinstance(snapshot, dict) else {}

    def _format_schedule_event(self, event: Any) -> str:
        if not (
            isinstance(event, tuple)
            and len(event) == 2
            and isinstance(event[0], datetime)
        ):
            return "—"
        when = dt_util.as_local(event[0])
        cover_name = self._entity_name(event[1])
        value = when.strftime("%Y-%m-%d %H:%M")
        return value if cover_name == "—" else f"{value} ({cover_name})"

    def _entity_name(self, entity_id: Any) -> str:
        if not entity_id:
            return "—"
        state = self.hass.states.get(str(entity_id))
        return state.name if state else "—"

    async def async_step_hardware(self, user_input=None) -> FlowResult:
        """Edit room-local hardware while retaining function configuration."""

        data = self._room_data()
        settings = data.get(CONF_ROOM_SETTINGS, {})
        if user_input is not None:
            settings = dict(data.get(CONF_ROOM_SETTINGS, {}))
            settings.update(_normalize_position_fields(dict(user_input)))
            if CONF_TILT_POSITION_TOLERANCE in user_input:
                settings[CONF_TILT_POSITION_TOLERANCE] = float(
                    user_input[CONF_TILT_POSITION_TOLERANCE]
                )
            settings[CONF_COVERS] = list(user_input[CONF_COVERS])
            data[CONF_ROOM_SETTINGS] = settings
            return await self._save_room(data)
        return self.async_show_form(
            step_id="hardware",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_COVERS, default=settings.get(CONF_COVERS, [])
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["cover"], multiple=True)
                    ),
                    vol.Required(
                        CONF_COVER_TYPE,
                        default=settings.get(
                            CONF_COVER_TYPE,
                            DEFAULT_BEHAVIOR_SETTINGS[CONF_COVER_TYPE],
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                CONF_COVER_TYPE_BLIND,
                                CONF_COVER_TYPE_AWNING,
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="cover_type",
                        )
                    ),
                    vol.Optional(
                        CONF_DRIVE_TIME,
                        default=settings.get(CONF_DRIVE_TIME, DEFAULT_DRIVE_TIME),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=600,
                            step=0.1,
                            unit_of_measurement="s",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_COVER_TILT_WAIT_MODE,
                        default=settings.get(
                            CONF_COVER_TILT_WAIT_MODE,
                            DEFAULT_COVER_TILT_WAIT_MODE,
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                COVER_TILT_WAIT_FIXED_DELAY,
                                COVER_TILT_WAIT_IDLE,
                                COVER_TILT_WAIT_BEFORE_POSITION,
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="cover_tilt_wait_mode",
                        )
                    ),
                    vol.Optional(
                        CONF_COVER_TILT_WAIT_TIMEOUT,
                        default=settings.get(
                            CONF_COVER_TILT_WAIT_TIMEOUT,
                            DEFAULT_COVER_TILT_WAIT_TIMEOUT,
                        ),
                    ): vol.Coerce(int),
                    vol.Required(
                        CONF_POSITION_TOLERANCE,
                        default=_position_default(dict(settings), CONF_POSITION_TOLERANCE),
                    ): _position_number_selector(CONF_POSITION_TOLERANCE),
                    vol.Optional(
                        CONF_TILT_POSITION_TOLERANCE,
                        default=_position_default(dict(settings), CONF_TILT_POSITION_TOLERANCE),
                    ): _position_number_selector(CONF_TILT_POSITION_TOLERANCE),
                }
            ),
            description_placeholders=self._room_context_placeholders(),
        )

    async def async_step_positions(self, user_input=None) -> FlowResult:
        """Edit room-owned physical cover and tilt positions."""

        data = self._room_data()
        settings = dict(data.get(CONF_ROOM_SETTINGS, {}))
        if user_input is not None:
            submitted: dict[str, Any] = {}
            for value in user_input.values():
                if isinstance(value, dict):
                    submitted.update(value)
            keys = {
                CONF_OPEN_POSITION,
                CONF_CLOSE_POSITION,
                CONF_INTERMEDIATE_CLOSE_POSITION,
                CONF_CHRISTMAS_POSITION,
                CONF_SUMMER_SKIP_CLOSE_ENABLED,
                CONF_CHRISTMAS_POSITION_ENABLED,
                CONF_SHADING_POSITION,
                CONF_SHADING_POSITION_ALT,
                CONF_SHADING_POSITION_ALT_ENTITY,
                CONF_VENTILATE_POSITION,
                CONF_LOCKOUT_POSITION,
                CONF_OPEN_TILT_POSITION,
                CONF_CLOSE_TILT_POSITION,
                CONF_SHADING_TILT_POSITION,
                CONF_VENTILATE_TILT_POSITION,
                CONF_SHADING_TILT_POSITION_0,
                CONF_SHADING_TILT_POSITION_1,
                CONF_SHADING_TILT_POSITION_2,
                CONF_SHADING_TILT_POSITION_3,
            }
            normalized = _normalize_position_fields(
                {key: value for key, value in submitted.items() if key in keys}
            )
            optional_keys = {CONF_LOCKOUT_POSITION, CONF_SHADING_POSITION_ALT}
            for key in keys:
                if key in normalized and normalized[key] not in (None, ""):
                    settings[key] = normalized[key]
                elif key in submitted or key in optional_keys:
                    settings.pop(key, None)
            data[CONF_ROOM_SETTINGS] = settings
            return await self._save_room(data)

        return self.async_show_form(
            step_id="positions",
            data_schema=vol.Schema(
                {
                    vol.Optional("positions"): section(
                        vol.Schema(
                            {
                                vol.Required(
                                    CONF_OPEN_POSITION,
                                    default=_position_default(settings, CONF_OPEN_POSITION),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_CLOSE_POSITION,
                                    default=_position_default(settings, CONF_CLOSE_POSITION),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_INTERMEDIATE_CLOSE_POSITION,
                                    default=_position_default(settings, CONF_INTERMEDIATE_CLOSE_POSITION),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_CHRISTMAS_POSITION,
                                    default=_position_default(settings, CONF_CHRISTMAS_POSITION),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_SUMMER_SKIP_CLOSE_ENABLED,
                                    default=bool(settings.get(CONF_SUMMER_SKIP_CLOSE_ENABLED, False)),
                                ): bool,
                                vol.Required(
                                    CONF_CHRISTMAS_POSITION_ENABLED,
                                    default=bool(settings.get(CONF_CHRISTMAS_POSITION_ENABLED, False)),
                                ): bool,
                                vol.Required(
                                    CONF_SHADING_POSITION,
                                    default=_position_default(settings, CONF_SHADING_POSITION),
                                ): _position_number_selector(),
                                vol.Optional(
                                    CONF_SHADING_POSITION_ALT,
                                    default=_selector_default(settings.get(CONF_SHADING_POSITION_ALT)),
                                ): vol.Any(_position_number_selector(), None),
                                vol.Optional(
                                    CONF_SHADING_POSITION_ALT_ENTITY,
                                    default=_selector_default(settings.get(CONF_SHADING_POSITION_ALT_ENTITY)),
                                ): selector.EntitySelector(
                                    selector.EntitySelectorConfig(
                                        domain=["binary_sensor", "input_boolean"]
                                    )
                                ),
                                vol.Required(
                                    CONF_VENTILATE_POSITION,
                                    default=_position_default(settings, CONF_VENTILATE_POSITION),
                                ): _position_number_selector(),
                                vol.Optional(
                                    CONF_LOCKOUT_POSITION,
                                    default=_selector_default(settings.get(CONF_LOCKOUT_POSITION)),
                                ): vol.Any(_position_number_selector(), None),
                            }
                        ),
                        {"collapsed": False},
                    ),
                    vol.Optional("tilt_positions"): section(
                        vol.Schema(
                            {
                                vol.Required(
                                    CONF_OPEN_TILT_POSITION,
                                    default=_position_default(settings, CONF_OPEN_TILT_POSITION),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_CLOSE_TILT_POSITION,
                                    default=_position_default(settings, CONF_CLOSE_TILT_POSITION),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_SHADING_TILT_POSITION,
                                    default=_position_default(settings, CONF_SHADING_TILT_POSITION),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_VENTILATE_TILT_POSITION,
                                    default=_position_default(settings, CONF_VENTILATE_TILT_POSITION),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_SHADING_TILT_POSITION_0,
                                    default=_position_default(settings, CONF_SHADING_TILT_POSITION_0),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_SHADING_TILT_POSITION_1,
                                    default=_position_default(settings, CONF_SHADING_TILT_POSITION_1),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_SHADING_TILT_POSITION_2,
                                    default=_position_default(settings, CONF_SHADING_TILT_POSITION_2),
                                ): _position_number_selector(),
                                vol.Required(
                                    CONF_SHADING_TILT_POSITION_3,
                                    default=_position_default(settings, CONF_SHADING_TILT_POSITION_3),
                                ): _position_number_selector(),
                            }
                        ),
                    ),
                }
            ),
            description_placeholders=self._room_context_placeholders(),
        )

    async def async_step_source_overrides(self, user_input=None) -> FlowResult:
        data = self._room_data()
        overrides = dict(data.get(CONF_SOURCE_OVERRIDES, {}))
        if user_input is not None:
            data[CONF_SOURCE_OVERRIDES] = {
                key: value
                for key, value in user_input.items()
                if value not in (None, "")
            }
            return await self._save_room(data)
        schema = {}
        for key in sorted(ROOM_SOURCE_OVERRIDE_KEYS):
            current = overrides.get(key)
            marker = vol.Optional(
                key,
                description={"suggested_value": current} if current else None,
            )
            schema[marker] = selector.EntitySelector(selector.EntitySelectorConfig())
        return self.async_show_form(
            step_id="source_overrides",
            data_schema=vol.Schema(schema),
            description_placeholders=self._room_context_placeholders(),
        )

    async def async_step_group_assignment(self, user_input=None) -> FlowResult:
        data = self._room_data()
        if user_input is not None:
            data[CONF_GROUP] = user_input[CONF_GROUP]
            return await self._save_room(data)
        return self.async_show_form(
            step_id="group_assignment",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_GROUP, default=data.get(CONF_GROUP, DEFAULT_GROUP)
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(GROUPS), translation_key="group"
                        )
                    )
                }
            ),
            description_placeholders=self._room_context_placeholders(),
        )


for _room_flow_name in (
    "_room_entry",
    "_room_id",
    "_room_title",
    "_room_data",
    "_controller_entry_for_room",
    "_controller_groups",
    "_save_room",
    "_room_context_placeholders",
    "_contact_key",
    "_contact_key_map",
    "_room_entry_snapshot",
    "_format_schedule_event",
    "_entity_name",
    "async_step_controls",
    "async_step_general",
    "async_step_contacts",
    "async_step_room_sensors",
    "async_step_geometry",
    "async_step_hardware",
    "async_step_positions",
    "async_step_safety",
    "async_step_source_overrides",
    "async_step_group_assignment",
):
    setattr(CoverControlFlow, _room_flow_name, getattr(RoomFlowMixin, _room_flow_name))

CoverControlFlow._contact_key = staticmethod(RoomFlowMixin._contact_key)
CoverControlFlow.async_step_room_reconfigure = RoomFlowMixin.async_step_room_reconfigure
CoverControlFlow.async_step_room_diagnostics = RoomFlowMixin.async_step_diagnostics


async def _cover_control_diagnostics(self, user_input=None) -> FlowResult:
    """Route diagnostics to controller or room content by entry type."""

    if self._entry().data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_ROOM:
        return await RoomFlowMixin.async_step_diagnostics(self, user_input)
    model = self._model()
    usage = [
        f"{group}: {', '.join(self._room_names(model, sorted(rooms))) or '—'}"
        for group, rooms in model.group_users.items()
    ]
    return self.async_show_form(
        step_id="diagnostics",
        data_schema=vol.Schema({}),
        description_placeholders={"groups": "; ".join(usage)},
    )


CoverControlFlow.async_step_diagnostics = _cover_control_diagnostics
