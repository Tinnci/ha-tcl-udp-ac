"""Sensor platform for TCL UDP AC."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfTemperature, UnitOfTime
from homeassistant.helpers.entity import EntityCategory

from .config_settings import capabilities_for_entry
from .entity import TclUdpEntity
from .protocol_profiles import DiagnosticSensorCapability
from .temperature_validity import is_valid_outdoor_temperature

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
    capabilities = capabilities_for_entry(coordinator.config_entry)
    async_add_entities(
        [
            TclUdpOutdoorTempSensor(coordinator),
            TclUdpCurrentMonthEnergySensor(coordinator),
            TclUdpCurrentMonthRuntimeSensor(coordinator),
            *(
                TclUdpDiagnosticSensor(coordinator, capability)
                for capability in capabilities.diagnostic_sensors
            ),
        ]
    )


class TclUdpDiagnosticSensor(TclUdpEntity, SensorEntity):
    """One profile-described read-only diagnostic value."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: TclUdpDataUpdateCoordinator,
        capability: DiagnosticSensorCapability,
    ) -> None:
        """Initialize the diagnostic entity."""
        super().__init__(coordinator)
        self._capability = capability
        self._attr_translation_key = capability.translation_key
        self._attr_unique_id = self._entity_unique_id(capability.data_key)
        self._attr_icon = capability.icon
        self._attr_native_unit_of_measurement = capability.native_unit
        if capability.device_class:
            self._attr_device_class = SensorDeviceClass(capability.device_class)
        if capability.state_class:
            self._attr_state_class = SensorStateClass(capability.state_class)

    @property
    def available(self) -> bool:
        """Return true only after the cloud has reported this field."""
        return getattr(super(), "available", True) and self._capability.data_key in (
            self.coordinator.data or {}
        )

    @property
    def native_value(self) -> Any:
        """Return the normalized diagnostic value."""
        return (self.coordinator.data or {}).get(self._capability.data_key)


class TclUdpOutdoorTempSensor(TclUdpEntity, SensorEntity):
    """TCL UDP Outdoor Temperature Sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: TclUdpDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_translation_key = "outdoor_temperature"
        self._attr_unique_id = self._entity_unique_id("outdoor_temperature")

    @property
    def available(self) -> bool:
        """Return true if the outdoor temperature has a valid reading."""
        base_available = getattr(super(), "available", True)
        return base_available and self.native_value is not None

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data and "outdoor_temp" in self.coordinator.data:
            # Check for valid range, sometimes devices report placeholder values.
            val = float(self.coordinator.data["outdoor_temp"])
            if is_valid_outdoor_temperature(val):
                return val
        return None


class TclUdpCloudStatisticsSensor(TclUdpEntity, SensorEntity):
    """Base class for TCL+ cloud report statistics sensors."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def _statistics(self) -> dict | None:
        data = self.coordinator.data or {}
        stats = data.get("energy_statistics")
        if isinstance(stats, dict):
            return stats
        return None

    @property
    def available(self) -> bool:
        """Return true if the TCL+ report value is available."""
        base_available = getattr(super(), "available", True)
        return base_available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the report period used by TCL+ for this value."""
        stats = self._statistics()
        if not stats:
            return None
        attrs = {}
        if stats.get("period_start"):
            attrs["period_start"] = str(stats["period_start"])
        if stats.get("period_end"):
            attrs["period_end"] = str(stats["period_end"])
        return attrs or None

    @property
    def last_reset(self) -> datetime | None:
        """Return the TCL+ report period start as the statistics reset boundary."""
        stats = self._statistics()
        if not stats or not stats.get("period_start"):
            return None
        try:
            return datetime.fromisoformat(str(stats["period_start"])).replace(
                tzinfo=UTC
            )
        except ValueError:
            return None


class TclUdpCurrentMonthEnergySensor(TclUdpCloudStatisticsSensor):
    """TCL+ current-month reported electricity usage."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator: TclUdpDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_translation_key = "current_month_energy"
        self._attr_unique_id = self._entity_unique_id("current_month_energy")

    @property
    def native_value(self) -> float | None:
        """Return TCL+'s current-month kWh report value."""
        stats = self._statistics()
        if not stats:
            return None
        value = stats.get("energy_kwh")
        return float(value) if value is not None else None


class TclUdpCurrentMonthRuntimeSensor(TclUdpCloudStatisticsSensor):
    """TCL+ current-month reported running hours."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfTime.HOURS

    def __init__(self, coordinator: TclUdpDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_translation_key = "current_month_runtime"
        self._attr_unique_id = self._entity_unique_id("current_month_runtime")

    @property
    def native_value(self) -> float | None:
        """Return TCL+'s current-month runtime report value."""
        stats = self._statistics()
        if not stats:
            return None
        value = stats.get("running_hours")
        return float(value) if value is not None else None
