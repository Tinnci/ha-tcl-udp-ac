"""Climate platform for TCL UDP AC."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .const import LOGGER
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
    """Set up the climate platform."""
    async_add_entities([TclUdpClimate(entry.runtime_data.coordinator)])


class TclUdpClimate(TclUdpEntity, ClimateEntity):
    """TCL UDP AC Climate entity."""

    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes: ClassVar[list[HVACMode]] = [HVACMode.OFF, HVACMode.COOL]
    _attr_min_temp = 60
    _attr_max_temp = 86
    _attr_target_temperature_step = 1

    def __init__(self, coordinator: TclUdpDataUpdateCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._attr_name = "TCL Air Conditioner"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_climate"

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.coordinator.data and "current_temp" in self.coordinator.data:
            return float(self.coordinator.data["current_temp"])
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        if self.coordinator.data and "target_temp" in self.coordinator.data:
            return float(self.coordinator.data["target_temp"])
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        if self.coordinator.data and "power" in self.coordinator.data:
            return HVACMode.COOL if self.coordinator.data["power"] else HVACMode.OFF
        return HVACMode.OFF

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            LOGGER.debug("Setting temperature to %s", temperature)
            client = self.coordinator.config_entry.runtime_data.client
            await client.async_set_temperature(int(temperature))
            # Optimistically update state
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        LOGGER.debug("Setting HVAC mode to %s", hvac_mode)
        power_on = hvac_mode != HVACMode.OFF
        client = self.coordinator.config_entry.runtime_data.client
        await client.async_set_power(power_on=power_on)
        # Optimistically update state
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn on the AC."""
        await self.async_set_hvac_mode(HVACMode.COOL)

    async def async_turn_off(self) -> None:
        """Turn off the AC."""
        await self.async_set_hvac_mode(HVACMode.OFF)
