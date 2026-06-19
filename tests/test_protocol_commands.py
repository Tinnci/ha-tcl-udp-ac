"""Protocol command mapping tests for TCL UDP AC."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import MethodType

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "custom_components.tcl_udp_ac"


def load_integration_module(name: str):
    """Load an integration module without importing Home Assistant package init."""
    if "aiohttp" not in sys.modules:
        aiohttp = types.ModuleType("aiohttp")
        aiohttp.ClientError = Exception
        aiohttp.ClientSession = object
        sys.modules["aiohttp"] = aiohttp

    if "custom_components" not in sys.modules:
        package_root = types.ModuleType("custom_components")
        package_root.__path__ = [str(ROOT / "custom_components")]
        sys.modules["custom_components"] = package_root

    if PACKAGE not in sys.modules:
        package = types.ModuleType(PACKAGE)
        package.__path__ = [str(ROOT / "custom_components" / "tcl_udp_ac")]
        sys.modules[PACKAGE] = package

    full_name = f"{PACKAGE}.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]

    path = ROOT / "custom_components" / "tcl_udp_ac" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(full_name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    assert spec.loader is not None
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(full_name, None)
        raise
    return module


class CloudProtocolMappingTest(unittest.TestCase):
    """Cloud payload mapping should match captured TCL app requests."""

    def setUp(self) -> None:
        self.api = load_integration_module("api")
        self.client = self.api.CloudClient(
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

    def test_heat_mode_maps_to_captured_base_mode_value(self) -> None:
        self.assertEqual(
            self.client._map_cloud_item("BaseMode", "heat"), ("baseMode", "4")
        )

    def test_sleep_mode_switch_uses_numeric_cloud_value(self) -> None:
        self.assertEqual(
            self.client._map_cloud_item("Opt_sleepMode", "on"), ("optSleepMd", "1")
        )
        self.assertEqual(
            self.client._map_cloud_item("Opt_sleepMode", "off"), ("optSleepMd", "0")
        )

    def test_solid_wind_can_be_cleared_with_swing_commands(self) -> None:
        self.assertEqual(
            self.client._map_cloud_item("OptSolidWd", "off"), ("optSolidWd", "0")
        )

    def test_tsl_cloud_status_maps_protocol_one_fields(self) -> None:
        status = self.client._parse_cloud_status(
            {
                "powerSwitch": 1,
                "workMode": 1,
                "targetTemperature": 23.5,
                "currentTemperature": 27.7,
                "externalUnitTemperature": 32,
                "windSpeedAutoSwitch": 1,
                "windSpeed7Gear": 0,
                "ECO": 1,
                "sleep": 0,
                "screen": 1,
                "beepSwitch": 1,
                "healthy": 0,
                "turbo": 0,
                "PTCStatus": 1,
                "horizontalDirection": 1,
                "verticalDirection": 8,
            }
        )

        self.assertEqual(
            status,
            {
                "power": True,
                "target_temp": 23.5,
                "current_temp": 27.7,
                "outdoor_temp": 32.0,
                "fan_speed": "auto",
                "mode": "cool",
                "swing_h": True,
                "swing_v": False,
                "eco_mode": True,
                "sleep_mode": False,
                "turbo_mode": False,
                "aux_heat": True,
                "health_mode": False,
                "display": True,
                "beep": True,
            },
        )

    def test_tsl_cloud_status_maps_dry_and_seven_gear_fan_speed(self) -> None:
        status = self.client._parse_cloud_status(
            {
                "powerSwitch": 0,
                "workMode": 2,
                "targetTemperature": 27.5,
                "currentTemperature": 27.7,
                "windSpeedAutoSwitch": 0,
                "windSpeed7Gear": 2,
            }
        )

        self.assertEqual(status["power"], False)
        self.assertEqual(status["mode"], "dehumi")
        self.assertEqual(status["target_temp"], 27.5)
        self.assertEqual(status["current_temp"], 27.7)
        self.assertEqual(status["fan_speed"], "low")

    def _tsl_cloud_client(self):
        return self.api.CloudClient(
            session=None,
            enabled=True,
            tid="45816970",
            token="token",
            from_jid=None,
            to_jid=None,
            base_url="https://io.zx.tcljd.com",
            control_enabled=True,
            headers=self.api.CloudHeaderProfile(
                platform="android",
                user_agent="ua",
                app_package="pkg",
                system_version="16",
                brand="brand",
                app_version="4.1.3",
                sdk_version="6.0.4",
                channel="xiaomi",
                app_build_version="4.1.3.0",
                t_app_version="4.1.3.0",
                t_platform_type="Android",
                t_store_uuid="TCL+",
                origin="https://h5.zx.tcljd.com",
                x_requested_with="com.tcl.tclplus",
                accept="text/plain",
                accept_encoding="gzip",
                accept_language="zh-CN",
            ),
            product_key="1112013595N",
        )

    def test_tsl_temperature_property_request_matches_native_card_shape(self) -> None:
        profiles = load_integration_module("protocol_profiles")
        bundle = profiles.resolve_protocol_profile(
            "45816970",
            product_key="1112013595N",
        ).build_temperature_command(25.5)
        client = self._tsl_cloud_client()

        payload = client._build_tsl_property_payload(bundle)

        self.assertEqual(
            client._tsl_property_url(bundle),
            "https://io.zx.tcljd.com/v1/tclplus/property/45816970",
        )
        self.assertEqual(payload["version"], "1.0")
        self.assertEqual(payload["source"], "APP")
        self.assertEqual(payload["params"], [{"targetTemperature": 25.5}])
        self.assertNotIn("moduleId", payload)

    def test_tsl_mode_property_request_uses_control_property_source_type(self) -> None:
        profiles = load_integration_module("protocol_profiles")
        bundle = profiles.resolve_protocol_profile(
            "45816970",
            product_key="1112013595N",
        ).build_mode_command("cool", target_temperature=23)
        client = self._tsl_cloud_client()

        headers = client._build_tsl_property_headers(bundle)

        self.assertEqual(
            client._tsl_property_url(bundle),
            "https://io.zx.tcljd.com/v1/control/property/45816970",
        )
        self.assertEqual(headers["sourceType"], "2")
        self.assertEqual(headers["accesstoken"], "token")
        self.assertEqual(
            client._build_tsl_property_payload(bundle)["params"],
            [{"powerSwitch": 1, "workMode": 1, "targetTemperature": 23.0}],
        )


class EntityCommandTest(unittest.TestCase):
    """High-level entity commands should emit app-compatible command groups."""

    def setUp(self) -> None:
        self.api = load_integration_module("api")

    def test_sleep_mode_switch_emits_numeric_values(self) -> None:
        client = object.__new__(self.api.TclUdpApiClient)
        calls = []

        async def fake_send_command(self, command, value, degree_half=None):
            calls.append((command, value, degree_half))

        client.async_send_command = MethodType(fake_send_command, client)

        asyncio.run(client.async_set_sleep_mode(enabled=True))
        asyncio.run(client.async_set_sleep_mode(enabled=False))

        self.assertEqual(
            calls,
            [
                ("Opt_sleepMode", "1", None),
                ("Opt_sleepMode", "0", None),
            ],
        )

    def test_swing_command_clears_solid_wind_mode(self) -> None:
        client = object.__new__(self.api.TclUdpApiClient)
        calls = []

        async def fake_send_commands(self, items):
            calls.append(items)

        client.async_send_commands = MethodType(fake_send_commands, client)

        asyncio.run(client.async_set_swing(vertical=True, horizontal=False))

        self.assertEqual(
            calls,
            [
                [
                    ("WindDirection_V", "on"),
                    ("WindDirection_H", "off"),
                    ("OptSolidWd", "off"),
                ]
            ],
        )

    def test_power_off_uses_app_shutdown_group(self) -> None:
        client = object.__new__(self.api.TclUdpApiClient)
        calls = []

        async def fake_send_commands(self, items):
            calls.append(items)

        client.async_send_commands = MethodType(fake_send_commands, client)

        asyncio.run(client.async_set_power(power=False))

        self.assertEqual(
            calls,
            [
                [
                    ("Opt_sleepMode", "0"),
                    ("Opt_ECO", "0"),
                    ("OptHealthy", "0"),
                    ("Opt_super", "0"),
                    ("OptHeat", "0"),
                    ("TurnOn", "0"),
                ]
            ],
        )

    def test_tsl_bundle_routes_to_property_cloud_without_legacy_commands(self) -> None:
        profiles = load_integration_module("protocol_profiles")
        client = object.__new__(self.api.TclUdpApiClient)
        client._pending_command_confirmation = None
        legacy_calls = []
        property_calls = []

        class FakeCloud:
            async def async_send_tsl_property_bundle(self, bundle):
                property_calls.append(bundle)
                return True

        async def fake_send_commands(self, items):
            legacy_calls.append(items)

        client._cloud = FakeCloud()
        client.async_send_commands = MethodType(fake_send_commands, client)
        bundle = profiles.resolve_protocol_profile(
            "45816970",
            product_key="1112013595N",
        ).build_temperature_command(25.5)

        asyncio.run(client.async_send_command_bundle(bundle))

        self.assertEqual(property_calls, [bundle])
        self.assertEqual(legacy_calls, [])
        self.assertEqual(
            client.pending_command_confirmation()["expected_status"],
            {"target_temp": 25.5},
        )

    def test_tsl_bundle_send_failure_does_not_record_pending_confirmation(
        self,
    ) -> None:
        profiles = load_integration_module("protocol_profiles")
        client = object.__new__(self.api.TclUdpApiClient)
        client._pending_command_confirmation = None

        class FakeCloud:
            async def async_send_tsl_property_bundle(self, bundle):
                return False

        client._cloud = FakeCloud()
        bundle = profiles.resolve_protocol_profile(
            "45816970",
            product_key="1112013595N",
        ).build_temperature_command(25.5)

        asyncio.run(client.async_send_command_bundle(bundle))

        self.assertIsNone(client.pending_command_confirmation())

    def test_tsl_profile_blocks_unmapped_fan_and_swing_commands(self) -> None:
        profiles = load_integration_module("protocol_profiles")
        client = object.__new__(self.api.TclUdpApiClient)
        client._pending_command_confirmation = None
        client._protocol_profile = profiles.resolve_protocol_profile(
            "45816970",
            product_key="1112013595N",
        )
        calls = []

        async def fake_send_commands(self, items):
            calls.append(items)

        client.async_send_commands = MethodType(fake_send_commands, client)

        asyncio.run(client.async_set_fan_speed("high"))
        asyncio.run(client.async_set_swing(vertical=True, horizontal=True))

        self.assertEqual(calls, [])
        self.assertIsNone(client.pending_command_confirmation())


class ToolProtocolMappingTest(unittest.TestCase):
    """Standalone test tools should use the same protocol values."""

    def test_heat_mode_uses_live_verified_base_mode_value(self) -> None:
        from tools import test_control_api

        self.assertEqual(test_control_api.MODE_MAP["heat"], "4")


if __name__ == "__main__":
    unittest.main()
