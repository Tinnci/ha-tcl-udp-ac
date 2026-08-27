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
        self.assertEqual(
            deleted[0][1:], ("tcl_udp_ac", "command_not_confirmed_entry-1")
        )
        event_type, event = coordinator.hass.bus.events[-1]
        self.assertEqual(event_type, "tcl_udp_ac_command_result")
        self.assertEqual(event["outcome"], "applied")
        self.assertEqual(event["transport_outcome"], "unknown")

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
        self.assertEqual(
            created[0][0][1:], ("tcl_udp_ac", "command_not_confirmed_entry-1")
        )
        self.assertEqual(created[0][1]["translation_key"], "command_not_confirmed")
        event_type, event = coordinator.hass.bus.events[-1]
        self.assertEqual(event_type, "tcl_udp_ac_command_result")
        self.assertEqual(event["outcome"], "not_confirmed")

    def test_api_client_returns_power_command_receipt(self) -> None:
        client = self.api_mod.TclUdpApiClient(cloud_enabled=False)

        receipt = asyncio.run(client.async_set_power(power=True))

        self.assertEqual(receipt.intent, "power:on")
        self.assertEqual(receipt.expected_status, {"power": True})
        self.assertFalse(receipt.delivery.accepted)

    def test_explicit_command_id_clears_only_that_session_command(self) -> None:
        tracker_mod = load_integration_module("command_tracker")
        bundles = load_integration_module("command_bundles")

        class FakeSession:
            def __init__(self) -> None:
                self.tracker = tracker_mod.CommandTracker()

            def pending_command_confirmation(self, command_id=None):
                pending = self.tracker.pending(command_id)
                return pending.as_dict() if pending else None

            def clear_pending_command_confirmation(self, command_id=None):
                pending = self.tracker.pending(command_id)
                if pending:
                    self.tracker.complete(pending.command_id)

            def get_last_status(self):
                return {}

        session = FakeSession()
        delivery = bundles.TransportDelivery(udp=bundles.TransportAttempt.ACCEPTED)
        power_id = session.tracker.record(
            bundles.CommandReceipt("power:on", {"power": True}, delivery)
        )
        mode_id = session.tracker.record(
            bundles.CommandReceipt("mode:cool", {"mode": "cool"}, delivery)
        )
        coordinator = self.make_coordinator(
            FakeClient({}),
            [{"power": True, "mode": "cool"}],
        )
        coordinator.config_entry.runtime_data.session = session

        result = asyncio.run(
            coordinator.async_confirm_pending_command(
                command_id=power_id,
                timeout=0,
                interval=0,
            )
        )

        self.assertTrue(result)
        self.assertIsNone(session.tracker.pending(power_id))
        self.assertIsNotNone(session.tracker.pending(mode_id))
        _event_type, event = coordinator.hass.bus.events[-1]
        self.assertEqual(event["command_id"], power_id)
        self.assertEqual(event["transport_outcome"], "accepted_by_udp")
        self.assertEqual(
            event["transport_attempts"], {"cloud": "skipped", "udp": "accepted"}
        )


if __name__ == "__main__":
    unittest.main()
