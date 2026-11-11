"""End-to-end contact mapping, listener, and runtime regressions."""

from __future__ import annotations

from types import SimpleNamespace

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

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
    CONF_GLOBAL,
    CONF_GROUP,
    CONF_GROUPS,
    CONF_LOCKOUT_POSITION,
    CONF_NAME,
    CONF_OPEN_POSITION,
    CONF_POSITION_TOLERANCE,
    CONF_ROOM_ID,
    CONF_ROOM_SETTINGS,
    CONF_SOURCE_OVERRIDES,
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


async def _setup_runtime(hass, *, covers: dict[str, tuple[list[str], list[str]]]):
    calls = async_mock_service(hass, "cover", "set_cover_position")
    open_calls = async_mock_service(hass, "cover", "open_cover")
    async_mock_service(hass, "cover", "close_cover")
    async_mock_service(hass, "cover", "set_cover_tilt_position")
    for cover in covers:
        hass.states.async_set(cover, "open", {"current_position": 100})
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
    assert calls[-1].data == {"entity_id": "cover.wohnzimmer", "position": 80}

    assert await hass.config_entries.async_unload(room_entry.entry_id)
    assert await hass.config_entries.async_unload(controller_entry.entry_id)
