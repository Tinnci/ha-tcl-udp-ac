"""Read-only binary diagnostics for TCL protocol profiles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.entity import EntityCategory

from .config_settings import capabilities_for_entry
from .entity import TclUdpEntity
from .protocol_profiles import BinaryDiagnosticCapability

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
    """Set up profile-described binary diagnostics."""
    coordinator = entry.runtime_data.coordinator
    capabilities = capabilities_for_entry(coordinator.config_entry)
    async_add_entities(
        [
            TclUdpBinaryDiagnostic(coordinator, capability)
            for capability in capabilities.binary_diagnostics
        ]
    )


class TclUdpBinaryDiagnostic(TclUdpEntity, BinarySensorEntity):
    """One normalized boolean diagnostic."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: TclUdpDataUpdateCoordinator,
        capability: BinaryDiagnosticCapability,
    ) -> None:
        """Initialize the diagnostic entity."""
        super().__init__(coordinator)
        self._capability = capability
        self._attr_translation_key = capability.translation_key
        self._attr_unique_id = self._entity_unique_id(capability.data_key)
        self._attr_icon = capability.icon
        if capability.device_class:
            self._attr_device_class = BinarySensorDeviceClass(capability.device_class)

    @property
    def available(self) -> bool:
        """Return true only after the cloud has reported this field."""
        return (
            getattr(super(), "available", True)
            and self._capability.data_key in (self.coordinator.data or {})
        )

    @property
    def is_on(self) -> bool | None:
        """Return the normalized boolean state."""
        value = (self.coordinator.data or {}).get(self._capability.data_key)
        return bool(value) if value is not None else None
