"""Command transport delivery result tests."""

from __future__ import annotations

import asyncio
import logging
import unittest
from unittest.mock import AsyncMock, patch

from tests.test_protocol_commands import load_integration_module


class CommandDeliveryTest(unittest.TestCase):
    """Transport attempts should remain visible without pretending to be atomic."""

    def setUp(self) -> None:
        self.api = load_integration_module("api")
        self.bundles = load_integration_module("command_bundles")
        self.profiles = load_integration_module("protocol_profiles")
        self.udp_client_mod = load_integration_module("udp_client")

    def make_client(self, *, cloud_accepted: bool, udp_result=True):
        client = object.__new__(self.api.TclUdpApiClient)
        client._protocol_profile = self.profiles.resolve_protocol_profile("2743138")
        client._cloud_sequence = 0

        class FakeCloud:
            control_enabled = True

            async def async_send_commands(self, _items, _seq):
                return cloud_accepted

        class FakeUdp:
            def __init__(self) -> None:
                self.calls: list[tuple[list[tuple[str, str]], bool]] = []

            async def async_send_commands(self, items, *, cloud_accepted: bool = False):
                self.calls.append((items, cloud_accepted))
                if isinstance(udp_result, Exception):
                    raise udp_result
                return udp_result

        client._cloud = FakeCloud()
        client._udp = FakeUdp()
        return client

    def test_cloud_acceptance_survives_udp_failure_as_partial_delivery(self) -> None:
        client = self.make_client(cloud_accepted=True, udp_result=OSError("offline"))

        delivery = asyncio.run(client.async_send_commands([("TurnOn", "on")]))

        self.assertEqual(delivery.cloud, self.bundles.TransportAttempt.ACCEPTED)
        self.assertEqual(delivery.udp, self.bundles.TransportAttempt.FAILED)
        self.assertEqual(delivery.outcome, "accepted_by_cloud")
        self.assertEqual(client._udp.calls, [([("TurnOn", "on")], True)])

    def test_rejected_cloud_and_skipped_udp_is_not_accepted(self) -> None:
        client = self.make_client(cloud_accepted=False, udp_result=False)

        delivery = asyncio.run(client.async_send_commands([("TurnOn", "on")]))

        self.assertEqual(delivery.cloud, self.bundles.TransportAttempt.REJECTED)
        self.assertEqual(delivery.udp, self.bundles.TransportAttempt.SKIPPED)
        self.assertFalse(delivery.accepted)
        self.assertEqual(delivery.outcome, "not_sent")
        self.assertEqual(client._udp.calls, [([("TurnOn", "on")], False)])

    def test_udp_control_skipped_logs_debug_when_cloud_accepted_else_warning(self) -> None:
        udp_client = self.udp_client_mod.UdpClient(
            action_jid="user@tcl.com/ha",
            action_source="1",
            account="user",
        )
        logger_name = self.udp_client_mod.LOGGER.name

        with self.assertLogs(logger_name, level=logging.DEBUG) as debug_logs:
            result = asyncio.run(
                udp_client.async_send_commands([("TurnOn", "on")], cloud_accepted=True)
            )
        self.assertFalse(result)
        self.assertTrue(
            any(
                rec.levelno == logging.DEBUG and "udp_control_skipped" in rec.getMessage()
                for rec in debug_logs.records
            )
        )
        self.assertFalse(any(rec.levelno >= logging.WARNING for rec in debug_logs.records))

        with self.assertLogs(logger_name, level=logging.WARNING) as warn_logs:
            result = asyncio.run(
                udp_client.async_send_commands([("TurnOn", "on")], cloud_accepted=False)
            )
        self.assertFalse(result)
        self.assertTrue(
            any(
                rec.levelno == logging.WARNING and "udp_control_skipped" in rec.getMessage()
                for rec in warn_logs.records
            )
        )

    def test_undiscovered_request_status_applies_backoff_and_resets_on_ip(self) -> None:
        udp_client = self.udp_client_mod.UdpClient(
            action_jid="user@tcl.com/ha",
            action_source="1",
            account="user",
        )
        udp_client._send_sock = object()
        udp_client.async_send_discovery = AsyncMock()
        now = 1000.0

        with patch.object(self.udp_client_mod.time, "time", side_effect=lambda: now):
            asyncio.run(udp_client.async_request_status())
            self.assertEqual(udp_client.async_send_discovery.await_count, 1)

            now = 1015.0  # < 30s initial backoff -> skipped
            asyncio.run(udp_client.async_request_status())
            self.assertEqual(udp_client.async_send_discovery.await_count, 1)

            now = 1031.0  # >= 30s -> triggers second discovery, backoff becomes 60s
            asyncio.run(udp_client.async_request_status())
            self.assertEqual(udp_client.async_send_discovery.await_count, 2)

            now = 1065.0  # 34s elapsed < 60s -> skipped
            asyncio.run(udp_client.async_request_status())
            self.assertEqual(udp_client.async_send_discovery.await_count, 2)

            now = 1095.0  # 64s elapsed >= 60s -> triggers third discovery, backoff 120s
            asyncio.run(udp_client.async_request_status())
            self.assertEqual(udp_client.async_send_discovery.await_count, 3)

            async def _exercise_reset() -> None:
                udp_client._handle_status_update(
                    b'<deviceInfo><DevIP>192.168.1.50</DevIP></deviceInfo>',
                    ("192.168.1.50", 60002),
                )

            asyncio.run(_exercise_reset())
            self.assertIsNone(udp_client._last_discovery_time)
            self.assertEqual(
                udp_client._discovery_backoff_seconds,
                self.udp_client_mod.DISCOVERY_BACKOFF_INITIAL_SECONDS,
            )


if __name__ == "__main__":
    unittest.main()
