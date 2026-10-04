"""Config-entry manager and multi-cover coordination."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.core import (
    HomeAssistant,
    callback,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..config_resolver import (
    ResolvedRoomConfig,
    config_entry_room_id,
    entry_config_model,
    resolve_config_model,
    resolve_entry_config,
)
from ..const import (
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_SHADING,
    CONF_AUTO_SUN,
    CONF_AUTO_TIME,
    CONF_AUTO_VENTILATE,
    CONF_COVERS,
    CONF_PROFILE_SELECTIONS,
    CONF_RESIDENT_SENSOR,
    CONF_ROOMS,
    CONF_ROOM_OVERRIDES,
    DOMAIN,
    SIGNAL_ENTRY_STATE_UPDATED,
)
from .common import (
    _TRIGGER_PRIORITY,
    IDLE_REASON,
    STORAGE_VERSION,
    _unique_covers,
)
from .controller import CoverController
from ..feature_state import FeatureState, feature_configured

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from ..hub import CoverControlHub


class ControllerManager:
    """Create and coordinate per-cover controllers."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        hub: CoverControlHub | None = None,
        *,
        room_id: str | None = None,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.hub = hub
        self.room_id = room_id or config_entry_room_id(entry.data, entry.entry_id)
        self.controllers: dict[str, CoverController] = {}
        # Runtime-only feature overrides controlled by integration switch entities.
        # None/absent => follow persisted config flow options.
        self._runtime_toggles: dict[str, bool] = {}
        self._store: Store | None = None
        self._stored_state: dict = {"covers": {}}
        self._pending_evaluations: dict[str, set[str]] = {}
        self._evaluation_task: asyncio.Task | None = None
        self._evaluation_lock = asyncio.Lock()
        self._group_command_lock = asyncio.Lock()
        self._batch_active = False
        self._batch_group_actions: set[tuple[str, float]] = set()
        self._pending_state_controllers: set[str] = set()
        self._entry_snapshot: dict[str, object] = {
            "covers": {},
            "next_open": None,
            "next_close": None,
            "control_state": "idle",
            "resident_status": "off",
            "resident_entity": None,
        }
        self._shared_listener_unsub = None
        self._shared_entities: set[str] = set()
        self._entity_routes: dict[str, set[str]] = {}
        self._resolved_config: ResolvedRoomConfig | None = None
        self._config_model: dict = {}
        self.profile_users: dict[tuple[str, str], set[str]] = {}

    async def async_setup(self) -> None:
        self._store = Store(
            self.hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{self.entry.entry_id}.{self.room_id}.cover_status",
        )
        loaded = await self._store.async_load()
        if isinstance(loaded, dict):
            self._stored_state = loaded
        self._stored_state.setdefault("covers", {})

        data = self._resolve_entry_config()
        self._batch_active = True
        for cover in _unique_covers(data.get(CONF_COVERS, [])):
            controller = CoverController(
                self.hass,
                self.entry,
                cover,
                data,
                self._stored_state["covers"].get(cover),
                self._store_cover_status,
                self._request_evaluate,
                self._async_set_group_position,
                self._controller_state_updated,
            )
            self.controllers[cover] = controller
            await controller.async_setup()
        self._batch_active = False
        self._setup_shared_listener()
        self._flush_state_updates()

    async def async_unload(self) -> None:
        if self._evaluation_task is not None:
            self._evaluation_task.cancel()
            self._evaluation_task = None
        self._pending_evaluations.clear()
        self._clear_shared_listener()
        for controller in self.controllers.values():
            controller.persist_status()
            await controller.async_unload()
        if self._store:
            await self._store.async_save(self._stored_state)
        self.controllers.clear()

    @callback
    def _store_cover_status(self, cover: str, status: dict) -> None:
        self._stored_state.setdefault("covers", {})[cover] = status
        if self._store:
            self._store.async_delay_save(lambda: self._stored_state, 1)

    @callback
    def _request_evaluate(self, controller: CoverController, trigger: str) -> None:
        """Batch room evaluations so shared triggers move covers together."""

        if controller.cover not in self.controllers:
            return
        self._pending_evaluations.setdefault(controller.cover, set()).add(trigger)
        if self._evaluation_task is None or self._evaluation_task.done():
            self._start_evaluation_task()

    @callback
    def _start_evaluation_task(self) -> None:
        """Start evaluation without holding up Home Assistant startup."""

        self._evaluation_task = self.entry.async_create_background_task(
            self.hass,
            self._async_flush_evaluations(),
            "cover control evaluation",
        )

    async def _async_flush_evaluations(self) -> None:
        """Evaluate all pending room covers from the same state snapshot."""

        await asyncio.sleep(0.05)
        try:
            while self._pending_evaluations:
                pending = self._pending_evaluations
                self._pending_evaluations = {}
                async with self._evaluation_lock:
                    self._batch_active = True
                    self._batch_group_actions.clear()
                    context = self._evaluation_context()
                    try:
                        for cover, triggers in pending.items():
                            controller = self.controllers.get(cover)
                            if controller is not None:
                                trigger = max(triggers, key=self._trigger_priority)
                                controller._evaluation_context = context
                                try:
                                    await controller._evaluate(
                                        trigger, frozenset(triggers)
                                    )
                                finally:
                                    controller._evaluation_context = None
                    finally:
                        self._batch_active = False
                        self._batch_group_actions.clear()
                        self._flush_state_updates()
                await asyncio.sleep(0)
        finally:
            self._evaluation_task = None
            if self._pending_evaluations:
                self._start_evaluation_task()

    async def _async_set_group_position(
        self, source: CoverController, position: float, reason: str
    ) -> None:
        """Apply non-ventilation room movements consistently to all covers."""

        if "ventilation" in reason or reason.startswith("manual_"):
            await source._set_position_local(position, reason)
            return

        group_key = (reason, float(position))
        if self._batch_active:
            if group_key in self._batch_group_actions:
                return
            self._batch_group_actions.add(group_key)

        action = (
            "close"
            if "close" in reason or reason == "resident_asleep"
            else "shading"
            if "shading" in reason and "end_open" not in reason
            else "open"
        )
        now = dt_util.utcnow()
        async with self._group_command_lock:
            eligible = [
                controller
                for controller in self.controllers.values()
                if not controller._manual_blocks_action(action)
            ]
            independent = [
                controller
                for controller in eligible
                if controller is not source
                and controller._ventilation_requires_independent_control(now)
            ]
            for controller in independent:
                controller._record_group_background(reason)
            recipients = [
                controller for controller in eligible if controller not in independent
            ]
            await asyncio.gather(
                *(
                    controller._set_position_local(position, reason)
                    for controller in recipients
                )
            )

    @callback
    def _controller_state_updated(self, controller: CoverController) -> None:
        """Defer repeated controller publications until the batch is complete."""

        if controller.cover not in self.controllers:
            return
        self._pending_state_controllers.add(controller.cover)
        if not self._batch_active:
            self._flush_state_updates()

    @callback
    def _flush_state_updates(self) -> None:
        if not self._pending_state_controllers:
            return
        changed = tuple(self._pending_state_controllers)
        self._pending_state_controllers.clear()
        for cover in changed:
            controller = self.controllers.get(cover)
            if controller is not None:
                controller._dispatch_state()
        self._rebuild_entry_snapshot()
        async_dispatcher_send(
            self.hass, SIGNAL_ENTRY_STATE_UPDATED, self.entry.entry_id
        )
        hub = getattr(self, "hub", None)
        if hub is not None:
            hub.refresh_profile_evaluations()

    @callback
    def _rebuild_entry_snapshot(self) -> None:
        """Prepare all entry sensor data from one read-only controller pass."""

        covers: dict[str, dict[str, object]] = {}
        open_candidates: list[tuple[datetime, str]] = []
        close_candidates: list[tuple[datetime, str]] = []
        active_reasons: list[str] = []
        now = dt_util.utcnow()
        for cover, controller in self.controllers.items():
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
            reason_value = reason or IDLE_REASON
            covers[cover] = {
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
            if isinstance(next_open, datetime) and next_open >= now:
                open_candidates.append((next_open, cover))
            if isinstance(next_close, datetime) and next_close >= now:
                close_candidates.append((next_close, cover))
            if reason_value != IDLE_REASON and reason_value not in active_reasons:
                active_reasons.append(reason_value)

        control_state = (
            IDLE_REASON
            if not active_reasons
            else active_reasons[0]
            if len(active_reasons) == 1
            else "multiple"
        )
        first_controller = next(iter(self.controllers.values()), None)
        resident_entity = (
            first_controller.config.get(CONF_RESIDENT_SENSOR)
            if first_controller is not None
            else None
        )
        resident_state = self.hass.states.get(resident_entity) if resident_entity else None
        self._entry_snapshot = {
            "covers": covers,
            "next_open": min(open_candidates) if open_candidates else None,
            "next_close": min(close_candidates) if close_candidates else None,
            "control_state": control_state,
            "resident_status": (
                "on"
                if resident_state is not None
                and first_controller._resident_state_is_on(resident_state.state)
                else "off"
            ),
            "resident_entity": resident_entity,
        }

    def entry_snapshot(self) -> dict[str, object]:
        """Return the already prepared entry-level sensor snapshot."""

        return self._entry_snapshot

    def configuration_diagnostics(self) -> dict[str, object]:
        """Return a bounded view of selected profiles and important origins."""

        resolved = self._resolved_config
        if resolved is None:
            return {}
        keys = (
            "shading_position",
            "shading_waitingtime_start",
            "shading_waitingtime_end",
            "temperature_threshold",
            "manual_override_minutes",
        )
        def readable_source(key: str) -> str:
            source = resolved.sources.get(key, "unknown")
            if source.startswith("profile:"):
                profile_id = source.removeprefix("profile:")
                name = next(
                    (
                        resolved.profile_names.get(kind, profile_id)
                        for kind, selected in resolved.selected_profiles.items()
                        if selected == profile_id
                    ),
                    profile_id,
                )
                return f'Profile "{name}"'
            return {
                "system_default": "Default",
                "global_default": "Global default",
                "room_setting": "Room setting",
                "room_override": "Room override",
                "global_source": "Global source",
                "room_source_override": "Room source override",
            }.get(source, source)

        room = getattr(self, "_config_model", {}).get(CONF_ROOMS, {}).get(
            resolved.room_id, {}
        )
        runtime_toggles = getattr(self, "_runtime_toggles", {})
        toggle_keys = (
            CONF_AUTO_TIME,
            CONF_AUTO_VENTILATE,
            CONF_AUTO_BRIGHTNESS,
            CONF_AUTO_SUN,
            CONF_AUTO_SHADING,
        )
        return {
            "room_id": resolved.room_id,
            "room_name": resolved.room_name,
            "profiles": dict(resolved.profile_names),
            "resolved": {
                key: {
                    "value": resolved.get(key),
                    "source": resolved.sources.get(key),
                    "source_name": readable_source(key),
                }
                for key in keys
                if key in resolved
            },
            "room_overrides": dict(room.get(CONF_ROOM_OVERRIDES, {})),
            "feature_switches": {
                key: runtime_toggles.get(key, bool(resolved.get(key)))
                for key in toggle_keys
            },
        }

    def _evaluation_context(self) -> dict[str, object]:
        """Capture entry-wide states once for a complete evaluation batch."""

        hub = getattr(self, "hub", None)
        if hub is not None:
            states = dict(hub.shared_input_coordinator.snapshot.states)
        else:
            states = {
                entity_id: self.hass.states.get(entity_id)
                for entity_id in self._shared_entities
            }
        return {
            "now": dt_util.utcnow(),
            "states": states,
        }

    @staticmethod
    def _trigger_priority(trigger: str) -> int:
        if trigger.startswith(("condition_timer:", "calendar_boundary:")):
            return 1
        return _TRIGGER_PRIORITY.get(trigger, 0)

    @callback
    def request_evaluate_all(self, trigger: str) -> None:
        """Queue every cover in this entry for the same shared cause."""

        for controller in self.controllers.values():
            self._request_evaluate(controller, trigger)

    @callback
    def _handle_shared_state_event(self, event) -> None:
        entity_id = event.data.get("entity_id")
        trigger = "sun" if entity_id == "sun.sun" else "state"
        routed_covers = self._entity_routes.get(entity_id, set())
        routed_controllers = [
            self.controllers[cover]
            for cover in routed_covers
            if cover in self.controllers
        ]
        controller = routed_controllers[0] if routed_controllers else None
        if controller is not None and entity_id == controller.config.get(CONF_RESIDENT_SENSOR):
            old_state = event.data.get("old_state")
            new_state = event.data.get("new_state")
            old_value = old_state.state if old_state else None
            new_value = new_state.state if new_state else None
            if controller._resident_state_is_on(
                old_value
            ) and controller._resident_state_is_off(new_value):
                trigger = "resident_woke"
            elif controller._resident_state_is_off(
                old_value
            ) and controller._resident_state_is_on(new_value):
                trigger = "resident_asleep"
        for routed_controller in routed_controllers:
            self._request_evaluate(routed_controller, trigger)

    @callback
    def _setup_shared_listener(self) -> None:
        desired = self.shared_entity_routes()
        hub = getattr(self, "hub", None)
        if hub is not None:
            self._clear_shared_listener(clear_routes=False)
            hub.refresh_shared_listener()
            return
        if desired == self._shared_entities:
            return
        self._clear_shared_listener(clear_routes=False)
        self._shared_entities = desired
        if self._shared_entities:
            self._shared_listener_unsub = async_track_state_change_event(
                self.hass,
                sorted(self._shared_entities),
                self._handle_shared_state_event,
            )

    @callback
    def shared_entity_routes(self) -> set[str]:
        """Return shared entity IDs while retaining cover-level routing."""

        routes: dict[str, set[str]] = {}
        for cover, controller in self.controllers.items():
            for entity_id in controller._shared_decision_entities():
                routes.setdefault(entity_id, set()).add(cover)
        self._entity_routes = routes
        return set(routes)

    @callback
    def _clear_shared_listener(self, *, clear_routes: bool = True) -> None:
        if self._shared_listener_unsub is not None:
            self._shared_listener_unsub()
            self._shared_listener_unsub = None
        self._shared_entities.clear()
        if clear_routes:
            self._entity_routes.clear()

    @callback
    def async_update_options(self) -> None:
        new_data = self._resolve_entry_config()
        for controller in self.controllers.values():
            controller.update_config(new_data)
        self._setup_shared_listener()

    def _resolve_entry_config(self) -> ResolvedRoomConfig:
        """Build the entry model and expose only its resolved room to runtime."""

        room_id = getattr(
            self,
            "room_id",
            config_entry_room_id(self.entry.data, self.entry.entry_id),
        )
        hub = getattr(self, "hub", None)
        if hub is not None and room_id in hub.model.get(CONF_ROOMS, {}):
            self._config_model = hub.model
            resolved = resolve_config_model(hub.model, room_id)
        else:
            self._config_model = entry_config_model(
                self.entry.data, self.entry.options, room_id=room_id
            )
            resolved = resolve_entry_config(
                self.entry.data, self.entry.options, room_id=room_id
            )
        self._resolved_config = resolved
        self._index_profile_users()
        return resolved

    @callback
    def apply_config_model(
        self, model: dict, affected_rooms: set[str] | None = None
    ) -> set[str]:
        """Apply a model edit only to rooms affected by the changed dependency."""

        self._config_model = model
        self._index_profile_users()
        room_id = getattr(
            self,
            "room_id",
            config_entry_room_id(self.entry.data, self.entry.entry_id),
        )
        affected = affected_rooms or {room_id}
        if room_id not in affected:
            return set()
        resolved = resolve_config_model(model, room_id)
        self._resolved_config = resolved
        for controller in self.controllers.values():
            controller.update_config(resolved)
        self._setup_shared_listener()
        return {room_id}

    def _index_profile_users(self) -> None:
        """Build the runtime-only profile-to-room dependency index."""

        users: dict[tuple[str, str], set[str]] = {}
        for room_id, room in self._config_model.get(CONF_ROOMS, {}).items():
            for profile_type, profile_id in room.get(
                CONF_PROFILE_SELECTIONS, {}
            ).items():
                users.setdefault((profile_type, profile_id), set()).add(room_id)
        self.profile_users = users

    def set_manual_override(self, cover: str, minutes: int) -> bool:
        controller = self.controllers.get(cover)
        if not controller:
            return False
        controller.set_manual_override(minutes)
        return True

    @callback
    def get_runtime_toggle(self, key: str) -> bool | None:
        """Return runtime override for a feature toggle, if present."""

        return self._runtime_toggles.get(key)

    def feature_state(self, key: str, *, eligible: bool) -> FeatureState:
        """Expose three independent function lifecycle dimensions."""

        configured = feature_configured(self._config_model, self.room_id, key)
        persisted = bool((self._resolved_config or {}).get(key, False))
        enabled = self._runtime_toggles.get(key, persisted)
        return FeatureState(
            configured=configured,
            enabled=bool(enabled),
            eligible=bool(eligible),
        )

    @callback
    def set_runtime_toggle(self, key: str, enabled: bool) -> None:
        """Set runtime-only feature toggle and re-evaluate all controllers."""

        self._runtime_toggles[key] = bool(enabled)
        self._setup_shared_listener()
        for controller in self.controllers.values():
            controller.async_request_evaluate("runtime_toggle")

    @callback
    def clear_runtime_toggle(self, key: str) -> None:
        """Clear runtime override so persisted config controls the feature again."""

        if key in self._runtime_toggles:
            self._runtime_toggles.pop(key, None)
            self._setup_shared_listener()
            for controller in self.controllers.values():
                controller.async_request_evaluate("runtime_toggle")

    def activate_shading(self, cover: str, minutes: int | None) -> bool:
        controller = self.controllers.get(cover)
        if not controller:
            return False
        controller.activate_shading(minutes)
        return True

    def clear_manual_override(self, cover: str) -> bool:
        controller = self.controllers.get(cover)
        if not controller:
            return False
        controller.clear_manual_override()
        return True

    def clear_all_manual_overrides(self) -> None:
        """Clear manual override state for every cover in this entry."""

        for controller in self.controllers.values():
            controller.clear_manual_override()

    async def recalibrate_cover(self, cover: str, full_open: float | None) -> bool:
        controller = self.controllers.get(cover)
        if not controller:
            return False
        await controller.recalibrate(full_open)
        return True

    async def recalibrate_all(self, full_open: float | None = None) -> None:
        """Recalibrate every cover in this entry sequentially."""

        for controller in self.controllers.values():
            await controller.recalibrate(full_open)

    async def force_action(self, cover: str, action: str) -> bool:
        controller = self.controllers.get(cover)
        if not controller:
            return False

        if action in {"open", "close"}:
            await controller.force_move(action)
            return True
        if action in {"ventilate_start", "ventilate_stop"}:
            await controller.force_ventilation(
                "start" if action == "ventilate_start" else "stop"
            )
            return True
        if action in {"shading_activate", "shading_deactivate"}:
            await controller.force_shading(
                "activate" if action == "shading_activate" else "deactivate"
            )
            return True

        return False

    def state_snapshot(
        self,
        cover: str,
    ) -> (
        tuple[
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
        ]
        | None
    ):
        controller = self.controllers.get(cover)
        if not controller:
            return (
                None,
                IDLE_REASON,
                None,
                False,
                None,
                None,
                None,
                False,
                False,
                False,
            )
        return controller.state_snapshot()
