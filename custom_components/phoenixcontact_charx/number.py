"""Number platform for Phoenix Contact CHARX integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from aiophoenixcontactcharx import CharxConnectionError, CharxModbusError

from . import CharxConfigEntry
from .const import MAX_CURRENT_A, MIN_CURRENT_A
from .coordinator import CharxCoordinator
from .entity import CharxChargingPointEntity, CharxEntity

_LOGGER = logging.getLogger(__name__)


class CharxMaxCurrentNumber(CharxChargingPointEntity, NumberEntity):
    """Number entity to set the maximum charging current for one charging point."""

    _attr_translation_key = "max_current"
    _attr_device_class = NumberDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = MIN_CURRENT_A
    _attr_native_max_value = MAX_CURRENT_A
    _attr_native_step = 1.0

    def __init__(self, coordinator: CharxCoordinator, charging_point: int) -> None:
        super().__init__(coordinator, charging_point, "max_current_number")

    @property
    def native_value(self) -> float | None:
        cp_data = next(
            (cp for cp in self.coordinator.data.charging_points
             if cp.charging_point == self._charging_point),
            None,
        )
        return float(cp_data.control.max_current_a) if cp_data else None

    async def async_set_native_value(self, value: float) -> None:
        current = int(value)
        try:
            await self.coordinator.client.set_max_current(self._charging_point, current)
        except ValueError as err:
            message = (
                f"Invalid max current value {current} on "
                f"CP{self._charging_point}: {err}"
            )
            _LOGGER.error(message)
            raise HomeAssistantError(message) from err
        except (CharxConnectionError, CharxModbusError) as err:
            message = (
                f"Failed to set max current on CP{self._charging_point}: {err}"
            )
            _LOGGER.error(message)
            raise HomeAssistantError(message) from err
        await self.coordinator.async_request_refresh()


class CharxDynamicMaxCurrentNumber(CharxEntity, NumberEntity):
    """Number entity for the group-level dynamic maximum current (load management)."""

    _attr_translation_key = "dynamic_max_current_number"
    _attr_device_class = NumberDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 0.0
    _attr_native_max_value = float(MAX_CURRENT_A)
    _attr_native_step = 1.0

    def __init__(self, coordinator: CharxCoordinator) -> None:
        super().__init__(coordinator, "dynamic_max_current_number")

    @property
    def native_value(self) -> float | None:
        return float(self.coordinator.data.device_info.dynamic_max_current_a)

    async def async_set_native_value(self, value: float) -> None:
        current = int(value)
        try:
            await self.coordinator.client.set_dynamic_max_current(current)
        except (CharxConnectionError, CharxModbusError) as err:
            message = f"Failed to set dynamic max current on CP group: {err}"
            _LOGGER.error(message)
            raise HomeAssistantError(message) from err
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CharxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = [CharxDynamicMaxCurrentNumber(coordinator)]
    for cp in range(1, coordinator.num_charging_points + 1):
        entities.append(CharxMaxCurrentNumber(coordinator, cp))
    async_add_entities(entities)
