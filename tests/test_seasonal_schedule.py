"""Regression tests for recurring summer and Christmas schedule behavior."""

from __future__ import annotations

from datetime import datetime, timezone
import inspect
from unittest.mock import Mock

from custom_components.cover_control.const import (
    CONF_CHRISTMAS_END,
    CONF_CHRISTMAS_POSITION,
    CONF_CHRISTMAS_POSITION_ENABLED,
    CONF_CHRISTMAS_START,
    CONF_CLOSE_POSITION,
    CONF_FINAL_CLOSE_TIME,
    CONF_INTERMEDIATE_CLOSE_ENABLED,
    CONF_INTERMEDIATE_CLOSE_POSITION,
    CONF_SUMMER_END,
    CONF_SUMMER_SKIP_CLOSE_ENABLED,
    CONF_SUMMER_START,
)
from custom_components.cover_control.runtime.controller import CoverController
from custom_components.cover_control.runtime.evaluation import EvaluationMixin
from custom_components.cover_control.runtime.manager import (
    _blocking_controls_for_reason,
    _controls_for_reason,
)


def _controller(**config) -> CoverController:
    controller = object.__new__(CoverController)
    controller.config = {
        CONF_CLOSE_POSITION: 0,
        CONF_INTERMEDIATE_CLOSE_POSITION: 50,
        CONF_FINAL_CLOSE_TIME: "22:00:00",
        **config,
    }
    controller._position_value = Mock(
        side_effect=lambda key, default: controller.config.get(key, default)
    )
    return controller


def _at(month: int, day: int, hour: int = 12) -> datetime:
    return datetime(2026, month, day, hour, tzinfo=timezone.utc)


def test_summer_period_blocks_configured_normal_close() -> None:
    controller = _controller(
        **{
            CONF_SUMMER_SKIP_CLOSE_ENABLED: True,
            CONF_SUMMER_START: "01.03.",
            CONF_SUMMER_END: "30.09.",
        }
    )

    suppressed, target, intermediate = controller._seasonal_close_target(
        _at(7, 1), 100, False
    )

    assert suppressed is True
    assert target == 0
    assert intermediate is False
    assert _controls_for_reason("summer_period") == {"summer_period"}
    assert _blocking_controls_for_reason("summer_period") == {"summer_period"}


def test_summer_period_does_not_block_unconfigured_cover() -> None:
    controller = _controller(
        **{
            CONF_SUMMER_SKIP_CLOSE_ENABLED: False,
            CONF_SUMMER_START: "01.03.",
            CONF_SUMMER_END: "30.09.",
        }
    )

    assert controller._summer_close_suppressed(_at(7, 1)) is False


def test_summer_period_handles_start_boundary() -> None:
    controller = _controller(
        **{
            CONF_SUMMER_SKIP_CLOSE_ENABLED: True,
            CONF_SUMMER_START: "01.03.",
            CONF_SUMMER_END: "30.09.",
        }
    )

    assert controller._summer_close_suppressed(_at(3, 1)) is True
    assert controller._summer_close_suppressed(_at(2, 28)) is False


def test_summer_period_handles_end_boundary() -> None:
    controller = _controller(
        **{
            CONF_SUMMER_SKIP_CLOSE_ENABLED: True,
            CONF_SUMMER_START: "01.03.",
            CONF_SUMMER_END: "30.09.",
        }
    )

    assert controller._summer_close_suppressed(_at(9, 30)) is True
    assert controller._summer_close_suppressed(_at(10, 1)) is False


def test_recurring_period_handles_year_wrap() -> None:
    assert CoverController._is_date_in_recurring_range(
        _at(12, 24), "01.11.", "15.02."
    )
    assert CoverController._is_date_in_recurring_range(
        _at(1, 10), "01.11.", "15.02."
    )
    assert not CoverController._is_date_in_recurring_range(
        _at(3, 1), "01.11.", "15.02."
    )


def test_christmas_period_uses_configured_position() -> None:
    controller = _controller(
        **{
            CONF_CHRISTMAS_POSITION_ENABLED: True,
            CONF_CHRISTMAS_POSITION: 25,
            CONF_CHRISTMAS_START: "01.12.",
            CONF_CHRISTMAS_END: "06.01.",
        }
    )

    assert controller._christmas_close_position(_at(12, 24)) == 25


def test_christmas_position_not_used_outside_period() -> None:
    controller = _controller(
        **{
            CONF_CHRISTMAS_POSITION_ENABLED: True,
            CONF_CHRISTMAS_POSITION: 25,
            CONF_CHRISTMAS_START: "01.12.",
            CONF_CHRISTMAS_END: "06.01.",
        }
    )

    assert controller._christmas_close_position(_at(2, 1)) is None


def test_christmas_disabled_cover_uses_normal_close_position() -> None:
    controller = _controller(**{CONF_CHRISTMAS_POSITION_ENABLED: False})

    assert controller._seasonal_close_target(_at(12, 24), 100, False) == (
        False,
        0,
        False,
    )


def test_christmas_overrides_intermediate_and_final_close() -> None:
    controller = _controller(
        **{
            CONF_INTERMEDIATE_CLOSE_ENABLED: True,
            CONF_CHRISTMAS_POSITION_ENABLED: True,
            CONF_CHRISTMAS_POSITION: 25,
            CONF_CHRISTMAS_START: "01.12.",
            CONF_CHRISTMAS_END: "06.01.",
        }
    )

    assert controller._seasonal_close_target(_at(12, 24, 20), 100, False) == (
        False,
        25,
        False,
    )
    assert controller._seasonal_close_target(_at(12, 24, 22), 50, True) == (
        False,
        25,
        False,
    )


def test_christmas_period_handles_year_wrap() -> None:
    controller = _controller(
        **{
            CONF_CHRISTMAS_POSITION_ENABLED: True,
            CONF_CHRISTMAS_POSITION: 25,
            CONF_CHRISTMAS_START: "01.12.",
            CONF_CHRISTMAS_END: "06.01.",
        }
    )

    assert controller._christmas_close_position(_at(12, 1)) == 25
    assert controller._christmas_close_position(_at(1, 6)) == 25
    assert controller._christmas_close_position(_at(1, 7)) is None


def test_summer_period_does_not_block_safety() -> None:
    source = inspect.getsource(EvaluationMixin._evaluate)

    assert source.index("await self._evaluate_safety()") < source.index(
        "self._seasonal_close_target"
    )


def test_christmas_does_not_override_safety() -> None:
    evaluation_source = inspect.getsource(EvaluationMixin._evaluate)
    target_source = inspect.getsource(EvaluationMixin._seasonal_close_target)

    assert evaluation_source.index("await self._evaluate_safety()") < (
        evaluation_source.index("self._seasonal_close_target")
    )
    assert "self._christmas_close_position" in target_source


def test_restart_inside_and_outside_season_uses_current_date() -> None:
    controller = _controller(
        **{
            CONF_SUMMER_SKIP_CLOSE_ENABLED: True,
            CONF_SUMMER_START: "01.03.",
            CONF_SUMMER_END: "30.09.",
            CONF_CHRISTMAS_POSITION_ENABLED: True,
            CONF_CHRISTMAS_POSITION: 25,
            CONF_CHRISTMAS_START: "01.12.",
            CONF_CHRISTMAS_END: "06.01.",
        }
    )

    assert controller._summer_close_suppressed(_at(7, 1))
    assert not controller._summer_close_suppressed(_at(11, 1))
    assert controller._christmas_close_position(_at(12, 24)) == 25
    assert controller._christmas_close_position(_at(2, 1)) is None
