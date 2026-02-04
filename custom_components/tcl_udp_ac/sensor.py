"""Sensor platform for TCL UDP AC."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature

from .entity import TclUdpEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import TclUdpDataUpdateCoordinator
    from .data import TclUdpConfigEntry


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: TclUdpConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([TclUdpOutdoorTempSensor(coordinator)])


class TclUdpOutdoorTempSensor(TclUdpEntity, SensorEntity):
    """TCL UDP Outdoor Temperature Sensor."""

    _MIN_VALID_TEMP_F = -40
    _MAX_VALID_TEMP_F = 160
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT

    def __init__(self, coordinator: TclUdpDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "TCL AC Outdoor Temperature"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_outdoor_temp"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "outdoor_temp" in self.coordinator.data:
            # Check for valid range, sometimes devices report 176 or similar for invalid
            val = float(self.coordinator.data["outdoor_temp"])
            if self._MIN_VALID_TEMP_F < val < self._MAX_VALID_TEMP_F:
                return val
        return None
