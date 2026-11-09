"""Integration-wide configuration, dependency routing, and group evaluation."""
from __future__ import annotations
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_point_in_time
from .config_groups import ConfigGroupModel
from .config_resolver import GLOBAL_SOURCE_KEYS, resolve_room_config, system_defaults
from .const import (
    CONF_CLOSE_MODE, CONF_GLOBAL, CONF_GLOBAL_DEFAULTS, CONF_GLOBAL_SOURCES, CONF_GROUP, CONF_GROUPS,
    CONF_OPEN_MODE,
    CONF_ROOMS, DEFAULT_GROUP, GROUPS, SIGNAL_HUB_STATE_UPDATED,
)
from .runtime.group_evaluation import evaluate_time_group
from .runtime.common import scheduled_trigger
from .shared_input import SharedInputCoordinator

if TYPE_CHECKING:
    from .runtime.manager import ControllerManager

@dataclass(frozen=True)
class GroupEvaluation:
    """Transient shared result for one fixed group."""
    next_open: datetime | None = None
    next_close: datetime | None = None

class CoverControlHub:
    """Own shared configuration and route global events to room managers."""
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.model = ConfigGroupModel({}).data
        self.managers: dict[str, ControllerManager] = {}
        self.group_users: dict[str, set[str]] = {group: set() for group in GROUPS}
        self.entity_room_routes: dict[str, set[str]] = {}
        self.group_evaluations: dict[str, GroupEvaluation] = {}
        self._shared_entities: set[str] = set()
        self.shared_input_coordinator = SharedInputCoordinator(hass, self._handle_shared_state_event)
        self._group_timer_unsubs: dict[tuple[str, str], Any] = {}
        self._group_timer_at: dict[tuple[str, str], datetime] = {}

    @callback
    def set_parent_model(self, model: Mapping[str, Any]) -> None:
        self.model = ConfigGroupModel(model).data
        self._rebuild_dependencies()

    async def async_register_room(self, manager: ControllerManager) -> None:
        self.managers[manager.room_id] = manager
        manager.hub = self
        manager.apply_config_model(self.model, {manager.room_id})
        self._rebuild_dependencies()
        self.refresh_shared_listener()
        self.refresh_group_evaluations()

    async def async_unregister_room(self, room_id: str) -> None:
        self.managers.pop(room_id, None)
        self._rebuild_dependencies()
        self.refresh_shared_listener()
        self.refresh_group_evaluations()

    async def async_unload_parent(self) -> None:
        self.managers.clear()
        self._clear_shared_listener()
        self._clear_group_timers()

    @callback
    def apply_model(self, model: Mapping[str, Any], affected_rooms: set[str]) -> None:
        self.model = ConfigGroupModel(model).data
        self._rebuild_dependencies()
        for manager in self.managers.values():
            manager.apply_config_model(self.model, affected_rooms)
        self.refresh_shared_listener()
        affected_groups = {
            self.model[CONF_ROOMS][room_id].get(CONF_GROUP, DEFAULT_GROUP)
            for room_id in affected_rooms if room_id in self.model[CONF_ROOMS]
        }
        self.refresh_group_evaluations(affected_groups)

    @callback
    def _rebuild_dependencies(self) -> None:
        self.group_users = ConfigGroupModel(self.model).group_users
        routes: dict[str, set[str]] = {}
        for key, entity_id in self.model.get(CONF_GLOBAL, {}).get(CONF_GLOBAL_SOURCES, {}).items():
            if key in GLOBAL_SOURCE_KEYS and isinstance(entity_id, str):
                routes.setdefault(entity_id, set()).update(self.model.get(CONF_ROOMS, {}))
        for manager in self.managers.values():
            for entity_id in manager.shared_entity_routes():
                routes.setdefault(entity_id, set()).add(manager.room_id)
        self.entity_room_routes = routes

    @callback
    def refresh_shared_listener(self) -> None:
        desired = {entity for manager in self.managers.values() for entity in manager.shared_entity_routes()}
        if desired != self._shared_entities:
            self._shared_entities = desired
            self.shared_input_coordinator.update_entities(desired)

    @callback
    def _handle_shared_state_event(self, event) -> None:
        affected_rooms = self.entity_room_routes.get(event.data.get("entity_id"), set())
        affected_groups: set[str] = set()
        for room_id in affected_rooms:
            manager = self.managers.get(room_id)
            if manager is not None:
                manager._handle_shared_state_event(event)
                manager.refresh_schedule_snapshot()
            room = self.model.get(CONF_ROOMS, {}).get(room_id, {})
            affected_groups.add(str(room.get(CONF_GROUP, DEFAULT_GROUP)))
        self.refresh_group_evaluations(affected_groups)

    @callback
    def _clear_shared_listener(self) -> None:
        self.shared_input_coordinator.clear()
        self._shared_entities.clear()

    @callback
    def refresh_group_evaluations(self, groups: set[str] | None = None) -> None:
        candidates = set(self.group_users) if groups is None else groups
        evaluations = {} if groups is None else dict(self.group_evaluations)
        global_config = self.model.get(CONF_GLOBAL, {})
        for group in candidates:
            if group not in GROUPS or not self.group_users.get(group):
                evaluations.pop(group, None)
                continue
            config = resolve_room_config(
                system_defaults(),
                global_config.get(CONF_GLOBAL_SOURCES, {}),
                global_config.get(CONF_GLOBAL_DEFAULTS, {}),
                group,
                self.model.get(CONF_GROUPS, {}).get(group, {}),
                {}, {}, room_id="group", room_name=group,
            )
            next_open, next_close = evaluate_time_group(
                self.hass,
                config,
                capabilities={"time", "sun", "brightness", "opening", "closing"},
            )
            evaluations[group] = GroupEvaluation(next_open, next_close)
        if evaluations != self.group_evaluations:
            self.group_evaluations = evaluations
            async_dispatcher_send(self.hass, SIGNAL_HUB_STATE_UPDATED)
            for group in candidates:
                for room_id in self.group_users.get(group, set()):
                    manager = self.managers.get(room_id)
                    if manager is not None:
                        manager.refresh_schedule_snapshot()
        self._reschedule_group_timers()

    @callback
    def _reschedule_group_timers(self) -> None:
        desired = {
            (group, action): due
            for group, evaluation in self.group_evaluations.items()
            for action, due in (("open", evaluation.next_open), ("close", evaluation.next_close))
            if due is not None
        }
        for key in set(self._group_timer_unsubs) - set(desired):
            self._group_timer_unsubs.pop(key)()
            self._group_timer_at.pop(key, None)
        for key, due_at in desired.items():
            if self._group_timer_at.get(key) == due_at:
                continue
            old = self._group_timer_unsubs.pop(key, None)
            if old is not None:
                old()
            @callback
            def _handle(_now: datetime, timer_key=key) -> None:
                self._group_timer_unsubs.pop(timer_key, None)
                self._group_timer_at.pop(timer_key, None)
                for room_id in self.group_users.get(timer_key[0], set()):
                    manager = self.managers.get(room_id)
                    if manager is not None:
                        group_config = self.model.get(CONF_GROUPS, {}).get(
                            timer_key[0], {}
                        )
                        mode_key = (
                            CONF_OPEN_MODE
                            if timer_key[1] == "open"
                            else CONF_CLOSE_MODE
                        )
                        manager.request_evaluate_all(
                            scheduled_trigger(
                                timer_key[1], str(group_config.get(mode_key, "time"))
                            )
                        )
                self.refresh_group_evaluations({timer_key[0]})
            self._group_timer_unsubs[key] = async_track_point_in_time(self.hass, _handle, due_at)
            self._group_timer_at[key] = due_at

    @callback
    def _clear_group_timers(self) -> None:
        for unsubscribe in self._group_timer_unsubs.values():
            unsubscribe()
        self._group_timer_unsubs.clear()
        self._group_timer_at.clear()

    def room_uses_shared_time_timer(self, room_id: str) -> bool:
        return room_id in self.model.get(CONF_ROOMS, {})

    def diagnostics(self) -> dict[str, Any]:
        return {
            "global_sources": deepcopy(self.model.get(CONF_GLOBAL, {}).get(CONF_GLOBAL_SOURCES, {})),
            "groups": {
                group: {"users": sorted(self.group_users.get(group, ())) }
                for group in GROUPS
            },
            "group_evaluation": {
                group: {"next_open": evaluation.next_open, "next_close": evaluation.next_close}
                for group, evaluation in self.group_evaluations.items()
            },
        }
