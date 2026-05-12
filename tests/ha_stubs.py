"""Small Home Assistant stubs for unit tests.

These stubs are intentionally minimal. They let tests import the custom
integration entity modules without requiring Home Assistant as a test
dependency.
"""

from __future__ import annotations

import enum
import sys
import types


def install_homeassistant_stubs() -> None:
    """Install minimal Home Assistant modules into sys.modules."""
    if "homeassistant" in sys.modules:
        return

    ha = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    climate = types.ModuleType("homeassistant.components.climate")
    sensor = types.ModuleType("homeassistant.components.sensor")
    switch = types.ModuleType("homeassistant.components.switch")
    config_entries = types.ModuleType("homeassistant.config_entries")
    const = types.ModuleType("homeassistant.const")
    exceptions = types.ModuleType("homeassistant.exceptions")
    helpers = types.ModuleType("homeassistant.helpers")
    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
    entity = types.ModuleType("homeassistant.helpers.entity")
    loader = types.ModuleType("homeassistant.loader")

    class HVACMode(enum.StrEnum):
        OFF = "off"
        AUTO = "auto"
        COOL = "cool"
        DRY = "dry"
        FAN_ONLY = "fan_only"
        HEAT = "heat"

    class HVACAction(enum.StrEnum):
        OFF = "off"
        IDLE = "idle"
        COOLING = "cooling"
        HEATING = "heating"
        DRYING = "drying"
        FAN = "fan"

    class ClimateEntityFeature(enum.IntFlag):
        TARGET_TEMPERATURE = 1
        TURN_ON = 2
        TURN_OFF = 4
        FAN_MODE = 8
        SWING_MODE = 16

    class UnitOfTemperature(enum.StrEnum):
        CELSIUS = "°C"
        FAHRENHEIT = "°F"

    class Platform(enum.StrEnum):
        CLIMATE = "climate"
        SWITCH = "switch"
        SENSOR = "sensor"

    class EntityCategory(enum.StrEnum):
        CONFIG = "config"

    class ClimateEntity:
        entity_id = "climate.tcl_air_conditioner"

    class SensorEntity:
        entity_id = "sensor.tcl_ac_outdoor_temperature"

    class SwitchEntity:
        entity_id = "switch.tcl_ac_power"

    class CoordinatorEntity:
        @classmethod
        def __class_getitem__(cls, _item):
            return cls

        def __init__(self, coordinator):
            self.coordinator = coordinator

    class DataUpdateCoordinator:
        def __init__(self, **kwargs):
            self.config_entry = kwargs.get("config_entry")
            self.data = None

        async def async_config_entry_first_refresh(self):
            self.data = await self._async_update_data()

        def async_set_updated_data(self, data):
            self.data = data

    class UpdateFailed(Exception):
        pass

    class ConfigEntryNotReady(Exception):
        pass

    class HomeAssistantError(Exception):
        pass

    class SensorDeviceClass(enum.StrEnum):
        TEMPERATURE = "temperature"

    class SensorStateClass(enum.StrEnum):
        MEASUREMENT = "measurement"

    class DeviceInfo(dict):
        pass

    climate.FAN_AUTO = "auto"
    climate.FAN_HIGH = "high"
    climate.FAN_LOW = "low"
    climate.FAN_MEDIUM = "medium"
    climate.SWING_BOTH = "both"
    climate.SWING_HORIZONTAL = "horizontal"
    climate.SWING_OFF = "off"
    climate.SWING_VERTICAL = "vertical"
    climate.ClimateEntity = ClimateEntity
    climate.ClimateEntityFeature = ClimateEntityFeature
    climate.HVACAction = HVACAction
    climate.HVACMode = HVACMode

    sensor.SensorDeviceClass = SensorDeviceClass
    sensor.SensorEntity = SensorEntity
    sensor.SensorStateClass = SensorStateClass

    switch.SwitchEntity = SwitchEntity

    const.ATTR_TEMPERATURE = "temperature"
    const.Platform = Platform
    const.UnitOfTemperature = UnitOfTemperature

    config_entries.ConfigEntry = object
    exceptions.ConfigEntryNotReady = ConfigEntryNotReady
    exceptions.HomeAssistantError = HomeAssistantError
    aiohttp_client.async_get_clientsession = lambda _hass: None
    entity.EntityCategory = EntityCategory
    device_registry.DeviceInfo = DeviceInfo
    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator.CoordinatorEntity = CoordinatorEntity
    update_coordinator.UpdateFailed = UpdateFailed
    loader.async_get_loaded_integration = lambda _hass, _domain: None

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.components"] = components
    sys.modules["homeassistant.components.climate"] = climate
    sys.modules["homeassistant.components.sensor"] = sensor
    sys.modules["homeassistant.components.switch"] = switch
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.const"] = const
    sys.modules["homeassistant.exceptions"] = exceptions
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client
    sys.modules["homeassistant.helpers.device_registry"] = device_registry
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator
    sys.modules["homeassistant.helpers.entity"] = entity
    sys.modules["homeassistant.loader"] = loader
