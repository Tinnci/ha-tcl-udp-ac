"""
Custom integration to integrate tcl_udp_ac with Home Assistant.

For more details about this integration, please refer to
https://github.com/Tinnci/ha-tcl-udp-ac
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import TclUdpApiClient, TclUdpApiClientCommunicationError
from .config_settings import ConfigEntrySettings, reload_signature
from .const import DOMAIN, LOGGER
from .coordinator import TclUdpDataUpdateCoordinator
from .credential_manager import CredentialManager
from .data import TclUdpData
from .device_session import DeviceSession
from .integration_runtime import get_integration_runtime
from .token_manager import TokenManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import TclUdpConfigEntry

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SWITCH,
    Platform.SENSOR,
]
SCAN_INTERVAL = timedelta(minutes=1)


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: TclUdpConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    coordinator = TclUdpDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        config_entry=entry,
        # UDP push is primary, but some networks miss broadcasts. Keep a
        # practical backup poll so external app/remote changes do not leave
        # Home Assistant stale for a long time.
        update_interval=SCAN_INTERVAL,
    )
    coordinator.config_entry = entry

    settings = ConfigEntrySettings.from_entry(entry)
    integration_runtime = get_integration_runtime(hass)
    http_session = async_get_clientsession(hass)
    if integration_runtime.credential_manager is None:
        integration_runtime.credential_manager = CredentialManager(hass, http_session)
    client = TclUdpApiClient(
        session=http_session,
        udp_hub=integration_runtime.udp_hub,
        **settings.api_client_kwargs(),
    )
    device_session = DeviceSession(client)

    entry.runtime_data = TclUdpData(
        client=client,
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
        session=device_session,
        reload_signature=reload_signature(entry),
    )

    # Token manager handles cloud token auto-refresh when a refresh token is
    # configured (login flow). In manual-token mode it is a no-op.
    entry.runtime_data.token_manager = TokenManager(
        hass=hass,
        entry=entry,
        client=client,
        session=http_session,
        credential_manager=integration_runtime.credential_manager,
    )
    client.set_token_manager(entry.runtime_data.token_manager)

    try:
        # Start UDP listener with callback to coordinator
        await device_session.async_start_listener(
            coordinator.async_handle_status_update
        )

        # Trigger active discovery
        # This sends a broadcast query so we don't have to wait for the next
        # spontaneous heartbeat.
        await device_session.async_send_discovery()

        # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
        await coordinator.async_config_entry_first_refresh()
    except TclUdpApiClientCommunicationError as exception:
        await device_session.async_close()
        msg = "TCL UDP listener is not ready"
        raise ConfigEntryNotReady(msg) from exception

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: TclUdpConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        device = getattr(entry.runtime_data, "session", entry.runtime_data.client)
        await device.async_close()
    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant,
    entry: TclUdpConfigEntry,
) -> None:
    """Reload config entry."""
    runtime = getattr(entry, "runtime_data", None)
    if runtime is not None and runtime.reload_signature == reload_signature(entry):
        return
    await hass.config_entries.async_reload(entry.entry_id)
