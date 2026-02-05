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
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TclUdpApiClient
from .const import (
    CONF_ACCOUNT,
    CONF_ACTION_JID,
    CONF_ACTION_SOURCE,
    CONF_CLOUD_ACCEPT,
    CONF_CLOUD_ACCEPT_ENCODING,
    CONF_CLOUD_ACCEPT_LANGUAGE,
    CONF_CLOUD_APP_BUILD_VERSION,
    CONF_CLOUD_APP_PACKAGE,
    CONF_CLOUD_APP_VERSION,
    CONF_CLOUD_BRAND,
    CONF_CLOUD_BASE_URL,
    CONF_CLOUD_CHANNEL,
    CONF_CLOUD_CONTROL,
    CONF_CLOUD_ENABLED,
    CONF_CLOUD_FROM,
    CONF_CLOUD_ORIGIN,
    CONF_CLOUD_PLATFORM,
    CONF_CLOUD_SDK_VERSION,
    CONF_CLOUD_SYSTEM_VERSION,
    CONF_CLOUD_T_APP_VERSION,
    CONF_CLOUD_T_PLATFORM_TYPE,
    CONF_CLOUD_T_STORE_UUID,
    CONF_CLOUD_TID,
    CONF_CLOUD_TOKEN,
    CONF_CLOUD_TO,
    CONF_CLOUD_USER_AGENT,
    CONF_CLOUD_X_REQUESTED_WITH,
    DEFAULT_ACCOUNT,
    DEFAULT_ACTION_JID,
    DEFAULT_ACTION_SOURCE,
    DEFAULT_CLOUD_ACCEPT,
    DEFAULT_CLOUD_ACCEPT_ENCODING,
    DEFAULT_CLOUD_ACCEPT_LANGUAGE,
    DEFAULT_CLOUD_APP_BUILD_VERSION,
    DEFAULT_CLOUD_APP_PACKAGE,
    DEFAULT_CLOUD_APP_VERSION,
    DEFAULT_CLOUD_BRAND,
    DEFAULT_CLOUD_BASE_URL,
    DEFAULT_CLOUD_FROM,
    DEFAULT_CLOUD_CHANNEL,
    DEFAULT_CLOUD_CONTROL,
    DEFAULT_CLOUD_ENABLED,
    DEFAULT_CLOUD_ORIGIN,
    DEFAULT_CLOUD_PLATFORM,
    DEFAULT_CLOUD_SDK_VERSION,
    DEFAULT_CLOUD_SYSTEM_VERSION,
    DEFAULT_CLOUD_T_APP_VERSION,
    DEFAULT_CLOUD_T_PLATFORM_TYPE,
    DEFAULT_CLOUD_TID,
    DEFAULT_CLOUD_TO,
    DEFAULT_CLOUD_TOKEN,
    DEFAULT_CLOUD_T_STORE_UUID,
    DEFAULT_CLOUD_USER_AGENT,
    DEFAULT_CLOUD_X_REQUESTED_WITH,
    DOMAIN,
    LOGGER,
)
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
    cloud_enabled = entry.options.get(
        CONF_CLOUD_ENABLED, entry.data.get(CONF_CLOUD_ENABLED, DEFAULT_CLOUD_ENABLED)
    )
    cloud_tid = entry.options.get(
        CONF_CLOUD_TID, entry.data.get(CONF_CLOUD_TID, DEFAULT_CLOUD_TID)
    )
    cloud_token = entry.options.get(
        CONF_CLOUD_TOKEN, entry.data.get(CONF_CLOUD_TOKEN, DEFAULT_CLOUD_TOKEN)
    )
    cloud_from = entry.options.get(
        CONF_CLOUD_FROM, entry.data.get(CONF_CLOUD_FROM, DEFAULT_CLOUD_FROM)
    )
    cloud_to = entry.options.get(
        CONF_CLOUD_TO, entry.data.get(CONF_CLOUD_TO, DEFAULT_CLOUD_TO)
    )
    cloud_base_url = entry.options.get(
        CONF_CLOUD_BASE_URL,
        entry.data.get(CONF_CLOUD_BASE_URL, DEFAULT_CLOUD_BASE_URL),
    )
    cloud_control = entry.options.get(
        CONF_CLOUD_CONTROL, entry.data.get(CONF_CLOUD_CONTROL, DEFAULT_CLOUD_CONTROL)
    )
    cloud_user_agent = entry.options.get(
        CONF_CLOUD_USER_AGENT,
        entry.data.get(CONF_CLOUD_USER_AGENT, DEFAULT_CLOUD_USER_AGENT),
    )
    cloud_platform = entry.options.get(
        CONF_CLOUD_PLATFORM,
        entry.data.get(CONF_CLOUD_PLATFORM, DEFAULT_CLOUD_PLATFORM),
    )
    cloud_app_package = entry.options.get(
        CONF_CLOUD_APP_PACKAGE,
        entry.data.get(CONF_CLOUD_APP_PACKAGE, DEFAULT_CLOUD_APP_PACKAGE),
    )
    cloud_system_version = entry.options.get(
        CONF_CLOUD_SYSTEM_VERSION,
        entry.data.get(CONF_CLOUD_SYSTEM_VERSION, DEFAULT_CLOUD_SYSTEM_VERSION),
    )
    cloud_brand = entry.options.get(
        CONF_CLOUD_BRAND,
        entry.data.get(CONF_CLOUD_BRAND, DEFAULT_CLOUD_BRAND),
    )
    cloud_app_version = entry.options.get(
        CONF_CLOUD_APP_VERSION,
        entry.data.get(CONF_CLOUD_APP_VERSION, DEFAULT_CLOUD_APP_VERSION),
    )
    cloud_sdk_version = entry.options.get(
        CONF_CLOUD_SDK_VERSION,
        entry.data.get(CONF_CLOUD_SDK_VERSION, DEFAULT_CLOUD_SDK_VERSION),
    )
    cloud_channel = entry.options.get(
        CONF_CLOUD_CHANNEL,
        entry.data.get(CONF_CLOUD_CHANNEL, DEFAULT_CLOUD_CHANNEL),
    )
    cloud_app_build_version = entry.options.get(
        CONF_CLOUD_APP_BUILD_VERSION,
        entry.data.get(CONF_CLOUD_APP_BUILD_VERSION, DEFAULT_CLOUD_APP_BUILD_VERSION),
    )
    cloud_t_app_version = entry.options.get(
        CONF_CLOUD_T_APP_VERSION,
        entry.data.get(CONF_CLOUD_T_APP_VERSION, DEFAULT_CLOUD_T_APP_VERSION),
    )
    cloud_t_platform_type = entry.options.get(
        CONF_CLOUD_T_PLATFORM_TYPE,
        entry.data.get(CONF_CLOUD_T_PLATFORM_TYPE, DEFAULT_CLOUD_T_PLATFORM_TYPE),
    )
    cloud_t_store_uuid = entry.options.get(
        CONF_CLOUD_T_STORE_UUID,
        entry.data.get(CONF_CLOUD_T_STORE_UUID, DEFAULT_CLOUD_T_STORE_UUID),
    )
    cloud_origin = entry.options.get(
        CONF_CLOUD_ORIGIN,
        entry.data.get(CONF_CLOUD_ORIGIN, DEFAULT_CLOUD_ORIGIN),
    )
    cloud_x_requested_with = entry.options.get(
        CONF_CLOUD_X_REQUESTED_WITH,
        entry.data.get(CONF_CLOUD_X_REQUESTED_WITH, DEFAULT_CLOUD_X_REQUESTED_WITH),
    )
    cloud_accept = entry.options.get(
        CONF_CLOUD_ACCEPT,
        entry.data.get(CONF_CLOUD_ACCEPT, DEFAULT_CLOUD_ACCEPT),
    )
    cloud_accept_encoding = entry.options.get(
        CONF_CLOUD_ACCEPT_ENCODING,
        entry.data.get(CONF_CLOUD_ACCEPT_ENCODING, DEFAULT_CLOUD_ACCEPT_ENCODING),
    )
    cloud_accept_language = entry.options.get(
        CONF_CLOUD_ACCEPT_LANGUAGE,
        entry.data.get(CONF_CLOUD_ACCEPT_LANGUAGE, DEFAULT_CLOUD_ACCEPT_LANGUAGE),
    )

    # Create API client
    session = async_get_clientsession(hass)
    client = TclUdpApiClient(
        action_jid=action_jid,
        action_source=action_source,
        account=account,
        session=session,
        cloud_enabled=cloud_enabled,
        cloud_tid=cloud_tid,
        cloud_token=cloud_token,
        cloud_from=cloud_from,
        cloud_to=cloud_to,
        cloud_base_url=cloud_base_url,
        cloud_control=cloud_control,
        cloud_user_agent=cloud_user_agent,
        cloud_platform=cloud_platform,
        cloud_app_package=cloud_app_package,
        cloud_system_version=cloud_system_version,
        cloud_brand=cloud_brand,
        cloud_app_version=cloud_app_version,
        cloud_sdk_version=cloud_sdk_version,
        cloud_channel=cloud_channel,
        cloud_app_build_version=cloud_app_build_version,
        cloud_t_app_version=cloud_t_app_version,
        cloud_t_platform_type=cloud_t_platform_type,
        cloud_t_store_uuid=cloud_t_store_uuid,
        cloud_origin=cloud_origin,
        cloud_x_requested_with=cloud_x_requested_with,
        cloud_accept=cloud_accept,
        cloud_accept_encoding=cloud_accept_encoding,
        cloud_accept_language=cloud_accept_language,
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
