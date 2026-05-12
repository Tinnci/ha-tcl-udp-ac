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
    switch = types.ModuleType("homeassistant.components.switch")
    const = types.ModuleType("homeassistant.const")
    helpers = types.ModuleType("homeassistant.helpers")
    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
    entity = types.ModuleType("homeassistant.helpers.entity")

    class HVACMode(enum.StrEnum):
        OFF = "off"
        AUTO = "auto"
        COOL = "cool"
        DRY = "dry"
        FAN_ONLY = "fan_only"
        HEAT = "heat"

    class ClimateEntityFeature(enum.IntFlag):
        TARGET_TEMPERATURE = 1
        TURN_ON = 2
        TURN_OFF = 4
        FAN_MODE = 8
        SWING_MODE = 16

    class UnitOfTemperature(enum.StrEnum):
        CELSIUS = "°C"
        FAHRENHEIT = "°F"

    class EntityCategory(enum.StrEnum):
        CONFIG = "config"

    class ClimateEntity:
        entity_id = "climate.tcl_air_conditioner"

    class SwitchEntity:
        entity_id = "switch.tcl_ac_power"

    class CoordinatorEntity:
        @classmethod
        def __class_getitem__(cls, _item):
            return cls

        def __init__(self, coordinator):
            self.coordinator = coordinator

    class DataUpdateCoordinator:
        pass

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
    climate.HVACMode = HVACMode

    switch.SwitchEntity = SwitchEntity

    const.ATTR_TEMPERATURE = "temperature"
    const.UnitOfTemperature = UnitOfTemperature

    entity.EntityCategory = EntityCategory
    device_registry.DeviceInfo = DeviceInfo
    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator.CoordinatorEntity = CoordinatorEntity

    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.components"] = components
    sys.modules["homeassistant.components.climate"] = climate
    sys.modules["homeassistant.components.switch"] = switch
    sys.modules["homeassistant.const"] = const
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.device_registry"] = device_registry
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator
    sys.modules["homeassistant.helpers.entity"] = entity
