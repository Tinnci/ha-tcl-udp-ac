"""Per-device session facade tests."""

from __future__ import annotations

import asyncio
import unittest

from tests.test_protocol_commands import load_integration_module


class FakeTransportClient:
    cloud_enabled = True
    cloud_statistics_enabled = False

    def __init__(self) -> None:
        self.callback = None
        self.status: dict = {}

    async def async_start_listener(self, callback) -> None:
        self.callback = callback

    async def async_request_status(self) -> None:
        return None

    async def async_fetch_cloud_status(self, **_kwargs):
        return {"power": False, "target_temp": 23.0}

    async def async_fetch_cloud_energy_statistics(self):
        return None

    def get_last_status(self):
        return self.status

    async def async_set_power(self, *, power: bool):
        bundles = load_integration_module("command_bundles")
        return bundles.CommandReceipt(
            intent=f"power:{'on' if power else 'off'}",
            expected_status={"power": power},
            delivery=bundles.TransportDelivery(udp=bundles.TransportAttempt.ACCEPTED),
        )


class DeviceSessionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.session_mod = load_integration_module("device_session")
        self.state_mod = load_integration_module("device_state")

    def test_local_push_is_reconciled_before_callback(self) -> None:
        client = FakeTransportClient()
        session = self.session_mod.DeviceSession(client)
        received = []

        async def run_case() -> None:
            await session.async_start_listener(received.append)
            await client.callback({"power": True})

        asyncio.run(run_case())

        self.assertEqual(received, [{"power": True}])
        self.assertEqual(session.get_last_status(), {"power": True})

    def test_recent_udp_state_survives_cloud_fallback(self) -> None:
        client = FakeTransportClient()
        session = self.session_mod.DeviceSession(client)
        session.observe(
            self.state_mod.StateSource.UDP,
            {"power": True},
            received_at=100,
        )

        session.observe(
            self.state_mod.StateSource.CLOUD,
            {"power": False, "target_temp": 23.0},
            received_at=101,
        )

        self.assertEqual(
            session.get_last_status(), {"power": True, "target_temp": 23.0}
        )

    def test_command_returns_id_and_moves_expectation_into_tracker(self) -> None:
        client = FakeTransportClient()
        session = self.session_mod.DeviceSession(client)

        command_id = asyncio.run(session.async_set_power(power=True))

        self.assertIsNotNone(command_id)
        self.assertEqual(
            session.pending_command_confirmation(command_id)["expected_status"],
            {"power": True},
        )

    def test_concurrent_commands_keep_their_own_receipts(self) -> None:
        bundles = load_integration_module("command_bundles")

        class ConcurrentClient(FakeTransportClient):
            async def async_set_power(self, *, power: bool):
                await asyncio.sleep(0 if power else 0.01)
                return bundles.CommandReceipt(
                    intent=f"power:{'on' if power else 'off'}",
                    expected_status={"power": power},
                    delivery=bundles.TransportDelivery(
                        udp=bundles.TransportAttempt.ACCEPTED
                    ),
                )

        session = self.session_mod.DeviceSession(ConcurrentClient())

        async def run_case():
            return await asyncio.gather(
                session.async_set_power(power=False),
                session.async_set_power(power=True),
            )

        off_id, on_id = asyncio.run(run_case())

        self.assertNotEqual(off_id, on_id)
        self.assertEqual(
            session.pending_command_confirmation(off_id)["expected_status"],
            {"power": False},
        )
        self.assertEqual(
            session.pending_command_confirmation(on_id)["expected_status"],
            {"power": True},
        )

    def test_unaccepted_receipt_is_not_tracked(self) -> None:
        bundles = load_integration_module("command_bundles")

        class SkippedClient(FakeTransportClient):
            async def async_set_power(self, *, power: bool):
                return bundles.CommandReceipt(
                    intent="power:on",
                    expected_status={"power": True},
                    delivery=bundles.TransportDelivery(),
                )

        session = self.session_mod.DeviceSession(SkippedClient())

        command_id = asyncio.run(session.async_set_power(power=True))

        self.assertIsNone(command_id)
        self.assertIsNone(session.pending_command_confirmation())
        self.assertEqual(
            session.last_command_attempt(),
            {
                "intent": "power:on",
                "expected_status": {"power": True},
                "transport_outcome": "not_sent",
                "transport_attempts": {"cloud": "skipped", "udp": "skipped"},
                "created_at": session.last_command_attempt()["created_at"],
            },
        )

    def test_derived_state_rejects_device_control_fields(self) -> None:
        session = self.session_mod.DeviceSession(FakeTransportClient())

        with self.assertRaises(ValueError):
            session.merge_derived({"power": True})


if __name__ == "__main__":
    unittest.main()
