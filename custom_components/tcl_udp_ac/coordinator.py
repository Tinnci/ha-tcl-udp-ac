"""DataUpdateCoordinator for tcl_udp_ac."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import TclUdpApiClientError

if TYPE_CHECKING:
    from .data import TclUdpConfigEntry


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class TclUdpDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: TclUdpConfigEntry

    async def _async_update_data(self) -> Any:
        """Update data via library."""
        # For UDP push-based updates, we return the last known status
        # But we also trigger a SyncStatusReq as a manual poll fallback
        try:
            await self.config_entry.runtime_data.client.async_request_status()
            if self.config_entry.runtime_data.client.cloud_enabled:
                await self.config_entry.runtime_data.client.async_fetch_cloud_status()
            return self.config_entry.runtime_data.client.get_last_status()
        except TclUdpApiClientError:
            if self.config_entry.runtime_data.client.cloud_enabled:
                await self.config_entry.runtime_data.client.async_fetch_cloud_status()
            return self.config_entry.runtime_data.client.get_last_status()

    async def async_handle_status_update(self, status: dict[str, Any]) -> None:
        """Handle status update from UDP broadcast."""
        # Update coordinator data and notify listeners
        self.async_set_updated_data(status)
