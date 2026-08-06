"""Config-entry manager and multi-cover coordination."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.core import (
    HomeAssistant,
    callback,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..const import (
    CONF_COVERS,
    DEFAULT_AUTOMATION_FLAGS,
    DEFAULT_BEHAVIOR_SETTINGS,
    DEFAULT_CONTACT_SETTINGS,
    DEFAULT_MANUAL_OVERRIDE_FLAGS,
    DEFAULT_POSITION_SETTINGS,
    DEFAULT_SHADING_TIMING_SETTINGS,
    DEFAULT_TIME_SETTINGS,
    DOMAIN,
)
from .common import (
    _TRIGGER_PRIORITY,
    IDLE_REASON,
    STORAGE_VERSION,
    _unique_covers,
)
from .controller import CoverController

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


class ControllerManager:
    """Create and coordinate per-cover controllers."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.controllers: dict[str, CoverController] = {}
        # Runtime-only feature overrides controlled by integration switch entities.
        # None/absent => follow persisted config flow options.
        self._runtime_toggles: dict[str, bool] = {}
        self._store: Store | None = None
        self._stored_state: dict = {"covers": {}}
        self._pending_evaluations: dict[str, str] = {}
        self._evaluation_task: asyncio.Task | None = None
        self._evaluation_lock = asyncio.Lock()
        self._group_command_lock = asyncio.Lock()

    async def async_setup(self) -> None:
        self._store = Store(
            self.hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{self.entry.entry_id}.cover_status",
        )
        loaded = await self._store.async_load()
        if isinstance(loaded, dict):
            self._stored_state = loaded
        self._stored_state.setdefault("covers", {})

        data = {
            **DEFAULT_POSITION_SETTINGS,
            **DEFAULT_TIME_SETTINGS,
            **DEFAULT_AUTOMATION_FLAGS,
            **DEFAULT_MANUAL_OVERRIDE_FLAGS,
            **DEFAULT_CONTACT_SETTINGS,
            **DEFAULT_BEHAVIOR_SETTINGS,
            **DEFAULT_SHADING_TIMING_SETTINGS,
            **self.entry.data,
            **self.entry.options,
        }
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
            )
            self.controllers[cover] = controller
            await controller.async_setup()

    async def async_unload(self) -> None:
        if self._evaluation_task is not None:
            self._evaluation_task.cancel()
            self._evaluation_task = None
        self._pending_evaluations.clear()
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
        previous_trigger = self._pending_evaluations.get(controller.cover)
        if previous_trigger is None or _TRIGGER_PRIORITY.get(
            trigger, 0
        ) >= _TRIGGER_PRIORITY.get(previous_trigger, 0):
            self._pending_evaluations[controller.cover] = trigger
        if self._evaluation_task is None or self._evaluation_task.done():
            self._evaluation_task = self.hass.async_create_task(
                self._async_flush_evaluations()
            )

    async def _async_flush_evaluations(self) -> None:
        """Evaluate all pending room covers from the same state snapshot."""

        await asyncio.sleep(0.05)
        try:
            while self._pending_evaluations:
                pending = self._pending_evaluations
                self._pending_evaluations = {}
                async with self._evaluation_lock:
                    for cover, trigger in pending.items():
                        controller = self.controllers.get(cover)
                        if controller is not None:
                            await controller._evaluate(trigger)
                await asyncio.sleep(0)
        finally:
            self._evaluation_task = None
            if self._pending_evaluations:
                self._evaluation_task = self.hass.async_create_task(
                    self._async_flush_evaluations()
                )

    async def _async_set_group_position(
        self, source: CoverController, position: float, reason: str
    ) -> None:
        """Apply non-ventilation room movements consistently to all covers."""

        if "ventilation" in reason or reason.startswith("manual_"):
            await source._set_position_local(position, reason)
            return

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
    def async_update_options(self) -> None:
        new_data = {
            **DEFAULT_POSITION_SETTINGS,
            **DEFAULT_TIME_SETTINGS,
            **DEFAULT_AUTOMATION_FLAGS,
            **DEFAULT_MANUAL_OVERRIDE_FLAGS,
            **DEFAULT_CONTACT_SETTINGS,
            **DEFAULT_BEHAVIOR_SETTINGS,
            **DEFAULT_SHADING_TIMING_SETTINGS,
            **self.entry.data,
            **self.entry.options,
        }
        for controller in self.controllers.values():
            controller.update_config(new_data)

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

    @callback
    def set_runtime_toggle(self, key: str, enabled: bool) -> None:
        """Set runtime-only feature toggle and re-evaluate all controllers."""

        self._runtime_toggles[key] = bool(enabled)
        for controller in self.controllers.values():
            controller.async_request_evaluate("runtime_toggle")

    @callback
    def clear_runtime_toggle(self, key: str) -> None:
        """Clear runtime override so persisted config controls the feature again."""

        if key in self._runtime_toggles:
            self._runtime_toggles.pop(key, None)
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
