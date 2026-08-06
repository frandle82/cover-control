"""Cover controller behavior split from the public controller facade."""

from __future__ import annotations

from datetime import datetime

from homeassistant.util import dt as dt_util

from ..const import (
    CONF_CLOSE_POSITION,
    CONF_OPEN_POSITION,
    DEFAULT_CLOSE_POSITION,
    DEFAULT_OPEN_POSITION,
)
from .common import (
    _coerce_float,
    _ts_now,
)


class StatusMixin:
    def _hydrate_persistent_status(self) -> None:
        target = _coerce_float(self._status.get("target"))
        self._target = target
        reason = self._status.get("reason")
        self._reason = reason if isinstance(reason, str) and reason else None

        ventilation = self._status.get("ventilation", {})
        if isinstance(ventilation, dict):
            self._pre_ventilation_position = _coerce_float(
                ventilation.get("restore_position")
            )

        manual = self._status.get("manual", {})
        if isinstance(manual, dict):
            until_raw = manual.get("until")
            until = dt_util.parse_datetime(until_raw) if until_raw else None
            if until:
                until = dt_util.as_utc(until)
            self._manual_until = until
            self._manual_active = bool(
                manual.get("active") and (until is None or until > dt_util.utcnow())
            )
            self._manual_scope_all = bool(manual.get("scope_all"))
            if not self._manual_active:
                self._manual_until = None
                self._manual_scope_all = False

        dates = self._status.get("last_action_dates", {})
        if isinstance(dates, dict):
            for action, date_value in dates.items():
                try:
                    self._last_action_dates[str(action)] = datetime.fromisoformat(
                        str(date_value)
                    ).date()
                except (TypeError, ValueError):
                    continue

    def persist_status(self) -> None:
        self._sync_runtime_status()
        if self._persist_callback:
            self._persist_callback(self.cover, self._status)

    def _sync_runtime_status(self) -> None:
        self._status["reason"] = self._reason
        self._status["target"] = self._target
        self._status["last_action_dates"] = {
            action: date_value.isoformat()
            for action, date_value in self._last_action_dates.items()
        }
        manual = self._status.setdefault("manual", {})
        manual["active"] = self._manual_active
        manual["scope_all"] = self._manual_scope_all
        manual["until"] = self._manual_until.isoformat() if self._manual_until else None
        if self._manual_active and not manual.get("ts"):
            manual["ts"] = _ts_now()

        ventilation = self._status.setdefault("ventilation", {})
        ventilation["restore_position"] = self._pre_ventilation_position

    def _set_status_bucket(
        self, bucket: str, active: bool, ts: int | None = None
    ) -> None:
        section = self._status.setdefault(bucket, {})
        section["active"] = active
        section["ts"] = ts if ts is not None else _ts_now()

    def _status_active(self, bucket: str) -> bool:
        section = self._status.get(bucket, {})
        return isinstance(section, dict) and bool(section.get("active"))

    def _ventilation_status_active(self) -> bool:
        section = self._status.get("ventilation", {})
        return isinstance(section, dict) and bool(
            section.get("partial") or section.get("full")
        )

    def _shading_status(self) -> dict:
        section = self._status.setdefault("shading", {})
        if not isinstance(section, dict):
            section = {}
            self._status["shading"] = section
        section.setdefault("active", False)
        section.setdefault("start_pending", 0)
        section.setdefault("end_pending", 0)
        section.setdefault("ts", 0)
        return section

    def _set_shading_pending(
        self, kind: str, due_at: datetime | None, active: bool | None = None
    ) -> None:
        section = self._shading_status()
        key = "start_pending" if kind == "start" else "end_pending"
        section[key] = int(due_at.timestamp()) if due_at else 0
        section["ts"] = _ts_now()
        if active is not None:
            section["active"] = active
        self.persist_status()

    def _shading_pending_due(self, kind: str, now: datetime) -> bool:
        section = self._shading_status()
        key = "start_pending" if kind == "start" else "end_pending"
        due_ts = _coerce_float(section.get(key)) or 0
        return bool(due_ts and now.timestamp() >= due_ts)

    def _shading_pending_active(self, kind: str) -> bool:
        section = self._shading_status()
        key = "start_pending" if kind == "start" else "end_pending"
        return bool((_coerce_float(section.get(key)) or 0) > 0)

    def _clear_shading_pending(
        self, kind: str | None = None, persist: bool = True
    ) -> None:
        section = self._shading_status()
        if kind in (None, "start"):
            section["start_pending"] = 0
        if kind in (None, "end"):
            section["end_pending"] = 0
        section["ts"] = _ts_now()
        if persist:
            self.persist_status()

    def _set_ventilation_status(
        self, partial: bool = False, full: bool = False, ts: int | None = None
    ) -> None:
        section = self._status.setdefault("ventilation", {})
        section["partial"] = partial
        section["full"] = full
        section["restore_position"] = self._pre_ventilation_position
        section.setdefault(
            "background", {"open": False, "close": False, "shading": False}
        )
        section["ts"] = ts if ts is not None else _ts_now()

    def _status_background(self) -> dict[str, bool]:
        return {
            "open": self._status_active("open"),
            "close": self._status_active("close"),
            "shading": self._status_active("shading")
            or self._reason in {"shading", "manual_shading"},
        }

    def _remember_status_background(self, section_key: str) -> None:
        section = self._status.setdefault(section_key, {})
        section["background"] = self._status_background()
        section["restore_position"] = self._current_position()
        section["ts"] = _ts_now()

    def _background_for(self, section_key: str) -> dict[str, bool]:
        section = self._status.get(section_key, {})
        background = section.get("background") if isinstance(section, dict) else None
        if not isinstance(background, dict):
            return {"open": False, "close": False, "shading": False}
        return {key: bool(background.get(key)) for key in ("open", "close", "shading")}

    def _background_return_target(
        self,
        background: dict[str, bool],
        *,
        fallback: float | None,
        allow_open: bool = True,
        allow_shading: bool = True,
    ) -> tuple[float | None, str]:
        if background.get("shading") and allow_shading:
            return (
                self._effective_shading_position(),
                "ventilation_end_shading",
            )
        if background.get("close"):
            return (
                self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION),
                "ventilation_end_close",
            )
        if background.get("open") and allow_open:
            return (
                self._position_value(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION),
                "ventilation_end_open",
            )
        if fallback is not None:
            return fallback, "ventilation_end_restore"
        return (
            self._position_value(CONF_CLOSE_POSITION, DEFAULT_CLOSE_POSITION),
            "ventilation_end_close",
        )

    def _record_action_status(self, reason: str, position: float | None = None) -> None:
        ts = _ts_now()
        today = dt_util.as_local(dt_util.utcnow()).date()
        if reason == "ventilation_full":
            self._set_status_bucket("open", True, ts)
            self._set_status_bucket("close", False, ts)
            self._set_ventilation_status(False, True, ts)
        elif "open" in reason:
            self._last_action_dates["open"] = today
            self._set_status_bucket("open", True, ts)
            self._set_status_bucket("close", False, ts)
            self._set_status_bucket("shading", False, ts)
            self._clear_shading_pending(persist=False)
            self._set_ventilation_status(False, False, ts)
        elif "close" in reason or reason == "resident_asleep":
            self._last_action_dates["close"] = today
            self._set_status_bucket("open", False, ts)
            self._set_status_bucket("close", True, ts)
            self._set_status_bucket("shading", False, ts)
            self._clear_shading_pending(persist=False)
            self._set_ventilation_status(False, False, ts)
        elif reason in {"ventilation", "shading_end_ventilation"}:
            self._set_status_bucket("open", False, ts)
            self._set_status_bucket("close", False, ts)
            self._set_ventilation_status(True, False, ts)
        elif "shading" in reason:
            self._last_action_dates["shading"] = today
            self._set_status_bucket("open", True, ts)
            self._set_status_bucket("close", False, ts)
            self._set_status_bucket("shading", reason != "manual_shading_end", ts)
            self._clear_shading_pending(persist=False)
            self._set_ventilation_status(False, False, ts)

        self._status["target"] = position if position is not None else self._target
        self._status["reason"] = self._reason
        self.persist_status()

    def _record_group_background(self, reason: str) -> None:
        """Update the shared room target without interrupting local ventilation."""

        ts = _ts_now()
        today = dt_util.as_local(dt_util.utcnow()).date()
        background = self._status.setdefault("ventilation", {}).setdefault(
            "background", {"open": False, "close": False, "shading": False}
        )

        if "close" in reason or reason == "resident_asleep":
            self._last_action_dates["close"] = today
            self._set_status_bucket("open", False, ts)
            self._set_status_bucket("close", True, ts)
            self._set_status_bucket("shading", False, ts)
            background.update({"open": False, "close": True, "shading": False})
        elif "shading" in reason and "end_open" not in reason:
            self._last_action_dates["shading"] = today
            self._set_status_bucket("open", True, ts)
            self._set_status_bucket("close", False, ts)
            self._set_status_bucket("shading", True, ts)
            background.update({"open": True, "close": False, "shading": True})
        else:
            self._last_action_dates["open"] = today
            self._set_status_bucket("open", True, ts)
            self._set_status_bucket("close", False, ts)
            self._set_status_bucket("shading", False, ts)
            background.update({"open": True, "close": False, "shading": False})

        self._clear_shading_pending(persist=False)
        self.persist_status()
        self._publish_state()

    def _sync_position_reference_from_entity(self) -> None:
        """Seed missing runtime position data without replacing persisted intent."""

        current_position = self._current_position()
        if current_position is None:
            return
        self._last_position = current_position
        if self._target is None:
            self._target = current_position
            self._status["target"] = current_position
