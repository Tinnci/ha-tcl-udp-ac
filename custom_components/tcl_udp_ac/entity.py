"""TclUdpEntity class."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CLOUD_TID
from .coordinator import TclUdpDataUpdateCoordinator


class TclUdpEntity(CoordinatorEntity[TclUdpDataUpdateCoordinator]):
    """TclUdpEntity class."""

    def __init__(self, coordinator: TclUdpDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        device_id = self._device_identifier()
        self._attr_has_entity_name = True
        self._attr_unique_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    coordinator.config_entry.domain,
                    device_id,
                ),
            },
            name="TCL Air Conditioner",
            manufacturer="TCL",
            model="UDP AC",
        )

    def _device_identifier(self) -> str:
        """Return the most stable known device identifier for registry IDs."""
        entry = self.coordinator.config_entry
        for source in (getattr(entry, "options", {}), getattr(entry, "data", {})):
            value = source.get(CONF_CLOUD_TID)
            if value:
                return str(value)

        data = self.coordinator.data or {}
        for key in ("device_id", "mac", "device_mac"):
            value = data.get(key)
            if value:
                return str(value)

        return str(entry.entry_id)

    def _entity_unique_id(self, suffix: str) -> str:
        """Build a stable unique ID for an entity under this device."""
        return f"{self._device_identifier()}_{suffix}"
