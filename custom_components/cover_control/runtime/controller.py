"""Per-cover runtime facade assembled from focused behavior mixins."""

from __future__ import annotations

from datetime import datetime
from typing import (
    TYPE_CHECKING,
    Awaitable,
    Callable,
)

from homeassistant.core import (
    CALLBACK_TYPE,
    HomeAssistant,
)
from homeassistant.helpers.typing import ConfigType

from ..const import (
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_BRIGHTNESS_ENTITY,
    CONF_AUTO_DOWN,
    CONF_AUTO_DOWN_ENTITY,
    CONF_AUTO_SHADING,
    CONF_AUTO_SHADING_ENTITY,
    CONF_AUTO_SUN,
    CONF_AUTO_SUN_ENTITY,
    CONF_AUTO_UP,
    CONF_AUTO_UP_ENTITY,
    CONF_AUTO_VENTILATE,
    CONF_AUTO_VENTILATE_ENTITY,
)
from .actuator import ActuatorMixin
from .common import _normalize_cover_status
from .evaluation import EvaluationMixin
from .events import EventsMixin
from .schedule import ScheduleMixin
from .shading import ShadingMixin
from .status import StatusMixin

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


class CoverController(
    StatusMixin,
    EventsMixin,
    EvaluationMixin,
    ShadingMixin,
    ScheduleMixin,
    ActuatorMixin,
):
    """Translate blueprint-style parameters into runtime cover control."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        cover: str,
        config: ConfigType,
        persisted_status: object = None,
        persist_callback: Callable[[str, dict], None] | None = None,
        evaluate_callback: Callable[[CoverController, str], None] | None = None,
        group_position_callback: Callable[
            [CoverController, float, str], Awaitable[None]
        ]
        | None = None,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.cover = cover
        self.config = config
        self._persist_callback = persist_callback
        self._evaluate_callback = evaluate_callback
        self._group_position_callback = group_position_callback
        self._status = _normalize_cover_status(persisted_status)
        self._unsubs: list[CALLBACK_TYPE] = []
        self._manual_until: datetime | None = None
        self._manual_active: bool = False
        self._manual_scope_all: bool = False
        self._target: float | None = None
        self._last_position: float | None = None
        self._pre_ventilation_position: float | None = None
        self._last_command_at: datetime | None = None
        self._ignore_service_call_until: datetime | None = None
        self._manual_expire_unsub: CALLBACK_TYPE | None = None
        self._last_command_context_id: str | None = None
        self._shading_forecast_cache: dict[str, object] | None = None
        self._reason: str | None = None
        self._next_open: datetime | None = None
        self._next_close: datetime | None = None
        self._master_entity_id: str | None = None
        self._condition_since: dict[str, datetime] = {}
        self._last_action_dates: dict[str, datetime.date] = {}
        self._cover_unavailable_logged = False
        self._unavailable_dependencies: set[str] = set()
        self._hydrate_persistent_status()
        self._auto_entity_map = {
            CONF_AUTO_UP: CONF_AUTO_UP_ENTITY,
            CONF_AUTO_DOWN: CONF_AUTO_DOWN_ENTITY,
            CONF_AUTO_BRIGHTNESS: CONF_AUTO_BRIGHTNESS_ENTITY,
            CONF_AUTO_SUN: CONF_AUTO_SUN_ENTITY,
            CONF_AUTO_VENTILATE: CONF_AUTO_VENTILATE_ENTITY,
            CONF_AUTO_SHADING: CONF_AUTO_SHADING_ENTITY,
        }
