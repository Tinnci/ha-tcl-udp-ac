"""TclUdpEntity class."""

from __future__ import annotations

import copy
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later
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

REPORT_INTERVAL = 120.0
_RECEIPT_ATTRIBUTES = frozenset(
    {
        "observed_at",
        "hvac_mode_observed_at",
        "hvac_action_observed_at",
        "current_temperature_observed_at",
        "current_humidity_observed_at",
    }
)


class TclUdpEntity(CoordinatorEntity[TclUdpDataUpdateCoordinator]):
    """TclUdpEntity class."""

    def __init__(self, coordinator: TclUdpDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._published_state: tuple | None = None
        self._published_at = 0.0
        self._publish_unsub: Callable[[], None] | None = None
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

    def _publication_state(self) -> tuple:
        """Compare all entity values while retaining receipt times in published states."""
        attrs = {**(self.state_attributes or {}), **(self.extra_state_attributes or {})}
        return (
            self.available,
            self.state,
            {
                key: value
                for key, value in attrs.items()
                if key not in _RECEIPT_ATTRIBUTES
            },
        )

    async def async_added_to_hass(self) -> None:
        """Start publication timing from the first registered state."""
        await super().async_added_to_hass()
        self._published_state = copy.deepcopy(self._publication_state())
        self._published_at = time.monotonic()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel pending publication before removing the entity."""
        if self._publish_unsub is not None:
            self._publish_unsub()
            self._publish_unsub = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Coalesce duplicate entity reports without delaying command reconciliation."""
        elapsed = time.monotonic() - self._published_at
        if (
            self._publication_state() != self._published_state
            or elapsed >= REPORT_INTERVAL
        ):
            self._publish_report()
        elif self._publish_unsub is None:
            self._publish_unsub = async_call_later(
                self.hass, REPORT_INTERVAL - elapsed, self._publish_report
            )

    @callback
    def _publish_report(self, _now: datetime | None = None) -> None:
        if self._publish_unsub is not None:
            self._publish_unsub()
            self._publish_unsub = None
        # Use the latest snapshot's receipt times, never the publication clock.
        self._published_state = copy.deepcopy(self._publication_state())
        self._published_at = time.monotonic()
        self.async_write_ha_state()

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
