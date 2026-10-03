"""Integration-wide configuration, dependency routing, and profile evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
)

from .config_profiles import ConfigProfileModel
from .config_profile_schema import infer_capabilities
from .config_resolver import (
    GLOBAL_SOURCE_KEYS,
    config_entry_room_id,
    entry_config_model,
    resolve_profile_config,
)
from .const import (
    CONF_GLOBAL,
    CONF_GLOBAL_DEFAULTS,
    CONF_GLOBAL_SOURCES,
    CONF_CONFIG_MODEL,
    CONF_HUB_ENTRY_ID,
    CONF_NAME,
    CONF_ROOM_ID,
    CONF_PROFILE_ID,
    CONF_PROFILE_CAPABILITIES,
    CONF_PROFILE_NAME,
    CONF_PROFILE_SETTINGS,
    CONF_PROFILE_SELECTIONS,
    CONF_PROFILES,
    CONF_ROOMS,
    CONF_ROOM_OVERRIDES,
    PROFILE_TYPES,
    PROFILE_TYPE_TIME,
    PROFILE_TYPE_SHADING,
    PROFILE_TYPE_BEHAVIOR,
    SIGNAL_HUB_STATE_UPDATED,
)
from .runtime.profile_evaluation import evaluate_time_profile

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .runtime.manager import ControllerManager


@dataclass(frozen=True)
class ProfileEvaluation:
    """Transient shared result for one reusable profile."""

    next_open: datetime | None = None
    next_close: datetime | None = None
    brightness_eligible: bool | None = None
    forecast_eligible: bool | None = None
    weather_eligible: bool | None = None


def merge_config_models(
    base: Mapping[str, Any], incoming: Mapping[str, Any], *, namespace: str
) -> dict[str, Any]:
    """Merge room entries without unsafe profile-name deduplication."""

    merged = ConfigProfileModel(base).data
    other = ConfigProfileModel(incoming).data
    for layer in (CONF_GLOBAL_SOURCES, CONF_GLOBAL_DEFAULTS):
        target = merged[CONF_GLOBAL][layer]
        for key, value in other[CONF_GLOBAL][layer].items():
            target.setdefault(key, deepcopy(value))

    remapped: dict[tuple[str, str], str] = {}
    suffix = namespace.replace("-", "")[:8] or "imported"
    for profile_type in PROFILE_TYPES:
        target_catalog = merged[CONF_PROFILES][profile_type]
        for profile_id, profile in other[CONF_PROFILES][profile_type].items():
            new_id = profile_id
            existing = target_catalog.get(profile_id)
            if existing is not None and existing != profile:
                new_id = f"{profile_id}-{suffix}"
                counter = 2
                while new_id in target_catalog:
                    new_id = f"{profile_id}-{suffix}-{counter}"
                    counter += 1
            if new_id not in target_catalog:
                copied = deepcopy(profile)
                copied[CONF_PROFILE_ID] = new_id
                target_catalog[new_id] = copied
            remapped[(profile_type, profile_id)] = new_id

    for room_id, room in other[CONF_ROOMS].items():
        copied_room = deepcopy(room)
        selections = copied_room.setdefault(CONF_PROFILE_SELECTIONS, {})
        for profile_type, profile_id in tuple(selections.items()):
            selections[profile_type] = remapped.get(
                (profile_type, profile_id), profile_id
            )
        candidate = room_id
        if candidate in merged[CONF_ROOMS] and merged[CONF_ROOMS][candidate] != copied_room:
            candidate = f"{room_id}-{suffix}"
        merged[CONF_ROOMS][candidate] = copied_room
    return merged


class CoverControlHub:
    """Own shared configuration and route global events to room managers."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.owner_entry_id: str | None = None
        self.model = ConfigProfileModel({}).data
        self.managers: dict[str, ControllerManager] = {}
        self.profile_users: dict[tuple[str, str], set[str]] = {}
        self.entity_profile_routes: dict[str, set[tuple[str, str]]] = {}
        self.entity_room_routes: dict[str, set[str]] = {}
        self.profile_evaluations: dict[tuple[str, str], ProfileEvaluation] = {}
        self._shared_listener_unsub = None
        self._shared_entities: set[str] = set()
        self._profile_timer_unsubs: dict[tuple[str, str], Any] = {}
        self._profile_timer_at: dict[tuple[str, str], datetime] = {}

    def prepare_entry(self, entry: ConfigEntry) -> None:
        """Load or merge persisted data before a room manager starts."""

        room_id = config_entry_room_id(entry.data, entry.entry_id)
        hinted_owner = entry.data.get(CONF_HUB_ENTRY_ID)
        if self.owner_entry_id is None:
            owner = (
                self.hass.config_entries.async_get_entry(str(hinted_owner))
                if hinted_owner
                else None
            )
            if owner is not None and isinstance(
                owner.data.get(CONF_CONFIG_MODEL), Mapping
            ):
                owner_room_id = config_entry_room_id(owner.data, owner.entry_id)
                self.owner_entry_id = owner.entry_id
                self.model = ConfigProfileModel(
                    entry_config_model(
                        owner.data, owner.options, room_id=owner_room_id
                    )
                ).data
            else:
                self.owner_entry_id = entry.entry_id
        incoming = entry_config_model(entry.data, entry.options, room_id=room_id)
        if entry.entry_id == self.owner_entry_id:
            self.model = ConfigProfileModel(incoming).data
        elif room_id not in self.model[CONF_ROOMS]:
            self.model = merge_config_models(
                self.model, incoming, namespace=entry.entry_id
            )

    async def async_register(
        self, entry: ConfigEntry, manager: ControllerManager
    ) -> None:
        """Register one room execution manager and persist the canonical model."""

        room_id = manager.room_id
        self.managers[entry.entry_id] = manager
        manager.hub = self
        manager.apply_config_model(self.model, {room_id})
        self._rebuild_dependencies()
        self.refresh_shared_listener()
        self.refresh_profile_evaluations()
        await self.async_persist()

    async def async_persist(self) -> None:
        """Store the hub model once and keep room entries as lightweight references."""

        if self.owner_entry_id is None:
            return
        for entry_id, manager in self.managers.items():
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry is None:
                continue
            if entry_id == self.owner_entry_id:
                data = dict(entry.data)
                data.update(
                    {
                        CONF_HUB_ENTRY_ID: self.owner_entry_id,
                        CONF_CONFIG_MODEL: deepcopy(self.model),
                    }
                )
            else:
                room = self.model[CONF_ROOMS].get(manager.room_id, {})
                data = {
                    CONF_HUB_ENTRY_ID: self.owner_entry_id,
                    CONF_ROOM_ID: manager.room_id,
                    CONF_NAME: room.get(CONF_NAME, entry.title),
                }
            if data != dict(entry.data):
                self.hass.config_entries.async_update_entry(
                    entry, data=data, options={}
                )

    async def async_unregister(self, entry_id: str) -> None:
        self.managers.pop(entry_id, None)
        self._rebuild_dependencies()
        self.refresh_shared_listener()
        self.refresh_profile_evaluations()
        if not self.managers:
            self._clear_shared_listener()
            self._clear_profile_timers()

    @callback
    def apply_model(self, model: Mapping[str, Any], affected_rooms: set[str]) -> None:
        """Apply a canonical edit only to dependent runtime rooms."""

        self.model = ConfigProfileModel(model).data
        self._rebuild_dependencies()
        for manager in self.managers.values():
            manager.apply_config_model(self.model, affected_rooms)
        self.refresh_shared_listener()
        self.refresh_profile_evaluations()

    @callback
    def _rebuild_dependencies(self) -> None:
        users: dict[tuple[str, str], set[str]] = {}
        for room_id, room in self.model.get(CONF_ROOMS, {}).items():
            for profile_type, profile_id in room.get(
                CONF_PROFILE_SELECTIONS, {}
            ).items():
                users.setdefault((profile_type, profile_id), set()).add(room_id)
        self.profile_users = users

        profile_routes: dict[str, set[tuple[str, str]]] = {}
        room_routes: dict[str, set[str]] = {}
        global_sources = self.model.get(CONF_GLOBAL, {}).get(
            CONF_GLOBAL_SOURCES, {}
        )
        for key, entity_id in global_sources.items():
            if key not in GLOBAL_SOURCE_KEYS or not isinstance(entity_id, str):
                continue
            for profile_key, rooms in users.items():
                profile = self.model[CONF_PROFILES][profile_key[0]].get(
                    profile_key[1], {}
                )
                if not self._profile_uses_source(profile_key[0], profile, key):
                    continue
                profile_routes.setdefault(entity_id, set()).add(profile_key)
                room_routes.setdefault(entity_id, set()).update(rooms)
        for manager in self.managers.values():
            for entity_id in manager.shared_entity_routes():
                room_routes.setdefault(entity_id, set()).add(manager.room_id)
        self.entity_profile_routes = profile_routes
        self.entity_room_routes = room_routes

    @staticmethod
    def _profile_uses_source(
        profile_type: str, profile: Mapping[str, Any], source_key: str
    ) -> bool:
        capability_by_source = {
            "workday_sensor": (PROFILE_TYPE_TIME, "workday"),
            "workday_tomorrow_sensor": (PROFILE_TYPE_TIME, "workday"),
            "calendar_entity": (PROFILE_TYPE_TIME, "calendar"),
            "brightness_sensor": (PROFILE_TYPE_TIME, "brightness"),
            "sun_elevation_dynamic_open_sensor": (PROFILE_TYPE_TIME, "sun"),
            "sun_elevation_dynamic_close_sensor": (PROFILE_TYPE_TIME, "sun"),
            "shading_brightness_sensor": (PROFILE_TYPE_SHADING, "brightness"),
            "temperature_sensor_outdoor": (PROFILE_TYPE_SHADING, "temperature"),
            "cold_protection_forecast_sensor": (PROFILE_TYPE_SHADING, "temperature"),
            "shading_forecast_sensor": (PROFILE_TYPE_SHADING, "forecast"),
            "shading_forecast_temp_sensor": (PROFILE_TYPE_SHADING, "forecast"),
            "resident_sensor": (PROFILE_TYPE_BEHAVIOR, "resident"),
        }
        required = capability_by_source.get(source_key)
        if required is None or required[0] != profile_type:
            return False
        capabilities = profile.get(CONF_PROFILE_CAPABILITIES)
        if not isinstance(capabilities, list):
            capabilities = infer_capabilities(
                profile_type, profile.get(CONF_PROFILE_SETTINGS, {})
            )
        return required[1] in capabilities

    @callback
    def refresh_shared_listener(self) -> None:
        """Maintain exactly one listener for all shared entities."""

        desired: set[str] = set()
        for manager in self.managers.values():
            desired.update(manager.shared_entity_routes())
        if desired == self._shared_entities:
            return
        self._clear_shared_listener()
        self._shared_entities = desired
        if desired:
            self._shared_listener_unsub = async_track_state_change_event(
                self.hass, sorted(desired), self._handle_shared_state_event
            )

    @callback
    def _handle_shared_state_event(self, event) -> None:
        entity_id = event.data.get("entity_id")
        for manager in self.managers.values():
            if entity_id in manager.shared_entity_routes():
                manager._handle_shared_state_event(event)
        self.refresh_profile_evaluations()

    @callback
    def _clear_shared_listener(self) -> None:
        if self._shared_listener_unsub is not None:
            self._shared_listener_unsub()
            self._shared_listener_unsub = None
        self._shared_entities.clear()

    @callback
    def refresh_profile_evaluations(self) -> None:
        """Calculate each profile once without room overrides."""

        evaluations: dict[tuple[str, str], ProfileEvaluation] = {}
        for profile_key in self.profile_users:
            if profile_key[0] != PROFILE_TYPE_TIME:
                continue
            config = resolve_profile_config(
                self.model, profile_key[0], profile_key[1]
            )
            next_open, next_close = evaluate_time_profile(self.hass, config)
            evaluations[profile_key] = ProfileEvaluation(
                next_open=next_open,
                next_close=next_close,
            )
        if evaluations != self.profile_evaluations:
            self.profile_evaluations = evaluations
            async_dispatcher_send(self.hass, SIGNAL_HUB_STATE_UPDATED)
        self._reschedule_profile_timers()

    @callback
    def _reschedule_profile_timers(self) -> None:
        desired: dict[tuple[str, str], datetime] = {}
        for profile_key, evaluation in self.profile_evaluations.items():
            if evaluation.next_open is not None:
                desired[(profile_key[1], "open")] = evaluation.next_open
            if evaluation.next_close is not None:
                desired[(profile_key[1], "close")] = evaluation.next_close
        for timer_key in set(self._profile_timer_unsubs) - set(desired):
            self._profile_timer_unsubs.pop(timer_key)()
            self._profile_timer_at.pop(timer_key, None)
        for timer_key, due_at in desired.items():
            if self._profile_timer_at.get(timer_key) == due_at:
                continue
            old = self._profile_timer_unsubs.pop(timer_key, None)
            if old is not None:
                old()

            @callback
            def _handle(_now: datetime, key=timer_key) -> None:
                self._profile_timer_unsubs.pop(key, None)
                self._profile_timer_at.pop(key, None)
                rooms = self.profile_users.get((PROFILE_TYPE_TIME, key[0]), set())
                for manager in self.managers.values():
                    if manager.room_id in rooms:
                        manager.request_evaluate_all(f"profile_{key[1]}")
                self.refresh_profile_evaluations()

            self._profile_timer_unsubs[timer_key] = async_track_point_in_time(
                self.hass, _handle, due_at
            )
            self._profile_timer_at[timer_key] = due_at

    @callback
    def _clear_profile_timers(self) -> None:
        for unsubscribe in self._profile_timer_unsubs.values():
            unsubscribe()
        self._profile_timer_unsubs.clear()
        self._profile_timer_at.clear()

    def room_uses_shared_time_timer(self, room_id: str) -> bool:
        room = self.model.get(CONF_ROOMS, {}).get(room_id, {})
        profile_id = room.get(CONF_PROFILE_SELECTIONS, {}).get(PROFILE_TYPE_TIME)
        overrides = room.get(CONF_ROOM_OVERRIDES, {}).get(PROFILE_TYPE_TIME, {})
        return bool(profile_id and not overrides)

    def profile_name(self, profile_type: str, profile_id: str) -> str:
        profile = self.model.get(CONF_PROFILES, {}).get(profile_type, {}).get(
            profile_id, {}
        )
        return str(profile.get(CONF_PROFILE_NAME, profile_id))

    def diagnostics(self) -> dict[str, Any]:
        return {
            "global_sources": deepcopy(
                self.model.get(CONF_GLOBAL, {}).get(CONF_GLOBAL_SOURCES, {})
            ),
            "profiles": {
                profile_type: {
                    profile_id: {
                        "name": profile.get(CONF_PROFILE_NAME, profile_id),
                        "users": sorted(
                            self.profile_users.get((profile_type, profile_id), ())
                        ),
                    }
                    for profile_id, profile in catalog.items()
                }
                for profile_type, catalog in self.model.get(
                    CONF_PROFILES, {}
                ).items()
            },
            "profile_evaluation": {
                f"{profile_type}:{profile_id}": {
                    "next_open": evaluation.next_open,
                    "next_close": evaluation.next_close,
                }
                for (profile_type, profile_id), evaluation in self.profile_evaluations.items()
            },
        }
