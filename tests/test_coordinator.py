"""Data update coordinator behavior tests."""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from tests.ha_stubs import install_homeassistant_stubs
from tests.test_protocol_commands import load_integration_module

install_homeassistant_stubs()


class FakeClient:
    """Fake integration client for coordinator tests."""

    def __init__(self, *, cloud_enabled: bool = True, fail_udp: bool = False) -> None:
        self.cloud_enabled = cloud_enabled
        self.fail_udp = fail_udp
        self.calls = []
        self.last_status = {"power": False, "target_temp": 23.0}

    async def async_request_status(self) -> None:
        self.calls.append("async_request_status")
        if self.fail_udp:
            raise load_integration_module("api").TclUdpApiClientError

    async def async_fetch_cloud_status(self) -> dict:
        self.calls.append("async_fetch_cloud_status")
        self.last_status = {"power": True, "target_temp": 24.0}
        return self.last_status

    def get_last_status(self) -> dict:
        self.calls.append("get_last_status")
        return self.last_status


class CoordinatorTest(unittest.TestCase):
    """Coordinator should poll UDP first and use cloud fallback when configured."""

    def setUp(self) -> None:
        self.coordinator_mod = load_integration_module("coordinator")

    def make_coordinator(self, client: FakeClient):
        coordinator = object.__new__(self.coordinator_mod.TclUdpDataUpdateCoordinator)
        coordinator.config_entry = SimpleNamespace(
            runtime_data=SimpleNamespace(client=client)
        )
        return coordinator

    def test_update_requests_udp_then_cloud_when_enabled(self) -> None:
        client = FakeClient(cloud_enabled=True)
        coordinator = self.make_coordinator(client)

        result = asyncio.run(coordinator._async_update_data())

        self.assertEqual(
            client.calls,
            ["async_request_status", "async_fetch_cloud_status", "get_last_status"],
        )
        self.assertEqual(result, {"power": True, "target_temp": 24.0})

    def test_update_returns_last_status_when_cloud_disabled(self) -> None:
        client = FakeClient(cloud_enabled=False)
        coordinator = self.make_coordinator(client)

        result = asyncio.run(coordinator._async_update_data())

        self.assertEqual(client.calls, ["async_request_status", "get_last_status"])
        self.assertEqual(result, {"power": False, "target_temp": 23.0})

    def test_udp_error_still_fetches_cloud_fallback(self) -> None:
        client = FakeClient(cloud_enabled=True, fail_udp=True)
        coordinator = self.make_coordinator(client)

        result = asyncio.run(coordinator._async_update_data())

        self.assertEqual(
            client.calls,
            ["async_request_status", "async_fetch_cloud_status", "get_last_status"],
        )
        self.assertEqual(result, {"power": True, "target_temp": 24.0})


if __name__ == "__main__":
    unittest.main()
