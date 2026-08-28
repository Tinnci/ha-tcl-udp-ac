"""Per-entry facade for account-scoped credential maintenance."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, TypeVar

from homeassistant.exceptions import ConfigEntryAuthFailed

from .account_client import AccountClient
from .config_settings import AuthSettings, entry_value
from .const import CONF_CLOUD_TOKEN
from .credential_manager import CloudAuthRejectedError, CredentialManager

_T = TypeVar("_T")

if TYPE_CHECKING:
    import aiohttp
    from homeassistant.core import HomeAssistant

    from .api import TclUdpApiClient
    from .data import TclUdpConfigEntry


class TokenManager:
    """Expose credential maintenance for one config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TclUdpConfigEntry,
        client: TclUdpApiClient,
        session: aiohttp.ClientSession,
        *,
        credential_manager: CredentialManager | None = None,
    ) -> None:
        """Initialize the facade for one config entry and device client."""
        self._entry = entry
        self._client = client
        self._session = session
        self._credential_manager = credential_manager or CredentialManager(
            hass,
            session,
            account_client_factory=lambda settings: self._account_client(settings),
        )

    def _account_client(self, settings: AuthSettings) -> AccountClient:
        return AccountClient(
            self._session,
            base_url=settings.base_url,
            app_id=settings.app_id,
            app_secret=settings.app_secret,
            tenant_id=settings.tenant_id,
            cloud_base_url=settings.cloud_base_url,
        )

    async def async_ensure_fresh_token(
        self,
        *,
        force: bool = False,
        rejected_token: str | None = None,
    ) -> str | None:
        """Ensure this entry has a fresh token and hot-update its client."""
        previous = str(entry_value(self._entry, CONF_CLOUD_TOKEN, "") or "")
        token = await self._credential_manager.async_ensure_fresh(
            self._entry,
            force=force,
            rejected_token=rejected_token,
            now=time.time(),
        )
        if token and token != previous:
            self._client.update_cloud_token(token)
        return token

    async def async_authenticated_request(
        self, operation: Callable[[], Awaitable[_T]]
    ) -> _T:
        """Run one cloud request with freshness and one auth-only retry."""
        await self.async_ensure_fresh_token()
        rejected_token = str(entry_value(self._entry, CONF_CLOUD_TOKEN, "") or "")
        try:
            return await operation()
        except CloudAuthRejectedError:
            await self.async_ensure_fresh_token(
                force=True,
                rejected_token=rejected_token,
            )
        try:
            return await operation()
        except CloudAuthRejectedError as exc:
            msg = "TCL cloud authentication was rejected after token refresh"
            raise ConfigEntryAuthFailed(msg) from exc
