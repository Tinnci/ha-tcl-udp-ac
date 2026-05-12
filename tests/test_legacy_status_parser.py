"""Profile-aware legacy status parser tests."""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from tests.test_protocol_commands import load_integration_module


class LegacyStatusParserTest(unittest.TestCase):
    """Legacy profile should own baseMode=0 interpretation."""

    def setUp(self) -> None:
        self.api = load_integration_module("api")
        self.udp_client = load_integration_module("udp_client")
        self.profiles = load_integration_module("protocol_profiles")
        self.const = load_integration_module("const")

    def test_cloud_legacy_base_mode_zero_maps_to_fan(self) -> None:
        client = self.api.CloudClient(
            session=None,
            enabled=False,
            tid="2743138",
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

        status = client._parse_cloud_status({"baseMode": "0"})

        self.assertEqual(status["mode"], self.const.MODE_FAN)

    def test_default_cloud_base_mode_zero_remains_unknown(self) -> None:
        client = self.api.CloudClient(
            session=None,
            enabled=False,
            tid="other",
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

        status = client._parse_cloud_status({"baseMode": "0"})

        self.assertNotIn("mode", status)

    def test_udp_legacy_base_modes_map_to_supported_modes(self) -> None:
        udp = self.udp_client.UdpClient(
            "user@tcl.com/PH-android-zx01-2",
            "1",
            "user",
            protocol_profile=self.profiles.resolve_protocol_profile("2743138"),
        )

        for base_mode, expected in {
            "0": self.const.MODE_FAN,
            "1": self.const.MODE_COOL,
            "2": self.const.MODE_DEHUMI,
            "4": self.const.MODE_HEAT,
        }.items():
            root = ET.fromstring(f"<status><baseMode>{base_mode}</baseMode></status>")
            self.assertEqual(udp._parse_status(root)["mode"], expected)

    def test_legacy_base_mode_seven_and_eight_are_unknown(self) -> None:
        profile = self.profiles.resolve_protocol_profile("2743138")

        self.assertIsNone(profile.parse_base_mode("7"))
        self.assertIsNone(profile.parse_base_mode("8"))

    def test_cloud_legacy_base_mode_seven_and_eight_do_not_fallback(self) -> None:
        client = self.api.CloudClient(
            session=None,
            enabled=False,
            tid="2743138",
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

        self.assertNotIn("mode", client._parse_cloud_status({"baseMode": "7"}))
        self.assertNotIn("mode", client._parse_cloud_status({"baseMode": "8"}))

    def test_udp_legacy_base_mode_seven_and_eight_do_not_fallback(self) -> None:
        udp = self.udp_client.UdpClient(
            "user@tcl.com/PH-android-zx01-2",
            "1",
            "user",
            protocol_profile=self.profiles.resolve_protocol_profile("2743138"),
        )

        for base_mode in ("7", "8"):
            root = ET.fromstring(f"<status><baseMode>{base_mode}</baseMode></status>")
            self.assertNotIn("mode", udp._parse_status(root))


if __name__ == "__main__":
    unittest.main()
