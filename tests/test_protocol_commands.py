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
                "fan_gear": 0,
                "aux_heat_active": True,
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
        self.assertEqual(status["fan_speed"], "2")

    def test_tsl_cloud_status_preserves_all_observed_diagnostics(self) -> None:
        status = self.client._parse_cloud_status(
            {
                "errorCode": [52, 3, 99],
                "internalUnitCoilTemperature": 25,
                "externalUnitCoilTemperature": 20,
                "externalUnitExhaustTemperature": 49,
                "externalUnitVoltage": 225,
                "externalUnitElectricCurrent": 1.5,
                "compressorFrequency": 42,
                "internalUnitFanSpeed": 700,
                "externalUnitFanSpeed": 800,
                "internalUnitFanCurrentGear": 3,
                "externalUnitFanGear": 4,
                "windSpeedPercentage": 85,
                "newWindSetMode": 1,
                "newWindPercentage": 33,
                "sleepTime": 120,
                "selfCleanStatus": 6,
                "expansionValve ": 302,
                "tslLatestVersion": "V3.0.0",
                "tslReqVersion": "V2.0.0",
                "tslQueryTime": 1787583278199,
                "aiSmartControlSource": "APP",
                "filterBlockStatus": 1,
                "fourWayValveStatus": 1,
                "PTCStatus": 1,
                "selfLearn": 1,
                "beepTempEn": 1,
                "antiMoldew": 1,
                "softWind": 1,
                "selfClean": 1,
                "newWindAutoSwitch": 1,
            }
        )

        expected = {
            "error_codes": "E1, E3, 99",
            "internal_coil_temperature": 25,
            "external_coil_temperature": 20,
            "external_exhaust_temperature": 49,
            "external_voltage": 225,
            "external_current": 1.5,
            "compressor_frequency": 42,
            "internal_fan_speed": 700,
            "external_fan_speed": 800,
            "internal_fan_gear": 3,
            "external_fan_gear": 4,
            "wind_speed_percentage": 85,
            "fresh_air_mode": 1,
            "fresh_air_percentage": 33,
            "sleep_time": 120,
            "self_clean_status": 6,
            "expansion_valve": 302,
            "tsl_version": "V3.0.0",
            "tsl_request_version": "V2.0.0",
            "ai_control_source": "APP",
            "filter_blocked": True,
            "four_way_valve_active": True,
            "aux_heat_active": True,
            "self_learning": True,
            "beep_temperature": True,
            "anti_mildew": True,
            "soft_wind": True,
            "self_clean": True,
            "fresh_air_auto": True,
        }
        for key, value in expected.items():
            self.assertEqual(status[key], value)
        self.assertEqual(status["tsl_query_time"].timestamp(), 1787583278.199)

    def test_tsl_ascii_zero_error_marker_means_no_fault(self) -> None:
        status = self.client._parse_cloud_status({"errorCode": [48]})

        self.assertEqual(status["error_codes"], "none")

    def test_tsl_status_uses_native_thing_status_endpoint(self) -> None:
        calls = []

        class Response:
            status = 200

            async def text(self):
                return '{"code":200,"data":{"status":{"powerSwitch":1}}}'

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

        class Session:
            def post(self, url, **kwargs):
                calls.append((url, kwargs))
                return Response()

        client = self._tsl_cloud_client()
        client._session = Session()

        status = asyncio.run(client.async_fetch_status())

        self.assertEqual(status["power"], True)
        self.assertEqual(calls[0][0], "https://io.zx.tcljd.com/v1/thing/status")
        self.assertEqual(calls[0][1]["json"], {"deviceId": "45816970"})

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
        bundles = load_integration_module("command_bundles")

        async def fake_send_commands(self, items):
            calls.append(items)
            return bundles.TransportDelivery()

        client.async_send_commands = MethodType(fake_send_commands, client)

        asyncio.run(client.async_set_sleep_mode(enabled=True))
        asyncio.run(client.async_set_sleep_mode(enabled=False))

        self.assertEqual(
            calls,
            [
                [("Opt_sleepMode", "1")],
                [("Opt_sleepMode", "0")],
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

        receipt = asyncio.run(client.async_send_command_bundle(bundle))

        self.assertEqual(property_calls, [bundle])
        self.assertEqual(legacy_calls, [])
        self.assertEqual(
            receipt.expected_status,
            {"target_temp": 25.5},
        )
        self.assertEqual(receipt.delivery.outcome, "accepted_by_cloud")

    def test_tsl_bundle_send_failure_does_not_record_pending_confirmation(
        self,
    ) -> None:
        profiles = load_integration_module("protocol_profiles")
        client = object.__new__(self.api.TclUdpApiClient)

        class FakeCloud:
            async def async_send_tsl_property_bundle(self, bundle):
                return False

        client._cloud = FakeCloud()
        bundle = profiles.resolve_protocol_profile(
            "45816970",
            product_key="1112013595N",
        ).build_temperature_command(25.5)

        receipt = asyncio.run(client.async_send_command_bundle(bundle))

        self.assertFalse(receipt.delivery.accepted)

    def test_tsl_profile_skips_every_local_udp_operation(self) -> None:
        profiles = load_integration_module("protocol_profiles")
        client = object.__new__(self.api.TclUdpApiClient)
        client._protocol_profile = profiles.resolve_protocol_profile(
            "45816970", product_key="1112013595N"
        )
        calls = []

        class Udp:
            async def async_start_listener(self, _callback):
                calls.append("listen")

            async def async_stop_listener(self):
                calls.append("stop")

            async def async_send_discovery(self):
                calls.append("discover")

            async def async_request_status(self):
                calls.append("status")

        client._udp = Udp()

        async def run_case():
            await client.async_start_listener(lambda _status: None)
            await client.async_send_discovery()
            await client.async_request_status()
            await client.async_stop_listener()

        asyncio.run(run_case())
        self.assertEqual(calls, [])

    def test_tsl_profile_emits_property_fan_and_swing_commands(self) -> None:
        profiles = load_integration_module("protocol_profiles")
        client = object.__new__(self.api.TclUdpApiClient)
        client._protocol_profile = profiles.resolve_protocol_profile(
            "45816970",
            product_key="1112013595N",
        )
        property_calls = []

        class FakeCloud:
            async def async_send_tsl_property_bundle(self, bundle):
                property_calls.append(bundle)
                return True

        client._cloud = FakeCloud()

        fan_receipt = asyncio.run(client.async_set_fan_speed("7"))
        swing_receipt = asyncio.run(
            client.async_set_swing(vertical=True, horizontal=True)
        )

        self.assertEqual(
            property_calls[0].payload, {"windSpeedAutoSwitch": 0, "windSpeed7Gear": 7}
        )
        self.assertEqual(
            property_calls[1].payload,
            {"verticalDirection": 1, "horizontalDirection": 1},
        )
        self.assertTrue(fan_receipt.delivery.accepted)
        self.assertTrue(swing_receipt.delivery.accepted)


class ToolProtocolMappingTest(unittest.TestCase):
    """Standalone test tools should use the same protocol values."""

    def test_heat_mode_uses_live_verified_base_mode_value(self) -> None:
        from tools import test_control_api

        self.assertEqual(test_control_api.MODE_MAP["heat"], "4")


if __name__ == "__main__":
    unittest.main()
