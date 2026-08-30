"""Shared UDP hub routing tests."""

from __future__ import annotations

import asyncio
import unittest

from tests.test_protocol_commands import load_integration_module


class UdpHubRoutingTest(unittest.TestCase):
    """Datagrams should route to one deterministic device channel."""

    def setUp(self) -> None:
        self.udp_hub = load_integration_module("udp_hub")

    def test_routes_by_configured_mac(self) -> None:
        hub = self.udp_hub.UdpHub()
        first: list[bytes] = []
        second: list[bytes] = []
        hub.subscribe(
            lambda data, _addr: first.append(data),
            expected_mac="AA:BB:CC:DD:EE:01",
        )
        hub.subscribe(
            lambda data, _addr: second.append(data),
            expected_mac="AA:BB:CC:DD:EE:02",
        )
        payload = (
            b'<msg cmd="status" type="notify" tclid="AA:BB:CC:DD:EE:02">'
            b"<statusUpdateMsg><turnOn>1</turnOn></statusUpdateMsg></msg>"
        )

        delivered = hub.route_datagram(payload, ("192.0.2.2", 10075))

        self.assertEqual(delivered, 1)
        self.assertEqual(first, [])
        self.assertEqual(second, [payload])

    def test_routes_by_configured_cloud_device_id(self) -> None:
        hub = self.udp_hub.UdpHub()
        first: list[bytes] = []
        second: list[bytes] = []
        hub.subscribe(
            lambda data, _addr: first.append(data), expected_device_id="2743138"
        )
        hub.subscribe(
            lambda data, _addr: second.append(data), expected_device_id="45816970"
        )
        payload = b'<msg cmd="status" type="notify" tclid="45816970" />'

        delivered = hub.route_datagram(payload, ("192.0.2.2", 10075))

        self.assertEqual(delivered, 1)
        self.assertEqual(first, [])
        self.assertEqual(second, [payload])

    def test_conflicting_identity_is_refused_instead_of_fanned_out(self) -> None:
        hub = self.udp_hub.UdpHub()
        received: list[bytes] = []
        for _ in range(2):
            hub.subscribe(
                lambda data, _addr: received.append(data),
                expected_device_id="45816970",
            )

        delivered = hub.route_datagram(
            b'<msg cmd="status" type="notify" tclid="45816970" />',
            ("192.0.2.2", 10075),
        )

        self.assertEqual(delivered, 0)
        self.assertEqual(received, [])

    def test_single_unknown_subscription_can_bind_first_device(self) -> None:
        hub = self.udp_hub.UdpHub()
        received: list[bytes] = []
        subscription = hub.subscribe(lambda data, _addr: received.append(data))
        payload = (
            b'<msg cmd="status" type="notify" tclid="AA">'
            b"<statusUpdateMsg><turnOn>1</turnOn></statusUpdateMsg></msg>"
        )

        delivered = hub.route_datagram(payload, ("192.0.2.10", 10075))

        self.assertEqual(delivered, 1)
        self.assertEqual(received, [payload])
        self.assertEqual(subscription.bound_ip, "192.0.2.10")

    def test_multiple_unknown_subscriptions_refuse_ambiguous_packet(self) -> None:
        hub = self.udp_hub.UdpHub()
        first: list[bytes] = []
        second: list[bytes] = []
        hub.subscribe(lambda data, _addr: first.append(data))
        hub.subscribe(lambda data, _addr: second.append(data))
        payload = (
            b'<msg cmd="status" type="notify" tclid="AA">'
            b"<statusUpdateMsg><turnOn>1</turnOn></statusUpdateMsg></msg>"
        )

        delivered = hub.route_datagram(payload, ("192.0.2.10", 10075))

        self.assertEqual(delivered, 0)
        self.assertEqual(first, [])
        self.assertEqual(second, [])

    def test_unknown_subscription_cannot_claim_known_devices_unmatched_mac(
        self,
    ) -> None:
        hub = self.udp_hub.UdpHub()
        known: list[bytes] = []
        unknown: list[bytes] = []
        hub.subscribe(
            lambda data, _addr: known.append(data), expected_device_id="2743138"
        )
        hub.subscribe(lambda data, _addr: unknown.append(data))
        payload = b"<deviceInfo><DevMAC>38:76:CA:43:69:B9</DevMAC></deviceInfo>"

        delivered = hub.route_datagram(payload, ("192.0.2.10", 10075))

        self.assertEqual(delivered, 0)
        self.assertEqual(known, [])
        self.assertEqual(unknown, [])

    def test_bound_ip_routes_identity_free_reply(self) -> None:
        hub = self.udp_hub.UdpHub()
        first: list[bytes] = []
        second: list[bytes] = []
        first_sub = hub.subscribe(
            lambda data, _addr: first.append(data), expected_mac="AA"
        )
        hub.subscribe(lambda data, _addr: second.append(data), expected_mac="BB")
        first_sub.bound_ip = "192.0.2.10"
        payload = b'{"method":"statusResp"}'

        delivered = hub.route_datagram(payload, ("192.0.2.10", 10075))

        self.assertEqual(delivered, 1)
        self.assertEqual(first, [payload])
        self.assertEqual(second, [])

    def test_packet_identity_wins_over_stale_ip_binding(self) -> None:
        hub = self.udp_hub.UdpHub()
        first: list[bytes] = []
        second: list[bytes] = []
        first_sub = hub.subscribe(
            lambda data, _addr: first.append(data), expected_mac="AA"
        )
        hub.subscribe(lambda data, _addr: second.append(data), expected_mac="BB")
        first_sub.bound_ip = "192.0.2.10"
        payload = (
            b'<msg cmd="status" type="notify" tclid="BB">'
            b"<statusUpdateMsg><turnOn>1</turnOn></statusUpdateMsg></msg>"
        )

        delivered = hub.route_datagram(payload, ("192.0.2.10", 10075))

        self.assertEqual(delivered, 1)
        self.assertEqual(first, [])
        self.assertEqual(second, [payload])

    def test_udp_client_uses_shared_hub_for_send_and_release(self) -> None:
        udp_client = load_integration_module("udp_client")

        class FakeHub:
            def __init__(self) -> None:
                self.callback = None
                self.acquired = 0
                self.released = 0
                self.sent = []
                self.unsubscribed = []

            def subscribe(
                self, callback, *, expected_mac=None, expected_device_id=None
            ):
                self.callback = callback
                return self.udp_hub.UdpSubscription(
                    1,
                    callback,
                    expected_mac=expected_mac,
                    expected_device_id=expected_device_id,
                )

            async def async_acquire(self):
                self.acquired += 1

            async def async_release(self):
                self.released += 1

            def unsubscribe(self, subscription):
                self.unsubscribed.append(subscription)

            def sendto(self, data, addr):
                self.sent.append((data, addr))

        hub = FakeHub()
        hub.udp_hub = self.udp_hub
        client = udp_client.UdpClient(
            "jid",
            "1",
            "account",
            device_mac="AA:BB",
            udp_hub=hub,
        )

        async def run_case() -> None:
            await client.async_start_listener(lambda _status: None)
            client._device_ip = "192.0.2.10"
            await client.async_send_commands([("TurnOn", "on")])
            await client.async_close()

        asyncio.run(run_case())

        self.assertEqual(hub.acquired, 1)
        self.assertEqual(hub.released, 1)
        self.assertEqual(len(hub.sent), 1)
        self.assertEqual(hub.sent[0][1], ("192.0.2.10", 10075))


if __name__ == "__main__":
    unittest.main()
