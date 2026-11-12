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

from ..config_resolver import ResolvedRoomConfig, resolve_config_model
from ..config_subentries import model_from_subentries
from ..const import (
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_DOWN,
    CONF_AUTO_SHADING,
    CONF_AUTO_SUN,
    CONF_AUTO_TIME,
    CONF_AUTO_UP,
    CONF_AUTO_VENTILATE,
    CONF_COVERS,
    CONF_CLOSE_MODE,
    CONF_HEAT_PROTECTION_ENABLED,
    CONF_HEAT_PROTECTION_THRESHOLD,
    CONF_GROUP,
    CONF_OPEN_MODE,
    CONF_RESIDENT_STATUS,
    CONF_RESIDENT_SENSOR,
    CONF_ROOMS,
    CONF_ROOM_OVERRIDES,
    CONF_SHADING_MODE,
    DOMAIN,
    SIGNAL_ENTRY_STATE_UPDATED,
)
from .common import (
    _TRIGGER_PRIORITY,
    IDLE_REASON,
    STORAGE_VERSION,
    _unique_covers,
    TRIGGER_FIRE_LATCH_RESET,
)
from .controller import CoverController
from .safety import SAFETY_REASONS
from ..feature_state import FeatureState, feature_configured


def _controls_for_reason(reason: str) -> set[str]:
    """Map the runtime decision reason to diagnostic control names."""

    if reason in {
        "scheduled_open",
        "scheduled_close",
        "scheduled_intermediate_close",
        "scheduled_final_close",
    }:
        return {"time"}
    if reason in {"sun_open", "sun_close"}:
        return {"sun"}
    if reason in {
        "manual_override",
        "window_lockout",
        "no_go_time",
        "summer_period",
    }:
        return {reason}
    if "ventilation" in reason:
        return {"ventilation"}
    if reason == "heat_protection":
        return {"heat_protection"}
    if "shading" in reason:
        return {"shading"}
    if "resident" in reason:
        return {"resident"}
    if "brightness" in reason:
        return {"brightness"}
    if "calendar" in reason:
        return {"calendar"}
    if reason in SAFETY_REASONS:
        return {reason}
    return set()


def _blocking_controls_for_reason(reason: str) -> set[str]:
    if reason in {
        "manual_override",
        "window_lockout",
        "summer_period",
    }:
        return {reason}
    return set()


def _configured_controls(resolved: ResolvedRoomConfig | None) -> set[str]:
    if resolved is None:
        return set()
    return set(resolved.configured_functions)


