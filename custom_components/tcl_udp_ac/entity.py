"""TclUdpEntity class."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .config_settings import entry_value
from .const import (
    CONF_CLOUD_TID,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_NAME,
    CONF_DEVICE_ROOM,
)
from .coordinator import TclUdpDataUpdateCoordinator
from .device_state import DeviceState


class TclUdpEntity(CoordinatorEntity[TclUdpDataUpdateCoordinator]):
    """TclUdpEntity class."""

    def __init__(self, coordinator: TclUdpDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        device_id = self._device_identifier()
        entry = coordinator.config_entry
        self._attr_has_entity_name = True
        self._attr_unique_id = device_id
        device_info = DeviceInfo(
            identifiers={
                (
                    coordinator.config_entry.domain,
                    device_id,
                ),
            },
            name=entry_value(entry, CONF_DEVICE_NAME, None)
            or getattr(entry, "title", None)
            or "TCL Air Conditioner",
            manufacturer="TCL",
            model=entry_value(entry, CONF_DEVICE_MODEL, None) or "UDP AC",
        )
        room = entry_value(entry, CONF_DEVICE_ROOM, None)
        if room:
            device_info["suggested_area"] = room
        self._attr_device_info = device_info

    def _state_snapshot(self) -> DeviceState | None:
        """Read one detached snapshot from the device session when available."""
        runtime = getattr(self.coordinator.config_entry, "runtime_data", None)
        session = getattr(runtime, "session", None)
        return session.state_snapshot() if session is not None else None

    def _reported_state(self) -> dict[str, Any]:
        """Keep expired or derived fields out of physical entity feedback."""
        snapshot = self._state_snapshot()
        if snapshot is not None:
            return snapshot.fresh_values(time.monotonic())
        return dict(self.coordinator.data or {})

    def _observation_attributes(self, key: str) -> dict[str, str | None] | None:
        """Expose receipt provenance independently of HA publication time."""
        snapshot = self._state_snapshot()
        if snapshot is None:
            return None
        observation = snapshot.observations.get(key)
        return {
            "observed_at": snapshot.observed_at(key),
            "observation_source": observation.source.value
            if observation is not None
            else None,
        }

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
