"""Account-scoped cloud credential maintenance tests."""

from __future__ import annotations

import asyncio
import base64
import json
import unittest
from types import SimpleNamespace

from tests.ha_stubs import install_homeassistant_stubs
from tests.test_protocol_commands import load_integration_module

install_homeassistant_stubs()


def jwt(exp: int, iat: int) -> str:
    body = (
        base64.urlsafe_b64encode(json.dumps({"exp": exp, "iat": iat}).encode())
        .decode()
        .rstrip("=")
    )
    return f"hdr.{body}.sig"


class FakeSession:
    def __init__(self) -> None:
        self.tokens: list[str] = []

    def update_cloud_token(self, token: str) -> None:
        self.tokens.append(token)


class FakeEntry:
    def __init__(self, entry_id: str, data: dict, *, loaded: bool = True) -> None:
        self.entry_id = entry_id
        self.data = data
        self.options = {}
        self.domain = "tcl_udp_ac"
        self.runtime_data = (
            SimpleNamespace(session=FakeSession()) if loaded else None
        )


class FakeConfigEntries:
    def __init__(self, entries) -> None:
        self.entries = entries
        self.updates = []

    def async_entries(self, domain):
        return [entry for entry in self.entries if entry.domain == domain]

    def async_update_entry(self, entry, *, data=None):
        entry.data = data
        self.updates.append(entry.entry_id)


class FakeAccountClient:
    def __init__(self, tokens) -> None:
        self.tokens = tokens
        self.calls = 0

    async def async_refresh(self, _refresh_token, _account_id):
        self.calls += 1
        await asyncio.sleep(0)
        return self.tokens


class CredentialManagerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_integration_module("credential_manager")
        self.account = load_integration_module("account_client")
        self.now = 1_800_000_000

    def entry(self, entry_id, account_id="account-1", *, loaded=True):
        return FakeEntry(
            entry_id,
            {
                "cloud_access_token": jwt(self.now - 1, self.now - 100),
                "cloud_refresh_token": jwt(self.now + 1000, self.now - 100),
                "cloud_account_id": account_id,
            },
            loaded=loaded,
        )

    def test_same_account_concurrent_refresh_is_single_flight_and_synchronised(
        self,
    ) -> None:
        first = self.entry("first")
        second = self.entry("second", loaded=False)
        other = self.entry("other", "account-2")
        config_entries = FakeConfigEntries([first, second, other])
        hass = SimpleNamespace(config_entries=config_entries)
        tokens = self.account.TclTokens(
            "new-access", "new-refresh", "canonical-account"
        )
        account_client = FakeAccountClient(tokens)
        manager = self.mod.CredentialManager(
            hass,
            session=object(),
            account_client_factory=lambda _settings: account_client,
        )

        async def run_case():
            await asyncio.gather(
                manager.async_ensure_fresh(first, now=self.now),
                manager.async_ensure_fresh(second, now=self.now),
            )

        asyncio.run(run_case())

        self.assertEqual(account_client.calls, 1)
        for entry in (first, second):
            self.assertEqual(entry.data["cloud_access_token"], "new-access")
            self.assertEqual(entry.data["cloud_refresh_token"], "new-refresh")
            self.assertEqual(entry.data["cloud_account_id"], "canonical-account")
        self.assertEqual(first.runtime_data.session.tokens, ["new-access"])
        self.assertNotEqual(other.data["cloud_access_token"], "new-access")

    def test_force_refresh_skips_if_waiter_observes_new_access_token(self) -> None:
        entry = self.entry("first")
        config_entries = FakeConfigEntries([entry])
        hass = SimpleNamespace(config_entries=config_entries)
        tokens = self.account.TclTokens("new-access", "new-refresh", "account-1")
        account_client = FakeAccountClient(tokens)
        manager = self.mod.CredentialManager(
            hass,
            session=object(),
            account_client_factory=lambda _settings: account_client,
        )
        rejected = entry.data["cloud_access_token"]

        async def run_case():
            await asyncio.gather(
                manager.async_ensure_fresh(
                    entry, force=True, rejected_token=rejected, now=self.now
                ),
                manager.async_ensure_fresh(
                    entry, force=True, rejected_token=rejected, now=self.now
                ),
            )

        asyncio.run(run_case())

        self.assertEqual(account_client.calls, 1)


if __name__ == "__main__":
    unittest.main()