def _control_state(
    active_reasons: list[str], active_controls: set[str] | None = None
) -> str:
    """Return the stable, translatable state for active runtime reasons."""

    controls = {
        control
        for reason in active_reasons
        for control in _controls_for_reason(reason)
    }
    controls.update(active_controls or ())
    if not controls:
        return IDLE_REASON
    if len(controls) > 1:
        return "multiple"
    return next(iter(controls))

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
        self.room_id = room_id or entry.entry_id
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
            "active_controls": [],
            "configured_controls": [],
            "blocked_by": [],
            "reason": IDLE_REASON,
            "resident_status": "off",
            "resident_entity": None,
            "active_safety": None,
            "fire_latched": False,
            "safety_target": None,
            "window_down_sequences": {},
            "heat_protection_active": False,
        }
        self._shared_listener_unsub = None
        self._shared_entities: set[str] = set()
        self._entity_routes: dict[str, set[str]] = {}
        self._resolved_config: ResolvedRoomConfig | None = None
        self._config_model: dict = {}
        self.group_users: dict[str, set[str]] = {}

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
        self.refresh_schedule_snapshot()

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
                                trigger = max(
                                    sorted(triggers), key=self._trigger_priority
                                )
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

        if CoverController._is_background_reason(reason):
            group_key = (reason, float(position))
            if self._batch_active:
                if group_key in self._batch_group_actions:
                    return
                self._batch_group_actions.add(group_key)
            for controller in self.controllers.values():
                controller._set_background_target(position, reason)
            await asyncio.gather(
                *(
                    controller._apply_effective_target()
                    for controller in self.controllers.values()
                )
            )
            for controller in self.controllers.values():
                controller._refresh_next_events(dt_util.utcnow())
            return

        if (
            "ventilation" in reason
            or reason.startswith("manual_")
            or reason == "frost_alarm"
        ):
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
            if ("shading" in reason or reason == "heat_protection")
            and "end_open" not in reason
            else "open"
        )
        async with self._group_command_lock:
            eligible = [
                controller
                for controller in self.controllers.values()
                if reason in SAFETY_REASONS
                or not controller._manual_blocks_action(action)
            ]
            await asyncio.gather(
                *(
                    controller._set_position_local(position, reason)
                    for controller in eligible
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
        try:
            self._rebuild_entry_snapshot()
        except (TypeError, ValueError):
            return False
        async_dispatcher_send(
            self.hass, SIGNAL_ENTRY_STATE_UPDATED, self.entry.entry_id
        )
        hub = getattr(self, "hub", None)
        if hub is not None:
            hub.refresh_group_evaluations()

    @callback
    def refresh_schedule_snapshot(self) -> bool:
        """Publish changed room schedule data without requiring cover state churn."""

        self._entry_snapshot = getattr(
            self,
            "_entry_snapshot",
            {
                "covers": {},
                "next_open": None,
                "next_close": None,
                "control_state": IDLE_REASON,
                "resident_status": "off",
                "resident_entity": None,
                "active_safety": None,
                "fire_latched": False,
                "safety_target": None,
                "window_down_sequences": {},
                "heat_protection_active": False,
            },
        )
        previous = (
            self._entry_snapshot.get("next_open"),
            self._entry_snapshot.get("next_close"),
            self._entry_snapshot.get("resident_status"),
            self._entry_snapshot.get("resident_entity"),
        )
        try:
            self._rebuild_entry_snapshot()
        except (TypeError, ValueError):
            return False
        current = (
            self._entry_snapshot.get("next_open"),
            self._entry_snapshot.get("next_close"),
            self._entry_snapshot.get("resident_status"),
            self._entry_snapshot.get("resident_entity"),
        )
        if current == previous:
            return False
        async_dispatcher_send(
            self.hass, SIGNAL_ENTRY_STATE_UPDATED, self.entry.entry_id
        )
        return True

    @callback
    def _rebuild_entry_snapshot(self) -> None:
        """Prepare all entry sensor data from one read-only controller pass."""

        covers: dict[str, dict[str, object]] = {}
        open_candidates: list[tuple[datetime, str]] = []
        close_candidates: list[tuple[datetime, str]] = []
        active_reasons: list[str] = []
        active_controls: set[str] = set()
        active_safety: str | None = None
        safety_target: float | None = None
        fire_latched = False
        window_down_sequences: dict[str, dict[str, object]] = {}
        heat_protection_active = False
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
            decision_controls = getattr(controller, "active_decision_controls", None)
            if callable(decision_controls):
                values = decision_controls()
                if isinstance(values, (set, frozenset, list, tuple)):
                    active_controls.update(values)
            safety_snapshot = getattr(controller, "safety_snapshot", None)
            safety = safety_snapshot() if callable(safety_snapshot) else {}
            if not isinstance(safety, dict):
                safety = {}
            sequence_snapshot = getattr(
                controller, "window_down_sequence_snapshot", None
            )
            sequence = sequence_snapshot() if callable(sequence_snapshot) else {}
            if not isinstance(sequence, dict):
                sequence = {}
            heat_snapshot_fn = getattr(controller, "heat_protection_snapshot", None)
            heat_snapshot = heat_snapshot_fn() if callable(heat_snapshot_fn) else {}
            if not isinstance(heat_snapshot, dict):
                heat_snapshot = {}
            target_state_fn = getattr(controller, "target_state_snapshot", None)
            target_state = target_state_fn() if callable(target_state_fn) else {}
            if not isinstance(target_state, dict):
                target_state = {}
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
                **safety,
                "window_down_sequence": sequence,
                "heat_protection": heat_snapshot,
                **target_state,
            }
            if sequence:
                window_down_sequences[cover] = sequence
            heat_protection_active = heat_protection_active or bool(
                heat_snapshot.get("active")
            )
            active_safety = active_safety or safety.get("active_safety")
            safety_target = (
                safety.get("safety_target")
                if safety.get("safety_target") is not None
                else safety_target
            )
            fire_latched = fire_latched or bool(safety.get("fire_latched"))
            if isinstance(next_open, datetime) and next_open >= now:
                open_candidates.append((next_open, cover))
            if isinstance(next_close, datetime) and next_close >= now:
                close_candidates.append((next_close, cover))
            if reason_value != IDLE_REASON and reason_value not in active_reasons:
                active_reasons.append(reason_value)

        active_controls.update(
            control
            for reason in active_reasons
            for control in _controls_for_reason(reason)
        )
        control_state = _control_state(active_reasons, active_controls)
        first_controller = next(iter(self.controllers.values()), None)
        resolved = getattr(self, "_resolved_config", None)
        resolved_get = getattr(resolved, "get", None)
        resident_entity = (
            resolved_get(CONF_RESIDENT_SENSOR)
            if callable(resolved_get)
            else (
                first_controller.config.get(CONF_RESIDENT_SENSOR)
                if first_controller is not None
                else None
            )
        )
        resident_state = self.hass.states.get(resident_entity) if resident_entity else None
        first_status = getattr(first_controller, "_status", {})
        shading_conditions = (
            first_status.get("shading_conditions", {})
            if isinstance(first_status, dict)
            else {}
        )
        self._entry_snapshot = {
            "covers": covers,
            "next_open": min(open_candidates) if open_candidates else None,
            "next_close": min(close_candidates) if close_candidates else None,
            "control_state": control_state,
            "active_controls": sorted(active_controls),
            "configured_controls": sorted(
                _configured_controls(getattr(self, "_resolved_config", None))
            ),
            "blocked_by": sorted(
                {
                    control
                    for reason in active_reasons
                    for control in _blocking_controls_for_reason(reason)
                }
            ),
            "reason": active_reasons[0] if active_reasons else IDLE_REASON,
            "resident_status": (
                "on"
                if resident_state is not None
                and first_controller is not None
                and first_controller._resident_state_is_on(resident_state.state)
                else "off"
            ),
            "resident_entity": resident_entity,
            "active_safety": active_safety,
            "fire_latched": fire_latched,
            "safety_target": safety_target,
            "window_down_sequences": window_down_sequences,
            "heat_protection_active": heat_protection_active,
            "shading_mode": (
                resolved_get(CONF_SHADING_MODE)
                if callable(resolved_get)
                else None
            ),
            "shading_conditions": dict(shading_conditions),
        }

    def entry_snapshot(self) -> dict[str, object]:
        """Return the already prepared entry-level sensor snapshot."""

        return self._entry_snapshot

    def configuration_diagnostics(self) -> dict[str, object]:
        """Return a bounded view of the selected group and important origins."""

        resolved = self._resolved_config
        if resolved is None:
            return {}
        keys = (
            CONF_OPEN_MODE,
            CONF_CLOSE_MODE,
            CONF_SHADING_MODE,
            "shading_position",
            "shading_waitingtime_end",
            "temperature_threshold",
            CONF_HEAT_PROTECTION_ENABLED,
            CONF_HEAT_PROTECTION_THRESHOLD,
            "manual_override_minutes",
        )
        def readable_source(key: str) -> str:
            source = resolved.sources.get(key, "unknown")
            if source.startswith("group:"):
                return f'Group "{source.removeprefix("group:")}"'
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
            CONF_RESIDENT_STATUS,
        )
        return {
            "room_id": resolved.room_id,
            "room_name": resolved.room_name,
            "group": resolved.group,
            "configured_functions": sorted(resolved.configured_functions),
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
            "runtime_toggles": dict(getattr(self, "_runtime_toggles", {})),
        }

    @staticmethod
    def _trigger_priority(trigger: str) -> int:
        return _TRIGGER_PRIORITY.get(trigger, 0)

    @callback
    def request_evaluate_all(self, trigger: str) -> None:
        """Queue every cover in this entry for the same shared cause."""

        for controller in self.controllers.values():
            self._request_evaluate(controller, trigger)

    @callback
    def _handle_shared_state_event(self, event) -> None:
        entity_id = event.data.get("entity_id")
        routed_covers = self._entity_routes.get(entity_id, set())
        routed_controllers = [
            self.controllers[cover]
            for cover in routed_covers
            if cover in self.controllers
        ]
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        old_value = old_state.state if old_state else None
        new_value = new_state.state if new_state else None
        for routed_controller in routed_controllers:
            for trigger in routed_controller._shared_state_triggers(
                entity_id, old_value, new_value
            ):
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

        room_id = getattr(self, "room_id", self.entry.entry_id)
        hub = getattr(self, "hub", None)
        if hub is not None and room_id in hub.model.get(CONF_ROOMS, {}):
            self._config_model = hub.model
            resolved = resolve_config_model(hub.model, room_id)
        else:
            self._config_model = model_from_subentries(
                self.entry.data, self.entry.subentries.values()
            )
            resolved = resolve_config_model(self._config_model, room_id)
        self._resolved_config = resolved
        self._index_group_users()
        return resolved

    @callback
    def apply_config_model(
        self, model: dict, affected_rooms: set[str] | None = None
    ) -> set[str]:
        """Apply a model edit only to rooms affected by the changed dependency."""

        self._config_model = model
        self._index_group_users()
        room_id = getattr(self, "room_id", self.entry.entry_id)
        affected = affected_rooms or {room_id}
        if room_id not in affected:
            return set()
        runtime = getattr(self.entry, "runtime_data", None)
        if runtime is not None:
            runtime.model = model
        resolved = resolve_config_model(model, room_id)
        self._resolved_config = resolved
        for controller in self.controllers.values():
            controller.update_config(resolved)
        self._setup_shared_listener()
        self.refresh_schedule_snapshot()
        return {room_id}

    def _index_group_users(self) -> None:
        """Build the runtime-only group-to-room dependency index."""

        users: dict[str, set[str]] = {}
        for room_id, room in self._config_model.get(CONF_ROOMS, {}).items():
            users.setdefault(str(room.get(CONF_GROUP)), set()).add(room_id)
        self.group_users = users

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
        trigger = self._runtime_toggle_trigger(key)
        for controller in self.controllers.values():
            controller.async_request_evaluate(trigger)

    @callback
    def clear_runtime_toggle(self, key: str) -> None:
        """Clear runtime override so persisted config controls the feature again."""

        if key in self._runtime_toggles:
            self._runtime_toggles.pop(key, None)
            self._setup_shared_listener()
            trigger = self._runtime_toggle_trigger(key)
            for controller in self.controllers.values():
                controller.async_request_evaluate(trigger)

    @staticmethod
    def _runtime_toggle_trigger(key: str) -> str:
        return {
            CONF_AUTO_TIME: "toggle_time",
            CONF_AUTO_UP: "toggle_time",
            CONF_AUTO_DOWN: "toggle_time",
            CONF_AUTO_SUN: "toggle_sun",
            CONF_AUTO_BRIGHTNESS: "toggle_brightness",
            CONF_AUTO_SHADING: "toggle_shading",
            CONF_AUTO_VENTILATE: "toggle_ventilation",
            CONF_RESIDENT_STATUS: "toggle_resident",
        }.get(key, f"toggle_{key}")

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

    def reset_fire_latch(self) -> bool:
        latched = [
            controller
            for controller in self.controllers.values()
            if controller.fire_latched()
        ]
        if not latched or not all(
            controller.can_reset_fire_latch() for controller in latched
        ):
            return False
        for controller in latched:
            controller.reset_fire_latch()
            controller.async_request_evaluate(TRIGGER_FIRE_LATCH_RESET)
        return True

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
