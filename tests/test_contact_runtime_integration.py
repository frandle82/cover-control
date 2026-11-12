"""End-to-end contact mapping, listener, and runtime regressions."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.config_entries import ConfigEntryState
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.cover_control import button
from custom_components.cover_control.config_subentries import model_from_entries
from custom_components.cover_control.const import (
    CONF_AUTO_TIME,
    CONF_AUTO_VENTILATE,
    CONF_CLOSE_POSITION,
    CONF_CONTACT_STATUS_DELAY,
    CONF_CONTACT_TRIGGER_DELAY,
    CONF_CONTROLLER_ENTRY_ID,
    CONF_COVERS,
    CONF_ENTRY_TYPE,
    CONF_ENABLE_CLEAR_MANUAL_OVERRIDE_BUTTON,
    CONF_GLOBAL,
    CONF_GROUP,
    CONF_GROUPS,
    CONF_FINAL_CLOSE_TIME_ENABLED,
    CONF_FINAL_CLOSE_ELEVATION_ENABLED,
    CONF_INTERMEDIATE_CLOSE_ENABLED,
    CONF_INTERMEDIATE_CLOSE_POSITION,
    CONF_LOCKOUT_POSITION,
    CONF_MANUAL_OVERRIDE_MINUTES,
    CONF_NAME,
    CONF_OPEN_POSITION,
    CONF_POSITION_TOLERANCE,
    CONF_ROOM_ID,
    CONF_ROOM_SETTINGS,
    CONF_SOURCE_OVERRIDES,
    CONF_TIME_DOWN_EARLY_NON_WORKDAY,
    CONF_TIME_DOWN_EARLY_WORKDAY,
    CONF_TIME_DOWN_LATE_NON_WORKDAY,
    CONF_TIME_DOWN_LATE_WORKDAY,
    CONF_TIME_UP_EARLY_NON_WORKDAY,
    CONF_TIME_UP_EARLY_WORKDAY,
    CONF_TIME_UP_LATE_NON_WORKDAY,
    CONF_TIME_UP_LATE_WORKDAY,
    CONF_VENTILATE_POSITION,
    CONF_VENTILATION_DELAY_AFTER_CLOSE,
    CONF_WINDOW_SENSOR_FULL,
    CONF_WINDOW_SENSOR_TILT,
    DOMAIN,
    ENTRY_TYPE_CONTROLLER,
    ENTRY_TYPE_ROOM,
    GROUPS,
    GROUP_LIVING,
)
from custom_components.cover_control.runtime.common import (
    TRIGGER_SCHEDULED_CLOSE,
    TRIGGER_SCHEDULED_FINAL_CLOSE,
)


async def _setup_runtime(
    hass,
    *,
    covers: dict[str, tuple[list[str], list[str]]],
    enable_clear_manual_override_button: bool = False,
    group_settings: dict | None = None,
    initial_position: int = 100,
    supports_position: bool = False,
):
    calls = async_mock_service(hass, "cover", "set_cover_position")
    open_calls = async_mock_service(hass, "cover", "open_cover")
    async_mock_service(hass, "cover", "close_cover")
    async_mock_service(hass, "cover", "set_cover_tilt_position")
    for cover in covers:
        hass.states.async_set(
            cover,
            "open" if initial_position else "closed",
            {"current_position": initial_position}
            | (
                {"supported_features": CoverEntityFeature.SET_POSITION}
                if supports_position
                else {}
            ),
        )
    for full_sensors, tilt_sensors in covers.values():
        for sensor in (*full_sensors, *tilt_sensors):
            hass.states.async_set(sensor, "off")

    controller = MockConfigEntry(
        domain=DOMAIN,
        version=20,
        unique_id=DOMAIN,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_CONTROLLER,
            CONF_GLOBAL: {"sources": {}, "defaults": {}},
            CONF_GROUPS: {
                group: (
                    {
                        CONF_AUTO_TIME: False,
                        CONF_AUTO_VENTILATE: True,
                        CONF_CONTACT_TRIGGER_DELAY: 0,
                        CONF_CONTACT_STATUS_DELAY: 0,
                        CONF_VENTILATION_DELAY_AFTER_CLOSE: 0,
                        **(group_settings or {}),
                    }
                    if group == GROUP_LIVING
                    else {}
                )
                for group in GROUPS
            },
        },
    )
    room = MockConfigEntry(
        domain=DOMAIN,
        version=20,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_ROOM,
            CONF_CONTROLLER_ENTRY_ID: controller.entry_id,
            CONF_ROOM_ID: "living",
            CONF_NAME: "Living",
            CONF_GROUP: GROUP_LIVING,
            CONF_ROOM_SETTINGS: {
                CONF_COVERS: list(covers),
                CONF_OPEN_POSITION: 100,
                CONF_CLOSE_POSITION: 0,
                CONF_VENTILATE_POSITION: 25,
                CONF_LOCKOUT_POSITION: 80,
                CONF_POSITION_TOLERANCE: 1,
                CONF_ENABLE_CLEAR_MANUAL_OVERRIDE_BUTTON: (
                    enable_clear_manual_override_button
                ),
                CONF_WINDOW_SENSOR_FULL: {
                    cover: full_sensors
                    for cover, (full_sensors, _tilt_sensors) in covers.items()
                },
                CONF_WINDOW_SENSOR_TILT: {
                    cover: tilt_sensors
                    for cover, (_full_sensors, tilt_sensors) in covers.items()
                },
            },
            CONF_SOURCE_OVERRIDES: {},
        },
    )
    controller.add_to_hass(hass)
    room.add_to_hass(hass)
    assert await hass.config_entries.async_setup(controller.entry_id)
    await hass.async_block_till_done()
    if room.state is ConfigEntryState.NOT_LOADED:
        assert await hass.config_entries.async_setup(room.entry_id)
        await hass.async_block_till_done()
    manager = room.runtime_data.room_managers["living"]
    if manager._evaluation_task is not None:
        await manager._evaluation_task
    calls.clear()
    open_calls.clear()
    return controller, room, manager, calls, open_calls


async def _flush_evaluations(hass, manager) -> None:
    await hass.async_block_till_done()
    if manager._evaluation_task is not None:
        await manager._evaluation_task


async def test_contact_state_changes_drive_only_the_mapped_cover(hass) -> None:
    controller_entry, room_entry, manager, calls, open_calls = await _setup_runtime(
        hass,
        covers={
            "cover.links": (
                ["binary_sensor.links_offen", "binary_sensor.links_tuer"],
                ["binary_sensor.links_gekippt"],
            ),
            "cover.rechts": (
                ["binary_sensor.rechts_offen"],
                ["binary_sensor.rechts_gekippt"],
            ),
        },
    )
    left = manager.controllers["cover.links"]
    right = manager.controllers["cover.rechts"]

    assert left._full_open_sensors() == [
        "binary_sensor.links_offen",
        "binary_sensor.links_tuer",
    ]
    assert left._tilt_sensors() == ["binary_sensor.links_gekippt"]
    assert set(left._contact_entities()) <= left._local_listener_entities
    assert set(right._contact_entities()) <= right._local_listener_entities

    hass.states.async_set("binary_sensor.links_tuer", "on")
    await _flush_evaluations(hass, manager)

    assert [(call.data["entity_id"], call.data["position"]) for call in calls] == [
        ("cover.links", 80)
    ]
    assert left._effective_target == 80
    assert right._effective_target == 100
    assert left._background_target == right._background_target == 100

    hass.states.async_set("cover.links", "open", {"current_position": 80})
    calls.clear()
    hass.states.async_set("binary_sensor.links_tuer", "off")
    await _flush_evaluations(hass, manager)
    assert open_calls[-1].data == {"entity_id": "cover.links"}

    hass.states.async_set("cover.links", "open", {"current_position": 100})
    calls.clear()
    hass.states.async_set("binary_sensor.links_gekippt", "on")
    await _flush_evaluations(hass, manager)
    assert calls[-1].data == {"entity_id": "cover.links", "position": 25}

    calls.clear()
    hass.states.async_set("binary_sensor.rechts_offen", "unknown")
    hass.states.async_set("binary_sensor.rechts_gekippt", "unavailable")
    await _flush_evaluations(hass, manager)
    assert not calls

    assert await hass.config_entries.async_unload(room_entry.entry_id)
    assert await hass.config_entries.async_unload(controller_entry.entry_id)


async def test_contact_switch_blocks_then_rechecks_current_state(hass) -> None:
    controller_entry, room_entry, manager, calls, _open_calls = await _setup_runtime(
        hass,
        covers={
            "cover.wohnzimmer": (
                ["binary_sensor.fenster_offen"],
                ["binary_sensor.fenster_gekippt"],
            )
        },
    )

    manager.set_runtime_toggle(CONF_AUTO_VENTILATE, False)
    await _flush_evaluations(hass, manager)
    calls.clear()
    hass.states.async_set("binary_sensor.fenster_offen", "on")
    await _flush_evaluations(hass, manager)
    assert not calls

    manager.set_runtime_toggle(CONF_AUTO_VENTILATE, True)
    await _flush_evaluations(hass, manager)
    assert calls[-1].data == {"entity_id": "cover.wohnzimmer", "position": 80}

    assert await hass.config_entries.async_unload(room_entry.entry_id)
    assert await hass.config_entries.async_unload(controller_entry.entry_id)


async def test_contact_without_tilt_sensor_drives_to_ventilation_position(hass) -> None:
    """A single open contact means ventilation, not a full-open lockout."""

    controller_entry, room_entry, manager, calls, _open_calls = await _setup_runtime(
        hass,
        covers={"cover.wohnzimmer": (["binary_sensor.fenster_offen"], [])},
        initial_position=0,
        supports_position=True,
    )

    hass.states.async_set("binary_sensor.fenster_offen", "on")
    await _flush_evaluations(hass, manager)

    assert calls[-1].data == {"entity_id": "cover.wohnzimmer", "position": 25}
    controller = manager.controllers["cover.wohnzimmer"]
    assert not controller._manual_active

    hass.states.async_set(
        "cover.wohnzimmer",
        "open",
        {
            "current_position": 25,
            "supported_features": CoverEntityFeature.SET_POSITION,
        },
    )
    await _flush_evaluations(hass, manager)
    assert not controller._manual_active

    assert await hass.config_entries.async_unload(room_entry.entry_id)
    assert await hass.config_entries.async_unload(controller_entry.entry_id)


async def test_clear_manual_override_button_resets_runtime_and_reevaluates(hass) -> None:
    """The public clear button must release a permanent manual override."""

    controller_entry, room_entry, manager, _calls, _open_calls = await _setup_runtime(
        hass,
        covers={"cover.wohnzimmer": ([], [])},
        enable_clear_manual_override_button=True,
    )
    controller = manager.controllers["cover.wohnzimmer"]
    controller._manual_active = True
    controller._manual_until = None
    controller._reason = "manual_override"
    controller._status["manual"] = {"active": True, "until": None, "ts": 1}
    controller._manual_expire_unsub = expiry_timer = Mock()
    controller._evaluate_callback = evaluate = Mock()
    entities = []

    await button.async_setup_entry(hass, room_entry, entities.extend)
    clear_button = next(
        entity
        for entity in entities
        if entity.translation_key == "clear_manual_override"
    )
    await clear_button.async_press()

    assert not controller._manual_active
    assert controller._manual_until is None
    assert controller._manual_expire_unsub is None
    assert controller._reason is None
    assert controller._status["manual"] == {"active": False, "until": None, "ts": None}
    expiry_timer.assert_called_once_with()
    evaluate.assert_called_once_with(controller, "manual_cleared")

    assert await hass.config_entries.async_unload(room_entry.entry_id)
    assert await hass.config_entries.async_unload(controller_entry.entry_id)


def _time_settings(*, opening: bool) -> dict[str, str | bool]:
    now = dt_util.as_local(dt_util.utcnow())

    def _time_after(minutes: int) -> str:
        return (now + timedelta(minutes=minutes)).time().replace(microsecond=0).isoformat()

    up_early, up_late = (
        (_time_after(-1), _time_after(1))
        if opening
        else (_time_after(2), _time_after(3))
    )
    down_early, down_late = (
        (_time_after(2), _time_after(3))
        if opening
        else (_time_after(-1), _time_after(1))
    )
    return {
        CONF_AUTO_TIME: True,
        CONF_TIME_UP_EARLY_WORKDAY: up_early,
        CONF_TIME_UP_LATE_WORKDAY: up_late,
        CONF_TIME_UP_EARLY_NON_WORKDAY: up_early,
        CONF_TIME_UP_LATE_NON_WORKDAY: up_late,
        CONF_TIME_DOWN_EARLY_WORKDAY: down_early,
        CONF_TIME_DOWN_LATE_WORKDAY: down_late,
        CONF_TIME_DOWN_EARLY_NON_WORKDAY: down_early,
        CONF_TIME_DOWN_LATE_NON_WORKDAY: down_late,
    }


async def test_window_ventilation_overrides_scheduled_close(hass) -> None:
    """An open window must win over the active scheduled-close background."""

    controller_entry, room_entry, manager, calls, _open_calls = await _setup_runtime(
        hass,
        covers={"cover.wohnzimmer": (["binary_sensor.fenster_offen"], [])},
        group_settings=_time_settings(opening=False),
        initial_position=0,
        supports_position=True,
    )
    controller = manager.controllers["cover.wohnzimmer"]

    hass.states.async_set("binary_sensor.fenster_offen", "on")
    await _flush_evaluations(hass, manager)

    assert calls[-1].data == {"entity_id": "cover.wohnzimmer", "position": 25}
    assert controller._reason == "ventilation"
    assert not controller._manual_active

    hass.states.async_set(
        "cover.wohnzimmer",
        "open",
        {
            "current_position": 25,
            "supported_features": CoverEntityFeature.SET_POSITION,
        },
    )
    await _flush_evaluations(hass, manager)
    calls.clear()
    hass.states.async_set("binary_sensor.fenster_offen", "off")
    await _flush_evaluations(hass, manager)

    assert calls[-1].data == {"entity_id": "cover.wohnzimmer", "position": 0}
    assert not controller._manual_active

    assert await hass.config_entries.async_unload(room_entry.entry_id)
    assert await hass.config_entries.async_unload(controller_entry.entry_id)


@pytest.mark.parametrize(
    ("opening", "initial_position", "expected_position"),
    [(True, 0, 100), (False, 100, 0)],
)
async def test_contact_close_restores_current_background_target(
    hass, opening: bool, initial_position: int, expected_position: int
) -> None:
    """Contact close releases ventilation to the current time target."""

    controller_entry, room_entry, manager, calls, _open_calls = await _setup_runtime(
        hass,
        covers={"cover.wohnzimmer": (["binary_sensor.fenster_offen"], [])},
        group_settings=_time_settings(opening=True),
        initial_position=initial_position,
        supports_position=True,
    )
    controller = manager.controllers["cover.wohnzimmer"]

    hass.states.async_set("binary_sensor.fenster_offen", "on")
    await _flush_evaluations(hass, manager)
    assert calls[-1].data == {"entity_id": "cover.wohnzimmer", "position": 25}
    assert not controller._manual_active

    hass.states.async_set(
        "cover.wohnzimmer",
        "open",
        {
            "current_position": 25,
            "supported_features": CoverEntityFeature.SET_POSITION,
        },
    )
    await _flush_evaluations(hass, manager)
    if not opening:
        controller_data = {
            **controller_entry.data,
            CONF_GROUPS: {
                **controller_entry.data[CONF_GROUPS],
                GROUP_LIVING: {
                    **controller_entry.data[CONF_GROUPS][GROUP_LIVING],
                    **_time_settings(opening=False),
                },
            },
        }
        model = model_from_entries(
            controller_entry.entry_id, controller_data, [room_entry]
        )
        manager.apply_config_model(model, {"living"})
        await _flush_evaluations(hass, manager)
    assert controller._background_target == expected_position
    assert controller._effective_target == 25
    calls.clear()
    hass.states.async_set("binary_sensor.fenster_offen", "off")
    await _flush_evaluations(hass, manager)

    assert calls[-1].data == {
        "entity_id": "cover.wohnzimmer",
        "position": expected_position,
    }
    assert not controller._manual_active

    assert await hass.config_entries.async_unload(room_entry.entry_id)
    assert await hass.config_entries.async_unload(controller_entry.entry_id)


async def test_background_changes_from_intermediate_to_final_while_window_open(
    hass,
) -> None:
    """An open window must not freeze the earlier automation target."""

    controller_entry, room_entry, manager, calls, _open_calls = await _setup_runtime(
        hass,
        covers={"cover.wohnzimmer": (["binary_sensor.fenster_offen"], [])},
        group_settings={
            **_time_settings(opening=False),
            CONF_INTERMEDIATE_CLOSE_ENABLED: True,
            CONF_INTERMEDIATE_CLOSE_POSITION: 50,
            CONF_FINAL_CLOSE_TIME_ENABLED: False,
            CONF_FINAL_CLOSE_ELEVATION_ENABLED: True,
        },
        initial_position=100,
        supports_position=True,
    )

    hass.states.async_set("binary_sensor.fenster_offen", "on")
    await _flush_evaluations(hass, manager)
    hass.states.async_set(
        "cover.wohnzimmer",
        "open",
        {
            "current_position": 25,
            "supported_features": CoverEntityFeature.SET_POSITION,
        },
    )
    await _flush_evaluations(hass, manager)
    calls.clear()

    manager.request_evaluate_all(TRIGGER_SCHEDULED_CLOSE)
    await _flush_evaluations(hass, manager)
    runtime = manager.controllers["cover.wohnzimmer"]
    assert runtime._background_target == 50
    assert runtime._background_reason == "scheduled_intermediate_close"
    assert runtime._effective_target == 25
    assert runtime._effective_reason == "ventilation"
    manager.request_evaluate_all(TRIGGER_SCHEDULED_FINAL_CLOSE)
    await _flush_evaluations(hass, manager)

    assert not calls
    assert runtime._background_target == 0
    assert runtime._background_reason == "scheduled_final_close"
    assert runtime._effective_target == 25
    assert runtime._effective_reason == "ventilation"
    hass.states.async_set("binary_sensor.fenster_offen", "off")
    await _flush_evaluations(hass, manager)

    assert calls[-1].data == {"entity_id": "cover.wohnzimmer", "position": 0}
    assert all(call.data["position"] != 50 for call in calls)

    assert await hass.config_entries.async_unload(room_entry.entry_id)
    assert await hass.config_entries.async_unload(controller_entry.entry_id)


async def test_final_close_then_window_restore_never_reuses_intermediate(
    hass,
) -> None:
    """Real HA events restore Final Close, never the earlier middle position."""

    controller_entry, room_entry, manager, calls, _open_calls = await _setup_runtime(
        hass,
        covers={"cover.wohnzimmer": (["binary_sensor.fenster_offen"], [])},
        group_settings={
            **_time_settings(opening=False),
            CONF_INTERMEDIATE_CLOSE_ENABLED: True,
            CONF_INTERMEDIATE_CLOSE_POSITION: 50,
            CONF_FINAL_CLOSE_TIME_ENABLED: False,
            CONF_FINAL_CLOSE_ELEVATION_ENABLED: True,
        },
        initial_position=100,
        supports_position=True,
    )
    runtime = manager.controllers["cover.wohnzimmer"]

    manager.request_evaluate_all(TRIGGER_SCHEDULED_CLOSE)
    await _flush_evaluations(hass, manager)
    assert calls[-1].data["position"] == 50
    hass.states.async_set(
        "cover.wohnzimmer",
        "open",
        {
            "current_position": 50,
            "supported_features": CoverEntityFeature.SET_POSITION,
        },
    )
    await _flush_evaluations(hass, manager)

    manager.request_evaluate_all(TRIGGER_SCHEDULED_FINAL_CLOSE)
    await _flush_evaluations(hass, manager)
    assert calls[-1].data["position"] == 0
    hass.states.async_set(
        "cover.wohnzimmer",
        "closed",
        {
            "current_position": 0,
            "supported_features": CoverEntityFeature.SET_POSITION,
        },
    )
    await _flush_evaluations(hass, manager)

    hass.states.async_set("binary_sensor.fenster_offen", "on")
    await _flush_evaluations(hass, manager)
    assert calls[-1].data["position"] == 25
    hass.states.async_set(
        "cover.wohnzimmer",
        "open",
        {
            "current_position": 25,
            "supported_features": CoverEntityFeature.SET_POSITION,
        },
    )
    await _flush_evaluations(hass, manager)
    calls.clear()

    hass.states.async_set("binary_sensor.fenster_offen", "off")
    await _flush_evaluations(hass, manager)

    assert calls[-1].data == {"entity_id": "cover.wohnzimmer", "position": 0}
    assert all(call.data["position"] != 50 for call in calls)
    assert runtime._background_reason == "scheduled_final_close"

    assert await hass.config_entries.async_unload(room_entry.entry_id)
    assert await hass.config_entries.async_unload(controller_entry.entry_id)


@pytest.mark.parametrize(
    ("opening", "manual_position", "expected_position"),
    [(True, 50, 100), (False, 50, 0)],
)
async def test_clear_manual_override_button_immediately_resumes_automation(
    hass, opening: bool, manual_position: int, expected_position: int
) -> None:
    """The public reset unblocks both automatic opening and closing."""

    controller_entry, room_entry, manager, calls, _open_calls = await _setup_runtime(
        hass,
        covers={"cover.wohnzimmer": ([], [])},
        enable_clear_manual_override_button=True,
        group_settings={CONF_MANUAL_OVERRIDE_MINUTES: 0},
        supports_position=True,
    )
    controller = manager.controllers["cover.wohnzimmer"]
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.wohnzimmer", "position": manual_position},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert controller._manual_active
    assert controller._manual_until is None

    if opening:
        hass.states.async_set(
            "cover.wohnzimmer",
            "closed",
            {
                "current_position": 0,
                "supported_features": CoverEntityFeature.SET_POSITION,
            },
        )
        await _flush_evaluations(hass, manager)

    controller_data = {
        **controller_entry.data,
        CONF_GROUPS: {
            **controller_entry.data[CONF_GROUPS],
            GROUP_LIVING: {
                **controller_entry.data[CONF_GROUPS][GROUP_LIVING],
                **_time_settings(opening=opening),
            },
        },
    }
    model = model_from_entries(controller_entry.entry_id, controller_data, [room_entry])
    manager.apply_config_model(model, {"living"})
    await _flush_evaluations(hass, manager)
    assert controller._background_target == expected_position
    assert controller._effective_reason == "manual_override"
    calls.clear()

    entities = []
    await button.async_setup_entry(hass, room_entry, entities.extend)
    clear_button = next(
        entity
        for entity in entities
        if entity.translation_key == "clear_manual_override"
    )
    await clear_button.async_press()
    await _flush_evaluations(hass, manager)

    assert not controller._manual_active
    assert controller._manual_until is None
    assert controller._status["manual"] == {
        "active": False,
        "until": None,
        "ts": None,
    }
    assert manager._stored_state["covers"]["cover.wohnzimmer"]["manual"] == {
        "active": False,
        "until": None,
        "ts": None,
    }
    assert calls[-1].data == {
        "entity_id": "cover.wohnzimmer",
        "position": expected_position,
    }

    assert await hass.config_entries.async_unload(room_entry.entry_id)
    assert await hass.config_entries.async_unload(controller_entry.entry_id)


async def test_contact_listener_updates_after_reconfigure(hass) -> None:
    controller_entry, room_entry, manager, calls, _open_calls = await _setup_runtime(
        hass,
        covers={
            "cover.wohnzimmer": (["binary_sensor.alt"], [])
        },
    )
    settings = dict(room_entry.data[CONF_ROOM_SETTINGS])
    settings[CONF_WINDOW_SENSOR_FULL] = {
        "cover.wohnzimmer": ["binary_sensor.neu"]
    }
    hass.states.async_set("binary_sensor.neu", "off")
    updated_room = SimpleNamespace(
        entry_id=room_entry.entry_id,
        title=room_entry.title,
        data={**room_entry.data, CONF_ROOM_SETTINGS: settings},
    )
    model = model_from_entries(
        controller_entry.entry_id, controller_entry.data, [updated_room]
    )
    manager.apply_config_model(model, {"living"})

    controller = manager.controllers["cover.wohnzimmer"]
    assert "binary_sensor.alt" not in controller._local_listener_entities
    assert "binary_sensor.neu" in controller._local_listener_entities

    hass.states.async_set("binary_sensor.alt", "on")
    await _flush_evaluations(hass, manager)
    assert not calls
    hass.states.async_set("binary_sensor.neu", "on")
    await _flush_evaluations(hass, manager)
    assert calls[-1].data == {"entity_id": "cover.wohnzimmer", "position": 25}

    assert await hass.config_entries.async_unload(room_entry.entry_id)
    assert await hass.config_entries.async_unload(controller_entry.entry_id)
