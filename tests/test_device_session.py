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
        self.pending = None
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

    async def async_set_power(self, *, power: bool) -> None:
        self.pending = {
            "intent": f"power:{'on' if power else 'off'}",
            "expected_status": {"power": power},
        }

    def pending_command_confirmation(self):
        return self.pending

    def clear_pending_command_confirmation(self) -> None:
        self.pending = None


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
        self.assertIsNone(client.pending)


if __name__ == "__main__":
    unittest.main()
