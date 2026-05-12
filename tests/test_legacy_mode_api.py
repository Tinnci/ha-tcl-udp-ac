"""API routing tests for legacy protocol profile mode commands."""

from __future__ import annotations

import asyncio
import unittest
from types import MethodType

from tests.test_protocol_commands import load_integration_module


class LegacyModeApiTest(unittest.TestCase):
    """API client should send legacy mode changes through profile bundles."""

    def setUp(self) -> None:
        self.api = load_integration_module("api")
        self.profiles = load_integration_module("protocol_profiles")
        self.const = load_integration_module("const")

    def _client_with_profile(self, device_id: str):
        client = object.__new__(self.api.TclUdpApiClient)
        client._protocol_profile = self.profiles.resolve_protocol_profile(device_id)
        calls = []

        async def fake_send_command_bundle(self, bundle):
            calls.append(bundle)

        client.async_send_command_bundle = MethodType(fake_send_command_bundle, client)
        return client, calls

    def test_fan_profile_api_sends_base_mode_zero(self) -> None:
        client, calls = self._client_with_profile("2743138")

        asyncio.run(client.async_set_mode_profile(self.const.MODE_FAN))

        self.assertEqual(calls[0].payload["baseMode"], "0")
        self.assertEqual(calls[0].payload["setTemp"], "73")

    def test_dry_profile_api_sends_base_mode_two(self) -> None:
        client, calls = self._client_with_profile("2743138")

        asyncio.run(client.async_set_mode_profile(self.const.MODE_DEHUMI))

        self.assertEqual(calls[0].payload["baseMode"], "2")
        self.assertEqual(calls[0].payload["setTemp"], "82")

    def test_cool_and_heat_use_current_target_temp(self) -> None:
        client, calls = self._client_with_profile("2743138")

        asyncio.run(
            client.async_set_mode_profile(
                self.const.MODE_COOL,
                target_temperature=24.0,
            )
        )
        asyncio.run(
            client.async_set_mode_profile(
                self.const.MODE_HEAT,
                target_temperature=28.0,
            )
        )

        self.assertEqual(calls[0].payload["baseMode"], "1")
        self.assertEqual(calls[0].payload["setTemp"], "75")
        self.assertEqual(calls[0].payload["optSuper"], "0")
        self.assertEqual(calls[1].payload["baseMode"], "4")
        self.assertEqual(calls[1].payload["setTemp"], "82")

    def test_legacy_temperature_uses_profile_context(self) -> None:
        client, calls = self._client_with_profile("2743138")
        client.get_last_status = lambda: {"mode": self.const.MODE_COOL}

        asyncio.run(client.async_set_temperature(25.0))

        self.assertEqual(
            calls[0].payload,
            {"setTemp": "77", "degreeH": "0", "optSuper": "0"},
        )

    def test_legacy_temperature_rejects_unknown_context(self) -> None:
        client, calls = self._client_with_profile("2743138")
        client.get_last_status = lambda: {"mode": self.const.MODE_DEHUMI}

        with self.assertRaises(self.profiles.UnsupportedModeError):
            asyncio.run(client.async_set_temperature(25.0))

        self.assertEqual(calls, [])

    def test_unsupported_auto_sends_zero_packets(self) -> None:
        client, calls = self._client_with_profile("2743138")

        with self.assertRaises(self.profiles.UnsupportedModeError):
            asyncio.run(client.async_set_mode_profile(self.const.MODE_AUTO))

        self.assertEqual(calls, [])

    def test_non_legacy_profile_preserves_existing_shape(self) -> None:
        client, calls = self._client_with_profile("other")

        asyncio.run(client.async_set_mode_profile(self.const.MODE_FAN))

        self.assertEqual(calls[0].payload, {"turnOn": "1", "baseMode": "7"})

    def test_legacy_power_off_api_uses_profile_shutdown_bundle(self) -> None:
        client, calls = self._client_with_profile("2743138")

        asyncio.run(client.async_set_power(power=False))

        self.assertEqual(
            calls[0].payload,
            {
                "optSleepMd": "0",
                "optECO": "0",
                "optHealthy": "0",
                "optSuper": "0",
                "optHeat": "0",
                "turnOn": "0",
            },
        )


if __name__ == "__main__":
    unittest.main()
