"""
Custom integration to integrate tcl_udp_ac with Home Assistant.

For more details about this integration, please refer to
https://github.com/Tinnci/ha-tcl-udp-ac
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.loader import async_get_loaded_integration

from .api import TclUdpApiClient
from .const import DOMAIN, LOGGER
from .coordinator import TclUdpDataUpdateCoordinator
from .data import TclUdpData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import TclUdpConfigEntry

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SWITCH,
    Platform.SENSOR,
]

from .const import (
    CONF_ACCOUNT,
    CONF_ACTION_JID,
    CONF_ACTION_SOURCE,
    DEFAULT_ACCOUNT,
    DEFAULT_ACTION_JID,
    DEFAULT_ACTION_SOURCE,
)


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
        # For push-based updates, we set a long interval as backup
        update_interval=timedelta(minutes=30),
    )

    # Get config or options, falling back to defaults
    action_jid = entry.options.get(
        CONF_ACTION_JID, entry.data.get(CONF_ACTION_JID, DEFAULT_ACTION_JID)
    )
    action_source = entry.options.get(
        CONF_ACTION_SOURCE,
        entry.data.get(CONF_ACTION_SOURCE, DEFAULT_ACTION_SOURCE),
    )
    account = entry.options.get(
        CONF_ACCOUNT, entry.data.get(CONF_ACCOUNT, DEFAULT_ACCOUNT)
    )

    # Create API client
    client = TclUdpApiClient(
        action_jid=action_jid,
        action_source=action_source,
        account=account,
    )

    entry.runtime_data = TclUdpData(
        client=client,
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # Start UDP listener with callback to coordinator
    await client.async_start_listener(coordinator.async_handle_status_update)

    # Trigger active discovery
    # This sends a broadcast query so we don't have to wait for the next spontaneous heartbeat
    await client.async_send_discovery()

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: TclUdpConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    # Stop UDP listener
    await entry.runtime_data.client.async_close()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: TclUdpConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
