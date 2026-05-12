"""Temperature unit tests for Home Assistant-facing climate behavior."""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
import unittest
from types import MethodType

from tests.test_protocol_commands import load_integration_module


class TemperatureUnitTest(unittest.TestCase):
    """The integration should expose Celsius to Home Assistant."""

    def setUp(self) -> None:
        self.api = load_integration_module("api")

    def test_cloud_status_prefers_celsius_target_temperature(self) -> None:
        client = self.api.CloudClient(
            session=None,
            enabled=False,
            tid=None,
            token=None,
            from_jid=None,
            to_jid=None,
            base_url="https://io.zx.tcljd.com",
            control_enabled=False,
            headers=self.api.CloudHeaderProfile(
                platform="android",
                user_agent="ua",
                app_package="pkg",
                system_version="16",
                brand="brand",
                app_version="4.1.1",
                sdk_version="6.0.3",
                channel="xiaomi",
                app_build_version="4.1.1.0",
                t_app_version="4.1.1.0",
                t_platform_type="Android",
                t_store_uuid="TCL+",
                origin="https://h5.zx.tcljd.com",
                x_requested_with="com.tcl.tclplus",
                accept="text/plain",
                accept_encoding="gzip",
                accept_language="zh-CN",
            ),
        )

        status = client._parse_cloud_status(
            {
                "celsiusSetTemp": 23.0,
                "setTemp": "73",
                "inTemp": "85",
                "outTemp": "86",
            }
        )

        self.assertEqual(status["target_temp"], 23.0)
        self.assertEqual(status["current_temp"], 29.4)
        self.assertEqual(status["outdoor_temp"], 30.0)

    def test_set_temperature_accepts_celsius_and_sends_protocol_fahrenheit(self) -> None:
        client = object.__new__(self.api.TclUdpApiClient)
        calls = []

        async def fake_send_command(self, command, value, degree_half=None):
            calls.append((command, value, degree_half))

        client.async_send_command = MethodType(fake_send_command, client)

        asyncio.run(client.async_set_temperature(23.0))

        self.assertEqual(calls, [("SetTemp", "73", 0)])

    def test_udp_status_converts_protocol_temperatures_to_celsius(self) -> None:
        udp_client = load_integration_module("udp_client").UdpClient(
            action_jid="user@tcl.com/PH-android-zx01-2",
            action_source="1",
            account="user",
        )
        root = ET.fromstring(
            "<status>"
            "<SetTemp>73</SetTemp>"
            "<DegreeH>0</DegreeH>"
            "<InTemp>85</InTemp>"
            "<OutTemp>86</OutTemp>"
            "</status>"
        )

        status = udp_client._parse_status(root)

        self.assertEqual(status["target_temp"], 22.8)
        self.assertEqual(status["current_temp"], 29.4)
        self.assertEqual(status["outdoor_temp"], 30.0)

    def test_celsius_mapping_round_trips_within_half_degree_step(self) -> None:
        client = object.__new__(self.api.TclUdpApiClient)

        for temp_c in (16, 20.5, 23, 23.5, 25.5, 30.5, 31):
            temp_int, degree_half = client._map_set_temp(temp_c)
            round_trip_c = round(
                client._fahrenheit_to_celsius(temp_int) + 0.5 * degree_half,
                1,
            )

            self.assertLessEqual(abs(round_trip_c - temp_c), 0.25, temp_c)


if __name__ == "__main__":
    unittest.main()
