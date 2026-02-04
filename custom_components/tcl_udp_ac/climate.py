"""Climate platform for TCL UDP AC."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .const import (
    FAN_AUTO as TCL_FAN_AUTO,
)
from .const import (
    FAN_HIGH as TCL_FAN_HIGH,
)
from .const import (
    FAN_LOW as TCL_FAN_LOW,
)
from .const import (
    FAN_MIDDLE as TCL_FAN_MIDDLE,
)
from .const import (
    LOGGER,
)
from .const import (
    MODE_AUTO as TCL_MODE_AUTO,
)
from .const import (
    MODE_COOL as TCL_MODE_COOL,
)
from .const import (
    MODE_DEHUMI as TCL_MODE_DEHUMI,
)
from .const import (
    MODE_FAN as TCL_MODE_FAN,
)
from .const import (
    MODE_HEAT as TCL_MODE_HEAT,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import TclUdpDataUpdateCoordinator
    from .data import TclUdpConfigEntry

# Protocol mappings
# Fan Speed
FAN_MODE_MAP = {
    FAN_AUTO: TCL_FAN_AUTO,
    FAN_LOW: TCL_FAN_LOW,
    FAN_MEDIUM: TCL_FAN_MIDDLE,
    FAN_HIGH: TCL_FAN_HIGH,
}
FAN_MODE_MAP_REV = {v: k for k, v in FAN_MODE_MAP.items()}

# mode: HA Mode -> API String
HVAC_MODE_MAP = {
    HVACMode.AUTO: TCL_MODE_AUTO,
    HVACMode.COOL: TCL_MODE_COOL,
    HVACMode.DRY: TCL_MODE_DEHUMI,
    HVACMode.FAN_ONLY: TCL_MODE_FAN,
    HVACMode.HEAT: TCL_MODE_HEAT,
}
HVAC_MODE_MAP_REV = {v: k for k, v in HVAC_MODE_MAP.items()}


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
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
    )
    _attr_hvac_modes: ClassVar[list[HVACMode]] = [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.HEAT,
    ]
    _attr_fan_modes: ClassVar[list[str]] = [
        FAN_AUTO,
        FAN_LOW,
        FAN_MEDIUM,
        FAN_HIGH,
    ]
    _attr_swing_modes: ClassVar[list[str]] = [
        SWING_OFF,
        SWING_VERTICAL,
        SWING_HORIZONTAL,
        SWING_BOTH,
    ]
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
        data = self.coordinator.data
        if not data:
            return HVACMode.OFF

        # If power is off, return OFF
        if not data.get("power"):
            return HVACMode.OFF

        # Read mode from device
        mode_val = data.get("mode", MODE_COOL)  # Default to Cool if missing
        return HVAC_MODE_MAP_REV.get(mode_val, HVACMode.COOL)

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        data = self.coordinator.data
        if not data:
            return None
        speed_val = data.get("fan_speed", FAN_SPEED_AUTO)
        return FAN_MODE_MAP_REV.get(speed_val, FAN_AUTO)

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting."""
        data = self.coordinator.data
        if not data:
            return None

        swing_h = data.get("swing_h", False)
        swing_v = data.get("swing_v", False)

        if swing_h and swing_v:
            return SWING_BOTH
        if swing_h:
            return SWING_HORIZONTAL
        if swing_v:
            return SWING_VERTICAL
        return SWING_OFF

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            LOGGER.debug("Setting temperature to %s", temperature)
            client = self.coordinator.config_entry.runtime_data.client
            await client.async_set_temperature(int(temperature))
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        LOGGER.debug("Setting HVAC mode to %s", hvac_mode)
        client = self.coordinator.config_entry.runtime_data.client

        if hvac_mode == HVACMode.OFF:
            await client.async_set_power(power=False)
        else:
            # Ensure power is on
            if not self.coordinator.data.get("power"):
                await client.async_set_power(power=True)

            # Send mode command
            udp_mode = HVAC_MODE_MAP.get(hvac_mode)
            if udp_mode is not None:
                await client.async_set_mode(udp_mode)

        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        LOGGER.debug("Setting fan mode to %s", fan_mode)
        client = self.coordinator.config_entry.runtime_data.client

        speed_val = FAN_MODE_MAP.get(fan_mode)
        if speed_val is not None:
            await client.async_set_fan_speed(speed_val)
            await self.coordinator.async_request_refresh()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode."""
        LOGGER.debug("Setting swing mode to %s", swing_mode)
        client = self.coordinator.config_entry.runtime_data.client

        vertical = swing_mode in (SWING_VERTICAL, SWING_BOTH)
        horizontal = swing_mode in (SWING_HORIZONTAL, SWING_BOTH)

        await client.async_set_swing(vertical=vertical, horizontal=horizontal)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn on the AC."""
        # Restore last known mode or default to COOL
        await self.async_set_hvac_mode(HVACMode.COOL)

    async def async_turn_off(self) -> None:
        """Turn off the AC."""
        await self.async_set_hvac_mode(HVACMode.OFF)
