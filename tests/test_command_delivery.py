"""Command transport delivery result tests."""

from __future__ import annotations

import asyncio
import unittest

from tests.test_protocol_commands import load_integration_module


class CommandDeliveryTest(unittest.TestCase):
    """Transport attempts should remain visible without pretending to be atomic."""

    def setUp(self) -> None:
        self.api = load_integration_module("api")
        self.bundles = load_integration_module("command_bundles")
        self.profiles = load_integration_module("protocol_profiles")

    def make_client(self, *, cloud_accepted: bool, udp_result=True):
        client = object.__new__(self.api.TclUdpApiClient)
        client._protocol_profile = self.profiles.resolve_protocol_profile("2743138")
        client._cloud_sequence = 0

        class FakeCloud:
            control_enabled = True

            async def async_send_commands(self, _items, _seq):
                return cloud_accepted

        class FakeUdp:
            async def async_send_commands(self, _items):
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

    def test_rejected_cloud_and_skipped_udp_is_not_accepted(self) -> None:
        client = self.make_client(cloud_accepted=False, udp_result=False)

        delivery = asyncio.run(client.async_send_commands([("TurnOn", "on")]))

        self.assertEqual(delivery.cloud, self.bundles.TransportAttempt.REJECTED)
        self.assertEqual(delivery.udp, self.bundles.TransportAttempt.SKIPPED)
        self.assertFalse(delivery.accepted)
        self.assertEqual(delivery.outcome, "not_sent")


if __name__ == "__main__":
    unittest.main()
