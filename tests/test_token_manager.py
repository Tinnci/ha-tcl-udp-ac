"""Tests for the cloud token lifecycle manager."""

from __future__ import annotations

import asyncio
import base64
import json
import unittest
from types import SimpleNamespace

from tests.ha_stubs import install_homeassistant_stubs
from tests.test_protocol_commands import load_integration_module

install_homeassistant_stubs()


def _jwt(exp: int, iat: int) -> str:
    body = (
        base64.urlsafe_b64encode(json.dumps({"exp": exp, "iat": iat}).encode())
        .decode()
        .rstrip("=")
    )
    return f"hdr.{body}.sig"


class FakeConfigEntries:
    """Records async_update_entry calls."""

    def __init__(self) -> None:
        self.updated: dict | None = None

    def async_update_entry(self, entry, data=None) -> None:
        self.updated = data
        entry.data = data


class FakeEntry:
    def __init__(self, data: dict) -> None:
        self.data = data
        self.options: dict = {}


class FakeClient:
    def __init__(self) -> None:
        self.token_updated: str | None = None

    def update_cloud_token(self, token: str) -> None:
        self.token_updated = token


class FakeAccountClient:
    def __init__(self, tokens=None, error=None) -> None:
        self._tokens = tokens
        self._error = error
        self.called = False

    async def async_refresh(self, refresh_token, account_id):  # noqa: ARG002
        self.called = True
        if self._error:
            raise self._error
        return self._tokens


def _build_manager(entry_data, account_client):
    mod = load_integration_module("token_manager")
    hass = SimpleNamespace(config_entries=FakeConfigEntries())
    entry = FakeEntry(entry_data)
    client = FakeClient()
    tm = mod.TokenManager(hass=hass, entry=entry, client=client, session=object())
    # Inject the fake account client.
    tm._account_client = lambda: account_client  # noqa: SLF001
    return mod, tm, hass, entry, client


class TokenManagerTest(unittest.TestCase):
    """TokenManager refreshes, persists, and signals reauth correctly."""

    def setUp(self) -> None:
        self.now = 1_800_000_000
        self.account_mod = load_integration_module("account_client")

    def test_no_refresh_token_is_noop(self) -> None:
        _mod, tm, _hass, _entry, client = _build_manager(
            {"cloud_access_token": "x", "cloud_refresh_token": ""},
            FakeAccountClient(),
        )
        asyncio.run(tm.async_ensure_fresh_token())
        self.assertIsNone(client.token_updated)

    def test_fresh_token_skips_refresh(self) -> None:
        iat = self.now - 100
        exp = self.now + 30 * 86400
        acct = FakeAccountClient()
        _mod, tm, _hass, _entry, _client = _build_manager(
            {
                "cloud_access_token": _jwt(exp, iat),
                "cloud_refresh_token": _jwt(exp + 1000, iat),
                "cloud_account_id": "1",
            },
            acct,
        )
        # Patch time within the module.
        tm_mod = load_integration_module("token_manager")
        original = tm_mod.time.time
        tm_mod.time.time = lambda: self.now
        try:
            asyncio.run(tm.async_ensure_fresh_token())
        finally:
            tm_mod.time.time = original
        self.assertFalse(acct.called)

    def test_expired_access_triggers_refresh_and_persist(self) -> None:
        # Access token past 70% of life -> refresh.
        iat = self.now - 29 * 86400
        exp = self.now + 1 * 86400  # ~97% through life
        new_tokens = self.account_mod.TclTokens(
            access_token="new.access", refresh_token="new.refresh", account_id="1"
        )
        acct = FakeAccountClient(tokens=new_tokens)
        tm_mod, tm, hass, _entry, client = _build_manager(
            {
                "cloud_access_token": _jwt(exp, iat),
                "cloud_refresh_token": _jwt(self.now + 60 * 86400, iat),
                "cloud_account_id": "1",
            },
            acct,
        )
        original = tm_mod.time.time
        tm_mod.time.time = lambda: self.now
        try:
            asyncio.run(tm.async_ensure_fresh_token())
        finally:
            tm_mod.time.time = original
        self.assertTrue(acct.called)
        self.assertEqual(client.token_updated, "new.access")
        self.assertEqual(
            hass.config_entries.updated["cloud_access_token"], "new.access"
        )
        self.assertEqual(
            hass.config_entries.updated["cloud_refresh_token"], "new.refresh"
        )

    def test_dead_refresh_token_raises_auth_failed(self) -> None:
        from homeassistant.exceptions import ConfigEntryAuthFailed

        iat = self.now - 70 * 86400
        tm_mod, tm, _hass, _entry, _client = _build_manager(
            {
                "cloud_access_token": _jwt(self.now - 86400, iat),
                "cloud_refresh_token": _jwt(self.now - 100, iat),  # already expired
                "cloud_account_id": "1",
            },
            FakeAccountClient(),
        )
        original = tm_mod.time.time
        tm_mod.time.time = lambda: self.now
        try:
            with self.assertRaises(ConfigEntryAuthFailed):
                asyncio.run(tm.async_ensure_fresh_token())
        finally:
            tm_mod.time.time = original

    def test_transient_refresh_error_is_swallowed(self) -> None:
        iat = self.now - 29 * 86400
        exp = self.now + 86400
        acct = FakeAccountClient(error=self.account_mod.TclAccountError("network"))
        tm_mod, tm, _hass, _entry, client = _build_manager(
            {
                "cloud_access_token": _jwt(exp, iat),
                "cloud_refresh_token": _jwt(self.now + 60 * 86400, iat),
                "cloud_account_id": "1",
            },
            acct,
        )
        original = tm_mod.time.time
        tm_mod.time.time = lambda: self.now
        try:
            # Should not raise — transient errors keep the old token.
            asyncio.run(tm.async_ensure_fresh_token())
        finally:
            tm_mod.time.time = original
        self.assertIsNone(client.token_updated)


if __name__ == "__main__":
    unittest.main()
