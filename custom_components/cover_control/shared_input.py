"""Single subscription and snapshot for shared Home Assistant inputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event


@dataclass(frozen=True, slots=True)
class SharedInputSnapshot:
    """Immutable state view produced by latest shared input event."""

    states: dict[str, Any] = field(default_factory=dict)
    changed: frozenset[str] = frozenset()


class SharedInputCoordinator:
    """Subscribe to each shared entity once and retain latest snapshot."""

    def __init__(self, hass: HomeAssistant, on_change: Callable[[Any], None]) -> None:
        self.hass = hass
        self._on_change = on_change
        self.entities: set[str] = set()
        self.snapshot = SharedInputSnapshot()
        self._unsubscribe = None

    @callback
    def update_entities(self, entities: set[str]) -> None:
        if entities == self.entities:
            return
        self.clear()
        self.entities = set(entities)
        states = {entity_id: self.hass.states.get(entity_id) for entity_id in entities}
        self.snapshot = SharedInputSnapshot(states=states)
        if entities:
            self._unsubscribe = async_track_state_change_event(
                self.hass, sorted(entities), self._handle_event
            )

    @callback
    def _handle_event(self, event) -> None:
        entity_id = event.data.get("entity_id")
        states = dict(self.snapshot.states)
        if isinstance(entity_id, str):
            states[entity_id] = event.data.get("new_state")
        self.snapshot = SharedInputSnapshot(
            states=states,
            changed=frozenset({entity_id}) if isinstance(entity_id, str) else frozenset(),
        )
        self._on_change(event)

    @callback
    def clear(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        self.entities.clear()
        self.snapshot = SharedInputSnapshot()
