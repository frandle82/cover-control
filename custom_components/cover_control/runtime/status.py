"""Cover controller behavior split from the public controller facade."""

from __future__ import annotations

from datetime import datetime

from homeassistant.util import dt as dt_util

from ..const import (
    CONF_MANUAL_CONTROL,
    DEFAULT_MANUAL_CONTROL,
)
from .common import (
    BACKGROUND_REASON_KIND,
    _coerce_float,
    _ts_now,
)


class StatusMixin:
    def _hydrate_persistent_status(self) -> None:
        legacy_target = _coerce_float(self._status.get("target"))
        legacy_reason = self._status.get("reason")
        legacy_reason = (
            legacy_reason
            if isinstance(legacy_reason, str) and legacy_reason
            else None
        )
        background = self._status.get("background", {})
        effective = self._status.get("effective", {})
        restore_position = _coerce_float(self._status.get("legacy_restore_position"))
        self._background_target = _coerce_float(background.get("target"))
        self._background_reason = background.get("reason")
        self._background_updated_at = background.get("updated_at")
        if self._background_target is None:
            if legacy_reason and self._is_background_reason(legacy_reason):
                self._background_target = legacy_target
                self._background_reason = legacy_reason
            elif restore_position is not None:
                self._background_target = restore_position
            else:
                self._background_target = legacy_target
        self._effective_target = _coerce_float(effective.get("target"))
        self._effective_reason = effective.get("reason") or legacy_reason
        self._effective_updated_at = effective.get("updated_at")
        if self._effective_target is None:
            self._effective_target = legacy_target

        manual = self._status.get("manual", {})
        if isinstance(manual, dict):
            until_raw = manual.get("until")
            until = dt_util.parse_datetime(until_raw) if until_raw else None
            if until:
                until = dt_util.as_utc(until)
            self._manual_until = until
            self._manual_active = bool(
                self.config.get(CONF_MANUAL_CONTROL, DEFAULT_MANUAL_CONTROL)
                and manual.get("active")
                and (until is None or until > dt_util.utcnow())
            )
            if not self._manual_active:
                self._manual_until = None

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
        # ``target``/``reason`` and ventilation.restore_position are read only
        # during legacy hydration.  Persist only the canonical state afterwards.
        self._status.pop("reason", None)
        self._status.pop("target", None)
        self._status.pop("legacy_restore_position", None)
        self._status["background"] = {
            "target": self._background_target,
            "reason": self._background_reason,
            "updated_at": self._background_updated_at,
        }
        self._status["effective"] = {
            "target": self._effective_target,
            "reason": self._effective_reason,
            "updated_at": self._effective_updated_at,
        }
        self._status["last_action_dates"] = {
            action: date_value.isoformat()
            for action, date_value in self._last_action_dates.items()
        }
        manual = self._status.setdefault("manual", {})
        manual["active"] = self._manual_active
        manual["until"] = self._manual_until.isoformat() if self._manual_until else None
        if self._manual_active and not manual.get("ts"):
            manual["ts"] = _ts_now()

        ventilation = self._status.setdefault("ventilation", {})
        ventilation.pop("restore_position", None)

    def _set_background_target(
        self, target: float | None, reason: str | None, *, persist: bool = True
    ) -> None:
        """Store the latest normal automation decision independently of overrides."""

        if target is None:
            return
        target = float(target)
        changed = (
            getattr(self, "_background_target", None) != target
            or getattr(self, "_background_reason", None) != reason
        )
        self._background_target = target
        self._background_reason = reason
        if changed or getattr(self, "_background_updated_at", None) is None:
            self._background_updated_at = _ts_now()
        if reason:
            self._record_background_status(reason)
        if persist:
            self.persist_status()

    def _background_reason_kind(self) -> str | None:
        """Return the declared category of the canonical background reason."""

        return BACKGROUND_REASON_KIND.get(self._background_reason)

    def _set_effective_state(
        self, target: float | None, reason: str | None, *, persist: bool = True
    ) -> None:
        """Store the target currently selected by the priority resolver."""

        changed = (
            getattr(self, "_effective_target", None) != target
            or getattr(self, "_effective_reason", None) != reason
        )
        self._effective_target = target
        self._effective_reason = reason
        if changed or getattr(self, "_effective_updated_at", None) is None:
            self._effective_updated_at = _ts_now()
        if persist:
            self.persist_status()

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
        if active is not None:
            section["active"] = active
        if due_at is None:
            self._shading_pending.pop(kind, None)
            self._cancel_shading_timer(kind)
            return
        if (
            self._shading_pending.get(kind) == due_at
            and kind in self._shading_timer_unsubs
        ):
            return
        self._cancel_shading_timer(kind)
        self._shading_pending[kind] = due_at
        self._schedule_shading_timer(kind, due_at)

    def _shading_pending_due(self, kind: str, now: datetime) -> bool:
        due_at = self._shading_pending.get(kind)
        return bool(due_at and now >= due_at)

    def _shading_pending_active(self, kind: str) -> bool:
        return kind in self._shading_pending

    def _shading_pending_at(self, kind: str) -> datetime | None:
        return self._shading_pending.get(kind)

    def _clear_shading_pending(
        self, kind: str | None = None, persist: bool = True
    ) -> None:
        if kind in (None, "start"):
            self._shading_pending.pop("start", None)
            self._cancel_shading_timer("start")
        if kind in (None, "end"):
            self._shading_pending.pop("end", None)
            self._cancel_shading_timer("end")

    def _set_ventilation_status(
        self, partial: bool = False, full: bool = False, ts: int | None = None
    ) -> None:
        section = self._status.setdefault("ventilation", {})
        section["partial"] = partial
        section["full"] = full
        section["ts"] = ts if ts is not None else _ts_now()

    def _record_background_status(self, reason: str) -> None:
        """Update legacy activity buckets from the canonical background decision."""

        ts = _ts_now()
        today = dt_util.as_local(dt_util.utcnow()).date()
        kind = BACKGROUND_REASON_KIND.get(reason)
        if kind is None:
            return
        if not hasattr(self, "_last_action_dates"):
            self._last_action_dates = {}
        self._last_action_dates[kind] = today
        if kind == "close":
            if reason == "scheduled_final_close":
                self._last_action_dates["final_close"] = today
            self._set_status_bucket("open", False, ts)
            self._set_status_bucket("close", True, ts)
            self._set_status_bucket("shading", False, ts)
        elif kind == "shading":
            self._set_status_bucket("open", True, ts)
            self._set_status_bucket("close", False, ts)
            self._set_status_bucket("shading", True, ts)
        else:
            self._set_status_bucket("open", True, ts)
            self._set_status_bucket("close", False, ts)
            self._set_status_bucket("shading", False, ts)

    def _record_action_status(self, reason: str, position: float | None = None) -> None:
        ts = _ts_now()
        self._logbook_action(reason, position)
        if reason == "ventilation_full":
            self._set_ventilation_status(False, True, ts)
        elif reason in {"ventilation", "shading_end_ventilation"}:
            self._set_ventilation_status(True, False, ts)
        elif reason in BACKGROUND_REASON_KIND:
            self._record_background_status(reason)
            self._clear_shading_pending(persist=False)
            self._set_ventilation_status(False, False, ts)

        if reason.startswith("shading_end_"):
            self._set_heat_protection_status(False, False)

        self.persist_status()

    def _logbook_action(self, reason: str, position: float | None) -> None:
        """Describe significant completed controller actions in the cover logbook."""

        target = self._target if position is None else position
        target_text = f"{target:g}%" if target is not None else "the target position"
        if reason == "scheduled_open":
            self._logbook_entry(f"Moved to {target_text} · scheduled opening")
        elif reason in {
            "scheduled_close",
            "scheduled_intermediate_close",
            "scheduled_final_close",
        }:
            self._logbook_entry(f"Moved to {target_text} · scheduled closing")
        elif reason in {"shading", "manual_shading", "heat_protection"}:
            message = (
                f"Moved to {target_text} · heat protection started"
                if reason == "heat_protection"
                else (
                    f"Moved to {target_text} · sun shading started"
                    if reason == "shading"
                    else f"Moved to {target_text} · sun shading started manually"
                )
            )
            self._logbook_entry(message)
        elif reason.startswith("shading_end") or reason == "manual_shading_end":
            self._logbook_entry("Sun shading ended")
            if reason == "shading_end_ventilation":
                self._logbook_entry(
                    f"Moved to {target_text} · ventilation started"
                )
        elif reason in {"ventilation", "ventilation_full", "ventilation_start"}:
            self._logbook_entry(f"Moved to {target_text} · ventilation started")
        elif reason.startswith("ventilation_end") or reason == "ventilation_stop":
            self._logbook_entry("Ventilation ended")
    def _sync_position_reference_from_entity(self) -> None:
        """Seed missing runtime position data without replacing persisted intent."""

        current_position = self._current_position()
        if current_position is None:
            return
        self._last_position = current_position
        if getattr(self, "_effective_target", None) is None:
            self._effective_target = current_position
        if getattr(self, "_background_target", None) is None:
            self._background_target = current_position
