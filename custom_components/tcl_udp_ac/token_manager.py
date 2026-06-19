"""
Token lifecycle manager.

Decides when the cloud access token needs refreshing (70%-of-lifetime rule),
performs the refresh against the TCL+ account API, persists the new tokens back
to the config entry, and updates the live API client. When refresh is not
possible (no/expired refresh token, or the refresh call is rejected), it raises
``ConfigEntryAuthFailed`` so Home Assistant surfaces a reauth prompt.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryAuthFailed

from .account_client import AccountClient, TclAccountAuthError, TclAccountError
from .config_settings import entry_value
from .const import (
    CONF_ACCOUNT_APP_ID,
    CONF_ACCOUNT_APP_SECRET,
    CONF_ACCOUNT_BASE_URL,
    CONF_ACCOUNT_TENANT_ID,
    CONF_CLOUD_ACCOUNT_ID,
    CONF_CLOUD_REFRESH_TOKEN,
    CONF_CLOUD_TOKEN,
    DEFAULT_ACCOUNT_APP_ID,
    DEFAULT_ACCOUNT_APP_SECRET,
    DEFAULT_ACCOUNT_BASE_URL,
    DEFAULT_ACCOUNT_TENANT_ID,
    LOGGER,
)
from .token_state import access_token_needs_refresh, refresh_token_expired

if TYPE_CHECKING:
    import aiohttp
    from homeassistant.core import HomeAssistant

    from .api import TclUdpApiClient
    from .data import TclUdpConfigEntry


class TokenManager:
    """Manages cloud token refresh and persistence for a config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TclUdpConfigEntry,
        client: TclUdpApiClient,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the token manager."""
        self._hass = hass
        self._entry = entry
        self._client = client
        self._session = session

    def _value(self, key: str, default: str) -> str:
        return entry_value(self._entry, key, default)

    def _account_client(self) -> AccountClient:
        return AccountClient(
            self._session,
            base_url=self._value(CONF_ACCOUNT_BASE_URL, DEFAULT_ACCOUNT_BASE_URL),
            app_id=self._value(CONF_ACCOUNT_APP_ID, DEFAULT_ACCOUNT_APP_ID),
            app_secret=self._value(CONF_ACCOUNT_APP_SECRET, DEFAULT_ACCOUNT_APP_SECRET),
            tenant_id=self._value(CONF_ACCOUNT_TENANT_ID, DEFAULT_ACCOUNT_TENANT_ID),
        )

    async def async_ensure_fresh_token(self) -> None:
        """
        Refresh the cloud token if it is near expiry.

        No-op when no refresh token is configured (manual-token mode), so users
        who paste a token by hand keep working exactly as before.
        """
        access_token = self._value(CONF_CLOUD_TOKEN, "")
        refresh_token = self._value(CONF_CLOUD_REFRESH_TOKEN, "")
        account_id = self._value(CONF_CLOUD_ACCOUNT_ID, "")

        if not refresh_token:
            # Manual-token mode: nothing to refresh with.
            return

        now = time.time()
        if access_token and not access_token_needs_refresh(access_token, now):
            return

        if refresh_token_expired(refresh_token, now):
            msg = "TCL refresh token expired; please log in again"
            raise ConfigEntryAuthFailed(msg)

        if not account_id:
            msg = "Missing TCL account id for token refresh"
            raise ConfigEntryAuthFailed(msg)

        account = self._account_client()
        try:
            tokens = await account.async_refresh(refresh_token, account_id)
        except TclAccountAuthError as exc:
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except TclAccountError as exc:
            # Transient/network error: don't force reauth, just log and keep the
            # current token (the cloud call will fall back to UDP on failure).
            LOGGER.warning("TCL token refresh failed: %s", exc)
            return

        self._persist_tokens(tokens.access_token, tokens.refresh_token, account_id)

    def _persist_tokens(
        self, access_token: str, refresh_token: str, account_id: str
    ) -> None:
        new_data = dict(self._entry.data)
        new_data[CONF_CLOUD_TOKEN] = access_token
        if refresh_token:
            new_data[CONF_CLOUD_REFRESH_TOKEN] = refresh_token
        new_data[CONF_CLOUD_ACCOUNT_ID] = account_id
        self._hass.config_entries.async_update_entry(self._entry, data=new_data)
        self._client.update_cloud_token(access_token)
        LOGGER.debug("Persisted refreshed TCL cloud token")
