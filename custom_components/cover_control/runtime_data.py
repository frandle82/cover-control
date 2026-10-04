"""Typed runtime owned by the single parent ConfigEntry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeAlias

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .hub import CoverControlHub
    from .runtime.manager import ControllerManager
    from .shared_input import SharedInputCoordinator
    from .recovery import RecoveryManager


@dataclass(slots=True)
class CoverControlRuntime:
    """All runtime services and room managers for one parent entry."""

    hub: CoverControlHub
    model: dict[str, Any]
    room_managers: dict[str, ControllerManager] = field(default_factory=dict)
    recovery_manager: RecoveryManager | None = None

    @property
    def shared_input_coordinator(self) -> SharedInputCoordinator:
        return self.hub.shared_input_coordinator

    @property
    def dependency_index(self) -> CoverControlHub:
        """Expose hub dependency routes through typed parent runtime."""

        return self.hub

    @property
    def profile_evaluators(self) -> dict:
        """Return shared profile evaluation registry."""

        return self.hub.profile_evaluations

    @property
    def evaluation_scheduler(self) -> CoverControlHub:
        """Expose deduplicated profile timer scheduler."""

        return self.hub

    def manager(self, room_subentry_id: str) -> ControllerManager | None:
        """Return manager belonging to one room subentry."""

        return self.room_managers.get(room_subentry_id)


if TYPE_CHECKING:
    CoverControlConfigEntry: TypeAlias = ConfigEntry[CoverControlRuntime]
else:
    CoverControlConfigEntry: TypeAlias = Any
