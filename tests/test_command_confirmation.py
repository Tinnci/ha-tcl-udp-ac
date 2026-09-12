"""Command confirmation and HA issue/event tests."""

from __future__ import annotations

import asyncio
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests.ha_stubs import install_homeassistant_stubs
from tests.test_device_session import FakeTransportClient
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
        self.assertEqual(coordinator.last_command_result["outcome"], "applied")

    def test_command_result_event_preserves_entity_and_context_correlation(
        self,
    ) -> None:
        client = FakeClient({"power": True})
        client._pending.update(
            {
                "entity_id": "climate.bedroom_ac",
                "context_id": "roommind-cycle-1",
            }
        )
        coordinator = self.make_coordinator(client, [{"power": True}])

        result = asyncio.run(
            coordinator.async_confirm_pending_command(timeout=0, interval=0)
        )

        self.assertTrue(result)
        _event_type, event = coordinator.hass.bus.events[-1]
        self.assertEqual(event["entity_id"], "climate.bedroom_ac")
        self.assertEqual(event["context_id"], "roommind-cycle-1")

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

    def test_unrelated_report_cannot_confirm_cached_matching_power(self) -> None:
        """A refreshed temperature must not confirm power retained before dispatch."""
        session_mod = load_integration_module("device_session")
        state_mod = load_integration_module("device_state")
        session = session_mod.DeviceSession(FakeTransportClient())
        session.observe(state_mod.StateSource.UDP, {"power": True}, received_at=10)
        with patch.object(session_mod.time, "monotonic", return_value=20):
            command_id = asyncio.run(session.async_set_power(power=True))
        coordinator = self.make_coordinator(session, [])
        coordinator.config_entry.runtime_data.session = session

        async def refresh():
            coordinator.data = session.observe(
                state_mod.StateSource.UDP, {"current_temp": 25.0}, received_at=21
            )

        coordinator.async_request_refresh = refresh
        result = asyncio.run(
            coordinator.async_confirm_pending_command(
                command_id=command_id, timeout=0, interval=0
            )
        )

        self.assertFalse(result)
        self.assertEqual(coordinator.last_command_result["outcome"], "not_confirmed")

    def test_every_required_field_needs_a_post_dispatch_report(self) -> None:
        """One new field does not make the rest of a mode bundle fresh."""
        session_mod = load_integration_module("device_session")
        state_mod = load_integration_module("device_state")
        bundles = load_integration_module("command_bundles")

        class ModeClient(FakeTransportClient):
            async def async_set_power(self, *, power):
                return bundles.CommandReceipt(
                    intent="mode:cool",
                    expected_status={
                        "power": power,
                        "mode": "cool",
                        "target_temp": 24.0,
                    },
                    delivery=bundles.TransportDelivery(
                        udp=bundles.TransportAttempt.ACCEPTED
                    ),
                )

        session = session_mod.DeviceSession(ModeClient())
        session.observe(
            state_mod.StateSource.UDP,
            {"power": True, "mode": "cool", "target_temp": 24.0},
            received_at=10,
        )
        with patch.object(session_mod.time, "monotonic", return_value=20):
            command_id = asyncio.run(session.async_set_power(power=True))
        coordinator = self.make_coordinator(session, [])
        coordinator.config_entry.runtime_data.session = session

        async def refresh():
            coordinator.data = session.observe(
                state_mod.StateSource.UDP, {"power": True}, received_at=21
            )

        coordinator.async_request_refresh = refresh
        result = asyncio.run(
            coordinator.async_confirm_pending_command(command_id=command_id, timeout=0)
        )

        self.assertFalse(result)

    def test_report_during_dispatch_can_confirm_before_receipt_is_recorded(
        self,
    ) -> None:
        """Do not miss fast device feedback while transport dispatch is awaiting."""
        session_mod = load_integration_module("device_session")
        state_mod = load_integration_module("device_state")

        class EarlyReportClient(FakeTransportClient):
            async def async_set_power(self, *, power):
                session.observe(
                    state_mod.StateSource.UDP, {"power": power}, received_at=21
                )
                clock.return_value = 22
                return await super().async_set_power(power=power)

        session = session_mod.DeviceSession(EarlyReportClient())
        with patch.object(session_mod.time, "monotonic", return_value=20) as clock:
            command_id = asyncio.run(session.async_set_power(power=True))
            coordinator = self.make_coordinator(session, [session.get_last_status()])
            coordinator.config_entry.runtime_data.session = session
            result = asyncio.run(
                coordinator.async_confirm_pending_command(
                    command_id=command_id, timeout=0
                )
            )

        self.assertTrue(result)
        self.assertEqual(coordinator.last_command_result["outcome"], "applied")

    def test_compatibility_cache_is_not_device_confirmation(self) -> None:
        """A compatibility seed has no physical report provenance."""
        session_mod = load_integration_module("device_session")
        client = FakeTransportClient()
        client.status = {"power": True}
        session = session_mod.DeviceSession(client)
        command_id = asyncio.run(session.async_set_power(power=True))
        coordinator = self.make_coordinator(session, [session.get_last_status()])
        coordinator.config_entry.runtime_data.session = session

        result = asyncio.run(
            coordinator.async_confirm_pending_command(command_id=command_id, timeout=0)
        )

        self.assertFalse(result)

    def test_cloud_request_started_before_dispatch_cannot_confirm_it(self) -> None:
        """A response already in flight may describe the pre-command state."""
        session_mod = load_integration_module("device_session")

        async def run_case():
            requested = asyncio.Event()
            release = asyncio.Event()

            class InFlightClient(FakeTransportClient):
                async def async_fetch_cloud_status(self, **kwargs):
                    requested.set()
                    await release.wait()
                    return {"power": True}

            session = session_mod.DeviceSession(InFlightClient())
            with patch.object(session_mod.time, "monotonic", return_value=10) as clock:
                status_task = asyncio.create_task(session.async_fetch_cloud_status())
                await requested.wait()
                clock.return_value = 20
                command_id = await session.async_set_power(power=True)
                clock.return_value = 21
                release.set()
                await status_task
                coordinator = self.make_coordinator(
                    session, [session.get_last_status()]
                )
                coordinator.config_entry.runtime_data.session = session
                return await coordinator.async_confirm_pending_command(
                    command_id=command_id, timeout=0
                )

        self.assertFalse(asyncio.run(run_case()))

    def test_unaccepted_delivery_creates_error_issue_and_event(self) -> None:
        class FailedSession:
            def last_command_attempt(self):
                return {
                    "intent": "power:on",
                    "expected_status": {"power": True},
                    "transport_outcome": "not_sent",
                    "transport_attempts": {
                        "cloud": "failed",
                        "udp": "rejected",
                    },
                }

            def get_last_status(self):
                return {"power": False}

        coordinator = self.make_coordinator(FakeClient({}), [{"power": False}])
        coordinator.config_entry.runtime_data.session = FailedSession()
        created = []
        original_create = self.issue_registry.async_create_issue
        self.issue_registry.async_create_issue = lambda *args, **kwargs: created.append(
            (args, kwargs)
        )
        try:
            reported = asyncio.run(
                coordinator.async_report_command_delivery_failure(
                    entity_id="climate.bedroom_ac",
                    context_id="service-call-1",
                )
            )
        finally:
            self.issue_registry.async_create_issue = original_create

        self.assertTrue(reported)
        self.assertEqual(created[0][0][1:], ("tcl_udp_ac", "command_not_sent_entry-1"))
        self.assertEqual(created[0][1]["translation_key"], "command_not_sent")
        self.assertEqual(created[0][1]["severity"], "error")
        event_type, event = coordinator.hass.bus.events[-1]
        self.assertEqual(event_type, "tcl_udp_ac_command_result")
        self.assertEqual(event["outcome"], "not_sent")
        self.assertEqual(event["entity_id"], "climate.bedroom_ac")
        self.assertEqual(event["context_id"], "service-call-1")
        self.assertEqual(coordinator.last_command_result, event)

    def test_entity_helper_surfaces_unaccepted_delivery(self) -> None:
        climate = load_integration_module("climate")
        exceptions = sys.modules["homeassistant.exceptions"]

        class FailedCoordinator:
            def __init__(self) -> None:
                self.config_entry = SimpleNamespace(
                    runtime_data=SimpleNamespace(session=object())
                )
                self.refreshes = 0

            async def async_confirm_pending_command(self, **_kwargs):
                return True

            async def async_report_command_delivery_failure(self, **_kwargs):
                return True

            async def async_request_refresh(self):
                self.refreshes += 1

        coordinator = FailedCoordinator()
        with self.assertRaises(exceptions.HomeAssistantError):
            asyncio.run(
                climate._async_after_command(
                    coordinator,
                    entity_id="climate.bedroom_ac",
                    context_id="service-call-1",
                )
            )
        self.assertEqual(coordinator.refreshes, 0)

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
