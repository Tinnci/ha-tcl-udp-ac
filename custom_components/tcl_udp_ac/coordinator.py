"""DataUpdateCoordinator for tcl_udp_ac."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
        runtime = self.config_entry.runtime_data
        client = runtime.client
        token_manager = getattr(runtime, "token_manager", None)
        if client.cloud_enabled and token_manager is not None:
            # Refresh the cloud token if near expiry; raises ConfigEntryAuthFailed
            # when reauth is required (HA then prompts the user to log in again).
            await token_manager.async_ensure_fresh_token()
        try:
            await client.async_request_status()
            if client.cloud_enabled:
                await client.async_fetch_cloud_status()
            status = client.get_last_status()
        except TclUdpApiClientError:
            if client.cloud_enabled:
                await client.async_fetch_cloud_status()
            status = client.get_last_status()

        if not status:
            raise UpdateFailed("No status received from TCL UDP AC")
        return status

    async def async_handle_status_update(self, status: dict[str, Any]) -> None:
        """Handle status update from UDP broadcast."""
        # Update coordinator data and notify listeners
        self.async_set_updated_data(status)
