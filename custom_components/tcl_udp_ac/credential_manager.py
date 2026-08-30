"""Account-scoped cloud credential refresh and persistence."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from homeassistant.exceptions import ConfigEntryAuthFailed

from .account_client import (
    AccountClient,
    TclAccountAuthError,
    TclAccountError,
    TclTokens,
)
from .config_settings import AuthSettings, entry_value
from .const import (
    CONF_CLOUD_ACCOUNT_ID,
    CONF_CLOUD_REFRESH_TOKEN,
    CONF_CLOUD_TOKEN,
    DOMAIN,
    LOGGER,
)
from .token_state import access_token_needs_refresh, refresh_token_expired


class CloudAuthRejectedError(Exception):
    """A cloud request was rejected specifically for authentication."""


class CredentialManager:
    """Maintain one refresh flow for every TCL account identity."""

    def __init__(
        self,
        hass: Any,
        session: Any,
        *,
        account_client_factory: Callable[[AuthSettings], AccountClient] | None = None,
    ) -> None:
        """Initialize account-scoped credential storage and refresh state."""
        self._hass = hass
        self._session = session
        self._locks: dict[str, asyncio.Lock] = {}
        self._account_clients: dict[AuthSettings, AccountClient] = {}
        self._account_client_factory = account_client_factory

    def _account_client(self, settings: AuthSettings) -> AccountClient:
        client = self._account_clients.get(settings)
        if client is not None:
            return client
        if self._account_client_factory is not None:
            client = self._account_client_factory(settings)
        else:
            client = AccountClient(
                self._session,
                base_url=settings.base_url,
                app_id=settings.app_id,
                app_secret=settings.app_secret,
                tenant_id=settings.tenant_id,
                cloud_base_url=settings.cloud_base_url,
            )
        self._account_clients[settings] = client
        return client

    @staticmethod
    def _value(entry: Any, key: str) -> str:
        return str(entry_value(entry, key, "") or "")

    def _entries(self, current_entry: Any) -> list[Any]:
        async_entries = getattr(self._hass.config_entries, "async_entries", None)
        if async_entries is None:
            return [current_entry]
        entries = list(async_entries(DOMAIN))
        if current_entry not in entries:
            entries.append(current_entry)
        return entries

    async def async_ensure_fresh(
        self,
        entry: Any,
        *,
        force: bool = False,
        rejected_token: str | None = None,
        now: float | None = None,
    ) -> str | None:
        """Return a usable access token, refreshing once per account as needed."""
        access_token = self._value(entry, CONF_CLOUD_TOKEN)
        refresh_token = self._value(entry, CONF_CLOUD_REFRESH_TOKEN)
        account_id = self._value(entry, CONF_CLOUD_ACCOUNT_ID)
        current_time = time.time() if now is None else now

        if not refresh_token:
            if force:
                msg = "Manual TCL cloud token was rejected; update authentication"
                raise ConfigEntryAuthFailed(msg)
            return access_token or None
        if (
            not force
            and access_token
            and not access_token_needs_refresh(access_token, current_time)
        ):
            return access_token
        if not account_id:
            msg = "Missing TCL account id for token refresh"
            raise ConfigEntryAuthFailed(msg)

        lock = self._locks.setdefault(account_id, asyncio.Lock())
        initial_access = access_token
        async with lock:
            access_token = self._value(entry, CONF_CLOUD_TOKEN)
            refresh_token = self._value(entry, CONF_CLOUD_REFRESH_TOKEN)
            current_account_id = self._value(entry, CONF_CLOUD_ACCOUNT_ID)
            if access_token != initial_access:
                return access_token or None
            if force and rejected_token is not None and access_token != rejected_token:
                return access_token or None
            if (
                not force
                and access_token
                and not access_token_needs_refresh(access_token, current_time)
            ):
                return access_token
            if refresh_token_expired(refresh_token, current_time):
                msg = "TCL refresh token expired; please log in again"
                raise ConfigEntryAuthFailed(msg)

            account = self._account_client(AuthSettings.from_entry(entry))
            try:
                tokens = await account.async_refresh(refresh_token, current_account_id)
            except TclAccountAuthError as exc:
                raise ConfigEntryAuthFailed(str(exc)) from exc
            except TclAccountError as exc:
                LOGGER.warning("TCL token refresh failed: %s", exc)
                if force:
                    # The cloud already rejected this access token. Retrying it
                    # after a temporary refresh outage would turn a network,
                    # rate-limit, or server failure into a false HA reauth.
                    raise
                return access_token or None

            await self.async_apply_tokens(
                entry,
                tokens,
                previous_account_id=current_account_id,
            )
            return tokens.access_token

    async def async_apply_tokens(
        self,
        entry: Any,
        tokens: TclTokens,
        *,
        previous_account_id: str | None = None,
    ) -> None:
        """Persist tokens to every entry for the account and hot-update runtimes."""
        old_account_id = previous_account_id or self._value(
            entry, CONF_CLOUD_ACCOUNT_ID
        )
        new_account_id = str(tokens.account_id or old_account_id)
        targets = [
            candidate
            for candidate in self._entries(entry)
            if candidate is entry
            or self._value(candidate, CONF_CLOUD_ACCOUNT_ID) == old_account_id
        ]
        for candidate in targets:
            new_data = dict(candidate.data)
            new_data[CONF_CLOUD_TOKEN] = tokens.access_token
            if tokens.refresh_token:
                new_data[CONF_CLOUD_REFRESH_TOKEN] = tokens.refresh_token
            if new_account_id:
                new_data[CONF_CLOUD_ACCOUNT_ID] = new_account_id
            self._hass.config_entries.async_update_entry(candidate, data=new_data)
            try:
                runtime = candidate.runtime_data
            except (AttributeError, RuntimeError):
                runtime = None
            device = getattr(runtime, "session", None)
            if device is not None:
                device.update_cloud_token(tokens.access_token)
        LOGGER.debug("Persisted TCL credentials for %d account entries", len(targets))
