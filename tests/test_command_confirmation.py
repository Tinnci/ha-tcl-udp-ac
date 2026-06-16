"""Command confirmation and HA issue/event tests."""

from __future__ import annotations

import asyncio
import sys
import unittest
from types import SimpleNamespace

from tests.ha_stubs import install_homeassistant_stubs
from tests.test_protocol_commands import load_integration_module

install_homeassistant_stubs()


class FakeClient:
    """Fake client exposing pending command confirmation state."""

    def __init__(self, expected_status: dict) -> None:
        self._pending = {
            "intent": "power:on",
            "expected_status": expected_status,
        }
        self.cleared = False

    def pending_command_confirmation(self):
        return self._pending

    def clear_pending_command_confirmation(self) -> None:
        self.cleared = True
        self._pending = None

    def get_last_status(self) -> dict:
        return {}


class FakeBus:
    """Record Home Assistant events."""

    def __init__(self) -> None:
        self.events = []

    def async_fire(self, event_type, event_data):
        self.events.append((event_type, event_data))


class CommandConfirmationTest(unittest.TestCase):
    """Coordinator should confirm command application separately from sending."""

    def setUp(self) -> None:
        self.coordinator_mod = load_integration_module("coordinator")
        self.api_mod = load_integration_module("api")
        self.issue_registry = sys.modules["homeassistant.helpers.issue_registry"]

    def make_coordinator(self, client, statuses):
        coordinator = object.__new__(self.coordinator_mod.TclUdpDataUpdateCoordinator)
        coordinator.data = statuses[0] if statuses else {}
        coordinator.hass = SimpleNamespace(bus=FakeBus())
        coordinator.config_entry = SimpleNamespace(
            entry_id="entry-1",
            runtime_data=SimpleNamespace(client=client),
        )
        queue = list(statuses)

        async def refresh():
            if queue:
                coordinator.data = queue.pop(0)

        coordinator.async_request_refresh = refresh
        return coordinator

    def test_confirm_pending_command_success_fires_event_and_clears_issue(self) -> None:
        client = FakeClient({"power": True})
        coordinator = self.make_coordinator(
            client,
            [{"power": False}, {"power": True}],
        )
        deleted = []
        original_delete = self.issue_registry.async_delete_issue
        self.issue_registry.async_delete_issue = lambda *args: deleted.append(args)
        try:
            result = asyncio.run(
                coordinator.async_confirm_pending_command(timeout=1, interval=0)
            )
        finally:
            self.issue_registry.async_delete_issue = original_delete

        self.assertTrue(result)
        self.assertTrue(client.cleared)
        self.assertEqual(deleted[0][1:], ("tcl_udp_ac", "command_not_confirmed"))
        event_type, event = coordinator.hass.bus.events[-1]
        self.assertEqual(event_type, "tcl_udp_ac_command_result")
        self.assertEqual(event["outcome"], "applied")

    def test_confirm_pending_command_timeout_creates_issue(self) -> None:
        client = FakeClient({"power": True})
        coordinator = self.make_coordinator(client, [{"power": False}])
        created = []
        original_create = self.issue_registry.async_create_issue
        self.issue_registry.async_create_issue = lambda *args, **kwargs: created.append(
            (args, kwargs)
        )
        try:
            result = asyncio.run(
                coordinator.async_confirm_pending_command(timeout=0, interval=0)
            )
        finally:
            self.issue_registry.async_create_issue = original_create

        self.assertFalse(result)
        self.assertTrue(client.cleared)
        self.assertEqual(created[0][0][1:], ("tcl_udp_ac", "command_not_confirmed"))
        self.assertEqual(created[0][1]["translation_key"], "command_not_confirmed")
        event_type, event = coordinator.hass.bus.events[-1]
        self.assertEqual(event_type, "tcl_udp_ac_command_result")
        self.assertEqual(event["outcome"], "not_confirmed")

    def test_api_client_records_pending_power_command(self) -> None:
        client = self.api_mod.TclUdpApiClient(cloud_enabled=False)

        asyncio.run(client.async_set_power(power=True))

        pending = client.pending_command_confirmation()
        self.assertEqual(pending["intent"], "power:on")
        self.assertEqual(pending["expected_status"], {"power": True})


if __name__ == "__main__":
    unittest.main()
