"""Tests for sensor, binary_sensor, switch, and number entities."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.exceptions import HomeAssistantError

from aiophoenixcontactcharx import CharxConnectionError

from .conftest import fake_charx_data, fake_cp_data


async def _setup(hass, config_entry, mock_client, charx_data=None):
    if charx_data:
        mock_client.fetch_data = AsyncMock(return_value=charx_data)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# Sensors
# ---------------------------------------------------------------------------

class TestSensors:
    async def test_vehicle_status_idle(self, hass, config_entry, mock_client):
        await _setup(hass, config_entry, mock_client)
        state = hass.states.get("sensor.charging_point_1_vehicle_status")
        assert state is not None
        assert state.state == "a1"

    async def test_vehicle_status_charging(self, hass, config_entry, mock_client):
        data = fake_charx_data()
        data.charging_points[0].status.vehicle_status = "C2"
        await _setup(hass, config_entry, mock_client, data)
        state = hass.states.get("sensor.charging_point_1_vehicle_status")
        assert state.state == "c2"

    async def test_total_energy_kwh(self, hass, config_entry, mock_client):
        # fixture: energy_active_wh = 12_345_000 → 12345.0 kWh
        await _setup(hass, config_entry, mock_client)
        state = hass.states.get("sensor.charging_point_1_total_energy")
        assert state is not None
        assert float(state.state) == pytest.approx(12345.0, rel=1e-3)

    async def test_voltage_l1(self, hass, config_entry, mock_client):
        # fixture: voltage_l1_mv = 230_000 → 230.0 V
        await _setup(hass, config_entry, mock_client)
        state = hass.states.get("sensor.charging_point_1_voltage_l1")
        assert float(state.state) == pytest.approx(230.0, rel=1e-3)

    async def test_phase_current_unknown_is_unknown(self, hass, config_entry, mock_client):
        data = fake_charx_data()
        data.charging_points[0].status.current_l1_ma = None
        await _setup(hass, config_entry, mock_client, data)
        state = hass.states.get("sensor.charging_point_1_current_l1")
        assert state.state == STATE_UNKNOWN

    async def test_group_active_power(self, hass, config_entry, mock_client):
        data = fake_charx_data(group_active_power_mw=11_000_000)
        await _setup(hass, config_entry, mock_client, data)
        state = hass.states.get("sensor.charx_group_active_power")
        assert float(state.state) == pytest.approx(11000.0, rel=1e-3)

    async def test_error_code_formatted_as_hex(self, hass, config_entry, mock_client):
        data = fake_charx_data()
        data.charging_points[0].status.error_code = 0x00000040
        await _setup(hass, config_entry, mock_client, data)
        state = hass.states.get("sensor.charging_point_1_error_code")
        assert state.state == "0x00000040"

    async def test_error_code_zero_formatted(self, hass, config_entry, mock_client):
        await _setup(hass, config_entry, mock_client)
        state = hass.states.get("sensor.charging_point_1_error_code")
        assert state.state == "0x00000000"


# ---------------------------------------------------------------------------
# Binary sensors
# ---------------------------------------------------------------------------

class TestBinarySensors:
    async def test_connected_false_when_a1(self, hass, config_entry, mock_client):
        await _setup(hass, config_entry, mock_client)
        state = hass.states.get("binary_sensor.charging_point_1_connected")
        assert state.state == STATE_OFF

    async def test_connected_true_when_c2(self, hass, config_entry, mock_client):
        data = fake_charx_data()
        data.charging_points[0].status.vehicle_status = "C2"
        await _setup(hass, config_entry, mock_client, data)
        state = hass.states.get("binary_sensor.charging_point_1_connected")
        assert state.state == STATE_ON

    async def test_charging_true_when_c2(self, hass, config_entry, mock_client):
        data = fake_charx_data()
        data.charging_points[0].status.vehicle_status = "C2"
        await _setup(hass, config_entry, mock_client, data)
        state = hass.states.get("binary_sensor.charging_point_1_charging")
        assert state.state == STATE_ON

    async def test_charging_false_when_b1(self, hass, config_entry, mock_client):
        data = fake_charx_data()
        data.charging_points[0].status.vehicle_status = "B1"
        await _setup(hass, config_entry, mock_client, data)
        state = hass.states.get("binary_sensor.charging_point_1_charging")
        assert state.state == STATE_OFF

    async def test_error_true_when_e0(self, hass, config_entry, mock_client):
        data = fake_charx_data()
        data.charging_points[0].status.vehicle_status = "E0"
        await _setup(hass, config_entry, mock_client, data)
        state = hass.states.get("binary_sensor.charging_point_1_error")
        assert state.state == STATE_ON

    async def test_error_false_when_c2(self, hass, config_entry, mock_client):
        data = fake_charx_data()
        data.charging_points[0].status.vehicle_status = "C2"
        await _setup(hass, config_entry, mock_client, data)
        state = hass.states.get("binary_sensor.charging_point_1_error")
        assert state.state == STATE_OFF


# ---------------------------------------------------------------------------
# Switches
# ---------------------------------------------------------------------------

class TestSwitches:
    async def test_charging_release_state_off(self, hass, config_entry, mock_client):
        await _setup(hass, config_entry, mock_client)
        state = hass.states.get("switch.charging_point_1_charging_release")
        assert state.state == STATE_OFF

    async def test_charging_release_state_on(self, hass, config_entry, mock_client):
        data = fake_charx_data()
        data.charging_points[0].control.charging_release = True
        await _setup(hass, config_entry, mock_client, data)
        state = hass.states.get("switch.charging_point_1_charging_release")
        assert state.state == STATE_ON

    async def test_turn_on_charging_release_calls_client(self, hass, config_entry, mock_client):
        await _setup(hass, config_entry, mock_client)
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_on",
            {"entity_id": "switch.charging_point_1_charging_release"},
            blocking=True,
        )
        mock_client.set_charging_release.assert_awaited_once_with(1, True)

    async def test_turn_off_charging_release_calls_client(self, hass, config_entry, mock_client):
        await _setup(hass, config_entry, mock_client)
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_off",
            {"entity_id": "switch.charging_point_1_charging_release"},
            blocking=True,
        )
        mock_client.set_charging_release.assert_awaited_once_with(1, False)

    async def test_turn_on_charging_release_raises_on_write_failure(
        self, hass, config_entry, mock_client
    ):
        mock_client.set_charging_release.side_effect = CharxConnectionError(
            "device offline"
        )
        await _setup(hass, config_entry, mock_client)

        with pytest.raises(
            HomeAssistantError,
            match="Failed to enable charging release on CP1: device offline",
        ):
            await hass.services.async_call(
                SWITCH_DOMAIN, "turn_on",
                {"entity_id": "switch.charging_point_1_charging_release"},
                blocking=True,
            )

    async def test_availability_switch_on(self, hass, config_entry, mock_client):
        await _setup(hass, config_entry, mock_client)
        state = hass.states.get("switch.charging_point_1_available")
        assert state.state == STATE_ON  # fixture: available=True

    async def test_turn_off_availability_calls_client(self, hass, config_entry, mock_client):
        await _setup(hass, config_entry, mock_client)
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_off",
            {"entity_id": "switch.charging_point_1_available"},
            blocking=True,
        )
        mock_client.set_availability.assert_awaited_once_with(1, False)

    async def test_turn_off_availability_raises_on_write_failure(
        self, hass, config_entry, mock_client
    ):
        mock_client.set_availability.side_effect = CharxConnectionError(
            "device offline"
        )
        await _setup(hass, config_entry, mock_client)

        with pytest.raises(
            HomeAssistantError,
            match="Failed to set CP1 to status F: device offline",
        ):
            await hass.services.async_call(
                SWITCH_DOMAIN, "turn_off",
                {"entity_id": "switch.charging_point_1_available"},
                blocking=True,
            )


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------

class TestNumbers:
    async def test_max_current_initial_value(self, hass, config_entry, mock_client):
        await _setup(hass, config_entry, mock_client)
        state = hass.states.get("number.charging_point_1_max_current")
        assert float(state.state) == 16.0  # fixture: max_current_a=16

    async def test_set_max_current_calls_client(self, hass, config_entry, mock_client):
        await _setup(hass, config_entry, mock_client)
        await hass.services.async_call(
            NUMBER_DOMAIN, "set_value",
            {"entity_id": "number.charging_point_1_max_current", "value": 11},
            blocking=True,
        )
        mock_client.set_max_current.assert_awaited_once_with(1, 11)

    async def test_set_max_current_raises_on_write_failure(
        self, hass, config_entry, mock_client
    ):
        mock_client.set_max_current.side_effect = CharxConnectionError(
            "device offline"
        )
        await _setup(hass, config_entry, mock_client)

        with pytest.raises(
            HomeAssistantError,
            match="Failed to set max current on CP1: device offline",
        ):
            await hass.services.async_call(
                NUMBER_DOMAIN, "set_value",
                {"entity_id": "number.charging_point_1_max_current", "value": 11},
                blocking=True,
            )

    async def test_set_max_current_raises_on_invalid_value(
        self, hass, config_entry, mock_client
    ):
        mock_client.set_max_current.side_effect = ValueError(
            "must be between 6 and 32 A"
        )
        await _setup(hass, config_entry, mock_client)

        with pytest.raises(
            HomeAssistantError,
            match="Invalid max current value 11 on CP1: must be between 6 and 32 A",
        ) as exc_info:
            await hass.services.async_call(
                NUMBER_DOMAIN, "set_value",
                {"entity_id": "number.charging_point_1_max_current", "value": 11},
                blocking=True,
            )

        assert isinstance(exc_info.value.__cause__, ValueError)

    async def test_dynamic_max_current_initial_value(self, hass, config_entry, mock_client):
        await _setup(hass, config_entry, mock_client)
        state = hass.states.get("number.charx_dynamic_max_current_group")
        assert float(state.state) == 32.0  # fixture: dynamic_max_current_a=32

    async def test_set_dynamic_max_current_calls_client(self, hass, config_entry, mock_client):
        await _setup(hass, config_entry, mock_client)
        await hass.services.async_call(
            NUMBER_DOMAIN, "set_value",
            {"entity_id": "number.charx_dynamic_max_current_group", "value": 48},
            blocking=True,
        )
        mock_client.set_dynamic_max_current.assert_awaited_once_with(48)

    async def test_set_dynamic_max_current_raises_on_write_failure(
        self, hass, config_entry, mock_client
    ):
        mock_client.set_dynamic_max_current.side_effect = CharxConnectionError(
            "device offline"
        )
        await _setup(hass, config_entry, mock_client)

        with pytest.raises(
            HomeAssistantError,
            match="Failed to set dynamic max current on CP group: device offline",
        ):
            await hass.services.async_call(
                NUMBER_DOMAIN, "set_value",
                {"entity_id": "number.charx_dynamic_max_current_group", "value": 48},
                blocking=True,
            )
