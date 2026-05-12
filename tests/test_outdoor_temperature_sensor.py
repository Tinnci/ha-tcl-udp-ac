"""Outdoor temperature sensor behavior tests."""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from types import SimpleNamespace

from tests.ha_stubs import install_homeassistant_stubs
from tests.test_protocol_commands import load_integration_module


install_homeassistant_stubs()


class OutdoorTemperatureSensorTest(unittest.TestCase):
    """Outdoor temperature should not expose protocol placeholder values."""

    def setUp(self) -> None:
        self.sensor_mod = load_integration_module("sensor")
        self.api_mod = load_integration_module("api")
        self.udp_mod = load_integration_module("udp_client")

    def make_sensor(self, data: dict):
        coordinator = SimpleNamespace(
            data=data,
            config_entry=SimpleNamespace(entry_id="entry-1", domain="tcl_udp_ac"),
        )
        return self.sensor_mod.TclUdpOutdoorTempSensor(coordinator)

    def test_sensor_is_unavailable_when_reading_is_missing(self) -> None:
        entity = self.make_sensor({})

        self.assertFalse(entity.available)
        self.assertIsNone(entity.native_value)

    def test_sensor_is_unavailable_for_zero_celsius_placeholder(self) -> None:
        entity = self.make_sensor({"outdoor_temp": 0.0})

        self.assertFalse(entity.available)
        self.assertIsNone(entity.native_value)

    def test_sensor_remains_available_for_real_outdoor_temperature(self) -> None:
        entity = self.make_sensor({"outdoor_temp": 30.0})

        self.assertTrue(entity.available)
        self.assertEqual(entity.native_value, 30.0)

    def test_cloud_status_skips_outdoor_temperature_placeholder(self) -> None:
        client = self.api_mod.CloudClient(
            session=None,
            enabled=False,
            tid=None,
            token=None,
            from_jid=None,
            to_jid=None,
            base_url="https://io.zx.tcljd.com",
            control_enabled=False,
            headers=self.api_mod.CloudHeaderProfile(
                platform="android",
                user_agent="ua",
                app_package="pkg",
                system_version="16",
                brand="brand",
                app_version="4.0.9",
                sdk_version="6.0.3",
                channel="xiaomi",
                app_build_version="4.0.9.0",
                t_app_version="4.0.9.0",
                t_platform_type="Android",
                t_store_uuid="TCL+",
                origin="https://h5.zx.tcljd.com",
                x_requested_with="com.tcl.tclplus",
                accept="text/plain",
                accept_encoding="gzip",
                accept_language="zh-CN",
            ),
        )

        self.assertNotIn("outdoor_temp", client._parse_cloud_status({"outTemp": "32"}))

    def test_udp_status_skips_outdoor_temperature_placeholder(self) -> None:
        client = self.udp_mod.UdpClient("jid", "1", "account")
        root = ET.fromstring("<status><OutTemp>32</OutTemp></status>")

        self.assertNotIn("outdoor_temp", client._parse_status(root))


if __name__ == "__main__":
    unittest.main()
