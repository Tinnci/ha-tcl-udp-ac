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
        self.assertEqual(self.client._map_cloud_item("BaseMode", "heat"), ("baseMode", "4"))

    def test_sleep_mode_switch_uses_numeric_cloud_value(self) -> None:
        self.assertEqual(self.client._map_cloud_item("Opt_sleepMode", "on"), ("optSleepMd", "1"))
        self.assertEqual(self.client._map_cloud_item("Opt_sleepMode", "off"), ("optSleepMd", "0"))

    def test_solid_wind_can_be_cleared_with_swing_commands(self) -> None:
        self.assertEqual(self.client._map_cloud_item("OptSolidWd", "off"), ("optSolidWd", "0"))


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
            [[
                ("WindDirection_V", "on"),
                ("WindDirection_H", "off"),
                ("OptSolidWd", "off"),
            ]],
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
            [[
                ("Opt_sleepMode", "0"),
                ("Opt_ECO", "0"),
                ("OptHealthy", "0"),
                ("Opt_super", "0"),
                ("OptHeat", "0"),
                ("TurnOn", "0"),
            ]],
        )


class ToolProtocolMappingTest(unittest.TestCase):
    """Standalone test tools should use the same protocol values."""

    def test_heat_mode_uses_live_verified_base_mode_value(self) -> None:
        from tools import test_control_api

        self.assertEqual(test_control_api.MODE_MAP["heat"], "4")


if __name__ == "__main__":
    unittest.main()
